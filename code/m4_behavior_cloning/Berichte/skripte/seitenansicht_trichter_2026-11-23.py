"""Seitenansicht Endanflug: Trichter der Demos gegen die Policy-Fahrten an der Anlage (23.11.).

Links: seitlicher Versatz zu PICK (vorzeichenbehaftet entlang der Richtung, in der die Fahrt bei 90 mm
daneben lag; positiv = Ausgangsseite, negativ = ueber die Mitte hinaus) gegen die Hoehe ueber PICK.
Rechts: TCP-Tempo gegen die Hoehe.
Demos: data_vm/2026-11-19-2 (gleiche Einstellungen wie der Trainingsdatensatz G2-G4, 20 mm/s) -- Ist-TCP.
Aufruf aus m4_behavior_cloning: python Berichte/skripte/seitenansicht_trichter_2026-11-23.py
"""
import glob, json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE, ORANGE = '#2a78d6', '#eb6834'
INK, INK2, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#8a8984', '#e4e3df', '#fcfcfb'
OUT = 'Berichte/abbildungen_2026-11-23'
os.makedirs(OUT, exist_ok=True)


def signed(xy_off, z, ref_h=90.0):
    """Versatz entlang der Richtung, in der die Fahrt bei ref_h (bzw. beim ersten Takt darunter) lag."""
    k = np.where(z <= ref_h)[0]
    i = k[0] if len(k) else 0
    u = xy_off[i] / max(np.linalg.norm(xy_off[i]), 1e-9)
    along = xy_off @ u
    perp = xy_off @ np.array([-u[1], u[0]])
    return along, perp


# Demos
demo = []
for f in sorted(glob.glob('data_vm/2026-11-19-2/ep_*/arrays.npz')) + sorted(glob.glob('data_vm/2026-11-23/ep_*/arrays.npz')):
    z_ = np.load(f); m = json.load(open(os.path.join(os.path.dirname(f), 'meta.json')))['metadata']
    s = z_['observation__state']; g = np.where(z_['action'][:, 6] > 0.5)[0][0]
    pk = np.array(m['object_pose']['PICK'][:3]); p = s[:g + 1, 6:9].astype(float)
    off = (p[:, :2] - pk[:2]) * 1e3; h = (p[:, 2] - pk[2]) * 1e3
    sp = np.r_[np.nan, np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 * 15]
    demo.append((off, h, sp if '2026-11-19-2' in f else np.full_like(sp, np.nan)))

# Policy
pol = []
for f in sorted(glob.glob('checkpoints/G*/policy/rollouts/2026-11-23_*/rollout_000.npz')):
    d = os.path.dirname(f); e = json.load(open(d + '/summary.json'))['episodes'][0]
    if not e['stop_reason'].startswith(('kollision vorab', 'stopp: [Viol')):
        continue
    r = np.load(f); pk = np.array(e['lage']['pick'][:3]); p = r['tcp'][:, :3]
    off = (p[:, :2] - pk[:2]) * 1e3; h = (p[:, 2] - pk[2]) * 1e3
    sp = np.r_[np.nan, np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 / np.diff(r['t'])]
    sp = np.convolve(np.nan_to_num(sp, nan=sp[1]), np.ones(3) / 3, mode='same')
    name = d.split(os.sep)[-4][:2] + ' ' + os.path.basename(d)[11:16].replace('-', ':')
    pol.append((off, h, sp, name))

# Trichter der Demos: |Versatz| p50 / p90 je 5-mm-Hoehenklasse
edges = np.arange(0, 160, 10); mid = edges[:-1] + 5.0
allr = np.concatenate([np.linalg.norm(o, axis=1) for o, h, s in demo]); allh = np.concatenate([h for o, h, s in demo])
allsp = np.concatenate([s for o, h, s in demo])
p50 = np.array([np.median(allr[(allh >= a) & (allh < b)]) if ((allh >= a) & (allh < b)).any() else np.nan for a, b in zip(edges[:-1], edges[1:])])
p90 = np.array([np.percentile(allr[(allh >= a) & (allh < b)], 90) if ((allh >= a) & (allh < b)).any() else np.nan for a, b in zip(edges[:-1], edges[1:])])
dsp = np.array([np.nanmedian(allsp[(allh >= a) & (allh < b)]) if ((allh >= a) & (allh < b)).any() else np.nan for a, b in zip(edges[:-1], edges[1:])])

# Statistik Ueberschiessen
stats = []
for off, h, sp, name in pol:
    k = h <= 90
    along, perp = signed(off, h)
    a = along[k]
    cross = int(np.sum(np.diff(np.sign(a[np.abs(a) > 1.0])) != 0))
    stats.append((name, a[0] if len(a) else np.nan, a.min() if len(a) else np.nan, cross, np.abs(perp[k]).max() if k.any() else np.nan,
                  np.linalg.norm(off[-1]), h[-1]))

plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK2, 'xtick.color': INK2,
                     'ytick.color': INK2, 'font.family': 'DejaVu Sans'})
fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 7), sharey=True, gridspec_kw={'width_ratios': [1.6, 1]}, facecolor=SURF)
for a_ in (ax, bx):
    a_.set_facecolor(SURF); a_.grid(color=GRID, lw=0.6); a_.set_axisbelow(True)
    for sp_ in ('top', 'right'): a_.spines[sp_].set_visible(False)

# Zonen (Hoehe ueber PICK), Planer: ANFLUG 150, PRE_PICK 50, Versatz voll 50-100, null unter 20
zones = [(0, 20, 'Versatz + Rauschen = 0\n(Demos exakt mittig)', '#efeeea'),
         (20, 50, 'Versatz klingt ab, Rauschen < 1 mm\nEndanflug 20 mm/s', '#f6f5f2'),
         (50, 100, 'Versatz voll (5–10 mm)\nTransit 150 mm/s, Trichter dämpft', SURF),
         (100, 150, 'Versatz baut auf\nTransit 150 mm/s', '#f6f5f2')]
for lo, hi, txt, c in zones:
    for a_ in (ax, bx): a_.axhspan(lo, hi, color=c, zorder=0)
    ax.text(-29, (lo + hi) / 2, txt, va='center', ha='left', fontsize=7.5, color=INK2, bbox=dict(fc=SURF, ec='none', alpha=0.85, pad=1.5), zorder=6)
for y, lab in ((150, 'ANFLUG'), (50, 'PRE_PICK – Bremsen 150 → 20 mm/s'), (32, 'Höhengrenze Policy-Test (~32 mm)')):
    for a_ in (ax, bx): a_.axhline(y, color=INK2 if y != 32 else '#d03b3b', lw=1, ls='-' if y != 32 else (0, (4, 3)), zorder=2)
    ax.text(29, y + 1.5, lab, ha='right', va='bottom', fontsize=7.5, color=INK2 if y != 32 else '#d03b3b')
# Objekt und Spiel je Backe
ax.add_patch(plt.Rectangle((-2.5, -6.6), 5, 6.6 + 8.3, color='#cfcdc6', zorder=1))
ax.text(0, 4, 'Spiel je\nBacke\n±2,5 mm', ha='center', va='center', fontsize=6.5, color=INK)

# Trichter
ax.fill_betweenx(mid, -p90, p90, color=BLUE, alpha=0.10, lw=0, zorder=2)
ax.plot(p90, mid, color=BLUE, ls=(0, (5, 3)), lw=2, zorder=3, label='Demos 19.11. + 23.11. (33): Trichter, p90 |Versatz|')
ax.plot(-p90, mid, color=BLUE, ls=(0, (5, 3)), lw=2, zorder=3)
ax.plot(p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.5, zorder=3, label='Demos: Median |Versatz|')
ax.plot(-p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.5, zorder=3)
# Policy
for i, (off, h, sp, name) in enumerate(pol):
    along, perp = signed(off, h)
    k = h <= 155
    ax.plot(along[k], h[k], color=ORANGE, lw=1.2, alpha=0.75, zorder=4, label='Policy-Fahrten Anlage 23.11. (G2/G3/G4, 20)' if i == 0 else None)
    ax.plot(along[-1], h[-1], 'o', ms=6, color=ORANGE, mec=SURF, mew=1.5, zorder=5,
            label='Stopp an der Höhengrenze' if i == 0 else None)
ax.axvline(0, color=INK2, lw=0.8, zorder=2)
ax.set_xlim(-30, 30); ax.set_ylim(-7, 155)
ax.set_xlabel('seitlicher Versatz zu PICK [mm]  (+ = Seite, auf der die Fahrt bei 90 mm lag, − = über die Mitte hinaus)')
ax.set_ylabel('Höhe TCP über PICK [mm]')
ax.set_title('Seitenansicht: Demo-Trichter gegen Policy', loc='left', color=INK, fontsize=11)
ax.legend(loc='upper left', bbox_to_anchor=(0, -0.08), ncol=2, frameon=False, fontsize=8)

# Tempo
bx.plot(dsp, mid, color=BLUE, lw=2, label='Demos 19.11. (20 mm/s): Tempo, Median', zorder=3)
for i, (off, h, sp, name) in enumerate(pol):
    k = h <= 155
    bx.plot(sp[k], h[k], color=ORANGE, lw=1, alpha=0.6, zorder=2, label='Policy-Fahrten (über 3 Takte geglättet)' if i == 0 else None)
bx.set_xlim(0, 300); bx.set_xlabel('TCP-Tempo [mm/s]')
bx.set_title('Tempo gegen Höhe', loc='left', color=INK, fontsize=11)
bx.legend(loc='upper left', bbox_to_anchor=(0, -0.08), frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig(OUT + '/seitenansicht_trichter.png', dpi=150, facecolor=SURF)

print('Fahrt     Versatz@90  min(along)  Mitte-Kreuzungen  quer max  |xy| Stopp  Hoehe Stopp')
for s in stats:
    print('%-9s %7.1f %10.1f %10d %14.1f %9.1f %9.1f' % s)
print('Demos Trichter p90/p50 je Hoehe:', ' '.join('%d:%.1f/%.1f' % (m_, a, b) for m_, a, b in zip(mid[::2], p90[::2], p50[::2])))
