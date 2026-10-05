import os
import shutil
import time
from pathlib import Path

import pytest
import yaml

from common.config import DEFAULT_CONFIG
from gui.config_store import ConfigStore, parse_value
from m2_robot_control.robot import VENDOR_DIR

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

needs_neurapy = pytest.mark.skipif(
    not (VENDOR_DIR / "neurapy" / "robot.py").exists(),
    reason="vendor/neurapy/robot.py not present (proprietary, excluded from the public repo) "
           "- get it from your Neura contact for tests using the 'sim' robot")


PHOTO_WORKSPACE = Path(__file__).parents[2] / "m1_vision_topdown" / "tests" / "data" / "workspace.yaml"


@pytest.fixture
def store(tmp_path):
    f = tmp_path / "system.yaml"
    shutil.copy(DEFAULT_CONFIG, f)
    return ConfigStore(f)


def use_photo_workspace(store):
    """Replay images show the old board -> use its workspace section."""
    store.data["workspace"].update(yaml.safe_load(PHOTO_WORKSPACE.read_text(encoding="utf-8")))


# --- config store (no Qt) ----------------------------------------------------------

def test_roundtrip_is_lossless(store):
    before = store.path.read_text(encoding="utf-8")
    store.save()
    assert store.path.read_text(encoding="utf-8") == before


def test_edit_keeps_comments_and_flow_lists(store):
    store.set(["robot", "poses", "inspection"], [1.0, 2.0, 3.0, 180.0, 0.0, 180.0])
    store.set(["inspection", "hole_nominal_mm"], 8.5)
    store.save()
    text = store.path.read_text(encoding="utf-8")
    assert "    inspection: [1.0, 2.0, 3.0, 180.0, 0.0, 180.0]" in text
    assert "hole_nominal_mm: 8.5" in text
    assert "# IP printed on the robot base" in text
    assert ConfigStore(store.path).get(["inspection", "hole_nominal_mm"]) == 8.5


def test_reload_keeps_dict_identity(store):
    data = store.data
    store.set(["robot", "override"], 0.9)
    store.reload()
    assert store.data is data and data["robot"]["override"] == 0.2 and not store.dirty


def test_parse_value():
    assert parse_value("3", 1.5) == 3.0 and isinstance(parse_value("3", 1.5), float)
    assert parse_value("[1, 2]", [0.0, 0.0]) == [1, 2]
    assert parse_value("white_frame", "auto") == "white_frame"
    with pytest.raises(ValueError):
        parse_value("abc", 1.0)
    with pytest.raises(ValueError):
        parse_value("5", [1.0, 2.0])


# --- session: modules individually and the full cycle (no Qt) --------------------

@needs_neurapy
def test_session_modules_and_cycle(store, tmp_path):
    from gui.session import Session
    store.data["logging"]["cycle_dir"] = str(tmp_path / "logs")
    use_photo_workspace(store)
    s = Session(store)
    try:
        r1 = s.analyze_m1(s.grab("m1", "replay"))
        assert r1.part.chamfer_found
        s.m3.reader.read = lambda roi, pattern: ("69420", 0.99)   # skip OCR model
        d3 = s.analyze_m3(s.grab("m3", "replay"))
        assert d3.result.is_good
        orch = s.build_orchestrator("replay", "sim", "replay")
        result = orch.run_cycle()
        assert result.ok and result.inspection.is_good and result.duration_s > 0
        assert s.robot.sim_state.gripper_closed is False
    finally:
        s.close()


def test_logbook_csv(tmp_path):
    from common.config import load_config
    from common.interfaces import InspectionResult, ObjectPose
    from orchestrator import logbook
    from orchestrator.state_machine import CycleResult
    cfg = load_config()
    cfg["logging"]["cycle_dir"] = str(tmp_path)
    r = CycleResult(1, ObjectPose(1, 2, 0, 3), InspectionResult("69420", 9.8, True, True), duration_s=1.5)
    f = logbook.append_csv(cfg, r)
    logbook.append_csv(cfg, r)
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("time;cycle") and len(lines) == 3 and "69420" in lines[1]


# --- Qt window (offscreen) -----------------------------------------------------

