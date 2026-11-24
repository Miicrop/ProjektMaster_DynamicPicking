"""Anflug-Versatz naeher am Objekt mit Backen-Pruefung (bc/noise.py, record.py --anflug-versatz-nah, Sim-Versuch V6)."""
import numpy as np

from bc import config, noise
from bc.trajectory import Waypoint, build_ideal_trajectory

Q = [0.0, 0.0, 0.0, 1.0]
PRUEF = {"top_above_pick_m": 0.0084, "overshoot_m": 0.0024, "reserve_m": 0.001, "eps_m": 0.0001,
         "lever_m": 0.029}


def _wp(z, **kw):
    return Waypoint(np.array([0.3, 0.0, z] + Q, dtype=float), **kw)


def _ideal():
    return build_ideal_trajectory([_wp(0.25), _wp(0.05, blend_m=0.01),
                                   _wp(0.0, approach=True, gripper_closed=True), _wp(0.05)])


def _bahn(offset):
    return noise.sample_noisy_poses(_ideal(), np.random.default_rng(0), sigma_pos=0.0, sigma_rot=0.0,
                                    approach_offset=offset)


def test_standard_ohne_pruefung():
    assert config.APPROACH_TIP_CHECK is None
    ideal = _ideal()
    poses = _bahn(np.array([0.02, 0.0, 0.0, 0.0]))
    assert noise.approach_rest(ideal, poses) == noise.approach_rest(ideal, poses, free_m=0.020)


def test_backen_frei_wenn_versatz_hoch_genug_null(monkeypatch):
    monkeypatch.setattr(config, "APPROACH_OFFSET_FULL_M", 0.025)
    monkeypatch.setattr(config, "APPROACH_OFFSET_FREE_M", 0.012)
    ideal = _ideal()
    for off in ([0.025, 0.0, 0.0, 0.0], [0.0, 0.01, 0.0, np.radians(35.0)]):
        frei = noise.approach_tip_clearance(ideal, _bahn(np.array(off)), PRUEF)
        assert 0.0 <= frei < np.inf
    assert noise.approach_tip_clearance(ideal, _bahn(None), PRUEF) == np.inf


def test_backen_verletzt_wenn_versatz_zu_tief(monkeypatch):
    monkeypatch.setattr(config, "APPROACH_OFFSET_FULL_M", 0.025)
    monkeypatch.setattr(config, "APPROACH_OFFSET_FREE_M", 0.008)
    frei = noise.approach_tip_clearance(_ideal(), _bahn(np.array([0.02, 0.0, 0.0, 0.0])), PRUEF)
    assert frei < 0.0
