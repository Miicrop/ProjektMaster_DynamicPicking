"""NeuraRobot against the official Neura simulation (VirtualBox VM, robot kind "vm").

Opt-in only: VM and lab robot both use 192.168.2.13 by default, so an automatic run in the lab
could move the real robot. Run explicitly with the VM started (PowerShell):

    $env:NEURA_VM = "1"; python -m pytest m2_robot_control/tests/test_neura_vm.py -v
"""
import copy
import os
import socket

import pytest

from common.config import load_config
from m2_robot_control.robot import VENDOR_DIR
from orchestrator.factory import build_robot

CFG = load_config()
HOST = CFG["robot"]["vm_host"]

if os.environ.get("NEURA_VM") != "1":
    pytest.skip("Neura VM test is opt-in: set NEURA_VM=1 (never in the lab, see module docstring)",
                allow_module_level=True)
if not (VENDOR_DIR / "neurapy" / "robot.py").exists():
    pytest.skip("vendor/neurapy/robot.py not present", allow_module_level=True)
try:
    socket.create_connection((HOST, 65432), timeout=2).close()
except OSError:
    pytest.skip(f"Neura VM not reachable at {HOST}:65432 - start it first", allow_module_level=True)


@pytest.fixture
def vm():
    robot = build_robot(copy.deepcopy(CFG), "vm")
    yield robot
    robot.disconnect()


def test_vm_reports_simulation(vm):
    r = vm.open_client()
    assert r.is_robot_in_simulation()


def test_vm_home_and_jog_roundtrip(vm):
    vm.connect()
    vm.home()
    start = vm.current_pose()
    vm.jog(dz_mm=-20.0)
    down = vm.current_pose()
    vm.jog(dz_mm=+20.0)
    back = vm.current_pose()
    assert down.z_mm == pytest.approx(start.z_mm - 20.0, abs=1.0)
    assert (back.x_mm, back.y_mm, back.z_mm) == pytest.approx((start.x_mm, start.y_mm, start.z_mm), abs=1.0)
