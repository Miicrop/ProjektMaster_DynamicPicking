"""Tiefpass auf die Policy-Ziele und Offline-Test DDIM/Glaettung (Anlage 2026-11-23)."""

import numpy as np

import _paths  # noqa: F401

from bc import offline_glaette
from bc.gui import operation
from bc.servo import CommandLowpass, lowpass_series


def test_lowpass_off_passes_through_and_on_smooths_with_lag():
    off = CommandLowpass(1.0).reset(np.zeros(6))
    assert not off.active
    assert np.allclose(off.apply(np.ones(6)), 1.0)

    lp = CommandLowpass(0.5).reset(np.zeros(6))
    assert lp.active and abs(lp.lag_steps - 1.0) < 1e-9
    assert np.allclose(lp.apply(np.ones(6)), 0.5)
    assert np.allclose(lp.apply(np.ones(6)), 0.75)
    # Reset auf ein gehaltenes Ziel: kein Nachziehen danach
    lp.reset(np.full(6, 2.0))
    assert np.allclose(lp.apply(np.full(6, 2.0)), 2.0)


def test_lowpass_rejects_bad_alpha_and_needs_reset():
    for alpha in (0.0, -0.1, 1.5):
        try:
            CommandLowpass(alpha)
        except ValueError:
            continue
        raise AssertionError("alpha %s haette abgelehnt werden muessen" % alpha)
    try:
        CommandLowpass(0.5).apply(np.zeros(6))
    except RuntimeError:
        pass
    else:
        raise AssertionError("apply ohne reset")


def test_lowpass_series_reduces_zigzag():
    t = np.arange(60)
    zigzag = np.stack([0.01 * t + 0.003 * (-1) ** t] * 6, axis=1)
    smooth = lowpass_series(zigzag, 0.3)
    jerk = lambda x: np.abs(np.diff(x, 2, axis=0)).mean()
    assert jerk(smooth) < 0.3 * jerk(zigzag)
    assert np.allclose(lowpass_series(zigzag, 1.0), zigzag)


def test_offline_metrics_on_straight_descent():
    # Gerade, gleichfoermige Bahn: Ruck 0; Chunks gleich -> kein Sprung
    fk = lambda q: np.asarray(q, dtype=float)[..., :3]
    n = 40
    tcp = np.zeros((n, 3))
    tcp[:, 2] = np.linspace(0.10, 0.0, n)
    gripper = np.zeros(n)
    gripper[30:] = 1.0
    near = offline_glaette.near_mask(tcp, gripper, near_mm=60.0)
    assert near[:30].sum() > 0 and not near[30:].any()
    actions = np.hstack([tcp, np.zeros((n, 3)), gripper[:, None]])
    history = [(s, actions[s:s + 8]) for s in range(0, n - 8, 2)]
    inside, gaps = offline_glaette.chunk_metrics(history, fk, near)
    assert inside.max() < 1e-9 and gaps.max() < 1e-9
    m = offline_glaette.command_metrics(actions, actions, fk, near, (1.0, 0.3))
    assert m[1.0]["abstand_mm"].max() < 1e-9
    assert m[0.3]["abstand_mm"].max() > 0.5          # Glaettung kostet Verzug
    assert offline_glaette.stats([])["n"] == 0


def test_argv_ddim_and_glaettung():
    plain = operation.infer_argv("checkpoints/x", "neura", 1)
    assert "--inference-steps" not in plain and "--glaettung" not in plain
    off = operation.infer_argv("checkpoints/x", "neura", 1, glaettung=1.0)
    assert off[off.index("--glaettung") + 1] == "1"          # aus muss explizit mit
    argv = operation.infer_argv("checkpoints/x", "neura", 1, inference_steps=20, glaettung=0.3)
    assert argv[argv.index("--inference-steps") + 1] == "20"
    assert argv[argv.index("--glaettung") + 1] == "0.3"
    off = operation.offline_ddim_argv("checkpoints/x", "data_vm/a", schritte="10, 20",
                                      glaettung="1,0.5", episodes="0-2")
    assert off[0] == "apps/ddim_offline.py" and off[4] == "data_vm/a"
    assert off[off.index("--schritte") + 1] == "10,20"
    for bad in ((None, "d"), ("c", "")):
        try:
            operation.offline_ddim_argv(*bad)
        except ValueError:
            continue
        raise AssertionError("ohne Modell/Aufnahme haette es abbrechen muessen")
