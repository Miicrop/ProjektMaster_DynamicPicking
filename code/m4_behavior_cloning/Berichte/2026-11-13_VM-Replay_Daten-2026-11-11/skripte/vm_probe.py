"""Nur lesen: Simulation? Tool in der VM? Lokale FK mit Tool-Versatz?"""
import os, sys, json
ROOT = r"E:\Projekt\ProjektMaster_DynamicPicking\code\m4_behavior_cloning"
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import _bootstrap  # noqa
from bc.adapters import open_robot

r = open_robot("neura")
r.connect(power_on=False)
try:
    print("in_simulation:", r.in_simulation)
    print("tool_name:", r.tool_name)
    print("has_tool_offset:", r.has_tool_offset())
    print("local_fk_check:", json.dumps(r.local_fk_check, default=str))
    s = r.read_state()
    print("joints:", [round(float(v), 3) for v in s.joints])
    print("tcp:", [round(float(v), 4) for v in s.tcp_quat])
    print("flange:", [round(float(v), 4) for v in r.get_flange_pose()])
finally:
    r.close()
