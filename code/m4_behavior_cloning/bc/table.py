"""Tischreferenz aus geteachten Punkten (AP 2.2/4.2, Anwender 2026-10-26).

Der Anwender teacht einige Punkte auf dem Tisch bzw. ``config.TABLE_POINT_OFFSET_M``
darueber, mittig ueber den ArUco-Markern (seit 2026-11-02 ID0-ID8 als 3x3-Raster,
Greifer beruehrt den Tisch). Daraus:

* **Tischebene** ``z = a*x + b*y + c`` (ab drei Punkten, sonst waagerecht).
  Bisher lag der "Tisch" im Kollisionsmodell pauschal 15 cm unter dem
  tiefsten Wegpunkt und fing nichts ab.
* **Gewoelbter Tisch** (Anwender 2026-11-01: vermutlich 1-2 mm Bauch in der
  Mitte, nach aussen abfallend): ab ``config.TABLE_CURVED_MIN_POINTS``
  Punkten zusaetzlich eine quadratische Flaeche
  ``+ d*dx^2 + e*dx*dy + f*dy^2`` (dx, dy ab Schwerpunkt der Punkte).
  Genommen wird sie nur, wenn sie die Punkte um mindestens
  ``config.TABLE_CURVED_MIN_GAIN_M`` besser trifft als die Ebene -- sonst
  waere es Anpassen an Teach-Streuung. Punkte am besten als 3x3-Raster
  (Ecken, Kantenmitten, Mitte); die Senkrechte zum Tisch gilt dann je Stelle.
* **Korrektur an den Tischpunkten** (Anlage 2026-11-02, B013-B037): Die
  Ebene verfehlt die Punkte um bis zu 0,4 mm (Mitte tiefer, Raender
  hoeher); beim Umlegen ueber 10-30 cm wurde dadurch spuerbar zu hoch
  oder zu tief abgelegt. Die Abweichung je Punkt wird dazwischen
  interpoliert (inverse Abstandsgewichtung, an den Punkten exakt, weit
  weg gegen ihren Mittelwert ~0) und zur Flaeche addiert -- nur die Hoehe,
  die Senkrechte bleibt die der Flaeche (``config.TABLE_LOCAL_CORRECTION``).
* **Untergrenze**: Kein Wegpunkt und keine Werkzeugspitze darf naeher als
  ``config.TABLE_MIN_CLEARANCE_M`` an die Ebene -- vor jeder Bewegung
  (:func:`table_problems`) und im Kollisionsmodell (:class:`TableSurface`).
* **Ausrichten** von PICK (:func:`align_pose`): Werkzeugachse senkrecht zur
  Tischebene, Drehung um die Hochachse wie geteacht, Hoehe = feste
  Greifhoehe ueber dem Tisch. Begruendung: Neigung (gemessen 0,5-1,3 Grad)
  und Hoehe (5-11 mm) schwankten beim Teachen, ohne dass die Kamera einen
  Grund dafuer sieht -- fuer die Policy widerspruechliche Labels genau an
  der Stelle, an der das Rauschen bewusst auf null gedaempft ist.

Hardwarefrei; Posen als [x, y, z, qw, qx, qy, qz].
"""

from dataclasses import dataclass

import numpy as np

from . import config, geometry


