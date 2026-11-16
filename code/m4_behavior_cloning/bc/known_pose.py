"""Policy-Test mit bekannter Lage (Anwender 2026-11-16).

Zwischending aus Inferenz und Datenaufnahme: die Policy faehrt selbst, aber
die Objektlage ist bekannt wie bei der Aufnahme -- PICK und Tisch live aus
der Steuerung, die Idealbahn aus derselben Ablaufdatei wie die Aufnahme.
So laesst sich je Takt messen, wie weit die Policy abweicht, und am Griff
bzw. beim Stopp, wo sie gegriffen haette.

Qt-frei und ohne Roboterverbindung testbar; ``apps/infer.py --lage-bekannt``
benutzt es.

Kennzahlen je Takt (TCP gemessen, Basis-KS):

* ``path_dev``  Abstand zur Idealbahn (Polylinie bis zum Greifen)
* ``xy_pick``   waagrechter Abstand zu PICK
* ``dz_pick``   Hoehe des TCP ueber PICK (positiv = darueber)
* ``table``     Hoehe des TCP ueber der Tischebene an seiner Stelle
* ``yaw_err``   Drehung um die Tischnormale gegen PICK, Grad, modulo 180
                (Parallelgreifer) auf -90..90

Probegriff (``--probegriff``):

* ``tisch``  -- echter Griff, Geofence wie immer (TCP >= 3 mm ueber Tisch)
* ``objekt`` -- Stopp, bevor die Backenspitzen die Objektoberkante erreichen:
  TCP >= PICK + PROBE_OBJECT_TOP_ABOVE_PICK_M + PROBE_GAP_M ueber dem Tisch.
  Beim Stopp wird der Rest des vorhergesagten Chunks gespeichert -- daraus
  :func:`predicted_grasp`, wo die Policy gegriffen haette.
"""

from dataclasses import dataclass

import numpy as np

from . import config
from .metrics import distance_to_path
from .table import clearance, yaw_deg

PROBE_MODES = ("tisch", "objekt")

#: Spaltennamen der CSV je Fahrt (apps/infer.py, ``policy_test.csv``)
CSV_COLUMNS = (
    "fahrt", "pick_x_mm", "pick_y_mm", "pick_drehung_grad", "probegriff", "stopp",
    "griff_takt", "griff_xy_mm", "griff_dz_mm", "griff_drehung_grad", "griff_tisch_mm",
    "stopp_takt", "stopp_xy_mm", "stopp_dz_mm", "stopp_drehung_grad", "stopp_tisch_mm",
    "vorhersage_schliesst", "vorhersage_xy_mm", "vorhersage_dz_mm", "vorhersage_drehung_grad",
    "bahn_p95_mm", "bahn_max_mm", "tisch_min_mm",
    "korrektur_dx_mm", "korrektur_dy_mm", "korrektur_xy_mm", "korrektur_drehung_grad",
    "abstieg_mm", "danach",
)


@dataclass
class KnownPose:
    """Bekannte Lage einer Fahrt."""

    pick: np.ndarray            # (7,) PICK-Pose (TCP beim Greifen), Basis-KS
    table: object               # bc/table.TablePlane
    path: np.ndarray            # (N, 3) Idealbahn des TCP bis zum Greifen
    source: str = "Steuerung"
    #: Tischpunkte (Posen) und Sperrzonen -- fuer neue Lagen beim Umlegen
    region: list = None
    keepouts: list = None
    #: Idealbahn bis zum Greifen (bc/trajectory.IdealTrajectory, gekuerzt) --
    #: Quelle der DAgger-Labels (bc/dagger.py); None bei aelteren Aufrufern
    ideal: object = None

    @property
    def pick_yaw_deg(self):
        return yaw_deg(self.pick, self.table)

    @property
    def pick_above_table_m(self):
        return clearance(self.table, self.pick[:3])

    def describe(self):
        return ("PICK x %.1f y %.1f mm, %.1f mm ueber Tisch, Drehung %.1f Grad (%s)"
                % (1e3 * self.pick[0], 1e3 * self.pick[1], 1e3 * self.pick_above_table_m,
                   self.pick_yaw_deg, self.source))


def approach_end(ideal, tail=0):
    """Index hinter dem ersten Schliessen der Idealbahn (+ ``tail`` Takte)."""
    poses = np.asarray(ideal.poses_quat, dtype=float)
    grip = np.asarray(ideal.gripper, dtype=float) > config.GRIPPER_THRESHOLD
    closing = np.flatnonzero(grip[1:] & ~grip[:-1])
    end = int(closing[0]) + 2 if closing.size else len(poses)
    return min(len(poses), end + int(tail))


