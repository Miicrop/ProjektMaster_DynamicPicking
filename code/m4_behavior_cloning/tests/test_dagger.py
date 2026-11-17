"""DAgger-Mitschrieb, Labels, Violation-Stopp und PICK aus M1 (2026-11-16)."""

import json
import sys
from pathlib import Path

import _paths  # noqa: F401

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from bc import config, dagger, dataset, known_pose  # noqa: E402

# Stoppgruende vom Anlagentag 2026-11-16 (12-50-59 / 12-52-08)
VIOLATION_16_11 = ("stopp: [Violation(Schritt None, Frame 'tool', Quader 'Tischebene', "
                   "Freiraum -0.0031 m, Position [0.5091, -0.139, 0.0142])]")


def _ideal(m=40):
    """Gerade senkrechte Idealbahn: z 0.10 -> 0.01, Gelenk 1 laeuft mit."""
    from bc.trajectory import IdealTrajectory

    poses = np.zeros((m, 7))
    poses[:, 2] = np.linspace(0.10, 0.01, m)
    poses[:, 3] = 1.0
    grip = np.zeros(m)
    grip[m - 5:] = 1.0
    q = np.zeros((m, 6))
    q[:, 1] = np.linspace(0.0, 0.3, m)
    ideal = IdealTrajectory(poses_quat=poses, gripper=grip, dwell_mask=np.zeros(m, bool),
                            dist_to_anchor=np.zeros(m))
    return ideal, q


def test_relabel_pulls_back_to_the_path_without_jumping():
    ideal, q = _ideal()
    tcp = np.array([[0.02, 0.0, 0.05]])            # 20 mm neben der Bahn, halbe Hoehe
    joints = np.array([[0.1, 0.15, 0.0, 0.0, 0.0, 0.0]])
    lab = dagger.relabel(joints, tcp, q, ideal.poses_quat, ideal.gripper)
    k = int(lab["index"][0])
    assert ideal.poses_quat[k, 2] < 0.05 + 0.01      # naechster Punkt auf der Bahn
    step = np.abs(lab["action"][0, :6] - joints[0])
    assert step.max() <= np.abs(q[k] - q[k - 1]).max() + config.DAGGER_EXTRA_STEP_RAD + 1e-6
    assert lab["action"][0, 0] < joints[0, 0]        # Gelenk 0 zurueck Richtung Bahn
    assert lab["offset_m"][0] == pytest.approx(0.02, abs=2e-3)
    assert lab["action"][0, 6] == 0.0                 # noch offen


def test_relabel_is_monotonic_and_closes_at_the_end():
    ideal, q = _ideal()
    tcp = ideal.poses_quat[[5, 30, 10, 38], :3]      # zurueckgefallen in Takt 3
    lab = dagger.relabel(q[[5, 30, 10, 38]], tcp, q, ideal.poses_quat, ideal.gripper)
    assert list(lab["index"]) == sorted(lab["index"])
    assert lab["action"][-1, 6] == 1.0


def _mitschrieb(n_pol=6, n_exp=30, cams=("wrist", "scene")):
    rec = dagger.Mitschrieb(cams)
    for i in range(n_pol + n_exp):
        state = dataset.build_state(np.full(6, 0.01 * i), [0, 0, 0.1 - 0.001 * i, 1, 0, 0, 0], 0.0)
        obs = {"observation.state": state}
        for c in cams:
            obs["observation.images.%s" % c] = np.full((config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3),
                                                       i, dtype=np.uint8)
        phase = dagger.POLICY if i < n_pol else dagger.EXPERT
        grip = 1.0 if i >= n_pol + 8 else 0.0
        rec.add(obs, np.full(6, 0.01 * (i + 1)), grip, phase, policy_action=np.zeros(7))
    return rec


def test_episode_matches_the_recording_schema_and_ends_after_the_grasp():
    ideal, q = _ideal()
    rec = _mitschrieb()
    ep, info = dagger.build_episode(rec, ideal, q, metadata={"robot": "sim"}, success=True)
    ep.validate(("wrist", "scene"))
    assert info["policy_steps"] == 6
    # Experte: Schliessen in Experten-Takt 8, danach DAGGER_TAIL_STEPS
    assert info["expert_steps"] == 8 + config.DAGGER_TAIL_STEPS + 1
    assert ep.arrays["next.done"][-1, 0] and not ep.arrays["next.done"][:-1].any()
    assert ep.metadata["mode"] == "dagger" and ep.metadata["dagger"]["policy_steps"] == 6
    # Experten-Label = Ziel des naechsten Takts (wie die Aufnahme)
    assert np.allclose(ep.arrays["action"][6, :6], rec.sent[7])
    # Bilder in der richtigen Reihenfolge
    assert ep.arrays["observation.images.wrist"][7, 0, 0, 0] == 7
    json.dumps(ep.metadata)


def test_probe_violation_of_the_plant_counts_as_probe_stop():
    import infer

    assert infer.probe_violation(VIOLATION_16_11)
    assert infer.expected_test_stop(VIOLATION_16_11, "objekt")
    assert not infer.expected_test_stop(VIOLATION_16_11)           # echter Griff: nein
    deep = VIOLATION_16_11.replace("-0.0031", "-0.0150")
    assert not infer.probe_violation(deep)
    other = VIOLATION_16_11.replace("'Tischebene'", "'Sperrzone IGNORE'")
    assert not infer.probe_violation(other)
    wrist = VIOLATION_16_11.replace("Frame 'tool'", "Frame 'wrist'")
    assert not infer.probe_violation(wrist)
    two = VIOLATION_16_11[:-1] + ", " + wrist[7:]
    assert not infer.probe_violation(two)
    assert not infer.probe_violation("kollision vorab: tool an Tischebene (Rest -0 mm)")


