"""Griffpruefung (bc/known_pose.grasp_check, Anwender 2026-11-25)."""

import _paths  # noqa: F401

import numpy as np

from bc import config, known_pose
from bc.table import fit_table


def _down(x, y, z, yaw_deg=0.0):
    t = np.radians(yaw_deg) / 2.0
    return np.array([x, y, z, 0.0, np.cos(t), np.sin(t), 0.0])


def _known(yaw=30.0):
    plane = fit_table([[x, y, 0.0, 0, 1, 0, 0] for x in (0.2, 0.6) for y in (-0.3, 0.1)])
    pick = _down(0.4, -0.1, 0.009, yaw)
    return known_pose.KnownPose(pick, plane, np.array([[0.4, -0.1, 0.1], [0.4, -0.1, 0.009]]),
                                "Test")


def test_clearance_centered_is_half_the_play():
    plus, minus = known_pose.jaw_clearance(0.0, 0.0, 0.0)
    assert abs(plus - 0.00245) < 1e-9 and abs(minus - 0.00245) < 1e-9


def test_rotation_limit_about_14_degrees_when_centered():
    assert min(known_pose.jaw_clearance(0.0, 0.0, 13.5)) > 0
    assert min(known_pose.jaw_clearance(0.0, 0.0, 14.5)) < 0
    assert min(known_pose.jaw_clearance(0.0, 0.0, -14.5)) < 0


def test_long_offset_in_object_frame_is_no_lever_but_cross_is():
    # Versatz im Objekt-KS: laengs aendert das Spiel bei Drehung nicht (der
    # Greifer dreht um seine Mitte, die auf der Mittellinie des Objekts liegt)
    for long_ in (0.0, 0.010, -0.015):
        assert min(known_pose.jaw_clearance(0.0, long_, 13.5)) > 0
        assert abs(min(known_pose.jaw_clearance(0.0, long_, 0.0)) - 0.00245) < 1e-9
    # 1 mm quer: Grenze ~9,4 statt ~13,9 Grad, in beide Drehrichtungen
    assert min(known_pose.jaw_clearance(0.001, 0.0, 8.0)) > 0
    assert min(known_pose.jaw_clearance(0.001, 0.0, 9.5)) < 0
    assert min(known_pose.jaw_clearance(0.001, 0.0, -9.5)) < 0


def test_cross_offset_hits_a_jaw():
    plus, minus = known_pose.jaw_clearance(0.003, 0.0, 0.0)
    assert minus < 0 < plus      # Greifer nach +quer: die Backe auf -quer setzt auf
    assert known_pose.jaw_clearance(0.0, 0.040, 0.0) == (None, None)   # Backen daneben


def _shifted(known, cross, long_, yaw=0.0, dz=0.0):
    phi = np.radians(known_pose.jaw_axis_deg(known.pick, known.table))
    d = cross * np.array([np.cos(phi), np.sin(phi)]) + long_ * np.array([-np.sin(phi), np.cos(phi)])
    return _down(known.pick[0] + d[0], known.pick[1] + d[1], known.pick[2] + dz, 30.0 + yaw)


def test_grasp_check_levels_in_object_frame():
    known = _known()
    assert abs(known_pose.jaw_axis_deg(known.pick, known.table)
               - (30.0 + config.GRASP_JAW_AXIS_FROM_TOOL_X_DEG)) < 1e-6
    ok = known_pose.grasp_check(_shifted(known, 0.001, 0.002), known)
    assert ok["stufe"] == known_pose.GRASP_OK
    assert abs(ok["quer_m"] - 0.001) < 1e-9 and abs(ok["laengs_m"] - 0.002) < 1e-9
    warn = known_pose.grasp_check(_shifted(known, 0.0, 0.010), known)
    assert warn["stufe"] == known_pose.GRASP_WARN and "laengs" in warn["gruende"][0]
    # 2,2 mm quer: geometrisch frei (2,45), aber unter dem Sicherheitsabzug -> knapp
    tight = known_pose.grasp_check(_shifted(known, 0.0022, 0.0), known)
    assert tight["stufe"] == known_pose.GRASP_WARN and "knapp" in tight["gruende"][0]
    hit = known_pose.grasp_check(_shifted(known, 0.0026, 0.0), known)
    assert hit["stufe"] == known_pose.GRASP_FAIL
    turned = known_pose.grasp_check(_shifted(known, 0.001, 0.010, yaw=9.5), known)
    assert turned["stufe"] == known_pose.GRASP_FAIL
    high = known_pose.grasp_check(_shifted(known, 0.0, 0.0, dz=0.008), known)
    assert high["stufe"] == known_pose.GRASP_WARN
    # 180 Grad gedreht greift der Parallelgreifer gleich
    flipped = known_pose.grasp_check(_shifted(known, 0.001, 0.002, yaw=180.0), known)
    assert flipped["stufe"] == known_pose.GRASP_OK


def test_summarize_checks_grasp_then_prediction():
    known = _known()
    tcp = np.array([_down(0.4, -0.1, 0.05, 30.0), _shifted(known, 0.0, 0.010)])
    rows = known_pose.track(tcp, known)
    s = known_pose.summarize(rows, known, grasp_step=1, tcp=tcp)
    assert s["grasp_check"]["quelle"] == "griff"
    assert s["grasp_check"]["stufe"] == known_pose.GRASP_WARN
    predicted = {"pose": list(_shifted(known, 0.004, 0.0)), "xy_m": 0.004}
    s = known_pose.summarize(rows, known, predicted=predicted, tcp=tcp)
    assert s["grasp_check"]["quelle"] == "vorhersage"
    assert s["grasp_check"]["stufe"] == known_pose.GRASP_FAIL
    assert "kein Erfolg" in known_pose.check_line(s["grasp_check"], "vorhersage")


def test_comparison_shows_level():
    from bc.gui import vergleich as v
    row = {"erfolg": True, "bewertung": "warnung"}
    assert v.result_text(row) == "Erfolg mit Warnung"
    assert v.result_text({"erfolg": True}) == "Erfolg"
    assert v.result_text({"erfolg": False, "bewertung": "kein_erfolg"}) == "kein Erfolg"
    assert [v.clearance_level(x) for x in (None, -0.1, 0.0, 0.3, 0.5, 2.45)] == [
        None, "schlecht", "knapp", "knapp", "gut", "gut"]
