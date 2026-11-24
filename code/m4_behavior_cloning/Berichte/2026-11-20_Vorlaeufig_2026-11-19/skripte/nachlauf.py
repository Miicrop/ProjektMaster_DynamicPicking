"""Echter Nachlauf beim Experten: Ist-TCP gegen Ideal-TCP am Ende des Endanflugs (Aufnahmen)."""
import sys, glob
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
for name, pat in [(a.split("=")[0], a.split("=")[1]) for a in sys.argv[1:]]:
    ov, lagz, latlag, vz = [], [], [], []
    for f in sorted(glob.glob(pat)):
        z = np.load(f); st, act, idl = z["observation__state"], z["action"], z["aux__pose_ideal"]
        c = np.flatnonzero(act[:, 6] > 0.5)
        if not len(c) or c[0] < 15: continue
        c = int(c[0]); zg = idl[c, 2]
        w = slice(c - 15, min(len(st), c + 8))
        ov.append((st[w, 8].min() - zg) * 1000)               # tiefster Ist-Punkt gegen Greifhoehe (<0 = unter Soll)
        lagz.append(np.max(st[c-15:c, 8] - idl[c-15:c, 2]) * 1000)  # Ist hinter Soll im Abstieg (oben = positiv)
        latlag.append(np.max(np.linalg.norm(st[c-15:c+1, 6:8] - idl[c-15:c+1, :2], axis=1)) * 1000)
        vz.append(np.max(-np.diff(idl[c-15:c+1, 2])) * 15 * 1000)
    ov, lagz, latlag, vz = map(np.array, (ov, lagz, latlag, vz))
    print(f"{name}: {len(ov)} Ep., Soll-Abstieg max {np.median(vz):.0f} mm/s | Ist hinkt im Abstieg nach: median {np.median(lagz):.1f} mm, p95 {np.percentile(lagz,95):.1f}, max {lagz.max():.1f} | "
          f"tiefster Punkt gegen Greifhöhe: median {np.median(ov):+.1f} mm, p5 {np.percentile(ov,5):+.1f}, min {ov.min():+.1f} | seitlich max in letzten 1 s: median {np.median(latlag):.1f}, p95 {np.percentile(latlag,95):.1f} mm")