def approach_path(ideal):
    """TCP-Positionen der Idealbahn bis zum ersten Schliessen des Greifers."""
    return np.asarray(ideal.poses_quat, dtype=float)[:approach_end(ideal), :3]


def approach_ideal(ideal, tail=config.DAGGER_TAIL_STEPS):
    """Idealbahn bis kurz nach dem Schliessen (Kopie, fuer DAgger-Labels)."""
    from dataclasses import replace

    end = approach_end(ideal, tail)
    return replace(ideal, poses_quat=np.asarray(ideal.poses_quat)[:end],
                   gripper=np.asarray(ideal.gripper)[:end],
                   dwell_mask=np.asarray(ideal.dwell_mask)[:end],
                   dist_to_anchor=np.asarray(ideal.dist_to_anchor)[:end],
                   joints=None if ideal.joints is None else np.asarray(ideal.joints)[:end])


def from_resolved(resolved, ideal, source="Steuerung"):
    """Aus einem aufgeloesten Ablauf (bc/sequence) und seiner Idealbahn."""
    if "PICK" not in resolved.points:
        raise ValueError("Ablauf ohne PICK -- Lage nicht bekannt")
    if resolved.table is None:
        raise ValueError("Ablauf ohne Tischpunkte -- Tisch nicht bekannt (fehlend: %s)"
                         % (", ".join(resolved.table_missing) or "keine Angabe"))
    pick = np.asarray(resolved.points["PICK"]["pose_quat"], dtype=float)
    region = [np.asarray(p["pose_quat"], dtype=float) for p in resolved.table_points.values()]
    return KnownPose(pick, resolved.table, approach_path(ideal), source,
                     region=region, keepouts=list(resolved.keepouts or []),
                     ideal=approach_ideal(ideal))


def load(sequence_path, robot, planner=None):
    """Lage live aus der Steuerung: Ablauf aufloesen, Idealbahn planen.

    ``planner``: ``recording.planner`` aus bc_policy.json (Tempo wie in der
    Aufnahme), sonst die Werte aus config. Rueckgabe ``(known, resolved)``.
    """
    from .sequence import load_sequence, resolve_sequence
    from .trajectory import build_ideal_trajectory

    planner = planner or {}
    resolved = resolve_sequence(load_sequence(sequence_path), robot)
    ideal = build_ideal_trajectory(
        resolved.waypoints, fk=robot.fk,
        transit_speed=planner.get("transit_speed_ms") or config.TRANSIT_SPEED_MS,
        approach_speed=planner.get("approach_speed_ms") or config.APPROACH_SPEED_MS,
        ptp_joint_speed=planner.get("ptp_joint_speed_rads") or config.PTP_JOINT_SPEED_RADS)
    return from_resolved(resolved, ideal), resolved


def probe_clearance(mode, known):
    """Mindestabstand des TCP zur Tischebene (m) fuer den Probegriff."""
    if mode == "objekt":
        return (known.pick_above_table_m + config.PROBE_OBJECT_TOP_ABOVE_PICK_M
                + config.PROBE_GAP_M)
    return config.TABLE_MIN_CLEARANCE_M


def _yaw_err(pose, known):
    return float((yaw_deg(pose, known.table) - known.pick_yaw_deg + 90.0) % 180.0 - 90.0)


def track(tcp, known):
    """Kennzahlen je Takt fuer gemessene TCP-Posen ``tcp`` (N, 7)."""
    tcp = np.asarray(tcp, dtype=float).reshape(-1, 7)
    if not len(tcp):
        return {k: np.zeros(0) for k in ("path_dev", "xy_pick", "dz_pick", "table", "yaw_err")}
    return {
        "path_dev": distance_to_path(tcp[:, :3], known.path),
        "xy_pick": np.linalg.norm(tcp[:, :2] - known.pick[:2], axis=1),
        "dz_pick": tcp[:, 2] - known.pick[2],
        "table": np.array([clearance(known.table, p[:3]) for p in tcp]),
        "yaw_err": np.array([_yaw_err(p, known) for p in tcp]),
    }


