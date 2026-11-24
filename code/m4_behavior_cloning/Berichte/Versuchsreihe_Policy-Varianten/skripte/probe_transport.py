"""Probelauf planned_transport() am SimRobot (ohne VM, ohne Policy).

Startet in einer Greifstellung aus der Aufnahme 11.11. (PICK einer Testlage),
plant Dwell + 5 cm anheben + PTP zur Station (PRE_PLACE) und faehrt das im
SimRobot. Prueft: erreicht die Station, TCP steigt zuerst senkrecht, nie unter
die Startpose, Gelenktempo unter dem ServoGuard.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps"))
import _bootstrap  # noqa: F401,E402
import numpy as np  # noqa: E402

import infer  # noqa: E402
from bc import config  # noqa: E402
from bc.adapters import open_robot  # noqa: E402
from bc.clock import SimClock  # noqa: E402
from bc.collision import default_workspace  # noqa: E402

meta = json.loads((ROOT / "data/2026-11-11/ep_00007/meta.json").read_text(encoding="utf-8"))["metadata"]
pick_q = np.asarray(meta["points"]["PICK"]["joints"], dtype=float)
station = np.asarray(meta["points"]["PRE_PLACE"]["joints"], dtype=float)

clock = SimClock()
robot = open_robot("sim", clock=clock)
robot.connect()
robot.move_to_joints(pick_q)
p_start = np.asarray(robot.fk(pick_q), dtype=float)
ws = default_workspace(table_height_m=p_start[2] - 0.15)
log = infer.planned_transport(robot, ws, station, clock, threaded_watchdog=False,
                              planner={"transit_speed_ms": 0.15, "approach_speed_ms": 0.05,
                                       "ptp_joint_speed_rads": 0.5})
tcp = log["tcp"]
q = log["joints"]
print("Ende:", log["stop_reason"], "Takte", len(tcp), "geplant", log["steps_planned"])
print("Abstand Endstellung max %.4f rad" % float(np.abs(q[-1] - station).max()))
dz = tcp[:, 2] - p_start[2]
dxy = np.linalg.norm(tcp[:, :2] - p_start[:2], axis=1)
k = int(np.argmax(dz >= 0.045))
print("bis 45 mm Hoehe: %d Takte, seitlich dabei max %.1f mm" % (k, 1e3 * dxy[:k + 1].max()))
print("tiefster Punkt relativ Start %.1f mm" % (1e3 * dz.min()))
speed = np.abs(np.diff(q, axis=0)).max() * config.CONTROL_RATE_HZ
print("Gelenktempo max %.2f rad/s (ServoGuard %.2f)" % (speed, config.SERVO_MAX_JOINT_SPEED_RADS))
