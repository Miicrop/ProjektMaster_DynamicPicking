"""Reusable Qt widgets and helpers for the GUI."""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

import cv2
import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMessageBox, QPlainTextEdit, QSizePolicy, QWidget

log = logging.getLogger(__name__)

GOOD, BAD, NEUTRAL, ACTIVE = "#2e7d32", "#c62828", "#9e9e9e", "#1565c0"


# --- images ----------------------------------------------------------------------

def to_pixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) if bgr.ndim == 3 else cv2.cvtColor(bgr, cv2.COLOR_GRAY2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())


class ImageView(QLabel):
    """Shows a BGR image scaled to the widget size, keeping the aspect ratio."""

    def __init__(self, placeholder: str = "kein Bild", parent: QWidget | None = None):
        super().__init__(placeholder, parent)
        self._pix: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#202020; color:#aaa; border:1px solid #444;")

    def set_image(self, bgr: np.ndarray | None) -> None:
        if bgr is None:
            self._pix = None
            self.clear()
            return
        # downscale big camera frames once (4K) - keeps the UI fast
        scale = 1600 / max(bgr.shape[:2])
        if scale < 1:
            bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        self._pix = to_pixmap(bgr)
        self._rescale()

    def _rescale(self) -> None:
        if self._pix is not None:
            self.setPixmap(self._pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._rescale()


class Badge(QLabel):
    """Big coloured status text (GUT / SCHLECHT / ...)."""

    def __init__(self, text: str = "–", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        self.setFont(f)
        self.setMinimumHeight(56)
        self.show_state(text, NEUTRAL)

    def show_state(self, text: str, colour: str) -> None:
        self.setText(text)
        self.setStyleSheet(f"background:{colour}; color:white; border-radius:6px; padding:6px;")


# --- background tasks --------------------------------------------------------------

class TaskRunner(QObject):
    """Runs functions in worker threads and delivers results in the GUI thread.

    pool "vision": image grabbing / processing (2 threads)
    pool "robot" : everything that talks to the robot, strictly one after another
    pool "stop"  : emergency stop, never blocked by a running motion
    """
    _deliver = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self._deliver.connect(self._on_deliver)
        self.pools = {"vision": ThreadPoolExecutor(2, "vision"), "robot": ThreadPoolExecutor(1, "robot"),
                      "stop": ThreadPoolExecutor(1, "stop")}
        self.pending = {k: 0 for k in self.pools}

    def submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None] | None = None,
               on_error: Callable[[Exception], None] | None = None, pool: str = "vision") -> Future:
        self.pending[pool] += 1

        def job():
            try:
                value = fn()
                self._deliver.emit(on_done, value)
            except Exception as e:  # reported in the GUI thread
                log.error("%s", e, exc_info=not isinstance(e, (RuntimeError, ValueError)))
                self._deliver.emit(on_error or show_error, e)
            finally:
                self._deliver.emit(lambda _: self._finished(pool), None)
        return self.pools[pool].submit(job)

    def _finished(self, pool: str) -> None:
        self.pending[pool] -= 1

    def busy(self, pool: str) -> bool:
        return self.pending[pool] > 0

    @Slot(object, object)
    def _on_deliver(self, callback, value) -> None:
        if callback is not None:
            callback(value)

    def shutdown(self) -> None:
        for p in self.pools.values():
            p.shutdown(wait=False, cancel_futures=True)


def show_error(e: Exception) -> None:
    QMessageBox.warning(None, "Fehler", f"{type(e).__name__}: {e}")


