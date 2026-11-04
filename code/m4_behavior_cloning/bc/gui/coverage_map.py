"""Tischabdeckung als Grafik: Felder, Lagen, Drehungen (Anwender 2026-11-01).

Zeigt, was ``apps/record.py`` beim Verteilen der Lagen sieht
(bc/auto_layout.Coverage): den Bereich der Tischpunkte, geteilt in Felder,
eingefaerbt nach der Zahl der Fahrten darin, dazu die Sperrzonen, jede
bisherige Lage als Punkt mit Strich in Richtung der Greiferbacken und
darunter die Belegung der Drehabschnitte. Leere Felder sind hervorgehoben,
die Kandidaten fuer die naechste Lage blau umrandet.

Zwei Teile:

* Qt-frei (testbar): :func:`load_episodes` liest die meta.json im Zielordner,
  :func:`region_from_resolved` / :func:`region_from_meta` liefern Bereich,
  Sperrzonen und Bezugsdrehung, :func:`build_snapshot` rechnet alles fuer
  die Grafik zusammen.
* :class:`CoverageMap` zeichnet einen Snapshot.

Ansicht: von oben, Roboter unten (Basis-x nach oben, Basis-y nach links) --
so, wie man hinter dem Roboter steht. "Drehen" dreht in 90-Grad-Schritten.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import config
from ..auto_layout import Coverage, episode_metas
from ..table import Keepout, TablePlane, align_pose, yaw_deg


# -- Daten -------------------------------------------------------------------

@dataclass
class Region:
    """Bereich der Tischpunkte, Sperrzonen und Bezugsdrehung (geteachter PICK)."""

    points: dict                      # Name -> (x, y)
    keepouts: list = field(default_factory=list)
    base_yaw_deg: float = 0.0
    pick_xy: tuple = None
    source: str = ""                  # "Steuerung" | "Episode ep_00012"


def region_from_resolved(resolved, pick_height=config.PICK_HEIGHT_DEFAULT_M):
    """Aus einem aufgeloesten Ablauf (bc/sequence.resolve_sequence)."""
    if resolved is None or len(resolved.table_points) < 3:
        return None
    points = {name: tuple(float(v) for v in p["pose_quat"][:2])
              for name, p in resolved.table_points.items()}
    base, pick_xy = 0.0, None
    if "PICK" in resolved.points:
        pick = np.asarray(resolved.points["PICK"]["pose_quat"], dtype=float)
        base = yaw_deg(align_pose(pick, resolved.table, pick_height), resolved.table)
        pick_xy = (float(pick[0]), float(pick[1]))
    return Region(points, list(resolved.keepouts), base, pick_xy, "Steuerung")


def _plane_from_dict(data):
    if not data:
        return None
    known = {k: data[k] for k in ("a", "b", "c", "d", "e", "f", "x0", "y0", "residual_m", "count")
             if k in data}
    if data.get("corr_dz"):
        known["corr_xy"] = tuple(tuple(p) for p in data.get("corr_xy", ()))
        known["corr_dz"] = tuple(data["corr_dz"])
    try:
        return TablePlane(**known)
    except TypeError:
        return None


def region_from_meta(meta, folder=""):
    """Aus den Metadaten einer Episode (``table_points``, ``keepout``, PICK)."""
    data = meta.get("metadata", meta) if isinstance(meta, dict) else {}
    table_points = data.get("table_points") or {}
    if len(table_points) < 3:
        return None
    points = {name: tuple(float(v) for v in p["pose_quat"][:2])
              for name, p in table_points.items() if p.get("pose_quat")}
    keepouts = []
    for zone in data.get("keepout") or []:
        try:
            keepouts.append(Keepout(zone["name"], tuple(zone["center"]),
                                    float(zone.get("half_size", config.KEEPOUT_HALF_SIZE_M)),
                                    float(zone.get("min_height", config.KEEPOUT_MIN_HEIGHT_M)),
                                    float(zone.get("object_margin",
                                                   config.KEEPOUT_OBJECT_MARGIN_M))))
        except (KeyError, TypeError, ValueError):
            continue
    plane = _plane_from_dict(data.get("table"))
    base, pick_xy = 0.0, None
    pick = (data.get("points") or {}).get("PICK")
    if pick and pick.get("pose_quat"):
        pose = np.asarray(pick["pose_quat"], dtype=float)
        base = yaw_deg(pose, plane)
        pick_xy = (float(pose[0]), float(pose[1]))
    return Region(points, keepouts, base, pick_xy, "Episode %s" % folder if folder else "Episode")


@dataclass
class EpisodeSpot:
    """Eine aufgezeichnete Lage."""

    folder: str
    xy: tuple
    yaw_deg: float = None
    source: str = ""                  # geteacht | automatisch | variante
    group: str = None                 # repeat_group -- Varianten einer Lage
    recorded_at: str = ""
    discarded: bool = False


def load_episodes(roots, in_simulation=None):
    """Lagen aller Episoden unter ``roots`` (Ordner oder Liste, jede Episode
    einmal) und die Metadaten der juengsten mit Tischpunkten und geteachtem
    PICK (fuer :func:`region_from_meta`). Mit ``in_simulation``: nur Episoden
    derselben Art Roboter, wie record.py zaehlt (bc/auto_layout.counts_for).
    Rueckgabe ``(spots, (ordner, meta) | None)``."""
    if not roots:
        return [], None
    if isinstance(roots, (str, Path)):
        roots = [roots]
    spots, latest = [], None
    for meta_path, meta in episode_metas(roots):
        if not meta:
            continue
        data = meta.get("metadata") or {}
        other = data.get("in_simulation")
        if in_simulation is not None and other is not None and bool(other) != bool(in_simulation):
            continue
        folder = meta_path.parent
        if data.get("table_points") and data.get("object_source", "geteacht") == "geteacht":
            stamp = data.get("recorded_at") or ""
            if latest is None or stamp >= latest[2]:
                latest = (folder.name, meta, stamp)
        xy = data.get("object_xy_m")
        if not xy:
            continue
        spots.append(EpisodeSpot(
            folder="%s/%s" % (folder.parent.name, folder.name), xy=(float(xy[0]), float(xy[1])),
            yaw_deg=data.get("object_yaw_deg"), source=data.get("object_source") or "",
            group=data.get("repeat_group"), recorded_at=data.get("recorded_at") or "",
            discarded=bool(meta.get("discarded"))))
    spots.sort(key=lambda s: (s.recorded_at, s.folder))
    return spots, (latest[:2] if latest else None)


@dataclass
class Snapshot:
    """Alles, was :class:`CoverageMap` zeichnet."""

    region: Region
    coverage: Coverage
    spots: list
    candidates: list                  # Felder, aus denen die naechste Lage kommt
    yaw_candidates: list
    error: str = ""

    def cell_rect(self, cell):
        cov = self.coverage
        x = cov.x_lo + cell[0] * cov.cw
        y = cov.y_lo + cell[1] * cov.ch
        return x, y, cov.cw, cov.ch

    def summary(self):
        counts = list(self.coverage.cell_count.values())
        used = [s for s in self.spots if not s.discarded]
        return ("%d Fahrt(en) gezählt · %d Felder, %d leer · Fahrten je Feld %d–%d"
                % (len(used), len(counts), sum(1 for c in counts if not c),
                   min(counts) if counts else 0, max(counts) if counts else 0))


def build_snapshot(region, spots, margin=config.AUTO_EDGE_MARGIN_M,
                   yaw_range_deg=config.AUTO_YAW_RANGE_DEG):
    """Belegung wie in record.py (verworfene Episoden zaehlen nicht).
    None, wenn kein Bereich da ist; bei unbrauchbarem Bereich ``error``."""
    if region is None:
        return None
    try:
        coverage = Coverage([np.r_[xy, 0.0] for xy in region.points.values()],
                            region.base_yaw_deg, region.keepouts, margin=margin,
                            yaw_range_deg=yaw_range_deg, rng=np.random.default_rng(0))
    except ValueError as exc:
        return Snapshot(region, None, list(spots), [], [], str(exc))
    for spot in spots:
        if not spot.discarded:
            coverage.add(spot.xy, spot.yaw_deg)
    least = min(coverage.cell_count.values())
    candidates = [c for c, n in coverage.cell_count.items() if n == least]
    if coverage.seen_xy and len(candidates) > 1:
        seen = np.asarray(coverage.seen_xy)

        def gap(cell):
            centre = np.array([coverage.x_lo + (cell[0] + 0.5) * coverage.cw,
                               coverage.y_lo + (cell[1] + 0.5) * coverage.ch])
            return float(np.min(np.linalg.norm(seen - centre, axis=1)))

        best = max(gap(c) for c in candidates)
        candidates = [c for c in candidates
                      if gap(c) >= best - 0.25 * min(coverage.cw, coverage.ch)]
    low = min(coverage.yaw_count)
    yaw_candidates = [k for k, n in enumerate(coverage.yaw_count) if n == low]
    return Snapshot(region, coverage, list(spots), candidates, yaw_candidates)


# -- Zeichnen ----------------------------------------------------------------

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
    from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget
except ImportError:  # Qt-freie Nutzung (Tests ohne Oberflaeche)
    QWidget = object

    def Signal(*_args):                      # noqa: N802
        return None


#: Farben (Fusion hell)
_PAPER = "#fbfaf7"
_TABLE = "#efe9df"
_EDGE = "#8d8478"
_EMPTY = "#ffcc80"            # leeres Feld: hier fehlt noch etwas
_FULL = (46, 125, 50)         # meistbelegtes Feld (GOOD)
_CANDIDATE = "#1565c0"
_KEEPOUT = "#c62828"
_OLD = "#546e7a"
_RUN = "#e65100"
_TEXT = "#37474f"


class CoverageMap(QWidget):
    """Draufsicht auf den Tisch mit Feldern, Lagen und Drehabschnitten.

    Drehabschnitte als Raster rechts neben den Feldern (Anwender 2026-11-03:
    die Leiste darunter kostete Hoehe, die Felder waren zu klein).
    ``double_clicked``: der Reiter oeffnet daraufhin eine Grossansicht.
    """

    #: Breite der Spalte rechts mit den Drehabschnitten (px)
    YAW_PANEL = 132
    #: Drehabschnitte je Zeile im Raster
    YAW_COLUMNS = 2

    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = None
        self.run_since = ""           # Lagen ab diesem Zeitstempel: laufender Aufruf
        self.rotation = 0             # Vielfache von 90 Grad
        self.placeholder = "Keine Tischpunkte — Ablauf mit Tischpunkten wählen und verbinden."
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # -- Daten --
    def set_snapshot(self, snapshot, run_since=None):
        self.snapshot = snapshot
        if run_since is not None:
            self.run_since = run_since
        self.update()

    def rotate(self):
        self.rotation = (self.rotation + 1) % 4
        self.update()

    # -- Abbildung Basis-KS -> Bild --
    def _view(self, x, y):
        """Basis (x, y) -> Ansichtskoordinaten (u nach rechts, v nach oben)."""
        u, v = -y, x                  # Roboter unten: x nach oben, y nach links
        for _ in range(self.rotation):
            u, v = v, -u
        return u, v

    def _layout(self):
        snap = self.snapshot
        xs = [p for p in snap.region.points.values()]
        xs += [s.xy for s in snap.spots]
        for zone in snap.region.keepouts:
            cx, cy = zone.center
            h = zone.half_size + zone.object_margin
            xs += [(cx - h, cy - h), (cx + h, cy + h)]
        uv = np.array([self._view(*p) for p in xs])
        lo, hi = uv.min(axis=0), uv.max(axis=0)
        span = np.maximum(hi - lo, 1e-3)
        pad = 26
        panel = self.YAW_PANEL if snap.coverage is not None else 0
        w = max(10.0, self.width() - 2 * pad - panel)
        h = max(10.0, self.height() - 2 * pad - 20)
        scale = min(w / span[0], h / span[1])
        ox = pad + (w - scale * span[0]) / 2.0
        oy = pad + 18 + (h - scale * span[1]) / 2.0
        return lo, scale, ox, oy, span

    def _to_px(self, layout, x, y):
        lo, scale, ox, oy, span = layout
        u, v = self._view(x, y)
        return QPointF(ox + (u - lo[0]) * scale, oy + (span[1] - (v - lo[1])) * scale)

    def _rect_px(self, layout, x, y, w, h):
        corners = [self._to_px(layout, x + a, y + b) for a, b in ((0, 0), (w, 0), (w, h), (0, h))]
        return QPolygonF(corners)

    # -- Zeichnen --
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(_PAPER))
        snap = self.snapshot
        if snap is None or not snap.region.points:
            painter.setPen(QColor(_TEXT))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.placeholder)
            return
        layout = self._layout()
        cov = snap.coverage

        # Tischflaeche (Huelle der Tischpunkte)
        hull = cov.hull if cov is not None else None
        if hull is None:
            from ..auto_layout import convex_hull
            hull = convex_hull(list(snap.region.points.values()))
        poly = QPolygonF([self._to_px(layout, x, y) for x, y in hull])
        painter.setPen(QPen(QColor(_EDGE), 1.5))
        painter.setBrush(QColor(_TABLE))
        painter.drawPolygon(poly)

        # Felder
        if cov is not None:
            top = max(cov.cell_count.values()) or 1
            small = QFont(self.font())
            small.setPointSizeF(max(7.0, self.font().pointSizeF() - 1))
            painter.setFont(small)
            for cell, count in cov.cell_count.items():
                rect = self._rect_px(layout, *snap.cell_rect(cell))
                if count == 0:
                    color = QColor(_EMPTY)
                    color.setAlpha(170)
                else:
                    t = 0.25 + 0.75 * count / top
                    color = QColor(int(255 + (_FULL[0] - 255) * t), int(255 + (_FULL[1] - 255) * t),
                                   int(255 + (_FULL[2] - 255) * t), 200)
                painter.setPen(QPen(QColor(_EDGE), 0.6, Qt.PenStyle.DotLine))
                painter.setBrush(color)
                painter.drawPolygon(rect)
                if cell in snap.candidates:
                    painter.setPen(QPen(QColor(_CANDIDATE), 2.2, Qt.PenStyle.DashLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPolygon(rect.boundingRect().adjusted(2, 2, -2, -2))
                painter.setPen(QColor("#ffffff" if count and count >= 0.6 * top else _TEXT))
                painter.drawText(rect.boundingRect(), Qt.AlignmentFlag.AlignCenter, str(count))
            painter.setFont(self.font())

        # Sperrzonen
        for zone in snap.region.keepouts:
            cx, cy = zone.center
            h = zone.half_size
            rect = self._rect_px(layout, cx - h, cy - h, 2 * h, 2 * h)
            red = QColor(_KEEPOUT)
            fill = QColor(red)
            fill.setAlpha(45)
            painter.setPen(QPen(red, 1.4))
            painter.setBrush(QBrush(fill))
            painter.drawPolygon(rect)
            painter.setBrush(QBrush(red, Qt.BrushStyle.BDiagPattern))
            painter.drawPolygon(rect)
            painter.setPen(red)
            painter.drawText(rect.boundingRect().adjusted(3, 1, 0, 0),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, zone.name)
            if zone.object_margin > 0:
                # bis hierher kommt der TCP neuer Lagen (Bauteil ausserhalb)
                m = zone.object_margin
                outer = self._rect_px(layout, cx - h - m, cy - h - m, 2 * (h + m), 2 * (h + m))
                radius = m * layout[1]
                painter.setPen(QPen(red, 1.0, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(outer.boundingRect(), radius, radius)

        # Tischpunkte
        painter.setPen(QPen(QColor(_EDGE), 1))
        for name, (x, y) in sorted(snap.region.points.items()):
            p = self._to_px(layout, x, y)
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(QRectF(p.x() - 3.5, p.y() - 3.5, 7, 7))
            painter.drawText(QPointF(p.x() + 5, p.y() - 5), name)

        # Lagen: Varianten einer Lage verbinden, dann Punkte mit Backenrichtung
        groups = {}
        for spot in snap.spots:
            if spot.group and not spot.discarded:
                groups.setdefault(spot.group, []).append(spot)
        for members in groups.values():
            if len(members) < 2:
                continue
            centre = members[0]
            run = centre.recorded_at >= self.run_since if self.run_since else False
            painter.setPen(QPen(QColor(_RUN if run else _OLD), 0.8))
            for other in members[1:]:
                painter.drawLine(self._to_px(layout, *centre.xy), self._to_px(layout, *other.xy))
        last = snap.spots[-1] if snap.spots else None
        _, scale, _, _, _ = layout
        jaw = max(6.0, 0.012 * scale)            # 12 mm Strich, mindestens 6 px
        for spot in snap.spots:
            run = bool(self.run_since) and spot.recorded_at >= self.run_since
            color = QColor(_RUN if run else _OLD)
            if spot.discarded:
                color.setAlpha(80)
            p = self._to_px(layout, *spot.xy)
            if spot.yaw_deg is not None:
                a = np.radians(float(spot.yaw_deg))
                tip = self._to_px(layout, spot.xy[0] + 0.012 * np.cos(a), spot.xy[1] + 0.012 * np.sin(a))
                d = tip - p
                length = max(1e-6, (d.x() ** 2 + d.y() ** 2) ** 0.5)
                d = QPointF(d.x() / length * jaw, d.y() / length * jaw)
                painter.setPen(QPen(color, 1.6))
                painter.drawLine(p - d, p + d)
            radius = 4.2 if run else 3.0
            painter.setPen(QPen(QColor("#ffffff"), 0.8))
            painter.setBrush(color)
            painter.drawEllipse(p, radius, radius)
            if spot is last:
                painter.setPen(QPen(color, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(p, radius + 4, radius + 4)

        # geteachter PICK
        if snap.region.pick_xy is not None:
            p = self._to_px(layout, *snap.region.pick_xy)
            painter.setPen(QPen(QColor("#000000"), 1.6))
            painter.drawLine(QPointF(p.x() - 6, p.y()), QPointF(p.x() + 6, p.y()))
            painter.drawLine(QPointF(p.x(), p.y() - 6), QPointF(p.x(), p.y() + 6))

        self._draw_header(painter, snap)
        self._draw_axes(painter, layout)
        if cov is not None:
            self._draw_yaw_panel(painter, snap)

    def _draw_header(self, painter, snap):
        painter.setPen(QColor(_TEXT))
        text = snap.error or snap.summary()
        painter.drawText(QRectF(8, 2, self.width() - 16, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

    def _draw_axes(self, painter, layout):
        """Kleiner Pfeil fuer Basis-x und -y unten links."""
        base = QPointF(34, self.height() - 14)
        for axis, label in (((1.0, 0.0), "x"), ((0.0, 1.0), "y")):
            u, v = self._view(*axis)
            tip = QPointF(base.x() + 18 * u, base.y() - 18 * v)
            painter.setPen(QPen(QColor(_TEXT), 1.2))
            painter.drawLine(base, tip)
            painter.drawText(QPointF(tip.x() + 2 * u - 3, tip.y() - 2 * v + 4), label)

    def _yaw_cells(self, n):
        """Rechtecke der Drehabschnitte im Raster rechts (Spalten x Zeilen)."""
        cols = max(1, min(self.YAW_COLUMNS, n))
        rows = (n + cols - 1) // cols
        x0 = self.width() - self.YAW_PANEL + 4
        y0 = 44.0
        cell_w = (self.YAW_PANEL - 10) / float(cols)
        cell_h = min(56.0, max(30.0, (self.height() - y0 - 10) / float(rows)))
        return [QRectF(x0 + (k % cols) * cell_w, y0 + (k // cols) * cell_h,
                       cell_w - 4, cell_h - 4) for k in range(n)]

    def _draw_yaw_panel(self, painter, snap):
        cov = snap.coverage
        n = len(cov.yaw_count)
        top = max(cov.yaw_count) or 1
        painter.setPen(QColor(_TEXT))
        painter.drawText(QRectF(self.width() - self.YAW_PANEL, 24, self.YAW_PANEL - 6, 18),
                         Qt.AlignmentFlag.AlignCenter, "Drehung")
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, self.font().pointSizeF() - 1))
        for k, (count, cell) in enumerate(zip(cov.yaw_count, self._yaw_cells(n))):
            label_h = 15.0
            rect = QRectF(cell.left(), cell.top(), cell.width(), cell.height() - label_h)
            painter.setPen(QPen(QColor(_EDGE), 0.6))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(rect)
            filled = QRectF(rect.left(), rect.bottom() - rect.height() * count / top,
                            rect.width(), rect.height() * count / top)
            painter.setBrush(QColor(*_FULL) if count else QColor(_EMPTY))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(filled if count else QRectF(rect.left(), rect.bottom() - 3,
                                                         rect.width(), 3))
            if k in snap.yaw_candidates:
                painter.setPen(QPen(QColor(_CANDIDATE), 1.8, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
            painter.setPen(QColor("#ffffff" if count >= 0.5 * top else _TEXT))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(count))
            painter.setPen(QColor(_TEXT))
            painter.setFont(small)
            lo = -cov.yaw_range + k * 2 * cov.yaw_range / n
            painter.drawText(QRectF(cell.left() - 2, rect.bottom(), cell.width() + 4, label_h),
                             Qt.AlignmentFlag.AlignCenter,
                             "%+.0f…%+.0f°" % (lo, lo + 2 * cov.yaw_range / n))
            painter.setFont(self.font())

    def mouseDoubleClickEvent(self, event):          # noqa: N802 (Qt-API)
        self.double_clicked.emit()

    # -- Tooltip --
    def mouseMoveEvent(self, event):
        snap = self.snapshot
        if snap is None or snap.coverage is None:
            return
        layout = self._layout()
        pos = event.position() if hasattr(event, "position") else event.pos()
        for cell, count in snap.coverage.cell_count.items():
            if self._rect_px(layout, *snap.cell_rect(cell)).containsPoint(
                    pos, Qt.FillRule.OddEvenFill):
                x, y, w, h = snap.cell_rect(cell)
                text = ("Feld %d/%d: %d Fahrt(en)\nx %.0f–%.0f mm, y %.0f–%.0f mm%s"
                        % (cell[0] + 1, cell[1] + 1, count, 1e3 * x, 1e3 * (x + w),
                           1e3 * y, 1e3 * (y + h),
                           "\nKandidat für die nächste Lage" if cell in snap.candidates else ""))
                QToolTip.showText(event.globalPosition().toPoint()
                                  if hasattr(event, "globalPosition") else event.globalPos(),
                                  text, self)
                return
        QToolTip.hideText()

