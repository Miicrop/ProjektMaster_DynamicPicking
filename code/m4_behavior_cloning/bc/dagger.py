"""DAgger-Episoden aus Policy-Test + Experte (Anwender 2026-11-16).

Ablauf an der Anlage (apps/infer.py ``--lage-bekannt --probegriff objekt
--dagger <ordner>``): Die Policy faehrt mit bekannter Lage (PICK aus der
Steuerung oder aus M1, bc/lokalisierung.py) und haelt 3 mm ueber dem Objekt.
Der Experte (Planer) korrigiert, greift, legt neu ab. Beide Teile werden
hier Takt fuer Takt MIT Bildern mitgeschrieben und als normale Episode im
Aufnahmeformat abgelegt (bc/dataset.DatasetWriter) -- Export und
tools/export_variante.py nehmen sie wie jede Aufnahme.

Labels (``action``) -- die DAgger-Idee: Zustaende, in die die POLICY faehrt,
bekommen die Aktion des EXPERTEN.

* Policy-Teil: je Takt der naechstgelegene Punkt der Idealbahn (monoton,
  kein Zurueckspringen) und davon der naechste Takt -- "zurueck auf die Bahn,
  dann weiter auf ihr", wie die Rauschaufnahmen (Zustand verrauscht, Label
  ideal). Damit es kein Sprung wird, ist der Schritt je Gelenk auf den
  Schritt der Idealbahn plus ``config.DAGGER_EXTRA_STEP_RAD`` begrenzt.
  Gesendet hat die Policy etwas anderes -- das steht in
  ``aux.joints_command``.
* Experten-Teil: das, was der Planer im naechsten Takt anfaehrt (wie in der
  Aufnahme), bis ``config.DAGGER_TAIL_STEPS`` nach dem Schliessen.

``aux.pose_noisy`` ist hier die GEMESSENE TCP-Pose (die gesendete der Policy
waere ein FK-Aufruf je Takt) -- sie dient nur der Huelle der TCP-Positionen.
"""

import json
from datetime import datetime

import numpy as np

from . import config, dataset

POLICY, EXPERT = "policy", "experte"


class Mitschrieb(object):
    """Takte einer Fahrt: Zustand, Bilder, gesendetes Ziel, Greifer, Phase."""

    def __init__(self, cameras):
        self.cameras = list(cameras)
        self.reset()

    def reset(self):
        self.state, self.sent, self.gripper, self.phase = [], [], [], []
        self.policy_action = []
        self.images = {c: [] for c in self.cameras}

    def __len__(self):
        return len(self.state)

    def add(self, obs, sent_joints, gripper, phase, policy_action=None):
        """Ein Takt: ``obs`` wie build_observation (Zustand + Bilder in
        Schema-Groesse), ``sent_joints`` das in diesem Takt gesendete Ziel."""
        self.state.append(np.asarray(obs["observation.state"], dtype=np.float32))
        for c in self.cameras:
            self.images[c].append(np.asarray(obs["observation.images.%s" % c], dtype=np.uint8))
        self.sent.append(np.asarray(sent_joints, dtype=float)[:6])
        self.gripper.append(float(gripper))
        self.phase.append(phase)
        self.policy_action.append(None if policy_action is None
                                  else np.asarray(policy_action, dtype=float))

    def count(self, phase):
        return sum(1 for p in self.phase if p == phase)


def ideal_joints(robot, ideal, seed_joints):
    """Gelenkbahn der Idealbahn (IK der Steuerung, wie die Aufnahme)."""
    from .kinematics import Kinematics

    kin = Kinematics(robot)
    return np.asarray(kin.solve_path(ideal.poses_quat, np.asarray(seed_joints, dtype=float),
                                     fixed_joints=ideal.joints), dtype=float)


def relabel(joints, tcp, ideal_q, ideal_poses, ideal_gripper,
            extra_step=config.DAGGER_EXTRA_STEP_RAD):
    """Expertenlabels fuer Zustaende der Policy.

    ``joints`` (N, 6) und ``tcp`` (N, 3) gemessen, ``ideal_q`` (M, 6),
    ``ideal_poses`` (M, 7), ``ideal_gripper`` (M,). Rueckgabe dict mit
    ``action`` (N, 7), ``index`` (N,) Bahnindex des Labels, ``offset_m`` (N,)
    Abstand des Zustands zur Bahn.
    """
    joints = np.asarray(joints, dtype=float)
    tcp = np.asarray(tcp, dtype=float)[:, :3]
    ideal_q = np.asarray(ideal_q, dtype=float)
    path = np.asarray(ideal_poses, dtype=float)[:, :3]
    m = len(ideal_q)
    out_q, out_g, index, offset = [], [], [], []
    prev = 0
    for q, p in zip(joints, tcp):
        dist = np.linalg.norm(path - p, axis=1)
        j = max(prev, int(np.argmin(dist)))
        prev = j
        k = min(j + 1, m - 1)
        step = np.abs(ideal_q[k] - ideal_q[j]) + float(extra_step)
        out_q.append(q + np.clip(ideal_q[k] - q, -step, step))
        out_g.append(float(ideal_gripper[k]))
        index.append(k)
        offset.append(float(dist[j]))
    return {"action": np.column_stack([np.asarray(out_q), np.asarray(out_g)]).astype(np.float32),
            "index": np.asarray(index, dtype=int), "offset_m": np.asarray(offset)}


