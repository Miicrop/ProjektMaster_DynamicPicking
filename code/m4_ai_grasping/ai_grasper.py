"""M4 - learning-based grasping with the wrist camera. Implemented by person 4.

Role (team decision 2026-10-21): M4 takes over PICK and PLACE_INSPECT from M2.
M1 still detects the part; M4 gets that pose as a starting point, grasps the part
using the wrist camera and puts it down at the inspection fixture. After M3 has
classified it, M2 picks it up again and sorts it.

Only requirement: implement Grasper (common/interfaces.py). Poses in and out are in
the robot base frame, like everywhere else. Switch it on with GUI tab "Ablauf" ->
Greifen "KI (M4)", `python -m orchestrator --grasper ai` or
`implementations.grasper: ai` in config/system.yaml.

Cameras (config/system.yaml):
- wrist_camera: camera on the robot wrist (planned) - open it with wrist_camera()
"""
from __future__ import annotations

from typing import Any

from common.camera import open_camera
from common.interfaces import Grasper, ObjectPose, RobotController, RobotTarget


class AiGrasper(Grasper):
    def __init__(self, cfg: dict[str, Any], robot: RobotController):
        self._cfg = cfg
        self.robot = robot               # M2 controller - for motions and the gripper
        self._wrist = None               # opened lazily

    def wrist_camera(self):
        if self._wrist is None:
            self._wrist = open_camera(self._cfg["wrist_camera"])
        return self._wrist

    def pick(self, pose: ObjectPose) -> None:
        raise NotImplementedError("AiGrasper is not implemented yet")

    def place(self, target: RobotTarget) -> None:
        raise NotImplementedError("AiGrasper is not implemented yet")

    def close(self) -> None:
        if self._wrist is not None:
            self._wrist.close()
