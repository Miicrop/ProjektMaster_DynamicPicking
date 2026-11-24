"""Sim-Versuch V7 "Korrektur-Halt": Anflug mit grossem Versatz, Abbremsen in Haltehoehe,
seitlich (und in der Gier) korrigieren, dann senkrecht absenken -- als IDEALBAHN.

Auftrag 22.11. abends (Anwender-Freigabe): Die Sim-Policies, die nie schliessen, stehen
10-19 mm hoch und ~12 mm seitlich neben dem Objekt -- eine Lage ohne Trainingsbeispiel.
In einem Teil der Episoden (``share``) fuehrt die Bahn deshalb absichtlich dorthin und
zeigt, wie man da herauskommt:

    ANFLUG (unveraendert) -> PRE_PICK' (versetzt, ggf. gedreht)
    -> HALT' (versetzt, Haltehoehe ueber PICK, Endanflug-Tempo)
    -> HALT (ueber PICK, Haltehoehe, Gier wie PICK, Endanflug-Tempo)
    -> PICK (senkrecht, wie immer)

Die L-Bahn ist die Idealbahn dieser Episode. Damit folgen Label (action = ideale
Gelenkbahn bei t+1, bc/recorder.py), aux.pose_ideal und aux.joints_ideal der
Korrektur -- nicht dem schraegen Weg zur Mitte. Das Rauschen kommt wie immer obendrauf
(bc/noise.sample_noisy_poses), der normale Anflug-Versatz entfaellt in diesen Episoden.

Kein echter Stillstand: HALT' und HALT werden ueberschliffen (bc/trajectory.py,
Ueberlagerung der Rampen). An HALT' liegt der verrundete Weg innerhalb der Ecke, also
nie unter der Haltehoehe; an HALT ist der Radius klein (``blend_halt_m``), damit der
Rest-Versatz beim Absenken unter dem Spiel der Backen bleibt.

Sicherheit (:func:`clearance`): Solange der Versatz der Backen gegen PICK (xy-Abstand +
Drehwinkel x Hebel) groesser als das Spiel ist, muss gelten
    TCP-Hoehe ueber PICK - Nachlauf >= Oberkante ueber PICK + Reserve.
Geprueft auf der Idealbahn und auf jeder verrauschten Bahn (Takt + 3 Zwischenschritte).
"""
from dataclasses import dataclass

import numpy as np

from . import config, geometry
from .trajectory import MOTION_LIN, Waypoint


@dataclass
class KorrekturHalt:
    """Einstellungen (Laengen in m, Winkel in Grad)."""

    share: float = 0.4
    offset_range_m: tuple = (0.010, 0.020)
    yaw_share: float = 0.5
    yaw_range_deg: tuple = config.APPROACH_YAW_RANGE_DEG
    hold_m: float = 0.014
    top_above_pick_m: float = 0.0084
    overshoot_m: float = config.APPROACH_TIP_OVERSHOOT_M
    reserve_m: float = 0.003
    play_m: float = 0.0025
    lever_m: float = config.APPROACH_TIP_LEVER_M
    blend_hold_in_m: float = 0.005
    blend_halt_m: float = 0.001

    def as_dict(self):
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


def sample(rng, cfg):
    """Korrektur dieser Episode: ``(dx, dy, dyaw_rad)`` oder None (Basis-Episode)."""
    if rng.random() >= cfg.share:
        return None
    size = rng.uniform(*cfg.offset_range_m)
    angle = rng.uniform(0.0, 2.0 * np.pi)
    yaw = 0.0
    if rng.random() < cfg.yaw_share:
        yaw = np.radians(rng.uniform(*cfg.yaw_range_deg)) * (1.0 if rng.random() < 0.5 else -1.0)
    return (size * np.cos(angle), size * np.sin(angle), yaw)


def _pick_index(waypoints):
    for k, wp in enumerate(waypoints):
        if k > 0 and wp.approach and wp.gripper_closed and not waypoints[k - 1].gripper_closed:
            return k
    raise ValueError("Korrektur-Halt: kein Greifpunkt (approach + Greifer zu) in der Ablaufdatei")


