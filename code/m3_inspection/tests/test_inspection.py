from pathlib import Path

import cv2
import numpy as np
import pytest

from common.config import load_config
from m3_inspection import InspectionPipeline
from m3_inspection.features import find_hole, find_notch, locate_part

CFG = load_config()
IC = CFG["inspection"]
DATA = Path(__file__).parent / "data"
IMAGES = sorted(p.name for p in DATA.glob("*.jpg"))


class FakeReader:
    """Stands in for EasyOCR where OCR is not under test."""

    def read(self, roi, pattern):
        return "69420", 0.99


def _paint_over(img, contour, grow=0.15):
    """Paint a feature with the surrounding face colour -> simulated defect."""
    out = img.copy()
    x, y, w, h = cv2.boundingRect(contour)
    pad = int(grow * max(w, h))
    ring = out[max(0, y - 2 * pad):y + h + 2 * pad, x + w + pad:x + w + 2 * pad]
    colour = np.median(ring.reshape(-1, 3), axis=0)
    cv2.rectangle(out, (x - pad, y - pad), (x + w + pad, y + h + pad), colour.tolist(), -1)
    return out


@pytest.fixture(scope="module")
def pipeline_fake_ocr():
    return InspectionPipeline(CFG, reader=FakeReader())


@pytest.mark.parametrize("name", IMAGES)
def test_real_images_are_good(pipeline_fake_ocr, name):
    d = pipeline_fake_ocr.process(cv2.imread(str(DATA / name)))
    assert d.result.is_good, d.result.reasons
    # hole diameter relative to part height is scale independent: 0.647 .. 0.663 measured
    assert 0.62 < d.hole_diameter_px / d.part_box[3] < 0.69
    assert d.notch is not None


@pytest.mark.parametrize("name", IMAGES)
def test_missing_notch_is_bad(pipeline_fake_ocr, name):
    img = cv2.imread(str(DATA / name))
    notch = find_notch(img, locate_part(img, IC), IC)
    defect = _paint_over(img, notch.contour)
    r = pipeline_fake_ocr.process(defect).result
    assert not r.is_good and r.notch_present is False


@pytest.mark.parametrize("name", IMAGES)
def test_missing_hole_is_bad(pipeline_fake_ocr, name):
    img = cv2.imread(str(DATA / name))
    hole, _ = find_hole(img, locate_part(img, IC), IC)
    defect = _paint_over(img, hole.contour, grow=0.05)
    r = pipeline_fake_ocr.process(defect).result
    assert not r.is_good and r.hole_diameter_mm is None


def test_no_part_raises(pipeline_fake_ocr):
    from common.interfaces import InspectionError
    with pytest.raises(InspectionError):
        pipeline_fake_ocr.process(np.full((400, 600, 3), 200, np.uint8))


# --- real OCR (loads the EasyOCR model, a few seconds) --------------------------------

@pytest.fixture(scope="module")
def pipeline_real_ocr():
    pytest.importorskip("easyocr")
    return InspectionPipeline(CFG)


@pytest.mark.parametrize("name", IMAGES)
def test_ocr_reads_serial(pipeline_real_ocr, name):
    d = pipeline_real_ocr.process(cv2.imread(str(DATA / name)))
    assert d.result.serial_number == "69420"


# --- intermediate steps for documentation ---------------------------------------------

def test_trace_collects_steps(pipeline_fake_ocr):
    from common.trace import Trace
    img = cv2.imread(str(DATA / IMAGES[0]))
    trace = Trace()
    d = pipeline_fake_ocr.process(img, trace)
    assert trace.names == ["original", "part_mask", "part_opened", "part_closed", "part_box",
                           "label_roi", "hole_roi", "hole_mask", "hole_candidates",
                           "notch_roi", "notch_region_mask", "notch_edges", "notch_candidates", "result"]
    plain = pipeline_fake_ocr.process(img)
    assert (d.hole_diameter_px, d.result.is_good) == (plain.hole_diameter_px, plain.result.is_good)


def test_inspector_keeps_trace_only_when_enabled():
    from common.camera import FileCamera
    from m3_inspection import CameraInspector
    insp = CameraInspector(CFG, FileCamera(str(DATA / "*.jpg")), InspectionPipeline(CFG, reader=FakeReader()))
    insp.inspect()
    assert insp.last_trace is None
    insp.trace_steps = True
    insp.inspect()
    assert insp.last_trace.names[0] == "original" and insp.last_trace.names[-1] == "result"
