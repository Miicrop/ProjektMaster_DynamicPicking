"""MuJoCo-Szene der Taktiksimulation: MJCF-Aufbau und die gemeinsame Welt.

**Kinematik** kommt aus ``bc/data/lara5_candidate.urdf`` -- derselben Kette,
die die Pipeline nutzt und die an der Anlage auf 1e-11 m mit der Steuerung
uebereinstimmt (``local_fk_check`` der Aufnahmen 2026-11-19). Das Werkzeug
sitzt 197,5 mm vor dem Flansch (TCP = Spitze der Greiferbacken).

**Optik** der Glieder: die Meshes der Praesentation
(``presentation/abschluss/public/urdf/meshes``). Deren URDF hat andere
Gliedlaengen und -rahmen, aber dieselbe Nullstellung und dieselben
Drehrichtungen; jedes Mesh haengt deshalb mit einem festen Versatz an
seinem Glied (:func:`mesh_offsets`, je Glied ``W_A(0)^-1 W_B(0)``). Am
Handgelenk weichen die beiden Modelle um ~8 mm ab -- reine Optik. Fehlen die
Meshes, zeichnet die Szene einfache Zylinder.

**Kameras:** Lage und Objektiv aus den Referenzbildern (``kalibrierung.py``).
MuJoCo rendert nur eine ideale Lochkamera; die radiale Verzeichnung (Wrist:
3,6-mm-Objektiv mit k1/k2, Szene: Fisheye-Modell, angepasst) wird danach per
``cv2.remap`` aufgebracht (:class:`Objektiv`).

**Greifen** ist kein Kontakt: Schliesst der Greifer und liegt das Objekt
zwischen den Backen, wird es angeheftet (mittig zwischen die Backen gezogen,
Drehung auf die Backen ausgerichtet). Oeffnet er, faellt es senkrecht auf
die Tischebene.

**Zeit:** Die Welt rechnet nur, wenn jemand fragt -- :meth:`Welt.weiter_bis`
fuehrt das Folgemodell bis zur Uhrzeit nach. Kein eigener Takt, keine
Physik-Schritte.
"""

import math
import threading
from pathlib import Path

import numpy as np

from .. import config, geometry
from ..table import TablePlane
from ..urdf import KinematicChain
from . import parameter as params_module
from .folgemodell import Folgemodell

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[3]
PRESENTATION_URDF = REPO_ROOT / "presentation" / "abschluss" / "public" / "urdf" / "lara5.urdf"
TEXTURE_DIR = _HERE / "texturen"
PUNKTE_DATEI = _HERE / "punkte_2026-11-19.json"

#: Kamera-Namen in der Szene = Kameraplaetze der Pipeline (config.CAMERAS)
CAMERA_NAMES = ("wrist", "scene")

#: Groesse des Zwischenbilds (Lochkamera) fuer die Verzeichnungs-Umrechnung: Hoehe
#: in Pixeln je Ausgabezeile. 2 = doppelt so fein wie das Ausgabebild.
OVERSAMPLE = 2


# --------------------------------------------------------------------------
# Hilfen: Transformationen
# --------------------------------------------------------------------------

def _T(R=None, p=None):
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if p is not None:
        T[:3, 3] = p
    return T


def _quat(R):
    q = np.asarray(geometry.matrix_to_quat(R), dtype=float)
    return q / np.linalg.norm(q)


def _fmt(values):
    return " ".join("%.9g" % float(v) for v in values)


def _rpy(r, p, y):
    from ..urdf import _rpy_matrix

    return _rpy_matrix(r, p, y)


def _joint_origin(j):
    return _T(_rpy(*j.rpy), j.xyz)


def link_frames(chain, q):
    """Weltrahmen je Glied: [Basis, Glied 1, ..., Glied n, Flansch].

    Basis = Rahmen vor dem ersten revoluten Gelenk, Flansch = Kettenende.
    """
    frames = chain.fk_frames(q)
    out = []
    prev = np.eye(4)
    for (name, T), j in zip(frames, chain.joints):
        if j.type == "revolute":
            if not out:
                out.append(prev)
            out.append(T)
        prev = T
    out.append(frames[-1][1])
    return out