def _shifted(pose, dx, dy, yaw, z=None):
    p = np.array(pose, dtype=float)
    p[0] += dx
    p[1] += dy
    if z is not None:
        p[2] = z
    if yaw:
        dq = geometry.quat_from_axis_angle(np.array([0.0, 0.0, 1.0]), float(yaw))
        p[3:7] = geometry.quat_normalize(geometry.quat_multiply(dq, p[3:7]))
    return p


def waypoints_mit_halt(waypoints, korrektur, cfg):
    """Wegpunkte der Episode: PRE_PICK vor dem Greifpunkt versetzt, dazu HALT' und HALT."""
    dx, dy, yaw = korrektur
    k = _pick_index(waypoints)
    pre, pick = waypoints[k - 1], waypoints[k]
    if pre.motion != MOTION_LIN or pick.motion != MOTION_LIN:
        raise ValueError("Korrektur-Halt erwartet LIN zu PRE_PICK und PICK")
    z_hold = pick.pose_quat[2] + cfg.hold_m
    if pre.pose_quat[2] <= z_hold + 0.005:
        raise ValueError("Korrektur-Halt: PRE_PICK liegt nicht ueber der Haltehoehe")
    neu = list(waypoints[:k - 1])
    neu.append(Waypoint(_shifted(pre.pose_quat, dx, dy, yaw), gripper_closed=pre.gripper_closed,
                        name=(pre.name or "PRE_PICK") + "_VERSETZT", motion=MOTION_LIN,
                        blend_m=pre.blend_m))
    neu.append(Waypoint(_shifted(pick.pose_quat, dx, dy, yaw, z=z_hold), gripper_closed=pre.gripper_closed,
                        approach=True, name="HALT_VERSETZT", motion=MOTION_LIN,
                        blend_m=cfg.blend_hold_in_m))
    neu.append(Waypoint(_shifted(pick.pose_quat, 0.0, 0.0, 0.0, z=z_hold), gripper_closed=pre.gripper_closed,
                        approach=True, name="HALT", motion=MOTION_LIN, blend_m=cfg.blend_halt_m))
    neu.extend(waypoints[k:])
    return neu


def clearance(poses, pick_pose, grasp_index, cfg, substeps=4):
    """Kleinster Freiraum (m) Backenspitze -> Oberkante + Reserve, nach Nachlauf, solange die
    Backen mehr als ``play_m`` gegen PICK versetzt sind; ``inf`` = nie versetzt unterhalb.
    ``poses``: (N, 7) bis mindestens ``grasp_index`` (erster Takt mit Greifer zu)."""
    poses = np.asarray(poses, dtype=float)
    k = int(grasp_index)
    f = np.linspace(0.0, 1.0, int(substeps), endpoint=False)
    a, b = np.arange(0, k), np.arange(1, k + 1)
    p = (poses[a, None, :] * (1 - f)[None, :, None] + poses[b, None, :] * f[None, :, None]).reshape(-1, 7)
    lat = np.linalg.norm(p[:, :2] - np.asarray(pick_pose[:2])[None, :], axis=1)
    q = p[:, 3:7] / np.linalg.norm(p[:, 3:7], axis=1, keepdims=True)
    q0 = np.asarray(pick_pose[3:7], dtype=float)
    q0 = q0 / np.linalg.norm(q0)
    rot = 2.0 * np.arccos(np.clip(np.abs(q @ q0), 0.0, 1.0))
    on = lat + cfg.lever_m * rot > cfg.play_m
    if not on.any():
        return np.inf
    h = p[on, 2] - float(pick_pose[2])
    return float(np.min(h - cfg.overshoot_m - (cfg.top_above_pick_m + cfg.reserve_m)))


def grasp_index(ideal):
    g = np.asarray(ideal.gripper, dtype=float) > config.GRIPPER_THRESHOLD
    idx = np.flatnonzero(g[1:] & ~g[:-1])
    if not len(idx):
        raise ValueError("Korrektur-Halt: Bahn ohne Greifen")
    return int(idx[0]) + 1


def path_check(ideal, pick_pose, cfg):
    """Fuer bc/noise.generate_plan(path_check=...): Grund (str) bei Verletzung, sonst None."""
    k = grasp_index(ideal)

    def check(poses_noisy):
        frei = clearance(poses_noisy, pick_pose, k, cfg)
        if frei < 0:
            return "Backen %.1f mm zu tief, solange noch > %.1f mm versetzt" % (-1e3 * frei, 1e3 * cfg.play_m)
        return None

    return check
