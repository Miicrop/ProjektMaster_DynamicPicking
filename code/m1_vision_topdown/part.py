"""Segment the part in the rectified workspace image and compute its planar pose."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.interfaces import VisionError


@dataclass
class PartPose:
    """Pose in the rectified image (px) and the workspace frame (mm, deg)."""
    u: float
    v: float
    theta_img_deg: float        # image angle (y down) of the part x-axis
    length_px: float
    width_px: float
    chamfer_found: bool
    contour: np.ndarray
    box: np.ndarray             # minAreaRect corners (debug)


def segment_part(rect_img: np.ndarray, cfg: dict[str, Any], px_per_mm: float,
                 border_px: int) -> np.ndarray:
    """Largest blob that is clearly brighter or more colourful than the board.

    Thresholds are relative to the board (median of the workspace image, the part only
    covers a small area), so they adapt to lighting changes.
    """
    pc = cfg["part_topdown"]
    hsv = cv2.cvtColor(rect_img, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1].astype(np.int16), hsv[..., 2].astype(np.int16)
    board_s, board_v = np.median(s), np.median(v)
    mask = ((v > board_v + pc["brightness_delta"])
            | ((s > board_s + pc["saturation_delta"]) & (v > pc["value_min"])))
    mask = mask.astype(np.uint8) * 255
    if border_px > 0:  # ignore the frame edge
        mask[:border_px, :] = mask[-border_px:, :] = 0
        mask[:, :border_px] = mask[:, -border_px:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    min_px = pc["min_area_mm2"] * px_per_mm ** 2
    max_px = pc["max_area_mm2"] * px_per_mm ** 2
    candidates = [c for c in contours if min_px <= cv2.contourArea(c) <= max_px]
    if not candidates:
        raise VisionError("No part found in workspace")
    return max(candidates, key=cv2.contourArea)


def part_pose(contour: np.ndarray, chamfer_min_frac: float = 0.08) -> PartPose:
    """Centroid + orientation.

    The part x-axis is the long axis of the minimum-area rectangle. If a chamfered
    corner is found (rectangle corner far away from the contour), the axis points
    towards the chamfered end -> angle unique in [0, 360). Otherwise [0, 180).
    """
    m = cv2.moments(contour)
    if m["m00"] == 0:
        raise VisionError("Degenerate part contour")
    u, v = m["m10"] / m["m00"], m["m01"] / m["m00"]

    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    e1, e2 = box[1] - box[0], box[2] - box[1]
    long_edge, short_edge = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
    length, width = float(np.linalg.norm(long_edge)), float(np.linalg.norm(short_edge))
    axis = long_edge / length

    # distance of each rectangle corner to the contour (positive = outside the part)
    dists = [-cv2.pointPolygonTest(contour, (float(p[0]), float(p[1])), True) for p in box]
    k = int(np.argmax(dists))
    chamfer = dists[k] > chamfer_min_frac * width
    if chamfer:
        centre = np.array(rect[0])
        if np.dot(box[k] - centre, axis) < 0:
            axis = -axis
    theta = math.degrees(math.atan2(axis[1], axis[0]))
    theta = theta % 360.0 if chamfer else theta % 180.0
    return PartPose(u, v, theta, length, width, bool(chamfer), contour, box)
