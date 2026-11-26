"""M1 - top-down camera: find workspace and locate the part.

Processing chain: see plan/02_modul1_objekterkennung.md
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from common.camera import open_camera
from common.interfaces import ObjectDetector, ObjectPose, VisionError
from common.trace import Trace
from common.transforms import workspace_to_robot
from m1_vision_topdown.part import PartPose, draw_part_pose, part_pose, segment_part
from m1_vision_topdown.workspace import Workspace, find_workspace

log = logging.getLogger(__name__)


@dataclass
class TopDownResult:
    workspace: Workspace
    part: PartPose
    x_ws_mm: float
    y_ws_mm: float
    theta_ws_deg: float
    pose: ObjectPose            # in robot frame

    def debug_image(self, img: np.ndarray) -> np.ndarray:
        """Rectified workspace with part contour, axis and pose text."""
        rect = self.workspace.rectify(img)
        p = self.part
        cv2.drawContours(rect, [p.contour], -1, (0, 0, 255), 2)
        cv2.drawContours(rect, [p.box.astype(np.int32)], -1, (0, 255, 0), 1)
        tip = (int(p.u + 0.6 * p.length_px * np.cos(np.radians(p.theta_img_deg))),
               int(p.v + 0.6 * p.length_px * np.sin(np.radians(p.theta_img_deg))))
        cv2.arrowedLine(rect, (int(p.u), int(p.v)), tip, (255, 255, 0), 2, tipLength=0.3)
        text = (f"ws x={self.x_ws_mm:.1f} y={self.y_ws_mm:.1f} mm  th={self.theta_ws_deg:.1f} deg"
                f"  [{self.workspace.method}{'' if p.chamfer_found else ', no chamfer'}]")
        cv2.putText(rect, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return rect

    def overlay_image(self, img: np.ndarray) -> np.ndarray:
        """Original camera image with workspace reference points and part contour."""
        out = img.copy()
        lw = max(2, img.shape[1] // 400)
        H_inv = np.linalg.inv(self.workspace.H_img2rect)
        w, h = self.workspace.rect_size_px
        frame = cv2.perspectiveTransform(np.float32([[[0, 0], [w, 0], [w, h], [0, h]]]), H_inv)
        cv2.polylines(out, [frame.astype(np.int32)], True, (0, 255, 0), lw)
        for p in self.workspace.corners_img:
            cv2.circle(out, (int(p[0]), int(p[1])), 4 * lw, (0, 255, 255), -1)
        part = cv2.perspectiveTransform(self.part.contour.astype(np.float32).reshape(1, -1, 2), H_inv)
        cv2.polylines(out, [part.astype(np.int32)], True, (0, 0, 255), lw)
        c = cv2.perspectiveTransform(np.float32([[[self.part.u, self.part.v]]]), H_inv)[0, 0]
        cv2.drawMarker(out, (int(c[0]), int(c[1])), (255, 255, 0), cv2.MARKER_CROSS, 12 * lw, lw)
        return out


def correct_position(x_ws: float, y_ws: float, pc: dict[str, Any]) -> tuple[float, float]:
    """Pull the detected centre towards `center_mm` by `scale` per axis (part_topdown.position_correction).
    The part top lies above the table plane the image is rectified to (parallax) and the lens is not
    calibrated, so the detected centre drifts outward from the image centre - linear in the distance."""
    corr = pc.get("position_correction")
    if not corr:
        return x_ws, y_ws
    (cx, cy), (kx, ky) = corr["center_mm"], corr["scale"]
    return x_ws - kx * (x_ws - cx), y_ws - ky * (y_ws - cy)


class TopDownPipeline:
    """Image in, part pose out. No camera access -> directly testable with image files."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def process(self, img: np.ndarray, trace: Trace | None = None) -> TopDownResult:
        """`trace` (optional) collects the intermediate images for documentation."""
        if trace is not None:
            trace.add("original", img)
        ws = find_workspace(img, self.cfg, trace)
        rect = ws.rectify(img)
        if trace is not None:
            trace.add("rectified", rect)
        border_px = int(self.cfg["workspace"]["border_mm"] * ws.px_per_mm)
        contour = segment_part(rect, self.cfg, ws.px_per_mm, border_px, trace)
        part = part_pose(contour, self.cfg["part_topdown"]["chamfer_min_frac"])
        if trace is not None:
            trace.add("part_pose", draw_part_pose(rect, part))
        expected = self.cfg["part_topdown"].get("chamfer_side")
        if expected and part.chamfer_side and part.chamfer_side != expected:
            raise VisionError("Part is upside down (chamfer mirrored) - turn it over")

        x_ws, y_ws = correct_position(*ws.rect_to_mm(part.u, part.v), self.cfg["part_topdown"])
        period = 360.0 if part.chamfer_found else 180.0
        theta_ws = (-part.theta_img_deg) % period          # image y down -> workspace y up

        w2r = self.cfg["workspace_to_robot"]
        x, y, theta = workspace_to_robot(x_ws, y_ws, theta_ws, w2r["rotation_deg"],
                                         np.array(w2r["translation_mm"]))
        pose = ObjectPose(x, y, w2r["table_z_mm"], theta % period,
                          confidence=1.0 if part.chamfer_found else 0.5)
        result = TopDownResult(ws, part, x_ws, y_ws, theta_ws, pose)
        if trace is not None:
            trace.add("result", result.debug_image(img))
        return result


