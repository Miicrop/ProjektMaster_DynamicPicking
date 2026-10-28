"""Only one side talks to the Neura controller at a time: M2 (incl. the automatic cycle) or M4.

Both connect on their own (M2 with its NeuraRobot, M4 with its own adapter, in this process or in
one of its subprocesses). Switching is seamless: whoever wants the robot takes it over and the
other side is disconnected automatically - as long as it is idle. While the other side is moving
(cycle, robot task, M4 recording / inference / teach series) the takeover is refused with a message.

Same for the Daheng top-down camera, which M4 uses as its scene camera: before M4 opens a camera,
M1 / the cycle let go of theirs (it opens again on the next image).
"""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from common.camera import daheng_serial

log = logging.getLogger(__name__)

SHARED_KINDS = ("vm", "real")      # M2 kinds that use the Neura controller - mock / sim do not


class RobotBusy(RuntimeError):
    pass


class RobotAccess(QObject):
    _call = Signal(object, object)      # fn, result box - executed in the GUI thread

    def __init__(self, session, runner, m2_tab, auto_tab, m4_tab):
        super().__init__()
        self.s, self.runner = session, runner
        self.m2, self.auto, self.m4 = m2_tab, auto_tab, m4_tab
        self._call.connect(self._run, Qt.ConnectionType.BlockingQueuedConnection)
        session.before_robot_connect = self.claim_for_m2
        m4_tab.before_robot_use = self.claim_for_m4
        m4_tab.before_camera_use = self.release_cameras_for_m4

    # -- M2 / cycle wants the robot (called in the robot worker thread) --------------------
    def claim_for_m2(self, kind: str) -> None:
        if kind in SHARED_KINDS:
            self._in_gui(self._release_m4)

    def _release_m4(self) -> None:
        reason = self.m4.robot_busy_reason()
        if reason:
            raise RobotBusy(f"M4 benutzt gerade den Roboter ({reason}) - erst im Reiter M4 beenden.")
        if self.m4.release_robot():
            log.info("M4 vom Roboter getrennt - M2 übernimmt")

    # -- M4 wants the robot (GUI thread) -----------------------------------------------------
    def claim_for_m4(self) -> None:
        if not (self.s.robot_connected and self.s.robot_kind in SHARED_KINDS):
            return
        if self.auto.running or self.runner.busy("robot"):
            raise RobotBusy("M2 bzw. der automatische Ablauf benutzt gerade den Roboter - "
                            "erst dort beenden, dann in M4 neu starten.")
        self.s.disconnect_robot()
        self.m2._set_connected(False)
        log.info("M2 vom Roboter getrennt - M4 übernimmt")

    def release_cameras_for_m4(self) -> None:
        if daheng_serial(self.s.cfg["topdown_camera"]["source"]) is not None:
            if self.auto.running:
                raise RobotBusy("Der automatische Ablauf braucht die Draufsichtkamera - erst dort beenden.")
            self.s.release_cameras()

    # -- helpers ----------------------------------------------------------------------------
    def _in_gui(self, fn: Callable[[], None]) -> None:
        if QThread.currentThread() is self.thread():
            fn()
            return
        box: list = []
        self._call.emit(fn, box)
        if box:
            raise box[0]

    @Slot(object, object)
    def _run(self, fn, box) -> None:
        try:
            fn()
        except Exception as e:      # handed back to the worker thread
            box.append(e)
