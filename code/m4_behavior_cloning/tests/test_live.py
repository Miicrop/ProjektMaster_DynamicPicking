"""Live-Ansicht der Inferenz (bc/live.py, Anwender 2026-11-17)."""

import json
import math

import numpy as np

from bc import config, live
from bc.policy import ChunkEnsembler


class _State(object):
    def __init__(self, joints, tcp):
        self.joints = np.asarray(joints, dtype=float)
        self.tcp_quat = np.asarray(tcp, dtype=float)


def _fk_yaw(q):
    """Spielzeug-FK: x = q0, y = q1, z = q2, Drehung um z = q5 (rad)."""
    h = 0.5 * float(q[5])
    return np.array([q[0], q[1], q[2], math.cos(h), 0.0, 0.0, math.sin(h)])


def test_yaw_diff_uses_the_full_turn():
    assert live.yaw_diff(170.0, 10.0) == 160.0
    assert live.yaw_diff(350.0, 10.0) == -20.0
    assert live.yaw_diff(10.0, 190.0) == -180.0
    assert live.yaw_diff(None, 3.0) is None


def test_mean_actions_like_the_ensembler():
    a = np.zeros((4, 7))
    b = np.ones((2, 7))
    mean = live.mean_actions([a, b])
    assert mean.shape == (2, 7)                 # so weit beide reichen
    assert np.allclose(mean, 0.5)


def test_plan_info_finds_the_grasp_and_its_yaw():
    actions = np.zeros((10, 7))
    actions[:, 0] = np.linspace(0.3, 0.4, 10)
    actions[:, 5] = math.radians(30.0)
    actions[6:, 6] = 1.0                      # schliesst ab Index 6
    info = live.plan_info(actions, _fk_yaw, None, offset_deg=0.0)
    g = info["grasp"]
    assert g["closes"] and g["in_steps"] == 6
    assert abs(g["x"] - actions[6, 0]) < 1e-9
    assert abs(g["yaw"] - 30.0) < 1e-6


def test_two_modes_are_averaged_to_a_wrong_yaw():
    """Der Kern der Vermutung: zwei Vorhersagen +40 und -40 Grad, Mittel 0."""
    up = np.zeros((8, 7))
    up[:, 5] = math.radians(130.0)
    down = np.zeros((8, 7))
    down[:, 5] = math.radians(50.0)
    mean = live.plan_info(live.mean_actions([up, down]), _fk_yaw, None, offset_deg=0.0)
    assert abs(mean["grasp"]["yaw"] - 90.0) < 1e-6


def test_robot_to_image_inverts_m1():
    """M1: Bild -> entzerrt (H) -> Arbeitsbereich -> Roboter (starr)."""
    H = np.array([[1.1, 0.05, -20.0], [0.02, 0.95, 10.0], [1e-5, 2e-5, 1.0]])
    m = {"H_img2rect": H.tolist(), "px_per_mm": 2.0, "size_mm": [400.0, 300.0],
         "rotation_deg": 0.35, "translation_mm": [205.1, -319.7]}
    u, v = 500.0, 250.0
    r = H @ np.array([u, v, 1.0])
    ru, rv = r[0] / r[2], r[1] / r[2]
    x_ws, y_ws = ru / 2.0, 300.0 - rv / 2.0
    c, s = math.cos(math.radians(0.35)), math.sin(math.radians(0.35))
    x_r = c * x_ws - s * y_ws + 205.1
    y_r = s * x_ws + c * y_ws - 319.7
    back = live.robot_to_image(m, [1e-3 * x_r, 1e-3 * y_r])[0]
    assert np.allclose(back, [u, v], atol=1e-6)


class _Policy(object):
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def reset(self):
        pass

    def observe(self, _obs):
        pass

    def snapshot(self, obs):
        return obs

    def predict_snapshot(self, _snap):
        return self.chunks.pop(0)


