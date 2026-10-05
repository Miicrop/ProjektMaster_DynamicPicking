"""Step-by-step checks for the Neura robot (see m2_robot_control/ANLEITUNG_NEURA.md).

    python -m m2_robot_control.robot_check info          # read-only: name, version, mode, pose
    python -m m2_robot_control.robot_check pose NAME     # print current TCP pose as config line
    python -m m2_robot_control.robot_check home          # MOVES: go to the Home point
    python -m m2_robot_control.robot_check gripper       # open / close / open the gripper
    python -m m2_robot_control.robot_check pick-test     # MOVES: pick + place at the inspection pose
    python -m m2_robot_control.robot_check axes          # MOVES: guided +/-X, Y, Z, rz steps from Home
    python -m m2_robot_control.robot_check jog z 20      # MOVES: one relative step (x|y|z mm, rz deg)
    python -m m2_robot_control.robot_check calib         # read-only: teach marker centres -> workspace_to_robot
    python -m m2_robot_control.robot_check point         # MOVES: detect part (M1), hover above it, no grasp

Add --sim to run against the built-in fake controller, or --vm to run against the official Neura
simulation (VirtualBox VM at robot.vm_host) instead of the real robot.
"""
from __future__ import annotations

import argparse
import csv
import logging
import time

import numpy as np

from common.config import load_config, robot_target
from common.transforms import fit_workspace_to_robot
from m2_robot_control.fake_neura_server import FakeNeuraServer
from m2_robot_control.robot import NeuraRobot, _wrap_deg, load_neurapy_client

JOG_AXES = {"x": "dx_mm", "y": "dy_mm", "z": "dz_mm", "rz": "drz_deg"}


def _fmt(p) -> str:
    return (f"x={p.x_mm:.1f} y={p.y_mm:.1f} z={p.z_mm:.1f} mm  "
            f"rx={p.rx_deg:.1f} ry={p.ry_deg:.1f} rz={p.rz_deg:.1f} deg")


def _confirm(msg: str) -> bool:
    return input(f"{msg} Hand am Not-Halt? [j/N] ").strip().lower() in ("j", "y", "ja", "yes")


def _jog(robot: NeuraRobot, axis: str, value: float) -> str:
    """One relative step; returns the measured change as text."""
    before = robot.current_pose()
    robot.jog(**{JOG_AXES[axis]: value})
    after = robot.current_pose()
    return (f"gemessen: dx={after.x_mm - before.x_mm:+.1f} dy={after.y_mm - before.y_mm:+.1f} "
            f"dz={after.z_mm - before.z_mm:+.1f} mm  drz={_wrap_deg(after.rz_deg - before.rz_deg):+.1f} deg")


def _axes_test(robot: NeuraRobot, step_mm: float, step_deg: float, ask: bool) -> None:
    """From Home: each axis a small step in + direction and back. The user notes the observed direction."""
    seq = [("z", step_mm, "nach OBEN (weg vom Tisch)"),
           ("x", step_mm, "Richtung +X der Basis"),
           ("y", step_mm, "Richtung +Y der Basis"),
           ("rz", step_deg, "Greifer dreht um die senkrechte Achse (+rz)")]
    notes: list[tuple[str, str]] = []
    robot.home()
    print(f"Home erreicht: {_fmt(robot.current_pose())}\n")
    for axis, value, expect in seq:
        unit = "deg" if axis == "rz" else "mm"
        print(f"--- {axis.upper()} {value:+.0f} {unit}: {expect}")
        if ask:
            k = input("  Enter = fahren, s = ueberspringen, q = beenden: ").strip().lower()
            if k == "q":
                break
            if k == "s":
                continue
        print("  " + _jog(robot, axis, value))
        note = input("  Beobachtung (z. B. 'zum Fenster', 'im Uhrzeigersinn von oben'): ").strip() if ask else ""
        notes.append((f"+{axis.upper()}", note or "-"))
        print("  zurueck: " + _jog(robot, axis, -value))
    robot.home()
    print("\n=== Achsentest Protokoll (in ANLEITUNG_NEURA.md / Kalibrierung uebernehmen) ===")
    for axis, note in notes:
        print(f"  {axis:4s} -> {note}")


