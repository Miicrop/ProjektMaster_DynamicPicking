"""Nachlauf und Ueberschwingen bei Probefahrten, die UEBER dem Objekt anhalten (kein Schliessen).

Bezug ist der tiefste Soll-Punkt der Episode (Stopp-Punkt, aux.pose_ideal), nicht die Greifhoehe.
Je Episode:
  stopp_ueber_pick  Soll-Stopp ueber dem PICK-Punkt (mm, falls PICK in den Metadaten)
  tempo             groesstes Soll-Tempo im Abstieg der letzten 40 mm vor dem Stopp (mm/s)
  nachlauf          groesster Abstand Ist ueber Soll in z im Abstieg (mm)
  ueberschwingen    tiefster Ist-Punkt minus Stopp-Punkt (mm; < 0 = Arm faehrt UNTER den Stopp)
  seitlich          groesste xy-Abweichung Ist gegen Soll in der letzten Sekunde vor dem Stopp (mm)

Aufruf (aus m4_behavior_cloning):
  python Berichte/2026-11-20_Vorlaeufig_2026-11-19/skripte/nachlauf_stopp.py "35=<ordner>/ep_*/arrays.npz" ...
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
HZ = 15.0
for name, pat in [(a.split("=", 1)[0], a.split("=", 1)[1]) for a in sys.argv[1:]]:
    rows = []
    for f in sorted(glob.glob(pat)):
        z = np.load(f)
        st, idl = z["observation__state"], z["aux__pose_ideal"]
        k = int(np.argmin(idl[:, 2]))                     # Stopp-Punkt (tiefstes Soll)
        zs = idl[k, 2]
        win = np.flatnonzero(idl[:k + 1, 2] - zs < 0.040)  # letzte 40 mm Abstieg
        a = int(win[0]) if len(win) else max(0, k - 30)
        v = np.max(-np.diff(idl[a:k + 1, 2])) * HZ * 1000 if k > a else float("nan")
        lag = np.max(st[a:k + 1, 8] - idl[a:k + 1, 2]) * 1000
        after = st[a:min(len(st), k + 30), 8]              # bis 2 s nach dem Stopp
        over = (after.min() - zs) * 1000
        lat = np.max(np.linalg.norm(st[max(0, k - 15):k + 1, 6:8] - idl[max(0, k - 15):k + 1, :2], axis=1)) * 1000
        pick = None
        meta = Path(f).parent / "meta.json"
        if meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8")).get("metadata") or {}
            p = (m.get("points") or {}).get("PICK") or {}
            if "pose" in p:
                pick = (zs - p["pose"][2]) * 1000
        rows.append((v, lag, over, lat, pick if pick is not None else np.nan))
    if not rows:
        print(name, "keine Episoden"); continue
    r = np.array(rows, float)
    q = lambda c, p: np.nanpercentile(r[:, c], p)
    print(f"{name}: {len(r)} Ep. | Soll-Tempo {q(0,50):.0f} mm/s | Nachlauf median {q(1,50):.1f} / p95 {q(1,95):.1f} / max {np.nanmax(r[:,1]):.1f} mm"
          f" | Ueberschwingen unter Stopp: median {q(2,50):+.1f} / p5 {q(2,5):+.1f} / min {np.nanmin(r[:,2]):+.1f} mm"
          f" | seitlich max median {q(3,50):.1f} / p95 {q(3,95):.1f} mm"
          + (f" | Stopp ueber PICK median {q(4,50):.0f} mm (min {np.nanmin(r[:,4]):.0f})" if not np.all(np.isnan(r[:, 4])) else ""))
