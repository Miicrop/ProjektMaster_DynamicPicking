"""Tab "Ablauf": automatic cycle DETECT -> PICK -> ... -> SORT with live visual feedback."""
from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from gui.session import Session
from gui.tab_robot import StopButton
from gui.widgets import (ACTIVE, BAD, GOOD, NEUTRAL, Badge, ImageView, RobotMapView, TaskRunner, confirm_motion,
                         show_error)
from orchestrator import logbook
from orchestrator.state_machine import CycleResult, State

log = logging.getLogger(__name__)

FLOW = [State.DETECT, State.PICK, State.PLACE_INSPECT, State.INSPECT, State.PICK_INSPECT, State.SORT]
LABELS = {State.DETECT: "Erkennen\n(M1)", State.PICK: "Greifen\n(M2)", State.PLACE_INSPECT: "Ablegen\nPrüfplatz",
          State.INSPECT: "Prüfen\n(M3)", State.PICK_INSPECT: "Aufnehmen\nPrüfplatz", State.SORT: "Sortieren\n(M2)"}
KINDS = {
    "detector": [("Mock", "mock"), ("Testbilder", "replay"), ("Kamera", "camera"), ("KI (M4)", "ai")],
    "robot": [("Mock", "mock"), ("Simulator", "sim"), ("Neura-VM", "vm"), ("Echter Roboter", "real")],
    "inspector": [("Mock", "mock"), ("Testbilder", "replay"), ("Kamera", "camera")],
}
COLUMNS = ["#", "Zeit", "Dauer s", "x mm", "y mm", "θ °", "Seriennr.", "Loch mm", "Kerbe", "Ergebnis", "Grund / Fehler"]


