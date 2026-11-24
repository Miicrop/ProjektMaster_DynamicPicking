"""Stufe 2 (apps/infer.py --replay) in der VM, mit Tool-Versatz.

Die VM hat kein Tool ("NoTool"), ihre FK endet am Flansch. Die Anlagendaten
liegen im Tool-Frame (ZimmerLWR50). Ohne Korrektur saehe die Policy einen
TCP 197,5 mm ueber dem gewohnten -- der Zustand laege ausserhalb der
Verteilung. Hier wird nur der Versatz Flansch -> Tool aus der Aufnahme
bestimmt (VM-FK der aufgezeichneten Gelenke gegen den aufgezeichneten TCP)
und als ``_tool_offset`` der lokalen FK gesetzt. Sonst laeuft infer.main()
unveraendert mit allen Pruefungen.

Aufruf: stufe2_vm.py <infer-Argumente ...>
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
import _bootstrap  # noqa: F401
import infer  # noqa: E402
from bc import geometry, replay  # noqa: E402

args = sys.argv[1:]
data = args[args.index("--replay") + 1]
states = np.asarray(replay.load_arrays(data, replay.usable_episodes(data)[0])["observation.state"], float)
HOLD = {}

_real_open = infer.open_robot


def open_robot(kind, **kw):
    robot = _real_open(kind, **kw)
    real_connect = robot.connect

    def connect(*a, **k):
        r = real_connect(*a, **k)
        if robot.in_simulation is not True:
            raise SystemExit("Abbruch: is_robot_in_simulation() ist nicht True.")
        if not robot._local_fk_active:
            raise SystemExit("Abbruch: lokale FK in der VM nicht aktiv: %s" % robot.local_fk_check)
        offs = []
        for i in np.linspace(0, len(states) - 1, 8).astype(int):
            flange = robot._pose_from_chain(robot._chain, states[i, :6], None)
            R = geometry.quat_to_matrix(flange[3:7])
            T_f = np.eye(4); T_f[:3, :3] = R; T_f[:3, 3] = flange[:3]
            T_r = np.eye(4); T_r[:3, :3] = geometry.quat_to_matrix(states[i, 9:13]); T_r[:3, 3] = states[i, 6:9]
            offs.append(np.linalg.inv(T_f) @ T_r)
        off = offs[0]
        spread = max(float(np.linalg.norm(o[:3, 3] - off[:3, 3])) for o in offs)
        robot._tool_offset = off
        # Kollisionspunkte: Die lokalen Stuetzpunkte wurden beim Verbinden den
        # Frames der Steuerung zugeordnet -- in der VM endet "tool" am Flansch.
        # Ohne Korrektur prueft der Geofence einen Punkt 197,5 mm zu hoch
        # (Befund 2026-11-14: Huelle der Demonstrationen stoppt im 1. Takt).
        real_links = robot.link_positions

        def link_positions(joints):
            pos = dict(real_links(joints))
            pos["tool"] = robot._pose_from_chain(robot._chain, joints, robot._tool_offset)[:3]
            return pos

        robot.link_positions = link_positions
        HOLD.update(tool_offset_m=off[:3, 3].tolist(), spread_mm=1e3 * spread, tool=robot.tool_name)
        print("VM-Tool '%s' -> Versatz aus Aufnahme %s mm (Streuung %.3f mm)"
              % (robot.tool_name, np.round(1e3 * off[:3, 3], 2), 1e3 * spread))
        return r

    robot.connect = connect
    return robot


# GEOFENCE=alt: Kollisionsmodell wie beim Checkpoint 2026-11-09 (nur grober
# Tischquader), damit der Variantenvergleich gleiche Bedingungen hat. Tisch-
# und Huellenverstoesse werden danach aus den Protokollen nachgerechnet.
if os.environ.get("GEOFENCE") == "alt":
    def _no_recorded_workspace(*a, **k):
        print("Kollisionsmodell: GEOFENCE=alt -- Tischebene/Huelle aus bc_policy.json NICHT geladen")
        return None

    infer.add_recorded_workspace = _no_recorded_workspace

infer.open_robot = open_robot

# Vergleichsvariante BILDWAHL=position: statt "ein Bild je Takt" das Bild der
# Aufnahme, deren Ist-TCP der aktuellen Stellung am naechsten liegt (gleicher
# Greiferzustand, Fenster -5/+40 um das zuletzt gewaehlte). Trennt Drift
# zwischen Bild und Arm vom Rest.
if os.environ.get("BILDWAHL") == "position":
    from bc.adapters import cam_replay
    REF = {"tcp": None, "grip": None, "cur": 0, "trace": []}
    _sel = cam_replay.ReplayCamera.select

    def select(self, episode):
        r = _sel(self, episode)
        st = np.asarray(replay.load_arrays(self.root, int(episode))["observation.state"], float)
        REF.update(tcp=st[:, 6:9], grip=st[:, 13] > 0.5, cur=0)
        return r

    cam_replay.ReplayCamera.select = select
    _build = infer.build_observation

    def build_observation(robot, captures, frames_out=None):
        state = robot.read_state()
        robot_read = robot.read_state
        robot.read_state = lambda: state
        try:
            if REF["tcp"] is not None:
                a, b = max(0, REF["cur"] - 5), min(len(REF["tcp"]), REF["cur"] + 40)
                d = np.linalg.norm(REF["tcp"][a:b] - np.asarray(state.tcp_quat[:3]), axis=1)
                d[REF["grip"][a:b] != bool(state.gripper_closed)] += 1.0
                REF["cur"] = a + int(np.argmin(d))
                REF["trace"].append((REF["cur"], float(d.min())))
                for cap in captures:
                    cap.camera._index = REF["cur"]
            return _build(robot, captures, frames_out)
        finally:
            robot.read_state = robot_read

    infer.build_observation = build_observation
    _run = infer.run_episode

    def run_episode(*a, **k):
        REF["cur"] = 0
        return _run(*a, **k)

    infer.run_episode = run_episode
    print("Bildwahl: nach Position (Vergleichsvariante)")

sys.argv = ["infer.py"] + args
infer.main()
print("TOOL_OFFSET", json.dumps(HOLD))