def snapshot(rows, index):
    """Kennzahlen eines Takts als dict; None ohne Index oder ausserhalb."""
    n = len(rows["xy_pick"])
    if index is None or not n or not -n <= index < n:
        return None
    return {"step": int(index % n),
            "xy_m": float(rows["xy_pick"][index]),
            "dz_m": float(rows["dz_pick"][index]),
            "yaw_deg": float(rows["yaw_err"][index]),
            "table_m": float(rows["table"][index]),
            "path_dev_m": float(rows["path_dev"][index])}


def predicted_grasp(actions, fk, known):
    """Wo haette die Policy gegriffen? Aus dem Rest des Chunks beim Stopp.

    ``actions``: (K, 7) Gelenkziele + Greifer, ab dem abgelehnten Ziel.
    Greifpunkt = erstes Ziel mit geschlossenem Greifer; schliesst der Chunk
    nicht, das tiefste Ziel (``closes`` False). None ohne Actions.
    """
    actions = np.asarray(actions, dtype=float)
    if actions.ndim != 2 or not len(actions):
        return None
    closed = np.flatnonzero(actions[:, -1] > config.GRIPPER_THRESHOLD)
    poses = np.array([np.asarray(fk(a[:6]), dtype=float) for a in actions])
    index = int(closed[0]) if closed.size else int(np.argmin(poses[:, 2]))
    pose = poses[index]
    return {"closes": bool(closed.size), "index": index, "pose": [float(v) for v in pose],
            "xy_m": float(np.linalg.norm(pose[:2] - known.pick[:2])),
            "dz_m": float(pose[2] - known.pick[2]),
            "yaw_deg": _yaw_err(pose, known),
            "table_m": clearance(known.table, pose[:3]),
            "path": [[float(v) for v in p[:3]] for p in poses]}


def summarize(rows, known, grasp_step=None, stop_step=None, predicted=None, probe=None):
    """Zusammenfassung einer Fahrt fuer summary.json und die CSV.

    ``grasp_step``: Takt des Schliessbefehls der Policy (None: nicht
    geschlossen), ``stop_step``: letzter Takt (Default: der letzte).
    """
    n = len(rows["xy_pick"])
    if stop_step is None and n:
        stop_step = n - 1
    return {
        "pick": [float(v) for v in known.pick],
        "pick_yaw_deg": known.pick_yaw_deg,
        "pick_above_table_m": known.pick_above_table_m,
        "source": known.source,
        "probe": probe,
        "at_grasp": snapshot(rows, grasp_step),
        "at_stop": snapshot(rows, stop_step),
        "predicted": predicted,
        "path_dev_p95_m": float(np.percentile(rows["path_dev"], 95)) if n else None,
        "path_dev_max_m": float(np.max(rows["path_dev"])) if n else None,
        "table_min_m": float(np.min(rows["table"])) if n else None,
    }


# -- Experte nach dem Probegriff (Anwender 2026-11-16) -------------------------
#
# Die Policy steht 3 mm ueber dem Objekt, ohne es beruehrt zu haben. Der
# Experte (Planer) korrigiert auf derselben Hoehe in xy und Drehung auf PICK,
# senkt senkrecht ab, greift, hebt an und legt das Objekt an eine neue Lage
# (wie die Aufnahme, bc/auto_layout.Coverage); PICK wird nachgefuehrt. Die
# Korrektur ist genau das, was die Policy noch haette tun muessen -- als
# Kennzahl fuer die Analyse und als Bahn fuer DAgger gespeichert.

def flip_closer(pose, reference, plane):
    """``pose`` oder um 180 Grad um die Tischnormale gedreht -- was naeher an
    der Orientierung von ``reference`` liegt (Parallelgreifer: gleichwertig)."""
    from .auto_layout import rotated_about
    from . import geometry

    pose = np.asarray(pose, dtype=float)
    flipped = rotated_about(pose, plane.normal_at(pose[0], pose[1]), np.pi)

    def angle(q):
        return float(abs(np.dot(geometry.quat_canonical(q, reference[3:]), reference[3:])))

    return (flipped, True) if angle(flipped[3:]) > angle(pose[3:]) else (pose, False)


