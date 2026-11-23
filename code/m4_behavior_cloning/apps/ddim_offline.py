"""Offline-Test: DDIM-Schritte und Glaettung auf aufgezeichneten Demos.

Anlage 2026-11-23: Die Policy-Chunks zittern schon in sich, der Arm schwingt
darauf seitlich ueber (Berichte/Testprotokoll.md). Zwei Stellschrauben ohne
neues Training:

  * mehr DDIM-Schritte (``--inference-steps`` in apps/infer.py) -- weniger
    Restrauschen im Chunk, aber laengere Vorhersage;
  * Tiefpass auf die Ziele (``--glaettung`` in apps/infer.py) -- glatter,
    aber mit Verzug.

Dieses Werkzeug spielt Demos Takt fuer Takt durch die Policy (wie
apps/replay_check.py, ChunkEnsembler synchron, kein Roboter) und misst je
DDIM-Schrittzahl:

  * Vorhersagezeit (median / p95 / max) -- Grenze an der Anlage ~130 ms
    (2 Takte), heute ~105 ms mit 10 Schritten;
  * Ruck innerhalb der Chunks und Sprung zwischen Chunks (unter 60 mm);
  * Ruck des gemittelten Befehls und Abstand zur Aufnahme, je Glaettung.

Grenzen: Die Policy sieht hier Demo-Bilder (bekannte Situationen), das
Zittern ist an der Anlage eher groesser. Synchron heisst ohne die ~2 Takte
Verzug der asynchronen Vorhersage. Die Vorhersagezeit gilt fuer DIESEN
Rechner -- an der Anlage dort messen (Betrieb, Probefahrt).

Ausfuehren (aus dem Ordner m4_behavior_cloning):
    python apps/ddim_offline.py --checkpoint checkpoints/G2_licht_langsam_nur_griff --data data_vm/2026-11-19-2
    python apps/ddim_offline.py --checkpoint <policy> --data <aufnahme> --schritte 10,20,50 --glaettung 1,0.5,0.3
Protokoll: <checkpoint>/offline_ddim/<Zeit>/protokoll.txt und summary.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from bc import config, offline_glaette, replay
from bc.policy import ChunkEnsembler

#: Grenze der Vorhersagezeit an der Anlage (2 Takte bei 15 Hz)
PREDICT_LIMIT_MS = 2000.0 / config.CONTROL_RATE_HZ


def _floats(text):
    return [float(v) for v in str(text).replace(";", ",").split(",") if v.strip()]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", required=True, help="Policy-Ordner (apps/train.py)")
    parser.add_argument("--data", required=True, help="Aufnahme-Ordner mit index.json")
    parser.add_argument("--episodes", default="0-4",
                        help="'3', '0,4,7', '2-5' oder 'alle' (Default %(default)s)")
    parser.add_argument("--schritte", default="10,20,50",
                        help="DDIM-Schritte, kommagetrennt (Default %(default)s; 1-100)")
    parser.add_argument("--glaettung", default="1,0.5,0.3",
                        help="Tiefpass alpha, kommagetrennt, 1 = aus (Default %(default)s)")
    parser.add_argument("--nah-mm", type=float, default=60.0,
                        help="Hoehe ueber dem Greifpunkt, unter der gemessen wird (Default %(default)s)")
    parser.add_argument("--replan", type=int, default=None,
                        help="alle N Takte neu vorhersagen (Default aus bc_policy.json)")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=None,
                        help="Ergebnisordner (Default <checkpoint>/offline_ddim/<Zeit>)")
    args = parser.parse_args(argv)
    try:
        args.schritte = sorted({int(v) for v in _floats(args.schritte)})
        args.glaettung = sorted({float(v) for v in _floats(args.glaettung)}, reverse=True)
    except ValueError:
        parser.error("--schritte / --glaettung: Zahlen, kommagetrennt")
    if not args.schritte or any(not 1 <= s <= 100 for s in args.schritte):
        parser.error("--schritte: 1 bis 100")
    if not args.glaettung or any(not 0.0 < a <= 1.0 for a in args.glaettung):
        parser.error("--glaettung: Werte in (0, 1]")
    return args


def run_steps(checkpoint, steps, args, episodes, cameras, replan, decay, fk_for, progress=print):
    """Alle Episoden mit ``steps`` DDIM-Schritten; Rueckgabe dict mit Kennzahlen."""
    from bc.diffusion import DiffusionPolicyRunner

    policy = DiffusionPolicyRunner(checkpoint, device=args.device,
                                   inference_steps=steps, seed=args.seed)
    executor = ChunkEnsembler(policy, replan_steps=replan, decay=decay, asynchronous=False)
    first = replay.load_arrays(args.data, episodes[0])
    warm = policy.warmup(replay.observation_at(first, 0, cameras))
    progress("  %d DDIM-Schritte: Aufwaermen %.1f ms" % (steps, 1e3 * warm))

    predict_ms, inside, gaps, open_loop = [], [], [], []
    per_alpha = {a: {"ruck": [], "abstand_mm": []} for a in args.glaettung}
    for ep in episodes:
        arrays = replay.load_arrays(args.data, ep)
        fk = fk_for(ep)
        n = len(arrays["observation.state"])
        executor.reset()
        commands = np.zeros((n, config.ACTION_DIM))
        for step in range(n):
            before = executor.predictions
            commands[step] = executor.next_action(replay.observation_at(arrays, step, cameras))
            if executor.predictions > before and policy.last_predict_s is not None:
                predict_ms.append(1e3 * policy.last_predict_s)
        recorded = np.asarray(arrays["action"], dtype=float)
        state = np.asarray(arrays["observation.state"], dtype=float)
        tcp = state[:, 6:9]
        near = offline_glaette.near_mask(tcp, recorded[:, 6], args.nah_mm)
        c_in, c_gap = offline_glaette.chunk_metrics(executor.history, fk, near)
        inside.extend(c_in)
        gaps.extend(c_gap)
        for alpha, m in offline_glaette.command_metrics(commands, recorded, fk, near,
                                                        args.glaettung).items():
            per_alpha[alpha]["ruck"].extend(m["ruck"])
            per_alpha[alpha]["abstand_mm"].extend(m["abstand_mm"])
        summary = replay.summarize_open_loop({"predicted": commands, "recorded": recorded})
        open_loop.append(summary)
        progress("    Episode %d: %d Takte, %d nah, Gelenkfehler p95 %.2f Grad, Greifer gleich %.0f %%"
                 % (ep, n, int(near.sum()), summary["joint_err_deg_p95"],
                    100 * summary["gripper_agreement"]))
    try:
        executor.close()
    except Exception:
        pass
    return {
        "ddim_schritte": int(steps),
        "aufwaermen_ms": 1e3 * float(warm),
        "vorhersage_ms": offline_glaette.stats(predict_ms),
        "chunk_ruck_mm": offline_glaette.stats(inside),
        "chunk_sprung_mm": offline_glaette.stats(gaps),
        "befehl": {("%.2f" % a): {"ruck_mm": offline_glaette.stats(m["ruck"]),
                                  "abstand_aufnahme_mm": offline_glaette.stats(m["abstand_mm"])}
                   for a, m in per_alpha.items()},
        "gelenkfehler_p95_grad_median": float(np.median([s["joint_err_deg_p95"] for s in open_loop])),
        "greifer_gleich": float(np.mean([s["gripper_agreement"] for s in open_loop])),
    }


def format_report(report):
    """Protokoll als Text (Tabellen fuer protokoll.txt und Konsole)."""
    lines = [
        "Offline-Test DDIM-Schritte / Glaettung -- %s" % report["created"],
        "Modell   : %s" % report["checkpoint"],
        "Aufnahme : %s, Episoden %s" % (report["data"], report["episodes"]),
        "Rechner  : %s" % report["rechner"],
        "Gemessen unter %.0f mm ueber dem Greifpunkt, vor dem Schliessen. Ruck = 2. Differenz der "
        "TCP-Position je Takt (Planer-Labels ~0,0 mm)." % report["nah_mm"],
        "",
        "%-7s %-22s %-17s %-17s %-17s %-9s" % ("DDIM", "Vorhersage ms", "Chunk-Ruck mm",
                                              "Chunk-Sprung mm", "Gelenkfehler p95", "Greifer"),
        "%-7s %-22s %-17s %-17s %-17s %-9s" % ("", "med / p95 / max", "med / p95",
                                              "med / p95", "Grad (median Ep.)", "gleich"),
    ]
    for r in report["ergebnisse"]:
        v, ci, cg = r["vorhersage_ms"], r["chunk_ruck_mm"], r["chunk_sprung_mm"]
        flag = "  <-- ueber %.0f ms" % PREDICT_LIMIT_MS if v["p95"] > PREDICT_LIMIT_MS else ""
        lines.append("%-7d %-22s %-17s %-17s %-17s %-9s%s" % (
            r["ddim_schritte"], "%.0f / %.0f / %.0f" % (v["median"], v["p95"], v["max"]),
            "%.2f / %.2f" % (ci["median"], ci["p95"]), "%.1f / %.1f" % (cg["median"], cg["p95"]),
            "%.2f" % r["gelenkfehler_p95_grad_median"], "%.0f %%" % (100 * r["greifer_gleich"]), flag))
    lines += ["", "Befehl an den Arm (gemittelte Chunks), je Glaettung alpha (1 = aus):",
              "%-7s %-8s %-20s %-24s" % ("DDIM", "alpha", "Ruck mm med / p95", "Abstand Aufnahme mm med / p95")]
    for r in report["ergebnisse"]:
        for alpha, m in r["befehl"].items():
            lines.append("%-7d %-8s %-20s %-24s" % (
                r["ddim_schritte"], alpha,
                "%.2f / %.2f" % (m["ruck_mm"]["median"], m["ruck_mm"]["p95"]),
                "%.1f / %.1f" % (m["abstand_aufnahme_mm"]["median"], m["abstand_aufnahme_mm"]["p95"])))
    lines += ["",
              "Lesart: kleinerer Chunk-Ruck/-Sprung = ruhigere Vorhersage. Der Abstand zur Aufnahme "
              "waechst mit der Glaettung (Verzug ~(1-alpha)/alpha Takte) -- er darf nicht viel "
              "groesser werden als ohne Glaettung. Vorhersagezeit an der Anlage separat pruefen "
              "(Grenze ~%.0f ms)." % PREDICT_LIMIT_MS]
    return "\n".join(lines)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)
    from bc.diffusion import hardware_info, read_policy_info, select_device
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
    decay = defaults.get("ensemble_decay", config.POLICY_ENSEMBLE_DECAY)

    fks = {}

    def fk_for(ep):
        try:
            meta = json.loads((replay.episode_dir(args.data, ep) / "meta.json")
                              .read_text(encoding="utf-8"))
            offset = offline_glaette.tool_offset_from_meta(meta)
        except (OSError, ValueError):
            offset = None
        key = tuple(offset) if offset else None
        if key not in fks:
            fks[key] = offline_glaette.ToolFK(offset or offline_glaette.DEFAULT_TOOL_OFFSET_M)
        return fks[key]

    out = Path(args.out) if args.out else (
        Path(checkpoint) / "offline_ddim" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    out.mkdir(parents=True, exist_ok=True)
    try:
        rechner = hardware_info(select_device(args.device))
    except Exception as exc:          # nur Protokoll
        rechner = "unbekannt (%s)" % exc
    print("Offline-Test %s auf %s, Episoden %s, DDIM %s, Glaettung %s, neu alle %d Takte -> %s"
          % (checkpoint, args.data, episodes, args.schritte, args.glaettung, replan, out))

    report = {"checkpoint": str(checkpoint), "data": str(args.data), "episodes": episodes,
              "created": datetime.now().isoformat(timespec="seconds"),
              "rechner": rechner if isinstance(rechner, str) else json.dumps(rechner),
              "nah_mm": args.nah_mm, "replan_steps": replan, "ensemble_decay": decay,
              "ergebnisse": []}
    for steps in args.schritte:
        print("DDIM-Schritte %d ..." % steps)
        report["ergebnisse"].append(
            run_steps(checkpoint, steps, args, episodes, cameras, replan, decay, fk_for))
        (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    text = format_report(report)
    (out / "protokoll.txt").write_text(text + "\n", encoding="utf-8")
    print("")
    print(text)
    print("")
    print("Protokoll: %s" % (out / "protokoll.txt"))
    return report


if __name__ == "__main__":
    main()