def test_expert_lifts_first_after_a_violation_stop():
    from bc.table import fit_table

    plane = fit_table([[x, y, 0.0, 1, 0, 0, 0] for x in (0.3, 0.6) for y in (-0.3, 0.0)])
    pick = np.array([0.45, -0.15, 0.007, 0.0, 1.0, 0.0, 0.0])
    known = known_pose.KnownPose(pick, plane, np.zeros((2, 3)))
    stop = pick.copy()
    stop[0] += 0.006
    stop[2] = pick[2] + 0.006                  # unter der Probehoehe (PICK + 10 mm)
    above, grasp, info = known_pose.correction(known, stop)
    probe_z = pick[2] + config.PROBE_OBJECT_TOP_ABOVE_PICK_M + config.PROBE_GAP_M
    assert above[2] == pytest.approx(probe_z)
    wps = known_pose.expert_waypoints(stop, None, above, grasp, grasp, np.zeros(6), 0.05,
                                      np.zeros(6), np.zeros(6), grasp)
    names = [w.name for w in wps]
    assert names[:3] == ["STOPP", "FREI", "KORREKTUR"]
    assert wps[1].pose_quat[0] == pytest.approx(stop[0])          # senkrecht
    assert wps[1].pose_quat[2] == pytest.approx(probe_z)
    # normaler Stopp (ueber der Probehoehe): kein Zwischenpunkt
    stop[2] = probe_z + 0.010
    above, grasp, _ = known_pose.correction(known, stop)
    wps = known_pose.expert_waypoints(stop, None, above, grasp, grasp, np.zeros(6), 0.05,
                                      np.zeros(6), np.zeros(6), grasp)
    assert [w.name for w in wps][:2] == ["STOPP", "KORREKTUR"]


def test_dagger_series_in_the_simulation_writes_exportable_episodes(tmp_path):
    from test_auto_layout import _points
    from test_known_pose import _run_infer

    from bc import lerobot_io

    points, _probe = _points(size=0.12)
    folder = tmp_path / "dagger"
    error, log, _ = _run_infer(tmp_path, ["--episodes", "2", "--probegriff", "objekt",
                                          "--dagger", str(folder)], points)
    assert error is None, log[-4000:]
    assert log.count("   DAgger: Episode") == 2, log[-4000:]
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    assert len(index["episodes"]) == 2
    for k in range(2):
        ep = dataset.load_episode(folder, k)
        ep.validate(index["cameras"])
        assert ep.metadata["mode"] == "dagger" and ep.success is True
        assert ep.metadata["dagger"]["expert_steps"] > 10
        assert ep.metadata["repeat_group"].startswith("dagger/")
        assert ep.arrays["action"][:, 6].max() == 1.0          # der Experte schliesst
    scan = lerobot_io.scan_sources([folder])
    assert len(scan["episodes"]) == 2 and not scan["conflicts"]
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert all(e["dagger"]["geschrieben"] for e in summary["episodes"])


def test_pick_from_m1_is_written_to_the_controller(tmp_path, monkeypatch):
    import infer
    from test_auto_layout import _points
    from test_known_pose import _run_infer

    from bc import lokalisierung
    from bc.table import yaw_deg

    points, probe = _points(size=0.12)
    taught = probe.fk(points["PICK"])
    seen = []

    class FakeM1(object):
        def locate(self, image):
            seen.append(None if image is None else image.shape)
            return lokalisierung.Localization(
                x_m=float(taught[0]) + 0.02, y_m=float(taught[1]) - 0.01, theta_deg=0.0,
                gripper_yaw_deg=(yaw_deg(taught) + 10.0) % 180.0, chamfer=True)

    monkeypatch.setattr(infer, "make_localizer", lambda: FakeM1())
    error, log, opened = _run_infer(tmp_path, ["--episodes", "1", "--probegriff", "objekt",
                                               "--pick-quelle", "m1", "--foto-punkt", "CLEAR_FOV"],
                                    points)
    assert error is None, log[-4000:]
    assert seen and "Lokalisierung: PICK gesetzt" in log
    robot = opened[-1]
    pick = robot.fk(robot._points["PICK"])
    assert pick[0] == pytest.approx(taught[0] + 0.02, abs=1e-3)
    assert pick[1] == pytest.approx(taught[1] - 0.01, abs=1e-3)
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    lok = summary["episodes"][0]["lokalisierung"]
    assert lok["gegen_vorher"]["xy_m"] == pytest.approx(np.hypot(0.02, 0.01), abs=1e-3)
    assert abs(lok["gegen_vorher"]["yaw_deg"]) == pytest.approx(10.0, abs=0.5)


def test_m1_failure_stops_the_series_before_moving(tmp_path, monkeypatch):
    import infer
    from test_auto_layout import _points
    from test_known_pose import _run_infer

    from bc import lokalisierung

    class NoMarkers(object):
        def locate(self, image):
            raise lokalisierung.LocalizationError("M1: ArUco markers not found -- Arm im Bild?")

    points, _ = _points(size=0.12)
    monkeypatch.setattr(infer, "make_localizer", lambda: NoMarkers())
    error, log, _ = _run_infer(tmp_path, ["--episodes", "2", "--probegriff", "objekt",
                                          "--pick-quelle", "m1", "--foto-punkt", "CLEAR_FOV"],
                               points)
    assert error is None, log[-3000:]
    assert "Lokalisierung gescheitert" in log and "Fahrt 0:" not in log.split("gescheitert")[1]
