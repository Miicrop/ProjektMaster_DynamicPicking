"""Vergleichstabelle der Laeufe auf den Testlagen (T60 bzw. T20) als Markdown.

Aufruf: vergleich.py <name>=<rollout-ordner> [...]
Laeufe mit mehr Episoden (z. B. die Hauptreihe vom 13.11.) werden auf die
Episoden der Testlagen (testlagen.json, T60) gefiltert.
"""
import json
import sys
from pathlib import Path

import numpy as np

V = Path(__file__).resolve().parents[1]
spec = json.loads((V / "testlagen.json").read_text(encoding="utf-8"))
T60 = set(spec["T60"])

print("| Lauf | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy beim Schließen median | unter Tisch | tiefer als −10 mm | ServoGuard-Abbruch | Endstellung | Querabw. p95 median | Welligkeit median |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for arg in sys.argv[1:]:
    name, d = arg.split("=", 1)
    d = Path(d)
    rows = [r for r in json.loads((d / "auswertung.json").read_text(encoding="utf-8")) if r["episode"] in T60]
    sw = {r["lauf"]: r for r in json.loads((d / "schwingen.json").read_text(encoding="utf-8"))} \
        if (d / "schwingen.json").exists() else {}
    n = len(rows)
    A = lambda k: np.array([r[k] for r in rows if r.get(k) is not None], float)
    near, gx, mc = A("nearest_mm"), A("grasp_xy_mm"), A("min_clear_mm")
    q = [sw[r["lauf"]]["amp_fahrt_mm"] for r in rows if r["lauf"] in sw]
    w = [sw[r["lauf"]]["welligkeit_mm"] for r in rows if r["lauf"] in sw]
    print("| %s | %d | %.1f mm | %d %% | %.0f mm | %.1f mm | %d %% | %d %% | %d %% | %d %% | %s | %s |" % (
        name, n, np.median(near), round(100 * (near <= 10).mean()), np.percentile(near, 90), np.median(gx),
        round(100 * (mc < 0).mean()), round(100 * (mc < -10).mean()),
        round(100 * sum(r["stop"].startswith("abgelehnt") for r in rows) / n),
        round(100 * sum(r["stop"] == "endstellung" for r in rows) / n),
        "%.1f mm" % np.median(q) if q else "-", "%.1f mm" % np.median(w) if w else "-"))
