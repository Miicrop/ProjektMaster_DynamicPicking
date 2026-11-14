"""Ist die Kamera am 11.11. anders als an den Trainingstagen?

Bild beim Start (Takt 0, Arm in derselben Startstellung) je Episode. Gegen ein
Bezugsbild (erste Episode 09.11.) per Merkmalsabgleich (ORB + RANSAC,
Aehnlichkeitstransformation) Verschiebung, Drehung und Massstab bestimmen --
fuer die Szenenkamera und die Handkamera, ueber den Tag verteilt.
Dazu ein Kontaktbogen (Bezug, 11.11., Differenz).

Aufruf: kameralage.py <ausgabe-png>
"""
import sys
import glob
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
DAYS = ["2026-11-02", "2026-11-03", "2026-11-09", "2026-11-11"]
orb = cv2.ORB_create(1500)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def first(ep, cam):
    z = np.load(Path(ep) / "arrays.npz", mmap_mode="r")
    return np.asarray(z["observation__images__" + cam][0])


def gray(img):
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return cv2.equalizeHist(g)  # Helligkeit der Tage angleichen


def pose(ref, img):
    k1, d1 = orb.detectAndCompute(gray(ref), None)
    k2, d2 = orb.detectAndCompute(gray(img), None)
    if d1 is None or d2 is None:
        return None
    m = bf.match(d1, d2)
    if len(m) < 12:
        return None
    a = np.float32([k1[x.queryIdx].pt for x in m])
    b = np.float32([k2[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None:
        return None
    s = float(np.hypot(M[0, 0], M[1, 0]))
    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    # Verschiebung des Bildmittelpunkts
    c = np.array([160.0, 120.0, 1.0])
    d = M @ c - c[:2]
    return d[0], d[1], rot, s, int(inl.sum())


eps = {d: sorted(glob.glob(str(ROOT / "data" / d / "ep_*"))) for d in DAYS}
ref_ep = eps["2026-11-09"][0]
refs = {c: first(ref_ep, c) for c in ("scene", "wrist")}
print("Bezug: %s (Takt 0)" % ref_ep)
print("| Tag | Kamera | Ep. | dx px | dy px | Drehung ° | Maßstab | Inlier |")
print("|---|---|---:|---:|---:|---:|---:|---:|")
sheet = {}
for d in DAYS:
    sel = eps[d][:: max(1, len(eps[d]) // 12)]
    for cam in ("scene", "wrist"):
        res = []
        for e in sel:
            r = pose(refs[cam], first(e, cam))
            if r:
                res.append(r)
        res = np.array(res)
        if len(res):
            print("| %s | %s | %d | %+.1f (%.1f…%.1f) | %+.1f (%.1f…%.1f) | %+.2f (%.2f…%.2f) | %.3f | %.0f |" % (
                d, cam, len(res), np.median(res[:, 0]), res[:, 0].min(), res[:, 0].max(),
                np.median(res[:, 1]), res[:, 1].min(), res[:, 1].max(),
                np.median(res[:, 2]), res[:, 2].min(), res[:, 2].max(), np.median(res[:, 3]), np.median(res[:, 4])))
    sheet[d] = {c: first(eps[d][len(eps[d]) // 2], c) for c in ("scene", "wrist")}

# Ende 11.11. (Test-Episoden) separat
tests = [e for e in eps["2026-11-11"]
         if "Test" in str(json.loads((Path(e) / "meta.json").read_text(encoding="utf-8"))["metadata"].get("block"))]
for cam in ("scene", "wrist"):
    res = np.array([r for r in (pose(refs[cam], first(e, cam)) for e in tests) if r])
    if len(res):
        print("| 2026-11-11 Test | %s | %d | %+.1f | %+.1f | %+.2f | %.3f | %.0f |" % (
            cam, len(res), np.median(res[:, 0]), np.median(res[:, 1]), np.median(res[:, 2]),
            np.median(res[:, 3]), np.median(res[:, 4])))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(2, len(DAYS) + 1, figsize=(3.2 * (len(DAYS) + 1), 5.2))
for j, cam in enumerate(("scene", "wrist")):
    for i, d in enumerate(DAYS):
        ax[j, i].imshow(sheet[d][cam])
        ax[j, i].set_title("%s %s" % (d[5:], "Szene" if cam == "scene" else "Hand"), fontsize=9)
    a = gray(sheet["2026-11-09"][cam]).astype(float)
    b = gray(sheet["2026-11-11"][cam]).astype(float)
    ax[j, -1].imshow(np.dstack([a, b, a]) / 255.0)
    ax[j, -1].set_title("09.11. (magenta) / 11.11. (grün)", fontsize=9)
for a in ax.flat:
    a.axis("off")
fig.suptitle("Startbild (Takt 0) je Aufnahmetag, mittlere Episode", fontsize=10)
fig.tight_layout()
fig.savefig(sys.argv[1], dpi=110)
print("Bild:", sys.argv[1])
