"""Where M4 (Behavior Cloning, code/m4_behavior_cloning) lives and how to reach it.

His pipeline runs in two Python environments: our GUI process imports only the Qt/numpy parts
of `bc`; everything with torch/lerobot runs as a subprocess with his own venv (BC_PYTHON).
Used by the M4 tab (gui/tab_m4.py), the M4 grasper (orchestrator/m4_grasper.py) and the
Daheng camera (common/camera.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from common.config import CODE_ROOT

BC_DIR = CODE_ROOT / "m4_behavior_cloning"
BC_VENV_PYTHON = BC_DIR / ".venv" / "Scripts" / "python.exe"
NEURAPY_DIR = CODE_ROOT / "m2_robot_control" / "vendor"   # same neurapy v5.0.8 as his


def available() -> bool:
    return (BC_DIR / "bc" / "__init__.py").is_file()


def prepare(cfg: dict[str, Any] | None = None) -> None:
    """Make `import bc` work here and point his subprocesses at the right Python / controller.

    Only sets what is not set yet, so his own variables (BC_PYTHON, BC_NEURAPY_DIR) win.
    """
    if not available():
        raise RuntimeError(f"M4 nicht gefunden: {BC_DIR}")
    os.environ.setdefault("BC_NEURAPY_DIR", str(NEURAPY_DIR))
    if BC_VENV_PYTHON.is_file():
        os.environ.setdefault("BC_PYTHON", str(BC_VENV_PYTHON))
    if str(BC_DIR) not in sys.path:
        sys.path.insert(0, str(BC_DIR))


def bc_python() -> str:
    """Interpreter for his subprocesses: BC_PYTHON, else his venv, else ours (no torch then)."""
    configured = os.environ.get("BC_PYTHON")
    if configured and Path(configured).is_file():
        return configured
    return str(BC_VENV_PYTHON) if BC_VENV_PYTHON.is_file() else sys.executable


def has_own_env() -> bool:
    return bc_python() != sys.executable
