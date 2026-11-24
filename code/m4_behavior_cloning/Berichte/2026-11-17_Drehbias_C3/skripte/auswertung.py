"""Auswertung Drehbias: C2 gegen C3 (gewichtet) und C3a (ausgeduennt).

Liest, was vorhanden ist (fehlende Laeufe werden uebersprungen):
  daten/gewichte_*.json, daten/offline.json (bzw. offline_C2.json),
  daten/frueh_1111_<M>.json, Anlagenfahrten var_C2 16./17.11.,
  VM-Laeufe vm_heute_2026-11-17 (+ _wdh) und vm_T60 je Modell.
Schreibt abbildungen/*.png und daten/zusammenfassung.json, Tabellen nach stdout.

Aufruf (aus m4_behavior_cloning): python Berichte/2026-11-17_Drehbias_C3/skripte/auswertung.py
"""
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401,E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analyse_drehung import diff, richtung, rollout_rows, yaw360  # noqa: E402
from drehung_vm import run_rows, stats  # noqa: E402

D = Path("Berichte/2026-11-17_Drehbias_C3")
ABB = D / "abbildungen"
ABB.mkdir(parents=True, exist_ok=True)
MODELLE = ["C2", "C3", "C3a"]
ORDNER = {"C2": "C2_nur_griff_ohne_1111", "C3": "C3_wie_C2_drehung_gewichtet",
          "C3a": "C3a_wie_C2_plus_ausgeduennt"}
FARBE = {"C2": "#2a78d6", "C3": "#eb6834", "C3a": "#1baf7a", "Anlage": "#52514c"}
NAME = {"C2": "C2 (Bias)", "C3": "C3 gewichtet", "C3a": "C3a ausgedünnt", "Anlage": "Anlage (C2)"}
OUT = {}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6})


def fit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return None
    k, d = np.polyfit(x, y, 1)
    return float(k), float(d)


def by_class(need, err):
    out = {}
    for key in ("minus", "klein", "plus"):
        e = [v for n, v in zip(need, err) if richtung(n) == key]
        if e:
            out[key] = dict(n=len(e), median=float(np.median(e)), abs_median=float(np.median(np.abs(e))))
    return out


def ideal(ax, lo=-100, hi=170):
    ax.plot([lo, hi], [lo, hi], color="#9c9a92", lw=1, ls="--", zorder=0)
    ax.axhline(0, color="#c3c2b7", lw=0.8, zorder=0)
    ax.axvline(0, color="#c3c2b7", lw=0.8, zorder=0)


# 1. Daten -----------------------------------------------------------------
print("\n## 1. Daten")
info = json.loads(Path("datasets/var_C2/meta/bc_export.json").read_text(encoding="utf-8"))
length = np.array([float(e["length"]) for e in info["episodes"]])
gw = {m: json.loads((D / ("gewichte_C3_%s.json" % m)).read_text(encoding="utf-8"))
      for m in ("gewichten", "ausduennen")}
need = np.array(gw["gewichten"]["noetig_deg"], float)
OUT["daten"] = {m: dict(regel=g["regel"], vorher=g["vorher"], nachher=g["nachher"]) for m, g in gw.items()}
for m, g in gw.items():
    print("%s: %s | vorher %s | nachher %s" % (m, g["regel"], g["vorher"], g["nachher"]))
fig, ax = plt.subplots(figsize=(7, 3.2))
bins = np.arange(-120, 181, 15)
for key, w, lab in [("C2", np.ones_like(need), "C2 (Original)"),
                    ("C3", np.array(gw["gewichten"]["gewichte"]), "C3 gewichtet"),
                    ("C3a", np.array(gw["ausduennen"]["gewichte"]), "C3a ausgedünnt")]:
    h, _ = np.histogram(need, bins=bins, weights=w * length)
    ax.step(bins[:-1], 100 * h / h.sum(), where="post", color=FARBE[key], lw=2, label=lab)
ax.axvline(0, color="#52514c", lw=0.8)
ax.set_xlabel("nötige Drehung Start → Griff [Grad]  (+ = plus)")
ax.set_ylabel("Anteil Trainings-Frames [%]")
ax.legend(frameon=False)
ax.set_title("Drehrichtung in den Trainingsdaten (frame-gewichtet)", loc="left")
fig.tight_layout()
fig.savefig(ABB / "daten_verteilung.png", dpi=150)
plt.close(fig)