def correction(known, stop_pose):
    """Korrektur vom Stopp auf PICK: Pose ueber PICK auf Stopphoehe + Kennzahlen.

    Rueckgabe ``(above, grasp, info)``: ``above`` = PICK-Orientierung (oder um
    180 Grad gedreht, was naeher liegt), xy von PICK, z vom Stopp; ``grasp``
    = PICK in derselben Orientierung; ``info`` mit dx/dy (m, Basis-KS), Drehung
    (Grad) und Abstieg (m).
    """
    stop_pose = np.asarray(stop_pose, dtype=float)
    grasp, flipped = flip_closer(known.pick, stop_pose, known.table)
    above = grasp.copy()
    # gleiche Hoehe wie beim Stopp: nur xy und Drehung -- aber nie unter der
    # Probehoehe (Violation-Stopp, 16.11.: der Arm schwang 3-4 mm darunter,
    # waagrecht korrigiert haette eine Backe das Teil schieben koennen)
    probe_z = known.pick[2] + config.PROBE_OBJECT_TOP_ABOVE_PICK_M + config.PROBE_GAP_M
    above[2] = max(stop_pose[2], probe_z)
    info = {"dx_m": float(grasp[0] - stop_pose[0]), "dy_m": float(grasp[1] - stop_pose[1]),
            "xy_m": float(np.hypot(grasp[0] - stop_pose[0], grasp[1] - stop_pose[1])),
            "yaw_deg": -_yaw_err(stop_pose, known),
            "descent_m": float(stop_pose[2] - grasp[2]),
            "flipped": bool(flipped),
            "start_pose": [float(v) for v in stop_pose]}
    return above, grasp, info


def new_place_pose(known, reference_pick, rng, used_xy=(), yaw_range_deg=None,
                   camera_guard=True, candidates=10):
    """Kandidaten fuer die naechste Lage (Pose, xy, Drehung gegen die Bezugslage).

    Wie apps/record.py: seltenstes Feld der Tischabdeckung, Drehung gleich
    verteilt um die Bezugslage (``reference_pick``, der PICK beim Start), auf
    der Greifhoehe der aktuellen Lage. Liefert eine Liste -- der Aufrufer
    nimmt den ersten erreichbaren.
    """
    from .auto_layout import Coverage, place_pose
    from .table import align_pose

    if not known.region or len(known.region) < 3:
        raise ValueError("Umlegen braucht mindestens drei Tischpunkte")
    height = known.pick_above_table_m
    base_yaw = yaw_deg(reference_pick, known.table)
    coverage = Coverage(known.region, base_yaw, keepouts=known.keepouts or (),
                        yaw_range_deg=(config.AUTO_YAW_RANGE_DEG if yaw_range_deg is None
                                       else yaw_range_deg),
                        rng=rng, camera_guard=camera_guard)
    for xy in list(used_xy) + [known.pick[:2]]:
        coverage.add(xy)
    upright = align_pose(reference_pick, known.table, height)
    out, tried = [], set()
    while len(out) < candidates:
        try:
            cell = coverage.next_cell(exclude=tried)
        except ValueError:
            break
        tried.add(cell)
        try:
            xy = coverage.point_in(cell)
        except ValueError:
            continue
        for turn in coverage.turn_candidates():
            pose = place_pose(upright, known.table, xy, turn, height)
            if not coverage.camera_blocked(pose):
                out.append((pose, (float(xy[0]), float(xy[1])), float(turn)))
                break
    return out


def expert_waypoints(stop_pose, stop_joints, above, grasp, place, start_joints, lift_m,
                     lift_joints, place_above_joints, start_pose, gripper_closed=False):
    """Wegpunkte des Experten (bc/trajectory.Waypoint).

    STOPP -> KORREKTUR (gleiche Hoehe, xy + Drehung) -> GRIFF (senkrecht ab,
    schliessen) -> ANHEBEN -> UEBER_ABLAGE -> ABLAGE (oeffnen) ->
    UEBER_ABLAGE -> START. ``place``: Ablagepose in derselben Orientierung
    wie gegriffen.
    """
    from .trajectory import MOTION_LIN, MOTION_PTP, Waypoint

    def up(pose):
        p = np.asarray(pose, dtype=float).copy()
        p[2] += lift_m
        return p

    place_down = np.asarray(place, dtype=float).copy()
    place_down[2] += config.PUT_BACK_PLACE_OFFSET_M
    stop_pose = np.asarray(stop_pose, dtype=float)
    above = np.asarray(above, dtype=float)
    start = [Waypoint(stop_pose, gripper_closed=bool(gripper_closed), name="STOPP",
                      joints=stop_joints)]
    if above[2] > stop_pose[2] + 0.0005:
        # erst senkrecht auf die Korrekturhoehe, dann waagrecht (Violation-Stopp)
        free = stop_pose.copy()
        free[2] = above[2]
        start.append(Waypoint(free, gripper_closed=False, name="FREI", motion=MOTION_LIN,
                              approach=True))
    return start + [
        Waypoint(above, gripper_closed=False, name="KORREKTUR", motion=MOTION_LIN, approach=True),
        Waypoint(grasp, gripper_closed=True, name="GRIFF", motion=MOTION_LIN, approach=True),
        Waypoint(up(grasp), gripper_closed=True, name="ANHEBEN", motion=MOTION_LIN,
                 joints=lift_joints),
        Waypoint(up(place), gripper_closed=True, name="UEBER_ABLAGE", motion=MOTION_PTP,
                 joints=place_above_joints),
        Waypoint(place_down, gripper_closed=False, name="ABLAGE", motion=MOTION_LIN, approach=True),
        Waypoint(up(place), gripper_closed=False, name="UEBER_ABLAGE", motion=MOTION_LIN,
                 joints=place_above_joints),
        Waypoint(start_pose, gripper_closed=False, name="START", motion=MOTION_PTP,
                 joints=start_joints),
    ]


