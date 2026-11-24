"""Takt-Gewichte fuer apps/train.py --episoden-gewichte: Takte ausblenden, deren Action-Chunk ein
Gelenk-Label enthaelt, das mehr als GRENZE rad von der Ist-Stellung desselben Takts liegt (Weg 2).

Der Chunk eines Trainings-Takts t umfasst die Labels t-(n_obs-1) .. t-(n_obs-1)+horizon-1.
Gewicht 0 fuer jeden Takt, dessen Fenster einen solchen Label-Takt enthaelt; sonst 1.
Zaehlt zugleich, was --label-kappen GRENZE beim Export kappen wuerde (Weg 1).

Aufruf (aus m4_behavior_cloning):
  takt_gewichte_sprung.py --dataset datasets/2026-11-19_nur_griff --grenze 0.30 --out <json>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--dataset", required=True)
ap.add_argument("--grenze", type=float, default=0.30)
ap.add_argument("--horizon", type=int, default=16)
ap.add_argument("--n-obs", type=int, default=2)
ap.add_argument("--out")
a = ap.parse_args()

root = Path(a.dataset)
df = pd.concat([pd.read_parquet(p, columns=["episode_index", "frame_index", "observation.state", "action"])
                for p in sorted((root / "data").rglob("*.parquet"))])
df = df.sort_values(["episode_index", "frame_index"])
n_eps = int(df["episode_index"].max()) + 1
lo, hi = a.n_obs - 1, a.horizon - a.n_obs  # Fenster [t-lo, t+hi]
takt, eps_hit, frames_hit, frames_null, frames_all = {}, 0, np.zeros(6, int), 0, 0
for ep, g in df.groupby("episode_index"):
    q = np.stack(g["observation.state"].to_numpy())[:, :6]
    act = np.stack(g["action"].to_numpy())[:, :6]
    over = np.abs(act - q) > a.grenze
    frames_hit += over.sum(axis=0)
    bad = np.flatnonzero(over.any(axis=1))
    n = len(g)
    frames_all += n
    if not len(bad):
        continue
    eps_hit += 1
    w = np.ones(n)
    for j in bad:
        w[max(0, j - hi):min(n, j + lo + 1)] = 0.0
    frames_null += int((w == 0).sum())
    takt[str(int(ep))] = w.tolist()
print("Datensatz %s: %d Episoden, %d Takte, Grenze %.2f rad" % (root, n_eps, frames_all, a.grenze))
print("Label-Takte ueber der Grenze je Gelenk (= Weg 1 kappt): %s" % frames_hit.tolist())
print("Episoden betroffen: %d (%.0f %%)" % (eps_hit, 100 * eps_hit / n_eps))
print("Weg 2 blendet aus: %d Trainings-Takte (%.2f %%)" % (frames_null, 100 * frames_null / frames_all))
if a.out:
    Path(a.out).write_text(json.dumps({"modus": "takt", "regel": "Chunk mit Label > %.2f rad ausblenden" % a.grenze,
                                       "gewichte": [1.0] * n_eps, "takt_gewichte": takt}), encoding="utf-8")
    print("->", a.out)