# 2. Anlage ----------------------------------------------------------------
print("\n## 2. Anlage (var_C2, 16./17.11.)")
rows = rollout_rows(sorted(glob.glob("checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/2026-11-1[67]_*")))
an_need = [r["noetig"] for r in rows]
an_done = [r["gedreht"] for r in rows]
OUT["anlage"] = dict(n=len(rows), klassen=by_class(an_need, [r["fehler"] for r in rows]),
                     fit=fit(an_need, an_done), falsch_herum=int(sum(r["falsch_herum"] for r in rows)))
print(OUT["anlage"])

# 3. Offline-Nachbau heute ---------------------------------------------------
print("\n## 3. Offline-Nachbau der Anlagenfahrten 17.11. (DAgger-Bilder)")
f = D / "daten" / "offline.json"
if not f.exists():
    f = D / "daten" / "offline_C2.json"
off = json.loads(f.read_text(encoding="utf-8"))
OUT["offline"] = {}
treue = []
print("| Ep. | nötig | Anlage gedreht (Stopp) | " + " | ".join("%s Ziel" % m for m in MODELLE
                                                              if m in off["episoden"][0]["modelle"]) + " |")
for e in off["episoden"]:
    ms = [m for m in MODELLE if m in e["modelle"]]
    z = np.load(e["rollout"]) if e.get("rollout") else None
    an = diff(yaw360(z["tcp"][-1]), e["start"]) if z is not None else float("nan")
    e["anlage_ende"] = an
    print("| %d | %+.0f | %+.0f | %s |" % (e["index"], e["noetig"], an,
                                         " | ".join("%+.0f" % e["modelle"][m]["ziel"][-1] for m in ms)))
    a = e.get("anlage_C2")
    if a and "C2" in e["modelle"]:
        o = dict(zip(e["modelle"]["C2"]["steps"], e["modelle"]["C2"]["wunsch"]))
        treue += [abs(o[t - t % 2] - w) for t, w in zip(a["steps"], a["wunsch"]) if (t - t % 2) in o]
OUT["offline_treue_C2"] = dict(n=len(treue), abs_median=float(np.median(treue)),
                               abs_p95=float(np.percentile(treue, 95)))
print("Treue Nachbau C2 gegen Anlagen-Vorhersagen: |Diff| median %.2f, p95 %.2f Grad (n=%d)"
      % (np.median(treue), np.percentile(treue, 95), len(treue)))
for m in MODELLE:
    if m not in off["episoden"][0]["modelle"]:
        continue
    nd = [e["noetig"] for e in off["episoden"]]
    zi = [e["modelle"][m]["ziel"][-1] for e in off["episoden"]]
    OUT["offline"][m] = dict(klassen=by_class(nd, [z - n for z, n in zip(zi, nd)]), fit=fit(nd, zi))
    print(m, OUT["offline"][m])

# 3b. Kumulierter Drehwunsch: Endziel zeigt nur den letzten Chunk (dort steht jedes
# Modell in der C2-Stellung). Summe der Wuensche (je 8 Takte, alle 2 Takte neu)
# / 4 = Drehung, die das Modell offen (ohne Rueckkopplung) gefahren haette.
print("\n## 3b. Kumulierter Drehwunsch (Summe Wunsch/4, ohne Rueckkopplung)")
ms = [m for m in MODELLE if m in off["episoden"][0]["modelle"]]
print("| Ep. | nötig | Anlage | " + " | ".join(ms) + " |")
OUT["kumuliert"] = {m: [] for m in ms}
for e in off["episoden"]:
    vals = [float(np.sum(e["modelle"][m]["wunsch"]) / 4.0) for m in ms]
    for m, v in zip(ms, vals):
        OUT["kumuliert"][m].append(dict(index=e["index"], noetig=e["noetig"], kum=v))
    print("| %d | %+.0f | %+.0f | %s |" % (e["index"], e["noetig"], e["anlage_ende"],
                                         " | ".join("%+.0f" % v for v in vals)))
