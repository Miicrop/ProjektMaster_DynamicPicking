"""Check whether printed ArUco markers are detected by the top-down camera.

Holds the camera on the markers for a number of frames and reports per marker ID how
often it was found and how large it appears. Uses the same detector settings as the
workspace detection (workspace.py) and the IDs / dictionary from config/system.yaml.

    python -m m1_vision_topdown.check_markers                  # 30 frames from the configured camera
    python -m m1_vision_topdown.check_markers --frames 0       # run until Ctrl+C
    python -m m1_vision_topdown.check_markers photo.jpg        # image file(s) instead of the camera

The annotated last frame is written to <out>/markers_check.jpg (found = green with ID,
rejected square candidates = thin red). Red boxes inside markers are normal (white bits).
A red box around a whole marker means the square was seen but the code could not be read
(blur, glare, wrong dictionary); no box at all usually means the white quiet zone is missing.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from common.camera import FileCamera, open_camera
from common.config import CODE_ROOT, load_config
from m1_vision_topdown.workspace import _aruco_detector


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="?", help="image file or glob pattern (default: configured camera)")
    ap.add_argument("--frames", type=int, default=30, help="number of frames, 0 = until Ctrl+C")
    ap.add_argument("--out", default="logs/markers", help="folder for the annotated image")
    args = ap.parse_args()

    cfg = load_config()
    ws = cfg["workspace"]
    expected = sorted(int(k) for k in ws["markers_mm"])
    detector = _aruco_detector(ws["aruco_dictionary"])
    cam = FileCamera(args.images) if args.images else open_camera(cfg["topdown_camera"])
    out = Path(args.out)
    if not out.is_absolute():
        out = CODE_ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    print(f"Dictionary {ws['aruco_dictionary']}, expected IDs {expected}. Ctrl+C to stop.")
    hits: Counter[int] = Counter()
    side_px: dict[int, list[float]] = {}
    n = 0
    vis = None
    try:
        while args.frames == 0 or n < args.frames:
            img = cam.read()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
            corners, ids, rejected = detector.detectMarkers(gray)
            found = [] if ids is None else [int(i) for i in ids.ravel()]
            for i, c in zip(found, corners):
                hits[i] += 1
                pts = c.reshape(4, 2)
                side_px.setdefault(i, []).append(float(np.mean(np.linalg.norm(pts - np.roll(pts, 1, 0), axis=1))))
            n += 1
            missing = [i for i in expected if i not in found]
            unknown = sorted(set(found) - set(expected))
            print(f"frame {n:4d}: found {sorted(found)}  missing {missing}"
                  + (f"  unexpected {unknown}" if unknown else ""))

            vis = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if rejected:
                cv2.polylines(vis, [r.astype(np.int32) for r in rejected], True, (0, 0, 255), 1)
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(vis, corners, ids, (0, 255, 0))
            cv2.imwrite(str(out / "markers_check.jpg"), vis)
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()

    if n == 0:
        return
    print(f"\nSummary over {n} frame(s):")
    for i in sorted(set(expected) | set(hits)):
        tag = "" if i in expected else "  (not in config)"
        if hits[i]:
            print(f"  ID {i}: {100 * hits[i] / n:5.1f} %   edge ~{np.mean(side_px[i]):.0f} px{tag}")
        else:
            print(f"  ID {i}:   0.0 %   NOT FOUND{tag}")
    ok = all(hits[i] == n for i in expected)
    print("OK - all markers found in every frame." if ok else
          "Problem - see above. Check lighting, white quiet zone, marker size (>= ~30 px edge) "
          "and that the IDs match workspace.markers_mm.")
    print(f"Annotated image: {out / 'markers_check.jpg'}")


if __name__ == "__main__":
    main()
