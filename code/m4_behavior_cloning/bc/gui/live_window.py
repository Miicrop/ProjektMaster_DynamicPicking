"""Live-Fenster der Inferenz (Anwender 2026-11-17).

Eigenes Fenster (zweiter Bildschirm), liest den Ordner, den apps/infer.py
mit bc/live.py schreibt:

* Szenenkamera mit Pfeilen (PICK, TCP, Plan) -- ueber die ArUco-Abbildung
  von M1; ohne erkannte Marker das Bild ohne Pfeile
* Handgelenkkamera
* Draufsicht auf das Feld: PICK (gruen), TCP mit Spur (blau), jede gerade
  gemittelte Vorhersage (orange, duenn) und ihr Mittel -- das, was der Arm
  tatsaechlich faehrt (orange, dick)
* Verlauf der Drehfehler gegen PICK: TCP, Mittel, einzelne Vorhersagen
  (Punkte). Springen die Punkte zwischen zwei Lagen und liegt das Mittel
  dazwischen, mittelt das Ensembling zwei Modi.

Ein Pfeil je Pose: Richtung der Werkzeug-x-Achse, volle 360 Grad -- das
Objekt hat eine Fase, die Handgelenkkamera schaut zu ihr.
"""

import json
import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QLabel, QSizePolicy, QSplitter,
                               QVBoxLayout, QWidget)

from .. import live as live_module
from .pick_view import convex_hull
from .widgets import ImageView

PICK_COLOR = "#1e8449"
TCP_COLOR = "#2874a6"
PLAN_COLOR = "#e67e22"
CHUNK_COLOR = (230, 126, 34, 90)
#: Pfeillaenge in der Draufsicht und im Kamerabild (m, je Seite)
ARROW_M = 0.03
HISTORY = 400


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def _fmt(value, pattern="%.1f", none="–"):
    return none if value is None else pattern % value


def axis_points(x, y, yaw_deg, half=ARROW_M):
    """Schwanz und Spitze eines Pfeils (Basis-KS, m) durch (x, y) in Richtung yaw."""
    t = math.radians(yaw_deg)
    dx, dy = half * math.cos(t), half * math.sin(t)
    return (x - dx, y - dy), (x + dx, y + dy)


def draw_scene_overlay(bgr, scene_map, image_size, state):
    """Pfeile ins (verkleinerte) Szenenbild. ``image_size``: Vollbild (w, h)."""
    import cv2

    if not scene_map or not state or not image_size:
        return bgr
    out = bgr.copy()
    scale = out.shape[1] / float(image_size[0])
    lw = max(2, int(round(out.shape[1] / 300.0)))

    def px(points):
        uv = live_module.robot_to_image(scene_map, points) * scale
        return [tuple(int(round(v)) for v in p) for p in uv]

    def arrow(info, color, width):
        if not info:
            return
        a, b = axis_points(info["x"], info["y"], info["yaw"], 0.05)
        (ua, va), (ub, vb), (uc, vc) = px([a, b, (info["x"], info["y"])])
        cv2.line(out, (ua, va), (uc, vc), color, width)
        cv2.arrowedLine(out, (uc, vc), (ub, vb), color, width, tipLength=0.4)
        cv2.circle(out, (uc, vc), 2 * width, color, -1)

    trail = state.get("trail") or []
    if len(trail) > 1:
        pts = np.array(px(trail), dtype=np.int32)
        cv2.polylines(out, [pts], False, (180, 140, 60), lw)
    for plan in state.get("chunks") or []:
        if plan.get("path"):
            pts = np.array(px([p[:2] for p in plan["path"]]), dtype=np.int32)
            cv2.polylines(out, [pts], False, (60, 160, 240), max(1, lw - 1))
    mean = state.get("mean")
    if mean and mean.get("path"):
        pts = np.array(px([p[:2] for p in mean["path"]]), dtype=np.int32)
        cv2.polylines(out, [pts], False, (34, 126, 230), lw + 1)
        arrow(mean["grasp"], (34, 126, 230), lw + 1)
    arrow(state.get("pick"), (73, 132, 30), lw + 1)
    arrow(state.get("tcp"), (166, 116, 40), lw + 1)
    return out


