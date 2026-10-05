"""Generate printable ArUco markers WITH a white quiet zone.

The current 3D-printed markers (black block, white bits) have no light border around
them, so the black marker border merges with the dark board and OpenCV cannot find
them reliably. Printing these (or adding a white rim of >= 1 bit width) fixes that.

    python -m m1_vision_topdown.make_markers --size-mm 50 --out logs/markers

Besides one PNG per marker, all markers are packed onto A4 pages in markers_A4.pdf.
Print the PDF at 100 % / "actual size" (not "fit to page") and check the edge length
with a ruler.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

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


def layout_a4(tiles: list[np.ndarray], dpi: int, margin_mm: float = 10.0,
              gap_mm: float = 5.0) -> list[np.ndarray]:
    """Pack equally sized marker tiles row by row onto as many A4 pages as needed.

    A thin grey cut line is drawn around every tile (outside its white quiet zone)."""
    mm = dpi / 25.4
    page_w, page_h = int(round(210 * mm)), int(round(297 * mm))
    margin, gap = int(round(margin_mm * mm)), int(round(gap_mm * mm))
    th, tw = tiles[0].shape[:2]
    cols = (page_w - 2 * margin + gap) // (tw + gap)
    rows = (page_h - 2 * margin + gap) // (th + gap)
    if cols < 1 or rows < 1:
        raise ValueError(f"marker tile ({tw / mm:.0f} mm) does not fit on A4 with {margin_mm:g} mm margin")
    per_page = cols * rows
    pages = []
    for start in range(0, len(tiles), per_page):
        page = np.full((page_h, page_w), 255, np.uint8)
        for i, tile in enumerate(tiles[start:start + per_page]):
            r, c = divmod(i, cols)
            x, y = margin + c * (tw + gap), margin + r * (th + gap)
            page[y:y + th, x:x + tw] = tile
            cv2.rectangle(page, (x - 1, y - 1), (x + tw, y + th), 180, 1)
        pages.append(page)
    return pages


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
    tiles = []
    for mid in cfg["workspace"]["markers_mm"]:
        img = marker_with_border(dict_name, int(mid), args.size_mm, args.dpi)
        tiles.append(img)
        f = out / f"aruco_{dict_name}_id{mid}.png"
        cv2.imwrite(str(f), img)
        print(f"wrote {f} (print at {args.dpi} dpi, 100 % scale)")

    pages = [Image.fromarray(p) for p in layout_a4(tiles, args.dpi)]
    f = out / "markers_A4.pdf"
    pages[0].save(f, save_all=True, append_images=pages[1:], resolution=args.dpi)
    print(f"wrote {f} ({len(pages)} A4 page(s), print at 100 % / actual size)")


if __name__ == "__main__":
    main()
