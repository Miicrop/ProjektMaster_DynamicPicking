"""PICK aus der Objekterkennung der Gruppe (M1/M2) -- Anbindung, kein fremder Code.

Idee Anwender 2026-11-16: Das Teil liegt irgendwo, M1 bestimmt Lage und
Orientierung aus dem Bild der Draufsichtkamera (= Szenenkamera von M4), die
Policy faehrt, und wenn sie danebenliegt, korrigiert der Planer auf genau
diese Pose (DAgger). Hier wird M1/M2 nur IMPORTIERT, nichts daran geaendert:

* M1: ``m1_vision_topdown.detector.TopDownPipeline`` -- Bild rein, Pose im
  Roboter-KS raus (``common.interfaces.ObjectPose``, mm/Grad), mit der
  Kalibrierung aus ``code/config/system.yaml``.
* M2: ``m2_robot_control.robot.as_target`` -- dieselbe Umrechnung
  Objektwinkel -> Greiferdrehung, mit der M2 selbst greift.

Abgleich mit den Aufnahmen (2026-11-16, Block B012 vom 02.11.): M1 fand das
Teil 0,3 mm neben dem geteachten PICK, die Greiferdrehung nach M2-Konvention
lag 0,3 Grad neben der geteachten -- M1/M2 und die M4-Demos passen zusammen.

Das Bild kommt aus der laufenden M4-Kamera (eine Kamera, ein Prozess). M4
belichtet anders als M1 (8 ms, Gain automatisch statt 15 ms, Gain 0); die
Schwellen von M1 sind relativ zur Platte, auf den M4-Vollbildern fand M1 das
Teil, sobald der Arm aus dem Bild war. Der Arm muss dafuer in einer
Fotostellung stehen (Default: Steuerungspunkt ``Home``, wie bei M2): in der
Startstellung der Policy verdeckt er einen Marker und oft das Teil.

Die endgueltige Einbindung (Orchestrator der Gruppe) kommt spaeter; dieses
Modul ist nur die Bruecke fuer Policy-Test und DAgger.
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config

#: ``code/`` -- dort liegen common, m1_vision_topdown, m2_robot_control
CODE_ROOT = Path(__file__).resolve().parents[2]


class LocalizationError(RuntimeError):
    """Keine verwertbare Lage (Marker fehlen, kein Teil, M1 nicht vorhanden)."""


@dataclass
class Localization:
    """Ergebnis einer Lokalisierung."""

    x_m: float
    y_m: float
    theta_deg: float            # Objektwinkel nach M1 (Roboter-KS)
    gripper_yaw_deg: float      # Greiferdrehung nach M2-Konvention (0..180)
    chamfer: bool               # Fase erkannt -> Winkel eindeutig
    size_mm: tuple = ()
    method: str = ""
    extra: dict = field(default_factory=dict)
    #: mit Fase: Greiferdrehung nach M2-Konvention 0..360 (sonst None)
    gripper_yaw360_deg: float = None

    def as_dict(self):
        return {"x_m": self.x_m, "y_m": self.y_m, "theta_deg": self.theta_deg,
                "gripper_yaw_deg": self.gripper_yaw_deg, "chamfer": self.chamfer,
                "gripper_yaw360_deg": self.gripper_yaw360_deg,
                "size_mm": list(self.size_mm), "method": self.method, **self.extra}

    def describe(self):
        return ("M1: x %.1f y %.1f mm, Objekt %.1f Grad%s, Greifer %.1f Grad, %s"
                % (1e3 * self.x_m, 1e3 * self.y_m, self.theta_deg,
                   "" if self.chamfer else " (ohne Fase, nur 0..180)", self.gripper_yaw_deg,
                   "x".join("%.0f" % v for v in self.size_mm) + " mm" if self.size_mm else ""))


def _import_group(code_root=None):
    """M1/M2 importierbar machen (hinten in sys.path -- M4-Module gewinnen)."""
    root = Path(code_root or CODE_ROOT)
    if not (root / "m1_vision_topdown" / "detector.py").is_file():
        raise LocalizationError("M1 nicht gefunden unter %s (m1_vision_topdown)" % root)
    if str(root) not in sys.path:
        sys.path.append(str(root))
    return root


class M1Localizer(object):
    """Bild (RGB wie die M4-Kameras) -> :class:`Localization`."""

    def __init__(self, code_root=None, config_path=None):
        root = _import_group(code_root)
        from common.config import load_config
        from m1_vision_topdown.detector import TopDownPipeline

        self.cfg = load_config(config_path) if config_path else load_config(
            root / "config" / "system.yaml")
        self.pipeline = TopDownPipeline(self.cfg)
        self.last_result = None

    def locate(self, image_rgb):
        import cv2
        from common.interfaces import ObjectPose, VisionError

        if image_rgb is None:
            raise LocalizationError("kein Bild der Szenenkamera")
        bgr = cv2.cvtColor(np.asarray(image_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        try:
            result = self.pipeline.process(bgr)
        except VisionError as exc:
            text = str(exc)
            hint = (" -- Arm im Bild? Fotostellung pruefen" if "markers not found" in text
                    else " -- liegt das Teil im Arbeitsbereich zwischen den Markern?"
                    if "No part" in text else "")
            raise LocalizationError("M1: %s%s" % (text, hint))
        self.last_result = result
        pose = result.pose
        obj = ObjectPose(pose.x_mm, pose.y_mm, pose.z_mm, pose.theta_deg, pose.confidence)
        yaw = gripper_yaw_deg(self.cfg, obj)
        yaw360 = gripper_yaw_deg(self.cfg, obj, full=True) if result.part.chamfer_found else None
        px = result.workspace.px_per_mm
        return Localization(
            x_m=pose.x_mm / 1000.0, y_m=pose.y_mm / 1000.0, theta_deg=float(pose.theta_deg),
            gripper_yaw_deg=yaw, chamfer=bool(result.part.chamfer_found),
            size_mm=(result.part.length_px / px, result.part.width_px / px),
            method=str(result.workspace.method), gripper_yaw360_deg=yaw360,
            extra={"x_ws_mm": float(result.x_ws_mm), "y_ws_mm": float(result.y_ws_mm)})


def gripper_yaw_deg(cfg, object_pose, full=False):
    """Greiferdrehung (Werkzeug-x-Achse, Grad 0..180) wie M2 greifen wuerde.

    ``m2_robot_control.robot.as_target`` setzt rx/ry der Home-Pose (Werkzeug
    nach unten) und rz = Home + Objektwinkel + Greiferversatz. Bei rx=180,
    ry=0 zeigt die Werkzeug-x-Achse in Richtung rz -- modulo 180 genau das,
    was bc/table.yaw_deg misst.
    """
    try:
        from m2_robot_control.robot import as_target
        target = as_target(cfg, object_pose)
        rz = float(target.rz_deg)
    except ImportError:   # M2 fehlt: dieselbe Formel aus der Konfiguration
        rc = cfg["robot"]
        rz = (float(rc["poses"]["home"][5]) + float(object_pose.theta_deg)
              + float(rc["gripper_angle_offset_deg"]))
    return rz % (360.0 if full else 180.0)


def pick_pose(loc, template_pick, plane, height_m=None):
    """PICK-Pose (7) an der lokalisierten Lage.

    Orientierung aus ``template_pick`` (Werkzeug senkrecht zum Tisch, wie
    geteacht), um die Tischnormale auf die Greiferdrehung gedreht; von den
    zwei gleichwertigen Drehungen (Parallelgreifer) die naeher am Template.
    Hoehe ueber dem Tisch wie beim Template (``height_m`` setzt sie fest).
    """
    from .auto_layout import rotated_about
    from .known_pose import flip_closer
    from .table import align_pose, clearance, yaw_deg

    template = np.asarray(template_pick, dtype=float)
    height = clearance(plane, template[:3]) if height_m is None else float(height_m)
    pose = template.copy()
    pose[0], pose[1] = loc.x_m, loc.y_m
    pose = align_pose(pose, plane, height)
    turn = math.radians((loc.gripper_yaw_deg - yaw_deg(pose, plane) + 90.0) % 180.0 - 90.0)
    pose = rotated_about(pose, plane.normal_at(pose[0], pose[1]), turn)
    target = chamfer_yaw_deg(loc)
    if target is None:
        pose, _ = flip_closer(pose, template, plane)
        return pose
    # Fase erkannt und Versatz abgeglichen: Richtung eindeutig, kein Umklappen
    from .live import yaw360
    turn = math.radians((target - yaw360(pose, plane) + 180.0) % 360.0 - 180.0)
    return rotated_about(pose, plane.normal_at(pose[0], pose[1]), turn)


def chamfer_yaw_deg(loc, offset_deg="config"):
    """Werkzeug-x-Richtung (0..360) aus der Fase, oder None (keine Fase /
    Versatz nicht abgeglichen, config.LOCALIZE_CHAMFER_OFFSET_DEG)."""
    offset = config.LOCALIZE_CHAMFER_OFFSET_DEG if offset_deg == "config" else offset_deg
    if loc.gripper_yaw360_deg is None or offset is None:
        return None
    return float((loc.gripper_yaw360_deg + float(offset)) % 360.0)


def compare(pose_a, pose_b, plane=None):
    """Abstand zweier Greifposen: dx, dy, xy (m) und Drehung (Grad, -90..90)."""
    from .table import yaw_deg

    a, b = np.asarray(pose_a, dtype=float), np.asarray(pose_b, dtype=float)
    d = a[:2] - b[:2]
    yaw = (yaw_deg(a, plane) - yaw_deg(b, plane) + 90.0) % 180.0 - 90.0
    return {"dx_m": float(d[0]), "dy_m": float(d[1]), "xy_m": float(np.hypot(*d)),
            "yaw_deg": float(yaw)}


def full_frame(capture, settle_s=None, clock=None):
    """Neuestes Vollbild (RGB) einer laufenden Kamera, nach kurzer Wartezeit."""
    import time

    wait = config.LOCALIZE_SETTLE_S if settle_s is None else settle_s
    (clock.sleep if clock is not None else time.sleep)(wait)
    frame = capture.latest()
    return None if frame is None else frame.image
