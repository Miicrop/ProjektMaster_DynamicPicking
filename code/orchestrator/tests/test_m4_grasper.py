import sys

import pytest

from common import m4
from common.camera import DahengCamera, FileCamera, daheng_serial, open_camera
from common.config import load_config
from common.interfaces import ObjectPose, RobotTarget
from m2_robot_control import MockRobot
from orchestrator.factory import build_grasper
from orchestrator.m4_grasper import BcGrasper

pytestmark = pytest.mark.skipif(not m4.available(), reason="m4_behavior_cloning missing")

OK_LINE = ("Fahrt 0: ERFOLG -- 176 Takte, Greifpunkt 3.2 mm, Ende 5.1 mm, Bahn p95 8.0 mm, "
           "end_reached, Vorhersage 77.1 ms, Overruns 0, gekappt 3")
FAIL_LINE = OK_LINE.replace("ERFOLG", "kein Erfolg").replace("end_reached", "max_steps")
POSE = ObjectPose(300.0, -200.0, 0.0, 15.0)


def _cfg(**m4_cfg):
    cfg = load_config()
    cfg["m4"].update(checkpoint="checkpoints/test/policy", **m4_cfg)
    cfg["topdown_camera"]["source"] = "daheng:TOP123"
    return cfg


def test_daheng_source_parsing():
    assert daheng_serial("daheng:EBK24100633") == "EBK24100633"
    assert daheng_serial("daheng") == ""
    assert daheng_serial(0) is None and daheng_serial("m1_vision_topdown/tests/data/*.jpg") is None
    cam = open_camera({"source": "daheng:TOP123"})          # opened lazily, no SDK needed here
    assert isinstance(cam, DahengCamera) and cam.serial == "TOP123"
    cam.release()
    assert isinstance(open_camera({"source": "m1_vision_topdown/tests/data/*.jpg"}), FileCamera)


def test_command_per_robot_kind():
    cfg = _cfg()
    argv, stdin, env = BcGrasper(cfg, MockRobot(cfg), "vm").command()
    assert "apps/infer.py" in argv and argv[argv.index("--robot") + 1] == "neura"
    assert "scene=daheng:TOP123" in argv and "--real-robot" not in argv and stdin is None
    assert env["SOCKET_ADDRESS"] == str(cfg["robot"]["vm_host"])

    argv, stdin, env = BcGrasper(cfg, MockRobot(cfg), "real").command()
    assert "--real-robot" in argv and stdin == "ANLAGE\n" and env["SOCKET_ADDRESS"] == str(cfg["robot"]["host"])

    argv, _, env = BcGrasper(cfg, MockRobot(cfg), "mock").command()    # his simulation, sim cameras
    assert argv[argv.index("--robot") + 1] == "sim" and "scene=daheng:TOP123" not in argv


def test_command_needs_a_checkpoint():
    cfg = load_config()
    with pytest.raises(RuntimeError, match="m4.checkpoint"):
        BcGrasper(cfg, MockRobot(cfg), "vm").command()


def _fake_run(monkeypatch, grasper, line, code=0):
    script = f"import sys; print({line!r}); sys.exit({code})"
    monkeypatch.setattr(grasper, "command", lambda: ([sys.executable, "-c", script], None, None))


def test_pick_runs_policy_then_m2_places(monkeypatch):
    cfg = _cfg()
    robot = MockRobot(cfg)
    released = []
    grasper = build_grasper(cfg, "bc", robot, "mock", lambda: released.append(True))
    assert isinstance(grasper, BcGrasper)
    _fake_run(monkeypatch, grasper, OK_LINE)
    grasper.pick(POSE)
    assert released and grasper.last_rollout.success and grasper.last_rollout.grasp_mm == 3.2
    grasper.place(RobotTarget("inspection", 520.8, 199.6, 42.0, -180.0, 0.0, -157.0))
    assert any(h.startswith("place at inspection") for h in robot.history)


def test_pick_fails_without_handover(monkeypatch):
    cfg = _cfg()
    grasper = BcGrasper(cfg, MockRobot(cfg), "mock")
    _fake_run(monkeypatch, grasper, FAIL_LINE)
    with pytest.raises(RuntimeError, match="max_steps"):
        grasper.pick(POSE)
    _fake_run(monkeypatch, grasper, "Traceback: kaputt", code=1)
    with pytest.raises(RuntimeError, match="kaputt"):
        grasper.pick(POSE)


def test_stop_aborts_running_inference(monkeypatch):
    import threading
    cfg = _cfg(timeout_s=30)
    grasper = BcGrasper(cfg, MockRobot(cfg), "mock")
    monkeypatch.setattr(grasper, "command", lambda: (
        [sys.executable, "-c", "import time; print('laeuft', flush=True); time.sleep(30)"], None, None))
    threading.Timer(1.0, grasper.stop).start()
    with pytest.raises(RuntimeError, match="abgebrochen: STOPP"):
        grasper.pick(POSE)