def _unstable(a: TopDownResult, img_a: np.ndarray, b: TopDownResult, img_b: np.ndarray,
              sc: dict[str, Any]) -> str | None:
    """Why two consecutive detections do not show a still scene, None if they do."""
    d_mm = float(np.hypot(a.x_ws_mm - b.x_ws_mm, a.y_ws_mm - b.y_ws_mm))
    period = 360.0 if a.part.chamfer_found and b.part.chamfer_found else 180.0
    d_deg = abs((a.theta_ws_deg - b.theta_ws_deg + period / 2) % period - period / 2)
    if d_mm > sc["pose_tol_mm"] or d_deg > sc["pose_tol_deg"]:
        return f"part moved {d_mm:.1f} mm / {d_deg:.1f} deg"
    # whole workspace, both images rectified with the same (first) homography
    ga, gb = (cv2.GaussianBlur(cv2.cvtColor(a.workspace.rectify(i), cv2.COLOR_BGR2GRAY), (5, 5), 0)
              for i in (img_a, img_b))
    changed = (cv2.absdiff(ga, gb) > sc["pixel_delta"]).astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    frac = float(changed.mean())
    if frac > sc["max_changed_frac"]:
        return f"{100 * frac:.1f} % of the workspace changed"
    return None


class TopDownDetector(ObjectDetector):
    """Real M1 detector: camera + TopDownPipeline."""

    def __init__(self, cfg: dict[str, Any], camera=None):
        self._cfg = cfg
        self._pipeline = TopDownPipeline(cfg)
        self._owns_camera = camera is None
        self._camera = camera or open_camera(cfg["topdown_camera"])
        self.last_result: TopDownResult | None = None
        self.last_image: np.ndarray | None = None
        self.last_reject: str | None = None        # why the last detect() returned None (GUI text)
        self.trace_steps = False                   # collect intermediate images (documentation)
        self.last_trace: Trace | None = None

    def _detect_once(self) -> TopDownResult | None:
        img = self._camera.read()
        self.last_image = img
        self.last_result = None
        self.last_trace = Trace() if self.trace_steps else None
        try:
            self.last_result = self._pipeline.process(img, self.last_trace)
        except VisionError as e:
            if "No part" in str(e):
                self.last_reject = str(e)
                return None
            raise
        return self.last_result

    def detect(self) -> ObjectPose | None:
        """Part pose, or None if there is no part or the scene is not still yet (see `stability`)."""
        self.last_reject = None
        sc = self._cfg["part_topdown"].get("stability") or {}
        frames = sc.get("frames", 1) if getattr(self._camera, "is_live", True) else 1
        prev = self._detect_once()
        for _ in range(frames - 1):
            if prev is None:
                break
            prev_img = self.last_image
            time.sleep(sc["interval_s"])
            cur = self._detect_once()
            why = None if cur is None else _unstable(prev, prev_img, cur, self.last_image, sc)
            if why:
                self.last_reject = f"scene not still: {why}"
                self.last_result = None
                cur = None
            prev = cur
        if prev is None:
            log.info("No part detected: %s", self.last_reject)
            return None
        log.info("Part detected: %s", prev.pose)
        return prev.pose

    def close(self) -> None:
        if self._owns_camera:
            self._camera.close()


class MockDetector(ObjectDetector):
    """Returns a random part pose inside the workspace. For development without camera."""

    def __init__(self, cfg: dict[str, Any], seed: int | None = None):
        self._cfg = cfg
        self._rng = random.Random(seed)

    def detect(self) -> ObjectPose | None:
        w, h = self._cfg["workspace"]["size_mm"]
        x_ws = self._rng.uniform(50, w - 50)
        y_ws = self._rng.uniform(50, h - 50)
        theta_ws = self._rng.uniform(0, 360)

        w2r = self._cfg["workspace_to_robot"]
        x, y, theta = workspace_to_robot(x_ws, y_ws, theta_ws, w2r["rotation_deg"],
                                         np.array(w2r["translation_mm"]))
        pose = ObjectPose(x, y, w2r["table_z_mm"], theta % 360, confidence=1.0)
        log.info("Mock detection: %s", pose)
        return pose
