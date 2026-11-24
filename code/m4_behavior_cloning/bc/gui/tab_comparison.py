"""Modus "Vergleich": mehrere Modelle an denselben Lagen (Anwender 2026-11-24).

Je Lage faehrt jedes gewaehlte Modell nacheinander ``Fahrten`` Mal an und
bleibt im gewaehlten Abstand ueber dem Objekt stehen (Probegriff "objekt",
ohne Experte). Danach legt der Experte das Teil an eine neue Lage, und die
Reihe beginnt von vorn. Ablauf und Auswertung: bc/gui/vergleich.py.

Jeder Schritt ist ein eigener Aufruf von apps/infer.py, den DIESER Reiter
startet -- STOPP beendet die laufende Fahrt selbst und bricht die Reihe ab.
Bricht ein Schritt ab oder steht der Arm danach nicht sicher am Start, endet
die Reihe ebenfalls: der naechste Schritt finge sonst an einer unbekannten
Stelle an. Ein SOFTWARE-Stopp, kein zertifizierter Not-Aus (AP 4.2).
"""

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import _bootstrap
from .. import config
from . import cameras as cameras_module
from . import operation as operation_module
from . import session as session_module
from . import training as training_module
from . import vergleich as vergleich_module
from .runner import ProcessRunner
from .tab_base import ModeTab
from .widgets import BAD, GOOD, NEUTRAL, WARN, CameraAssignmentView, LogView, block_wheel

log = logging.getLogger(__name__)

#: Unter diesem Namen belegt der Vergleich die Kameras (widgets.CameraShare)
CAMERA_OWNER = "Modellvergleich"


