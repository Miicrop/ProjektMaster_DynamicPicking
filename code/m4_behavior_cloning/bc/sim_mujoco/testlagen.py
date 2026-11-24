"""Fester Testlagen-Satz fuer geschlossene Testfahrten (Phase 2).

Alle Modelle fahren dieselben Lagen, gezogen mit festem Seed und NIE im
Training (Plan, Abschnitt 2 "Testlagen"). Eine Lage entsteht auf demselben
Weg wie eine automatische Lage der Aufnahme (bc/auto_layout.py, apps/record.py):

* Bereich: Huelle der Tischpunkte ID0-8, ``RAND_M`` nach innen (wie am 19.11.:
  ``--randabstand 0.025``), nicht in einer Sperrzone (IGNORE), mindestens
  ``MIN_ABSTAND_M`` zu allen anderen Testlagen.
* Drehung: Greifer ueber volle 360 Grad gegen den geteachten PICK (die
  Aufnahme verteilt ebenfalls ueber 360 Grad, Fase) -- GESCHICHTET: je Lage
  ein eigener Abschnitt von 360/n Grad, Reihenfolge zufaellig. Bei 60 Lagen
  ist so jeder 60-Grad-Bereich gleich oft vertreten (reiner Zufall gab
  3 bis 17). Ausnahme: Gegen den PICK um -180..-120 Grad gedreht laeuft die IK
  (geseedet am PICK, q6 = 1,28) ueber die Grenze von Gelenk 6 -- dieselbe
  Grenze gilt in der Aufnahme. Liefert ein Abschnitt nach ``VERSUCHE_JE_DREHUNG``
  Positionen keine Lage, wird seine Drehung frei neu gezogen (``ersetzt``).
* Greifpose: ``auto_layout.place_pose`` (senkrecht zur Tischebene, Greifhoehe
  des geteachten PICK), IK geseedet am PICK.
* Pruefung wie vor einer Aufnahme: Ablauf ``pick_bis_griff`` mit diesem PICK
  aufloesen (ANFLUG/PRE_PICK berechnet), ideale Bahn planen und gegen das
  Kollisionsmodell (Tisch, Sperrzone, Zelle) und das Gelenktempo loesen
  (``noise.solve_ideal``). Scheitert das, wird neu gezogen.

Gespeichert je Lage: Greifpose und -gelenke, die Objektlage (x, y, Gier ueber
360 Grad, so wie ``Welt.objekt_an_punkt`` es hinlegt) und die ideale
TCP-Bahn mit dem Greiftakt -- Bezug fuer Querabweichung und Welligkeit in
``auswertung.py``.

    python -m bc.sim_mujoco.testlagen --erzeugen          # testlagen_v1.json
    python -m bc.sim_mujoco.testlagen --zeigen            # Uebersicht + Bild
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .. import config

_HERE = Path(__file__).resolve().parent
DATEI = _HERE / "testlagen_v1.json"
ABLAUF = _HERE.parents[1] / "sequences" / "pick_bis_griff.json"

#: Seed des Satzes -- nie fuer Aufnahmen verwenden (record.py --seed)
SEED = 77_2611_21
ANZAHL = 60
VERSUCHE_JE_DREHUNG = 60
RAND_M = 0.025
MIN_ABSTAND_M = 0.03


def _planer(robot):
    """Ablauf, Tisch, Sperrzonen und Kollisionsmodell wie in apps/record.py."""
    from ..collision import default_workspace
    from ..kinematics import Kinematics
    from ..sequence import load_sequence, resolve_sequence
    from ..table import KeepoutSurface, TableSurface
    from .. import obstacles

    seq = load_sequence(str(ABLAUF))
    resolved = resolve_sequence(seq, robot)
    return seq, resolved, Kinematics(robot), (default_workspace, TableSurface, KeepoutSurface,
                                             obstacles.load())


def plane_lage(robot, seq, resolved_ref, kin, werkzeug, xy, turn_deg, intern=False):
    """Eine Lage planen -> dict oder ValueError mit Grund.

    ``intern=True``: zusaetzlich (ideal, joints_ideal, waypoints, workspace) --
    fuer die Expertenfahrt der Abnahme (abnahme.py experte)."""
    from ..auto_layout import OverridePoints, place_pose
    from ..noise import PlanRejected, solve_ideal
    from ..ports import IKError
    from ..sequence import SequenceError, resolve_sequence
    from ..table import align_pose, clearance as table_clearance
    from ..trajectory import build_ideal_trajectory

    default_workspace, TableSurface, KeepoutSurface, zelle = werkzeug
    plane = resolved_ref.table
    pick_ref = resolved_ref.points["PICK"]
    height = table_clearance(plane, pick_ref["pose_quat"])
    upright = align_pose(np.asarray(pick_ref["pose_quat"], dtype=float), plane, height)
    pose = place_pose(upright, plane, xy, turn_deg, height)
    try:
        q = robot.ik(pose, np.asarray(pick_ref["joints"], dtype=float))
    except IKError as exc:
        raise ValueError("IK PICK: %s" % exc)
    try:
        resolved = resolve_sequence(seq, OverridePoints(robot, {"PICK": (q, pose)}))
    except (SequenceError, KeyError, IKError) as exc:
        raise ValueError("Ablauf: %s" % exc)
    waypoints = resolved.waypoints
    ideal = build_ideal_trajectory(waypoints, fk=robot.fk)
    z_min = min(wp.pose_quat[2] for wp in waypoints)
    ws = default_workspace(table_height_m=z_min - 0.15)
    ws.add_box(TableSurface(plane))
    if zelle is not None:
        ws.add_obstacles(zelle)
    for zone in resolved.keepouts:
        ws.add_box(KeepoutSurface(zone, plane))
    try:
        joints_ideal = solve_ideal(kin, ws, ideal, waypoints[0].joints)
    except PlanRejected as exc:
        raise ValueError("ideale Bahn: %s" % exc)
    tcp = np.asarray(ideal.poses_quat, dtype=float)[:, :3]
    grip = np.asarray(ideal.gripper, dtype=float)
    close = np.flatnonzero(grip >= config.GRIPPER_THRESHOLD)
    out = {"pick_pose": [float(v) for v in pose], "pick_joints": [float(v) for v in q],
           "greifer_drehung_grad": float(turn_deg),
           "ideal_tcp_mm": np.round(1e3 * tcp, 1).tolist(),
           "ideal_greiftakt": int(close[0]) if len(close) else None}
    if intern:
        return out, (ideal, joints_ideal, waypoints, ws)
    return out


def erzeugen(anzahl=ANZAHL, seed=SEED, verbose=True):
    from ..auto_layout import convex_hull, inside_with_margin
    from ..clock import SimClock
    from ..adapters.mujoco_robot import MujocoRobot

    robot = MujocoRobot(clock=SimClock()).connect()
    seq, resolved, kin, werkzeug = _planer(robot)
    hull = convex_hull([p["pose_quat"][:2] for p in resolved.table_points.values()])
    xs, ys = [p[0] for p in hull], [p[1] for p in hull]
    rng = np.random.default_rng(seed)
    width = 360.0 / anzahl
    turns = [-180.0 + width * (k + rng.uniform()) for k in rng.permutation(anzahl)]
    lagen, verworfen, ersetzt = [], {}, []
    tries, this_turn = 0, 0
    while len(lagen) < anzahl:
        tries += 1
        this_turn += 1
        if tries > 200 * anzahl:
            raise RuntimeError("nur %d Testlagen gefunden" % len(lagen))
        if this_turn > VERSUCHE_JE_DREHUNG:
            ersetzt.append(round(float(turns[len(lagen)]), 1))
            turns[len(lagen)] = float(rng.uniform(-180.0, 180.0))
            this_turn = 0
        xy = np.array([rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))])
        turn = float(turns[len(lagen)])
        if not inside_with_margin(hull, xy, RAND_M):
            continue
        if any(zone.blocks_object(xy) for zone in resolved.keepouts):
            verworfen["Sperrzone"] = verworfen.get("Sperrzone", 0) + 1
            continue
        if any(math.hypot(*(xy - np.array([l["objekt"]["x_m"], l["objekt"]["y_m"]]))) < MIN_ABSTAND_M
               for l in lagen):
            continue
        try:
            lage = plane_lage(robot, seq, resolved, kin, werkzeug, xy, turn)
        except ValueError as exc:
            grund = str(exc).split(":")[0]
            verworfen[grund] = verworfen.get(grund, 0) + 1
            continue
        robot.welt.objekt_an_punkt(joints=lage["pick_joints"])
        x, y, yaw, _T = robot.welt.objekt_lage()
        lage = dict(id=len(lagen), seed=int(seed * 1000 + len(lagen)),
                    objekt={"x_m": round(x, 5), "y_m": round(y, 5),
                            "gier_grad": round(math.degrees(yaw) % 360.0, 2)}, **lage)
        lagen.append(lage)
        this_turn = 0
        if verbose and len(lagen) % 10 == 0:
            print("  %d Testlagen (%d Zuege)" % (len(lagen), tries))
    data = {
        "_hinweis": ("Fester Testlagen-Satz der MuJoCo-Taktiksimulation -- NIE fuer Aufnahmen "
                     "verwenden. Erzeugt mit bc/sim_mujoco/testlagen.py --erzeugen."),
        "seed": seed, "anzahl": anzahl, "rand_m": RAND_M, "min_abstand_m": MIN_ABSTAND_M,
        "ablauf": "sequences/pick_bis_griff.json",
        "punkte": "bc/sim_mujoco/punkte_2026-11-19.json",
        "verworfen": verworfen, "zuege": tries,
        "drehung_ersetzt_grad": ersetzt,
        "lagen": lagen,
    }
    return data


def laden(path=DATEI):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def auswahl(data, text):
    """``"0-4"``, ``"0,3,7"`` oder None (alle) -> Liste der Lagen."""
    lagen = data["lagen"]
    if not text:
        return list(lagen)
    out = []
    for part in str(text).split(","):
        if "-" in part:
            a, b = part.split("-")
            out += [lagen[i] for i in range(int(a), int(b) + 1)]
        else:
            out.append(lagen[int(part)])
    return out


def bild(data, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ..sim_mujoco.szene import load_points

    pts = load_points()
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    for name, p in pts["punkte"].items():
        if name.startswith("ID"):
            ax.plot(p["pose_quat"][1] * 1e3, p["pose_quat"][0] * 1e3, "s", color="#888888", ms=5)
            ax.annotate(name, (p["pose_quat"][1] * 1e3, p["pose_quat"][0] * 1e3), fontsize=7,
                        color="#666666", xytext=(3, 3), textcoords="offset points")
    for k in pts.get("keepout") or []:
        cx, cy = k["center"]
        h = k["half_size"] * 1e3
        ax.add_patch(plt.Rectangle((cy * 1e3 - h, cx * 1e3 - h), 2 * h, 2 * h, color="#d62728", alpha=0.3))
    for l in data["lagen"]:
        o = l["objekt"]
        a = math.radians(o["gier_grad"])
        x, y = o["x_m"] * 1e3, o["y_m"] * 1e3
        ax.arrow(y, x, 18 * math.sin(a), 18 * math.cos(a), head_width=6, color="#1f77b4",
                 length_includes_head=True)
        ax.annotate(str(l["id"]), (y, x), fontsize=6, xytext=(-8, -9), textcoords="offset points")
    ax.set_xlabel("y Basis (mm)")
    ax.set_ylabel("x Basis (mm)")
    ax.invert_xaxis()
    ax.set_aspect("equal")
    ax.set_title("Testlagen v1 (%d, Seed %d): Pfeil = Objekt-x (lange Seite, Fase vorn)"
                 % (len(data["lagen"]), data["seed"]), fontsize=9)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fester Testlagen-Satz")
    parser.add_argument("--erzeugen", action="store_true")
    parser.add_argument("--zeigen", action="store_true")
    parser.add_argument("--datei", default=str(DATEI))
    parser.add_argument("--bild", default="Dokumentation/Bilder/MuJoCo/testlagen_v1.png")
    args = parser.parse_args(argv)
    if args.erzeugen:
        data = erzeugen()
        Path(args.datei).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
        print("-> %s (%d Lagen aus %d Zuegen, verworfen %s, Drehung ersetzt %s)"
              % (args.datei, len(data["lagen"]), data["zuege"], data["verworfen"],
                 data["drehung_ersetzt_grad"]))
    if args.zeigen or args.erzeugen:
        data = laden(args.datei)
        bild(data, args.bild)
        gier = [l["objekt"]["gier_grad"] for l in data["lagen"]]
        print("%d Lagen, x %.0f..%.0f mm, y %.0f..%.0f mm, Gier-Abschnitte (6 x 60 Grad) %s -> %s"
              % (len(data["lagen"]), 1e3 * min(l["objekt"]["x_m"] for l in data["lagen"]),
                 1e3 * max(l["objekt"]["x_m"] for l in data["lagen"]),
                 1e3 * min(l["objekt"]["y_m"] for l in data["lagen"]),
                 1e3 * max(l["objekt"]["y_m"] for l in data["lagen"]),
                 np.histogram(gier, bins=6, range=(0, 360))[0].tolist(), args.bild))


if __name__ == "__main__":
    main()
