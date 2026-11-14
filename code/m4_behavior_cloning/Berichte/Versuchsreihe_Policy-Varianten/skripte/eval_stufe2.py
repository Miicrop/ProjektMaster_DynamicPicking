"""Auswertung Stufe 2: Greifpunkt gegen das Objekt (PICK der Episode) und Tischabstand.

Je Fahrt:
  * Greifpunkt: TCP einen Takt nach dem ersten Schliessbefehl gegen PICK
    (object_pose der Aufnahme): xy, z, Drehung um die Hochachse (mod 180).
  * Tisch: Abstand TCP zur Tischflaeche der Aufnahme (meta.table) ueber die
    ganze Fahrt; Minimum und Stelle. Zum Vergleich derselbe Wert der Aufnahme.
Aufruf: eval_stufe2.py <rollout-ordner> [<ausgabe.json>]
"""
import sys, os, json
from pathlib import Path
import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa
from bc import replay, config, geometry
from bc.table import TablePlane

run = Path(sys.argv[1])
summ = json.loads((run / "summary.json").read_text(encoding="utf-8"))


def yaw_deg(q):
    # Richtung der Werkzeug-x-Achse in der xy-Ebene
    R = geometry.quat_to_matrix(q)
    return np.degrees(np.arctan2(R[1, 0], R[0, 0]))


def d180(a, b):
    return abs(((a - b) + 90.0) % 180.0 - 90.0)


rows = []
for i, ep in enumerate(summ["episodes"]):
    rp = ep.get("replay") or {}
    data, idx = rp.get("root"), rp.get("episode")
    f = run / ("rollout_%03d.npz" % ep["episode"])
    if data is None or not f.exists():
        continue
    r = np.load(f)
    d = replay.episode_dir(data, idx)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))["metadata"]
    plane = TablePlane.from_dict(meta["table"])
    pick = np.asarray(meta["object_pose"]["PICK"], float)
    arr = replay.load_arrays(data, idx)
    st = np.asarray(arr["observation.state"], float)
    tcp = np.asarray(r["tcp"], float)
    g = np.asarray(r["gripper_cmd"], float) > config.GRIPPER_THRESHOLD
    clear = np.array([p[2] - plane.height_at(p[0], p[1]) for p in tcp[:, :3]])
    rec_clear = np.array([p[2] - plane.height_at(p[0], p[1]) for p in st[:, 6:9]])
    close = np.flatnonzero(g)
    out = dict(lauf=i, episode=idx, block=meta.get("block"), repeat=meta.get("repeat_index"),
               noise=round(float(meta.get("noise_scale") or 0), 2),
               yaw_obj=meta.get("object_yaw_deg"), pick_x_mm=round(1e3 * pick[0]), pick_y_mm=round(1e3 * pick[1]),
               stop=ep["stop_reason"], steps=ep["steps"], guard=ep["guard_rejections"],
               clamped=ep["limiter_clamped_steps"], overruns=ep["pacer_overruns"],
               predict_ms=None if ep.get("predict_ms_median") is None else round(ep["predict_ms_median"], 1),
               spread_p95=None if ep.get("ensemble_spread_p95_rad") is None else round(ep["ensemble_spread_p95_rad"], 3),
               path_dev_p95_mm=rp.get("path_dev_mm_p95"), end_mm=rp.get("end_err_mm"),
               grasp_vs_rec_mm=rp.get("grasp_err_mm"), grasp_step_offset=rp.get("grasp_step_offset"),
               min_clear_mm=round(1e3 * float(clear.min()), 1), min_clear_step=int(clear.argmin()),
               min_clear_closed=bool(g[int(clear.argmin())]),
               rec_min_clear_mm=round(1e3 * float(rec_clear.min()), 1),
               pick_over_table_mm=round(1e3 * float(meta.get("pick_over_table_m") or 0), 1))
    if len(close):
        k = min(int(close[0]) + 1, len(tcp) - 1)
        p = tcp[k]
        out.update(grasp_step=int(close[0]),
                   grasp_xy_mm=round(1e3 * float(np.linalg.norm(p[:2] - pick[:2])), 1),
                   grasp_dz_mm=round(1e3 * float(p[2] - pick[2]), 1),
                   grasp_clear_mm=round(1e3 * float(clear[k]), 1),
                   grasp_yaw_err_deg=round(d180(yaw_deg(p[3:7]), yaw_deg(pick[3:7])), 1))
        # tiefster Punkt im Umfeld des Schliessens (+-15 Takte)
        a, b = max(0, close[0] - 15), min(len(tcp), close[0] + 15)
        lo = a + int(np.argmin(tcp[a:b, 2]))
        out.update(low_xy_mm=round(1e3 * float(np.linalg.norm(tcp[lo, :2] - pick[:2])), 1))
        # naechste Annaeherung an PICK (3D) im Fenster +-15 Takte und deren Zeitversatz
        dd = np.linalg.norm(tcp[a:b, :3] - pick[:3], axis=1)
        j = int(np.argmin(dd))
        out.update(nearest_mm=round(1e3 * float(dd[j]), 1),
                   nearest_xy_mm=round(1e3 * float(np.linalg.norm(tcp[a + j, :2] - pick[:2])), 1),
                   nearest_shift=int(a + j - (close[0] + 1)))
    else:
        out.update(grasp_step=None, grasp_xy_mm=None, grasp_dz_mm=None, grasp_clear_mm=None,
                   grasp_yaw_err_deg=None, low_xy_mm=None, nearest_mm=None, nearest_xy_mm=None,
                   nearest_shift=None)
    rows.append(out)

dst = Path(sys.argv[2]) if len(sys.argv) > 2 else run / "auswertung.json"
dst.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
for x in rows:
    print({k: x[k] for k in ("lauf", "episode", "block", "stop", "grasp_xy_mm", "grasp_dz_mm", "grasp_yaw_err_deg",
                             "min_clear_mm", "grasp_vs_rec_mm", "path_dev_p95_mm")})
gx = np.array([x["grasp_xy_mm"] for x in rows if x["grasp_xy_mm"] is not None])
mc = np.array([x["min_clear_mm"] for x in rows])
print("\nFahrten %d, Endstellung %d, Greifer geschlossen %d" % (
    len(rows), sum(x["stop"] == "endstellung" for x in rows), len(gx)))
if len(gx):
    print("Greif-xy median %.1f, p90 %.1f, max %.1f mm; <=5 mm %d, <=10 mm %d, >20 mm %d" % (
        np.median(gx), np.percentile(gx, 90), gx.max(), (gx <= 5).sum(), (gx <= 10).sum(), (gx > 20).sum()))
nx = np.array([x["nearest_mm"] for x in rows if x["nearest_mm"] is not None])
ns = np.array([x["nearest_shift"] for x in rows if x["nearest_shift"] is not None])
if len(nx):
    print("Naechste Annaeherung an PICK (+-15 Takte): median %.1f, p90 %.1f mm; <=10 mm %d; Zeitversatz median %+d Takte" % (
        np.median(nx), np.percentile(nx, 90), (nx <= 10).sum(), int(np.median(ns))))
print("Tischabstand min: median %.1f, min %.1f mm; <3 mm: %d, <0 mm: %d" % (
    np.median(mc), mc.min(), (mc < 3).sum(), (mc < 0).sum()))
