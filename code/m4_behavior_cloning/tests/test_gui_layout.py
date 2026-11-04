"""Aufnahme-Reiter neu geordnet, Kameraausschnitt, Kameraeinstellungen (Anwender 2026-11-03)."""

import json
import os
from types import SimpleNamespace

import _paths  # noqa: F401

import numpy as np

from bc import camera_settings, config, preview
from bc.gui import recording
from bc.gui import reload as reload_module


# -- Qt-frei ------------------------------------------------------------------

def test_policy_crop_box_is_centred():
    x0, y0, x1, y1 = preview.policy_crop_box((240, 320, 3), ratio=0.9)
    assert (x1 - x0 + 1, y1 - y0 + 1) == (288, 216)
    assert x0 == 320 - 1 - x1 and y0 == 240 - 1 - y1


def test_display_frames_never_touch_the_camera_image():
    image = np.zeros((1080, 1440, 3), dtype=np.uint8)
    frame = SimpleNamespace(image=image, timestamp=1.5)
    shown = preview.display_frames({"wrist": frame, "scene": None}, recorded=True, crop=True)
    assert shown["wrist"].image.shape == (config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3)
    assert shown["wrist"].image.any() and not image.any()     # Rahmen nur in der Kopie
    assert shown["wrist"].timestamp == 1.5 and shown["scene"] is None
    assert preview.display_frames({"wrist": frame}, False, False)["wrist"] is frame
    assert not preview.distorted_by_recording((1080, 1440)) and preview.distorted_by_recording((1080, 1920))


