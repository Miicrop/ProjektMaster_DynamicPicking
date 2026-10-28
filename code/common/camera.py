"""Camera access for all modules.

Config sections: topdown_camera (M1), inspection_camera (M3). M4 (m4_behavior_cloning) opens its
cameras itself; its scene camera is the M1 top-down camera.
`source` decides the backend:
- int              -> live OpenCV camera (device index), e.g. the M3 USB camera
- "daheng:<serial>" -> Daheng USB3-Vision camera via the Galaxy SDK (M1 top-down, VEN-161);
                      "daheng" alone = the only connected one
- other str        -> image file or glob pattern, replayed in a loop (testing without hardware)

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


class DahengCamera:
    """Daheng USB3-Vision camera via the Galaxy SDK (gxipy) - OpenCV cannot open it.

    Uses the camera code of M4 (bc/adapters/cam_daheng.py, in use at the plant): it finds gxipy
    in the SDK install and sets trigger, exposure and white balance. Full sensor (1440x1080).
    Opened on the first read; release() closes it so M4 can use the same camera in its own
    process (scene camera) - the next read() opens it again.
    """

    def __init__(self, serial: str | None = None, exposure_us: float | None = None,
                 gain_db: float | None = None):
        self.serial = serial or None
        self.exposure_us, self.gain_db = exposure_us, gain_db
        self._cam = None

    def _open(self):
        from common import m4
        m4.prepare()
        from bc.adapters.cam_daheng import DahengCamera as BcDahengCamera
        from bc.config import CameraConfig
        cfg = CameraConfig(name="topdown", backend="daheng", device=self.serial, width=None, height=None,
                           exposure_us=self.exposure_us, gain_db=self.gain_db, fps=None)
        try:
            return BcDahengCamera(cfg).open()
        except Exception as e:
            raise RuntimeError(f"Daheng camera {self.serial or ''}: {e}") from e

    def read(self) -> np.ndarray:
        if self._cam is None:
            self._cam = self._open()
        try:
            rgb = self._cam.read().image
        except Exception as e:
            raise RuntimeError(f"Camera read failed (Daheng {self.serial or ''}): {e}") from e
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def release(self) -> None:
        if self._cam is not None:
            self._cam.close()
            self._cam = None

    close = release


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


CAMERA_SECTIONS = ("topdown_camera", "inspection_camera")


def daheng_serial(source: Any) -> str | None:
    """Serial of a "daheng:<serial>" source ("" for plain "daheng"), None if it is no Daheng source."""
    if isinstance(source, str) and source.split(":", 1)[0].strip().lower() == "daheng":
        return source.partition(":")[2].strip()
    return None


def open_camera(section: dict[str, Any]) -> OpenCVCamera | DahengCamera | FileCamera:
    src = section["source"]
    if isinstance(src, int):
        return OpenCVCamera(src, section.get("width"), section.get("height"))
    serial = daheng_serial(src)
    if serial is not None:
        return DahengCamera(serial, section.get("exposure_us"), section.get("gain_db"))
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
    try:
        from common import m4
        m4.prepare()
        from bc.adapters import list_daheng_devices
        devices, note = list_daheng_devices()
    except Exception as e:      # M4 folder missing
        devices, note = [], str(e)
    for d in devices:
        src = f"daheng:{d.device}"
        users = [s for s in CAMERA_SECTIONS if cfg.get(s, {}).get("source") == src]
        print(f"  {src}: {d.label}   used by: {', '.join(users) or '-'}")
    if note:
        print(f"  Daheng: {note}")
    print(f"Snapshots: {CODE_ROOT / cfg['logging']['cycle_dir'] / 'cameras'}  ->  set 'source' in config/system.yaml")


if __name__ == "__main__":
    main()
