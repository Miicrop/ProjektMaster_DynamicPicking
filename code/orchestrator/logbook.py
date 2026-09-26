"""Cycle results as CSV (one file per day) and debug images per cycle - data for the evaluation."""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import cv2

from common.config import CODE_ROOT
from orchestrator.state_machine import CycleResult

FIELDS = ["time", "cycle", "ok", "error", "duration_s", "x_mm", "y_mm", "theta_deg",
          "serial", "hole_mm", "notch", "good", "reasons", "images"]


def log_dir(cfg: dict[str, Any]) -> Path:
    d = CODE_ROOT / cfg["logging"]["cycle_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_images(cfg: dict[str, Any], result: CycleResult, detector, inspector) -> Path | None:
    """M1/M3 debug images of the cycle, if the real pipelines were used."""
    m1 = getattr(detector, "last_result", None)
    m3 = getattr(inspector, "last_details", None)
    if m1 is None and m3 is None:
        return None
    out = log_dir(cfg) / time.strftime("%Y%m%d") / f"{time.strftime('%H%M%S')}_c{result.cycle_id:03d}"
    out.mkdir(parents=True, exist_ok=True)
    if m1 is not None:
        cv2.imwrite(str(out / "m1_overlay.jpg"), m1.overlay_image(detector.last_image))
        cv2.imwrite(str(out / "m1_workspace.jpg"), m1.debug_image(detector.last_image))
    if m3 is not None:
        cv2.imwrite(str(out / "m3_inspection.jpg"), m3.debug_image(inspector.last_image, cfg["inspection"]))
    return out


def append_csv(cfg: dict[str, Any], result: CycleResult, images: Path | None = None) -> Path:
    f = log_dir(cfg) / f"cycles_{time.strftime('%Y%m%d')}.csv"
    new = not f.exists()
    p, r = result.pose, result.inspection
    row = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result.started_at)),
        "cycle": result.cycle_id, "ok": result.ok, "error": result.error or "",
        "duration_s": f"{result.duration_s:.2f}" if result.duration_s else "",
        "x_mm": f"{p.x_mm:.1f}" if p else "", "y_mm": f"{p.y_mm:.1f}" if p else "",
        "theta_deg": f"{p.theta_deg:.1f}" if p else "",
        "serial": (r.serial_number or "") if r else "",
        "hole_mm": f"{r.hole_diameter_mm:.3f}" if r and r.hole_diameter_mm else "",
        "notch": r.notch_present if r else "", "good": r.is_good if r else "",
        "reasons": "; ".join(r.reasons) if r else "", "images": str(images or ""),
    }
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter=";")
        if new:
            w.writeheader()
        w.writerow(row)
    return f
