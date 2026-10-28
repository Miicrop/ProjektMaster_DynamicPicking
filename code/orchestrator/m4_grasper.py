"""M4 grasper: the Behavior Cloning policy of person 4 does PICK, M2 does PLACE_INSPECT.

pick() runs his inference (m4_behavior_cloning/apps/infer.py, one run) as a subprocess with his
Python environment. The policy sees the wrist and scene camera, grasps the part and stops at his
handover point PRE_PLACE (~9 cm above the inspection fixture) with the part in the gripper.
place() is M2 as before: it first re-applies its own settings (his program sets its own override),
then lowers the part onto the fixture and opens the gripper.

The pose from M1 is only logged - the policy finds the part in the camera images itself.
The scene camera is the M1 top-down camera; it is released for the run (one process per camera).
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any, Callable

from common import m4
from common.camera import daheng_serial
from common.interfaces import Grasper, ObjectPose, RobotController, RobotTarget

log = logging.getLogger(__name__)

# our robot kind -> his: vm/real is the Neura controller, mock/sim his own simulation (wiring test)
BC_ROBOT = {"mock": "sim", "sim": "sim", "vm": "neura", "real": "neura"}


class BcGrasper(Grasper):
    def __init__(self, cfg: dict[str, Any], robot: RobotController, robot_kind: str = "mock",
                 release_cameras: Callable[[], None] | None = None):
        self._cfg = cfg
        self.robot = robot
        self.robot_kind = robot_kind
        self._release_cameras = release_cameras
        self._proc: subprocess.Popen | None = None
        self._stopped: str | None = None    # why the run was aborted (stop / timeout)
        self.last_rollout = None          # his Rollout of the last run (success, mm values, ...)

    def command(self) -> tuple[list[str], str | None, dict[str, str]]:
        """argv for his Python, stdin text and environment of one inference run."""
        m4.prepare(self._cfg)
        from bc.gui.operation import infer_argv
        mc = self._cfg.get("m4", {})
        checkpoint = mc.get("checkpoint")
        if not checkpoint:
            raise RuntimeError("M4: kein Modell eingestellt - in den Einstellungen 'm4.checkpoint' setzen "
                               "(Ordner aus dem Training, z. B. checkpoints/<name>/policy)")
        bc_robot = BC_ROBOT[self.robot_kind]
        real = self.robot_kind == "real"
        cameras = mc.get("cameras", "auto")
        specs = []
        serial = daheng_serial(self._cfg["topdown_camera"]["source"])
        if bc_robot == "neura" and cameras != "sim":
            if not serial:
                raise RuntimeError("M4: Seriennummer der Draufsichtkamera fehlt (= Szenenkamera von M4) - "
                                   "'topdown_camera.source: daheng:<Seriennummer>' eintragen (python -m common.camera), "
                                   "zum Testen ohne Kameras 'm4.cameras: sim'")
            specs.append(f"scene=daheng:{serial}")          # scene camera = M1 top-down camera
        argv = infer_argv(checkpoint, robot_kind=bc_robot, episodes=1, camera_specs=specs,
                          max_steps=mc.get("max_steps"), real_robot=real)
        if cameras != "auto":
            argv += ["--cameras", cameras]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                   PYTHONPATH=os.pathsep.join([str(m4.BC_DIR), str(m4.BC_DIR.parent)]))
        if bc_robot == "neura":
            rc = self._cfg["robot"]
            env["SOCKET_ADDRESS"] = str(rc["vm_host"] if self.robot_kind == "vm" else rc["host"])
        # his release word for the real plant; the GUI / CLI has asked before the cycle started
        return [m4.bc_python(), "-u", *argv], "ANLAGE\n" if real else None, env

    def pick(self, pose: ObjectPose) -> None:
        log.info("M4 greift (M1-Pose nur zur Info: x=%.1f y=%.1f θ=%.1f)", pose.x_mm, pose.y_mm, pose.theta_deg)
        argv, stdin_text, env = self.command()
        m4.prepare(self._cfg)
        from bc.gui.operation import RolloutProgress
        if self._release_cameras is not None:
            self._release_cameras()
        self._stopped = None
        progress = RolloutProgress(total_episodes=1)
        timeout = float(self._cfg.get("m4", {}).get("timeout_s", 300))
        self._proc = subprocess.Popen(argv, cwd=m4.BC_DIR, env=env, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace")
        timer = threading.Timer(timeout, self._timeout)
        timer.start()
        try:
            if stdin_text:
                self._proc.stdin.write(stdin_text)
            self._proc.stdin.close()      # further questions get EOF -> his safe branch (no motion)
            tail = []
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    log.info("M4: %s", line)
                    progress.feed(line)
                    tail = (tail + [line])[-5:]
            code = self._proc.wait()
        finally:
            timer.cancel()
            self._proc = None
        if self._stopped:
            raise RuntimeError(f"M4 abgebrochen: {self._stopped}")
        self.last_rollout = progress.rollouts[-1] if progress.rollouts else None
        if code != 0 or self.last_rollout is None or not self.last_rollout.success:
            reason = self.last_rollout.stop_reason if self.last_rollout else (" / ".join(tail[-3:]) or f"Exit {code}")
            raise RuntimeError(f"M4 hat den Übergabepunkt nicht erreicht: {reason}")
        if hasattr(self.robot, "holding"):
            self.robot.holding = True     # part is in the gripper now (MockRobot keeps track of it)

    def place(self, target: RobotTarget) -> None:
        self.robot.reset()        # M2's tool, override, speed and init_program again after his run
        self.robot.place(target)

    def _timeout(self) -> None:
        self.stop(f"nicht fertig nach {self._cfg.get('m4', {}).get('timeout_s', 300)} s (m4.timeout_s)")

    def stop(self, reason: str = "STOPP") -> None:
        """Abort a running inference (software STOP / timeout); the robot stop itself is M2's stop()."""
        proc = self._proc
        if proc is not None and proc.poll() is None:
            self._stopped = reason
            log.warning("M4: Inferenz wird abgebrochen (%s)", reason)
            proc.terminate()

    def close(self) -> None:
        self.stop()
