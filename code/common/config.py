"""Loading of config/system.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from common.interfaces import RobotTarget

CODE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = CODE_ROOT / "config" / "system.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def robot_target(cfg: dict[str, Any], name: str) -> RobotTarget:
    """Build a RobotTarget from a named pose in the robot section."""
    try:
        x, y, z, rx, ry, rz = cfg["robot"]["poses"][name]
    except KeyError as e:
        raise KeyError(f"Pose '{name}' not defined in config robot.poses") from e
    return RobotTarget(name, x, y, z, rx, ry, rz)
