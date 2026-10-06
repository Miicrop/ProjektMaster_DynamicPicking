"""M2 - Neura robot control: pick, place and sort.

Grasp sequence and safety concept: see plan/03_modul2_robotersteuerung.md
Neura API: docs/neura/neurapy_v5.0.8.pdf (poses are [x, y, z, roll, pitch, yaw] in m / rad).
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from common.config import robot_target
from common.interfaces import ObjectPose, RobotController, RobotError, RobotTarget

log = logging.getLogger(__name__)

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
STOPPED_MSG = "Robot stopped - acknowledge first (GUI: 'Fehler quittieren' / 'Freigeben')"
JOG_MAX_MM = 100.0     # largest relative step allowed by NeuraRobot.jog()
JOG_MAX_DEG = 15.0     # rz: only small turns (direction check, fine alignment)
TOOL_TOLERANCE_MM = 1.0  # allowed difference controller tool TCP vs. robot.tool_tcp_mm
INIT_RETRIES = 3        # init_program attempts while the controller refuses play mode (seen on the Neura VM)
INIT_RETRY_WAIT_S = 1.0
SAME_JOINTS_RAD = 1e-3  # joint targets closer than this are not sent (controller would skip them anyway)


# --- helpers -------------------------------------------------------------------

def _wrap_deg(a: float) -> float:
    """Wrap an angle into (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def to_neura(t: RobotTarget) -> list[float]:
    """RobotTarget (mm, deg) -> Neura pose [x, y, z, r, p, y] (m, rad)."""
    return [t.x_mm / 1000.0, t.y_mm / 1000.0, t.z_mm / 1000.0,
            math.radians(t.rx_deg), math.radians(t.ry_deg), math.radians(t.rz_deg)]


def from_neura(name: str, pose: list[float]) -> RobotTarget:
    """Neura pose (m, rad) -> RobotTarget (mm, deg)."""
    x, y, z, r, p, yw = pose[:6]
    return RobotTarget(name, x * 1000.0, y * 1000.0, z * 1000.0,
                       math.degrees(r), math.degrees(p), math.degrees(yw))


def offset_z(t: RobotTarget, dz_mm: float, name: str | None = None) -> RobotTarget:
    return RobotTarget(name or f"{t.name}_approach", t.x_mm, t.y_mm, t.z_mm + dz_mm,
                       t.rx_deg, t.ry_deg, t.rz_deg)


def as_target(cfg: dict[str, Any], pose: ObjectPose | RobotTarget) -> RobotTarget:
    """Convert a detected planar pose into a gripper target (tool pointing down).

    Orientation = home orientation, rotated about the base z-axis by the part angle
    plus the gripper offset (fingers close across the short side of the part).
    """
    if isinstance(pose, RobotTarget):
        return pose
    rc = cfg["robot"]
    home = robot_target(cfg, "home")
    rz = _wrap_deg(home.rz_deg + pose.theta_deg + rc["gripper_angle_offset_deg"])
    return RobotTarget("object", pose.x_mm, pose.y_mm, pose.z_mm + rc["grasp_height_mm"],
                       home.rx_deg, home.ry_deg, rz)


def check_limits(cfg: dict[str, Any], t: RobotTarget) -> None:
    lim = cfg["robot"]["limits_mm"]
    for axis, value in (("x", t.x_mm), ("y", t.y_mm), ("z", t.z_mm)):
        lo, hi = lim[axis]
        if not lo <= value <= hi:
            raise RobotError(f"Target '{t.name}' {axis}={value:.1f} mm outside limits [{lo}, {hi}]")


def load_neurapy_client(host: str, port: int | None = None):
    """Create a neurapy Robot client for the controller at `host`.

    The vendored Windows client reads SOCKET_ADDRESS at import time, so the module
    globals are overwritten before the Robot object is created.
    """
    os.environ["SOCKET_ADDRESS"] = host
    if str(VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(VENDOR_DIR))
    import neurapy.robot as neurapy_robot
    neurapy_robot.SOCKET_ADDRESS = host
    if port is not None:
        neurapy_robot.SOCKET_PORT = port
    try:
        return neurapy_robot.Robot()
    except ConnectionError as e:
        raise RobotError(f"Robot controller {host} not reachable: {e}") from e


# --- implementations -------------------------------------------------------------

class MockRobot(RobotController):
    """Logs motions instead of moving. Checks limits like the real robot."""

    def __init__(self, cfg: dict[str, Any]):
        self._cfg = cfg
        self.holding = False
        self.stopped = False
        self.history: list[str] = []

    def _log(self, msg: str) -> None:
        self.history.append(msg)
        log.info("MockRobot: %s", msg)

    def connect(self) -> None:
        self._log("connect")

    def disconnect(self) -> None:
        self._log("disconnect")

    def _check_ready(self) -> None:
        if self.stopped:
            raise RobotError(STOPPED_MSG)

    def home(self) -> None:
        self._check_ready()
        self._log("home")

    def pick(self, pose: ObjectPose | RobotTarget) -> None:
        self._check_ready()
        t = as_target(self._cfg, pose)
        check_limits(self._cfg, t)
        if self.holding:
            raise RobotError("Gripper already holds a part")
        self._log(f"pick at {t.name} ({t.x_mm:.1f}, {t.y_mm:.1f}, {t.z_mm:.1f}) rz={t.rz_deg:.1f}")
        self.holding = True

    def place(self, target: RobotTarget) -> None:
        self._check_ready()
        check_limits(self._cfg, target)
        if not self.holding:
            raise RobotError("Nothing to place")
        self._log(f"place at {target.name}")
        self.holding = False

    def stop(self) -> None:
        self.stopped = True
        self._log("stop")

    def reset(self) -> None:
        self.stopped = False
        self._log("reset")


class NeuraRobot(RobotController):
    """Neura LARA via the neurapy socket client."""

    def __init__(self, cfg: dict[str, Any],
                 client_factory: Callable[[str], Any] | None = None, gripper: bool | None = None):
        """gripper=None follows robot.gripper_enabled (live), False/True overrides it (e.g. Neura VM)."""
        self._cfg = cfg
        self._rc = cfg["robot"]
        self._gripper = gripper
        self._factory = client_factory or load_neurapy_client
        self.r = None   # neurapy Robot client
        self.stopped = True   # no motion before connect()/reset() has run init_program()

    # -- connection ----------------------------------------------------------
    def open_client(self):
        """Connect without changing anything on the robot (read-only use)."""
        if self.r is None:
            self.r = self._factory(self._rc["host"])
            log.info("Connected to %s (%s DOF), server version %s",
                     getattr(self.r, "robot_name", "?"), getattr(self.r, "dof", "?"),
                     getattr(self.r, "version", "?"))
        return self.r

    def connect(self) -> None:
        self._prepare()

    def _prepare(self) -> None:
        """Power, mode, tool, speed and init_program - needed initially and after every stop()."""
        r = self.open_client()
        if not r.power_on():
            raise RobotError("power_on failed - check emergency stop and pendant")
        if r.is_robot_in_teach_mode():
            log.info("Switching from teach to automatic mode")
            r.switch_to_automatic_mode()
        if self._rc.get("tool_name"):
            r.set_tool(tool_name=self._rc["tool_name"])
        self._check_tool()
        r.set_override(self._rc["override"])
        r.set_joint_speed(self._rc["joint_speed_percent"])
        self._init_program(r)   # required before any motion command
        self.stopped = False

    def _init_program(self, r) -> None:
        """init_program, retried while the controller transiently refuses to switch to play mode."""
        for attempt in range(1, INIT_RETRIES + 1):
            try:
                r.init_program()
                return
            except Exception as e:
                if "play mode" not in str(e):
                    raise
                log.warning("init_program refused (attempt %d/%d): %s", attempt, INIT_RETRIES, e)
                if attempt < INIT_RETRIES:
                    time.sleep(INIT_RETRY_WAIT_S)
        raise RobotError(f"Controller refuses to switch to play mode after {INIT_RETRIES} attempts - "
                         "check the operating mode (automatic) and messages on the pendant / Neura GUI")

    def disconnect(self) -> None:
        self.stop()  # ends the motion program on the controller

    def stop(self) -> None:
        """Stop motion. neurapy's stop() also ends the program on the controller, so every
        further motion is refused until reset() has called init_program() again."""
        self.stopped = True
        if self.r is not None:
            self.r.stop()

    def reset(self) -> None:
        log.info("Reset: preparing robot again (init_program)")
        self._prepare()

    def _check_ready(self) -> None:
        if self.stopped:
            raise RobotError(STOPPED_MSG)

    # -- motion primitives ---------------------------------------------------
    def tool(self) -> tuple[str, list[float]]:
        """Active tool on the controller and its TCP translation offset from the flange [mm].
        All poses in the config and all motion targets refer to this TCP."""
        r = self.open_client()
        return r.get_selected_tool_name(), [v * 1000.0 for v in r.get_current_tool_translation_offsets()]

    @property
    def gripper_enabled(self) -> bool:
        return self._rc.get("gripper_enabled", True) if self._gripper is None else self._gripper

    def gripper(self, close: bool) -> None:
        """Close / open the gripper - skipped (only logged) while the gripper is disabled."""
        if not self.gripper_enabled:
            log.info("Gripper disabled - skipping %s", "close" if close else "open")
            return
        self.open_client().grasp() if close else self.open_client().release()

    def _check_tool(self) -> None:
        """Refuse motion if the controller tool's TCP differs from robot.tool_tcp_mm - every
        pose in the config refers to this TCP, so a wrong offset shifts every grasp height."""
        name, off = self.tool()
        log.info("Tool '%s': TCP offset from flange x=%.1f y=%.1f z=%.1f mm", name, *off)
        expected = self._rc.get("tool_tcp_mm")
        if expected is not None and max(abs(a - b) for a, b in zip(off, expected)) > TOOL_TOLERANCE_MM:
            raise RobotError(
                f"Tool '{name}' TCP offset on the controller {[round(v, 1) for v in off]} mm differs from "
                f"robot.tool_tcp_mm {list(expected)} mm - correct the tool on the pendant (or the config)")

    def current_pose(self) -> RobotTarget:
        return from_neura("current", self.open_client().get_tcp_pose())

    def _joint_move_to(self, t: RobotTarget) -> None:
        """Joint motion (via IK) - used for the large moves between stations."""
        self._check_ready()
        check_limits(self._cfg, t)
        joints = self.r.compute_inverse_kinematics(to_neura(t), self.r.get_current_joint_angles())
        self._move_joint(joints, joints)

    def _move_joint(self, target, joints: list[float]) -> None:
        """move_joint(target) unless the robot already stands at `joints`."""
        current = self.r.get_current_joint_angles()
        if max(abs(a - b) for a, b in zip(current, joints)) < SAME_JOINTS_RAD:
            log.info("Already at %s - joint motion not sent", target if isinstance(target, str) else "target")
            return
        self.r.move_joint(target)

    def _linear(self, a: RobotTarget, b: RobotTarget, speed_mps: float) -> None:
        self._check_ready()
        check_limits(self._cfg, b)
        self.r.move_linear(target_pose=[to_neura(a), to_neura(b)], speed=speed_mps)

    def _slow_point(self, t: RobotTarget) -> RobotTarget | None:
        """Point approach_slow_mm above t where fast and slow motion meet (None: whole way slow)."""
        slow_mm = self._rc.get("approach_slow_mm")
        if slow_mm is None or slow_mm >= self._rc["approach_height_mm"]:
            return None
        return offset_z(t, slow_mm, f"{t.name}_slow")

    def _approach(self, above: RobotTarget, t: RobotTarget) -> None:
        """above -> t: fast down to approach_slow_mm above t, the last mm with approach speed."""
        mid = self._slow_point(t)
        if mid is not None:
            self._linear(above, mid, self._rc["linear_speed_mps"])
            above = mid
        self._linear(above, t, self._rc["approach_speed_mps"])

    def _retreat(self, t: RobotTarget, above: RobotTarget) -> None:
        """t -> above: reverse of _approach (slow off the part, then fast)."""
        mid = self._slow_point(t)
        self._linear(t, mid or above, self._rc["approach_speed_mps"])
        if mid is not None:
            self._linear(mid, above, self._rc["linear_speed_mps"])

    def jog(self, dx_mm: float = 0.0, dy_mm: float = 0.0, dz_mm: float = 0.0,
            drz_deg: float = 0.0) -> RobotTarget:
        """Small relative linear move in the robot BASE frame (slow, approach speed).

        drz_deg turns the tool about the base z-axis (same convention as the grasp angle).
        Returns the commanded target so callers can compare it with the measured pose.
        """
        if max(abs(dx_mm), abs(dy_mm), abs(dz_mm)) > JOG_MAX_MM or abs(drz_deg) > JOG_MAX_DEG:
            raise RobotError(f"Jog step too large (max {JOG_MAX_MM:.0f} mm / {JOG_MAX_DEG:.0f} deg)")
        self._check_ready()
        a = self.current_pose()
        b = RobotTarget("jog", a.x_mm + dx_mm, a.y_mm + dy_mm, a.z_mm + dz_mm,
                        a.rx_deg, a.ry_deg, a.rz_deg + drz_deg)   # NOT wrapped: 180 + 5 -> -175 would
        # make the controller interpolate the angle the long way round (-355 deg) -> joint limit
        log.info("jog dx=%.1f dy=%.1f dz=%.1f mm drz=%.1f deg", dx_mm, dy_mm, dz_mm, drz_deg)
        self._linear(a, b, self._rc["approach_speed_mps"])
        return b

    def _point_targets(self, pose: ObjectPose, hover_mm: float) -> tuple[RobotTarget, RobotTarget]:
        if not 10.0 <= hover_mm < self._rc["approach_height_mm"]:
            raise RobotError(f"Pointing hover {hover_mm:.0f} mm must be >= 10 mm and below the "
                             f"approach height ({self._rc['approach_height_mm']:.0f} mm)")
        t = as_target(self._cfg, pose)
        return offset_z(t, hover_mm, "point"), offset_z(t, self._rc["approach_height_mm"])

    def point_at(self, pose: ObjectPose, hover_mm: float = 30.0) -> RobotTarget:
        """Pointing test: move the open gripper to `hover_mm` above the grasp pose and stay there.

        Same approach as pick() but the gripper never closes - for checking the calibration
        (measure the offset gripper centre <-> part centre). Returns the pointing target.
        """
        hover, above = self._point_targets(pose, hover_mm)
        check_limits(self._cfg, hover)
        check_limits(self._cfg, above)
        log.info("point at (%.1f, %.1f, %.1f) rz=%.1f", hover.x_mm, hover.y_mm, hover.z_mm, hover.rz_deg)
        self._check_ready()
        self.gripper(close=False)
        self._joint_move_to(above)
        self._linear(above, hover, self._rc["approach_speed_mps"])
        return hover

    def retreat(self, pose: ObjectPose, hover_mm: float = 30.0) -> None:
        """Back up from point_at() to the approach height."""
        hover, above = self._point_targets(pose, hover_mm)
        self._linear(hover, above, self._rc["approach_speed_mps"])

    # -- RobotController -----------------------------------------------------
    def home(self) -> None:
        self._check_ready()
        point = self._rc["home_point"]
        self._move_joint(point, self.r.get_point(point, representation="Joint"))

    def pick(self, pose: ObjectPose | RobotTarget) -> None:
        t = as_target(self._cfg, pose)
        above = offset_z(t, self._rc["approach_height_mm"])
        check_limits(self._cfg, t)
        log.info("pick %s at (%.1f, %.1f, %.1f) rz=%.1f", t.name, t.x_mm, t.y_mm, t.z_mm, t.rz_deg)
        self._check_ready()
        self.gripper(close=False)
        self._joint_move_to(above)
        self._approach(above, t)
        self.gripper(close=True)
        time.sleep(self._rc["grip_wait_s"])
        self._retreat(t, above)

    def place(self, target: RobotTarget) -> None:
        above = offset_z(target, self._rc["approach_height_mm"])
        check_limits(self._cfg, target)
        log.info("place at %s", target.name)
        self._joint_move_to(above)
        self._approach(above, target)
        self.gripper(close=False)
        time.sleep(self._rc["grip_wait_s"])
        self._retreat(target, above)