@dataclass
class TablePlane:
    """Tischoberflaeche ``z = a*x + b*y + c`` im Basis-KS, gewoelbt zusaetzlich
    ``+ d*dx^2 + e*dx*dy + f*dy^2`` mit ``dx = x - x0``, ``dy = y - y0``."""

    a: float
    b: float
    c: float
    #: Groesste Abweichung der Punkte von der Flaeche (m) -- Pruefgroesse
    residual_m: float = 0.0
    #: Anzahl der Punkte, aus denen sie bestimmt wurde
    count: int = 0
    #: Kruemmung (alle 0 = Ebene) und ihr Bezugspunkt (Schwerpunkt der Punkte)
    d: float = 0.0
    e: float = 0.0
    f: float = 0.0
    x0: float = 0.0
    y0: float = 0.0
    #: Groesste Abweichung der Punkte von der besten EBENE (m) -- zum Vergleich
    plane_residual_m: float = 0.0
    #: Woelbung (m): Flaeche minus beste Ebene in der Mitte der Punkte,
    #: positiv = Bauch nach oben
    bulge_m: float = 0.0
    #: Korrektur an den Tischpunkten: (x, y) je Punkt und dessen Abweichung
    #: von der Flaeche (m), dazwischen interpoliert (leer = keine)
    corr_xy: tuple = ()
    corr_dz: tuple = ()

    @property
    def corrected(self):
        return len(self.corr_dz) > 0

    def correction_at(self, x, y):
        """Interpolierte Abweichung der Tischpunkte von der Flaeche (m)."""
        if not self.corr_dz:
            return 0.0
        # reines Python: wird im Kollisionsmodell je Bahnpunkt gerufen,
        # numpy kostet bei 9 Punkten das 30-fache
        x, y = float(x), float(y)
        total = weights = 0.0
        for (px, py), dz in zip(self.corr_xy, self.corr_dz):
            dist2 = (px - x) * (px - x) + (py - y) * (py - y)
            if dist2 < 1e-12:
                return dz
            weight = 1.0 / dist2
            total += weight * dz
            weights += weight
        return total / weights

    @property
    def curved(self):
        return bool(self.d or self.e or self.f)

    def height_at(self, x, y):
        dx, dy = float(x) - self.x0, float(y) - self.y0
        return (self.a * float(x) + self.b * float(y) + self.c
                + self.d * dx * dx + self.e * dx * dy + self.f * dy * dy
                + self.correction_at(x, y))

    def normal_at(self, x, y):
        """Einheitsnormale nach oben an der Stelle (x, y)."""
        dx, dy = float(x) - self.x0, float(y) - self.y0
        n = np.array([-(self.a + 2 * self.d * dx + self.e * dy),
                      -(self.b + self.e * dx + 2 * self.f * dy), 1.0])
        return n / np.linalg.norm(n)

    @property
    def normal(self):
        """Einheitsnormale nach oben -- in der Mitte der Punkte."""
        return self.normal_at(self.x0, self.y0)

    @property
    def tilt_deg(self):
        return float(np.degrees(np.arccos(self.normal[2])))

    def describe(self):
        text = ("Tisch aus %d Punkt(en): Hoehe %.1f mm am Ursprung, Neigung %.2f Grad, "
                "groesste Abweichung %.1f mm"
                % (self.count, 1e3 * self.height_at(0.0, 0.0), self.tilt_deg,
                   1e3 * self.residual_m))
        if self.curved:
            text += ("; gewoelbt: %s %.1f mm in der Mitte, als Ebene waeren es %.1f mm "
                     "Abweichung" % ("Bauch" if self.bulge_m >= 0 else "Mulde",
                                     abs(1e3 * self.bulge_m), 1e3 * self.plane_residual_m))
        elif self.count >= config.TABLE_CURVED_MIN_POINTS:
            text += " (eben: Woelbung truege weniger als %.1f mm bei)" % (
                1e3 * config.TABLE_CURVED_MIN_GAIN_M)
        if self.corrected:
            text += "; Korrektur an den Punkten %+.1f..%+.1f mm" % (
                1e3 * min(self.corr_dz), 1e3 * max(self.corr_dz))
        return text

    @classmethod
    def from_dict(cls, data):
        """Gegenstueck zu :meth:`as_dict` (Metadaten einer Aufnahme / Policy)."""
        keys = ("a", "b", "c", "residual_m", "count", "d", "e", "f", "x0", "y0",
                "plane_residual_m", "bulge_m")
        values = {k: data[k] for k in keys if k in data}
        values["corr_xy"] = tuple(tuple(float(v) for v in xy) for xy in data.get("corr_xy") or ())
        values["corr_dz"] = tuple(float(v) for v in data.get("corr_dz") or ())
        return cls(**values)

    def as_dict(self):
        return {"a": self.a, "b": self.b, "c": self.c, "residual_m": self.residual_m,
                "count": self.count, "tilt_deg": self.tilt_deg,
                "model": "gewoelbt" if self.curved else "eben",
                "d": self.d, "e": self.e, "f": self.f, "x0": self.x0, "y0": self.y0,
                "plane_residual_m": self.plane_residual_m, "bulge_m": self.bulge_m,
                "corr_xy": [list(p) for p in self.corr_xy], "corr_dz": list(self.corr_dz)}


