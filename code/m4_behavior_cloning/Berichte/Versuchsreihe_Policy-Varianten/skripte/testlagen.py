"""Feste Testlagen der Versuchsreihe aus der Aufnahme 11.11. waehlen.

20 der Lagen B01-B50 (ohne "Test"/"Test 2": Licht an bzw. identisch mit einer
Trainingslage), gleichmaessig ueber Position und Drehung verteilt
(Farthest-Point-Sampling in x, y und Drehung mod 180; 100 mm ~ 45 Grad).
Diese Lagen kommen in KEINE Trainingsvariante.

  T60 = alle nicht verworfenen Episoden der 20 Lagen (Variantenvergleich)
  T20 = je Lage die Wiederholung mit dem kleinsten Rauschfaktor (schnelle
        Vergleiche; wenig Bildrauschen = wenig Replay-Artefakt, Testprotokoll
        2026-11-13 Test 7)

Ausgabe: ../testlagen.json
    python skripte/testlagen.py
"""
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
DATA = "data/2026-11-11"
N = 20

idx = json.loads((Path(DATA) / "index.json").read_text(encoding="utf-8"))["episodes"]
lagen = {}
for i, e in enumerate(idx):
    meta = json.loads((Path(DATA) / e["dir"] / "meta.json").read_text(encoding="utf-8"))
    md = meta["metadata"]
    if meta["discarded"] or str(md["block"]).startswith("Test"):
        continue
    lagen.setdefault(md["block"], []).append(dict(index=i, dir=e["dir"], noise=float(md.get("noise_scale") or 0),
                                                  xy=md["object_xy_m"], yaw=float(md["object_yaw_deg"])))
namen = sorted(lagen)
X = np.array([[lagen[b][0]["xy"][0], lagen[b][0]["xy"][1]] for b in namen]) * 1000
Y = np.array([lagen[b][0]["yaw"] % 180.0 for b in namen])


def abstand(i, j):
    dy = abs(((Y[i] - Y[j]) + 90) % 180 - 90) * (100.0 / 45.0)
    return float(np.sqrt(((X[i] - X[j]) ** 2).sum() + dy ** 2))


mitte = X.mean(axis=0)
wahl = [int(np.argmin(((X - mitte) ** 2).sum(1)))]
while len(wahl) < N:
    rest = [k for k in range(len(namen)) if k not in wahl]
    wahl.append(max(rest, key=lambda k: min(abstand(k, j) for j in wahl)))
test = sorted(namen[k] for k in wahl)
t60 = sorted(e["index"] for b in test for e in lagen[b])
t20 = sorted(min(lagen[b], key=lambda e: e["noise"])["index"] for b in test)
out = dict(aufnahme=DATA, testlagen=test, T60=t60, T20=t20,
           trainingslagen_11_11=sorted(set(namen) - set(test)) + ["Test", "Test 2"],
           regel=__doc__.strip().splitlines()[0])
dst = Path(__file__).resolve().parents[1] / "testlagen.json"
dst.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print("Testlagen:", test)
print("T60 (%d):" % len(t60), ",".join(map(str, t60)))
print("T20 (%d):" % len(t20), ",".join(map(str, t20)))
print("->", dst)
