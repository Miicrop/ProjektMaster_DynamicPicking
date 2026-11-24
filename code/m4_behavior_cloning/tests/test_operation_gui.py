"""Reiter Betrieb: Kamerapruefung als Tabelle, einklappbare Abschnitte und eine
gemeinsame Kamerazuordnung mit dem Reiter Aufnahme (Anwender 2026-11-24)."""

import json
import os

import _paths  # noqa: F401

from bc import camera_check
from bc.gui import operation

# Ausgabe von apps/infer.py am 24.11. (G2c, Weissabgleich "Once")
LINES = [
    "KAMERAPRUEFUNG scene: WARNUNG -- Farbe R/G 0.98 (Training 1.40..1.55); "
    "Saettigung 42 (Training 103..136)",
    "   in Ordnung: Helligkeit 133 (Training 143..161)",
    "KAMERAPRUEFUNG wrist: OK -- Helligkeit 43 (Training 29..50); "
    "Kameralage: Versatz 0.6 px, Drehung 0.1 Grad, Massstab 1.001",
]


def _results():
    return [
        {"camera": "scene", "level": "warnung",
         "checks": [("ok", "Helligkeit 133 (Training 143..161)"),
                    ("warnung", "Farbe R/G 0.98 (Training 1.40..1.55)"),
                    ("ok", "Kameralage: Versatz 2.2 px, Drehung -0.5 Grad, Massstab 1.000")]},
        {"camera": "wrist", "level": "warnung",
         "checks": [("ok", "Farbe R/G 2.17 (Training 2.15..2.24)"),
                    ("warnung", "Kameralage: Versatz 9.0 px, Drehung 3.0 Grad, Massstab 1.000")]},
    ]


def test_checks_are_grouped_into_light_and_pose():
    groups = camera_check.group_levels(_results()[0]["checks"])
    assert groups == {"licht": "warnung", "lage": "ok"}
    groups = camera_check.group_levels(_results()[1]["checks"])
    assert groups == {"licht": "ok", "lage": "warnung"}


def test_table_from_json_line():
    progress = operation.RolloutProgress()
    assert progress.feed(camera_check.to_json_line(_results()))
    progress.feed("KAMERAPRUEFUNG gesamt: WARNUNG (Bilder: ...)")
    rows = operation.camera_check_table(progress)
    assert [r["label"] for r in rows] == ["Szene", "Wrist"]
    scene, wrist = rows
    assert scene["groups"]["licht"]["level"] == "warnung"
    assert scene["groups"]["licht"]["short"] == "Farbe R/G 0.98"
    assert "Helligkeit 133" in scene["groups"]["licht"]["detail"]   # auch die guten Werte
    assert scene["groups"]["lage"]["level"] == "ok"
    assert wrist["groups"]["lage"]["level"] == "warnung"
    assert wrist["groups"]["licht"]["short"] == "OK"


def test_table_from_old_text_lines():
    progress = operation.RolloutProgress()
    for line in LINES + ["KAMERAPRUEFUNG gesamt: WARNUNG (Bilder: ...)"]:
        progress.feed(line)
    assert progress.camera_groups is None
    scene, wrist = operation.camera_check_table(progress)
    assert scene["groups"]["licht"]["level"] == "warnung"
    assert scene["groups"]["licht"]["short"] == "Farbe R/G 0.98; Saettigung 42"
    assert scene["groups"]["lage"]["level"] == "ok"
    assert wrist["groups"]["lage"]["level"] == "ok"
    assert "Versatz 0.6 px" in wrist["groups"]["lage"]["detail"]


def test_skipped_check_has_no_table():
    progress = operation.RolloutProgress()
    progress.feed("KAMERAPRUEFUNG: uebersprungen (Platzhalter- oder Replay-Bilder)")
    assert operation.camera_check_table(progress) == []


# -- Qt (offscreen) -----------------------------------------------------------

def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return None
    return QApplication.instance() or QApplication([])


