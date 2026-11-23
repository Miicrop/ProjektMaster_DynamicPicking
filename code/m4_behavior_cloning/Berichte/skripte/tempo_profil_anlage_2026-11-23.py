"""Tempo-Profil und Pendeln an der Anlage (23.11.), Ersatz/Anpassung von tempo_profil.py.

Policy-Rollouts: checkpoints/<Modell>/policy/rollouts/2026-11-23_*/rollout_000.npz
Experte: data_vm/2026-11-19-2, data_vm/2026-11-23 (record.py) und experte_000.npz der Rollouts.

Abstand = 3D-Abstand TCP -> PICK. Tempo = |dp|/dt (Zeitstempel t bzw. 15 Hz).
Umkehrungen: Annaeherungsrate v = -d(Abstand)/dt wechselt das Vorzeichen, mit Hysterese 5 mm/s,
beim ersten Durchgang 30-90 mm (erster Takt < 90 mm bis erster Takt < 30 mm bzw. Ende).
Hoehengrenze (Probegriff objekt): 7 mm Objektoberkante + 25 mm Probeabstand ueber PICK.
Policy-Ziele: FK der Aktion (ausgefuehrtes Ziel) und aller 8 Schritte jedes vorhergesagten Chunks.
Aufruf: python Berichte/skripte/tempo_profil_anlage_2026-11-23.py  (aus m4_behavior_cloning)
"""
import glob, json, os, sys
import numpy as np
sys.path.insert(0, '.')
from bc.urdf import KinematicChain
from bc import geometry

CH = KinematicChain.from_urdf('bc/data/lara5_candidate.urdf')
TOOL = np.array([0, 0, 0.1975])
BINS = [(0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 80), (80, 120)]
LIMIT_DZ = 32.0  # mm ueber PICK


def fk(q):
    T = CH.fk(q); return T[:3, 3] + T[:3, :3] @ TOOL


def yaw360(q):
    R = geometry.quat_to_matrix(np.asarray(q, float)[3:]); return np.degrees(np.arctan2(R[1, 0], R[0, 0]))


def profile(t, p, pick):
    d = np.linalg.norm(p - pick[:3], axis=1) * 1e3
    dt = np.diff(t); dt[dt <= 0] = np.nan
    sp = np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 / dt
    va = -np.diff(d) / dt
    dm = 0.5 * (d[1:] + d[:-1])
    prof = {}
    for lo, hi in BINS:
        k = (dm >= lo) & (dm < hi)
        prof[(lo, hi)] = float(np.nanmedian(sp[k])) if k.any() else np.nan
        prof[(lo, hi, 'a')] = float(np.nanmedian(va[k])) if k.any() else np.nan  # Annaeherungsrate
    i0 = np.where(d < 90)[0]
    rev = np.nan
    if len(i0):
        a = i0[0]; b = np.where(d[a:] < 30)[0]; b = a + b[0] if len(b) else len(d) - 1
        s = 0; rev = 0
        for v in va[a:b]:
            if not np.isfinite(v): continue
            if v > 5: n = 1
            elif v < -5: n = -1
            else: continue
            if s and n != s: rev += 1
            s = n
    # Schleichen: laengste Zeit mit Tempo < 5 mm/s bei Abstand 20-80 mm
    slow = (sp < 5) & (dm < 80) & (dm > 20)
    best = cur = 0.0
    for ok, step in zip(slow, dt):
        cur = cur + (step if np.isfinite(step) else 0) if ok else 0.0; best = max(best, cur)
    return d, sp, prof, rev, best


def fmt(v): return '–' if not np.isfinite(v) else ('%.0f' % v)


def expert_recordings(pattern, cut_grip=True):
    out = []
    for f in sorted(glob.glob(pattern)):
        z = np.load(f); m = json.load(open(os.path.join(os.path.dirname(f), 'meta.json')))['metadata']
        s = z['observation__state']; a = z['action']
        g = np.where(a[:, 6] > 0.5)[0]; n = int(g[0]) + 1 if len(g) else len(s)
        p = s[:n, 6:9].astype(float); t = np.arange(n) / 15.0
        out.append((m['planner']['approach_speed_ms'], profile(t, p, np.array(m['object_pose']['PICK']))))
    return out


