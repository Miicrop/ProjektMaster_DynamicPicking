"""Weitermachen nach einem Abbruch, Kameraschutz, gemerkte Einstellungen (Anwender 2026-11-09)."""

import json
import os
from types import SimpleNamespace

import _paths  # noqa: F401

import numpy as np

from bc import config, touchup
from bc.auto_layout import Coverage, inner_distance
from bc.gui import recording
from bc.probe import placement_plans

#: Tischecken wie an der Anlage (ID0-ID3), z und Orientierung egal
CORNERS = [[0.168, -0.312], [0.572, -0.308], [0.571, 0.011], [0.169, 0.009]]


def _pose(x, y, y_axis):
    """Greifer senkrecht nach unten, Werkzeug-y zeigt in Richtung ``y_axis`` (Basis-KS)."""
    # 180 Grad um (cos t, sin t, 0): Werkzeug-y = (sin 2t, -cos 2t), Quaternion w, x, y, z
    t = np.arctan2(y_axis[1], y_axis[0]) / 2 + np.pi / 4
    return np.array([x, y, 0.01, 0.0, np.cos(t), np.sin(t), 0.0])


def _coverage(guard=True):
    return Coverage(CORNERS, 0.0, rng=np.random.default_rng(1), camera_guard=guard)


def test_camera_guard_blocks_only_outward_camera_in_listed_fields():
    cover = _coverage()
    assert cover.field_of((0.20, -0.02)) == (1, 5)   # wie ep_00208-210: Lage am Rand zaehlt mit
    # ep_00209 (heute ohne Kollision): ragt kaum hinaus, bleibt erlaubt
    assert not cover.camera_blocked(_pose(0.20, -0.014, (-0.94, 0.35)))
    outward = _pose(0.17, 0.0, (-1.0, 0.0))
    inward = _pose(0.17, 0.0, (1.0, 0.0))
    assert cover.camera_overhang(outward) > config.CAMERA_EDGE_ALLOWANCE_M
    assert cover.camera_blocked(outward) and not cover.camera_blocked(inward)
    # anderes Feld am Rand: nicht betroffen, auch wenn die Kamera hinausragt
    other = _pose(0.565, 0.005, (0.0, 1.0))
    assert cover.camera_overhang(other) > config.CAMERA_EDGE_ALLOWANCE_M
    assert not cover.camera_blocked(other)
    assert not _coverage(guard=False).camera_blocked(outward)


def test_inner_distance_matches_camera_overhang_sign():
    cover = _coverage()
    assert inner_distance(cover.hull, (0.37, -0.15)) > 0
    assert cover.camera_overhang(_pose(0.37, -0.15, (0.0, 1.0))) == 0.0


def test_turn_candidates_stay_in_range():
    cover = _coverage()
    turns = cover.turn_candidates()
    assert len(turns) == config.CAMERA_GUARD_TURN_TRIES
    assert all(abs(t) <= cover.yaw_range for t in turns)


def _backups_redirected(tmp_path):
    saved = config.TOUCHUP_BACKUP_ROOT
    config.TOUCHUP_BACKUP_ROOT = str(tmp_path / "sicherungen")
    return saved


def test_every_placement_updates_pick_with_a_single_backup(tmp_path):
    from test_auto_layout import _points, _record

    points, _probe = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    saved = _backups_redirected(tmp_path)
    try:
        error, log, opened = _record(tmp_path, ["--episodes", "2", "--lagen", "2"], points)
    finally:
        config.TOUCHUP_BACKUP_ROOT = saved
    assert error is None, log[-3000:]
    # 2 Varianten + Lagenwechsel + Variante + zurueck: je einmal geschrieben
    assert log.count("PICK uebernommen: x") >= 3
    assert "seit dem Start geaendert" not in log and "LAUF_ENDE" not in log
    assert len(list((tmp_path / "sicherungen").glob("*_PICK.json"))) == 1
    # am Ende liegt das Objekt wieder am geteachten PICK -- dort steht auch der Punkt
    assert np.allclose(opened[-1].point_record("PICK")["jointAngles"], taught, atol=1e-6)
    assert list((tmp_path / "data").glob("laufprotokoll_*.txt"))


