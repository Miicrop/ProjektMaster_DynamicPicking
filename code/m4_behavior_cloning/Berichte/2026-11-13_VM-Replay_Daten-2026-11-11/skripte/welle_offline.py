"""Ist die Welligkeit schon in der Policy selbst? Stufe 1 (offline, Bilder+Zustand der Aufnahme).

Vergleich der vorhergesagten Gelenk-Actions mit den Labels (ideale Sollwerte):
Welligkeit = p95 |x - gleitendes Mittel 1 s| je Gelenk, max ueber Gelenke, in Grad.
Zusaetzlich als TCP (FK der VM-Kette ohne Tool -- fuer Querabweichung reicht
die Flanschbahn, Versatz ist starr): Querabweichung der vorhergesagten Bahn zur Label-Bahn.
"""
import sys, os, glob, json
from pathlib import Path
import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa
from bc import config
from bc.urdf import KinematicChain
from bc.metrics import distance_to_path

chain = KinematicChain.from_urdf(config.URDF_PATH)
T = np.eye(4); T[2, 3] = 0.1975


def smooth(x, w=15):
    k = np.ones(w) / w
    return np.stack([np.convolve(np.pad(x[:, i], (w // 2, w // 2), mode="edge"), k, mode="valid")
                     for i in range(x.shape[1])], 1)


def tcp(q):
    return np.array([(chain.fk(j) @ T)[:3, 3] for j in q])


rows = []
for f in sorted(glob.glob(sys.argv[1] + "/ep_*.npz")):
    d = np.load(f)
    pred, rec = d["predicted"][:, :6], d["recorded"][:, :6]
    wp = np.degrees(np.percentile(np.abs(pred - smooth(pred)), 95, axis=0)).max()
    wr = np.degrees(np.percentile(np.abs(rec - smooth(rec)), 95, axis=0)).max()
    pp, pr = tcp(pred), tcp(rec)
    dev = distance_to_path(pp, pr)
    wtp = np.percentile(np.linalg.norm(pp - smooth(pp), axis=1), 95)
    wtr = np.percentile(np.linalg.norm(pr - smooth(pr), axis=1), 95)
    rows.append((os.path.basename(f), round(wp, 2), round(wr, 2), round(1e3 * np.percentile(dev, 95), 1),
                 round(1e3 * wtp, 1), round(1e3 * wtr, 1)))
for r in rows:
    print(r)
A = np.array([r[1:] for r in rows])
print("Median: Welligkeit Gelenke Policy %.2f / Label %.2f Grad; Abstand zur Label-Bahn p95 %.1f mm; "
      "Welligkeit TCP Policy %.1f / Label %.1f mm" % tuple(np.median(A, axis=0)))
