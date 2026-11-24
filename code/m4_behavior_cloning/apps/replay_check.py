"""Offline-Abgleich: Policy auf den Bildern und Zustaenden einer Aufnahme.

Stufe 1 des Replay-Tests (bc/replay.py). Je Takt geht die Beobachtung der
Aufnahme (beide Kamerabilder + Zustand) in die Policy -- ueber denselben
ChunkEnsembler wie apps/infer.py, nur synchron. Die vorhergesagte Action
wird mit der aufgezeichneten verglichen. Kein Roboter, keine VM.

Lesart:
  * Gelenkfehler klein (wenige Grad) und Greiferwechsel an der richtigen
    Stelle -> die Policy hat die Bahn gelernt; weiter mit Stufe 2 in der VM
    (apps/infer.py --replay).
  * Gross schon hier -> die VM-Fahrt verraet nichts Neues; erst Training,
    Export oder Vorverarbeitung pruefen.
  * Episoden, die im Training waren, zeigen die Anpassung, nicht die
    Verallgemeinerung -- zum Vergleich eine Aufnahme nehmen, die nicht im
    Export war.

Ausfuehren (aus dem Ordner "Behavior Cloning"):
    python apps/replay_check.py --checkpoint <policy> --data data_vm/2026-11-11
    python apps/replay_check.py --checkpoint <policy> --data data_vm/2026-11-11 --episodes 0,5,9 --plot
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from bc import config, replay
from bc.policy import ChunkEnsembler


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", required=True, help="Policy-Ordner (apps/train.py)")
    parser.add_argument("--data", required=True, help="Aufnahme-Ordner mit index.json")
    parser.add_argument("--episodes", default="0-4",
                        help="'3', '0,4,7', '2-5' oder 'alle' (Default %(default)s)")
    parser.add_argument("--replan", type=int, default=None,
                        help="alle N Takte neu vorhersagen (Default aus bc_policy.json)")
    parser.add_argument("--decay", type=float, default=None,
                        help="Gewichtung beim Mitteln (Default aus bc_policy.json)")
    parser.add_argument("--inference-steps", type=int, default=None, help="DDIM-Schritte")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--plot", action="store_true",
                        help="je Episode ein PNG: Gelenke aufgezeichnet vs. vorhergesagt")
    parser.add_argument("--out", default=None,
                        help="Ergebnisordner (Default <checkpoint>/replay_check/<Zeit>)")
    return parser.parse_args()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    from bc.diffusion import DiffusionPolicyRunner, read_policy_info
    from infer import resolve_checkpoint

    checkpoint = resolve_checkpoint(args.checkpoint)
    info = read_policy_info(checkpoint)
    problems = replay.check_compatible(args.data, info)
    if problems:
        raise SystemExit("Aufnahme passt nicht zur Policy:\n  - " + "\n  - ".join(problems))
    episodes = replay.parse_episodes(args.episodes, args.data)
    if not episodes:
        raise SystemExit("--episodes: keine Episode ausgewaehlt")
    cameras = list(info["cameras"])

    defaults = info.get("inference_defaults", {})
    replan = args.replan or defaults.get("replan_steps", config.POLICY_REPLAN_STEPS)
    decay = args.decay if args.decay is not None else defaults.get(
        "ensemble_decay", config.POLICY_ENSEMBLE_DECAY)

    print("Lade Policy %s ..." % checkpoint)
    policy = DiffusionPolicyRunner(checkpoint, device=args.device,
                                   inference_steps=args.inference_steps, seed=args.seed)
    executor = ChunkEnsembler(policy, replan_steps=replan, decay=decay, asynchronous=False)
    out = Path(args.out) if args.out else (
        Path(checkpoint) / "replay_check" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    out.mkdir(parents=True, exist_ok=True)
    print("Aufnahme %s, Episoden %s, Kameras %s, neu alle %d Takte, decay %.2f -> %s"
          % (args.data, episodes, cameras, replan, decay, out))

    results = []
    for ep in episodes:
        arrays = replay.load_arrays(args.data, ep)
        print("Episode %d (%d Takte) ..." % (ep, len(arrays["observation.state"])))
        result = replay.open_loop(executor, arrays, cameras, progress=print)
        summary = dict(episode=ep, **replay.summarize_open_loop(result))
        results.append(summary)
        np.savez_compressed(out / ("ep_%05d.npz" % ep), **result)
        print("  Gelenke: median %.2f / p95 %.2f / max %.2f Grad (Takt %d), "
              "Greifer gleich %.0f %%, Wechsel Aufnahme %s, Policy %s"
              % (summary["joint_err_deg_median"], summary["joint_err_deg_p95"],
                 summary["joint_err_deg_max"], summary["joint_err_deg_max_step"],
                 100 * summary["gripper_agreement"], summary["gripper_switch_recorded"],
                 summary["gripper_switch_predicted"]))
        if args.plot:
            path = plot_episode(result, ep, out)
            if path:
                print("  Plot: %s" % path)

    report = {
        "checkpoint": str(checkpoint),
        "data": str(args.data),
        "created": datetime.now().isoformat(timespec="seconds"),
        "replan_steps": replan,
        "ensemble_decay": decay,
        "episodes": results,
        "joint_err_deg_p95_median": float(np.median([r["joint_err_deg_p95"] for r in results])),
        "gripper_agreement_mean": float(np.mean([r["gripper_agreement"] for r in results])),
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print("\n%d Episoden: Gelenkfehler p95 (Median ueber Episoden) %.2f Grad, Greifer gleich %.0f %% -> %s"
          % (len(results), report["joint_err_deg_p95_median"],
             100 * report["gripper_agreement_mean"], out / "summary.json"))


def plot_episode(result, ep, out):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  (matplotlib fehlt -- kein Plot)")
        return None
    pred, rec = np.asarray(result["predicted"]), np.asarray(result["recorded"])
    fig, axes = plt.subplots(7, 1, figsize=(9, 12), sharex=True)
    for j in range(6):
        axes[j].plot(np.degrees(rec[:, j]), label="Aufnahme", color="#1f77b4")
        axes[j].plot(np.degrees(pred[:, j]), label="Policy", color="#d62728", linestyle="--")
        axes[j].set_ylabel("J%d [Grad]" % (j + 1))
    axes[6].step(range(len(rec)), rec[:, 6], label="Aufnahme", color="#1f77b4", where="post")
    axes[6].step(range(len(pred)), pred[:, 6], label="Policy", color="#d62728",
                 linestyle="--", where="post")
    axes[6].set_ylabel("Greifer")
    axes[6].set_xlabel("Takt (15 Hz)")
    axes[0].legend(loc="upper right")
    fig.suptitle("Episode %d: Action aufgezeichnet vs. vorhergesagt" % ep)
    fig.tight_layout()
    path = out / ("ep_%05d.png" % ep)
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return path


if __name__ == "__main__":
    main()
