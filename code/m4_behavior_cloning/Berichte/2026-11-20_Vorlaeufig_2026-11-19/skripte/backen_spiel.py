"""Vergleichslaeufe (vergleiche/<Zeit>/vergleich.csv): Versatz in Backen-Schliessrichtung, Drehung, Backen-Spiel.
Backenachse = Werkzeug-x um 28 Grad um Werkzeug-z (bc/sim_mujoco/parameter.json, geschaetzt; Ergebnis bei 23/118 Grad gleich).
Werkzeug-z zeigt nach unten -> Backenachse in der Basis = pick_drehung - 28 Grad.
Rest je Backe = 2,55 - |quer| - 7,5 * |sin dGier|  (Backen 44,8 / Objekt 39,7 mm, Backenlaenge ~15 mm).
Rest < 0: Backe setzt auf der Objektoberkante auf; >= 0,5 mm gilt als sicherer Griff.
Aufruf aus m4_behavior_cloning: python .../backen_spiel.py vergleiche/2026-11-24_15-39-34 [...]"""
import sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
ACH = 28.0
d = pd.concat([pd.read_csv(f + "/vergleich.csv", sep=";").assign(lauf=f.rstrip("/")[-8:]) for f in sys.argv[1:]])
d["m"] = d.modell.str.split("_").str[0]
psi = np.radians(d.pick_drehung_grad - ACH)
dx, dy = d.griff_x_mm - d.pick_x_mm, d.griff_y_mm - d.pick_y_mm
d["quer"] = (dx * np.cos(psi) + dy * np.sin(psi)).abs()
d["rest"] = 2.55 - d.quer - 7.5 * np.abs(np.sin(np.radians(d.drehung_grad)))
print(d.groupby("m").agg(fahrten=("xy_mm", "size"), xy_median=("xy_mm", "median"), xy_max=("xy_mm", "max"),
      quer_median=("quer", "median"), quer_max=("quer", "max"), rest_median=("rest", "median"),
      erfolg_xy10=("erfolg", "sum"), rest_ab_0_5=("rest", lambda s: (s >= 0.5).sum()),
      backe_auf_objekt=("rest", lambda s: (s < 0).sum())).round(1).to_string())
