"""Kameras gegen die Aufnahme des Modells pruefen (Anwender 2026-11-16).

Vor der ersten Fahrt, Arm in der Startstellung: Sehen die Kameras ungefaehr
das, was die Policy im Training gesehen hat? Hintergrund: die Bildstatistik
ist mitgelernt (Versuchsreihe 2026-11-14: Licht/Helligkeit der Tage, Kamera
an den Trainingstagen um 8-10 px und 3-6 Grad verschieden).

Referenz je Kamera, aus dem ersten Bild (Startstellung) der Trainingsepisoden:

* Spanne (p5, Median, p95) von Helligkeit, Farbverhaeltnis R/G und B/G,
  Saettigung und Anteil uebersteuerter Pixel,
* ein Bezugsbild (das mit der mittleren Helligkeit) fuer die Kameralage --
  Merkmalsabgleich ORB + RANSAC wie Berichte/.../skripte/kameralage.py.

Die Referenz steht in bc_policy.json unter ``camera_reference`` (Export ab
2026-11-16; aeltere Checkpoints: tools/kamera_referenz.py traegt sie nach).
Qt-frei; Bilder in Schema-Groesse (240x320), Kanalreihenfolge wie im Datensatz.
"""

import base64

import numpy as np

REFERENCE_KEY = "camera_reference"

#: Hoechstens so viele Episoden fuer die Referenz (gleichmaessig verteilt)
MAX_EPISODES = 40
#: Toleranz um die Trainingsspanne: Helligkeit (Grauwert 0..255) ...
BRIGHTNESS_MARGIN = 12.0
#: ... Farbverhaeltnisse R/G, B/G ...
COLOR_MARGIN = 0.08
#: ... Saettigung (0..255)
SATURATION_MARGIN = 15.0
#: Uebersteuert (>= 250) -- Warnung ab diesem Anteil, mindestens aber dem
#: Doppelten des Trainings (Befund 11.11.: lila Objekt fast weiss)
CLIPPED_WARN = 0.02
#: Kameralage gegen das Bezugsbild: Warnung ab so viel Versatz (px im
#: 320x240-Bild), Drehung (Grad), Massstab (relativ)
SHIFT_WARN_PX = 4.0
ROTATION_WARN_DEG = 1.5
SCALE_WARN = 0.03
#: Mindestzahl uebereinstimmender Merkmale fuer eine Lageaussage
MIN_MATCHES = 15

STAT_KEYS = ("brightness", "red_green", "blue_green", "saturation", "clipped")

OK, WARN = "ok", "warnung"


def frame_stats(image):
    """Kennzahlen eines Bilds (H, W, 3) uint8."""
    import cv2

    img = np.asarray(image, dtype=np.uint8)
    rgb = img.astype(float)
    gray = rgb.mean(axis=2)
    means = rgb.reshape(-1, 3).mean(axis=0)
    green = max(float(means[1]), 1.0)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    return {
        "brightness": float(gray.mean()),
        "red_green": float(means[0]) / green,
        "blue_green": float(means[2]) / green,
        "saturation": float(hsv[..., 1].mean()),
        "clipped": float((img.max(axis=2) >= 250).mean()),
    }


def _encode(image):
    import cv2

    ok, buf = cv2.imencode(".png", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise ValueError("Bezugsbild nicht kodierbar")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def decode_image(text):
    import cv2

    data = np.frombuffer(base64.b64decode(text), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def build_reference(frames_by_camera):
    """``{kamera: [Bild, ...]}`` -> Referenz fuer bc_policy.json."""
    out = {}
    for name, frames in frames_by_camera.items():
        frames = [f for f in frames if f is not None]
        if not frames:
            continue
        stats = [frame_stats(f) for f in frames]
        table = {k: np.array([s[k] for s in stats]) for k in STAT_KEYS}
        median_b = float(np.median(table["brightness"]))
        pick = int(np.argmin(np.abs(table["brightness"] - median_b)))
        out[name] = {
            "episodes": len(frames),
            "stats": {k: [float(np.percentile(v, 5)), float(np.median(v)),
                          float(np.percentile(v, 95))] for k, v in table.items()},
            "image_png_b64": _encode(frames[pick]),
        }
    return out


def first_frames(episode_dirs, cameras, max_episodes=MAX_EPISODES):
    """Erstes Bild je Kamera aus Rohepisoden (``ep_*/arrays.npz``)."""
    dirs = list(episode_dirs)
    if len(dirs) > max_episodes:
        dirs = [dirs[int(i)] for i in np.linspace(0, len(dirs) - 1, max_episodes)]
    frames = {name: [] for name in cameras}
    for d in dirs:
        with np.load(d / "arrays.npz") as npz:
            for name in cameras:
                key = "observation__images__%s" % name
                if key in npz.files:
                    frames[name].append(np.asarray(npz[key][0]))
    return frames


def estimate_shift(reference, image):
    """Versatz (px), Drehung (Grad), Massstab von ``image`` gegen ``reference``.

    None, wenn zu wenige Merkmale passen. Helligkeit wird vorher angeglichen.
    """
    import cv2

    def gray(img):
        return cv2.equalizeHist(cv2.cvtColor(np.asarray(img, dtype=np.uint8), cv2.COLOR_RGB2GRAY))

    orb = cv2.ORB_create(1500)
    k1, d1 = orb.detectAndCompute(gray(reference), None)
    k2, d2 = orb.detectAndCompute(gray(image), None)
    if d1 is None or d2 is None:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(matches) < MIN_MATCHES:
        return None
    src = np.float32([k1[m.queryIdx].pt for m in matches])
    dst = np.float32([k2[m.trainIdx].pt for m in matches])
    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                                  ransacReprojThreshold=3.0)
    if matrix is None or inliers is None or int(inliers.sum()) < MIN_MATCHES:
        return None
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    return {"shift_px": float(np.hypot(matrix[0, 2], matrix[1, 2])),
            "dx_px": float(matrix[0, 2]), "dy_px": float(matrix[1, 2]),
            "rotation_deg": float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))),
            "scale": scale, "inliers": int(inliers.sum())}


