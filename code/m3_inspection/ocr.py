"""Serial number OCR with EasyOCR (lazy loaded, the model load takes a few seconds)."""
from __future__ import annotations

import logging
import re

import cv2
import numpy as np

from common.interfaces import InspectionError

log = logging.getLogger(__name__)


class SerialReader:
    def __init__(self, allowlist: str = "0123456789", gpu: bool = False):
        self._allowlist = allowlist
        self._gpu = gpu
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            try:
                import easyocr
            except ImportError as e:
                raise InspectionError("EasyOCR not installed: pip install easyocr") from e
            log.info("Loading EasyOCR model ...")
            self._reader = easyocr.Reader(["en"], gpu=self._gpu, verbose=False)
        return self._reader

    def read(self, roi: np.ndarray, pattern: str) -> tuple[str | None, float]:
        """Best text in the ROI matching `pattern`. Returns (text, confidence)."""
        if roi.shape[0] < 64:  # small text -> upscale for the detector
            f = 64 / roi.shape[0]
            roi = cv2.resize(roi, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        results = self._get_reader().readtext(roi, allowlist=self._allowlist, detail=1)
        candidates = [(text.replace(" ", ""), float(conf)) for _, text, conf in results]
        log.debug("OCR candidates: %s", candidates)
        matching = [c for c in candidates if re.fullmatch(pattern, c[0])]
        if matching:
            return max(matching, key=lambda c: c[1])
        if candidates:  # report what was read, validation fails later
            return max(candidates, key=lambda c: c[1])
        return None, 0.0
