"""Episoden-Gewichte gegen den Drehrichtungs-Bias der Demos (Anlage 2026-11-17).

Befund: In den Demos von var_C2 (02./03./09.11.) muss das Werkzeug vom Start
bis zum Griff in 62 % der Episoden nach PLUS drehen, nur in 25 % nach MINUS
(Mittel +32 Grad). An der Anlage drehte var_C2 bei Minus-Lagen median 31 Grad
daneben, zweimal sogar falsch herum; Plus-Lagen gingen.

Der Datensatz bleibt unveraendert (gleiche Episoden, gleicher Split, gleiche
Normierung). Geschrieben wird nur eine Gewichtsdatei fuer
``apps/train.py --episoden-gewichte``:

``--modus gewichten``  alle Episoden bleiben, MINUS bekommt das Gewicht
                       Frames_plus / Frames_minus -- beide Richtungen werden
                       gleich oft gezogen (Vorschlag Betreuer, Variante 1).
``--modus ausduennen`` zufaellig so viele PLUS-Episoden auf Gewicht 0, dass
                       gleich viele PLUS- wie MINUS-Frames bleiben (Variante 2:
                       "Plus-Fahrten rausnehmen").

"klein" (|Drehung| < 10 Grad) behaelt Gewicht 1. Drehung = Richtung der
Werkzeug-x-Achse um die Senkrechte (volle 360 Grad, wie tools/analyse_drehung.py),
Griff = erster Takt mit geschlossenem Greifer.

    python tools/drehung_ausgleich.py --dataset datasets/var_C2 --modus gewichten \
        --out einstellungen/gewichte_C3.json
"""

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from bc import config, replay
from analyse_drehung import diff, richtung, yaw360


def noetige_drehung(root, source_dir):
    """Drehung Start -> Griff einer Aufnahme-Episode in Grad (None ohne Griff)."""
    path = Path(root) / source_dir / "arrays.npz"
    with np.load(path) as z:
        state = np.asarray(z["observation__state"], dtype=float)
    grip = state[:, 13] > config.GRIPPER_THRESHOLD
    closing = np.flatnonzero(grip[1:] & ~grip[:-1])
    if not closing.size:
        return None
    at = int(closing[0]) + 1
    return diff(yaw360(state[at, 6:13]), yaw360(state[0, 6:13]))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="LeRobotDataset (mit meta/bc_export.json)")
    parser.add_argument("--modus", required=True, choices=("gewichten", "ausduennen"))
    parser.add_argument("--out", required=True, help="Gewichtsdatei (JSON)")
    parser.add_argument("--seed", type=int, default=0, help="Zufall fuer --modus ausduennen")
    args = parser.parse_args()

    info = json.loads((Path(args.dataset) / "meta" / "bc_export.json").read_text(encoding="utf-8"))
    episodes = info["episodes"]
    need = []
    for ep in episodes:
        try:
            need.append(noetige_drehung(ep["source"], ep["source_dir"]))
        except Exception as exc:  # noqa: BLE001
            print("  Episode %s: nicht lesbar (%s)" % (ep["episode_index"], exc), file=sys.stderr)
            need.append(None)
    klasse = [richtung(n) if n is not None else "unbekannt" for n in need]
    n_plus, n_minus = klasse.count("plus"), klasse.count("minus")
    if not n_plus or not n_minus:
        raise SystemExit("keine Plus- oder Minus-Episoden -- nichts auszugleichen")

    # Ausgeglichen wird die FRAME-Masse (der Sampler zieht Frames; Plus-Episoden
    # sind im Mittel laenger, gleiche Episodenzahl ergaebe noch ~50/40).
    length = np.array([float(ep.get("length") or 0) for ep in episodes])
    plus = [k for k, c in enumerate(klasse) if c == "plus"]
    minus = [k for k, c in enumerate(klasse) if c == "minus"]
    f_plus, f_minus = length[plus].sum(), length[minus].sum()
    weights = np.ones(len(episodes))
    if args.modus == "gewichten":
        w_minus = f_plus / f_minus
        weights[minus] = w_minus
        regel = "MINUS x %.3f (Frames plus %d / minus %d; Episoden %d / %d)" % (
            w_minus, f_plus, f_minus, n_plus, n_minus)
    else:
        rng = np.random.default_rng(args.seed)
        order = rng.permutation(plus)
        kept, mass = [], 0.0
        for k in order:
            if mass + length[k] > f_minus:
                break
            kept.append(int(k))
            mass += length[k]
        drop = sorted(set(plus) - set(kept))
        weights[drop] = 0.0
        regel = ("%d von %d PLUS-Episoden auf 0 (Seed %d), bleiben %d PLUS / %d MINUS "
                 "(Frames %d / %d)" % (len(drop), n_plus, args.seed, len(kept), n_minus, mass, f_minus))

    valid = np.array([n is not None for n in need])
    nd = np.array([n if n is not None else 0.0 for n in need])
    w = weights * valid

    def summary(wv):
        cls = {c: float(sum(wv[k] * length[k] for k in range(len(klasse)) if klasse[k] == c))
               for c in ("plus", "klein", "minus")}
        tot = sum(cls.values())
        return {"anteil_frames": {c: round(v / tot, 3) for c, v in cls.items()},
                "mittel_deg": round(float(np.sum(wv * length * nd) / np.sum(wv * length)), 1)}

    vorher, nachher = summary(valid.astype(float)), summary(w)
    out = {
        "dataset": str(args.dataset),
        "modus": args.modus,
        "regel": regel,
        "schwelle_deg": 10.0,
        "vorher": vorher,
        "nachher": nachher,
        "gewichte": [float(x) for x in weights],
        "noetig_deg": [None if n is None else round(float(n), 2) for n in need],
        "klasse": klasse,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("%d Episoden: plus %d, klein %d, minus %d, unbekannt %d"
          % (len(episodes), n_plus, klasse.count("klein"), n_minus, klasse.count("unbekannt")))
    print("Regel: %s" % regel)
    print("vorher : %s" % vorher)
    print("nachher: %s" % nachher)
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
