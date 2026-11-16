"""Kamerareferenz in einen vorhandenen Checkpoint nachtragen (Anwender 2026-11-16).

Neue Exporte schreiben ``camera_reference`` selbst (bc/lerobot_io.py ->
bc_policy.json). Aeltere Checkpoints haben sie nicht; dieses Werkzeug liest
das erste Bild (Startstellung) aus den Rohepisoden der Quellordner des
Datensatzes (bc_policy.json ``dataset.sources``) und traegt Bildstatistik und
Bezugsbild ein. Die alte bc_policy.json bleibt als Sicherung daneben.

    python tools/kamera_referenz.py --checkpoint checkpoints/var_Cp/policy
    python tools/kamera_referenz.py --checkpoint <policy> --quelle data/2026-11-09 --anzeigen
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from bc import camera_check

M4_ROOT = Path(__file__).resolve().parents[1]


def episode_dirs(sources):
    """Nicht verworfene Episoden der Quellordner, sortiert."""
    out = []
    for source in sources:
        root = Path(source)
        if not root.is_absolute() and not root.exists():
            root = M4_ROOT / root
        if not root.is_dir():
            print("Hinweis: Quellordner fehlt: %s" % source)
            continue
        for d in sorted(root.glob("ep_*")):
            try:
                meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not meta.get("discarded") and (d / "arrays.npz").is_file():
                out.append(d)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checkpoint", required=True, help="Ordner mit bc_policy.json")
    parser.add_argument("--quelle", action="append", default=None,
                        help="Quellordner der Episoden statt dataset.sources (mehrfach angebbar)")
    parser.add_argument("--episoden", type=int, default=camera_check.MAX_EPISODES,
                        help="hoechstens so viele Episoden (Default %(default)s)")
    parser.add_argument("--anzeigen", action="store_true",
                        help="nur berechnen und anzeigen, nichts schreiben")
    args = parser.parse_args(argv)

    path = Path(args.checkpoint) / "bc_policy.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    sources = args.quelle or (info.get("dataset") or {}).get("sources") or []
    if not sources:
        raise SystemExit("Keine Quellordner -- bc_policy.json ohne dataset.sources, --quelle angeben")
    dirs = episode_dirs(sources)
    if not dirs:
        raise SystemExit("Keine Episoden in %s" % ", ".join(map(str, sources)))
    cameras = info.get("cameras") or []
    print("%d Episoden in %d Quellordner(n), Kameras %s" % (len(dirs), len(sources), cameras))
    reference = camera_check.build_reference(
        camera_check.first_frames(dirs, cameras, max_episodes=args.episoden))
    for name, ref in reference.items():
        print("  %s aus %d Episoden: %s" % (
            name, ref["episodes"],
            ", ".join("%s %.2f..%.2f" % (k, v[0], v[2]) for k, v in ref["stats"].items())))
    if args.anzeigen:
        return 0
    backup = path.with_name("bc_policy.json.bak_%s" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(path, backup)
    info[camera_check.REFERENCE_KEY] = reference
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Eingetragen in %s (Sicherung %s)" % (path, backup.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