if "C2" in ms:
    for m in ms[1:]:
        for key, sel in (("minus", lambda n: n < -10), ("plus", lambda n: n > 10)):
            dd = [a["kum"] - b["kum"] for a, b in zip(OUT["kumuliert"][m], OUT["kumuliert"]["C2"])
                  if sel(a["noetig"])]
            OUT.setdefault("kumuliert_diff", {}).setdefault(m, {})[key] = dict(
                median=float(np.median(dd)), werte=[round(x, 1) for x in dd])
            print("%s - C2 %s: median %+.1f Grad  %s" % (m, key, np.median(dd), [round(x) for x in dd]))

# 3c. Wo wird gedreht? Anteil der noetigen Drehung beim Unterschreiten der Hoehen
print("\n## 3c. Drehfortschritt nach Hoehe ueber dem Griff (ANFLUG 15 cm, PRE_PICK 5 cm)")
HOEHEN = (0.15, 0.05, 0.01)


def fortschritt(tcp, at, need):
    zz = tcp[:, 2]
    s = yaw360(tcp[0])
    out = []
    for h in HOEHEN:
        idx = np.flatnonzero(zz[:at + 1] <= zz[at] + h + 0.003)
        t = int(idx[0]) if idx.size else at
        out.append(diff(yaw360(tcp[t]), s) / need)
    return out


prof = {"demo_plus": [], "demo_minus": [], "anlage_plus": [], "anlage_minus": []}
g_info = json.loads((D / "gewichte_C3_gewichten.json").read_text(encoding="utf-8"))
exp = json.loads(Path("datasets/var_C2/meta/bc_export.json").read_text(encoding="utf-8"))
for ep, n, k in list(zip(exp["episodes"], g_info["noetig_deg"], g_info["klasse"]))[::4]:
    if n is None or abs(n) < 20:
        continue
    with np.load(Path(ep["source"]) / ep["source_dir"] / "arrays.npz") as z:
        st = np.asarray(z["observation__state"], float)
    gr = st[:, 13] > 0.5
    c = np.flatnonzero(gr[1:] & ~gr[:-1])
    prof["demo_" + k].append(fortschritt(st[:, 6:13], int(c[0]) + 1, n))
for e in off["episoden"]:
    if not e.get("rollout") or abs(e["noetig"]) < 20:
        continue
    z = np.load(e["rollout"])
    T = np.asarray(z["tcp"], float)
    gc = np.flatnonzero(np.asarray(z["gripper_cmd"]) > 0.5)
    at = int(gc[0]) if gc.size else len(T) - 1
    prof["anlage_" + ("plus" if e["noetig"] > 0 else "minus")].append(fortschritt(T, at, e["noetig"]))
OUT["hoehenprofil"] = {}
for key, v in prof.items():
    v = np.array(v)
    OUT["hoehenprofil"][key] = dict(n=len(v), median=[float(x) for x in np.median(v, 0)],
                                    min=[float(x) for x in v.min(0)], max=[float(x) for x in v.max(0)])
    print("%-13s n=%3d  Anteil bei 15/5/1 cm: %s  (min %s)" % (
        key, len(v), " / ".join("%.0f %%" % (100 * x) for x in np.median(v, 0)),
        " / ".join("%.0f %%" % (100 * x) for x in v.min(0))))

# 3d. Nachfuehrung (skripte/ausfuehrung.py)
f = D / "daten" / "ausfuehrung.json"
if f.exists():
    OUT["ausfuehrung"] = {k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items()
                          if k != "anlage_fahrten"}
    print("\n## 3d. Nachfuehrung gemessen gegen Kommando:", OUT["ausfuehrung"])

