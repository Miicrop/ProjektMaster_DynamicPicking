"""Wie genau liegt G2b in welcher Hoehe ueber dem Objekt? (Frage Endabstieg, 27.11.)

Alle Fahrten von G2b mit bekanntem PICK (``lage_pick`` im Rollout):
Vergleiche (vergleiche/*/lage_*/G2b_580*) und Rollouts der Policy
(checkpoints/G2b_580_dagger_nur_griff/policy/rollouts, Policy-Tests und DAgger).
Echte Griffe ohne bekannten PICK fehlen (keine Lage zum Vergleichen).

Je Fahrt und Hoehe h ueber der Objektoberkante (Oberkante = PICK + 7 mm):
TCP beim ersten Unterschreiten von h (linear zwischen zwei Takten), daraus
xy-Abstand und Drehung gegen PICK und die geometrische Griffpruefung
(bc/known_pose.grasp_check), wenn man von DORT senkrecht auf PICK-Hoehe
abstiege (xy und Drehung bleiben, dz = 0). Zusaetzlich: Endabstieg 'pick'
(PICK genutzt, wenn <= 6 mm und <= 5 Grad neben der Policy, sonst senkrecht).

Stoss-Fahrten vom 26.11. (DAgger mit Stoerung): die summary.json fehlt dort
(JSON-Fehler), der Stoss steht in der meta.json der DAgger-Episode
(data/2026-11-26_dagger, gleiche Reihenfolge).

Aufruf aus m4_behavior_cloning: python <dieses Skript>  -> hoehen_g2b.csv daneben
"""
import csv
import glob
import json
import statistics as st
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bc import config, known_pose  # noqa: E402
from bc.table import yaw_deg  # noqa: E402

TOP = config.PROBE_OBJECT_TOP_ABOVE_PICK_M * 1e3
HEIGHTS = list(range(0, 21))          # mm ueber Oberkante
POLICY = ROOT / "checkpoints" / "G2b_580_dagger_nur_griff" / "policy" / "rollouts"
PICK_MAX_MM, PICK_MAX_DEG = 6.0, 5.0
DAGGER_2611 = ["2026-11-26_14-19-25", "2026-11-26_14-25-20", "2026-11-26_14-39-24",
               "2026-11-26_14-46-52"]


def stoss_map():
    """(Rollout-Ordner, Fahrt) -> Stoss erfolgt (DAgger 26.11., Reihenfolge wie die Episoden)."""
    metas = sorted((ROOT / "data" / "2026-11-26_dagger").glob("ep_*/meta.json"))
    flags = [bool(((json.loads(m.read_text(encoding="utf-8"))["metadata"].get("dagger") or {})
                   .get("stoerung") or {}).get("erfolgt")) for m in metas]
    out, k = {}, 0
    for r in DAGGER_2611:
        for i in range(len(list((POLICY / r).glob("rollout_*.npz")))):
            if k < len(flags):
                out[(r, i)] = flags[k]
            k += 1
    return out


def run_info(folder):
    p = folder / "summary.json"
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    a = data.get("args") or {}
    return {"dagger": bool(a.get("dagger")),
            "offiziell": [e.get("grasp_level") for e in data.get("episodes") or []]}


def dagger_2611_levels():
    """Offizielle Bewertung der DAgger-Fahrten 26.11. (summary fehlt) aus der meta.json."""
    metas = sorted((ROOT / "data" / "2026-11-26_dagger").glob("ep_*/meta.json"))
    levels = [((json.loads(m.read_text(encoding="utf-8"))["metadata"].get("dagger") or {})
               .get("lage") or {}).get("grasp_check", {}).get("stufe") for m in metas]
    out, k = {}, 0
    for r in DAGGER_2611:
        for i in range(len(list((POLICY / r).glob("rollout_*.npz")))):
            if k < len(levels):
                out[(r, i)] = levels[k]
            k += 1
    return out


def at_height(tcp, z_target):
    """TCP-Pose beim ersten Unterschreiten von z_target (None, wenn nie)."""
    below = np.flatnonzero(tcp[:, 2] <= z_target)
    if not len(below) or below[0] == 0:
        return None
    i = below[0]
    a, b = tcp[i - 1], tcp[i]
    w = (a[2] - z_target) / max(a[2] - b[2], 1e-9)
    pose = a + w * (b - a)
    pose[3:] = b[3:] if w > 0.5 else a[3:]
    return pose


