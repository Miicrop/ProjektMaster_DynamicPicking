"""Aktueller PICK in der Draufsicht (Anwender 2026-11-16).

Vor einem Policy-Test mit bekannter Lage muss PICK in der Steuerung dort
stehen, wo das Objekt wirklich liegt -- sonst misst der Test gegen eine
veraltete Lage. Die kleine Ansicht zeigt die Tischpunkte (ID0-ID8) und PICK
mit der Richtung der Greiferbacken, wie die Tischabdeckung im Reiter
Aufnahme (Roboter unten, Basis-x nach oben, Basis-y nach links), dazu:

* wann PICK in der Steuerung zuletzt geaendert wurde (``updatedAt``),
* ob PICK im Tischbereich und auf Greifhoehe liegt (``pick_height`` des
  Ablaufs) -- sonst ist er vermutlich nicht der Punkt dieser Lage,
* wo PICK in der juengsten Episode der Aufnahme stand (Vergleich).

Zwei Teile: Qt-frei :func:`read_pick_state` / :func:`pick_warnings` (testbar),
:class:`PickView` zeichnet.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .. import config
from ..auto_layout import convex_hull, inside_with_margin
from ..table import clearance, yaw_deg

#: PICK weicht so weit von der Greifhoehe des Ablaufs ab -> Hinweis
HEIGHT_TOL_M = 0.002
#: PICK steht so weit von der juengsten Episode entfernt -> Hinweis
MOVED_TOL_M = 0.003


@dataclass
class PickState:
    """Was die Ansicht zeigt (Basis-KS, m)."""

    table_points: dict                    # Name -> (x, y)
    pick: tuple = None                    # (x, y)
    pick_yaw_deg: float = None
    pick_above_table_m: float = None
    pick_height_m: float = config.PICK_HEIGHT_DEFAULT_M
    updated_at: str = None                # Zeitstempel der Steuerung (ISO), sonst None
    read_at: str = ""                     # wann gelesen (lokal)
    last_episode: dict = None             # {"xy", "when", "where"} oder None
    warnings: list = field(default_factory=list)


def _parse_time(text):
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


def describe_age(updated_at, now=None):
    """'vor 12 min' / 'vor 3 h' / 'am 14.11. 09:12' -- oder '' ohne Zeit."""
    when = _parse_time(updated_at)
    if when is None:
        return ""
    now = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    minutes = (now - when).total_seconds() / 60.0
    if minutes < 0:
        return when.astimezone().strftime("am %d.%m. %H:%M")
    if minutes < 90:
        return "vor %d min" % int(round(minutes))
    if minutes < 36 * 60:
        return "vor %.0f h" % (minutes / 60.0)
    return when.astimezone().strftime("am %d.%m. %H:%M")


def latest_episode_pick(data_root):
    """PICK der juengsten Episode unter ``data_root`` (Tag/ep_*/meta.json)."""
    root = Path(data_root) if data_root else None
    if root is None or not root.is_dir():
        return None
    metas = sorted(root.glob("*/ep_*/meta.json"), key=lambda p: p.stat().st_mtime)
    for path in reversed(metas[-20:]):
        try:
            meta = json.loads(path.read_text(encoding="utf-8")).get("metadata") or {}
            pose = meta["points"]["PICK"]["pose_quat"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        return {"xy": (float(pose[0]), float(pose[1])),
                "when": str(meta.get("recorded_at") or ""),
                "where": "%s/%s" % (path.parent.parent.name, path.parent.name)}
    return None


def read_pick_state(robot, sequence_path, data_root=None, now=None):
    """PICK und Tischpunkte live aus der Steuerung (wie record.py/infer.py)."""
    from ..sequence import load_sequence, resolve_sequence

    sequence = load_sequence(sequence_path)
    resolved = resolve_sequence(sequence, robot)
    points = {name: (float(p["pose_quat"][0]), float(p["pose_quat"][1]))
              for name, p in resolved.table_points.items()}
    state = PickState(points, pick_height_m=float(sequence.pick_height or config.PICK_HEIGHT_DEFAULT_M),
                      read_at=(now or datetime.now()).strftime("%H:%M:%S"))
    if "PICK" in resolved.points:
        pose = np.asarray(resolved.points["PICK"]["pose_quat"], dtype=float)
        state.pick = (float(pose[0]), float(pose[1]))
        state.pick_yaw_deg = yaw_deg(pose, resolved.table)
        if resolved.table is not None:
            state.pick_above_table_m = clearance(resolved.table, pose[:3])
        try:
            record = robot.point_record("PICK")
            state.updated_at = record.get("updatedAt") or record.get("createdAt")
        except Exception:      # Sim/aeltere Steuerung: kein Zeitstempel
            state.updated_at = None
    state.last_episode = latest_episode_pick(data_root)
    state.warnings = pick_warnings(state)
    return state


def pick_warnings(state):
    """Hinweise, dass PICK nicht zur aktuellen Lage passen koennte."""
    out = []
    if state.pick is None:
        return ["PICK fehlt in der Steuerung"]
    if len(state.table_points) >= 3:
        hull = convex_hull(list(state.table_points.values()))
        if not inside_with_margin(hull, state.pick, 0.0):
            out.append("PICK liegt ausserhalb der Tischpunkte")
    else:
        out.append("weniger als 3 Tischpunkte -- Tischbereich unbekannt")
    if state.pick_above_table_m is not None and \
            abs(state.pick_above_table_m - state.pick_height_m) > HEIGHT_TOL_M:
        out.append("PICK %.1f mm ueber dem Tisch, Ablauf erwartet %.1f mm -- anders geteacht?"
                   % (1e3 * state.pick_above_table_m, 1e3 * state.pick_height_m))
    last = state.last_episode
    if last is not None:
        moved = float(np.hypot(state.pick[0] - last["xy"][0], state.pick[1] - last["xy"][1]))
        if moved > MOVED_TOL_M:
            out.append("PICK %.0f mm neben dem der juengsten Episode (%s) -- Objekt seitdem "
                       "umgelegt? Lage pruefen." % (1e3 * moved, last["where"]))
    return out


def state_text(state, now=None):
    """Kurzbeschreibung unter der Ansicht."""
    if state is None:
        return "PICK nicht gelesen -- mit der Steuerung verbinden, dann \"PICK lesen\"."
    if state.pick is None:
        return "PICK fehlt in der Steuerung."
    bits = ["PICK x %.1f  y %.1f mm, Drehung %.0f°" % (1e3 * state.pick[0], 1e3 * state.pick[1],
                                                      state.pick_yaw_deg or 0.0)]
    if state.pick_above_table_m is not None:
        bits.append("%.1f mm über Tisch" % (1e3 * state.pick_above_table_m))
    age = describe_age(state.updated_at, now)
    bits.append("geändert %s" % age if age else "Änderungszeit unbekannt")
    bits.append("gelesen %s" % state.read_at)
    return " · ".join(bits)


# -- Zeichnen ---------------------------------------------------------------

try:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
    from PySide6.QtWidgets import QWidget
except ImportError:          # Qt-freie Tests
    QWidget = object


class PickView(QWidget):
    """Draufsicht: Tischpunkte, Tischbereich, PICK mit Backenrichtung."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = None
        self.setMinimumSize(220, 200)

    def set_state(self, state):
        self.state = state
        self.update()

    def _view(self, x, y):
        # Roboter unten: Basis-x nach oben, Basis-y nach links
        return -y, -x

    def paintEvent(self, _event):     # noqa: N802 (Qt-API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -8)
        state = self.state
        if state is None or not state.table_points:
            painter.setPen(QColor("#888"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "PICK nicht gelesen")
            return
        pts = dict(state.table_points)
        extra = [state.pick] if state.pick else []
        if state.last_episode:
            extra.append(state.last_episode["xy"])
        view = [self._view(*p) for p in list(pts.values()) + extra]
        u = np.array([v[0] for v in view])
        w = np.array([v[1] for v in view])
        span = max(float(u.max() - u.min()), float(w.max() - w.min()), 0.05) * 1.15
        cu, cw = float(u.mean()), float(w.mean())
        scale = min(rect.width(), rect.height()) / span

        def px(x, y):
            a, b = self._view(x, y)
            return QPointF(rect.center().x() + (a - cu) * scale,
                           rect.center().y() + (b - cw) * scale)

        # Tischbereich
        hull = convex_hull(list(pts.values()))
        painter.setPen(QPen(QColor("#9aa7b4"), 1))
        painter.setBrush(QColor(154, 167, 180, 40))
        painter.drawPolygon(QPolygonF([px(*p) for p in hull]))
        # Tischpunkte
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        for name, (x, y) in sorted(pts.items()):
            p = px(x, y)
            painter.setPen(QPen(QColor("#5b6b7b"), 1))
            painter.setBrush(QColor("#5b6b7b"))
            painter.drawEllipse(p, 2.5, 2.5)
            painter.drawText(QRectF(p.x() + 3, p.y() - 12, 40, 12), name)
        # juengste Episode (grau, gestrichelt)
        if state.last_episode:
            p = px(*state.last_episode["xy"])
            painter.setPen(QPen(QColor("#999"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(p, 6, 6)
        # PICK mit Backenrichtung
        if state.pick:
            color = QColor("#c0392b" if state.warnings else "#1e8449")
            p = px(*state.pick)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(p, 4, 4)
            if state.pick_yaw_deg is not None:
                t = np.radians(state.pick_yaw_deg)
                tip = px(state.pick[0] + 0.03 * np.cos(t), state.pick[1] + 0.03 * np.sin(t))
                tail = px(state.pick[0] - 0.03 * np.cos(t), state.pick[1] - 0.03 * np.sin(t))
                painter.drawLine(tail, tip)
            painter.drawText(QRectF(p.x() + 6, p.y() + 2, 40, 12), "PICK")
        painter.setPen(QColor("#888"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                         "Roboter")
