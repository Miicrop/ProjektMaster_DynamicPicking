"""Folgt der Arm der kommandierten Drehung? Anlage (var_C2 16./17.11.) gegen Demos.

Je Takt: Gierwinkel (Werkzeug-x um die Senkrechte, aus Gelenken per FK) der
GEMESSENEN Gelenke gegen den des KOMMANDOS zwei Takte vorher (Totzeit wie in
den Demos). Kennzahlen je Fahrt (erste 60 Takte): mittlere |Abweichung|,
groesste Abweichung in Richtung plus/minus; Kommando-Schrittweite p95
(groesste Gelenkaenderung je Takt, Grad).

Aufruf (aus m4_behavior_cloning):
  python Berichte/2026-11-17_Drehbias_C3/skripte/ausfuehrung.py
-> daten/ausfuehrung.json
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nachstellen_offline as N  # noqa: E402  (setzt cwd und Pfade)

from bc import config  # noqa: E402
from bc.urdf import KinematicChain  # noqa: E402
from analyse_drehung import diff  # noqa: E402

LAG = 2
D = Path("Berichte/2026-11-17_Drehbias_C3")


def kennzahlen(chain, states, actions, tcp0=None):
    if tcp0 is None:
        off = N.tool_offset(chain, states)
        joints = states[:, :6]
    else:
        off = N.tool_offset(chain, np.concatenate([states[:1, :6], tcp0[None], [[0.0]]], 1))
        joints = states[:, :6]
    ym = [N.yaw_of_joints(chain, off, q) for q in joints]
    ya = [N.yaw_of_joints(chain, off, q[:6]) for q in actions]
    n = min(len(ym), 60)
    d = np.array([diff(ym[t], ya[t - LAG]) for t in range(LAG, n)])
    step = np.degrees(np.abs(np.diff(actions[:40, :6], axis=0))).max(1)
    return dict(abs_mittel=float(np.mean(np.abs(d))), max_plus=float(d.max()),
                max_minus=float(d.min()), cmd_schritt_p95=float(np.percentile(step, 95)),
                cmd_ende=float(diff(ya[-1], ya[0])))


def main():
    chain = KinematicChain.from_urdf(config.URDF_PATH)
    anlage = []
    for f in sorted(glob.glob("checkpoints/C2_nur_griff_ohne_1111/policy/rollouts/2026-11-1[67]_*/rollout_*.npz")):
        z = np.load(f)
        if len(z["joints"]) < 20:
            continue
        k = kennzahlen(chain, np.asarray(z["joints"], float), np.asarray(z["action"], float),
                       tcp0=np.asarray(z["tcp"][0], float))
        k["fahrt"] = str(Path(f).relative_to("checkpoints/C2_nur_griff_ohne_1111/policy/rollouts"))
        anlage.append(k)

    g = json.loads((D / "gewichte_C3_gewichten.json").read_text(encoding="utf-8"))
    info = json.loads(Path("datasets/var_C2/meta/bc_export.json").read_text(encoding="utf-8"))
    demos = []
    for ep, kl in list(zip(info["episodes"], g["klasse"]))[::6]:
        if kl not in ("plus", "minus"):
            continue
        with np.load(Path(ep["source"]) / ep["source_dir"] / "arrays.npz") as z:
            st, ac = np.asarray(z["observation__state"], float), np.asarray(z["action"], float)
        k = kennzahlen(chain, st, ac)
        k["klasse"] = kl
        demos.append(k)

    def zus(rows):
        a = {key: float(np.median([r[key] for r in rows]))
             for key in ("abs_mittel", "max_plus", "max_minus", "cmd_schritt_p95")}
        a["n"] = len(rows)
        a["groesste_abweichung_p90"] = float(np.percentile(
            [max(r["max_plus"], -r["max_minus"]) for r in rows], 90))
        return a

    out = {"lag_takte": LAG, "anlage": zus(anlage), "demos": zus(demos),
           "anlage_fahrten": anlage}
    for name in ("anlage", "demos"):
        print(name, out[name])
    (D / "daten" / "ausfuehrung.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
