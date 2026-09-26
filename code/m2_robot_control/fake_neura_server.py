"""Minimal stand-in for the Neura controller's neurapy socket server.

Speaks the same JSON protocol as the real controller (port 65432), so the unmodified
vendor client and NeuraRobot can be tested without robot or VM. It only records the
calls and keeps a fake TCP pose - no kinematics, no collision checks.

    python -m m2_robot_control.fake_neura_server            # listens on 127.0.0.1:65432
"""
from __future__ import annotations

import argparse
import json
import logging
import socket
import socketserver
import threading
from typing import Any

log = logging.getLogger(__name__)

# Named points taken from the robot backup (m, rad)
POINTS = {
    "Home": {"joint": [0.0, 0.0, 1.5708, 0.0, 1.5708, 0.0],
             "cartesian": [0.42, 0.0, 0.4345, 3.14159265, 0.0, 3.14159265]},
    "Parking": {"joint": [1.5708, 0.0, -2.4958, 0.0, 0.0, 0.0],
                "cartesian": [0.0, -0.3524, 0.1324, 3.14159265, -0.6458, -1.5708]},
}


class FakeNeura:
    """State + implementation of the supported API functions."""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self.calls: list[tuple[str, list, dict]] = []
        self.tcp = list(POINTS["Home"]["cartesian"])
        self.joints = list(POINTS["Home"]["joint"])
        self.powered = False
        self.teach_mode = True
        self.program_ready = False
        self.gripper_closed = False
        self.override = 1.0
        self.tool = "NoTool"
        self._ik: dict[tuple, list[float]] = {}

    # -- bookkeeping -------------------------------------------------------------
    def initialize_attributes(self) -> dict[str, Any]:
        return {"robot_name": "LARA5-FAKE", "dof": 6, "payload": 5.0,
                "controller_ip": self.host, "version": "v5.0.8"}

    def get_functions(self) -> list[str]:
        return [n for n in dir(self) if not n.startswith("_") and callable(getattr(self, n))
                and n not in ("dispatch",)]

    def get_diagnostics(self) -> dict:
        return {"critical": False}

    def get_errors(self) -> list:
        return []

    def get_doc(self, name: str) -> str:
        return f"{name}: fake server, no documentation"

    # -- state -------------------------------------------------------------------
    def power_on(self) -> bool:
        self.powered = True
        return True

    def power_off(self) -> bool:
        self.powered = False
        return True

    def is_robot_in_teach_mode(self) -> bool:
        return self.teach_mode

    def is_robot_in_automatic_mode(self) -> bool:
        return not self.teach_mode

    def switch_to_automatic_mode(self) -> bool:
        self.teach_mode = False
        return True

    def set_tool(self, tool_name: str) -> bool:
        self.tool = tool_name
        return True

    def set_override(self, value: float) -> bool:
        self.override = value
        return True

    def set_joint_speed(self, speed: float) -> bool:
        return True

    def init_program(self) -> bool:
        self.program_ready = True
        return True

    def stop(self) -> bool:
        self.program_ready = False
        return True

    # -- queries -------------------------------------------------------------
    def get_tcp_pose(self, timestamp: bool = False, representation: str = "rpy") -> list[float]:
        return list(self.tcp)

    def get_current_joint_angles(self) -> list[float]:
        return list(self.joints)

    def get_point(self, name: str, representation: str = "Joint") -> list[float]:
        return list(POINTS[name]["joint" if representation == "Joint" else "cartesian"])

    def get_point_names(self) -> list[str]:
        return list(POINTS)

    def compute_inverse_kinematics(self, target_pose, reference_joint, *args, **kwargs):
        # fake "joints": remember which pose they belong to
        joints = [round(v, 6) for v in target_pose[:6]]
        self._ik[tuple(joints)] = list(target_pose[:6])
        return joints

    # -- motion --------------------------------------------------------------
    def _require_motion(self) -> None:
        if not self.powered:
            raise RuntimeError("Robot not powered")
        if self.teach_mode:
            raise RuntimeError("Robot in teach mode")
        if not self.program_ready:
            raise RuntimeError("init_program not called")

    def move_joint(self, target_joint=None, *args, **kwargs) -> bool:
        self._require_motion()
        target = target_joint if target_joint is not None else kwargs.get("target_joint")
        if isinstance(target, str):
            self.joints = list(POINTS[target]["joint"])
            self.tcp = list(POINTS[target]["cartesian"])
        else:
            self.joints = list(target)
            self.tcp = self._ik.get(tuple(round(v, 6) for v in target), self.tcp)
        return True

    def move_linear(self, target_pose=None, *args, **kwargs) -> bool:
        self._require_motion()
        poses = target_pose if target_pose is not None else kwargs["target_pose"]
        self.tcp = list(poses[-1])
        return True

    def grasp(self) -> bool:
        self.gripper_closed = True
        return True

    def release(self) -> bool:
        self.gripper_closed = False
        return True

    # -- protocol ------------------------------------------------------------
    def dispatch(self, request: dict) -> dict:
        name, args, kwargs = request["function"], request.get("args", []), request.get("kwargs", {})
        if name != "get_diagnostics":
            self.calls.append((name, args, kwargs))
        fn = getattr(self, name, None)
        if fn is None or name.startswith("_") or name == "dispatch":
            return {"result": None, "error": f"Function {name} not supported by fake server"}
        try:
            return {"result": fn(*args, **kwargs), "error": None}
        except Exception as e:  # reported to the client like the real server does
            return {"result": None, "error": str(e)}


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = b""
        while True:
            chunk = self.request.recv(8192)
            if not chunk:
                return
            data += chunk
            try:
                request = json.loads(data.decode("utf-8"))
                break
            except json.JSONDecodeError:
                continue
        response = self.server.fake.dispatch(request)
        self.request.sendall(json.dumps(response).encode("utf-8"))


class FakeNeuraServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, host: str = "127.0.0.1", port: int = 65432):
        super().__init__((host, port), _Handler)
        self.fake = FakeNeura(host)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def start_background(self) -> "FakeNeuraServer":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self


_shared: FakeNeuraServer | None = None


def shared_server() -> FakeNeuraServer:
    """One fake controller per process, never shut down.

    The neurapy client polls get_diagnostics() every 2 s in a background thread for
    the lifetime of the process; stopping the server would make that thread fail.
    """
    global _shared
    if _shared is None:
        _shared = FakeNeuraServer("127.0.0.1", 0).start_background()
    return _shared


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=65432)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    server = FakeNeuraServer(args.host, args.port)
    print(f"Fake Neura controller on {args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
