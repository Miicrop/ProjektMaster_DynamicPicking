import cv2
import numpy as np

from common.trace import Trace


def test_add_keeps_a_copy_in_order():
    t = Trace()
    img = np.zeros((4, 4), np.uint8)
    t.add("first", img)
    img[:] = 255                         # later in-place change must not leak into the trace
    t.add("second", img)
    assert t.names == ["first", "second"]
    assert t.steps[0][1].max() == 0 and t.steps[1][1].min() == 255


def test_save_writes_numbered_files(tmp_path):
    t = Trace()
    t.add("mask", np.full((4, 4), 255, np.uint8))
    t.add("result", np.zeros((4, 4, 3), np.uint8))
    files = t.save(tmp_path, "m1")
    assert [f.name for f in files] == ["m1_01_mask.png", "m1_02_result.jpg"]
    assert cv2.imread(str(files[0]), cv2.IMREAD_UNCHANGED).max() == 255   # lossless