rows = []
for m in ['G2_licht_langsam_nur_griff', 'G3_kappen030', 'G4_ausblenden030']:
    for f in sorted(glob.glob(f'checkpoints/{m}/policy/rollouts/2026-11-23_*/rollout_000.npz')):
        d = os.path.dirname(f); s = json.load(open(d + '/summary.json')); e = s['episodes'][0]; L = e['lage']
        r = np.load(f); pick = np.array(L['pick'])
        p = np.vstack([r['tcp'][:, :3], r['final_tcp'][None, :3]]); t = np.append(r['t'], r['t'][-1] + 1 / 15)
        dist, sp, prof, rev, slow = profile(t, p, pick)
        # Policy-Ziele
        act_dz = np.array([fk(q)[2] for q in r['action'][:, :6]]) * 1e3 - pick[2] * 1e3
        ch = r['pred_chunk']
        ch_dz = np.array([[fk(q[:6])[2] for q in c] for c in ch]) * 1e3 - pick[2] * 1e3 if len(ch) else np.zeros((0, 8))
        tcp_dz = p[:, 2] * 1e3 - pick[2] * 1e3
        # Grenze erreicht: erster Takt, in dem ein Chunk-Ziel unter die Grenze geht
        below_chunks = int((ch_dz.min(axis=1) < LIMIT_DZ).sum()) if len(ch) else 0
        last_ch_min = float(ch_dz[-1].min()) if len(ch) else np.nan
        stop = e['stop_reason']
        valid_end = stop.startswith(('kollision vorab', 'stopp: [Viol'))
        yaw_u = (yaw360(r['final_tcp']) - yaw360(pick) + 180) % 360 - 180
        jumps_gap = np.abs(r['action'][:, :6] - r['joints']).max(axis=0)
        dq = np.abs(np.diff(r['action'][:, :6], axis=0)).max(axis=0) if len(r['action']) > 1 else np.zeros(6)
        # Welligkeit: Umweg-Faktor im ersten Durchgang 30-90 mm (Weglaenge / Abstandsabnahme)
        i0 = np.where(dist < 90)[0]; um = np.nan
        if len(i0):
            a = i0[0]; b = np.where(dist[a:] < 30)[0]; b = a + b[0] if len(b) else len(dist) - 1
            if dist[a] - dist[b] > 5:
                um = np.linalg.norm(np.diff(p[a:b + 1], axis=0), axis=1).sum() * 1e3 / (dist[a] - dist[b])
        ps = r['predict_s'][np.isfinite(r['predict_s'])] * 1e3
        rows.append(dict(m=m[:2], run=os.path.basename(d)[11:16].replace('-', ':'), steps=e['steps'], stop=stop, valid=valid_end,
                         xy=L['at_stop']['xy_m'] * 1e3, dz=L['at_stop']['dz_m'] * 1e3, yaw=yaw_u,
                         act_min=act_dz.min(), ch_min=ch_dz.min() if len(ch) else np.nan, last_ch=last_ch_min,
                         below=below_chunks, nch=len(ch), tcp_min=tcp_dz.min(),
                         grip_act=r['action'][:, 6].max(), grip_ch=ch[:, :, 6].max() if len(ch) else np.nan,
                         gap=jumps_gap.max(), gap_j=int(jumps_gap.argmax()) + 1, dq=dq.max(),
                         prof=prof, rev=rev, slow=slow, um=um, pms=np.median(ps), p95=np.percentile(ps, 95), pmax=ps.max(),
                         ovr=e['pacer_overruns'], ovr_rate=e['pacer_overruns'] / max(t[-1] - t[0], 1e-6)))

