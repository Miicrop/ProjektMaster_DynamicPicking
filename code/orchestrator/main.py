"""Automatic cycle from the command line (the GUI offers the same in the tab "Ablauf").

    python -m orchestrator --mock --cycles 5                    # everything mocked
    python -m orchestrator --replay --cycles 4                  # M1/M3 on the test photos, robot mocked
    python -m orchestrator --replay --sim-robot --save-images   # ... NeuraRobot against the fake controller
    python -m orchestrator --replay --vm-robot                  # ... NeuraRobot against the Neura VM
    python -m orchestrator --replay --save-steps                # + intermediate images (masks, ROIs) for docs
    python -m orchestrator --detector camera --robot real --inspector camera --cycles 0   # until Ctrl+C
    python -m orchestrator                                      # kinds from config/system.yaml

Every cycle is appended to logs/cycles_<date>.csv.
"""
from __future__ import annotations

import argparse
import logging

from common.config import DEFAULT_CONFIG, load_config
from orchestrator import logbook
from orchestrator.factory import (DETECTOR_KINDS, INSPECTOR_KINDS, ROBOT_KINDS, build_detector,
                                  build_inspector, build_robot)
from orchestrator.state_machine import Orchestrator, State


def main() -> None:
    ap = argparse.ArgumentParser(description="Dynamic grasping + inspection cell",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--mock", action="store_true", help="use mocks for all modules")
    ap.add_argument("--replay", action="store_true", help="M1/M3 on the test photos, robot mocked")
    ap.add_argument("--sim-robot", action="store_true", help="NeuraRobot against the fake controller")
    ap.add_argument("--vm-robot", action="store_true", help="NeuraRobot against the Neura VM (robot.vm_host)")
    ap.add_argument("--detector", choices=DETECTOR_KINDS)
    ap.add_argument("--robot", choices=ROBOT_KINDS)
    ap.add_argument("--inspector", choices=INSPECTOR_KINDS)
    ap.add_argument("--cycles", type=int, default=1, help="0 = run until Ctrl+C")
    ap.add_argument("--save-images", action="store_true", help="save M1/M3 debug images per cycle")
    ap.add_argument("--save-steps", action="store_true",
                    help="additionally save the M1/M3 intermediate images (masks, ROIs, ...); implies --save-images")
    args = ap.parse_args()

    cfg = load_config(args.config)
    logging.basicConfig(level=cfg["logging"]["level"],
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    kinds = dict(cfg["implementations"])
    kinds = {"detector": kinds["detector"], "robot": kinds["robot"], "inspector": kinds["inspector"]}
    if args.mock:
        kinds = {k: "mock" for k in kinds}
    if args.replay:
        kinds.update(detector="replay", inspector="replay", robot="mock")
    if args.sim_robot:
        kinds["robot"] = "sim"
    if args.vm_robot:
        kinds["robot"] = "vm"
    for k in kinds:
        if getattr(args, k):
            kinds[k] = getattr(args, k)
    print(f"detector={kinds['detector']} robot={kinds['robot']} inspector={kinds['inspector']}")

    robot = build_robot(cfg, kinds["robot"])
    detector = build_detector(cfg, kinds["detector"])
    inspector = build_inspector(cfg, kinds["inspector"])
    if args.save_steps:
        args.save_images = True
        for module in (detector, inspector):
            if hasattr(module, "trace_steps"):
                module.trace_steps = True
    orch = Orchestrator(cfg, detector, robot, inspector)

    robot.connect()
    n = 0
    try:
        robot.home()
        while args.cycles == 0 or n < args.cycles:
            n += 1
            result = orch.run_cycle()
            images = logbook.save_images(cfg, result, detector, inspector) if args.save_images else None
            csv_file = logbook.append_csv(cfg, result, images)
            verdict = ("GOOD" if result.inspection and result.inspection.is_good
                       else "BAD" if result.inspection else "-")
            pose = (f" | part at ({result.pose.x_mm:.0f}, {result.pose.y_mm:.0f}) mm, "
                    f"{result.pose.theta_deg:.0f} deg" if result.pose else "")
            print(f"cycle {result.cycle_id}: {'OK' if result.ok else 'ERROR ' + result.error}{pose}"
                  f" | result {verdict}"
                  + (f" ({result.inspection.serial_number})" if result.inspection else "")
                  + (f" | reasons: {'; '.join(result.inspection.reasons)}"
                     if result.inspection and result.inspection.reasons else "")
                  + (f" | images: {images}" if images else ""))
            if orch.state is State.ERROR:
                break
    except KeyboardInterrupt:
        print("stopped by user")
        robot.stop()
    finally:
        robot.disconnect()
        detector.close()
        inspector.close()
    print(f"log: {csv_file if n else '-'}")


if __name__ == "__main__":
    main()
