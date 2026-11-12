"""Replay einer Aufnahme: Kamera-Backend, Offline-Abgleich, Bahnvergleich."""

import sys
from pathlib import Path
from types import SimpleNamespace

import _paths  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

import numpy as np

import _fixtures
from bc import config, dataset, replay
from bc.adapters import replay_configs, start_cameras
from bc.clock import SimClock
from bc.policy import ChunkEnsembler, HoldPolicy, PolicyPort

N = 30
CLOSE_AT = 12


def _episode(n=N, offset=0.0):
    """Episode mit Bahn in J1, Greiferwechsel bei CLOSE_AT; im Bild steht der Takt."""
    t = np.arange(n, dtype=np.float32)
    joints = np.zeros((n, 6), dtype=np.float32)
    joints[:, 0] = 0.01 * t + offset
    gripper = (t >= CLOSE_AT).astype(np.float32)
    state = np.zeros((n, config.STATE_DIM), dtype=np.float32)
    state[:, :6] = joints
    state[:, 6] = 0.4 + 0.002 * t          # TCP x: 2 mm je Takt
    state[:, 9] = 1.0                       # Quaternion w
    state[:, 13] = gripper
    action = np.zeros((n, config.ACTION_DIM), dtype=np.float32)
    action[:-1, :6] = joints[1:]
    action[-1, :6] = joints[-1]
    action[:, 6] = gripper
    pose = np.zeros((n, 7), dtype=np.float32)
    pose[:, :3] = state[:, 6:9]
    pose[:, 3] = 1.0
    arrays = {
        "observation.state": state,
        "action": action,
        "aux.joints_ideal": joints.copy(),
        "aux.joints_command": joints.copy(),
        "aux.pose_ideal": pose,
        "aux.pose_noisy": pose.copy(),
        "aux.sync_ok": np.ones((n, 1), dtype=bool),
        "next.done": np.zeros((n, 1), dtype=bool),
    }
    for cam in ("wrist", "scene"):
        img = np.zeros((n, config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3), dtype=np.uint8)
        img[:, 0, 0, 0] = np.arange(n) % 256
        arrays["observation.images.%s" % cam] = img
    return dataset.Episode(arrays=arrays, metadata={"mode": "test"})


def _recording(tmp_path):
    writer = dataset.DatasetWriter(tmp_path / "aufnahme")
    writer.append(_episode())
    writer.append(_episode(n=20, offset=0.1))
    discarded = _episode(n=10)
    discarded.discarded = True
    writer.append(discarded)
    return tmp_path / "aufnahme"


def test_parse_episodes(tmp_path):
    recording = _recording(tmp_path)
    assert replay.parse_episodes("1", recording) == [1]
    assert replay.parse_episodes("0, 2", recording) == [0, 2]
    assert replay.parse_episodes("0-2", recording) == [0, 1, 2]
    assert replay.parse_episodes("alle", recording) == [0, 1]   # verworfene nicht


def test_replay_camera_plays_one_frame_per_read_and_holds_the_last(tmp_path):
    recording = _recording(tmp_path)
    clock = SimClock()
    captures, cfgs = start_cameras("sim", clock, cfgs=replay_configs(recording, 1))
    assert [c.name for c in cfgs] == ["wrist", "scene"]
    wrist = captures[0]
    seen = []
    for _ in range(25):
        clock.sleep(1.0 / 15)
        frame = wrist.latest()
        assert frame.timestamp == clock.now()   # frisch fuer den FrameAgeGuard
        assert frame.image.shape == (config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3)
        seen.append(int(frame.image[0, 0, 0]))
    assert seen[:20] == list(range(20))
    assert seen[20:] == [19] * 5                # Episode 1 hat 20 Takte
    wrist.camera.select(0)
    assert int(wrist.latest().image[0, 0, 0]) == 0
    for cap in captures:
        cap.stop()


def test_replay_check_compatible(tmp_path):
    recording = _recording(tmp_path)
    info = {"schema_version": config.SCHEMA_VERSION, "rate_hz": config.CONTROL_RATE_HZ,
            "cameras": ["wrist", "scene"], "image_size_hw": [config.IMAGE_HEIGHT,
                                                              config.IMAGE_WIDTH]}
    assert replay.check_compatible(recording, info) == []
    info["cameras"] = ["wrist", "top"]
    assert any("top" in p for p in replay.check_compatible(recording, info))


