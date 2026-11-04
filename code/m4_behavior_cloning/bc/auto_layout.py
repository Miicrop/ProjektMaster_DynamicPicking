"""Automatische Objektlagen: der Roboter legt das Objekt selbst um (AP 2.2/2.4).

Wunsch Anwender 2026-10-26: Nach den Fahrten einer Lage legt der Arm das
Objekt nicht an PICK zurueck, sondern an eine NEUE Lage -- neue Position im
Bereich der Tischpunkte, neue Drehung --, und die naechsten Fahrten greifen
dort. Die Lage ist damit exakt bekannt (der Roboter hat sie selbst
hergestellt) und landet als Zahl in den Metadaten. Von Hand geteachte Lagen
bleiben daneben moeglich, vor allem am Rand.

Wie gezogen wird:
* **Bereich**: konvexe Huelle der Tischpunkte (ID0-ID3), um
  ``config.AUTO_EDGE_MARGIN_M`` nach innen geschrumpft.
* **Sperrzonen** (bc/table.Keepout): die neue Greifposition liegt ausserhalb.
* **Abstand**: mindestens ``config.AUTO_MIN_DIST_M`` zu allen bisherigen Lagen
  des Aufrufs -- gleichmaessig ueber die Flaeche statt Haufen.
* **Drehung**: gleichverteilt in +-``yaw_range_deg`` um die geteachte.
* **Hoehe und Neigung**: wie "Ausrichten" (bc/table.align_pose) -- senkrecht
  zur Tischebene, Greifhoehe darueber. So wird an jeder Stelle des schiefen
  Tisches gleich hoch gegriffen und abgelegt.

Seit 2026-11-01 (Anwender: reiner Zufall haeuft manche Stellen) zieht
``record.py`` neue Lagen mit :class:`Coverage` statt :func:`sample_pose`:
Felder und Drehabschnitte, jeweils der bisher seltenste -- auch ueber die
Episoden, die schon im Zielordner liegen (:func:`load_coverage`). Innerhalb
einer Lage legt der Arm das Objekt nach jedem Griff leicht verschoben und
gedreht ab (:func:`variant_offsets`, Varianten).

Erreichbarkeit, Gelenktempo und Kollisionsmodell prueft der Aufrufer wie
bei jeder Lage (apps/record.py); scheitert das, wird neu gezogen.
"""

import numpy as np

from . import config, geometry
from .table import align_pose


class OverridePoints(object):
    """Punktquelle mit ersetzten Punkten -- der Rest kommt aus ``source``.

    So laeuft eine gezogene Lage durch dieselbe Aufloesung wie eine geteachte
    (bc/sequence.resolve_sequence): PRE_PICK/ANFLUG werden daraus berechnet.
    """

    def __init__(self, source, overrides):
        self.source = source
        self.overrides = dict(overrides)

    def point_names(self):
        return list(dict.fromkeys(list(self.source.point_names()) + list(self.overrides)))

    def get_point(self, name):
        if name in self.overrides:
            joints, pose = self.overrides[name]
            return np.asarray(joints, dtype=float), np.asarray(pose, dtype=float)
        return self.source.get_point(name)

    def ik(self, pose, reference):
        return self.source.ik(pose, reference)


