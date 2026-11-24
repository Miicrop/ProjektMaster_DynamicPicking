"""Seitenansicht je Einzelfahrt: Ist (gemessener TCP) gegen Soll (FK der ausgefuehrten Policy-Aktion),
dazu die Greifpunkte der Chunks und der Demo-Trichter. Eine Zeile je Fahrt.

Aufruf aus m4_behavior_cloning:
  python Berichte/skripte/seitenansicht_einzelfahrten_2026-11-23.py [G4:11-46-08 G2:11-50-46 G4:11-58-48]
"""
import glob, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, '.')
from bc.urdf import KinematicChain

BLUE, ORANGE, VIOLET = '#2a78d6', '#eb6834', '#6250d6'
INK, INK2, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#8a8984', '#e4e3df', '#fcfcfb'
CH = KinematicChain.from_urdf('bc/data/lara5_candidate.urdf'); TOOL = np.array([0, 0, 0.1975])
MODELS = {'G2': 'G2_licht_langsam_nur_griff', 'G3': 'G3_kappen030', 'G4': 'G4_ausblenden030'}
ARGS = [a for a in sys.argv[1:] if not a.startswith('--out=')]
OUTNAME = next((a[6:] for a in sys.argv[1:] if a.startswith('--out=')), 'seitenansicht_einzelfahrten.png')
RUNS = ARGS or ['G4:11-46-08', 'G2:11-50-46', 'G4:11-58-48']


def fk(q):
    T = CH.fk(q); return T[:3, 3] + T[:3, :3] @ TOOL


# Demo-Trichter (wie Berichtsgrafik)
allr, allh, allsp = [], [], []
for f in sorted(glob.glob('data_vm/2026-11-19-2/ep_*/arrays.npz')) + sorted(glob.glob('data_vm/2026-11-23/ep_*/arrays.npz')):
    z_ = np.load(f); m = json.load(open(os.path.join(os.path.dirname(f), 'meta.json')))['metadata']
    s = z_['observation__state']; g = np.where(z_['action'][:, 6] > 0.5)[0][0]
    pk = np.array(m['object_pose']['PICK'][:3]); p = s[:g + 1, 6:9].astype(float)
    allr.append(np.linalg.norm(p[:, :2] - pk[:2], axis=1) * 1e3); allh.append((p[:, 2] - pk[2]) * 1e3)
    sp = np.r_[np.nan, np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 * 15]
    allsp.append(sp if '2026-11-19-2' in f else np.full_like(sp, np.nan))
allr, allh, allsp = map(np.concatenate, (allr, allh, allsp))
edges = np.arange(0, 160, 10); mid = edges[:-1] + 5
def binstat(v, fn):
    return np.array([fn(v[(allh >= a) & (allh < b)]) for a, b in zip(edges[:-1], edges[1:])])
p90 = binstat(allr, lambda x: np.percentile(x, 90)); p50 = binstat(allr, np.median)
dsp = binstat(allsp, np.nanmedian)

plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK2, 'xtick.color': INK2,
                     'ytick.color': INK2, 'font.family': 'DejaVu Sans'})
fig, axes = plt.subplots(len(RUNS), 2, figsize=(12, 5.2 * len(RUNS)), sharey=True,
                         gridspec_kw={'width_ratios': [1.6, 1]}, facecolor=SURF)
