"""Auswertung von empfindlichkeit.py: Tabelle + Abbildung nach Phase.

    python auswertung.py <daten-ordner> <abbildungen-ordner>
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PHASEN = [("Anflug > 100 mm", 100, 1e9), ("100–50 mm", 50, 100),
          ("50–20 mm", 20, 50), ("letzte 20 mm", -1e9, 20)]
VARIANTEN = [("scene_dx10", "Szene 10 px quer"), ("scene_dy10", "Szene 10 px längs"),
             ("scene_rot5", "Szene 5° gedreht"), ("scene_aus", "Szene ausgeblendet"),
             ("wrist_aus", "Handgelenk ausgeblendet")]
BEZUG = [("rauschen", "anderes Rauschen"), ("label", "Abstand zur Aufnahme")]
FARBEN = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK2, MUTED, GRID, AXIS = "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
IDX = 1          # Chunk-Index 7 (Ende der ausgefuehrten Aktionen)

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
    "figure.facecolor": "white", "axes.facecolor": "#fcfcfb",
})


def main():
    rows = json.loads((Path(sys.argv[1]) / "takte.json").read_text(encoding="utf-8"))
    dst = Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    gruppen = [("val", "Validierung Trainingstage"), ("neu", "neuer Tag 11.11.")]
    table = {}
    lines = ["| Herkunft | Phase | Takte | " + " | ".join(l for _, l in VARIANTEN + BEZUG) + " |",
             "|---|---|---:|" + "---:|" * (len(VARIANTEN) + len(BEZUG))]
    for g, gname in gruppen:
        for pname, lo, hi in PHASEN:
            sel = [r for r in rows if r["herkunft"].startswith(g) and lo <= r["hoehe_mm"] < hi]
            cells = []
            for key, _ in VARIANTEN + BEZUG:
                v = np.array([r[key][IDX] for r in sel]) if sel else np.array([np.nan])
                med, p90 = float(np.median(v)), float(np.percentile(v, 90))
                table[(g, pname, key)] = (med, p90, len(sel))
                cells.append("%.1f (%.1f)" % (med, p90))
            lines.append("| %s | %s | %d | %s |" % (gname, pname, len(sel), " | ".join(cells)))
    episodes = {(r["herkunft"], r["root"], r["episode"]) for r in rows}
    head = ("Median (p90) der waagrechten TCP-Änderung in mm am Ende der ausgeführten Aktionen "
            "(Chunk-Index 7), %d Takte aus %d Episoden." % (len(rows), len(episodes)))
    (dst / "tabelle.md").write_text(head + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(head)
    print("\n".join(lines))

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    x = np.arange(len(PHASEN))
    for ax, (g, gname) in zip(axes, gruppen):
        for k, (key, label) in enumerate(VARIANTEN):
            y = [table[(g, p, key)][0] for p, _, _ in PHASEN]
            ax.plot(x, y, color=FARBEN[k], lw=2, marker="o", ms=4, label=label)
        y = [table[(g, p, "label")][0] for p, _, _ in PHASEN]
        ax.plot(x, y, color=INK2, lw=1.2, ls="--", label="Abstand zur Aufnahme")
        y = [table[(g, p, "rauschen")][0] for p, _, _ in PHASEN]
        ax.plot(x, y, color=MUTED, lw=1.2, ls=":", label="anderes Rauschen")
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace(" ", "\n", 1) for p, _, _ in PHASEN], fontsize=7.5)
        ax.set_title(gname, fontsize=9)
        ax.set_ylim(0, 20)
    axes[0].set_ylabel("Änderung der Vorhersage, Median [mm]")
    axes[1].legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(dst / "empfindlichkeit.png", dpi=170, bbox_inches="tight")
    print("Bild:", dst / "empfindlichkeit.png")


if __name__ == "__main__":
    main()
