"""Run the M3 inspection on image files and save debug images.

    python -m m3_inspection.run "m3_inspection/tests/data/*.jpg" --out logs/m3
    python -m m3_inspection.run --camera
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import cv2

from common.camera import open_camera
from common.config import load_config
from common.interfaces import InspectionError
from m3_inspection.inspector import InspectionPipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--camera", action="store_true")
    ap.add_argument("--out", default="logs/m3")
    args = ap.parse_args()

    cfg = load_config()
    pipeline = InspectionPipeline(cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    inputs = []
    if args.camera:
        cam = open_camera(cfg["inspection_camera"])
        inputs.append(("camera", cam.read()))
        cam.close()
    for pattern in args.images:
        inputs += [(f, cv2.imread(f)) for f in sorted(glob.glob(pattern))]

    for name, img in inputs:
        try:
            d = pipeline.process(img)
        except InspectionError as e:
            print(f"{name}: ERROR {e}")
            continue
        r = d.result
        ratio = d.hole_diameter_px / d.part_box[3] if d.hole_diameter_px else None
        print(f"{name}: {'GOOD' if r.is_good else 'BAD'} serial={r.serial_number} "
              f"(conf {d.ocr_confidence:.2f}) hole={r.hole_diameter_mm and round(r.hole_diameter_mm, 3)} mm "
              f"(D/H={ratio and round(ratio, 3)}) notch={r.notch_present} {r.reasons}")
        cv2.imwrite(str(out / (Path(name).stem + "_m3.jpg")), d.debug_image(img, cfg["inspection"]))
    print(f"debug images in {out.resolve()}")


if __name__ == "__main__":
    main()
