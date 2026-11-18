"""Vorlaeufiger Vergleich auf den Episoden, die C2 schon hat (gleiche Replay-Episoden)."""
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
RUNS = {
    "alt s0 (Wdh.)": "checkpoints/2026-11-09/policy/rollouts/2026-11-14_vm_T60_wiederholung",
    "alt s1": "checkpoints/kontrolle_2026-11-09_seed1/policy/rollouts/vm_T60",
    "A": "checkpoints/A_basis/policy/rollouts/vm_T60",
    "C": "checkpoints/C_nur_griff/policy/rollouts/vm_T60",
    "C2": "checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/vm_T60",
    "F": "checkpoints/F_licht_augment/policy/rollouts/vm_T60",
}
data = {k: {r["episode"]: r for r in json.loads((ROOT / v / "auswertung.json").read_text(encoding="utf-8"))}
        for k, v in RUNS.items()}
eps = sorted(data["C2"])
print("Episoden:", len(eps))
print("| Lauf | n | naechste Annaeherung median | <=10 mm | p90 | unter Tisch | Endstellung |")
for k, d in data.items():
    rows = [d[e] for e in eps if e in d]
    near = np.array([r["nearest_mm"] for r in rows if r["nearest_mm"] is not None], float)
    mc = np.array([r["min_clear_mm"] for r in rows], float)
    print("| %s | %d/%d | %.1f | %d %% | %.0f | %d %% | %d %% |" % (
        k, len(near), len(rows), np.median(near), round(100 * (near <= 10).mean()), np.percentile(near, 90),
        round(100 * (mc < 0).mean()), round(100 * np.mean([r["stop"] == "endstellung" for r in rows]))))


def per_block(d):
    b = {}
    for e in eps:
        if e in d:
            v = d[e]["nearest_mm"]
            if v is not None:
                b.setdefault(d[e]["block"], []).append(v)
    return {k: float(np.median(v)) for k, v in b.items()}


def sign(x, y, label):
    bx, by = per_block(x), per_block(y)
    ks = sorted(set(bx) & set(by))
    diff = np.array([bx[k] - by[k] for k in ks])
    worse, better = int((diff > 0).sum()), int((diff < 0).sum())
    n = worse + better
    p = min(1.0, 2 * sum(comb(n, i) for i in range(min(worse, better) + 1)) / 2 ** n) if n else 1.0
    print("%s: %d Lagen, schlechter %d / besser %d, Differenz median %+.1f mm, Vorzeichentest p=%.3f" % (
        label, len(ks), worse, better, np.median(diff), p))


old = {}
for e in eps:
    v = [data[k][e]["nearest_mm"] for k in ("alt s0 (Wdh.)", "alt s1") if e in data[k] and data[k][e]["nearest_mm"] is not None]
    if v:
        old[e] = dict(data["alt s1"][e], nearest_mm=float(np.mean(v)))
sign(data["C2"], old, "C2 gegen alt (Mittel s0/s1)")
sign(data["C2"], data["C"], "C2 gegen C")
sign(data["C2"], data["A"], "C2 gegen A")
sign(data["C"], old, "C gegen alt (gleiche Episoden)")
sign(data["F"], data["A"], "F gegen A")
sign(data["F"], old, "F gegen alt (Mittel s0/s1)")
sign(data["F"], data["C2"], "F gegen C2")
