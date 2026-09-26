"""Tabs for M1 (top-down) and M3 (inspection): grab or load an image, analyse, show the result."""
from __future__ import annotations

import time

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget)

from gui.session import Session
from gui.widgets import BAD, GOOD, NEUTRAL, Badge, ImageView, TaskRunner

SOURCES = [("Testbilder (Wiedergabe)", "replay"), ("Kamera", "camera")]


class VisionTab(QWidget):
    """Common frame: source selection, grab/analyse, live mode, two image views, result panel."""
    module = ""          # "m1" / "m3"
    title_left = title_right = ""

    def __init__(self, session: Session, runner: TaskRunner, parent: QWidget | None = None):
        super().__init__(parent)
        self.s, self.runner = session, runner
        self.last_image = None

        self.source = QComboBox()
        for text, kind in SOURCES:
            self.source.addItem(text, kind)
        self.btn_grab = QPushButton("Bild holen + analysieren")
        self.btn_file = QPushButton("Datei öffnen …")
        self.btn_again = QPushButton("Erneut analysieren")
        self.live = QCheckBox("Live")
        self.live.setToolTip("Fortlaufend Bilder holen und analysieren")
        self.timer = QTimer(self, interval=700)
        self.btn_grab.clicked.connect(self.grab)
        self.btn_file.clicked.connect(self.open_file)
        self.btn_again.clicked.connect(lambda: self.analyze(self.last_image, "erneut"))
        self.live.toggled.connect(lambda on: self.timer.start() if on else self.timer.stop())
        self.timer.timeout.connect(self._live_tick)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Quelle:"))
        bar.addWidget(self.source)
        for w in (self.btn_grab, self.btn_file, self.btn_again, self.live):
            bar.addWidget(w)
        self.extra_controls(bar)
        bar.addStretch()

        self.view_left, self.view_right = ImageView(self.title_left), ImageView(self.title_right)
        views = QSplitter(Qt.Orientation.Horizontal)
        views.addWidget(self._titled(self.title_left, self.view_left))
        views.addWidget(self._titled(self.title_right, self.view_right))

        self.badge = Badge()
        self.form = QFormLayout()
        self.info = QLabel()
        self.info.setWordWrap(True)
        result_box = QGroupBox("Ergebnis")
        rl = QVBoxLayout(result_box)
        rl.addWidget(self.badge)
        rl.addLayout(self.form)
        rl.addWidget(self.info)
        rl.addStretch()
        result_box.setMaximumWidth(360)

        body = QHBoxLayout()
        body.addWidget(views, 1)
        body.addWidget(result_box)
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addLayout(body, 1)

    @staticmethod
    def _titled(title: str, w: QWidget) -> QWidget:
        box = QGroupBox(title)
        QVBoxLayout(box).addWidget(w)
        return box

    def extra_controls(self, bar: QHBoxLayout) -> None:
        pass

    # -- actions -------------------------------------------------------------------
    def grab(self) -> None:
        kind = self.source.currentData()
        self.runner.submit(lambda: self.s.grab(self.module, kind),
                           lambda img: self.analyze(img, self.source.currentText()))

    def open_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Bild öffnen", "", "Bilder (*.jpg *.jpeg *.png *.bmp)")
        if f:
            self.analyze(cv2.imread(f), f)

    def _live_tick(self) -> None:
        if not self.runner.busy("vision"):
            self.grab()

    def analyze(self, img, origin: str = "") -> None:
        if img is None:
            return
        self.last_image = img
        self.badge.show_state("…", NEUTRAL)

        def work():
            t = time.perf_counter()
            try:
                return self.process(img), None, time.perf_counter() - t
            except Exception as e:  # analysis errors are shown, not raised
                return None, e, time.perf_counter() - t
        self.runner.submit(work, lambda r: self.show_result(img, *r, origin))

    # -- to implement ----------------------------------------------------------------
    def process(self, img):
        raise NotImplementedError

    def show_result(self, img, result, error, seconds, origin) -> None:
        raise NotImplementedError

    def set_form(self, rows: list[tuple[str, str]]) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        for k, v in rows:
            lab = QLabel(v)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.form.addRow(k, lab)


