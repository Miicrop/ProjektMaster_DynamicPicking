"""Form der idealen Anflugbahn je Aufnahmetag.

Je Episode (ideale TCP-Bahn aux__pose_ideal, Start bis Greiftakt):
* seitliche Abweichung (xy) von der Geraden Start -> Greifpunkt, max (mm)
* hoechster Punkt (mm), Hoehe 10 Takte vor dem Griff (mm)
* Wegpunkte/Metadaten: Sequenz-Punkte, Hindernisse, Blend
Aufruf: bahnform.py <tag> ...
"""
import sys
import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")

print("| Tag | Ep. | seitl. Abw. max median | p90 | Scheitel z median | z 10 Takte vor Griff | Weglänge bis Griff median | Punkte der Sequenz |")
print("|---|---:|---:|---:|---:|---:|---:|---|")
for day in sys.argv[1:]:
    eps = sorted(glob.glob(str(ROOT / "data" / day / "ep_*")))
    lat, top, z10, length, seqs = [], [], [], [], {}
    for e in eps[::2]:
        z = np.load(Path(e) / "arrays.npz")
        m = json.loads((Path(e) / "meta.json").read_text(encoding="utf-8"))
        md = m.get("metadata", m)
        g = np.flatnonzero(z["action"][:, 6] > 0.5)
        if not len(g):
            continue
        g = int(g[0])
        p = z["aux__pose_ideal"][: g + 1, :3]
        a, b = p[0, :2], p[-1, :2]
        u = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        n = np.array([-u[1], u[0]])
        lat.append(1e3 * np.abs((p[:, :2] - a) @ n).max())
        top.append(1e3 * p[:, 2].max())
        z10.append(1e3 * p[max(0, g - 10), 2])
        length.append(1e3 * np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
        key = ",".join(sorted((md.get("points") or {}).keys()))
        seqs[key] = seqs.get(key, 0) + 1
    seq = "; ".join("%s (%d)" % (k[:90], v) for k, v in sorted(seqs.items(), key=lambda t: -t[1])[:2])
    print("| %s | %d | %.0f mm | %.0f mm | %.0f mm | %.0f mm | %.0f mm | %s |" % (
        day, len(lat), np.median(lat), np.percentile(lat, 90), np.median(top), np.median(z10),
        np.median(length), seq))