def confirm_motion(parent: QWidget, what: str) -> bool:
    return QMessageBox.question(
        parent, "Roboter bewegt sich",
        f"{what}\n\nArbeitsraum frei? Hand am Not-Halt?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


# --- log -------------------------------------------------------------------------

class _LogEmitter(QObject):
    message = Signal(str, int)


class QtLogHandler(logging.Handler):
    """Forwards log records (from any thread) to a LogView."""

    def __init__(self) -> None:
        super().__init__()
        self.emitter = _LogEmitter()
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.emitter.message.emit(self.format(record).split("\n")[0], record.levelno)


class LogView(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2000)
        self.setFont(QFont("Consolas", 9))

    @Slot(str, int)
    def append_record(self, text: str, level: int) -> None:
        colour = "#c62828" if level >= logging.ERROR else "#e65100" if level >= logging.WARNING else "#333"
        self.appendHtml(f'<span style="color:{colour}">{text.replace("<", "&lt;")}</span>')


# --- robot top view --------------------------------------------------------------

class RobotMapView(QWidget):
    """Top view of the robot base frame: limits, workspace, taught poses, TCP, part."""

    def __init__(self, cfg: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.cfg = cfg
        self.tcp: tuple[float, float] | None = None
        self.part: tuple[float, float, float] | None = None       # x, y, theta
        self.trail: list[tuple[float, float]] = []
        self.setMinimumSize(260, 220)

    def set_tcp(self, x: float, y: float) -> None:
        self.tcp = (x, y)
        self.trail = (self.trail + [(x, y)])[-40:]
        self.update()

    def set_part(self, x: float, y: float, theta: float) -> None:
        self.part = (x, y, theta)
        self.update()

    def _workspace_corners(self) -> list[tuple[float, float]]:
        import math
        w, h = self.cfg["workspace"]["size_mm"]
        w2r = self.cfg["workspace_to_robot"]
        c, s = math.cos(math.radians(w2r["rotation_deg"])), math.sin(math.radians(w2r["rotation_deg"]))
        tx, ty = w2r["translation_mm"]
        return [(c * x - s * y + tx, s * x + c * y + ty) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]

    def paintEvent(self, event) -> None:  # noqa: N802
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#fafafa"))
        lim = self.cfg["robot"]["limits_mm"]
        pts = [(0.0, 0.0)] + self._workspace_corners() + [tuple(v[:2]) for v in self.cfg["robot"]["poses"].values()]
        xs = [x for x, _ in pts] + list(lim["x"])
        ys = [y for _, y in pts] + list(lim["y"])
        x0, x1, y0, y1 = min(xs) - 60, max(xs) + 60, min(ys) - 160, max(ys) + 60   # room for labels
        # robot x -> screen up, robot y -> screen left (view from above, robot base at the bottom)
        sc = min(self.width() / (y1 - y0), self.height() / (x1 - x0))

        def m(x: float, y: float) -> QPointF:
            return QPointF(self.width() / 2 - (y - (y0 + y1) / 2) * sc,
                           self.height() / 2 - (x - (x0 + x1) / 2) * sc)

        p.setPen(QPen(QColor("#bbb"), 1, Qt.PenStyle.DashLine))
        p.drawRect(QRectF(m(lim["x"][1], lim["y"][1]), m(lim["x"][0], lim["y"][0])))
        p.setPen(QPen(QColor("#888"), 2))
        ws = [m(*c) for c in self._workspace_corners()]
        for i in range(4):
            p.drawLine(ws[i], ws[(i + 1) % 4])
        p.setBrush(QBrush(QColor("#555")))
        p.drawEllipse(m(0, 0), 8, 8)
        p.drawText(m(0, 0) + QPointF(10, 4), "Basis")
        colours = {"home": "#607d8b", "inspection": ACTIVE, "bin_good": GOOD, "bin_bad": BAD}
        for name, v in self.cfg["robot"]["poses"].items():
            p.setBrush(QBrush(QColor(colours.get(name, "#795548"))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(m(v[0], v[1]) - QPointF(6, 6), m(v[0], v[1]) + QPointF(6, 6)))
            p.setPen(QColor("#333"))
            p.drawText(m(v[0], v[1]) + QPointF(9, -6), name)
        if self.part:
            x, y, th = self.part
            p.setPen(QPen(QColor("#8e24aa"), 3))
            tip = (x + 40 * math.cos(math.radians(th)), y + 40 * math.sin(math.radians(th)))
            p.drawLine(m(x, y), m(*tip))
            p.setBrush(QBrush(QColor("#ce93d8")))
            p.drawEllipse(m(x, y), 7, 7)
        if len(self.trail) > 1:
            p.setPen(QPen(QColor(255, 152, 0, 120), 2))
            for a, b in zip(self.trail, self.trail[1:]):
                p.drawLine(m(*a), m(*b))
        if self.tcp:
            p.setPen(QPen(QColor("#e65100"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            c = m(*self.tcp)
            p.drawEllipse(c, 9, 9)
            p.drawLine(c - QPointF(12, 0), c + QPointF(12, 0))
            p.drawLine(c - QPointF(0, 12), c + QPointF(0, 12))
        p.setPen(QColor("#666"))
        p.drawText(8, 16, "Draufsicht Roboter-KS (x ↑, y ←) · ■ Posen · ● Bauteil · ⊕ TCP")
        p.end()