def expert_end(gripper, tail=config.DAGGER_TAIL_STEPS):
    """Anzahl Experten-Takte bis ``tail`` nach dem ersten Schliessen (alle, wenn keins)."""
    g = np.asarray(gripper, dtype=float) > config.GRIPPER_THRESHOLD
    closing = np.flatnonzero(g[1:] & ~g[:-1]) + 1 if len(g) > 1 else np.array([], int)
    if g.size and g[0]:
        closing = np.r_[0, closing]
    return len(g) if not closing.size else min(len(g), int(closing[0]) + int(tail) + 1)


def build_episode(rec, ideal, ideal_q, expert_ideal_poses=None, metadata=None, success=None):
    """Episode im Aufnahmeformat aus einem :class:`Mitschrieb`.

    ``ideal``/``ideal_q``: Idealbahn der bekannten Lage (Labels der Policy),
    ``expert_ideal_poses``: Idealposen des Experten je Takt (optional, fuer
    ``aux.pose_ideal``). Rueckgabe ``(Episode, info)``.
    """
    phase = np.asarray(rec.phase)
    state = np.asarray(rec.state, dtype=np.float32)
    sent = np.asarray(rec.sent, dtype=float)
    pol = np.flatnonzero(phase == POLICY)
    exp = np.flatnonzero(phase == EXPERT)
    if len(exp):
        exp = exp[:expert_end(np.asarray(rec.gripper)[exp])]
    keep = np.r_[pol, exp].astype(int)
    if not len(pol):
        raise ValueError("keine Policy-Takte mitgeschrieben")

    ideal_poses = np.asarray(ideal.poses_quat, dtype=float)
    lab = relabel(state[pol, :6], state[pol, 6:9], ideal_q, ideal_poses, ideal.gripper)
    action = np.zeros((len(keep), config.ACTION_DIM), dtype=np.float32)
    joints_ideal = np.zeros((len(keep), 6), dtype=np.float32)
    pose_ideal = np.zeros((len(keep), 7), dtype=np.float32)
    n_pol = len(pol)
    action[:n_pol] = lab["action"]
    joints_ideal[:n_pol] = lab["action"][:, :6]
    pose_ideal[:n_pol] = [dataset.canonical_pose(ideal_poses[k]) for k in lab["index"]]
    if len(exp):
        # Experte: das Ziel des naechsten Takts (wie die Aufnahme: Label = t+1)
        nxt = np.r_[exp[1:], exp[-1]]
        action[n_pol:, :6] = sent[nxt]
        action[n_pol:, 6] = np.asarray(rec.gripper)[nxt]
        joints_ideal[n_pol:] = sent[exp]
        if expert_ideal_poses is not None:
            poses = np.asarray(expert_ideal_poses, dtype=float)
            pose_ideal[n_pol:] = [dataset.canonical_pose(poses[min(i, len(poses) - 1)])
                                  for i in range(len(exp))]
        else:
            pose_ideal[n_pol:] = state[exp, 6:13]
    arrays = {
        "observation.state": state[keep],
        "action": action,
        "aux.joints_ideal": joints_ideal,
        "aux.joints_command": sent[keep].astype(np.float32),
        "aux.pose_ideal": pose_ideal,
        "aux.pose_noisy": state[keep, 6:13].astype(np.float32),
        "aux.sync_ok": np.ones((len(keep), 1), dtype=bool),
        "next.done": np.zeros((len(keep), 1), dtype=bool),
    }
    arrays["next.done"][-1, 0] = True
    for c in rec.cameras:
        arrays["observation.images.%s" % c] = np.stack([rec.images[c][i] for i in keep])
    off = lab["offset_m"]
    info = {
        "policy_steps": int(n_pol),
        "expert_steps": int(len(exp)),
        "label_offset_mm_median": float(1e3 * np.median(off)),
        "label_offset_mm_max": float(1e3 * off.max()),
        "label_index_last": int(lab["index"][-1]),
        "ideal_steps": int(len(ideal_q)),
    }
    meta = dict(metadata or {})
    meta.setdefault("mode", "dagger")
    meta["dagger"] = {**(meta.get("dagger") or {}), **info}
    # meta.json verlangt reine Python-Typen (numpy-Zahlen aus Lage/Korrektur)
    meta = json.loads(json.dumps(meta, default=_plain))
    episode = dataset.Episode(arrays=arrays, metadata=meta, success=success)
    return episode, info


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def recording_metadata(info, robot_info, camera_backends, camera_settings=None,
                       sequence_file=None, session=None, extra=None):
    """Metadaten wie die Aufnahme -- die Export-Pruefung (lerobot_io.CONSISTENCY_KEYS)
    vergleicht sie mit den Demos. Tempo/Ausfuehrung aus bc_policy.json ``recording``."""
    rec = dict(info.get("recording") or {})
    now = datetime.now()
    meta = {
        "robot": robot_info.get("robot", rec.get("robot")),
        "in_simulation": robot_info.get("in_simulation"),
        "override": robot_info.get("override", rec.get("override")),
        "servo_rate_hz": rec.get("servo_rate_hz"),
        "rate_hz": config.CONTROL_RATE_HZ,
        "cameras": dict(camera_backends),
        "planner": rec.get("planner"),
        "execution": rec.get("execution"),
        "gripper_mode": robot_info.get("gripper_mode", "hardware"),
        "sequence": "pick_to_station",
        "sequence_file": sequence_file,
        "recorded_at": now.isoformat(timespec="seconds"),
        "session": session or now.strftime("%Y-%m-%d"),
        "block": "DAgger",
        "object_source": "dagger",
    }
    if camera_settings:
        meta["camera_settings"] = camera_settings
    meta.update(extra or {})
    return meta
