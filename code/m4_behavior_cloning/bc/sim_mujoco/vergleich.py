"""Vergleich geschlossener Testfahrten mehrerer Modelle (Phase 2).

    python -m bc.sim_mujoco.vergleich SIM_basis_400 SIM_basis_600 [--md]

Liest je Modell ``data_sim_mujoco/rollouts_<name>/sim_auswertung.json``
(apps/infer.py --robot mujoco --testlagen) und die letzte Val-Zeile aus
``checkpoints/<name>/train_log.csv``. Kennzahlen je Modell:

- Griff gelungen (mit 95-%-Wilson-Intervall: 60 Lagen sind wenige)
- naechste Annaeherung median, Anteil <= 10 mm, p90
- Greif-xy median/p90, Gier-Fehler |median|/p90
- Tisch < 0 / < -10 mm, Sprung-Abbrueche (> 0,35 rad) je Gelenk,
  Endstellung erreicht, Welligkeit median
- getrennt nach Drehbedarf: |q6 an der Greifpose - q6 an CLEAR_FOV|
  unter/ueber dem Median der Testlagen (wie viel das Werkzeug drehen muss;
  einen Anflug-Drehversatz gibt es in der geschlossenen Fahrt nicht)

Testfahrten: ``testfahrt.py --ohne-tisch --verzoegerung 2`` (wie die
VM-Fahrten). Namen mit Zusatz (``<modell>_alt_...``) sind weitere Fahrten
desselben Modells; die Val-Zeile kommt vom Modell. "Griff ueber Tisch":
Griff und Tisch min >= 0 -- ohne Tischebene im Kollisionsmodell folgt der
Arm in der Sim auch unter den Tisch.

Trainingsbereich (Befund 21.11. abends, Stand 9.7): Die Aufnahme dreht das
Objekt nur um +-45 Grad (+ Varianten +-15) um die Mitte -- Gelenk 6 dreht in
den Sim-Daten von CLEAR_FOV zum PICK um -81..+63 Grad (real 19.11.: -93..+83).
Die Testlagen ueberdecken 360 Grad; 33 von 60 liegen ausserhalb. Dort greift
die Policy um 180 Grad verdreht (Fase falsch herum). Deshalb zusaetzlich:
"im Trainingsbereich" (q6-Drehung -86..+68 Grad, 27 Lagen) und
"Griff richtig herum" (Griff und |Gier| <= 90 Grad).

Paarweise (gleiche Lagen): McNemar-Test auf die Griffe -- nur die Lagen, auf
denen genau eines der Modelle greift, tragen Information.
"""

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

