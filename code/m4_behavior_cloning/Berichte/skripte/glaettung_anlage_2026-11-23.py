"""Anlage 23.11. nachmittags: Policy-Fahrten mit und ohne Glaettung (Tiefpass auf die Ziele).

Je Fahrt (unter 60 mm ueber PICK, wo vormittags das Pendeln sass):
  Ist->Soll   Abstand des gemessenen TCP zur Bahn der gesendeten Ziele (zeitunabhaengig)
  Spannweite  seitliche Ausdehnung des Ist-TCP (xy) unter 60 mm
  Umk/s       Umkehrungen der Annaeherung (zum Objekt hin / weg, Hysterese 5 mm/s) je s, 30-90 mm
  Ruck        2. Differenz der TCP-Position je Takt: Action (roh), Ziel (gesendet), Ist (Arm)
  Ende        xy / dz des TCP gegen PICK nach der Fahrt, Gier ungefaltet
Aufruf aus m4_behavior_cloning:
  python Berichte/skripte/glaettung_anlage_2026-11-23.py [ab HH-MM]   (Default ab 15-20)
"""
import glob, json, os, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, '.')
from bc.offline_glaette import ToolFK, jerk_mm
from bc import geometry

FK = ToolFK()
SINCE = sys.argv[1] if len(sys.argv) > 1 else '15-20'


def pathdev(P, Q):
    out = []
    for p in P:
        best = 1e9
        for a, b in zip(Q[:-1], Q[1:]):
            ab = b - a
            t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-12), 0, 1)
            best = min(best, np.linalg.norm(p - (a + t * ab)))
        out.append(best)
    return np.array(out)


def reversals(v, h=5.0):
    s = c = 0
    for x in v:
        n = 1 if x > h else (-1 if x < -h else 0)
        if n == 0:
            continue
        if s and n != s:
            c += 1
        s = n
    return c


def yaw360(q):
    R = geometry.quat_to_matrix(np.asarray(q, float)[3:])
    return np.degrees(np.arctan2(R[1, 0], R[0, 0]))


rows = []
for f in sorted(glob.glob('checkpoints/*/policy/rollouts/2026-11-23_*/rollout_000.npz')):
    d = os.path.dirname(f)
    stamp = os.path.basename(d)[11:]
    if stamp < SINCE:
        continue
    sp = d + '/summary.json'
    S = json.load(open(sp)) if os.path.exists(sp) else None
    r = np.load(f)
    e = S['episodes'][0] if S and S['episodes'] else None
    args = S['args'] if S else {}
    pk7 = r['lage_pick'] if 'lage_pick' in r.files else np.array(e['lage']['pick'])
    pk = pk7[:3]
    ist = r['tcp'][:, :3]
    soll = FK(r['ziel'] if 'ziel' in r.files else r['action'][:, :6])
    act = FK(r['action'][:, :6])
    h = (ist[:, 2] - pk[2]) * 1e3
    k = h < 60
    dist = np.linalg.norm(ist - pk, axis=1) * 1e3
    dt = np.diff(r['t'])
    va = -np.diff(dist) / dt
    i0 = np.where(dist < 90)[0]
    rv = np.nan
    if len(i0):
        a = i0[0]
        b = np.where(dist[a:] < 30)[0]
        b = a + b[0] if len(b) else len(dist) - 1
        rv = reversals(va[a:b]) / max(dt[a:b].sum(), 1e-3)
    kk = k[1:-1]
    def jm(P):
        j = jerk_mm(P)
        return float(np.median(j[kk])) if len(j) and kk.any() else np.nan
    fin = r['final_tcp']
    yaw_end = (yaw360(fin) - yaw360(pk7) + 180) % 360 - 180
    ps = r['predict_s'][np.isfinite(r['predict_s'])] * 1e3
    rows.append(dict(
        modell=d.split(os.sep)[-4][:6], zeit=stamp[:8].replace('-', ':'),
        alpha=float(args.get('glaettung', 1.0) or 1.0), ddim=args.get('inference_steps') or 10,
        abstand=float(args.get('probe_abstand') or 25), experte=args.get('experte'),
        lage='%.0f/%.0f' % (pk[0] * 1e3, pk[1] * 1e3),
        takte=len(r['t']), n_nah=int(k.sum()),
        dev=float(np.median(pathdev(ist[k], soll) * 1e3)) if k.sum() else np.nan,
        dev_p95=float(np.percentile(pathdev(ist[k], soll) * 1e3, 95)) if k.sum() else np.nan,
        span=float(np.ptp(ist[k, :2] - pk[:2], axis=0).max() * 1e3) if k.sum() > 1 else np.nan,
        umk=rv, ruck_act=jm(act), ruck_ziel=jm(soll), ruck_ist=jm(ist),
        end_xy=float(np.linalg.norm(fin[:2] - pk[:2]) * 1e3), end_dz=float((fin[2] - pk[2]) * 1e3),
        min_dz=float(np.min(np.r_[h, (fin[2] - pk[2]) * 1e3])), yaw=float(yaw_end),
        ms=float(np.median(ps)) if len(ps) else np.nan, verzug=float(np.nanmax(r['delay_steps'])),
        ueberl=e['pacer_overruns'] if e else -1,
        stopp=(e['stop_reason'] if e else 'kein summary'), rueckzug=(e.get('rueckzug') if e else '')))

hdr = ('Modell', 'Zeit', 'alpha', 'Abst', 'Takte', 'Ist-Soll', 'p95', 'Spann', 'Umk/s', 'RuckAct', 'RuckZiel',
       'RuckIst', 'xyEnde', 'dzEnde', 'Gier', 'ms', 'Verz', 'Uebl', 'Stopp')
print(' '.join('%-8s' % x for x in hdr))
for x in rows:
    print('%-8s %-8s %-8.2f %-8.0f %-8d %-8.1f %-8.1f %-8.1f %-8.1f %-8.2f %-8.2f %-8.2f %-8.1f %-8.1f %-8.1f %-8.0f %-8.0f %-8d %s' % (
        x['modell'], x['zeit'], x['alpha'], x['abstand'], x['takte'], x['dev'], x['dev_p95'], x['span'], x['umk'],
        x['ruck_act'], x['ruck_ziel'], x['ruck_ist'], x['end_xy'], x['end_dz'], x['yaw'], x['ms'], x['verzug'],
        x['ueberl'], x['stopp'][:45]))

print('\nZusammenfassung je Modell und alpha (Median ueber Fahrten):')
g = defaultdict(list)
for x in rows:
    g[(x['modell'], x['alpha'])].append(x)
keys = ['dev', 'dev_p95', 'span', 'umk', 'ruck_act', 'ruck_ziel', 'ruck_ist', 'end_xy', 'end_dz', 'yaw']
print('%-8s %-6s %-4s ' % ('Modell', 'alpha', 'n') + ' '.join('%-9s' % k for k in keys) + ' Abstaende')
for (m, a), v in sorted(g.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
    med = [np.nanmedian([x[k] for x in v]) for k in keys]
    med[-1] = np.nanmedian([abs(x['yaw']) for x in v])
    print('%-8s %-6.2f %-4d ' % (m, a, len(v)) + ' '.join('%-9.2f' % z for z in med)
          + ' ' + ','.join(sorted({'%.0f' % x['abstand'] for x in v})))
json.dump(rows, open(os.environ.get('OUT', os.devnull), 'w'), indent=0, default=float)
