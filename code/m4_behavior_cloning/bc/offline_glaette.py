"""Kennzahlen fuer den Offline-Test DDIM-Schritte / Glaettung (apps/ddim_offline.py).

Hardware- und torch-frei, damit die Rechnung testbar ist. Befund Anlage
2026-11-23 (Berichte/Testprotokoll.md, "Woher der Ruck kommt"): Die Labels
sind glatt, aber schon ein einzelner Chunk der Policy zittert, und
aufeinanderfolgende Chunks liegen fuer denselben Takt mm auseinander. Der Arm
schwingt darauf seitlich ueber. Diese Funktionen messen genau das:

* ``Ruck``         = Norm der 2. Differenz der TCP-Position je Takt (mm/Takt^2);
                     0 = gleichfoermige Bewegung, Planer-Labels ~0,0 mm.
* ``Chunk-Ruck``   = Ruck innerhalb eines Chunks (seine Schritte untereinander).
* ``Chunk-Sprung`` = Abstand zweier aufeinanderfolgender Chunks fuer denselben Takt.
* ``Befehls-Ruck`` = Ruck der gemittelten Actions (das, was an den Arm ginge),
                     ohne und mit Tiefpass (bc/servo.lowpass_series).
* ``Verzug``       = mittlerer Abstand Befehl zu aufgezeichneter Action (mm) --
                     waechst mit der Glaettung, ist ihr Preis.

"Nah" = TCP der Aufnahme weniger als ``near_mm`` ueber dem Greifpunkt (TCP im
Takt des ersten Schliessens), vor dem Schliessen -- dort pendelte die Policy.
"""

from pathlib import Path

import numpy as np

from . import config
from .servo import lowpass_series

#: URDF der lokalen FK (wie bc/adapters/neura.py)
URDF_PATH = Path(__file__).resolve().parent / "data" / "lara5_candidate.urdf"
#: Werkzeugversatz Flansch -> TCP, falls die Aufnahme keinen nennt (ZimmerLWR50)
DEFAULT_TOOL_OFFSET_M = (0.0, 0.0, 0.1975)


class ToolFK(object):
    """TCP-Position aus Gelenkwinkeln: URDF-Kette + Werkzeugversatz."""

    def __init__(self, tool_offset_m=DEFAULT_TOOL_OFFSET_M, urdf=URDF_PATH):
        from .urdf import KinematicChain

        self.chain = KinematicChain.from_urdf(str(urdf))
        self.offset = np.asarray(tool_offset_m, dtype=float).reshape(3)

    def __call__(self, joints):
        joints = np.asarray(joints, dtype=float)
        if joints.ndim == 1:
            T = self.chain.fk(joints[:6])
            return T[:3, 3] + T[:3, :3] @ self.offset
        return np.array([self(q) for q in joints])


def tool_offset_from_meta(meta):
    """Werkzeugversatz aus meta.json einer Aufnahme (local_fk_check), sonst None."""
    check = (meta.get("metadata") or meta).get("local_fk_check") or {}
    offset = check.get("tool_offset_m")
    return None if offset is None else [float(v) for v in offset]


def jerk_mm(positions_m):
    """Norm der 2. Differenz je Takt (mm/Takt^2), Laenge N-2."""
    p = np.asarray(positions_m, dtype=float)
    if len(p) < 3:
        return np.zeros(0)
    return np.linalg.norm(np.diff(p, 2, axis=0), axis=1) * 1e3


def near_mask(tcp_m, gripper, near_mm=60.0):
    """Takte, in denen der TCP < ``near_mm`` ueber dem Greifpunkt steht, vor dem Schliessen."""
    tcp_m = np.asarray(tcp_m, dtype=float)
    g = np.asarray(gripper, dtype=float) > config.GRIPPER_THRESHOLD
    closed = np.flatnonzero(g)
    if not len(closed):
        return np.zeros(len(tcp_m), dtype=bool)
    grasp = int(closed[0])
    height = (tcp_m[:, 2] - tcp_m[grasp, 2]) * 1e3
    mask = height < near_mm
    mask[grasp:] = False
    return mask


def chunk_metrics(history, fk, near):
    """Ruck innerhalb der Chunks und Sprung zwischen aufeinanderfolgenden Chunks.

    ``history``: Liste (Takt der Beobachtung, Chunk (K, 7)) wie
    bc/policy.ChunkEnsembler.history. ``near``: bool je Takt; ein Chunk zaehlt,
    wenn sein Beobachtungstakt "nah" ist.
    """
    near = np.asarray(near, dtype=bool)
    inside, gaps = [], []
    prev = None
    for step, chunk in history:
        chunk = np.asarray(chunk, dtype=float)
        is_near = 0 <= step < len(near) and near[step]
        tcp = fk(chunk[:, :6])
        if is_near:
            inside.extend(jerk_mm(tcp))
        if prev is not None and is_near:
            p_step, p_tcp = prev
            for k in range(len(tcp)):
                t = step + k
                j = t - p_step
                if 0 <= j < len(p_tcp):
                    gaps.append(np.linalg.norm(tcp[k] - p_tcp[j]) * 1e3)
                    break      # erster gemeinsamer Takt reicht
        prev = (step, tcp)
    return np.asarray(inside, dtype=float), np.asarray(gaps, dtype=float)


def command_metrics(commands, recorded, fk, near, alphas=(1.0,)):
    """Befehls-Ruck und Abstand zur Aufnahme je Glaettung ``alpha``.

    Rueckgabe {alpha: {"ruck": array (nah), "abstand_mm": array (nah)}}.
    ``abstand_mm`` = |FK(Befehl) - FK(aufgezeichnete Action)| -- enthaelt den
    Fehler der Policy UND den Verzug des Tiefpasses.
    """
    commands = np.asarray(commands, dtype=float)[:, :6]
    rec_tcp = fk(np.asarray(recorded, dtype=float)[:, :6])
    near = np.asarray(near, dtype=bool)
    out = {}
    for alpha in alphas:
        cmd = lowpass_series(commands, alpha) if alpha < 1.0 else commands
        tcp = fk(cmd)
        jerk = jerk_mm(tcp)
        out[float(alpha)] = {
            "ruck": jerk[near[1:-1]] if len(jerk) else jerk,
            "abstand_mm": np.linalg.norm(tcp - rec_tcp, axis=1)[near] * 1e3,
        }
    return out


def stats(values):
    """median / p95 / max als dict (NaN bei leerer Menge)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return {"median": float("nan"), "p95": float("nan"), "max": float("nan"), "n": 0}
    return {"median": float(np.median(v)), "p95": float(np.percentile(v, 95)),
            "max": float(v.max()), "n": int(len(v))}
