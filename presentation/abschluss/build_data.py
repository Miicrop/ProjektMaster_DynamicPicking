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
            "figures": copy_figures(), "tests": export_tests(), "lab": export_lab()}
    (OUT_DATA / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT_DATA / 'data.json'}")


if __name__ == "__main__":
    main()