# 4. Fruehentscheidung 11.11. -------------------------------------------------
print("\n## 4. Fruehentscheidung auf den Demos vom 11.11. (in keinem Training)")
OUT["frueh"] = {}
fig, ax = plt.subplots(figsize=(6, 4))
for m in MODELLE:
    f = D / "daten" / ("frueh_1111_%s.json" % m)
    if not f.exists():
        continue
    r = json.loads(f.read_text(encoding="utf-8"))
    x, y = [], []
    for e in r["episoden"]:
        w = e["modelle"][m]["wunsch"][:3]  # Takte 0, 2, 4: Arm steht noch (< 1 Grad gedreht)
        if w:
            x.append(e["noetig"])
            y.append(float(np.mean(w)))
    x, y = np.array(x), np.array(y)
    k, d = fit(x, y)
    mi, pl = y[x < -10], y[x > 10]
    OUT["frueh"][m] = dict(n=len(x), fit=(k, d), minus_median=float(np.median(mi)),
                           plus_median=float(np.median(pl)),
                           minus_richtig=float(np.mean(mi < 0)), plus_richtig=float(np.mean(pl > 0)),
                           null_bei_deg=float(-d / k))
    print("%-4s n=%d  Wunsch = %.3f x noetig %+.2f  (Nullstelle %+.0f Grad) | minus med %+.1f, richtig %.0f %% "
          "| plus med %+.1f, richtig %.0f %%" % (m, len(x), k, d, -d / k, np.median(mi), 100 * np.mean(mi < 0),
                                                np.median(pl), 100 * np.mean(pl > 0)))
    ax.scatter(x, y, s=10, color=FARBE[m], alpha=0.55, edgecolors="none")
    xx = np.array([-100, 170])
    ax.plot(xx, k * xx + d, color=FARBE[m], lw=2, label="%s: %.3f·x %+.2f" % (NAME[m], k, d))