ROLLOUTS = "data_sim_mujoco/rollouts_%s/sim_auswertung.json"
#: q6-Drehung CLEAR_FOV -> PICK der Sim-Basisdaten (-81..+63 Grad) mit 5 Grad Rand
TRAININGSBEREICH_GRAD = (-86.0, 68.0)
TRAIN_LOG = "checkpoints/%s/train_log.csv"


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def mcnemar_p(b, c):
    """Exakter zweiseitiger McNemar-Test (Binomial auf die diskordanten Paare)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2 * p)


def drehbedarf(signed=False):
    """|q6(pick) - q6(CLEAR_FOV)| je Testlage in Grad (``signed``: mit Vorzeichen)."""
    from . import testlagen

    data = testlagen.laden()
    punkte = json.loads(Path(data["punkte"]).read_text(encoding="utf-8"))
    q6_start = float(punkte["punkte"]["CLEAR_FOV"]["joints"][5])
    d = {l["id"]: math.degrees(float(l["pick_joints"][5]) - q6_start) for l in data["lagen"]}
    return d if signed else {k: abs(v) for k, v in d.items()}


def im_trainingsbereich(dq6):
    return TRAININGSBEREICH_GRAD[0] <= dq6 <= TRAININGSBEREICH_GRAD[1]


def val_zeile(name):
    while not Path(TRAIN_LOG % name).is_file() and "_" in name:
        name = name.rsplit("_", 1)[0]   # Zusatz einer weiteren Testfahrt
    path = Path(TRAIN_LOG % name)
    if not path.is_file():
        return {}
    rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r.get("val_joint_mae_rad")]
    if not rows:
        return {}
    r = rows[-1]
    return {"step": int(r["step"]), "val_mae_rad": float(r["val_joint_mae_rad"]),
            "val_p95_rad": float(r["val_joint_p95_rad"]), "val_greifer": float(r["val_gripper_acc"]),
            "val_loss": float(r["val_loss"])}


def kennzahlen(rows):
    n = len(rows)
    if not n:
        return {"fahrten": 0, "griff": 0}

    def vals(key, absolute=False):
        v = [r[key] for r in rows if r.get(key) is not None]
        return np.abs(v) if absolute else np.asarray(v, dtype=float)

    def q(key, p, absolute=False):
        v = vals(key, absolute)
        return round(float(np.percentile(v, p)), 1) if len(v) else None

    griffe = sum(1 for r in rows if r["griff"])
    ann = vals("annaeherung_mm")
    sprung = [0] * 6
    for r in rows:
        if r.get("abbruch") == "sprung" and r.get("sprung_gelenk_abbruch"):
            sprung[int(r["sprung_gelenk_abbruch"]) - 1] += 1
    abbruch = {}
    for r in rows:
        abbruch[r["abbruch"]] = abbruch.get(r["abbruch"], 0) + 1
    return {
        "fahrten": n,
        "griff": griffe,
        "griff_quote": round(griffe / n, 3),
        "griff_95": wilson(griffe, n),
        "griff_ueber_tisch": sum(1 for r in rows if r["griff"] and not r.get("unter_tisch")),
        "griff_richtig": sum(1 for r in rows if r["griff"] and r.get("gier_fehler_grad") is not None
                             and abs(r["gier_fehler_grad"]) <= 90.0),
        "gier_ueber_90": sum(1 for r in rows if r.get("gier_fehler_grad") is not None
                             and abs(r["gier_fehler_grad"]) > 90.0),
        "annaeherung_median_mm": q("annaeherung_mm", 50),
        "annaeherung_le10": int((ann <= 10.0).sum()) if len(ann) else 0,
        "annaeherung_p90_mm": q("annaeherung_mm", 90),
        "greif_xy_median_mm": q("greif_xy_mm", 50),
        "greif_xy_p90_mm": q("greif_xy_mm", 90),
        "gier_median_abs_grad": q("gier_fehler_grad", 50, True),
        "gier_p90_abs_grad": q("gier_fehler_grad", 90, True),
        "unter_tisch": sum(1 for r in rows if r.get("unter_tisch")),
        "unter_tisch_10": sum(1 for r in rows if r.get("unter_tisch_10")),
        "sprung_abbruch_je_gelenk": sprung,
        "fahrten_mit_sprung_je_gelenk": [int(v) for v in
                                         (np.array([r.get("sprung_takte") or [0] * 6 for r in rows]) > 0).sum(0)],
        "endstellung": abbruch.get("endstellung", 0),
        "abbruch": abbruch,
        "welligkeit_median_mm": q("welligkeit_mm", 50),
        "quer_p95_median_mm": q("quer_p95_mm", 50),
    }


def laden(name):
    d = json.loads(Path(ROLLOUTS % name).read_text(encoding="utf-8"))
    return d["fahrten"]


def vergleich(names):
    dreh = drehbedarf()
    dreh_s = drehbedarf(signed=True)
    grenze = float(np.median(list(dreh.values())))
    out = {"drehbedarf_grenze_grad": round(grenze, 1), "modelle": {}}
    fahrten = {}
    for name in names:
        rows = laden(name)
        fahrten[name] = {r["lage"]: r for r in rows}
        out["modelle"][name] = {
            "alle": kennzahlen(rows),
            "wenig_drehung": kennzahlen([r for r in rows if dreh[r["lage"]] <= grenze]),
            "viel_drehung": kennzahlen([r for r in rows if dreh[r["lage"]] > grenze]),
            "im_training": kennzahlen([r for r in rows if im_trainingsbereich(dreh_s[r["lage"]])]),
            "ausserhalb": kennzahlen([r for r in rows if not im_trainingsbereich(dreh_s[r["lage"]])]),
            "val": val_zeile(name),
        }
    paare = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = sorted(set(fahrten[a]) & set(fahrten[b]))
            only_a = sum(1 for k in common if fahrten[a][k]["griff"] and not fahrten[b][k]["griff"])
            only_b = sum(1 for k in common if fahrten[b][k]["griff"] and not fahrten[a][k]["griff"])
            paare["%s|%s" % (a, b)] = {"lagen": len(common), "nur_%s" % a: only_a, "nur_%s" % b: only_b,
                                       "mcnemar_p": round(mcnemar_p(only_a, only_b), 3)}
    out["paare"] = paare
    return out


def tabelle(v):
    names = list(v["modelle"])
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]

    def row(label, f):
        lines.append("| %s | %s |" % (label, " | ".join(f(v["modelle"][n]) for n in names)))

    def fmt(x):
        return "–" if x is None else ("%g" % x if isinstance(x, (int, float)) else str(x))

    row("Griff (95-%-Intervall)", lambda m: "**%d/%d** (%s–%s)" % (
        m["alle"]["griff"], m["alle"]["fahrten"], *[fmt(round(100 * x)) + " %" if x is not None else "–"
                                                    for x in m["alle"]["griff_95"]]))
    row("davon Werkzeug nie unter dem Tisch", lambda m: "%d" % m["alle"].get("griff_ueber_tisch", 0))
    row("davon richtig herum (\\|Gier\\| ≤ 90°)", lambda m: "%d" % m["alle"].get("griff_richtig", 0))
    row("Griff im Trainingsbereich (95-%-Intervall) / außerhalb", lambda m: "**%d/%d** (%s) · %d/%d" % (
        m["im_training"]["griff"], m["im_training"]["fahrten"],
        "–".join(fmt(round(100 * x)) + " %" for x in m["im_training"]["griff_95"]),
        m["ausserhalb"]["griff"], m["ausserhalb"]["fahrten"]))
    row("Gier \\|median\\| im Trainingsbereich / außerhalb; \\|Gier\\| > 90°", lambda m: "%s° / %s° · %d" % (
        fmt(m["im_training"]["gier_median_abs_grad"]), fmt(m["ausserhalb"]["gier_median_abs_grad"]),
        m["alle"]["gier_ueber_90"]))
    row("Annäherung median im Trainingsbereich", lambda m: "%s mm" % fmt(m["im_training"]["annaeherung_median_mm"]))
    row("Griff wenig / viel Drehung (≤/> %.0f°)" % v["drehbedarf_grenze_grad"],
        lambda m: "%d/%d · %d/%d" % (m["wenig_drehung"]["griff"], m["wenig_drehung"]["fahrten"],
                                     m["viel_drehung"]["griff"], m["viel_drehung"]["fahrten"]))
    row("Annäherung median / ≤ 10 mm / p90", lambda m: "%s mm / %d / %s mm" % (
        fmt(m["alle"]["annaeherung_median_mm"]), m["alle"]["annaeherung_le10"], fmt(m["alle"]["annaeherung_p90_mm"])))
    row("Greif-xy median / p90", lambda m: "%s / %s mm" % (fmt(m["alle"]["greif_xy_median_mm"]),
                                                          fmt(m["alle"]["greif_xy_p90_mm"])))
    row("Gier-Fehler \\|median\\| / p90", lambda m: "%s / %s°" % (fmt(m["alle"]["gier_median_abs_grad"]),
                                                                 fmt(m["alle"]["gier_p90_abs_grad"])))
    row("Tisch < 0 / < −10 mm", lambda m: "%d / %d" % (m["alle"]["unter_tisch"], m["alle"]["unter_tisch_10"]))
    row("Sprung-Abbrüche je Gelenk 1–6", lambda m: " ".join(str(x) for x in m["alle"]["sprung_abbruch_je_gelenk"]))
    row("Endstellung erreicht", lambda m: "%d" % m["alle"]["endstellung"])
    row("Abbrüche", lambda m: ", ".join("%s %d" % kv for kv in sorted(m["alle"]["abbruch"].items())))
    row("Welligkeit median", lambda m: "%s mm" % fmt(m["alle"]["welligkeit_median_mm"]))
    row("Val-MAE / p95 (Training, eigene Val)", lambda m: "%s / %s rad" % (
        fmt(round(m["val"]["val_mae_rad"], 4)) if m["val"] else "–",
        fmt(round(m["val"]["val_p95_rad"], 4)) if m["val"] else "–"))
    out = "\n".join(lines)
    for k, p in v["paare"].items():
        a, b = k.split("|")
        out += "\n\nPaarweise %s gegen %s: nur %s greift %d, nur %s greift %d (McNemar p = %s)" % (
            a, b, a, p["nur_%s" % a], b, p["nur_%s" % b], p["mcnemar_p"])
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("namen", nargs="+")
    parser.add_argument("--json", default=None, help="Ergebnis zusaetzlich als JSON")
    args = parser.parse_args(argv)
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    v = vergleich(args.namen)
    print(tabelle(v))
    if args.json:
        Path(args.json).write_text(json.dumps(v, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
