"""Main window: one tab per module + automatic cycle + settings, log panel at the bottom.

    python -m gui                 # all tabs
    python -m gui --tab m1        # start directly in a tab: auto | m1 | m2 | m3 | settings
"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QMessageBox, QTabWidget

from gui.session import Session
from gui.tab_auto import AutoTab
from gui.tab_robot import RobotTab
from gui.tab_settings import SettingsTab
from gui.tab_vision import M1Tab, M3Tab
from gui.widgets import LogView, QtLogHandler, TaskRunner

TABS = ["auto", "m1", "m2", "m3", "settings"]


class MainWindow(QMainWindow):
    def __init__(self, session: Session | None = None, start_tab: str = "auto"):
        super().__init__()
        self.s = session or Session()
        self.runner = TaskRunner()
        self.setWindowTitle("Dynamisches Greifen mit Sichtprüfung")
        self.resize(1500, 950)

        self.tab_auto = AutoTab(self.s, self.runner)
        self.tab_m1 = M1Tab(self.s, self.runner)
        self.tab_m2 = RobotTab(self.s, self.runner)
        self.tab_m3 = M3Tab(self.s, self.runner)
        self.tab_settings = SettingsTab(self.s.store)
        self.tabs = QTabWidget()
        for w, title in ((self.tab_auto, "Ablauf (automatisch)"), (self.tab_m1, "M1 Erkennung"),
                         (self.tab_m2, "M2 Roboter"), (self.tab_m3, "M3 Prüfung"),
                         (self.tab_settings, "Einstellungen")):
            self.tabs.addTab(w, title)
        self.tabs.setCurrentIndex(TABS.index(start_tab))
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)
        self.tab_settings.changed.connect(self._config_changed)

        # log dock
        self.log_view = LogView()
        self.log_handler = QtLogHandler()
        self.log_handler.emitter.message.connect(self.log_view.append_record)
        logging.getLogger().addHandler(self.log_handler)
        dock = QDockWidget("Log", self)
        dock.setWidget(self.log_view)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.resizeDocks([dock], [160], Qt.Orientation.Vertical)

        save = QAction("Einstellungen speichern", self, shortcut=QKeySequence.StandardKey.Save)
        save.triggered.connect(self.tab_settings.save)
        self.addAction(save)
        self.statusBar().showMessage(f"Konfiguration: {self.s.store.path}")

    def _tab_changed(self, index: int) -> None:
        w = self.tabs.widget(index)
        if hasattr(w, "refresh"):
            w.refresh()

    def _config_changed(self) -> None:
        self.tab_m2.refresh()
        self.tab_auto.map.update()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.s.store.dirty:
            answer = QMessageBox.question(
                self, "Beenden", "Einstellungen wurden geändert. Speichern?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                self.s.store.save()
        self.tab_auto._stop_after_cycle.set()
        for tab in (self.tab_m1, self.tab_m3):
            tab.timer.stop()
        self.tab_m2.poll.stop()
        logging.getLogger().removeHandler(self.log_handler)
        self.runner.shutdown()
        self.s.close()
        event.accept()


def main() -> None:
    ap = argparse.ArgumentParser(description="GUI for the grasping and inspection cell")
    ap.add_argument("--tab", choices=TABS, default="auto")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(start_tab=args.tab)
    win.show()
    sys.exit(app.exec())
