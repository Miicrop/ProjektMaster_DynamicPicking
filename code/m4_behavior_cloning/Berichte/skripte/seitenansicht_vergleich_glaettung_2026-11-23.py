"""Seitenansicht im Vergleich: ohne Glaettung (Vormittag) gegen alpha 0,5 und 0,25 (ab 16 Uhr, viele Lagen).

Gleiche Darstellung wie seitenansicht_trichter_2026-11-23.py (Demo-Trichter, seitlicher Versatz gegen Hoehe,
rechts Tempo), eine Zeile je Gruppe, gleiche Achsen:
  1. Vormittag 11:41-12:00, G2/G3/G4, ohne Glaettung (die 20 Fahrten der ersten Grafik)
  2. ab 16:00, G2, alpha 0,5  (Probegriff objekt, Experte legt um)
  3. ab 16:00, G2, alpha 0,25 (dito, dazu Probeabstand 7/4/1 mm)
alpha je Episode aus dem Log geschaetzt (ziel gegen action); Griffversuche (Probegriff tisch) und
Fahrten ohne Bewegung ("arm steht") sind nicht dabei.
Aufruf aus m4_behavior_cloning: python Berichte/skripte/seitenansicht_vergleich_glaettung_2026-11-23.py
"""
import glob, json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE, ORANGE = '#2a78d6', '#eb6834'
INK, INK2, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#8a8984', '#e4e3df', '#fcfcfb'
OUT = 'Berichte/abbildungen_2026-11-23/seitenansicht_vergleich_glaettung.png'
VALID = ('kollision vorab', 'stopp: [Viol')


def signed(off, h, ref_h=90.0):
    k = np.where(h <= ref_h)[0]
    i = k[0] if len(k) else 0
    u = off[i] / max(np.linalg.norm(off[i]), 1e-9)
    return off @ u


def alpha_est(r):
    if 'ziel' not in r.files:
        return 1.0
    z, a = r['ziel'], r['action'][:, :6]
    x = (a[1:] - z[:-1]).ravel(); y = (z[1:] - z[:-1]).ravel()
    return round(float(x @ y / (x @ x)), 2) if x @ x > 0 else 1.0


def episodes(since, until):
    """(alpha, off, h, sp) je gueltiger Probe-Episode im Zeitfenster [since, until)."""
    out = []
    for d in sorted(glob.glob('checkpoints/*/policy/rollouts/2026-11-23_*')):
        stamp = os.path.basename(d)[11:]
        if not since <= stamp < until:
            continue
        S = json.load(open(d + '/summary.json')) if os.path.exists(d + '/summary.json') else None
        stops = {}
        if S:
            stops = {i: e['stop_reason'] for i, e in enumerate(S['episodes'])}
        elif os.path.exists(d + '/policy_test.csv'):
            import csv
            with open(d + '/policy_test.csv', encoding='utf-8') as fh:
                stops = {i: row.get('stopp', '') for i, row in enumerate(csv.DictReader(fh, delimiter=';'))}
        for f in sorted(glob.glob(d + '/rollout_*.npz')):
            i = int(os.path.basename(f)[8:11])
            if not str(stops.get(i, '')).startswith(VALID):
                continue
            r = np.load(f)
            pk = r['lage_pick'][:3] if 'lage_pick' in r.files else np.array(S['episodes'][i]['lage']['pick'][:3])
            p = r['tcp'][:, :3]
            off = (p[:, :2] - pk[:2]) * 1e3
            h = (p[:, 2] - pk[2]) * 1e3
            sp = np.r_[np.nan, np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 / np.diff(r['t'])]
            sp = np.convolve(np.nan_to_num(sp, nan=sp[1]), np.ones(3) / 3, mode='same')
            out.append((alpha_est(r), off, h, sp))
    return out


# Demo-Trichter (33 Demos, wie Berichtsgrafik)
allr, allh, allsp = [], [], []
for f in sorted(glob.glob('data_vm/2026-11-19-2/ep_*/arrays.npz')) + sorted(glob.glob('data_vm/2026-11-23/ep_*/arrays.npz')):
    z_ = np.load(f); m = json.load(open(os.path.join(os.path.dirname(f), 'meta.json')))['metadata']
    s = z_['observation__state']; g = np.where(z_['action'][:, 6] > 0.5)[0][0]
    pk = np.array(m['object_pose']['PICK'][:3]); p = s[:g + 1, 6:9].astype(float)
    allr.append(np.linalg.norm(p[:, :2] - pk[:2], axis=1) * 1e3); allh.append((p[:, 2] - pk[2]) * 1e3)
    v = np.r_[np.nan, np.linalg.norm(np.diff(p, axis=0), axis=1) * 1e3 * 15]
    allsp.append(v if '2026-11-19-2' in f else np.full_like(v, np.nan))
