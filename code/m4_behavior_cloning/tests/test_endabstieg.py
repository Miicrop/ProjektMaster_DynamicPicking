"""Geplanter Endabstieg (bc/endabstieg.py, apps/infer.py --endabstieg)."""
import contextlib
import io
import json
import math
import sys
from types import SimpleNamespace

import numpy as np

import _paths  # noqa: F401
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from bc import config, geometry
from bc import endabstieg as ea


def _pose(x=0.4, y=-0.1, z=0.05, yaw_deg=30.0):
    q_down = geometry.quat_from_axis_angle([1, 0, 0], math.pi)
    rz = geometry.quat_from_axis_angle([0, 0, 1], math.radians(yaw_deg))
    return np.r_[x, y, z, geometry.quat_multiply(rz, q_down)]


def test_senkrecht_haelt_lage_und_drehung():
    p0 = _pose()
    tgt, info = ea.target("senkrecht", p0, 0.01)
    assert np.allclose(tgt[:2], p0[:2]) and abs(tgt[2] - 0.01) < 1e-12
    assert np.allclose(tgt[3:], p0[3:]) and info["quelle"] == "policy"
    assert abs(info["abstieg_m"] - 0.04) < 1e-12


def test_pick_nur_wenn_er_passt():
    p0 = _pose(yaw_deg=30.0)
    ziel = SimpleNamespace(pick=_pose(x=0.403, y=-0.098, z=0.008, yaw_deg=32.0 + 180.0))
    tgt, info = ea.target("pick", p0, 0.01, ziel, max_xy_m=0.006, max_grad=5.0)
    assert info["quelle"] == "pick" and np.allclose(tgt[:3], ziel.pick[:3])
    # 180 Grad symmetrisch: nur +2 Grad gedreht, nicht 182
    assert abs(ea.yaw_diff_sym(ea.tool_yaw_deg(tgt[3:]), ea.tool_yaw_deg(p0[3:])) - 2.0) < 1e-6
    assert abs(info["pick_dreh_grad"] - 2.0) < 1e-6
    weit = SimpleNamespace(pick=_pose(x=0.41, z=0.008))
    tgt, info = ea.target("pick", p0, 0.01, weit, max_xy_m=0.006)
    assert info["quelle"] == "policy" and "passt nicht" in info["grund"]
    assert np.allclose(tgt[:2], p0[:2])
    gedreht = SimpleNamespace(pick=_pose(z=0.008, yaw_deg=40.0))
    assert ea.target("pick", p0, 0.01, gedreht, max_grad=5.0)[1]["quelle"] == "policy"
    tgt, info = ea.target("pick", p0, 0.01, None)
    assert info["quelle"] == "policy" and "kein PICK" in info["grund"]


def test_grasp_z_reihenfolge():
    plane = SimpleNamespace(height_at=lambda x, y: -0.1)
    assert ea.grasp_z([0, 0], None, plane, 0.008)[0] == -0.1 + 0.008
    assert ea.grasp_z([0, 0], None, None, None, 0.02) == (0.02, "tiefster Punkt der Demonstrationen")
    assert ea.grasp_z([0, 0])[0] is None
    assert abs(ea.stop_height(0.0, 0.012) - (config.PROBE_OBJECT_TOP_ABOVE_PICK_M + 0.012)) < 1e-12


def test_run_episode_endet_unterhalb_und_abstieg_greift():
    from infer import planned_descent, run_episode
    from test_apps import _infer_setup

    from bc.kinematics import Kinematics
    from bc.policy import ChunkEnsembler, HoldPolicy

    robot, captures, clock, workspace = _infer_setup()
    log = run_episode(robot, captures, ChunkEnsembler(HoldPolicy(), replan_steps=2), clock,
                      max_steps=20, workspace=workspace, threaded_watchdog=False, progress=None,
                      end_below=lambda tcp: True)
    assert log["stop_reason"].startswith("endabstieg")
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    p0 = np.asarray(robot.fk(q0), dtype=float)
    tgt, info = ea.target("senkrecht", p0, p0[2] - 0.02)
    down = planned_descent(robot, workspace, tgt, clock, threaded_watchdog=False)
    assert down["stop_reason"] == "gegriffen", down["stop_reason"]
    end = np.asarray(robot.fk(robot.read_state().joints), dtype=float)
    assert np.linalg.norm(end[:3] - tgt[:3]) < 5e-4
    assert robot.read_state().gripper_closed
    # unterwegs senkrecht: xy bleibt
    xy = np.asarray(down["tcp"])[:, :2]
    assert np.max(np.linalg.norm(xy - p0[:2], axis=1)) < 5e-4


def test_infer_mit_endabstieg_laeuft_ohne_lage_bekannt(tmp_path):
    import infer
    from test_auto_layout import SEQ, _points

    from bc.adapters.sim_robot import SimRobot

    points, _ = _points(size=0.12)
    seq = tmp_path / "ablauf.json"
    seq.write_text(json.dumps(SEQ), encoding="utf-8")
    saved = sys.argv, infer.open_robot
    sys.argv = ["infer.py", "--sim", "--hold", "--steps", "10", "--episodes", "1",
                "--ablauf", str(seq), "--endabstieg", "pick", "--out", str(tmp_path / "out")]
    infer.open_robot = lambda kind, clock=None, **kw: SimRobot(clock=clock, points=points)
    log, error = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(log):
            infer.main()
    except SystemExit as exc:
        error = exc
    finally:
        sys.argv, infer.open_robot = saved
    text = log.getvalue()
    assert error is None, (repr(error), getattr(error, "code", None), text[-1500:])
    assert "Endabstieg pick: PICK" in text and "Greifhoehe aus" in text, text[-3000:]
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["args"]["endabstieg"] == "pick"


def test_infer_ganzer_ablauf_policy_ende_abstieg_griff_transport(tmp_path):
    """Hold-Policy, Endabstieg sofort ausgeloest: Abstieg, Griff, geplanter Transport."""
    import infer
    from test_auto_layout import SEQ, _points

    from bc.adapters.sim_robot import SimRobot

    points, _ = _points(size=0.12)
    seq = tmp_path / "ablauf.json"
    seq.write_text(json.dumps(SEQ), encoding="utf-8")
    saved = sys.argv, infer.open_robot, ea.stop_height, ea.MAX_DESCENT_M
    ea.stop_height = lambda z, a: 10.0          # sofort unter der Hoehe
    ea.MAX_DESCENT_M = 1.0
    sys.argv = ["infer.py", "--sim", "--hold", "--steps", "10", "--episodes", "1",
                "--ablauf", str(seq), "--endabstieg", "pick", "--out", str(tmp_path / "out")]
    infer.open_robot = lambda kind, clock=None, **kw: SimRobot(clock=clock, points=points)
    log, error = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(log):
            infer.main()
    except SystemExit as exc:
        error = exc
    finally:
        sys.argv, infer.open_robot, ea.stop_height, ea.MAX_DESCENT_M = saved
    text = log.getvalue()
    assert error is None, (repr(error), text[-2000:])
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    ep = summary["episodes"][0]
    info = ep["endabstieg"]
    # Start weit weg vom PICK: PICK passt nicht -> senkrecht
    assert info["quelle"] == "policy" and "passt nicht" in info["grund"], info
    assert info["ergebnis"] == "gegriffen", (info, text[-2000:])
    assert ep["stop_reason"] == "endstellung", (ep["stop_reason"], text[-2000:])
