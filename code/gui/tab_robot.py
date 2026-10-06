"""Tab M2: main robot control - connect, jog, STOP, and the commissioning steps as sub-pages
(Erste Schritte, Achsentest, Posen teachen, Kalibrierung, Zeigetest; see gui/robot_pages.py)."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from common.config import robot_target
from gui.robot_pages import AxesPage, CalibPage, PointPage, StepsPage, TeachPage
from gui.session import Session
from gui.widgets import BAD, GOOD, NEUTRAL, Badge, RobotMapView, TaskRunner, confirm_motion

MODES = [("Simulator", "sim"), ("Neura-VM", "vm"), ("Echter Roboter", "real")]
HOST_KEY = {"vm": "vm_host", "real": "host"}   # config key of the address per mode (sim: local fake)
JOG_PRESETS = [1, 5, 10, 20, 50]               # quick step selection, mm (rz: deg)


class StopButton(QPushButton):
    def __init__(self, text: str = "STOPP", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setMinimumHeight(56)
        self.setStyleSheet("QPushButton{background:#c62828;color:white;font-size:18px;font-weight:bold;"
                           "border-radius:6px} QPushButton:pressed{background:#8e0000}")
        self.setToolTip("Software-Stopp der Roboterbewegung. Ersetzt NICHT den Not-Halt!")


class RobotTab(QWidget):
    def __init__(self, session: Session, runner: TaskRunner, parent: QWidget | None = None):
        super().__init__(parent)
        self.s, self.runner = session, runner
        cfg = session.cfg
        self.motion_buttons: list[QPushButton] = []

        # connection
        self.mode = QComboBox()
        for text, kind in MODES:
            self.mode.addItem(text, kind)
        self.host = QLineEdit()
        self.host.editingFinished.connect(self._store_host)
        self.mode.currentIndexChanged.connect(self._show_host)
        self.btn_connect = QPushButton("Verbinden")
        self.btn_disconnect = QPushButton("Trennen")
        self.status = Badge("getrennt")
        self.btn_connect.clicked.connect(self.connect_robot)
        self.btn_disconnect.clicked.connect(self.disconnect_robot)
        con = QGroupBox("Verbindung")
        cl = QFormLayout(con)
        cl.addRow("Modus", self.mode)
        cl.addRow("IP Steuerung", self.host)
        row = QHBoxLayout()
        row.addWidget(self.btn_connect)
        row.addWidget(self.btn_disconnect)
        cl.addRow(row)
        cl.addRow(self.status)

        # status
        self.lbl_robot, self.lbl_mode, self.lbl_pose, self.lbl_err = QLabel("–"), QLabel("–"), QLabel("–"), QLabel("–")
        self.lbl_pose.setMinimumHeight(34)
        self.lbl_err.setWordWrap(True)
        st = QGroupBox("Status")
        sl = QFormLayout(st)
        sl.addRow("Roboter", self.lbl_robot)
        self.lbl_ready = QLabel("–")
        sl.addRow("Freigabe", self.lbl_ready)
        sl.addRow("Teach-Modus", self.lbl_mode)
        sl.addRow("TCP-Pose", self.lbl_pose)
        sl.addRow("Meldung", self.lbl_err)

        # motion
        self.override = QDoubleSpinBox(minimum=0.05, maximum=1.0, singleStep=0.05, decimals=2)
        self.override.setValue(float(cfg["robot"]["override"]))
        self.override.setSuffix("  (Anteil v_max)")
        self.override.valueChanged.connect(self.set_override)
        buttons = {
            "Home": lambda: self.run("Home anfahren", lambda r: r.home()),
            "Greifer auf": lambda: self.run("Greifer öffnen", lambda r: r.gripper(close=False), moves=False),
            "Greifer zu": lambda: self.run("Greifer schließen", lambda r: r.gripper(close=True), moves=False),
        }
        mv = QGroupBox("Bewegen")
        ml = QGridLayout(mv)
        ml.addWidget(QLabel("Override"), 0, 0)
        ml.addWidget(self.override, 0, 1, 1, 2)
        for i, (text, fn) in enumerate(buttons.items()):
            b = QPushButton(text)
            b.clicked.connect(fn)
            ml.addWidget(b, 1, i)
            self.needs_robot(b)
        self.stop = StopButton()
        self.stop.clicked.connect(self.emergency_stop)
        ml.addWidget(self.stop, 2, 0, 1, 3)
        self.btn_release = QPushButton("Freigeben (nach STOPP / Fehler)")
        self.btn_release.setToolTip("Bereitet den Roboter wieder vor (init_program). Fährt nicht.")
        self.btn_release.clicked.connect(self.release_robot)
        ml.addWidget(self.btn_release, 3, 0, 1, 3)
        self.needs_robot(self.btn_release)

        # jog: small relative linear steps in the base frame
        self.jog_step = QDoubleSpinBox(minimum=0.5, maximum=100.0, singleStep=1.0, decimals=1)
        self.jog_step.setValue(10.0)
        self.jog_step.setSuffix(" mm")
        self.jog_step_deg = QDoubleSpinBox(minimum=0.5, maximum=15.0, singleStep=1.0, decimals=1)
        self.jog_step_deg.setValue(5.0)
        self.jog_step_deg.setSuffix(" °")
        self.jog_step_deg.setToolTip("Schritt für ±rz (max. 15°)")
        jg = QGroupBox("Joggen (relativ, Basis-KS, langsam)")
        jl = QGridLayout(jg)
        jl.addWidget(QLabel("Schritt"), 0, 0)
        jl.addWidget(self.jog_step, 0, 1, 1, 2)
        jl.addWidget(self.jog_step_deg, 0, 3)
        presets = QHBoxLayout()
        for v in JOG_PRESETS:
            b = QPushButton(str(v))
            b.setMaximumWidth(44)
            b.clicked.connect(lambda _=False, x=v: self.jog_step.setValue(x))
            presets.addWidget(b)
        jl.addLayout(presets, 1, 0, 1, 4)
        for col, axis in enumerate(("x", "y", "z", "rz")):
            for row_i, sign in ((2, +1), (3, -1)):
                b = QPushButton(f"{'+' if sign > 0 else '−'}{axis.upper()}")
                b.setMinimumHeight(34)
                b.clicked.connect(lambda _=False, a=axis, sg=sign: self.jog(a, sg))
                jl.addWidget(b, row_i, col)
                self.needs_robot(b)

        # commissioning pages
        self.map = RobotMapView(cfg)
        self.pages = QTabWidget()
        self.steps = StepsPage(self)
        self.page_axes = AxesPage(self)
        self.page_teach = TeachPage(self)
        self.page_calib = CalibPage(self)
        self.page_point = PointPage(self)
        self._page_index = {}
        for key, w, title in (("steps", self.steps, "Erste Schritte"), ("axes", self.page_axes, "Achsentest"),
                              ("teach", self.page_teach, "Posen teachen"), ("calib", self.page_calib, "Kalibrierung"),
                              ("point", self.page_point, "Zeigetest")):
            self._page_index[key] = self.pages.addTab(w, title)

        left = QVBoxLayout()
        for w in (con, st, mv, jg):
            left.addWidget(w)
        left.addStretch()
        right = QVBoxLayout()
        right.addWidget(self.map, 2)
        right.addWidget(self.pages, 3)
        layout = QHBoxLayout(self)
        lw = QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(420)
        layout.addWidget(lw)
        layout.addLayout(right, 1)

        self.poll = QTimer(self, interval=1000)
        self.poll.timeout.connect(self.refresh_status)
        self.refresh()
        self._show_host()
        self._set_connected(False)

    # -- helpers ----------------------------------------------------------------------
    @property
    def is_real(self) -> bool:
        return self.mode.currentData() == "real"

    def needs_robot(self, *buttons: QPushButton) -> None:
        """Buttons that are only enabled while a robot is connected."""
        self.motion_buttons.extend(buttons)

    def show_page(self, key: str) -> None:
        self.pages.setCurrentIndex(self._page_index[key])

    def message(self, text: str, error: bool = False) -> None:
        self.lbl_err.setText(f"<span style='color:{BAD}'>{text}</span>" if error else text)

    def _show_host(self) -> None:
        key = HOST_KEY.get(self.mode.currentData())
        self.host.setText(str(self.s.cfg["robot"][key]) if key else "127.0.0.1 (lokal)")
        self.host.setEnabled(key is not None and self.mode.isEnabled())

    def _store_host(self) -> None:
        key = HOST_KEY.get(self.mode.currentData())
        if key:
            self.s.store.set(["robot", key], self.host.text().strip())

    def _set_connected(self, on: bool) -> None:
        for b in self.motion_buttons:
            b.setEnabled(on)
        self.btn_disconnect.setEnabled(on)
        self.btn_connect.setEnabled(not on)
        self.mode.setEnabled(not on)
        self.host.setEnabled(not on and self.mode.currentData() in HOST_KEY)
        if on:
            self.status.show_state(f"verbunden ({self.mode.currentText()})", GOOD)
            self.poll.start()
        else:
            self.status.show_state("getrennt", NEUTRAL)
            self.poll.stop()

    def refresh(self) -> None:
        """Pose table, marker table and map from the config (also after edits in the settings tab)."""
        self.page_teach.refresh()
        self.page_calib.refresh()
        self.map.update()

    # -- actions -------------------------------------------------------------------
    def connect_robot(self) -> None:
        kind = self.mode.currentData()
        self.status.show_state("verbinde …", NEUTRAL)
        self.runner.submit(lambda: self.s.connect_robot(kind), lambda _: (self._set_connected(True),
                                                                           self.refresh_status()),
                           lambda e: (self.status.show_state("Fehler", BAD), self._error(e)), pool="robot")

    def disconnect_robot(self) -> None:
        self.runner.submit(self.s.disconnect_robot, lambda _: self._set_connected(False), pool="robot")

    def _error(self, e: Exception) -> None:
        from gui.widgets import show_error
        self.message(str(e), error=True)
        show_error(e)

    def run(self, what: str, fn, on_done=None, moves: bool = True, on_error=None) -> None:
        """Run fn(robot) in the robot pool (one task at a time); moves=True asks first on the real robot."""
        robot = self.s.robot
        if robot is None:
            return
        if moves and self.is_real and not confirm_motion(self, what):
            return
        self.message(f"läuft: {what} …")

        def done(value):
            self.message(f"fertig: {what}")
            self.refresh_status()
            if on_done is not None:
                on_done(value)

        def failed(e):
            if on_error is not None:
                on_error(e)
            self._error(e)
        self.runner.submit(lambda: fn(robot), done, failed, pool="robot")

    def pick_test(self, robot) -> None:
        target = robot_target(self.s.cfg, "inspection")
        robot.home()
        robot.pick(target)
        robot.place(target)
        robot.home()

    def jog(self, axis: str, sign: int) -> None:
        step = sign * (self.jog_step_deg if axis == "rz" else self.jog_step).value()
        key = {"x": "dx_mm", "y": "dy_mm", "z": "dz_mm", "rz": "drz_deg"}[axis]
        unit = "°" if axis == "rz" else " mm"
        self.run(f"Relativ {axis.upper()} {step:+.1f}{unit} (Basis-Koordinatensystem)",
                 lambda r: r.jog(**{key: step}))

    def set_override(self, v: float) -> None:
        self.s.store.set(["robot", "override"], round(v, 2))
        if self.s.robot is not None:
            self.run(f"Override {v:.2f}", lambda r: r.r.set_override(round(v, 2)), moves=False)

    def emergency_stop(self) -> None:
        self.runner.submit(self.s.emergency_stop, lambda _: (self.message(
            "<b>STOPP gesendet – zum Weiterarbeiten 'Freigeben'</b>", error=True), self._show_ready()), pool="stop")

    def release_robot(self) -> None:
        self.run("Freigeben", lambda r: r.reset(), moves=False)

    def _show_ready(self) -> None:
        robot = self.s.robot
        stopped = robot is not None and getattr(robot, "stopped", False)
        self.lbl_ready.setText(f"<b style='color:{BAD}'>gestoppt – Freigeben drücken</b>" if stopped
                               else f"<span style='color:{GOOD}'>bereit</span>" if robot else "–")

    def refresh_status(self) -> None:
        robot = self.s.robot
        if robot is None or self.runner.busy("robot"):
            return

        def read():
            r = robot.open_client()
            return (f"{r.robot_name} ({r.dof} Achsen), v{str(r.version).lstrip('v')}",
                    r.is_robot_in_teach_mode(), robot.current_pose(), r.get_errors())

        def show(v):
            name, teach, p, errors = v
            self.lbl_robot.setText(name)
            self.lbl_mode.setText("ja" if teach else "nein (Automatik)")
            self.lbl_pose.setText(f"x {p.x_mm:.1f}  y {p.y_mm:.1f}  z {p.z_mm:.1f} mm\n"
                                  f"rx {p.rx_deg:.1f}  ry {p.ry_deg:.1f}  rz {p.rz_deg:.1f}°")
            if errors:
                self.message(str(errors), error=True)
            self.map.set_tcp(p.x_mm, p.y_mm)
            self._show_ready()
        self.runner.submit(read, show, lambda e: self.lbl_err.setText(str(e)), pool="robot")