def mesh_offsets(chain_a, chain_b):
    """Fester Versatz je Glied: Rahmen von Modell B im Rahmen von Modell A.

    Gleiche Nullstellung und Drehrichtungen vorausgesetzt (geprueft mit
    zufaelligen Stellungen: Abweichung 0). Rueckgabe Liste 4x4 je Glied
    0..n (0 = Basis, bezogen auf die WELT, nicht auf Glied 0 von A).
    """
    zero = np.zeros(chain_a.n_joints)
    fa = link_frames(chain_a, zero)
    fb = link_frames(chain_b, zero)
    out = [fb[0]]
    for k in range(1, chain_a.n_joints + 1):
        out.append(np.linalg.inv(fa[k]) @ fb[k])
    return out


def _presentation_meshes():
    """Meshes je Glied (Dateinamen) aus der Praesentations-URDF."""
    import xml.etree.ElementTree as ET

    root = ET.parse(str(PRESENTATION_URDF)).getroot()
    out = {}
    for link in root.findall("link"):
        files = []
        for vis in link.findall("visual"):
            mesh = vis.find("geometry/mesh")
            if mesh is not None:
                files.append(mesh.get("filename"))
        if files:
            out[link.get("name")] = files
    return out


# --------------------------------------------------------------------------
# Objektiv: ideale Lochkamera rendern, Verzeichnung aufbringen
# --------------------------------------------------------------------------

class Objektiv(object):
    """Abbildung Ausgabebild <- Lochkamera-Zwischenbild.

    ``eintrag``: Kamera-Abschnitt aus parameter.json (modell, f_px, k1,
    bild_px). Ausgabe ``width`` x ``height`` (gleiches Seitenverhaeltnis wie
    ``bild_px``). Berechnet Zwischenbildgroesse und vertikalen Oeffnungswinkel
    der MuJoCo-Kamera so, dass alle Strahlen des Ausgabebilds darin liegen.
    """

    def __init__(self, eintrag, width, height, oversample=OVERSAMPLE):
        import cv2

        self.width, self.height = int(width), int(height)
        scale = self.width / float(eintrag["bild_px"][0])
        f = float(eintrag["f_px"]) * scale
        k1 = float(eintrag["k1"])
        k2 = float(eintrag.get("k2", 0.0))
        model = eintrag["modell"]
        u = np.arange(self.width) + 0.5 - self.width / 2.0
        v = np.arange(self.height) + 0.5 - self.height / 2.0
        uu, vv = np.meshgrid(u, v)
        r = np.hypot(uu, vv)
        theta = _invert_radius(r / f, k1, model, k2)
        t = np.tan(theta)
        with np.errstate(invalid="ignore", divide="ignore"):
            scale_r = np.where(r > 1e-9, t / r, 1.0 / f)
        tx, ty = uu * scale_r, vv * scale_r  # Tangens-Koordinaten (Lochkamera)
        need_x = float(np.max(np.abs(tx))) * 1.02
        need_y = float(np.max(np.abs(ty))) * 1.02
        self.pin_h = int(self.height * oversample)
        self.pin_w = int(round(self.pin_h * need_x / need_y))
        self.pin_w += self.pin_w % 2
        fp = (self.pin_h / 2.0) / need_y
        self.fovy_deg = math.degrees(2 * math.atan(need_y))
        self.map_x = (tx * fp + self.pin_w / 2.0 - 0.5).astype(np.float32)
        self.map_y = (ty * fp + self.pin_h / 2.0 - 0.5).astype(np.float32)
        self._cv2 = cv2

    def apply(self, pinhole_image):
        return self._cv2.remap(pinhole_image, self.map_x, self.map_y,
                               interpolation=self._cv2.INTER_LINEAR,
                               borderMode=self._cv2.BORDER_CONSTANT)


def _invert_radius(rn, k1, model, k2=0.0):
    """r/f -> theta fuer beide Modelle (Newton, wenige Schritte).

    fisheye: r/f = theta (1 + k1 theta^2 + k2 theta^4)
    pinhole: r/f = t (1 + k1 t^2 + k2 t^4), t = tan(theta)"""
    u = rn.copy()
    for _ in range(15):
        g = u * (1 + k1 * u ** 2 + k2 * u ** 4) - rn
        dg = 1 + 3 * k1 * u ** 2 + 5 * k2 * u ** 4
        u = u - g / dg
    if model == "fisheye":
        return np.clip(u, 0.0, 1.45)
    return np.arctan(np.clip(u, 0.0, 50.0))


