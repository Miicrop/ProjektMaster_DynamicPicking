"""Bilder fuer das Testprotokoll: Draufsicht Greifpunkte, Greiffehler, Tischabstand.

Aufruf: bilder.py <auswertung.json> <data1111.json> <zielordner>
"""
import sys, os, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa
from bc import replay, config

rows = json.load(open(sys.argv[1], encoding="utf-8"))
cov = json.load(open(sys.argv[2], encoding="utf-8"))
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
run = Path(sys.argv[4]) if len(sys.argv) > 4 else None

C_OK, C_MID, C_BAD = "#1baf7a", "#eb9b34", "#d03b3b"
INK, INK2, GRID, GREY = "#0b0b0b", "#52514e", "#e4e3df", "#c9c8c3"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False})


def cat(e):
    return C_OK if e <= 10 else (C_MID if e <= 20 else C_BAD)


ok = [r for r in rows if r["grasp_xy_mm"] is not None]

# 1) Draufsicht
pick = {}
for r in rows:
    meta = json.loads((replay.episode_dir("data/2026-11-11", r["episode"]) / "meta.json").read_text(encoding="utf-8"))
    pick[r["lauf"]] = np.asarray(meta["metadata"]["object_pose"]["PICK"][:2]) * 1000
T = np.asarray(cov["train_xy"]) * 1000
fig, ax = plt.subplots(figsize=(7.2, 5.4))
ax.plot(T[:, 0], T[:, 1], ".", color=GREY, markersize=3, label="PICK der Trainingsepisoden")
for r in ok:
    p = pick[r["lauf"]]
    tcp = np.load(run / ("rollout_%03d.npz" % r["lauf"]))["tcp"] if run else None
    if tcp is None:
        continue
    k = min(r["grasp_step"] + 1, len(tcp) - 1)
    g = tcp[k, :2] * 1000
    c = cat(r["grasp_xy_mm"])
    ax.annotate("", xy=g, xytext=p, arrowprops=dict(arrowstyle="-|>", color=c, lw=1.0, mutation_scale=7))
    ax.plot(*p, "o", mfc="none", mec=INK2, markersize=4, mew=0.7)
for c, l in ((C_OK, "Greifpunkt <= 10 mm daneben"), (C_MID, "10-20 mm"), (C_BAD, "> 20 mm")):
    ax.plot([], [], "-", color=c, label=l)
ax.plot([], [], "o", mfc="none", mec=INK2, label="PICK der Aufnahme 11.11.")
ax.set_xlabel("x [mm]"); ax.set_ylabel("y [mm]"); ax.set_aspect("equal", adjustable="box")
ax.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
ax.set_title("Draufsicht: PICK -> Greifpunkt der Policy (Pfeile 1:1)", fontsize=9, color=INK, loc="left")
fig.savefig(out / "draufsicht.png", dpi=160, bbox_inches="tight"); plt.close(fig)

# 2) Greiffehler und Tischabstand je Fahrt, sortiert
fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.8))
e = np.sort([r["grasp_xy_mm"] for r in ok])
ax[0].scatter(np.arange(len(e)), e, s=9, c=[cat(v) for v in e])
ax[0].axhline(np.median(e), color=INK2, lw=0.8, ls="--")
ax[0].text(1, np.median(e) + 0.5, "Median %.1f mm" % np.median(e), color=INK2, fontsize=7, va="bottom")
ax[0].set_ylabel("Greifpunkt xy daneben [mm]"); ax[0].set_xlabel("Fahrten, sortiert")
ax[0].set_title("Greifgenauigkeit (gegen PICK)", fontsize=9, color=INK, loc="left")
mc = np.sort([r["min_clear_mm"] for r in rows])
ax[1].scatter(np.arange(len(mc)), mc, s=9, c=[C_BAD if v < 0 else (C_MID if v < 3 else C_OK) for v in mc])
ax[1].axhline(0, color=INK, lw=0.9)
ax[1].axhline(3, color=INK2, lw=0.7, ls=":")
rec = np.median([r["rec_min_clear_mm"] for r in rows])
ax[1].axhline(rec, color=INK2, lw=0.7, ls="--")
ax[1].text(0.98, 0.04, "durchgezogen: Tischflaeche\npunktiert: 3 mm Mindestabstand\ngestrichelt: Aufnahme (%.1f mm)" % rec,
           transform=ax[1].transAxes, ha="right", va="bottom", color=INK2, fontsize=6.5)