def fit_table(positions, offset=config.TABLE_POINT_OFFSET_M, curved=True,
              correct=config.TABLE_LOCAL_CORRECTION):
    """Tischflaeche durch die Punkte (TCP-Positionen), um ``offset`` nach unten.

    Ein oder zwei Punkte: waagerecht auf ihrer mittleren Hoehe. Ab drei:
    Ebene nach kleinsten Quadraten. Ab ``config.TABLE_CURVED_MIN_POINTS``
    (und ``curved``): gewoelbt, wenn das die Punkte um mindestens
    ``config.TABLE_CURVED_MIN_GAIN_M`` besser trifft. Ab
    ``config.TABLE_CORRECTION_MIN_POINTS`` (und ``correct``): Korrektur an
    den Punkten (siehe Moduldoku). None ohne Punkte.
    """
    surface = _fit_surface(positions, offset, curved)
    pts = np.asarray([p[:3] for p in positions], dtype=float).reshape(-1, 3)
    if surface is None or not correct or len(pts) < config.TABLE_CORRECTION_MIN_POINTS:
        return surface
    z = pts[:, 2] - offset
    dz = tuple(float(z[k] - surface.height_at(pts[k, 0], pts[k, 1])) for k in range(len(pts)))
    surface.corr_xy = tuple((float(p[0]), float(p[1])) for p in pts)
    surface.corr_dz = dz
    return surface


def _fit_surface(positions, offset, curved):
    """Ebene bzw. gewoelbte Flaeche ohne Korrektur (:func:`fit_table`)."""
    pts = np.asarray([p[:3] for p in positions], dtype=float).reshape(-1, 3)
    if len(pts) == 0:
        return None
    z = pts[:, 2] - offset
    if len(pts) < 3:
        c = float(np.mean(z))
        residual = float(np.max(np.abs(z - c)))
        return TablePlane(0.0, 0.0, c, residual, len(pts), plane_residual_m=residual)
    design = np.column_stack([pts[:, 0], pts[:, 1], np.ones(len(pts))])
    (a, b, c), *_ = np.linalg.lstsq(design, z, rcond=None)
    residual = float(np.max(np.abs(design @ np.array([a, b, c]) - z)))
    flat = TablePlane(float(a), float(b), float(c), residual, len(pts),
                      plane_residual_m=residual)
    if not curved or len(pts) < config.TABLE_CURVED_MIN_POINTS:
        return flat
    x0, y0 = (float(v) for v in pts[:, :2].mean(axis=0))
    dx, dy = pts[:, 0] - x0, pts[:, 1] - y0
    quad = np.column_stack([design, dx * dx, dx * dy, dy * dy])
    coeffs, _res, rank, _sv = np.linalg.lstsq(quad, z, rcond=None)
    if rank < quad.shape[1]:
        return flat  # z. B. alle Punkte auf einer Linie: Woelbung nicht bestimmbar
    curved_residual = float(np.max(np.abs(quad @ coeffs - z)))
    if residual - curved_residual < config.TABLE_CURVED_MIN_GAIN_M:
        return flat
    qa, qb, qc, d, e, f = (float(v) for v in coeffs)
    surface = TablePlane(qa, qb, qc, curved_residual, len(pts), d=d, e=e, f=f, x0=x0, y0=y0,
                         plane_residual_m=residual)
    surface.bulge_m = surface.height_at(x0, y0) - flat.height_at(x0, y0)
    return surface


def clearance(plane, position):
    """Hoehe eines Punkts ueber der Tischebene (m)."""
    return float(position[2]) - plane.height_at(position[0], position[1])


def table_problems(waypoints, plane, min_clearance=config.TABLE_MIN_CLEARANCE_M,
                   max_residual=config.TABLE_MAX_RESIDUAL_M):
    """Textzeilen fuer Punkte zu nah am (oder unter dem) Tisch. Leer = in Ordnung."""
    if plane is None:
        return []
    out = []
    if plane.residual_m > max_residual:
        out.append("Tischpunkte liegen nicht %s (Abweichung %.1f mm, "
                   "erlaubt %.1f) -- einen davon falsch geteacht?"
                   % ("auf einer glatten Flaeche" if plane.curved else "in einer Ebene",
                      1e3 * plane.residual_m, 1e3 * max_residual))
    seen = set()
    for wp in waypoints:
        name = wp.name or "?"
        if name in seen:
            continue
        seen.add(name)
        height = clearance(plane, wp.pose_quat)
        if height < min_clearance:
            out.append("%s liegt %.1f mm %s dem Tisch (mindestens %.1f mm darueber)"
                       % (name, abs(1e3 * height), "ueber" if height >= 0 else "UNTER",
                          1e3 * min_clearance))
    return out


