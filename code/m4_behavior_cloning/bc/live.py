"""Live-Ansicht der Inferenz (Anwender 2026-11-17) -- Qt-frei.

``apps/infer.py`` haelt die Kameras und das Modell; die Oberflaeche kann sie
nicht selbst oeffnen. Deshalb schreibt der Inferenzprozess in einen Ordner
(``<Protokollordner>/live``), und das Fenster (bc/gui/live_window.py) liest
ihn etwa 7x je Sekunde:

* ``state.json`` -- Takt, TCP, PICK, was die Policy plant (je gemittelter
  Vorhersage und das Mittel, das der Arm tatsaechlich faehrt), Spur
* ``scene.jpg``, ``wrist.jpg`` -- verkleinerte Kamerabilder
* ``scene_map.json`` -- Abbildung Roboter-Basis (xy) -> Pixel der
  Szenenkamera, aus den ArUco-Markern von M1 (fuer Pfeile im Livebild)

Die Fahrt darf davon nie langsamer werden: :meth:`LiveWriter.update` legt
nur Kopien in einen Platz, Kinematik, JPEG und Schreiben laufen in einem
eigenen Thread mit eigener Rate. Fehler dort werden einmal gemeldet und
sonst geschluckt -- die Anzeige stoppt nie eine Fahrt.

Drehung: Richtung der Werkzeug-x-Achse, volle 360 Grad (Anwender
2026-11-17: das Objekt hat eine Fase, die Handgelenkkamera schaut zu ihr --
die Greifrichtung ist eindeutig, ein Pfeil).
"""

import json
import math
import os
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from . import config

#: Zeile in der Ausgabe von apps/infer.py, an der die GUI den Ordner erkennt
LIVE_PREFIX = "LIVE-ANSICHT: "
STATE_FILE = "state.json"
SCENE_MAP_FILE = "scene_map.json"
#: Breite der Livebilder (Pixel) -- klein genug fuer ~5 Bilder/s ohne Last
IMAGE_WIDTH = 640
STATE_HZ = 10.0
IMAGE_HZ = 5.0
TRAIL_POINTS = 600
#: Zuletzt erkannte Abbildung der Szenenkamera (die Kamera steht fest). In der
#: Startstellung verdeckt der Arm immer einen Marker (Referenzbilder
#: 2026-11-11: Marker 2 oder 3) -- dann gilt die gespeicherte.
SCENE_MAP_CACHE = Path(__file__).resolve().parents[1] / "einstellungen" / "live_szene.local.json"


