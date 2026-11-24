"""Sind die Labels gemeinsamer Episoden in zwei Exporten gleich?

Aufruf: export_gleich.py <datensatz-neu> <datensatz-alt>
"""
import sys
import json
import glob
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")


def load(d):
    d = ROOT / d
    info = json.loads((d / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(d / "data" / "*" / "*.parquet")))])
    return info, df


def key(e):
    return (Path(e["source"]).as_posix(), e["source_dir"])


ia, da = load(sys.argv[1])
ib, db = load(sys.argv[2])
ma = {key(e): e["episode_index"] for e in ia["episodes"]}
mb = {key(e): e["episode_index"] for e in ib["episodes"]}
common = sorted(set(ma) & set(mb))
print("gemeinsam", len(common), "| nur alt", len(set(mb) - set(ma)), "| nur neu", len(set(ma) - set(mb)))
print("nur alt nach Quelle", dict(Counter(k[0] for k in set(mb) - set(ma))))
print("nur neu nach Quelle", dict(Counter(k[0] for k in set(ma) - set(mb))))
mx = {"action": 0.0, "observation.state": 0.0}
nlen = 0
for k in common[::5]:
    a = da[da.episode_index == ma[k]]
    b = db[db.episode_index == mb[k]]
    if len(a) != len(b):
        nlen += 1
        continue
    for c in mx:
        mx[c] = max(mx[c], float(np.abs(np.stack(a[c].values) - np.stack(b[c].values)).max()))
print("max Abweichung (jede 5. gemeinsame Episode)", mx, "| Laengen ungleich", nlen)
sa = json.loads((ROOT / sys.argv[1] / "meta" / "stats.json").read_text())
sb = json.loads((ROOT / sys.argv[2] / "meta" / "stats.json").read_text())
for c in ("action", "observation.state"):
    for s in ("min", "max", "mean", "std"):
        x, y = np.asarray(sa[c][s], float), np.asarray(sb[c][s], float)
        print("%-18s %-4s neu %s" % (c, s, np.round(x, 3)))
        print("%-18s %-4s alt %s" % ("", "", np.round(y, 3)))
