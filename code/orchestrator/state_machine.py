"""Cycle state machine: DETECT -> PICK -> PLACE_INSPECT -> INSPECT -> PICK_INSPECT -> SORT.

See plan/01_architektur.md, section "Zustandsautomat".
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from common.config import robot_target
from common.interfaces import (InspectionResult, Inspector, ObjectDetector, ObjectPose,
                               RobotController)

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    DETECT = auto()
    PICK = auto()
    PLACE_INSPECT = auto()
    INSPECT = auto()
    PICK_INSPECT = auto()
    SORT = auto()
    ERROR = auto()


@dataclass
class CycleResult:
    cycle_id: int
    pose: ObjectPose | None = None
    inspection: InspectionResult | None = None
    states: list[State] = field(default_factory=list)
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    duration_s: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


StateListener = Callable[[State, CycleResult], None]


class Orchestrator:
    def __init__(self, cfg: dict[str, Any], detector: ObjectDetector,
                 robot: RobotController, inspector: Inspector):
        self.cfg = cfg
        self.detector = detector
        self.robot = robot
        self.inspector = inspector
        self.state = State.IDLE
        self._cycle_id = 0
        self.listeners: list[StateListener] = []   # e.g. GUI updates, called on every transition

    def _enter(self, state: State, result: CycleResult) -> None:
        log.info("[cycle %d] %s -> %s", result.cycle_id, self.state.name, state.name)
        self.state = state
        result.states.append(state)
        if state in (State.IDLE, State.ERROR):
            result.duration_s = time.time() - result.started_at
        for listener in self.listeners:
            try:
                listener(state, result)
            except Exception:
                log.exception("State listener failed")

    def run_cycle(self) -> CycleResult:
        """Run one full cycle. Returns to IDLE on success or if no part is found."""
        self._cycle_id += 1
        result = CycleResult(self._cycle_id)
        try:
            self._enter(State.DETECT, result)
            result.pose = self.detector.detect()
            if result.pose is None:
                log.info("No part in workspace")
                self._enter(State.IDLE, result)
                return result

            self._enter(State.PICK, result)
            self.robot.pick(result.pose)

            self._enter(State.PLACE_INSPECT, result)
            inspection_pose = robot_target(self.cfg, "inspection")
            self.robot.place(inspection_pose)
            self.robot.home()  # clear the inspection camera's view

            self._enter(State.INSPECT, result)
            result.inspection = self.inspector.inspect()

            self._enter(State.PICK_INSPECT, result)
            self.robot.pick(inspection_pose)

            self._enter(State.SORT, result)
            bin_name = "bin_good" if result.inspection.is_good else "bin_bad"
            self.robot.place(robot_target(self.cfg, bin_name))
            self.robot.home()

            self._enter(State.IDLE, result)
        except Exception as e:  # any module failure stops the robot
            log.exception("Cycle %d failed in state %s", result.cycle_id, self.state.name)
            result.error = f"{self.state.name}: {e}"
            self._enter(State.ERROR, result)
            try:
                self.robot.stop()
            except Exception:
                log.exception("robot.stop() failed")
        return result

    def reset(self) -> None:
        """Acknowledge an error or STOP: re-enable the robot, drive home, return to IDLE."""
        self.robot.reset()
        self.robot.home()
        self.state = State.IDLE
