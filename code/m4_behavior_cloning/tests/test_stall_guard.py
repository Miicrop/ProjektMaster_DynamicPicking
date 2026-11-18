"""Arm steht, Ziel nicht (safety.StallGuard, Anwender 2026-11-16).

Am 16.11. hat der Not-Aus am Handbediengeraet zweimal den Arm angehalten,
infer.py fuhr trotzdem bis max_steps weiter (11-37-51, 12-42-28).
"""

import sys
from pathlib import Path

import _paths  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

import numpy as np
import pytest

from bc import config
from bc.safety import ArmStalled, StallGuard

ROLLOUTS = (Path(__file__).resolve().parents[1]
            / "checkpoints" / "C2_nur_griff_ohne_1111" / "policy" / "rollouts")


def test_frozen_arm_with_distant_target_stops_after_the_limit():
    guard = StallGuard()
    q = np.zeros(6)
    target = q + 0.05
    for _ in range(config.STALL_STEPS):          # erster Aufruf: keine Vorgeschichte
        guard.check(q, target)
    with pytest.raises(ArmStalled, match="arm steht"):
        guard.check(q, target)


def test_standing_at_the_target_or_moving_is_no_stall():
    guard = StallGuard()
    q = np.zeros(6)
    for _ in range(50):                           # Dwell / Zoegern: Arm am Ziel
        assert guard.check(q, q + 0.005) == 0
    for k in range(1, 50):                        # Arm faehrt hinterher
        assert guard.check(q + 0.01 * k, q + 0.01 * k + 0.1) == 0


def test_a_short_stand_resets():
    guard = StallGuard()
    q = np.zeros(6)
    for _ in range(config.STALL_STEPS):
        guard.check(q, q + 0.05)
    guard.check(q + 0.01, q + 0.05)               # Arm bewegt sich wieder
    assert guard.count == 0


def _replay(name, episode=0):
    path = ROLLOUTS / name / ("rollout_%03d.npz" % episode)
    if not path.is_file():
        pytest.skip("Anlagen-Rollout %s nicht vorhanden" % name)
    z = np.load(path)
    guard = StallGuard()
    for step, (q, action) in enumerate(zip(z["joints"], z["action"])):
        try:
            guard.check(q, action[:6])
        except ArmStalled:
            return step
    return None


@pytest.mark.parametrize("name,limit", [("2026-11-16_11-37-51", 95), ("2026-11-16_12-42-28", 90)])
def test_the_emergency_stops_of_the_plant_are_detected(name, limit):
    step = _replay(name)
    assert step is not None and step <= limit, step


@pytest.mark.parametrize("name,episode", [("2026-11-16_12-45-48", 0), ("2026-11-16_12-53-36", 1),
                                          ("2026-11-16_12-55-03", 0), ("2026-11-16_12-55-03", 1)])
def test_normal_plant_runs_are_not_stopped(name, episode):
    assert _replay(name, episode) is None


def _frozen(robot):
    """Not-Aus nachstellen: servo_j kommt an, der Arm bewegt sich nicht."""
    robot.servo_j = lambda *args, **kwargs: None
    return robot


def _base_turn_policy(q0):
    from bc.policy import HoldPolicy

    class Turn(HoldPolicy):
        def predict(self, observation):
            chunk = super().predict(observation)
            chunk[:, :6] = q0
            chunk[:, 0] = q0[0] + 0.1             # Grundachse: Hoehe bleibt
            return chunk
    return Turn()


def test_run_episode_ends_when_the_arm_stands():
    from infer import run_episode
    from test_apps import _infer_setup

    from bc.policy import ChunkEnsembler

    robot, captures, clock, workspace = _infer_setup()
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    _frozen(robot)
    log = run_episode(robot, captures, ChunkEnsembler(_base_turn_policy(q0), replan_steps=2),
                      clock, max_steps=200, workspace=workspace, threaded_watchdog=False,
                      progress=None)
    assert log["stop_reason"].startswith("arm steht"), log["stop_reason"]
    assert len(log["t"]) < 40
    assert robot.stop_requested


def test_run_episode_with_a_following_arm_is_not_stopped():
    from infer import run_episode
    from test_apps import _infer_setup

    from bc.policy import ChunkEnsembler

    robot, captures, clock, workspace = _infer_setup()
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    log = run_episode(robot, captures, ChunkEnsembler(_base_turn_policy(q0), replan_steps=2),
                      clock, max_steps=60, workspace=workspace, threaded_watchdog=False,
                      progress=None)
    assert log["stop_reason"] == "max_steps"


def test_planned_run_ends_when_the_arm_stands():
    from infer import run_planned
    from test_apps import _infer_setup

    robot, captures, clock, workspace = _infer_setup()
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    targets = np.array([q0 + [0.005 * k, 0, 0, 0, 0, 0] for k in range(1, 60)])
    _frozen(robot)
    out = run_planned(robot, workspace, targets, np.zeros(len(targets)), clock,
                      threaded_watchdog=False)
    assert out["stop_reason"].startswith("arm steht"), out["stop_reason"]
    assert len(out["t"]) < 20
