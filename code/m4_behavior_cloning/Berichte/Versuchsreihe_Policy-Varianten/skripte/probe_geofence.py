"""Warum stoppt der Geofence der neuen Policies in der VM im ersten Takt?

Verbindet mit der VM (ohne Bewegung), setzt den Tool-Versatz wie
stufe2_vm.py, baut das Kollisionsmodell wie apps/infer.py und prueft die
aktuelle Stellung sowie die Start-/Greifstellungen einiger Testepisoden.

Aufruf: probe_geofence.py <policy-ordner> [episoden ...]
"""
import os
import sys
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "tools"))
import _bootstrap  # noqa: F401,E402
import infer  # noqa: E402
from bc import config, geometry, replay  # noqa: E402
from bc.adapters import open_robot  # noqa: E402
from bc.collision import default_workspace  # noqa: E402

policy = Path(sys.argv[1])
eps = [int(e) for e in sys.argv[2:]] or [6, 13, 57]
data = "data/2026-11-11"
info = json.loads((policy / "bc_policy.json").read_text(encoding="utf-8"))

robot = open_robot("neura")
robot.connect(power_on=False)
assert robot.in_simulation is True
states0 = np.asarray(replay.load_arrays(data, replay.usable_episodes(data)[0])["observation.state"], float)
flange = robot._pose_from_chain(robot._chain, states0[0, :6], None)
T_f = np.eye(4); T_f[:3, :3] = geometry.quat_to_matrix(flange[3:7]); T_f[:3, 3] = flange[:3]
T_r = np.eye(4); T_r[:3, :3] = geometry.quat_to_matrix(states0[0, 9:13]); T_r[:3, 3] = states0[0, 6:9]
robot._tool_offset = np.linalg.inv(T_f) @ T_r
print("Tool-Versatz", np.round(1e3 * robot._tool_offset[:3, 3], 1), "mm")
if os.environ.get("LINKFIX") == "1":  # wie stufe2_vm.py seit 2026-11-14
    _links = robot.link_positions

    def _fixed(joints):
        pos = dict(_links(joints))
        pos["tool"] = robot._pose_from_chain(robot._chain, joints, robot._tool_offset)[:3]
        return pos

    robot.link_positions = _fixed
    print("Stuetzpunkt tool mit Tool-Versatz")

table_z = info.get("ideal_z_min")
table_z = (table_z - 0.15) if table_z is not None else None
ws = default_workspace(table_height_m=table_z)
infer.add_recorded_workspace(ws, info, robot, "neura")
env = info.get("tcp_envelope")
print("Huelle lo", np.round(np.asarray(env["lo"]) * 1e3), "hi", np.round(np.asarray(env["hi"]) * 1e3), "mm")
print("Boxen:", [getattr(b, "name", type(b).__name__) for b in ws.boxes])


def check(label, joints):
    pos = ws.positions_for(robot, joints)
    tool = pos.get("tool")
    fk_tool = robot.fk(joints)
    v = ws.check_positions(pos)
    print("%-28s tool(link_positions) %s  fk %s  -> %s" % (
        label, np.round(1e3 * np.asarray(tool), 1) if tool is not None else None,
        np.round(1e3 * np.asarray(fk_tool[:3]), 1),
        "frei" if not v else "; ".join("%s an %s (%.0f mm)" % (x.frame, x.box, 1e3 * x.clearance) for x in v[:3])))


check("aktuelle Stellung", robot.read_state().joints)
for e in eps:
    st = np.asarray(replay.load_arrays(data, e)["observation.state"], float)
    check("Ep %d Start" % e, st[0, :6])
    print("    Aufnahme-TCP Start", np.round(1e3 * st[0, 6:9], 1))
    g = int(np.argmax(st[:, 13] > 0.5)) if (st[:, 13] > 0.5).any() else len(st) // 2
    check("Ep %d Griff (Takt %d)" % (e, g), st[g, :6])
robot.close()
