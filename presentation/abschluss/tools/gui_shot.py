"""Screenshots der echten GUI für Szene 2.4 (auto.png) und 4.7 (robot.png) → public/img/gui/*.png.

Startet die GUI ohne Bildschirm (Qt offscreen) mit einer Kopie von system.yaml, lässt im Tab
„Ablauf“ drei Zyklen laufen (Wiedergabe der Testfotos + Neura-Simulator) und fotografiert das Fenster;
dann Tab „M2 Roboter“ mit dem Simulator verbunden, erste Schritte der Checkliste erledigt.
Logs landen in einem Temp-Ordner, code/logs bleibt unberührt.
Aufruf mit dem Projekt-venv:  ..\\..\\.venv\\Scripts\\python tools\\gui_shot.py
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"))  # offscreen hat sonst keine Schriften

HERE = Path(__file__).resolve().parent.parent
CODE = HERE.parent.parent / "code"
sys.path.insert(0, str(CODE))

import yaml  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from common.config import DEFAULT_CONFIG  # noqa: E402
from gui.app import MainWindow  # noqa: E402
from gui.config_store import ConfigStore  # noqa: E402
from gui.session import Session  # noqa: E402

OUT = HERE / "public" / "img" / "gui"
PHOTO_WORKSPACE = CODE / "m1_vision_topdown" / "tests" / "data" / "workspace.yaml"
CYCLES = 3


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(DEFAULT_CONFIG, tmp / "system.yaml")
    store = ConfigStore(tmp / "system.yaml")
    store.data["logging"]["cycle_dir"] = str(tmp / "logs")
    # Wiedergabebilder zeigen die alte Platte → deren Arbeitsraum (wie gui/tests)
    store.data["workspace"].update(yaml.safe_load(PHOTO_WORKSPACE.read_text(encoding="utf-8")))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    s = Session(store)
    s.m3.reader.read = lambda roi, pattern: ("69420", 0.99)  # ohne OCR-Modell
    w = MainWindow(s)
    w.resize(1600, 980)
    w.show()

    def wait(cond, timeout=120):
        end = time.time() + timeout
        while time.time() < end and not cond():
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        return cond()

    auto = w.tab_auto
    auto.pause.setValue(0)
    for n in range(1, CYCLES + 1):
        auto.btn_one.click()
        if not wait(lambda: auto.table.rowCount() == n and not auto.running):
            raise SystemExit(f"Zyklus {n} nicht fertig")
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    # Temp-Pfade im Bild durch die echten ersetzen
    auto.counter.setText(auto.counter.text().replace(str(tmp / "logs"), "logs"))
    w.statusBar().showMessage("Konfiguration: code/config/system.yaml")
    app.processEvents()
    w.grab().save(str(OUT / "auto.png"))
    print(f"→ {OUT / 'auto.png'}  ({auto.counts})")

    # Tab M2 für Szene 4.7: mit dem Simulator verbunden, die ersten Schritte der Checkliste erledigt
    m2 = w.tab_m2
    w.tabs.setCurrentWidget(m2)
    m2.mode.setCurrentIndex(0)
    m2.connect_robot()
    if not wait(lambda: s.robot is not None and not w.runner.busy("robot")):
        raise SystemExit("Simulator nicht verbunden")
    for fn in (m2.steps.info, m2.steps.home, lambda: m2.jog("z", +1)):
        fn()
        wait(lambda: not w.runner.busy("robot"))
    m2.refresh_status()
    wait(lambda: not w.runner.busy("robot"))
    for _ in range(30):
        app.processEvents()
        time.sleep(0.02)
    w.grab().save(str(OUT / "robot.png"))
    print(f"→ {OUT / 'robot.png'}")
    m2.disconnect_robot()
    wait(lambda: s.robot is None)

    store.dirty = False
    w.close()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
