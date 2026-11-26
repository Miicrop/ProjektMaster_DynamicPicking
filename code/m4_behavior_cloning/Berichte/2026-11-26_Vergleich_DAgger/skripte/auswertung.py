"""Auswertung Anlagenvergleich 26.11.: 6 Modelle (G2/G2b je ohne, DAgger fest, DAgger gemischt).

Je Fahrt aus vergleich.csv + rollout_000.npz + ausgabe.txt:
  Griff (quer/laengs/xy/Drehung/Spiel), Pendeln ueber dem Objekt, Licht (Kamerapruefung).
Pendeln: Phase "ueber dem Objekt" = TCP weniger als HOCH_MM ueber PICK-Hoehe bis Fahrtende,
  geteilt in oben (HOCH_MM..TIEF_MM) und unten (< TIEF_MM).
  weg_xy  : in der Phase seitlich gefahrener Weg (Summe |d xy|)
  netto   : |xy Ende - xy Anfang|
  umweg   : weg_xy - netto  (seitliches Hin und Her)
  wenden  : Richtungswechsel in x oder y mit >= 0,3 mm Hub
Aufruf: python auswertung.py <vergleichsordner> [weitere ...]  -> fahrten.csv, ausgabe auf stdout
"""
import csv, json, re, sys, statistics as st
from collections import defaultdict
from pathlib import Path
import numpy as np

HOCH_MM, TIEF_MM, HUB_MM = 150.0, 60.0, 0.3
KURZ = {"G2_licht_langsam_nur_griff": "G2", "G2-D_449_dagger2511_val_fest": "G2-D fest",
        "G2-D_449_dagger2511_val_gemischt": "G2-D gem", "G2b_580_dagger_nur_griff": "G2b",
        "G2b-D_669_dagger2511_val_fest": "G2b-D fest", "G2b-D_669_dagger2511_val_gemischt": "G2b-D gem",
        "G2c_579_nur_griff": "G2c"}


def wenden(x):
    """Richtungswechsel mit Hysterese HUB_MM."""
    n, ext, rich = 0, x[0], 0
    for v in x[1:]:
        if rich >= 0 and v < ext - HUB_MM:
            n += rich > 0; rich, ext = -1, v
        elif rich <= 0 and v > ext + HUB_MM:
            n += rich < 0; rich, ext = 1, v
        elif (rich >= 0 and v > ext) or (rich <= 0 and v < ext):
            ext = v
    return n


def pendeln(npz):
    d = np.load(npz, allow_pickle=True)
    p = 1e3 * d["lage_pick"][:3]
    t = 1e3 * d["tcp"][:, :3] - p
    g = np.flatnonzero(d["gripper_cmd"] > 0.5)
    end = int(g[0]) if len(g) else len(t)
    out = {}
    for name, lo, hi in (("oben", TIEF_MM, HOCH_MM), ("unten", -1e9, TIEF_MM), ("gesamt", -1e9, HOCH_MM)):
        idx = [i for i in range(end) if lo <= t[i, 2] < hi]
        if name != "gesamt" and idx:  # zusammenhaengend ab erstem Eintritt
            idx = list(range(idx[0], (idx[-1] + 1)))
        if len(idx) < 3:
            out.update({"%s_%s" % (k, name): None for k in ("weg", "umweg", "wenden", "takte", "spread")})
            continue
        xy = t[idx, :2]
        weg = float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())
        netto = float(np.linalg.norm(xy[-1] - xy[0]))
        out["weg_" + name] = round(weg, 2)
        out["umweg_" + name] = round(weg - netto, 2)
        out["wenden_" + name] = wenden(xy[:, 0]) + wenden(xy[:, 1])
        out["takte_" + name] = len(idx)
        out["spread_" + name] = round(float(np.median(d["ensemble_spread"][idx])), 4)
    return out


ZAHL = r"(-?[\d.]+)"


def licht(txt):
    o = {}
    for cam in ("wrist", "scene"):
        m = re.search(r"KAMERAPRUEFUNG %s: (\w+) -- Helligkeit %s.*?R/G %s.*?B/G %s.*?Saettigung %s.*?uebersteuert %s"
                      % (cam, ZAHL, ZAHL, ZAHL, ZAHL, ZAHL), txt)
        if m:
            o[cam + "_stufe"] = m.group(1)
            for k, v in zip(("hell", "rg", "bg", "satt", "ueber"), m.groups()[1:]):
                o["%s_%s" % (cam, k)] = float(v)
    m = re.search(r"== (\S+)  Lage", txt)
    o["zeit"] = m.group(1)[11:19] if m else ""
    return o


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def lade(ordner):
    ordner = Path(ordner)
    rows = []
    for r in csv.DictReader(open(ordner / "vergleich.csv", encoding="utf-8"), delimiter=";"):
        run = ordner / r["ordner"]
        r = {k: (f(v) if f(v) is not None else v) for k, v in r.items()}
        r["vergleich"] = ordner.name
        r["kurz"] = KURZ.get(r["modell"], r["modell"])
        r["erfolg"] = str(r["erfolg"]) == "True"
        if (run / "rollout_000.npz").is_file():
            r.update(pendeln(run / "rollout_000.npz"))
        if (run / "ausgabe.txt").is_file():
            r.update(licht((run / "ausgabe.txt").read_text(encoding="utf-8", errors="replace")))
        rows.append(r)
    return rows


def med(v, nd=1):
    v = [x for x in v if isinstance(x, (int, float))]
    return round(st.median(v), nd) if v else None


def p90(v):
    v = sorted(x for x in v if isinstance(x, (int, float)))
    return round(float(np.percentile(v, 90)), 1) if v else None


def main(argv):
    rows = [r for o in argv for r in lade(o)]
    out = Path(__file__).resolve().parent.parent / "fahrten.csv"
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, keys, delimiter=";"); w.writeheader(); w.writerows(rows)
    print("geschrieben:", out, len(rows), "Fahrten")
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
