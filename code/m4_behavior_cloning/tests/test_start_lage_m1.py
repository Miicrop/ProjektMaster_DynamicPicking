"""--start-lage m1 (Anwender 2026-11-17): Handlage per M1, erster Griff unaufgezeichnet."""

import numpy as np

from bc import config
from bc.gui import recording
from bc.probe import slowed_plan
from bc.noise import TrajectoryPlan


def _plan(n=20):
    joints = np.linspace(0, 1, n)[:, None] * np.ones((1, 6))
    poses = np.zeros((n, 7))
    poses[:, 3] = 1.0
    grip = np.full(n, config.GRIPPER_OPEN)
    grip[12:] = config.GRIPPER_CLOSED
    return TrajectoryPlan(joints_ideal=joints, joints_noisy=joints.copy(), poses_ideal=poses,
                          poses_noisy=poses.copy(), gripper=grip, dwell_mask=np.zeros(n, bool),
                          rate_hz=15.0)


def test_first_grasp_keeps_the_gripper_closing():
    slow = slowed_plan(_plan(), 0.5, keep_gripper=True)
    assert len(slow) > 20
    assert slow.gripper[0] == config.GRIPPER_OPEN
    assert slow.gripper[-1] == config.GRIPPER_CLOSED


def test_probe_drive_still_opens_the_gripper():
    slow = slowed_plan(_plan(), 0.5)
    assert np.all(slow.gripper == config.GRIPPER_OPEN)


def test_gui_passes_start_lage_m1_and_reads_the_question():
    argv = recording.record_argv("data/x", robot_kind="neura", sequence="seq.json",
                                 start_lage="m1")
    assert argv[argv.index("--start-lage") + 1] == "m1"
    assert recording.first_grasp_question(
        "ERSTER_GRIFF x 412 y -80 -> x 300 y -150 -- Handlage (M1)") == (412, -80, 300, -150)
    assert recording.first_grasp_question("LAGEVORSCHLAG x 1 y 2 Drehung 3") is None


def test_gui_passes_start_lage_pick():
    """Anwender 2026-11-19: Teil am geteachten PICK holen und umlegen (ohne M1)."""
    argv = recording.record_argv("data/x", robot_kind="neura", sequence="seq.json",
                                 start_lage="pick")
    assert argv[argv.index("--start-lage") + 1] == "pick"


def test_put_back_aligns_small_lag_and_refuses_large(monkeypatch):
    """Anlage 2026-11-19: 0,0154 rad Nachlauf brach das Zuruecklegen ab."""
    import sys
    from types import SimpleNamespace

    import pytest

    sys.path.insert(0, "apps")
    import record
    from bc.ports import RobotError

    class Robot(object):
        def __init__(self, joints):
            self.joints = np.asarray(joints, dtype=float)
            self.moves = []

        def read_state(self):
            return SimpleNamespace(joints=self.joints)

        def move_to_joints(self, q):
            self.moves.append(np.asarray(q))
            self.joints = np.asarray(q, dtype=float)

    plan = _plan()
    start = plan.joints_noisy[0]
    exact = Robot(start)
    record.align_to_plan(exact, plan)
    assert exact.moves == []
    lag = Robot(start + 0.0154)
    record.align_to_plan(lag, plan)
    assert len(lag.moves) == 1 and np.allclose(lag.joints, start)
    far = Robot(start + 0.3)
    with pytest.raises(RobotError):
        record.align_to_plan(far, plan)
    assert far.moves == []


def test_coverage_counts_only_chosen_folders(tmp_path):
    """Anwender 2026-11-19: Abdeckung ueber gewaehlte Aufnahmeordner statt alle Tage."""
    root = tmp_path / "data_vm"
    for name, eps in (("2026-11-09", 2), ("2026-11-19", 3), ("2026-11-20", 1)):
        (root / name).mkdir(parents=True)
        (root / name / "index.json").write_text("{}", encoding="utf-8")
        for k in range(eps):
            (root / name / ("ep_%05d" % k)).mkdir()
    (root / "kein_aufnahmeordner").mkdir()
    assert recording.coverage_folders(root) == [("2026-11-09", 2), ("2026-11-19", 3),
                                                ("2026-11-20", 1)]
    # ohne Auswahl: der ganze Datenordner (wie bisher)
    assert recording.coverage_roots(root, None) == [root]
    # Auswahl: nur diese Ordner, der Zielordner faellt weg (zaehlt ohnehin)
    roots = recording.coverage_roots(root, ["2026-11-19", "2026-11-20"],
                                     out=root / "2026-11-20")
    assert roots == [root / "2026-11-19"]
    argv = recording.record_argv("data_vm/2026-11-20", robot_kind="neura", sequence="seq.json",
                                 coverage_roots=["data_vm/2026-11-19"])
    assert argv[argv.index("--abdeckung") + 1] == "data_vm/2026-11-19"


def test_next_target_line_and_camera_arrow():
    """Anwender 2026-11-19: naechste Lage (lila X) und Kamerapfeile in der Abdeckung."""
    import math

    from bc.gui import coverage_map

    assert recording.next_target("NAECHSTE_LAGE x 420 y -60 Kamera 30") == (0.42, -0.06, 30.0)
    assert recording.next_target("Lage 2: x 410 mm") is None
    # Werkzeug-x in Welt +y (90 Grad): Kamera = 90 + LIVE_CAMERA_YAW_OFFSET_DEG
    h = math.radians(90.0) / 2
    pose = [0.4, 0.0, 0.01, math.cos(h), 0.0, 0.0, math.sin(h)]
    assert abs(coverage_map.camera_yaw(pose)
               - (90.0 + config.LIVE_CAMERA_YAW_OFFSET_DEG) % 360.0) < 1e-6
    assert coverage_map.camera_yaw(None) is None


def test_coverage_region_without_taught_episode_and_centered_on_start(tmp_path):
    """Anwender 2026-11-19: Grafik leer, wenn keine Episode 'geteacht' war;
    Drehabschnitte muessen um die Startstellung zaehlen wie record.py."""
    import json
    import math

    from bc.gui import coverage_map

    def quat(deg):
        h = math.radians(deg) / 2
        return [math.cos(h), 0.0, 0.0, math.sin(h)]

    folder = tmp_path / "data_vm" / "2026-11-20" / "ep_00000"
    folder.mkdir(parents=True)
    table = {"ID%d" % k: {"pose_quat": [0.3 + 0.1 * (k % 2), -0.2 + 0.1 * (k // 2), 0.0, 1, 0, 0, 0]}
             for k in range(4)}
    meta = {"discarded": False, "metadata": {
        "object_source": "vorgeschlagen", "object_xy_m": [0.35, -0.15], "object_yaw_deg": 150.0,
        "table_points": table, "recorded_at": "2026-11-20T10:00:00",
        "points": {"PICK": {"pose_quat": [0.35, -0.15, 0.01] + quat(150.0)},
                   config.AUTO_YAW_CENTER_POINT: {"pose_quat": [0.2, 0.0, 0.4] + quat(100.0)}}}}
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    spots, latest = coverage_map.load_episodes([tmp_path / "data_vm"])
    assert latest is not None                         # Bereich trotz "vorgeschlagen"
    region = coverage_map.region_from_meta(latest[1], latest[0])
    assert abs(region.center_shift_deg - (-50.0)) < 1e-6
    snap = coverage_map.build_snapshot(region, spots, yaw_range_deg=60)
    # die Lage liegt 50 Grad gegen den Start -> oberster Drehabschnitt
    assert snap.coverage.yaw_count[-1] == 1
