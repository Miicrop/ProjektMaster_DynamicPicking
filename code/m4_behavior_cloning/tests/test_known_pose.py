"""Policy-Test mit bekannter Lage (bc/known_pose.py, apps/infer.py --lage-bekannt)."""

import contextlib
import csv
import io
import json
import sys
from pathlib import Path

import _paths  # noqa: F401

import numpy as np

from bc import config, known_pose
from bc.table import fit_table

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps"))


def _down(x, y, z, yaw_deg=0.0):
    """Greifer senkrecht nach unten, Werkzeug-x um ``yaw_deg`` gedreht (w, x, y, z)."""
    t = np.radians(yaw_deg) / 2.0
    return np.array([x, y, z, 0.0, np.cos(t), np.sin(t), 0.0])


def _known(pick_z=0.009, yaw=30.0):
    plane = fit_table([[x, y, 0.0, 0, 1, 0, 0] for x in (0.2, 0.6) for y in (-0.3, 0.1)])
    pick = _down(0.4, -0.1, pick_z, yaw)
    path = np.array([[0.4, -0.1, 0.10], [0.4, -0.1, pick_z]])
    return known_pose.KnownPose(pick, plane, path, "Test")


def test_track_measures_path_pick_table_and_yaw():
    known = _known()
    tcp = np.array([_down(0.405, -0.1, 0.05, 30.0),     # 5 mm neben Bahn und PICK
                    _down(0.4, -0.097, 0.012, 200.0)])  # 3 mm daneben, 170 Grad = -10
    rows = known_pose.track(tcp, known)
    assert np.allclose(rows["path_dev"], [0.005, 0.003], atol=1e-6)
    assert np.allclose(rows["xy_pick"], [0.005, 0.003], atol=1e-6)
    assert np.allclose(rows["dz_pick"], [0.041, 0.003], atol=1e-6)
    assert np.allclose(rows["table"], [0.05, 0.012], atol=1e-6)
    assert np.allclose(rows["yaw_err"], [0.0, -10.0], atol=1e-6)
    summary = known_pose.summarize(rows, known, grasp_step=1, probe="tisch")
    assert summary["at_grasp"]["step"] == 1 and summary["at_stop"]["step"] == 1
    assert abs(summary["table_min_m"] - 0.012) < 1e-9
    assert abs(summary["pick_above_table_m"] - 0.009) < 1e-9
    # ohne Takte: nichts, aber kein Fehler
    empty = known_pose.summarize(known_pose.track(np.zeros((0, 7)), known), known)
    assert empty["at_stop"] is None and empty["path_dev_p95_m"] is None


def test_probe_clearance_object_stops_above_the_object_top():
    known = _known(pick_z=0.009)
    assert known_pose.probe_clearance("tisch", known) == config.TABLE_MIN_CLEARANCE_M
    expected = 0.009 + config.PROBE_OBJECT_TOP_ABOVE_PICK_M + config.PROBE_GAP_M
    assert abs(known_pose.probe_clearance("objekt", known) - expected) < 1e-9


def test_predicted_grasp_from_the_rest_of_the_chunk():
    known = _known(yaw=0.0)

    def fk(q):   # Gelenke 0..2 = Position (Testattrappe)
        return _down(q[0], q[1], q[2], 0.0)

    actions = np.array([[0.404, -0.1, 0.03 - 0.005 * k, 0, 0, 0, 1.0 if k >= 3 else 0.0]
                        for k in range(6)])
    pred = known_pose.predicted_grasp(actions, fk, known)
    assert pred["closes"] and pred["index"] == 3
    assert abs(pred["xy_m"] - 0.004) < 1e-9 and abs(pred["dz_m"] - (0.015 - 0.009)) < 1e-9
    # schliesst nicht: das tiefste Ziel
    actions[:, -1] = 0.0
    pred = known_pose.predicted_grasp(actions, fk, known)
    assert not pred["closes"] and pred["index"] == 5
    assert known_pose.predicted_grasp(np.zeros((0, 7)), fk, known) is None


