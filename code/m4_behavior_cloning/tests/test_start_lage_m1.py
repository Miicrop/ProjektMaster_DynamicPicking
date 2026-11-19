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
