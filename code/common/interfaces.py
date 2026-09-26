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
    """Grasp pose of the part in the robot base frame (M1/M4 -> M2)."""
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
    """M1 (classic vision) and M4 (AI grasping) implement this."""

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


class Inspector(ABC):
    """M3 implements this."""

    @abstractmethod
    def inspect(self) -> InspectionResult: ...

    def close(self) -> None:
        pass