def yaw_diff(a, b):
    """a - b auf -180..180 Grad (volle Drehung, Richtung eindeutig)."""
    if a is None or b is None:
        return None
    return float((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def yaw360(pose_quat, plane=None):
    """Richtung der Werkzeug-x-Achse um die Tischnormale, Grad 0..360
    (wie bc/table.yaw_deg, aber ohne modulo 180)."""
    from . import geometry
    from .table import _up

    rot = geometry.quat_to_matrix(np.asarray(pose_quat, dtype=float)[3:7])
    up = _up(plane, pose_quat)
    x = rot[:, 0] - np.dot(rot[:, 0], up) * up
    return float(np.degrees(np.arctan2(x[1], x[0])) % 360.0)


def fast_fk(robot):
    """Vorwaertskinematik ohne Roundtrip zur Steuerung, oder None.

    An der Anlage nur, wenn der Adapter die URDF-Kette beim Verbinden gegen
    die Steuerung bestaetigt hat (bc/adapters/neura.py, ``_local_fk_active``)
    -- sonst kostete jede Pose ~7 ms RPC, je Vorhersage ~100 Posen. Der
    SimRobot rechnet ohnehin lokal.
    """
    if getattr(robot, "_local_fk_active", False) and getattr(robot, "_chain", None) is not None:
        chain, offset = robot._chain, robot._tool_offset
        pose_from_chain = robot._pose_from_chain
        return lambda q: pose_from_chain(chain, np.asarray(q, dtype=float)[:6], offset)
    if type(robot).__name__ == "SimRobot":
        return lambda q: robot.fk(np.asarray(q, dtype=float)[:6])
    return None


def pose_info(pose, plane):
    """Pose (7) -> dict x, y, z (m), yaw (Grad, 0..180), Hoehe ueber Tisch (mm)."""
    from .table import clearance

    pose = np.asarray(pose, dtype=float)
    out = {"x": float(pose[0]), "y": float(pose[1]), "z": float(pose[2]),
           "yaw": yaw360(pose, plane)}
    if plane is not None:
        out["table_mm"] = 1e3 * clearance(plane, pose[:3])
    return out


def grasp_index(actions):
    """Erste Action mit geschlossenem Greifer; sonst None."""
    actions = np.asarray(actions, dtype=float)
    if actions.ndim != 2 or actions.shape[1] < 7:
        return None
    closed = np.flatnonzero(actions[:, 6] > config.GRIPPER_THRESHOLD)
    return int(closed[0]) if closed.size else None


def plan_info(actions, fk, plane, stride=2):
    """Was eine Vorhersage noch vorhat: Bahn (jede ``stride``-te Action) und
    Greifpunkt (erstes Schliessen; schliesst sie nicht: das Ende).
    """
    actions = np.asarray(actions, dtype=float)
    if not len(actions):
        return None
    index = grasp_index(actions)
    picks = sorted(set(list(range(0, len(actions), stride)) + [len(actions) - 1]
                       + ([index] if index is not None else [])))
    poses = {i: np.asarray(fk(actions[i]), dtype=float) for i in picks}
    end = index if index is not None else len(actions) - 1
    grasp = pose_info(poses[end], plane)
    grasp["closes"] = index is not None
    grasp["in_steps"] = int(end)
    path = [[round(float(poses[i][0]), 5), round(float(poses[i][1]), 5),
             round(float(poses[i][2]), 5)] for i in picks]
    return {"path": path, "grasp": grasp}


def mean_actions(chunks):
    """Mittel der Reste wie der ChunkEnsembler (gleiche Gewichte, decay 0),
    so weit ALLE Chunks reichen -- dahinter fiele der aelteste heraus und das
    Mittel spraenge auf eine einzelne Vorhersage."""
    if not chunks:
        return np.zeros((0, 7))
    n = min(len(c) for c in chunks)
    return np.mean([np.asarray(c[:n], dtype=float) for c in chunks], axis=0)


# -- Abbildung Roboter -> Szenenkamera ---------------------------------------

def scene_map_from_workspace(workspace, w2r):
    """M1-Arbeitsbereich (``m1_vision_topdown.workspace.Workspace``) und
    ``workspace_to_robot`` aus system.yaml -> dict fuer :func:`robot_to_image`."""
    return {
        "H_img2rect": np.asarray(workspace.H_img2rect, dtype=float).tolist(),
        "px_per_mm": float(workspace.px_per_mm),
        "size_mm": [float(v) for v in workspace.size_mm],
        "rotation_deg": float(w2r["rotation_deg"]),
        "translation_mm": [float(v) for v in w2r["translation_mm"]],
        "method": str(getattr(workspace, "method", "")),
    }


def robot_to_image(scene_map, xy_m):
    """Roboter-Basis xy (m, (N,2) oder (2,)) -> Pixel im Vollbild der Szenenkamera.

    Umkehrung von M1: Roboter -> Arbeitsbereich (starr, ``workspace_to_robot``
    rueckwaerts) -> entzerrtes Bild -> Kamerabild (Homographie invertiert).
    Gilt exakt in der Tischebene; ein Punkt darueber erscheint durch die
    Perspektive leicht nach aussen versetzt (Lotfusspunkt wird gezeichnet).
    """
    xy = np.asarray(xy_m, dtype=float).reshape(-1, 2) * 1e3
    rot = math.radians(scene_map["rotation_deg"])
    c, s = math.cos(rot), math.sin(rot)
    d = xy - np.asarray(scene_map["translation_mm"], dtype=float)
    ws = np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], axis=1)
    ppm = scene_map["px_per_mm"]
    rect = np.stack([ws[:, 0] * ppm, (scene_map["size_mm"][1] - ws[:, 1]) * ppm,
                     np.ones(len(ws))], axis=1)
    H_inv = np.linalg.inv(np.asarray(scene_map["H_img2rect"], dtype=float))
    img = rect @ H_inv.T
    return img[:, :2] / img[:, 2:3]


