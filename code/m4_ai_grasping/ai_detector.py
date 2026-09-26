"""M4 - learning-based grasp pose estimation. Implemented by person 4.

Only requirement: implement ObjectDetector and return an ObjectPose in the robot
frame, so the orchestrator can switch between M1 and M4 (GUI "KI (M4)",
`python -m orchestrator --detector ai`).

Cameras (config/system.yaml):
- topdown_camera: passed in as `camera` when started from GUI/orchestrator (shared with M1)
- wrist_camera  : camera on the robot wrist (planned) - open it with open_camera() when needed
"""
from __future__ import annotations

from typing import Any

from common.camera import open_camera
from common.interfaces import ObjectDetector, ObjectPose


class AiGraspDetector(ObjectDetector):
    def __init__(self, cfg: dict[str, Any], camera=None):
        self._cfg = cfg
        self._camera = camera            # top-down camera (may be None)
        self._wrist = None               # opened lazily

    def wrist_camera(self):
        if self._wrist is None:
            self._wrist = open_camera(self._cfg["wrist_camera"])
        return self._wrist

    def detect(self) -> ObjectPose | None:
        raise NotImplementedError("AiGraspDetector is not implemented yet")

    def close(self) -> None:
        if self._wrist is not None:
            self._wrist.close()
