"""Commissioning steps shared by robot_check (CLI) and the GUI (tab M2): info, axis test,
marker calibration, pointing test. Qt-free; see ANLEITUNG_NEURA.md sections 6-7b."""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from common.config import robot_target
from common.interfaces import RobotTarget
from common.transforms import fit_workspace_to_robot, rigid_2d
from m2_robot_control.robot import NeuraRobot, _wrap_deg

JOG_AXES = {"x": "dx_mm", "y": "dy_mm", "z": "dz_mm", "rz": "drz_deg"}
STATIONS = ["inspection", "bin_good", "bin_bad"]
CALIB_RMS_WARN_MM = 3.0

# axis test: (axis, expected observation) in the order of ANLEITUNG_NEURA.md section 6
AXES_SEQUENCE = [("z", "nach OBEN (weg vom Tisch)"), ("x", "Richtung +X der Basis"),
                 ("y", "Richtung +Y der Basis"), ("rz", "Greifer dreht um die senkrechte Achse (+rz)")]


def fmt_pose(p: RobotTarget) -> str:
    return (f"x={p.x_mm:.1f} y={p.y_mm:.1f} z={p.z_mm:.1f} mm  "
            f"rx={p.rx_deg:.1f} ry={p.ry_deg:.1f} rz={p.rz_deg:.1f} deg")


def pose_list(p: RobotTarget) -> list[float]:
    """Pose as config line value [x, y, z, rx, ry, rz], rounded to 0.1."""
    return [round(v, 1) for v in (p.x_mm, p.y_mm, p.z_mm, p.rx_deg, p.ry_deg, p.rz_deg)]


# --- step 1: info --------------------------------------------------------------------

def robot_info(robot: NeuraRobot, cfg: dict[str, Any]) -> tuple[list[tuple[str, str]], list[str]]:
    """Read-only overview. Returns (rows, problems); no problems = step passed."""
    r = robot.open_client()
    name, off = robot.tool()
    errors = r.get_errors()
    points = r.get_point_names()
    rc = cfg["robot"]
    rows = [("Roboter", f"{r.robot_name}  dof={r.dof}  Server v{str(r.version).lstrip('v')}"),
            ("Teach-Modus", str(r.is_robot_in_teach_mode())),
            ("Tool", f"{name}  TCP-Versatz {[round(v, 1) for v in off]} mm  "
                     f"(Config: {rc.get('tool_name')} {rc.get('tool_tcp_mm')} mm)"),
            ("TCP-Pose", fmt_pose(robot.current_pose())),
            ("Gelenke [rad]", str([round(j, 4) for j in r.get_current_joint_angles()])),
            ("Punkte", str(points)),
            ("Fehler", str(errors) if errors else "keine")]
    problems = []
    if errors:
        problems.append(f"Fehler am Roboter: {errors}")
    if rc.get("home_point") not in (points or []):
        problems.append(f"Punkt '{rc.get('home_point')}' fehlt auf dem Roboter")
    expected = rc.get("tool_tcp_mm")
    if name != rc.get("tool_name"):
        rows.append(("Hinweis", f"Tool '{rc.get('tool_name')}' wird erst beim Verbinden aktiviert"))
    elif expected is not None and max(abs(a - b) for a, b in zip(off, expected)) > 1.0:
        problems.append("TCP-Versatz des Tools weicht von robot.tool_tcp_mm ab")
    return rows, problems


# --- step 4: axis test -----------------------------------------------------------------

def jog_measured(robot: NeuraRobot, axis: str, value: float) -> dict[str, float]:
    """One relative step; returns the measured change of the TCP pose."""
    before = robot.current_pose()
    robot.jog(**{JOG_AXES[axis]: value})
    after = robot.current_pose()
    return {"dx": after.x_mm - before.x_mm, "dy": after.y_mm - before.y_mm, "dz": after.z_mm - before.z_mm,
            "drz": _wrap_deg(after.rz_deg - before.rz_deg)}


def fmt_delta(d: dict[str, float]) -> str:
    return f"dx={d['dx']:+.1f} dy={d['dy']:+.1f} dz={d['dz']:+.1f} mm  drz={d['drz']:+.1f} deg"


def axis_there_and_back(robot: NeuraRobot, axis: str, value: float) -> tuple[dict, dict]:
    """Axis test of one axis: step in + direction, then back. Returns both measured changes."""
    return jog_measured(robot, axis, value), jog_measured(robot, axis, -value)