allr, allh, allsp = map(np.concatenate, (allr, allh, allsp))
edges = np.arange(0, 160, 10); mid = edges[:-1] + 5
def binstat(v, fn):
    return np.array([fn(v[(allh >= a) & (allh < b)]) for a, b in zip(edges[:-1], edges[1:])])
p90 = binstat(allr, lambda x: np.percentile(x, 90)); p50 = binstat(allr, np.median)
dsp = binstat(allsp, np.nanmedian)

morning = [e for e in episodes('11-40', '12-05')]
afternoon = episodes('16-00', '16-42')
groups = [
    ('Ohne Glättung (α 1,0) – Vormittag, G2/G3/G4, 4 Lagen', morning),
    ('Glättung α 0,5 – G2, viele Lagen', [e for e in afternoon if abs(e[0] - 0.5) < 0.05]),
    ('Glättung α 0,25 – G2, viele Lagen', [e for e in afternoon if abs(e[0] - 0.25) < 0.05]),
]

plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK2, 'xtick.color': INK2,
                     'ytick.color': INK2, 'font.family': 'DejaVu Sans'})
fig, axes = plt.subplots(len(groups), 2, figsize=(12, 6.2 * len(groups)), sharey=True,
                         gridspec_kw={'width_ratios': [1.6, 1]}, facecolor=SURF)
for row, (title, eps) in enumerate(groups):
    ax, bx = axes[row]
    for a_ in (ax, bx):
        a_.set_facecolor(SURF); a_.grid(color=GRID, lw=0.6); a_.set_axisbelow(True)
        for s_ in ('top', 'right'):
            a_.spines[s_].set_visible(False)
        for lo, hi, c in ((0, 20, '#efeeea'), (20, 50, '#f6f5f2'), (100, 150, '#f6f5f2')):
            a_.axhspan(lo, hi, color=c, zorder=0)
        a_.axhline(50, color=INK2, lw=1); a_.axhline(150, color=INK2, lw=1)
    ax.text(29, 51.5, 'PRE_PICK – Demos bremsen 150 → 20 mm/s', ha='right', fontsize=7.5, color=INK2)
    ax.fill_betweenx(mid, -p90, p90, color=BLUE, alpha=0.10, lw=0)
    ax.plot(p90, mid, color=BLUE, ls=(0, (5, 3)), lw=1.8, label='Demo-Trichter p90 |Versatz|')
    ax.plot(-p90, mid, color=BLUE, ls=(0, (5, 3)), lw=1.8)
    ax.plot(p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.3, label='Demo-Median')
    ax.plot(-p50, mid, color=BLUE, ls=(0, (1, 2)), lw=1.3)
    ax.add_patch(plt.Rectangle((-2.5, -6.6), 5, 14.9, color='#cfcdc6', zorder=1))
    ax.axvline(0, color=INK2, lw=0.8)
    stops = []
    for j, (a, off, h, sp) in enumerate(eps):
        al = signed(off, h)
        k = h <= 155
        ax.plot(al[k], h[k], color=ORANGE, lw=1.1, alpha=0.7, zorder=4,
                label='Policy-Fahrten (%d)' % len(eps) if j == 0 else None)
        ax.plot(al[-1], h[-1], 'o', ms=5, color=ORANGE, mec=SURF, mew=1.2, zorder=5,
                label='Stopp an der Höhengrenze' if j == 0 else None)
        bx.plot(sp[k], h[k], color=ORANGE, lw=0.9, alpha=0.55, zorder=2,
                label='Policy-Fahrten' if j == 0 else None)
        stops.append(np.linalg.norm(off[-1]))
    bx.plot(dsp, mid, color=BLUE, lw=2, zorder=3, label='Demos 19.11. (Median)')
    ax.set_xlim(-30, 30); ax.set_ylim(-7, 155); bx.set_xlim(0, 300)
    ax.set_ylabel('Höhe TCP über PICK [mm]')
    ax.set_title('%s – Stopp median %.1f mm neben PICK' % (title, np.median(stops) if stops else np.nan),
                 loc='left', color=INK, fontsize=10.5)
    bx.set_title('Tempo gegen Höhe', loc='left', color=INK, fontsize=10.5)
    if row == 0:
        ax.legend(loc='upper left', fontsize=7.5, frameon=True, facecolor=SURF, edgecolor=GRID)
        bx.legend(loc='upper right', fontsize=7.5, frameon=True, facecolor=SURF, edgecolor=GRID)
    if row == len(groups) - 1:
        ax.set_xlabel('seitlicher Versatz zu PICK [mm]  (+ = Seite bei 90 mm Höhe, − = über die Mitte hinaus)')
        bx.set_xlabel('TCP-Tempo [mm/s] (über 3 Takte geglättet)')
    print('%s: %d Fahrten, Stopp median %.1f mm' % (title, len(eps), np.median(stops) if stops else np.nan))
fig.tight_layout()
fig.savefig(OUT, dpi=140, facecolor=SURF)
print(OUT)