class M1Tab(VisionTab):
    module = "m1"
    title_left = "Kamerabild mit Arbeitsbereich und Bauteil"
    title_right = "Arbeitsbereich entzerrt"

    def extra_controls(self, bar: QHBoxLayout) -> None:
        self.method = QComboBox()
        self.method.addItems(["auto", "aruco", "white_frame"])
        self.method.setCurrentText(str(self.s.cfg["workspace"]["method"]))
        self.method.currentTextChanged.connect(self._set_method)
        bar.addWidget(QLabel("Arbeitsbereich:"))
        bar.addWidget(self.method)

    def _set_method(self, m: str) -> None:
        self.s.store.set(["workspace", "method"], m)
        if self.last_image is not None:
            self.analyze(self.last_image, "Methode geändert")

    def process(self, img):
        return self.s.analyze_m1(img)

    def show_result(self, img, r, error, seconds, origin) -> None:
        if error is not None:
            self.view_left.set_image(img)
            self.view_right.set_image(None)
            self.badge.show_state("nicht erkannt", BAD)
            self.set_form([("Quelle", origin)])
            self.info.setText(f"<span style='color:{BAD}'>{error}</span>")
            return
        self.view_left.set_image(r.overlay_image(img))
        self.view_right.set_image(r.debug_image(img))
        ppm = r.workspace.px_per_mm
        self.badge.show_state("Bauteil gefunden" if r.part.chamfer_found else "gefunden (ohne Fase)",
                              GOOD if r.part.chamfer_found else "#ef6c00")
        self.set_form([
            ("Quelle", origin),
            ("Methode", r.workspace.method),
            ("Arbeitsbereich", f"x = {r.x_ws_mm:.1f} mm, y = {r.y_ws_mm:.1f} mm"),
            ("Winkel", f"θ = {r.theta_ws_deg:.1f}°"),
            ("Größe", f"{r.part.length_px / ppm:.1f} × {r.part.width_px / ppm:.1f} mm"),
            ("Roboter-KS", f"x = {r.pose.x_mm:.1f}, y = {r.pose.y_mm:.1f} mm, θ = {r.pose.theta_deg:.1f}°"),
            ("Rechenzeit", f"{seconds * 1000:.0f} ms"),
        ])
        self.info.setText("Maße basieren auf <i>workspace.size_mm</i> – bis zum Ausmessen Platzhalter.")


class M3Tab(VisionTab):
    module = "m3"
    title_left = "Kamerabild"
    title_right = "Bauteil mit Prüfbereichen (ROIs)"

    def process(self, img):
        return self.s.analyze_m3(img)

    def show_result(self, img, d, error, seconds, origin) -> None:
        if error is not None:
            self.view_left.set_image(img)
            self.view_right.set_image(None)
            self.badge.show_state("Fehler", BAD)
            self.set_form([("Quelle", origin)])
            self.info.setText(f"<span style='color:{BAD}'>{error}</span>")
            return
        ic = self.s.cfg["inspection"]
        r = d.result
        self.view_left.set_image(d.debug_image(img, ic))
        self.view_right.set_image(d.part_crop(img, ic))
        self.badge.show_state("GUTTEIL" if r.is_good else "SCHLECHTTEIL", GOOD if r.is_good else BAD)
        ok = lambda b: "✔" if b else "✘"  # noqa: E731
        ratio = f" (D/H = {d.hole_diameter_px / d.part_box[3]:.3f})" if d.hole_diameter_px else ""
        serial_ok = r.serial_number is not None and not any("serial" in x for x in r.reasons)
        hole_ok = r.hole_diameter_mm is not None and not any("hole" in x for x in r.reasons)
        self.set_form([
            ("Quelle", origin),
            ("Seriennummer", f"{ok(serial_ok)} {r.serial_number} (Konfidenz {d.ocr_confidence:.2f})"),
            ("Loch", f"{ok(hole_ok)} {r.hole_diameter_mm:.3f} mm{ratio}" if r.hole_diameter_mm
             else f"{ok(False)} nicht gefunden"),
            ("Soll", f"{ic['hole_nominal_mm']} ± {ic['hole_tolerance_mm']} mm"),
            ("Kerbe", f"{ok(r.notch_present)} {'vorhanden' if r.notch_present else 'fehlt'}"),
            ("Rechenzeit", f"{seconds * 1000:.0f} ms"),
        ])
        legend = ("ROIs: <span style='color:#00c8c8'>■</span> Etikett "
                  "<span style='color:#ff8000'>■</span> Loch <span style='color:#ff00ff'>■</span> Kerbe")
        self.info.setText(legend + ("<br><span style='color:%s'>%s</span>" % (BAD, "<br>".join(r.reasons))
                                    if r.reasons else ""))
