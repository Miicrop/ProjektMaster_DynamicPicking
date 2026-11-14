"""Auffaellige Episoden eines Aufnahmetags (Not-Aus, Abbruch, Schleppfehler).

Je Episode: Laenge geplant/aufgezeichnet, Dauer geplant/ist, groesster
Schleppfehler, Pausen in den Zeitstempeln, Greiferschluss vorhanden, Ende an
der Station, success/discarded -- und ob sie im Export der Varianten steckt.

Aufruf: notaus_suche.py <tag> [datensatz ...]
"""
import sys
import json
import glob
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
day = sys.argv[1]
exports = {}
for ds in sys.argv[2:]:
    info = json.loads((ROOT / ds / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    exports[Path(ds).name] = {e["source_dir"] for e in info["episodes"] if day in Path(e["source"]).as_posix()}

rows = []
for d in sorted(glob.glob(str(ROOT / "data" / day / "ep_*"))):
    d = Path(d)
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    md = m.get("metadata") or {}
    z = np.load(d / "arrays.npz")
    st = z["observation__state"]
    q, act = st[:, :6], z["action"]
    closed = np.flatnonzero(act[:, 6] > 0.5)
    end_joint_err = float(np.abs(q[-1] - z["aux__joints_ideal"][-1]).max())
    jump = float(np.abs(np.diff(q, axis=0)).max()) if len(q) > 1 else 0.0
    flags = []
    if m.get("discarded"):
        flags.append("verworfen: %s" % m.get("discard_reason"))
    if m.get("success") is False:
        flags.append("success=False")
    ps, rs = md.get("planned_steps"), md.get("recorded_steps")
    if ps and rs and rs < 0.95 * ps:
        flags.append("kurz %s/%s Takte" % (rs, ps))
    pd_, du = md.get("planned_duration_s"), md.get("duration_s")
    if pd_ and du and du > 1.3 * pd_:
        flags.append("Dauer %.1f/%.1f s" % (du, pd_))
    fe = md.get("max_follow_error_rad")
    if fe is not None and fe > 0.1:
        flags.append("Schleppfehler %.2f rad" % fe)
    if not len(closed):
        flags.append("kein Greiferschluss")
    if end_joint_err > 0.05:
        flags.append("Ende %.2f rad neben Ideal" % end_joint_err)
    if jump > 0.05:
        flags.append("Gelenksprung %.2f rad/Takt" % jump)
    bfr = md.get("bad_frame_ratio")
    if bfr is not None and bfr > 0.03:
        flags.append("schlechte Frames %.0f %%" % (100 * bfr))
    inn = [k for k, s in exports.items() if d.name in s]
    rows.append((d.name, md.get("block"), md.get("repeat_index"), md.get("session"), md.get("recorded_at"),
                 len(q), fe, flags, inn))

print("Episoden %d, auffaellig %d" % (len(rows), sum(1 for r in rows if r[7])))
for r in rows:
    if r[7]:
        print("%s  Lage %s Wdh %s  Session %s  %s  %d Takte  Schlepp %s  -> %s  | im Export: %s" % (
            r[0], r[1], r[2], r[3], r[4], r[5], "%.3f" % r[6] if r[6] is not None else "-",
            "; ".join(r[7]), ", ".join(r[8]) or "nein"))
fe = np.array([r[6] for r in rows if r[6] is not None], float)
print("Schleppfehler aller Episoden: median %.3f, p95 %.3f, max %.3f rad" % (np.median(fe), np.percentile(fe, 95), fe.max()))
