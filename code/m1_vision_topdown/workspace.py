"""Find the workspace in the top-down image and rectify it.

Workspace frame: origin at the inner bottom-left corner of the white frame, x to the
right, y up (as seen from the camera), units mm. The rectified image has
`px_per_mm` resolution and covers [0, W] x [0, H] mm.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.interfaces import VisionError
from common.trace import Trace, draw_candidates


@dataclass
class Workspace:
    H_img2rect: np.ndarray      # homography: image px -> rectified px
    size_mm: tuple[float, float]
    px_per_mm: float
    method: str
    corners_img: np.ndarray     # 4x2 reference points in the image (for debug drawing)

    @property
    def rect_size_px(self) -> tuple[int, int]:
        w, h = self.size_mm
        return int(round(w * self.px_per_mm)), int(round(h * self.px_per_mm))

    def rectify(self, img: np.ndarray) -> np.ndarray:
        return cv2.warpPerspective(img, self.H_img2rect, self.rect_size_px)

    def rect_to_mm(self, u: float, v: float) -> tuple[float, float]:
        """Rectified pixel -> workspace mm (y axis flipped: image down = workspace -y)."""
        return u / self.px_per_mm, self.size_mm[1] - v / self.px_per_mm

    def mm_to_rect(self, x: float, y: float) -> tuple[float, float]:
        return x * self.px_per_mm, (self.size_mm[1] - y) * self.px_per_mm


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left (image coordinates)."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
                    dtype=np.float32)


def _aruco_detector(dict_name: str) -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMax = 53
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    return cv2.aruco.ArucoDetector(dictionary, params)


def find_workspace_aruco(img: np.ndarray, cfg: dict[str, Any], trace: Trace | None = None) -> Workspace:
    """Homography from the 4 marker centres to their known workspace positions."""
    ws = cfg["workspace"]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    corners, ids, _ = _aruco_detector(ws["aruco_dictionary"]).detectMarkers(gray)
    markers_mm = {int(k): v for k, v in ws["markers_mm"].items()}
    found = {} if ids is None else {int(i): c.reshape(4, 2).mean(axis=0)
                                    for i, c in zip(ids.ravel(), corners)}
    if trace is not None:
        vis = img.copy()
        cv2.aruco.drawDetectedMarkers(vis, corners, ids)
        trace.add("aruco_markers", vis)
    missing = sorted(set(markers_mm) - set(found))
    if missing:
        raise VisionError(f"ArUco markers not found: {missing} (found {sorted(found)})")

    tmp = Workspace(np.eye(3), tuple(ws["size_mm"]), ws["px_per_mm"], "aruco", np.zeros((4, 2)))
    src = np.array([found[i] for i in sorted(markers_mm)], dtype=np.float32)
    dst = np.array([tmp.mm_to_rect(*markers_mm[i]) for i in sorted(markers_mm)], dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    tmp.H_img2rect, tmp.corners_img = H, src
    return tmp


def find_workspace_white_frame(img: np.ndarray, cfg: dict[str, Any],
                               trace: Trace | None = None) -> Workspace:
    """Inner edge of the white frame = workspace boundary."""
    ws = cfg["workspace"]
    scale = 1000.0 / max(img.shape[:2])          # detect on a downscaled copy
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    white = ((hsv[..., 1] < 60) & (hsv[..., 2] > 170)).astype(np.uint8) * 255
    if trace is not None:
        trace.add("white_mask", white)
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    if trace is not None:
        trace.add("white_closed", white)

    contours, hierarchy = cv2.findContours(white, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for i, c in enumerate(contours):
        if hierarchy[0][i][3] < 0:               # only holes (inner boundaries)
            continue
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        area = cv2.contourArea(c)
        if len(approx) == 4 and cv2.isContourConvex(approx) and (best is None or area > best[0]):
            best = (area, approx)
    if trace is not None:
        holes = [c for i, c in enumerate(contours) if hierarchy[0][i][3] >= 0]
        trace.add("white_frame", draw_candidates(small, holes, None if best is None else best[1]))
    if best is None or best[0] < 0.05 * small.shape[0] * small.shape[1]:
        raise VisionError("White workspace frame not found")

    corners = order_corners(best[1].reshape(4, 2) / scale)
    w, h = ws["size_mm"]
    ppm = ws["px_per_mm"]
    dst = np.array([[0, 0], [w * ppm, 0], [w * ppm, h * ppm], [0, h * ppm]], dtype=np.float32)
    H = cv2.getPerspectiveTransform(corners, dst)
    return Workspace(H, (w, h), ppm, "white_frame", corners)


def find_workspace(img: np.ndarray, cfg: dict[str, Any], trace: Trace | None = None) -> Workspace:
    method = cfg["workspace"]["method"]
    if method == "aruco":
        return find_workspace_aruco(img, cfg, trace)
    if method == "white_frame":
        return find_workspace_white_frame(img, cfg, trace)
    if method == "auto":
        try:
            return find_workspace_aruco(img, cfg, trace)
        except VisionError:
            return find_workspace_white_frame(img, cfg, trace)
    raise ValueError(f"Unknown workspace method: {method}")
