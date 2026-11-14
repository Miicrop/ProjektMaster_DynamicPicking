"""Gelenk 6 am Greifpunkt gegen Objektdrehung: eindeutig oder mehrdeutig?"""
import json
import os
import sys

import numpy as np

root = sys.argv[1]
exp = json.load(open(os.path.join(root, "datasets/2026-11-09/meta/bc_export.json"), encoding="utf-8"))
rows = []
for ep in exp["episodes"]:
    md = ep["metadata"]
    s = np.load(os.path.join(root, ep["source"], ep["source_dir"], "arrays.npz"))["observation__state"]
    c = np.flatnonzero(s[:, 13] > 0.5)
    if not len(c):
        continue
    j6 = float(s[c[0], 5])
    j1 = float(s[c[0], 0])
    rows.append((md.get("object_yaw_deg"), np.degrees(j6), np.degrees(j1), md["session"],
                 float(s[0, 5])))
yaw = np.array([r[0] if r[0] is not None else np.nan for r in rows], dtype=float)
j6 = np.array([r[1] for r in rows])
j1 = np.array([r[2] for r in rows])
print("Episoden:", len(rows), " object_yaw_deg vorhanden:", int(np.isfinite(yaw).sum()))
print("j6 am Greifpunkt: min %.0f  max %.0f  Grad" % (j6.min(), j6.max()))
print("Objekt-yaw: min %.0f  max %.0f  Grad" % (np.nanmin(yaw), np.nanmax(yaw)))
# j6 - j1 ist grob die Werkzeugdrehung um z bei senkrechtem Greifen
tool = j6 - j1
ok = np.isfinite(yaw)
res = (tool[ok] - yaw[ok] + 180) % 360 - 180
print("Werkzeugdrehung(j6-j1) - Objekt-yaw: median %.0f  p5 %.0f  p95 %.0f Grad"
      % (np.median(res), np.percentile(res, 5), np.percentile(res, 95)))
h, e = np.histogram(j6, bins=12)
print("Histogramm j6:", list(zip(np.round(e[:-1]).astype(int).tolist(), h.tolist())))
h, e = np.histogram(yaw[ok], bins=12)
print("Histogramm yaw:", list(zip(np.round(e[:-1]).astype(int).tolist(), h.tolist())))
