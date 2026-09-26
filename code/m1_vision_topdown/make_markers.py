"""Generate printable ArUco markers WITH a white quiet zone.

The current 3D-printed markers (black block, white bits) have no light border around
them, so the black marker border merges with the dark board and OpenCV cannot find
them reliably. Printing these (or adding a white rim of >= 1 bit width) fixes that.

    python -m m1_vision_topdown.make_markers --size-mm 50 --out logs/markers
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from common.config import load_config


def marker_with_border(dict_name: str, marker_id: int, size_mm: float, dpi: int = 300,
                       border_bits: float = 1.0) -> np.ndarray:
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    px = int(round(size_mm / 25.4 * dpi))
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, px)
    bits = dictionary.markerSize + 2
    pad = int(round(border_bits * px / bits))
    img = cv2.copyMakeBorder(marker, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    cv2.putText(img, f"ID {marker_id} / {dict_name} / {size_mm:g} mm", (5, img.shape[0] - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4 * dpi / 100, 128, 1)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-mm", type=float, default=50.0, help="black marker edge length")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="logs/markers")
    args = ap.parse_args()

    cfg = load_config()
    dict_name = cfg["workspace"]["aruco_dictionary"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for mid in cfg["workspace"]["markers_mm"]:
        f = out / f"aruco_{dict_name}_id{mid}.png"
        cv2.imwrite(str(f), marker_with_border(dict_name, int(mid), args.size_mm, args.dpi))
        print(f"wrote {f} (print at {args.dpi} dpi, 100 % scale)")


if __name__ == "__main__":
    main()
