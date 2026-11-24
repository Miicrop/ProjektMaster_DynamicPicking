"""Hoehenprotokoll an jedem Greiferwechsel: Greifen (zu) und Ablegen (auf).

Wunsch Anwender 2026-11-02: Nach dem Vereinheitlichen der Greifhoehe
(apps/record.grasp_height) wurde nach ep_00006 trotzdem zu tief abgelegt.
Die Soll-Hoehen waren ueberall gleich; aufgefallen ist nur, dass der
Greifer bei ep_00006 schloss, als der Arm noch 0,5 mm ueber dem Ziel war
und weiter abwaerts fuhr. Vermutung: unterschiedlich schnelles Greifen ->
Versatz des Objekts im Greifer.

Darum je Greiferwechsel: absolute z (Soll/Ist), Tischhoehe an der Stelle,
Hoehe ueber dem Tisch, ob und wie schnell der Arm sich beim Schaltbefehl
noch hoch oder runter bewegte, und wie weit er bis zum Ende der Wartezeit
noch gefahren ist. Fuer Episoden UND die (nicht aufgezeichnete) Rueckfahrt
beim Zuruecklegen -- dort wird abgelegt.
"""

import json
import time
from pathlib import Path

import numpy as np

from . import config

#: Dateiname des Protokolls im Datensatzordner (eine JSON-Zeile je Wechsel)
LOG_NAME = "hoehen_protokoll.jsonl"
#: darunter gilt der Arm beim Schaltbefehl als stehend (mm/s)
STILL_MM_S = 1.0


def _arrays(episode):
    arrays = episode.arrays
    return (np.asarray(arrays["observation.state"], dtype=float),
            np.asarray(arrays["aux.pose_ideal"], dtype=float),
            np.asarray(arrays["action"], dtype=float)[:, -1])


def gripper_events(episode, table=None, rate_hz=config.CONTROL_RATE_HZ,
                   dwell_steps=config.GRIPPER_DWELL_STEPS):
    """Liste der Greiferwechsel einer Episode (oder Rueckfahrt) als dicts.

    Hoehen in mm. ``schritt``: erster Takt mit dem neuen Greiferbefehl.
    ``vz_mm_s``: z-Geschwindigkeit des Arms (Ist) um diesen Takt, positiv =
    aufwaerts. ``nachlauf_mm``: Ist-z am Ende der Wartezeit minus Ist-z beim
    Befehl (negativ = danach noch abwaerts gefahren).
    """
    state, ideal, gripper = _arrays(episode)
    n = len(gripper)
    if n < 2:
        return []
    closed = gripper >= config.GRIPPER_THRESHOLD
    out = []
    for k in np.flatnonzero(closed[1:] != closed[:-1]) + 1:
        k = int(k)
        x, y, z = state[k, 6:9]
        before, after = max(0, k - 1), min(n - 1, k + 1)
        vz = (state[after, 8] - state[before, 8]) / max(1, after - before) * float(rate_hz)
        end = min(n - 1, k + int(dwell_steps))
        table_z = table.height_at(x, y) if table is not None else None
        event = {
            "greifer": "zu" if closed[k] else "auf",
            "schritt": k,
            "z_soll_mm": round(1e3 * float(ideal[k, 2]), 2),
            "z_ist_mm": round(1e3 * float(z), 2),
            "z_ist_ende_mm": round(1e3 * float(state[end, 8]), 2),
            "z_ist_min_mm": round(1e3 * float(np.min(state[k:end + 1, 8])), 2),
            "nachlauf_mm": round(1e3 * float(state[end, 8] - z), 2),
            "vz_mm_s": round(1e3 * float(vz), 1),
            "bewegung": ("steht" if abs(1e3 * vz) < STILL_MM_S
                         else "hoch" if vz > 0 else "runter"),
            "x_mm": round(1e3 * float(x), 1),
            "y_mm": round(1e3 * float(y), 1),
        }
        if table_z is not None:
            event["tisch_mm"] = round(1e3 * float(table_z), 2)
            event["ueber_tisch_soll_mm"] = round(
                1e3 * float(ideal[k, 2] - table.height_at(ideal[k, 0], ideal[k, 1])), 2)
            event["ueber_tisch_ist_mm"] = round(1e3 * float(z - table_z), 2)
            event["ueber_tisch_ende_mm"] = round(1e3 * float(state[end, 8] - table_z), 2)
        out.append(event)
    return out


def format_event(event, label=""):
    """Eine Konsolenzeile, z. B. fuer "Episode 2" oder "Zuruecklegen"."""
    over = ""
    if "ueber_tisch_ist_mm" in event:
        over = ", ueber Tisch soll %.2f / ist %.2f -> Ende %.2f mm" % (
            event["ueber_tisch_soll_mm"], event["ueber_tisch_ist_mm"],
            event["ueber_tisch_ende_mm"])
    return ("Hoehe %sGreifer %s: z soll %.2f / ist %.2f mm%s, Arm %s (%+.1f mm/s), "
            "danach %+.2f mm"
            % (label + " " if label else "", event["greifer"], event["z_soll_mm"],
               event["z_ist_mm"], over, event["bewegung"], event["vz_mm_s"],
               event["nachlauf_mm"]))


def append_log(root, events, **context):
    """Wechsel als JSON-Zeilen an ``root``/LOG_NAME anhaengen.

    ``context``: z. B. ``episode="ep_00006"``, ``fahrt="zuruecklegen"``.
    Fehler beim Schreiben brechen den Lauf nicht ab (nur Meldung).
    """
    if root is None or not events:
        return
    path = Path(root) / LOG_NAME
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(dict(context, zeit=stamp, **event),
                                        ensure_ascii=False) + "\n")
    except OSError as exc:
        print("Hoehenprotokoll nicht geschrieben: %s" % exc)
