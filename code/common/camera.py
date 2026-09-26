"""Camera access for all modules.

Config sections: topdown_camera (M1), inspection_camera (M3), wrist_camera (M4, planned).
`source` decides the backend:
- int      -> live OpenCV camera (device index)
- str      -> image file or glob pattern, replayed in a loop (testing without hardware)

Which index is which camera? Windows numbers USB cameras in plug-in order, so with several
cameras run `python -m common.camera` - it opens every index, prints the resolution and saves
a snapshot per index to logs/cameras/.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from common.config import CODE_ROOT


class OpenCVCamera:
    def __init__(self, device: int, width: int | None = None, height: int | None = None,
                 flush_frames: int = 3):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(device, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera {device}")
        if width and height:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._flush = flush_frames

    def read(self) -> np.ndarray:
        for _ in range(self._flush):  # drop buffered (old) frames
            self._cap.grab()
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("Camera read failed")
        return frame

    def close(self) -> None:
        self._cap.release()


class FileCamera:
    """Replays image files in a loop."""

    def __init__(self, pattern: str):
        path = Path(pattern)
        if not path.is_absolute():
            path = CODE_ROOT / path
        self.files = sorted(glob.glob(str(path)))
        if not self.files:
            raise FileNotFoundError(f"No images match {path}")
        self._i = 0

    def read(self) -> np.ndarray:
        f = self.files[self._i % len(self.files)]
        self._i += 1
        img = cv2.imread(f)
        if img is None:
            raise RuntimeError(f"Cannot read image {f}")
        return img

    def close(self) -> None:
        pass


CAMERA_SECTIONS = ("topdown_camera", "inspection_camera", "wrist_camera")


def open_camera(section: dict[str, Any]) -> OpenCVCamera | FileCamera:
    src = section["source"]
    if isinstance(src, int):
        return OpenCVCamera(src, section.get("width"), section.get("height"))
    return FileCamera(str(src))


def probe(max_index: int = 6) -> list[tuple[int, int, int]]:
    """Try device indices 0..max_index-1; returns (index, width, height) of working cameras."""
    import logging
    from common.config import load_config
    out_dir = CODE_ROOT / load_config()["logging"]["cycle_dir"] / "cameras"
    out_dir.mkdir(parents=True, exist_ok=True)
    found = []
    logging.getLogger().setLevel(logging.ERROR)
    for i in range(max_index):
        try:
            cam = OpenCVCamera(i, 3840, 2160)   # request max, the driver picks the nearest mode
            frame = cam.read()
            cam.close()
        except RuntimeError:
            continue
        h, w = frame.shape[:2]
        cv2.imwrite(str(out_dir / f"camera_{i}.jpg"), frame)
        found.append((i, w, h))
    return found


def main() -> None:
    from common.config import load_config
    cfg = load_config()
    print("Searching cameras (this takes a few seconds) ...")
    found = probe()
    for i, w, h in found:
        users = [s for s in CAMERA_SECTIONS if cfg.get(s, {}).get("source") == i]
        print(f"  index {i}: {w}x{h}   used by: {', '.join(users) or '-'}")
    if not found:
        print("  no camera found")
    print(f"Snapshots: {CODE_ROOT / cfg['logging']['cycle_dir'] / 'cameras'}  ->  set 'source' in config/system.yaml")


if __name__ == "__main__":
    main()
