"""Ersatz fuer das fehlende skripte/nachlauf.py.
Aufruf: python nachlauf_eigen.py "30=glob" "35=glob" ...
Nachlauf = z_ist(t) - z_soll(t) (gleicher Takt, Soll = aux.pose_noisy) im Abstieg PRE_PICK->PICK
(Soll faellt, Soll < PICK+50 mm, vor Greifer zu). Tiefster Punkt = min z_ist ab Abstieg bis Ende Greifen
gegen PICK-z (Greifhoehe). Seitlich = |xy_ist - xy_soll| in den 15 Takten vor Greifer zu."""
import sys, glob, json, os
import numpy as np
def ep(path):
    d = np.load(path); m = json.load(open(os.path.join(os.path.dirname(path), 'meta.json')))['metadata']
    s = d['observation__state']; a = d['action']; pn = d['aux__pose_noisy']
    zi = s[:, 8] * 1e3; zs = pn[:, 2] * 1e3; xyi = s[:, 6:8] * 1e3; xys = pn[:, :2] * 1e3
    zp = m['object_pose']['PICK'][2] * 1e3
    g = np.where(a[:, 6] > 0.5)[0]; tg = int(g[0]) if len(g) else len(a) - 1
    dz = np.diff(zs, prepend=zs[0])
    desc = np.where((np.arange(len(zs)) < tg) & (dz < -0.3) & (zs < zp + 50.5))[0]
    lag = zi[desc] - zs[desc]
    # Ende des Greifens: bis Soll wieder steigt
    up = np.where((np.arange(len(zs)) > tg) & (dz > 0.3))[0]; te = int(up[0]) if len(up) else len(zs)
    t0 = desc[0] if len(desc) else max(tg - 30, 0)
    low = zi[t0:te].min() - zp
    lat = np.linalg.norm(xyi[max(tg - 15, 0):tg + 1] - xys[max(tg - 15, 0):tg + 1], axis=1)
    lat_end = np.linalg.norm(xyi[tg] - xys[tg])
    return dict(lag=lag, low=low, lat_max=lat.max(), lat_end=lat_end, v=m['planner']['approach_speed_ms'],
                ovr=m.get('pacer_overruns'), n=len(desc), tg=tg)
print(f"{'Gruppe':8}{'Ep':>4}{'v':>7}{'NL med':>8}{'p95':>7}{'max':>7}{'tief min':>10}{'tief med':>10}{'lat med':>9}{'lat max':>9}{'Ueberl.':>8}")
for arg in sys.argv[1:]:
    name, pat = arg.split('=', 1)
    files = sorted(sum([glob.glob(p) for p in pat.split(",")], [])); R = [ep(f) for f in files]
    lag = np.concatenate([r['lag'] for r in R]); low = np.array([r['low'] for r in R]); lm = np.array([r['lat_max'] for r in R])
    print(f"{name:8}{len(R):>4}{sorted({r['v'] for r in R})[0]:>7.3f}{np.median(lag):>8.2f}{np.percentile(lag,95):>7.2f}{lag.max():>7.2f}"
          f"{low.min():>10.2f}{np.median(low):>10.2f}{np.median(lm):>9.2f}{lm.max():>9.2f}{sum(r['ovr'] or 0 for r in R):>8}")
    if '-v' in os.environ.get('NLV', ''):
        for f, r in zip(files, R): print('   ', f.split(os.sep)[-2] if os.sep in f else f, f"lagmax {r['lag'].max():.2f} low {r['low']:.2f} lat {r['lat_max']:.2f} n {r['n']}")