def test_csv_row_and_result_line():
    known = _known()
    rows = known_pose.track(np.array([_down(0.405, -0.1, 0.02, 30.0)]), known)
    summary = known_pose.summarize(rows, known, probe="objekt",
                                   predicted={"closes": True, "xy_m": 0.0042, "dz_m": 0.001,
                                              "yaw_deg": 2.0})
    row = known_pose.csv_row(3, "kollision vorab: tool an Tischebene (Rest -1 mm)", summary)
    assert len(row) == len(known_pose.CSV_COLUMNS)
    line = known_pose.result_line(summary)
    assert line.startswith("   Lage: Stopp xy 5.0 mm") and "Vorhersage xy 4.2 mm" in line
    from bc.gui import operation
    assert operation.parse_known_line(line)["predicted_mm"] == 4.2


def test_run_episode_saves_the_rest_of_the_prediction_on_a_table_stop():
    """Lehnt der Tisch ein Ziel ab, bleibt der Rest der Vorhersage im Log."""
    from infer import run_episode
    from test_apps import _infer_setup

    from bc.policy import ChunkEnsembler, HoldPolicy
    from bc.table import TableSurface

    robot, captures, clock, workspace = _infer_setup()
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    z0 = float(robot.fk(q0)[2])
    # Gelenk 2 so drehen, dass die Werkzeugspitze sinkt
    step = np.zeros_like(q0)
    step[1] = 0.02
    step = step if robot.fk(q0 + step)[2] < robot.fk(q0 - step)[2] else -step
    z_low = float(robot.fk(q0 + step)[2])
    assert z0 - z_low > 0.002

    class Sinking(HoldPolicy):
        def predict(self, observation):
            chunk = super().predict(observation)
            chunk[:, :6] = q0 + step
            return chunk

    tcp = np.asarray(robot.fk(q0), dtype=float)
    # Ist-Stellung frei (>= 3 mm), das Ziel der Policy nicht
    height = z_low - 0.001
    plane = fit_table([[tcp[0] + dx, tcp[1] + dy, height, 0, 1, 0, 0]
                       for dx in (-0.1, 0.1) for dy in (-0.1, 0.1)])
    workspace.add_box(TableSurface(plane))
    log = run_episode(robot, captures, ChunkEnsembler(Sinking(), replan_steps=2), clock,
                      max_steps=20, workspace=workspace, threaded_watchdog=False, progress=None)
    assert log["stop_reason"].startswith("kollision vorab") and "Tischebene" in log["stop_reason"]
    assert log["probe_actions"].ndim == 2 and log["probe_actions"].shape[1] == 7
    from infer import expected_test_stop, retreat_after_test
    assert expected_test_stop(log["stop_reason"]) and expected_test_stop("griff")
    assert not expected_test_stop("max_steps")

    # Rueckzug: Stopp quittieren, Greifer auf, anheben, zurueck zum Start
    from types import SimpleNamespace
    robot.gripper_command(True)
    start = robot.read_state().joints.copy()
    text = retreat_after_test(robot, workspace, log, start, clock,
                              SimpleNamespace(servo_rate=config.SERVO_RATE_HZ))
    assert text == "am Start", text
    assert not robot.stop_requested and not robot.read_state().gripper_closed
    assert np.allclose(robot.read_state().joints, start, atol=1e-3)
    # nach einem fremden Stopp bleibt der Arm stehen
    assert retreat_after_test(robot, workspace, {"stop_reason": "max_steps"}, start, clock,
                              SimpleNamespace(servo_rate=config.SERVO_RATE_HZ)).startswith("keiner")