axes = np.atleast_2d(axes)
for row, spec in enumerate(RUNS):
    mod, stamp = spec.split(':')
    d = f'checkpoints/{MODELS[mod]}/policy/rollouts/2026-11-23_{stamp}'
    e = json.load(open(d + '/summary.json'))['episodes'][0]; r = np.load(d + '/rollout_000.npz')
    pk = np.array(e['lage']['pick'][:3]); t = r['t'] - r['t'][0]
    ist = r['tcp'][:, :3]
    # ab 23.11. nachmittags: gesendetes Ziel (nach Tiefpass) im Log, sonst die Action
    q_soll = r['ziel'] if 'ziel' in r.files and np.isfinite(r['ziel']).all() else r['action'][:, :6]
    soll = np.array([fk(q) for q in q_soll])
    # Greifpunkt je Chunk = tiefster vorhergesagter Schritt
    gp = np.array([min((fk(q[:6]) for q in c), key=lambda v: v[2]) for c in r['pred_chunk']])
    h_i = (ist[:, 2] - pk[2]) * 1e3; h_s = (soll[:, 2] - pk[2]) * 1e3
    off_i = (ist[:, :2] - pk[:2]) * 1e3; off_s = (soll[:, :2] - pk[:2]) * 1e3; off_g = (gp[:, :2] - pk[:2]) * 1e3
    k = np.where(h_i <= 90)[0]; i0 = k[0] if len(k) else 0
    u = off_i[i0] / max(np.linalg.norm(off_i[i0]), 1e-9)
    al_i, al_s, al_g = off_i @ u, off_s @ u, off_g @ u
    h_g = (gp[:, 2] - pk[2]) * 1e3
    ax, bx = axes[row]
    for a_ in (ax, bx):
        a_.set_facecolor(SURF); a_.grid(color=GRID, lw=0.6); a_.set_axisbelow(True)
        for s_ in ('top', 'right'): a_.spines[s_].set_visible(False)
        for lo, hi, c in ((0, 20, '#efeeea'), (20, 50, '#f6f5f2'), (100, 150, '#f6f5f2')):
            a_.axhspan(lo, hi, color=c, zorder=0)
        a_.axhline(50, color=INK2, lw=1); a_.axhline(150, color=INK2, lw=1)
        a_.axhline(32, color='#d03b3b', lw=1, ls=(0, (4, 3)))
    ax.text(29, 51.5, 'PRE_PICK – Demos bremsen 150 → 20 mm/s', ha='right', fontsize=7.5, color=INK2)
    ax.text(29, 33.5, 'Höhengrenze (~32 mm)', ha='right', fontsize=7.5, color='#d03b3b')
    ax.fill_betweenx(mid, -p90, p90, color=BLUE, alpha=0.10, lw=0)
    ax.plot(p90, mid, color=BLUE, ls=(0, (5, 3)), lw=1.6, label='Demo-Trichter p90'); ax.plot(-p90, mid, color=BLUE, ls=(0, (5, 3)), lw=1.6)
    ax.plot(p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.2, label='Demo-Median'); ax.plot(-p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.2)
    ax.add_patch(plt.Rectangle((-2.5, -6.6), 5, 14.9, color='#cfcdc6', zorder=1))
    ax.axvline(0, color=INK2, lw=0.8)
    ax.plot(al_s, h_s, color=VIOLET, lw=1.5, ls=(0, (3, 2)), zorder=4, label='Soll (gesendetes Ziel, FK)')
    ax.plot(al_i, h_i, color=ORANGE, lw=2, zorder=5, label='Ist (gemessener TCP)')
    ax.plot(al_g, h_g, 'o', ms=4.5, mfc='none', mec=VIOLET, mew=1, zorder=4, label='Greifpunkt je Chunk (tiefster Schritt)')
    # Zeitmarken alle 0,5 s am Ist
    for tt in np.arange(0, t[-1], 0.5):
        j = np.argmin(np.abs(t - tt))
        if h_i[j] <= 155:
            ax.plot(al_i[j], h_i[j], '.', color=INK, ms=4, zorder=6)
    ax.plot(al_i[-1], h_i[-1], 'o', ms=7, color=ORANGE, mec=SURF, mew=1.5, zorder=7, label='Stopp')
    ax.set_xlim(-30, 30); ax.set_ylim(-7, 155)
    ax.set_ylabel('Höhe über PICK [mm]')
    alpha = (e.get('_alpha') if False else json.load(open(d + '/summary.json'))['args'].get('glaettung', 1.0)) if os.path.exists(d + '/summary.json') else None
    ax.set_title(f"{mod} {stamp[:5].replace('-', ':')}" + (f" – Glättung α {alpha:.2f}" if alpha is not None else "") + f" – Lage x {pk[0]*1e3:.0f} / y {pk[1]*1e3:.0f} mm, "
                 f"Stopp {np.linalg.norm(off_i[-1]):.1f} mm daneben", loc='left', color=INK, fontsize=10.5)
    # Tempo Ist und Soll
    dt = np.diff(t)
    v_i = np.r_[np.nan, np.linalg.norm(np.diff(ist, axis=0), axis=1) * 1e3 / dt]
    v_s = np.r_[np.nan, np.linalg.norm(np.diff(soll, axis=0), axis=1) * 1e3 / dt]
    bx.plot(dsp, mid, color=BLUE, lw=2, label='Demos 19.11. (Median)')
    bx.plot(v_s, h_s, color=VIOLET, lw=1.3, ls=(0, (3, 2)), label='Soll')
    bx.plot(v_i, h_i, color=ORANGE, lw=1.8, label='Ist')
    bx.set_xlim(0, 300)
    bx.set_title('Tempo gegen Höhe', loc='left', color=INK, fontsize=10.5)
    if row == 0:
        ax.legend(loc='upper left', fontsize=7.5, frameon=True, facecolor=SURF, edgecolor=GRID)
        bx.legend(loc='upper right', fontsize=7.5, frameon=True, facecolor=SURF, edgecolor=GRID)
    if row == len(RUNS) - 1:
        ax.set_xlabel('seitlicher Versatz zu PICK [mm]  (+ = Seite bei 90 mm Höhe, − = über die Mitte hinaus); Punkte = alle 0,5 s')
        bx.set_xlabel('TCP-Tempo [mm/s]')
    lag = np.linalg.norm(soll - ist, axis=1) * 1e3
    print(f"{spec}: Takte {len(t)}, Dauer {t[-1]:.1f} s, Soll-Ist median {np.median(lag):.1f} max {lag.max():.1f} mm, "
          f"Greifpunkt-xy letzter {np.linalg.norm(off_g[-1]):.1f} mm")
fig.tight_layout()
out = 'Berichte/abbildungen_2026-11-23/' + OUTNAME
fig.savefig(out, dpi=140, facecolor=SURF); print(out)
