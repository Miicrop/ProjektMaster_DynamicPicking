"""Anlage 23.11. ab 16 Uhr: Glaettung 0,5 gegen 0,25 auf vielen Lagen (Experte legt um), plus Griffversuche.

Wie glaettung_anlage_2026-11-23.py, aber fuer alle Episoden je Lauf (rollout_XXX.npz) und mit Tempo je
Abschnitt. alpha wird zusaetzlich aus dem Log geschaetzt (ziel gegen action), damit Laeufe ohne
summary.json zuordenbar sind.
Aufruf aus m4_behavior_cloning:  python Berichte/skripte/glaettung_lagen_2026-11-23.py [ab HH-MM]
"""
import csv, glob, json, os, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, '.')
from bc.offline_glaette import ToolFK, jerk_mm
from bc import geometry

FK = ToolFK()
SINCE = sys.argv[1] if len(sys.argv) > 1 else '16-00'


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


def alpha_est(r):
    z, a = r['ziel'], r['action'][:, :6]
    x = (a[1:] - z[:-1]).ravel(); y = (z[1:] - z[:-1]).ravel()
    return float(x @ y / (x @ x)) if x @ x > 0 else np.nan


rows = []
for d in sorted(glob.glob('checkpoints/*/policy/rollouts/2026-11-23_*')):
    stamp = os.path.basename(d)[11:]
    if stamp < SINCE:
        continue
    S = json.load(open(d + '/summary.json')) if os.path.exists(d + '/summary.json') else None
    csvrows = []
    if os.path.exists(d + '/policy_test.csv'):
        with open(d + '/policy_test.csv', encoding='utf-8') as fh:
            csvrows = list(csv.DictReader(fh, delimiter=';'))
    for f in sorted(glob.glob(d + '/rollout_*.npz')):
        i = int(os.path.basename(f)[8:11])
        r = np.load(f)
        e = S['episodes'][i] if S and i < len(S['episodes']) else None
        args = S['args'] if S else {}
        cr = csvrows[i] if i < len(csvrows) else {}
        pk7 = r['lage_pick']
        pk = pk7[:3]
        ist = r['tcp'][:, :3]
        soll = FK(r['ziel'])
        h = (ist[:, 2] - pk[2]) * 1e3
        k = h < 60
        dist = np.linalg.norm(ist - pk, axis=1) * 1e3
        dt = np.diff(r['t'])
        va = -np.diff(dist) / dt
        sp = np.linalg.norm(np.diff(ist, axis=0), axis=1) * 1e3 / dt
        hm = 0.5 * (h[1:] + h[:-1])
        i0 = np.where(dist < 90)[0]
        rv = np.nan
        if len(i0):
            a = i0[0]
            b = np.where(dist[a:] < 30)[0]
            b = a + b[0] if len(b) else len(dist) - 1
            rv = reversals(va[a:b]) / max(dt[a:b].sum(), 1e-3)
        fin = r['final_tcp']
        g = np.flatnonzero(r['gripper_cmd'] > 0.5)
        gstep = int(g[0]) if len(g) else None
        probe = args.get('probegriff') or (cr.get('probegriff', '').split(' ')[0] or None)
        gap = args.get('probe_abstand')
        if gap is None and '(' in cr.get('probegriff', ''):
            gap = float(cr['probegriff'].split('(')[1].split()[0])
        rows.append(dict(
            lauf=stamp[:8].replace('-', ':'), ep=i, alpha=round(alpha_est(r), 2),
            alpha_arg=args.get('glaettung'), probe=probe, abstand=gap,
            lage='%.0f/%.0f' % (pk[0] * 1e3, pk[1] * 1e3), pick_yaw=float(yaw360(pk7)), takte=len(r['t']),
            dev=float(np.median(pathdev(ist[k], soll)) * 1e3) if k.sum() else np.nan,
            span=float(np.ptp(ist[k, :2] - pk[:2], axis=0).max() * 1e3) if k.sum() > 1 else np.nan,
            umk=rv, ruck=float(np.median(jerk_mm(ist)[k[1:-1]])) if k.sum() > 2 else np.nan,
            v_transit=float(np.median(sp[(hm > 80) & (hm < 150)])) if ((hm > 80) & (hm < 150)).any() else np.nan,
            v_end=float(np.median(sp[(hm > 15) & (hm < 45)])) if ((hm > 15) & (hm < 45)).any() else np.nan,
            end_dx=float((fin[0] - pk[0]) * 1e3), end_dy=float((fin[1] - pk[1]) * 1e3),
            end_xy=float(np.linalg.norm(fin[:2] - pk[:2]) * 1e3), end_dz=float((fin[2] - pk[2]) * 1e3),
            yaw=float((yaw360(fin) - yaw360(pk7) + 180) % 360 - 180),
            gstep=gstep, g_end=float(r['gripper_cmd'][-1]) if len(r['gripper_cmd']) else np.nan,
            stopp=(e['stop_reason'] if e else cr.get('stopp', 'kein summary')),
            danach=((e.get('rueckzug') or '') if e else cr.get('danach', '')),
            ovr=e['pacer_overruns'] if e else -1,
            ms=float(np.nanmedian(r['predict_s']) * 1e3)))

