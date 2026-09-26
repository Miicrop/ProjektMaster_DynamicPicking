"""Image processing for the side-view inspection.

All feature regions are defined relative to the part bounding box, so the result does
not depend on the exact distance to the camera. The visible part height is the length
reference for mm conversion (see config inspection.part_height_mm).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.interfaces import InspectionError

Box = tuple[int, int, int, int]   # x, y, w, h


def locate_part(img: np.ndarray, ic: dict[str, Any]) -> Box:
    """Bounding box of the part (coloured body incl. label and holes)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    lo, hi = ic["part_hue"]
    mask = ((h >= lo) & (h <= hi) & (s >= ic["part_saturation_min"])
            & (v >= ic["part_value_min"])).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise InspectionError("Part not found in inspection image")
    height = cv2.boundingRect(max(contours, key=cv2.contourArea))[3]

    # close vertically over the part height -> label and holes become part of the body
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, height // 4), max(3, height)))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    box = cv2.boundingRect(max(contours, key=cv2.contourArea))
    if box[3] < 20:
        raise InspectionError("Part too small in inspection image")
    return box


def sub_roi(img: np.ndarray, box: Box, rel: list[float]) -> tuple[np.ndarray, tuple[int, int]]:
    """Crop a region given relative to the part box. Returns (crop, offset)."""
    x, y, w, h = box
    x0, y0 = int(x + rel[0] * w), int(y + rel[1] * h)
    x1, y1 = int(x + rel[2] * w), int(y + rel[3] * h)
    return img[y0:y1, x0:x1], (x0, y0)


@dataclass
class Feature:
    contour: np.ndarray         # in full-image coordinates
    area_px: float
    shape_score: float          # circularity (hole) or rectangularity (notch), 0..1


def _enclosed(contours, roi_shape, offset, min_area) -> list[tuple[np.ndarray, float]]:
    """Contours not touching the ROI border, shifted to full-image coordinates."""
    rh, rw = roi_shape[:2]
    result = []
    for c in contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bx <= 1 or by <= 1 or bx + bw >= rw - 1 or by + bh >= rh - 1:
            continue
        area = cv2.contourArea(c)
        if area >= min_area:
            result.append((c + np.array(offset), area))
    return result


def _non_face_features(roi: np.ndarray, offset: tuple[int, int], part_h: int,
                       ic: dict[str, Any]) -> list[tuple[np.ndarray, float]]:
    """Regions that are NOT bright part-coloured face (used for the through-hole).

    Covers dark bore walls as well as bright background visible through the hole.
    Face brightness reference = 70th percentile of the part-coloured pixels.
    """
    hsv = cv2.GaussianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), (5, 5), 0)
    h, s, v = cv2.split(hsv)
    lo, hi = ic["part_hue"]
    coloured = (h >= lo) & (h <= hi) & (s >= ic["part_saturation_min"])
    if coloured.sum() < 50:
        return []
    face = coloured & (v > ic["face_brightness_frac"] * np.percentile(v[coloured], 70))
    mask = cv2.morphologyEx((~face).astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # the hole ROI spans the full part height: only top/bottom contact disqualifies
    rh = roi.shape[0]
    return [(c + np.array(offset), cv2.contourArea(c)) for c in contours
            if cv2.boundingRect(c)[1] > 2 and sum(cv2.boundingRect(c)[1::2]) < rh - 2
            and cv2.contourArea(c) >= 0.01 * part_h * part_h]


def _region_features(roi: np.ndarray, offset: tuple[int, int], part_h: int,
                     ic: dict[str, Any]) -> list[tuple[np.ndarray, float]]:
    """Regions that differ from the surrounding part face (used for the notch).

    The face reference is the ROI border (mostly flat face). A pixel belongs to a
    feature if it is clearly darker (bore wall, shadow) or clearly differently
    saturated (background seen through a hole, coloured inner wall).
    """
    hsv = cv2.GaussianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), (5, 5), 0)
    s, v = hsv[..., 1].astype(np.int16), hsv[..., 2].astype(np.int16)
    ring = np.zeros(v.shape, bool)
    ring[:3, :] = ring[-3:, :] = ring[:, :3] = ring[:, -3:] = True
    face_s, face_v = np.median(s[ring]), np.median(v[ring])
    differs = (v < ic["face_brightness_frac"] * face_v) | (np.abs(s - face_s) > ic["face_saturation_delta"])
    mask = cv2.morphologyEx(differs.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return _enclosed(contours, roi.shape, offset, 0.01 * part_h * part_h)


def _edge_features(roi: np.ndarray, offset: tuple[int, int], part_h: int) -> list[tuple[np.ndarray, float]]:
    """Closed edge outlines (convex hulls) - for openings with the same colour as the face."""
    k = max(3, (part_h // 40) | 1)
    gray = cv2.GaussianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), (k, k), 0)
    edges = cv2.morphologyEx(cv2.Canny(gray, 30, 90), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return _enclosed([cv2.convexHull(c) for c in contours], roi.shape, offset, 0.01 * part_h * part_h)


def find_hole(img: np.ndarray, box: Box, ic: dict[str, Any]) -> tuple[Feature, float] | None:
    """Most circular enclosed feature in the hole ROI. Returns (feature, diameter_px)."""
    roi, off = sub_roi(img, box, ic["hole_roi"])
    best = None
    for c, area in _non_face_features(roi, off, box[3], ic):
        if area < 0.05 * box[3] ** 2 or len(c) < 5:
            continue
        (_, _), r = cv2.minEnclosingCircle(c)
        circularity = area / (np.pi * r * r)
        if best is None or circularity > best.shape_score:
            best = Feature(c, area, circularity)
    if best is None or best.shape_score < 0.75:
        return None
    (_, _), (a, b), _ = cv2.fitEllipse(best.contour)
    return best, (a + b) / 2.0


def find_notch(img: np.ndarray, box: Box, ic: dict[str, Any]) -> Feature | None:
    """Most rectangular enclosed feature in the notch ROI (region- or edge-based)."""
    roi, off = sub_roi(img, box, ic["notch_roi"])
    best = None
    candidates = _region_features(roi, off, box[3], ic) + _edge_features(roi, off, box[3])
    for c, area in candidates:
        if not 0.02 * box[3] ** 2 < area < 0.3 * box[3] ** 2:
            continue
        (_, _), (w, h), _ = cv2.minAreaRect(c)
        if w == 0 or h == 0 or not 0.5 < w / h < 2.0:
            continue
        rectangularity = area / (w * h)
        if best is None or rectangularity > best.shape_score:
            best = Feature(c, area, rectangularity)
    if best is None or best.shape_score < 0.7:
        return None
    return best