def _calibrate(robot: NeuraRobot, cfg: dict) -> None:
    """Read the TCP pose at each marker centre and fit workspace -> robot base (no motion)."""
    markers = cfg["workspace"]["markers_mm"]
    ws, rb, zs, ids = [], [], [], []
    print("Greiferspitze (TCP) nacheinander mittig auf die Marker setzen (Pendant oder 'robot_check jog'"
          " in einem zweiten Terminal). Die Spitze soll den Tisch gerade beruehren.\n")
    for mid in sorted(markers, key=int):
        k = input(f"Marker {mid} (Arbeitsraum {markers[mid][0]:.1f}, {markers[mid][1]:.1f} mm): "
                  "Enter = uebernehmen, s = ueberspringen, q = abbrechen: ").strip().lower()
        if k == "q":
            return
        if k == "s":
            continue
        p = robot.current_pose()
        ws.append(markers[mid][:2])
        rb.append((p.x_mm, p.y_mm))
        zs.append(p.z_mm)
        ids.append(mid)
        print(f"  -> Basis x={p.x_mm:.1f} y={p.y_mm:.1f} z={p.z_mm:.1f} mm")
    if len(ws) < 3:
        print("Mindestens 3 Marker noetig - nichts berechnet.")
        return
    rot, t, res = fit_workspace_to_robot(ws, rb)
    rms = float(np.sqrt(np.mean(res ** 2)))
    print("\n=== Restfehler (Abstand gemessen <-> Modell) ===")
    for mid, r in zip(ids, res):
        print(f"  Marker {mid}: {r:.1f} mm")
    print(f"  RMS: {rms:.1f} mm")
    if rms > 3.0:
        print("  WARNUNG: RMS > 3 mm - Marker-IDs vertauscht, markers_mm falsch gemessen oder TCP nicht mittig?")
    print("\n=== In config/system.yaml uebernehmen ===")
    print("workspace_to_robot:")
    print(f"  rotation_deg: {rot:.2f}")
    print(f"  translation_mm: [{t[0]:.1f}, {t[1]:.1f}]")
    print(f"  table_z_mm: {float(np.mean(zs)):.1f}")
    print("\nHinweis: gilt nur, wenn der TCP-Versatz des Tools (robot.tool_name) stimmt.")


POINT_FIELDS = ["time", "detector", "x_ws_mm", "y_ws_mm", "theta_ws_deg", "x_mm", "y_mm", "theta_deg",
                "confidence", "target_x_mm", "target_y_mm", "target_z_mm", "target_rz_deg", "hover_mm",
                "dx_mm", "dy_mm", "note"]


