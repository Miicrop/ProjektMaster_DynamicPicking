"""Feste Hindernisse der Zelle und Vorabpruefung der Ziele (Analyse 2026-11-11)."""

import _paths  # noqa: F401

import numpy as np

import _fixtures
from bc import obstacles
from bc.collision import CollisionModel, default_workspace
from bc.obstacles import BaseCylinder, CellObstacles, Envelope, ObstacleBox
from bc.safety import TargetRejected, check_target


def _nah(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def test_cell_file_loads_and_applies_only_at_the_real_plant():
    cell = obstacles.load()
    assert cell is not None, "einstellungen/hindernisse.json fehlt"
    names = {s.name for s in cell.surfaces}
    assert {"Kamerastange", "Teststation"} <= names
    assert abs(np.linalg.norm(cell.camera_offset_tool) - 0.054) < 0.005
    # VM und SimRobot haben andere Koordinaten -> dort nicht (auto)
    assert obstacles.applies("neura", False)
    assert not obstacles.applies("neura", True)
    assert not obstacles.applies("sim", True)
    assert obstacles.applies("sim", True, "an") and not obstacles.applies("neura", False, "aus")


def test_box_rules_per_support_point():
    stange = ObstacleBox("Stange", (0.0, 0.0, None), (0.03, 0.03, None),
                         {"camera": 0.02, "tool": 0.05})
    # nur genannte Stuetzpunkte werden geprueft
    assert stange.clearance_for("elbow", (0.1, 0.0, 0.0), 0.09) is None
    # senkrecht unbegrenzt: Hoehe egal
    assert _nah(stange.clearance_for("camera", (0.06, 0.01, 2.0), 0.0), 0.01)
    assert _nah(stange.clearance_for("tool", (0.06, 0.01, -1.0), 0.0), -0.02)
    station = ObstacleBox("Station", (0, 0, -0.05), (0.2, 0.1, 0.066), {"tool": 0.012})
    assert _nah(station.clearance_for("tool", (0.1, 0.05, 0.136), 0.0), 0.058)
    assert station.clearance_for("tool", (0.1, 0.05, 0.070), 0.0) < 0     # zu tief ueber der Station


def test_base_cylinder_and_envelope():
    basis = BaseCylinder("Basis", {"tool": 0.15, "camera": 0.105})
    assert _nah(basis.clearance_for("tool", (0.158, 0.0, 0.2), 0.0), 0.008)
    assert basis.clearance_for("camera", (0.10, 0.0, 0.2), 0.0) < 0
    huelle = obstacles.envelope_from_points([[0, 0, 0], [0.4, 0.2, 0.3]], margin=0.03)
    assert huelle.clearance_for("tool", (0.2, 0.1, 0.1), 0.0) > 0
    assert huelle.clearance_for("tool", (0.2, 0.1, 0.35), 0.0) < 0          # 2 cm ueber der Huelle
    assert huelle.clearance_for("wrist", (5, 5, 5), 0.0) is None


def test_camera_point_sits_beside_the_tool():
    # Werkzeug senkrecht nach unten (180 Grad um x): Werkzeug-y zeigt nach -y
    pose = [0.3, 0.0, 0.1, 0.0, 1.0, 0.0, 0.0]
    cam = obstacles.camera_point(pose, (0.0, 0.054, 0.0))
    assert np.allclose(cam, [0.3, -0.054, 0.1], atol=1e-9)


def _robot_with_obstacle(where):
    robot = _fixtures.make_robot("sim")
    joints = robot.read_state().joints
    tool = np.asarray(robot.link_positions(joints)["tool"])
    model = default_workspace(table_height_m=float(tool[2]) - 0.5)
    lo = tool + np.asarray(where) - 0.01
    model.add_obstacles(CellObstacles(
        [ObstacleBox("Testklotz", lo, lo + 0.02, {"tool": 0.01, "camera": 0.0})],
        camera_offset_tool=(0.0, 0.054, 0.0)))
    return robot, joints, model


def test_check_target_rejects_before_sending():
    robot, joints, model = _robot_with_obstacle(where=(0.0, 0.0, 0.0))   # Klotz am TCP
    try:
        check_target(model, robot, joints)
        assert False, "TargetRejected erwartet"
    except TargetRejected as exc:
        assert "Testklotz" in str(exc)
    robot, joints, model = _robot_with_obstacle(where=(0.0, 0.0, 0.3))   # weit weg
    check_target(model, robot, joints)
    # Kamera-Stuetzpunkt wird mitgerechnet, auch in der Pfadpruefung (Aufnahme)
    assert "camera" in model.positions_for(robot, joints)
    assert model.check_path(robot, [joints]) == []


def test_model_without_obstacles_has_no_camera_point():
    robot = _fixtures.make_robot("sim")
    joints = robot.read_state().joints
    model = CollisionModel()
    assert "camera" not in model.positions_for(robot, joints)
