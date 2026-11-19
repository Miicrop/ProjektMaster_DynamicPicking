"""Modus "Betrieb": Modell laden und die Policy fahren lassen.

Aufbau des Reiters:

    1. Modell    Checkpoint waehlen; darunter steht, woraus er stammt und
                 unter welchen Randbedingungen er trainiert wurde.
    2. Kameras   Welches Geraet auf welchem Platz. Muss zur Aufzeichnung
                 passen -- die Pruefung darunter sagt das VORHER.
    3. Fahrt     Fahrten, Takte, Neuvorhersage, Geraet, Echtzeit.
    4. Test      Policy-Test mit bekannter Lage (PICK aus der Steuerung, je
                 Takt die Abweichung; Probegriff 3 mm ueber Tisch oder ueber
                 dem Objekt) mit Draufsicht auf den aktuellen PICK, und die
                 Kamerapruefung gegen die Aufnahme des Modells.

Die Ampel oben im Fenster gilt auch hier: Rot heisst reale Anlage. Der
Stoppknopf beendet den Unterprozess -- ein SOFTWARE-Stopp, der keinen
zertifizierten Not-Aus ersetzt (AP 4.2).

Bewusst NICHT gebaut: die Uebergabe an die andere Gruppe bei PRE_PLACE. Die
braucht eine zweite Schnittstelle (Uebergabe der Roboterhoheit statt eines
Rueckgabewerts) und damit eine Absprache -- siehe unten "Offen".
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QSpinBox, QSplitter, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from . import _bootstrap
from .. import config
from . import cameras as cameras_module
from . import operation as operation_module
from . import pick_view as pick_view_module
from . import session as session_module
from . import training as training_module
from .runner import ProcessRunner
from .tab_base import ModeTab
from .widgets import (BAD, GOOD, LogView, NEUTRAL, WARN,
                      CameraAssignmentView, block_wheel, find_data)

log = logging.getLogger(__name__)


class OperationTab(ModeTab):
    mode = "operation"
    title = "Betrieb"

    def __init__(self, session, runner, parent=None):
        super().__init__(session, runner, parent)
        self.workdir = Path(_bootstrap.WORKDIR)
        self.process = ProcessRunner(self)
        self.process.line.connect(self._on_line)
        self.process.finished.connect(self._on_finished)
        self.process.started.connect(self._on_started)
        self._progress = None
        self._described = None
        self._problems = []
        self._out_dir = None
        self._pick_state = None

        left = self._build_controls()
        right = self._build_output()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 780])

        layout = QVBoxLayout(self)
        layout.addWidget(self.requirement_view)
        layout.addWidget(splitter, 1)

        session.add_listener(self._on_session_status)
        self.refresh()

    # -- Aufbau: Bedienseite ------------------------------------------------

    def _build_controls(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self._build_model_box())
        column.addWidget(self._build_camera_box())
        column.addWidget(self._build_run_box())
        column.addWidget(self._build_test_box())
        column.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(page)

        panel = QWidget()
        panel.setMinimumWidth(500)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(area, 1)
        layout.addWidget(self._build_action_bar(), 0)
        return panel

    def _build_model_box(self):
        box = QGroupBox("1. Modell")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        self.checkpoint = block_wheel(QComboBox())
        self.checkpoint.currentIndexChanged.connect(self._on_checkpoint_changed)
        row.addWidget(self.checkpoint, 1)
        self.btn_rescan = QPushButton("Neu suchen")
        self.btn_rescan.clicked.connect(self.refresh)
        row.addWidget(self.btn_rescan)
        layout.addLayout(row)

        self.model_info = _hint("")
        layout.addWidget(self.model_info)

        self.hold = QCheckBox("Ohne Modell fahren (Verdrahtungstest)")
        self.hold.setToolTip(
            "HoldPolicy statt Policy: die Kette aus Takt, Servo-Interpolation "
            "und Kameras läuft, der Arm hält die Stellung. Damit prüft man die "
            "Verdrahtung, bevor ein Modell drankommt.")
        self.hold.toggled.connect(self._on_hold_toggled)
        layout.addWidget(self.hold)
        return box

    def _build_camera_box(self):
        box = QGroupBox("2. Kameras")
        layout = QVBoxLayout(box)
        self.cameras = CameraAssignmentView(self.runner)
        self.cameras.changed.connect(self._on_cameras_changed)
        layout.addWidget(self.cameras)
        return box

    def _build_run_box(self):
        box = QGroupBox("3. Fahrt")
        layout = QVBoxLayout(box)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.episodes = block_wheel(QSpinBox())
        self.episodes.setRange(1, 200)
        self.episodes.setValue(1)
        self.episodes.valueChanged.connect(self._update_command)
        form.addRow("Fahrten", self.episodes)

        self.max_steps = block_wheel(QSpinBox())
        self.max_steps.setRange(0, 100000)
        self.max_steps.setSingleStep(10)
        self.max_steps.setSpecialValueText("aus dem Modell")
        self.max_steps.setToolTip(
            "Höchstzahl Takte je Fahrt. 0 = 1.5 × längste Episode der "
            "Aufzeichnung (Default von apps/infer.py).")
        self.max_steps.valueChanged.connect(self._update_command)
        form.addRow("Takte je Fahrt", self.max_steps)

        self.replan = block_wheel(QSpinBox())
        self.replan.setRange(0, 64)
        self.replan.setSpecialValueText("aus dem Modell")
        self.replan.setToolTip(
            "Alle N Takte neu vorhersagen. Kleiner = reaktiver, aber mehr "
            "GPU-Last; die Vorhersage dauert ~77 ms und damit länger als ein "
            "Takt (67 ms).")
        self.replan.valueChanged.connect(self._update_command)
        form.addRow("Neu vorhersagen", self.replan)

        self.device = block_wheel(QComboBox())
        self.device.currentIndexChanged.connect(self._update_command)
        form.addRow("Gerät", self.device)

        # Derselbe Wert wie oben in der Backend-Leiste. Wird ein Modell
        # gewaehlt, setzt der Reiter ihn auf den der Aufzeichnung: ein
        # anderer Wert laesst apps/infer.py ohnehin abbrechen (AP 2.6).
        self.override = block_wheel(QDoubleSpinBox())
        self.override.setRange(0.05, 1.0)
        self.override.setSingleStep(0.05)
        self.override.setDecimals(2)
        self.override.setValue(float(self.session.override))
        self.override.setToolTip(
            "Geschwindigkeits-Override am Neura — dieselbe Zahl wie oben in "
            "der Backend-Leiste. Muss dem der Aufzeichnung entsprechen, das "
            "Tempo ist mitgelernt (AP 2.6); apps/infer.py erzwingt das.")
        self.override.valueChanged.connect(self.session.set_override)
        form.addRow("Override", self.override)

        layout.addLayout(form)

        self.realtime = QCheckBox("SimRobot mit echter Uhr (Echtzeit)")
        self.realtime.setToolTip(
            "Ohne Haken läuft der SimRobot mit der Simulationsuhr, die "
            "Vorhersagedauer fällt dann nicht ins Gewicht. Mit Haken wirkt "
            "die Latenz wie an der Anlage.")
        self.realtime.toggled.connect(self._update_command)
        layout.addWidget(self.realtime)

        self.no_ensemble = QCheckBox("Chunks nicht mitteln (Vergleichslauf)")
        self.no_ensemble.toggled.connect(self._update_command)
        layout.addWidget(self.no_ensemble)

        row = QHBoxLayout()
        row.addWidget(QLabel("Protokoll"))
        self.out = QLineEdit()
        self.out.setPlaceholderText("Default: <Modell>/rollouts/<Zeit>")
        self.out.textChanged.connect(self._update_command)
        row.addWidget(self.out, 1)
        layout.addLayout(row)

        return box

    def _build_test_box(self):
        """Policy-Test mit bekannter Lage und Kamerapruefung (Anwender 2026-11-16)."""
        box = QGroupBox("4. Policy-Test und Kameras")
        layout = QVBoxLayout(box)

        self.known = QCheckBox("Lage bekannt (Policy-Test gegen PICK)")
        self.known.setToolTip(
            "PICK und Tisch live aus der Steuerung, Idealbahn aus der Ablaufdatei der "
            "Aufnahme. Je Takt Abweichung zur Bahn, zu PICK und Höhe über dem Tisch; "
            "am Griff bzw. Stopp die Lage gegen PICK. Die Policy endet mit dem Griff, "
            "danach Greifer auf, anheben, zurück zum Start. Ergebnis zusätzlich in "
            "policy_test.csv im Protokollordner.")
        self.known.toggled.connect(self._on_known_toggled)
        layout.addWidget(self.known)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.probe = block_wheel(QComboBox())
        # Standard: Probegriff ueber dem Objekt (Anwender 2026-11-17: keine Crashs mehr);
        # "Tisch" nur bewusst waehlen
        self.probe.addItem("Probegriff (über Objekt, Abstand unten)", "objekt")
        self.probe.addItem("Echter Griff (%g mm über Tisch)" % (1e3 * config.TABLE_MIN_CLEARANCE_M), "tisch")
        self.probe.setToolTip(
            "Probegriff: der Geofence hält die Werkzeugspitze den eingestellten Abstand "
            "über der Objektoberkante (Standard %g mm; Nachlauf nach dem Stopp an der "
            "Anlage bis 7,5 mm — schrittweise annähern). Beim Stopp wird der Rest der Vorhersage gespeichert — "
            "daraus der Greifpunkt, an dem die Policy gegriffen hätte.\n"
            "1 Fahrt: der Arm bleibt über dem Objekt stehen (Spiel prüfen).\n"
            "Mehrere Fahrten: der Experte korrigiert auf derselben Höhe xy und "
            "Drehung auf PICK, senkt ab, greift, legt das Objekt an eine neue Lage "
            "und führt PICK nach (Korrektur in policy_test.csv, Bahn in "
            "experte_XXX.npz)." % (1e3 * config.PROBE_GAP_M))
        self.probe.currentIndexChanged.connect(self._on_probe_changed)
        form.addRow("Ende", self.probe)
        self.probe_gap = block_wheel(QDoubleSpinBox())
        self.probe_gap.setRange(1.0, 100.0)
        self.probe_gap.setDecimals(1)
        self.probe_gap.setSingleStep(1.0)
        self.probe_gap.setSuffix(" mm")
        self.probe_gap.setValue(1e3 * config.PROBE_GAP_M)
        self.probe_gap.setToolTip(
            "Abstand der Werkzeugspitze über der Objektoberkante beim Probegriff "
            "(--probe-abstand). Standard %g mm. Der Arm läuft nach dem Stopp bis "
            "7,5 mm nach (Anlage 2026-11-17) — unter %g mm fragt die Oberfläche nach."
            % (1e3 * config.PROBE_GAP_M, 1e3 * config.PROBE_GAP_WARN_M))
        self.probe_gap.valueChanged.connect(self._update_command)
        form.addRow("Abstand über Objekt", self.probe_gap)
        self.expert = QCheckBox("Experte greift und legt um")
        self.expert.setChecked(True)
        self.expert.setToolTip(
            "An: nach dem Stopp über dem Objekt korrigiert der Planer auf PICK, greift, "
            "legt das Teil an eine neue Lage (Voraussetzung für DAgger).\n"
            "Aus: nur anfliegen und messen -- die Policy hält über dem Objekt, gespeichert "
            "wird, wohin sie noch wollte; dann senkrecht anheben und zurück zum Start. "
            "Das Teil wird nicht berührt (z. B. wenn die M1-Lage nicht sicher stimmt).")
        self.expert.toggled.connect(self._on_probe_changed)
        form.addRow("", self.expert)
        self.sequence = QLineEdit()
        self.sequence.setPlaceholderText("aus dem Modell")
        self.sequence.textChanged.connect(self._update_command)
        form.addRow("Ablauf", self.sequence)
        self.pick_source = block_wheel(QComboBox())
        self.pick_source.addItem("PICK aus der Steuerung", "steuerung")
        self.pick_source.addItem("PICK aus M1 (Lokalisierung)", "m1")
        self.pick_source.setToolTip(
            "M1: vor jeder Fahrt an die Fotostellung, die Objekterkennung der Gruppe "
            "bestimmt Lage und Drehung aus dem Bild der Szenenkamera, PICK wird in der "
            "Steuerung gesetzt (Sicherung wie Touch-up). Das Teil darf irgendwo im "
            "Arbeitsbereich zwischen den Markern liegen (bc/lokalisierung.py).")
        self.pick_source.currentIndexChanged.connect(self._on_pick_source_changed)
        form.addRow("PICK", self.pick_source)
        self.photo_point = QLineEdit(config.LOCALIZE_POINT)
        self.photo_point.setToolTip(
            "Steuerungspunkt, an dem der Arm aus dem Bild der Draufsichtkamera ist "
            "(alle vier Marker und das Teil sichtbar). Standard: CLEAR_FOV aus dem "
            "Ablauf; steht der Arm nicht dort, fährt er vor dem Foto selbst hin.")
        self.photo_point.textChanged.connect(self._update_command)
        form.addRow("Fotostellung", self.photo_point)
        # Vorbelegt (Anlage 2026-11-17: Feld war leer, DAgger lief nie mit)
        from datetime import date
        self.dagger_dir = QLineEdit("data/%s_dagger" % date.today().isoformat())
        self.dagger_dir.setPlaceholderText("leer = nicht mitschreiben")
        self.dagger_dir.setToolTip(
            "Nur Probegriff mit Experte: jede Fahrt (Policy + Korrektur) mit Bildern als "
            "Episode im Aufnahmeformat in diesen Ordner, z. B. data/2026-11-17_dagger. "
            "Export: tools/export_variante.py --data <Demos> <Ordner> --dagger-gewicht 5.")
        self.dagger_dir.textChanged.connect(self._update_command)
        form.addRow("DAgger-Ordner", self.dagger_dir)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.pick_view = pick_view_module.PickView()
        row.addWidget(self.pick_view, 1)
        side = QVBoxLayout()
        self.btn_read_pick = QPushButton("PICK lesen")
        self.btn_read_pick.setToolTip(
            "PICK und Tischpunkte (ID0–ID8) aus der verbundenen Steuerung lesen.")
        self.btn_read_pick.clicked.connect(self.read_pick)
        side.addWidget(self.btn_read_pick)
        side.addStretch(1)
        row.addLayout(side)
        layout.addLayout(row)
        self.pick_info = _hint(pick_view_module.state_text(None))
        layout.addWidget(self.pick_info)
        self.pick_warnings = QLabel("")
        self.pick_warnings.setWordWrap(True)
        layout.addWidget(self.pick_warnings)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.camera_check = block_wheel(QComboBox())
        self.camera_check.addItem("prüfen, bei Abweichung nicht fahren", "an")
        self.camera_check.addItem("prüfen, nur warnen", "warnen")
        self.camera_check.addItem("aus", "aus")
        self.camera_check.setToolTip(
            "In der Startstellung: Helligkeit, Farbe, Sättigung und Kameralage gegen "
            "die ersten Bilder der Trainingsepisoden (bc/camera_check.py). Ohne "
            "Antwort auf die Rückfrage fährt apps/infer.py bei Abweichung nicht.")
        self.camera_check.currentIndexChanged.connect(self._update_command)
        form.addRow("Kameraprüfung", self.camera_check)
        for combo in (self.probe, self.camera_check):   # Spalte nicht breiter machen
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(16)
        layout.addLayout(form)
        self.camera_ref_info = _hint("")
        layout.addWidget(self.camera_ref_info)
        for widget in self._known_widgets():           # erst mit "Lage bekannt"
            widget.setEnabled(False)
        return box

    def _known_widgets(self):
        return (self.probe, self.probe_gap, self.expert, self.sequence, self.pick_source,
                self.photo_point, self.dagger_dir)

    def _on_probe_changed(self, *_):
        objekt = self.known.isChecked() and self.probe.currentData() == "objekt"
        self.probe_gap.setEnabled(objekt)
        self.expert.setEnabled(objekt)
        self.dagger_dir.setEnabled(objekt and self.expert.isChecked())
        self._update_command()

    def _on_pick_source_changed(self, *_):
        self.photo_point.setEnabled(self.known.isChecked()
                                    and self.pick_source.currentData() == "m1")
        self._update_command()

    def _build_action_bar(self):
        """Pruefung und Knoepfe ausserhalb des Bildlaufs.

        Ob Modell, Kameras und Tempo zusammenpassen, ist die Frage, die
        unmittelbar vor dem Klick zaehlt -- sie darf nicht unter der
        Bildschirmkante stehen. Der Stoppknopf erst recht nicht.
        """
        bar = QWidget()
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(0, 4, 0, 0)
        self.check_label = QLabel("")
        self.check_label.setWordWrap(True)
        outer.addWidget(self.check_label)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.btn_start = QPushButton("Inferenz starten")
        self.btn_stop = QPushButton("STOPP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip(
            "Beendet den laufenden Prozess. Software-Stopp — ersetzt keinen "
            "zertifizierten Not-Aus (AP 4.2).")
        self.btn_stop.setStyleSheet(
            "QPushButton:enabled{background:%s; color:white; font-weight:bold}" % BAD)
        self.btn_start.clicked.connect(self.start_inference)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_camera_check = QPushButton("Kameras prüfen")
        self.btn_camera_check.setToolTip(
            "Nur die Kameraprüfung: Arm in die Startstellung, Bilder gegen die "
            "Aufnahme des Modells vergleichen, nicht fahren.")
        self.btn_camera_check.clicked.connect(self.start_camera_check)
        self.btn_live = QPushButton("Live-Ansicht")
        self.btn_live.setToolTip(
            "Eigenes Fenster: Kamerabilder, Draufsicht mit PICK, TCP und dem, was die "
            "Policy plant (je Vorhersage und gemittelt), Verlauf des Drehfehlers. "
            "Öffnet sich beim Start einer Fahrt von selbst.")
        self.btn_live.setEnabled(False)
        self.btn_live.clicked.connect(self.show_live)
        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_camera_check)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_live)
        layout.addStretch(1)
        outer.addWidget(row)
        return bar

    # -- Aufbau: Ausgabeseite ----------------------------------------------

    def _build_output(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        command_box = QGroupBox("Kommandozeile")
        command_layout = QVBoxLayout(command_box)
        self.command = QLabel("")
        self.command.setWordWrap(True)
        self.command.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.command.setStyleSheet("font-family:Consolas; color:palette(text)")
        command_layout.addWidget(self.command)
        layout.addWidget(command_box)

        progress_box = QGroupBox("Fahrt")
        progress_layout = QVBoxLayout(progress_box)
        self.headline = QLabel("noch nichts gestartet")
        headline_font = QFont()
        headline_font.setBold(True)
        self.headline.setFont(headline_font)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.detail_line = _hint("")
        self.totals_line = _hint("")
        progress_layout.addWidget(self.headline)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.detail_line)
        progress_layout.addWidget(self.totals_line)
        self.camera_line = QLabel("")
        self.camera_line.setWordWrap(True)
        progress_layout.addWidget(self.camera_line)

        self.rollouts = QTreeWidget()
        self.rollouts.setHeaderLabels(
            ["Fahrt", "Ergebnis", "Takte", "Greifpunkt", "Ende", "Bahn p95",
             "Vorhersage", "Überläufe", "Abbruchgrund",
             "Lage xy", "Lage dz", "Drehung", "Tisch min", "Vorh. Griff xy",
             "Korrektur xy / Drehung"])
        self.rollouts.setRootIsDecorated(False)
        self.rollouts.setMaximumHeight(170)
        for column, width in enumerate((55, 90, 60, 85, 70, 80, 85, 75, 130,
                                        75, 75, 65, 75, 90, 140)):
            self.rollouts.setColumnWidth(column, width)
        progress_layout.addWidget(self.rollouts)
        layout.addWidget(progress_box)

        output_box = QGroupBox("Ausgabe")
        output_layout = QVBoxLayout(output_box)
        self.output = LogView()
        output_layout.addWidget(self.output)
        layout.addWidget(output_box, 1)
        return page

    # -- Aktualisieren ------------------------------------------------------

    def refresh(self):
        super().refresh()
        self._reload_checkpoints()
        self._reload_devices()
        self.cameras.refresh(
            backend_is_sim_robot=self.session.backend == session_module.BACKEND_SIM)
        self._update_command()

    def _reload_checkpoints(self):
        current = self.checkpoint.currentData()
        self.checkpoint.blockSignals(True)
        self.checkpoint.clear()
        self.checkpoint.addItem("— keines —", None)
        # Derselbe Ablageort wie im Reiter Training ("Ablageorte -> Laeufe").
        root = training_module.load_locations(self.workdir)["checkpoints"]
        for path in operation_module.find_policies(self.workdir, root):
            self.checkpoint.addItem(str(path), str(path))
        index = find_data(self.checkpoint, current)
        self.checkpoint.setCurrentIndex(index if index >= 0 else 0)
        self.checkpoint.blockSignals(False)
        self._on_checkpoint_changed()

    def _reload_devices(self):
        current = self.device.currentData()
        self.device.blockSignals(True)
        self.device.clear()
        for device in training_module.devices():
            self.device.addItem(device.label, device.key)
        index = find_data(self.device, current)
        self.device.setCurrentIndex(index if index >= 0 else 0)
        self.device.blockSignals(False)

    def _on_session_status(self, _status):
        """Ampel oder Override haben sich geaendert -- nachziehen."""
        if abs(self.override.value() - self.session.override) > 1e-12:
            self.override.blockSignals(True)
            self.override.setValue(float(self.session.override))
            self.override.blockSignals(False)
        self._update_command()

    def _on_checkpoint_changed(self):
        path = self.checkpoint.currentData()
        if not path:
            self._described = None
            self.model_info.setText("")
            self._update_command()
            return
        self._described = operation_module.describe_policy(path)
        self.model_info.setText(operation_module.policy_summary(self._described))
        seq = self._described.get("sequence_file")
        self.sequence.setPlaceholderText(
            "aus dem Modell: %s" % seq if seq else "Modell nennt keinen — Datei angeben")
        self.camera_ref_info.setText(
            "Kamerareferenz im Modell vorhanden." if self._described.get("camera_reference")
            else "Modell ohne Kamerareferenz — nachtragen mit "
                 "tools/kamera_referenz.py --checkpoint <Modell>; bis dahin nur Hinweis.")
        # Vorbelegung aus dem Modell -- die Werte der Aufzeichnung sind die,
        # die passen muessen. Wer abweichen will, tut das bewusst; die
        # Vorabpruefung sagt es dann.
        if self._described["override"] is not None:
            self.session.set_override(float(self._described["override"]))
        self._update_command()

    def _on_hold_toggled(self, checked):
        self.checkpoint.setEnabled(not checked)
        self._update_command()

    def _on_cameras_changed(self):
        self._update_command()

    # -- Pruefung und Kommandozeile ----------------------------------------

    def _robot_kind(self):
        return ("sim" if self.session.backend == session_module.BACKEND_SIM
                else "neura")

    def _assignment(self):
        return self.cameras.assignment()

    def _argv(self, camera_check=None):
        """Kommandozeile aus den Feldern; ``camera_check="nur"``: nur pruefen."""
        status = self.session.status()
        only_check = camera_check == "nur"
        return operation_module.infer_argv(
            self.checkpoint.currentData(),
            robot_kind=self._robot_kind(),
            episodes=self.episodes.value(),
            camera_specs=cameras_module.to_specs(self._assignment(), self.cameras.fps()),
            override=(self.session.override
                      if self._robot_kind() == "neura" else None),
            max_steps=self.max_steps.value() or None,
            replan=self.replan.value() or None,
            device=self.device.currentData(),
            realtime=self.realtime.isChecked(),
            hold=self.hold.isChecked(),
            no_ensemble=self.no_ensemble.isChecked(),
            out=self.out.text().strip() or None,
            real_robot=status.is_real_plant,
            known_pose=self.known.isChecked() and not only_check,
            probe=self.probe.currentData(),
            probe_gap_mm=self.probe_gap.value(),
            expert=self.expert.isChecked(),
            sequence=self.sequence.text().strip() or None,
            camera_check=camera_check or self.camera_check.currentData(),
            pick_source=self.pick_source.currentData(),
            photo_point=self.photo_point.text().strip() or None,
            dagger_dir=self.dagger_dir.text().strip() or None)

    def _update_command(self):
        status = self.session.status()
        assignment = self._assignment()
        try:
            argv = self._argv()
            self.command.setText(training_module.command_line(argv))
        except ValueError as exc:
            self.command.setText("Betrieb: %s" % exc)

        self._problems = []
        lines = []
        if self._described is not None and not self.hold.isChecked():
            self._problems = operation_module.compatibility(
                self._described, assignment, self._robot_kind(),
                self.session.override if self._robot_kind() == "neura" else None,
                is_real_plant=status.is_real_plant)
        for problem in self._problems:
            lines.append(("✗ " if problem.blocking else "! ") + problem.text)
        for warning in cameras_module.assignment_warnings(
                assignment, self.cameras.inventory, status.is_real_plant):
            lines.append("! " + warning)
        if not lines:
            self.check_label.setText(
                "Modell, Kameras und Tempo passen zusammen."
                if self._described is not None or self.hold.isChecked()
                else "Kein Modell gewählt.")
            self.check_label.setStyleSheet("color:%s" % NEUTRAL)
        else:
            self.check_label.setText("\n".join(lines))
            self.check_label.setStyleSheet(
                "color:%s" % (BAD if operation_module.blocking(self._problems) else WARN))

    # -- Starten ------------------------------------------------------------

    def start_camera_check(self):
        """Nur die Kamerapruefung: Startstellung anfahren, vergleichen, nicht fahren."""
        self.start_inference(camera_check="nur")

    def start_inference(self, camera_check=None):
        """Rueckfragen, dann apps/infer.py starten.

        Wiedereintrittsschutz (Anlage 2026-11-17): solange eine Rueckfrage
        offen ist, sind die Startknoepfe gesperrt und ein weiterer Klick
        tut nichts -- sonst stapelten sich die Dialoge und jeder "Ja"
        startete eine eigene Fahrt.
        """
        if camera_check is not None and not isinstance(camera_check, str):
            camera_check = None          # clicked(bool) von Qt
        if getattr(self, "_starting", False):
            return
        self._starting = True
        self.btn_start.setEnabled(False)
        self.btn_camera_check.setEnabled(False)
        try:
            self._start_inference(camera_check)
        finally:
            self._starting = False
            if not self.process.running:
                self.btn_start.setEnabled(True)
                self.btn_camera_check.setEnabled(True)

    def _start_inference(self, camera_check):
        if self.process.running:
            QMessageBox.information(self, "Läuft bereits",
                                    "Es läuft schon eine Fahrt.")
            return
        if not self.hold.isChecked() and not self.checkpoint.currentData():
            QMessageBox.information(
                self, "Kein Modell",
                "Ein Modell wählen — oder \"Ohne Modell fahren\" für den "
                "Verdrahtungstest ankreuzen.")
            return

        assignment = self._assignment()
        keys = ["torch", "lerobot"] if not self.hold.isChecked() else []
        keys += cameras_module.required_backend_keys(assignment)
        if self._robot_kind() == "neura":
            keys.append("neurapy")
        if not self.hold.isChecked():
            keys.append("cuda")
        if not self.ensure_requirements(
                "Eine Policy-Fahrt", keys,
                "Ohne GPU braucht eine Vorhersage 384 ms und reißt den "
                "15-Hz-Takt — in der Simulation zum Nachsehen trotzdem "
                "brauchbar, an der Anlage nicht."):
            return

        blocking = operation_module.blocking(self._problems)
        if blocking and not self.confirm(
                "Modell passt nicht zur Fahrt",
                "apps/infer.py bricht dabei ab:\n\n"
                + "\n".join("  - " + p.text for p in blocking)
                + "\n\nTrotzdem starten?"):
            return

        if self.known.isChecked() and camera_check != "nur" and self._pick_state is not None \
                and self._pick_state.warnings and not self.confirm(
                    "PICK prüfen",
                    "Der zuletzt gelesene PICK passt vielleicht nicht zur Lage:\n\n"
                    + "\n".join("  - " + w for w in self._pick_state.warnings)
                    + "\n\nTrotzdem fahren?"):
            return

        if not self._confirm_motion(only_check=camera_check == "nur"):
            return

        self._progress = operation_module.RolloutProgress(
            total_episodes=None if camera_check == "nur" else self.episodes.value())
        self.camera_line.setText("")
        self.rollouts.clear()
        self.output.clear()
        self.totals_line.setText("")
        self.detail_line.setText("")
        self.progress_bar.setValue(0)
        self.headline.setText("startet …")
        self.headline.setStyleSheet("font-weight:bold")

        status = self.session.status()
        argv = self._argv(camera_check=camera_check)
        try:
            # apps/infer.py fragt bei --real-robot nach dem Freigabewort und
            # nach einem Stopp vor jeder weiteren Fahrt. Die Rueckfragen hat
            # die GUI schon gestellt; das Wort geht deshalb mit, der Rest
            # laeuft auf EOF in den sicheren Zweig (Fahrt nicht fortsetzen).
            self.process.start(argv, stdin_text="ANLAGE\n"
                               if status.is_real_plant else None)
        except Exception as exc:
            QMessageBox.warning(self, "Start gescheitert", str(exc))
            return
        self._set_running(True)

    def _confirm_motion(self, only_check=False):
        """Rueckfrage vor jeder Bewegung -- die Antwort der Steuerung zaehlt."""
        status = self.session.status()
        lines = (["Kameraprüfung: der Arm fährt in die Startstellung, die Policy fährt "
                  "nicht.", ""] if only_check else ["Die Policy bewegt den Roboter.", ""])
        lines.append("Backend laut Steuerung: %s" % status.text)
        lines.append("Kameras: %s" % cameras_module.describe(self._assignment()))
        if not only_check:
            lines.append("Fahrten: %d" % self.episodes.value())
            if self.known.isChecked():
                lines.append("Policy-Test mit bekannter Lage, %s" % self.probe.currentText())
                if self.probe.currentData() == "objekt":
                    gap = self.probe_gap.value()
                    lines.append("Abstand über Objekt: %.1f mm" % gap)
                    if gap < 1e3 * config.PROBE_GAP_WARN_M:
                        lines.append("ACHTUNG: unter %.0f mm — der Arm lief nach dem Stopp "
                                     "bis 7,5 mm nach, die Backen können das Objekt treffen."
                                     % (1e3 * config.PROBE_GAP_WARN_M))
                else:
                    lines.append("ACHTUNG: echter Griff — nur 3 mm Tischabstand.")
                if self.pick_source.currentData() == "m1":
                    lines.append("PICK aus M1: vor jeder Fahrt an die Fotostellung '%s'"
                                 % (self.photo_point.text().strip() or config.LOCALIZE_POINT))
                if self.probe.currentData() == "objekt" and not self.expert.isChecked():
                    lines.append("Ohne Experte: Policy hält über dem Objekt, danach anheben "
                                 "und zurück zum Start -- das Teil wird nicht gegriffen.")
                if self.dagger_dir.text().strip() and self.probe.currentData() == "objekt" \
                        and self.expert.isChecked():
                    lines.append("DAgger: Episoden nach %s" % self.dagger_dir.text().strip())
        if status.state == session_module.OFFLINE:
            lines += ["", "Es ist nichts verbunden — apps/infer.py verbindet "
                          "selbst. Welche Steuerung antwortet, steht erst dann fest."]
        if status.is_real_plant:
            lines += ["", "ACHTUNG: Das ist die REALE ANLAGE, nicht die Simulation.",
                      "Die Fahrt wird mit --real-robot gestartet."]
        lines += ["", "Arbeitsraum frei? Not-Aus in Reichweite?"]
        return self.confirm("Policy fährt", "\n".join(lines))

    def stop(self):
        if not self.process.running:
            return
        self.process.stop()
        self.output.append_record(
            "STOPP ausgelöst — Prozess beendet. Das ist ein Software-Stopp "
            "und ersetzt keinen Not-Aus (AP 4.2).", logging.WARNING)

    # -- Ausgabe ------------------------------------------------------------

    def _on_started(self, command):
        self.output.append_record("$ " + " ".join(command[1:]), logging.INFO)

    def show_live(self):
        """Live-Fenster zeigen (bc/gui/live_window.py) -- Ordner aus der Ausgabe."""
        if getattr(self, "_live_folder", None) is None:
            return
        if getattr(self, "_live_window", None) is None:
            from .live_window import LiveWindow
            self._live_window = LiveWindow()
        if self._live_window.folder != self._live_folder:
            self._live_window.set_folder(self._live_folder)
        self._live_window.show()
        self._live_window.raise_()

    def _on_line(self, text):
        from .. import live as live_module

        if text.startswith(live_module.LIVE_PREFIX):
            self._live_folder = Path(text[len(live_module.LIVE_PREFIX):].strip())
            self.btn_live.setEnabled(True)
            try:
                self.show_live()
            except Exception as exc:     # Anzeige darf nichts blockieren
                self.output.append_record("Live-Ansicht: %s" % exc, logging.WARNING)
        self.output.append_line(text)
        if self._progress is None or not self._progress.feed(text):
            return
        before = self.rollouts.topLevelItemCount()
        for rollout in self._progress.rollouts[before:]:
            item = QTreeWidgetItem(self.rollouts, rollout.row())
            item.setForeground(1, QBrush(QColor(GOOD if rollout.success else WARN)))
            self.rollouts.addTopLevelItem(item)
            self.rollouts.scrollToItem(item)
        # Die Lage-Zeile kommt nach der Ergebniszeile: Spalten nachtragen
        if self._progress.rollouts and self.rollouts.topLevelItemCount():
            last = self.rollouts.topLevelItem(self.rollouts.topLevelItemCount() - 1)
            for column, text in enumerate(self._progress.rollouts[-1].row()):
                last.setText(column, text)
        text, level = operation_module.camera_check_summary(self._progress)
        if text:
            self.camera_line.setText(text)
            self.camera_line.setStyleSheet("color:%s" % (
                GOOD if level == "ok" else WARN if level == "warnung" else NEUTRAL))
        self.headline.setText(self._progress.headline())
        self.detail_line.setText(self._progress.detail_line())
        self.totals_line.setText(self._progress.totals_line())
        percent = self._progress.percent
        if percent is not None:
            self.progress_bar.setValue(percent)

    def _on_finished(self, code, text):
        self._set_running(False)
        ok = code == 0
        if ok and self._progress is not None and self._progress.total is not None:
            succeeded = self._progress.succeeded
            total = self._progress.total
            self.headline.setText("Erfolg %d von %d Fahrten" % (succeeded, total))
            self.headline.setStyleSheet(
                "color:%s; font-weight:bold" % (GOOD if succeeded == total else WARN))
        elif ok:
            self.headline.setText("Durchgelaufen")
            self.headline.setStyleSheet("color:%s; font-weight:bold" % GOOD)
        else:
            self.headline.setText("Abgebrochen (Rückgabewert %d)" % code)
            self.headline.setStyleSheet("color:%s; font-weight:bold" % BAD)
        self.output.append_record(
            "-> Fahrt beendet, Rückgabewert %d" % code,
            logging.INFO if ok else logging.ERROR)

    def _set_running(self, running):
        for widget in (self.btn_start, self.btn_rescan, self.checkpoint,
                       self.hold, self.episodes, self.cameras, self.btn_camera_check,
                       self.btn_read_pick, self.known):
            widget.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    # -- Policy-Test: PICK --------------------------------------------------

    def _on_known_toggled(self, checked):
        for widget in self._known_widgets():
            widget.setEnabled(checked)
        self._on_pick_source_changed()
        self._on_probe_changed()

    def _sequence_path(self):
        text = self.sequence.text().strip() or (self._described or {}).get("sequence_file")
        if not text:
            return None
        path = Path(text)
        return path if path.is_absolute() else self.workdir / path

    def read_pick(self):
        """PICK und Tischpunkte aus der verbundenen Steuerung lesen."""
        robot = self.session.robot
        if robot is None:
            QMessageBox.information(self, "Nicht verbunden",
                                    "Erst oben mit der Steuerung verbinden.")
            return
        path = self._sequence_path()
        if path is None:
            QMessageBox.information(self, "Kein Ablauf",
                                    "Modell wählen oder eine Ablaufdatei angeben.")
            return
        recordings = training_module.load_locations(self.workdir).get("recordings") or []
        data_root = self.workdir / recordings[0] if recordings else None
        try:
            state = pick_view_module.read_pick_state(robot, path, data_root=data_root)
        except Exception as exc:
            QMessageBox.warning(self, "PICK nicht lesbar", "%s: %s" % (type(exc).__name__, exc))
            return
        self.set_pick_state(state)

    def set_pick_state(self, state):
        self._pick_state = state
        self.pick_view.set_state(state)
        self.pick_info.setText(pick_view_module.state_text(state))
        if state is not None and state.warnings:
            self.pick_warnings.setText("\n".join("! " + w for w in state.warnings))
            self.pick_warnings.setStyleSheet("color:%s" % WARN)
        else:
            self.pick_warnings.setText("PICK passt zum Tisch." if state is not None else "")
            self.pick_warnings.setStyleSheet("color:%s" % GOOD)

    # -- Lebenszyklus -------------------------------------------------------

    def shutdown(self):
        if self.process.running:
            self.process.stop()
        if getattr(self, "_live_window", None) is not None:
            self._live_window.close()


def _hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color:%s" % NEUTRAL)
    return label