def _up(plane, pose_quat):
    """Senkrechte zum Tisch an der Stelle der Pose (gewoelbt: oertlich)."""
    if plane is None:
        return np.array([0.0, 0.0, 1.0])
    return plane.normal_at(pose_quat[0], pose_quat[1])


def align_pose(pose_quat, plane=None, pick_height=None):
    """PICK ausrichten: Werkzeugachse senkrecht zum Tisch (gewoelbt: an dieser
    Stelle), Drehung um die Hochachse und x/y bleiben, Hoehe = ``pick_height``
    ueber dem Tisch.

    Ohne Tisch: senkrecht zum Basis-KS, Hoehe bleibt. Welche Richtung der
    Werkzeugachse "unten" ist, wird aus der geteachten Pose uebernommen.
    """
    pose = np.asarray(pose_quat, dtype=float).copy()
    original = pose[3:].copy()
    rot = geometry.quat_to_matrix(original)
    up = _up(plane, pose_quat)
    z_new = up if float(np.dot(rot[:, 2], up)) >= 0 else -up
    # x-Achse des Werkzeugs in die Ebene senkrecht zu z_new projizieren:
    # so bleibt die Drehung um die Hochachse erhalten
    x_old = rot[:, 0]
    x_new = x_old - np.dot(x_old, z_new) * z_new
    if np.linalg.norm(x_new) < 1e-6:  # x zeigte senkrecht -- dann y nehmen
        y_old = rot[:, 1]
        y_new = y_old - np.dot(y_old, z_new) * z_new
        y_new /= np.linalg.norm(y_new)
        x_new = np.cross(y_new, z_new)
    x_new /= np.linalg.norm(x_new)
    y_new = np.cross(z_new, x_new)
    pose[3:] = geometry.quat_canonical(
        geometry.matrix_to_quat(np.column_stack([x_new, y_new, z_new])), original)
    if plane is not None and pick_height is not None:
        pose[2] = plane.height_at(pose[0], pose[1]) + float(pick_height)
    return pose


def yaw_deg(pose_quat, plane=None):
    """Drehung des Greifers um die Tischnormale (Grad, 0..180).

    Winkel der Werkzeug-x-Achse, in die Tischebene projiziert, gegen die
    Basis-x-Achse. Modulo 180: ein Parallelgreifer greift bei 10 und 190
    Grad gleich -- als Objektorientierung zaehlt nur die Achse.
    """
    rot = geometry.quat_to_matrix(np.asarray(pose_quat, dtype=float)[3:])
    up = _up(plane, pose_quat)
    x = rot[:, 0] - np.dot(rot[:, 0], up) * up
    return float(np.degrees(np.arctan2(x[1], x[0])) % 180.0)


def tilt_deg(pose_quat, plane=None):
    """Neigung der Werkzeugachse gegen die Tischnormale (Grad)."""
    rot = geometry.quat_to_matrix(np.asarray(pose_quat, dtype=float)[3:])
    up = _up(plane, pose_quat)
    return float(np.degrees(np.arccos(min(1.0, abs(float(np.dot(rot[:, 2], up)))))))


@dataclass
class Keepout:
    """Sperrzone: Quadrat ``+-half_size`` um ``center`` (x, y) in der Tischebene.

    Darin muss die Werkzeugspitze mindestens ``min_height`` ueber dem Tisch
    bleiben (Anlage 2026-10-26: Schraube im Tisch an Punkt IGNORE).
    Berechnete Greif-/Ablagestellen halten zusaetzlich das Bauteil heraus:
    TCP mindestens ``object_margin`` vom Quadrat (:meth:`blocks_object`).
    """

    name: str
    center: tuple
    half_size: float = config.KEEPOUT_HALF_SIZE_M
    min_height: float = config.KEEPOUT_MIN_HEIGHT_M
    object_margin: float = config.KEEPOUT_OBJECT_MARGIN_M

    def contains_xy(self, position):
        """Liegt der TCP selbst im Quadrat?"""
        return (abs(float(position[0]) - self.center[0]) <= self.half_size
                and abs(float(position[1]) - self.center[1]) <= self.half_size)

    def distance_xy(self, position):
        """Abstand des TCP zum Quadrat in der Ebene (m), 0 = darin."""
        dx = max(0.0, abs(float(position[0]) - self.center[0]) - self.half_size)
        dy = max(0.0, abs(float(position[1]) - self.center[1]) - self.half_size)
        return float(np.hypot(dx, dy))

    def blocks_object(self, position):
        """Ragte ein hier gegriffenes Bauteil ins Quadrat?"""
        return self.distance_xy(position) < self.object_margin

    @classmethod
    def from_dict(cls, data):
        """Gegenstueck zu :meth:`as_dict`."""
        return cls(data["name"], tuple(float(v) for v in data["center"]),
                   **{k: float(data[k]) for k in ("half_size", "min_height", "object_margin")
                      if k in data})

    def as_dict(self):
        return {"name": self.name, "center": [float(v) for v in self.center],
                "half_size": self.half_size, "min_height": self.min_height,
                "object_margin": self.object_margin}


