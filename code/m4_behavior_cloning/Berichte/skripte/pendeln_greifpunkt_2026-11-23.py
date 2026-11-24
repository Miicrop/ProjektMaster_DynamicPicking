"""Pendelt das Tempo beim Wechsel Transit -> Endanflug, und haengt das mit den vorhergesagten Greifpunkten zusammen?

Je Policy-Fahrt (23.11., gueltige Fahrten):
- Tempo-Pendeln im Wechsel (Abstand 30-90 mm, erster Durchgang): Umkehrungen der Annaeherungsrate (Hyst. 5 mm/s)
  und Umkehrungen des Tempobetrags (Beschleunigen/Bremsen-Wechsel, Hyst. 5 mm/s).
- Vorhergesagter Greifpunkt je Chunk: tiefster Chunk-Schritt (FK), xy gegen PICK; Spruenge zwischen aufeinander-
  folgenden Chunks (|Delta xy| und |Delta z|), im selben Abschnitt.
- Zusammenhang: ueber Fahrten (Spearman) und innerhalb der Fahrt (folgt auf einen Greifpunkt-Sprung > 3 mm
  innerhalb von 3 Takten eine Tempo-Umkehr? gegen die Grundrate).
Aufruf aus m4_behavior_cloning: python Berichte/skripte/pendeln_greifpunkt_2026-11-23.py
"""
import glob, json, os, sys
import numpy as np
sys.path.insert(0, '.')
from bc.urdf import KinematicChain

CH = KinematicChain.from_urdf('bc/data/lara5_candidate.urdf'); TOOL = np.array([0, 0, 0.1975])
def fk(q): T = CH.fk(q); return T[:3, 3] + T[:3, :3] @ TOOL

def reversals(v, h=5.0):
    s = 0; idx = []
    for i, x in enumerate(v):
        if not np.isfinite(x): continue
        n = 1 if x > h else (-1 if x < -h else 0)
        if n == 0: continue
        if s and n != s: idx.append(i)
        s = n
    return idx

def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return np.corrcoef(ra, rb)[0, 1]

rows = []; hits = []; base = []
for f in sorted(glob.glob('checkpoints/G*/policy/rollouts/2026-11-23_*/rollout_000.npz')):
    d = os.path.dirname(f); e = json.load(open(d + '/summary.json'))['episodes'][0]
    if not e['stop_reason'].startswith(('kollision vorab', 'stopp: [Viol')): continue
    r = np.load(f); pk = np.array(e['lage']['pick'][:3])
    p = r['tcp'][:, :3]; t = r['t']
    dist = np.linalg.norm(p - pk, axis=1) * 1e3
    dt = np.diff(t); va = -np.diff(dist) / dt; sp = np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 / dt
    acc = np.diff(sp)  # Tempoaenderung je Takt
    i0 = np.where(dist < 90)[0]
    if not len(i0): continue
    a = i0[0]; b = np.where(dist[a:] < 30)[0]; b = a + b[0] if len(b) else len(dist) - 1
    rev_a = reversals(va[a:b]); rev_s = reversals(acc[a:b] / np.maximum(dt[a:b][:len(acc[a:b])], 1e-3) * 0 + acc[a:b], 5.0)
    # Greifpunkt je Chunk
    gp = []; gstep = []
    for st, c in zip(r['pred_step'], r['pred_chunk']):
        P = np.array([fk(q[:6]) for q in c]); k = np.argmin(P[:, 2]); gp.append(P[k]); gstep.append(st)
    gp = np.array(gp); gstep = np.array(gstep)
    sel = (gstep >= a) & (gstep <= b)
    g = gp[sel]; gs = gstep[sel]
    if len(g) < 3: continue
    dxy = np.linalg.norm(np.diff(g[:, :2], axis=0), axis=1) * 1e3
    dz = np.abs(np.diff(g[:, 2])) * 1e3
    gxy = np.linalg.norm(g[:, :2] - pk[:2], axis=1) * 1e3
    # innerhalb der Fahrt: Umkehr der Annaeherung innerhalb von 3 Takten nach Greifpunkt-Sprung > 3 mm?
    rev_steps = set(a + i for i in rev_a)
    for j, jump in enumerate(dxy):
        st = gs[j + 1]
        hit = any((st <= s_ <= st + 3) for s_ in rev_steps)
        (hits if jump > 3 else base).append(hit)
    rows.append(dict(name=d.split(os.sep)[-4][:2] + ' ' + os.path.basename(d)[11:16], rev_a=len(rev_a), rev_s=len(rev_s),
                     um=np.linalg.norm(np.diff(p[a:b + 1], axis=0), axis=1).sum() * 1e3 / max(dist[a] - dist[b], 1),
                     jxy=np.median(dxy), jxy_max=dxy.max(), jz=np.median(dz), gxy_sd=np.std(gxy), gxy_med=np.median(gxy),
                     gxy_last=gxy[-1], xy_stop=e['lage']['at_stop']['xy_m'] * 1e3, n=len(g)))

print('Fahrt     Umk.Ann Umk.Tempo Umweg | GP-Sprung xy med/max  z med | GP-xy med  sd  letzter | xy Stopp  Chunks')
for x in rows:
    print(f"{x['name']:9} {x['rev_a']:5d} {x['rev_s']:7d} {x['um']:6.2f} | {x['jxy']:6.1f} {x['jxy_max']:6.1f} {x['jz']:6.1f} | {x['gxy_med']:6.1f} {x['gxy_sd']:5.1f} {x['gxy_last']:6.1f} | {x['xy_stop']:6.1f} {x['n']:4d}")
A = lambda k: np.array([x[k] for x in rows], float)
print('\nSpearman ueber %d Fahrten:' % len(rows))
for k1 in ['rev_a', 'rev_s', 'um']:
    print('  %-6s' % k1, ' '.join('%s %.2f' % (k2, spearman(A(k1), A(k2))) for k2 in ['jxy', 'jxy_max', 'jz', 'gxy_sd', 'gxy_last', 'xy_stop']))
print('\nInnerhalb der Fahrt: Annaeherungs-Umkehr <= 3 Takte nach Greifpunkt-Sprung > 3 mm: %d/%d (%.0f %%), sonst %d/%d (%.0f %%)'
      % (sum(hits), len(hits), 100 * np.mean(hits) if hits else np.nan, sum(base), len(base), 100 * np.mean(base) if base else np.nan))