# --------------------------------------------------------------------------
# MJCF
# --------------------------------------------------------------------------

def _aruco_textures():
    """ArUco-Marker 0-3 (DICT_4X4_50) mit weissem Rand als PNG (einmalig)."""
    import cv2

    TEXTURE_DIR.mkdir(exist_ok=True)
    paths = {}
    for mid in range(4):
        path = TEXTURE_DIR / ("aruco_%d.png" % mid)
        if not path.is_file():
            marker = cv2.aruco.generateImageMarker(
                cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), mid, 200)
            pad = int(round(200 * (67.0 / 50.0 - 1) / 2))
            img = cv2.copyMakeBorder(marker, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
            cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        paths[mid] = path
    return paths


def _object_vertices(p):
    """Lila Quader mit EINER gefasten Ecke (+x, +y) -- Objekt-KS: x = lange
    Seite, z nach oben, Ursprung in der Mitte."""
    L, W, H, c = p["laenge_m"] / 2, p["breite_m"] / 2, p["hoehe_m"] / 2, p["fase_m"]
    ring = [(-L, -W), (L, -W), (L, W - c), (L - c, W), (-L, W)]
    verts = []
    for z in (-H, H):
        for x, y in ring:
            verts.append((x, y, z))
    return verts


def build_mjcf(par, table_plane):
    """MJCF-Text der ganzen Szene."""
    chain = KinematicChain.from_urdf(config.URDF_PATH)
    tool_offset = np.asarray(par["werkzeug"]["tcp_versatz_m"], dtype=float)
    g = par["greifer"]
    obj = par["objekt"]
    tisch = par["tisch"]
    licht = par["licht"]

    use_meshes = PRESENTATION_URDF.is_file()
    assets, bodies = [], []
    offsets = None
    meshes = {}
    if use_meshes:
        chain_b = KinematicChain.from_urdf(PRESENTATION_URDF)
        offsets = mesh_offsets(chain, chain_b)
        meshes = _presentation_meshes()
        mesh_dir = PRESENTATION_URDF.parent
        link_names_b = ["lara5_link%d" % k for k in range(chain.n_joints + 1)]
        for k, lname in enumerate(link_names_b):
            for fname in meshes.get(lname, []):
                mname = Path(fname).stem
                assets.append('<mesh name="%s" file="%s"/>'
                              % (mname, (mesh_dir / fname).as_posix()))

    tex = _aruco_textures()
    for mid, path in tex.items():
        assets.append('<texture name="aruco%d" type="2d" file="%s"/>' % (mid, path.as_posix()))
        assets.append('<material name="aruco%d" texture="aruco%d" texrepeat="1 1" '
                      'texuniform="false" specular="0" shininess="0"/>' % (mid, mid))
    assets.append('<mesh name="objekt" vertex="%s"/>'
                  % " ".join(_fmt(v) for v in _object_vertices(obj)))
    assets.append('<material name="weiss" rgba="0.93 0.93 0.93 1" specular="0.3" shininess="0.3"/>')
    assets.append('<material name="greifer" rgba="0.22 0.22 0.24 1" specular="0.4"/>')
    assets.append('<material name="backen" rgba="0.2 0.2 0.22 1" specular="0.3"/>')
    assets.append('<material name="tisch" rgba="%s" specular="0.02" shininess="0.1"/>'
                  % _fmt(tisch["rgba"]))
    assets.append('<material name="objekt" rgba="%s" specular="0.1" shininess="0.1"/>'
                  % _fmt(obj["rgba"]))

    def mesh_geoms(k, indent):
        if not use_meshes:
            return []
        out = []
        C = offsets[k]
        for fname in meshes.get("lara5_link%d" % k, []):
            out.append('%s<geom type="mesh" mesh="%s" material="weiss" pos="%s" quat="%s"/>'
                       % (indent, Path(fname).stem, _fmt(C[:3, 3]), _fmt(_quat(C[:3, :3]))))
        return out

    # -- Arm: Koerper je revolutem Gelenk, feste Gelenke werden eingerechnet
    lines = []
    if use_meshes:
        lines += mesh_geoms(0, "    ")
    else:
        lines.append('    <geom type="cylinder" size="0.07 0.06" pos="0 0 0.06" material="weiss"/>')
    pending = np.eye(4)
    depth = 1
    k = 0
    revolute = [j for j in chain.joints if j.type == "revolute"]
    for j in chain.joints:
        if j.type != "revolute":
            pending = pending @ _joint_origin(j)
            continue
        k += 1
        T = pending @ _joint_origin(j)
        pending = np.eye(4)
        ind = "    " * depth
        lo, hi = j.limit if j.limit is not None else (-math.pi, math.pi)
        lines.append('%s<body name="glied%d" pos="%s" quat="%s">'
                     % (ind, k, _fmt(T[:3, 3]), _fmt(_quat(T[:3, :3]))))
        lines.append('%s    <joint name="q%d" type="hinge" axis="%s" range="%s"/>'
                     % (ind, k, _fmt(j.axis), _fmt((lo, hi))))
        if use_meshes:
            lines += mesh_geoms(k, ind + "    ")
        else:
            nxt = revolute[k] if k < len(revolute) else None
            if nxt is not None:
                lines.append('%s    <geom type="capsule" size="0.045" fromto="0 0 0 %s" material="weiss"/>'
                             % (ind, _fmt(nxt.xyz)))
        depth += 1
    # Flansch (Rest der festen Gelenke) -> Greifer und Werkzeug
    ind = "    " * depth
    lines.append('%s<body name="flansch" pos="%s" quat="%s">'
                 % (ind, _fmt(pending[:3, 3]), _fmt(_quat(pending[:3, :3]))))
    i2 = ind + "    "
    fs = g["flansch_scheibe"]
    lines.append('%s<geom type="cylinder" size="%s" pos="0 0 %s" material="greifer"/>'
                 % (i2, _fmt((fs["radius_m"], fs["laenge_m"] / 2)), "%.6g" % (fs["laenge_m"] / 2)))
    gh = np.asarray(g["gehaeuse_m"], dtype=float)
    z_backen = tool_offset[2] - g["backen_laenge_m"]
    z_geh = fs["laenge_m"] + gh[2] / 2
    # Gehaeuse und Backen um die Werkzeugachse verdreht montiert (backen_drehung_grad)
    a = math.radians(g["backen_drehung_grad"])
    lines.append('%s<body name="greifer" quat="%s">' % (i2, _fmt((math.cos(a / 2), 0, 0, math.sin(a / 2)))))
    i3 = i2 + "    "
    lines.append('%s<geom type="box" size="%s" pos="0 0 %s" material="greifer"/>'
                 % (i3, _fmt(gh / 2), "%.6g" % z_geh))
    half = np.array([g["backen_dicke_m"], g["backen_breite_m"], g["backen_laenge_m"]]) / 2
    zc = z_backen + g["backen_laenge_m"] / 2
    for side, name in ((1, "backe_plus"), (-1, "backe_minus")):
        lines.append('%s<body name="%s" pos="%s">' % (i3, name, _fmt(np.array([0, 0, zc]))))
        lines.append('%s    <joint name="%s" type="slide" axis="%s"/>' % (i3, name, _fmt((side, 0, 0))))
        lines.append('%s    <geom type="box" size="%s" material="backen"/>' % (i3, _fmt(half)))
        lines.append('%s</body>' % i3)
    lines.append('%s</body>' % i2)
    # Werkzeug (TCP) und Wrist-Kamera
    lines.append('%s<body name="werkzeug" pos="%s">' % (i2, _fmt(tool_offset)))
    lines.append('%s    <site name="tcp" size="0.002" rgba="0 0 0 0"/>' % i2)
    wk = par["kameras"].get("wrist", {})
    if "versatz_werkzeug_m" in wk:
        R_cv = geometry.quat_to_matrix(wk["quat_werkzeug_wxyz"])
        R_mj = R_cv @ np.diag([1.0, -1.0, -1.0])
        lines.append('%s    <body name="wrist_kamera" pos="%s" quat="%s">'
                     % (i2, _fmt(wk["versatz_werkzeug_m"]), _fmt(_quat(R_mj))))
        lines.append('%s        <camera name="wrist" fovy="90"/>' % i2)
        lines.append('%s        <geom type="box" size="0.016 0.016 0.02" pos="0 0 0.022" material="greifer"/>' % i2)
        lines.append('%s        <light name="wrist_licht" mode="fixed" type="spot" pos="0 0 0.005" '
                     'dir="0 0 -1" cutoff="%s" exponent="2" diffuse="%s" specular="0.1 0.1 0.1" '
                     'attenuation="1 0 0.6" castshadow="false"/>'
                     % (i2, "%.6g" % licht["wrist_oeffnung_grad"], _fmt(licht["wrist_diffus"])))
        lines.append('%s    </body>' % i2)
    lines.append('%s</body>' % i2)
    lines.append('%s</body>' % ind)
    for d in range(depth - 1, 0, -1):
        lines.append('%s</body>' % ("    " * d))

    # -- Tisch: Platte in der geteachten Ebene (geneigt), Marker darauf
    x0, x1 = tisch["x_m"]
    y0, y1 = tisch["y_m"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    n = table_plane.normal_at(cx, cy)
    R_t = _rot_z_to(n)
    zc = table_plane.height_at(cx, cy) - table_plane.correction_at(cx, cy)
    center = np.array([cx, cy, zc]) - n * tisch["dicke_m"] / 2
    world = []
    world.append('<geom name="tisch" type="box" size="%s" pos="%s" quat="%s" material="tisch"/>'
                 % (_fmt(((x1 - x0) / 2, (y1 - y0) / 2, tisch["dicke_m"] / 2)), _fmt(center),
                    _fmt(_quat(R_t))))
    from .kalibrierung import marker_centers

    def plane_z(x, y):
        return table_plane.height_at(x, y) - table_plane.correction_at(x, y)

    for mid, c in marker_centers(plane_z).items():
        world.append('<geom name="marker%d" type="box" size="0.0335 0.0335 0.0003" pos="%s" '
                     'quat="%s" material="aruco%d"/>'
                     % (mid, _fmt(c + n * 0.0003), _fmt(_quat(R_t)), mid))
    # Boden und Umgebung (warm, wie im Referenzbild ausserhalb der Platte)
    world.append('<geom name="boden" type="plane" size="3 3 0.1" pos="0 0 -0.75" rgba="0.62 0.5 0.36 1"/>')
    world.append('<geom name="wand_x" type="box" size="0.02 1.5 1" pos="1.1 0 0" rgba="0.75 0.62 0.45 1"/>')
    world.append('<geom name="wand_y" type="box" size="1.5 0.02 1" pos="0 -0.95 0" rgba="0.7 0.58 0.44 1"/>')
    # Objekt (frei, Lage setzt die Welt direkt)
    world.append('<body name="objekt" pos="0.4 -0.15 0.01">')
    world.append('    <freejoint name="objekt"/>')
    world.append('    <geom type="mesh" mesh="objekt" material="objekt"/>')
    world.append('</body>')
    # Szenenkamera (fest)
    sk = par["kameras"].get("scene", {})
    if "pos_m" in sk:
        R_cv = geometry.quat_to_matrix(sk["quat_wxyz"])
        R_mj = R_cv @ np.diag([1.0, -1.0, -1.0])
        world.append('<camera name="scene" pos="%s" quat="%s" fovy="60"/>'
                     % (_fmt(sk["pos_m"]), _fmt(_quat(R_mj))))
    # Licht: Decke + Fenster (gerichtet), Umgebung ueber headlight
    world.append('<light name="decke" mode="fixed" directional="true" pos="0.4 -0.1 2" dir="0 0 -1" '
                 'diffuse="%s" specular="0.15 0.15 0.15" castshadow="false"/>' % _fmt(licht["decke_diffus"]))
    world.append('<light name="fenster" mode="fixed" directional="true" pos="1 -1 1.5" dir="-0.4 0.5 -0.75" '
                 'diffuse="0.25 0.22 0.18" specular="0 0 0" castshadow="false"/>')

    xml = """<mujoco model="lara5_taktiksim">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="0.002" gravity="0 0 0"/>
  <visual>
    <global offwidth="2400" offheight="1600"/>
    <headlight active="1" ambient="%s" diffuse="0 0 0" specular="0 0 0"/>
    <quality shadowsize="2048"/>
    <map znear="0.005" zfar="20"/>
  </visual>
  <default>
    <geom contype="0" conaffinity="0"/>
  </default>
  <asset>
    %s
  </asset>
  <worldbody>
%s
    %s
  </worldbody>
</mujoco>
""" % (_fmt(licht["umgebung"]), "\n    ".join(assets), "\n".join(lines), "\n    ".join(world))
    return xml


def _rot_z_to(n):
    """Drehung, die z auf ``n`` legt (minimal, um die Achse z x n)."""
    z = np.array([0.0, 0.0, 1.0])
    n = np.asarray(n, dtype=float) / np.linalg.norm(n)
    v = np.cross(z, n)
    s, c = np.linalg.norm(v), float(np.dot(z, n))
    if s < 1e-12:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / s ** 2)


# --------------------------------------------------------------------------
# Welt
# --------------------------------------------------------------------------

def load_points(path=PUNKTE_DATEI):
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


class Welt(object):
    """Gemeinsamer Zustand von Arm, Greifer, Objekt -- und die Renderer.

    Alle oeffentlichen Methoden sind threadsicher (ein Lock). Zeiten in
    Sekunden der injizierten Uhr.
    """

    def __init__(self, clock=None, par=None, punkte_datei=PUNKTE_DATEI):
        import mujoco

        self._mj = mujoco
        self.clock = clock
        self.par = par if par is not None else params_module.load()
        self.punkte = load_points(punkte_datei)
        self.table = TablePlane.from_dict(self.punkte["table"])
        self.xml = build_mjcf(self.par, self.table)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self._lock = threading.RLock()
        self.chain = KinematicChain.from_urdf(config.URDF_PATH)
        self.tool_offset = _T(p=self.par["werkzeug"]["tcp_versatz_m"])
        a = math.radians(self.par["greifer"]["backen_drehung_grad"])
        #: Greifer-KS = Werkzeug-KS um z gedreht: x = Backenachse (Schliessrichtung)
        self.greifer_rot = _T(np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]))
        m = self.model
        self._qadr = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "q%d" % (i + 1))]
                      for i in range(6)]
        self._jaw = [m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
                     for n in ("backe_plus", "backe_minus")]
        self._obj = m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "objekt")]
        self._wrist_light = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_LIGHT, "wrist_licht")
        self._tcp_site = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, "tcp")
        self.folge = Folgemodell(self.par["folgemodell"])
        home = np.asarray(self.punkte["punkte"]["CLEAR_FOV"]["joints"], dtype=float)
        self.folge.reset(home, None)
        g = self.par["greifer"]
        self.greifer_zu = False
        self._jaw_from = self._jaw_to = g["abstand_offen_m"]
        self._jaw_t0 = None
        #: Objektlage im Basis-KS (4x4) und -- angeheftet -- im Werkzeug-KS
        self.objekt = np.eye(4)
        self.angeheftet = None
        #: Protokoll fuer Tests/Abnahme: (t, "angeheftet"/"abgelegt"/"verfehlt", xy)
        self.ereignisse = []
        self.wrist_licht = True
        self._renderers = {}
        self._objektive = {}
        self.objekt_an_punkt("PICK")

    # -- Zeit ---------------------------------------------------------------

    def now(self):
        if self.clock is None:
            raise RuntimeError("Welt hat keine Uhr")
        return self.clock.now()

    def weiter_bis(self, t=None):
        """Folgemodell bis ``t`` (Default: jetzt) nachrechnen."""
        with self._lock:
            t = self.now() if t is None else float(t)
            self.folge.advance(t)

    # -- Arm ----------------------------------------------------------------

    @property
    def gelenke(self):
        with self._lock:
            return self.folge.q.copy()

    def sollwert(self, t, q):
        """Ein servo_j-Sollwert (Zeitpunkt des Eingangs)."""
        with self._lock:
            self.folge.advance(t)
            self.folge.push(t, np.asarray(q, dtype=float))

    def setze_gelenke(self, q, t=None):
        """Arm steht sofort bei ``q`` (Ende einer PTP-Fahrt, Start)."""
        with self._lock:
            self.folge.reset(np.asarray(q, dtype=float), t)

    def tool_matrix(self, q):
        return self.chain.fk(np.asarray(q, dtype=float)) @ self.tool_offset

    def greifer_matrix(self, q):
        """Werkzeug-KS um die Montagedrehung gedreht: x = Backenachse."""
        return self.tool_matrix(q) @ self.greifer_rot

    # -- Greifer und Objekt -------------------------------------------------

    def _jaw_opening(self, t):
        g = self.par["greifer"]
        if self._jaw_t0 is None:
            return self._jaw_to
        a = min(1.0, max(0.0, (t - self._jaw_t0) / g["schliesszeit_s"]))
        return self._jaw_from + a * (self._jaw_to - self._jaw_from)

    def greifer(self, close, t=None):
        """Greiferbefehl. Schliessen heftet das Objekt an, wenn es zwischen
        den Backen liegt; Oeffnen legt es auf die Tischebene."""
        with self._lock:
            t = self.now() if t is None else float(t)
            self.folge.advance(t)
            close = bool(close)
            if close == self.greifer_zu:
                return
            g = self.par["greifer"]
            self._jaw_from = self._jaw_opening(t)
            self._jaw_t0 = t
            self.greifer_zu = close
            T_tool = self.greifer_matrix(self.folge.q)
            if close:
                fit = self._grasp_check(T_tool)
                if fit is not None:
                    self.angeheftet = fit
                    self.objekt = T_tool @ fit
                    self._jaw_to = self.par["objekt"]["breite_m"]
                    self.ereignisse.append((t, "angeheftet", self.objekt[:2, 3].tolist()))
                else:
                    self._jaw_to = g["abstand_zu_leer_m"]
                    self.ereignisse.append((t, "verfehlt", T_tool[:2, 3].tolist()))
            else:
                self._jaw_to = g["abstand_offen_m"]
                if self.angeheftet is not None:
                    self.objekt = self._drop(T_tool @ self.angeheftet)
                    self.angeheftet = None
                    self.ereignisse.append((t, "abgelegt", self.objekt[:2, 3].tolist()))

    def _grasp_check(self, T_tool):
        """Liegt das Objekt zwischen den Backen? -> Lage im Greifer-KS oder None.

        ``T_tool`` ist hier das Greifer-KS (x = Backenachse, z = Werkzeug-z)."""
        g = self.par["greifer"]
        o = self.par["objekt"]
        rel = np.linalg.inv(T_tool) @ self.objekt
        p = rel[:3, 3]
        a, b = 0, 1
        # Hoehe: Werkzeug-z zeigt nach unten, die Backenspitzen liegen bei z = 0,
        # die Oberseite des Objekts bei p_z - h/2. Die Backen muessen mindestens
        # anheften_hoehe_min ins Objekt reichen und duerfen nicht ganz darueber
        # stehen (Backen reichen bis z = -backen_laenge).
        overlap = o["hoehe_m"] / 2 - p[2]
        if overlap < g["anheften_hoehe_min_m"] or p[2] + o["hoehe_m"] / 2 < -g["backen_laenge_m"]:
            return None
        # Objektachsen im Werkzeug-KS: kurze Seite (Objekt-y) soll laengs der Backen liegen
        ox = rel[:3, 0]
        yaw_obj = math.atan2(ox[1], ox[0])
        # gewuenscht: lange Seite quer zu den Backen -> Objekt-x laengs Greifer-y
        target = math.pi / 2
        d = (yaw_obj - target + math.pi / 2) % math.pi - math.pi / 2
        if abs(d) > math.radians(25):
            return None
        span = abs(math.cos(d)) * o["breite_m"] + abs(math.sin(d)) * o["laenge_m"]
        if abs(p[a]) + span / 2 > g["abstand_offen_m"] / 2 + 0.002:
            return None
        if abs(p[b]) > g["anheften_quer_toleranz_m"] + (o["laenge_m"] - g["backen_breite_m"]) / 2:
            return None
        # Backen zentrieren und ausrichten
        fit = np.eye(4)
        yaw = yaw_obj - d
        c, s = math.cos(yaw), math.sin(yaw)
        fit[:3, :3] = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        # Objekt-z zeigt nach oben, Werkzeug-z nach unten: im Werkzeug-KS ist das
        # Objekt um seine x-Achse gekippt (Objekt-z = -Werkzeug-z)
        if rel[2, 2] < 0:
            fit[:3, :3] = fit[:3, :3] @ np.diag([1.0, -1.0, -1.0])
        pos = p.copy()
        pos[a] = 0.0
        fit[:3, 3] = pos
        return fit

    def _drop(self, T_obj):
        """Objekt senkrecht auf die Tischebene fallen lassen (Gier bleibt)."""
        x, y = T_obj[0, 3], T_obj[1, 3]
        ox = T_obj[:3, 0]
        yaw = math.atan2(ox[1], ox[0])
        # Ist das Objekt im Greifer kopfueber? Dann bleibt die Fase gespiegelt
        upright = T_obj[2, 2] > 0
        return self.objekt_matrix(x, y, yaw, upright)

    def objekt_matrix(self, x, y, yaw, upright=True):
        n = self.table.normal_at(x, y)
        h = self.par["objekt"]["hoehe_m"]
        z = self.table.height_at(x, y) - self.table.correction_at(x, y)
        c, s = math.cos(yaw), math.sin(yaw)
        R = _rot_z_to(n) @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        if not upright:
            R = R @ np.diag([1.0, -1.0, -1.0])
        return _T(R, np.array([x, y, z]) + n * h / 2)

    def objekt_ablegen(self, x, y, yaw_rad, upright=True):
        """Sim-Haken: Objekt an eine Lage legen (loest es vom Greifer)."""
        with self._lock:
            self.angeheftet = None
            self.objekt = self.objekt_matrix(x, y, yaw_rad, upright)

    def objekt_an_punkt(self, name="PICK", joints=None):
        """Sim-Haken: Objekt so hinlegen, dass der Greifer an ``name`` es fasst
        (Mitte unter dem TCP, kurze Seite laengs der Backenachse)."""
        q = joints if joints is not None else self.punkte["punkte"][name]["joints"]
        T = self.greifer_matrix(q)
        b_axis = T[:3, 1]
        yaw = math.atan2(b_axis[1], b_axis[0])
        self.objekt_ablegen(T[0, 3], T[1, 3], yaw)

    def objekt_lage(self):
        """(x, y, Gier in rad) der Objektmitte im Basis-KS -- volle 360 Grad."""
        with self._lock:
            T = self.objekt if self.angeheftet is None else (
                self.greifer_matrix(self.folge.q) @ self.angeheftet)
            ox = T[:3, 0]
            return float(T[0, 3]), float(T[1, 3]), math.atan2(ox[1], ox[0]), T.copy()

    # -- Rendern ------------------------------------------------------------

    def _sync(self, t):
        mj = self._mj
        q = self.folge.q
        for adr, v in zip(self._qadr, q):
            self.data.qpos[adr] = v
        gap = self._jaw_opening(t)
        half = gap / 2 + self.par["greifer"]["backen_dicke_m"] / 2
        for adr in self._jaw:
            self.data.qpos[adr] = half
        T = self.objekt if self.angeheftet is None else self.greifer_matrix(q) @ self.angeheftet
        self.data.qpos[self._obj:self._obj + 3] = T[:3, 3]
        self.data.qpos[self._obj + 3:self._obj + 7] = _quat(T[:3, :3])
        self.model.light_active[self._wrist_light] = 1 if self.wrist_licht else 0
        mj.mj_kinematics(self.model, self.data)
        mj.mj_camlight(self.model, self.data)

    def objektiv(self, name, width, height):
        key = (name, int(width), int(height))
        if key not in self._objektive:
            self._objektive[key] = Objektiv(self.par["kameras"][name], width, height)
        return self._objektive[key]

    def render(self, name, width=config.IMAGE_WIDTH, height=config.IMAGE_HEIGHT, t=None):
        """RGB-Bild (H, W, 3) uint8 der Kamera ``name`` zum Zeitpunkt ``t``."""
        mj = self._mj
        with self._lock:
            t = self.now() if t is None and self.clock is not None else t
            if t is not None:
                self.folge.advance(t)
            obj = self.objektiv(name, width, height)
            cam_id = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_CAMERA, name)
            if cam_id < 0:
                raise KeyError("Kamera %r fehlt in der Szene" % name)
            self.model.cam_fovy[cam_id] = obj.fovy_deg
            self._sync(t if t is not None else 0.0)
            rkey = (obj.pin_w, obj.pin_h)
            if rkey not in self._renderers:
                self._renderers[rkey] = mj.Renderer(self.model, height=obj.pin_h, width=obj.pin_w)
            r = self._renderers[rkey]
            r.update_scene(self.data, camera=name)
            img = r.render()
            return obj.apply(img)

    def tcp_site(self):
        """TCP aus MuJoCo (Pruefung der Kette) -- nach dem letzten Render/_sync."""
        with self._lock:
            self._sync(self.folge.t if self.folge.t is not None else 0.0)
            return self.data.site_xpos[self._tcp_site].copy(), \
                self.data.site_xmat[self._tcp_site].reshape(3, 3).copy()

    def close(self):
        with self._lock:
            for r in self._renderers.values():
                try:
                    r.close()
                except Exception:
                    pass
            self._renderers.clear()