class FieldView(QWidget):
    """Draufsicht wie bc/gui/pick_view.PickView (Basis-x nach oben, y nach links)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = None
        self.setMinimumSize(320, 300)

    def set_state(self, state):
        self.state = state
        self.update()

    @staticmethod
    def _view(x, y):
        return -y, -x

    def paintEvent(self, _event):     # noqa: N802 (Qt-API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fbfbfb"))
        rect = self.rect().adjusted(10, 10, -10, -24)
        st = self.state
        if not st or (not st.get("tcp") and not st.get("pick")):
            painter.setPen(QColor("#888"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "wartet auf die Fahrt …")
            return
        pts = [tuple(p) for p in st.get("region") or []]
        for key in ("pick", "tcp"):
            if st.get(key):
                pts.append((st[key]["x"], st[key]["y"]))
        mean = st.get("mean")
        if mean:
            pts.append((mean["grasp"]["x"], mean["grasp"]["y"]))
        if not st.get("region") and st.get("pick"):
            # ohne Tischpunkte: 15 cm um PICK
            px0, py0 = st["pick"]["x"], st["pick"]["y"]
            pts += [(px0 - 0.075, py0 - 0.075), (px0 + 0.075, py0 + 0.075)]
        view = np.array([self._view(*p) for p in pts])
        span = max(float(np.ptp(view[:, 0])), float(np.ptp(view[:, 1])), 0.08) * 1.15
        cu, cw = (float(view[:, 0].min() + view[:, 0].max()) / 2,
                  float(view[:, 1].min() + view[:, 1].max()) / 2)
        scale = min(rect.width(), rect.height()) / span

        def px(x, y):
            a, b = self._view(x, y)
            return QPointF(rect.center().x() + (a - cu) * scale,
                           rect.center().y() + (b - cw) * scale)

        def double_arrow(info, color, width, label=None):
            if not info:
                return
            a, b = axis_points(info["x"], info["y"], info["yaw"])
            c = px(info["x"], info["y"])
            pen = QPen(QColor(color), width)
            painter.setPen(pen)
            painter.setBrush(QColor(color))
            painter.drawLine(px(*a), px(*b))
            self._head(painter, c, px(*b), QColor(color))
            painter.drawEllipse(c, width + 1.5, width + 1.5)
            if label:
                painter.drawText(QRectF(c.x() + 7, c.y() + 2, 90, 14), label)

        if st.get("region"):
            hull = convex_hull([tuple(p) for p in st["region"]])
            painter.setPen(QPen(QColor("#9aa7b4"), 1))
            painter.setBrush(QColor(154, 167, 180, 40))
            painter.drawPolygon(QPolygonF([px(*p) for p in hull]))
        trail = st.get("trail") or []
        if len(trail) > 1:
            path = QPainterPath(px(*trail[0]))
            for p in trail[1:]:
                path.lineTo(px(*p))
            painter.setPen(QPen(QColor(40, 116, 166, 120), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        for plan in st.get("chunks") or []:
            line = plan.get("path") or []
            if len(line) > 1:
                path = QPainterPath(px(*line[0][:2]))
                for p in line[1:]:
                    path.lineTo(px(*p[:2]))
                painter.setPen(QPen(QColor(*CHUNK_COLOR), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            g = plan["grasp"]
            a, b = axis_points(g["x"], g["y"], g["yaw"], ARROW_M * 0.7)
            painter.setPen(QPen(QColor(*CHUNK_COLOR), 1))
            painter.drawLine(px(*a), px(*b))
        if mean and mean.get("path"):
            line = mean["path"]
            path = QPainterPath(px(*line[0][:2]))
            for p in line[1:]:
                path.lineTo(px(*p[:2]))
            painter.setPen(QPen(QColor(PLAN_COLOR), 2.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            double_arrow(mean["grasp"], PLAN_COLOR, 2.5, "Plan")
        double_arrow(st.get("pick"), PICK_COLOR, 2.5, "PICK")
        double_arrow(st.get("tcp"), TCP_COLOR, 2.5, "TCP")
        painter.setPen(QColor("#888"))
        painter.drawText(self.rect().adjusted(0, 0, 0, -4),
                         Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                         "Roboter (unten) — dünn: einzelne Vorhersagen, dick: gemittelt (wird gefahren)")

    @staticmethod
    def _head(painter, base, tip, color):
        dx, dy = tip.x() - base.x(), tip.y() - base.y()
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        size = 8.0
        left = QPointF(tip.x() - size * ux + 0.5 * size * uy, tip.y() - size * uy - 0.5 * size * ux)
        right = QPointF(tip.x() - size * ux - 0.5 * size * uy, tip.y() - size * uy + 0.5 * size * ux)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([tip, left, right]))


class YawHistory(QWidget):
    """Drehfehler gegen PICK ueber den Takten (-180..180 Grad)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []          # (step, tcp, mean, [chunks])
        self.setMinimumHeight(150)

    def clear(self):
        self.rows = []
        self.update()

    def add(self, state):
        step = state.get("step")
        if step is None or not state.get("pick"):
            return
        if self.rows and self.rows[-1][0] == step:
            return
        if self.rows and step < self.rows[-1][0]:
            self.rows = []      # neue Fahrt
        tcp = (state.get("tcp") or {}).get("yaw_err")
        mean = ((state.get("mean") or {}).get("grasp") or {}).get("yaw_err")
        chunks = [p["grasp"].get("yaw_err") for p in state.get("chunks") or []]
        self.rows.append((step, tcp, mean, [c for c in chunks if c is not None]))
        self.rows = self.rows[-HISTORY:]
        self.update()

    def paintEvent(self, _event):     # noqa: N802 (Qt-API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fbfbfb"))
        r = self.rect().adjusted(34, 8, -8, -18)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#bbb"))
        for deg in (-180, -90, -45, 0, 45, 90, 180):
            y = r.center().y() - deg / 180.0 * r.height() / 2
            painter.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            painter.drawText(QRectF(0, y - 7, 30, 14),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             "%+d°" % deg)
        painter.setPen(QColor("#666"))
        painter.drawText(self.rect().adjusted(34, 0, 0, -2), Qt.AlignmentFlag.AlignBottom,
                         "Drehfehler gegen PICK: blau TCP, orange Mittel (gefahren), "
                         "Punkte einzelne Vorhersagen")
        if not self.rows:
            return
        s0, s1 = self.rows[0][0], max(self.rows[-1][0], self.rows[0][0] + 30)

        def pt(step, deg):
            x = r.left() + (step - s0) / float(s1 - s0) * r.width()
            return QPointF(x, r.center().y() - deg / 180.0 * r.height() / 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*CHUNK_COLOR))
        for step, _t, _m, chunks in self.rows:
            for c in chunks:
                painter.drawEllipse(pt(step, c), 2.2, 2.2)
        for index, color in ((1, TCP_COLOR), (2, PLAN_COLOR)):
            path, started = QPainterPath(), False
            for row in self.rows:
                if row[index] is None:
                    started = False
                    continue
                p = pt(row[0], row[index])
                if started:
                    path.lineTo(p)
                else:
                    path.moveTo(p)
                    started = True
            painter.setPen(QPen(QColor(color), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)


class LiveWindow(QWidget):
    """Eigenes Fenster; :meth:`set_folder` mit dem Ordner aus der Ausgabe."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Live-Ansicht Inferenz")
        self.resize(1280, 820)
        self.folder = None
        self._mtimes = {}
        self._scene_map = None
        self._image_sizes = {}
        self._scene_bgr = None
        self._state = None

        self.scene = ImageView("Szenenkamera — kein Bild")
        self.wrist = ImageView("Handgelenkkamera — kein Bild")
        self.field = FieldView()
        self.history = YawHistory()
        self.info = QLabel("")
        self.info.setTextFormat(Qt.TextFormat.RichText)
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.info.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#666")

        cams = QSplitter(Qt.Orientation.Vertical)
        cams.addWidget(self.scene)
        cams.addWidget(self.wrist)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.field, 3)
        rl.addWidget(self.info)
        rl.addWidget(self.history, 1)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(cams)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.poll)

    def set_folder(self, folder):
        self.folder = Path(folder)
        self._mtimes = {}
        self._scene_map = None
        self.history.clear()
        self.status.setText("Ordner: %s" % self.folder)
        self.timer.start()
        self.poll()

    def closeEvent(self, event):      # noqa: N802 (Qt-API)
        self.timer.stop()
        super().closeEvent(event)

    def showEvent(self, event):       # noqa: N802 (Qt-API)
        if self.folder is not None:
            self.timer.start()
        super().showEvent(event)

    def _changed(self, name):
        path = self.folder / name
        m = _mtime(path)
        if m is None or self._mtimes.get(name) == m:
            return None
        self._mtimes[name] = m
        return path

    def poll(self):
        if self.folder is None:
            return
        path = self._changed(live_module.SCENE_MAP_FILE)
        if path:
            self._scene_map = _read_json(path)
        path = self._changed("images.json")
        if path:
            self._image_sizes = _read_json(path) or self._image_sizes
        path = self._changed(live_module.STATE_FILE)
        if path:
            state = _read_json(path)
            if state is not None:
                self._state = state
                self.field.set_state(state)
                self.history.add(state)
                self.info.setText(self._info_html(state))
        for name, view in (("scene", self.scene), ("wrist", self.wrist)):
            path = self._changed("%s.jpg" % name)
            if not path:
                continue
            bgr = self._load_jpg(path)
            if bgr is None:
                continue
            if name == "scene":
                self._scene_bgr = bgr
            view.set_image(bgr)
        if self._scene_bgr is not None and self._scene_map and self._state:
            try:
                self.scene.set_image(draw_scene_overlay(
                    self._scene_bgr, self._scene_map, self._image_sizes.get("scene"), self._state))
            except Exception as exc:
                self.status.setText("Pfeile im Kamerabild: %s" % exc)

    @staticmethod
    def _load_jpg(path):
        import cv2

        try:
            data = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
        except OSError:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None

    @staticmethod
    def _info_html(st):
        rows = []
        head = "Fahrt %s" % _fmt(st.get("episode"), "%d")
        if st.get("step") is not None:
            head += ", Takt %d" % st["step"]
        if st.get("phase") and st.get("phase") != "Policy":
            head += " — %s" % st["phase"]
        rows.append("<b>%s</b>" % head)
        tcp = st.get("tcp") or {}
        mean = (st.get("mean") or {}).get("grasp") or {}
        if st.get("pick"):
            rows.append("<span style='color:%s'>TCP</span>: %s mm neben PICK, Drehung %s°, "
                        "%s mm über Tisch"
                        % (TCP_COLOR, _fmt(tcp.get("xy_mm")), _fmt(tcp.get("yaw_err"), "%+.1f"),
                           _fmt(tcp.get("table_mm"))))
            if mean:
                rows.append("<span style='color:%s'>Plan (gemittelt, wird gefahren)</span>: "
                            "%s %s mm neben PICK, Drehung %s°, in %d Takten"
                            % (PLAN_COLOR, "Griff" if mean.get("closes") else "Ende",
                               _fmt(mean.get("xy_mm")), _fmt(mean.get("yaw_err"), "%+.1f"),
                               mean.get("in_steps", 0)))
            chunks = st.get("chunks") or []
            if chunks:
                errs = [p["grasp"].get("yaw_err") for p in chunks
                        if p["grasp"].get("yaw_err") is not None]
                text = "Einzelvorhersagen: %d gemittelt" % len(chunks)
                if errs:
                    text += ", Drehung von %+.0f° bis %+.0f°" % (min(errs), max(errs))
                    if max(errs) - min(errs) > 20:
                        text += " <b style='color:#c0392b'>— uneinig (zwei Modi?)</b>"
                rows.append(text)
            if st.get("gap_mm"):
                rows.append("<span style='color:#666'>Probegriff: %.0f mm über Objekt</span>"
                            % st["gap_mm"])
        elif tcp:
            rows.append("TCP x %.1f y %.1f mm, Drehung %.1f°"
                        % (1e3 * tcp["x"], 1e3 * tcp["y"], tcp["yaw"]))
        if not st.get("fk", True):
            rows.append("<span style='color:#888'>ohne Vorhersage-Bahn (keine lokale Kinematik)"
                        "</span>")
        return "<br>".join(rows)
