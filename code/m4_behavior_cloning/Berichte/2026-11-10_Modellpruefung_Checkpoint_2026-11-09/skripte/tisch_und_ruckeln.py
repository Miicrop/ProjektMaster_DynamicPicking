"""Tischabstand und Bildspruenge je Replay-Fahrt (nur lesend).

Tisch: Ebene aus den Metadaten der Demo (``table``: z = a*x + b*y + c, geprueft
gegen ``pick_over_table_m``). Ausgegeben wird der tiefste TCP-Punkt UEBER dem
Tisch an seiner xy-Stelle (negativ = unter der Tischflaeche).
Ruckeln: Spruenge des Bildzeigers (Frames je Takt) und Zielaenderung je Takt.
"""
import json
from pathlib import Path

import numpy as np

ROLL = Path("checkpoints/2026-11-09/rollouts")


def table_z(t, x, y):
    return t["a"] * x + t["b"] * y + t["c"]


checked = False
print("%-10s %-5s %-5s %8s %9s %6s %9s %9s %8s %8s" % (
    "Serie", "Art", "Block", "Demo_ueT", "min_ueT", "Takt", "Phase", "Spr>3", "dA_p95", "dA_max"))
for summ in sorted(ROLL.glob("2026-11-10_vm_replay_*/replay_summary.json")):
    serie = summ.parent.name.replace("2026-11-10_vm_replay_", "")
    for r in json.loads(summ.read_text(encoding="utf-8"))["results"]:
        run = summ.parent / ("%s_%s_%s_ep%03d" % (r["kind"], r["session"], r["block"], r["dataset_episode"]))
        z = np.load(str(run / "rollout_000.npz"))
        tr = json.loads((run / "replay_trace.json").read_text(encoding="utf-8"))
        meta = json.loads((Path(tr["episode_dir"]) / "meta.json").read_text(encoding="utf-8"))["metadata"]
        s = np.load(str(Path(tr["episode_dir"]) / "arrays.npz"))["observation__state"]
        t = meta["table"]
        rc = int(np.flatnonzero(s[:, 13] > 0.5)[0])
        demo = s[rc, 6:9]
        demo_above = demo[2] - table_z(t, demo[0], demo[1])
        if not checked:
            print("Pruefung Tischmodell: Demo ueber Tisch %.1f mm, Metadaten pick_over_table %.1f mm"
                  % (1e3 * demo_above, 1e3 * meta["pick_over_table_m"]))
            checked = True
        tcp, g = z["tcp"], z["gripper_cmd"]
        above = tcp[:, 2] - table_z(t, tcp[:, 0], tcp[:, 1])
        k = int(np.argmin(above))
        c = np.flatnonzero(g > 0.5)
        phase = "vor Griff" if (not len(c) or k < c[0]) else ("am Griff" if k <= c[0] + 3 else "nach Griff")
        frames = np.array([f for f, _ in tr["trace"]])
        jumps = int((np.abs(np.diff(frames)) > 3).sum())
        da = np.max(np.abs(np.diff(z["action"][:, :6], axis=0)), axis=1)
        print("%-10s %-5s %-5s %8.1f %9.1f %6d %9s %9d %8.3f %8.3f" % (
            serie, r["kind"], r["block"], 1e3 * demo_above, 1e3 * above[k], k, phase, jumps,
            np.percentile(da, 95), da.max()))
