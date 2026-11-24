"""Anlagentest var_C2 vom 2026-11-16: Kennzahlen und Abbildungen.

    python skripte/auswertung.py <rollouts-ordner> <ausgabe-ordner>

Liest alle Laeufe 2026-11-16_* (summary.json, rollout_*.npz, experte_*.npz)
und schreibt fahrten.csv, hoehe.csv sowie die PNGs versatz_hoehe.png,
draufsicht.png, abstieg_beispiel.png.
"""
import csv
import glob
import json
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Referenzpalette (dataviz, light), feste Reihenfolge je Lage
FARBEN = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
HOEHEN_MM = (100, 60, 40, 30, 20, 15, 10)

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
    "figure.facecolor": "white", "axes.facecolor": "#fcfcfb",
})


def lage_name(pick):
    return "x %.0f / y %.0f" % (1e3 * pick[0], 1e3 * pick[1])


def laeufe(root):
    out = []
    for d in sorted(glob.glob(os.path.join(root, "2026-11-16_*"))):
        sj = os.path.join(d, "summary.json")
        if not os.path.exists(sj):
            continue
        s = json.load(open(sj, encoding="utf-8"))
        for ep in s["episodes"]:
            if not ep.get("lage"):
                continue
            z = np.load(os.path.join(d, "rollout_%03d.npz" % ep["episode"]))
            tcp = np.vstack([z["tcp"], z["final_tcp"][None]])
            out.append(dict(lauf=os.path.basename(d)[11:], ep=ep["episode"], s=ep, z=z, tcp=tcp,
                            pick=z["lage_pick"], dz=z["lage_dz_pick"], yaw=z["lage_yaw_err"]))
    return out


