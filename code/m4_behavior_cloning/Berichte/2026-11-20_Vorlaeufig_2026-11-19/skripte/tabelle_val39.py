"""Vergleichstabelle (Markdown) fuer VM-Laeufe auf den 39 Val-Episoden, Spalten wie im Testprotokoll.

Aufruf (aus m4_behavior_cloning): tabelle_val39.py <name>=<rollout-ordner> [...] [--split]
--split: zusaetzlich je Lauf ohne / mit Drehversatz (meta.anflug_drehung_grad der Rohdaten).
"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import numpy as np

RAW = Path("data/2026-11-19")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
split = "--split" in sys.argv


def dreh(ep):
    m = json.loads((RAW / ("ep_%05d" % ep) / "meta.json").read_text(encoding="utf-8"))
    return m["metadata"].get("anflug_drehung_grad") is not None


def zeile(name, rows, sw):
    n = len(rows)
    A = lambda k: np.array([r[k] for r in rows if r.get(k) is not None], float)
    near, gx, mc, gy = A("nearest_mm"), A("grasp_xy_mm"), A("min_clear_mm"), np.abs(A("grasp_yaw_err_deg"))
    q = [sw[r["lauf"]]["amp_fahrt_mm"] for r in rows if r["lauf"] in sw]
    w = [sw[r["lauf"]]["welligkeit_mm"] for r in rows if r["lauf"] in sw]
    f = lambda x: ("%.1f" % x).replace(".", ",")
    print("| %s | %d | %s mm | %d %% | %.0f | %s | %s° / %.0f° | %d %% | %d %% | %d | %d | %d %% | %s | %s |" % (
        name, n, f(np.median(near)), round(100 * (near <= 10).mean()), np.percentile(near, 90), f(np.median(gx)),
        f(np.median(gy)), np.percentile(gy, 90),
        round(100 * (mc < 0).mean()), round(100 * (mc < -10).mean()),
        sum("von der Ist-Stellung entfernt" in r["stop"] for r in rows),
        sum(r["stop"].startswith("abgelehnt") and "entfernt" not in r["stop"] for r in rows),
        round(100 * sum(r["stop"] == "endstellung" for r in rows) / n),
        f(np.median(q)) if q else "-", f(np.median(w)) if w else "-"))


print("| | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy | Gier median / p90 | Tisch < 0 | < −10 mm "
      "| Sprung > 0,35 | andere Abbrüche | Endstellung | Querabw. | Welligkeit |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for arg in args:
    name, d = arg.split("=", 1)
    d = Path(d)
    rows = json.loads((d / "auswertung.json").read_text(encoding="utf-8"))
    sw = {r["lauf"]: r for r in json.loads((d / "schwingen.json").read_text(encoding="utf-8"))} \
        if (d / "schwingen.json").exists() else {}
    zeile(name, rows, sw)
    if split:
        zeile(name + " ohne Drehversatz", [r for r in rows if not dreh(r["episode"])], sw)
        zeile(name + " mit Drehversatz", [r for r in rows if dreh(r["episode"])], sw)
