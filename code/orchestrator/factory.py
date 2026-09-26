"""Build detector / robot / inspector from a kind name. Shared by CLI and GUI.

Kinds
    detector : mock | replay | camera | ai
    robot    : mock | sim | real
    inspector: mock | replay | camera

replay = real image processing on the stored test photos, sim = NeuraRobot code
against the built-in fake controller. "real" is accepted as alias for "camera".
"""
from __future__ import annotations

import logging
from typing import Any

from common.camera import FileCamera, OpenCVCamera, open_camera
from common.interfaces import Inspector, ObjectDetector, RobotController

log = logging.getLogger(__name__)

DETECTOR_KINDS = ("mock", "replay", "camera", "ai")
ROBOT_KINDS = ("mock", "sim", "real")
INSPECTOR_KINDS = ("mock", "replay", "camera")

REPLAY_SOURCES = {
    "topdown_camera": "m1_vision_topdown/tests/data/*.jpg",
    "inspection_camera": "m3_inspection/tests/data/*.jpg",
}


def _norm(kind: str) -> str:
    return "camera" if kind == "real" else kind


def open_source(cfg: dict[str, Any], section: str, kind: str) -> OpenCVCamera | FileCamera:
    """Camera for `section` (topdown_camera / inspection_camera): live or replayed test photos."""
    if _norm(kind) == "replay":
        if section not in REPLAY_SOURCES:
            raise ValueError(f"No test images for {section}")
        return FileCamera(REPLAY_SOURCES[section])
    return open_camera(cfg[section])


def build_detector(cfg: dict[str, Any], kind: str, camera=None) -> ObjectDetector:
    kind = _norm(kind)
    if kind == "mock":
        from m1_vision_topdown import MockDetector
        return MockDetector(cfg)
    if kind in ("replay", "camera"):
        from m1_vision_topdown import TopDownDetector
        return TopDownDetector(cfg, camera or open_source(cfg, "topdown_camera", kind))
    if kind == "ai":
        from m4_ai_grasping import AiGraspDetector
        return AiGraspDetector(cfg, camera=camera)
    raise ValueError(f"Unknown detector kind: {kind}")


def build_robot(cfg: dict[str, Any], kind: str) -> RobotController:
    from m2_robot_control import MockRobot, NeuraRobot
    if kind == "mock":
        return MockRobot(cfg)
    if kind == "real":
        return NeuraRobot(cfg)
    if kind == "sim":
        from m2_robot_control.fake_neura_server import shared_server
        from m2_robot_control.robot import load_neurapy_client
        server = shared_server()
        robot = NeuraRobot(cfg, client_factory=lambda host: load_neurapy_client("127.0.0.1", server.port))
        robot.sim_state = server.fake   # for visualisation / tests
        log.info("Fake Neura controller on port %d", server.port)
        return robot
    raise ValueError(f"Unknown robot kind: {kind}")


def build_inspector(cfg: dict[str, Any], kind: str, camera=None, pipeline=None) -> Inspector:
    kind = _norm(kind)
    if kind == "mock":
        from m3_inspection import MockInspector
        return MockInspector(cfg)
    if kind in ("replay", "camera"):
        from m3_inspection import CameraInspector
        return CameraInspector(cfg, camera or open_source(cfg, "inspection_camera", kind), pipeline)
    raise ValueError(f"Unknown inspector kind: {kind}")