@needs_neurapy
def test_main_window_smoke(store, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from gui.app import MainWindow
    from gui.session import Session

    store.data["logging"]["cycle_dir"] = str(tmp_path / "logs")
    use_photo_workspace(store)
    app = QApplication.instance() or QApplication([])
    s = Session(store)
    s.m3.reader.read = lambda roi, pattern: ("69420", 0.99)
    w = MainWindow(s)
    w.show()

    def wait(cond, timeout=60):
        end = time.time() + timeout
        while time.time() < end and not cond():
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        return cond()

    w.tab_m1.grab()
    assert wait(lambda: w.tab_m1.form.rowCount() > 0 and not w.runner.busy("vision"))
    assert "gefunden" in w.tab_m1.badge.text()

    w.tab_auto.pause.setValue(0)
    w.tab_auto.btn_one.click()
    assert wait(lambda: w.tab_auto.table.rowCount() == 1 and not w.tab_auto.running)
    assert w.tab_auto.counts["good"] == 1

    # regression: NOT-STOPP -> Fehler quittieren -> new cycle must work
    w.tab_auto.btn_stop.click()
    assert wait(lambda: s.robot.stopped and not w.runner.busy("stop"))
    w.tab_auto.btn_one.click()                      # refused while stopped
    assert wait(lambda: not w.tab_auto.running and "quittieren" in w.tab_auto.badge.text())
    w.tab_auto.btn_reset.click()
    assert wait(lambda: not s.robot.stopped and not w.runner.busy("robot"))
    w.tab_auto.btn_one.click()
    assert wait(lambda: w.tab_auto.table.rowCount() == 2 and not w.tab_auto.running)
    assert w.tab_auto.counts["good"] == 2

    # edit a setting through the tree
    tree = w.tab_settings.tree
    item = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
            if tree.topLevelItem(i).text(0) == "robot"][0]
    override = [item.child(i) for i in range(item.childCount()) if item.child(i).text(0) == "override"][0]
    override.setText(1, "0.35")
    assert store.data["robot"]["override"] == 0.35 and store.dirty

    store.dirty = False
    w.close()


def test_robot_tab_host_field_follows_mode(store):
    """Neura-VM and real robot keep separate addresses; editing one must not change the other."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from gui.app import MainWindow
    from gui.session import Session

    app = QApplication.instance() or QApplication([])  # noqa: F841
    store.data["robot"]["host"] = "10.0.0.1"
    store.data["robot"]["vm_host"] = "10.0.0.2"
    w = MainWindow(Session(store))
    tab = w.tab_m2
    tab.mode.setCurrentIndex(tab.mode.findData("vm"))
    assert tab.host.text() == "10.0.0.2" and tab.host.isEnabled()
    tab.host.setText("10.0.0.3")
    tab.host.editingFinished.emit()
    assert store.data["robot"]["vm_host"] == "10.0.0.3" and store.data["robot"]["host"] == "10.0.0.1"
    tab.mode.setCurrentIndex(tab.mode.findData("real"))
    assert tab.host.text() == "10.0.0.1"
    tab.mode.setCurrentIndex(tab.mode.findData("sim"))
    assert not tab.host.isEnabled()

    store.dirty = False
    w.close()


def test_same_camera_index_for_two_modules_is_refused(store, monkeypatch):
    import gui.session as session_mod
    monkeypatch.setattr(session_mod, "open_source", lambda cfg, section, kind: object())
    store.data["topdown_camera"]["source"] = 0
    store.data["inspection_camera"]["source"] = 0
    s = session_mod.Session(store)
    s.camera("m1", "camera")
    with pytest.raises(RuntimeError, match="schon"):
        s.camera("m3", "camera")
    s._cameras.clear()


def test_logbook_saves_trace_steps(tmp_path):
    import numpy as np
    from common.config import load_config
    from common.trace import Trace
    from orchestrator import logbook
    from orchestrator.state_machine import CycleResult
    cfg = load_config()
    cfg["logging"]["cycle_dir"] = str(tmp_path)
    trace = Trace()
    trace.add("mask", np.zeros((4, 4), np.uint8))

    class Det:                       # only a trace, no final debug image (e.g. detection failed)
        last_result, last_trace = None, trace

    out = logbook.save_images(cfg, CycleResult(7), Det(), object())
    assert [f.name for f in (out / "steps").iterdir()] == ["m1_01_mask.png"]