print('## Policy je Fahrt')
print('Mod Zeit  ok  xy   dz   yawU  act_min ch_min last_ch below/n  grip(a/ch)  gap(J) dq   rev slow[s] umweg  ms med/p95/max ovr(/s) | Tempo je Klasse ' + ' '.join('%d-%d' % b for b in BINS))
for x in rows:
    print(f"{x['m']} {x['run']} {'J' if x['valid'] else 'N'} {x['xy']:5.1f} {x['dz']:5.1f} {x['yaw']:5.1f} {x['act_min']:7.1f} {x['ch_min']:6.1f} {x['last_ch']:7.1f} {x['below']:3d}/{x['nch']:<3d} {x['grip_act']:.2f}/{x['grip_ch']:.2f} {x['gap']:.2f}({x['gap_j']}) {x['dq']:.2f} {fmt(x['rev']):>3} {x['slow']:5.2f} {x['um']:5.2f} {x['pms']:.0f}/{x['p95']:.0f}/{x['pmax']:.0f} {x['ovr']}({x['ovr_rate']:.1f}) | " + ' '.join(fmt(x['prof'][b]) for b in BINS))

print('\n## Zusammenfassung Policy (gueltige Fahrten)')
for mm in ['G2', 'G3', 'G4']:
    v = [x for x in rows if x['m'] == mm and x['valid']]
    P = {b: np.nanmedian([x['prof'][b] for x in v]) for b in BINS}
    revs = np.array([x['rev'] for x in v], float)
    print(mm, 'n', len(v), 'Umkehr median %.0f (min %.0f max %.0f)' % (np.nanmedian(revs), np.nanmin(revs), np.nanmax(revs)),
          'Chunk unter Grenze: %d/%d Fahrten' % (sum(x['ch_min'] < LIMIT_DZ for x in v), len(v)),
          'Akt.-Ziel unter Grenze: %d/%d' % (sum(x['act_min'] < LIMIT_DZ for x in v), len(v)),
          'Ch-min median %.1f' % np.median([x['ch_min'] for x in v]),
          'Schleichen>=1s: %d' % sum(x['slow'] >= 1 for x in v), 'slow max %.2f' % max(x['slow'] for x in v),
          'Umweg median %.2f' % np.nanmedian([x['um'] for x in v]),
          '| ' + ' '.join('%s:%s' % ('%d-%d' % b, fmt(P[b])) for b in BINS))
    A = {b: np.nanmedian([x['prof'][b + ('a',)] for x in v]) for b in BINS}
    print('   Annaeherungsrate ' + ' '.join('%s:%s' % ('%d-%d' % b, fmt(A[b])) for b in BINS))

print('\n## Experte')
groups = {'19.11. 20 mm/s (data_vm/2026-11-19-2)': expert_recordings('data_vm/2026-11-19-2/ep_*/arrays.npz')}
for v_ in (0.03, 0.035, 0.04):
    groups['23.11. %d mm/s (record.py)' % round(v_ * 1000)] = [x for x in expert_recordings('data_vm/2026-11-23/ep_*/arrays.npz') if abs(x[0] - v_) < 1e-4]
exp_ro = []
for f in sorted(glob.glob('checkpoints/*/policy/rollouts/2026-11-23_*/experte_000.npz')):
    d = os.path.dirname(f); e = json.load(open(d + '/summary.json'))['episodes'][0]; z = np.load(f)
    pick = np.array(e['lage']['pick'])
    g = np.where(z['gripper_cmd'] > 0.5)[0]; n = int(g[0]) + 1 if len(g) else len(z['t'])
    exp_ro.append((None, profile(z['t'][:n], z['tcp'][:n, :3], pick)))
groups['23.11. Experte nach Policy (infer.py, 4)'] = exp_ro
for name, G in groups.items():
    P = {b: np.nanmedian([g[1][2][b] for g in G]) for b in BINS}
    revs = np.array([g[1][3] for g in G], float)
    A = {b: np.nanmedian([g[1][2][b + ('a',)] for g in G]) for b in BINS}
    print('   Annaeherungsrate ' + ' '.join('%s:%s' % ('%d-%d' % b, fmt(A[b])) for b in BINS))
    print(f"{name}: n {len(G)} Umkehr median {np.nanmedian(revs):.0f} (min {np.nanmin(revs):.0f} max {np.nanmax(revs):.0f}) | " + ' '.join('%s:%s' % ('%d-%d' % b, fmt(P[b])) for b in BINS))
