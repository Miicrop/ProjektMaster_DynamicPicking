"""Live-Inferenz (AP 4): die trainierte Policy faehrt selbst.

Aufbau der Schleife (AP 4.1/4.2), in jedem 15-Hz-Takt:
    1. Beobachtung EXAKT wie der Recorder bauen (dataset.build_state,
       Bildgroesse 240x320) -- AP 1.5.1.
    2. Policy: jede Beobachtung in die Historie, alle ``--replan`` Takte neu
       vorhersagen, ueberlappende Chunks mitteln (policy.ChunkEnsembler).
    3. Pruefen: Ziel nicht weiter als SERVO_MAX_TARGET_GAP_RAD von der
       Ist-Stellung (policy.check_action).
    4. Ziel fuer t+1 mit SERVO_RATE_HZ interpoliert anfahren (servo.py, wie
       im Recorder). Jeder Zwischenschritt laeuft im Adapter durch den
       Sprung- und Geschwindigkeitsfilter (servo.ServoGuard).
    5. Greiferbefehl bei Wechsel (Schwelle 0.5). Ausfuehrung ``online`` mit
       Halteregel (``reach_*`` aus der Aufzeichnung, bc/execution.py): vor
       dem Befehl am Ziel der Policy warten, bis der Arm dort steht, und
       bis zum Ende des Dwells nicht darueber hinaus vorausschauen -- wie
       der Recorder. Die Wartezeit steht je Takt in ``halt_s``.
    Geofence-Watchdog parallel (echte Uhr: eigener Thread; SimClock: je Takt).

Vor jeder Fahrt geht es ausserhalb der Policy an die Startstellung der
Aufzeichnung (bc_policy.json), wie beim Reset zwischen Episoden (AP 5.2).
Die Fahrt endet am Uebergabepunkt (Endstellung erreicht und ruhig), nach
``--max-steps`` oder bei Stopp.

Gleichheit mit der Aufzeichnung wird erzwungen, nicht nur empfohlen:
Schema, Rate, Kameras, servo_j-Rate und Override muessen zu bc_policy.json
passen (AP 2.6 -- das Tempo und das Folgeverhalten sind mitgelernt).

Ausfuehren (aus dem Ordner "Behavior Cloning"):
    python apps/infer.py --sim --checkpoint checkpoints/sim/policy --episodes 5
    python apps/infer.py --robot neura --cameras sim --checkpoint checkpoints/vm/policy
    python apps/infer.py --sim --hold --steps 45        # Verdrahtung ohne Modell
    python apps/infer.py --robot neura --checkpoint <policy> --replay data_vm/2026-11-11 --replay-episode 0,5,9
    python apps/infer.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco --checkpoint <policy> --testlagen

``--robot mujoco`` (Taktiksimulation, bc/sim_mujoco): geschlossene Testfahrt --
die Kameras rendern aus der Stellung, die der Arm (Folgemodell) gerade hat.
``--testlagen [DATEI]``: vor jeder Fahrt liegt das Objekt an der naechsten Lage
des festen Satzes (Default bc/sim_mujoco/testlagen_v1.json, Auswahl mit
``--testlagen-auswahl 0-4``); danach Sim-Auswertung (bc/sim_mujoco/auswertung.py)
nach ``sim_auswertung.json``/``.csv`` im Protokollordner.

``--replay``: statt der Kameras die Bilder einer Aufnahme einspielen (je Takt
ein Bild, bc/adapters/cam_replay.py), vor jeder Fahrt an die Startstellung
DIESER Episode, danach Vergleich der gefahrenen mit der aufgezeichneten Bahn
(bc/replay.py). Nur Simulation/VM -- die Bilder zeigen nicht die Wirklichkeit.
Offline ohne Roboter: apps/replay_check.py.

SICHERHEIT: Am Neura nur mit is_robot_in_simulation() == True, die reale
Anlage braucht --real-robot und eine Bestaetigung. Software-Stopp ersetzt
keinen Hardware-Not-Aus (AP 4.2).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from bc import config, dagger, dataset, known_pose, metrics, obstacles, replay
from bc import live as live_module
from bc import camera_settings as camera_settings_module
from bc.adapters import (
    CAMERA_MODES,
    SOFT_BACKENDS,
    camera_configs,
    open_robot,
    replay_configs,
    resolve_camera_mode,
    start_cameras,
)
from bc.clock import RealClock, SimClock
from bc.collision import default_workspace
from bc.policy import ChunkEnsembler, ChunkExecutor, HoldPolicy, PredictionTooSlow, check_action
from bc.ports import MotionRefused, RobotError
from bc.recorder import _to_schema_size
from bc.safety import (ArmStalled, CameraStale, FrameAgeGuard, StallGuard, TargetRejected,
                       Watchdog, check_target, geofence_check)
from bc import execution as execution_module
from bc.servo import CommandLowpass, ServoGuard, ServoInterpolator, TargetLimiter, substeps_for
from bc.sync import Pacer

#: Wortlaut fuer --real-robot (wie apps/record.py).
REAL_ROBOT_CONFIRMATION = "ANLAGE"

#: Endstellung gilt als erreicht, wenn alle Gelenke naeher als dies sind ...
END_TOL_RAD = 0.02
#: ... und das so viele Takte in Folge bleibt.
END_HOLD_STEPS = 5


def build_observation(robot, captures, frames_out=None):
    """Baut die Beobachtung EXAKT wie der Recorder (AP 1.5.1).

    ``frames_out``: optionales dict, bekommt je Kamera den Original-Frame
    (oder None) -- fuer die Pruefung auf eingefrorene Bilder (FrameAgeGuard).
    """
    state = robot.read_state()
    obs = {
        "observation.state": dataset.build_state(
            state.joints,
            state.tcp_quat,
            config.GRIPPER_CLOSED if state.gripper_closed else config.GRIPPER_OPEN,
        )
    }
    for cap in captures:
        frame = cap.latest()
        if frames_out is not None:
            frames_out[cap.name] = frame
        obs["observation.images.%s" % cap.name] = (
            np.zeros((config.IMAGE_HEIGHT, config.IMAGE_WIDTH, 3), dtype=np.uint8)
            if frame is None
            else _to_schema_size(frame.image)
        )
    return obs, state


def run_episode(robot, captures, executor, clock, max_steps, workspace,
                end_joints=None, end_gripper=None, min_steps=0, threaded_watchdog=True,
                progress=print, servo_rate_hz=config.SERVO_RATE_HZ, execution=None,
                frame_guard=None, stop_at_grasp=False, on_tick=None, mitschrieb=None,
                target_lookahead=0.0, live=None, glaettung=1.0):
    """Eine Policy-Fahrt. Rueckgabe: Log-dict (Arrays je Takt + Zusammenfassung).

    ``glaettung``: alpha des Tiefpasses auf die Ziele (bc/servo.CommandLowpass,
    1 = aus). Wirkt hinter dem TargetLimiter und vor der Kollisionspruefung;
    das gesendete Ziel steht je Takt in ``ziel`` (Log), die rohe Action in
    ``action``.

    ``mitschrieb``: bc/dagger.Mitschrieb -- bekommt je Takt Beobachtung (mit
    Bildern), gesendetes Ziel und Greifer (DAgger, ``--dagger``).

    ``on_tick``: optional ``f(state) -> str``, haengt Text an die
    Fortschrittszeile (``--lage-bekannt``: aktuelle Abweichung).

    Lehnt das Kollisionsmodell ein Ziel ab, steht der Rest der Vorhersage ab
    diesem Takt in ``probe_actions`` (K, 7) -- beim Probegriff "objekt" der
    Weg, den die Policy noch gefahren waere (bc/known_pose.predicted_grasp).

    Ende = Endstellung +-END_TOL_RAD UND (falls bekannt) Greiferzustand wie am
    Ende der Aufzeichnung, END_HOLD_STEPS Takte lang, fruehestens ab
    ``min_steps``. Stellung allein ist nicht eindeutig: dieselbe Stellung kann
    in einer Bahn mehrfach vorkommen (Befund 2026-09-17, Sim-Demo).

    ``frame_guard``: safety.FrameAgeGuard (Default: Werte aus config) -- haelt
    an, wenn ein Kamerabild einfriert (die Policy saehe ein Standbild).

    ``live``: bc/live.LiveWriter -- je Takt TCP, Bilder und die Vorhersagen
    fuer das Live-Fenster der GUI (nur Kopien, rechnet im eigenen Thread).

    ``target_lookahead``: Ziele zusaetzlich um so viele Takte verlaengert
    pruefen (bc/safety.check_target, Nachlauf; Probegriff "objekt").

    ``stop_at_grasp``: die Policy endet mit dem Schliessbefehl (stop_reason
    "griff"); Anheben und Transport uebernimmt :func:`planned_transport`
    (``--transport-geplant``, Versuchsreihe 2026-11-13, Variante C).
    """
    executor.reset()
    frame_guard = frame_guard or FrameAgeGuard()
    frame_guard.reset()
    guard = getattr(robot, "servo_guard", None) or ServoGuard()
    watchdog = Watchdog(robot, [geofence_check(robot, workspace)], clock)
    if threaded_watchdog:
        watchdog.start()

    log = {k: [] for k in ("t", "joints", "tcp", "action", "ziel", "gripper_cmd", "predict_s",
                           "delay_steps", "ensemble_spread", "ensemble_count", "halt_s")}
    # Takt 0 VOR dem Aktivieren des Servo-Interface: die erste Vorhersage
    # (bei asynchroner Vorhersage wird auf sie gewartet) haelt so keinen
    # laufenden Servostrom an. Der Arm steht, die Beobachtung bleibt gueltig.
    frames = {}
    obs, state = build_observation(robot, captures, frames)
    try:
        frame_guard.check(frames, clock.now())
    except CameraStale:
        watchdog.stop()
        raise
    first = (obs, state, executor.next_action(obs))
    execution = execution or execution_module.describe(execution_module.SERVO_J)
    online = execution["mode"] == execution_module.ONLINE
    # "Erst weiter, wenn erreicht" wie im Recorder: hold_end ist der letzte
    # Dwell-Takt nach einem Greiferwechsel, bis dahin kein Vorlauf darueber.
    halt = execution_module.reach_rule(execution)
    hold_end, last_target, reach_waits = None, None, []
    prev_ziel = None
    # Wie in der Aufnahme: servo_j linear oder servo_j_pos ohne v/a.
    interp = ServoInterpolator(
        servo_rate_hz=servo_rate_hz,
        profile=execution_module.servo_profile(execution) or "linear",
    ).reset(state.joints)
    limiter = TargetLimiter().reset(state.joints)
    lowpass = CommandLowpass(glaettung).reset(state.joints)
    # Arm steht, Ziel nicht (Not-Aus am Handbediengeraet, 16.11.) -> Ende
    stall = StallGuard()
    robot.activate_servo("position")
    # nach der Aktivierung; online: ein Aufruf je Regeltakt
    pacer = Pacer(clock, config.CONTROL_RATE_HZ if online else servo_rate_hz).start()
    stop_reason, at_end, prev_gripper = None, 0, None
    probe_actions = None
    try:
        if not online:
            q, v, a = interp.hold()
            pacer.tick()
            robot.servo_j(q, v, a)
        for step in range(max_steps):
            if not threaded_watchdog and watchdog.run_once() is not None:
                stop_reason = "geofence: %s" % watchdog.tripped
                break
            if robot.stop_requested:
                stop_reason = "stopp: %s" % (watchdog.tripped or "angefordert")
                break
            before = executor.predictions
            if first is not None:
                (obs, state, action), first = first, None
                before = 0
            else:
                frames = {}
                obs, state = build_observation(robot, captures, frames)
                frame_guard.check(frames, clock.now())
                action = executor.next_action(obs)
            predicted = executor.predictions > before
            check_action(action, state.joints, guard)

            # Weiche Stufe: Zielaenderung je Takt begrenzen (servo.TargetLimiter);
            # der ServoGuard im Adapter bleibt die harte Stufe.
            if online:
                # Wie in der Aufnahme: Ziel mit Vorlauf (bc/execution.py). Die
                # Action dieses Takts ist das Ziel fuer t+1, also liegt das
                # Ziel fuer t+Vorlauf (lead_steps - 1) Actions weiter.
                vorlauf = max(0, int(execution["lead_steps"]) - 1)
                if hold_end is not None and step <= hold_end:
                    # Im Dwell: hoechstens bis zu dessen Ende vorausschauen
                    # (Recorder: lead_index mit hold_end). -1 = das Ziel
                    # des Vortakts, also weiter am Haltepunkt stehen.
                    vorlauf = min(vorlauf, hold_end - step - 1)
                if vorlauf < 0:
                    ziel = last_target
                else:
                    ziel = lowpass.apply(limiter.limit(
                        (executor.lookahead(vorlauf) if vorlauf else action)[:6]))
                    check_target(workspace, robot, ziel, last_target, target_lookahead)
                if not robot.stop_requested:
                    pacer.tick()
                    robot.online_j(ziel, execution["vel"], execution["acc"])
                    last_target = ziel
            else:
                ziel = lowpass.apply(limiter.limit(action[:6]))
                check_target(workspace, robot, ziel, prev_ziel, target_lookahead)
                prev_ziel = ziel
                for q, v, a in interp.window(ziel):
                    if robot.stop_requested:
                        break
                    pacer.tick()
                    robot.servo_j(q, v, a)
            if robot.stop_requested:
                stop_reason = "stopp: %s" % (watchdog.tripped or "angefordert")
                break
            gripper = dataset.gripper_from_action(action)
            wait_s = 0.0
            if halt and prev_gripper is not None and gripper != prev_gripper:
                # Haltepunkt: das Ziel dieser Action halten, bis der Arm dort
                # steht, dann Greiferbefehl und voller Dwell (wie der Recorder;
                # der erste Greiferbefehl ist der Startzustand, kein Halt).
                last_target = limiter.limit(action[:6])
                lowpass.reset(last_target)   # gehaltenes Ziel ungeglaettet, kein Nachziehen
                ergebnis = execution_module.wait_until_reached(
                    robot, last_target, execution, clock, config.CONTROL_RATE_HZ)
                ergebnis["step"] = step
                reach_waits.append(ergebnis)
                wait_s = ergebnis["wait_s"]
                if not ergebnis["reached"]:
                    stop_reason = ("stopp: %s" % (watchdog.tripped or "angefordert")
                                   if ergebnis["reason"] == "schutzstopp"
                                   else execution_module.reach_failure_text(ergebnis, step))
                    break
                hold_end = step + int(execution.get("hold_dwell_steps",
                                                    config.GRIPPER_DWELL_STEPS))
                pacer.start().tick()   # Wartezeit ist kein Rueckstand, naechster Takt in 1/15 s
            # Der erste Greiferbefehl ist der Startzustand, kein Griff.
            grasped = bool(gripper) and prev_gripper is not None and gripper != prev_gripper
            if gripper != prev_gripper:
                robot.gripper_command(gripper)
                prev_gripper = gripper

            log["t"].append(clock.now())
            log["joints"].append(state.joints)
            log["tcp"].append(np.asarray(state.tcp_quat, dtype=float))
            log["action"].append(action)
            log["ziel"].append(np.full(6, np.nan) if ziel is None else np.asarray(ziel, dtype=float))
            log["gripper_cmd"].append(float(gripper))
            predict_s = getattr(executor, "last_predict_s", None) if predicted else None
            log["predict_s"].append(np.nan if predict_s is None else predict_s)
            log["delay_steps"].append(getattr(executor, "last_delay_steps", 0) if predicted else np.nan)
            log["ensemble_spread"].append(getattr(executor, "last_spread", 0.0))
            log["ensemble_count"].append(getattr(executor, "last_count", 1))
            log["halt_s"].append(wait_s)
            if live is not None:
                try:
                    live.update(step, state, frames, executor, ziel)
                except Exception:      # Anzeige darf die Fahrt nie stoppen
                    pass
            if mitschrieb is not None:
                mitschrieb.add(obs, state.joints if ziel is None else ziel, gripper,
                               dagger.POLICY, policy_action=action)
            # Messung vom Anfang des Takts gegen das gesendete Ziel
            if ziel is not None:
                stall.check(state.joints, ziel)

            if stop_at_grasp and grasped:
                stop_reason = "griff"
                break
            if end_joints is not None:
                near = float(np.max(np.abs(np.asarray(state.joints) - end_joints))) < END_TOL_RAD
                if end_gripper is not None:
                    near = near and bool(state.gripper_closed) == (end_gripper > config.GRIPPER_THRESHOLD)
                near = near and step >= min_steps
                at_end = at_end + 1 if near else 0
                if at_end >= END_HOLD_STEPS:
                    stop_reason = "endstellung"
                    break
            if progress and step % 15 == 0:
                extra = ""
                if on_tick is not None:
                    try:
                        extra = on_tick(state) or ""
                    except Exception as exc:   # Anzeige darf die Fahrt nie stoppen
                        extra = "  (Abweichung nicht berechenbar: %s)" % exc
                progress("  Takt %4d  Spread %.4f rad  Vorhersage %s%s"
                         % (step, log["ensemble_spread"][-1],
                            "-" if predict_s is None else "%.1f ms" % (1e3 * predict_s), extra))
        else:
            stop_reason = "max_steps"
    except RobotError as exc:
        stop_reason = "abgelehnt: %s" % exc
        robot.emergency_stop()
    except PredictionTooSlow as exc:
        stop_reason = "vorhersage zu langsam: %s" % exc
        robot.emergency_stop()
    except TargetRejected as exc:
        stop_reason = str(exc)
        robot.emergency_stop()
        probe_actions = _rest_of_prediction(executor)
    except CameraStale as exc:
        stop_reason = str(exc)
        robot.emergency_stop()
    except ArmStalled as exc:
        stop_reason = str(exc)
        report_stall(robot, "Fahrt", exc)
        robot.emergency_stop()
    finally:
        watchdog.stop()
        if online and not robot.stop_requested:
            robot.stop_online()   # bremst nicht -- Abbrueche liefen ueber emergency_stop
        robot.deactivate_servo()

    # Letzten Zustand nachtragen (Ziel des letzten Takts ist dort erreicht)
    final = robot.read_state()
    log["final_tcp"] = np.asarray(final.tcp_quat, dtype=float)
    log["final_joints"] = np.asarray(final.joints, dtype=float)
    arrays = {k: np.asarray(v, dtype=float) for k, v in log.items()}
    arrays["pacer_overruns"] = pacer.overruns
    arrays["stop_reason"] = stop_reason
    arrays["reached_end"] = stop_reason == "endstellung"
    arrays["guard_rejections"] = guard.rejections
    arrays["limiter_clamped"] = limiter.clamped
    arrays["frame_age_max_s"] = frame_guard.worst_age_s
    arrays.update(execution_module.reach_summary(reach_waits))
    if probe_actions is not None:
        arrays["probe_actions"] = probe_actions
    return arrays


def _rest_of_prediction(executor, horizon=config.POLICY_HORIZON):
    """Die gemittelten Ziele ab dem zuletzt gelieferten Takt (K, 7) oder None."""
    if not hasattr(executor, "lookahead"):
        return None
    try:
        rest = [np.asarray(executor.lookahead(k), dtype=float) for k in range(horizon)]
    except Exception:
        return None
    # lookahead haelt am Chunkende den letzten Schritt -- Wiederholungen weg
    while len(rest) > 1 and np.array_equal(rest[-1], rest[-2]):
        rest.pop()
    return np.vstack(rest) if rest else None


#: Anheben nach dem Griff wie in pick_to_station (PICK -> PRE_PICK, 5 cm).
TRANSPORT_LIFT_M = 0.05
#: Ueberschleifen am Anhebepunkt wie in pick_to_station (PRE_PICK "blend": 0.04).
TRANSPORT_LIFT_BLEND_M = 0.04


def planned_transport(robot, workspace, station_joints, clock, servo_rate_hz=config.SERVO_RATE_HZ,
                      planner=None, lift_m=TRANSPORT_LIFT_M, threaded_watchdog=True):
    """Nach dem Griff der Policy: Dwell, senkrecht anheben, PTP zur Station.

    Variante C der Versuchsreihe 2026-11-13: die Policy lernt nur Anflug und
    Griff, der Rest ist fuer jede Objektlage gleich und wird wie in der
    Aufnahme geplant (bc/trajectory.py, gleiche Tempi und Rampen) und als
    servo_j-Strom gefahren. Jede Sollstellung geht vorab durch das
    Kollisionsmodell, der Watchdog laeuft mit.

    Posen kommen aus ``robot.fk`` (Frame der Steuerung), nicht aus
    ``read_state``: die IK rechnet in diesem Frame.
    Rueckgabe: Log-dict wie :func:`run_episode` (nur t/joints/tcp/action/
    gripper_cmd) plus ``stop_reason`` und ``pacer_overruns``.
    """
    from bc.kinematics import IKFailure, Kinematics
    from bc.trajectory import MOTION_LIN, MOTION_PTP, Waypoint, build_ideal_trajectory

    planner = planner or {}
    log = {k: [] for k in ("t", "joints", "tcp", "action", "gripper_cmd")}
    out = {"stop_reason": None, "pacer_overruns": 0, "steps_planned": 0}
    kin = Kinematics(robot)
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    station_joints = np.asarray(station_joints, dtype=float)
    try:
        p0 = np.asarray(robot.fk(q0), dtype=float)
        up = p0.copy()
        up[2] += float(lift_m)
        q_up = kin.ik(up, q0)
        waypoints = [
            Waypoint(p0, gripper_closed=True, name="GRIFF", joints=q0),
            Waypoint(up, gripper_closed=True, name="ANHEBEN", motion=MOTION_LIN, joints=q_up,
                     blend_m=TRANSPORT_LIFT_BLEND_M),
            Waypoint(np.asarray(robot.fk(station_joints), dtype=float), gripper_closed=True,
                     name="STATION", motion=MOTION_PTP, joints=station_joints),
        ]
        ideal = build_ideal_trajectory(
            waypoints, fk=robot.fk,
            transit_speed=planner.get("transit_speed_ms") or config.TRANSIT_SPEED_MS,
            approach_speed=planner.get("approach_speed_ms") or config.APPROACH_SPEED_MS,
            ptp_joint_speed=planner.get("ptp_joint_speed_rads") or config.PTP_JOINT_SPEED_RADS)
        targets = kin.solve_path(ideal.poses_quat, q0, fixed_joints=ideal.joints)
        for q in targets:
            check_target(workspace, robot, q)
    except (IKFailure, TargetRejected, ValueError) as exc:
        out["stop_reason"] = "transport nicht planbar: %s" % exc
        return {**{k: np.asarray(v, dtype=float) for k, v in log.items()}, **out}
    out["steps_planned"] = len(targets)

    watchdog = Watchdog(robot, [geofence_check(robot, workspace)], clock)
    if threaded_watchdog:
        watchdog.start()
    interp = ServoInterpolator(servo_rate_hz=servo_rate_hz).reset(q0)
    stall = StallGuard()
    robot.activate_servo("position")
    pacer = Pacer(clock, servo_rate_hz).start()
    try:
        # Dwell wie in der Aufnahme: stehen, bis der Greifer zu ist
        for _ in range(config.GRIPPER_DWELL_STEPS * interp.substeps):
            q, v, a = interp.hold()
            pacer.tick()
            robot.servo_j(q, v, a)
        for q in targets:
            if not threaded_watchdog and watchdog.run_once() is not None:
                out["stop_reason"] = "geofence: %s" % watchdog.tripped
                break
            for qq, v, a in interp.window(q):
                if robot.stop_requested:
                    break
                pacer.tick()
                robot.servo_j(qq, v, a)
            if robot.stop_requested:
                out["stop_reason"] = "stopp: %s" % (watchdog.tripped or "angefordert")
                break
            state = robot.read_state()
            log["t"].append(clock.now())
            log["joints"].append(state.joints)
            log["tcp"].append(np.asarray(state.tcp_quat, dtype=float))
            log["action"].append(np.append(q, config.GRIPPER_CLOSED))
            log["gripper_cmd"].append(1.0)
            stall.check(state.joints, q)
        else:
            out["stop_reason"] = "endstellung"
    except RobotError as exc:
        out["stop_reason"] = "abgelehnt im transport: %s" % exc
        robot.emergency_stop()
    except ArmStalled as exc:
        out["stop_reason"] = "im transport: %s" % exc
        report_stall(robot, "Transport/Rueckzug", exc)
        robot.emergency_stop()
    finally:
        watchdog.stop()
        robot.deactivate_servo()
    out["pacer_overruns"] = pacer.overruns
    return {**{k: np.asarray(v, dtype=float) for k, v in log.items()}, **out}


def merge_transport(log, transport, robot):
    """Haengt die geplante Fahrt an das Log der Policy-Fahrt an."""
    n = len(transport["t"])
    for key in ("t", "joints", "tcp", "action", "gripper_cmd"):
        if n:
            log[key] = np.concatenate([log[key], transport[key]]) if len(log[key]) else transport[key]
    for key, fill in (("predict_s", np.nan), ("delay_steps", np.nan), ("ensemble_spread", 0.0),
                      ("ensemble_count", 0.0), ("halt_s", 0.0)):
        log[key] = np.concatenate([log[key], np.full(n, fill)])
    if "ziel" in log and n:
        # geplante Fahrt: gesendet wird die Planerbahn, kein Policy-Ziel
        ziel = np.asarray(log["ziel"], dtype=float).reshape(-1, 6)
        log["ziel"] = np.concatenate([ziel, np.asarray(transport["action"], dtype=float)[:, :6]])
    final = robot.read_state()
    log["final_tcp"] = np.asarray(final.tcp_quat, dtype=float)
    log["final_joints"] = np.asarray(final.joints, dtype=float)
    log["stop_reason"] = transport["stop_reason"]
    log["reached_end"] = transport["stop_reason"] == "endstellung"
    log["pacer_overruns"] = int(log["pacer_overruns"]) + int(transport["pacer_overruns"])
    log["policy_steps"] = int(len(log["t"]) - n)
    return log


def add_recorded_workspace(workspace, info, robot, robot_kind, progress=print,
                           table_clearance=None):
    """Tisch, Sperrzonen und Huelle der Demonstrationen ins Kollisionsmodell.

    ``table_clearance``: Mindestabstand der Werkzeugspitze zur Tischebene (m),
    Default config.TABLE_MIN_CLEARANCE_M -- groesser beim Probegriff "objekt"
    (bc/known_pose.probe_clearance).

    Tisch und Sperrzonen live aus den Punkten der Steuerung (Namen aus der
    Aufnahme, bc_policy.json ``table_spec``) -- verschiebt sich der Tisch,
    wird nachgeteacht. Rueckfall: die Werte der juengsten Aufnahme. Aeltere
    Policies ohne diese Eintraege fahren wie bisher (nur der grobe Tischquader).
    Rueckgabe: Quelle des Tischs ("live", "aufnahme" oder None).
    """
    from bc.obstacles import Envelope
    from bc.sequence import resolve_table
    from bc.table import Keepout, KeepoutSurface, TablePlane, TableSurface

    spec = info.get("table_spec") or None
    recorded = TablePlane.from_dict(info["table"]) if info.get("table") else None
    recorded_keepouts = [Keepout.from_dict(k) for k in info.get("keepouts") or []]
    plane, keepouts, source = None, [], None
    if spec and spec.get("points") and robot_kind == "neura":
        try:
            sizes = {k: v for k, v in (spec.get("keepout_sizes") or {}).items() if v is not None}
            plane, points, keepouts, _, missing = resolve_table(
                spec["points"], spec.get("keepout") or [], sizes, config.KEEPOUT_HALF_SIZE_M, robot)
            if missing:
                progress("Hinweis: Tisch-/Sperrpunkte fehlen in der Steuerung: %s" % ", ".join(missing))
            if plane is not None:
                source = "live"
                if recorded is not None:
                    xy = [p["pose_quat"][:2] for p in points.values()]
                    diff = max(abs(plane.height_at(x, y) - recorded.height_at(x, y)) for x, y in xy)
                    if diff > config.INFER_TABLE_WARN_M:
                        progress("WARNUNG: Tisch live weicht %.1f mm von der Aufnahme ab -- "
                                 "verschoben oder nachgeteacht? Es gilt der live gelesene."
                                 % (1e3 * diff))
        except Exception as exc:
            progress("Hinweis: Tisch nicht live lesbar (%s) -- Werte der Aufnahme." % exc)
            plane = None
    if plane is None and recorded is not None:
        plane, keepouts, source = recorded, recorded_keepouts, "aufnahme"
    if plane is not None:
        clearance_m = config.TABLE_MIN_CLEARANCE_M if table_clearance is None else table_clearance
        workspace.add_box(TableSurface(plane, min_clearance=clearance_m))
        for zone in keepouts:
            workspace.add_box(KeepoutSurface(zone, plane))
        progress("Kollisionsmodell: Tisch %s (%s), Sperrzonen %s, Werkzeugspitze >= %.1f mm"
                 % (source, plane.describe(), ", ".join(z.name for z in keepouts) or "keine",
                    1e3 * clearance_m))
    env = info.get("tcp_envelope")
    if env:
        margin = config.INFER_ENVELOPE_MARGIN_M
        workspace.add_box(Envelope(np.asarray(env["lo"]) - margin, np.asarray(env["hi"]) + margin))
        progress("Kollisionsmodell: Werkzeugspitze in der Huelle der Demonstrationen + %.0f mm"
                 % (1e3 * margin))
    return source


#: Ordner "Behavior Cloning" (relative Ablaufdateien aus bc_policy.json)
M4_ROOT = Path(__file__).resolve().parents[1]


def load_known_pose(args, info, robot, planner=None):
    """Bekannte Lage fuer ``--lage-bekannt`` (bc/known_pose.py)."""
    path = args.ablauf or (info.get("table_spec") or {}).get("sequence_file")
    if not path:
        raise SystemExit("--lage-bekannt: keine Ablaufdatei -- bc_policy.json nennt keine "
                         "(table_spec.sequence_file), bitte mit --ablauf angeben")
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = M4_ROOT / path
    try:
        known, resolved = known_pose.load(path, robot, planner)
    except (OSError, ValueError) as exc:
        raise SystemExit("--lage-bekannt: %s (%s)" % (exc, path))
    gap_mm = getattr(args, "probe_abstand", None)
    known.probe_gap_m = None if gap_mm is None else 1e-3 * float(gap_mm)
    if resolved.table_missing:
        print("Hinweis: Tischpunkte fehlen in der Steuerung: %s" % ", ".join(resolved.table_missing))
    print("Ablauf: %s, Tisch aus %d Punkt(en): %s"
          % (path, len(resolved.table_points), ", ".join(sorted(resolved.table_points))))
    return known


def _deviation_text(known):
    """Fortschrittszeile: Abweichung im aktuellen Takt (``run_episode(on_tick=...)``)."""
    def text(state):
        rows = known_pose.track(np.asarray(state.tcp_quat, dtype=float)[None], known)
        return ("  Abweichung Bahn %.1f mm  PICK xy %.1f mm  ueber Tisch %.1f mm"
                % (1e3 * rows["path_dev"][0], 1e3 * rows["xy_pick"][0], 1e3 * rows["table"][0]))
    return text


def evaluate_known(log, known, robot, probe):
    """Kennzahlen je Takt und Zusammenfassung einer Fahrt mit bekannter Lage.

    Am Griff zaehlt der Takt NACH dem Schliessbefehl (dort hat der Arm das
    Ziel erreicht, mit dem der Befehl gesendet wurde -- wie metrics).
    """
    tcp = log["tcp"]
    tcp = np.vstack([tcp, log["final_tcp"][None]]) if len(tcp) else log["final_tcp"][None]
    rows = known_pose.track(tcp, known)
    grip = np.asarray(log["gripper_cmd"], dtype=float) > config.GRIPPER_THRESHOLD
    closing = np.flatnonzero(grip[1:] & ~grip[:-1]) + 1
    grasp_step = min(int(closing[0]) + 1, len(tcp) - 1) if closing.size else None
    predicted = None
    if log.get("probe_actions") is not None:
        try:
            predicted = known_pose.predicted_grasp(log["probe_actions"], robot.fk, known)
        except Exception as exc:   # FK nach dem Stopp nicht verfuegbar o. ae.
            print("   Hinweis: vorhergesagter Greifpunkt nicht berechenbar (%s)" % exc)
    summary = known_pose.summarize(rows, known, grasp_step=grasp_step, predicted=predicted,
                                   probe=probe, tcp=tcp,
                                   jaw_offset_deg=getattr(robot, "jaw_axis_offset_deg", None))
    return {"rows": rows, "summary": summary}


def report_stall(robot, where, exc):
    """Zustand der Steuerung ins Protokoll, wenn der Arm nicht folgt (Anwender
    2026-11-25) -- VOR dem Not-Halt, damit er den Haengerzustand zeigt. Nur am
    Neura-Adapter (``diagnose_state``); Fehler hier brechen nichts ab."""
    diagnose = getattr(robot, "diagnose_state", None)
    if diagnose is None:
        return None
    try:
        state = diagnose()
    except Exception as e:      # Diagnose darf den Abbruch nicht stoeren
        print("   STEUERUNG (%s): nicht abfragbar (%s)" % (where, e))
        return None
    print("   STEUERUNG (%s, %s): %s" % (where, str(exc).split(":")[0],
                                         json.dumps(state, ensure_ascii=False, default=str)))
    return state


def append_csv(path, columns, row):
    """Eine Zeile an ``path`` anhaengen (Kopfzeile beim ersten Mal). Trenner ';'."""
    import csv
    new = not Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        if new:
            writer.writerow(columns)
        writer.writerow(row)


_VIOLATION = re.compile(r"Violation\(Schritt [^,]*, Frame '([^']*)', Quader '([^']*)', "
                        r"Freiraum (-?[0-9.]+) m")


def probe_violation(stop_reason, limit_m=None):
    """Hielt der Geofence-Waechter am Probegriff-Quader (Tischebene, Werkzeug)?

    Anlage 2026-11-16: Der Arm schwang 9-10 mm unter das letzte geprufte Ziel,
    der Waechter (gemessene Stellung) hielt 3-4 mm unter der Probehoehe. Das
    ist derselbe Probegriff-Stopp, nur spaeter erkannt. Gilt nur, wenn ALLE
    Verletzungen das Werkzeug an der Tischebene betreffen und hoechstens
    ``limit_m`` tief sind -- alles andere bleibt ein echter Stopp.
    """
    text = str(stop_reason)
    if not text.startswith("stopp: [Violation"):
        return False
    limit = config.PROBE_VIOLATION_MAX_M if limit_m is None else limit_m
    found = _VIOLATION.findall(text)
    return bool(found) and text.count("Violation(") == len(found) and all(
        frame == "tool" and box == "Tischebene" and float(free) >= -limit
        for frame, box, free in found)


def expected_test_stop(stop_reason, probe=None):
    """Endete die Policy wie beim Policy-Test vorgesehen (Griff oder Probegriff)?

    ``probe="objekt"``: auch der Violation-Stopp am Probegriff-Quader
    (:func:`probe_violation`) -- der Experte hebt dann zuerst senkrecht an.
    """
    text = str(stop_reason)
    if text == "griff" or (text.startswith("kollision vorab") and "Tischebene" in text):
        return True
    return probe == "objekt" and probe_violation(text)


def retreat_after_test(robot, workspace, log, start_joints, clock, args, planner=None,
                       probe=None):
    """Nach dem Policy-Test: Greifer auf, senkrecht anheben, zurueck zum Start.

    Nur nach dem vorgesehenen Ende (Griff, Probegriff am Tisch-Geofence) --
    nach jedem anderen Stopp bleibt der Arm stehen, wie bisher. Der
    Probegriff-Stopp ist ein Software-Stopp an einem erlaubten Ziel; er wird
    quittiert (``clear_stop``), der Rueckzug ist geplant und vorab geprueft.
    Rueckgabe: Text fuer Protokoll und Oberflaeche.
    """
    if not (expected_test_stop(log["stop_reason"], probe)
            or (probe == "objekt" and log["stop_reason"] == "max_steps")):
        return "keiner -- Stopp nicht vom Test (%s), Arbeitsraum pruefen" % log["stop_reason"]
    if start_joints is None:
        return "keiner -- keine Startstellung in bc_policy.json"
    robot.clear_stop()
    if robot.read_state().gripper_closed:
        robot.gripper_command(False)   # oeffnet waehrend des Dwells vor dem Anheben
    result = planned_transport(robot, workspace, start_joints, clock,
                               servo_rate_hz=args.servo_rate, planner=planner,
                               threaded_watchdog=not isinstance(clock, SimClock))
    return "am Start" if result["stop_reason"] == "endstellung" else result["stop_reason"]


def grasp_height(info, known=None):
    """Greifhoehe (z des Werkzeugpunkts): PICK der bekannten Lage, sonst der
    tiefste Punkt der Demonstrationen; None, wenn beides fehlt."""
    if known is not None:
        return float(np.asarray(known.pick, dtype=float)[2])
    if info.get("ideal_z_min") is not None:
        return float(info["ideal_z_min"])
    return None


def ptp_height_problem(robot, grasp_z):
    """Text, wenn eine PTP-Fahrt aus der jetzigen Stellung zu tief beginnt, sonst None.

    Befund 2026-11-24: Der Rueckzug hing ~10 mm ueber dem Objekt; der naechste
    Lauf fuhr per PTP direkt zur Startstellung. Eine Gelenkfahrt hebt nicht erst
    an -- die Backen koennen dabei durchs Objekt gezogen werden.
    """
    if grasp_z is None:
        return None
    height = float(robot.read_state().tcp_quat[2]) - grasp_z
    if height >= config.PTP_MIN_ABOVE_GRASP_M:
        return None
    return ("Werkzeug steht nur %.0f mm ueber der Greifhoehe (Grenze %.0f mm) -- keine "
            "PTP-Fahrt von hier, sie koennte durchs Objekt ziehen. Arm erst von Hand "
            "(Handbediengeraet) senkrecht anheben, dann neu starten."
            % (1e3 * height, 1e3 * config.PTP_MIN_ABOVE_GRASP_M))


def move_to_joints_checked(robot, joints, grasp_z, what):
    """``move_to_joints`` nur, wenn :func:`ptp_height_problem` nichts meldet.
    Rueckgabe False = nicht gefahren (Meldung ist ausgegeben)."""
    problem = ptp_height_problem(robot, grasp_z)
    if problem is not None:
        print("NICHT GEFAHREN (%s): %s" % (what, problem))
        return False
    robot.move_to_joints(joints)
    return True


def camera_check_before_run(robot, captures, info, start, start_gripper, args,
                            use_sim_cameras, out, grasp_z=None):
    """Kameras in der Startstellung gegen die Aufnahme pruefen (bc/camera_check.py).

    Rueckgabe False = nicht fahren (Abweichung, ``--kamerapruefung an`` und
    keine Freigabe). Ohne Referenz im Checkpoint oder mit Platzhalter-/Replay-
    Kameras: nur ein Hinweis, gefahren wird wie bisher.
    """
    from bc import camera_check

    reference = info.get(camera_check.REFERENCE_KEY)
    if use_sim_cameras or args.replay:
        print("KAMERAPRUEFUNG: uebersprungen (Platzhalter- oder Replay-Bilder)")
        return True
    if not reference:
        print("KAMERAPRUEFUNG: keine Referenz im Checkpoint -- nachtragen mit "
              "tools/kamera_referenz.py --checkpoint <policy>")
        return True
    # Startstellung wie die Referenzbilder (erstes Bild jeder Episode)
    if start_gripper is not None:
        robot.gripper_command(start_gripper > config.GRIPPER_THRESHOLD)
    if start is not None and not args.no_start_move:
        away = float(np.max(np.abs(robot.read_state().joints - start)))
        if away > config.START_POSE_TOL_RAD:
            print("Kamerapruefung: an die Startstellung (%.3f rad entfernt)" % away)
            if not move_to_joints_checked(robot, start, grasp_z, "Kamerapruefung"):
                return False
    time.sleep(config.CAMERA_CHECK_SETTLE_S)    # frische Bilder nach dem Anhalten
    frames = {}
    for cap in captures:
        frame = cap.latest()
        frames[cap.name] = None if frame is None else _to_schema_size(frame.image)
    results = camera_check.compare(reference, frames)
    for line in camera_check.format_lines(results):
        print(line)
    print(camera_check.to_json_line(results))   # fuer die Tabelle in der Oberflaeche
    try:
        import cv2
        for name, image in frames.items():
            if image is not None:
                ref = camera_check.decode_image(reference[name]["image_png_b64"]) \
                    if name in reference else np.zeros_like(image)
                # Bilder liegen als RGB vor, cv2 schreibt BGR
                cv2.imwrite(str(Path(out) / ("kamerapruefung_%s.png" % name)),
                            np.ascontiguousarray(np.hstack([ref, image])[..., ::-1]))
    except Exception as exc:   # Bild ist nur Beiwerk
        print("Hinweis: Pruefbilder nicht gespeichert (%s)" % exc)
    warn = any(r["level"] == camera_check.WARN for r in results)
    print("KAMERAPRUEFUNG gesamt: %s (Bilder: Training links, jetzt rechts, in %s)"
          % ("WARNUNG" if warn else "OK", out))
    if not warn or args.kamerapruefung in ("warnen", "nur"):
        return True
    answer = ask("Kameras weichen von der Aufnahme ab -- trotzdem fahren? [j/N] ", "n")
    if answer.strip().lower() != "j":
        print("Nicht gefahren: Kamerapruefung mit Abweichung (Licht, Belichtung, Kameralage "
              "pruefen oder --kamerapruefung warnen).")
        return False
    return True


def run_planned(robot, workspace, targets, gripper, clock, servo_rate_hz=config.SERVO_RATE_HZ,
                threaded_watchdog=True, captures=None, mitschrieb=None):
    """Geplante Gelenkbahn als servo_j-Strom, Greifer je Takt wie geplant.

    ``targets`` (N, 6) aus kin.solve_path, ``gripper`` (N,) aus der Idealbahn
    (der Planer hat am Greiferwechsel den Dwell schon eingefuegt). Jedes Ziel
    ist vorab geprueft; der Watchdog laeuft mit. Rueckgabe: Log mit t/joints/
    tcp/gripper_cmd und ``stop_reason`` ("fertig" oder der Grund).

    ``mitschrieb`` (mit ``captures``): je Takt die Beobachtung VOR dem Senden
    und das Ziel dieses Takts (DAgger: Label des Experten).
    """
    log = {k: [] for k in ("t", "joints", "tcp", "gripper_cmd")}
    stop_reason = "fertig"
    q0 = np.asarray(robot.read_state().joints, dtype=float)
    watchdog = Watchdog(robot, [geofence_check(robot, workspace)], clock)
    if threaded_watchdog:
        watchdog.start()
    interp = ServoInterpolator(servo_rate_hz=servo_rate_hz).reset(q0)
    stall = StallGuard()
    robot.activate_servo("position")
    pacer = Pacer(clock, servo_rate_hz).start()
    closed = None
    try:
        for q, g in zip(targets, gripper):
            if not threaded_watchdog and watchdog.run_once() is not None:
                stop_reason = "geofence: %s" % watchdog.tripped
                break
            want = bool(g > config.GRIPPER_THRESHOLD)
            if mitschrieb is not None and captures is not None:
                obs, _ = build_observation(robot, captures)
                mitschrieb.add(obs, q, float(want), dagger.EXPERT)
            if want != closed:
                robot.gripper_command(want)
                closed = want
            for qq, v, a in interp.window(q):
                if robot.stop_requested:
                    break
                pacer.tick()
                robot.servo_j(qq, v, a)
            if robot.stop_requested:
                stop_reason = "stopp: %s" % (watchdog.tripped or "angefordert")
                break
            state = robot.read_state()
            log["t"].append(clock.now())
            log["joints"].append(state.joints)
            log["tcp"].append(np.asarray(state.tcp_quat, dtype=float))
            log["gripper_cmd"].append(float(want))
            stall.check(state.joints, q)
    except RobotError as exc:
        stop_reason = "abgelehnt: %s" % exc
        robot.emergency_stop()
    except ArmStalled as exc:
        stop_reason = str(exc)
        report_stall(robot, "Experte", exc)
        robot.emergency_stop()
    finally:
        watchdog.stop()
        robot.deactivate_servo()
    out = {k: np.asarray(v, dtype=float) for k, v in log.items()}
    out["stop_reason"] = stop_reason
    return out


def approach_above_pick(robot, workspace, known):
    """Gelenkwinkel ueber dem PICK (``RELOCATE_APPROACH_ABOVE_PICK_M``), in der
    Greiferdrehung, die der jetzigen naeher liegt; vorab gegen das
    Kollisionsmodell geprueft. Wirft bei IK-Fehler oder verbotenem Ziel."""
    from bc.kinematics import Kinematics

    q0 = np.asarray(robot.read_state().joints, dtype=float)
    p0 = np.asarray(robot.fk(q0), dtype=float)
    _above, grasp, _info = known_pose.correction(known, p0)
    target = np.asarray(grasp, dtype=float).copy()
    target[2] += config.RELOCATE_APPROACH_ABOVE_PICK_M
    q = np.asarray(Kinematics(robot).ik(target, q0), dtype=float)
    check_target(workspace, robot, q)
    return q


def relocate_only(robot, workspace, known, reference_pick, start_joints, grasp_z, clock, args,
                  planner, rng, pick_state):
    """Teil ohne Policy-Fahrt umlegen (``--nur-umlegen``, Modellvergleich).

    Arm an die Startstellung (PTP nur aus sicherer Hoehe), Greifer auf, dann
    derselbe Experte wie nach einem Probegriff: ueber PICK, greifen, an eine
    neue Lage legen, PICK in der Steuerung nachfuehren, zurueck zum Start.
    Rueckgabe dict ``result`` (Text), ``new_pick``, ``placed_xy``, ``ok``.
    """
    if workspace is None or known is None:
        return {"ok": False, "result": "keine bekannte Lage", "new_pick": None,
                "placed_xy": None}
    if start_joints is not None:
        away = float(np.max(np.abs(robot.read_state().joints - start_joints)))
        if away > config.START_POSE_TOL_RAD and not move_to_joints_checked(
                robot, start_joints, grasp_z, "Umlegen"):
            return {"ok": False, "result": "nicht gefahren: Arm steht zu tief",
                    "new_pick": None, "placed_xy": None}
    if robot.read_state().gripper_closed:
        robot.gripper_command(False)
    back_to = start_joints if start_joints is not None else np.asarray(robot.read_state().joints)
    # Erst per PTP ueber den PICK (Gelenkfahrt, keine Singularitaet auf einer
    # langen Geraden), dann der Experte wie nach einem Probestopp: senkrecht ab
    try:
        q_above = approach_above_pick(robot, workspace, known)
    except Exception as exc:
        return {"ok": False, "result": "nicht ueber den PICK planbar (%s)" % exc,
                "new_pick": None, "placed_xy": None}
    print("Umlegen: per PTP %.0f mm ueber den PICK"
          % (1e3 * config.RELOCATE_APPROACH_ABOVE_PICK_M))
    robot.move_to_joints(q_above)
    expert = expert_after_probe(robot, workspace, known, reference_pick, back_to, clock, args,
                                planner, rng, pick_state)
    new_pick = expert.get("new_pick")
    return {"ok": new_pick is not None, "result": expert.get("result"),
            "new_pick": None if new_pick is None else [float(v) for v in new_pick],
            "placed_xy": expert.get("placed_xy")}


def placement_history():
    """Gemerkte Ablagen des Experten ueber alle Laeufe (bc/known_pose.py)."""
    return known_pose.placement_history(known_pose.placements_file(config.TOUCHUP_BACKUP_ROOT))


def remember_placement(xy):
    try:
        known_pose.remember_placement(known_pose.placements_file(config.TOUCHUP_BACKUP_ROOT), xy)
    except OSError as exc:
        print("Hinweis: Ablage nicht gemerkt (%s)" % exc)


def _write_pick(robot, joints, pick_state):
    """PICK in der Steuerung auf ``joints`` setzen. Erste Aenderung je Lauf mit
    Sicherung wie beim Touch-up, danach nur schreiben (Stand vor dem Lauf
    bleibt in der Sicherung, wie apps/record.py adopt_pick)."""
    from bc import touchup

    joints = [float(v) for v in joints]
    if pick_state.get("backup") is None:
        plan = {"name": "PICK", "joints": joints, "problems": [], "warnings": [],
                "tool": getattr(robot, "tool_name", None),
                "in_simulation": getattr(robot, "in_simulation", None)}
        pick_state["backup"], _record = touchup.apply_touch_up(robot, plan,
                                                               config.TOUCHUP_BACKUP_ROOT)
    else:
        robot.store_point("PICK", joints)
        touchup.update_backup_target(pick_state["backup"], joints)
    return pick_state["backup"]


def expert_after_probe(robot, workspace, known, reference_pick, start_joints, clock, args,
                       planner, rng, pick_state, captures=None, mitschrieb=None):
    """Experte nach dem Probegriff: korrigieren, greifen, neu ablegen, PICK nachfuehren.

    Rueckgabe dict: ``correction`` (bc/known_pose.correction), ``result``
    (Text), ``log`` (gefahrene Bahn, fuer DAgger), ``new_pick`` (Pose) und
    ``placed_xy`` -- oder ohne ``log``, wenn nichts planbar war (dann steht
    der Arm noch am Stopp).
    """
    from bc.auto_layout import rotated_about
    from bc.kinematics import IKFailure, Kinematics
    from bc.trajectory import build_ideal_trajectory

    planner = planner or {}
    if robot.stop_requested:
        robot.clear_stop()
    state = robot.read_state()
    if state.gripper_closed:
        robot.gripper_command(False)       # Policy hat in der Luft geschlossen
    kin = Kinematics(robot)
    q0 = np.asarray(state.joints, dtype=float)
    p0 = np.asarray(robot.fk(q0), dtype=float)
    above, grasp, info = known_pose.correction(known, p0)
    lift = TRANSPORT_LIFT_M
    up_grasp = grasp.copy()
    up_grasp[2] += lift
    out = {"correction": info, "result": None}
    try:
        lift_joints = kin.ik(up_grasp, q0)
    except IKFailure as exc:
        out["result"] = "Greifpunkt nicht erreichbar (%s)" % exc
        return out
    start_pose = np.asarray(robot.fk(start_joints), dtype=float)
    speeds = dict(transit_speed=planner.get("transit_speed_ms") or config.TRANSIT_SPEED_MS,
                  approach_speed=planner.get("approach_speed_ms") or config.APPROACH_SPEED_MS,
                  ptp_joint_speed=planner.get("ptp_joint_speed_rads") or config.PTP_JOINT_SPEED_RADS)
    plan, last_error = None, "keine freie Lage"
    # Drehverteilung um die Startstellung (config.AUTO_YAW_CENTER_POINT): plus und
    # minus gegen den Start gleich oft -- wie bei der Aufnahme
    from bc.live import yaw360 as _yaw360
    center = (((_yaw360(start_pose, known.table) - _yaw360(reference_pick, known.table)
                + 180.0) % 360.0 - 180.0) if config.AUTO_YAW_CENTER_POINT else None)
    candidates = list(known_pose.new_place_pose(known, reference_pick, rng,
                                                used_xy=placement_history()
                                                + list(pick_state.get("used_xy", ())),
                                                center_shift_deg=center))
    planned = getattr(args, "ablage_pose", None)
    if planned:
        # vorab geplante Lage (Reiter Vergleich) zuerst, sonst automatisch
        from bc.table import yaw_deg as _yaw_deg
        planned = np.asarray(planned, dtype=float)
        turn_planned = ((_yaw_deg(planned, known.table) - _yaw_deg(reference_pick, known.table)
                         + 90.0) % 180.0) - 90.0
        candidates.insert(0, (planned, (float(planned[0]), float(planned[1])),
                              float(turn_planned)))
    for pose, xy, turn in candidates:
        # in derselben Orientierung ablegen, wie gegriffen wurde
        place = (rotated_about(pose, known.table.normal_at(pose[0], pose[1]), np.pi)
                 if info["flipped"] else pose)
        up_place = place.copy()
        up_place[2] += lift
        try:
            place_above_joints = kin.ik(up_place, lift_joints)
            waypoints = known_pose.expert_waypoints(
                p0, q0, above, grasp, place, start_joints, lift, lift_joints,
                place_above_joints, start_pose,
                regrasp=bool(getattr(args, "nachgreifen", False)))
            ideal = build_ideal_trajectory(waypoints, fk=robot.fk, **speeds)
            targets = kin.solve_path(ideal.poses_quat, q0, fixed_joints=ideal.joints)
            for q in targets:
                check_target(workspace, robot, q)
        except (IKFailure, TargetRejected, ValueError) as exc:
            last_error = str(exc)
            continue
        plan = (pose, xy, turn, place, ideal, targets)
        break
    if plan is None:
        out["result"] = "keine Ablage planbar (%s) -- Arm steht am Stopp" % last_error
        return out
    pose, xy, turn, place, ideal, targets = plan
    out["planned_pose_used"] = bool(planned is not None and len(planned)
                                    and np.allclose(pose, planned))
    if planned is not None and len(planned) and not out["planned_pose_used"]:
        print("   Hinweis: geplante Ablage nicht erreichbar (%s) -- ausgewichen" % last_error)
    log = run_planned(robot, workspace, targets, ideal.gripper, clock,
                      servo_rate_hz=args.servo_rate,
                      threaded_watchdog=not isinstance(clock, SimClock),
                      captures=captures, mitschrieb=mitschrieb)
    out["log"] = log
    out["ideal_poses"] = np.asarray(ideal.poses_quat, dtype=float)
    out["placed_xy"] = xy
    if log["stop_reason"] != "fertig":
        out["result"] = "abgebrochen: %s" % log["stop_reason"]
        return out
    # PICK = Greifpose der neuen Lage (wie die Aufnahme sie greifen wuerde)
    opened = np.flatnonzero(np.diff((np.asarray(ideal.gripper) > config.GRIPPER_THRESHOLD)
                                    .astype(int)) < 0)
    seed = targets[int(opened[0]) + 1] if opened.size else targets[-1]
    try:
        joints = kin.ik(pose, seed)
        backup = _write_pick(robot, joints, pick_state)
    except Exception as exc:     # Objekt liegt trotzdem dort
        out["result"] = ("abgelegt bei x %.0f y %.0f mm, PICK NICHT nachgefuehrt (%s) -- "
                         "vor der naechsten Fahrt teachen" % (1e3 * xy[0], 1e3 * xy[1], exc))
        return out
    pick_state.setdefault("used_xy", []).append(xy)
    remember_placement(xy)
    out["new_pick"] = [float(v) for v in pose]
    out["result"] = ("gegriffen, abgelegt bei x %.0f y %.0f mm (Drehung %+.0f Grad), PICK "
                     "nachgefuehrt (Sicherung %s)" % (1e3 * xy[0], 1e3 * xy[1], turn,
                                                     Path(backup).name))
    return out


def make_localizer():
    """M1-Lokalisierung der Gruppe (bc/lokalisierung.py) -- in Tests ersetzbar."""
    from bc import lokalisierung
    return lokalisierung.M1Localizer()


def localize_pick(robot, captures, localizer, known, args, info, planner, pick_state, clock):
    """Fotostellung, M1 lokalisiert, PICK in der Steuerung setzen, Lage neu laden.

    Rueckgabe ``(protokoll, known)``. Der Vergleich gegen den bisherigen PICK
    (geteacht oder vom Experten nachgefuehrt) steht im Protokoll -- liegt das
    Teil seit dem Umlegen unveraendert, ist das die Genauigkeit von M1.
    """
    from bc import lokalisierung
    from bc.kinematics import Kinematics

    scene = next((c for c in captures if c.name == "scene"), None)
    if scene is None:
        raise lokalisierung.LocalizationError("keine Szenenkamera -- M1 braucht ihr Bild")
    joints, _ = robot.get_point(args.foto_punkt)
    joints = np.asarray(joints, dtype=float)
    if float(np.max(np.abs(robot.read_state().joints - joints))) > config.START_POSE_TOL_RAD:
        print("Lokalisierung: an die Fotostellung '%s'" % args.foto_punkt)
        problem = ptp_height_problem(robot, grasp_height(info, known))
        if problem is not None:
            raise lokalisierung.LocalizationError("Fotostellung nicht angefahren: " + problem)
        robot.move_to_joints(joints)
    loc = localizer.locate(lokalisierung.full_frame(scene, clock=clock))
    print("Lokalisierung: %s" % loc.describe())
    before = np.asarray(known.pick, dtype=float).copy()
    pose = lokalisierung.pick_pose(loc, before, known.table)
    try:
        seed = np.asarray(robot.get_point("PICK")[0], dtype=float)
    except KeyError:
        seed = robot.read_state().joints
    q = Kinematics(robot).ik(pose, seed)
    backup = _write_pick(robot, q, pick_state)
    known = load_known_pose(args, info, robot, planner)
    diff = lokalisierung.compare(known.pick, before, known.table)
    print("Lokalisierung: PICK gesetzt (Sicherung %s), gegen den bisherigen PICK dx %.1f dy %.1f "
          "mm, Drehung %.1f Grad" % (Path(backup).name, 1e3 * diff["dx_m"], 1e3 * diff["dy_m"],
                                     diff["yaw_deg"]))
    if loc.gripper_yaw360_deg is not None:
        # Abgleich der Fase (config.LOCALIZE_CHAMFER_OFFSET_DEG): M2-Richtung gegen
        # die Werkzeug-x-Richtung des bisherigen PICK (geteacht / vom Experten)
        from bc.live import yaw360, yaw_diff
        offset = yaw_diff(yaw360(before, known.table), loc.gripper_yaw360_deg)
        print("Lokalisierung: Fase erkannt -- M2-Richtung %.0f Grad, bisheriger PICK %.0f Grad, "
              "Versatz %+.0f Grad (config.LOCALIZE_CHAMFER_OFFSET_DEG = %s)"
              % (loc.gripper_yaw360_deg, yaw360(before, known.table), offset,
                 config.LOCALIZE_CHAMFER_OFFSET_DEG))
    if diff["xy_m"] > config.LOCALIZE_WARN_M:
        print("   Hinweis: mehr als %.0f mm -- Teil von Hand bewegt? Sonst M1-Kalibrierung pruefen."
              % (1e3 * config.LOCALIZE_WARN_M))
    record = dict(loc.as_dict(), pick=[float(v) for v in known.pick],
                  gegen_vorher=diff, foto_punkt=args.foto_punkt)
    return record, known


def write_dagger_episode(writer, rec, known, ideal_q, expert, log, lage, meta, ep, lokal=None):
    """Policy + Experte einer Fahrt als Episode schreiben (bc/dagger.py).

    Nicht geschrieben: Not-Aus (Arm steht) und Fahrten ohne Policy-Takte.
    Erfolg = der Experte hat gegriffen und neu abgelegt.
    """
    reason = str(log["stop_reason"])
    if reason.startswith("arm steht"):
        print("   DAgger: nicht geschrieben (Arm stand -- Not-Aus)")
        return {"geschrieben": False, "grund": "arm steht"}
    if not rec.count(dagger.POLICY):
        print("   DAgger: nicht geschrieben (keine Policy-Takte)")
        return {"geschrieben": False, "grund": "keine Takte"}
    expert = expert or {}
    expert_log = expert.get("log")
    grasped = bool(expert.get("new_pick") is not None and expert_log is not None
                   and expert_log["stop_reason"] == "fertig")
    episode_meta = dict(meta or {})
    stamp = datetime.now().isoformat(timespec="seconds")
    episode_meta.update({
        "recorded_at": stamp,
        "episode_index": int(ep),
        # Kopien beim Gewichten (export_variante --dagger-gewicht) bleiben so
        # auf derselben Seite der Train/Val-Aufteilung (apps/train.py)
        "repeat_group": "dagger/%s/%d" % (stamp, int(ep)),
        "stop_reason": reason,
        "points": {"PICK": {"pose_quat": [float(v) for v in known.pick]}},
        "dagger": {"lage": (lage or {}).get("summary"), "experte": {
            k: expert.get(k) for k in ("correction", "result", "new_pick", "placed_xy")},
            "lokalisierung": lokal},
    })
    try:
        episode, info = dagger.build_episode(rec, known.ideal, ideal_q,
                                             expert_ideal_poses=expert.get("ideal_poses"),
                                             metadata=episode_meta,
                                             success=True if grasped else None)
        index = writer.append(episode)
    except Exception as exc:     # ein Schreibfehler darf die Reihe nicht stoppen
        print("   DAgger: NICHT geschrieben (%s)" % exc)
        return {"geschrieben": False, "grund": str(exc)}
    print("   DAgger: Episode %d (Policy %d + Experte %d Takte, Abstand zur Idealbahn median "
          "%.1f / max %.1f mm)%s" % (index, info["policy_steps"], info["expert_steps"],
                                     info["label_offset_mm_median"], info["label_offset_mm_max"],
                                     "" if grasped else " -- Experte hat nicht gegriffen"))
    return dict(info, geschrieben=True, index=int(index), ordner=str(writer.root))


def build_workspace(table_z, info, robot, robot_info, args, known=None, table_clearance=None,
                    progress=print):
    """Kollisionsmodell der Fahrt: Tischquader, Tisch/Sperrzonen/Huelle aus der
    Aufnahme (live), ohne Tischdaten der Tisch der bekannten Lage, Hindernisse."""
    workspace = default_workspace(table_height_m=table_z)
    table_source = add_recorded_workspace(workspace, info, robot, robot_info["robot"],
                                          progress=progress, table_clearance=table_clearance)
    if known is not None and table_source is None:
        # Policy ohne Tischdaten: der Tisch der bekannten Lage schuetzt trotzdem
        from bc.table import TableSurface
        clearance_m = config.TABLE_MIN_CLEARANCE_M if table_clearance is None else table_clearance
        workspace.add_box(TableSurface(known.table, min_clearance=clearance_m))
        progress("Kollisionsmodell: Tisch aus dem Ablauf (%s), Werkzeugspitze >= %.1f mm"
                 % (known.table.describe(), 1e3 * clearance_m))
    if obstacles.applies(robot_info["robot"], robot_info.get("in_simulation"), args.hindernisse):
        zelle = obstacles.load()
        if zelle is None:
            progress("Hinweis: %s fehlt -- nur Kugelmodell und Tisch." % obstacles.OBSTACLES_FILE)
        else:
            workspace.add_obstacles(zelle)
            progress("Hindernisse: %s (%s)" % (zelle.describe(), obstacles.OBSTACLES_FILE))
    return workspace


def confirm_real_robot():
    print("\n!! --real-robot: Die POLICY faehrt die REALE ANLAGE.")
    print("   Not-Aus in Reichweite? Arbeitsraum frei? Override geprueft?")
    answer = ask("   Zum Fortfahren '%s' eintippen: " % REAL_ROBOT_CONFIRMATION)
    if answer.strip() != REAL_ROBOT_CONFIRMATION:
        raise SystemExit("Abgebrochen -- reale Anlage nicht freigegeben.")


def check_against_recording(info, args, robot_kind, cam_cfgs):
    """Erzwingt Gleichheit mit der Aufzeichnung (AP 1.5.1 / 2.6)."""
    problems = []
    camera_names = [c.name for c in cam_cfgs]
    backends = (info.get("recording") or {}).get("camera_backends")
    if backends:
        # Replay: die Bilder SIND die der Aufnahme, das Backend zaehlt nicht
        now = {c.name: c.backend for c in cam_cfgs
               if c.name in info["cameras"] and c.backend != "replay"}
        differ = {k: (backends.get(k), v) for k, v in now.items() if backends.get(k) != v}
        if differ and robot_kind == "mujoco":
            # Taktiksimulation: echte Policy auf Sim-Bildern ist erlaubt (Verdrahtung,
            # Vergleich) -- das Ergebnis sagt dann nichts ueber die Policy
            print("Hinweis: Kamera-Backends Aufzeichnung/jetzt: %s -- Policy kennt die "
                  "MuJoCo-Bilder nicht" % differ)
        elif differ:
            problems.append("Kamera-Backends Aufzeichnung/jetzt: %s (--cameras pruefen)" % differ)
    if info["schema_version"] != config.SCHEMA_VERSION:
        problems.append("Schema v%s, Code v%s" % (info["schema_version"], config.SCHEMA_VERSION))
    if float(info["rate_hz"]) != config.CONTROL_RATE_HZ:
        problems.append("Rate %.1f Hz, Code %.1f Hz" % (info["rate_hz"], config.CONTROL_RATE_HZ))
    if list(info["image_size_hw"]) != [config.IMAGE_HEIGHT, config.IMAGE_WIDTH]:
        problems.append("Bildgroesse %s" % info["image_size_hw"])
    missing = [c for c in info["cameras"] if c not in camera_names]
    if missing:
        problems.append("Kameras %s fehlen (vorhanden %s)" % (missing, camera_names))
    rec = info.get("recording", {})
    rec_mode = (rec.get("execution") or {}).get("mode") or execution_module.SERVO_J
    if args.execution_mode != rec_mode:
        problems.append("Ausfuehrung Aufzeichnung %s, jetzt %s (--ausfuehrung %s)"
                        % (rec_mode, args.execution_mode, rec_mode))
    if rec_mode in execution_module.SERVO_PROFILES and rec.get("servo_rate_hz") is not None \
            and float(rec["servo_rate_hz"]) != args.servo_rate:
        problems.append("servo_j-Rate Aufzeichnung %.0f Hz, jetzt %.0f Hz "
                        "(--servo-rate %.0f)"
                        % (rec["servo_rate_hz"], args.servo_rate, rec["servo_rate_hz"]))
    if robot_kind == "neura" and rec.get("override") is not None and float(rec["override"]) != args.override:
        problems.append("Override Aufzeichnung %.2f, jetzt %.2f" % (rec["override"], args.override))
    if rec.get("robot") and rec["robot"] != robot_kind:
        print("Hinweis: aufgezeichnet mit Roboter '%s', jetzt '%s'." % (rec["robot"], robot_kind))
    return problems


def ask(prompt, default=""):
    """Rueckfrage im Terminal; ohne stdin die sichere Antwort.

    Aus der Bedienoberflaeche laufen diese Skripte als Unterprozess mit
    geschlossenem stdin. ``input()`` wirft dort EOFError -- und zwar unter
    Umstaenden mitten in einem Lauf, der den Roboter bewegt. Eine
    unbeantwortete Sicherheitsfrage ist ein Nein, kein Absturz.
    """
    try:
        return input(prompt)
    except EOFError:
        # input() hat den Prompt schon geschrieben -- hier nur noch, was
        # daraus wird.
        print("[keine Eingabe moeglich -> '%s']" % default)
        return default


def resolve_checkpoint(path):
    path = Path(path)
    if (path / "policy" / "bc_policy.json").is_file():
        return path / "policy"
    return path


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--checkpoint", help="Policy-Ordner (apps/train.py: <out>/policy)")
    parser.add_argument("--hold", action="store_true",
                        help="HoldPolicy statt Modell (Verdrahtungstest)")
    parser.add_argument("--sim", action="store_true", help="= --robot sim")
    parser.add_argument("--robot", choices=("sim", "neura", "mujoco"), default=None,
                        help="mujoco = Taktiksimulation (bc/sim_mujoco), Kameras dazu "
                             "--camera wrist=mujoco --camera scene=mujoco")
    parser.add_argument("--testlagen", nargs="?", const="", default=None, metavar="DATEI",
                        help="nur --robot mujoco: fester Testlagen-Satz (Default "
                             "bc/sim_mujoco/testlagen_v1.json), eine Fahrt je Lage, danach "
                             "Sim-Auswertung")
    parser.add_argument("--testlagen-auswahl", dest="testlagen_auswahl", default=None,
                        help="Lagen aus dem Satz, z. B. '0-4' oder '0,7,12' (Default alle)")
    parser.add_argument("--cameras", choices=CAMERA_MODES, default="auto",
                        help="wie apps/record.py -- muss zur Aufzeichnung passen")
    parser.add_argument("--uvc-device", type=int, default=None,
                        help="OpenCV-Index der Webcam bei --cameras wrist-uvc (wie apps/record.py)")
    parser.add_argument("--camera", action="append", default=None,
                        metavar="NAME=BACKEND[:GERAET][@FPS]",
                        help="einzelnen Kameraplatz abweichend besetzen, z. B. 'scene=uvc:1' oder 'wrist=sim'; mehrfach angebbar. Ergaenzt --cameras, das den Ausgangspunkt setzt (Geraete auflisten: tools/check_cameras.py --list)")
    parser.add_argument("--replay", default=None, metavar="AUFNAHME",
                        help="Bilder dieser Aufnahme (Ordner mit index.json) statt der Kameras "
                             "einspielen; nur Simulation/VM (bc/replay.py)")
    parser.add_argument("--replay-episode", default="0", metavar="LISTE",
                        help="Episoden fuer --replay: '3', '0,4,7', '2-5' oder 'alle'; "
                             "Fahrt i nimmt die i-te (Default %(default)s)")
    parser.add_argument("--real-robot", action="store_true")
    parser.add_argument("--override", type=float, default=None,
                        help="Neura-Override; Default und Pflichtwert: der der Aufzeichnung")
    parser.add_argument("--servo-rate", type=float, default=config.SERVO_RATE_HZ,
                        help="servo_j-Senderate in Hz, Vielfaches von %.0f. MUSS die "
                             "der Aufzeichnung sein (AP 1.5.1) -- der Abgleich gegen "
                             "die Metadaten des Checkpoints bricht sonst ab."
                             % config.CONTROL_RATE_HZ)
    parser.add_argument("--ausfuehrung", choices=(execution_module.AUTO,) + execution_module.MODES,
                        default=None,
                        help="servo_j, servo_j_pos oder online (bc/execution.py). Default und Pflichtwert: "
                             "die der Aufzeichnung (bc_policy.json); --hold: auto")
    parser.add_argument("--realtime", action="store_true",
                        help="SimRobot mit echter Uhr (Latenz der Vorhersage wirkt wie an der Anlage)")
    parser.add_argument("--episodes", type=int, default=None,
                        help="Anzahl Fahrten (Default 1, mit --replay: eine je Episode)")
    parser.add_argument("--steps", "--max-steps", dest="max_steps", type=int, default=None,
                        help="Hoechstzahl Takte je Fahrt (Default 1.5 x laengste Episode)")
    parser.add_argument("--replan", type=int, default=None,
                        help="alle N Takte neu vorhersagen (Default aus bc_policy.json)")
    parser.add_argument("--decay", type=float, default=None,
                        help="Gewichtung beim Mitteln, exp(-k*Alter) (Default aus bc_policy.json)")
    parser.add_argument("--no-ensemble", action="store_true",
                        help="Chunks nicht mitteln, sondern je --replan Takte abarbeiten (Vergleich)")
    parser.add_argument("--inference-steps", type=int, default=None, help="DDIM-Schritte")
    parser.add_argument("--glaettung", type=float, default=None,
                        help="Tiefpass auf die Ziele: alpha in (0, 1], je Takt "
                             "z = alpha*Ziel + (1-alpha)*z_vorher. 1 = aus. Default aus "
                             "bc_policy.json (inference_defaults), sonst "
                             "config.POLICY_COMMAND_LOWPASS_ALPHA (0,5; Anlage 23.11.). "
                             "0,5 ~1 Takt Verzug, 0,25 ~3 Takte (bc/servo.CommandLowpass)")
    parser.add_argument("--sync-predict", action="store_true",
                        help="Vorhersage im Takt statt im eigenen Thread (Default nur bei SimClock)")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ablage-seed", dest="ablage_seed", type=int, default=None,
                        help="Zufall fuer die Ablage des Experten (Default: jedes Mal neu, "
                             "steht in summary.json unter args)")
    parser.add_argument("--table-z", type=float, default=None)
    parser.add_argument("--hindernisse", choices=("auto", "an", "aus"), default="auto",
                        help="feste Hindernisse der Zelle (einstellungen/hindernisse.json); "
                             "auto = nur an der realen Anlage (Default %(default)s)")
    parser.add_argument("--no-start-move", action="store_true",
                        help="nicht vorher an die Startstellung fahren")
    parser.add_argument("--transport-geplant", action="store_true",
                        help="Policy nur bis zum Griff; danach Dwell, %.0f cm senkrecht anheben und "
                             "PTP zur Endstellung aus bc_policy.json (Policies, die nur auf Anflug "
                             "und Griff trainiert sind, tools/export_variante.py --abschneiden-nach)"
                             % (100 * TRANSPORT_LIFT_M))
    parser.add_argument("--lage-bekannt", dest="lage_bekannt", action="store_true",
                        help="Policy-Test mit bekannter Lage (bc/known_pose.py): PICK und Tisch "
                             "live aus der Steuerung, Idealbahn aus der Ablaufdatei; je Takt die "
                             "Abweichung, am Griff/Stopp die Lage gegen PICK. Die Policy endet mit "
                             "dem Griff, danach Greifer auf, anheben, zurueck zum Start.")
    parser.add_argument("--ablauf", default=None, metavar="DATEI",
                        help="Ablaufdatei fuer --lage-bekannt (Default: die der Aufnahme aus "
                             "bc_policy.json table_spec.sequence_file)")
    parser.add_argument("--probe-abstand", dest="probe_abstand", type=float, default=None,
                        metavar="MM",
                        help="mit --probegriff objekt: Abstand der Werkzeugspitze ueber der "
                             "Objektoberkante in mm (Default %.0f; Nachlauf nach dem Stopp an der "
                             "Anlage bis 7,5 mm -- schrittweise annaehern)" % (1e3 * config.PROBE_GAP_M))
    parser.add_argument("--nur-umlegen", dest="nur_umlegen", action="store_true",
                        help="mit --lage-bekannt --probegriff objekt: keine Policy-Fahrt -- "
                             "der Experte greift das Teil am PICK, legt es an eine neue Lage "
                             "und fuehrt PICK nach (Modellvergleich, apps/vergleich.py)")
    parser.add_argument("--ablage-pose", dest="ablage_pose", default=None, metavar="X,Y,Z,QW,QX,QY,QZ",
                        help="Experte: zuerst an diese Pose ablegen (m, Basis-KS; vorab geplant, "
                             "Reiter Vergleich) -- nicht erreichbar: automatische Wahl wie sonst")
    parser.add_argument("--nachgreifen", action="store_true",
                        help="mit Experte: nach dem Ablegen auf Greifhoehe noch einmal "
                             "schliessen und oeffnen -- der Greifer schiebt das Teil mittig, "
                             "es liegt dann am nachgefuehrten PICK (Anwender 2026-11-24)")
    parser.add_argument("--ohne-experte", dest="experte", action="store_false",
                        help="mit --probegriff objekt: nach dem Stopp ueber dem Objekt NICHT "
                             "korrigieren/greifen/umlegen -- senkrecht anheben, zurueck zum "
                             "Start; gespeichert wird, wohin die Policy noch wollte "
                             "(Anwender 2026-11-19). Das Objekt bleibt liegen.")
    parser.add_argument("--probegriff", choices=known_pose.PROBE_MODES, default="objekt",
                        help="mit --lage-bekannt: 'tisch' = echter Griff (Werkzeugspitze >= %.0f mm "
                             "ueber dem Tisch), 'objekt' = Stopp %.0f mm ueber der Objektoberkante, "
                             "ohne Kontakt (Default %%(default)s)"
                             % (1e3 * config.TABLE_MIN_CLEARANCE_M, 1e3 * config.PROBE_GAP_M))
    parser.add_argument("--pick-quelle", dest="pick_quelle", choices=("steuerung", "m1"),
                        default="steuerung",
                        help="mit --lage-bekannt: woher PICK kommt. 'steuerung' = geteachter Punkt "
                             "(bzw. vom Experten nachgefuehrt), 'm1' = vor jeder Fahrt aus der "
                             "Objekterkennung der Gruppe (bc/lokalisierung.py): Arm an die "
                             "Fotostellung, M1 lokalisiert, PICK wird gesetzt (Sicherung wie "
                             "Touch-up). Default %(default)s")
    parser.add_argument("--foto-punkt", dest="foto_punkt", default=config.LOCALIZE_POINT,
                        metavar="PUNKT",
                        help="mit --pick-quelle m1: Steuerungspunkt, an dem der Arm aus dem Bild "
                             "der Draufsichtkamera ist (Default %(default)s, wie M2)")
    parser.add_argument("--dagger", default=None, metavar="ORDNER",
                        help="mit --lage-bekannt --probegriff objekt: jede Fahrt (Policy + "
                             "Experte) mit Bildern als Episode im Aufnahmeformat nach ORDNER "
                             "schreiben, Labels vom Planer (bc/dagger.py). Export wie jede "
                             "Aufnahme, z. B. tools/export_variante.py --dagger-gewicht")
    parser.add_argument("--kamerapruefung", choices=("an", "warnen", "aus", "nur"), default="an",
                        help="vor der ersten Fahrt in der Startstellung die Kameras gegen die "
                             "Aufnahme des Modells pruefen (bc/camera_check.py): 'an' = bei "
                             "Abweichung nachfragen (ohne Antwort: nicht fahren), 'warnen' = nur "
                             "anzeigen, 'nur' = pruefen und nicht fahren (Default %(default)s)")
    parser.add_argument("--keine-live-ansicht", dest="live", action="store_false",
                        help="keine Live-Ansicht schreiben (<Protokoll>/live, bc/live.py: "
                             "Kamerabilder, TCP, Vorhersagen fuer das Fenster der GUI)")
    parser.add_argument("--out", default=None,
                        help="Ordner fuer Fahrtprotokolle (Default: <checkpoint>/rollouts/<Zeit>)")
    args = parser.parse_args()
    if args.lage_bekannt and args.replay:
        parser.error("--lage-bekannt nicht mit --replay: die eingespielten Bilder zeigen eine "
                     "andere Lage")
    if args.lage_bekannt and args.transport_geplant:
        parser.error("--lage-bekannt endet selbst mit dem Griff -- ohne --transport-geplant")
    if args.dagger and not args.experte:
        parser.error("--dagger braucht den Experten (ohne --ohne-experte)")
    if args.ablage_pose is not None:
        try:
            args.ablage_pose = [float(v) for v in str(args.ablage_pose).split(",")]
        except ValueError:
            args.ablage_pose = []
        if len(args.ablage_pose) != 7:
            parser.error("--ablage-pose: sieben Zahlen x,y,z,qw,qx,qy,qz (m)")
    if args.nur_umlegen and not (args.lage_bekannt and args.probegriff == "objekt"
                                 and args.experte and not args.dagger and not args.hold):
        parser.error("--nur-umlegen braucht --lage-bekannt --probegriff objekt und den "
                     "Experten, ohne --dagger/--hold")
    if not args.experte and not (args.lage_bekannt and args.probegriff == "objekt"):
        parser.error("--ohne-experte gilt nur mit --lage-bekannt --probegriff objekt")
    if args.glaettung is not None and not 0.0 < args.glaettung <= 1.0:
        parser.error("--glaettung muss in (0, 1] liegen (1 = aus)")
    if args.inference_steps is not None and not 1 <= args.inference_steps <= 100:
        parser.error("--inference-steps: 1 bis 100 (trainiert mit 100 Rausch-Stufen)")
    if args.dagger and not (args.lage_bekannt and args.probegriff == "objekt"):
        parser.error("--dagger braucht --lage-bekannt --probegriff objekt (der Experte "
                     "uebernimmt nach dem Probegriff)")
    if args.probe_abstand is not None and not 0.0 < args.probe_abstand <= 100.0:
        parser.error("--probe-abstand: 0 < mm <= 100")
    if args.probe_abstand is not None and args.probegriff != "objekt":
        parser.error("--probe-abstand gilt nur mit --probegriff objekt")
    if args.pick_quelle != "steuerung" and not args.lage_bekannt:
        parser.error("--pick-quelle gilt nur mit --lage-bekannt")
    if not args.hold and not args.checkpoint:
        parser.error("--checkpoint fehlt (oder --hold fuer den Verdrahtungstest)")
    args.replay_episodes = []
    if args.replay:
        if args.real_robot:
            parser.error("--replay nicht mit --real-robot: die eingespielten Bilder zeigen "
                         "nicht, was vor der Anlage liegt")
        try:
            args.replay_episodes = replay.parse_episodes(args.replay_episode, args.replay)
        except (OSError, ValueError) as exc:
            parser.error("--replay: %s" % exc)
        if not args.replay_episodes:
            parser.error("--replay-episode: keine Episode ausgewaehlt")
    args.testlagen_liste = None
    if args.testlagen is not None:
        if args.robot != "mujoco":
            parser.error("--testlagen nur mit --robot mujoco")
        from bc.sim_mujoco import testlagen as testlagen_module

        try:
            data = testlagen_module.laden(args.testlagen or testlagen_module.DATEI)
            args.testlagen_liste = testlagen_module.auswahl(data, args.testlagen_auswahl)
        except (OSError, ValueError, IndexError) as exc:
            parser.error("--testlagen: %s" % exc)
        if args.episodes is None:
            args.episodes = len(args.testlagen_liste)
    if args.episodes is None:
        args.episodes = len(args.replay_episodes) or 1
    # Siehe apps/record.py: lieber hier scheitern als nach dem Bestromen.
    try:
        substeps_for(args.servo_rate)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # Fortschritt auch in Logdateien
    args = parse_args()
    robot_kind = args.robot or ("sim" if args.sim else "neura")
    # MuJoCo-Taktiksimulation zaehlt als Simulation (SimClock, keine Hardware)
    use_sim_robot = robot_kind in ("sim", "mujoco")
    camera_mode = resolve_camera_mode(args.cameras, use_sim_robot)
    try:
        cam_cfgs = camera_configs(camera_mode, uvc_device=args.uvc_device,
                                  specs=args.camera)
    except ValueError as exc:
        raise SystemExit("--camera: %s" % exc)
    if args.replay:
        try:
            cam_cfgs = replay_configs(args.replay, args.replay_episodes[0],
                                      names=[c.name for c in cam_cfgs])
            for ep_idx in args.replay_episodes:
                replay.episode_dir(args.replay, ep_idx)
        except (OSError, IndexError) as exc:
            raise SystemExit("--replay: %s" % exc)
        print("Replay: Bilder aus %s, Episoden %s" % (args.replay, args.replay_episodes))
    # Dieselbe Belichtung/Gain wie bei der Aufnahme (bc/camera_settings.py)
    # Weissabgleich: nicht der Standard aus config, sondern wie im Modell (unten)
    cam_cfgs, notes = camera_settings_module.apply(cam_cfgs, default_wb=False)
    for note in notes:
        print("Kamera %s" % note)
    use_sim_cameras = all(c.backend in SOFT_BACKENDS for c in cam_cfgs)

    info, policy = None, None
    if args.hold:
        policy = HoldPolicy(horizon=config.POLICY_N_ACTION_STEPS)
        info = {"start_joints": None, "end_joints": None, "episode_length_max": 45,
                "inference_defaults": {}, "reference": {}, "ideal_z_min": None,
                "recording": {}}
    else:
        from bc.diffusion import DiffusionPolicyRunner, read_policy_info

        checkpoint = resolve_checkpoint(args.checkpoint)
        info = read_policy_info(checkpoint)
        rec_override = info.get("recording", {}).get("override")
        if args.override is None:
            args.override = float(rec_override) if rec_override is not None else config.DEFAULT_OVERRIDE
        # Ausfuehrungsart: Default und Pflichtwert ist die der Aufzeichnung
        # (aeltere Policies ohne Eintrag: servo_j). Ausdruecklich angegeben
        # wird sie gegen die Aufzeichnung geprueft.
        rec_exec = info.get("recording", {}).get("execution") or {}
        if args.ausfuehrung in execution_module.MODES:
            args.execution_mode = args.ausfuehrung
        else:
            args.execution_mode = rec_exec.get("mode") or execution_module.SERVO_J
        problems = check_against_recording(info, args, robot_kind, cam_cfgs)
        if args.replay:
            problems += ["Replay: %s" % p for p in replay.check_compatible(args.replay, info)]
        if problems and args.nur_umlegen:
            # die Policy faehrt nicht -- Kameras/Tempo der Aufnahme spielen keine Rolle
            print("Hinweis (nur umlegen): " + "; ".join(problems))
        elif problems:
            raise SystemExit("Policy passt nicht zu dieser Ausfuehrung:\n  - " + "\n  - ".join(problems))
    if args.override is None:
        args.override = config.DEFAULT_OVERRIDE

    if args.real_robot:
        if use_sim_robot:
            raise SystemExit("--real-robot ergibt mit dem SimRobot keinen Sinn.")
        confirm_real_robot()
    if not use_sim_cameras:
        warnings = config.check_cameras_configured(cam_cfgs)
        if warnings:
            print("\n!! KAMERA-KONFIGURATION UNBESTAETIGT:")
            for warning in warnings:
                print("   - %s" % warning)
            if ask("Trotzdem fahren? [j/N] ", "n").strip().lower() != "j":
                raise SystemExit("Abgebrochen.")

    if policy is None and args.nur_umlegen:
        # nur Startstellung und Tischhoehe aus bc_policy.json -- die Policy faehrt nicht
        policy = HoldPolicy(horizon=config.POLICY_N_ACTION_STEPS)
    if policy is None:
        print("Lade Policy %s ..." % checkpoint)
        policy = DiffusionPolicyRunner(checkpoint, device=args.device,
                                       inference_steps=args.inference_steps, seed=args.seed)
        print("  Geraet %s, trainiert %s Schritte auf %s, Kameras %s"
              % (policy.device, info["training"]["step"],
                 info["training"]["hardware"].get("gpu", info["training"]["hardware"]["device"]),
                 info["cameras"]))

    defaults = info.get("inference_defaults", {})
    replan = args.replan or defaults.get("replan_steps", config.POLICY_REPLAN_STEPS)
    decay = args.decay if args.decay is not None else defaults.get("ensemble_decay",
                                                                   config.POLICY_ENSEMBLE_DECAY)
    if args.glaettung is None:
        args.glaettung = float(defaults.get("glaettung", config.POLICY_COMMAND_LOWPASS_ALPHA))
    max_steps = args.max_steps or int(round(1.5 * info["episode_length_max"]))

    clock = SimClock() if use_sim_robot and use_sim_cameras and not args.realtime else RealClock()
    # Asynchrone Vorhersage bei echter Uhr (Befund 2026-09-17: ~77 ms je
    # Vorhersage > 66 ms Takt). Mit SimClock gibt es keine echte Latenz --
    # dort synchron und damit reproduzierbar.
    asynchronous = isinstance(clock, RealClock) and not args.sync_predict
    if args.no_ensemble:
        if asynchronous:
            raise SystemExit("--no-ensemble nur mit synchroner Vorhersage (--sync-predict)")
        executor = ChunkExecutor(policy, n_execute=replan)
    else:
        executor = ChunkEnsembler(policy, replan_steps=replan, decay=decay,
                                  asynchronous=asynchronous)
    if robot_kind == "mujoco":
        robot = open_robot("mujoco", clock=clock, seed=args.seed).connect()
        robot_info = {"robot": "mujoco", "in_simulation": True, "tool": robot.tool_name}
    elif use_sim_robot:
        robot = open_robot("sim", clock=clock, seed=args.seed).connect()
        robot_info = {"robot": "sim"}
    else:
        robot = open_robot("neura", allow_real=args.real_robot, override=args.override)
        try:
            robot.connect(power_on=True, ensure_automatic=True)
        except MotionRefused as exc:
            raise SystemExit("Abbruch vor jeder Bewegung: %s" % exc)
        robot_info = {"robot": "neura", "in_simulation": robot.in_simulation,
                      "override": args.override, "gripper_mode": robot.gripper_mode}
        print("Neura: is_robot_in_simulation()=%r, Override=%.2f, Greifer=%s"
              % (robot.in_simulation, args.override, robot.gripper_mode))

    # --hold ohne Aufzeichnung: auto wie in apps/record.py.
    if getattr(args, "execution_mode", None) is None:
        args.execution_mode = execution_module.resolve_mode(
            args.ausfuehrung or execution_module.AUTO, robot_info["robot"],
            robot_info.get("in_simulation", True))
    rec = info.get("recording") or {}
    rec_exec = rec.get("execution") or {}
    rec_planner = rec.get("planner") or {}
    # Halteregel wie in der Aufzeichnung: dort ohne reach_* (aeltere online-
    # Aufnahmen) auch hier ohne Warten; --hold ohne Aufzeichnung: config.
    if rec_exec.get("mode"):
        reach = {"reach_tol_mm": rec_exec.get("reach_tol_mm"),
                 "reach_settle_steps": rec_exec.get("reach_settle_steps")
                 or config.ONLINE_REACH_SETTLE_STEPS,
                 "reach_timeout_s": rec_exec.get("reach_timeout_s")
                 or config.ONLINE_REACH_TIMEOUT_S,
                 "dwell_steps": rec_exec.get("hold_dwell_steps") or config.GRIPPER_DWELL_STEPS}
    else:
        reach = {}
    execution = execution_module.describe(
        args.execution_mode,
        transit_speed=rec_planner.get("transit_speed_ms") or config.TRANSIT_SPEED_MS,
        ptp_speed=rec_planner.get("ptp_joint_speed_rads") or config.PTP_JOINT_SPEED_RADS,
        lead_steps=rec_exec.get("lead_steps", config.ONLINE_LEAD_STEPS),
        speed_factor=rec_exec.get("speed_factor") or config.ONLINE_SPEED_FACTOR,
        accel_factor=rec_exec.get("accel_factor") or config.ONLINE_ACCEL_FACTOR,
        **reach)
    robot_info["execution"] = execution
    if execution["mode"] == execution_module.ONLINE:
        print("Ausfuehrung: online, Vorlauf %d Takte, Tempo x%.2f, Beschl. x%.2f, %s"
              % (execution["lead_steps"], execution["speed_factor"], execution["accel_factor"],
                 "Greiferwechsel erst bei %.1f mm (hoechstens %.1f s)"
                 % (execution["reach_tol_mm"], execution["reach_timeout_s"])
                 if execution_module.reach_rule(execution) else "Greiferwechsel ohne Warten"))
    else:
        print("Ausfuehrung: servo_j %.0f Hz%s" % (
            args.servo_rate,
            " ohne Geschwindigkeit (servo_j_pos)" if execution["mode"] == execution_module.SERVO_J_POS
            else ""))

    # Fester Weissabgleich der Aufnahme (neue Datensaetze, Anwender 2026-11-17):
    # derselbe wie im Training, bei mehreren der haeufigste; "Once" nur noch
    # fuer alte Aufnahmen, die selbst "Once" hatten (Befund 2026-11-24, G2c)
    from dataclasses import replace as _replace
    rec_cams = ((info or {}).get("recording") or {}).get("camera_settings")
    for k, cfg in enumerate(cam_cfgs):
        wb = camera_settings_module.recorded_white_balance(rec_cams, cfg.name)
        note = camera_settings_module.recorded_white_balance_note(rec_cams, cfg.name)
        if note and cfg.backend == "daheng":
            print("Hinweis: %s" % note)
        if wb is not None and cfg.backend == "daheng" and not cfg.white_balance_ratios:
            cam_cfgs[k] = _replace(cfg, white_balance_ratios=wb)
            print("Kamera %s: Weissabgleich fest wie in der Aufnahme %s"
                  % (cfg.name, "/".join("%.2f" % v for v in wb)))
    try:
        captures, cam_cfgs = start_cameras(camera_mode, clock, seed=args.seed,
                                           uvc_device=args.uvc_device,
                                           specs=args.camera, cfgs=cam_cfgs)
    except Exception:
        robot.close()
        raise

    # Belichtung, Gain, Weissabgleich wie in der Aufnahme? Nur Hinweis (Analyse
    # 2026-11-11): die Bildstatistik ist mitgelernt, Abweichungen erklaeren
    # schlechte Fahrten, verbieten sie aber nicht.
    now_settings = {cap.name: cap.camera.settings() for cap in captures
                    if hasattr(getattr(cap, "camera", None), "settings")}
    for line in camera_settings_module.compare(
            (info.get("recording") or {}).get("camera_settings"), now_settings):
        print("Hinweis: %s" % line)

    if args.table_z is not None:
        table_z = args.table_z
    elif info.get("ideal_z_min") is not None:
        table_z = float(info["ideal_z_min"]) - 0.15  # Regel wie apps/record.py
    else:
        table_z = float(robot.read_state().tcp_quat[2]) - 0.3
    known, table_clearance = None, None
    if args.lage_bekannt:
        try:
            known = load_known_pose(args, info, robot, rec_planner)
        except Exception:
            for cap in captures:
                cap.stop()
            robot.close()
            raise
        table_clearance = known_pose.probe_clearance(args.probegriff, known)
        print("Lage bekannt: %s" % known.describe())
        print("Probegriff %s: Werkzeugspitze bleibt >= %.1f mm ueber dem Tisch%s"
              % (args.probegriff, 1e3 * table_clearance,
                 " (%.1f mm ueber der Objektoberkante)" % (1e3 * known.gap_m)
                 if args.probegriff == "objekt" else " -- echter Griff"))
    workspace = build_workspace(table_z, info, robot, robot_info, args, known, table_clearance)
    # Experte nach dem Probegriff (bc/known_pose.py): normaler Tischabstand,
    # er greift ja am Objekt -- der erhoehte gilt nur fuer die Policy
    expert_workspace = None
    # auch ohne Experte: der Rueckzug nach dem Probegriff braucht den normalen
    # Tischabstand (nach einem Violation-Stopp liegt der Arm unter der Probe-Ebene)
    if known is not None and args.probegriff == "objekt" and (
            args.episodes > 1 or args.dagger or not args.experte or args.nur_umlegen):
        expert_workspace = build_workspace(table_z, info, robot, robot_info, args, known,
                                           None, progress=lambda *_: None)
    start = np.asarray(info["start_joints"]) if info.get("start_joints") else None
    end = np.asarray(info["end_joints"]) if info.get("end_joints") else None
    start_gripper, end_gripper = info.get("start_gripper"), info.get("end_gripper")
    if end is not None and end_gripper is None:
        print("WARNUNG: bc_policy.json ohne end_gripper (aelterer Export) -- Ende nur "
              "ueber die Stellung erkennbar, kann zu frueh ausloesen.")
    min_steps = int(0.5 * info.get("episode_length_median", 0))

    out = Path(args.out) if args.out else (
        (Path(checkpoint) if not args.hold else Path("rollouts"))
        / "rollouts" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    out.mkdir(parents=True, exist_ok=True)
    if hasattr(policy, "warmup"):
        warm = policy.warmup(build_observation(robot, captures)[0])
        print("  Vorhersage nach Aufwaermen: %.1f ms (%d DDIM-Schritte)"
              % (1e3 * warm, policy.policy.diffusion.num_inference_steps))
    if args.glaettung < 1.0:
        print("Glaettung: Tiefpass alpha %.2f auf die Ziele (~%.1f Takte Verzug)"
              % (args.glaettung, CommandLowpass(args.glaettung).lag_steps))
    print("Fahrt: bis %d Takte, Tischhoehe %.3f m, %s, Vorhersage %s, Protokoll %s"
          % (max_steps, table_z,
             "ohne Mitteln, neu alle %d Takte" % replan if args.no_ensemble
             else "Chunks gemittelt, neu alle %d Takte, decay %.2f" % (replan, decay),
             "asynchron" if asynchronous else "synchron", out))

    if args.transport_geplant:
        if execution["mode"] == execution_module.ONLINE or end is None:
            raise SystemExit("--transport-geplant braucht servo_j und eine Endstellung in bc_policy.json")
        print("Transport geplant: Policy bis zum Griff, dann %.0f cm anheben und PTP zur Endstellung"
              % (100 * TRANSPORT_LIFT_M))

    if args.kamerapruefung != "aus":
        try:
            go = camera_check_before_run(robot, captures, info, start, start_gripper, args,
                                         use_sim_cameras, out,
                                         grasp_z=grasp_height(info, known))
        except Exception:
            if hasattr(executor, "close"):
                executor.close()
            for cap in captures:
                cap.stop()
            robot.close()
            raise
        if not go or args.kamerapruefung == "nur":
            args.episodes = 0      # Kameras pruefen, nicht fahren (Abschluss wie immer)

    # Umlegen durch den Experten (Probegriff "objekt", mehrere Fahrten).
    # Eigener Zufall, nicht --seed (Anwender 2026-11-24): mit festem Startwert
    # und je Lauf nur einer Fahrt kennt die Abdeckung nur die aktuelle Lage --
    # der Experte pendelte so zwischen zwei Stellen. Startwert steht im Protokoll.
    if args.ablage_seed is None:
        args.ablage_seed = int(np.random.SeedSequence().entropy % (2 ** 32))
    rng = np.random.default_rng(args.ablage_seed)
    if args.experte and known is not None:
        print("Ablage-Zufall des Experten: %d (--ablage-seed zum Wiederholen)" % args.ablage_seed)
    reference_pick = None if known is None else known.pick.copy()
    pick_state = {}

    # Nur umlegen (Modellvergleich, apps/vergleich.py): keine Policy -- der
    # Experte greift am PICK und legt an eine neue Lage, wie nach einer Fahrt
    umlegen = None
    if args.nur_umlegen:
        args.episodes = 0
        umlegen = relocate_only(robot, expert_workspace, known, reference_pick, start,
                                grasp_height(info, known), clock, args, rec_planner, rng,
                                pick_state)
        print("UMLEGEN: %s" % umlegen["result"])

    # PICK aus der Lokalisierung der Gruppe (bc/lokalisierung.py)
    localizer = None
    if args.pick_quelle == "m1" and args.episodes:
        try:
            localizer = make_localizer()
        except Exception as exc:
            if hasattr(executor, "close"):
                executor.close()
            for cap in captures:
                cap.stop()
            robot.close()
            raise SystemExit("--pick-quelle m1: %s" % exc)
        print("PICK-Quelle: M1-Lokalisierung, Fotostellung '%s'" % args.foto_punkt)

    # DAgger: Policy + Experte mit Bildern mitschreiben (bc/dagger.py)
    dagger_writer, mitschrieb, dagger_meta = None, None, None
    if args.dagger and args.episodes:
        dagger_cams = list(info.get("cameras") or [c.name for c in cam_cfgs])
        dagger_writer = dataset.DatasetWriter(Path(args.dagger), camera_names=dagger_cams)
        mitschrieb = dagger.Mitschrieb(dagger_cams)
        dagger_meta = dagger.recording_metadata(
            info, robot_info, {c.name: c.backend for c in cam_cfgs if c.name in dagger_cams},
            camera_settings=now_settings or None,
            sequence_file=args.ablauf or (info.get("table_spec") or {}).get("sequence_file"),
            extra={"checkpoint": None if args.hold else str(checkpoint),
                   "pick_source": args.pick_quelle})
        print("DAgger: Episoden nach %s (bisher %d)"
              % (args.dagger, len(dagger_writer._index["episodes"])))

    live = None
    if args.live and args.episodes:
        fk_fast = live_module.fast_fk(robot)
        live = live_module.LiveWriter(out / "live", fk=fk_fast)
        live.set_known(known)
        print("%s%s" % (live_module.LIVE_PREFIX, (out / "live").resolve()))
        if fk_fast is None:
            print("   Live-Ansicht ohne Vorhersage-Bahn: keine bestaetigte lokale Kinematik "
                  "(FK je Pose waere ein RPC an die Steuerung)")
        if localizer is None:
            scene_cap = next((c for c in captures if c.name == "scene"), None)
            frame = None if scene_cap is None else scene_cap.latest()
            if frame is not None:
                try:
                    live.set_scene_map(live_module.detect_scene_map(frame.image))
                except Exception as exc:
                    cached = live_module.cached_scene_map()
                    if cached:
                        live.set_scene_map(cached, remember=False)
                        print("   Live-Ansicht: Marker verdeckt (%s) -- Abbildung vom %s"
                              % (str(exc).splitlines()[0][:80], cached.get("gespeichert", "?")))
                    else:
                        print("   Live-Ansicht: Szenenkamera ohne Pfeile (Marker nicht erkannt: "
                              "%s; einmal mit PICK aus M1 fahren, dann gespeichert)"
                              % str(exc).splitlines()[0][:120])

    results = []
    sim_rows, sim_plane = [], None
    if args.testlagen_liste is not None:
        from bc.sim_mujoco import auswertung as sim_auswertung
        from bc.table import TablePlane

        sim_plane = TablePlane.from_dict(robot.welt.punkte["table"])
        print("Testlagen: %d Fahrt(en), Lagen %s"
              % (args.episodes, [l["id"] for l in args.testlagen_liste][:args.episodes]))
    try:
        for ep in range(args.episodes):
            if robot.stop_requested and getattr(robot, "in_simulation", True) is not True:
                # An der Anlage nach einem Stopp nie automatisch weiterfahren.
                answer = ask("Fahrt %d wurde gestoppt. Arbeitsraum pruefen -- naechste Fahrt? [j/N] "
                               % (ep - 1))
                if answer.strip().lower() != "j":
                    print("Beendet nach Stopp.")
                    break
            robot.clear_stop()
            if ep > 0 and hasattr(robot, "reset_program"):
                # Befund 2026-11-24: ohne stop/init_program dazwischen nahm die
                # Steuerung in Fahrt 1 die Servo-Sollwerte meist nicht an
                try:
                    robot.reset_program()
                except Exception as exc:
                    print("Fahrt %d: Programm nicht neu initialisiert (%s) -- Steuerung pruefen"
                          % (ep, exc))
                    break
            # Reset wie in der Aufzeichnung (AP 5.2): Greifer auf den Startzustand,
            # dann an die Startstellung -- sonst beginnt die Policy z. B. mit
            # geschlossenem Greifer und "glaubt", das Objekt schon zu halten.
            ep_start, ep_start_gripper, replay_arrays, replay_ep = start, start_gripper, None, None
            if args.replay:
                # Startstellung und Greifer DIESER Episode -- die Bilder beginnen dort
                replay_ep = args.replay_episodes[ep % len(args.replay_episodes)]
                replay_arrays = replay.load_arrays(args.replay, replay_ep)
                for cap in captures:
                    if hasattr(cap.camera, "select"):
                        cap.camera.select(replay_ep)
                ep_start = np.asarray(replay_arrays["observation.state"][0, :6], dtype=float)
                ep_start_gripper = float(replay_arrays["observation.state"][0, 13])
                print("Fahrt %d: Replay Episode %d (%d Takte)"
                      % (ep, replay_ep, len(replay_arrays["observation.state"])))
            lokal = None
            if localizer is not None:
                try:
                    if live is not None:
                        live.phase("Lokalisierung (Fotostellung)")
                    lokal, known = localize_pick(robot, captures, localizer, known, args, info,
                                                 rec_planner, pick_state, clock)
                    if live is not None:
                        live.set_known(known)
                        try:
                            live.set_scene_map(live_module.detect_scene_map(None, localizer))
                        except Exception as exc:
                            print("   Live-Ansicht: keine Abbildung fuer das Kamerabild (%s)" % exc)
                except Exception as exc:
                    print("Fahrt %d: Lokalisierung gescheitert -- %s" % (ep, exc))
                    if not pick_state.get("used_xy"):
                        print("Beendet: ohne Lage keine Fahrt (Teil, Marker und Fotostellung "
                              "pruefen).")
                        break
                    # Der Experte hat das Teil selbst abgelegt -- sein PICK ist bekannt
                    # (z. B. ausserhalb des M1-Bereichs zwischen den Markern abgelegt)
                    print("   weiter mit dem PICK des Experten (Teil von ihm abgelegt)")
                    lokal = {"fehler": str(exc), "pick_quelle": "experte"}
            ideal_q = None
            if mitschrieb is not None:
                mitschrieb.reset()
                try:
                    ideal_q = dagger.ideal_joints(robot, known.ideal, ep_start if ep_start is not None
                                                  else robot.read_state().joints)
                except Exception as exc:
                    print("Hinweis: DAgger-Idealbahn nicht loesbar (%s) -- Fahrt ohne Mitschrieb"
                          % exc)
            if ep_start_gripper is not None:
                robot.gripper_command(ep_start_gripper > config.GRIPPER_THRESHOLD)
            testlage = None
            if args.testlagen_liste is not None:
                # Sim-Haken: Objekt an die Testlage (Greifer ist schon offen)
                testlage = args.testlagen_liste[ep % len(args.testlagen_liste)]
                robot.objekt_fuer_griff(testlage["pick_joints"])
                print("Fahrt %d: Testlage %d -- Objekt x %.0f y %.0f mm, Gier %.0f Grad"
                      % (ep, testlage["id"], 1e3 * testlage["objekt"]["x_m"],
                         1e3 * testlage["objekt"]["y_m"], testlage["objekt"]["gier_grad"]))
            if ep_start is not None and not args.no_start_move:
                away = float(np.max(np.abs(robot.read_state().joints - ep_start)))
                if away > config.START_POSE_TOL_RAD:
                    print("Fahrt %d: an die Startstellung (%.3f rad entfernt)" % (ep, away))
                    if not move_to_joints_checked(robot, ep_start, grasp_height(info, known),
                                                  "Fahrt %d" % ep):
                        print("Beendet: Arm steht zu tief fuer die Fahrt zur Startstellung.")
                        break
            if live is not None:
                live.start_episode(ep)
            t0 = time.perf_counter()
            log = run_episode(robot, captures, executor, clock, max_steps, workspace,
                              end_joints=end, end_gripper=end_gripper, min_steps=min_steps,
                              threaded_watchdog=not isinstance(clock, SimClock),
                              servo_rate_hz=args.servo_rate, execution=execution,
                              stop_at_grasp=args.transport_geplant or known is not None,
                              on_tick=None if known is None else _deviation_text(known),
                              mitschrieb=mitschrieb if ideal_q is not None else None,
                              live=live, glaettung=args.glaettung,
                              target_lookahead=(config.PROBE_TARGET_LOOKAHEAD_STEPS
                                                if known is not None and args.probegriff == "objekt"
                                                else 0.0))
            lage = None
            if known is not None:
                lage = evaluate_known(log, known, robot, args.probegriff)
            if args.transport_geplant and log["stop_reason"] == "griff":
                transport = planned_transport(robot, workspace, end, clock,
                                              servo_rate_hz=args.servo_rate, planner=rec_planner,
                                              threaded_watchdog=not isinstance(clock, SimClock))
                print("Fahrt %d: Griff nach %d Takten, geplanter Transport %d Takte -> %s"
                      % (ep, len(log["t"]), len(transport["t"]), transport["stop_reason"]))
                log = merge_transport(log, transport, robot)
            wall = time.perf_counter() - t0
            rollout = {"tcp": np.vstack([log["tcp"], log["final_tcp"][None]]) if len(log["tcp"]) else log["final_tcp"][None],
                       "gripper_cmd": np.append(log["gripper_cmd"], log["gripper_cmd"][-1] if len(log["gripper_cmd"]) else 0.0),
                       "reached_end": log["reached_end"]}
            summary = metrics.evaluate_rollout(rollout, info.get("reference") or {})
            # Erfolg = Uebergabe (Anwender 2026-11-11): Endstellung erreicht und
            # ruhig, Greifer wie am Ende der Aufnahme (bei pick_to_station: zu).
            # Der Vergleich mit den Greifpunkten AUS DEM TRAINING passt nur bei
            # fester Objektlage -- an einer neuen Lage waere ein richtiger Griff
            # "kein Erfolg". Er bleibt als Information (success_reference).
            summary["success_reference"] = summary["success"]
            summary["success"] = bool(log["reached_end"])
            if lage is not None:
                # Policy-Test: Greifpunkt gegen die BEKANNTE Lage (am Griff, beim
                # Probegriff vorhergesagt). Erfolg (Anwender 2026-11-25) =
                # vorgesehenes Ende und Griffpruefung ohne Backenkontakt
                # (bc/known_pose.grasp_check); der alte 10-mm-Test bleibt als
                # Information (success_xy).
                s = lage["summary"]
                at = s["at_grasp"] or s["predicted"] or s["at_stop"] or {}
                check = s.get("grasp_check")
                summary["grasp_error_m"] = at.get("xy_m")
                ended = expected_test_stop(log["stop_reason"], args.probegriff)
                summary["success_xy"] = bool(ended and at.get("xy_m") is not None
                                             and at["xy_m"] <= config.KNOWN_POSE_SUCCESS_XY_M)
                summary["grasp_check"] = check
                summary["grasp_level"] = (known_pose.GRASP_FAIL if not ended or not check
                                          else check["stufe"])
                summary["success"] = summary["grasp_level"] != known_pose.GRASP_FAIL
            predict = log["predict_s"][np.isfinite(log["predict_s"])] if len(log["predict_s"]) else np.array([])
            delays = log["delay_steps"][np.isfinite(log["delay_steps"])] if len(log["delay_steps"]) else np.array([])
            summary.update(
                episode=ep,
                stop_reason=log["stop_reason"],
                pacer_overruns=int(log["pacer_overruns"]),
                guard_rejections=int(log["guard_rejections"]),
                limiter_clamped_steps=int(log["limiter_clamped"]),
                predictions=int(len(predict)),
                asynchronous=asynchronous,
                chunk_delay_steps_max=float(delays.max()) if len(delays) else None,
                predictions_skipped_busy=int(getattr(executor, "skipped", 0)),
                predict_ms_median=float(np.median(predict) * 1e3) if len(predict) else None,
                predict_ms_p95=float(np.percentile(predict, 95) * 1e3) if len(predict) else None,
                ensemble_spread_p95_rad=float(np.percentile(log["ensemble_spread"], 95)) if len(log["ensemble_spread"]) else None,
                reach_wait_s=log["reach_wait_s"],
                reach_waits=log["reach_waits"],
                wall_s=wall,
                **robot_info,
            )
            if testlage is not None:
                sim = sim_auswertung.bewerte(log, testlage, robot.welt, sim_plane)
                summary["sim"] = sim
                sim_rows.append(sim)
                print("   %s" % sim_auswertung.zeile(sim))
            if replay_arrays is not None:
                cmp = replay.compare_rollout(log, replay_arrays)
                summary["replay"] = dict(root=str(args.replay), episode=replay_ep, **cmp)
            if lage is not None:
                summary["lage"] = lage["summary"]
            if lokal is not None:
                summary["lokalisierung"] = lokal
            results.append(summary)
            arrays_out = {k: v for k, v in log.items() if isinstance(v, np.ndarray)}
            # jede rohe Vorhersage (Anwender 2026-11-17: springt die Drehung?)
            history = list(getattr(executor, "history", None) or [])
            if history and len({c.shape for _, c in history}) == 1:
                arrays_out["pred_step"] = np.array([s for s, _ in history], dtype=int)
                arrays_out["pred_chunk"] = np.stack([c for _, c in history]).astype(np.float32)
            if lage is not None:
                # je Takt (gemessen, wie log["tcp"] plus Schlusszustand)
                arrays_out.update({"lage_" + k: v for k, v in lage["rows"].items()})
                arrays_out["lage_pick"] = np.asarray(known.pick, dtype=float)
            np.savez_compressed(out / ("rollout_%03d.npz" % ep), **arrays_out)
            print("Fahrt %d: %s -- %d Takte, Greifpunkt %s, Ende %s, Bahn p95 %s, %s, Vorhersage %s ms, "
                  "Overruns %d, gekappt %d"
                  % (ep, "ERFOLG" if summary["success"] else "kein Erfolg", summary["steps"],
                     _mm(summary.get("grasp_error_m")), _mm(summary.get("end_error_m")),
                     _mm(summary.get("path_dev_p95_m")), _one_field(log["stop_reason"]),
                     "%.1f" % summary["predict_ms_median"] if summary["predict_ms_median"] else "-",
                     summary["pacer_overruns"], summary["limiter_clamped_steps"]))
            for halt in log["reach_waits"]:
                print("   %s" % execution_module.reach_line(halt))
            if "replay" in summary:
                print("   %s" % replay.format_rollout_comparison(summary["replay"]))
            if lage is not None:
                print(known_pose.result_line(lage["summary"]))
                print(known_pose.check_line(lage["summary"].get("grasp_check"),
                                            (lage["summary"].get("grasp_check") or {}).get("quelle")))
                expert, stop_here = None, False
                if args.probegriff == "objekt":
                    if str(log["stop_reason"]).startswith("arm steht"):
                        # Not-Aus: nie automatisch weiterfahren, auch kein Experte
                        retreat = ("keiner -- Arm steht (Not-Aus am Handbediengeraet?), "
                                   "Anlage pruefen")
                    elif not (expected_test_stop(log["stop_reason"], "objekt")
                              or log["stop_reason"] == "max_steps"):
                        retreat = ("keiner -- Stopp nicht vom Test (%s), Arbeitsraum pruefen"
                                   % log["stop_reason"])
                    elif not args.experte:
                        # Anwender 2026-11-19: nur anfliegen und messen, nicht greifen --
                        # Vorhersage steht schon in lage["summary"]["predicted"]
                        retreat = retreat_after_test(robot, expert_workspace, log,
                                                     ep_start if ep_start is not None
                                                     else np.asarray(log["joints"][0]),
                                                     clock, args, rec_planner, probe="objekt")
                        if retreat == "am Start":
                            retreat = "ohne Experte: angehoben, am Start (Objekt unberuehrt)"
                    elif expert_workspace is None:
                        retreat = ("stehen geblieben -- Werkzeug %.0f mm ueber dem Objekt, "
                                   "Spiel pruefen" % (1e3 * known.gap_m))
                    else:
                        back_to = ep_start if ep_start is not None else np.asarray(log["joints"][0])
                        if probe_violation(log["stop_reason"]):
                            print("   Violation-Stopp an der Probegriff-Ebene: Experte hebt "
                                  "zuerst senkrecht an")
                        if live is not None:
                            live.phase("Experte korrigiert und legt um")
                        expert = expert_after_probe(
                            robot, expert_workspace, known, reference_pick, back_to, clock, args,
                            rec_planner, rng, pick_state, captures=captures,
                            mitschrieb=mitschrieb if ideal_q is not None else None)
                        print(known_pose.correction_line(expert["correction"]))
                        retreat = expert["result"]
                        summary["experte"] = {k: expert.get(k) for k in
                                              ("correction", "result", "new_pick", "placed_xy")}
                        if expert.get("log") is not None:
                            np.savez_compressed(
                                out / ("experte_%03d.npz" % ep),
                                **{k: v for k, v in expert["log"].items()
                                   if isinstance(v, np.ndarray)})
                        stop_here = expert.get("new_pick") is None
                else:
                    retreat = retreat_after_test(robot, workspace, log, ep_start, clock, args,
                                                 rec_planner)
                    if lage["summary"]["at_grasp"] is not None:
                        print("   Hinweis: Objekt wurde gegriffen und wieder abgelegt -- Lage kann "
                              "sich verschoben haben, PICK vor der naechsten Fahrt pruefen.")
                print("   Danach: %s" % retreat)
                summary["rueckzug"] = retreat
                append_csv(out / "policy_test.csv", known_pose.CSV_COLUMNS,
                           known_pose.csv_row(ep, log["stop_reason"], lage["summary"],
                                              None if expert is None else expert["correction"],
                                              retreat))
                if dagger_writer is not None and ideal_q is not None:
                    summary["dagger"] = write_dagger_episode(
                        dagger_writer, mitschrieb, known, ideal_q, expert, log, lage,
                        dagger_meta, ep, lokal)
                if stop_here:
                    print("Beendet: Experte konnte nicht umlegen -- Objekt und PICK pruefen.")
                    break
                if expert is not None and ep + 1 < args.episodes:
                    known = load_known_pose(args, info, robot, rec_planner)   # neuer PICK
                    print("Lage bekannt: %s" % known.describe())
                    if live is not None:
                        live.set_known(known)
    finally:
        if live is not None:
            live.close()
        if hasattr(executor, "close"):
            executor.close()
        for cap in captures:
            cap.stop()
        robot.close()

    report = {
        "checkpoint": None if args.hold else str(checkpoint),
        "created": datetime.now().isoformat(timespec="seconds"),
        "args": vars(args),
        "robot": robot_info,
        # was die Kameras wirklich eingestellt hatten (Befund 2026-11-24:
        # Weissabgleich der Fahrten war nicht nachvollziehbar)
        "camera_settings": now_settings or None,
        "replan_steps": replan,
        "ensemble_decay": None if args.no_ensemble else decay,
        "umlegen": umlegen,
        "episodes": results,
        "success_rate": float(np.mean([r["success"] for r in results])) if results else None,
    }
    if sim_rows:
        report["sim_zusammenfassung"] = sim_auswertung.zusammenfassen(sim_rows)
        (out / "sim_auswertung.json").write_text(json.dumps(
            {"zusammenfassung": report["sim_zusammenfassung"], "fahrten": sim_rows,
             "testlagen": args.testlagen or "bc/sim_mujoco/testlagen_v1.json",
             "checkpoint": report["checkpoint"]}, indent=1, ensure_ascii=False), encoding="utf-8")
        keys = [k for k in sim_rows[0] if not isinstance(sim_rows[0][k], (list, dict))]
        with open(out / "sim_auswertung.csv", "w", encoding="utf-8") as fh:
            fh.write(";".join(keys) + "\n")
            for r in sim_rows:
                fh.write(";".join("" if r.get(k) is None else str(r.get(k)) for k in keys) + "\n")
        z = report["sim_zusammenfassung"]
        print("\nSim-Auswertung: Griff %d/%d, Greif-xy median %s mm, Gier |median| %s Grad, "
              "Tisch min median %s mm, Abbrueche %s -> %s"
              % (round(z["griff_quote"] * z["fahrten"]), z["fahrten"], z["greif_xy_mm_median"],
                 z["gier_fehler_grad_median_abs"], z["tisch_min_mm_median"], z["abbruch"],
                 out / "sim_auswertung.json"))
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if results:
        print("\nErfolg %d/%d (Uebergabepunkt erreicht, Greifer wie aufgezeichnet) -> %s"
              % (sum(r["success"] for r in results), len(results), out / "summary.json"))


def _one_field(text):
    """Abbruchgrund als EIN Feld der Ergebniszeile: die Oberflaeche und der
    Orchestrator (bc/gui/operation.py) trennen die Felder an Kommas."""
    return str(text).replace(",", ";")


def _mm(value):
    return "-" if value is None else "%.1f mm" % (1e3 * value)


if __name__ == "__main__":
    main()
