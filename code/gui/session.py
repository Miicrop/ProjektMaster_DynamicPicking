"""State shared by all GUI tabs: config, cameras, robot connection, pipelines.

Qt-free, so it can be tested without a display. Cameras and the robot are opened
once and shared between the module tabs and the automatic cycle.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from gui.config_store import ConfigStore
from m1_vision_topdown import TopDownPipeline
from m1_vision_topdown.detector import TopDownResult
from m3_inspection import InspectionPipeline
from m3_inspection.inspector import InspectionDetails
from orchestrator.factory import build_detector, build_inspector, build_robot, open_source
from orchestrator.state_machine import Orchestrator

log = logging.getLogger(__name__)

SECTIONS = {"m1": "topdown_camera", "m3": "inspection_camera", "wrist": "wrist_camera"}


class Session:
    def __init__(self, store: ConfigStore | None = None):
        self.store = store or ConfigStore()
        self.cfg: dict[str, Any] = self.store.data
        self.m1 = TopDownPipeline(self.cfg)
        self.m3 = InspectionPipeline(self.cfg)       # keeps the OCR model loaded
        self._cameras: dict[tuple, Any] = {}
        self._cam_lock = threading.Lock()
        self.robot = None
        self.robot_kind: str | None = None
        self.robot_connected = False

    # -- cameras -----------------------------------------------------------------
    def camera(self, module: str, kind: str):
        """Shared camera for module 'm1'/'m3'; kind 'replay' (test photos) or 'camera'."""
        section = SECTIONS[module]
        source = self.cfg[section]["source"]
        key = (section, kind, str(source) if kind == "camera" else "")
        with self._cam_lock:
            if key not in self._cameras and kind == "camera" and isinstance(source, int):
                other = [k[0] for k in self._cameras if k[1] == "camera" and k[0] != section
                         and k[2] == str(source)]
                if other:
                    raise RuntimeError(f"Kamera {source} ist schon für '{other[0]}' geöffnet - "
                                       f"in den Einstellungen '{section}.source' prüfen "
                                       f"(Kameras suchen: python -m common.camera)")
            if key not in self._cameras:
                # a live camera can only be opened once -> drop other entries of this section
                for k in [k for k in self._cameras if k[0] == section and k[1] == "camera"]:
                    self._cameras.pop(k).close()
                self._cameras[key] = open_source(self.cfg, section, kind)
            return self._cameras[key]

    def grab(self, module: str, kind: str) -> np.ndarray:
        return self.camera(module, kind).read()

    def release_cameras(self) -> None:
        with self._cam_lock:
            for cam in self._cameras.values():
                cam.close()
            self._cameras.clear()

    # -- single-module analysis --------------------------------------------------
    def analyze_m1(self, img: np.ndarray) -> TopDownResult:
        return self.m1.process(img)

    def analyze_m3(self, img: np.ndarray) -> InspectionDetails:
        return self.m3.process(img)

    # -- robot -------------------------------------------------------------------
    def connect_robot(self, kind: str):
        """Connect (and prepare) the robot; reuses an existing connection of the same kind."""
        if self.robot is not None and self.robot_kind == kind and self.robot_connected:
            return self.robot
        self.disconnect_robot()
        robot = build_robot(self.cfg, kind)
        robot.connect()
        self.robot, self.robot_kind, self.robot_connected = robot, kind, True
        log.info("Robot connected (%s)", kind)
        return robot

    def disconnect_robot(self) -> None:
        if self.robot is not None:
            try:
                self.robot.disconnect()
            except Exception:
                log.exception("disconnect failed")
        self.robot, self.robot_kind, self.robot_connected = None, None, False

    def acknowledge(self) -> None:
        """After STOP/error: re-enable the robot (init_program) and drive home."""
        if self.robot is not None:
            self.robot.reset()
            self.robot.home()
            log.info("Robot acknowledged and at home")

    def emergency_stop(self) -> None:
        """Software stop - independent of any running task."""
        if self.robot is not None:
            self.robot.stop()
            log.warning("STOP sent to robot")

    # -- automatic cycle -----------------------------------------------------------
    def build_orchestrator(self, detector_kind: str, robot_kind: str, inspector_kind: str) -> Orchestrator:
        cam1 = self.camera("m1", detector_kind) if detector_kind in ("replay", "camera") else None
        cam3 = self.camera("m3", inspector_kind) if inspector_kind in ("replay", "camera") else None
        detector = build_detector(self.cfg, detector_kind, camera=cam1)
        inspector = build_inspector(self.cfg, inspector_kind, camera=cam3, pipeline=self.m3)
        robot = self.connect_robot(robot_kind)
        return Orchestrator(self.cfg, detector, robot, inspector)

    def close(self) -> None:
        self.disconnect_robot()
        self.release_cameras()
