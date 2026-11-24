"""Reset Control in der Neura-VM (nur Simulation!), danach warten bis erreichbar.

Hilft, wenn die VM nach servo_j-Abbruechen keine servo_j-Ziele mehr annimmt
("arm steht"), move_to_joints aber noch geht. Ablauf und Hintergrund:
Dokumentation/Laptop-Inbetriebnahme-Befunde.md, Abschnitt 3.3.

Aufruf (aus m4_behavior_cloning): python <dieses Skript>
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa: F401,E402

from bc.adapters import open_robot  # noqa: E402


def connect():
    r = open_robot("neura")
    r.connect(power_on=False)
    if r.in_simulation is not True:
        r.close()
        raise SystemExit("Abbruch: is_robot_in_simulation() ist nicht True -- kein Reset an der Anlage.")
    return r


r = connect()
raw = r._robot
print("reset_control:", raw.reset_control())
try:
    r.close()
except Exception:
    pass

t0 = time.time()
while True:
    time.sleep(3)
    try:
        r = connect()
        break
    except SystemExit:
        raise
    except Exception as exc:
        if time.time() - t0 > 180:
            raise SystemExit("VM nach 180 s nicht wieder erreichbar: %s" % exc)
print("wieder erreichbar nach %.0f s" % (time.time() - t0))
raw = r._robot
for name in ("reset_errors", "reset_collision"):
    try:
        print("%s:" % name, getattr(raw, name)())
    except Exception as exc:
        print("%s fehlgeschlagen: %s" % (name, exc))
try:
    print("Diagnose:", raw.get_diagnostics())
except Exception as exc:
    print("Diagnose fehlgeschlagen:", exc)
r.close()
