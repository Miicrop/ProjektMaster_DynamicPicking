"""Step-by-step checks for the Neura robot (see m2_robot_control/ANLEITUNG_NEURA.md).

    python -m m2_robot_control.robot_check info          # read-only: name, version, mode, pose
    python -m m2_robot_control.robot_check pose NAME     # print current TCP pose as config line
    python -m m2_robot_control.robot_check home          # MOVES: go to the Home point
    python -m m2_robot_control.robot_check gripper       # open / close / open the gripper
    python -m m2_robot_control.robot_check pick-test     # MOVES: pick + place at the inspection pose

Add --sim to run against the built-in fake controller instead of the real robot.
"""
from __future__ import annotations

import argparse
import logging
import time

from common.config import load_config, robot_target
from m2_robot_control.fake_neura_server import FakeNeuraServer
from m2_robot_control.robot import NeuraRobot, load_neurapy_client


def _fmt(p) -> str:
    return (f"x={p.x_mm:.1f} y={p.y_mm:.1f} z={p.z_mm:.1f} mm  "
            f"rx={p.rx_deg:.1f} ry={p.ry_deg:.1f} rz={p.rz_deg:.1f} deg")


def _confirm(msg: str) -> bool:
    return input(f"{msg} Hand am Not-Halt? [j/N] ").strip().lower() in ("j", "y", "ja", "yes")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["info", "pose", "home", "gripper", "pick-test"])
    ap.add_argument("name", nargs="?", default="new_pose", help="pose name for 'pose'")
    ap.add_argument("--host", help="override robot.host from config")
    ap.add_argument("--sim", action="store_true", help="use the fake controller")
    ap.add_argument("--yes", action="store_true", help="skip the safety confirmation")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    cfg = load_config()
    factory = None
    if args.sim:
        server = FakeNeuraServer("127.0.0.1", 0).start_background()
        factory = lambda host: load_neurapy_client("127.0.0.1", server.port)  # noqa: E731
        print(f"[sim] fake controller on port {server.port}")
    if args.host:
        cfg["robot"]["host"] = args.host

    robot = NeuraRobot(cfg, client_factory=factory)
    r = robot.open_client()

    if args.command == "info":
        print(f"robot      : {r.robot_name}  dof={r.dof}  server version={r.version}")
        print(f"teach mode : {r.is_robot_in_teach_mode()}")
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

    if not args.sim and not args.yes and not _confirm(f"Roboter {cfg['robot']['host']} bewegt sich!"):
        print("abgebrochen")
        return

    robot.connect()
    try:
        if args.command == "home":
            robot.home()
        elif args.command == "gripper":
            for action in ("release", "grasp", "release"):
                print(action)
                getattr(r, action)()
                time.sleep(1.5)
        elif args.command == "pick-test":
            # grasp at the inspection pose and put it back: tests the full sequence
            target = robot_target(cfg, "inspection")
            robot.home()
            robot.pick(target)
            robot.place(target)
            robot.home()
        print(f"done, tcp pose: {_fmt(robot.current_pose())}")
    finally:
        robot.disconnect()


if __name__ == "__main__":
    main()
