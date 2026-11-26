"""Geplanter Stoss waehrend der Policy-Fahrt (bc/stoerung.py, apps/infer.py --stoerung-*)."""
import math

import numpy as np

import _paths  # noqa: F401

from bc import config, dagger, geometry
from bc.stoerung import Stoerung, StoerungConfig, parse_range


def test_parse_range():
    assert parse_range("4-8", "x") == (4.0, 8.0)
    assert parse_range("6", "x") == (6.0, 6.0)
    assert parse_range("0,5-2", "x") == (0.5, 2.0)
    for bad in ("8-4", "a-b", "1-2-3"):
        try:
            parse_range(bad, "x")
        except ValueError:
            continue
        raise AssertionError(bad)


def test_ziehen_respektiert_anteil_und_bereiche():
    cfg = StoerungConfig(anteil=0.3, versatz_mm=(4, 8), drehung_grad=(1, 3), hoehe_mm=(70, 110))
    st = Stoerung(cfg, np.random.default_rng(0), 0.0)
    plans = [st.ziehen() for _ in range(400)]
    share = np.mean([p["geplant"] for p in plans])
    assert 0.22 < share < 0.38
    assert all(4 <= p["versatz_mm"] <= 8 and 1 <= abs(p["drehung_grad"]) <= 3
               and 70 <= p["hoehe_mm"] <= 110 for p in plans)
    assert Stoerung(StoerungConfig(), np.random.default_rng(0), 0.0).ziehen() is None


def _run(stoss, steps=20, mitschrieb=None):
    from infer import run_episode
    from test_apps import _infer_setup

    from bc.policy import ChunkEnsembler, HoldPolicy

    robot, captures, clock, workspace = _infer_setup()
    log = run_episode(robot, captures, ChunkEnsembler(HoldPolicy(), replan_steps=2), clock,
                      max_steps=steps, workspace=workspace, threaded_watchdog=False,
                      progress=None, stoerung=stoss, mitschrieb=mitschrieb)
    return robot, log


def test_stoss_versetzt_waagrecht_und_dreht_hoehe_bleibt():
    from test_apps import _infer_setup

    robot, _, _, _ = _infer_setup()
    p0 = np.asarray(robot.fk(robot.read_state().joints), dtype=float)
    cfg = StoerungConfig(anteil=1.0, versatz_mm=(6, 6), drehung_grad=(3, 3), hoehe_mm=(100, 100),
                         takte=6)
    # PICK 50 mm unter dem Start: sofort unter der Stosshoehe
    stoss = Stoerung(cfg, np.random.default_rng(1), p0[2] - 0.05)
    plan = stoss.ziehen()
    assert plan["geplant"]
    rec = dagger.Mitschrieb(["wrist", "scene"])
    robot, log = _run(stoss, mitschrieb=rec)
    info = log["stoerung"]
    assert info["erfolgt"] and info["takt"] == 1        # Takt 0 hat noch keinen Greiferbefehl
    end = np.asarray(log["final_tcp"], dtype=float)
    d = 1e3 * (end[:2] - p0[:2])
    # HoldPolicy haelt danach die verschobene Lage
    assert abs(np.linalg.norm(d) - 6.0) < 0.5, d
    w = math.radians(plan["richtung_grad"])
    assert np.dot(d / np.linalg.norm(d), [math.cos(w), math.sin(w)]) > 0.99
    assert abs(1e3 * (end[2] - p0[2])) < 0.5
    yaw = math.degrees(geometry.quat_angle_between(end[3:], p0[3:]))
    assert abs(yaw - 3.0) < 0.3, yaw
    # Stoss-Takte stehen im Log und im Mitschrieb (als Policy-Takte -> Labels zur Idealbahn)
    assert len(log["t"]) == 20 - 1 + cfg.takte
    assert rec.count(dagger.POLICY) == len(log["t"])
    assert np.isfinite(log["ensemble_spread"]).all()


def test_ohne_stoss_unveraendert():
    from test_apps import _infer_setup

    robot, _, _, _ = _infer_setup()
    p0 = np.asarray(robot.fk(robot.read_state().joints), dtype=float)
    cfg = StoerungConfig(anteil=1.0, hoehe_mm=(70, 70))
    stoss = Stoerung(cfg, np.random.default_rng(1), p0[2] - 0.5)   # 500 mm darueber: nie faellig
    stoss.ziehen()
    _, log = _run(stoss)
    assert not log["stoerung"]["erfolgt"] and len(log["t"]) == 20
    end = np.asarray(log["final_tcp"], dtype=float)
    assert np.linalg.norm(end[:3] - p0[:3]) < 1e-4


def test_discard_before_laesst_den_naechsten_takt_gedeckt():
    from bc.policy import ChunkEnsembler, HoldPolicy

    ens = ChunkEnsembler(HoldPolicy(horizon=8), replan_steps=2)
    obs = {"observation.state": np.zeros(config.STATE_DIM, dtype=np.float32)}
    for _ in range(5):
        ens.next_action(obs)
    ens.discard_before(100)          # alles waere alt: der juengste deckende bleibt
    ens.next_action(obs)
    ens.discard_before(ens.step - 1)
    assert all(s >= ens.step - 1 for s, _ in ens._chunks) or len(ens._chunks) == 1
