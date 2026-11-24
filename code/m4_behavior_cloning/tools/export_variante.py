"""Datensatz-Varianten fuer Vergleichstrainings (Versuchsreihe ab 2026-11-13).

Wie apps/export.py, aber mit Regeln, die beim Export angewandt werden. Die
Aufnahmen selbst bleiben unveraendert; geschrieben wird nur das
LeRobotDataset (Bilder als Video, daher keine Rohdaten-Kopien).

Regeln (kombinierbar):

``--ohne-lagen testlagen.json``
    Episoden der dort genannten Testlagen (``aufnahme`` + ``testlagen``)
    weglassen -- sie bleiben fuer den Vergleich der Varianten reserviert.

``--pause-behalten K``
    Stillstand am Greifpunkt kuerzen. In den Aufnahmen steht die ideale Bahn
    nach dem Schliessbefehl ~8 Takte (0,5 s Greifer-Dwell) still; die Policy
    sieht dort fast denselben Zustand und muss mal "bleiben", mal "los"
    lernen (Befund 2026-11-13: Abtauchen beim Wegfahren). Von den
    Stillstands-Takten nach dem Schliessen bleiben K, der Rest entfaellt.
    Die Bahn bleibt stetig: im Stillstand aendern sich Soll und Ist nicht.
    K so waehlen, dass der Greifer an der Anlage zu ist (K=3 ~ 0,2 s).

``--abschneiden-nach N``
    Episode N Takte nach dem Schliessbefehl beenden (Policy nur fuer Anflug
    und Griff; Anheben/Transport muss dann die Inferenz uebernehmen).

``--eine-drehung``
    Nur Demos, deren Werkzeug am Greifpunkt NICHT um 180 Grad gegen das
    Objekt gedreht ist (Werkzeug-Gierwinkel minus Objekt-Gierwinkel mod 360
    nahe 0). Befund 2026-11-10: bei Objekten mit 0-90 Grad greift die
    Haelfte der Demos gedreht -- zwei gleichwertige Loesungen fuer dasselbe Bild.

``--label-kappen RAD``
    Gelenk-Label (Action 0..5, ideale Gelenke t+1) auf hoechstens RAD Abstand
    zur Ist-Stellung desselben Takts begrenzen. Grund: Mit Drehversatz im
    Anflug liegt das Label (Idealbahn) an Gelenk 6 teils > 0,35 rad neben der
    Ist-Stellung -- die Inferenz lehnt solche Ziele ab
    (``config.SERVO_MAX_TARGET_GAP_RAD``). Gekappt zeigt das Label weiter zur
    Idealbahn, nur in kleineren Schritten. Greifer-Label bleibt unveraendert.

Ausfuehren (aus dem Ordner "Behavior Cloning" bzw. m4_behavior_cloning):
    python tools/export_variante.py --data data/2026-11-02 data/2026-11-03 data/2026-11-09 data/2026-11-11 \
        --ohne-lagen Berichte/Versuchsreihe_Policy-Varianten/testlagen.json --out datasets/var_A
    python tools/export_variante.py ... --pause-behalten 3 --out datasets/var_B
    python tools/export_variante.py ... --check            # nur Auswahl und Kuerzungen anzeigen
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))
from export import add_export_arguments, expand_sources  # noqa: E402

from bc import config, dataset, geometry, lerobot_io  # noqa: E402

#: Ideale Gelenke gelten als still, wenn sich kein Gelenk um mehr bewegt (rad/Takt).
STILL_RAD = 1e-5


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", nargs="+", required=True, help="Aufzeichnungsordner oder Glob-Muster")
    parser.add_argument("--out", help="Zielordner des LeRobotDataset")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true", help="nur Auswahl/Kuerzungen anzeigen")
    parser.add_argument("--ohne-lagen", metavar="JSON", help="Testlagen weglassen (testlagen.json)")
    parser.add_argument("--pause-behalten", type=int, default=None, metavar="K",
                        help="von der Pause nach dem Schliessen nur K Takte behalten")
    parser.add_argument("--abschneiden-nach", type=int, default=None, metavar="N",
                        help="Episode N Takte nach dem Schliessbefehl beenden")
    parser.add_argument("--eine-drehung", action="store_true",
                        help="nur Demos ohne 180-Grad-Drehung des Werkzeugs gegen das Objekt")
    parser.add_argument("--ohne-episoden", action="append", default=[], metavar="ORDNER=I,J",
                        help="einzelne Episoden eines Aufzeichnungsordners weglassen (z. B. Testfahrten), mehrfach moeglich")
    parser.add_argument("--dagger-gewicht", type=int, default=1, metavar="K",
                        help="DAgger-Episoden (apps/infer.py --dagger, metadata mode 'dagger') "
                             "K-mal in den Datensatz -- wenige Korrekturen neben vielen Demos "
                             "haetten sonst kaum Gewicht (Default %(default)s)")
    parser.add_argument("--label-kappen", type=float, default=None, metavar="RAD",
                        help="Gelenk-Label auf hoechstens RAD Abstand zur Ist-Stellung begrenzen")
    add_export_arguments(parser)
    args = parser.parse_args()
    if not args.check and not args.out:
        parser.error("--out fehlt (oder --check)")
    return args


def close_step(arrays):
    """Erster Takt mit Schliessbefehl (Action), None ohne Griff."""
    idx = np.flatnonzero(np.asarray(arrays["action"])[:, 6] > config.GRIPPER_THRESHOLD)
    return int(idx[0]) if len(idx) else None


def keep_mask(arrays, pause_keep=None, cut_after=None):
    """Bool-Maske der behaltenen Takte und Zahl der entfernten Pausen-Takte."""
    n = len(arrays["observation.state"])
    keep = np.ones(n, dtype=bool)
    c = close_step(arrays)
    removed = 0
    if c is None:
        return keep, removed
    if pause_keep is not None:
        ideal = np.asarray(arrays["aux.joints_ideal"], dtype=float)
        k = c
        while k + 1 < n and np.abs(ideal[k + 1] - ideal[k]).max() < STILL_RAD:
            k += 1
        # Takte c+1..k sind still (gleiches Soll wie c); behalten: c..c+K
        drop = np.arange(c + 1 + pause_keep, k + 1)
        keep[drop] = False
        removed = len(drop)
    if cut_after is not None:
        keep[c + cut_after + 1:] = False
    return keep, removed


def clip_labels(arrays, limit):
    """Gelenk-Label auf +-limit um die Ist-Stellung kappen. Gibt (arrays, gekappte Takte je Gelenk)."""
    act = np.array(arrays["action"], dtype=np.float32, copy=True)
    q = np.asarray(arrays["observation.state"], dtype=np.float32)[:, :6]
    gap = act[:, :6] - q
    hit = np.abs(gap) > limit
    act[:, :6] = q + np.clip(gap, -limit, limit)
    out = dict(arrays)
    out["action"] = act
    return out, hit.sum(axis=0)


def apply_mask(arrays, keep):
    out = {}
    n = len(keep)
    for key, arr in arrays.items():
        arr = np.asarray(arr)
        out[key] = arr[keep] if arr.ndim >= 1 and len(arr) == n else arr
    if "next.done" in out and len(out["next.done"]):
        done = np.zeros_like(out["next.done"])
        done[-1] = True
        out["next.done"] = done
    return out


def light_arrays(root, index):
    """Nur Zustand und Action einer Episode (ohne Bilder -- schnell)."""
    idx = json.loads((Path(root) / "index.json").read_text(encoding="utf-8"))
    with np.load(Path(root) / idx["episodes"][index]["dir"] / "arrays.npz") as npz:
        return {"observation.state": npz["observation__state"], "action": npz["action"],
                "aux.joints_ideal": npz["aux__joints_ideal"]}


def tool_flip(arrays, meta):
    """True, wenn das Werkzeug am Greifpunkt um ~180 Grad gegen das Objekt gedreht ist."""
    yaw_obj = (meta.get("metadata") or {}).get("object_yaw_deg")
    c = close_step(arrays)
    if yaw_obj is None or c is None:
        return None
    state = np.asarray(arrays["observation.state"], dtype=float)
    R = geometry.quat_to_matrix(state[min(c + 1, len(state) - 1), 9:13])
    tool = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    d = (tool - float(yaw_obj)) % 360.0
    return abs(d - 180.0) < 45.0


def main():
    args = parse_args()
    sources = expand_sources(args.data)
    test = None
    if args.ohne_lagen:
        spec = json.loads(Path(args.ohne_lagen).read_text(encoding="utf-8"))
        test = (Path(spec["aufnahme"]).resolve(), set(spec["testlagen"]))

    skip = {}
    for spec in args.ohne_episoden:
        folder, idx = spec.rsplit("=", 1)
        skip.setdefault(Path(folder).resolve(), set()).update(int(x) for x in idx.split(",") if x.strip())
    stats = Counter()
    trimmed = []
    orig_scan = lerobot_io.scan_sources
    orig_load = dataset.load_episode

    def scan_sources(srcs, require_success=False):
        scan = orig_scan(srcs, require_success=require_success)
        kept = []
        for root, i, meta in scan["episodes"]:
            block = (meta.get("metadata") or {}).get("block")
            if i in skip.get(Path(root).resolve(), ()):
                stats["weggelassen: --ohne-episoden"] += 1
                continue
            if test and Path(root).resolve() == test[0] and block in test[1]:
                stats["weggelassen: Testlage"] += 1
                continue
            if args.eine_drehung:
                flip = tool_flip(light_arrays(root, i), meta)
                if flip:
                    stats["weggelassen: Werkzeug 180 Grad gedreht"] += 1
                    continue
                if flip is None:
                    stats["Drehung nicht bestimmbar (behalten)"] += 1
            copies = 1
            if (meta.get("metadata") or {}).get("mode") == "dagger":
                stats["DAgger-Episoden"] += 1
                copies = max(1, int(args.dagger_gewicht))
                stats["DAgger-Kopien (Gewicht)"] += copies
            kept.extend([(root, i, meta)] * copies)
        stats["behalten"] = len(kept)
        scan["episodes"] = kept
        return scan

    clipped = np.zeros(6, dtype=int)
    clipped_eps = Counter()

    def load_episode(root, index):
        nonlocal clipped
        ep = orig_load(root, index)
        arrays = ep.arrays
        if args.pause_behalten is not None or args.abschneiden_nach is not None:
            keep, removed = keep_mask(arrays, args.pause_behalten, args.abschneiden_nach)
            trimmed.append((len(keep), int(keep.sum()), removed))
            arrays = apply_mask(arrays, keep)
        if args.label_kappen is not None:
            arrays, hit = clip_labels(arrays, args.label_kappen)
            clipped = clipped + hit
            clipped_eps["Episoden mit gekapptem Label"] += int(hit.sum() > 0)
        return ep if arrays is ep.arrays else replace(ep, arrays=arrays)

    lerobot_io.scan_sources = scan_sources
    lerobot_io.dataset.load_episode = load_episode

    rules = {
        "ohne_lagen": args.ohne_lagen,
        "pause_behalten": args.pause_behalten,
        "abschneiden_nach": args.abschneiden_nach,
        "eine_drehung": bool(args.eine_drehung),
        "dagger_gewicht": int(args.dagger_gewicht),
        "ohne_episoden": list(args.ohne_episoden),
        "label_kappen": args.label_kappen,
    }
    print("Quellen: %s" % ", ".join(map(str, sources)))
    print("Regeln: %s" % rules)
    if args.check:
        scan = scan_sources(sources, require_success=args.require_success)
        if args.pause_behalten is not None or args.abschneiden_nach is not None:
            for root, i, _ in scan["episodes"]:
                keep, removed = keep_mask(light_arrays(root, i), args.pause_behalten, args.abschneiden_nach)
                trimmed.append((len(keep), int(keep.sum()), removed))
        report(stats, trimmed)
        return

    try:
        info = lerobot_io.export(sources, args.out, require_success=args.require_success,
                                 allow_mixed=args.allow_mixed, use_video=not args.images,
                                 crf=args.crf, overwrite=args.overwrite)
    except lerobot_io.ExportError as exc:
        raise SystemExit("Export abgebrochen: %s" % exc)
    path = Path(args.out) / "meta" / lerobot_io.EXPORT_INFO
    info = json.loads(path.read_text(encoding="utf-8"))
    if args.abschneiden_nach is not None:
        # Die Episoden enden am Griff; Endstellung fuer apps/infer.py
        # --transport-geplant ist die Station (PRE_PLACE) der Aufnahmen. Ablauf
        # pick_bis_griff (ab 2026-11-19) hat keine Station, die Episoden enden
        # an UEBER_TISCH -- dann ist das die Endstellung (wie beim Modell ohne
        # Abschneiden).
        station, end_point = [], None
        for name in ("PRE_PLACE", "UEBER_TISCH"):
            station = [ep["metadata"]["points"][name]["joints"] for ep in info["episodes"]
                       if name in (ep["metadata"].get("points") or {})]
            if station:
                end_point = name
                break
        if not station:
            raise SystemExit("--abschneiden-nach: weder PRE_PLACE noch UEBER_TISCH in den Metadaten")
        info["end_joints_policy"] = info["end_joints"]
        info["end_joints"] = np.median(np.asarray(station, dtype=float), axis=0).tolist()
        info["end_gripper"] = float(config.GRIPPER_CLOSED)
        print("Endstellung = %s (Median aus %d Episoden, Spannweite %.4f rad)"
              % (end_point, len(station), float(np.max(np.ptp(np.asarray(station, dtype=float), axis=0)))))
    info["variante"] = dict(regeln=rules, auswahl=dict(stats),
                            takte_vorher=int(sum(t[0] for t in trimmed)) or None,
                            takte_nachher=int(sum(t[1] for t in trimmed)) or None,
                            pause_entfernt=int(sum(t[2] for t in trimmed)) or None)
    if args.label_kappen is not None:
        info["variante"]["label_gekappt_takte_je_gelenk"] = clipped.tolist()
        info["variante"]["label_gekappt_episoden"] = int(clipped_eps["Episoden mit gekapptem Label"])
        print("Label gekappt (> %.3f rad): Takte je Gelenk %s, Episoden %d"
              % (args.label_kappen, clipped.tolist(), clipped_eps["Episoden mit gekapptem Label"]))
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    report(stats, trimmed)
    print("LeRobotDataset %s: %d Episoden" % (args.out, len(info["episodes"])))


def report(stats, trimmed):
    for k, v in sorted(stats.items()):
        print("  %-42s %d" % (k, v))
    if trimmed:
        before = sum(t[0] for t in trimmed)
        after = sum(t[1] for t in trimmed)
        pause = [t[2] for t in trimmed]
        print("  Takte %d -> %d (%.1f %% weniger); Pause entfernt je Episode median %d, min %d, max %d"
              % (before, after, 100.0 * (before - after) / max(before, 1),
                 int(np.median(pause)), min(pause), max(pause)))


if __name__ == "__main__":
    main()