def main():
    root, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    runs = laeufe(root)
    lagen = []
    for r in runs:
        key = tuple(np.round(r["pick"][:2], 3))
        if key not in lagen:
            lagen.append(key)
        r["lage_i"] = lagen.index(key)

    # --- Tabellen ---------------------------------------------------------
    with open(os.path.join(dst, "fahrten.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["lauf", "fahrt", "lage", "probegriff", "stopp", "stopp_dz_mm", "stopp_dx_mm",
                    "stopp_dy_mm", "stopp_xy_mm", "stopp_yaw_grad", "vorh_dx_mm", "vorh_dy_mm",
                    "vorh_xy_mm", "vorh_yaw_grad", "vorh_schliesst", "korr_dx_mm", "korr_dy_mm",
                    "korr_xy_mm", "korr_yaw_grad", "erfolg_gezaehlt"])
        for r in runs:
            lage, ex = r["s"]["lage"], r["s"].get("experte") or {}
            d = 1e3 * (r["tcp"][-1, :2] - r["pick"][:2])
            pr = lage.get("predicted")
            pd = 1e3 * (np.array(pr["pose"][:2]) - r["pick"][:2]) if pr else (np.nan, np.nan)
            c = ex.get("correction") or {}
            w.writerow([r["lauf"], r["ep"], lage_name(r["pick"]), lage["probe"],
                        r["s"]["stop_reason"][:60], "%.1f" % (1e3 * r["dz"][-1]),
                        "%.1f" % d[0], "%.1f" % d[1], "%.1f" % np.hypot(*d), "%.1f" % r["yaw"][-1],
                        "%.1f" % pd[0], "%.1f" % pd[1], "%.1f" % np.hypot(*pd),
                        "%.1f" % pr["yaw_deg"] if pr else "", pr["closes"] if pr else "",
                        "%.1f" % (1e3 * c["dx_m"]) if c else "", "%.1f" % (1e3 * c["dy_m"]) if c else "",
                        "%.1f" % (1e3 * c["xy_m"]) if c else "", "%.1f" % c["yaw_deg"] if c else "",
                        r["s"]["success"]])
    with open(os.path.join(dst, "hoehe.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["lauf", "fahrt"] + ["xy_mm_bei_dz_%d" % h for h in HOEHEN_MM])
        for r in runs:
            vals = []
            for h in HOEHEN_MM:
                idx = np.flatnonzero(r["dz"] <= h / 1e3)
                vals.append("%.1f" % (1e3 * np.hypot(*(r["tcp"][idx[0], :2] - r["pick"][:2])))
                            if idx.size else "")
            w.writerow([r["lauf"], r["ep"]] + vals)

    # --- Abb. 1: Versatz ueber der Hoehe ----------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    shown = set()
    for r in runs:
        dz = 1e3 * r["dz"]
        xy = 1e3 * np.hypot(*(r["tcp"][:, :2] - r["pick"][:2]).T)
        m = dz <= 120
        i = r["lage_i"]
        lbl = None if i in shown else "Lage %d (%s)" % (i + 1, lage_name(r["pick"]))
        shown.add(i)
        ax.plot(dz[m], xy[m], color=FARBEN[i], lw=1.6, label=lbl, solid_capstyle="round")
        ax.plot(dz[m][-1], xy[m][-1], "o", ms=5, color=FARBEN[i], mec="white", mew=1.2)
    ax.axhline(10, color=INK2, lw=0.9, ls="--")
    ax.text(119, 10.6, "10 mm (Erfolgskriterium)", color=INK2, fontsize=8, ha="left")
    ax.axvspan(0, 30, color=GRID, alpha=0.45, lw=0)
    ax.text(15, 0.8, "letzte 30 mm", color=INK2, fontsize=8, ha="center")
    ax.set_xlim(120, 0)
    ax.set_ylim(0, 30)
    ax.set_xlabel("Höhe des TCP über PICK [mm]  (Abstieg →)")
    ax.set_ylabel("waagrechter Versatz zu PICK [mm]")
    ax.legend(fontsize=7.5, loc="upper left", ncol=1)
    fig.tight_layout()
    fig.savefig(os.path.join(dst, "versatz_hoehe.png"), dpi=170)
    plt.close(fig)

    # --- Abb. 2: Draufsicht im PICK-Koordinatensystem ---------------------
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(10 * np.cos(t), 10 * np.sin(t), color=INK2, lw=0.9, ls="--")
    ax.text(7.4, -8.6, "10 mm", color=INK2, fontsize=8)
    for r in runs:
        i = r["lage_i"]
        m = r["dz"] <= 0.06
        d = 1e3 * (r["tcp"][m, :2] - r["pick"][:2])
        ax.plot(d[:, 0], d[:, 1], color=FARBEN[i], lw=1.0, alpha=0.75)
        ax.plot(d[-1, 0], d[-1, 1], "o", ms=6, color=FARBEN[i], mec="white", mew=1.2)
        pr = r["s"]["lage"].get("predicted")
        if pr:
            p = 1e3 * (np.array(pr["pose"][:2]) - r["pick"][:2])
            ax.plot(p[0], p[1], "X", ms=8, color=FARBEN[i], mec="white", mew=1.0)
    ax.plot(0, 0, "+", ms=14, mew=1.6, color=INK)
    ax.set_aspect("equal")
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
    ax.set_xlabel("dx Basis-KS [mm]")
    ax.set_ylabel("dy Basis-KS [mm]")
    from matplotlib.lines import Line2D
    hand = [Line2D([], [], color=FARBEN[k], lw=2, label="Lage %d" % (k + 1)) for k in range(len(lagen))]
    hand += [Line2D([], [], color=MUTED, marker="o", ls="", label="Stopp (gemessen)"),
             Line2D([], [], color=MUTED, marker="X", ls="", ms=8, label="vorhergesagter Griff"),
             Line2D([], [], color=INK, marker="+", ls="", ms=12, label="PICK")]
    ax.legend(handles=hand, fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(os.path.join(dst, "draufsicht.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)

    # --- Abb. 3: Beispiel letzter Abstieg (dx, dy ueber Takt) -------------
    beispiele = [r for r in runs if (r["lauf"], r["ep"]) in (("12-55-03", 1), ("12-44-44", 0))]
    fig, axes = plt.subplots(1, len(beispiele), figsize=(7.2, 2.8), sharey=True)
    for ax, r in zip(np.atleast_1d(axes), beispiele):
        n = len(r["tcp"])
        k = np.arange(n)
        m = r["dz"] <= 0.10
        d = 1e3 * (r["tcp"][:, :2] - r["pick"][:2])
        ax.plot(k[m], d[m, 0], color=FARBEN[0], lw=1.8, label="dx")
        ax.plot(k[m], d[m, 1], color=FARBEN[1], lw=1.8, label="dy")
        ax2 = ax.twinx()
        ax2.set_visible(False)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.set_title("Lauf %s, Fahrt %d" % (r["lauf"], r["ep"]), fontsize=9, color=INK)
        ax.set_xlabel("Takt (≈ 14 Hz)")
        for j in np.flatnonzero(m)[::4]:
            ax.annotate("%.0f" % (1e3 * r["dz"][j]), (k[j], -27), fontsize=6.5, color=MUTED,
                        ha="center")
        ax.set_ylim(-30, 30)
    np.atleast_1d(axes)[0].set_ylabel("Versatz zu PICK [mm]")
    np.atleast_1d(axes)[0].legend(fontsize=7.5, loc="upper left")
    fig.text(0.5, 0.005, "graue Zahlen: Höhe über PICK [mm]", ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(dst, "abstieg_beispiel.png"), dpi=170)
    plt.close(fig)
    print("geschrieben:", dst)


if __name__ == "__main__":
    main()