def keepout_problems(waypoints, plane, zones):
    """Wegpunkte in einer Sperrzone und zu tief. Leer = in Ordnung."""
    out = []
    if not zones:
        return out
    seen = set()
    for wp in waypoints:
        name = wp.name or "?"
        if name in seen:
            continue
        seen.add(name)
        height = (clearance(plane, wp.pose_quat) if plane is not None
                  else float(wp.pose_quat[2]))
        for zone in zones:
            if zone.contains_xy(wp.pose_quat) and (plane is None or height < zone.min_height):
                out.append("%s liegt in der Sperrzone um %s (+-%.0f mm)%s -- dort nicht greifen"
                           % (name, zone.name, 1e3 * zone.half_size,
                              "" if plane is None else ", nur %.0f mm ueber dem Tisch" % (1e3 * height)))
    return out


def keepout_notes(waypoints, plane, zones):
    """Tiefe Wegpunkte ausserhalb, deren Bauteil aber ins Quadrat ragt.

    Fuer geteachte Punkte nur ein Hinweis -- der Anwender hat sie gesehen
    (Anlage 2026-11-03: PICK 31 mm neben IGNORE, Schraube ~10 cm weg).
    """
    out = []
    seen = set()
    for wp in waypoints:
        name = wp.name or "?"
        if name in seen or plane is None:
            continue
        seen.add(name)
        if clearance(plane, wp.pose_quat) >= config.KEEPOUT_MIN_HEIGHT_M:
            continue
        for zone in zones:
            if not zone.contains_xy(wp.pose_quat) and zone.blocks_object(wp.pose_quat):
                out.append("%s liegt %.0f mm neben der Sperrzone um %s -- ein Bauteil "
                           "(%.0f mm ab TCP) ragt hinein; geteacht, wird so gefahren"
                           % (name, 1e3 * zone.distance_xy(wp.pose_quat), zone.name,
                              1e3 * zone.object_margin))
    return out


class KeepoutSurface(object):
    """Sperrzone im Kollisionsmodell -- Werkzeugspitze, nur innerhalb der Zone."""

    margin = 0.0

    def __init__(self, zone, plane):
        self.zone = zone
        self.plane = plane
        self.name = "Sperrzone %s" % zone.name

    def clearance_for(self, frame, position, radius):
        if frame != "tool" or not self.zone.contains_xy(position):
            return None
        height = clearance(self.plane, position) if self.plane is not None else float(position[2])
        return height - self.zone.min_height


class TableSurface(object):
    """Tischebene im Kollisionsmodell -- nur fuer die Werkzeugspitze.

    Die Huellkugel des Werkzeugs (``collision.DEFAULT_ARM_POINTS``, 6 cm)
    plus Sicherheitsabstand (3 cm) passt nicht zu einem Griff wenige mm ueber
    dem Tisch: jede Bahn waere verworfen. Hier zaehlt deshalb nur der TCP
    mit eigenem Mindestabstand; Handgelenk und Ellbogen prueft weiter der
    Tischquader darunter (``collision.default_workspace``).
    """

    def __init__(self, plane, min_clearance=config.TABLE_MIN_CLEARANCE_M,
                 frames=("tool",), name="Tischebene"):
        self.plane = plane
        self.margin = float(min_clearance)
        self.frames = tuple(frames)
        self.name = name

    def clearance_for(self, frame, position, radius):
        """Freiraum (m); None = dieser Stuetzpunkt wird hier nicht geprueft."""
        if frame not in self.frames:
            return None
        return clearance(self.plane, position)
