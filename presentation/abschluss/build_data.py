"""Daten und Bilder für die Präsentation → public/data/data.json, public/img/.

Nutzt die echten Pipelines aus code/ (M1 TopDownPipeline, M3 InspectionPipeline) auf den
Testbildern, damit jede Zahl und jede Kontur in der Präsentation aus dem Projekt stammt.
Aufruf mit dem Projekt-venv:  ..\\..\\.venv\\Scripts\\python build_data.py
Bildkoordinaten werden normiert exportiert (u, v in 0..1 bezogen auf das exportierte Bild).
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from common.config import load_config  # noqa: E402
from common.trace import Trace  # noqa: E402
from m1_vision_topdown.detector import TopDownPipeline  # noqa: E402
from m3_inspection import InspectionPipeline  # noqa: E402
from m3_inspection.features import _region_features, find_notch, locate_part, sub_roi  # noqa: E402

OUT_DATA = HERE / "public" / "data"
OUT_IMG = HERE / "public" / "img"
MAX_W = 2048  # Texturbreite der Fotos
M3_HERO = 3  # Nahaufnahme: Schlechtteil wird aus diesem Bild erzeugt

# Bauteil (bestätigt 2026-10-21)
PART = {"length_mm": 60.0, "width_mm": 40.0, "height_mm": 15.0, "hole_mm": 10.0, "serial": "69420"}


def save_img(img: np.ndarray, rel: str, max_w: int = MAX_W) -> tuple[str, float]:
    """Speichert verkleinert (JPG bzw. PNG für Masken), gibt Pfad und Skalierung zurück."""
    s = min(1.0, max_w / img.shape[1])
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    path = OUT_IMG / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), small, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return f"img/{rel}", s


def norm(pts, w: int, h: int) -> list[list[float]]:
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    return [[round(float(x) / w, 5), round(float(y) / h, 5)] for x, y in pts]


def simplify(contour: np.ndarray, eps: float = 1.0) -> np.ndarray:
    return cv2.approxPolyDP(contour.astype(np.float32), eps, True).reshape(-1, 2)


def export_config(cfg: dict) -> dict:
    r, ws, ic = cfg["robot"], cfg["workspace"], cfg["inspection"]
    return {
        "workspace": {"size_mm": ws["size_mm"], "markers_mm": {str(k): v for k, v in ws["markers_mm"].items()},
                      "method": ws["method"], "dictionary": ws["aruco_dictionary"]},
        "workspace_to_robot": cfg["workspace_to_robot"],
        "robot": {k: r[k] for k in ("tool_name", "poses", "limits_mm", "linear_speed_mps", "approach_speed_mps",
                                    "approach_height_mm", "approach_slow_mm", "gripper_angle_offset_deg",
                                    "override", "joint_speed_percent", "grasp_height_mm", "tool_tcp_mm") if k in r},
        "inspection": {k: ic[k] for k in ("label_roi", "hole_roi", "notch_roi", "part_height_mm", "hole_nominal_mm",
                                          "hole_tolerance_mm", "serial_pattern", "ocr_min_confidence")},
    }


def export_m1(cfg: dict) -> dict:
    pipe = TopDownPipeline(cfg)
    shots = []
    for i, f in enumerate(sorted((CODE / "m1_vision_topdown" / "tests" / "data").glob("*.jpg"))):
        img = cv2.imread(str(f))
        trace = Trace()
        try:
            res = pipe.process(img, trace)
        except Exception as e:  # Bild ohne Ergebnis: auslassen, aber melden
            print(f"  M1 {f.name}: {e}")
            continue
        h, w = img.shape[:2]
        ws, p = res.workspace, res.part
        rw, rh = ws.rect_size_px
        name = f"m1/{i}"
        photo, _ = save_img(img, f"{name}_photo.jpg")
        rect, _ = save_img(ws.rectify(img), f"{name}_rect.jpg")
        steps = dict(trace.steps)
        mask, _ = save_img(steps["part_closed"], f"{name}_mask.png")
        mask_inv, _ = save_img(255 - steps["part_closed"], f"{name}_mask_inv.png")
        # Rahmen des Arbeitsraums im Foto (für den Mesh-Warp in 3.2)
        # Fasenecke = Ecke des minimalen Rechtecks mit dem größten Abstand zur Kontur (wie part_pose)
        dists = [-cv2.pointPolygonTest(p.contour, (float(q[0]), float(q[1])), True) for q in p.box]
        chamfer_corner = p.box[int(np.argmax(dists))]
        H_inv = np.linalg.inv(ws.H_img2rect)
        frame = cv2.perspectiveTransform(np.float32([[[0, 0], [rw, 0], [rw, rh], [0, rh]]]), H_inv).reshape(4, 2)
        shots.append({
            "file": f.name, "photo": photo, "rect": rect, "mask": mask, "mask_inv": mask_inv,
            "photo_size": [w, h], "rect_size": [rw, rh], "px_per_mm": ws.px_per_mm,
            "markers_img": norm(ws.corners_img, w, h),        # Markermitten in Reihenfolge der IDs 0..3
            "frame_img": norm(frame, w, h),                   # Arbeitsraumecken im Foto (oben links, oben rechts, unten rechts, unten links im Rechteckbild)
            "H_img2rect": ws.H_img2rect.tolist(),
            "contour_rect": norm(simplify(p.contour), rw, rh),
            "box_rect": norm(p.box, rw, rh),
            "centre_rect": norm([[p.u, p.v]], rw, rh)[0],
            "chamfer_rect": norm([chamfer_corner], rw, rh)[0],
            "theta_img_deg": p.theta_img_deg, "chamfer": p.chamfer_found,
            "length_mm": p.length_px / ws.px_per_mm, "width_mm": p.width_px / ws.px_per_mm,
            "ws": {"x": res.x_ws_mm, "y": res.y_ws_mm, "theta": res.theta_ws_deg},
            "robot": {"x": res.pose.x_mm, "y": res.pose.y_mm, "z": res.pose.z_mm, "theta": res.pose.theta_deg},
        })
        print(f"  M1 {f.name}: ws=({res.x_ws_mm:.1f}, {res.y_ws_mm:.1f}) mm, {res.theta_ws_deg:.1f} deg,"
              f" Fase={'ja' if p.chamfer_found else 'nein'}")
    return {"shots": shots}


def ocr_reader():
    try:
        from m3_inspection.ocr import SerialReader
        r = SerialReader()
        return r, "easyocr"
    except Exception as e:  # ohne EasyOCR: Ergebnis der Tests übernehmen
        print(f"  EasyOCR nicht verfügbar ({e}), nehme Testwert")

        class Fake:
            def read(self, roi, pattern):
                return PART["serial"], 0.99
        return Fake(), "fake"


def paint_over(img: np.ndarray, contour: np.ndarray, grow: float = 0.15) -> np.ndarray:
    """Wie m3_inspection/tests: Merkmal mit der Flächenfarbe übermalen → künstlicher Fehler."""
    out = img.copy()
    x, y, w, h = cv2.boundingRect(contour)
    pad = int(grow * max(w, h))
    ring = out[max(0, y - 2 * pad):y + h + 2 * pad, x + w + pad:x + w + 2 * pad]
    colour = np.median(ring.reshape(-1, 3), axis=0)
    cv2.rectangle(out, (x - pad, y - pad), (x + w + pad, y + h + pad), colour.tolist(), -1)
    return out


def inspect_shot(pipe, img: np.ndarray, name: str) -> dict:
    d = pipe.process(img)
    h, w = img.shape[:2]
    photo, _ = save_img(img, f"{name}_photo.jpg")
    x, y, bw, bh = d.part_box
    r = d.result
    return {
        "photo": photo, "photo_size": [w, h],
        "box": norm([[x, y], [x + bw, y + bh]], w, h),
        "hole": norm(simplify(d.hole.contour), w, h) if d.hole is not None else None,
        "notch": norm(simplify(d.notch.contour), w, h) if d.notch is not None else None,
        "hole_over_height": d.hole_diameter_px / bh if d.hole_diameter_px else None,
        "serial": r.serial_number, "ocr_conf": round(float(d.ocr_confidence), 3),
        "hole_mm": r.hole_diameter_mm, "notch_present": r.notch_present,
        "is_good": r.is_good, "reasons": r.reasons,
    }


def export_m3_notches(files: list[Path], ic: dict) -> list[dict]:
    """Kerben-Zwischenbilder aller Testbilder (5.5): ROI, Region, Kanten, Kandidaten; welcher Weg gewonnen hat."""
    out = []
    for i, f in enumerate(files):
        img = cv2.imread(str(f))
        box = locate_part(img, ic)
        trace = Trace()
        best = find_notch(img, box, ic, trace)
        steps = dict(trace.steps)
        crops = {}
        for k in ("notch_roi", "notch_region_mask", "notch_edges", "notch_candidates"):
            url, _ = save_img(steps[k], f"m3/notch/{i}_{k}.{'png' if steps[k].ndim == 2 else 'jpg'}")
            crops[k] = {"url": url, "w": steps[k].shape[1], "h": steps[k].shape[0]}
        via = None
        if best is not None:
            roi, off = sub_roi(img, box, ic["notch_roi"])
            region = [c for c, _ in _region_features(roi, off, box[3], ic)]
            via = "Region" if any(c.shape == best.contour.shape and np.array_equal(c, best.contour) for c in region) else "Kanten"
        out.append({"file": f.name, "crops": crops, "score": float(f"{best.shape_score:.2f}") if best else None, "via": via})
        print(f"  M3 Kerbe {f.name}: {out[-1]['score']} über {via}")
    return out


def export_m3(cfg: dict) -> dict:
    reader, ocr = ocr_reader()
    pipe = InspectionPipeline(cfg, reader=reader)
    ic = cfg["inspection"]
    shots = []
    files = sorted((CODE / "m3_inspection" / "tests" / "data").glob("*.jpg"))
    for i, f in enumerate(files):
        img = cv2.imread(str(f))
        s = inspect_shot(pipe, img, f"m3/{i}")
        s["file"] = f.name
        shots.append(s)
        print(f"  M3 {f.name}: {s['serial']} D/H={s['hole_over_height']:.3f} gut={s['is_good']}")
    # Schlechtteil: Kerbe der Nahaufnahme übermalt
    img = cv2.imread(str(files[M3_HERO]))
    notch = find_notch(img, locate_part(img, ic), ic)
    bad = inspect_shot(pipe, paint_over(img, notch.contour), "m3/bad_notch")
    print(f"  M3 Kerbe übermalt: gut={bad['is_good']} {bad['reasons']}")
    return {"ocr": ocr, "hero": M3_HERO, "shots": shots, "bad": bad, "trace": export_m3_trace(pipe, img, ic),
            "notches": export_m3_notches(files, ic)}


def export_m3_trace(pipe, img: np.ndarray, ic: dict) -> dict:
    """Zwischenbilder des Hero-Bilds (5.2–5.5): Masken in voller Größe invertiert (Papier-Overlay), ROIs als Ausschnitte."""
    trace = Trace()
    d = pipe.process(img, trace)
    steps = dict(trace.steps)
    h, w = img.shape[:2]
    out = {"masks": {}, "crops": {}}
    for k in ("part_mask", "part_opened", "part_closed"):
        out["masks"][k], _ = save_img(255 - steps[k], f"m3/hero/{k}_inv.png")
    for k in ("label_roi", "hole_roi", "hole_mask", "hole_candidates", "notch_roi", "notch_region_mask",
              "notch_edges", "notch_candidates"):
        url, _ = save_img(steps[k], f"m3/hero/{k}.{'png' if steps[k].ndim == 2 else 'jpg'}")
        ch, cw = steps[k].shape[:2]
        out["crops"][k] = {"url": url, "w": cw, "h": ch}
    x, y, bw, bh = d.part_box
    roi = lambda r: norm([[x + r[0] * bw, y + r[1] * bh], [x + r[2] * bw, y + r[3] * bh]], w, h)  # noqa: E731
    out.update({"box_px_h": bh, "hole_px": d.hole_diameter_px, "hole_score": d.hole.shape_score,
                "notch_score": d.notch.shape_score, "serial": d.result.serial_number, "ocr_conf": float(d.ocr_confidence),
                "rois": {k: roi(ic[k]) for k in ("label_roi", "hole_roi", "notch_roi")}})
    return out


def export_m2_check() -> dict:
    """Echte Ausgabe von robot_check gegen den eingebauten Simulator (--sim, schreibt nichts nach logs/)."""
    import os
    import subprocess
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    out = {}
    for key, args in (("info", ["info", "--sim"]), ("jog", ["jog", "z", "20", "--sim"])):
        res = subprocess.run([sys.executable, "-m", "m2_robot_control.robot_check", *args], cwd=CODE, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        lines = [ln for ln in res.stdout.splitlines() if ln.strip() and not ln.startswith("[sim]")]
        out[key] = {"cmd": "robot_check " + " ".join(args), "lines": lines}
    return out


def export_logs() -> dict:
    rows = []
    for f in sorted((CODE / "logs").glob("cycles_*.csv")):
        with open(f, encoding="utf-8") as fh:
            rows += list(csv.DictReader(fh, delimiter=";"))
    return {"cycles": rows}


def copy_figures() -> dict:
    """GROB-Bilder (Vorprojekt, freigegeben) und die Zwischenbilder von M1/M3 aus overview/ mit Bildgröße."""
    out = {}
    sources = (("grob", ROOT / "thesis" / "figures" / "grob", "*.png"),
               ("steps_m1", ROOT / "overview" / "img" / "m1" / "bild1", "m1_*"),
               ("steps_m3", ROOT / "overview" / "img" / "m3" / "bild1", "m3_*"))
    for sub, src, pattern in sources:
        dst = OUT_IMG / sub
        dst.mkdir(parents=True, exist_ok=True)
        files = []
        for f in sorted(src.glob(pattern)):
            shutil.copy2(f, dst / f.name)
            h, w = cv2.imread(str(f)).shape[:2]
            files.append({"url": f"img/{sub}/{f.name}", "name": f.stem, "w": w, "h": h})
        out[sub] = files
    # GUI-Screenshot (tools/gui_shot.py schreibt direkt nach public/img/gui)
    out["gui"] = [{"url": f"img/gui/{f.name}", "name": f.stem, "w": cv2.imread(str(f)).shape[1], "h": cv2.imread(str(f)).shape[0]}
                  for f in sorted((OUT_IMG / "gui").glob("*.png"))]
    return out


def export_lab() -> dict:
    """Labortag 06.10.: Posen und Kalibrierung vor (Schätzung aus der Skizze) und nach dem Teachen (Commit 1f5cdc1)."""
    import subprocess
    import yaml

    def cfg_at(rev: str) -> dict:
        txt = subprocess.run(["git", "show", f"{rev}:code/config/system.yaml"], cwd=ROOT, capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout
        return yaml.safe_load(txt)

    before, after = cfg_at("1f5cdc1^"), cfg_at("1f5cdc1")
    return {"date": "2026-10-06", "commit": "1f5cdc1",
            "poses": {k: {"before": before["robot"]["poses"][k], "after": after["robot"]["poses"][k]}
                      for k in ("inspection", "bin_good", "bin_bad")},
            "workspace_to_robot": {"before": before["workspace_to_robot"], "after": after["workspace_to_robot"]},
            "tool": {"before": before["robot"]["tool_name"], "after": after["robot"]["tool_name"]}}


M4_DIR = CODE / "m4_behavior_cloning"
M4_POINTS = "points_anlage_2026-10-26.json"  # Export aus der Steuerung (Anlage, Werkzeug ZimmerLWR50)
M4_SIDE_DIR = "data_vm/2026-11-19"  # echte Episoden der Anlage vom 19.11. (Teil des Datensatzes von G2b)
M4_DEMO_EP = "ep_00014"  # 6.6: Episode mit deutlichem Rauschen im Anflug (bis 26 mm)
M4_OBS_TAKT = 40  # 6.3: Takt der Episode für das Beobachtungspaar (im Anflug)
# Zittern an der Anlage, RMS über 5 Hz am Unterarm (Achse 5), m/s² – Labortag 16.10./19.10.
# Quelle: m4_behavior_cloning/Dokumentation/Labortag-2026-10-16-Uebergabe.md §1, Zittern-an-der-Anlage.md §0
M4_JITTER = [
    {"name": "servo_j 60 Hz", "lo": 1.80, "hi": 2.0},
    {"name": "servo_j ohne Geschw.", "lo": 0.83, "hi": 0.89},
    {"name": "online (Steuerung interpoliert)", "lo": 0.20, "hi": 0.20},
    {"name": "servo_j, Override 0,5", "lo": 0.19, "hi": 0.21, "chosen": True},
    {"name": "Neura-Standardprogramm", "lo": 0.18, "hi": 0.18},
]
# Durchstich Aufzeichnung → Training → Policy fährt selbst (Simulation), Lauf „Sim, echte Uhr, asynchron, Limiter“
# Quelle: m4_behavior_cloning/Berichte/2026-09-17_Durchstich_Policy.pdf (Seite 1 und 3); Abbildung thesis/figures/m4
M4_SIM = {"date": "2026-09-17", "success": [10, 10], "grip_mm": [1.3, 2.2], "path_p95_mm": [3.3, 4.4],
          "episodes": 50, "steps": 8000, "train_min": 32, "params_m": 89.5, "gpu": "RTX 5070 Ti",
          "predict_ms": 77, "predict_ms_load": 120, "sync_success": [8, 10], "vm_episodes": 30}
# Ergebnisse mit echten Bildern (Jeremys Doku, Kap. 10, Stand 19.11.; Thesis Kap. 8.10):
# VM-Test mit 151 Episoden eines unbekannten Tags, Anlagentest mit Modell C2 (Probegriff, 5 Lagen, 8 Griffe)
# C2: Datensatz var_C2 mit 602 Episoden, ohne Tiefpass (Berichte/2026-11-16_Anlagentest_var_C2/Testprotokoll.md)
# G2b mit Glättung 0,5 am 26.11.: 10/15 Griffe, xy Median 2,2 mm (Berichte/2026-11-26_Vergleich_DAgger/Auswertung.md §1)
M4_PLANT_G2B = {"date": "2026-11-26", "runs": 15, "success": 10, "xy_median_mm": 2.2, "xy_p90_mm": 4.8,
                "lowpass": 0.5, "source": "vergleiche/2026-11-26_12-06-00"}
M4_PLANT = {"demos": 602, "lagen": 164, "vm_runs": 151, "vm_median_mm": 10.7, "vm_le10_pct": 49,
            "plant_median_mm": 8.7, "plant_range_mm": [1.0, 18.0], "plant_le10": [5, 8], "rot_err_deg": 5,
            "follow_mm": [1, 7], "drift_mm": [10, 29], "offset_mm": [5, 10], "offset_deg": [10, 20]}
# Takt an der Anlage (Labortag 16.10.): servo_j-RPC median ~10 ms, p95 ~21 ms, 1–2 Hänger à ~210 ms je Lauf
# Quelle: Dokumentation/Labortag-2026-10-16-Uebergabe.md §1 F1; Vorhersage aus dem Durchstich-Bericht
M4_TIMING = {"cycle_ms": 1000 / 15, "servo_ms": 1000 / 60, "rpc_median_ms": 10, "rpc_p95_ms": 21,
             "hang_ms": 210, "predict_ms": 77}


LAB2_DAY = "2026-11-12"
LAB2_PHOTOS = (("aufbau/anlage_gesamt.jpg", "anlage"), ("aufbau/kamera_oben.jpg", "kamera_oben"),
               ("m3/vorrichtung_seite.jpg", "vorrichtung"), ("m4/handgelenkkamera.jpg", "handgelenk"),
               ("m1/aufbau_erkennung.jpg", "m1_live"), ("m3/aufbau_pruefung.jpg", "m3_live"))


def export_lab2(cfg: dict) -> dict | None:
    """Labortag 12.11.: Zeigetests (logs/point_tests.csv), Zyklen (logs/cycles_20261112.csv) und Laborfotos
    aus thesis/figures. logs/ ist nicht im Repo: fehlen die Dateien, bleibt der Stand aus dem alten data.json."""
    pt_file, cy_file = CODE / "logs" / "point_tests.csv", CODE / "logs" / f"cycles_{LAB2_DAY.replace('-', '')}.csv"
    if not (pt_file.exists() and cy_file.exists()):
        old = OUT_DATA / "data.json"
        prev = json.loads(old.read_text(encoding="utf-8")).get("lab2") if old.exists() else None
        print("  Labortag 12.11.: logs fehlen, alter Stand aus data.json" if prev else "  Labortag 12.11.: keine Daten")
        return prev
    with open(pt_file, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter=";") if r["time"].startswith(LAB2_DAY)]
    pt = lambda r: {"x": float(r["x_ws_mm"]), "y": float(r["y_ws_mm"]), "dx": float(r["dx_mm"]), "dy": float(r["dy_mm"])}
    # Notizen „nach Korrektur 2“ = mit der linearen Positionskorrektur, alle anderen ohne
    after = [pt(r) for r in rows if "Korrektur 2" in r["note"]]
    before = [pt(r) for r in rows if "Korrektur 2" not in r["note"]]
    with open(cy_file, encoding="utf-8") as fh:
        cycles = [{"x": float(r["x_mm"]), "y": float(r["y_mm"]), "theta": float(r["theta_deg"]), "ok": r["ok"] == "True",
                   "error": r["error"], "duration_s": float(r["duration_s"]), "serial": r["serial"],
                   "hole_mm": float(r["hole_mm"]) if r["hole_mm"] else None, "notch": r["notch"] == "True",
                   "good": r["good"] == "True"} for r in csv.DictReader(fh, delimiter=";")]
    dst = OUT_IMG / "lab"
    dst.mkdir(parents=True, exist_ok=True)
    photos = {}
    for rel, name in LAB2_PHOTOS:
        f = ROOT / "thesis" / "figures" / rel
        if f.exists():
            shutil.copy2(f, dst / f"{name}.jpg")
            h, w = cv2.imread(str(f)).shape[:2]
            photos[name] = {"url": f"img/lab/{name}.jpg", "w": w, "h": h}
    ic = cfg["inspection"]
    print(f"  Labortag 12.11.: {len(before)} Zeigetests ohne, {len(after)} mit Korrektur, {len(cycles)} Zyklen")
    return {"date": LAB2_DAY, "points_before": before, "points_after": after, "cycles": cycles, "photos": photos,
            "correction": cfg["part_topdown"].get("position_correction"),
            "workspace_mm": cfg["workspace"]["size_mm"] if "workspace" in cfg else 330,
            "hole_nominal_mm": ic["hole_nominal_mm"], "hole_tolerance_mm": ic["hole_tolerance_mm"],
            "exposure_us": cfg["topdown_camera"].get("exposure_us"), "focus": cfg["inspection_camera"].get("focus")}


LAB3_DAY = "20261126"


def export_lab3(cfg: dict) -> dict | None:
    """Labortag 26.11.: Zyklusprotokoll (logs/cycles_20261126.csv), Nachauswertung aller Prüfbilder
    (logs/20261126/*/steps/m3_01_original.jpg) mit Ellipsen- und Kreis-Fit an derselben Lochkontur,
    GUI-Screenshot und Fehlerbilder. Wie thesis/tools/eval_20261126.py; logs/ ist nicht im Repo:
    fehlen die Dateien, bleibt der Stand aus dem alten data.json."""
    cy_file, runs = CODE / "logs" / f"cycles_{LAB3_DAY}.csv", CODE / "logs" / LAB3_DAY
    if not (cy_file.exists() and runs.exists()):
        old = OUT_DATA / "data.json"
        prev = json.loads(old.read_text(encoding="utf-8")).get("lab3") if old.exists() else None
        print("  Labortag 26.11.: logs fehlen, alter Stand aus data.json" if prev else "  Labortag 26.11.: keine Daten")
        return prev
    with open(cy_file, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    cycles = [{"time": r["time"][11:16], "run": Path(r["images"]).name if r["images"] else "",
               "ok": r["ok"] == "True", "error": r["error"], "duration_s": float(r["duration_s"]),
               "part": bool(r["x_mm"]), "serial": r["serial"], "notch": r["notch"] == "True",
               "hole_mm": float(r["hole_mm"]) if r["hole_mm"] else None, "good": r["good"] == "True"}
              for r in rows]
    by_run = {c["run"]: c for c in cycles if c["run"]}
    ic = cfg["inspection"]
    pipe = InspectionPipeline(cfg)
    reeval = []
    for d in sorted(runs.iterdir()):
        c = by_run.get(d.name)
        f = d / "steps" / "m3_01_original.jpg"
        if not (c and c["hole_mm"] is not None and f.exists()):
            continue
        det = pipe.process(cv2.imread(str(f)))
        mmpp = ic["part_height_mm"] / det.part_box[3]
        (_, _), (a, b), _ = cv2.fitEllipse(det.hole.contour)
        reeval.append({"time": c["time"], "ellipse": round((a + b) / 2 * mmpp, 3),
                       "circle": round(det.result.hole_diameter_mm, 3), "upside_down": not det.result.serial_number})
    dst = OUT_IMG / "lab3"
    dst.mkdir(parents=True, exist_ok=True)
    photos = {}

    def photo(name: str, img: np.ndarray, max_w: int = MAX_W) -> None:
        url, s = save_img(img, f"lab3/{name}.jpg", max_w)
        photos[name] = {"url": url, "w": int(img.shape[1] * s), "h": int(img.shape[0] * s)}

    shot = CODE / "logs" / "Screenshot 2026-11-26 103844.png"
    if shot.exists():
        photo("gui", cv2.imread(str(shot)))
    fit = ROOT / "thesis" / "figures" / "eval" / "loch_vorher_nachher.png"
    if fit.exists():
        photo("fit", cv2.imread(str(fit)))
    hand = runs / "111559_c006" / "steps" / "m1_02_aruco_markers.jpg"
    if hand.exists():
        photo("hand", cv2.imread(str(hand)), 1440)
    back = runs / "112017_c003" / "steps" / "m3_01_original.jpg"
    if back.exists():
        img = cv2.imread(str(back))
        h, w = img.shape[:2]
        photo("rueckseite", img[int(0.40 * h):int(0.90 * h), int(0.06 * w):int(0.96 * w)], 1600)
    # 3.7: Abbruch „Part is upside down“ (11:38) – Pose mit gespiegelter Fase, Ausschnitt um das Teil
    flip = runs / "113849_c001" / "steps" / "m1_09_part_pose.jpg"
    if flip.exists():
        img = cv2.imread(str(flip))
        h, w = img.shape[:2]
        photo("kopfueber", img[int(0.22 * h):int(0.70 * h), int(0.36 * w):int(0.84 * w)], 900)
    print(f"  Labortag 26.11.: {len(cycles)} Einträge, {len(reeval)} Prüfbilder nachausgewertet")
    return {"date": "2026-11-26", "cycles": cycles, "reeval": reeval, "photos": photos,
            "hole_nominal_mm": ic["hole_nominal_mm"], "hole_tolerance_mm": ic["hole_tolerance_mm"]}


def export_smooth() -> dict:
    """6.12 Glättung: dieselbe Policy (G2) am 23.11. mit Tiefpass aus / 0,75 / 0,5 / 0,25, Probegriffe mit bekannter Lage.
    Je Fahrt der waagrechte Abstand zu PICK über der Höhe (wie die Versatz-Abbildungen) und der seitliche Weg unter 60 mm."""
    from collections import defaultdict
    root = M4_DIR / "checkpoints" / "G2_licht_langsam_nur_griff" / "policy" / "rollouts"
    groups = defaultdict(list)
    for d in sorted(root.glob("2026-11-23_1[56]-*")):
        if not (d / "summary.json").exists():
            continue
        sm = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        a = sm["args"].get("glaettung")
        if a is None or sm["args"].get("probegriff") != "objekt":
            continue
        for f in sorted(d.glob("rollout_*.npz")):
            z = np.load(f)
            tcp = np.vstack([z["tcp"], z["final_tcp"][None]])
            dz = 1e3 * z["lage_dz_pick"]
            n = min(len(dz), len(tcp))
            dz, p = dz[:n], 1e3 * (tcp[:n, :2] - z["lage_pick"][:2])
            if dz.min() > 100:  # abgebrochen, bevor die Policy absenkte
                continue
            m = dz < 60
            way = float(np.sum(np.hypot(*np.diff(p[m], axis=0).T))) if m.sum() > 1 else None
            if way is None or way > 200:  # Ausreißer: Fahrt mit Not-Aus/Wegfahren
                continue
            k = dz <= 120
            groups[a].append({"h": np.round(dz[k], 1).tolist(), "xy": np.round(np.hypot(*p[k].T), 1).tolist(), "way": round(way, 1)})
    out = []
    for a in sorted(groups, reverse=True):
        runs = groups[a]
        out.append({"alpha": a, "runs": runs, "n": len(runs), "way_median_mm": round(float(np.median([r["way"] for r in runs])), 1)})
        print(f"  M4: Glättung {a}: {len(runs)} Fahrten, seitlicher Weg unter 60 mm Median {out[-1]['way_median_mm']} mm")
    return {"date": "2026-11-23", "model": "G2", "groups": out}


def export_grasps() -> dict:
    """6.13 Die letzten Millimeter: echte Griffe von G2b mit bekannter Lage (Probegriff „tisch“, 25./26.11.) –
    je Takt x/y-Abstand zu PICK über der Höhe über PICK. Nur Fahrten mit bekannter Lage, nichts gemischt."""
    root = M4_DIR / "checkpoints" / "G2b_580_dagger_nur_griff" / "policy" / "rollouts"
    runs = []
    for d in sorted(root.glob("2026-11-2*")):
        if not (d / "summary.json").exists():
            continue
        a = json.loads((d / "summary.json").read_text(encoding="utf-8"))["args"]
        if a.get("probegriff") != "tisch" or not a.get("lage_bekannt"):
            continue
        for f in sorted(d.glob("rollout_*.npz")):
            z = np.load(f)
            if "lage_dz_pick" not in z.files or not (z["gripper_cmd"] > 0.5).any():
                continue
            tcp = np.vstack([z["tcp"], z["final_tcp"][None]])
            dz = 1e3 * z["lage_dz_pick"]
            n = min(len(dz), len(tcp), int(np.flatnonzero(z["gripper_cmd"] > 0.5)[0]) + 1)  # bis der Greifer schließt
            p = 1e3 * (tcp[:n, :2] - z["lage_pick"][:2])
            k = dz[:n] <= 160
            if np.hypot(*p[-1]) > 30:  # Lage passt nicht zur Fahrt (z. B. PICK der vorigen Lage) – nicht verwenden
                print(f"  M4: {d.name} ausgelassen: beim Schließen {np.hypot(*p[-1]):.0f} mm neben PICK")
                continue
            runs.append({"run": d.name[5:], "h": np.round(dz[:n][k], 1).tolist(), "dx": np.round(p[k, 0], 1).tolist(),
                         "dy": np.round(p[k, 1], 1).tolist()})
    print(f"  M4: echte Griffe G2b mit bekannter Lage: {len(runs)} Fahrten")
    return {"model": "G2b", "ref": "PICK", "runs": runs}


def export_heat() -> dict:
    """6.15 Wo greift die Policy gut? Alle Vergleichsfahrten von G2b (24.–26.11.) mit Lage, Drehung und Ergebnis
    (geometrische Griffprüfung, Spiel >= 0,5 mm) aus Berichte/2026-11-26_Vergleich_DAgger/fahrten.csv; dazu als
    Trainingslagen die PICK-Lagen der Episoden vom 19.11. (Ausschnitt des Datensatzes)."""
    import csv
    rows = list(csv.DictReader((M4_DIR / "Berichte" / "2026-11-26_Vergleich_DAgger" / "fahrten.csv").open(encoding="utf-8"), delimiter=";"))
    runs = []
    for r in rows:
        if not r["pick_x_mm"]:
            continue
        runs.append({"model": r["kurz"], "x": round(float(r["pick_x_mm"]), 1), "y": round(float(r["pick_y_mm"]), 1), "rot": round(float(r["pick_drehung_grad"]), 1),
                     "ok": r["erfolg"] == "True", "quer": round(abs(float(r["quer_mm"])), 1) if r["quer_mm"] else None,
                     "train_mm": round(float(r["trainingsabstand_mm"]), 1) if r["trainingsabstand_mm"] else None})
    train = []
    for ep in sorted((M4_DIR / M4_SIDE_DIR).glob("ep_*")):
        if not (ep / "arrays.npz").exists():
            continue
        z = np.load(ep / "arrays.npz")
        g = np.flatnonzero(z["action"][:, 6] > 0.5)
        if len(g):
            p = z["aux__pose_ideal"][g[0], :2] * 1000
            train.append([round(float(p[0]), 1), round(float(p[1]), 1)])
    print(f"  M4: Heatmap aus {len(runs)} Vergleichsfahrten (alle Modelle), {len(train)} Trainingslagen (19.11.)")
    return {"runs": runs, "train": train, "train_source": M4_SIDE_DIR}


def plot_g2b_versatz() -> dict:
    """6.9: dieselbe Abbildung wie im Anlagentest C2 (waagrechter Versatz zu PICK über der Höhe), für G2b mit Glättung
    0,5 am 26.11. – aus den Rohdaten rollout_000.npz der Vergleichsfahrten, wie Berichte/…_var_C2/skripte/auswertung.py."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = M4_DIR / M4_PLANT_G2B["source"]
    runs = []
    for f in sorted(root.glob("lage_*/G2b_*/rollout_000.npz")):
        z = np.load(f)
        tcp = np.vstack([z["tcp"], z["final_tcp"][None]])
        runs.append((1e3 * z["lage_dz_pick"], 1e3 * np.hypot(*(tcp[:, :2] - z["lage_pick"][:2]).T)))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for dz, xy in runs:
        n = min(len(dz), len(xy))
        dz, xy = dz[:n], xy[:n]
        m = dz <= 120
        ax.plot(dz[m], xy[m], color="#9A5A2E", lw=1.4, alpha=0.75, solid_capstyle="round")
        ax.plot(dz[m][-1], xy[m][-1], "o", ms=4.5, color="#9A5A2E", mec="white", mew=1.0)
    ax.axhline(10, color="#6B6F73", lw=0.9, ls="--")
    ax.text(119, 10.6, "10 mm (Erfolgskriterium)", color="#6B6F73", fontsize=8, ha="left")
    ax.axvspan(0, 30, color="#E6E1D6", alpha=0.6, lw=0)
    ax.text(15, 27, "letzte 30 mm", color="#6B6F73", fontsize=8, ha="center")
    ax.set_xlim(120, 0)
    ax.set_ylim(0, 30)
    ax.set_xlabel("Höhe des TCP über PICK [mm]  (Abstieg →)")
    ax.set_ylabel("waagrechter Versatz zu PICK [mm]")
    ax.text(118, 28, f"G2b, Glättung 0,5 · {len(runs)} Lagen, je 1 Fahrt", fontsize=8, color="#1E2328", va="top")
    fig.tight_layout()
    out = OUT_IMG / "m4" / "g2b_versatz_hoehe.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170)
    plt.close(fig)
    img = cv2.imread(str(out))
    print(f"  M4: Versatz über der Höhe für G2b aus {len(runs)} Fahrten")
    return {"url": "img/m4/g2b_versatz_hoehe.png", "w": img.shape[1], "h": img.shape[0]}


def export_m4() -> dict:
    """M4: geteachte Punkte der Anlage (TCP im Basis-KS, mm/°), Sollbahn bis zum Griff und echte Abweichungen.

    Die Sollbahn folgt sequences/pick_bis_griff.json (seit 19.11.): CLEAR_FOV → ANFLUG 150 mm über PICK →
    PRE_PICK 50 mm über PICK → PICK (Endanflug) → Greifer zu → zurück auf PRE_PICK, abgetastet mit 15 Hz.
    Der Weg danach zu PRE_PLACE ist nicht mehr Teil der Aufnahme. Die Seitenansicht des Trichters (6.7) kommt aus
    echten Episoden der Anlage (M4_SIDE_DIR): Abweichung der gefahrenen von der idealen TCP-Lage über der Höhe.
    """
    import math
    sys.path.insert(0, str(M4_DIR))
    from bc import config as bcc
    from bc import noise

    pts = json.loads((M4_DIR / "sequences" / M4_POINTS).read_text(encoding="utf-8"))["punkte"]
    pose = lambda k: [round(v * 1000, 1) for v in pts[k]["cartesian"][:3]] + \
        [round(math.degrees(a), 1) for a in pts[k]["cartesian"][3:]]
    P = {k: pose(k) for k in ("CLEAR_FOV", "PICK")}
    joints = {k: [round(math.degrees(a), 2) for a in pts[k]["joint"]] for k in P}  # Startwerte für die IK in der Zelle

    pick = np.array(P["PICK"][:3]) / 1000
    above = lambda dz: pick + [0, 0, dz]
    legs = [(np.array(P["CLEAR_FOV"][:3]) / 1000, above(0.15), bcc.TRANSIT_SPEED_MS),  # → ANFLUG
            (above(0.15), above(0.05), bcc.TRANSIT_SPEED_MS),  # → PRE_PICK
            (above(0.05), pick, bcc.APPROACH_SPEED_MS),  # Endanflug
            (pick, pick, None),  # Greifer schließt
            (pick, above(0.05), bcc.APPROACH_SPEED_MS)]  # zurück auf PRE_PICK
    rate = bcc.CONTROL_RATE_HZ
    path, dwell = [], []
    for a, b, v in legs:
        n = bcc.GRIPPER_DWELL_STEPS if v is None else max(2, int(math.ceil(np.linalg.norm(b - a) / v * rate)))
        for i in range(n):
            path.append(a + (b - a) * (i / n))
            dwell.append(v is None)
    path.append(legs[-1][1])
    dwell.append(False)
    path = np.array(path)
    print(f"  M4: Sollbahn {len(path)} Takte bis zum Griff und zurück auf PRE_PICK")

    # 6.7 Seitenansicht: echte Episoden der Anlage, bis der Greifer schließt
    side = {"source": M4_SIDE_DIR, "episodes": []}
    for ep in sorted((M4_DIR / M4_SIDE_DIR).glob("ep_*")):
        if not (ep / "arrays.npz").exists() or json.loads((ep / "meta.json").read_text(encoding="utf-8")).get("discarded"):
            continue  # abgebrochene oder verworfene Episode
        z = np.load(ep / "arrays.npz")
        ideal, noisy, grip = z["aux__pose_ideal"][:, :3], z["aux__pose_noisy"][:, :3], z["action"][:, 6]
        k = int(np.argmax(grip > 0.5)) if (grip > 0.5).any() else len(grip)
        h = (ideal[:k, 2] - ideal[k - 1, 2]) * 1000
        d = (noisy[:k, :2] - ideal[:k, :2]) * 1000
        side["episodes"].append({"h": np.round(h, 1).tolist(), "dx": np.round(d[:, 0], 1).tolist(),
                                 "dy": np.round(d[:, 1], 1).tolist()})
    # 6.6 eine echte verrauschte Episode für die Zelle (Abweichung je Höhe über PICK, auch z)
    z = np.load(M4_DIR / M4_SIDE_DIR / M4_DEMO_EP / "arrays.npz")
    ideal, noisy, grip = z["aux__pose_ideal"][:, :3], z["aux__pose_noisy"][:, :3], z["action"][:, 6]
    k = int(np.argmax(grip > 0.5))
    off = (noisy[:k] - ideal[:k]) * 1000
    side["demo"] = {"episode": M4_DEMO_EP, "h": np.round((ideal[:k, 2] - ideal[k - 1, 2]) * 1000, 1).tolist(),
                    "dx": np.round(off[:, 0], 1).tolist(), "dy": np.round(off[:, 1], 1).tolist(),
                    "dz": np.round(off[:, 2], 1).tolist()}
    # 6.3 ein echtes Beobachtungspaar: beide Kamerabilder, 14 Zustandswerte und die nächsten 16 Sollposen (Labels)
    t = M4_OBS_TAKT
    (OUT_IMG / "m4").mkdir(parents=True, exist_ok=True)
    for cam_name in ("wrist", "scene"):
        img = z[f"observation__images__{cam_name}"][t]
        cv2.imwrite(str(OUT_IMG / "m4" / f"obs_{cam_name}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    horizon = bcc.POLICY_HORIZON
    nxt = ideal[t + 1:t + 1 + horizon] - ideal[t]
    side["obs"] = {"takt": t, "episode": M4_DEMO_EP, "h_mm": round(float((ideal[t, 2] - ideal[k - 1, 2]) * 1000), 1),
                   "state": np.round(z["observation__state"][t], 4).tolist(),
                   "chunk_mm": np.round(nxt * 1000, 1).tolist(),
                   # Labels der nächsten 16 Takte: absolute Gelenk-Sollwinkel (hier relativ zur Stellung jetzt, in °) + Greifer
                   "chunk_joints_deg": np.round(np.degrees(z["action"][t:t + horizon, :6] - z["observation__state"][t, :6]), 2).tolist(),
                   "chunk_grip": np.round(z["action"][t:t + horizon, 6], 2).tolist(),
                   # TCP-Höhe der Labels (ideale Pose t+1 … t+16 = FK der Gelenk-Sollwinkel), relativ zum TCP jetzt (gefahren)
                   "chunk_tcp_z_mm": np.round((ideal[t + 1:t + 1 + horizon, 2] - noisy[t, 2]) * 1000, 1).tolist(),
                   "images": {c: {"url": f"img/m4/obs_{c}.jpg", "w": 320, "h": 240} for c in ("wrist", "scene")}}
    devs = [max(np.hypot(e["dx"], e["dy"])) for e in side["episodes"]]
    side["max_dev_mm"] = round(float(max(devs)), 1)
    print(f"  M4: Seitenansicht aus {len(devs)} echten Episoden ({M4_SIDE_DIR}), größte Abweichung {side['max_dev_mm']} mm")
    lim = noise.NoiseLimits()
    side["limit_mm"] = {"xy": round(lim.hi[0] * 1000, 1), "z_down": round(lim.lo[2] * 1000, 1)}
    side["max_rejects"] = bcc.NOISE_MAX_REJECTS
    seq = json.loads((M4_DIR / "sequences" / "pick_bis_griff.json").read_text(encoding="utf-8"))
    side["pick_above_table_mm"] = round(seq["table"]["pick_height"] * 1000, 1)  # TCP an PICK über dem Tisch
    side["rest_max_mm"] = round(bcc.APPROACH_REST_MAX_M * 1000, 1)
    side["free_mm"] = round(bcc.APPROACH_OFFSET_FREE_M * 1000, 1)
    # 6.4 Policy-Aufbau aus Jeremys Config
    policy = {"n_obs": bcc.POLICY_N_OBS_STEPS, "horizon": bcc.POLICY_HORIZON, "n_action": bcc.POLICY_N_ACTION_STEPS,
              "inference_steps": bcc.POLICY_INFERENCE_STEPS, "image": [bcc.IMAGE_HEIGHT, bcc.IMAGE_WIDTH],
              "replan": bcc.POLICY_REPLAN_STEPS, "lowpass": bcc.POLICY_COMMAND_LOWPASS_ALPHA, "decay": bcc.POLICY_ENSEMBLE_DECAY}
    # 6.5 Rollout-Abbildung aus dem Durchstich (unten abgeschnitten: dort beginnt im Original die Tabelle)
    fig = cv2.imread(str(ROOT / "thesis" / "figures" / "m4" / "durchstich_sim_rollouts.png"))[:396]
    fig = fig[:, fig.shape[1] // 2:]  # nur rechts: Höhe des TCP über der Zeit (die Draufsicht sagt wenig)
    (OUT_IMG / "m4").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_IMG / "m4" / "durchstich_sim_rollouts.png"), fig)
    sim = {**M4_SIM, "figure": {"url": "img/m4/durchstich_sim_rollouts.png", "w": fig.shape[1], "h": fig.shape[0]}}
    # 6.5 Anlage: Versatz über der Höhe im Anlagentest (Abbildung aus Jeremys Bericht, über thesis/figures/m4)
    fig = cv2.imread(str(ROOT / "thesis" / "figures" / "m4" / "c2_versatz_hoehe.png"))
    cv2.imwrite(str(OUT_IMG / "m4" / "c2_versatz_hoehe.png"), fig)
    plant = {**M4_PLANT, "figure": {"url": "img/m4/c2_versatz_hoehe.png", "w": fig.shape[1], "h": fig.shape[0]}}
    plant["g2b"] = {**M4_PLANT_G2B, "figure": plot_g2b_versatz()}
    smooth = export_smooth()
    grasps = export_grasps()
    heat = export_heat()
    return {"points": P, "joints": joints, "points_file": M4_POINTS, "rate_hz": rate, "ideal": np.round(path * 1000, 1).tolist(),
            "pick_index": int(np.argmax(dwell)), "anflug_mm": 150, "pre_pick_mm": 50, "side": side,
            "noise": {"sigma_mm": bcc.NOISE_TRANS_AMPLITUDE_M * 1000, "tau_s": bcc.NOISE_OU_TAU_S,
                      "funnel_mm": [bcc.FUNNEL_ZERO_DIST_M * 1000, bcc.FUNNEL_START_DIST_M * 1000]},
            "policy": policy, "sim": sim, "plant": plant, "timing": M4_TIMING, "jitter": M4_JITTER,
            "smooth": smooth, "grasps": grasps, "heat": heat}


def export_tests() -> dict:
    """Anzahl der Tests je Datei (pytest --collect-only)."""
    import subprocess
    res = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=CODE,
                         capture_output=True, text=True, encoding="utf-8")
    per_file: dict[str, int] = {}
    for line in res.stdout.splitlines():
        if "::" in line:
            f = line.split("::")[0].replace("\\", "/")
            per_file[f] = per_file.get(f, 0) + 1
    return {"total": sum(per_file.values()), "files": per_file}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows-Konsole: cp1252
    cfg = load_config()
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    print("M1 …")
    m1 = export_m1(cfg)
    print("M3 …")
    m3 = export_m3(cfg)
    print("M2 robot_check …")
    m2 = {"check": export_m2_check()}
    data = {"part": PART, "config": export_config(cfg), "m1": m1, "m2": m2, "m3": m3, "logs": export_logs(),
            "figures": copy_figures(), "tests": export_tests(), "lab": export_lab(), "lab2": export_lab2(cfg), "lab3": export_lab3(cfg),
            "m4": export_m4()}
    (OUT_DATA / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT_DATA / 'data.json'}")


if __name__ == "__main__":
    main()