def log_axes(cfg: dict[str, Any], rows: list[dict[str, str]]) -> Any:
    """Axis test protocol -> logs/axes_tests.csv (one row per axis)."""
    return _append_csv(cfg, "axes_tests.csv", ["time", "axis", "step", "measured", "observation"], rows)


# --- calibration workspace -> robot ------------------------------------------------------

@dataclass
class CalibResult:
    rotation_deg: float
    translation_mm: tuple[float, float]
    table_z_mm: float
    residuals_mm: dict[int, float] = field(default_factory=dict)

    @property
    def rms_mm(self) -> float:
        return float(np.sqrt(np.mean(np.square(list(self.residuals_mm.values())))))

    @property
    def ok(self) -> bool:
        return self.rms_mm <= CALIB_RMS_WARN_MM


def calibrate(cfg: dict[str, Any], taught: dict[int, tuple[float, float, float]]) -> CalibResult:
    """Fit workspace -> robot base from TCP positions (x, y, z) taught at the marker centres."""
    markers = {int(k): v for k, v in cfg["workspace"]["markers_mm"].items()}
    ids = sorted(m for m in taught if m in markers)
    if len(ids) < 3:
        raise ValueError("Mindestens 3 Marker nötig")
    rot, t, res = fit_workspace_to_robot([markers[m][:2] for m in ids], [taught[m][:2] for m in ids])
    return CalibResult(float(rot), (float(t[0]), float(t[1])),
                       float(np.mean([taught[m][2] for m in ids])),
                       {m: float(r) for m, r in zip(ids, res)})


def calib_config(c: CalibResult) -> dict[str, Any]:
    """Values for the config section workspace_to_robot."""
    return {"rotation_deg": round(c.rotation_deg, 2),
            "translation_mm": [round(c.translation_mm[0], 1), round(c.translation_mm[1], 1)],
            "table_z_mm": round(c.table_z_mm, 1)}


def marker_target(cfg: dict[str, Any], marker_id: int, height_mm: float) -> RobotTarget:
    """TCP target `height_mm` above a marker centre, using the CURRENT calibration
    (for re-teaching: drive above, then jog down onto the marker)."""
    mx, my = cfg["workspace"]["markers_mm"][marker_id][:2]
    w2r = cfg["workspace_to_robot"]
    x, y = rigid_2d([[mx, my]], w2r["rotation_deg"], w2r["translation_mm"])[0]
    home = robot_target(cfg, "home")
    return RobotTarget(f"marker_{marker_id}", float(x), float(y), w2r["table_z_mm"] + height_mm,
                       home.rx_deg, home.ry_deg, home.rz_deg)


# --- pointing test ------------------------------------------------------------------------

POINT_FIELDS = ["time", "detector", "x_ws_mm", "y_ws_mm", "theta_ws_deg", "x_mm", "y_mm", "theta_deg",
                "confidence", "target_x_mm", "target_y_mm", "target_z_mm", "target_rz_deg", "hover_mm",
                "dx_mm", "dy_mm", "note"]


def point_row(detector_kind: str, pose, ws, target: RobotTarget, hover_mm: float,
              dx_mm: float | None = None, dy_mm: float | None = None, note: str = "") -> dict[str, Any]:
    return {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "detector": detector_kind,
            "x_ws_mm": f"{ws.x_ws_mm:.1f}" if ws else "", "y_ws_mm": f"{ws.y_ws_mm:.1f}" if ws else "",
            "theta_ws_deg": f"{ws.theta_ws_deg:.1f}" if ws else "",
            "x_mm": f"{pose.x_mm:.1f}", "y_mm": f"{pose.y_mm:.1f}", "theta_deg": f"{pose.theta_deg:.1f}",
            "confidence": pose.confidence, "target_x_mm": f"{target.x_mm:.1f}",
            "target_y_mm": f"{target.y_mm:.1f}", "target_z_mm": f"{target.z_mm:.1f}",
            "target_rz_deg": f"{target.rz_deg:.1f}", "hover_mm": hover_mm,
            "dx_mm": "" if dx_mm is None else f"{dx_mm:.1f}", "dy_mm": "" if dy_mm is None else f"{dy_mm:.1f}",
            "note": note}


def log_point(cfg: dict[str, Any], row: dict[str, Any]) -> Any:
    return _append_csv(cfg, "point_tests.csv", POINT_FIELDS, [row])


def _append_csv(cfg: dict[str, Any], name: str, fields: list[str], rows: list[dict]) -> Any:
    from orchestrator.logbook import log_dir
    f = log_dir(cfg) / name
    new = not f.exists()
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter=";")
        if new:
            w.writeheader()
        w.writerows(rows)
    return f
