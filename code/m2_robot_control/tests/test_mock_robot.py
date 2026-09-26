import pytest

from common.config import load_config, robot_target
from common.interfaces import ObjectPose, RobotError
from m2_robot_control import MockRobot


def test_pick_place_cycle():
    cfg = load_config()
    robot = MockRobot(cfg)
    robot.pick(ObjectPose(400, 0, 0, 45))
    robot.place(robot_target(cfg, "inspection"))
    assert not robot.holding


def test_rejects_target_outside_limits():
    robot = MockRobot(load_config())
    with pytest.raises(RobotError):
        robot.pick(ObjectPose(5000, 0, 0, 0))


def test_place_without_part_fails():
    cfg = load_config()
    with pytest.raises(RobotError):
        MockRobot(cfg).place(robot_target(cfg, "bin_good"))
