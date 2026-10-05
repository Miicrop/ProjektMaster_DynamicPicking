"""build_robot: each Neura kind must connect to its own address (VM never to the lab robot and vice versa)."""
import copy

import pytest

import m2_robot_control.robot as robot_mod
from common.config import load_config
from orchestrator.factory import ROBOT_KINDS, build_robot

CFG = load_config()


@pytest.fixture
def hosts(monkeypatch):
    """Record the address every neurapy client is created for, without any network access."""
    seen = []
    monkeypatch.setattr(robot_mod, "load_neurapy_client", lambda host, port=None: seen.append(host) or object())
    cfg = copy.deepcopy(CFG)
    cfg["robot"]["host"] = "10.0.0.1"
    cfg["robot"]["vm_host"] = "10.0.0.2"
    return cfg, seen


def test_vm_is_a_robot_kind():
    assert "vm" in ROBOT_KINDS


@pytest.mark.parametrize("kind, expected", [("real", "10.0.0.1"), ("vm", "10.0.0.2")])
def test_neura_kinds_use_their_own_host(hosts, kind, expected):
    cfg, seen = hosts
    build_robot(cfg, kind).open_client()
    assert seen == [expected]


def test_vm_has_no_gripper_real_follows_config(hosts):
    cfg, _ = hosts
    cfg["robot"]["gripper_enabled"] = True
    assert build_robot(cfg, "vm").gripper_enabled is False
    assert build_robot(cfg, "real").gripper_enabled is True
    cfg["robot"]["gripper_enabled"] = False
    assert build_robot(cfg, "real").gripper_enabled is False


def test_vm_follows_vm_host_changed_after_build(hosts):
    cfg, seen = hosts
    robot = build_robot(cfg, "vm")
    cfg["robot"]["vm_host"] = "10.0.0.3"   # e.g. edited in the GUI before connecting
    robot.open_client()
    assert seen == ["10.0.0.3"]
