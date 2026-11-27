"""Schwanken der Policy vor dem Griff messen (Vortest Real-Time Chunking, 26.11.).

Je Fahrt (``rollout_*.npz`` in den genannten Ordnern, rekursiv) bezogen auf die
Hoehe am Ende der Policy-Phase (Griff, Endabstieg oder Stopp):

  weg_<band>   seitlich gefahrener Weg im Hoehenband (mm)
  takte_<band> Takte im Band
  sprung_max   groesste seitliche Aenderung innerhalb von 4 Takten auf den
               letzten 20 mm (mm) -- die Spruenge von 4-10 mm vom 26.11.
  spread_unten Median der Streuung der Chunks auf den letzten 20 mm (rad)

Die Einstellungen (replan, decay, no_ensemble, glaettung, endabstieg) kommen
aus der summary.json des Laufs. Ausgabe: Tabelle je Fahrt und Mittel je
Einstellung; ``--csv`` schreibt die Fahrten zusaetzlich als CSV.

Aufruf:
    python tools/schwanken.py checkpoints/G2b_580_dagger_nur_griff/policy/rollouts/2026-11-27_*
"""
import argparse
import csv
import glob
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

BANDS = ((60, 30), (30, 20), (20, 10), (10, -10))
JUMP_WINDOW = 4


def _settings(run):
    path = run / "summary.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    a = data.get("args") or {}
    return {"replan": data.get("replan_steps"), "decay": data.get("ensemble_decay"),
            "mitteln": not a.get("no_ensemble"), "glaettung": a.get("glaettung"),
            "endabstieg": a.get("endabstieg", "aus"), "episoden": data.get("episodes") or []}


def measure(npz, policy_steps=None):
    d = np.load(npz, allow_pickle=True)
    t = 1e3 * np.asarray(d["tcp"], dtype=float)[:, :3]
    g = np.flatnonzero(np.asarray(d["gripper_cmd"]) > 0.5)
    end = int(policy_steps) if policy_steps else (int(g[0]) if len(g) else len(t))
    end = max(2, min(end, len(t)))
    t = t[:end]
    ref = t[-1, 2]
    spread = np.asarray(d["ensemble_spread"], dtype=float)[:end]
    out = {"takte": end}
    for hi, lo in BANDS:
        idx = np.flatnonzero((t[:, 2] - ref < hi) & (t[:, 2] - ref >= lo))
        key = "%d_%d" % (hi, max(lo, 0))
        if len(idx) < 2:
            out["weg_" + key], out["takte_" + key] = None, 0
            continue
        idx = np.arange(idx[0], idx[-1] + 1)
        out["weg_" + key] = float(np.linalg.norm(np.diff(t[idx, :2], axis=0), axis=1).sum())
        out["takte_" + key] = len(idx)
    low = np.flatnonzero(t[:, 2] - ref < 20)
    if len(low) > JUMP_WINDOW:
        low = np.arange(low[0], end)
        xy = t[low, :2]
        out["sprung_max"] = float(max(np.linalg.norm(xy[i + JUMP_WINDOW] - xy[i])
                                      for i in range(len(xy) - JUMP_WINDOW)))
        out["spread_unten"] = float(np.median(spread[low]))
    else:
        out["sprung_max"], out["spread_unten"] = None, None
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ordner", nargs="+", help="Rollout-/Vergleichsordner (Glob erlaubt)")
    parser.add_argument("--csv", default=None, help="Fahrten zusaetzlich als CSV")
    args = parser.parse_args(argv)
    runs = sorted({Path(p) for pat in args.ordner for p in glob.glob(pat) if Path(p).is_dir()})
    rows = []
    for run in runs:
        for npz in sorted(run.rglob("rollout_*.npz")):
            cfg = _settings(npz.parent)
            i = int(npz.stem.split("_")[1])
            eps = cfg.pop("episoden", [])
            ep = eps[i] if i < len(eps) else {}
            pol = ep.get("policy_steps")
            row = {"lauf": str(npz.parent), "fahrt": i, **cfg,
                   "stopp": str(ep.get("stop_reason") or "")[:30], **measure(npz, pol)}
            rows.append(row)
    if not rows:
        print("keine rollout_*.npz gefunden")
        return 1
    cols = ["weg_60_30", "weg_30_20", "weg_20_10", "weg_10_0", "sprung_max", "spread_unten", "takte"]
    print("Lauf / Fahrt | replan decay mitteln glaettung endabstieg | " + " | ".join(cols) + " | Stopp")
    f = lambda v: "-" if v is None else ("%.3f" % v if isinstance(v, float) and v < 0.5 else
                                         "%.1f" % v if isinstance(v, float) else str(v))
    for r in rows:
        print("%s/%d | %s %s %s %s %s | %s | %s" % (
            Path(r["lauf"]).name, r["fahrt"], r.get("replan"), r.get("decay"), r.get("mitteln"),
            r.get("glaettung"), r.get("endabstieg"), " | ".join(f(r.get(c)) for c in cols), r["stopp"]))
    print("\nMedian je Einstellung:")
    groups = {}
    for r in rows:
        key = (r.get("replan"), r.get("decay"), r.get("mitteln"), r.get("glaettung"), r.get("endabstieg"))
        groups.setdefault(key, []).append(r)
    for key, rs in groups.items():
        vals = []
        for c in cols:
            v = [r[c] for r in rs if r.get(c) is not None]
            vals.append(f(float(st.median(v))) if v else "-")
        print("replan %s decay %s mitteln %s glaettung %s endabstieg %s (n=%d) | %s"
              % (*key, len(rs), " | ".join(vals)))
    if args.csv:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, keys, delimiter=";")
            w.writeheader()
            w.writerows(rows)
        print("CSV:", args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
