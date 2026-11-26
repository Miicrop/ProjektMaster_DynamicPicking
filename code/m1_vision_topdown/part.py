"""Segment the part in the rectified workspace image and compute its planar pose."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.interfaces import VisionError
from common.trace import Trace, draw_candidates


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
    # side of the part axis the chamfer lies on in the image (+1 / -1, 0 = no or ambiguous chamfer). Seen from
    # above, a part lying upside down shows the chamfer mirrored -> the other sign.
    chamfer_side: int = 0


def segment_part(rect_img: np.ndarray, cfg: dict[str, Any], px_per_mm: float,
                 border_px: int, trace: Trace | None = None) -> np.ndarray:
    """Largest blob that is clearly brighter or more colourful than the board.

    Thresholds are relative to the board (median of the workspace image, the part only
    covers a small area), so they adapt to lighting changes. Colourfulness = Lab chroma, not
    HSV saturation: S = (max-min)/max blows up a faint colour cast on the dark board (bluish
    reflection: S ~55, chroma ~10; part: chroma 40-50).
    """
    pc = cfg["part_topdown"]
    v = cv2.cvtColor(rect_img, cv2.COLOR_BGR2HSV)[..., 2].astype(np.int16)
    lab = cv2.cvtColor(rect_img, cv2.COLOR_BGR2LAB).astype(np.float32)
    chroma = np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)
    board_v, board_c = np.median(v), np.median(chroma)
    mask = (v > board_v + pc["brightness_delta"]) | (chroma > board_c + pc["chroma_delta"])
    mask = mask.astype(np.uint8) * 255
    if trace is not None:
        trace.add("part_mask", mask)
    if border_px > 0:  # ignore the frame edge
        mask[:border_px, :] = mask[-border_px:, :] = 0
        mask[:, :border_px] = mask[:, -border_px:] = 0
    if trace is not None:
        trace.add("part_mask_border", mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if trace is not None:
        trace.add("part_opened", mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    if trace is not None:
        trace.add("part_closed", mask)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    min_px = pc["min_area_mm2"] * px_per_mm ** 2
    max_px = pc["max_area_mm2"] * px_per_mm ** 2
    sized = [(c, shape_mismatch(c, px_per_mm, pc)) for c in contours
             if min_px <= cv2.contourArea(c) <= max_px]
    candidates = [c for c, why in sized if why is None]
    rejected = [why for _, why in sized if why is not None]
    best = max(candidates, key=cv2.contourArea) if candidates else None
    if trace is not None:   # all blobs grey with area, the selected part red
        trace.add("part_candidates", draw_candidates(
            rect_img, contours, best, [f"{cv2.contourArea(c) / px_per_mm ** 2:.0f} mm2" for c in contours]))
    if best is None:
        if rejected:   # something part-sized but not part-shaped, e.g. a hand in the workspace
            raise VisionError(f"No part found in workspace (wrong shape: {'; '.join(rejected)})")
        raise VisionError("No part found in workspace")
    return best


def shape_mismatch(contour: np.ndarray, px_per_mm: float, pc: dict[str, Any]) -> str | None:
    """Why the blob is not the part (size of its min-area rectangle or fill ratio), None if it fits.

    Without this a hand reaching into the workspace (bright, ~14000 mm2) passed the area check and
    the cycle started (lab 2026-11-26). Lab parts measure 59-61 x 38.5-41 mm, fill 0.90-0.95; the
    phone test photos up to 69 x 46 mm (lower camera -> more parallax of the part top).
    """
    size = pc.get("part_size_mm")
    if not size:
        return None
    (_, _), (a, b), _ = cv2.minAreaRect(contour)
    length, width = max(a, b) / px_per_mm, min(a, b) / px_per_mm
    tol = pc["part_size_tolerance"]
    if abs(length - size[0]) > tol * size[0] or abs(width - size[1]) > tol * size[1]:
        return f"{length:.0f} x {width:.0f} mm instead of {size[0]:.0f} x {size[1]:.0f} mm"
    fill = cv2.contourArea(contour) / max(a * b, 1e-6)
    if fill < pc["part_fill_min"]:
        return f"fill {fill:.2f} < {pc['part_fill_min']}"
    return None


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
    side = 0
    if chamfer:
        to_corner = box[k] - np.array(rect[0])
        if np.dot(to_corner, axis) < 0:
            axis = -axis
        # only with exactly one cut corner: a part clipped at the workspace edge has a second one
        if sorted(dists)[-2] <= chamfer_min_frac * width:
            side = 1 if axis[0] * to_corner[1] - axis[1] * to_corner[0] > 0 else -1   # 2D cross product
    theta = math.degrees(math.atan2(axis[1], axis[0]))
    theta = theta % 360.0 if chamfer else theta % 180.0
    return PartPose(u, v, theta, length, width, bool(chamfer), contour, box, side)


def draw_part_pose(rect_img: np.ndarray, p: PartPose) -> np.ndarray:
    """minAreaRect, chamfer corner (corner farthest from the contour) and part x-axis."""
    out = rect_img.copy()
    cv2.drawContours(out, [p.contour], -1, (0, 0, 255), 2)
    cv2.drawContours(out, [p.box.astype(np.int32)], -1, (0, 255, 0), 1)
    if p.chamfer_found:
        dists = [-cv2.pointPolygonTest(p.contour, (float(q[0]), float(q[1])), True) for q in p.box]
        k = p.box[int(np.argmax(dists))]
        cv2.circle(out, (int(k[0]), int(k[1])), 8, (0, 255, 255), 2)
    tip = (int(p.u + 0.6 * p.length_px * math.cos(math.radians(p.theta_img_deg))),
           int(p.v + 0.6 * p.length_px * math.sin(math.radians(p.theta_img_deg))))
    cv2.arrowedLine(out, (int(p.u), int(p.v)), tip, (255, 255, 0), 2, tipLength=0.3)
    cv2.drawMarker(out, (int(p.u), int(p.v)), (255, 255, 0), cv2.MARKER_CROSS, 12, 2)
    return out
