"""Shared data types and module interfaces.

Every module only exchanges the types defined here. Changes to this file affect
all modules and must be agreed on beforehand (see plan/01_architektur.md).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# --- Data exchanged between modules -----------------------------------------

@dataclass
class ObjectPose:
    """Grasp pose of the part in the robot base frame (M1 -> M2)."""
    x_mm: float
    y_mm: float
    z_mm: float
    theta_deg: float
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    image_path: str | None = None


@dataclass
class RobotTarget:
    """Named Cartesian pose in the robot base frame, loaded from config."""
    name: str
    x_mm: float
    y_mm: float
    z_mm: float
    rx_deg: float
    ry_deg: float
    rz_deg: float


@dataclass
class InspectionResult:
    """Result of the side-camera inspection (M3 -> M2)."""
    serial_number: str | None
    hole_diameter_mm: float | None
    notch_present: bool | None
    is_good: bool
    reasons: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    image_path: str | None = None


# --- Errors ------------------------------------------------------------------

class VisionError(RuntimeError):
    pass


class RobotError(RuntimeError):
    pass


class InspectionError(RuntimeError):
    pass


# --- Module interfaces -------------------------------------------------------

class ObjectDetector(ABC):
    """M1 implements this."""

    @abstractmethod
    def detect(self) -> ObjectPose | None:
        """Return the part pose in the robot frame, or None if no part is present."""

    def close(self) -> None:
        pass


class RobotController(ABC):
    """M2 implements this."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def home(self) -> None: ...

    @abstractmethod
    def pick(self, pose: ObjectPose | RobotTarget) -> None:
        """Grasp the part at a detected pose or at a named pose (e.g. inspection)."""

    @abstractmethod
    def place(self, target: RobotTarget) -> None: ...

    @abstractmethod
    def stop(self) -> None:
        """Stop all motion immediately. Afterwards every motion is refused until reset()."""

    def reset(self) -> None:
        """Acknowledge a stop/error and make the robot ready for motions again."""


class Grasper(ABC):
    """Grasps the detected part and puts it down at the inspection fixture (PICK, PLACE_INSPECT).

    Default: RobotGrasper (M2 does it). Alternative: BcGrasper (orchestrator/m4_grasper.py) - the
    M4 Behavior Cloning policy grasps, M2 places. Picking up again at the fixture and sorting always
    stays with M2.
    """

    @abstractmethod
    def pick(self, pose: ObjectPose) -> None:
        """Grasp the part; `pose` from M1 is the starting point (robot base frame)."""

    @abstractmethod
    def place(self, target: RobotTarget) -> None:
        """Put the held part down at `target` (the inspection fixture)."""

    def stop(self) -> None:
        """Abort what is running (software STOP); stopping the robot itself is RobotController.stop()."""

    def close(self) -> None:
        pass


class RobotGrasper(Grasper):
    """PICK and PLACE_INSPECT done by M2 directly."""

    def __init__(self, robot: RobotController):
        self.robot = robot

    def pick(self, pose: ObjectPose) -> None:
        self.robot.pick(pose)

    def place(self, target: RobotTarget) -> None:
        self.robot.place(target)


class Inspector(ABC):
    """M3 implements this."""

    @abstractmethod
    def inspect(self) -> InspectionResult: ...

    def close(self) -> None:
        pass
