"""Unterscheiden sich die Aufnahmetage in Labels, Timing oder Bildern?

Je Tag (Stichprobe von Episoden):
* Vorlauf: Takt-Versatz L, bei dem action[t] am besten zu joints[t+L] passt
* Abstand Label <-> Ist (Gelenke, rad) und ideal <-> verrauscht (TCP, mm)
* Glaette der Labels (groesster Gelenksprung je Takt)
* Bildstatistik: mittlere Helligkeit je Kamera, Bildverschiebung der Szene
  (Kreuzkorrelation des ersten Bildes gegen den Bezugstag)
* Laenge, Greiftakt, Anteil sync_ok

Aufruf: tage_vergleich.py <tag> ... (erster Tag = Bezug)
"""
import sys
import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
N = 25


def shift(a, b):
    """Verschiebung (dy, dx) von b gegen a per Phasenkorrelation (Graubild)."""
    a = a.mean(axis=2) - a.mean()
    b = b.mean(axis=2) - b.mean()
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-9)).real
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    h, w = r.shape
    return (dy - h if dy > h // 2 else dy, dx - w if dx > w // 2 else dx)


ref_img = None
print("| Tag | Ep. | Länge | Greiftakt | Vorlauf L | Label–Ist rad (L=1) | ideal–verrauscht TCP mm p95 | "
      "Label-Sprung p95 rad | sync_ok | Helligkeit Hand/Szene | Szene-Versatz px |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for day in sys.argv[1:]:
    files = sorted(glob.glob(str(ROOT / "data" / day / "ep_*" / "arrays.npz")))
    files = files[:: max(1, len(files) // N)][:N]
    L, lab, noisy, jump, sync, lens, grasp, br_w, br_s, sh = [], [], [], [], [], [], [], [], [], []
    for f in files:
        z = np.load(f)
        q = z["observation__state"][:, :6]
        a = z["action"][:, :6]
        errs = [np.mean(np.abs(a[: len(a) - k] - q[k:])) for k in range(0, 6)]
        L.append(int(np.argmin(errs)))
        lab.append(errs[1])
        noisy.append(np.percentile(1e3 * np.linalg.norm(z["aux__pose_ideal"][:, :3] - z["aux__pose_noisy"][:, :3], axis=1), 95))
        jump.append(np.percentile(np.abs(np.diff(a, axis=0)).max(axis=1), 95))
        sync.append(float(np.mean(z["aux__sync_ok"])))
        lens.append(len(a))
        g = np.flatnonzero(z["action"][:, 6] > 0.5)
        grasp.append(int(g[0]) if len(g) else np.nan)
        w = z["observation__images__wrist"]
        s = z["observation__images__scene"]
        br_w.append(float(w[::10].mean()))
        br_s.append(float(s[::10].mean()))
        img = s[0].astype(float)
        if ref_img is None:
            ref_img = img
        sh.append(shift(ref_img, img))
    sh = np.array(sh)
    print("| %s | %d | %.0f | %.0f | %s | %.4f | %.1f | %.4f | %.0f %% | %.0f / %.0f | %+.0f / %+.0f |" % (
        day, len(files), np.median(lens), np.nanmedian(grasp),
        "/".join("%d:%d" % (k, L.count(k)) for k in sorted(set(L))),
        np.median(lab), np.median(noisy), np.median(jump), 100 * np.mean(sync),
        np.median(br_w), np.median(br_s), np.median(sh[:, 0]), np.median(sh[:, 1])))
