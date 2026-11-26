"""Geplanter Stoss waehrend der Policy-Fahrt (DAgger mit Stoerung, Anwender 2026-11-26).

G2b liegt selten weit daneben, grosse Abweichungen fuer DAgger entstehen also
kaum von selbst. Deshalb wird die Fahrt einmal gezielt gestoert:

1. Unterschreitet der TCP eine zufaellige Hoehe ueber PICK (``hoehe_mm``),
   haelt die Policy an.
2. Der Arm wird ueber ``takte`` Regeltakte weich (Kosinus-Rampe) um einen
   zufaelligen waagrechten Versatz (``versatz_mm``, Richtung zufaellig) und
   eine Drehung um die senkrechte Achse (``drehung_grad``, Vorzeichen
   zufaellig) verschoben. Die Hoehe bleibt gleich. Eine IK fuer die Endpose,
   dazwischen linear im Gelenkraum (wenige mm, Unterschied vernachlaessigbar).
3. Die alten Vorhersagen werden verworfen, die Policy faehrt von dort weiter
   und muss sich selbst fangen. Beim Probe-Stopp entscheidet wie sonst die
   Griffpruefung, der Experte korrigiert den Rest.

Die Stoss-Takte werden beim DAgger-Mitschrieb wie Policy-Takte behandelt: Ihre
Labels fuehren zur Idealbahn zurueck (bc/dagger.relabel), das Modell lernt also
die Rueckfuehrung aus der verschobenen Lage.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from bc import geometry


@dataclass
class StoerungConfig:
    anteil: float = 0.0                  # Anteil der Fahrten mit Stoss (0 = aus)
    versatz_mm: tuple = (4.0, 8.0)       # waagrecht, Richtung zufaellig
    drehung_grad: tuple = (0.0, 4.0)     # um die Senkrechte, Vorzeichen zufaellig
    hoehe_mm: tuple = (70.0, 110.0)      # TCP ueber PICK, bei der gestossen wird
    takte: int = 6                       # Dauer des Stosses in Regeltakten

    @property
    def aktiv(self):
        return self.anteil > 0


def parse_range(text, name):
    """'4-8' oder '6' -> (min, max)."""
    parts = [p for p in str(text).replace(" ", "").split("-") if p != ""]
    try:
        vals = [float(p.replace(",", ".")) for p in parts]
    except ValueError:
        raise ValueError("%s: '%s' ist kein Bereich MIN-MAX" % (name, text))
    if len(vals) == 1:
        vals = vals * 2
    if len(vals) != 2 or vals[0] < 0 or vals[1] < vals[0]:
        raise ValueError("%s: '%s' ist kein Bereich MIN-MAX (0 <= MIN <= MAX)" % (name, text))
    return tuple(vals)


def rotate_about_z(quat, angle_rad):
    """Orientierung [w,x,y,z] um die senkrechte Achse der Basis drehen."""
    rz = geometry.quat_from_axis_angle([0.0, 0.0, 1.0], angle_rad)
    return geometry.quat_normalize(geometry.quat_multiply(rz, np.asarray(quat, dtype=float)))


class Stoerung:
    """Stoss einer Fahrt; ``ziehen`` je Fahrt, ``faellig`` je Takt, ``plan`` einmal."""

    def __init__(self, cfg: StoerungConfig, rng, pick_z_m):
        self.cfg = cfg
        self.rng = rng
        self.pick_z = float(pick_z_m)
        self.reset()

    def reset(self):
        self.aktiv = False
        self.erfolgt = False
        self.info = None

    def ziehen(self):
        """Zufall fuer die naechste Fahrt: ob und wie gestossen wird."""
        self.reset()
        c = self.cfg
        if not c.aktiv:
            return None
        r = self.rng
        self.aktiv = bool(r.random() < c.anteil)
        winkel = float(r.uniform(0.0, 2.0 * math.pi))
        self.info = {
            "geplant": self.aktiv,
            "hoehe_mm": float(r.uniform(*c.hoehe_mm)),
            "versatz_mm": float(r.uniform(*c.versatz_mm)),
            "richtung_grad": math.degrees(winkel),
            "drehung_grad": float(r.uniform(*c.drehung_grad)) * (1.0 if r.random() < 0.5 else -1.0),
            "takte": int(c.takte),
            "config": {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(c).items()},
        }
        return self.info

    def faellig(self, tcp):
        """Jetzt stossen? (einmal je Fahrt, sobald der TCP unter der Hoehe ist)."""
        if not self.aktiv or self.erfolgt:
            return False
        return 1e3 * (float(tcp[2]) - self.pick_z) <= self.info["hoehe_mm"]

    def plan(self, kin, q_now, step):
        """Gelenkziele des Stosses (takte, 6) ab ``q_now``; markiert den Stoss als erfolgt."""
        self.erfolgt = True
        i = self.info
        q_now = np.asarray(q_now, dtype=float)
        p0 = kin.fk_quat(q_now)
        p1 = p0.copy()
        w = math.radians(i["richtung_grad"])
        p1[0] += 1e-3 * i["versatz_mm"] * math.cos(w)
        p1[1] += 1e-3 * i["versatz_mm"] * math.sin(w)
        p1[3:] = rotate_about_z(p0[3:], math.radians(i["drehung_grad"]))
        q1 = np.asarray(kin.ik(p1, q_now), dtype=float)
        n = max(1, int(i["takte"]))
        s = 0.5 - 0.5 * np.cos(np.pi * np.arange(1, n + 1) / n)     # weich an und aus
        i.update({"takt": int(step), "start_tcp": [float(v) for v in p0[:3]],
                  "start_hoehe_mm": 1e3 * (float(p0[2]) - self.pick_z),
                  "dq_max_rad": float(np.max(np.abs(q1 - q_now)))})
        return q_now[None, :] + s[:, None] * (q1 - q_now)[None, :]
