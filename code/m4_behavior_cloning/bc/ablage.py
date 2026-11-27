"""Ablegen an einer Station von M2 (apps/infer.py --ablage, Anwender 2026-11-27).

Die Ablageposen stehen in ``code/config/system.yaml`` unter ``robot.poses``
(von M2 mit ``robot_check teach`` geteacht): TCP [x, y, z] in mm, [rx, ry, rz]
in Grad, Konvention der Neura-Steuerung (wie M2 ``to_neura``). M2 oeffnet den
Greifer ``place_height_mm`` darueber und faehrt die letzten
``approach_height_mm`` linear an.

M4 greift auf einer anderen Hoehe als M2 (``grasp_height_mm``): das Teil
haengt dann um die Differenz anders unter dem TCP. Die Oeffnungshoehe wird
deshalb um ``M4-Greifhoehe - M2-Greifhoehe`` verschoben, damit das Teil an
derselben Stelle aufsetzt wie bei M2.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from bc import geometry

#: code/config/system.yaml (gemeinsame Konfiguration der Gruppe)
SYSTEM_YAML = Path(__file__).resolve().parents[2] / "config" / "system.yaml"
#: Namen der Stationen in robot.poses (inspection = Teststation von M3)
STATIONS = ("inspection", "bin_good", "bin_bad")
TEXT = {"inspection": "Teststation (M3)", "bin_good": "Ablage gut", "bin_bad": "Ablage schlecht"}


def load_station(name, m4_grasp_above_table_m, path=None):
    """Ablage ``name`` aus system.yaml -> dict mit ``pose`` (7, Oeffnungspose),
    ``pose_alt`` (um 180 Grad gedreht, gleiche Backenachse), ``above_m`` und Quelle."""
    import yaml

    path = Path(path) if path is not None else SYSTEM_YAML
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    rc = cfg["robot"]
    poses = rc.get("poses") or {}
    if name not in poses:
        raise KeyError("%s: robot.poses.%s fehlt (vorhanden: %s)" % (path, name, ", ".join(poses)))
    x, y, z, rx, ry, rz = (float(v) for v in poses[name])
    place_h = float(rc.get("place_height_mm", 0.0))
    m2_grasp = float(rc.get("grasp_height_mm", 0.0))
    shift = 1e3 * float(m4_grasp_above_table_m) - m2_grasp
    z_open = z + place_h + shift
    pose = geometry.pose_rpy_to_quat([1e-3 * x, 1e-3 * y, 1e-3 * z_open,
                                      math.radians(rx), math.radians(ry), math.radians(rz)])
    alt = pose.copy()
    rz180 = geometry.quat_from_axis_angle([0.0, 0.0, 1.0], math.pi)
    alt[3:] = geometry.quat_normalize(geometry.quat_multiply(rz180, pose[3:]))
    return {"name": name, "text": TEXT.get(name, name), "quelle": "%s robot.poses.%s" % (path.name, name),
            "pose": pose, "pose_alt": alt, "above_m": 1e-3 * float(rc.get("approach_height_mm", 80.0)),
            "m2_pose_mm_deg": [x, y, z, rx, ry, rz], "oeffnen_z_mm": z_open,
            "hoehenausgleich_mm": shift, "place_height_mm": place_h}


def describe(st):
    return ("%s: x %.1f y %.1f mm, oeffnen bei z %.1f mm (M2-Pose %.1f + place_height %.1f + "
            "Greifhoehe M4-M2 %+.1f), von %.0f mm darueber linear (%s)"
            % (st["text"], st["m2_pose_mm_deg"][0], st["m2_pose_mm_deg"][1], st["oeffnen_z_mm"],
               st["m2_pose_mm_deg"][2], st["place_height_mm"], st["hoehenausgleich_mm"],
               1e3 * st["above_m"], st["quelle"]))
