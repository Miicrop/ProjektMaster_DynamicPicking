"""Nachlauf-Pruefung der Ziele (bc/safety.check_target, Anlage 2026-11-17)."""

import numpy as np
import pytest

from bc.safety import TargetRejected, check_target


class _Plane(object):
    """Ebene z = 0.02 nur fuer den Stuetzpunkt 'tool' (wie table.TableSurface)."""
    margin = 0.0
    name = "Ebene"


class _Model(object):
    def positions_for(self, robot, joints):
        return {"tool": np.array([0.0, 0.0, float(joints[0])])}

    def check_positions(self, positions):
        z = positions["tool"][2]
        return [] if z >= 0.02 else [type("V", (), {"frame": "tool", "box": "Ebene",
                                                     "clearance": z - 0.02})()]


def test_target_above_plane_passes_without_lookahead():
    check_target(_Model(), None, [0.025], previous=[0.035], lookahead=0.0)


def test_lookahead_rejects_fast_descent_before_the_plane():
    # Ziel 5 mm ueber der Ebene, Schritt 10 mm abwaerts: verlaengert 5 mm darunter
    with pytest.raises(TargetRejected, match="Nachlauf"):
        check_target(_Model(), None, [0.025], previous=[0.035], lookahead=1.0)


def test_lookahead_lets_slow_descent_pass():
    check_target(_Model(), None, [0.025], previous=[0.027], lookahead=1.0)
    check_target(_Model(), None, [0.025], previous=None, lookahead=1.0)