class ComparisonTab(ModeTab):
    mode = "comparison"
    title = "Vergleich"

    def __init__(self, session, runner, parent=None):
        super().__init__(session, runner, parent)
        self.workdir = Path(_bootstrap.WORKDIR)
        self.process = ProcessRunner(self)
        self.process.line.connect(self._on_line)
        self.process.finished.connect(self._on_finished)
        self._steps, self._index, self._rows = [], 0, []
        self._root, self._stopped, self._models, self._meta = None, False, [], {}

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_controls())
        splitter.addWidget(self._build_output())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 820])
        layout = QVBoxLayout(self)
        layout.addWidget(self.requirement_view)
        layout.addWidget(splitter, 1)
        self.refresh()

    # -- Aufbau -------------------------------------------------------------

    def _build_controls(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("1. Modelle (Reihenfolge wie in der Liste)")
        inner = QVBoxLayout(box)
        self.models = QListWidget()
        self.models.setMinimumHeight(140)
        self.models.itemChanged.connect(self._update_plan_text)
        inner.addWidget(self.models)
        row = QHBoxLayout()
        self.btn_rescan = QPushButton("Neu suchen")
        self.btn_rescan.clicked.connect(self.refresh)
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_up.setToolTip("Gewähltes Modell früher fahren")
        self.btn_down.setToolTip("Gewähltes Modell später fahren")
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))
        row.addWidget(self.btn_rescan)
        row.addStretch(1)
        row.addWidget(self.btn_up)
        row.addWidget(self.btn_down)
        inner.addLayout(row)
        column.addWidget(box)

        box = QGroupBox("2. Kameras")
        inner = QVBoxLayout(box)
        self.cameras = CameraAssignmentView(self.runner)      # gemeinsam mit den anderen Reitern
        inner.addWidget(self.cameras)
        column.addWidget(box)

        box = QGroupBox("3. Ablauf")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fahrten = block_wheel(QSpinBox())
        self.fahrten.setRange(1, 20)
        self.fahrten.setValue(2)
        self.fahrten.setToolTip("So oft fährt jedes Modell dieselbe Lage an.")
        form.addRow("Fahrten je Modell und Lage", self.fahrten)
        self.lagen = block_wheel(QSpinBox())
        self.lagen.setRange(1, 200)
        self.lagen.setValue(3)
        self.lagen.setToolTip("Nach jeder Lage legt der Experte das Teil an eine neue.")
        form.addRow("Lagen", self.lagen)
        self.probe_gap = block_wheel(QDoubleSpinBox())
        self.probe_gap.setRange(1.0, 100.0)
        self.probe_gap.setDecimals(1)
        self.probe_gap.setSingleStep(1.0)
        self.probe_gap.setSuffix(" mm")
        self.probe_gap.setValue(1.0)
        self.probe_gap.setToolTip(
            "Abstand über der Objektoberkante, an dem die Policy gestoppt wird "
            "(--probe-abstand, wie im Reiter Betrieb). Der Arm läuft nach dem Stopp noch "
            "etwas nach — unter %g mm fragt der Start nach." % (1e3 * config.PROBE_GAP_WARN_M))
        form.addRow("Abstand über Objekt", self.probe_gap)
        self.glaettung = block_wheel(QDoubleSpinBox())
        self.glaettung.setRange(0.05, 1.0)
        self.glaettung.setSingleStep(0.05)
        self.glaettung.setDecimals(2)
        self.glaettung.setValue(config.POLICY_COMMAND_LOWPASS_ALPHA)
        self.glaettung.setToolTip("Tiefpass auf die Ziele der Policy, für alle Modelle gleich.")
        form.addRow("Glättung (alpha)", self.glaettung)
        self.regrasp = QCheckBox("Beim Umlegen nachgreifen (Teil mittig)")
        self.regrasp.setChecked(True)
        form.addRow("", self.regrasp)
        for widget in (self.fahrten, self.lagen):
            widget.valueChanged.connect(self._update_plan_text)
        column.addWidget(box)
        column.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)
        panel = QWidget()
        panel.setMinimumWidth(460)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(area, 1)
        self.plan_text = QLabel("")
        self.plan_text.setWordWrap(True)
        self.plan_text.setStyleSheet("color:%s" % NEUTRAL)
        layout.addWidget(self.plan_text)
        row = QHBoxLayout()
        self.btn_start = QPushButton("Vergleich starten")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = QPushButton("STOPP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip("Beendet die laufende Fahrt und bricht den Vergleich ab. "
                                 "Software-Stopp — ersetzt keinen Not-Aus (AP 4.2).")
        self.btn_stop.setStyleSheet(
            "QPushButton:enabled{background:%s; color:white; font-weight:bold}" % BAD)
        self.btn_stop.clicked.connect(self.stop)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        row.addStretch(1)
        layout.addLayout(row)
        return panel

    def _build_output(self):
        splitter = QSplitter(Qt.Orientation.Vertical)
        box = QGroupBox("Stand")
        inner = QVBoxLayout(box)
        self.headline = QLabel("noch nichts gestartet")
        font = QFont()
        font.setBold(True)
        self.headline.setFont(font)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.step_line = QLabel("")
        self.step_line.setStyleSheet("color:%s" % NEUTRAL)
        self.folder_line = QLabel("")
        self.folder_line.setStyleSheet("color:%s" % NEUTRAL)
        self.folder_line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for widget in (self.headline, self.progress_bar, self.step_line, self.folder_line):
            inner.addWidget(widget)
        splitter.addWidget(box)

        box = QGroupBox("Ergebnis je Modell")
        inner = QVBoxLayout(box)
        self.stats = QTreeWidget()
        self.stats.setHeaderLabels(vergleich_module.STATS_HEADER)
        self.stats.setRootIsDecorated(False)
        self.stats.setToolTip(
            "xy = Abstand des vorhergesagten Griffpunkts zum PICK. Streuung je Lage = "
            "größter Abstand zwischen den Griffpunkten DESSELBEN Modells an derselben "
            "Lage (Varianz von Lauf zu Lauf), gemittelt über die Lagen.")
        inner.addWidget(self.stats)
        splitter.addWidget(box)

        box = QGroupBox("Fahrten")
        inner = QVBoxLayout(box)
        self.runs = QTreeWidget()
        self.runs.setHeaderLabels(vergleich_module.RUNS_HEADER)
        self.runs.setRootIsDecorated(False)
        inner.addWidget(self.runs)
        splitter.addWidget(box)

        box = QGroupBox("Ausgabe")
        inner = QVBoxLayout(box)
        self.output = LogView()
        inner.addWidget(self.output)
        splitter.addWidget(box)
        splitter.setSizes([110, 150, 220, 260])
        return splitter

    # -- Modelle --------------------------------------------------------------

    def refresh(self):
        super().refresh()
        self._reload_models()
        self.cameras.refresh(
            backend_is_sim_robot=self.session.backend == session_module.BACKEND_SIM)
        self._update_plan_text()

    def _reload_models(self):
        checked = set(self.selected_models())
        order = [self.models.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.models.count())]
        root = training_module.load_locations(self.workdir)["checkpoints"]
        found = [str(p) for p in operation_module.find_policies(self.workdir, root)]
        found = [p for p in order if p in found] + [p for p in found if p not in order]
        self.models.blockSignals(True)
        self.models.clear()
        for path in found:
            item = QListWidgetItem(vergleich_module.model_name(path))
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if path in checked
                               else Qt.CheckState.Unchecked)
            self.models.addItem(item)
        self.models.blockSignals(False)

    def selected_models(self):
        return [self.models.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.models.count())
                if self.models.item(i).checkState() == Qt.CheckState.Checked]

    def _move(self, delta):
        row = self.models.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self.models.count():
            return
        item = self.models.takeItem(row)
        self.models.insertItem(target, item)
        self.models.setCurrentRow(target)
        self._update_plan_text()

    def _update_plan_text(self, *_):
        models = self.selected_models()
        if not models:
            self.plan_text.setText("Modelle ankreuzen.")
            return
        n = len(models) * self.fahrten.value() * self.lagen.value()
        self.plan_text.setText(
            "%d Fahrten: %d Modell(e) × %d Fahrten × %d Lagen, %d× umlegen. Reihenfolge je Lage: %s."
            % (n, len(models), self.fahrten.value(), self.lagen.value(),
               self.lagen.value() - 1,
               ", ".join("%s ×%d" % (vergleich_module.model_name(m), self.fahrten.value())
                         for m in models)))

    # -- Ablauf ---------------------------------------------------------------

    def _robot_kind(self):
        return "sim" if self.session.backend == session_module.BACKEND_SIM else "neura"

    def _common(self):
        status = self.session.status()
        kind = self._robot_kind()
        return dict(robot_kind=kind,
                    camera_specs=cameras_module.to_specs(self.cameras.assignment(),
                                                         self.cameras.fps()),
                    override=self.session.override if kind == "neura" else None,
                    glaettung=self.glaettung.value(),
                    real_robot=status.is_real_plant)

    def start(self):
        if self.process.running:
            return
        models = self.selected_models()
        try:
            steps = vergleich_module.plan(models, self.fahrten.value(), self.lagen.value())
        except ValueError as exc:
            QMessageBox.information(self, "Vergleich", str(exc))
            return
        assignment = self.cameras.assignment()
        keys = ["torch", "lerobot", "cuda"] + cameras_module.required_backend_keys(assignment)
        if self._robot_kind() == "neura":
            keys.append("neurapy")
        if not self.ensure_requirements("Der Modellvergleich", keys):
            return
        status = self.session.status()
        gap = self.probe_gap.value()
        lines = ["%d Schritte: %s" % (len(steps), self.plan_text.text()), "",
                 "Jede Fahrt: Policy bis %.1f mm über das Objekt, dann senkrecht hoch und "
                 "zurück zum Start. Zwischen den Lagen greift der Experte das Teil und legt "
                 "es an eine neue Lage." % gap,
                 "Backend laut Steuerung: %s" % status.text,
                 "Kameras: %s" % cameras_module.describe(assignment)]
        if gap < 1e3 * config.PROBE_GAP_WARN_M:
            lines.append("ACHTUNG: unter %.0f mm — der Arm läuft nach dem Stopp noch nach."
                         % (1e3 * config.PROBE_GAP_WARN_M))
        if status.is_real_plant:
            lines += ["", "ACHTUNG: Das ist die REALE ANLAGE, nicht die Simulation."]
        lines += ["", "Arbeitsraum frei? Not-Aus in Reichweite?"]
        if not self.confirm("Modellvergleich", "\n".join(lines)):
            return
        if not cameras_module.all_simulated(assignment):
            closed, blocked = self.cameras.share.take_over(CAMERA_OWNER)
            if blocked:
                QMessageBox.information(
                    self, "Kameras belegt",
                    "Die Kameras sind gerade belegt: %s. Erst dort beenden." % ", ".join(blocked))
                return
            for other in closed:
                self.output.append_record("Kameras: %s geschlossen." % other, logging.INFO)
            self.cameras.share.claim(CAMERA_OWNER)
        self._steps, self._index, self._rows, self._stopped = steps, 0, [], False
        self._models = models
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._root = Path(vergleich_module.ROOT) / stamp
        self._meta = {"gestartet": stamp, "modelle_pfade": models,
                      "fahrten_je_lage": self.fahrten.value(), "lagen": self.lagen.value(),
                      "probe_abstand_mm": gap, "glaettung": self.glaettung.value(),
                      "nachgreifen": self.regrasp.isChecked(),
                      "backend": status.text}
        self.stats.clear()
        self.runs.clear()
        self.output.clear()
        self.folder_line.setText("Protokoll: %s" % self._root)
        self.headline.setStyleSheet("font-weight:bold")
        self._set_running(True)
        self._start_step()

    def _start_step(self):
        step = self._steps[self._index]
        argv = vergleich_module.step_argv(step, self._root, self.probe_gap.value(),
                                          regrasp=self.regrasp.isChecked(), **self._common())
        self.headline.setText("Schritt %d von %d" % (self._index + 1, len(self._steps)))
        self.step_line.setText(step.label)
        self.progress_bar.setValue(int(100 * self._index / len(self._steps)))
        self.output.append_record("== %s" % step.label, logging.INFO)
        try:
            self.process.start(argv, stdin_text="ANLAGE\n"
                               if self.session.status().is_real_plant else None)
        except Exception as exc:
            self._finish("Start gescheitert: %s" % exc)

    def _on_line(self, text):
        self.output.append_line(text)

    def _on_finished(self, code, _text):
        if not self._steps:
            return
        step = self._steps[self._index]
        if self._stopped:
            self._finish("Abgebrochen mit STOPP (%s)" % step.label)
            return
        summary = operation_module.read_summary(self.workdir / self._root / step.out)
        row, reason = vergleich_module.evaluate(step, summary, code)
        if row is not None:
            self._rows.append(row)
            item = QTreeWidgetItem(self.runs, vergleich_module.run_row(row))
            item.setForeground(3, QBrush(QColor(GOOD if row["erfolg"] else WARN)))
            self.runs.scrollToItem(item)
            self._show_stats()
        if reason:
            self._finish(reason)
            return
        self._index += 1
        if self._index >= len(self._steps):
            self._finish(None)
            return
        self._start_step()

    def _show_stats(self):
        stats = vergleich_module.aggregate(self._rows, self._models)
        self.stats.clear()
        for stat in stats:
            QTreeWidgetItem(self.stats, vergleich_module.stats_row(stat))
        for column in range(len(vergleich_module.STATS_HEADER)):
            self.stats.resizeColumnToContents(column)
        vergleich_module.write_results(self.workdir / self._root, self._rows, stats,
                                       dict(self._meta, abgeschlossen=False))
        return stats

    def _finish(self, reason):
        stats = vergleich_module.aggregate(self._rows, self._models)
        meta = dict(self._meta or {}, abgeschlossen=reason is None, abbruch=reason)
        if self._root is not None:
            vergleich_module.write_results(self.workdir / self._root, self._rows, stats, meta)
        self._set_running(False)
        self.cameras.share.free(CAMERA_OWNER)
        self._steps = []
        if reason is None:
            self.headline.setText("Fertig: %d Fahrten" % len(self._rows))
            self.headline.setStyleSheet("color:%s; font-weight:bold" % GOOD)
            self.progress_bar.setValue(100)
            self.step_line.setText("Ergebnis: %s" % (self._root / "vergleich.csv"))
        else:
            self.headline.setText("Vergleich beendet nach %d Fahrten" % len(self._rows))
            self.headline.setStyleSheet("color:%s; font-weight:bold" % BAD)
            self.step_line.setText(reason)
            self.output.append_record("Vergleich beendet: %s" % reason, logging.WARNING)

    def stop(self):
        if not self.process.running:
            return
        self._stopped = True
        self.process.stop()
        self.output.append_record(
            "STOPP ausgelöst — Fahrt beendet, Vergleich abgebrochen. Software-Stopp, "
            "ersetzt keinen Not-Aus (AP 4.2).", logging.WARNING)

    def _set_running(self, running):
        for widget in (self.btn_start, self.btn_rescan, self.models, self.cameras,
                       self.fahrten, self.lagen, self.probe_gap, self.glaettung, self.regrasp,
                       self.btn_up, self.btn_down):
            widget.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    # -- Lebenszyklus ---------------------------------------------------------

    def busy_reason(self):
        if self.process.running or self._steps:
            return "Modellvergleich läuft"
        return None

    def shutdown(self):
        if self.process.running:
            self._stopped = True
            self.process.stop()
        self.cameras.share.free(CAMERA_OWNER)