class _Oracle(PolicyPort):
    """Liest den Takt aus dem Bild und liefert die aufgezeichneten Actions."""

    def __init__(self, actions, bias=0.0, horizon=16):
        self.actions, self.bias, self.horizon = np.asarray(actions, dtype=float), bias, horizon

    def reset(self):
        pass

    def predict(self, observation):
        step = int(observation["observation.images.wrist"][0, 0, 0])
        idx = np.minimum(np.arange(step, step + self.horizon), len(self.actions) - 1)
        chunk = self.actions[idx].copy()
        chunk[:, :6] += self.bias
        return chunk


def test_open_loop_is_exact_for_a_perfect_policy(tmp_path):
    recording = _recording(tmp_path)
    arrays = replay.load_arrays(recording, 0)
    executor = ChunkEnsembler(_Oracle(arrays["action"]), replan_steps=8)
    result = replay.open_loop(executor, arrays, ["wrist", "scene"])
    summary = replay.summarize_open_loop(result)
    assert summary["steps"] == N
    assert summary["joint_err_deg_max"] < 1e-4
    assert summary["gripper_agreement"] == 1.0
    assert summary["gripper_switch_recorded"] == [CLOSE_AT]
    assert summary["gripper_switch_offset_steps"] == [0]


def test_open_loop_reports_a_constant_offset(tmp_path):
    recording = _recording(tmp_path)
    arrays = replay.load_arrays(recording, 0)
    executor = ChunkEnsembler(_Oracle(arrays["action"], bias=np.radians(2.0)), replan_steps=8)
    summary = replay.summarize_open_loop(replay.open_loop(executor, arrays, ["wrist", "scene"]))
    assert abs(summary["joint_err_deg_median"] - 2.0) < 1e-3
    assert abs(summary["joint_err_deg_p95_per_joint"][1] - 2.0) < 1e-3


def test_compare_rollout_path_and_grasp(tmp_path):
    recording = _recording(tmp_path)
    arrays = replay.load_arrays(recording, 0)
    ideal = arrays["aux.pose_ideal"].astype(float)
    tcp = ideal.copy()
    tcp[:, 1] += 0.005                                  # 5 mm seitlich
    gripper = arrays["action"][:, 6].astype(float)
    gripper = np.roll(gripper, 2)                       # 2 Takte spaeter geschlossen
    gripper[:2] = 0.0
    log = {"tcp": tcp, "joints": arrays["observation.state"][:, :6].astype(float),
           "gripper_cmd": gripper, "final_tcp": tcp[-1]}
    cmp = replay.compare_rollout(log, arrays)
    assert abs(cmp["path_dev_mm_p95"] - 5.0) < 0.01
    assert abs(cmp["step_err_mm_p95"] - 5.0) < 0.01
    assert abs(cmp["end_err_mm"] - 5.0) < 0.01
    assert cmp["grasp_step_offset"] == 2
    assert cmp["joint_err_deg_p95"] < 1e-6
    assert "Greifpunkt" in replay.format_rollout_comparison(cmp)


def test_infer_with_replay_cameras_advances_one_image_per_step(tmp_path):
    recording = _recording(tmp_path)
    from infer import run_episode

    from bc.collision import default_workspace

    clock = SimClock()
    robot = _fixtures.make_robot("sim", clock=clock)
    captures, _ = start_cameras("sim", clock, cfgs=replay_configs(recording, 0))
    workspace = default_workspace(table_height_m=float(robot.read_state().tcp_quat[2]) - 0.3)
    log = run_episode(robot, captures, ChunkEnsembler(HoldPolicy(), replan_steps=2), clock,
                      max_steps=10, workspace=workspace, threaded_watchdog=False, progress=None)
    assert log["stop_reason"] == "max_steps"
    for cap in captures:
        assert cap.camera.position == 10          # Takt 0..9 -> Bild 0..9
        cap.stop()


def test_infer_ignores_the_camera_backend_when_replaying(tmp_path):
    recording = _recording(tmp_path)
    from infer import check_against_recording

    info = {"schema_version": config.SCHEMA_VERSION, "rate_hz": config.CONTROL_RATE_HZ,
            "image_size_hw": [config.IMAGE_HEIGHT, config.IMAGE_WIDTH],
            "cameras": ["wrist", "scene"],
            "recording": {"camera_backends": {"wrist": "daheng", "scene": "daheng"}}}
    args = SimpleNamespace(execution_mode="servo_j", servo_rate=config.SERVO_RATE_HZ,
                           override=config.DEFAULT_OVERRIDE)
    assert check_against_recording(info, args, "sim", replay_configs(recording, 0)) == []
