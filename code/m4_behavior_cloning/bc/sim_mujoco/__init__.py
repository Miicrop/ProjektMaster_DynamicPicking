"""MuJoCo-Taktiksimulation (Plan: Dokumentation/MuJoCo-Taktiksimulation-Plan.md).

Zweck: Aufnahme-Einstellungen unter GLEICHEN, geschlossenen Testbedingungen
vergleichen -- kein Sim-to-Real. Die Pipeline bleibt unveraendert; dazu
kommen nur zwei Adapter, die beide auf dieselbe Welt zugreifen:

    bc/adapters/mujoco_robot.py  (RobotPort)   --+
    bc/adapters/cam_mujoco.py    (CameraPort)  --+--> :func:`welt`
                                                      (bc/sim_mujoco/szene.py)

Die Welt haelt Arm (mit Folgemodell), Greifer, Objekt und die Renderer. Die
Zeit kommt von aussen (SimClock oder Host-Uhr): vor jedem Zustandsabgriff
und jedem Bild wird bis zur aktuellen Uhrzeit nachgerechnet
(:meth:`szene.Welt.weiter_bis`). Deshalb gehoeren Roboter und Kameras an
DIESELBE Uhr -- record.py reicht sie ohnehin an beide durch.

Module:
    parameter.json / parameter.py  Masse, Kameralage, Licht, Folgemodell
    szene.py        MJCF aus der URDF-Kette + Welt (Zustand, Greifen, Rendern)
    folgemodell.py  Nachlauf je Gelenk, Anpassung an echte Aufnahmen
    kalibrierung.py Kameralage aus den ArUco-Markern der Referenzbilder
    abnahme.py      Abnahmebilder (Render neben Referenz, Folgemodell, Episode)
    punkte_2026-11-19.json  Punkte-Datenbank wie am 19.11. (CLEAR_FOV, PICK,
                    Tischpunkte ID0-8, IGNORE)
"""

import threading

_LOCK = threading.Lock()
_WELT = {"welt": None}


def welt(clock=None, neu=False, **kwargs):
    """Die prozessweite Welt (eine Szene fuer Roboter UND Kameras).

    ``neu=True`` baut sie frisch (Tests, neuer Lauf). ``clock`` wird beim
    ersten Aufruf gesetzt; spaetere Aufrufe mit einer ANDEREN Uhr sind ein
    Fehler, denn dann liefen Bild und Zustand auf verschiedenen Zeitachsen.
    """
    from .szene import Welt

    with _LOCK:
        current = _WELT["welt"]
        if current is None or neu:
            current = Welt(clock=clock, **kwargs)
            _WELT["welt"] = current
        elif clock is not None and current.clock is not clock:
            if current.clock is None:
                current.clock = clock
            else:
                raise ValueError("MuJoCo-Welt laeuft schon mit einer anderen Uhr -- "
                                 "Roboter und Kameras brauchen dieselbe Uhr")
        return current


def welt_vorhanden():
    return _WELT["welt"] is not None


def welt_verwerfen():
    """Welt freigeben (Renderer schliessen). Naechster :func:`welt` baut neu."""
    with _LOCK:
        current = _WELT["welt"]
        _WELT["welt"] = None
    if current is not None:
        current.close()
