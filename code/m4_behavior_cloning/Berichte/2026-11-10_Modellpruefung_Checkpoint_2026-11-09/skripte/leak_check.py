"""Wie weit liegt jede Val-Objektlage von der naechsten Trainings-Lage entfernt?"""
import json
import math
import sys
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
exp = json.loads((root / "datasets/2026-11-09/meta/bc_export.json").read_text(encoding="utf-8"))
cfg = json.loads((root / "checkpoints/2026-11-09/train_config.json").read_text(encoding="utf-8"))
val = set(cfg["val_episodes"])
eps = exp["episodes"]


def lage(ep):
    md = ep["metadata"]
    p = md["object_pose"]["PICK"]
    q = np.array(p[3:7])
    return np.array(p[:3]), q, md


def qang(a, b):
    d = abs(float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b))))
    return math.degrees(2 * math.acos(min(1.0, d)))


tr = [lage(e) for i, e in enumerate(eps) if i not in val]
va = [(i, *lage(e)) for i, e in enumerate(eps) if i in val]
seen = set()
rows = []
for i, p, q, md in va:
    g = md["repeat_group"]
    if g in seen:
        continue
    seen.add(g)
    d = [(np.linalg.norm(p[:2] - tp[:2]) * 1000, qang(q, tq)) for tp, tq, _ in tr]
    dxy = min(x for x, _ in d)
    # naechste Lage unter Beruecksichtigung beider: xy < 10 mm UND Winkel < 10 Grad
    both = min((x for x, a in d if a < 10), default=float("nan"))
    rows.append((md["session"], md["block"], md.get("variant_index"), i, p[0], p[1], dxy, both))

print("Val-Gruppen:", len(rows))
print("%-11s %-5s %3s %4s %7s %7s %10s %14s" % ("Session", "Block", "Var", "Ep", "x", "y",
                                               "naechst_xy", "xy_bei_<10Grad"))
for r in rows:
    print("%-11s %-5s %3s %4d %7.3f %7.3f %8.1fmm %12.1fmm" % r)

allp = np.array([lage(e)[0] for e in eps])
print("\nArbeitsbereich PICK x: %.3f..%.3f  y: %.3f..%.3f  z: %.3f..%.3f" % (
    allp[:, 0].min(), allp[:, 0].max(), allp[:, 1].min(), allp[:, 1].max(),
    allp[:, 2].min(), allp[:, 2].max()))