def test_auto_start_proposes_drives_and_adopts_the_pose(tmp_path, monkeypatch):
    import record
    from test_auto_layout import _points, _record

    points, _probe = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    answers = []
    monkeypatch.setattr(record, "ask", lambda prompt, default="": answers.append(prompt) or "j")
    saved = _backups_redirected(tmp_path)
    try:
        error, log, opened = _record(
            tmp_path, ["--episodes", "1", "--lagen", "1", "--start-lage", "auto"], points)
    finally:
        config.TOUCHUP_BACKUP_ROOT = saved
    assert error is None, log[-3000:]
    assert len(answers) == 2 and recording.place_question(
        [l for l in log.splitlines() if l.startswith("LAGEVORSCHLAG")][0]) is not None
    assert "EINLEGEN bereit" in log
    meta = json.loads((tmp_path / "data" / "ep_00000" / "meta.json").read_text())["metadata"]
    assert meta["object_source"] == "vorgeschlagen"
    written = np.asarray(opened[-1].point_record("PICK")["jointAngles"], dtype=float)
    assert float(np.max(np.abs(written - taught))) > 1e-3


def test_refused_proposal_moves_nothing_and_keeps_pick(tmp_path, monkeypatch):
    import record
    from test_auto_layout import _points, _record

    points, _probe = _points(size=0.12)
    taught = np.array(points["PICK"], dtype=float)
    monkeypatch.setattr(record, "ask", lambda prompt, default="": "n")
    saved = _backups_redirected(tmp_path)
    try:
        error, log, opened = _record(
            tmp_path, ["--episodes", "1", "--lagen", "1", "--start-lage", "auto"], points)
    finally:
        config.TOUCHUP_BACKUP_ROOT = saved
    assert error is not None and "nicht freigegeben" in str(error)
    assert "EINLEGEN bereit" not in log
    assert np.allclose(opened[-1].point_record("PICK")["jointAngles"], taught)
    assert not (tmp_path / "data" / "ep_00000").exists()


def _plan(n=40, close_at=25):
    joints = np.linspace(0.0, 1.0, n)[:, None] * np.ones((n, 6))
    poses = np.tile(np.array([0.4, 0, 0.1, 0, 1, 0, 0.0]), (n, 1))
    gripper = np.zeros(n)
    gripper[close_at:] = config.GRIPPER_CLOSED
    return SimpleNamespace(joints_ideal=joints, joints_noisy=joints + 0.01, poses_ideal=poses,
                           poses_noisy=poses, gripper=gripper, dwell_mask=np.zeros(n, dtype=bool),
                           rate_hz=15.0)


def test_placement_plan_stops_at_the_grasp_with_open_gripper():
    plan = _plan()
    hin, zurueck = placement_plans(plan, factor=0.5)
    assert np.allclose(hin.joints_ideal[-1], plan.joints_ideal[25])     # am Greifpunkt
    assert np.allclose(zurueck.joints_ideal[-1], plan.joints_ideal[0])  # wieder am Start
    assert len(hin) > 26                                                # zeitlich gestreckt
    assert not hin.gripper.any() and not zurueck.gripper.any()


def test_placement_plan_needs_a_grasp():
    plan = _plan()
    plan.gripper = np.zeros(len(plan.gripper))
    try:
        placement_plans(plan)
    except ValueError as exc:
        assert "Greifpunkt" in str(exc)
    else:
        raise AssertionError("ohne Greifpunkt muss es scheitern")


def test_one_backup_per_run_still_undoes_to_the_state_before_the_run(tmp_path):
    written = []

    class Robot(object):
        record = {"name": "PICK", "jointAngles": [0.0] * 6}

        def point_names(self):
            return ["PICK"]

        def point_record(self, _name):
            return dict(self.record)

        def store_point(self, _name, joints):
            written.append(list(joints))
            self.record = {"name": "PICK", "jointAngles": list(joints)}
            return self.record

        def restore_point(self, record):
            self.record = dict(record)

    robot = Robot()
    plan = {"name": "PICK", "joints": [0.1] * 6, "problems": [], "warnings": [],
            "tool": "T", "in_simulation": True}
    backup, _ = touchup.apply_touch_up(robot, plan, tmp_path)
    robot.store_point("PICK", [0.2] * 6)
    touchup.update_backup_target(backup, [0.2] * 6)
    assert len(list(tmp_path.glob("*.json"))) == 1
    touchup.undo_touch_up(robot, backup)       # ohne force: gilt nicht als fremd geaendert
    assert robot.record["jointAngles"] == [0.0] * 6


