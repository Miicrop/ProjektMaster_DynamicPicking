"""Watchdog und Geofencing (AP 4.2)."""

import _paths  # noqa: F401

import _fixtures
from bc.collision import default_workspace
from bc.safety import Watchdog, geofence_check


def test_watchdog_passes_when_free():
    robot = _fixtures.make_robot("sim")
    joints = robot.read_state().joints
    tool_z = float(robot.link_positions(joints)["tool"][2])
    workspace = default_workspace(table_height_m=tool_z - 0.5)

    dog = Watchdog(robot, [geofence_check(robot, workspace)], robot._clock)
    assert dog.run_once() is None
    assert not robot.stop_requested


def test_watchdog_trips_on_violation():
    robot = _fixtures.make_robot("sim")
    joints = robot.read_state().joints
    tool_z = float(robot.link_positions(joints)["tool"][2])
    # Tisch auf Werkzeughoehe -> sofortige Verletzung
    workspace = default_workspace(table_height_m=tool_z + 0.01)

    dog = Watchdog(robot, [geofence_check(robot, workspace)], robot._clock)
    violation = dog.run_once()
    assert violation
    assert robot.stop_requested
    assert dog.tripped == violation
    # Not-Halt hat das Servo-Interface deaktiviert
    assert not robot._servo_active


def test_broken_check_counts_as_violation():
    # Ein kaputter Waechter darf NIE "gruen" bedeuten
    robot = _fixtures.make_robot("sim")

    def broken():
        raise RuntimeError("Sensor weg")

    dog = Watchdog(robot, [broken], robot._clock)
    violation = dog.run_once()
    assert violation and "Sensor weg" in str(violation)
    assert robot.stop_requested


def test_frame_age_guard_needs_consecutive_stale_steps():
    """Eingefrorenes Bild (Anwender 2026-11-11): erst nach INFER_FRAME_AGE_STEPS
    Takten in Folge ueber INFER_MAX_FRAME_AGE_S anhalten, ein einzelnes
    verspaetetes Bild bricht nichts ab."""
    from bc.ports import Frame
    from bc.safety import CameraStale, FrameAgeGuard

    guard = FrameAgeGuard(max_age_s=0.1, max_steps=2)
    frisch = Frame(None, 10.0, 0, "wrist")
    alt = Frame(None, 9.8, 0, "scene")
    assert guard.check({"wrist": frisch, "scene": frisch}, 10.01) < 0.1
    guard.check({"wrist": frisch, "scene": alt}, 10.0)          # 1. schlechter Takt
    guard.check({"wrist": frisch, "scene": frisch}, 10.02)      # wieder gut -> Zaehler 0
    guard.check({"wrist": frisch, "scene": alt}, 10.0)
    try:
        guard.check({"wrist": frisch, "scene": alt}, 10.07)
        assert False, "CameraStale erwartet"
    except CameraStale as exc:
        assert "scene" in str(exc)
    # nie geliefert zaehlt als eingefroren
    guard = FrameAgeGuard(max_age_s=0.1, max_steps=1)
    try:
        guard.check({"wrist": None}, 10.0)
        assert False, "CameraStale erwartet"
    except CameraStale as exc:
        assert "nie geliefert" in str(exc)
