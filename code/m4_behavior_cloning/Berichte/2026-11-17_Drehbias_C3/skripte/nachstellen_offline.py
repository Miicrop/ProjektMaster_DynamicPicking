"""Anlagenfahrten vom 17.11. offline nachstellen: welche Drehung WILL die Policy?

Die DAgger-Episoden (data/2026-11-17_dagger) enthalten je Takt die Kamerabilder
und den Zustand der var_C2-Fahrten an der Anlage. Jedes Modell bekommt hier
genau diese Beobachtungen (Historie 2 Takte wie im Betrieb) und sagt alle
2 Takte einen Chunk vorher -- K-mal mit verschiedenen Seeds (Diffusion ist
stochastisch). Aus jedem Chunk:

  wunsch(t) = Gierwinkel(Chunk-Ziel Index 7) - Gierwinkel(Ist, Takt t)

also die Drehung, die die Policy in den naechsten ~8 Takten fahren will
(Grad, + = plus). Bezug "noetig" = M1-Drehung (gripper_yaw360) gegen Start.
Die Beobachtungen folgen der Bahn von var_C2; fuer andere Modelle ist das
nur bis zum Auseinanderlaufen ein echter Gegenversuch (Kennzahl "frueh":
Takte, in denen var_C2 noch weniger als 10 Grad gedreht hatte).

Zusaetzlich fuer var_C2 selbst: Vergleich mit den an der Anlage
protokollierten Vorhersagen (rollout_*.npz: pred_step, pred_chunk) --
prueft, ob der Nachbau dieselben Entscheidungen trifft.

Aufruf (aus m4_behavior_cloning):
  python Berichte/2026-11-17_Drehbias_C3/skripte/nachstellen_offline.py \
      --modelle C2=checkpoints/C2_nur_griff_ohne_1111/policy C3=checkpoints/C3_wie_C2_drehung_gewichtet/policy --samples 8 \
      --out Berichte/2026-11-17_Drehbias_C3/daten/offline.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps"))
import _bootstrap  # noqa: F401,E402

from bc import config, geometry, replay  # noqa: E402
from bc.urdf import KinematicChain  # noqa: E402
from analyse_drehung import diff, yaw360  # noqa: E402

DAGGER = "data/2026-11-17_dagger"
ROLLOUTS = Path("checkpoints/C2_nur_griff_ohne_1111/policy/rollouts")
REPLAN = 2
FRUEH_DEG = 10.0


def tool_offset(chain, states):
    """Flansch -> Tool aus aufgezeichneten Gelenken und TCP (wie stufe2_vm.py)."""
    q, pose = states[0, :6], states[0, 6:13]
    T_f = chain.fk(q)
    T_r = np.eye(4)
    T_r[:3, :3] = geometry.quat_to_matrix(pose[3:7])
    T_r[:3, 3] = pose[:3]
    return np.linalg.inv(T_f) @ T_r


def yaw_of_joints(chain, off, q):
    T = chain.fk(np.asarray(q, float)) @ off
    return float(np.degrees(np.arctan2(T[1, 0], T[0, 0])) % 360.0)


def demo_episodes(root, max_steps=None):
    """Demos (z. B. 11.11., in keinem Training): Bezug = Drehung Start -> Griff der Demo."""
    out = []
    for idx in replay.usable_episodes(root):
        with np.load(replay.episode_dir(root, idx) / "arrays.npz") as z:
            st = np.asarray(z["observation__state"], float)
        g = st[:, 13] > config.GRIPPER_THRESHOLD
        c = np.flatnonzero(g[1:] & ~g[:-1])
        if not c.size:
            continue
        at = int(c[0]) + 1
        m1 = yaw360(st[at, 6:13])
        n = at if max_steps is None else min(at, max_steps)
        out.append(dict(index=idx, meta=None, n_pol=n, m1=m1, stamp=None, rollout_ep=None))
    return out


def episodes():
    """DAgger-Episoden mit Bezug: (index, meta, Policy-Takte, noetig, Startgier, Fahrt-Datei)."""
    out = []
    for idx in replay.usable_episodes(DAGGER):
        meta = json.loads((replay.episode_dir(DAGGER, idx) / "meta.json").read_text(encoding="utf-8"))
        md = meta["metadata"]
        dg = md["dagger"]
        lok = dg.get("lokalisierung") or {}
        m1 = lok.get("gripper_yaw360_deg")
        n_pol = int(dg["policy_steps"])
        # zugehoerige Anlagenfahrt: gleicher Zeitstempel im repeat_group
        stamp = md["repeat_group"].split("/")[1].replace(":", "-").replace("T", "_")
        ep = int(md["repeat_group"].split("/")[2])
        out.append(dict(index=idx, meta=md, n_pol=n_pol, m1=m1, stamp=stamp, rollout_ep=ep))
    return out


def find_rollout(stamp, ep):
    """Anlagenfahrt zur Episode: Ordner, dessen Zeit <= stamp am naechsten liegt."""
    for p in reversed(sorted(ROLLOUTS.glob("2026-11-17_*"))):
        f = p / ("rollout_%03d.npz" % ep)
        if p.name <= stamp and f.exists():
            return f
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelle", nargs="+", required=True, help="NAME=policy-Ordner")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--daten", default=None,
                    help="statt der DAgger-Fahrten: Demo-Aufnahme (Bezug = Demo-Griff)")
    ap.add_argument("--nur-frueh", action="store_true",
                    help="nur vorhersagen, solange die Bahn < 10 Grad gedreht hat")
    args = ap.parse_args()
    global DAGGER
    if args.daten:
        DAGGER = args.daten

    from bc.diffusion import DiffusionPolicyRunner

    chain = KinematicChain.from_urdf(config.URDF_PATH)
    eps = demo_episodes(args.daten) if args.daten else episodes()
    data = {}
    for e in eps:
        arr = replay.load_arrays(DAGGER, e["index"])
        if args.daten:  # nur, was gebraucht wird (Speicher)
            arr = {k: v[:e["n_pol"]] for k, v in arr.items()
                   if k == "observation.state" or k.startswith("observation.images")}
        st = np.asarray(arr["observation.state"], float)
        e["off"] = tool_offset(chain, st)
        e["start"] = yaw360(st[0, 6:13])
        e["noetig"] = None if e["m1"] is None else diff(float(e["m1"]), e["start"])
        e["ist"] = [diff(yaw360(st[t, 6:13]), e["start"]) for t in range(e["n_pol"])]
        if args.nur_frueh:
            late = [t for t in range(e["n_pol"]) if abs(e["ist"][t]) >= FRUEH_DEG]
            if late:
                e["n_pol"] = late[0]
                e["ist"] = e["ist"][:late[0]]
        data[e["index"]] = {k: v[:e["n_pol"]] for k, v in arr.items()} if args.daten else arr
        del arr
        f = find_rollout(e["stamp"], e["rollout_ep"]) if e["stamp"] else None
        e["rollout"] = str(f) if f else None
    print("%d Episoden, noetig: %s" % (len(eps), [None if e["noetig"] is None else round(e["noetig"])
                                                 for e in eps]))

    result = {"replan": REPLAN, "samples": args.samples, "episoden": []}
    for e in eps:
        result["episoden"].append({k: e[k] for k in ("index", "n_pol", "m1", "start", "noetig", "ist",
                                                     "rollout", "stamp")})
        result["episoden"][-1]["modelle"] = {}

    for spec in args.modelle:
        name, path = spec.split("=", 1)
        print("Modell %s: %s" % (name, path))
        runner = DiffusionPolicyRunner(path, device="auto", seed=0)
        cams = runner.cameras
        for e, res in zip(eps, result["episoden"]):
            arr = data[e["index"]]
            runner.reset()
            steps, wunsch, wunsch_sd, chunk_end = [], [], [], []
            for t in range(e["n_pol"]):
                obs = replay.observation_at(arr, t, cams)
                runner.observe(obs)
                if t % REPLAN:
                    continue
                snap = runner.snapshot(obs)
                ws = []
                for k in range(args.samples):
                    chunk = runner.predict_snapshot(snap)
                    y_end = yaw_of_joints(chain, e["off"], chunk[min(7, len(chunk) - 1), :6])
                    ws.append(diff(y_end, e["start"]) - e["ist"][t])
                steps.append(t)
                wunsch.append(float(np.mean(ws)))
                wunsch_sd.append(float(np.std(ws)))
                chunk_end.append(float(np.mean(ws)) + e["ist"][t])
            res["modelle"][name] = dict(steps=steps, wunsch=wunsch, wunsch_sd=wunsch_sd, ziel=chunk_end)
            fr = [w for t, w in zip(steps, wunsch) if abs(e["ist"][t]) < FRUEH_DEG]
            if not steps:
                continue
            print("  ep %2d noetig %+5.0f | wunsch frueh %+5.1f (n=%d) | Ziel am Ende %+5.0f"
                  % (e["index"], e["noetig"] or 0, np.mean(fr) if fr else np.nan, len(fr), chunk_end[-1]))
        del runner
        import torch
        torch.cuda.empty_cache()

    # Anlagen-Vorhersagen von var_C2 (Treue des Nachbaus)
    for e, res in zip(eps, result["episoden"]):
        if not e["rollout"]:
            continue
        z = np.load(e["rollout"])
        if "pred_chunk" not in z.files:
            continue
        ps, pc = np.asarray(z["pred_step"], int), np.asarray(z["pred_chunk"], float)
        steps, wunsch = [], []
        for t, chunk in zip(ps, pc):
            if t >= e["n_pol"] or t < 0:
                continue
            y_end = yaw_of_joints(chain, e["off"], chunk[min(7, len(chunk) - 1), :6])
            steps.append(int(t))
            wunsch.append(diff(y_end, e["start"]) - e["ist"][t])
        res["anlage_C2"] = dict(steps=steps, wunsch=wunsch)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
