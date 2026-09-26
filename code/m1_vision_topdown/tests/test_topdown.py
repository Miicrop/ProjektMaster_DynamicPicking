import copy
import glob
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from common.config import load_config
from common.interfaces import VisionError
from m1_vision_topdown import TopDownPipeline
from m1_vision_topdown.make_markers import marker_with_border
from m1_vision_topdown.workspace import find_workspace_aruco

CFG = load_config()
DATA = Path(__file__).parent / "data"
MARGIN = 70.0   # mm around the workspace in the synthetic scene
S = 2.0         # px per mm in the synthetic scene


def _scene_px(x, y, h):
    return (x + MARGIN) * S, (h + MARGIN - y) * S


def synth_scene(x_mm, y_mm, theta_deg, part_size=(60.0, 40.0), chamfer=10.0, warp=True):
    """Top-down scene: grey board, white frame, ArUco markers with quiet zone, chamfered part."""
    w, h = CFG["workspace"]["size_mm"]
    img = np.full((int((h + 2 * MARGIN) * S), int((w + 2 * MARGIN) * S), 3), 70, np.uint8)

    band = 15.0  # white frame outside [0, w] x [0, h]
    p0, p1 = _scene_px(-band, h + band, h), _scene_px(w + band, -band, h)
    cv2.rectangle(img, tuple(map(int, p0)), tuple(map(int, p1)), (235, 235, 235), -1)
    q0, q1 = _scene_px(0, h, h), _scene_px(w, 0, h)
    cv2.rectangle(img, tuple(map(int, q0)), tuple(map(int, q1)), (70, 70, 70), -1)

    for mid, (mx, my) in CFG["workspace"]["markers_mm"].items():
        m = marker_with_border(CFG["workspace"]["aruco_dictionary"], int(mid), 30.0, dpi=int(S * 25.4))
        m = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
        cx, cy = _scene_px(mx, my, h)
        y0, x0 = int(cy - m.shape[0] / 2), int(cx - m.shape[1] / 2)
        img[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m

    # part outline in part frame (x = long axis, chamfer at the +x end, +y side)
    L, W = part_size
    poly = np.array([[-L / 2, -W / 2], [L / 2, -W / 2], [L / 2, W / 2 - chamfer],
                     [L / 2 - chamfer, W / 2], [-L / 2, W / 2]])
    c, s = math.cos(math.radians(theta_deg)), math.sin(math.radians(theta_deg))
    pts = poly @ np.array([[c, s], [-s, c]]) + [x_mm, y_mm]
    cv2.fillPoly(img, [np.array([_scene_px(px, py, h) for px, py in pts], np.int32)], (200, 120, 190))

    if warp:  # mild perspective as from a slightly tilted camera
        hh, ww = img.shape[:2]
        src = np.float32([[0, 0], [ww, 0], [ww, hh], [0, hh]])
        dst = np.float32([[30, 10], [ww - 10, 40], [ww - 40, hh - 20], [5, hh - 5]])
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (ww, hh),
                                  borderValue=(70, 70, 70))
    return img


def _angle_err(a, b, period=360.0):
    d = (a - b) % period
    return min(d, period - d)


@pytest.mark.parametrize("method", ["aruco", "white_frame"])
@pytest.mark.parametrize("x, y, theta", [(200, 200, 0), (120, 300, 35), (310, 90, 200), (250, 150, 300)])
def test_synthetic_pose(method, x, y, theta):
    cfg = copy.deepcopy(CFG)
    cfg["workspace"]["method"] = method
    r = TopDownPipeline(cfg).process(synth_scene(x, y, theta))
    assert r.workspace.method == method
    assert r.part.chamfer_found
    assert r.x_ws_mm == pytest.approx(x, abs=2.0)
    assert r.y_ws_mm == pytest.approx(y, abs=2.0)
    assert _angle_err(r.theta_ws_deg, theta) < 2.0


def test_empty_workspace_raises():
    img = synth_scene(200, 200, 0)
    cfg = copy.deepcopy(CFG)
    cfg["part_topdown"]["min_area_mm2"] = 1e6   # nothing is big enough
    with pytest.raises(VisionError, match="No part"):
        TopDownPipeline(cfg).process(img)


# --- real photos (new_input from 2026-07-31) ------------------------------------------

# Regression values from the first run (workspace size is still a placeholder!)
REAL = {
    "PXL_20260731_081831552.jpg": (103.9, 287.5, 209.7),
    "PXL_20260731_081836652.jpg": (291.5, 106.2, 95.6),
    "PXL_20260731_081841718.jpg": (188.9, 62.5, 234.0),
    "PXL_20260731_081847384.jpg": (113.2, 352.6, 99.5),
}


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_photo_regression(name):
    img = cv2.imread(str(DATA / name))
    r = TopDownPipeline(CFG).process(img)
    x, y, theta = REAL[name]
    assert r.part.chamfer_found
    assert 1.3 < r.part.length_px / r.part.width_px < 1.7
    assert r.x_ws_mm == pytest.approx(x, abs=3.0)
    assert r.y_ws_mm == pytest.approx(y, abs=3.0)
    assert _angle_err(r.theta_ws_deg, theta) < 3.0


def test_real_photo_markers_not_detectable():
    """Known issue: the 3D-printed markers have no white quiet zone (see plan/08)."""
    img = cv2.imread(sorted(glob.glob(str(DATA / "*.jpg")))[0])
    with pytest.raises(VisionError):
        find_workspace_aruco(img, CFG)
