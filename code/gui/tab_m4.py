"""Tab "M4 Behavior Cloning": the GUI of person 4 (m4_behavior_cloning/bc/gui) inside ours.

Built like his own window (bc.gui.app.MainWindow): backend bar on top (connect, sim/Neura,
"Reale Anlage freigeben"), below it his mode tabs Systemcheck | Aufnahme | Training | Betrieb |
Konsole. Everything with torch/lerobot runs as a subprocess with his Python (common/m4.py).

Robot and top-down camera are shared with M2 / M1 (gui/robot_access.py): before his session
connects, before one of his scripts uses the robot or a camera and before he opens a Daheng camera
in this process, the hooks before_robot_use / before_camera_use are called - they may raise to
refuse, which his tabs show as "Start gescheitert".
"""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from common import m4

log = logging.getLogger(__name__)

# his scripts that connect to the Neura controller; apps/record.py, apps/infer.py and
# tests/run_all.py only with "--robot neura"
ROBOT_SCRIPTS = {"apps/teach.py", "tools/check_gripper.py", "tools/check_ik.py", "tools/check_kinematics.py",
                 "tools/check_rpc_latency.py", "tools/check_servo_stream.py", "tools/check_servo_timing.py",
                 "tools/check_sim_robot.py", "tools/check_trajectory_buffer.py", "tools/export_points.py",
                 "tools/import_points.py", "tools/probe_arm_buttons.py"}
CAMERA_SCRIPTS = {"apps/record.py", "apps/infer.py", "tools/check_cameras.py", "tools/check_daheng_api.py",
                  "tools/check_rectify.py"}


def _script(argv: list[str]) -> str:
    return next((a.replace("\\", "/") for a in argv if a.endswith(".py")), "")


def uses_robot(argv: list[str]) -> bool:
    args = [str(a) for a in argv]
    neura = "--robot=neura" in args or "--real-robot" in args or any(
        a == "--robot" and b == "neura" for a, b in zip(args, args[1:]))
    return _script(args) in ROBOT_SCRIPTS or neura


def uses_camera(argv: list[str]) -> bool:
    args = [str(a) for a in argv]
    return _script(args) in CAMERA_SCRIPTS or any("daheng" in a for a in args)


class M4Tab(QWidget):
    def __init__(self, bc_app, bc_session, bc_runner, parent: QWidget | None = None):
        super().__init__(parent)
        self.before_robot_use: Callable[[], None] | None = None
        self.before_camera_use: Callable[[], None] | None = None
        self.session = bc_session.Session()
        self.runner = bc_runner.TaskRunner(self)
        self._backend_neura = bc_session.BACKEND_NEURA
        self._hook_session()
        self.bar = bc_app.BackendBar(self.session)
        self.mode_tabs = bc_app.make_tabs(self.session, self.runner)
        self._argv: dict[int, list[str]] = {}       # id(tab) -> argv of its running script
        for tab in self.mode_tabs:
            self._hook_process(tab)
        self.tabs = QTabWidget()
        for tab in self.mode_tabs:
            self.tabs.addTab(tab, tab.title)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        layout = QVBoxLayout(self)
        layout.addWidget(self.bar)
        layout.addWidget(self.tabs, 1)
        self._closed = False

    # -- hooks into his session and scripts ---------------------------------------------
    def _hook_session(self) -> None:
        connect = self.session.connect

        def guarded_connect():
            if self.session.backend == self._backend_neura:
                self._claim_robot()
            return connect()
        self.session.connect = guarded_connect     # his BackendBar calls session.connect()

    def _hook_process(self, tab) -> None:
        process = getattr(tab, "process", None)
        if process is None:
            return
        start = process.start

        def guarded_start(argv, *args, **kwargs):
            argv = list(argv)
            if uses_robot(argv):
                self._claim_robot()
            if uses_camera(argv) and self.before_camera_use is not None:
                self.before_camera_use()
            self._argv[id(tab)] = argv
            return start(argv, *args, **kwargs)
        process.start = guarded_start

    def _claim_robot(self) -> None:
        if self.before_robot_use is not None:
            self.before_robot_use()

    def guard_daheng_open(self) -> None:
        """Called before M4 opens a Daheng camera in this process (see make_m4_tab)."""
        if self.before_camera_use is not None:
            self.before_camera_use()

    # -- robot access (gui/robot_access.py) -------------------------------------------------
    def robot_busy_reason(self) -> str | None:
        """What of M4 uses the robot right now; None = free to take over."""
        for tab in self.mode_tabs:
            process = getattr(tab, "process", None)
            if process is not None and process.running:
                if uses_robot(self._argv.get(id(tab), [])):
                    return f"{tab.title}: Skript läuft"
                continue
            reason = tab.busy_reason()
            if reason and self.session.connected:
                return f"{tab.title}: {reason}"
        return None

    def release_robot(self) -> bool:
        """Disconnect his session if it is connected; True if it was."""
        if not self.session.connected:
            return False
        self.bar.disconnect_backend()
        return True

    # -- tab protocol of our main window ----------------------------------------------------
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
    try:
        m4.prepare()
        from bc.adapters import cam_daheng
        from bc.gui import app as bc_app
        from bc.gui import runner as bc_runner
        from bc.gui import session as bc_session
        tab = M4Tab(bc_app, bc_session, bc_runner)
    except Exception:
        log.warning("M4 Behavior Cloning konnte nicht geladen werden - GUI startet ohne M4.", exc_info=True)
        return None
    _guard_daheng(cam_daheng, tab)
    if not m4.has_own_env():
        log.warning("M4: keine eigene Umgebung (%s) - Training und Inferenz brauchen sie, "
                    "einrichten mit setup_m4.bat", m4.BC_VENV_PYTHON)
    return tab


def _guard_daheng(cam_daheng, tab: M4Tab) -> None:
    """His camera previews run in this process: let M1 release the top-down camera first.
    Our own top-down camera uses the same class with name "topdown" and is not guarded."""
    cls = cam_daheng.DahengCamera
    cls._m4_tab = tab
    if getattr(cls, "_m4_guarded", False):
        return
    open_ = cls.open

    def guarded_open(cam):
        if cam.name != "topdown" and cls._m4_tab is not None:
            try:
                cls._m4_tab.guard_daheng_open()
            except Exception as e:      # his previews run in worker threads and expect CameraError
                raise cam_daheng.CameraError(str(e)) from e
        return open_(cam)
    cls.open = guarded_open
    cls._m4_guarded = True