ax[1].set_ylabel("tiefster TCP ueber Tisch [mm]"); ax[1].set_xlabel("Fahrten, sortiert")
ax[1].set_title("Tischabstand (ganze Fahrt)", fontsize=9, color=INK, loc="left")
fig.tight_layout(); fig.savefig(out / "fehler_und_tisch.png", dpi=160, bbox_inches="tight"); plt.close(fig)

# 3) Fehler gegen Lage (x) und Drehung
fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.6), sharey=True)
xs = np.array([pick[r["lauf"]][0] for r in ok]); ev = np.array([r["grasp_xy_mm"] for r in ok])
yaw = np.array([r.get("yaw_obj", np.nan) for r in ok], dtype=float)
ax[0].scatter(xs, ev, s=9, c=[cat(v) for v in ev]); ax[0].set_xlabel("PICK x [mm] (Abstand vom Roboter)")
ax[0].set_ylabel("Greifpunkt xy daneben [mm]")
ax[1].scatter(yaw, ev, s=9, c=[cat(v) for v in ev]); ax[1].set_xlabel("Objektdrehung [Grad]")
fig.tight_layout(); fig.savefig(out / "fehler_lage.png", dpi=160, bbox_inches="tight"); plt.close(fig)
# 4) Hoehe ueber Tisch im Verlauf: typische Fahrten
if run is not None:
    from bc.table import TablePlane
    srt = sorted(rows, key=lambda r: r["min_clear_mm"])
    pick_rows = [srt[len(srt) // 2], srt[len(srt) // 4], srt[len(srt) // 8], srt[3], srt[1], srt[-5]]
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.0), sharey=True)
    for ax, r in zip(axes.flat, pick_rows):
        d = replay.episode_dir("data/2026-11-11", r["episode"])
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))["metadata"]
        plane = TablePlane.from_dict(meta["table"])
        st = np.asarray(replay.load_arrays("data/2026-11-11", r["episode"])["observation.state"], float)
        tcp = np.load(run / ("rollout_%03d.npz" % r["lauf"]))["tcp"]
        hz = lambda P: np.array([1e3 * (p[2] - plane.height_at(p[0], p[1])) for p in P])
        ax.plot(hz(st[:, 6:9]), color="#2a78d6", lw=1.5, label="Aufnahme (Anlage)")
        ax.plot(hz(tcp[:, :3]), color="#eb6834", lw=1.5, label="Policy in der VM")
        ax.axhline(0, color=INK, lw=0.9)
        if r["grasp_step"] is not None:
            ax.axvline(r["grasp_step"], color=INK2, lw=0.7, ls=":")
        ax.set_ylim(-80, 200); ax.set_xlim(0, max(len(st), 1) + 60)
        ax.set_title("%s ep %d: tiefster %.0f mm, xy %.0f mm" % (r["block"], r["episode"], r["min_clear_mm"],
                     r["grasp_xy_mm"] or -1), fontsize=7, color=INK, loc="left")
    for ax in axes[1]: ax.set_xlabel("Takt (15 Hz)")
    for ax in axes[:, 0]: ax.set_ylabel("TCP ueber Tisch [mm]")
    axes[0, 0].legend(frameon=False, fontsize=6.5, loc="upper right")
    fig.tight_layout(); fig.savefig(out / "hoehe_verlauf.png", dpi=160, bbox_inches="tight"); plt.close(fig)
print("Bilder ->", out)
