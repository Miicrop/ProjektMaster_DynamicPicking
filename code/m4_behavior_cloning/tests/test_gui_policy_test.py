"""Reiter Betrieb: Policy-Test mit bekannter Lage, PICK-Anzeige, Kamerapruefung."""

import json
import os
from datetime import datetime, timedelta, timezone

import _paths  # noqa: F401

from bc.gui import operation, pick_view


def test_argv_known_pose_probe_and_camera_check():
    argv = operation.infer_argv("checkpoints/x", "neura", 2, known_pose=True, probe="objekt",
                                sequence="sequences/a.json", camera_check="warnen")
    assert argv[argv.index("--probegriff") + 1] == "objekt"
    assert "--lage-bekannt" in argv and argv[argv.index("--ablauf") + 1] == "sequences/a.json"
    assert argv[argv.index("--kamerapruefung") + 1] == "warnen"
    plain = operation.infer_argv("checkpoints/x", "neura", 2)
    assert "--lage-bekannt" not in plain and "--kamerapruefung" not in plain   # Default "an"


def test_progress_reads_known_line_and_camera_check():
    progress = operation.RolloutProgress(total_episodes=1)
    progress.feed("KAMERAPRUEFUNG scene: WARNUNG -- Helligkeit 180 (Training 90..120)")
    progress.feed("KAMERAPRUEFUNG gesamt: WARNUNG (Bilder: ...)")
    text, level = operation.camera_check_summary(progress)
    assert level == "warnung" and "scene: WARNUNG" in text
    progress.feed("Fahrt 0: kein Erfolg -- 80 Takte, Greifpunkt 4.2 mm, Ende - mm, "
                  "Bahn p95 - mm, griff, Vorhersage 70.0 ms, Overruns 0, gekappt 0")
    progress.feed("   Lage: Griff xy 4.2 mm, dz 1.0 mm, Drehung -2.0 Grad, Bahn p95 8.1 mm, "
                  "Tisch min 7.9 mm, Vorhersage xy - mm")
    row = progress.rollouts[0].row()
    assert row[-6:] == ["4.2 mm", "1.0 mm", "-2.0°", "7.9 mm", "-", "-"]
    progress.feed("   Experte: Korrektur dx 1.0 mm, dy -2.0 mm, xy 2.2 mm, Drehung 3.0 Grad, "
                  "Abstieg 10.0 mm")
    assert progress.rollouts[0].row()[-1] == "2.2 mm / 3.0°"


def test_pick_state_from_the_sim_robot_and_warnings(tmp_path):
    from test_auto_layout import SEQ, _points

    from bc.adapters.sim_robot import SimRobot
    from bc.clock import SimClock

    points, _probe = _points(size=0.12)
    seq = tmp_path / "ablauf.json"
    seq.write_text(json.dumps(SEQ), encoding="utf-8")
    robot = SimRobot(clock=SimClock(), points=points).connect()
    state = pick_view.read_pick_state(robot, seq)
    assert set(state.table_points) == {"ID0", "ID1", "ID2", "ID3"}
    assert state.pick is not None and state.warnings == []          # mitten im Tisch, 8 mm
    assert "PICK x" in pick_view.state_text(state)
    # ausserhalb und falsche Hoehe -> Hinweise
    state.pick = (state.pick[0] + 1.0, state.pick[1])
    state.pick_above_table_m = 0.02
    warnings = pick_view.pick_warnings(state)
    assert any("ausserhalb" in w for w in warnings) and any("ueber dem Tisch" in w for w in warnings)
    # juengste Episode an anderer Stelle -> Hinweis
    ep = tmp_path / "data" / "2026-11-16" / "ep_00000"
    ep.mkdir(parents=True)
    (ep / "meta.json").write_text(json.dumps({"metadata": {"recorded_at": "x", "points": {
        "PICK": {"pose_quat": [state.pick[0] - 1.0 + 0.02, state.pick[1], 0, 1, 0, 0, 0]}}}}),
        encoding="utf-8")
    state = pick_view.read_pick_state(robot, seq, data_root=tmp_path / "data")
    assert state.last_episode["where"] == "2026-11-16/ep_00000"
    assert any("juengsten Episode" in w for w in state.warnings)


def test_age_text():
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    assert pick_view.describe_age((now - timedelta(minutes=12)).isoformat(), now) == "vor 12 min"
    assert pick_view.describe_age((now - timedelta(hours=5)).isoformat(), now) == "vor 5 h"
    assert pick_view.describe_age(None, now) == ""


def test_operation_tab_policy_test_controls(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance() or QApplication([])
    from bc.gui import session as session_module
    from bc.gui.runner import TaskRunner
    from bc.gui.tab_operation import OperationTab

    tab = OperationTab(session_module.Session(), TaskRunner())
    try:
        tab.hold.setChecked(True)
        tab.known.setChecked(True)
        tab.probe.setCurrentIndex(tab.probe.findData("objekt"))
        argv = tab._argv()
        assert "--lage-bekannt" in argv and argv[argv.index("--probegriff") + 1] == "objekt"
        assert "--pick-quelle" not in argv and "--dagger" not in argv
        assert not tab.photo_point.isEnabled()
        tab.pick_source.setCurrentIndex(tab.pick_source.findData("m1"))
        assert tab.photo_point.isEnabled()
        tab.photo_point.setText("FOTO")
        tab.dagger_dir.setText("data/2026-11-17_dagger")
        argv = tab._argv()
        assert argv[argv.index("--pick-quelle") + 1] == "m1"
        assert argv[argv.index("--foto-punkt") + 1] == "FOTO"
        assert argv[argv.index("--dagger") + 1] == "data/2026-11-17_dagger"
        tab.probe.setCurrentIndex(tab.probe.findData("tisch"))     # DAgger nur mit Probegriff
        assert "--dagger" not in tab._argv()
        tab.probe.setCurrentIndex(tab.probe.findData("objekt"))
        only = tab._argv(camera_check="nur")
        assert "--lage-bekannt" not in only
        assert only[only.index("--kamerapruefung") + 1] == "nur"
        state = pick_view.PickState({"ID0": (0.2, -0.3), "ID1": (0.6, -0.3), "ID2": (0.6, 0.0),
                                     "ID3": (0.2, 0.0)}, pick=(0.4, -0.1), pick_yaw_deg=30.0,
                                    pick_above_table_m=0.008)
        state.warnings = pick_view.pick_warnings(state)
        tab.set_pick_state(state)
        assert "PICK passt" in tab.pick_warnings.text()
        tab.resize(1300, 900)
        tab.show()
        app.processEvents()
        tab.pick_view.grab()
        # Lage-Zeile nach der Ergebniszeile fuellt die Spalten nach
        tab._progress = operation.RolloutProgress(total_episodes=1)
        tab._on_line("Fahrt 0: kein Erfolg -- 80 Takte, Greifpunkt 4.2 mm, Ende - mm, "
                     "Bahn p95 - mm, griff, Vorhersage 70.0 ms, Overruns 0, gekappt 0")
        tab._on_line("   Lage: Griff xy 4.2 mm, dz 1.0 mm, Drehung -2.0 Grad, Bahn p95 8.1 mm, "
                     "Tisch min 7.9 mm, Vorhersage xy - mm")
        assert tab.rollouts.topLevelItem(0).text(9) == "4.2 mm"
        tab._on_line("KAMERAPRUEFUNG gesamt: OK (Bilder: ...)")
        assert "Kameraprüfung: OK" in tab.camera_line.text()
    finally:
        tab.shutdown()
        tab.close()
