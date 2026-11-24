"""Zweistufiger Endanflug (bc/trajectory.py, record.py --anflug-zweistufig, Sim-Versuch V3b)."""
import numpy as np

from bc.trajectory import Waypoint, build_ideal_trajectory

Q = [0.0, 0.0, 0.0, 1.0]


def _wp(z, **kw):
    return Waypoint(np.array([0.3, 0.0, z] + Q, dtype=float), **kw)


def _pick_bahn():
    return [_wp(0.10), _wp(0.05, blend_m=0.01), _wp(0.0, approach=True, gripper_closed=True),
            _wp(0.05, blend_m=0.04)]


def _anflug(ideal):
    z = ideal.poses_quat[:, 2]
    close = int(np.flatnonzero(np.diff(ideal.gripper) != 0)[0])
    i0 = int(np.flatnonzero(z < 0.05 - 1e-6)[0])
    return z[i0:close + 1], -np.diff(z[i0 - 1:close + 1]) * ideal.rate_hz


def test_standard_unveraendert():
    ref = build_ideal_trajectory(_pick_bahn())
    for kw in ({"approach_fast_speed": 0.05, "approach_slow_m": 0.0},
               {"approach_fast_speed": None, "approach_slow_m": 0.02},
               {"approach_fast_speed": 0.01, "approach_slow_m": 0.02}):   # nicht schneller
        other = build_ideal_trajectory(_pick_bahn(), **kw)
        assert np.allclose(ref.poses_quat, other.poses_quat)
        assert ref.blend_applied == other.blend_applied


def test_zweistufig_schnell_dann_langsam_ohne_halt():
    ref = build_ideal_trajectory(_pick_bahn())
    two = build_ideal_trajectory(_pick_bahn(), approach_fast_speed=0.05, approach_slow_m=0.02)
    z, v = _anflug(two)
    assert len(two) < len(ref)                       # kuerzer als einstufig 0,02 m/s
    assert v.max() > 0.045                          # schneller Teil erreicht ~0,05 m/s
    k_max = int(np.argmax(v))
    k_slow = k_max + int(np.flatnonzero(v[k_max:] <= 0.0205)[0])
    # vom Hoechstwert bis 0,02 m/s faellt das Tempo, ohne darunter zu sacken
    assert np.all(np.diff(v[k_max:k_slow + 1]) <= 1e-6)
    zs = z[min(k_slow, len(z) - 1)]
    assert 0.018 <= zs <= 0.024                      # langsam ab ~20 mm ueber dem Griff
    # danach bis zum Bremsen konstant 0,02 m/s (+-1 mm/s)
    cruise = v[k_slow:][v[k_slow:] > 0.0185]
    assert len(cruise) >= 8 and np.all(np.abs(cruise - 0.02) < 0.0015)
    assert abs(two.poses_quat[np.flatnonzero(np.diff(two.gripper) != 0)[0], 2]) < 1e-9


def test_zu_kurzer_anflug_bleibt_einstufig():
    bahn = [_wp(0.10), _wp(0.03), _wp(0.0, approach=True, gripper_closed=True)]
    ref = build_ideal_trajectory(bahn)
    two = build_ideal_trajectory(bahn, approach_fast_speed=0.05, approach_slow_m=0.02)
    assert np.allclose(ref.poses_quat, two.poses_quat)