def _run_infer(tmp_path, extra, points=None):
    import infer
    from test_auto_layout import SEQ, _points

    from bc.adapters.sim_robot import SimRobot

    if points is None:
        points, _probe = _points(size=0.12)
    seq = tmp_path / "ablauf.json"
    seq.write_text(json.dumps(SEQ), encoding="utf-8")
    saved = sys.argv, infer.open_robot, config.TOUCHUP_BACKUP_ROOT
    config.TOUCHUP_BACKUP_ROOT = str(tmp_path / "sicherungen")   # nicht ins Repo
    sys.argv = ["infer.py", "--sim", "--hold", "--steps", "20", "--lage-bekannt",
                "--ablauf", str(seq), "--out", str(tmp_path / "out")] + extra
    opened = []

    def robot(kind, clock=None, **kw):
        opened.append(SimRobot(clock=clock, points=points))
        return opened[-1]

    infer.open_robot = robot
    log, error = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(log):
            infer.main()
    except SystemExit as exc:
        error = exc
    finally:
        sys.argv, infer.open_robot, config.TOUCHUP_BACKUP_ROOT = saved
    return error, log.getvalue(), opened


def test_infer_known_pose_writes_deviation_per_tick_and_csv(tmp_path):
    error, log, _ = _run_infer(tmp_path, ["--episodes", "1", "--probegriff", "tisch"])
    assert error is None, log[-3000:]
    assert "Lage bekannt: PICK" in log and "Probegriff tisch" in log
    assert "Abweichung Bahn" in log            # Fortschritt mit Abweichung
    assert log.count("   Lage: ") == 1
    out = tmp_path / "out"
    with open(out / "policy_test.csv", encoding="utf-8") as handle:
        table = list(csv.reader(handle, delimiter=";"))
    assert table[0] == list(known_pose.CSV_COLUMNS) and len(table) == 2
    assert all(len(row) == len(known_pose.CSV_COLUMNS) for row in table)
    z = np.load(out / "rollout_000.npz")
    n = len(z["tcp"]) + 1                       # plus Schlusszustand
    for key in ("lage_path_dev", "lage_xy_pick", "lage_dz_pick", "lage_table", "lage_yaw_err"):
        assert len(z[key]) == n
    assert z["lage_pick"].shape == (7,)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    lage = summary["episodes"][0]["lage"]
    assert lage["probe"] == "tisch" and lage["at_stop"] is not None
    # Hold-Policy greift nie: kein vorgesehenes Ende -> kein Rueckzug
    assert summary["episodes"][0]["rueckzug"].startswith("keiner")


def test_probe_single_run_stays_above_the_object(tmp_path):
    error, log, _ = _run_infer(tmp_path, ["--episodes", "1", "--probegriff", "objekt"])
    assert error is None, log[-3000:]
    assert "Danach: stehen geblieben" in log and "Experte:" not in log


def test_probe_series_corrects_grasps_and_places_at_a_new_pose(tmp_path):
    from test_auto_layout import _points

    points, _probe = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    error, log, opened = _run_infer(tmp_path, ["--episodes", "2", "--probegriff", "objekt"],
                                    points)
    assert error is None, log[-4000:]
    assert log.count("   Experte: Korrektur") == 2, log[-4000:]
    out = tmp_path / "out"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    first, second = (e["experte"] for e in summary["episodes"])
    assert first["result"].startswith("gegriffen"), first["result"]
    assert second["result"].startswith("gegriffen"), second["result"]
    # Korrektur = Weg vom Stopp ueber PICK (Hold-Policy: Startstellung, hoch oben)
    assert first["correction"]["descent_m"] > 0.02
    # zweite Fahrt an der neuen Lage, PICK in der Steuerung nachgefuehrt
    assert np.allclose(summary["episodes"][1]["lage"]["pick"], first["new_pick"], atol=1e-4)
    robot = opened[-1]
    assert float(np.max(np.abs(np.asarray(robot._points["PICK"]) - taught))) > 1e-3
    z = np.load(out / "experte_000.npz")
    assert len(z["tcp"]) == len(z["gripper_cmd"]) > 10
    assert z["gripper_cmd"].max() == 1.0 and z["gripper_cmd"][-1] == 0.0  # gegriffen, abgelegt
    with open(out / "policy_test.csv", encoding="utf-8") as handle:
        table = list(csv.reader(handle, delimiter=";"))
    col = known_pose.CSV_COLUMNS.index("korrektur_xy_mm")
    assert table[1][col] != "" and table[2][col] != ""
    assert list((tmp_path / "sicherungen").rglob("*.json"))     # eine Sicherung vom Lauf


