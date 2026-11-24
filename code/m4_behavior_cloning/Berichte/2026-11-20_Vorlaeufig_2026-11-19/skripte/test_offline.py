"""Offline-Test eines oder mehrerer Modelle auf Demos, die in keinem Training sind.

Jedes Modell bekommt Bild und Zustand der Demo (Historie 2 Takte wie im
Betrieb) und sagt alle 2 Takte einen Chunk (8 Takte) vorher. Verglichen wird
mit den aufgezeichneten Aktionen (ideale Gelenke t+1, ohne Rauschen):

  * Gelenkfehler: mittlerer |Fehler| ueber q1..q6 (rad)
  * TCP-Fehler: Abstand Werkzeugspitze (FK + Tool-Offset) Vorhersage gegen
    Label in mm -- gesamt und im Nahbereich (TCP < 60 mm ueber dem Griff,
    vor dem Schliessen)
  * Greifer: Anteil gleicher Zustaende (auf/zu)
  * Griffpunkt: Chunks, deren Fenster das Schliessen enthaelt -> TCP-Abstand
    am Schliesstakt (mm, xy und z getrennt)

Je Vorhersage ``--samples`` Ziehungen (Diffusion ist stochastisch), Fehler
gemittelt.

Aufruf (aus m4_behavior_cloning):
  python Berichte/2026-11-20_Vorlaeufig_2026-11-19/skripte/test_offline.py \
      --daten data/2026-11-19-2 --modelle neu=checkpoints/X/policy C2=checkpoints/C2_nur_griff_ohne_1111/policy \
      --out Berichte/2026-11-20_Vorlaeufig_2026-11-19/daten/test_offline.json
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
import _bootstrap  # noqa: F401,E402

from bc import config, geometry, replay  # noqa: E402
from bc.urdf import KinematicChain  # noqa: E402

REPLAN = 2
NAH_MM = 60.0


def tool_offset(chain, states):
    q, pose = states[0, :6], states[0, 6:13]
    T_r = np.eye(4)
    T_r[:3, :3] = geometry.quat_to_matrix(pose[3:7])
    T_r[:3, 3] = pose[:3]
    return np.linalg.inv(chain.fk(q)) @ T_r


def tcp_mm(chain, off, q):
    return (chain.fk(np.asarray(q, float)) @ off)[:3, 3] * 1000.0


def prepare(chain, root, idx):
    arr = replay.load_arrays(root, idx)
    st = np.asarray(arr["observation.state"], float)
    act = np.asarray(arr["action"], float)
    off = tool_offset(chain, st)
    lab_tcp = np.array([tcp_mm(chain, off, a[:6]) for a in act])
    g = act[:, 6] > config.GRIPPER_THRESHOLD
    c = np.flatnonzero(g[1:] & ~g[:-1])
    close = int(c[0]) + 1 if c.size else None
    grasp = lab_tcp[close] if close is not None else None
    # Nahbereich: vor dem Schliessen und TCP (Label) < NAH_MM ueber dem Griff
    nah = np.zeros(len(act), bool)
    if close is not None:
        nah[:close] = (lab_tcp[:close, 2] - grasp[2]) < NAH_MM
    return dict(index=idx, arr=arr, act=act, off=off, lab_tcp=lab_tcp, close=close, nah=nah)


def run_model(name, path, eps, samples):
    from bc.diffusion import DiffusionPolicyRunner

    chain = KinematicChain.from_urdf(config.URDF_PATH)
    runner = DiffusionPolicyRunner(path, device="auto", seed=0)
    cams = runner.cameras
    out = []
    for e in eps:
        arr, act, n = e["arr"], e["act"], len(e["act"])
        runner.reset()
        j_err, p_err, p_nah, g_ok, griff = [], [], [], [], []
        jb, pb, gb = [], [], []  # nur Labels bis Schliessen + 3 Takte (wie C2 trainiert)
        lim = (e["close"] + 3) if e["close"] is not None else n
        for t in range(n):
            runner.observe(replay.observation_at(arr, t, cams))
            if t % REPLAN:
                continue
            snap = runner.snapshot()
            chunks = [runner.predict_snapshot(snap) for _ in range(samples)]
            k = min(len(chunks[0]), n - t)
            lab = act[t:t + k]
            for ch in chunks:
                ch = ch[:k]
                je = np.abs(ch[:, :6] - lab[:, :6]).mean(axis=1)
                ge = (ch[:, 6] > config.GRIPPER_THRESHOLD) == (lab[:, 6] > config.GRIPPER_THRESHOLD)
                j_err.extend(je)
                g_ok.extend(ge)
                for i in range(k):
                    d = np.linalg.norm(tcp_mm(chain, e["off"], ch[i, :6]) - e["lab_tcp"][t + i])
                    p_err.append(d)
                    if t + i <= lim:
                        jb.append(je[i]); pb.append(d); gb.append(ge[i])
                    if e["nah"][t + i]:
                        p_nah.append(d)
                if e["close"] is not None and t <= e["close"] < t + k:
                    i = e["close"] - t
                    v = tcp_mm(chain, e["off"], ch[i, :6]) - e["lab_tcp"][e["close"]]
                    griff.append(dict(t=t, xy=float(np.hypot(v[0], v[1])), z=float(v[2]),
                                      d=float(np.linalg.norm(v))))
        r = dict(index=e["index"], takte=n, schliessen=e["close"],
                 gelenk_mae_rad=float(np.mean(j_err)), gelenk_p95_rad=float(np.percentile(j_err, 95)),
                 tcp_mm_median=float(np.median(p_err)), tcp_mm_p95=float(np.percentile(p_err, 95)),
                 nah_mm_median=float(np.median(p_nah)) if p_nah else None,
                 nah_mm_p95=float(np.percentile(p_nah, 95)) if p_nah else None,
                 greifer=float(np.mean(g_ok)), griff=griff,
                 _j=[float(x) for x in j_err], _p=[float(x) for x in p_err], _n=[float(x) for x in p_nah],
                 _g=[bool(x) for x in g_ok],
                 _jb=[float(x) for x in jb], _pb=[float(x) for x in pb], _gb=[bool(x) for x in gb])
        print("  %s ep %2d: Gelenk-MAE %.4f rad | TCP median %.1f mm (p95 %.1f) | nah %.1f mm (p95 %.1f) | "
              "Greifer %.1f %% | Griff xy %s mm"
              % (name, e["index"], r["gelenk_mae_rad"], r["tcp_mm_median"], r["tcp_mm_p95"],
                 r["nah_mm_median"] or np.nan, r["nah_mm_p95"] or np.nan, 100 * r["greifer"],
                 "%.1f" % np.median([g["xy"] for g in griff]) if griff else "-"))
        out.append(r)
    del runner
    import torch
    torch.cuda.empty_cache()
    return out


def gesamt(rows):
    J = np.concatenate([r["_j"] for r in rows])
    P = np.concatenate([r["_p"] for r in rows])
    N = np.concatenate([r["_n"] for r in rows])
    G = np.concatenate([r["_g"] for r in rows])
    gr = [g for r in rows for g in r["griff"]]
    JB = np.concatenate([r["_jb"] for r in rows])
    PB = np.concatenate([r["_pb"] for r in rows])
    GB = np.concatenate([r["_gb"] for r in rows])
    return dict(gelenk_mae_rad=float(J.mean()), gelenk_p95_rad=float(np.percentile(J, 95)),
                tcp_mm_median=float(np.median(P)), tcp_mm_p95=float(np.percentile(P, 95)),
                nah_mm_median=float(np.median(N)), nah_mm_p95=float(np.percentile(N, 95)),
                greifer=float(G.mean()),
                bis_griff=dict(gelenk_mae_rad=float(JB.mean()), gelenk_p95_rad=float(np.percentile(JB, 95)),
                               tcp_mm_median=float(np.median(PB)), tcp_mm_p95=float(np.percentile(PB, 95)),
                               greifer=float(GB.mean())),
                griff_xy_mm_median=float(np.median([g["xy"] for g in gr])) if gr else None,
                griff_xy_mm_p90=float(np.percentile([g["xy"] for g in gr], 90)) if gr else None,
                griff_z_mm_median=float(np.median([g["z"] for g in gr])) if gr else None,
                griff_n=len(gr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daten", required=True)
    ap.add_argument("--modelle", nargs="+", required=True, help="NAME=policy-Ordner")
    ap.add_argument("--samples", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    chain = KinematicChain.from_urdf(config.URDF_PATH)
    eps = [prepare(chain, args.daten, i) for i in replay.usable_episodes(args.daten)]
    print("%d Episoden, %d Takte, Schliessen: %s" % (len(eps), sum(len(e["act"]) for e in eps),
                                                     [e["close"] for e in eps]))
    result = {"daten": args.daten, "samples": args.samples, "replan": REPLAN, "nah_mm": NAH_MM, "modelle": {}}
    for spec in args.modelle:
        name, path = spec.split("=", 1)
        print("Modell %s: %s" % (name, path))
        rows = run_model(name, path, eps, args.samples)
        g = gesamt(rows)
        print("  %s GESAMT: %s" % (name, json.dumps(g)))
        result["modelle"][name] = dict(policy=path, gesamt=g,
                                       episoden=[{k: v for k, v in r.items() if not k.startswith("_")}
                                                 for r in rows])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("->", args.out)


if __name__ == "__main__":
    main()