def collect():
    stoss = stoss_map()
    levels_2611 = dagger_2611_levels()
    files = [(f, "vergleich") for f in
             glob.glob(str(ROOT / "vergleiche" / "*" / "lage_*" / "G2b_580*" / "rollout_*.npz"))]
    files += [(f, "rollout") for f in glob.glob(str(POLICY / "*" / "rollout_*.npz"))]
    rows = []
    for f, kind in sorted(files):
        f = Path(f)
        d = np.load(f, allow_pickle=True)
        if "lage_pick" not in d.files:
            continue
        pick = np.asarray(d["lage_pick"], dtype=float)
        known = SimpleNamespace(pick=pick, table=None, pick_yaw_deg=yaw_deg(pick, None))
        tcp = np.asarray(d["tcp"], dtype=float)
        g = np.flatnonzero(np.asarray(d["gripper_cmd"]) > 0.5)
        tcp = tcp[: int(g[0]) + 1] if len(g) else tcp
        folder = f.parent
        run = folder.parent.parent.name if kind == "vergleich" else folder.name
        i = int(f.stem.split("_")[1])
        s = stoss.get((folder.name, i))
        info = run_info(folder)
        off = info.get("offiziell") or []
        offiziell = off[i] if i < len(off) else levels_2611.get((folder.name, i))
        p_stop = tcp[-1].copy()
        xy_stop = 1e3 * float(np.linalg.norm(p_stop[:2] - pick[:2]))
        p_stop[2] = pick[2]
        chk_stop = known_pose.grasp_check(p_stop, known)
        if kind == "vergleich":
            tag = "vergleich"
        elif s is not None or info.get("dagger"):
            tag = "dagger"
        else:
            tag = "test"
        base = {"quelle": tag, "tag": run[:10], "lauf": run, "ordner": str(folder), "fahrt": i,
                "stoss": s, "offiziell": offiziell, "stufe_stopp": chk_stop["stufe"],
                "xy_stopp_mm": xy_stop, "dreh_stopp_grad": chk_stop["yaw_deg"],
                "quer_stopp_mm": 1e3 * chk_stop["quer_m"], "laengs_stopp_mm": 1e3 * chk_stop["laengs_m"],
                "stopp_ueber_oberkante_mm": round(1e3 * (tcp[-1, 2] - pick[2]) - TOP, 1)}
        for h in HEIGHTS:
            pose = at_height(tcp, pick[2] + 1e-3 * (TOP + h))
            if pose is None:
                continue
            p = pose.copy()
            p[2] = pick[2]
            chk = known_pose.grasp_check(p, known)
            xy = 1e3 * float(np.linalg.norm(pose[:2] - pick[:2]))
            rows.append(dict(base, h_mm=h, xy_mm=xy, quer_mm=1e3 * chk["quer_m"],
                             laengs_mm=1e3 * chk["laengs_m"], dreh_grad=chk["yaw_deg"],
                             spiel_mm=None if chk["spiel_min_m"] is None else 1e3 * chk["spiel_min_m"],
                             stufe=chk["stufe"],
                             pick_genutzt=bool(xy <= PICK_MAX_MM and abs(chk["yaw_deg"]) <= PICK_MAX_DEG)))
    return rows


def key(r):
    return (r["ordner"], r["fahrt"])


def same_runs(rows, lo, hi):
    """Nur Fahrten, die alle Hoehen lo..hi erreichen (gleiche Menge in jeder Zeile)."""
    have = {}
    for r in rows:
        have.setdefault(key(r), set()).add(r["h_mm"])
    keep = {k for k, hs in have.items() if set(range(lo, hi + 1)) <= hs}
    return [r for r in rows if key(r) in keep], len(keep)


def line(rows, sel):
    r = [x for x in rows if sel(x["h_mm"])]
    if not r:
        return None
    n = len(r)
    ok = sum(x["stufe"] == known_pose.GRASP_OK for x in r)
    wa = sum(x["stufe"] == known_pose.GRASP_WARN for x in r)
    fa = n - ok - wa
    pick = sum(x["pick_genutzt"] or x["stufe"] != known_pose.GRASP_FAIL for x in r)
    q = [abs(x["quer_mm"]) for x in r]
    lg = [abs(x["laengs_mm"]) for x in r]
    return {"n": n, "q": st.median(q), "q90": float(np.percentile(q, 90)),
            "l": st.median(lg), "l90": float(np.percentile(lg, 90)),
            "dreh": st.median(abs(x["dreh_grad"]) for x in r),
            "ok": ok, "wa": wa, "fa": fa, "ow": 100.0 * (ok + wa) / n, "pick": 100.0 * pick / n}