def cached_scene_map():
    """Zuletzt gespeicherte Abbildung oder None."""
    try:
        return json.loads(SCENE_MAP_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def detect_scene_map(image_rgb, localizer=None):
    """Abbildung aus einem Bild der Szenenkamera (Marker muessen sichtbar sein).

    Mit ``localizer`` (bc/lokalisierung.M1Localizer, nach ``locate``) wird
    dessen letzter Arbeitsbereich genommen. Wirft bei Fehlern.
    """
    if localizer is not None and getattr(localizer, "last_result", None) is not None:
        return scene_map_from_workspace(localizer.last_result.workspace,
                                        localizer.cfg["workspace_to_robot"])
    import cv2
    from . import lokalisierung

    lokalisierung._import_group()
    from common.config import load_config
    from m1_vision_topdown.workspace import find_workspace

    cfg = (localizer.cfg if localizer is not None
           else load_config(lokalisierung.CODE_ROOT / "config" / "system.yaml"))
    bgr = cv2.cvtColor(np.asarray(image_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)
    return scene_map_from_workspace(find_workspace(bgr, cfg), cfg["workspace_to_robot"])


# -- Schreiben ----------------------------------------------------------------

def write_json_atomic(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    for _ in range(5):              # Windows: Leser hat die Datei kurz offen
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.005)
    return False


def write_bytes_atomic(path, payload):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.005)
    return False


class LiveWriter(object):
    """Schreibt die Live-Ansicht in ``folder`` (eigener Thread).

    ``fk``: :func:`fast_fk` oder None (dann ohne Plan, nur TCP und Bilder).
    """

    def __init__(self, folder, fk=None, image_width=IMAGE_WIDTH, state_hz=STATE_HZ,
                 image_hz=IMAGE_HZ, threaded=True):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.fk = fk
        self.image_width = int(image_width)
        self.state_period = 1.0 / float(state_hz)
        self.image_period = 1.0 / float(image_hz)
        self.known = None
        self.episode = None
        self.errors = []
        self._trail = deque(maxlen=TRAIL_POINTS)
        self._slot = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._running = True
        self._last_state = 0.0
        self._last_image = 0.0
        self._thread = None
        if threaded:
            self._thread = threading.Thread(target=self._loop, name="live-ansicht", daemon=True)
            self._thread.start()

    # -- vom Fahrtprozess -----------------------------------------------------

    def set_known(self, known):
        self.known = known

    def set_scene_map(self, scene_map, remember=True):
        write_json_atomic(self.folder / SCENE_MAP_FILE, scene_map)
        if remember:
            try:
                write_json_atomic(SCENE_MAP_CACHE, dict(scene_map, gespeichert=time.strftime(
                    "%Y-%m-%d %H:%M:%S")))
            except OSError:
                pass

    def start_episode(self, episode, phase="Policy"):
        with self._lock:
            self.episode = int(episode)
            self._trail.clear()
            self._slot = {"phase": phase, "step": None}
        self._wake.set()

    def phase(self, text):
        """Nur Text (Lokalisierung, Experte, ...) -- ohne Takt."""
        with self._lock:
            slot = dict(self._slot or {})
            slot["phase"] = text
            slot.setdefault("step", None)
            self._slot = slot
        self._wake.set()

    def update(self, step, state, frames=None, executor=None, target=None):
        """Je Takt aus der Fahrtschleife: nur Kopien, keine Rechnung."""
        chunks = []
        if executor is not None and hasattr(executor, "active_chunks"):
            try:
                chunks = [(int(s), np.array(c, dtype=float)) for s, c in executor.active_chunks()]
            except Exception:
                chunks = []
        images = {}
        for name, frame in (frames or {}).items():
            if frame is not None and getattr(frame, "image", None) is not None:
                images[name] = frame.image
        slot = {
            "phase": "Policy",
            "step": int(step),
            "joints": np.array(state.joints, dtype=float),
            "tcp": np.array(state.tcp_quat, dtype=float),
            "chunks": chunks,
            "target": None if target is None else np.array(target, dtype=float),
            "images": images,
            "spread_rad": float(getattr(executor, "last_spread", 0.0) or 0.0),
            "t": time.time(),
        }
        with self._lock:
            self._trail.append((round(float(slot["tcp"][0]), 5), round(float(slot["tcp"][1]), 5)))
            self._slot = slot
        self._wake.set()

    def close(self):
        self._running = False
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # -- Thread ---------------------------------------------------------------

    def _loop(self):
        while self._running:
            self._wake.wait(timeout=0.5)
            self._wake.clear()
            try:
                self.flush()
            except Exception as exc:   # Anzeige darf die Fahrt nie stoppen
                if len(self.errors) < 3:
                    self.errors.append("%s: %s" % (type(exc).__name__, exc))
                    print("Hinweis Live-Ansicht: %s" % self.errors[-1])
            time.sleep(0.02)

    def flush(self, force=False):
        """Rechnet und schreibt, wenn faellig (``force``: sofort)."""
        now = time.monotonic()
        with self._lock:
            slot = self._slot
            trail = list(self._trail)
        if slot is None:
            return
        if force or now - self._last_state >= self.state_period:
            self._last_state = now
            write_json_atomic(self.folder / STATE_FILE, self.build_state(slot, trail))
        if slot.get("images") and (force or now - self._last_image >= self.image_period):
            self._last_image = now
            self._write_images(slot["images"])

    def build_state(self, slot, trail=()):
        known = self.known
        plane = None if known is None else known.table
        out = {"t": slot.get("t", time.time()), "episode": self.episode,
               "phase": slot.get("phase"), "step": slot.get("step"), "trail": list(trail),
               "fk": self.fk is not None}
        if known is not None:
            out["pick"] = pose_info(known.pick, plane)
            out["region"] = [[float(p[0]), float(p[1])] for p in (known.region or [])]
            out["gap_mm"] = 1e3 * getattr(known, "gap_m", config.PROBE_GAP_M)
        if slot.get("tcp") is None:
            return out
        out["tcp"] = pose_info(slot["tcp"], plane)
        out["spread_rad"] = slot.get("spread_rad", 0.0)
        if self.fk is None:
            return out
        if slot.get("target") is not None:
            out["target"] = pose_info(self.fk(slot["target"]), plane)
        plans = []
        for s, rest in slot.get("chunks") or []:
            info = plan_info(rest, self.fk, plane)
            if info is not None:
                info["from_step"] = s
                info["age"] = None if slot["step"] is None else int(slot["step"] - s)
                plans.append(info)
        out["chunks"] = plans
        mean = mean_actions([rest for _, rest in slot.get("chunks") or []])
        out["mean"] = plan_info(mean, self.fk, plane) if len(mean) else None
        pick_yaw = out.get("pick", {}).get("yaw")
        yaws = [p["grasp"]["yaw"] for p in plans]
        if yaws:
            ref = yaws[0] if pick_yaw is None else pick_yaw
            errs = [yaw_diff(y, ref) for y in yaws]
            out["grasp_yaw_spread_deg"] = float(max(errs) - min(errs))
        if pick_yaw is not None:
            out["tcp"]["yaw_err"] = yaw_diff(out["tcp"]["yaw"], pick_yaw)
            out["tcp"]["xy_mm"] = 1e3 * math.hypot(out["tcp"]["x"] - out["pick"]["x"],
                                                   out["tcp"]["y"] - out["pick"]["y"])
            for plan in plans + ([out["mean"]] if out.get("mean") else []):
                g = plan["grasp"]
                g["yaw_err"] = yaw_diff(g["yaw"], pick_yaw)
                g["xy_mm"] = 1e3 * math.hypot(g["x"] - out["pick"]["x"], g["y"] - out["pick"]["y"])
        return out

    def _write_images(self, images):
        import cv2

        sizes = {}
        for name, image in images.items():
            image = np.asarray(image)
            if image.ndim == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            h, w = image.shape[:2]
            sizes[name] = [int(w), int(h)]
            scale = min(1.0, self.image_width / float(w))
            small = cv2.resize(image, (int(w * scale), int(h * scale)),
                               interpolation=cv2.INTER_AREA) if scale < 1.0 else image
            ok, buf = cv2.imencode(".jpg", cv2.cvtColor(small, cv2.COLOR_RGB2BGR),
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ok:
                write_bytes_atomic(self.folder / ("%s.jpg" % name), buf.tobytes())
        write_json_atomic(self.folder / "images.json", sizes)