def test_writer_state_shows_each_prediction_and_the_mean(tmp_path):
    from types import SimpleNamespace

    first = np.zeros((16, 7))
    first[:, 5] = math.radians(130.0)
    second = np.zeros((16, 7))
    second[:, 5] = math.radians(50.0)
    ens = ChunkEnsembler(_Policy([first, second]), replan_steps=1)
    ens.next_action({})
    ens.next_action({})
    pick = np.array([0.0, 0.0, 0.0, math.cos(math.radians(45)), 0, 0, math.sin(math.radians(45))])
    known = SimpleNamespace(pick=pick, table=None, region=[], gap_m=0.025)
    writer = live.LiveWriter(tmp_path, fk=_fk_yaw, threaded=False)
    writer.offset_deg = 0.0
    writer.set_known(known)
    writer.start_episode(0)
    writer.update(1, _State(np.zeros(6), _fk_yaw(np.zeros(6))), executor=ens)
    writer.flush(force=True)
    state = json.loads((tmp_path / live.STATE_FILE).read_text(encoding="utf-8"))
    yaws = sorted(round(p["grasp"]["yaw"]) for p in state["chunks"])
    assert yaws == [50, 130]
    assert round(state["mean"]["grasp"]["yaw"]) == 90
    assert round(state["mean"]["grasp"]["yaw_err"]) == 0     # PICK 90 Grad
    assert state["grasp_yaw_spread_deg"] > 70
    assert state["gap_mm"] == 25.0


def test_writer_never_raises_into_the_loop(tmp_path):
    class Broken(object):
        def active_chunks(self):
            raise RuntimeError("kaputt")

    writer = live.LiveWriter(tmp_path, fk=None, threaded=False)
    writer.update(0, _State(np.zeros(6), [0.3, 0.0, 0.1, 1, 0, 0, 0]), executor=Broken())
    writer.flush(force=True)
    assert (tmp_path / live.STATE_FILE).exists()


def test_default_probe_gap_is_25_mm():
    assert config.PROBE_GAP_M == 0.025


def test_camera_offset_turns_every_arrow_alike():
    pose = _fk_yaw([0, 0, 0, 0, 0, math.radians(100.0)])
    assert abs(live.pose_info(pose, None, -107.0)["yaw"] - 353.0) < 1e-6


def test_cell_layout_has_base_and_obstacles():
    cell = live.cell_layout()
    assert cell["base"]["r"] > 0
    assert {b["name"] for b in cell["boxes"]} >= {"Kamerastange", "Teststation"}


def test_turns_are_balanced_around_the_start_not_the_pick():
    """Drehverteilung (Anwender 2026-11-17): PICK 30 Grad neben dem Start --
    die Drehungen sollen um den Start liegen, gleich oft plus und minus."""
    from bc.auto_layout import Coverage

    region = [[0.3, -0.2, 0, 1, 0, 0, 0], [0.6, -0.2, 0, 1, 0, 0, 0], [0.6, 0.1, 0, 1, 0, 0, 0],
              [0.3, 0.1, 0, 1, 0, 0, 0]]
    cov = Coverage(region, base_yaw_deg=133.0, yaw_range_deg=45.0, center_shift_deg=-30.0,
                   rng=np.random.default_rng(0))
    absolute = []
    for _ in range(600):
        turn = cov.next_turn()
        absolute.append(133.0 + turn)
        cov.add((0.4, 0.0), (133.0 + turn) % 180.0)
    rel = np.array(absolute) - 103.0
    assert abs(np.mean(rel)) < 3.0
    assert rel.min() >= -45.0 - 1e-9 and rel.max() <= 45.0 + 1e-9
    assert abs(np.sum(rel > 0) - np.sum(rel < 0)) < 30


def test_center_shift_uses_the_full_turn():
    """PICK 150 Grad neben dem Start (Fase auf der anderen Seite): modulo 180
    waeren das -30 Grad -- gedreht werden muss aber -150."""
    from bc.auto_layout import Coverage

    region = [[0.3, -0.2, 0, 1, 0, 0, 0], [0.6, -0.2, 0, 1, 0, 0, 0], [0.6, 0.1, 0, 1, 0, 0, 0],
              [0.3, 0.1, 0, 1, 0, 0, 0]]
    cov = Coverage(region, base_yaw_deg=73.0, yaw_range_deg=45.0, center_shift_deg=-150.0,
                   rng=np.random.default_rng(1))
    turns = np.array([cov.next_turn() for _ in range(200)])
    assert turns.min() >= -195.0 - 1e-9 and turns.max() <= -105.0 + 1e-9