def correction_line(info, placed=None):
    """Ergebniszeile ``   Experte: ...`` (bc/gui/operation.py liest sie mit)."""
    text = ("   Experte: Korrektur dx %.1f mm, dy %.1f mm, xy %.1f mm, Drehung %.1f Grad, "
            "Abstieg %.1f mm" % (1e3 * info["dx_m"], 1e3 * info["dy_m"], 1e3 * info["xy_m"],
                                 info["yaw_deg"], 1e3 * info["descent_m"]))
    if placed:
        text += " -- %s" % placed
    return text


def _mm(value):
    return "" if value is None else "%.1f" % (1e3 * value)


def _deg(value):
    return "" if value is None else "%.1f" % value


def csv_row(episode, stop_reason, summary, correction_info=None, after=""):
    """Eine Zeile fuer ``policy_test.csv`` (Reihenfolge CSV_COLUMNS).

    ``correction_info``: :func:`correction` des Experten (sonst leer),
    ``after``: was nach der Policy geschah (Text).
    """
    g = summary.get("at_grasp") or {}
    s = summary.get("at_stop") or {}
    p = summary.get("predicted") or {}
    return [
        episode, _mm(summary["pick"][0]), _mm(summary["pick"][1]), _deg(summary["pick_yaw_deg"]),
        summary.get("probe") or "", str(stop_reason),
        g.get("step", ""), _mm(g.get("xy_m")), _mm(g.get("dz_m")), _deg(g.get("yaw_deg")),
        _mm(g.get("table_m")),
        s.get("step", ""), _mm(s.get("xy_m")), _mm(s.get("dz_m")), _deg(s.get("yaw_deg")),
        _mm(s.get("table_m")),
        "" if not p else ("ja" if p.get("closes") else "nein"),
        _mm(p.get("xy_m")), _mm(p.get("dz_m")), _deg(p.get("yaw_deg")),
        _mm(summary.get("path_dev_p95_m")), _mm(summary.get("path_dev_max_m")),
        _mm(summary.get("table_min_m")),
    ] + _correction_cells(correction_info) + [after or ""]


def _correction_cells(info):
    if not info:
        return ["", "", "", "", ""]
    return [_mm(info["dx_m"]), _mm(info["dy_m"]), _mm(info["xy_m"]), _deg(info["yaw_deg"]),
            _mm(info["descent_m"])]


def result_line(summary):
    """Ergebniszeile ``   Lage: ...`` (bc/gui/operation.py liest sie mit).

    Ohne Kommas in den Zahlen -- die Felder trennt ein Komma.
    """
    g, s, p = summary.get("at_grasp"), summary.get("at_stop"), summary.get("predicted")
    at = g or s or {}
    parts = ["%s xy %s mm" % ("Griff" if g else "Stopp", _mm(at.get("xy_m")) or "-"),
             "dz %s mm" % (_mm(at.get("dz_m")) or "-"),
             "Drehung %s Grad" % (_deg(at.get("yaw_deg")) or "-"),
             "Bahn p95 %s mm" % (_mm(summary.get("path_dev_p95_m")) or "-"),
             "Tisch min %s mm" % (_mm(summary.get("table_min_m")) or "-"),
             "Vorhersage xy %s mm" % ((_mm(p.get("xy_m")) or "-") if p else "-")]
    return "   Lage: " + ", ".join(parts)
