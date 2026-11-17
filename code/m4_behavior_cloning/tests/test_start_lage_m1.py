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