def _log_point(cfg: dict, row: dict) -> None:
    from orchestrator.logbook import log_dir
    f = log_dir(cfg) / "point_tests.csv"
    new = not f.exists()
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=POINT_FIELDS, delimiter=";")
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"protokolliert in {f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["info", "pose", "home", "gripper", "pick-test", "axes", "jog",
                                        "calib", "point"])
    ap.add_argument("name", nargs="?", default="new_pose", help="pose name for 'pose', axis for 'jog'")
    ap.add_argument("value", nargs="?", type=float, help="step for 'jog' (mm, rz in deg)")
    ap.add_argument("--step", type=float, default=50.0, help="step for 'axes' in mm (default 50)")
    ap.add_argument("--step-deg", type=float, default=20.0, help="rz step for 'axes' in deg (default 20)")
    ap.add_argument("--detector", default="camera", help="M1 source for 'point': camera | replay (test photos)")
    ap.add_argument("--hover", type=float, default=30.0, help="height above the grasp pose for 'point' in mm")
    ap.add_argument("--host", help="override robot.host from config")
    ap.add_argument("--sim", action="store_true", help="use the fake controller")
    ap.add_argument("--vm", action="store_true", help="use the Neura VM (robot.vm_host)")
    ap.add_argument("--yes", action="store_true", help="skip the safety confirmation")
    args = ap.parse_args()
    if args.command == "jog" and (args.name not in JOG_AXES or args.value is None):
        ap.error("jog needs an axis (x, y, z, rz) and a step, e.g. 'jog z 20'")

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    cfg = load_config()
    factory = None
    if args.sim:
        server = FakeNeuraServer("127.0.0.1", 0).start_background()
        factory = lambda host: load_neurapy_client("127.0.0.1", server.port)  # noqa: E731
        print(f"[sim] fake controller on port {server.port}")
    if args.vm:
        cfg["robot"]["host"] = cfg["robot"]["vm_host"]
        print(f"[vm] Neura simulation at {cfg['robot']['host']}")
    if args.host:
        cfg["robot"]["host"] = args.host

    robot = NeuraRobot(cfg, client_factory=factory)
    r = robot.open_client()

    if args.command == "info":
        print(f"robot      : {r.robot_name}  dof={r.dof}  server version={r.version}")
        print(f"teach mode : {r.is_robot_in_teach_mode()}")
        name, off = robot.tool()
        print(f"tool       : {name}  TCP offset from flange = {[round(v, 1) for v in off]} mm"
              f"  (config: {cfg['robot'].get('tool_name')} {cfg['robot'].get('tool_tcp_mm')} mm)")
        print(f"tcp pose   : {_fmt(robot.current_pose())}")
        print(f"joints/rad : {[round(j, 4) for j in r.get_current_joint_angles()]}")
        print(f"points     : {r.get_point_names()}")
        print(f"errors     : {r.get_errors()}")
        return

    if args.command == "pose":
        p = robot.current_pose()
        print(f"    {args.name}: [{p.x_mm:.1f}, {p.y_mm:.1f}, {p.z_mm:.1f}, "
              f"{p.rx_deg:.1f}, {p.ry_deg:.1f}, {p.rz_deg:.1f}]")
        return

    if args.command == "calib":
        _calibrate(robot, cfg)
        return

    point = None
    if args.command == "point":   # detect first (no motion), then ask for confirmation
        from orchestrator.factory import build_detector
        detector = build_detector(cfg, args.detector)
        try:
            pose = detector.detect()
        finally:
            detector.close()
        if pose is None:
            print("Kein Bauteil erkannt - abgebrochen")
            return
        ws = getattr(detector, "last_result", None)
        print(f"Bauteil (Basis-KS): x={pose.x_mm:.1f} y={pose.y_mm:.1f} mm  theta={pose.theta_deg:.1f} deg"
              f"  confidence={pose.confidence:.1f}")
        if pose.confidence < 1.0:
            print("WARNUNG: Fase nicht gefunden - Winkel nur bis auf 180 deg eindeutig")
        point = (pose, ws)

    if not (args.sim or args.vm) and not args.yes and not _confirm(f"Roboter {cfg['robot']['host']} bewegt sich!"):
        print("abgebrochen")
        return

    robot.connect()
    try:
        if args.command == "home":
            robot.home()
        elif args.command == "gripper":
            for close in (False, True, False):
                print("grasp" if close else "release")
                robot.gripper(close=close)
                time.sleep(1.5)
        elif args.command == "pick-test":
            # grasp at the inspection pose and put it back: tests the full sequence
            target = robot_target(cfg, "inspection")
            robot.home()
            robot.pick(target)
            robot.place(target)
            robot.home()
        elif args.command == "axes":
            _axes_test(robot, args.step, args.step_deg, ask=not args.yes)
        elif args.command == "jog":
            print(_jog(robot, args.name, args.value))
        elif args.command == "point":
            pose, ws = point
            robot.home()
            t = robot.point_at(pose, args.hover)
            print(f"Greifer steht {args.hover:.0f} mm ueber der Greifposition: {_fmt(t)}")
            row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "detector": args.detector,
                   "x_ws_mm": f"{ws.x_ws_mm:.1f}" if ws else "", "y_ws_mm": f"{ws.y_ws_mm:.1f}" if ws else "",
                   "theta_ws_deg": f"{ws.theta_ws_deg:.1f}" if ws else "",
                   "x_mm": f"{pose.x_mm:.1f}", "y_mm": f"{pose.y_mm:.1f}", "theta_deg": f"{pose.theta_deg:.1f}",
                   "confidence": pose.confidence, "target_x_mm": f"{t.x_mm:.1f}", "target_y_mm": f"{t.y_mm:.1f}",
                   "target_z_mm": f"{t.z_mm:.1f}", "target_rz_deg": f"{t.rz_deg:.1f}",
                   "hover_mm": args.hover, "dx_mm": "", "dy_mm": "", "note": ""}
            if not args.yes:
                m = input("Versatz Bauteilmitte minus Greifermitte in Richtung Basis +X/+Y, 'dx dy' in mm "
                          "(Enter = ueberspringen): ").split()
                try:
                    dx, dy = (float(v.replace(",", ".")) for v in m)
                    row["dx_mm"], row["dy_mm"] = f"{dx:.1f}", f"{dy:.1f}"
                except ValueError:
                    print("  kein Versatz gespeichert")
                row["note"] = input("Notiz (z. B. 'Finger quer zur kurzen Seite ok'): ").strip()
            _log_point(cfg, row)
            robot.retreat(pose, args.hover)
            robot.home()
        print(f"done, tcp pose: {_fmt(robot.current_pose())}")
    finally:
        robot.disconnect()


if __name__ == "__main__":
    main()
