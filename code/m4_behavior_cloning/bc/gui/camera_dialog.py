"""Fenster "Kameraeinstellungen": Belichtung und Gain an der offenen Vorschau.

Wunsch Anwender 2026-11-03: Gain und Belichtung in der Oberflaeche statt in
``config.py``, in einem eigenen Fenster mit Bild -- in voller Aufloesung und
so, wie es aufgezeichnet wird, mit dem Ausschnitt, den die Policy sieht.

* **Uebernehmen** setzt die Werte an der offenen Kamera (nur Vorschau).
* **Fuer Aufnahmen speichern** schreibt sie nach
  ``einstellungen/kameras.local.json`` (bc/camera_settings.py); Vorschau,
  ``apps/record.py`` und ``apps/infer.py`` nehmen sie beim naechsten Oeffnen.

Nur Daheng -- bei Platzhalter und Webcam sind die Felder gesperrt.
"""

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout)

from .. import camera_settings
from ..adapters import describe_settings
from .widgets import BAD, NEUTRAL, WARN, ImageView, block_wheel

log = logging.getLogger(__name__)


class CameraSettingsDialog(QDialog):
    #: (Kameraname, zurueckgelesene Einstellungen) nach "Uebernehmen"
    applied = Signal(str, dict)

    def __init__(self, captures, runner, workdir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kameraeinstellungen")
        self.resize(980, 760)
        self.captures = {c.name: c for c in captures}
        self.runner = runner
        self.workdir = workdir
        self._busy = False

        self.camera = block_wheel(QComboBox())
        for name in self.captures:
            self.camera.addItem(name, name)
        self.camera.currentIndexChanged.connect(self._camera_changed)

        self.view = ImageView("wartet auf das nächste Bild …")
        self.view.setMinimumHeight(360)
        self.recorded = QCheckBox("Wie aufgezeichnet")
        self.recorded.setToolTip("Auf die Schemagröße verkleinert, wie im Datensatz.")
        self.crop = QCheckBox("Rahmen: Ausschnitt der Policy")
        self.crop.setChecked(True)

        self.exposure = block_wheel(QDoubleSpinBox())
        self.exposure.setRange(*camera_settings.EXPOSURE_RANGE_US)
        self.exposure.setDecimals(0)
        self.exposure.setSingleStep(500.0)
        self.exposure.setSuffix(" µs")
        self.exposure_auto = QCheckBox("Automatik")
        self.exposure_auto.toggled.connect(lambda on: self.exposure.setEnabled(not on))
        self.gain = block_wheel(QDoubleSpinBox())
        self.gain.setRange(*camera_settings.GAIN_RANGE_DB)
        self.gain.setDecimals(1)
        self.gain.setSingleStep(0.5)
        self.gain.setSuffix(" dB")
        self.gain_auto = QCheckBox("Automatik")
        self.gain_auto.toggled.connect(lambda on: self.gain.setEnabled(not on))
        hint = QLabel("Automatik ist für den Datensatz ungünstig: die Bildhelligkeit "
                      "ändert sich dann mit dem Bildinhalt. Lange Belichtung verwischt "
                      "bei Armbewegung und begrenzt die Bildrate (60 fps: unter ~16 ms).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:%s" % NEUTRAL)
        self.readback = QLabel("")
        self.readback.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Kamera", self.camera)
        row = QHBoxLayout()
        row.addWidget(self.exposure, 1)
        row.addWidget(self.exposure_auto)
        form.addRow("Belichtung", row)
        row = QHBoxLayout()
        row.addWidget(self.gain, 1)
        row.addWidget(self.gain_auto)
        form.addRow("Gain", row)

        self.btn_apply = QPushButton("Übernehmen")
        self.btn_apply.setToolTip("An der offenen Kamera setzen — nur für die Vorschau.")
        self.btn_apply.clicked.connect(self.apply)
        self.btn_save = QPushButton("Für Aufnahmen speichern")
        self.btn_save.setToolTip(
            "Übernehmen und nach %s schreiben: gilt dann für Vorschau, Aufnahme und "
            "Inferenz mit dieser Kamera." % camera_settings.SETTINGS_FILE)
        self.btn_save.clicked.connect(self.save)
        self.btn_default = QPushButton("Vorgabe aus config.py")
        self.btn_default.clicked.connect(self._fill_default)
        close = QPushButton("Schließen")
        close.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_apply)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_default)
        buttons.addStretch(1)
        buttons.addWidget(close)

        checks = QHBoxLayout()
        checks.addWidget(self.recorded)
        checks.addWidget(self.crop)
        checks.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addLayout(checks)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.readback)
        layout.addLayout(buttons)
        self._camera_changed()

    # -- Anzeige --------------------------------------------------------------

    def current(self):
        return self.captures.get(self.camera.currentData())

    def show_frames(self, frames):
        """Vom Reiter bei jedem Vorschautakt: Bild der gewaehlten Kamera."""
        from .. import preview as preview_module

        name = self.camera.currentData()
        frame = frames.get(name)
        if frame is None or getattr(frame, "image", None) is None:
            return
        shown = preview_module.display_frames({name: frame}, self.recorded.isChecked(),
                                              self.crop.isChecked())[name]
        self.view.set_image(preview_module.compose({name: shown},
                                                   height=shown.image.shape[0]))

    def _camera_changed(self):
        capture = self.current()
        cfg = getattr(getattr(capture, "camera", None), "cfg", None)
        adjustable = cfg is not None and cfg.backend == "daheng" \
            and hasattr(capture.camera, "apply_settings")
        for widget in (self.exposure, self.exposure_auto, self.gain, self.gain_auto,
                       self.btn_apply, self.btn_save, self.btn_default):
            widget.setEnabled(adjustable)
        if not adjustable:
            self.readback.setText("Diese Kamera lässt sich hier nicht einstellen "
                                  "(nur Daheng).")
            self.readback.setStyleSheet("color:%s" % NEUTRAL)
            return
        self._fill(cfg.exposure_us, cfg.gain_db)
        self._show_readback(capture.camera.settings())

    def _fill(self, exposure_us, gain_db):
        self.exposure_auto.setChecked(exposure_us is None)
        if exposure_us is not None:
            self.exposure.setValue(float(exposure_us))
        self.gain_auto.setChecked(gain_db is None)
        if gain_db is not None:
            self.gain.setValue(float(gain_db))
        self.exposure.setEnabled(not self.exposure_auto.isChecked())
        self.gain.setEnabled(not self.gain_auto.isChecked())

    def _fill_default(self):
        from .. import config

        capture = self.current()
        known = {c.name: c for c in config.CAMERAS}
        base = known.get(capture.name) if capture is not None else None
        if base is None or base.backend != "daheng":
            base = config.WRIST_CAMERA
        self._fill(base.exposure_us, base.gain_db)

    def _show_readback(self, settings, error=None):
        if error:
            self.readback.setText("Nicht gesetzt: %s" % error)
            self.readback.setStyleSheet("color:%s" % BAD)
            return
        text = describe_settings(self.camera.currentData(), settings)
        possible = (settings or {}).get("rate_possible_fps")
        warn = possible is not None and possible < 59.0
        if possible is not None:
            text += " — Kamera schafft so %.1f fps" % possible
        self.readback.setText("Kamera meldet: " + text)
        self.readback.setStyleSheet("color:%s" % (WARN if warn else NEUTRAL))

    # -- Setzen ---------------------------------------------------------------

    def values(self):
        return {"exposure_us": None if self.exposure_auto.isChecked() else self.exposure.value(),
                "gain_db": None if self.gain_auto.isChecked() else self.gain.value()}

    def apply(self, then=None):
        capture = self.current()
        if capture is None or self._busy:
            return
        values = self.values()
        self._busy = True
        self.btn_apply.setEnabled(False)
        self.btn_save.setEnabled(False)

        def done(settings):
            self._busy = False
            self._camera_changed_buttons()
            self._show_readback(settings)
            self.applied.emit(capture.name, settings or {})
            log.info("Kamera %s: %s gesetzt", capture.name, camera_settings.describe(values))
            if then is not None:
                then(values)

        def failed(error):
            self._busy = False
            self._camera_changed_buttons()
            self._show_readback(None, error)

        self.runner.submit(lambda: capture.camera.apply_settings(**values),
                           on_done=done, on_error=failed, pool="camera")

    def _camera_changed_buttons(self):
        self.btn_apply.setEnabled(True)
        self.btn_save.setEnabled(True)

    def save(self):
        capture = self.current()
        if capture is None:
            return

        def store(values):
            try:
                path = camera_settings.save(capture.camera.cfg, values,
                                            root=self.workdir)
            except OSError as exc:
                QMessageBox.warning(self, "Nicht gespeichert", str(exc))
                return
            self.readback.setText(self.readback.text() + "\nGespeichert in %s — gilt ab "
                                  "der nächsten Aufnahme." % path)

        self.apply(then=store)
