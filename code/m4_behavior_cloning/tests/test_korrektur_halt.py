"""Korrektur-Halt als Idealbahn (bc/korrektur_halt.py, record.py --korrektur-halt, Sim-Versuch V7)."""
import numpy as np

from bc import korrektur_halt as kh_mod
from bc.trajectory import Waypoint, build_ideal_trajectory

Q = [0.0, 0.0, 0.0, 1.0]


def _wp(z, **kw):
    return Waypoint(np.array([0.3, 0.0, z] + Q, dtype=float), **kw)


def _bahn():
    return [_wp(0.20), _wp(0.05, blend_m=0.01), _wp(0.0, approach=True, gripper_closed=True),
            _wp(0.05, gripper_closed=True, blend_m=0.04)]


def _ideal(korr, cfg):
    return build_ideal_trajectory(kh_mod.waypoints_mit_halt(_bahn(), korr, cfg))


def test_ohne_anteil_keine_korrektur():
    cfg = kh_mod.KorrekturHalt(share=0.0)
    rng = np.random.default_rng(0)
    assert all(kh_mod.sample(rng, cfg) is None for _ in range(50))


def test_l_bahn_sicher_und_ohne_stillstand():
    cfg = kh_mod.KorrekturHalt()
    pick = _bahn()[2].pose_quat
    for korr in ((0.02, 0.0, np.radians(20.0)), (0.0, -0.01, 0.0), (0.012, 0.012, np.radians(-15.0))):
        ideal = _ideal(korr, cfg)
        k = kh_mod.grasp_index(ideal)
        assert abs(ideal.poses_quat[k, 2] - pick[2]) < 1e-9          # greift am PICK
        assert kh_mod.clearance(ideal.poses_quat, pick, k, cfg) >= 0.0
        p = ideal.poses_quat[:k + 1]
        lat = np.linalg.norm(p[:, :2] - pick[:2], axis=1)
        h = p[:, 2] - pick[2]
        # unter der Haltehoehe hoechstens der kleine Ueberschleif-Rest daneben
        assert np.all(lat[h < cfg.hold_m - 1e-4] <= cfg.blend_halt_m + 1e-4)
        # mit grossem Versatz nie unter die Haltehoehe
        assert np.all(h[lat > 0.003] >= cfg.hold_m - 1e-4)
        # kein Stillstand zwischen Abstieg und Griff (ausser am Ende beim Bremsen)
        v = np.linalg.norm(np.diff(p[:, :3], axis=0), axis=1) * ideal.rate_hz
        i_hold = int(np.flatnonzero(h <= cfg.hold_m + 0.002)[0])
        assert v[i_hold:k - 3].min() > 0.002


def test_label_folgt_der_korrektur():
    """Die Idealbahn (= Label) faehrt erst seitlich, dann senkrecht -- nicht schraeg."""
    cfg = kh_mod.KorrekturHalt()
    pick = _bahn()[2].pose_quat
    ideal = _ideal((0.015, 0.0, 0.0), cfg)
    k = kh_mod.grasp_index(ideal)
    p = ideal.poses_quat[:k + 1]
    h = p[:, 2] - pick[2]
    unten = h < cfg.hold_m - 0.001
    assert np.all(np.abs(p[unten, 0] - pick[0]) < cfg.blend_halt_m + 1e-4)
    oben = h > cfg.hold_m + 0.003
    assert np.median(np.abs(p[oben, 0] - pick[0])[-5:]) > 0.014


def test_pruefung_meldet_zu_tiefen_versatz():
    cfg = kh_mod.KorrekturHalt()
    pick = _bahn()[2].pose_quat
    ideal = build_ideal_trajectory(_bahn())
    k = kh_mod.grasp_index(ideal)
    schief = ideal.poses_quat.copy()
    schief[:k, 0] += 0.01                                            # 10 mm daneben bis kurz vor dem Griff
    assert kh_mod.clearance(schief, pick, k, cfg) < 0.0
    assert kh_mod.path_check(ideal, pick, cfg)(schief)
    assert kh_mod.path_check(ideal, pick, cfg)(ideal.poses_quat) is None