#: Gruppen der Pruefung (Anwender 2026-11-24: getrennt anzeigen, ob Licht
#: oder eine verschobene Kamera die Warnung ausloest)
LIGHT, POSE = "licht", "lage"
GROUP_LABELS = {LIGHT: "Licht/Farbe", POSE: "Kameralage"}
#: Zeilenkopf der maschinenlesbaren Ergebniszeile fuer die Oberflaeche
JSON_PREFIX = "KAMERAPRUEFUNG_JSON "


def _range_check(label, value, span, margin, fmt):
    lo, med, hi = span
    ok = lo - margin <= value <= hi + margin
    text = "%s %s (Training %s..%s)" % (label, fmt % value, fmt % lo, fmt % hi)
    return (OK if ok else WARN), text


def group_of(text):
    """Gruppe eines Pruefungstexts -- auch fuer Zeilen aelterer Protokolle."""
    return POSE if text.startswith("Kameralage") else LIGHT


def compare(reference, frames):
    """Aktuelle Bilder ``{kamera: Bild}`` gegen die Referenz.

    Rueckgabe: Liste ``{camera, level, checks: [(level, text)]}``; ``level``
    ist "warnung", sobald eine Pruefung warnt.
    """
    results = []
    for name, ref in (reference or {}).items():
        image = frames.get(name)
        if image is None:
            results.append({"camera": name, "level": WARN,
                            "checks": [(WARN, "kein Bild")],
                            "groups": {LIGHT: WARN, POSE: WARN}})
            continue
        stats, span = frame_stats(image), ref["stats"]
        checks = [
            _range_check("Helligkeit", stats["brightness"], span["brightness"],
                         BRIGHTNESS_MARGIN, "%.0f"),
            _range_check("Farbe R/G", stats["red_green"], span["red_green"], COLOR_MARGIN, "%.2f"),
            _range_check("Farbe B/G", stats["blue_green"], span["blue_green"], COLOR_MARGIN, "%.2f"),
            _range_check("Saettigung", stats["saturation"], span["saturation"],
                         SATURATION_MARGIN, "%.0f"),
        ]
        clipped_limit = max(CLIPPED_WARN, 2.0 * span["clipped"][2])
        checks.append((OK if stats["clipped"] <= clipped_limit else WARN,
                       "uebersteuert %.1f %% (Training bis %.1f %%)"
                       % (100 * stats["clipped"], 100 * span["clipped"][2])))
        shift = estimate_shift(decode_image(ref["image_png_b64"]), image)
        if shift is None:
            checks.append((WARN, "Kameralage nicht bestimmbar (zu wenige passende Merkmale)"))
        else:
            bad = (shift["shift_px"] > SHIFT_WARN_PX or abs(shift["rotation_deg"]) > ROTATION_WARN_DEG
                   or abs(shift["scale"] - 1.0) > SCALE_WARN)
            checks.append((WARN if bad else OK,
                           "Kameralage: Versatz %.1f px, Drehung %.1f Grad, Massstab %.3f"
                           % (shift["shift_px"], shift["rotation_deg"], shift["scale"])))
        level = WARN if any(lvl == WARN for lvl, _ in checks) else OK
        results.append({"camera": name, "level": level, "checks": checks, "stats": stats,
                        "shift": shift, "groups": group_levels(checks)})
    return results


def group_levels(checks):
    """``{gruppe: "ok"|"warnung"}`` aus den Einzelpruefungen ``[(level, text)]``."""
    out = {LIGHT: OK, POSE: OK}
    for lvl, text in checks:
        if lvl == WARN:
            out[group_of(text)] = WARN
    return out


def to_json_line(results):
    """Eine Zeile fuer die Oberflaeche: je Kamera und Gruppe Stufe und Pruefungen."""
    import json

    data = {}
    for r in results:
        groups = {}
        for key in (LIGHT, POSE):
            checks = [{"level": lvl, "text": text} for lvl, text in r["checks"]
                      if group_of(text) == key]
            levels = r.get("groups") or group_levels(r["checks"])
            groups[key] = {"level": levels[key], "checks": checks}
        data[r["camera"]] = groups
    return JSON_PREFIX + json.dumps(data, ensure_ascii=True)


def format_lines(results):
    """Ausgabezeilen ``KAMERAPRUEFUNG <kamera>: OK|WARNUNG -- ...``."""
    lines = []
    for r in results:
        bad = [text for lvl, text in r["checks"] if lvl == WARN]
        good = [text for lvl, text in r["checks"] if lvl == OK]
        head = "KAMERAPRUEFUNG %s: %s" % (r["camera"], "OK" if r["level"] == OK else "WARNUNG")
        lines.append(head + " -- " + "; ".join(bad or good))
        if bad and good:
            lines.append("   in Ordnung: " + "; ".join(good))
    return lines