ax.axhline(0, color="#52514c", lw=0.8)
ax.axvline(0, color="#52514c", lw=0.8)
ax.set_xlabel("nötige Drehung [Grad]")
ax.set_ylabel("Drehwunsch nächste 8 Takte [Grad]")
ax.set_title("Startentscheidung (Takt 0–4, identische Startstellung)", loc="left")
ax.legend(frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig(ABB / "fruehentscheidung.png", dpi=150)
plt.close(fig)


# 5. VM ------------------------------------------------------------------------
def vm_heute(run):
    """Drehung beim Takt, an dem die Anlage gestoppt hat (Ende Policy-Teil)."""
    run = Path(run)
    if not (run / "summary.json").exists():
        return None
    summ = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    by_idx = {e["index"]: e for e in off["episoden"]}
    out = []
    for ep in summ["episodes"]:
        rp = ep.get("replay") or {}
        idx = rp.get("episode")
        fz = run / ("rollout_%03d.npz" % int(ep["episode"]))
        if idx not in by_idx or not fz.exists():
            continue
        e = by_idx[idx]
        tcp = np.load(fz)["tcp"]
        if not len(tcp):
            continue
        t = min(e["n_pol"] - 1, len(tcp) - 1)
        start = yaw360(tcp[0])
        dz = None
        if e.get("rollout"):
            pt = np.load(e["rollout"])["tcp"]
            n = min(len(pt), t + 1)
            dz = float(1e3 * np.median(np.linalg.norm(tcp[:n, :3] - pt[:n, :3], axis=1)))
        out.append(dict(index=idx, noetig=e["noetig"], gedreht=diff(yaw360(tcp[t]), start),
                        anlage=e["anlage_ende"], pos_diff_mm_median=dz, takt=t,
                        stop=ep.get("stop_reason")))
    return out


print("\n## 5. VM-Replay der heutigen Fahrten (Drehung am Stopp-Takt der Anlage)")
OUT["vm_heute"] = {}
vmh = {}
for m, run in [("C2", "checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/vm_heute_2026-11-17"),
               ("C2w", "checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/vm_heute_2026-11-17_wdh"),
               ("C3", "checkpoints/C3_wie_C2_drehung_gewichtet/policy/rollouts/vm_heute_2026-11-17"),
               ("C3a", "checkpoints/C3a_wie_C2_plus_ausgeduennt/policy/rollouts/vm_heute_2026-11-17")]:
    r = vm_heute(run)
    if not r:
        continue
    vmh[m] = r
    nd, gd = [x["noetig"] for x in r], [x["gedreht"] for x in r]
    OUT["vm_heute"][m] = dict(n=len(r), klassen=by_class(nd, [g - n for g, n in zip(gd, nd)]), fit=fit(nd, gd),
                              rows=r)
    if m.startswith("C2"):
        dv = [abs(x["gedreht"] - x["anlage"]) for x in r]
        pd = [x["pos_diff_mm_median"] for x in r if x["pos_diff_mm_median"] is not None]
        OUT["vm_heute"][m]["gegen_anlage"] = dict(dreh_abs_median=float(np.median(dv)),
                                                  dreh_abs_max=float(np.max(dv)),
                                                  pos_median_mm=float(np.median(pd)) if pd else None)
    print(m, {k: v for k, v in OUT["vm_heute"][m].items() if k != "rows"})

print("\n## 6. VM T60 (Demo-Bilder 11.11.)")
OUT["vm_T60"] = {}
t60 = {}
for m in MODELLE:
    run = Path("checkpoints/%s/policy/rollouts/vm_T60" % ORDNER[m])
    if not (run / "summary.json").exists():
        continue
    r = run_rows(run)
    s = stats(r)
    t60[m] = r
    ev = run / "auswertung.json"
    std = None
    if ev.exists():
        a = json.loads(ev.read_text(encoding="utf-8"))
        near = np.array([x["nearest_mm"] for x in a if x.get("nearest_mm") is not None], float)
        gx = np.array([x["grasp_xy_mm"] for x in a if x.get("grasp_xy_mm") is not None], float)
        mc = np.array([x["min_clear_mm"] for x in a if x.get("min_clear_mm") is not None], float)
        ye = np.array([x["grasp_yaw_err_deg"] for x in a if x.get("grasp_yaw_err_deg") is not None], float)
        std = dict(n=len(a), naechste_median_mm=float(np.median(near)), le10=float(np.mean(near <= 10)),
                   p90_mm=float(np.percentile(near, 90)), greif_xy_median_mm=float(np.median(gx)) if len(gx) else None,
                   unter_tisch=float(np.mean(mc < 0)),
                   servoguard=float(np.mean([x["stop"].startswith("abgelehnt") for x in a])),
                   endstellung=float(np.mean([x["stop"] == "endstellung" for x in a])),
                   drehfehler_mod180_median=float(np.median(ye)) if len(ye) else None)
    OUT["vm_T60"][m] = dict(drehung=s, standard=std)
    print(m, s, std)

# Abbildung: noetig gegen gedreht in allen Quellen ---------------------------------
panels = [("Anlage 16./17.11. (C2, Ende der Fahrt)", {"Anlage": (an_need, an_done)})]
panels.append(("Offline-Nachbau 17.11.: kumulierter Drehwunsch",
               {m: ([x["noetig"] for x in OUT["kumuliert"][m]], [x["kum"] for x in OUT["kumuliert"][m]])
                for m in MODELLE if m in OUT["kumuliert"]}))
if vmh:
    panels.append(("VM-Replay 17.11. (am Stopp-Takt der Anlage)",
                   {m: ([x["noetig"] for x in r], [x["gedreht"] for x in r]) for m, r in vmh.items() if m != "C2w"}))
if t60:
    panels.append(("VM-Replay T60 (Demo-Bilder 11.11., beim Schließen)",
                   {m: ([x["noetig"] for x in r], [x["gedreht"] for x in r]) for m, r in t60.items()}))
fig, axes = plt.subplots(1, len(panels), figsize=(4.0 * len(panels), 4.0), squeeze=False)
for ax, (title, series) in zip(axes[0], panels):
    ideal(ax)
    for m, (x, y) in series.items():
        ax.scatter(x, y, s=22, color=FARBE[m], alpha=0.8, edgecolors="white", linewidths=0.6, label=NAME[m])
        fr = fit(x, y)
        if fr:
            xx = np.array([min(x), max(x)])
            ax.plot(xx, fr[0] * xx + fr[1], color=FARBE[m], lw=1.6)
    ax.set_title(title, loc="left", fontsize=8.5)
    ax.set_xlabel("nötige Drehung [Grad]")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")
axes[0][0].set_ylabel("gefahrene / angestrebte Drehung [Grad]")
fig.tight_layout()
fig.savefig(ABB / "drehung_quellen.png", dpi=150)
plt.close(fig)

(D / "daten" / "zusammenfassung.json").write_text(json.dumps(OUT, indent=1, default=str), encoding="utf-8")
print("\n-> %s, %s" % (ABB, D / "daten" / "zusammenfassung.json"))
