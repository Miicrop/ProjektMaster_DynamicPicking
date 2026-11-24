"""Keine PTP-Fahrt aus tiefer Stellung (Befund 2026-11-24, Crash mit dem Objekt).

Der Rueckzug hing ~10 mm ueber dem Objekt; der naechste Lauf fuhr per
move_to_joints direkt zur Startstellung -- eine Gelenkfahrt hebt nicht erst an.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import _paths  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

import numpy as np

from bc import config


class _Robot(object):
    def __init__(self, z):
        self.z, self.moved = z, []

    def read_state(self):
        return SimpleNamespace(tcp_quat=np.array([0.4, -0.2, self.z, 1, 0, 0, 0]))

    def move_to_joints(self, joints):
        self.moved.append(joints)


def test_ptp_from_low_above_the_object_is_refused():
    import infer

    grasp_z = 0.008
    low = _Robot(grasp_z + 0.010)                  # wie 14:00:29, ~10 mm ueber dem Griff
    assert infer.ptp_height_problem(low, grasp_z) is not None
    assert infer.move_to_joints_checked(low, np.zeros(6), grasp_z, "Test") is False
    assert low.moved == []
    high = _Robot(grasp_z + config.PTP_MIN_ABOVE_GRASP_M + 0.01)
    assert infer.move_to_joints_checked(high, np.zeros(6), grasp_z, "Test") is True
    assert len(high.moved) == 1
    # ohne bekannte Greifhoehe wie bisher
    assert infer.ptp_height_problem(low, None) is None


def test_grasp_height_prefers_the_known_pick():
    import infer

    known = SimpleNamespace(pick=[0.44, -0.18, 0.008, 1, 0, 0, 0])
    assert infer.grasp_height({"ideal_z_min": 0.02}, known) == 0.008
    assert infer.grasp_height({"ideal_z_min": 0.02}) == 0.02
    assert infer.grasp_height({}) is None
