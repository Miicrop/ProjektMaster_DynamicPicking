"""Sub-pages of tab M2: commissioning steps 1-8 of ANLEITUNG_NEURA.md (sections 6-7b) as buttons.

Every page talks to the robot only through RobotTab.run() - one robot task at a time, safety
question for the real robot, errors shown in the tab. Logic shared with robot_check: m2_robot_control.steps.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from common.config import robot_target
from gui.widgets import BAD, GOOD, NEUTRAL, ImageView
from m2_robot_control import steps
from m2_robot_control.robot import offset_z

if TYPE_CHECKING:
    from gui.tab_robot import RobotTab

OK, FAIL, OPEN = "✓", "✗", "–"


def _status(label: QLabel, ok: bool | None, text: str = "") -> None:
    sym, colour = (OPEN, NEUTRAL) if ok is None else (OK, GOOD) if ok else (FAIL, BAD)
    label.setText(f"<b style='color:{colour}'>{sym}</b> {text}")


def _item(text: Any) -> QTableWidgetItem:
    return QTableWidgetItem("" if text is None else f"{text:.1f}" if isinstance(text, float) else str(text))


# --- 1-8: checklist ---------------------------------------------------------------------

class StepsPage(QWidget):
    """Checklist 'Erste Schritte': each step a button, the result as ✓ / ✗."""

    def __init__(self, tab: RobotTab):
        super().__init__()
        self.tab = tab
        self.status: dict[str, QLabel] = {}
        # key, title, what to expect, button text, action
        self.defs: list[tuple[str, str, str, str, Callable[[], None]]] = [
            ("info", "Verbindung lesen", "Name, Version v5.0.8, Punkte Home/Parking, keine Fehler",
             "Lesen", self.info),
            ("home", "Home anfahren", "Roboter fährt langsam nach Home", "Fahren", self.home),
            ("gripper", "Greifer testen", "öffnen → schließen → öffnen", "Testen", self.gripper),
            ("axes", "Achsentest", "±Z, ±X, ±Y, ±rz einzeln, Richtung notieren", "Öffnen →",
             lambda: tab.show_page("axes")),
            ("teach", "Posen teachen", "Prüfposition, Gut, Schlecht anfahren und übernehmen", "Öffnen →",
             lambda: tab.show_page("teach")),
            ("calib", "Kalibrierung", "Marker antasten → workspace_to_robot, RMS ≤ 3 mm", "Öffnen →",
             lambda: tab.show_page("calib")),
            ("point", "Zeigetest", "Greifer steht über dem erkannten Bauteil, greift nicht", "Öffnen →",
             lambda: tab.show_page("point")),
            ("pick", "Greiftest", "Home → greift an der Prüfposition → legt ab → Home", "Starten", self.pick),
        ]
        grid = QGridLayout()
        for i, (key, title, expect, btn_text, fn) in enumerate(self.defs):
            grid.addWidget(QLabel(f"<b>{i + 1}. {title}</b>"), i, 0)
            hint = QLabel(expect)
            hint.setStyleSheet("color:#666")
            grid.addWidget(hint, i, 1)
            b = QPushButton(btn_text)
            b.clicked.connect(fn)
            grid.addWidget(b, i, 2)
            if not btn_text.startswith("Öffnen"):
                tab.needs_robot(b)
            self.status[key] = QLabel()
            _status(self.status[key], None)
            grid.addWidget(self.status[key], i, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setStyleSheet("font-family:Consolas; font-size:9pt")
        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addWidget(self.details)
        lay.addStretch()

    def mark(self, key: str, ok: bool | None, text: str = "") -> None:
        _status(self.status[key], ok, text)

    def _step(self, key: str, what: str, fn, moves: bool = True) -> None:
        self.mark(key, None, "läuft …")
        self.tab.run(what, fn, lambda _: self.mark(key, True, time.strftime("%H:%M")),
                     moves=moves, on_error=lambda e: self.mark(key, False, str(e)[:80]))

    def info(self) -> None:
        def show(v):
            rows, problems = v
            self.details.setText("<br>".join(f"{k}: {val}" for k, val in rows + [("Probleme", p) for p in problems]))
            self.mark("info", not problems, "; ".join(problems) or time.strftime("%H:%M"))
        self.tab.run("Verbindung lesen", lambda r: steps.robot_info(r, self.tab.s.cfg), show, moves=False,
                     on_error=lambda e: self.mark("info", False, str(e)[:80]))

    def home(self) -> None:
        self._step("home", "Home anfahren", lambda r: r.home())

    def gripper(self) -> None:
        def run(r):
            for close in (False, True, False):
                r.gripper(close=close)
                time.sleep(1.5)
        self._step("gripper", "Greifer öffnen → schließen → öffnen", run, moves=False)

    def pick(self) -> None:
        self._step("pick", "Greiftest: Home → Greifen und Ablegen an der Prüfposition → Home", self.tab.pick_test)


# --- 4: axis test -------------------------------------------------------------------------

class AxesPage(QWidget):
    """Each axis: step in + direction and back; the user notes the observed direction."""

    def __init__(self, tab: RobotTab):
        super().__init__()
        self.tab = tab
        self.step_mm = QDoubleSpinBox(minimum=5.0, maximum=100.0, singleStep=10.0, decimals=0, value=50.0)
        self.step_mm.setSuffix(" mm")
        self.step_deg = QDoubleSpinBox(minimum=1.0, maximum=15.0, singleStep=1.0, decimals=0, value=5.0)
        self.step_deg.setSuffix(" °")
        top = QHBoxLayout()
        for w in (QLabel("Schritt x/y/z"), self.step_mm, QLabel("rz"), self.step_deg):
            top.addWidget(w)
        btn_home = QPushButton("Home anfahren")
        btn_home.clicked.connect(lambda: tab.run("Home anfahren", lambda r: r.home()))
        top.addWidget(btn_home)
        top.addStretch()
        grid = QGridLayout()
        self.measured: dict[str, QLabel] = {}
        self.notes: dict[str, QLineEdit] = {}
        for i, (axis, expect) in enumerate(steps.AXES_SEQUENCE):
            b = QPushButton(f"+{axis.upper()} und zurück")
            b.clicked.connect(lambda _=False, a=axis: self.test(a))
            grid.addWidget(b, i, 0)
            grid.addWidget(QLabel(f"erwartet: {expect}"), i, 1)
            self.measured[axis] = QLabel("–")
            grid.addWidget(self.measured[axis], i, 2)
            self.notes[axis] = QLineEdit(placeholderText="Beobachtung, z. B. 'zum Fenster'")
            grid.addWidget(self.notes[axis], i, 3)
            tab.needs_robot(b)
        tab.needs_robot(btn_home)
        grid.setColumnStretch(3, 1)
        self.btn_save = QPushButton("Protokoll speichern (logs/axes_tests.csv)")
        self.btn_save.clicked.connect(self.save)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(grid)
        hint = QLabel("Bewegt wird linear und langsam im Basis-KS. Prüfen: zeigt +Z nach oben? Wohin zeigen +X/+Y "
                      "im Raum? Dreht +rz von oben gesehen gegen den Uhrzeigersinn?")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addWidget(self.btn_save)
        lay.addStretch()

    def _value(self, axis: str) -> float:
        return self.step_deg.value() if axis == "rz" else self.step_mm.value()

    def test(self, axis: str) -> None:
        v = self._value(axis)
        unit = "°" if axis == "rz" else " mm"

        def show(res):
            there, back = res
            self.measured[axis].setText(f"hin: {steps.fmt_delta(there)}\nzurück: {steps.fmt_delta(back)}")
            self.notes[axis].setFocus()
        self.tab.run(f"Achsentest {axis.upper()} {v:+.0f}{unit} und zurück (Basis-KS)",
                     lambda r: steps.axis_there_and_back(r, axis, v), show)

    def save(self) -> None:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        rows = [{"time": now, "axis": f"+{a.upper()}", "step": self._value(a),
                 "measured": self.measured[a].text().replace("\n", " | "), "observation": self.notes[a].text()}
                for a, _ in steps.AXES_SEQUENCE if self.measured[a].text() != "–"]
        if not rows:
            self.tab.message("Noch keine Achse getestet", error=True)
            return
        f = steps.log_axes(self.tab.s.cfg, rows)
        self.tab.message(f"Achsentest protokolliert in {f}")
        self.tab.steps.mark("axes", all(self.notes[a].text().strip() for a, _ in steps.AXES_SEQUENCE),
                            f"{len(rows)}/4 Achsen")


# --- calibration workspace -> robot ----------------------------------------------------------

class CalibPage(QWidget):
    """Touch the marker centres with the TCP tip -> workspace_to_robot."""

    COLS = ["Marker", "Arbeitsraum x", "y", "Basis x", "y", "z", "Restfehler"]

    def __init__(self, tab: RobotTab):
        super().__init__()
        self.tab = tab
        self.taught: dict[int, tuple[float, float, float]] = {}
        self.result: steps.CalibResult | None = None
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.height = QDoubleSpinBox(minimum=5.0, maximum=100.0, singleStep=5.0, decimals=0, value=20.0)
        self.height.setSuffix(" mm")
        self.height.setToolTip("Höhe für 'Über Marker fahren' und Abheben nach dem Übernehmen")
        self.btn_above = QPushButton("Über Marker fahren")
        self.btn_above.setToolTip("Nutzt die AKTUELLE Kalibrierung - nur sinnvoll, wenn sie ungefähr stimmt "
                                  "(sonst mit Joggen hinfahren)")
        self.btn_take = QPushButton("Spitze auf Marker → übernehmen")
        self.btn_clear = QPushButton("Zeile löschen")
        self.btn_calc = QPushButton("Berechnen")
        self.btn_apply = QPushButton("In Konfiguration übernehmen")
        self.btn_above.clicked.connect(self.goto_above)
        self.btn_take.clicked.connect(self.take)
        self.btn_clear.clicked.connect(self.clear_row)
        self.btn_calc.clicked.connect(self.calc)
        self.btn_apply.clicked.connect(self.apply)
        tab.needs_robot(self.btn_above, self.btn_take)
        self.lbl_result = QLabel("Greiferspitze nacheinander mittig auf die Marker setzen (Tisch gerade "
                                 "berühren), jeweils übernehmen. Mindestens 3 Marker.")
        self.lbl_result.setWordWrap(True)
        row1 = QHBoxLayout()
        for w in (QLabel("Höhe"), self.height, self.btn_above, self.btn_take, self.btn_clear):
            row1.addWidget(w)
        row2 = QHBoxLayout()
        row2.addWidget(self.btn_calc)
        row2.addWidget(self.btn_apply)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table)
        lay.addLayout(row1)
        lay.addLayout(row2)
        lay.addWidget(self.lbl_result)
        self.refresh()
        self.table.selectRow(0)

    def _markers(self) -> dict[int, list[float]]:
        return {int(k): v for k, v in self.tab.s.cfg["workspace"]["markers_mm"].items()}

    def _selected(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        return int(self.table.item(rows[0].row(), 0).text()) if rows else None

    def refresh(self) -> None:
        markers = self._markers()
        sel = self.table.currentRow()
        self.table.setRowCount(len(markers))
        for i, mid in enumerate(sorted(markers)):
            t = self.taught.get(mid, (None, None, None))
            res = self.result.residuals_mm.get(mid) if self.result else None
            for j, v in enumerate([mid, float(markers[mid][0]), float(markers[mid][1]), *t, res]):
                self.table.setItem(i, j, _item(v))
        self.table.resizeColumnsToContents()
        if sel >= 0:
            self.table.selectRow(sel)
        self.btn_apply.setEnabled(self.result is not None)

    def goto_above(self) -> None:
        mid = self._selected()
        if mid is None:
            return
        t = steps.marker_target(self.tab.s.cfg, mid, self.height.value())
        self.tab.run(f"Über Marker {mid} fahren ({self.height.value():.0f} mm, aktuelle Kalibrierung)",
                     lambda r: r._joint_move_to(t))

    def take(self) -> None:
        mid = self._selected()
        if mid is None:
            return
        lift = self.height.value()

        def read_and_lift(r):
            p = r.current_pose()
            r.jog(dz_mm=lift)            # lift off the marker before the next move
            return p

        def store(p):
            self.taught[mid] = (p.x_mm, p.y_mm, p.z_mm)
            self.result = None
            self.refresh()
            self.table.selectRow(min(self.table.currentRow() + 1, self.table.rowCount() - 1))
            self.tab.message(f"Marker {mid}: x={p.x_mm:.1f} y={p.y_mm:.1f} z={p.z_mm:.1f} mm übernommen")
        self.tab.run(f"Marker {mid} übernehmen, danach {lift:.0f} mm anheben", read_and_lift, store)

    def clear_row(self) -> None:
        mid = self._selected()
        if mid is not None:
            self.taught.pop(mid, None)
            self.result = None
            self.refresh()

    def calc(self) -> None:
        try:
            self.result = steps.calibrate(self.tab.s.cfg, self.taught)
        except ValueError as e:
            self.tab.message(str(e), error=True)
            return
        c = self.result
        colour = GOOD if c.ok else BAD
        warn = "" if c.ok else (f"<br><b>RMS > {steps.CALIB_RMS_WARN_MM:.0f} mm</b> - Marker-IDs vertauscht, "
                                "markers_mm falsch gemessen oder Spitze nicht mittig? Marker mit großem "
                                "Restfehler neu antasten.")
        cfg = steps.calib_config(c)
        self.lbl_result.setText(f"rotation_deg {cfg['rotation_deg']}, translation_mm {cfg['translation_mm']}, "
                                f"table_z_mm {cfg['table_z_mm']} – <b style='color:{colour}'>RMS "
                                f"{c.rms_mm:.1f} mm</b>{warn}")
        self.refresh()

    def apply(self) -> None:
        if self.result is None:
            return
        for k, v in steps.calib_config(self.result).items():
            self.tab.s.store.set(["workspace_to_robot", k], v)
        self.tab.refresh()
        self.tab.steps.mark("calib", self.result.ok, f"RMS {self.result.rms_mm:.1f} mm, Strg+S speichert")
        self.tab.message("Kalibrierung übernommen (noch nicht gespeichert - Strg+S)")


# --- teach poses ---------------------------------------------------------------------------

class TeachPage(QWidget):
    """Drive to a station, jog onto the exact place pose, take the current TCP pose."""

    def __init__(self, tab: RobotTab):
        super().__init__()
        self.tab = tab
        self.taught: set[str] = set()
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Pose", "x", "y", "z", "rx", "ry", "rz"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._row_selected)
        self.pose_name = QComboBox()
        self.btn_above = QPushButton("Über Pose fahren")
        self.btn_goto = QPushButton("Pose anfahren (über Vorposition)")
        self.btn_teach = QPushButton("Aktuelle TCP-Pose übernehmen")
        self.btn_lift = QPushButton("Senkrecht anheben")
        self.btn_above.clicked.connect(self.goto_above)
        self.btn_goto.clicked.connect(self.goto_pose)
        self.btn_teach.clicked.connect(self.teach)
        self.btn_lift.clicked.connect(self.lift)
        tab.needs_robot(self.btn_above, self.btn_goto, self.btn_teach, self.btn_lift)
        row = QHBoxLayout()
        for w in (self.pose_name, self.btn_above, self.btn_goto):
            row.addWidget(w)
        row2 = QHBoxLayout()
        row2.addWidget(self.btn_teach)
        row2.addWidget(self.btn_lift)
        hint = QLabel("Ablauf: Pose wählen → <i>Über Pose fahren</i> → mit Joggen (links) genau auf die Ablagepose "
                      "fahren (Höhe, an der der Greifer öffnet; Prüfaufbau 38 mm über der Platte) → "
                      "<i>übernehmen</i> → <i>Senkrecht anheben</i>. Speichern: Strg+S.")
        hint.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table)
        lay.addLayout(row)
        lay.addLayout(row2)
        lay.addWidget(hint)

    def refresh(self) -> None:
        poses = self.tab.s.cfg["robot"]["poses"]
        self.table.setRowCount(len(poses))
        for i, (name, v) in enumerate(poses.items()):
            self.table.setItem(i, 0, _item(name + (" ✓" if name in self.taught else "")))
            for j, x in enumerate(v):
                self.table.setItem(i, j + 1, _item(float(x)))
        self.table.resizeColumnsToContents()
        current = self.pose_name.currentText()
        self.pose_name.blockSignals(True)
        self.pose_name.clear()
        self.pose_name.addItems([n for n in poses if n != "home"])
        if current:
            self.pose_name.setCurrentText(current)
        self.pose_name.blockSignals(False)

    def _row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            name = self.table.item(rows[0].row(), 0).text().split(" ")[0]
            if self.pose_name.findText(name) >= 0:
                self.pose_name.setCurrentText(name)

    def _above(self, name: str):
        return offset_z(robot_target(self.tab.s.cfg, name), self.tab.s.cfg["robot"]["approach_height_mm"])

    def goto_above(self) -> None:
        name = self.pose_name.currentText()
        above = self._above(name)
        self.tab.run(f"Über Pose '{name}' fahren", lambda r: r._joint_move_to(above))

    def goto_pose(self) -> None:
        name = self.pose_name.currentText()
        target, above = robot_target(self.tab.s.cfg, name), self._above(name)

        def go(r):
            r._joint_move_to(above)
            r._linear(above, target, self.tab.s.cfg["robot"]["approach_speed_mps"])
        self.tab.run(f"Pose '{name}' anfahren", go)

    def teach(self) -> None:
        name = self.pose_name.currentText()
        if not name:
            return

        def store(p):
            self.tab.s.store.set(["robot", "poses", name], steps.pose_list(p))
            self.taught.add(name)
            self.tab.refresh()
            done = [s for s in steps.STATIONS if s in self.taught]
            self.tab.steps.mark("teach", len(done) == len(steps.STATIONS) or None,
                                f"{len(done)}/{len(steps.STATIONS)} Stationen, Strg+S speichert")
            self.tab.message(f"Pose '{name}' übernommen, z = {p.z_mm:.1f} mm (noch nicht gespeichert)")
        self.tab.run("Pose lesen", lambda r: r.current_pose(), store, moves=False)

    def lift(self) -> None:
        dz = min(self.tab.s.cfg["robot"]["approach_height_mm"], 100.0)
        self.tab.run(f"Senkrecht {dz:.0f} mm anheben", lambda r: r.jog(dz_mm=dz))


# --- pointing test -----------------------------------------------------------------------------

class PointPage(QWidget):
    """Detect the part (M1), hover the open gripper above it, note the offset, log it."""

    def __init__(self, tab: RobotTab):
        super().__init__()
        self.tab = tab
        self.found = None           # (TopDownResult, kind)
        self.target = None
        self.source = QComboBox()
        self.source.addItem("Kamera", "camera")
        self.source.addItem("Testbilder", "replay")
        self.hover = QDoubleSpinBox(minimum=10.0, maximum=70.0, singleStep=5.0, decimals=0, value=30.0)
        self.hover.setSuffix(" mm über Greifpose")
        self.dx = QDoubleSpinBox(minimum=-100.0, maximum=100.0, singleStep=0.5, decimals=1)
        self.dy = QDoubleSpinBox(minimum=-100.0, maximum=100.0, singleStep=0.5, decimals=1)
        for w in (self.dx, self.dy):
            w.setSuffix(" mm")
        self.note = QLineEdit(placeholderText="z. B. 'Finger quer zur kurzen Seite ok'")
        self.btn_detect = QPushButton("1. Bauteil erkennen")
        self.btn_point = QPushButton("2. Hinfahren und zeigen")
        self.btn_log = QPushButton("3. Protokollieren")
        self.btn_back = QPushButton("4. Zurück und Home")
        self.btn_detect.clicked.connect(self.detect)
        self.btn_point.clicked.connect(self.point)
        self.btn_log.clicked.connect(self.log)
        self.btn_back.clicked.connect(self.back)
        tab.needs_robot(self.btn_point, self.btn_back)
        self.lbl = QLabel("–")
        self.lbl.setWordWrap(True)
        self.image = ImageView("Erkennung")
        form = QFormLayout()
        form.addRow("Quelle", self.source)
        form.addRow("Höhe", self.hover)
        form.addRow("Versatz Bauteil − Greifer, Basis +X", self.dx)
        form.addRow("Versatz Bauteil − Greifer, Basis +Y", self.dy)
        form.addRow("Notiz", self.note)
        buttons = QGridLayout()
        for i, b in enumerate((self.btn_detect, self.btn_point, self.btn_log, self.btn_back)):
            buttons.addWidget(b, i // 2, i % 2)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addLayout(buttons)
        left.addWidget(self.lbl)
        left.addStretch()
        lay = QHBoxLayout(self)
        lay.addLayout(left, 1)
        lay.addWidget(self.image, 1)

    def detect(self) -> None:
        kind = self.source.currentData()
        s = self.tab.s

        def run():
            img = s.grab("m1", kind)
            res = s.analyze_m1(img)
            return res, res.debug_image(img)

        def show(v):
            res, dbg = v
            self.found, self.target = (res, kind), None
            p = res.pose
            self.image.set_image(dbg)
            warn = "" if p.confidence >= 1.0 else (f"<br><b style='color:{BAD}'>Fase nicht gefunden - Winkel nur "
                                                    "bis auf 180° eindeutig</b>")
            self.lbl.setText(f"Bauteil (Basis-KS): x={p.x_mm:.1f} y={p.y_mm:.1f} mm, θ={p.theta_deg:.1f}°{warn}")
            self.tab.map.set_part(p.x_mm, p.y_mm, p.theta_deg)

        def fail(e):
            self.found = None
            self.lbl.setText(f"<span style='color:{BAD}'>{e}</span>")
        self.lbl.setText("erkenne …")
        self.tab.runner.submit(run, show, fail, pool="vision")

    def point(self) -> None:
        if self.found is None:
            self.tab.message("Erst ein Bauteil erkennen", error=True)
            return
        pose, hover = self.found[0].pose, self.hover.value()

        def go(r):
            r.home()
            return r.point_at(pose, hover)

        def done(t):
            self.target = t
            self.lbl.setText(self.lbl.text() + f"<br>Greifer steht {hover:.0f} mm darüber: {steps.fmt_pose(t)}")
        self.tab.run(f"Home → {hover:.0f} mm über das erkannte Bauteil fahren (greift nicht)", go, done)

    def log(self) -> None:
        if self.found is None or self.target is None:
            self.tab.message("Erst erkennen und hinfahren", error=True)
            return
        res, kind = self.found
        row = steps.point_row(kind, res.pose, res, self.target, self.hover.value(),
                              self.dx.value(), self.dy.value(), self.note.text().strip())
        f = steps.log_point(self.tab.s.cfg, row)
        off = (self.dx.value() ** 2 + self.dy.value() ** 2) ** 0.5
        self.tab.steps.mark("point", True, f"Versatz {off:.1f} mm")
        self.tab.message(f"Zeigetest protokolliert in {f}")

    def back(self) -> None:
        if self.found is None or self.target is None:
            self.tab.run("Home anfahren", lambda r: r.home())
            return
        pose, hover = self.found[0].pose, self.hover.value()

        def go(r):
            r.retreat(pose, hover)
            r.home()
        self.tab.run("Zurück auf Anfahrhöhe und Home", go)
