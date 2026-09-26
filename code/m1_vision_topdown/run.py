"""Run the M1 pipeline on image files and save debug images.

    python -m m1_vision_topdown.run m1_vision_topdown/tests/data/*.jpg --out logs/m1
    python -m m1_vision_topdown.run --camera            # one live frame from the configured camera
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import cv2

from common.camera import open_camera
from common.config import load_config
from common.interfaces import VisionError
from m1_vision_topdown.detector import TopDownPipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*", help="image files or glob patterns")
    ap.add_argument("--camera", action="store_true", help="grab one frame from the camera")
    ap.add_argument("--method", choices=["auto", "aruco", "white_frame"])
    ap.add_argument("--out", default="logs/m1", help="folder for debug images")
    args = ap.parse_args()

    cfg = load_config()
    if args.method:
        cfg["workspace"]["method"] = args.method
    pipeline = TopDownPipeline(cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    inputs: list[tuple[str, object]] = []
    if args.camera:
        cam = open_camera(cfg["topdown_camera"])
        inputs.append(("camera", cam.read()))
        cam.close()
    for pattern in args.images:
        for f in sorted(glob.glob(pattern)):
            inputs.append((f, cv2.imread(f)))

    for name, img in inputs:
        try:
            r = pipeline.process(img)
        except VisionError as e:
            print(f"{name}: ERROR {e}")
            continue
        print(f"{name}: [{r.workspace.method}] ws=({r.x_ws_mm:.1f}, {r.y_ws_mm:.1f}) mm "
              f"theta={r.theta_ws_deg:.1f} deg chamfer={r.part.chamfer_found} "
              f"size={r.part.length_px / r.workspace.px_per_mm:.1f}x"
              f"{r.part.width_px / r.workspace.px_per_mm:.1f} mm | robot=({r.pose.x_mm:.1f}, "
              f"{r.pose.y_mm:.1f}) mm theta={r.pose.theta_deg:.1f}")
        cv2.imwrite(str(out / (Path(name).stem + "_m1.jpg")), r.debug_image(img))
        cv2.imwrite(str(out / (Path(name).stem + "_m1_overlay.jpg")), r.overlay_image(img))
    print(f"debug images in {out.resolve()}")


if __name__ == "__main__":
    main()