def test_camera_assignment_is_shared_between_views():
    app = _app()
    if app is None:
        return
    from bc.adapters import CameraDevice
    from bc.gui import cameras as cameras_module
    from bc.gui.runner import TaskRunner
    from bc.gui.widgets import CameraAssignmentView

    runner = TaskRunner()
    try:
        first, second = CameraAssignmentView(runner), CameraAssignmentView(runner)
        seen = []
        second.changed.connect(lambda: seen.append(second.assignment()))
        # Suchergebnis in einem Reiter: Geraete und Wahl im anderen
        device = CameraDevice("daheng", "SN1", "Daheng")
        inventory = cameras_module.Inventory([device] + list(first.inventory.devices))
        first._search_cancel = cancel = object()
        first._on_found(inventory, cancel)
        first.set_assignment({"wrist": "daheng:SN1", "scene": "sim"})
        assert second.assignment() == {"wrist": "daheng:SN1", "scene": "sim"}
        assert seen and seen[-1] == second.assignment()
        assert second.inventory is inventory
        # Bildrate ebenso, und zurueck in die andere Richtung
        rate = second._rates["wrist"]
        rate.setCurrentIndex(rate.findData(30.0))
        assert first.fps()["wrist"] == 30.0
        # Belegung: Vorschau wird geschlossen, laufende Fahrt blockiert
        closed = []
        share = first.share
        assert share is second.share
        share.claim("Vorschau", lambda: closed.append(1))
        assert share.take_over("Fahrt") == (["Vorschau"], [])
        assert closed == [1] and share.holders() == []
        share.claim("Fahrt")
        assert share.take_over("Vorschau") == ([], ["Fahrt"])
        share.free("Fahrt")
    finally:
        runner.shutdown()


def test_operation_tab_sections_and_camera_table(tmp_path):
    app = _app()
    if app is None:
        return
    from bc.gui import session as session_module
    from bc.gui.runner import TaskRunner
    from bc.gui.tab_operation import RIGHT_SECTIONS, OperationTab

    runner = TaskRunner()
    tab = OperationTab(session_module.Session(), runner)
    try:
        tab.workdir = tmp_path                       # gemerkte Anordnung nicht ins Repo
        assert list(tab._sections) == ["modell", "kameras_zuordnung", "fahrt_einstellungen",
                                       "test", "offline"] + list(RIGHT_SECTIONS)
        tab.resize(1600, 1000)
        tab.show()
        app.processEvents()
        # Zuklappen rechts: nur noch die Kopfzeile, und gemerkt
        tab._sections["kameras"].set_open(False)
        app.processEvents()
        assert tab._sections["kameras"].maximumHeight() < 60
        state = json.loads((tmp_path / "einstellungen" / "oberflaeche.local.json")
                           .read_text(encoding="utf-8"))
        assert state["betrieb"]["offen"]["kameras"] is False
        assert len(state["betrieb"]["rechts"]) == len(RIGHT_SECTIONS)
        tab._sections["kameras"].set_open(True)
        assert tab._sections["kameras"].maximumHeight() > 10000
        tab._sections["modell"].set_open(False)
        assert not tab._sections["modell"].frame.isVisible()
        # Kamerapruefung als Tabelle
        tab._progress = operation.RolloutProgress()
        tab._on_line(camera_check.to_json_line(_results()))
        tab._on_line("KAMERAPRUEFUNG gesamt: WARNUNG (Bilder: ...)")
        table = tab.camera_table
        assert table.isVisible() and table.rowCount() == 2
        assert table.item(0, 0).text() == "Szene"
        assert table.item(0, 1).text().endswith("Farbe R/G 0.98")
        assert table.item(1, 2).text().startswith("⚠")
        assert "Helligkeit 133" in table.item(0, 1).toolTip()
        assert tab.camera_line.text() == "Kameraprüfung: WARNUNG"
        tab.grab()
    finally:
        tab.shutdown()
        runner.shutdown()
