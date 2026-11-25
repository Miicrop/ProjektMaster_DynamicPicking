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

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import _bootstrap
from .. import config
from . import cameras as cameras_module
from . import operation as operation_module
from . import pick_view as pick_view_module
from . import session as session_module
from . import training as training_module
from . import vergleich as vergleich_module
from .runner import ProcessRunner
from .tab_base import ModeTab
from .widgets import (BAD, GOOD, NEUTRAL, WARN, CameraAssignmentView, CollapsibleBox, LogView,
                      block_wheel)

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
        self._pick_state = pick_view_module.PickState({})
        #: Greiflagen aus dem Training je Modellname (None = nicht vollstaendig)
        self._training = {}
        #: vorab geplante Lagen ab Lage 2 (vergleich.plan_poses) und fuer die
        #: Ansicht je Lage (xy, Drehung) ab Lage 1; Schluessel = (Modelle, Lagen)
        self._plan, self._plan_xy, self._plan_key = [], [], None

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
        self._on_resume_toggled(False)

    # -- Aufbau -------------------------------------------------------------

    def _build_controls(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)

        box = CollapsibleBox("1. Modelle (Reihenfolge wie in der Liste)")
        inner = QVBoxLayout(box.content)
        self.models = QListWidget()
        self.models.setMinimumHeight(140)
        self.models.itemChanged.connect(self._update_plan_text)
        self.models.itemChanged.connect(self._on_models_changed)
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

        box = CollapsibleBox("2. Kameras")
        inner = QVBoxLayout(box.content)
        self.cameras = CameraAssignmentView(self.runner)      # gemeinsam mit den anderen Reitern
        inner.addWidget(self.cameras)
        column.addWidget(box)

        box = CollapsibleBox("3. Ablauf")
        form = QFormLayout(box.content)
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
        self.lagen_wahl = QComboBox()
        self.lagen_wahl.addItem("Raster (systematisch)", vergleich_module.LAGEN_RASTER)
        self.lagen_wahl.addItem("Zufall wie Experte", vergleich_module.LAGEN_ZUFALL)
        self.lagen_wahl.setToolTip(
            "Raster: Lagen gleichmäßig über den Tisch, Abstand nach der Lagenzahl (mehr Lagen = "
            "engeres Raster), Drehungen gleichmäßig über den Drehbereich, Reihenfolge Reihe für "
            "Reihe. Zufall: wie der Experte beim Aufnehmen (seltenstes Feld).")
        form.addRow("Lagenwahl", self.lagen_wahl)
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
        self.lagen.valueChanged.connect(self._drop_stale_plan)
        self.lagen_wahl.currentIndexChanged.connect(self._drop_stale_plan)
        column.addWidget(box)

        box = CollapsibleBox("4. Abgebrochenen Vergleich fortsetzen")
        inner = QVBoxLayout(box.content)
        self.resume = QCheckBox("Fortsetzen statt neu beginnen")
        self.resume.setToolTip(
            "Setzt einen abgebrochenen Vergleich im selben Ordner fort: Modelle, Fahrten, "
            "Lagen und geplante Lagen kommen aus dessen vergleich.json, erledigte Fahrten "
            "werden übernommen, der abgebrochene Schritt wird neu gefahren.")
        self.resume.toggled.connect(self._on_resume_toggled)
        inner.addWidget(self.resume)
        row = QHBoxLayout()
        self.btn_resume_folder = QPushButton("Ordner wählen …")
        self.btn_resume_folder.clicked.connect(self.choose_resume_folder)
        row.addWidget(self.btn_resume_folder)
        row.addStretch(1)
        inner.addLayout(row)
        self.resume_info = QLabel("")
        self.resume_info.setWordWrap(True)
        self.resume_info.setStyleSheet("color:%s" % NEUTRAL)
        inner.addWidget(self.resume_info)
        #: (Ordner relativ zum Arbeitsordner, meta, Schritte, Zeilen, Index, Hinweis)
        self._resume = None
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
        box = CollapsibleBox("Stand")
        inner = QVBoxLayout(box.content)
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

        box = CollapsibleBox("Lagen und aktueller PICK")
        row = QHBoxLayout(box.content)
        self.pick_view = pick_view_module.PickView()
        self.pick_view.setMinimumSize(360, 300)
        self.pick_view.setToolTip(
            "Draufsicht wie im Reiter Betrieb (Roboter unten): Tischpunkte, PICK in der "
            "Steuerung, dazu die Lagen dieses Vergleichs mit Nummer und Greiferrichtung "
            "-- die aktuelle blau.")
        row.addWidget(self.pick_view, 1)
        side = QVBoxLayout()
        self.btn_read_pick = QPushButton("PICK lesen")
        self.btn_read_pick.setToolTip("PICK und Tischpunkte aus der verbundenen Steuerung "
                                      "(Ablauf des ersten gewählten Modells).")
        self.btn_read_pick.clicked.connect(self.read_pick)
        side.addWidget(self.btn_read_pick)
        self.btn_plan = QPushButton("Lagen planen")
        self.btn_plan.setToolTip(
            "Alle Lagen vorab planen und anzeigen (wie der Experte: seltenstes Feld, "
            "frühere Ablagen zählen mit, nur erreichbare). Lage 1 = aktueller PICK. "
            "Ohne Planung wählt der Experte bei jedem Umlegen selbst.")
        self.btn_plan.clicked.connect(self.plan_lagen)
        side.addWidget(self.btn_plan)
        side.addWidget(QLabel("Abdeckung aus dem Training von"))
        self.heat_model = QComboBox()
        self.heat_model.setToolTip(
            "Heatmap: wo dieses Modell im Training gegriffen hat (2-cm-Felder, dunkler = "
            "mehr Episoden). Ohne vollständige Greifposen im Modell: keine Heatmap.")
        self.heat_model.currentIndexChanged.connect(lambda *_: self._show_pick())
        side.addWidget(self.heat_model)
        self.pick_info = QLabel(pick_view_module.state_text(None))
        self.pick_info.setWordWrap(True)
        self.pick_info.setStyleSheet("color:%s" % NEUTRAL)
        side.addWidget(self.pick_info)
        side.addStretch(1)
        row.addLayout(side, 1)
        splitter.addWidget(box)

        box = CollapsibleBox("Ergebnis je Modell")
        inner = QVBoxLayout(box.content)
        self.stats = QTreeWidget()
        self.stats.setHeaderLabels(vergleich_module.STATS_HEADER)
        self.stats.setRootIsDecorated(False)
        self.stats.setToolTip(
            "quer/längs = Versatz des vorhergesagten Griffpunkts im Objekt-KS (Beträge), "
            "Spiel min = kleinstes Restspiel einer Backe (Griffprüfung). "
            "xy = Abstand des vorhergesagten Griffpunkts zum PICK. Streuung je Lage = "
            "größter Abstand zwischen den Griffpunkten DESSELBEN Modells an derselben "
            "Lage (Varianz von Lauf zu Lauf), gemittelt über die Lagen.")
        inner.addWidget(self.stats)
        splitter.addWidget(box)

        box = CollapsibleBox("Fahrten")
        inner = QVBoxLayout(box.content)
        self.runs = QTreeWidget()
        self.runs.setHeaderLabels(vergleich_module.RUNS_HEADER)
        self.runs.setRootIsDecorated(False)
        inner.addWidget(self.runs)
        splitter.addWidget(box)

        box = CollapsibleBox("Ausgabe")
        inner = QVBoxLayout(box.content)
        self.output = LogView()
        inner.addWidget(self.output)
        splitter.addWidget(box)
        splitter.setSizes([110, 340, 140, 180, 180])
        return splitter

    # -- Modelle --------------------------------------------------------------

    def refresh(self):
        super().refresh()
        self._reload_models()
        self._on_models_changed()
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

    # -- PICK und Lagen -------------------------------------------------------

    def read_pick(self, quiet=False):
        """PICK und Tischpunkte aus der Steuerung (wie im Reiter Betrieb)."""
        robot = self.session.robot
        models = self.selected_models()
        if robot is None or not models:
            if not quiet:
                QMessageBox.information(self, "PICK lesen",
                                        "Erst oben verbinden und ein Modell ankreuzen.")
            return
        described = operation_module.describe_policy(self.workdir / models[0]) or {}
        text = described.get("sequence_file")
        if not text:
            if not quiet:
                QMessageBox.information(self, "PICK lesen", "Das Modell nennt keinen Ablauf.")
            return
        path = Path(text) if Path(text).is_absolute() else self.workdir / text
        try:
            state = pick_view_module.read_pick_state(robot, path)
        except Exception as exc:
            if not quiet:
                QMessageBox.warning(self, "PICK nicht lesbar", "%s: %s" % (type(exc).__name__, exc))
            log.warning("Vergleich: PICK nicht lesbar: %s", exc)
            return
        state.lagen = self._pick_state.lagen
        self._pick_state = state
        self._show_pick()

    def _on_models_changed(self, *_):
        """Abdeckung aus dem Training der gewaehlten Modelle neu laden."""
        self._training = {}
        for model in self.selected_models():
            info = operation_module._read_json(
                operation_module.policy_dir(self.workdir / model) / operation_module.POLICY_MARKER)
            self._training[vergleich_module.model_name(model)] = vergleich_module.training_xy(info)
        if hasattr(self, "heat_model"):
            current = self.heat_model.currentText()
            self.heat_model.blockSignals(True)
            self.heat_model.clear()
            for name, train in self._training.items():
                self.heat_model.addItem(name if train is not None
                                        else "%s (keine vollständigen Greifposen)" % name, name)
            index = self.heat_model.findText(current)
            self.heat_model.setCurrentIndex(index if index >= 0 else 0)
            self.heat_model.blockSignals(False)
        self._drop_stale_plan()

    def _drop_stale_plan(self, *_):
        """Plan passt nicht mehr zu Modellen/Lagen -> nicht mehr zeigen."""
        if self._plan_key is not None and self._plan_key != self._plan_key_now():
            self._plan, self._plan_xy, self._plan_key = [], [], None
        if hasattr(self, "pick_view") and not self._steps:
            self._show_pick()

    def _current_lage(self):
        if self._steps:
            step = self._steps[self._index]
            return step.lage + 1 if step.kind == vergleich_module.UMLEGEN else step.lage
        return None

    def _plan_key_now(self):
        return (tuple(self.selected_models()), self.lagen.value(), self.lagen_wahl.currentData())

    def plan_lagen(self, quiet=False):
        """Alle Lagen vorab planen (vergleich.plan_poses) -- braucht die Steuerung."""
        from .. import known_pose
        from ..kinematics import IKFailure, Kinematics
        from ..table import yaw_deg

        robot, models = self.session.robot, self.selected_models()
        if robot is None or not models:
            if not quiet:
                QMessageBox.information(self, "Lagen planen",
                                        "Erst oben verbinden und ein Modell ankreuzen.")
            return False
        info = operation_module._read_json(
            operation_module.policy_dir(self.workdir / models[0]) / operation_module.POLICY_MARKER)
        text = (info.get("table_spec") or {}).get("sequence_file")
        try:
            if not text:
                raise ValueError("das Modell nennt keinen Ablauf")
            path = Path(text) if Path(text).is_absolute() else self.workdir / text
            known, _resolved = known_pose.load(path, robot)
            kin = Kinematics(robot)
            start = info.get("start_joints")
            seed = np.asarray(start if start is not None else robot.read_state().joints, dtype=float)
            center = None
            if config.AUTO_YAW_CENTER_POINT and start is not None:
                from ..live import yaw360
                start_pose = np.asarray(robot.fk(seed), dtype=float)
                center = ((yaw360(start_pose, known.table) - yaw360(known.pick, known.table)
                           + 180.0) % 360.0 - 180.0)

            def reachable(pose):
                up = np.asarray(pose, dtype=float).copy()
                up[2] += 0.05
                try:
                    kin.ik(np.asarray(pose, dtype=float), seed)
                    kin.ik(up, seed)
                    return True
                except IKFailure:
                    return False

            history = known_pose.placement_history(known_pose.placements_file(
                self.workdir / config.TOUCHUP_BACKUP_ROOT))
            if self.lagen_wahl.currentData() == vergleich_module.LAGEN_RASTER:
                planned = vergleich_module.plan_grid_poses(known, self.lagen.value() - 1,
                                                           center_shift_deg=center,
                                                           reachable=reachable)
                if planned:
                    self.output.append_record("Lagen im Raster: %d mm Abstand, %d Lagen"
                                              % (round(planned[0]["raster_mm"]), len(planned)))
            else:
                planned = vergleich_module.plan_poses(known, self.lagen.value() - 1,
                                                      np.random.default_rng(), history=history,
                                                      center_shift_deg=center, reachable=reachable)
        except Exception as exc:
            log.warning("Vergleich: Lagen nicht planbar: %s", exc)
            if not quiet:
                QMessageBox.warning(self, "Lagen nicht planbar", "%s: %s" % (type(exc).__name__, exc))
            return False
        self._plan = planned
        self._plan_xy = [((float(known.pick[0]), float(known.pick[1])),
                          float(yaw_deg(known.pick, known.table)))]
        self._plan_xy += [(p["xy"], float(yaw_deg(np.asarray(p["pose"]), known.table)))
                          for p in planned]
        self._plan_key = self._plan_key_now()
        if len(planned) < self.lagen.value() - 1:
            self.output.append_record("Nur %d von %d Lagen planbar -- den Rest wählt der "
                                      "Experte beim Umlegen selbst."
                                      % (len(planned), self.lagen.value() - 1), logging.WARNING)
        self._show_pick()
        return True

    def _show_pick(self, placed_xy=None, current=None):
        state = self._pick_state
        state.training_xy = [tuple(p) for train in self._training.values() if train is not None
                             for p in train]
        chosen = self.heat_model.currentData() if hasattr(self, "heat_model") else None
        state.heat = vergleich_module.heat_grid(self._training.get(chosen))
        state.lagen = vergleich_module.lagen_view(
            self._rows, self._plan_xy, self._current_lage() if current is None else current,
            self._training, None if self._plan_xy else placed_xy)
        current = next((lage for lage in state.lagen if lage["current"]), None)
        if current is not None:
            state.pick = tuple(current["xy"])
            if current.get("yaw_deg") is not None:
                state.pick_yaw_deg = current["yaw_deg"]
            state.warnings = []
        self.pick_view.set_state(state)
        lines = [pick_view_module.state_text(state) if state.table_points else (
            "Lage %s: x %.1f  y %.1f mm" % (current["label"], 1e3 * current["xy"][0],
                                             1e3 * current["xy"][1]) if current
            else pick_view_module.state_text(None))]
        if current is not None and self._training:
            bits = []
            for name, train in self._training.items():
                d = vergleich_module.training_distance(current["xy"], train)
                bits.append("%s %s" % (name, "keine vollständige Abdeckung" if d is None
                                       else "%.0f mm" % (1e3 * d)))
            lines.append("Nächste Trainingslage: " + ", ".join(bits))
        lines.append("Heatmap = Greiflagen im Training des gewählten Modells · Nummer grün = für alle Modelle "
                     "bekannt (≤ %.0f mm), gelb = für einige, orange = für keines · "
                     "gestrichelt = geplant, blau = aktuell"
                     % (1e3 * vergleich_module.KNOWN_RADIUS_M))
        self.pick_info.setText("\n".join(lines))

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

    # -- Fortsetzen -------------------------------------------------------------

    def _on_resume_toggled(self, on):
        self.btn_resume_folder.setEnabled(bool(on))
        for widget in (self.models, self.fahrten, self.lagen, self.lagen_wahl,
                       self.btn_up, self.btn_down, self.btn_plan):
            widget.setEnabled(not on)
        if not on:
            self._resume = None
            self.resume_info.setText("")
        elif self._resume is None:
            self.resume_info.setText("Ordner des abgebrochenen Vergleichs wählen "
                                     "(unter %s)." % vergleich_module.ROOT)
        self.btn_start.setText("Vergleich fortsetzen" if on else "Vergleich starten")

    def choose_resume_folder(self):
        from PySide6.QtWidgets import QFileDialog

        start = self.workdir / vergleich_module.ROOT
        folder = QFileDialog.getExistingDirectory(self, "Abgebrochenen Vergleich wählen",
                                                  str(start if start.exists() else self.workdir))
        if folder:
            self.load_resume(folder)

    def load_resume(self, folder):
        """Stand eines frueheren Vergleichs lesen und anzeigen; True, wenn fortsetzbar."""
        folder = Path(folder)
        try:
            meta = vergleich_module.load_meta(folder)
            models = list(meta["modelle_pfade"])
            missing = [m for m in models if not (self.workdir / m).exists() and not Path(m).exists()]
            if missing:
                raise ValueError("Modell nicht gefunden: %s" % ", ".join(missing))
            steps = vergleich_module.plan(models, int(meta["fahrten_je_lage"]), int(meta["lagen"]))
        except ValueError as exc:
            self._resume = None
            self.resume_info.setText("Nicht fortsetzbar: %s" % exc)
            self.resume_info.setStyleSheet("color:%s" % BAD)
            return False
        vergleich_module.attach_targets(steps, [{"pose": p} for p in meta.get("geplante_lagen") or []])
        rows, index, note = vergleich_module.resume_point(folder, steps,
                                                          operation_module.read_summary)
        try:
            root = folder.resolve().relative_to(self.workdir.resolve())
        except ValueError:
            root = folder
        self._resume = (root, meta, steps, rows, index, note)
        lage = steps[index].lage + 1 if index < len(steps) else meta["lagen"]
        if index >= len(steps):
            text = "Dieser Vergleich ist schon vollständig (%d Fahrten)." % len(rows)
            colour = WARN
        else:
            text = ("%s: %d von %d Schritten erledigt (%d Fahrten), weiter bei Lage %d von %d -- "
                    "%s.\nAbbruch: %s" % (folder.name, index, len(steps), len(rows), lage,
                                          meta["lagen"], steps[index].label, note or "-"))
            colour = NEUTRAL
        self.resume_info.setText(text)
        self.resume_info.setStyleSheet("color:%s" % colour)
        # Einstellungen des alten Laufs anzeigen (die Liste bleibt gesperrt)
        self._select_models(models)
        self.fahrten.setValue(int(meta["fahrten_je_lage"]))
        self.lagen.setValue(int(meta["lagen"]))
        if meta.get("probe_abstand_mm"):
            self.probe_gap.setValue(float(meta["probe_abstand_mm"]))
        if meta.get("glaettung"):
            self.glaettung.setValue(float(meta["glaettung"]))
        if "nachgreifen" in meta:
            self.regrasp.setChecked(bool(meta["nachgreifen"]))
        return index < len(steps)

    def _select_models(self, models):
        """Genau ``models`` in dieser Reihenfolge ankreuzen (vorn in der Liste)."""
        items = [self.models.takeItem(0) for _ in range(self.models.count())]
        by_path = {item.data(Qt.ItemDataRole.UserRole): item for item in items}
        self.models.blockSignals(True)
        for path in models:
            item = by_path.pop(path, None)
            if item is None:
                item = QListWidgetItem(vergleich_module.model_name(path))
                item.setToolTip(path)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.models.addItem(item)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole) in by_path:
                item.setCheckState(Qt.CheckState.Unchecked)
                self.models.addItem(item)
        self.models.blockSignals(False)
        self._update_plan_text()
        self._on_models_changed()

    def _add_row(self, row):
        """Fahrt in die Tabelle (mit Trainingsabstand) und in ``self._rows``."""
        if row.get("pick_x_mm") is not None:
            d = vergleich_module.training_distance(
                (row["pick_x_mm"] / 1e3, row["pick_y_mm"] / 1e3),
                self._training.get(row["modell"]))
            row["trainingsabstand_mm"] = None if d is None else round(1e3 * d, 1)
            row["trainingslagen_umkreis"] = vergleich_module.training_density(
                (row["pick_x_mm"] / 1e3, row["pick_y_mm"] / 1e3),
                self._training.get(row["modell"]))
        self._rows.append(row)
        item = QTreeWidgetItem(self.runs, vergleich_module.run_row(row))
        stop_col = len(vergleich_module.RUNS_HEADER) - 1
        item.setToolTip(stop_col, str(row["stopp"] or ""))   # Abbruchgrund im Wortlaut
        item.setToolTip(3, row.get("gruende") or "")          # Griffpruefung
        colour = {"erfolg": GOOD, "warnung": WARN}.get(row.get("bewertung"),
                                                       GOOD if row["erfolg"] else BAD)
        item.setForeground(3, QBrush(QColor(colour)))
        level = vergleich_module.clearance_level(row.get("spiel_min_mm"))
        if level is not None:
            column = vergleich_module.RUNS_HEADER.index("Spiel min")
            item.setForeground(column, QBrush(QColor(
                {"schlecht": BAD, "knapp": WARN, "gut": GOOD}[level])))
            item.setToolTip(column, "Restspiel der knapperen Backe: unter 0 trifft sie das "
                                    "Objekt, unter %.1f mm knapp" % (1e3 * config.GRASP_SAFETY_M))
        self.runs.scrollToItem(item)

    def _start_resume(self):
        if self._resume is None or self._resume[4] >= len(self._resume[2]):
            QMessageBox.information(self, "Vergleich fortsetzen",
                                    self.resume_info.text() or "Erst einen Ordner wählen.")
            return
        root, meta, steps, rows, index, note = self._resume
        # neu einlesen: der Ordner koennte sich seit der Auswahl geaendert haben
        if not self.load_resume(self.workdir / root):
            return
        root, meta, steps, rows, index, note = self._resume
        assignment = self.cameras.assignment()
        keys = ["torch", "lerobot", "cuda"] + cameras_module.required_backend_keys(assignment)
        if self._robot_kind() == "neura":
            keys.append("neurapy")
        if not self.ensure_requirements("Der Modellvergleich", keys):
            return
        status = self.session.status()
        step = steps[index]
        lines = ["Fortsetzen: %s" % root,
                 "%d von %d Schritten erledigt, %d Fahrten übernommen." % (index, len(steps),
                                                                           len(rows)),
                 "Weiter mit: %s" % step.label, "Abbruch damals: %s" % (note or "-"), ""]
        if step.kind == vergleich_module.UMLEGEN:
            lines.append("ACHTUNG: Es geht mit dem UMLEGEN weiter. Liegt das Teil noch am PICK "
                         "der Steuerung (nicht im Greifer, nicht schon umgelegt)?")
        else:
            lines.append("Liegt das Teil am PICK der Steuerung (Lage %d)? Sonst erst den PICK "
                         "nachführen (Reiter Betrieb)." % (step.lage + 1))
        lines += ["Backend laut Steuerung: %s" % status.text,
                  "Kameras: %s" % cameras_module.describe(assignment)]
        if status.is_real_plant:
            lines += ["", "ACHTUNG: Das ist die REALE ANLAGE, nicht die Simulation."]
        lines += ["", "Arbeitsraum frei? Not-Aus in Reichweite?"]
        if not self.confirm("Modellvergleich fortsetzen", "\n".join(lines)):
            return
        if not self._take_cameras(assignment):
            return
        # Ordner des abgebrochenen Schritts beiseite (nicht loeschen)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        broken = self.workdir / root / step.out
        if broken.exists():
            broken.rename(broken.with_name("%s_abgebrochen_%s" % (broken.name, stamp)))
        self._steps, self._index, self._rows, self._stopped = steps, index, [], False
        self._models = list(meta["modelle_pfade"])
        self._root = Path(root)
        self._meta = {k: v for k, v in meta.items()
                      if k not in ("modelle", "fahrten", "abgeschlossen", "abbruch")}
        self._meta["fortgesetzt"] = list(meta.get("fortgesetzt") or []) + [
            {"zeit": stamp, "ab_schritt": index + 1, "abbruch_vorher": meta.get("abbruch")}]
        self._plan = [{"pose": p} for p in meta.get("geplante_lagen") or []]
        self.stats.clear()
        self.runs.clear()
        self.output.clear()
        for row in rows:
            self._add_row(row)
        self._show_stats()
        self.folder_line.setText("Protokoll: %s (fortgesetzt)" % self._root)
        self.headline.setStyleSheet("font-weight:bold")
        self.read_pick(quiet=True)
        self._show_pick()
        self.output.append_record("Fortgesetzt ab Schritt %d von %d (%s)"
                                  % (index + 1, len(steps), step.label), logging.INFO)
        self._set_running(True)
        self._start_step()

    def _take_cameras(self, assignment):
        if cameras_module.all_simulated(assignment):
            return True
        closed, blocked = self.cameras.share.take_over(CAMERA_OWNER)
        if blocked:
            QMessageBox.information(
                self, "Kameras belegt",
                "Die Kameras sind gerade belegt: %s. Erst dort beenden." % ", ".join(blocked))
            return False
        for other in closed:
            self.output.append_record("Kameras: %s geschlossen." % other, logging.INFO)
        self.cameras.share.claim(CAMERA_OWNER)
        return True

    def start(self):
        if self.process.running:
            return
        if self.resume.isChecked():
            self._start_resume()
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
        if not self._take_cameras(assignment):
            return
        self._steps, self._index, self._rows, self._stopped = steps, 0, [], False
        self._models = models
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._root = Path(vergleich_module.ROOT) / stamp
        self._meta = {"gestartet": stamp, "modelle_pfade": models,
                      "fahrten_je_lage": self.fahrten.value(), "lagen": self.lagen.value(),
                      "probe_abstand_mm": gap, "glaettung": self.glaettung.value(),
                      "nachgreifen": self.regrasp.isChecked(),
                      "lagenwahl": self.lagen_wahl.currentData(),
                      "backend": status.text}
        self.stats.clear()
        self.runs.clear()
        self.output.clear()
        self.folder_line.setText("Protokoll: %s" % self._root)
        self.headline.setStyleSheet("font-weight:bold")
        self.read_pick(quiet=True)          # Tischpunkte fuer die Ansicht, falls verbunden
        if self._plan_key != self._plan_key_now():
            self._plan, self._plan_xy, self._plan_key = [], [], None
            if self.session.robot is not None:
                self.plan_lagen(quiet=True)
        vergleich_module.attach_targets(steps, self._plan)
        self._meta["geplante_lagen"] = [p["pose"] for p in self._plan]
        self._show_pick()
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
        # Ausgabe des Schritts mitschreiben (Anlage 2026-11-25: Lage 9 brach mit
        # Rueckgabewert 1 ab, bevor infer.py den Ordner anlegte -- der Grund
        # stand nur im Ausgabefeld)
        self._log_path = self.workdir / self._root / step.out / vergleich_module.STEP_LOG
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write("== %s  %s\n%s\n" % (datetime.now().isoformat(timespec="seconds"),
                                                   step.label, " ".join(map(str, argv))))
        except OSError as exc:
            self._log_path = None
            self.output.append_record("Ausgabe wird nicht mitgeschrieben (%s)" % exc,
                                      logging.WARNING)
        try:
            self.process.start(argv, stdin_text="ANLAGE\n"
                               if self.session.status().is_real_plant else None)
        except Exception as exc:
            self._finish("Start gescheitert: %s" % exc)

    def _on_line(self, text):
        self.output.append_line(text)
        self._write_log(text)

    def _write_log(self, text):
        if getattr(self, "_log_path", None) is None:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write(str(text).rstrip("\n") + "\n")
        except OSError:
            self._log_path = None

    def _on_finished(self, code, _text):
        if not self._steps:
            return
        step = self._steps[self._index]
        self._write_log("== Ende, Rueckgabewert %s" % code)
        if self._stopped:
            self._finish("Abgebrochen mit STOPP (%s)" % step.label)
            return
        summary = operation_module.read_summary(self.workdir / self._root / step.out)
        row, reason = vergleich_module.evaluate(step, summary, code)
        if row is not None:
            self._add_row(row)
            self._show_stats()
        if step.kind == vergleich_module.UMLEGEN and not reason:
            self._show_pick((summary.get("umlegen") or {}).get("placed_xy"), current=step.lage + 1)
        elif row is not None:
            self._show_pick()
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
        if self.resume.isChecked() and self._root is not None:
            self.load_resume(self.workdir / self._root)     # Stand fuer ein weiteres Fortsetzen
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
                       self.fahrten, self.lagen, self.lagen_wahl, self.probe_gap, self.glaettung, self.regrasp,
                       self.btn_up, self.btn_down, self.btn_read_pick, self.btn_plan,
                       self.resume, self.btn_resume_folder):
            widget.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        if not running:
            self._on_resume_toggled(self.resume.isChecked())

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