def table(rows, title, heights):
    print()
    print(title)
    print("| Hoehe ueber Oberkante | n | quer Median | quer p90 | laengs Median | laengs p90 | Drehung Median | "
          "Erfolg | Warnung | Fehlgriff | Erfolg+Warnung | mit 'pick' |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    best = None
    for h in heights:
        if isinstance(h, int):
            v, label = line(rows, lambda x, h=h: x == h), "%d mm" % h
        else:
            v, label = line(rows, lambda x, h=h: h[0] <= x <= h[1]), "%d-%d mm (alle)" % h
        if v is None:
            continue
        n = v["n"]
        if isinstance(h, int) and (best is None or (v["ow"], -v["q"]) > (best[1]["ow"], -best[1]["q"])):
            best = (h, v)
        print("| %s | %d | %.1f mm | %.1f mm | %.1f mm | %.1f mm | %.2f Grad | %.0f %% | %.0f %% | "
              "%.0f %% | %.0f %% | %.0f %% |"
              % (label, n, v["q"], v["q90"], v["l"], v["l90"], v["dreh"], 100 * v["ok"] / n,
                 100 * v["wa"] / n, 100 * v["fa"] / n, v["ow"], v["pick"]))
    runs = {key(r): r for r in rows}.values()
    for name, field in (("am Stopp (TCP, senkrecht runter)", "stufe_stopp"),
                        ("offiziell (Vorhersage der Policy bis zum Griff)", "offiziell")):
        lv = [r[field] for r in runs if r[field]]
        if not lv:
            continue
        n = len(lv)
        ok = lv.count(known_pose.GRASP_OK)
        wa = lv.count(known_pose.GRASP_WARN)
        fa = n - ok - wa
        extra = ""
        if field == "stufe_stopp":
            q = [abs(r["quer_stopp_mm"]) for r in runs]
            lg = [abs(r["laengs_stopp_mm"]) for r in runs]
            extra = "%.1f mm | %.1f mm | %.1f mm | %.1f mm | %.2f Grad" % (
                st.median(q), float(np.percentile(q, 90)), st.median(lg), float(np.percentile(lg, 90)),
                st.median(abs(r["dreh_stopp_grad"]) for r in runs))
        else:
            extra = "- | - | - | - | -"
        print("| **%s** | %d | %s | %.0f %% | %.0f %% | %.0f %% | %.0f %% | - |"
              % (name, n, extra, 100 * ok / n, 100 * wa / n, 100 * fa / n, 100 * (ok + wa) / n))
    if best:
        print("-> beste Einzelhoehe: %d mm (Erfolg+Warnung %.0f %%, quer Median %.1f mm)"
              % (best[0], best[1]["ow"], best[1]["q"]))


def main():
    rows = collect()
    out = Path(__file__).resolve().parents[1] / "hoehen_g2b.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print("Fahrten mit bekanntem PICK: %d -> %s" % (len({key(r) for r in rows}), out))
    for q in ("vergleich", "test", "dagger"):
        sel = [r for r in rows if r["quelle"] == q]
        print("  %s: %d Fahrten (%s)" % (q, len({key(r) for r in sel}),
                                         ", ".join(sorted({r["tag"] for r in sel}))))
    hs = list(range(0, 21)) + [(10, 15), (12, 14)]
    sel, n = same_runs(rows, 5, 20)
    table(sel, "A) Alle Fahrten, die bis 5 mm ueber die Oberkante kamen (%d, gleiche in jeder Zeile)"
          % n, hs)
    sel, n = same_runs([r for r in rows if r["quelle"] == "vergleich"], 5, 20)
    table(sel, "B) davon Vergleiche 24.-26.11. (%d)" % n, hs)
    sel, n = same_runs([r for r in rows if r["quelle"] != "vergleich"], 5, 20)
    table(sel, "C) davon Policy-Rollouts: Tests und DAgger 25.11. (%d)" % n, hs)
    sel, n = same_runs([r for r in rows if r["stoss"] is not None], 18, 20)
    table(sel, "D) DAgger 26.11. mit/ohne Stoss, Stopp ~15-18 mm (%d)" % n, [18, 19, 20])
    for flag, name in ((True, "mit Stoss"), (False, "ohne Stoss")):
        sel, n = same_runs([r for r in rows if r["stoss"] is flag], 18, 20)
        table(sel, "   D%s) %s (%d)" % ("1" if flag else "2", name, n), [(18, 20)])
    return rows


if __name__ == "__main__":
    main()
