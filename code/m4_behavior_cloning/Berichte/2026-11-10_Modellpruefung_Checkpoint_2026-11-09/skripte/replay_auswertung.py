"""Fasst alle VM-Replay-Fahrten vom 2026-11-10 zusammen (nur lesend).

Aufruf aus m4_behavior_cloning:
    python Berichte/2026-11-10_Modellpruefung_Checkpoint_2026-11-09/skripte/replay_auswertung.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROLL = Path("checkpoints/2026-11-09/rollouts")
rows = []
for summ in sorted(ROLL.glob("2026-11-10_vm_replay_*/replay_summary.json")):
    serie = summ.parent.name.replace("2026-11-10_vm_replay_", "")
    for r in json.loads(summ.read_text(encoding="utf-8"))["results"]:
        run = summ.parent / ("%s_%s_%s_ep%03d" % (r["kind"], r["session"], r["block"], r["dataset_episode"]))
        z = np.load(str(run / "rollout_000.npz"))
        tr = json.loads((run / "replay_trace.json").read_text(encoding="utf-8"))
        s = np.load(str(Path(tr["episode_dir"]) / "arrays.npz"))["observation__state"]
        rc = int(np.flatnonzero(s[:, 13] > 0.5)[0])
        c = np.flatnonzero(z["gripper_cmd"] > 0.5)
        gp = z["tcp"][c[0], :3] if len(c) else None
        r.update(serie=serie, demo_grasp=s[rc, 6:9], policy_grasp=gp,
                 grasp_height_mm=1e3 * s[rc, 8])
        rows.append(r)

hdr = ("Serie", "Art", "Block", "yaw", "x", "y", "Greif", "xy", "dj6", "Ende", "z_min", "Bild95", "Erf", "Stopp")
print("%-9s %-5s %-5s %5s %6s %6s %6s %6s %6s %6s %6s %6s %4s  %s" % hdr)
for r in rows:
    f = lambda v: "-" if v is None else "%.0f" % v
    print("%-9s %-5s %-5s %5s %6.3f %6.3f %6s %6s %6s %6s %6s %6s %4s  %s" % (
        r["serie"], r["kind"], r["block"], f(r["object_yaw_deg"]), r["object_xy_m"][0], r["object_xy_m"][1],
        f(r.get("grasp_err_mm")), f(r.get("grasp_err_xy_mm")), f(r.get("grasp_dj6_deg")),
        f(r.get("end_err_mm")), f(r.get("z_min_mm")), f(r.get("replay_dist_p95_mm")),
        "ja" if r.get("success") else "nein", (r.get("stop_reason") or "")[:40]))
    if r["policy_grasp"] is not None:
        d = 1e3 * (r["policy_grasp"] - r["demo_grasp"])
        print("%28s Greifpunkt Policy - Demo: dx %+.0f dy %+.0f dz %+.0f mm (Demo z %.0f mm)"
              % ("", d[0], d[1], d[2], r["grasp_height_mm"]))

if "--json" in sys.argv:
    out = [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()} for r in rows]
    print(json.dumps(out, indent=1, ensure_ascii=False))
