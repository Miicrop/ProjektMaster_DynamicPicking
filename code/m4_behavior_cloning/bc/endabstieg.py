"""Geplanter Endabstieg (apps/infer.py --endabstieg, Anwender 2026-11-26).

Die Policy ist bis etwa 10-15 mm ueber der Objektoberkante zuverlaessig, auf
den letzten mm darunter springt sie zwischen Loesungen (Auswertung 26.11.,
Abschnitt 11). Mit Endabstieg endet die Policy in dieser Hoehe (oder wenn sie
vorher schliesst), der Rest wird geplant:

* ``senkrecht``: von der Lage der Policy senkrecht auf die Greifhoehe, Lage
  und Drehung bestimmt allein die Policy ("blind").
* ``pick``: auf den PICK (Steuerung oder M1/M2). Nur wenn er zur Policy passt
  (Abstand <= ``max_xy``, Drehung <= ``max_grad``), sonst senkrecht -- ein
  falscher PICK soll nicht in einen Crash fuehren.

Danach schliesst der Greifer und der geplante Transport faehrt weiter.
"""
from __future__ import annotations

import math

import numpy as np

from bc import config, geometry

MODES = ("aus", "senkrecht", "pick")
#: Laenger als so viel darf der geplante Abstieg nicht werden (Policy schloss zu hoch).
MAX_DESCENT_M = 0.06


def tool_yaw_deg(quat):
    """Richtung der Werkzeug-x-Achse in der Tischebene (Grad, Basis-KS)."""
    x = geometry.quat_rotate(np.asarray(quat, dtype=float), [1.0, 0.0, 0.0])
    return math.degrees(math.atan2(x[1], x[0]))


def yaw_diff_sym(a_deg, b_deg):
    """a - b fuer einen Parallelgreifer (180 Grad symmetrisch), in [-90, 90)."""
    return (a_deg - b_deg + 90.0) % 180.0 - 90.0


def grasp_z(tcp_xy, ziel=None, plane=None, pick_height_m=None, fallback_z=None):
    """Greifhoehe (z des TCP) an ``tcp_xy`` und woher sie kommt.

    Reihenfolge: Tisch der Lage (Ablauf, live) + Hoehe des PICK darueber,
    sonst Tischebene des Modells + ``pick_height``, sonst tiefster Punkt der
    Demonstrationen.
    """
    x, y = float(tcp_xy[0]), float(tcp_xy[1])
    if ziel is not None:
        return float(ziel.table.height_at(x, y) + ziel.pick_above_table_m), "Tisch + PICK-Hoehe"
    if plane is not None:
        h = config.PICK_HEIGHT_DEFAULT_M if pick_height_m is None else float(pick_height_m)
        return float(plane.height_at(x, y) + h), "Tisch + %.1f mm" % (1e3 * h)
    if fallback_z is not None:
        return float(fallback_z), "tiefster Punkt der Demonstrationen"
    return None, "unbekannt"


def stop_height(z_grasp, abstand_m):
    """TCP-Hoehe, unter der die Policy endet: Oberkante + ``abstand_m``."""
    return float(z_grasp) + config.PROBE_OBJECT_TOP_ABOVE_PICK_M + float(abstand_m)


def target(mode, tcp_pose, z_grasp, ziel=None, max_xy_m=0.006, max_grad=5.0):
    """Zielpose des Abstiegs (7,) und Protokoll.

    ``tcp_pose``: Pose beim Ende der Policy (Frame der Steuerung, robot.fk).
    ``ziel``: bekannte Lage mit ``pick`` (bc/known_pose.KnownPose) oder None.
    """
    p0 = np.asarray(tcp_pose, dtype=float)
    out = p0.copy()
    out[2] = float(z_grasp)
    info = {"modus": mode, "start": [float(v) for v in p0[:3]], "greifhoehe_m": float(z_grasp),
            "abstieg_m": float(p0[2] - z_grasp), "quelle": "policy"}
    if mode == "pick":
        if ziel is None:
            info["grund"] = "kein PICK bekannt -- senkrecht"
        else:
            pick = np.asarray(ziel.pick, dtype=float)
            dxy = pick[:2] - p0[:2]
            dyaw = yaw_diff_sym(tool_yaw_deg(pick[3:]), tool_yaw_deg(p0[3:]))
            info.update({"pick_dx_mm": 1e3 * float(dxy[0]), "pick_dy_mm": 1e3 * float(dxy[1]),
                         "pick_xy_mm": 1e3 * float(np.linalg.norm(dxy)), "pick_dreh_grad": float(dyaw)})
            if np.linalg.norm(dxy) > max_xy_m or abs(dyaw) > max_grad:
                info["grund"] = ("PICK passt nicht zur Policy (%.1f mm, %.1f Grad > %.1f mm / %.1f "
                                 "Grad) -- senkrecht" % (info["pick_xy_mm"], dyaw, 1e3 * max_xy_m,
                                                         max_grad))
            else:
                out[:2] = pick[:2]
                out[2] = float(pick[2])
                rz = geometry.quat_from_axis_angle([0.0, 0.0, 1.0], math.radians(dyaw))
                out[3:] = geometry.quat_normalize(geometry.quat_multiply(rz, p0[3:]))
                info["quelle"] = "pick"
                info["greifhoehe_m"] = float(pick[2])
                info["abstieg_m"] = float(p0[2] - pick[2])
    info["ziel"] = [float(v) for v in out]
    return out, info


def describe(info):
    text = "Endabstieg %s: %.1f mm nach unten" % (info["quelle"], 1e3 * info["abstieg_m"])
    if info.get("pick_xy_mm") is not None:
        text += ", PICK %.1f mm / %+.1f Grad neben der Policy" % (info["pick_xy_mm"],
                                                                 info["pick_dreh_grad"])
    if info.get("grund"):
        text += " (%s)" % info["grund"]
    return text