class AutoTab(QWidget):
    state_changed = Signal(object, object)       # emitted from the worker thread
    stage_feedback = Signal(str, object, str)    # "m1"/"m3", image or None, text - right after each step
    cycle_finished = Signal(object)

    def __init__(self, session: Session, runner: TaskRunner, parent: QWidget | None = None):
        super().__init__(parent)
        self.s, self.runner = session, runner
        self._stop_after_cycle = threading.Event()
        self.running = False
        self.counts = {"good": 0, "bad": 0, "error": 0, "empty": 0}

        # configuration row
        self.kind = {}
        cfg_impl = session.cfg["implementations"]
        defaults = {"detector": "replay", "robot": "sim", "inspector": "replay"}
        top = QHBoxLayout()
        for key, title in (("detector", "Erkennung"), ("robot", "Roboter"), ("inspector", "Prüfung")):
            cb = QComboBox()
            for text, k in KINDS[key]:
                cb.addItem(text, k)
            wanted = {"real": "camera"}.get(cfg_impl.get(key), cfg_impl.get(key)) if key != "robot" \
                else cfg_impl.get(key)
            idx = cb.findData(wanted if wanted != "mock" else defaults[key])
            cb.setCurrentIndex(max(idx, 0))
            self.kind[key] = cb
            top.addWidget(QLabel(title + ":"))
            top.addWidget(cb)
        self.pause = QDoubleSpinBox(minimum=0, maximum=30, value=1.0, singleStep=0.5, suffix=" s Pause")
        self.save_images = QCheckBox("Bilder speichern")
        self.save_steps = QCheckBox("+ Zwischenschritte")
        self.save_steps.setToolTip("M1/M3-Zwischenbilder (Masken, ROIs, Kandidaten) nach logs/…/steps/ – für die Doku")
        self.save_steps.setEnabled(False)
        self.save_images.toggled.connect(self.save_steps.setEnabled)
        top.addWidget(self.pause)
        top.addWidget(self.save_images)
        top.addWidget(self.save_steps)
        top.addStretch()

        # buttons
        self.btn_one = QPushButton("▶ 1 Zyklus")
        self.btn_run = QPushButton("▶▶ Dauerbetrieb")
        self.btn_halt = QPushButton("■ Stopp nach Zyklus")
        self.btn_reset = QPushButton("Fehler quittieren")
        self.btn_stop = StopButton("NOT-STOPP (Software)")
        self.btn_one.clicked.connect(lambda: self.start(single=True))
        self.btn_run.clicked.connect(lambda: self.start(single=False))
        self.btn_halt.clicked.connect(self._stop_after_cycle.set)
        self.btn_reset.clicked.connect(self.reset_error)
        self.btn_stop.clicked.connect(self.emergency_stop)
        buttons = QHBoxLayout()
        for b in (self.btn_one, self.btn_run, self.btn_halt, self.btn_reset):
            b.setMinimumHeight(40)
            buttons.addWidget(b)
        buttons.addWidget(self.btn_stop)

        # state chain
        chain = QHBoxLayout()
        self.state_labels = {}
        for i, st in enumerate(FLOW):
            lab = QLabel(LABELS[st])
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumHeight(48)
            self.state_labels[st] = lab
            chain.addWidget(lab, 1)
            if i < len(FLOW) - 1:
                chain.addWidget(QLabel("→"))
        self.badge = Badge("bereit")
        self.badge.setMinimumWidth(200)
        chain.addWidget(self.badge)
        self._paint_chain(None)

        # views
        self.view_m1, self.view_m3 = ImageView("Erkennung (M1)"), ImageView("Prüfung (M3)")
        self.info_m1, self.info_m3 = QLabel("–"), QLabel("–")
        self.map = RobotMapView(session.cfg)
        self.views = {"m1": (self.view_m1, self.info_m1), "m3": (self.view_m3, self.info_m3)}
        grid = QGridLayout()
        for col, (title, w, info) in enumerate((("Erkennung (M1)", self.view_m1, self.info_m1),
                                                ("Prüfung (M3)", self.view_m3, self.info_m3),
                                                ("Roboter", self.map, None))):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            bl.addWidget(w)
            if info is not None:
                info.setWordWrap(True)
                bl.addWidget(info)
            grid.addWidget(box, 0, col)

        # results
        self.counter = QLabel()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self._update_counter()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(buttons)
        layout.addLayout(chain)
        layout.addLayout(grid, 3)
        layout.addWidget(self.counter)
        layout.addWidget(self.table, 2)

        self.state_changed.connect(self._on_state)
        self.stage_feedback.connect(self._on_stage)
        self.cycle_finished.connect(self._on_cycle)
        self._set_running(False)

    # -- run control ---------------------------------------------------------------
    def _set_running(self, on: bool) -> None:
        self.running = on
        for w in (self.btn_one, self.btn_run, self.btn_reset, *self.kind.values()):
            w.setEnabled(not on)
        self.btn_halt.setEnabled(on)

    def start(self, single: bool) -> None:
        kinds = {k: cb.currentData() for k, cb in self.kind.items()}
        if kinds["robot"] == "real" and not confirm_motion(
                self, "Automatischer Ablauf mit dem echten Roboter" + (" (1 Zyklus)" if single else "")):
            return
        self._stop_after_cycle.clear()
        self._set_running(True)
        self.badge.show_state("startet …", ACTIVE)
        opts = {"save_images": self.save_images.isChecked(), "pause": self.pause.value(),
                "save_steps": self.save_images.isChecked() and self.save_steps.isChecked()}
        self.runner.submit(lambda: self._run(kinds, single, opts), lambda _: self._finished(),
                           self._run_failed, pool="robot")

    def _run_failed(self, e: Exception) -> None:
        self._finished()
        if "acknowledge" in str(e):
            self.badge.show_state("gestoppt – quittieren", BAD)
            log.warning("Roboter ist gestoppt: erst 'Fehler quittieren', dann neu starten")
        else:
            self.badge.show_state("Fehler", BAD)
            log.error("Ablauf abgebrochen: %s", e)

    def _run(self, kinds: dict[str, str], single: bool, opts: dict) -> None:
        """Worker thread (no widget access!): build the system and run cycles until stopped."""
        orch = self.s.build_orchestrator(kinds["detector"], kinds["robot"], kinds["inspector"])
        self.orch = orch
        orch.listeners = [lambda st, res: self.state_changed.emit(st, res),
                          lambda st, res: self._stage_feedback(orch, st, res)]
        for module in (orch.detector, orch.inspector):
            if hasattr(module, "trace_steps"):
                module.trace_steps = opts["save_steps"]
        orch.robot.home()
        while True:
            result = orch.run_cycle()
            images = None
            if opts["save_images"]:
                images = logbook.save_images(self.s.cfg, result, orch.detector, orch.inspector)
            logbook.append_csv(self.s.cfg, result, images)
            self.cycle_finished.emit(result)
            if single or self._stop_after_cycle.is_set() or result.error:
                break
            time.sleep(opts["pause"])

    def _stage_feedback(self, orch, state: State, res: CycleResult) -> None:
        """Worker thread: image + short text of M1 / M3 as soon as that step is done (not only at cycle end)."""
        det, insp = orch.detector, orch.inspector
        before = res.states[-2] if len(res.states) > 1 else None
        if state is State.DETECT:
            self.stage_feedback.emit("m1", None, f"Zyklus {res.cycle_id}: erkenne …")
        elif state is State.PICK:
            m1, img = getattr(det, "last_result", None), getattr(det, "last_image", None)
            p = res.pose
            text = f"x {p.x_mm:.1f}  y {p.y_mm:.1f} mm  θ {p.theta_deg:.1f}° (Basis-KS)"
            if m1 is not None:
                text += f"\nArbeitsraum: x {m1.x_ws_mm:.1f}  y {m1.y_ws_mm:.1f} mm  θ {m1.theta_ws_deg:.1f}°, " \
                        f"Fase {'erkannt' if m1.part.chamfer_found else 'nicht erkannt (θ nur mod 180°)'}"
            self.stage_feedback.emit("m1", m1.overlay_image(img) if m1 is not None and img is not None else img, text)
        elif state is State.IDLE and res.pose is None and before is State.DETECT:
            self.stage_feedback.emit("m1", getattr(det, "last_image", None), "kein Bauteil gefunden (Rohbild)")
        elif state is State.INSPECT:
            self.stage_feedback.emit("m3", None, f"Zyklus {res.cycle_id}: prüfe …")
        elif state is State.PICK_INSPECT:
            m3, img, r = getattr(insp, "last_details", None), getattr(insp, "last_image", None), res.inspection
            crop = m3.part_crop(img, self.s.cfg["inspection"]) if m3 is not None and img is not None else img
            hole = f"{r.hole_diameter_mm:.2f} mm" if r.hole_diameter_mm else "–"
            text = (f"{'GUT' if r.is_good else 'SCHLECHT'}: Seriennr. {r.serial_number or '–'}, Loch {hole}, "
                    f"Kerbe {({True: 'ja', False: 'nein'}).get(r.notch_present, '–')}" + (f"\n{'; '.join(r.reasons)}" if r.reasons else ""))
            self.stage_feedback.emit("m3", crop, text)
        elif state is State.ERROR and before in (State.DETECT, State.INSPECT):
            key, module = ("m1", det) if before is State.DETECT else ("m3", insp)
            self.stage_feedback.emit(key, getattr(module, "last_image", None), f"FEHLER: {res.error} (Rohbild)")

    def _finished(self) -> None:
        self._set_running(False)

    def reset_error(self) -> None:
        """After STOP or error: re-enable the robot (init_program), drive home, back to 'bereit'."""
        orch = getattr(self, "orch", None)
        fn = orch.reset if orch is not None and orch.robot is self.s.robot else self.s.acknowledge
        self.badge.show_state("quittiere …", ACTIVE)
        self.runner.submit(fn, lambda _: (self._paint_chain(None), self.badge.show_state("bereit", NEUTRAL)),
                           lambda e: (self.badge.show_state("Fehler", BAD), show_error(e)), pool="robot")

    def emergency_stop(self) -> None:
        self._stop_after_cycle.set()
        self.runner.submit(self.s.emergency_stop, pool="stop")
        self.badge.show_state("STOPP", BAD)

    # -- visual feedback (GUI thread) -------------------------------------------------
    def _paint_chain(self, current: State | None, error: bool = False, done: list[State] | None = None) -> None:
        for st, lab in self.state_labels.items():
            if st == current:
                colour, fg = (BAD if error else ACTIVE), "white"
            elif done and st in done:
                colour, fg = "#c8e6c9", "#1b5e20"
            else:
                colour, fg = "#eeeeee", "#555"
            lab.setStyleSheet(f"background:{colour}; color:{fg}; border-radius:6px; font-weight:bold;")

    def _on_state(self, state: State, result: CycleResult) -> None:
        if state is State.ERROR:
            failed = result.states[-2] if len(result.states) > 1 else None
            self._paint_chain(failed, error=True, done=result.states)
            self.badge.show_state("FEHLER", BAD)
        elif state is State.IDLE:
            self._paint_chain(None, done=result.states)
        else:
            self._paint_chain(state, done=result.states[:-1])
            self.badge.show_state(f"Zyklus {result.cycle_id}", ACTIVE)
        if result.pose and state is State.PICK:
            self.map.set_part(result.pose.x_mm, result.pose.y_mm, result.pose.theta_deg)
        robot = self.s.robot
        state_obj = getattr(robot, "sim_state", None)
        if state_obj is not None:
            self.map.set_tcp(state_obj.tcp[0] * 1000, state_obj.tcp[1] * 1000)

    def _on_stage(self, key: str, img, text: str) -> None:
        view, info = self.views[key]
        if img is not None:                       # None: keep the previous image (step still running)
            view.set_image(img)
        info.setText(text)

    def _on_cycle(self, r: CycleResult) -> None:
        insp = r.inspection
        if r.error:
            self.counts["error"] += 1
            self.badge.show_state("FEHLER", BAD)
        elif insp is None:
            self.counts["empty"] += 1
            self.badge.show_state("kein Bauteil", NEUTRAL)
        elif insp.is_good:
            self.counts["good"] += 1
            self.badge.show_state("GUTTEIL", GOOD)
        else:
            self.counts["bad"] += 1
            self.badge.show_state("SCHLECHTTEIL", BAD)
        p = r.pose
        values = [r.cycle_id, time.strftime("%H:%M:%S", time.localtime(r.started_at)),
                  f"{r.duration_s:.1f}" if r.duration_s else "",
                  f"{p.x_mm:.1f}" if p else "", f"{p.y_mm:.1f}" if p else "", f"{p.theta_deg:.1f}" if p else "",
                  insp.serial_number if insp else "",
                  f"{insp.hole_diameter_mm:.2f}" if insp and insp.hole_diameter_mm else "",
                  ("ja" if insp.notch_present else "nein") if insp else "",
                  "–" if insp is None else ("GUT" if insp.is_good else "SCHLECHT"),
                  r.error or ("; ".join(insp.reasons) if insp else "kein Bauteil")]
        self.table.insertRow(0)
        for j, v in enumerate(values):
            item = QTableWidgetItem(str(v) if v is not None else "")
            if j == 9 and insp is not None:
                item.setForeground(Qt.GlobalColor.darkGreen if insp.is_good else Qt.GlobalColor.red)
            self.table.setItem(0, j, item)
        self.table.resizeColumnsToContents()
        self._update_counter()

    def _update_counter(self) -> None:
        c = self.counts
        total = sum(c.values())
        self.counter.setText(f"<b>Zyklen: {total}</b> &nbsp; <span style='color:{GOOD}'>Gut: {c['good']}</span>"
                             f" &nbsp; <span style='color:{BAD}'>Schlecht: {c['bad']}</span> &nbsp; "
                             f"Fehler: {c['error']} &nbsp; ohne Bauteil: {c['empty']} &nbsp; "
                             f"<i>Log: code/{self.s.cfg['logging']['cycle_dir']}/cycles_&lt;datum&gt;.csv</i>")
