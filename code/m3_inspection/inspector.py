"""M3 - side-camera inspection: serial number, hole diameter, notch.

See plan/04_modul3_sichtpruefung.md
"""
from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.camera import open_camera
from common.interfaces import InspectionError, InspectionResult, Inspector
from m3_inspection.features import Box, Feature, find_hole, find_notch, locate_part, sub_roi
from m3_inspection.ocr import SerialReader

log = logging.getLogger(__name__)


def evaluate(cfg: dict[str, Any], serial: str | None, hole_mm: float | None,
             notch: bool | None) -> InspectionResult:
    """Good/bad decision from the individual measurements. Shared by mock and real inspector."""
    ic = cfg["inspection"]
    reasons = []
    if serial is None or not re.fullmatch(ic["serial_pattern"], serial):
        reasons.append(f"serial number invalid: {serial!r}")
    if hole_mm is None:
        reasons.append("hole not found")
    elif abs(hole_mm - ic["hole_nominal_mm"]) > ic["hole_tolerance_mm"]:
        reasons.append(f"hole diameter {hole_mm:.3f} mm out of tolerance "
                       f"{ic['hole_nominal_mm']} +/- {ic['hole_tolerance_mm']} mm")
    if not notch:
        reasons.append("notch missing")
    return InspectionResult(serial, hole_mm, notch, is_good=not reasons, reasons=reasons)


@dataclass
class InspectionDetails:
    result: InspectionResult
    part_box: Box
    ocr_confidence: float
    hole: Feature | None
    hole_diameter_px: float | None
    notch: Feature | None

    def debug_image(self, img: np.ndarray, ic: dict[str, Any] | None = None) -> np.ndarray:
        """Full image with part box, feature ROIs (if `ic` given), hole and notch."""
        out = img.copy()
        x, y, w, h = self.part_box
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 3)
        if ic is not None:
            for key, colour in (("label_roi", (200, 200, 0)), ("hole_roi", (0, 128, 255)),
                                ("notch_roi", (255, 0, 255))):
                r = ic[key]
                cv2.rectangle(out, (int(x + r[0] * w), int(y + r[1] * h)),
                              (int(x + r[2] * w), int(y + r[3] * h)), colour, 2)
        if self.hole is not None:
            cv2.drawContours(out, [self.hole.contour], -1, (0, 0, 255), 3)
        if self.notch is not None:
            cv2.drawContours(out, [self.notch.contour], -1, (255, 0, 0), 3)
        r = self.result
        lines = [f"{'GOOD' if r.is_good else 'BAD'}  serial={r.serial_number} "
                 f"({self.ocr_confidence:.2f})",
                 f"hole={r.hole_diameter_mm and round(r.hole_diameter_mm, 2)} mm  notch={r.notch_present}"]
        lines += r.reasons
        for i, t in enumerate(lines):
            cv2.putText(out, t, (20, 60 + 50 * i), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                        (0, 160, 0) if r.is_good else (0, 0, 255), 3)
        return out

    def part_crop(self, img: np.ndarray, ic: dict[str, Any], margin: float = 0.15) -> np.ndarray:
        """Zoom on the part with ROIs - the view needed when tuning the ROIs."""
        full = self.debug_image(img, ic)
        x, y, w, h = self.part_box
        m = int(margin * w)
        return full[max(0, y - m):y + h + m, max(0, x - m):x + w + m]


class InspectionPipeline:
    """Image in, InspectionResult out. No camera access -> directly testable."""

    def __init__(self, cfg: dict[str, Any], reader: SerialReader | None = None):
        self.cfg = cfg
        self.reader = reader or SerialReader()

    def process(self, img: np.ndarray) -> InspectionDetails:
        ic = self.cfg["inspection"]
        box = locate_part(img, ic)
        mm_per_px = ic["part_height_mm"] / box[3]

        label, _ = sub_roi(img, box, ic["label_roi"])
        serial, conf = self.reader.read(label, ic["serial_pattern"])
        if conf < ic["ocr_min_confidence"]:
            log.info("OCR confidence %.2f too low for %r", conf, serial)
            serial = None

        hole = find_hole(img, box, ic)
        hole_feature, hole_px = hole if hole else (None, None)
        hole_mm = hole_px * mm_per_px if hole_px else None

        notch = find_notch(img, box, ic)
        result = evaluate(self.cfg, serial, hole_mm, notch is not None)
        return InspectionDetails(result, box, conf, hole_feature, hole_px, notch)


class CameraInspector(Inspector):
    """Real M3 inspector: camera + InspectionPipeline."""

    def __init__(self, cfg: dict[str, Any], camera=None, pipeline: InspectionPipeline | None = None):
        self._pipeline = pipeline or InspectionPipeline(cfg)
        self._owns_camera = camera is None
        self._camera = camera or open_camera(cfg["inspection_camera"])
        self.last_details: InspectionDetails | None = None
        self.last_image: np.ndarray | None = None

    def inspect(self) -> InspectionResult:
        img = self._camera.read()
        self.last_image = img
        self.last_details = self._pipeline.process(img)
        log.info("Inspection: %s", self.last_details.result)
        return self.last_details.result

    def close(self) -> None:
        if self._owns_camera:
            self._camera.close()


class MockInspector(Inspector):
    """Generates random measurements; roughly `good_ratio` of the parts are good."""

    def __init__(self, cfg: dict[str, Any], good_ratio: float = 0.7, seed: int | None = None):
        self._cfg = cfg
        self._good_ratio = good_ratio
        self._rng = random.Random(seed)

    def inspect(self) -> InspectionResult:
        ic = self._cfg["inspection"]
        serial = "".join(self._rng.choices("0123456789", k=5))
        hole = ic["hole_nominal_mm"] + self._rng.uniform(-0.5, 0.5) * ic["hole_tolerance_mm"]
        notch = True
        if self._rng.random() > self._good_ratio:
            defect = self._rng.choice(["serial", "hole", "notch"])
            if defect == "serial":
                serial = None
            elif defect == "hole":
                hole += 3 * ic["hole_tolerance_mm"]
            else:
                notch = False
        result = evaluate(self._cfg, serial, hole, notch)
        log.info("Mock inspection: %s", result)
        return result


__all__ = ["CameraInspector", "InspectionError", "InspectionPipeline", "MockInspector", "evaluate"]
