"""Intermediate images of an image-processing run (masks, ROIs, candidates) for documentation.

Processing functions take an optional `trace`; without one they do no extra work.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class Trace:
    def __init__(self) -> None:
        self.steps: list[tuple[str, np.ndarray]] = []

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.steps]

    def add(self, name: str, img: np.ndarray) -> None:
        """Store a copy - callers often keep modifying the array in place."""
        self.steps.append((name, img.copy()))

    def save(self, directory: str | Path, prefix: str) -> list[Path]:
        """Write the steps as <prefix>_<nn>_<name>.png/.jpg.

        Masks (single channel) lossless as PNG so they stay exactly binary, colour images as
        JPG - full camera frames would be ~10 MB each as PNG.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for i, (name, img) in enumerate(self.steps, 1):
            f = directory / f"{prefix}_{i:02d}_{name}.{'png' if img.ndim == 2 else 'jpg'}"
            cv2.imwrite(str(f), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            files.append(f)
        return files


def draw_candidates(img: np.ndarray, contours, chosen=None, labels=None) -> np.ndarray:
    """Colour copy of `img` with all candidate contours (grey) and the chosen one (red)."""
    out = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    lw = max(1, out.shape[1] // 500)
    cv2.drawContours(out, list(contours), -1, (180, 180, 180), lw)
    placed: list[tuple[int, int]] = []
    for c, text in zip(contours, labels or []):
        x, y, _, _ = cv2.boundingRect(c)
        y = max(12 * lw, y - 4)
        while any(abs(x - px) < 30 * lw and abs(y - py) < 12 * lw for px, py in placed):
            y += 12 * lw                 # stack labels of (nearly) coincident candidates
        placed.append((x, y))
        cv2.putText(out, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4 * lw, (255, 255, 0), lw)
    if chosen is not None:
        cv2.drawContours(out, [chosen], -1, (0, 0, 255), 2 * lw)
    return out
