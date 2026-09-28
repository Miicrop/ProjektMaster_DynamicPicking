"""NeuraRobot against the fake controller, through the unmodified vendor client.

The vendor client itself (m2_robot_control/vendor/neurapy/) is Neura's proprietary code and is
not part of the public repo (see vendor/README.md) - get it from your Neura contact and place it
there. Without it, this whole file is skipped rather than failing with an import error.
"""
import copy
import math
from pathlib import Path

import pytest

from common.config import load_config, robot_target
from common.interfaces import ObjectPose, RobotError
from m2_robot_control.fake_neura_server import FakeNeuraServer
from m2_robot_control.robot import VENDOR_DIR, NeuraRobot, as_target, from_neura, load_neurapy_client, to_neura

if not (VENDOR_DIR / "neurapy" / "robot.py").exists():
    pytest.skip("vendor/neurapy/robot.py not present (proprietary, excluded from the public repo) "
               "- get it from your Neura contact for these tests", allow_module_level=True)

CFG = load_config()


@pytest.fixture
def sim():
    server = FakeNeuraServer("127.0.0.1", 0).start_background()
    cfg = copy.deepcopy(CFG)
    cfg["robot"]["grip_wait_s"] = 0.0
    robot = NeuraRobot(cfg, client_factory=lambda host: load_neurapy_client("127.0.0.1", server.port))
    yield robot, server.fake
    server.shutdown()
    server.server_close()


def names(fake):
    return [c[0] for c in fake.calls]


def test_unit_conversion_roundtrip():
    t = robot_target(CFG, "inspection")
    back = from_neura("x", to_neura(t))
    assert (back.x_mm, back.y_mm, back.z_mm) == pytest.approx((t.x_mm, t.y_mm, t.z_mm))
    assert to_neura(t)[0] == pytest.approx(t.x_mm / 1000)
    assert to_neura(t)[3] == pytest.approx(math.radians(t.rx_deg))


def test_grasp_orientation_follows_part_angle():
    a = as_target(CFG, ObjectPose(500, 0, 0, 0))
    b = as_target(CFG, ObjectPose(500, 0, 0, 30))
    assert (b.rz_deg - a.rz_deg) % 360 == pytest.approx(30)
    assert -180 < b.rz_deg <= 180


def test_connect_prepares_robot(sim):
    robot, fake = sim
    robot.connect()
    assert fake.powered and not fake.teach_mode and fake.program_ready
    assert fake.tool == CFG["robot"]["tool_name"]
    assert fake.override == CFG["robot"]["override"]


def test_pick_and_place_sequence(sim):
    robot, fake = sim
    robot.connect()
    robot.home()
    robot.pick(ObjectPose(500, 50, 0, 45))
    assert fake.gripper_closed
    robot.place(robot_target(CFG, "inspection"))
    assert not fake.gripper_closed
    seq = [n for n in names(fake) if n in ("move_joint", "move_linear", "grasp", "release")]
    assert seq == ["move_joint",                                   # home
                   "release", "move_joint", "move_linear", "grasp", "move_linear",  # pick
                   "move_joint", "move_linear", "release", "move_linear"]           # place
    # ends above the inspection pose
    assert fake.tcp[2] * 1000 == pytest.approx(
        CFG["robot"]["poses"]["inspection"][2] + CFG["robot"]["approach_height_mm"])


def test_motion_without_connect_fails(sim):
    robot, fake = sim
    robot.open_client()
    with pytest.raises(RobotError, match="acknowledge"):   # refused before anything is sent
        robot.home()
    assert "move_joint" not in names(fake)


def test_limits_checked_before_motion(sim):
    robot, fake = sim
    robot.connect()
    with pytest.raises(RobotError):
        robot.pick(ObjectPose(5000, 0, 0, 0))
    assert "move_joint" not in names(fake)


def test_stop_requires_reset_then_works_again(sim):
    """Regression: after STOP neurapy needs init_program() again (GUI 'Fehler quittieren')."""
    robot, fake = sim
    robot.connect()
    robot.stop()
    assert not fake.program_ready
    with pytest.raises(RobotError, match="acknowledge"):
        robot.home()
    robot.reset()
    assert fake.program_ready
    robot.home()
    robot.pick(ObjectPose(500, 50, 0, 45))


def test_jog_moves_relative_in_base_frame(sim):
    robot, fake = sim
    robot.connect()
    robot.home()
    start = robot.current_pose()
    robot.jog(dz_mm=50)
    robot.jog(dx_mm=-20, drz_deg=20)
    p = robot.current_pose()
    assert (p.x_mm, p.y_mm, p.z_mm) == pytest.approx((start.x_mm - 20, start.y_mm, start.z_mm + 50))
    assert (p.rz_deg - start.rz_deg) % 360 == pytest.approx(20)
    assert names(fake).count("move_linear") == 2


def test_jog_refuses_large_steps_and_limits(sim):
    robot, fake = sim
    robot.connect()
    robot.home()
    with pytest.raises(RobotError, match="too large"):
        robot.jog(dx_mm=150)
    robot._cfg["robot"]["limits_mm"]["z"] = [-10.0, 450.0]   # Home z = 434 mm
    with pytest.raises(RobotError, match="outside limits"):
        robot.jog(dz_mm=50)
    assert "move_linear" not in names(fake)


# --- pointing test (dry run above the detected part) ----------------------------------

def test_point_at_hovers_without_grasping(sim):
    robot, fake = sim
    robot.connect()
    robot.home()
    pose = ObjectPose(500, 50, 0, 45)
    robot.point_at(pose, hover_mm=30)
    t = as_target(CFG, pose)
    assert [v * 1000 for v in fake.tcp[:3]] == pytest.approx([t.x_mm, t.y_mm, t.z_mm + 30])
    assert "grasp" not in names(fake) and not fake.gripper_closed
    robot.retreat(pose, hover_mm=30)
    assert fake.tcp[2] * 1000 == pytest.approx(t.z_mm + CFG["robot"]["approach_height_mm"])


def test_point_at_refuses_low_hover_and_limits(sim):
    robot, fake = sim
    robot.connect()
    with pytest.raises(RobotError, match="hover"):
        robot.point_at(ObjectPose(500, 50, 0, 0), hover_mm=5)
    with pytest.raises(RobotError, match="outside limits"):
        robot.point_at(ObjectPose(5000, 0, 0, 0), hover_mm=30)
    assert "move_joint" not in names(fake) and "move_linear" not in names(fake)
