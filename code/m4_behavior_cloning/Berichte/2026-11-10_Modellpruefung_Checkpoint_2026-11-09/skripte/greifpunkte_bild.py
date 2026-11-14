"""Draufsicht: Trainingslagen, Demo- und Policy-Greifpunkte aller Replay-Fahrten (nur lesend).

Aufruf aus m4_behavior_cloning; schreibt greifpunkte.png neben das Protokoll.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
ROLL = Path("checkpoints/2026-11-09/rollouts")
exp = json.loads(Path("datasets/2026-11-09/meta/bc_export.json").read_text(encoding="utf-8"))
cfg = json.loads(Path("checkpoints/2026-11-09/train_config.json").read_text(encoding="utf-8"))
val = set(cfg["val_episodes"])
P = np.array([e["metadata"]["object_pose"]["PICK"][:2] for e in exp["episodes"]])
isval = np.array([i in val for i in range(len(P))])

fig, ax = plt.subplots(figsize=(7.5, 6.2))
ax.scatter(P[~isval, 1] * 1e3, P[~isval, 0] * 1e3, s=8, c="#bbbbbb", label="Trainingslagen (PICK)")
ax.scatter(P[isval, 1] * 1e3, P[isval, 0] * 1e3, s=8, c="#8fb8de", label="Val-Lagen (PICK)")
first = {"ok": True, "bad": True}
for summ in sorted(ROLL.glob("2026-11-10_vm_replay_*/replay_summary.json")):
    for r in json.loads(summ.read_text(encoding="utf-8"))["results"]:
        run = summ.parent / ("%s_%s_%s_ep%03d" % (r["kind"], r["session"], r["block"], r["dataset_episode"]))
        z = np.load(str(run / "rollout_000.npz"))
        tr = json.loads((run / "replay_trace.json").read_text(encoding="utf-8"))
        s = np.load(str(Path(tr["episode_dir"]) / "arrays.npz"))["observation__state"]
        d = s[int(np.flatnonzero(s[:, 13] > 0.5)[0]), 6:8] * 1e3
        c = np.flatnonzero(z["gripper_cmd"] > 0.5)
        if not len(c):
            continue
        p = z["tcp"][c[0], :2] * 1e3
        ok = r.get("grasp_err_mm") is not None and r["grasp_err_mm"] <= 25
        col = "#2a9d4b" if ok else "#d1495b"
        key = "ok" if ok else "bad"
        ax.annotate("", xy=(p[1], p[0]), xytext=(d[1], d[0]),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.4))
        ax.scatter([d[1]], [d[0]], marker="o", facecolors="none", edgecolors="k", s=40,
                   label="Demo-Greifpunkt" if first.get("demo", True) else None)
        first["demo"] = False
        ax.scatter([p[1]], [p[0]], marker="x", c=col, s=40,
                   label=("Policy, Fehler <= 25 mm" if ok else "Policy, Fehler > 25 mm") if first[key] else None)
        first[key] = False
        ax.text(d[1] + 4, d[0] + 4, r["block"], fontsize=7)
ax.set_xlabel("y [mm]")
ax.set_ylabel("x [mm]  (vom Roboter weg)")
ax.set_title("VM-Replay 2026-11-10: Greifpunkt Demo -> Policy (Draufsicht, Tool-Frame)", fontsize=10)
ax.set_aspect("equal")
ax.invert_xaxis()
ax.grid(alpha=0.3)
ax.legend(fontsize=7, loc="lower left")
fig.tight_layout()
fig.savefig(str(HERE / "greifpunkte.png"), dpi=150)
print(HERE / "greifpunkte.png")
