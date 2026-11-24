"""Bild: Welligkeit/Querabweichung gegen Rauschfaktor der eingespielten Aufnahme, Zeit- vs. Positionswahl.

Aufruf: schwingbild.py <zielordner>
"""
import sys, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning\checkpoints\2026-11-09\policy\rollouts")
out = Path(sys.argv[1])
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
C1, C2 = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False})
zeit = json.loads((R / "2026-11-13_vm_replay_daten-2026-11-11" / "schwingen.json").read_text(encoding="utf-8"))
pos = json.loads((R / "2026-11-13_vm_replay_positionswahl" / "schwingen.json").read_text(encoding="utf-8"))
fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.7))
for a, key, title in ((ax[0], "amp_fahrt_mm", "Querabweichung zur idealen Bahn (p95, Anflug)"),
                      (ax[1], "welligkeit_mm", "Welligkeit (p95, ohne 1-s-Mittel)")):
    a.scatter([r["noise"] for r in zeit], [r[key] for r in zeit], s=8, color=C1, label="Bild je Takt (infer --replay)")
    a.scatter([r["noise"] for r in pos], [r[key] for r in pos], s=14, color=C2, marker="D", label="Bild nach Position")
    ref = "amp_aufn_mm" if key == "amp_fahrt_mm" else "welligkeit_aufn_mm"
    xs = np.array([r["noise"] for r in zeit]); ys = np.array([r[ref] for r in zeit])
    o = np.argsort(xs)
    a.plot(xs[o], np.convolve(ys[o], np.ones(15) / 15, mode="same"), color=INK2, lw=1, ls="--",
           label="Aufnahme selbst (gleitend)")
    a.set_xlabel("Rauschfaktor der eingespielten Aufnahme"); a.set_ylabel("mm")
    a.set_title(title, fontsize=8.5, color=INK, loc="left"); a.set_ylim(0, None)
ax[0].legend(frameon=False, fontsize=6.5, loc="upper left")
fig.tight_layout(); fig.savefig(out / "schwingen.png", dpi=160, bbox_inches="tight"); plt.close(fig)
print(out / "schwingen.png")
