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


def test_dagger_backfill_matches_rollout_and_keeps_existing(tmp_path):
    import importlib.util
    import json
    from pathlib import Path

    tool = Path(__file__).resolve().parents[1] / "tools" / "dagger_glaettung_nachtragen.py"
    spec = importlib.util.spec_from_file_location("dagger_glaettung_nachtragen", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rng = np.random.default_rng(1)
    action = np.cumsum(rng.normal(0, 0.01, (40, 7)), axis=0)
    ziel = lowpass_series(action[:, :6], 0.5)
    run = tmp_path / "checkpoints" / "M" / "policy" / "rollouts" / "2026-11-23_16-00-00"
    run.mkdir(parents=True)
    np.savez(run / "rollout_000.npz", action=action, ziel=ziel)
    (run / "summary.json").write_text(json.dumps({"args": {"glaettung": 0.5, "inference_steps": None}}))
    data = tmp_path / "dagger"
    for i, cmd in enumerate((ziel, ziel + 0.5)):           # zweite Episode passt zu keiner Fahrt
        ep = data / ("ep_%05d" % i)
        ep.mkdir(parents=True)
        np.savez(ep / "arrays.npz", aux__joints_command=cmd)
        (ep / "meta.json").write_text(json.dumps({"metadata": {"mode": "dagger"}}))

    assert mod.main([str(data), "--root", str(tmp_path), "--schreiben"]) == 1   # eine ohne Zuordnung
    meta = json.loads((data / "ep_00000" / "meta.json").read_text())["metadata"]
    assert meta["glaettung"] == 0.5 and meta["inference_steps"] == 10
    assert meta["glaettung_nachtrag"]["quelle"] == "summary.json"
    assert "glaettung" not in json.loads((data / "ep_00001" / "meta.json").read_text())["metadata"]