def convex_hull(points):
    """Konvexe Huelle (x, y) gegen den Uhrzeigersinn (Andrew)."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside_with_margin(hull, xy, margin):
    """Liegt ``xy`` in der Huelle und mindestens ``margin`` von jeder Kante weg?"""
    if len(hull) < 3:
        return False
    x, y = float(xy[0]), float(xy[1])
    for k in range(len(hull)):
        (x1, y1), (x2, y2) = hull[k], hull[(k + 1) % len(hull)]
        edge = np.array([x2 - x1, y2 - y1])
        length = float(np.linalg.norm(edge))
        if length < 1e-9:
            continue
        # Abstand nach innen (Huelle gegen den Uhrzeigersinn -> links = innen)
        inner = (edge[0] * (y - y1) - edge[1] * (x - x1)) / length
        if inner < margin:
            return False
    return True


def inner_distance(hull, xy):
    """Kleinster Abstand von ``xy`` zu den Kanten, nach innen positiv."""
    x, y = float(xy[0]), float(xy[1])
    best = np.inf
    for k in range(len(hull)):
        (x1, y1), (x2, y2) = hull[k], hull[(k + 1) % len(hull)]
        length = float(np.hypot(x2 - x1, y2 - y1))
        if length < 1e-9:
            continue
        best = min(best, ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) / length)
    return float(best)


def rotated_about(pose, axis, angle_rad):
    """Orientierung von ``pose`` um ``axis`` (Basis-KS) gedreht, Position bleibt."""
    pose = np.asarray(pose, dtype=float).copy()
    turn = geometry.quat_from_axis_angle(np.asarray(axis, dtype=float), float(angle_rad))
    pose[3:] = geometry.quat_canonical(geometry.quat_multiply(turn, pose[3:]), pose[3:])
    return pose


def sample_pose(rng, base_pose, plane, region_points, keepouts=(), previous_xy=(),
                yaw_range_deg=config.AUTO_YAW_RANGE_DEG, pick_height=config.PICK_HEIGHT_DEFAULT_M,
                margin=config.AUTO_EDGE_MARGIN_M, min_dist=config.AUTO_MIN_DIST_M,
                tries=config.AUTO_SAMPLE_TRIES):
    """Eine neue Greifpose -> (Pose, Drehung gegen die geteachte in Grad).

    ``base_pose``: geteachte PICK-Pose (gibt Orientierung vor), ``plane``:
    Tischebene (Pflicht), ``region_points``: Tischpunkte (Posen).
    Wirft ``ValueError``, wenn in ``tries`` Zuegen nichts passt.
    """
    if plane is None:
        raise ValueError("Automatische Lagen brauchen die Tischpunkte (Tischebene)")
    hull = convex_hull([p[:2] for p in region_points])
    if len(hull) < 3:
        raise ValueError("Automatische Lagen brauchen mindestens drei Tischpunkte als Bereich")
    xs, ys = [p[0] for p in hull], [p[1] for p in hull]
    upright = align_pose(base_pose, plane, pick_height)
    for _ in range(int(tries)):
        xy = np.array([rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))])
        if not inside_with_margin(hull, xy, margin):
            continue
        if any(zone.blocks_object(xy) for zone in keepouts):
            continue
        if any(np.linalg.norm(xy - np.asarray(p)) < min_dist for p in previous_xy):
            continue
        turn = float(rng.uniform(-yaw_range_deg, yaw_range_deg))
        return place_pose(upright, plane, xy, turn, pick_height), turn
    raise ValueError("Keine freie Lage gefunden (%d Versuche) -- Bereich zu klein, "
                     "Mindestabstand zu gross oder Sperrzonen zu breit?" % tries)


def place_pose(upright, plane, xy, turn_deg, pick_height=config.PICK_HEIGHT_DEFAULT_M):
    """Greifpose an ``xy``, um ``turn_deg`` gegen ``upright`` gedreht.

    ``upright``: ausgerichtete Bezugspose (bc/table.align_pose). Senkrecht zum
    Tisch AN DIESER STELLE (gewoelbter Tisch) und ``pick_height`` darueber.
    """
    pose = np.asarray(upright, dtype=float).copy()
    pose[0], pose[1] = float(xy[0]), float(xy[1])
    pose = align_pose(pose, plane, pick_height)
    return rotated_about(pose, plane.normal_at(xy[0], xy[1]), np.radians(float(turn_deg)))


def yaw_offset(yaw_abs_deg, base_yaw_deg):
    """Drehung gegen die Bezugslage in -90..90 Grad (Parallelgreifer: modulo 180)."""
    return (float(yaw_abs_deg) - float(base_yaw_deg) + 90.0) % 180.0 - 90.0


class Coverage(object):
    """Kontrollierter Zufall: Felder und Drehabschnitte gleichmaessig belegen.

    Wunsch Anwender 2026-11-01: rein zufaellig gezogene Lagen haeufen sich an
    manchen Stellen. Hier wird der Bereich der Tischpunkte (Huelle minus
    Randabstand, ohne Sperrzonen) in Felder von etwa ``cell_size`` geteilt,
    der Drehbereich +-``yaw_range_deg`` in ``yaw_bins`` Abschnitte. Die
    naechste Gruppe kommt ins bisher seltenste Feld -- bei Gleichstand ins am
    weitesten von allen bisherigen Lagen entfernte -- an eine zufaellige
    Stelle darin, und in den seltensten Drehabschnitt, dort zufaellig.

    Gezaehlt wird alles, was :meth:`add` bekommt: die Episoden im Zielordner
    (:func:`load_coverage`) und jede Fahrt des laufenden Aufrufs.
    """

    def __init__(self, region_points, base_yaw_deg, keepouts=(), margin=config.AUTO_EDGE_MARGIN_M,
                 yaw_range_deg=config.AUTO_YAW_RANGE_DEG, cell_size=config.AUTO_CELL_SIZE_M,
                 yaw_bins=config.AUTO_YAW_BINS, rng=None):
        self.hull = convex_hull([p[:2] for p in region_points])
        if len(self.hull) < 3:
            raise ValueError("Automatische Lagen brauchen mindestens drei Tischpunkte als Bereich")
        self.margin = float(margin)
        self.keepouts = list(keepouts)
        self.base_yaw = float(base_yaw_deg)
        self.yaw_range = float(yaw_range_deg)
        self.yaw_bins = max(1, int(yaw_bins)) if self.yaw_range > 0 else 1
        self.rng = rng if rng is not None else np.random.default_rng()
        xs, ys = [p[0] for p in self.hull], [p[1] for p in self.hull]
        # Gitter ueber das um den Rand geschrumpfte Rechteck, Felder gleich
        # breit (Kantenlaenge hoechstens cell_size)
        self.x_lo, self.y_lo = min(xs) + self.margin, min(ys) + self.margin
        width = max(1e-6, max(xs) - self.margin - self.x_lo)
        height = max(1e-6, max(ys) - self.margin - self.y_lo)
        self.nx = max(1, int(np.ceil(width / float(cell_size) - 1e-9)))
        self.ny = max(1, int(np.ceil(height / float(cell_size) - 1e-9)))
        self.cw, self.ch = width / self.nx, height / self.ny
        self.cells = [(i, j) for i in range(self.nx) for j in range(self.ny)
                      if self._usable(i, j)]
        if not self.cells:
            raise ValueError("Kein freies Feld im Bereich der Tischpunkte -- Randabstand zu "
                             "gross oder Sperrzonen zu breit?")
        self.cell_count = {c: 0 for c in self.cells}
        self.yaw_count = [0] * self.yaw_bins
        self.seen_xy = []

    # -- Felder ---------------------------------------------------------------
    def allowed(self, xy, margin=None):
        """Im Bereich (``margin`` zum Rand, Default der eigene) und das Bauteil
        ausserhalb jeder Sperrzone (bc/table.Keepout.blocks_object)?"""
        margin = self.margin if margin is None else float(margin)
        return (inside_with_margin(self.hull, xy, margin)
                and not any(zone.blocks_object(xy) for zone in self.keepouts))

    def inner_distance(self, xy):
        """Abstand zum naechsten Rand der Huelle (negativ = ausserhalb)."""
        return inner_distance(self.hull, xy)

    def _cell_points(self, i, j, n=5):
        fx = (np.arange(n) + 0.5) / n
        return [(self.x_lo + (i + a) * self.cw, self.y_lo + (j + b) * self.ch)
                for a in fx for b in fx]

    def _usable(self, i, j):
        # mindestens ein Viertel des Felds liegt im erlaubten Bereich
        pts = self._cell_points(i, j)
        return sum(self.allowed(p) for p in pts) >= len(pts) / 4.0

    def cell_of(self, xy):
        i = int(np.floor((float(xy[0]) - self.x_lo) / self.cw))
        j = int(np.floor((float(xy[1]) - self.y_lo) / self.ch))
        return (i, j) if (i, j) in self.cell_count else None

    def yaw_bin_of(self, turn_deg):
        if self.yaw_bins == 1 or abs(turn_deg) > self.yaw_range + 1e-9:
            return 0 if self.yaw_bins == 1 else None
        k = int(np.floor((float(turn_deg) + self.yaw_range) / (2 * self.yaw_range) * self.yaw_bins))
        return min(self.yaw_bins - 1, max(0, k))

    def add(self, xy, yaw_abs_deg=None):
        """Eine Lage zaehlen (``yaw_abs_deg`` wie bc/table.yaw_deg)."""
        self.seen_xy.append((float(xy[0]), float(xy[1])))
        cell = self.cell_of(xy)
        if cell is not None:
            self.cell_count[cell] += 1
        if yaw_abs_deg is not None:
            k = self.yaw_bin_of(yaw_offset(yaw_abs_deg, self.base_yaw))
            if k is not None:
                self.yaw_count[k] += 1

    def summary(self):
        counts = list(self.cell_count.values())
        return ("%d Felder (%d x %d, je %.0f x %.0f mm), belegt %d, leer %d, "
                "Drehabschnitte %s"
                % (len(counts), self.nx, self.ny, 1e3 * self.cw, 1e3 * self.ch,
                   sum(1 for c in counts if c), sum(1 for c in counts if not c),
                   "/".join(str(c) for c in self.yaw_count)))

    # -- Ziehen ---------------------------------------------------------------
    def next_cell(self, exclude=()):
        """Seltenstes Feld; Gleichstand: am weitesten weg von allem Bisherigen."""
        cells = [c for c in self.cells if c not in set(exclude)]
        if not cells:
            raise ValueError("Alle Felder versucht -- keine weitere Lage planbar")
        least = min(self.cell_count[c] for c in cells)
        cands = [c for c in cells if self.cell_count[c] == least]
        if self.seen_xy:
            seen = np.asarray(self.seen_xy)

            def gap(cell):
                centre = np.array([self.x_lo + (cell[0] + 0.5) * self.cw,
                                   self.y_lo + (cell[1] + 0.5) * self.ch])
                return float(np.min(np.linalg.norm(seen - centre, axis=1)))

            best = max(gap(c) for c in cands)
            # etwas Spiel, damit nicht immer dieselbe Reihenfolge herauskommt
            cands = [c for c in cands if gap(c) >= best - 0.25 * min(self.cw, self.ch)]
        return cands[int(self.rng.integers(len(cands)))]

    def point_in(self, cell, tries=200):
        i, j = cell
        for _ in range(tries):
            xy = np.array([self.x_lo + (i + self.rng.uniform()) * self.cw,
                           self.y_lo + (j + self.rng.uniform()) * self.ch])
            if self.allowed(xy):
                return xy
        raise ValueError("Feld %s: keine erlaubte Stelle gefunden" % (cell,))

    def next_turn(self):
        """Drehung gegen die Bezugslage (Grad) aus dem seltensten Abschnitt."""
        if self.yaw_range <= 0:
            return 0.0
        least = min(self.yaw_count)
        cands = [k for k, c in enumerate(self.yaw_count) if c == least]
        k = cands[int(self.rng.integers(len(cands)))]
        width = 2 * self.yaw_range / self.yaw_bins
        return float(-self.yaw_range + (k + self.rng.uniform()) * width)


def episode_metas(roots):
    """``(Pfad, meta)`` aller Episoden ``ep_*/meta.json`` unter ``roots`` --
    jede Datei einmal, auch wenn ein Ordner in einem anderen liegt (Zielordner
    ``data_vm/<Datum>`` und ``--abdeckung data_vm``)."""
    import json
    from pathlib import Path

    seen = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for meta_path in sorted(root.rglob("meta.json")):
            if not meta_path.parent.name.startswith("ep_"):
                continue
            key = str(meta_path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = None
            yield meta_path, meta


def counts_for(meta, in_simulation=None):
    """Zaehlt diese Episode fuer die Abdeckung? Nicht verworfen, mit Lage
    (ab 2026-10-26) und -- wenn ``in_simulation`` gesetzt ist -- von derselben
    Art Roboter (VM-Testlaeufe nicht mit der Anlage mischen)."""
    if not meta or meta.get("discarded"):
        return False
    data = meta.get("metadata") or {}
    if not data.get("object_xy_m"):
        return False
    other = data.get("in_simulation")
    return in_simulation is None or other is None or bool(other) == bool(in_simulation)


def load_coverage(roots, in_simulation=None):
    """Lagen bisheriger Episoden: Liste ``(xy, yaw_deg)`` aus den meta.json.

    ``roots``: Zielordner (Episoden ``ep_*/meta.json`` darin oder tiefer).
    Verworfene Episoden, solche ohne Lage (vor 2026-10-26) und -- mit
    ``in_simulation`` -- die von der anderen Art Roboter zaehlen nicht
    (:func:`counts_for`). Rueckgabe ``(lagen, dateien, sekunden)``.
    """
    import time

    t0 = time.perf_counter()
    found, files = [], 0
    for _path, meta in episode_metas(roots):
        files += 1
        if not counts_for(meta, in_simulation):
            continue
        data = meta["metadata"]
        xy = data["object_xy_m"]
        found.append(((float(xy[0]), float(xy[1])), data.get("object_yaw_deg")))
    return found, files, time.perf_counter() - t0


def variant_offsets(rng, n, shift_m=config.AUTO_VARIANT_SHIFT_M,
                    yaw_deg=config.AUTO_VARIANT_YAW_DEG):
    """``n`` Abweichungen ``(dx, dy, dyaw_deg)`` fuer die Varianten einer Gruppe.

    Gestaffelt statt unabhaengig gezogen: Richtungen gleichmaessig ueber den
    Kreis (zufaellig verdreht), Weite halb bis ganz ``shift_m``; Drehung
    abwechselnd links/rechts, Betrag halb bis ganz ``yaw_deg``, die Betraege
    ueber die Varianten gestaffelt. Reihenfolge zufaellig.
    """
    n = int(n)
    if n <= 0:
        return []
    phase = rng.uniform(0.0, 2 * np.pi)
    angles = phase + 2 * np.pi * np.arange(n) / n
    radii = float(shift_m) * (0.5 + 0.5 * (np.arange(n) + rng.uniform(0, 1, n)) / n)
    radii = rng.permutation(radii)
    sign = 1.0 if rng.uniform() < 0.5 else -1.0
    turns = float(yaw_deg) * (0.5 + 0.5 * (np.arange(n) + rng.uniform(0, 1, n)) / n)
    turns = rng.permutation(turns) * np.array([sign * (-1) ** k for k in range(n)])
    order = rng.permutation(n)
    return [(float(radii[k] * np.cos(angles[k])), float(radii[k] * np.sin(angles[k])),
             float(turns[k])) for k in order]