def test_record_argv_new_options():
    plain = recording.record_argv("out", sequence="a.json")
    assert "--start-lage" not in plain and "--ohne-kameraschutz" not in plain
    argv = recording.record_argv("out", sequence="a.json", start_lage="auto", camera_guard=False)
    assert argv[argv.index("--start-lage") + 1] == "auto" and "--ohne-kameraschutz" in argv


def test_prompts_are_recognised():
    assert recording.place_question("LAGEVORSCHLAG x 412 y -77 Drehung -12 -- anfahren?") == (412, -77, -12)
    assert recording.place_question("Lage 2: x 412") is None
    assert recording.insert_question("EINLEGEN bereit -- Teil eingelegt, weiter?")
    assert recording.run_end_reason("LAUF_ENDE: arm folgt nicht") == "arm folgt nicht"
    assert recording.run_end_reason("Episode 0 ok") is None


def test_run_settings_roundtrip_and_broken_file(tmp_path):
    assert recording.load_run_settings(tmp_path) == {}
    assert recording.save_run_settings(tmp_path, {"lagen": 12})
    assert recording.load_run_settings(tmp_path) == {"lagen": 12}
    (tmp_path / recording.RUN_SETTINGS_FILE).write_text("{kaputt", encoding="utf-8")
    assert recording.load_run_settings(tmp_path) == {}


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return None
    return QApplication.instance() or QApplication([])


def test_recording_tab_restores_and_resets_settings(tmp_path):
    app = _app()
    if app is None:
        return
    from bc.gui import session as session_module
    from bc.gui import _bootstrap
    from bc.gui.runner import TaskRunner
    from bc.gui.tab_recording import RecordingTab

    recording.save_run_settings(tmp_path, {
        "lagen": 37, "variants": False, "first_lage": "auto", "block": "B057",
        "light": "Decke an", "block_benutzt": True, "naechster_block": "B058",
        "episodes": "unsinn"})
    original, _bootstrap.WORKDIR = _bootstrap.WORKDIR, str(tmp_path)
    runner = TaskRunner()
    tab = RecordingTab(session_module.Session(), runner)
    try:
        assert tab.lagen.value() == 37 and not tab.variants.isChecked()
        assert tab.first_lage.currentData() == "auto" and tab.block.text() == "B057"
        assert tab.light.currentText() == "Decke an"
        assert tab._block_used and tab._next_free_block == "B058"
        assert not tab.variant_shift.isEnabled()
        tab.confirm = lambda *_a: True
        tab.reset_settings()
        assert tab.lagen.value() == 1 and tab.variants.isChecked()
        assert tab.first_lage.currentData() == "geteacht"
        assert tab.block.text() == "B057"                   # Metadaten bleiben
        assert json.loads((tmp_path / recording.RUN_SETTINGS_FILE).read_text(
            encoding="utf-8"))["lagen"] == 1
        # zwei Spalten, solange die Seite breit genug ist
        tab.resize(1800, 900)
        tab.show()
        tab._focus_output(True)
        app.processEvents()
        bilder, abdeckung = tab._sections["bilder"], tab._sections["abdeckung"]
        fortschritt = tab._sections["fortschritt"]
        assert bilder.mapToGlobal(bilder.rect().topLeft()).x() \
            < abdeckung.mapToGlobal(abdeckung.rect().topLeft()).x()
        assert bilder.mapToGlobal(bilder.rect().topLeft()).y() \
            < fortschritt.mapToGlobal(fortschritt.rect().topLeft()).y()
        tab._focus_output(False)
    finally:
        _bootstrap.WORKDIR = original
        tab.shutdown()
        tab.close()
