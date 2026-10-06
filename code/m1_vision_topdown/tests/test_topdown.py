import copy
import glob
import math
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from common.config import load_config
from common.interfaces import VisionError
from m1_vision_topdown import TopDownPipeline
from m1_vision_topdown.make_markers import marker_with_border
from m1_vision_topdown.workspace import find_workspace_aruco

CFG = load_config()
DATA = Path(__file__).parent / "data"
# real photos have their own workspace section (see data/workspace.yaml)
PHOTO_CFG = copy.deepcopy(CFG)
PHOTO_CFG["workspace"] = yaml.safe_load((DATA / "workspace.yaml").read_text(encoding="utf-8"))
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
@pytest.mark.parametrize("x, y, theta", [(200, 200, 0), (120, 300, 35), (280, 90, 200), (250, 150, 300)])
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


# --- real photos (printed markers glued on, 2026-10-05) ----------------------------------

PHOTOS = sorted(p.name for p in DATA.glob("*.jpg"))


@pytest.mark.parametrize("name", PHOTOS)
def test_real_photo_markers_found(name):
    find_workspace_aruco(cv2.imread(str(DATA / name)), PHOTO_CFG)


@pytest.mark.parametrize("name", PHOTOS)
def test_real_photo_part_found(name):
    """The purple part is selected, not a bluish reflection on the dark board.

    Without ground truth: the centroid must lie on part-coloured pixels and the blob must have
    the part's size (64-69 x 43-46 mm, varies with the visible side faces, see README
    "Perspektive"). Before the Lab-chroma fix the reflection blob was 109 x 82 mm.
    """
    img = cv2.imread(str(DATA / name))
    r = TopDownPipeline(PHOTO_CFG).process(img)
    lab = cv2.cvtColor(r.workspace.rectify(img), cv2.COLOR_BGR2LAB).astype(float)
    a, b = lab[int(r.part.v), int(r.part.u), 1:] - 128
    assert math.hypot(a, b) > 25
    ppm = r.workspace.px_per_mm
    assert 60 < r.part.length_px / ppm < 75
    assert 40 < r.part.width_px / ppm < 50
    assert r.part.chamfer_found


def test_real_photo_same_scene_three_heights():
    """Three photos of the same scene from different camera heights give the same pose."""
    names = ("PXL_20261005_130218511.jpg", "PXL_20261005_130221409.jpg", "PXL_20261005_130225649.jpg")
    rs = [TopDownPipeline(PHOTO_CFG).process(cv2.imread(str(DATA / n))) for n in names]
    for r in rs[1:]:
        assert math.hypot(r.x_ws_mm - rs[0].x_ws_mm, r.y_ws_mm - rs[0].y_ws_mm) < 2.0
        assert _angle_err(r.theta_ws_deg, rs[0].theta_ws_deg) < 2.0


# --- intermediate steps for documentation ---------------------------------------------

@pytest.mark.parametrize("method, ws_steps", [
    ("aruco", ["aruco_markers"]),
    ("white_frame", ["white_mask", "white_closed", "white_frame"]),
])
def test_trace_collects_steps(method, ws_steps):
    from common.trace import Trace
    cfg = copy.deepcopy(CFG)
    cfg["workspace"]["method"] = method
    img = synth_scene(200, 200, 0)
    trace = Trace()
    r = TopDownPipeline(cfg).process(img, trace)
    assert trace.names == ["original", *ws_steps, "rectified", "part_mask", "part_mask_border",
                           "part_opened", "part_closed", "part_candidates", "part_pose", "result"]
    plain = TopDownPipeline(cfg).process(img)
    assert (r.x_ws_mm, r.y_ws_mm, r.theta_ws_deg) == (plain.x_ws_mm, plain.y_ws_mm, plain.theta_ws_deg)


def test_detector_keeps_trace_only_when_enabled():
    from common.camera import FileCamera
    from m1_vision_topdown import TopDownDetector
    det = TopDownDetector(PHOTO_CFG, FileCamera(str(DATA / "*.jpg")))
    det.detect()
    assert det.last_trace is None
    det.trace_steps = True
    det.detect()
    assert det.last_trace.names[0] == "original" and det.last_trace.names[-1] == "result"
