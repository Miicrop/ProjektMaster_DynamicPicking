"""Tab "M4 Behavior Cloning": the GUI of person 4 (m4_behavior_cloning/bc/gui) inside ours.

Built like his own window (bc.gui.app.MainWindow): backend bar on top (connect, sim/Neura,
"Reale Anlage freigeben"), below it his mode tabs Systemcheck | Aufnahme | Training | Betrieb |
Konsole. His code stays unchanged; everything with torch/lerobot runs as a subprocess with the
Python from BC_PYTHON (default: m4_behavior_cloning/.venv, see its INTEGRATION.md).

M2 and M4 each connect to the robot on their own - never connect both at the same time.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

log = logging.getLogger(__name__)

CODE_DIR = Path(__file__).resolve().parents[1]
BC_DIR = CODE_DIR / "m4_behavior_cloning"
BC_VENV_PYTHON = BC_DIR / ".venv" / "Scripts" / "python.exe"
NEURAPY_DIR = CODE_DIR / "m2_robot_control" / "vendor"   # same neurapy v5.0.8 as his


class M4Tab(QWidget):
    def __init__(self, bc_app, bc_session, bc_runner, parent: QWidget | None = None):
        super().__init__(parent)
        self.session = bc_session.Session()
        self.runner = bc_runner.TaskRunner(self)
        self.bar = bc_app.BackendBar(self.session)
        self.mode_tabs = bc_app.make_tabs(self.session, self.runner)
        self.tabs = QTabWidget()
        for tab in self.mode_tabs:
            self.tabs.addTab(tab, tab.title)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        layout = QVBoxLayout(self)
        layout.addWidget(self.bar)
        layout.addWidget(self.tabs, 1)
        self._closed = False

    def refresh(self) -> None:
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()

    def shutdown(self) -> None:
        """Stop cameras, servo loop and subprocesses; safe to call twice."""
        if self._closed:
            return
        self._closed = True
        for tab in self.mode_tabs:
            try:
                tab.shutdown()
            except Exception:
                log.exception("M4: Herunterfahren von %s gescheitert", tab.title)
        self.runner.shutdown()
        self.session.close()


def make_m4_tab() -> M4Tab | None:
    """M4 tab, or None (with a log warning) if m4_behavior_cloning is missing or does not import."""
    if not (BC_DIR / "bc" / "gui" / "app.py").is_file():
        log.warning("M4 nicht gefunden (%s) - GUI startet ohne M4.", BC_DIR)
        return None
    os.environ.setdefault("BC_NEURAPY_DIR", str(NEURAPY_DIR))
    if BC_VENV_PYTHON.is_file():
        os.environ.setdefault("BC_PYTHON", str(BC_VENV_PYTHON))
    if str(BC_DIR) not in sys.path:
        sys.path.insert(0, str(BC_DIR))
    try:
        from bc.gui import app as bc_app
        from bc.gui import runner as bc_runner
        from bc.gui import session as bc_session
        tab = M4Tab(bc_app, bc_session, bc_runner)
    except Exception:
        log.warning("M4 Behavior Cloning konnte nicht geladen werden - GUI startet ohne M4.", exc_info=True)
        return None
    if "BC_PYTHON" not in os.environ:
        log.warning("M4: keine BC-Umgebung (%s) - Training und Inferenz brauchen sie, "
                    "siehe m4_behavior_cloning/INTEGRATION.md.", BC_VENV_PYTHON)
    return tab