def test_camera_settings_follow_the_device(tmp_path):
    wrist = config.WRIST_CAMERA
    assert camera_settings.apply([wrist], root=tmp_path) == ([wrist], [])
    camera_settings.save(wrist, {"exposure_us": 6000.0, "gain_db": None}, root=tmp_path)
    data = json.loads((tmp_path / camera_settings.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert data == {"daheng:%s" % wrist.device: {"exposure_us": 6000.0, "gain_db": None}}
    (applied,), notes = camera_settings.apply([wrist], root=tmp_path)
    assert applied.exposure_us == 6000.0 and applied.gain_db is None
    assert "Belichtung 6000 us" in notes[0] and "Gain Automatik" in notes[0]
    # dieselbe Kamera auf dem anderen Platz: Werte wandern mit
    from dataclasses import replace

    (moved,), _ = camera_settings.apply([replace(wrist, name="scene")], root=tmp_path)
    assert moved.exposure_us == 6000.0
    # Platzhalter und andere Kameras bleiben unberuehrt
    sim = config.SIM_CAMERAS[0]
    assert camera_settings.apply([sim], root=tmp_path)[0] == [sim]


def test_outcome_hints_explain_the_result_column():
    assert "vollständig aufgezeichnet" in recording.outcome_hint("ok")
    both = recording.outcome_hint("ok, 3 Rausch-Rejects")
    assert "vollständig" in both and "neu gezogen" in both
    assert "Steuerung hat die Fahrt angehalten" in recording.outcome_hint("VERWORFEN (schutzstopp)")
    later = recording.outcome_hint("FEHLGESCHLAGEN (nachträglich)")
    assert "Rechtsklick" in later and "Fehlschlag" in later


def test_record_argv_put_back_speed_and_final_pose():
    base = recording.record_argv("x", sequence="s.json")
    assert "--ablage-tempo" not in base and "--schluss-lage" not in base
    tuned = recording.record_argv("x", sequence="s.json", put_back_speed=0.03, final_new=True)
    assert tuned[tuned.index("--ablage-tempo") + 1] == "0.03"
    assert tuned[tuned.index("--schluss-lage") + 1] == "neu"
    same = recording.record_argv("x", sequence="s.json",
                                 put_back_speed=config.PUT_BACK_APPROACH_SPEED_MS)
    assert "--ablage-tempo" not in same
    assert "--schluss-lage" not in recording.record_argv("x", sequence="s.json", put_back=False,
                                                         final_new=True)
    assert recording.adopted_pick_backup("PICK uebernommen: x 1 mm -- Sicherung: a/b.json") == "a/b.json"
    assert recording.adopted_pick_backup("PICK: 8.0 mm ueber dem Tisch") is None


def test_open_preview_does_not_block_the_restart():
    tab = SimpleNamespace(title="Aufnahme", busy_reason=lambda: None,
                          closable_reason=lambda: "Kameravorschau ist offen")
    plain = SimpleNamespace(title="Training", busy_reason=lambda: None)
    assert reload_module.busy_reasons([tab, plain]) == []
    assert reload_module.closable_reasons([tab, plain]) == ["Aufnahme: Kameravorschau ist offen"]


# -- Qt (offscreen) -----------------------------------------------------------

def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return None
    return QApplication.instance() or QApplication([])


def test_recording_tab_sections_and_focus(tmp_path):
    app = _app()
    if app is None:
        return
    from bc.gui import session as session_module
    from bc.gui.runner import TaskRunner
    from bc.gui.tab_recording import LEFT_MIN_WIDTH_TEACHING, LEFT_WIDTH_RECORDING, RecordingTab

    runner = TaskRunner()
    tab = RecordingTab(session_module.Session(), runner)
    try:
        tab.workdir = tmp_path                       # gemerkte Anordnung nicht ins Repo
        assert list(tab._sections) == ["bilder", "abdeckung", "fortschritt", "kommando",
                                       "ausgabe"]
        tab.resize(1400, 900)
        tab.show()
        app.processEvents()
        # Zuklappen merkt sich der Reiter
        tab._sections["abdeckung"].set_open(False)
        state = json.loads((tmp_path / "einstellungen" / "oberflaeche.local.json")
                           .read_text(encoding="utf-8"))
        assert state["offen"]["abdeckung"] is False and state["offen"]["bilder"] is True
        tab._sections["abdeckung"].set_open(True)
        # Aufnahme: rechts in den Vordergrund, danach wie vorher
        before = tab.splitter.sizes()
        tab._focus_output(True)
        app.processEvents()
        # so schmal wie die Knoepfe unten links es zulassen (offscreen breiter)
        narrow = max(LEFT_WIDTH_RECORDING, tab._left_panel.minimumSizeHint().width())
        assert tab.splitter.sizes()[0] <= narrow + 1 < before[0]
        tab._focus_output(False)
        assert tab._left_panel.minimumWidth() == LEFT_MIN_WIDTH_TEACHING
        assert tab.splitter.sizes() == before
        # Grossansicht der Tischabdeckung
        tab.coverage_map.double_clicked.emit()
        assert tab._coverage_view is not None
        tab._coverage_view.close()
        app.processEvents()
        # Ergebnis mit Erklaerung
        tab._progress = recording.RecordProgress(1)
        tab._on_line("Episode 0 -> ep_00000: 120 Schritte, ok, 2 Rausch-Rejects")
        item = tab.episode_list.topLevelItem(0)
        assert "neu gezogen" in item.toolTip(3)
        tab.grab()
    finally:
        tab.shutdown()
        runner.shutdown()


def test_camera_dialog_locks_cameras_it_cannot_set():
    app = _app()
    if app is None:
        return
    from bc.gui.camera_dialog import CameraSettingsDialog
    from bc.gui.runner import TaskRunner

    sim = SimpleNamespace(name="wrist", camera=SimpleNamespace(cfg=config.SIM_CAMERAS[0]))
    runner = TaskRunner()
    dialog = CameraSettingsDialog([sim], runner, ".")
    try:
        assert not dialog.btn_save.isEnabled() and not dialog.exposure.isEnabled()
        frame = SimpleNamespace(image=np.zeros((480, 640, 3), dtype=np.uint8), timestamp=0.0)
        dialog.show_frames({"wrist": frame})
        dialog.recorded.setChecked(True)
        dialog.show_frames({"wrist": frame})
    finally:
        dialog.close()
        runner.shutdown()
