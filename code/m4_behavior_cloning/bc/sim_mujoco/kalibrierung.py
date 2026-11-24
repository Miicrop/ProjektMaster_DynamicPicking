"""Kameralage fuer die MuJoCo-Szene aus den Referenzbildern (Phase 0).

Die vier ArUco-Marker der Tischplatte (``config/system.yaml``, 400 mm
Mittenabstand, 50 mm Kantenlaenge) liegen in den Vollbild-Referenzbildern
jedes Aufrufs (``data/2026-11-19/referenzbilder``). Aus ihren 16 Ecken wird
je Kamera geschaetzt:

* **Szenenkamera:** Lage im Basis-KS, Brennweite, eine radiale Verzerrung.
* **Wrist-Kamera:** dasselbe, aber die Lage relativ zum Werkzeug-KS -- die
  Referenzbilder entstehen beim Start des Aufrufs, der Arm steht dann an
  ``CLEAR_FOV`` (geprueft: die Bilder von B33, B51, B62, B66 und B116 zeigen
  die Marker an denselben Pixeln).

Kameramodell (nur so genau, wie die Taktiksimulation es braucht): Strahl
mit Winkel ``theta`` zur optischen Achse landet im Abstand ``r`` von der
Bildmitte,

    fisheye:  r = f * theta * (1 + k1 * theta^2)            (aequidistant)
    pinhole:  r = f * tan(theta) * (1 + k1 * tan(theta)^2)  (rektilinear)

Bildmitte fest in der Sensormitte. Je Kamera werden beide Modelle gerechnet,
das mit dem kleineren Restfehler gilt. Ergebnis: Abschnitt ``kameras`` in
``bc/sim_mujoco/parameter.json``.

Aufruf (aus ``code/m4_behavior_cloning``)::

    python -m bc.sim_mujoco.kalibrierung            # rechnen und anzeigen
    python -m bc.sim_mujoco.kalibrierung --schreiben  # parameter.json aktualisieren
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .. import geometry
from . import parameter as params

#: Marker der Tischplatte (config/system.yaml, workspace.markers_mm) im
#: Arbeitsraum-KS in mm, dazu die Abbildung Arbeitsraum -> Roboterbasis.
MARKER_WS_MM = {0: (-35.0, -35.0), 1: (365.0, -35.0), 2: (365.0, 365.0), 3: (-35.0, 365.0)}
WS_TO_ROBOT_DEG = 0.35
WS_TO_ROBOT_MM = (205.1, -319.7)
MARKER_SIZE_M = 0.050


def marker_centers(table_height):
    """Markermitten im Basis-KS (m); z aus der geteachten Tischebene."""
    a = math.radians(WS_TO_ROBOT_DEG)
    c, s = math.cos(a), math.sin(a)
    out = {}
    for mid, (x, y) in MARKER_WS_MM.items():
        xr = (c * x - s * y + WS_TO_ROBOT_MM[0]) / 1000.0
        yr = (s * x + c * y + WS_TO_ROBOT_MM[1]) / 1000.0
        out[mid] = np.array([xr, yr, table_height(xr, yr)])
    return out


def marker_corners(center, turn):
    """Vier Ecken in ArUco-Reihenfolge (oben links, oben rechts, unten rechts,
    unten links im Markerbild). ``turn`` (0..3): wie der Marker auf dem Tisch
    liegt, in 90-Grad-Schritten -- wird beim Anpassen bestimmt."""
    h = MARKER_SIZE_M / 2.0
    base = [(-h, h), (h, h), (h, -h), (-h, -h)]
    base = base[turn:] + base[:turn]
    return np.array([center + np.array([dx, dy, 0.0]) for dx, dy in base])


def detect(path):
    """ArUco-Ecken eines Bildes: {id: (4, 2)} und Bildgroesse (w, h).

    ``path``: Bilddatei oder schon geladenes Bild (ndarray, BGR oder RGB --
    der Detektor arbeitet auf Grauwerten)."""
    import cv2

    image = path if isinstance(path, np.ndarray) else cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(path)
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image)
    found = {}
    if ids is not None:
        for mid, c in zip(ids.ravel(), corners):
            if int(mid) in MARKER_WS_MM:
                found[int(mid)] = c[0].astype(float)
    return found, (image.shape[1], image.shape[0])


def project(points_cam, f, k1, size, model, k2=0.0):
    """Kamera-KS (OpenCV: x rechts, y unten, z Blickrichtung) -> Pixel."""
    x, y, z = points_cam[:, 0], points_cam[:, 1], points_cam[:, 2]
    rho = np.hypot(x, y)
    theta = np.arctan2(rho, z)
    if model == "fisheye":
        r = f * theta * (1.0 + k1 * theta ** 2 + k2 * theta ** 4)
    else:
        t = np.tan(np.minimum(theta, 1.5))
        r = f * t * (1.0 + k1 * t ** 2 + k2 * t ** 4)
    scale = np.where(rho > 1e-12, r / np.maximum(rho, 1e-12), 0.0)
    cx, cy = size[0] / 2.0, size[1] / 2.0
    return np.stack([cx + scale * x, cy + scale * y], axis=1)


def _rodrigues(rvec):
    angle = float(np.linalg.norm(rvec))
    if angle < 1e-12:
        return np.eye(3)
    k = rvec / angle
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * K @ K


def _rvec(R):
    q = geometry.matrix_to_quat(R)
    w = max(-1.0, min(1.0, float(q[0])))
    angle = 2 * math.acos(w)
    if angle < 1e-12:
        return np.zeros(3)
    return np.asarray(q[1:4]) / math.sin(angle / 2) * angle


def fit_camera(observed, world_corners, size, R0, p0, f0, model, fit_k2=False, f_fixed=None):
    """Kleinste Quadrate ueber Lage (Kamera im Basis-KS), f, k1 (und k2).

    ``f_fixed``: Brennweite fest (Pixel), z. B. aus Objektiv und Pixelgroesse.

    ``observed``/``world_corners``: (N, 2) Pixel und (N, 3) Weltpunkte.
    ``R0``/``p0``: Startwert Welt <- Kamera (Spalten = Kameraachsen in Welt).
    Rueckgabe dict mit R (Welt <- Kamera), p, f, k1, rms_px.
    """
    from scipy.optimize import least_squares

    if f_fixed is not None:
        f0 = float(f_fixed)

    def unpack(x):
        R = _rodrigues(x[:3]) @ R0
        f = f0 if f_fixed is not None else f0 * math.exp(x[6])
        k2 = x[8] if fit_k2 else 0.0
        return R, p0 + x[3:6], f, x[7], k2

    def residual(x):
        R, p, f, k1, k2 = unpack(x)
        cam = (world_corners - p) @ R  # = R^T (w - p)
        if np.any(cam[:, 2] <= 0.01):
            return np.full(observed.size, 1e3)
        return (project(cam, f, k1, size, model, k2) - observed).ravel()

    res = least_squares(residual, np.zeros(9),
                        x_scale=[0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.2, 0.05, 0.05])
    R, p, f, k1, k2 = unpack(res.x)
    rms = float(np.sqrt(np.mean(res.fun.reshape(-1, 2) ** 2) * 2))
    return {"R": R, "p": p, "f": f, "k1": float(k1), "k2": float(k2), "rms_px": rms,
            "model": model, "f_fest": f_fixed is not None}


#: Modellvarianten: (Modell, k2 anpassen, f fest)
VARIANTS_FREE = (("fisheye", False, None), ("pinhole", False, None))

#: Wrist-Objektiv laut Anwender 2026-11-20: 3,6 mm, F8.0 (kein Fisheye --
#: config.py und Kamera-Inbetriebnahme.md nennen noch das alte Fisheye 1,85 mm).
#: Daheng VEN-161-61U3C: 3,45 um Pixel -> f = 3,6 mm / 3,45 um ~ 1043 px im
#: Vollbild 1440 x 1080 (~69 Grad horizontal).
WRIST_LENS_MM = 3.6
PIXEL_UM = 3.45
WRIST_F_NOMINAL_PX = WRIST_LENS_MM / (PIXEL_UM * 1e-3)
#: Varianten fuer die Wrist-Kamera: das alte Fisheye nur zum Vergleich, gewaehlt
#: wird die beste Lochkamera
WRIST_VARIANTS = (("fisheye", False, None), ("pinhole", False, None),
                  ("pinhole", True, None), ("pinhole", True, WRIST_F_NOMINAL_PX))
WRIST_MODEL = "pinhole"


def best_fit(found, centers, size, R0, p0, f0, variants=VARIANTS_FREE, results=None):
    """Markerdrehung je Marker und Modell waehlen, dann alle Ecken anpassen.

    ``variants``: Folge (Modell, k2, f_fest). Gewinner = kleinster Rest;
    ``results`` (Liste) sammelt alle Varianten fuer den Vergleich."""
    ids = sorted(found)
    best = None
    for model, fit_k2, f_fixed in variants:
        # 1. nur Mitten: Lage grob
        obs_c = np.array([found[i].mean(axis=0) for i in ids])
        wc = np.array([centers[i] for i in ids])
        first = fit_camera(obs_c, wc, size, R0, p0, f0, model, f_fixed=f_fixed)
        # 2. Drehung je Marker: die Ecke, die am besten passt
        turns = {}
        for i in ids:
            errs = []
            for turn in range(4):
                cam = (marker_corners(centers[i], turn) - first["p"]) @ first["R"]
                pix = project(cam, first["f"], first["k1"], size, model)
                errs.append(float(np.sum((pix - found[i]) ** 2)))
            turns[i] = int(np.argmin(errs))
        obs = np.concatenate([found[i] for i in ids])
        wpts = np.concatenate([marker_corners(centers[i], turns[i]) for i in ids])
        fit = fit_camera(obs, wpts, size, first["R"], first["p"], first["f"], model,
                         fit_k2=fit_k2, f_fixed=f_fixed)
        fit["turns"] = turns
        if results is not None:
            results.append(fit)
        if best is None or fit["rms_px"] < best["rms_px"]:
            best = fit
    return best


def _table_height_fn(meta):
    from ..table import TablePlane

    plane = TablePlane.from_dict(meta["table"])
    return lambda x, y: plane.height_at(x, y) - plane.correction_at(x, y)


def estimate(data_root, wrist_pose_point="CLEAR_FOV", verbose=True):
    """Beide Kameras aus den Referenzbildern einer Aufnahme schaetzen."""
    from ..urdf import KinematicChain
    from .. import config

    data_root = Path(data_root)
    meta = None
    for meta_path in sorted(data_root.glob("ep_*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))["metadata"]
        if meta.get("table") and meta.get("points"):
            break
    centers = marker_centers(_table_height_fn(meta))
    refs = sorted((data_root / "referenzbilder").glob("*_scene.png"))
    out = {}

    # -- Szenenkamera: alle Bilder mit 4 Markern, Ecken gemittelt (die Kamera
    # steht fest; der Mittelwert daempft das Detektorrauschen)
    stacks = {}
    for path in refs:
        found, size = detect(path)
        if len(found) == 4:
            for i, c in found.items():
                stacks.setdefault(i, []).append(c)
    found = {i: np.mean(v, axis=0) for i, v in stacks.items()}
    # Start: ueber der Tischmitte, Bild-oben = +x, Bild-rechts = -y
    R0 = np.column_stack([[0, -1, 0], [-1, 0, 0], [0, 0, -1]]).astype(float)
    mid = np.mean([centers[i] for i in centers], axis=0)
    fit = best_fit(found, centers, size, R0, mid + np.array([0, 0, 0.9]), 1200.0)
    out["scene"] = _as_entry(fit, size, n_images=len(stacks.get(0, [])))
    if verbose:
        print("Szene:", _describe(out["scene"]))

    # -- Wrist-Kamera an CLEAR_FOV: Lage relativ zum Werkzeug
    chain = KinematicChain.from_urdf(config.URDF_PATH)
    tool = np.eye(4)
    tool[:3, 3] = params.load()["werkzeug"]["tcp_versatz_m"]
    q = np.asarray(meta["points"][wrist_pose_point]["joints"], dtype=float)
    T_tool = chain.fk(q) @ tool
    stacks = {}
    for path in sorted((data_root / "referenzbilder").glob("*_wrist.png")):
        found, size = detect(path)
        if len(found) == 4:
            for i, c in found.items():
                stacks.setdefault(i, []).append(c)
    found = {i: np.mean(v, axis=0) for i, v in stacks.items()}
    # Start: Kamera dort, wo hindernisse.json sie vermutet, Blick laengs
    # Werkzeug-z; Drehung um die Achse aus vier Versuchen
    offset = np.array(params.load()["kameras"]["wrist"]["start_versatz_werkzeug_m"])
    p0 = T_tool[:3, :3] @ offset + T_tool[:3, 3]
    best = None
    per_variant = {}
    for k in range(4):
        a = k * math.pi / 2
        Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        for variant in WRIST_VARIANTS:
            fit = best_fit(found, centers, size, T_tool[:3, :3] @ Rz, p0, WRIST_F_NOMINAL_PX,
                           variants=(variant,))
            if variant not in per_variant or fit["rms_px"] < per_variant[variant]["rms_px"]:
                per_variant[variant] = fit
    if verbose:
        print("Wrist-Objektiv, Rest der Markerecken je Modell (Vollbild 1440 x 1080):")
    for (model, k2, f_fixed), fit in per_variant.items():
        if verbose:
            print("   %-8s k2 %-4s f %-5s -> f %6.0f px, k1 %+.4f, k2 %+.4f, Rest %.2f px"
                  % (model, "ja" if k2 else "nein", "fest" if f_fixed else "frei",
                     fit["f"], fit["k1"], fit["k2"], fit["rms_px"]))
        if model == WRIST_MODEL and (best is None or fit["rms_px"] < best["rms_px"]):
            best = fit
    vergleich = [{"modell": m, "k2": bool(k2), "f_fest": bool(ff), "f_px": round(float(f["f"]), 1),
                  "k1": round(f["k1"], 5), "k2_wert": round(f["k2"], 5), "rest_px": round(f["rms_px"], 2)}
                 for (m, k2, ff), f in per_variant.items()]
    T_cam = np.eye(4)
    T_cam[:3, :3], T_cam[:3, 3] = best["R"], best["p"]
    rel = np.linalg.inv(T_tool) @ T_cam
    entry = _as_entry(best, size, n_images=len(stacks.get(0, [])))
    entry.pop("pos_m")
    entry.pop("quat_wxyz")
    entry["versatz_werkzeug_m"] = [round(float(v), 5) for v in rel[:3, 3]]
    entry["quat_werkzeug_wxyz"] = [round(float(v), 6) for v in geometry.matrix_to_quat(rel[:3, :3])]
    entry["bezug"] = "%s (%s)" % (wrist_pose_point, data_root.name)
    entry["objektiv"] = "%.1f mm F8.0 (Anwender 2026-11-20), nominal f %.0f px" % (
        WRIST_LENS_MM, WRIST_F_NOMINAL_PX)
    entry["modellvergleich"] = vergleich
    out["wrist"] = entry
    if verbose:
        print("Wrist:", _describe(entry))
        xy = rel[:2, 3]
        print("   Abstand zum TCP in xy %.1f mm, Richtung %.0f Grad von Werkzeug-x "
              "(hindernisse.json: 60 mm, 107 Grad), Hoehe ueber den Backenspitzen %.1f mm"
              % (1e3 * np.linalg.norm(xy), math.degrees(math.atan2(xy[1], xy[0])),
                 -1e3 * rel[2, 3]))
        axis = rel[:3, 2]
        print("   Blickrichtung im Werkzeug-KS %s (Werkzeug-z = Greifrichtung)"
              % np.round(axis, 3).tolist())
    return out


def _as_entry(fit, size, n_images):
    return {
        "modell": fit["model"],
        "f_px": round(float(fit["f"]), 2),
        "k1": round(float(fit["k1"]), 5),
        "k2": round(float(fit.get("k2", 0.0)), 5),
        "bild_px": [int(size[0]), int(size[1])],
        "pos_m": [round(float(v), 5) for v in fit["p"]],
        "quat_wxyz": [round(float(v), 6) for v in geometry.matrix_to_quat(fit["R"])],
        "rest_px": round(float(fit["rms_px"]), 2),
        "bilder": int(n_images),
        "marker_drehung": {str(k): v for k, v in fit["turns"].items()},
    }


def _describe(e):
    where = ("Lage %s m" % e["pos_m"]) if "pos_m" in e else ("Versatz Werkzeug %s m" % e["versatz_werkzeug_m"])
    from .szene import _invert_radius

    def angle(px):
        rn = np.array([px / e["f_px"]])
        return 2 * math.degrees(float(_invert_radius(rn, e["k1"], e["modell"], e.get("k2", 0.0))[0]))

    w, h = e["bild_px"]
    return ("%s, f %.0f px (Vollbild %dx%d), k1 %.3f, k2 %.3f, Bildwinkel h %.0f / v %.0f / diag %.0f Grad, "
            "%s, Rest %.2f px aus %d Bild(ern)"
            % (e["modell"], e["f_px"], w, h, e["k1"], e.get("k2", 0.0), angle(w / 2), angle(h / 2),
               angle(math.hypot(w, h) / 2), where, e["rest_px"], e["bilder"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--daten", default="data/2026-11-19")
    parser.add_argument("--schreiben", action="store_true",
                        help="Ergebnis in bc/sim_mujoco/parameter.json uebernehmen")
    args = parser.parse_args(argv)
    result = estimate(args.daten)
    if args.schreiben:
        data = params.load()
        for name, entry in result.items():
            keep = {k: v for k, v in data["kameras"].get(name, {}).items()
                    if k.startswith("start_") or k.startswith("_")}
            data["kameras"][name] = dict(keep, **entry)
        params.save(data)
        print("-> %s" % params.PATH)


if __name__ == "__main__":
    main()