def test_infer_known_pose_needs_a_sequence(tmp_path):
    import infer

    saved = sys.argv
    sys.argv = ["infer.py", "--sim", "--hold", "--lage-bekannt", "--replay", "x"]
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            infer.parse_args()
        raise AssertionError("--lage-bekannt mit --replay muss scheitern")
    except SystemExit:
        pass
    finally:
        sys.argv = saved


def test_expert_placement_differs_between_runs_without_fixed_seed():
    # Anwender 2026-11-24: je Lauf eine Fahrt, fester Seed -> der Experte pendelte
    # zwischen zwei Stellen. Mit demselben Startwert gleich, mit anderen verteilt.
    known = _known()
    known.region = [_down(x, y, 0.0) for x, y in ((0.2, -0.3), (0.6, -0.3), (0.6, 0.1),
                                                  (0.2, 0.1))]
    reference = known.pick.copy()

    def first_xy(seed):
        cands = known_pose.new_place_pose(known, reference, np.random.default_rng(seed),
                                          camera_guard=False)
        return tuple(np.round(cands[0][1], 3))

    assert first_xy(0) == first_xy(0)
    assert len({first_xy(seed) for seed in range(12)}) >= 4


def test_regrasp_after_placing_closes_and_opens_once_more():
    # Anwender 2026-11-24: nach dem Ablegen nachgreifen, damit das Teil mittig liegt
    pick = _down(0.4, -0.1, 0.009)
    place = _down(0.3, -0.2, 0.009)
    plain = known_pose.expert_waypoints(pick, None, pick, pick, place, np.zeros(6), 0.05,
                                        np.zeros(6), np.zeros(6), pick)
    names = [w.name for w in known_pose.expert_waypoints(
        pick, None, pick, pick, place, np.zeros(6), 0.05, np.zeros(6), np.zeros(6), pick,
        regrasp=True)]
    assert "NACHGRIFF" not in [w.name for w in plain]
    i = names.index("ABLAGE")
    assert names[i + 1:i + 4] == ["NACHGRIFF", "LOESEN", "UEBER_ABLAGE"]
    wps = known_pose.expert_waypoints(pick, None, pick, pick, place, np.zeros(6), 0.05,
                                      np.zeros(6), np.zeros(6), pick, regrasp=True)
    ablage, nach, los = wps[i], wps[i + 1], wps[i + 2]
    assert (ablage.gripper_closed, nach.gripper_closed, los.gripper_closed) == (False, True, False)
    assert nach.pose_quat[2] < ablage.pose_quat[2] == los.pose_quat[2]   # kein Nullsegment
    assert np.allclose(nach.pose_quat[:2], place[:2])


def test_expert_regrasps_in_the_simulation(tmp_path):
    from test_auto_layout import _points

    points, _probe = _points(size=0.12)
    # Experte erst ab zwei Fahrten (eine Fahrt: Arm bleibt ueber dem Objekt)
    error, log, _ = _run_infer(tmp_path, ["--episodes", "2", "--probegriff", "objekt",
                                          "--nachgreifen"], points)
    assert error is None, log[-4000:]
    z = np.load(tmp_path / "out" / "experte_000.npz")
    g = z["gripper_cmd"]
    closings = int(np.sum((g[1:] > 0.5) & (g[:-1] < 0.5)))
    assert closings == 2, closings                # greifen + nachgreifen
    assert g[-1] == 0.0