print('%-9s %3s %5s %-7s %5s %-9s %5s %4s %6s %6s %5s %6s %6s %6s %6s %6s %6s %6s %5s %s' % (
    'Lauf', 'Ep', 'alpha', 'Probe', 'Abst', 'Lage', 'Gier', 'Tkt', 'IstSol', 'Spann', 'Umk', 'vTrans', 'vEnd',
    'dx', 'dy', 'xyEnd', 'dzEnd', 'GierE', 'Griff', 'Stopp'))
for x in rows:
    print('%-9s %3d %5.2f %-7s %5s %-9s %5.0f %4d %6.2f %6.1f %5.1f %6.0f %6.0f %+6.1f %+6.1f %6.1f %6.1f %+6.1f %5s %s' % (
        x['lauf'], x['ep'], x['alpha'], x['probe'], '%g' % x['abstand'] if x['abstand'] is not None else '-',
        x['lage'], x['pick_yaw'], x['takte'], x['dev'], x['span'], x['umk'], x['v_transit'], x['v_end'],
        x['end_dx'], x['end_dy'], x['end_xy'], x['end_dz'], x['yaw'], x['gstep'], x['stopp'][:40]))

print('\nProbefahrten (probe objekt, Arm gefahren), Median je alpha:')
g = defaultdict(list)
for x in rows:
    if x['probe'] == 'objekt' and not str(x['stopp']).startswith('arm steht'):
        g[x['alpha']].append(x)
for a, v in sorted(g.items(), reverse=True):
    m = lambda k: np.nanmedian([y[k] for y in v])
    mx = lambda k: np.nanmax([y[k] for y in v])
    print('alpha %.2f: n %d, Lagen %d | Ist-Soll %.2f (max %.1f) | Spannweite %.1f (max %.1f) | Umk/s %.1f (max %.1f) | '
          'v Transit %.0f, v Endanflug %.0f mm/s | Takte %.0f | xy Ende %.1f (max %.1f), dx %+.1f dy %+.1f | |Gier| %.1f (max %.1f)'
          % (a, len(v), len({y['lage'] for y in v}), m('dev'), mx('dev'), m('span'), mx('span'), m('umk'), mx('umk'),
             m('v_transit'), m('v_end'), m('takte'), m('end_xy'), mx('end_xy'), m('end_dx'), m('end_dy'),
             np.nanmedian([abs(y['yaw']) for y in v]), np.nanmax([abs(y['yaw']) for y in v])))
json.dump(rows, open(os.environ.get('OUT', os.devnull), 'w'), indent=0, default=float)
