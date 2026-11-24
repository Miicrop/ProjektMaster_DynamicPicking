"""Zieht die Policy den Griff zu einer gelernten Lage hin?

Fuer jede Fahrt: Greifpunkt beim Schliessen (xy) gegen Ziel der Testlage und
gegen die naechste Greifposition im Trainingsdatensatz (alle Tage bzw. nur
der Tag der Testlagen). "Sog" = Anteil der Fahrten, die naeher an einer
gelernten Lage als am Ziel greifen; "Zug" = Median der Fehlerkomponente in
Richtung dieser Lage (mm).

Aufruf: sog.py <label>=<rollout-ordner>=<datensatz>[=<datensatz-fuer-tageslagen>] ...
"""
import sys
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
TAG = "2026-11-11"

print("| Lauf | Fahrten | Fehler xy median | nächste gelernte Lage (alle) median | Sog alle | Zug alle | "
      "nächste Lage vom 11.11. median | Sog 11.11. | Zug 11.11. |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for arg in sys.argv[1:]:
    parts = arg.split("=")
    label, run_dir, ds = parts[:3]
    # optional 4. Feld: Datensatz, aus dem die Lagen des Tages kommen (Kontrolle:
    # Policy, die diese Lagen NIE gesehen hat)
    day_ds = ROOT / (parts[3] if len(parts) > 3 else ds)
    run_dir, ds = ROOT / run_dir, ROOT / ds
    info = json.loads((ds / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    train = np.array([e["grasp_tcp"][:2] for e in info["episodes"] if e.get("grasp_tcp")], float)
    day_info = json.loads((day_ds / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    day = np.array([e["grasp_tcp"][:2] for e in day_info["episodes"]
                    if e.get("grasp_tcp") and TAG in Path(e["source"]).as_posix()], float).reshape(-1, 2)
    runs = json.loads((run_dir / "auswertung.json").read_text(encoding="utf-8"))
    rows = {"err": [], "all": [], "day": []}
    for r in runs:
        if r.get("grasp_step") is None:
            continue
        z = np.load(run_dir / ("rollout_%03d.npz" % r["lauf"]))
        g = z["tcp"][int(r["grasp_step"]), :2]
        tgt = np.array([r["pick_x_mm"], r["pick_y_mm"]], float) / 1e3
        e = g - tgt
        rows["err"].append(np.linalg.norm(e))
        for name, pts in (("all", train), ("day", day)):
            if not len(pts):
                rows[name].append((np.nan, np.nan, np.nan))
                continue
            # naechste gelernte Lage, die nicht die Testlage selbst ist (> 15 mm entfernt)
            d = np.linalg.norm(pts - tgt, axis=1)
            d[d < 0.015] = np.inf
            n = pts[int(np.argmin(d))]
            u = (n - tgt) / np.linalg.norm(n - tgt)
            rows[name].append((np.linalg.norm(n - tgt), float(np.linalg.norm(g - n) < np.linalg.norm(e)),
                               float(e @ u)))
    err = 1e3 * np.median(rows["err"])
    out = [label, str(len(rows["err"])), "%.1f mm" % err]
    for name in ("all", "day"):
        a = np.array(rows[name], float)
        if np.all(np.isnan(a[:, 0])):
            out += ["–", "–", "–"]
            continue
        out += ["%.0f mm" % (1e3 * np.nanmedian(a[:, 0])), "%.0f %%" % (100 * np.nanmean(a[:, 1])),
                "%+.1f mm" % (1e3 * np.nanmedian(a[:, 2]))]
    print("| " + " | ".join(out) + " |")
