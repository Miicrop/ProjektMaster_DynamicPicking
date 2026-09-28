"""Tab M2: connect to the robot (simulator or real), move, operate the gripper, teach poses."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from common.config import robot_target
from gui.session import Session
from gui.widgets import BAD, GOOD, NEUTRAL, Badge, RobotMapView, TaskRunner, confirm_motion

MODES = [("Simulator", "sim"), ("Echter Roboter", "real")]


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

        # connection
        self.mode = QComboBox()
        for text, kind in MODES:
            self.mode.addItem(text, kind)
        self.host = QLineEdit(str(cfg["robot"]["host"]))
        self.host.editingFinished.connect(lambda: self.s.store.set(["robot", "host"], self.host.text().strip()))
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
        sl.addRow("Fehler", self.lbl_err)

        # motion
        self.override = QDoubleSpinBox(minimum=0.05, maximum=1.0, singleStep=0.05, decimals=2)
        self.override.setValue(float(cfg["robot"]["override"]))
        self.override.setSuffix("  (Anteil v_max)")
        self.override.valueChanged.connect(self.set_override)
        self.buttons = {
            "Home": lambda: self.move("Home anfahren", lambda r: r.home()),
            "Greifer auf": lambda: self.robot_call(lambda r: r.r.release(), "Greifer geöffnet"),
            "Greifer zu": lambda: self.robot_call(lambda r: r.r.grasp(), "Greifer geschlossen"),
            "Pick-Test Prüfposition": lambda: self.move(
                "Greifen und Ablegen an der Prüfposition", self._pick_test),
        }
        mv = QGroupBox("Bewegen")
        ml = QGridLayout(mv)
        ml.addWidget(QLabel("Override"), 0, 0)
        ml.addWidget(self.override, 0, 1)
        self.motion_buttons = []
        for i, (text, fn) in enumerate(self.buttons.items()):
            b = QPushButton(text)
            b.clicked.connect(fn)
            ml.addWidget(b, 1 + i // 2, i % 2)
            self.motion_buttons.append(b)
        self.stop = StopButton()
        self.stop.clicked.connect(self.emergency_stop)
        ml.addWidget(self.stop, 4, 0, 1, 2)
        self.btn_release = QPushButton("Freigeben (nach STOPP / Fehler)")
        self.btn_release.setToolTip("Bereitet den Roboter wieder vor (init_program). Fährt nicht.")
        self.btn_release.clicked.connect(self.release_robot)
        ml.addWidget(self.btn_release, 5, 0, 1, 2)
        self.motion_buttons.append(self.btn_release)

        # axis test: small relative steps in the base frame
        self.jog_step = QDoubleSpinBox(minimum=1.0, maximum=100.0, singleStep=10.0, decimals=0)
        self.jog_step.setValue(20.0)
        self.jog_step.setSuffix(" mm / °")
        jg = QGroupBox("Achsen-Test (relativ, Basis-KS, langsam)")
        jl = QGridLayout(jg)
        jl.addWidget(QLabel("Schritt"), 0, 0)
        jl.addWidget(self.jog_step, 0, 1, 1, 3)
        for col, axis in enumerate(("x", "y", "z", "rz")):
            for row, sign in ((1, +1), (2, -1)):
                b = QPushButton(f"{'+' if sign > 0 else '−'}{axis.upper()}")
                b.clicked.connect(lambda _=False, a=axis, sg=sign: self.jog(a, sg))
                jl.addWidget(b, row, col)
                self.motion_buttons.append(b)

        # poses
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Pose", "x", "y", "z", "rx", "ry", "rz"])
        self.table.verticalHeader().setVisible(False)
        self.pose_name = QComboBox()
        self.btn_teach = QPushButton("Aktuelle TCP-Pose übernehmen →")
        self.btn_goto = QPushButton("Pose anfahren (über Vorposition)")
        self.btn_teach.clicked.connect(self.teach)
        self.btn_goto.clicked.connect(self.goto_pose)
        ps = QGroupBox("Posen (mm / °) – Speichern im Tab Einstellungen oder Strg+S")
        pl = QVBoxLayout(ps)
        pl.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(self.btn_teach)
        row.addWidget(self.pose_name)
        row.addWidget(self.btn_goto)
        pl.addLayout(row)
        self.motion_buttons += [self.btn_teach, self.btn_goto]

        self.map = RobotMapView(cfg)
        left = QVBoxLayout()
        for w in (con, st, mv, jg):
            left.addWidget(w)
        left.addStretch()
        right = QVBoxLayout()
        right.addWidget(self.map, 3)
        right.addWidget(ps, 2)
        layout = QHBoxLayout(self)
        lw = QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(420)
        layout.addWidget(lw)
        layout.addLayout(right, 1)

        self.poll = QTimer(self, interval=1000)
        self.poll.timeout.connect(self.refresh_status)
        self.refresh()
        self._set_connected(False)

    # -- helpers ----------------------------------------------------------------------
    @property
    def is_real(self) -> bool:
        return self.mode.currentData() == "real"

    def _set_connected(self, on: bool) -> None:
        for b in self.motion_buttons:
            b.setEnabled(on)
        self.btn_disconnect.setEnabled(on)
        self.btn_connect.setEnabled(not on)
        self.mode.setEnabled(not on)
        self.host.setEnabled(not on)
        if on:
            self.status.show_state(f"verbunden ({self.mode.currentText()})", GOOD)
            self.poll.start()
        else:
            self.status.show_state("getrennt", NEUTRAL)
            self.poll.stop()

    def refresh(self) -> None:
        """Pose table and map from the config (also after edits in the settings tab)."""
        poses = self.s.cfg["robot"]["poses"]
        self.table.setRowCount(len(poses))
        for i, (name, v) in enumerate(poses.items()):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            for j, x in enumerate(v):
                self.table.setItem(i, j + 1, QTableWidgetItem(f"{x:.1f}"))
        self.table.resizeColumnsToContents()
        current = self.pose_name.currentText()
        self.pose_name.clear()
        self.pose_name.addItems([n for n in poses if n != "home"])
        if current:
            self.pose_name.setCurrentText(current)
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
        self.lbl_err.setText(f"<span style='color:{BAD}'>{e}</span>")
        show_error(e)

    def robot_call(self, fn, done_text: str = "") -> None:
        robot = self.s.robot
        if robot is None:
            return
        self.runner.submit(lambda: fn(robot), lambda _: (self.refresh_status(),
                                                         self.lbl_err.setText(done_text or "ok")),
                           self._error, pool="robot")

    def move(self, what: str, fn) -> None:
        if self.is_real and not confirm_motion(self, what):
            return
        self.lbl_err.setText(f"läuft: {what} …")
        self.robot_call(fn, f"fertig: {what}")

    def _pick_test(self, robot) -> None:
        target = robot_target(self.s.cfg, "inspection")
        robot.home()
        robot.pick(target)
        robot.place(target)
        robot.home()

    def jog(self, axis: str, sign: int) -> None:
        step = sign * self.jog_step.value()
        key = {"x": "dx_mm", "y": "dy_mm", "z": "dz_mm", "rz": "drz_deg"}[axis]
        unit = "°" if axis == "rz" else " mm"
        self.move(f"Relativ {axis.upper()} {step:+.0f}{unit} (Basis-Koordinatensystem)",
                  lambda r: r.jog(**{key: step}))

    def set_override(self, v: float) -> None:
        self.s.store.set(["robot", "override"], round(v, 2))
        if self.s.robot is not None:
            self.robot_call(lambda r: r.r.set_override(round(v, 2)), f"Override {v:.2f}")

    def emergency_stop(self) -> None:
        self.runner.submit(self.s.emergency_stop, lambda _: (self.lbl_err.setText(
            f"<b style='color:{BAD}'>STOPP gesendet – zum Weiterarbeiten 'Freigeben'</b>"),
            self._show_ready()), pool="stop")

    def release_robot(self) -> None:
        self.robot_call(lambda r: r.reset(), "freigegeben")

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
                self.lbl_err.setText(f"<span style='color:{BAD}'>{errors}</span>")
            self.map.set_tcp(p.x_mm, p.y_mm)
            self._show_ready()
        self.runner.submit(read, show, lambda e: self.lbl_err.setText(str(e)), pool="robot")

    def teach(self) -> None:
        name = self.pose_name.currentText()
        robot = self.s.robot
        if robot is None or not name:
            return

        def store(p):
            self.s.store.set(["robot", "poses", name],
                             [round(v, 1) for v in (p.x_mm, p.y_mm, p.z_mm, p.rx_deg, p.ry_deg, p.rz_deg)])
            self.refresh()
            self.lbl_err.setText(f"Pose '{name}' übernommen (noch nicht gespeichert)")
        self.runner.submit(robot.current_pose, store, self._error, pool="robot")

    def goto_pose(self) -> None:
        name = self.pose_name.currentText()
        target = robot_target(self.s.cfg, name)

        def go(robot):
            from m2_robot_control.robot import offset_z
            above = offset_z(target, self.s.cfg["robot"]["approach_height_mm"])
            robot._joint_move_to(above)
            robot._linear(above, target, self.s.cfg["robot"]["approach_speed_mps"])
        self.move(f"Pose '{name}' anfahren", go)
