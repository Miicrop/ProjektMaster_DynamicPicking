"""Feste Hindernisse der Zelle mit eigenen Mindestabstaenden je Stuetzpunkt.

Hardwarefrei. Ergaenzt das Kugelmodell aus ``bc/collision.py`` (Werkzeug
6 cm, Handgelenk 8 cm, Ellbogen 9 cm plus 3 cm Abstand). Das ist fuer diese
Zelle zu grob: PRE_PLACE liegt 7 cm ueber der Teststation, die Tischpunkte an
der Kamerastange nur wenige cm davor -- mit Kugeln waeren beide "Kollision".
Hier hat deshalb jedes Hindernis je Stuetzpunkt einen eigenen Mindestabstand,
wie ``table.TableSurface`` fuer den Tisch. Stuetzpunkte ohne Eintrag werden
an diesem Hindernis nicht geprueft.

Stuetzpunkte: ``tool`` (Spitze der Greiferbacken), ``wrist``, ``elbow`` (aus
``RobotPort.link_positions``) und ``camera``: die Wrist-Kamera, seitlich am
Greifer (Werkzeugachse +y, Anwender 2026-11-11: ~53-55 mm), auf Hoehe der
Backenspitzen gerechnet -- fuer die senkrechten Hindernisse (Stange, Basis)
spielt die Hoehe keine Rolle.

Die Werte stehen in ``einstellungen/hindernisse.json`` (eingecheckt: sie
beschreiben die Zelle, nicht den Arbeitsplatz). Sie gelten nur an der REALEN
Anlage -- VM und SimRobot haben andere Koordinaten (VM ohne Tool). Ausserdem
nur fuer M4 (Aufnahme und Inferenz): M2 legt mit eigenem Code in der Station
ab und muss dort tiefer fahren duerfen.
"""

import json
from pathlib import Path

import numpy as np

from . import geometry

#: Name des berechneten Stuetzpunkts der Wrist-Kamera
CAMERA = "camera"

#: Ablage der Hinderniswerte, relativ zum Ordner m4_behavior_cloning
OBSTACLES_FILE = "einstellungen/hindernisse.json"

_ROOT = Path(__file__).resolve().parents[1]


def _box_distance(point, lo, hi):
    """Abstand Punkt -> achsparalleler Quader: positiv aussen, negativ innen."""
    p = np.asarray(point, dtype=float)
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    outside = np.maximum(np.maximum(lo - p, 0.0), p - hi)
    d = float(np.linalg.norm(outside))
    if d > 0.0:
        return d
    return -float(np.min(np.minimum(p - lo, hi - p)))


class ObstacleBox(object):
    """Achsparalleler Quader, Mindestabstand je Stuetzpunkt (m).

    ``lo``/``hi`` je 3 Werte; ``None`` in z = nach unten/oben unbegrenzt
    (senkrechte Stange). Fuer die Kollisionspruefung (collision.CollisionModel)
    ueber :meth:`clearance_for`.
    """

    margin = 0.0

    def __init__(self, name, lo, hi, clearances):
        self.name = name
        self.lo = np.array([-1e9 if v is None else float(v) for v in lo])
        self.hi = np.array([1e9 if v is None else float(v) for v in hi])
        if self.lo.shape != (3,) or np.any(self.lo > self.hi):
            raise ValueError("Hindernis %r: lo/hi ungueltig" % name)
        self.clearances = {k: float(v) for k, v in clearances.items()}

    def clearance_for(self, frame, position, radius):
        need = self.clearances.get(frame)
        if need is None:
            return None
        return _box_distance(position, self.lo, self.hi) - need


class BaseCylinder(object):
    """Roboter selbst (Basis, Glied 2): waagrechter Abstand zur Achse von
    Gelenk 1 mindestens ``radius_min[frame]``. Grenzpose Test-DArm: Kamera
    24 mm vor Achse 2."""

    margin = 0.0

    def __init__(self, name, radius_min):
        self.name = name
        self.radius_min = {k: float(v) for k, v in radius_min.items()}

    def clearance_for(self, frame, position, radius):
        need = self.radius_min.get(frame)
        if need is None:
            return None
        return float(np.hypot(position[0], position[1])) - need


class Envelope(object):
    """Huelle aus den Demonstrationen: der Stuetzpunkt muss INNERHALB bleiben
    (Werkzeugspitze, Quader um alle aufgezeichneten Posen plus Rand)."""

    margin = 0.0

    def __init__(self, lo, hi, frames=("tool",), name="Huelle der Demonstrationen"):
        self.name = name
        self.lo = np.asarray(lo, dtype=float)
        self.hi = np.asarray(hi, dtype=float)
        self.frames = tuple(frames)

    def clearance_for(self, frame, position, radius):
        if frame not in self.frames:
            return None
        return -_box_distance(position, self.lo, self.hi)

    def as_dict(self):
        return {"lo": self.lo.tolist(), "hi": self.hi.tolist(), "frames": list(self.frames)}


def envelope_from_points(points, margin):
    """Quader um alle Punkte (N x 3) plus ``margin`` je Seite."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    return Envelope(pts.min(axis=0) - margin, pts.max(axis=0) + margin)


def camera_point(tool_pose, offset_tool):
    """Kamera-Stuetzpunkt aus der Werkzeugpose [X,Y,Z,QW,QX,QY,QZ]."""
    pose = np.asarray(tool_pose, dtype=float)
    R = geometry.quat_to_matrix(pose[3:7])
    return pose[:3] + R @ np.asarray(offset_tool, dtype=float)


class CellObstacles(object):
    """Inhalt von ``einstellungen/hindernisse.json``."""

    def __init__(self, surfaces, camera_offset_tool, source=None):
        self.surfaces = list(surfaces)
        self.camera_offset_tool = np.asarray(camera_offset_tool, dtype=float)
        self.source = source

    def describe(self):
        return ", ".join(s.name for s in self.surfaces) or "keine"


def load(path=None):
    """Liest die Hindernisse. Fehlt die Datei: None (dann gilt nur das Kugelmodell)."""
    path = Path(path) if path is not None else _ROOT / OBSTACLES_FILE
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    surfaces = []
    for item in data.get("hindernisse", []):
        art = item.get("art")
        if art == "quader":
            surfaces.append(ObstacleBox(item["name"], item["lo"], item["hi"],
                                        item["mindestabstand_m"]))
        elif art == "basis":
            surfaces.append(BaseCylinder(item["name"], item["radius_min_m"]))
        else:
            raise ValueError("%s: Hindernis %r mit unbekannter Art %r"
                             % (path, item.get("name"), art))
    return CellObstacles(surfaces, data.get("kamera_versatz_werkzeug_m", (0.0, 0.0, 0.0)),
                         source=str(path))


def applies(robot_kind, in_simulation, choice="auto"):
    """Gelten die Hindernisse? ``auto``: nur an der realen Anlage."""
    if choice == "an":
        return True
    if choice == "aus":
        return False
    if choice != "auto":
        raise ValueError("Hindernisse: auto, an oder aus (nicht %r)" % choice)
    return robot_kind == "neura" and in_simulation is False
