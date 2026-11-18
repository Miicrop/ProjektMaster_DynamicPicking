"""Drehfehler in VM-Replay-Laeufen (apps/infer.py --replay, stufe2_vm.py).

Je Fahrt: noetige Drehung = Demo (Start -> erster geschlossener Greifer, aus
der Replay-Episode), gefahrene Drehung = Policy-TCP am ersten Schliessbefehl
(ohne Schliessen: am tiefsten Punkt). Volle 360 Grad wie analyse_drehung.py.

Aufruf: drehung_vm.py NAME=<rollout-ordner> [...] [--json AUSGABE]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa: F401,E402

from bc import config, replay  # noqa: E402
from analyse_drehung import diff, richtung, yaw360  # noqa: E402


def demo_need(root, idx, _cache={}):
    key = (str(root), int(idx))
    if key not in _cache:
        with np.load(replay.episode_dir(root, idx) / "arrays.npz") as z:
            st = np.asarray(z["observation__state"], float)
        g = st[:, 13] > config.GRIPPER_THRESHOLD
        c = np.flatnonzero(g[1:] & ~g[:-1])
        at = int(c[0]) + 1 if c.size else int(np.argmin(st[:, 8]))
        _cache[key] = diff(yaw360(st[at, 6:13]), yaw360(st[0, 6:13]))
    return _cache[key]


def run_rows(run, dagger_ref=False):
    run = Path(run)
    summ = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = []
    for ep in summ["episodes"]:
        rp = ep.get("replay") or {}
        if isinstance(rp, str):
            import ast
            rp = ast.literal_eval(rp)
        root, idx = rp.get("root"), rp.get("episode")
        f = run / ("rollout_%03d.npz" % int(ep["episode"]))
        if root is None or not f.exists():
            continue
        z = np.load(f)
        tcp = np.asarray(z["tcp"], float)
        if not len(tcp):
            continue
        g = np.asarray(z["gripper_cmd"], float) > config.GRIPPER_THRESHOLD
        c = np.flatnonzero(g)
        at = int(c[0]) if c.size else int(np.argmin(tcp[:, 2]))
        start = yaw360(tcp[0])
        if dagger_ref:
            md = json.loads((replay.episode_dir(root, idx) / "meta.json").read_text(encoding="utf-8"))
            m1 = md["metadata"]["dagger"]["lokalisierung"]["gripper_yaw360_deg"]
            need = diff(float(m1), start)
        else:
            need = demo_need(root, idx)
        done = diff(yaw360(tcp[at]), start)
        rows.append(dict(root=str(root), episode=int(idx), noetig=need, gedreht=done,
                         fehler=diff(done, need), schliesst=bool(c.size), takt=at,
                         richtung=richtung(need), stop=ep.get("stop_reason")))
    return rows


def stats(rows):
    out = {"n": len(rows)}
    for key in ("plus", "klein", "minus"):
        grp = [r for r in rows if r["richtung"] == key]
        if grp:
            e = np.array([r["fehler"] for r in grp])
            out[key] = dict(n=len(grp), fehler_median=float(np.median(e)),
                            abs_median=float(np.median(np.abs(e))),
                            falsch_herum=int(sum(1 for r in grp if richtung(r["gedreht"]) not in
                                                 ("klein", key) and key != "klein")))
    if len(rows) >= 3:
        need = np.array([r["noetig"] for r in rows])
        done = np.array([r["gedreht"] for r in rows])
        k, d = np.polyfit(need, done, 1)
        out["steigung"], out["achsabschnitt"] = float(k), float(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("laeufe", nargs="+", help="NAME=ordner")
    ap.add_argument("--dagger", action="store_true", help="Bezug = M1-Drehung der DAgger-Episode")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    res = {}
    for spec in args.laeufe:
        name, path = spec.split("=", 1)
        rows = run_rows(path, dagger_ref=args.dagger)
        s = stats(rows)
        res[name] = dict(ordner=path, stats=s, rows=rows)
        line = "%-14s n=%2d" % (name, s["n"])
        for key in ("plus", "klein", "minus"):
            if key in s:
                line += " | %s: n=%d Fehler med %+5.1f (|%4.1f|) falsch %d" % (
                    key, s[key]["n"], s[key]["fehler_median"], s[key]["abs_median"], s[key]["falsch_herum"])
        if "steigung" in s:
            line += " | gedreht ~ %.2f x noetig %+.1f" % (s["steigung"], s["achsabschnitt"])
        print(line)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
