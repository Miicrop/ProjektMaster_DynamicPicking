"""LARA 5 in der MuJoCo-Taktiksimulation (RobotPort, bc/sim_mujoco).

Anders als :class:`~bc.adapters.sim_robot.SimRobot`, der jeden Sollwert
sofort und exakt einnimmt, laeuft dieser Arm dem servo_j-Strom NACH -- mit
dem an die Aufnahmen vom 19.11. angepassten Folgemodell
(``bc/sim_mujoco/folgemodell.py``). Die Beobachtung enthaelt damit den
Schleppfehler wie an der Anlage, und die Kameras (``cam_mujoco.py``)
rendern den Arm dort, wo er wirklich steht.

Uebernommen vom SimRobot: DLS-IK mit Seed-Semantik, Punkte-Datenbank
(lesen/schreiben), Tippbetrieb, Fehlerinjektion. Neu bzw. anders:

* ``fk``/``ik`` mit Werkzeug (TCP 197,5 mm vor dem Flansch) -- wie die lokale
  FK am Neura; die Stuetzpunkte elbow/wrist/tool liegen in denselben Gliedern
  wie an der Steuerung (``local_fk_check.stuetzpunkte``).
* ``servo_j`` -> Folgemodell, ``ServoGuard`` wie real (Sprung, Tempo, Abstand
  zur Ist-Stellung).
* ``move_to_joints``: PTP mit ``config.PTP_JOINT_SPEED_RADS``; die Uhr laeuft
  um die Fahrzeit weiter (SimClock: sofort), danach steht der Arm am Ziel.
* Greifer: Schliessen heftet das Objekt an, wenn es zwischen den Backen liegt.
* Sim-Haken: :meth:`objekt_ablegen`, :meth:`objekt_an_punkt`,
  :meth:`objekt_lage`, :meth:`griff_haelt`.

Standard-Punkte: ``bc/sim_mujoco/punkte_2026-11-19.json`` (CLEAR_FOV, PICK,
Tischpunkte ID0-8, IGNORE wie am 19.11.); das Objekt liegt beim Start an PICK.
"""

import math

import numpy as np

from .. import config
from ..clock import RealClock
from ..ports import RobotError, ServoLimitError
from .sim_robot import SimRobot

#: Ein Name je Port-Frame -> Glied (Index in KinematicChain.fk_frames) und
#: Punkt im Glied-KS. Fehlt ein Eintrag, gilt die Zuordnung des SimRobot.
_FLANGE_FRAMES = ("flange",)


class MujocoRobot(SimRobot):
    """Simulierter LARA 5 mit Folgemodell, Greifer und Objekt in MuJoCo.

    ``welt``: vorhandene :class:`bc.sim_mujoco.szene.Welt` (Default: eine neue
    prozessweite Welt mit ``clock``, siehe :func:`bc.sim_mujoco.welt`).
    """

    #: Tool-Name wie an der Anlage, mit Kennzeichnung
    tool_name = "ZimmerLWR50 (MuJoCo)"
    in_simulation = True
    gripper_mode = "sim"
    gripper_via_outputs = False

    def __init__(self, clock=None, seed=0, faults=None, points=None, servo_guard=None,
                 welt=None, neue_welt=True, **kwargs):
        from .. import sim_mujoco

        clock = clock if clock is not None else RealClock()
        if welt is None:
            welt = sim_mujoco.welt(clock=clock, neu=neue_welt)
        self.welt = welt
        punkte = welt.punkte["punkte"]
        if points is None:
            points = {name: p["joints"] for name, p in punkte.items()}
        home = welt.gelenke
        super().__init__(clock=clock, faults=faults, seed=seed, home=home, points=points,
                         servo_guard=servo_guard, **kwargs)
        self._tool = np.asarray(welt.tool_offset, dtype=float)
        self._stuetz = {name: (int(v["glied"]), np.asarray(v["punkt_m"], dtype=float))
                        for name, v in (welt.punkte.get("stuetzpunkte") or {}).items()}
        #: Greiferbefehle wie am Neura-Adapter: [(t, zu)], record.py legt sie
        #: in die Metadaten
        self.gripper_log = []
        self.ptp_speed = config.PTP_JOINT_SPEED_RADS
        # Schnelle Kette fuer Planung/IK: feste Gelenk-Urspruenge vorab
        from ..urdf import _rpy_matrix

        self._fast = []
        for j in self._chain.joints:
            A = np.eye(4)
            A[:3, :3] = _rpy_matrix(*j.rpy)
            A[:3, 3] = j.xyz
            axis = None if j.type != "revolute" else np.asarray(j.axis, float) / np.linalg.norm(j.axis)
            self._fast.append((A, axis))

    # -- Zustand -------------------------------------------------------------

    @property
    def _joints(self):
        return self.welt.gelenke

    @_joints.setter
    def _joints(self, value):
        # SimRobot setzt _joints im Konstruktor -- die Welt fuehrt den Arm
        if getattr(self, "welt", None) is not None:
            self.welt.setze_gelenke(np.asarray(value, dtype=float), self._clock.now())

    def read_state(self):
        self._require_connected()
        self._fault_gate()
        self.welt.weiter_bis(self._clock.now())
        return super().read_state()

    # -- Kinematik ------------------------------------------------------------

    def _fk_fast(self, q):
        """Kettenende (4x4) und je revolutem Gelenk (Achse, Ursprung) im Welt-KS.

        Gleiche Rechnung wie KinematicChain.fk_frames, ohne die Ursprungs-
        Matrizen jedes Mal neu aufzubauen (Planung: ~10^5 Aufrufe je Lage)."""
        T = np.eye(4)
        axes = []
        qi = 0
        for A, axis in self._fast:
            T = T @ A
            if axis is not None:
                c, s_ = np.cos(q[qi]), np.sin(q[qi])
                x, y, z = axis
                K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
                R = np.eye(3) + s_ * K + (1 - c) * (K @ K)
                T = T.copy()
                T[:3, :3] = T[:3, :3] @ R
                axes.append((T[:3, :3] @ axis, T[:3, 3].copy()))
                qi += 1
        return T, axes

    def _frame_transform(self, joints, frame):
        if frame == "tool":
            return self._fk_fast(np.asarray(joints, dtype=float))[0] @ self._tool
        if frame in _FLANGE_FRAMES:
            return self._fk_fast(np.asarray(joints, dtype=float))[0]
        if frame in self._stuetz and frame != "tool":
            k, point = self._stuetz[frame]
            T = self._chain.fk_frames(joints)[k][1].copy()
            T[:3, 3] = T[:3, :3] @ point + T[:3, 3]
            return T
        return super()._frame_transform(joints, frame)

    #: IK (Planung). Gleiche DLS-Iteration und Seed-Semantik wie der SimRobot,
    #: aber mit analytischer Jacobi-Matrix (eine FK je Schritt statt sieben)
    #: und Abbruchregeln, die die Planung in der Sim bezahlbar machen:
    #:
    #: * Nahe CLEAR_FOV ist die Jacobi-Matrix schlecht konditioniert (kleinster
    #:   Singulaerwert ~0,03); dort braucht die Iteration bei ~2 % der
    #:   verrauschten Posen mehr als 200 Schritte. Sie laeuft deshalb bis
    #:   IK_MAX_ITER weiter -- aber nur, solange der Rest kleiner als
    #:   IK_CONTINUE_POS_M / _ROT_RAD ist (dann ist eine Loesung in Reichweite).
    #: * Stagniert der Rest (IK_STALL_ITER Schritte ohne Verbesserung um
    #:   IK_STALL_GAIN), gilt: Rest unter IK_ACCEPT_POS_M / _ROT_RAD -> Loesung
    #:   (zehnmal strenger als die FK-Rueckprobe der Pipeline,
    #:   config.IK_FK_TOL_*), sonst nicht erreichbar -> sofort IKError.
    #:   Befund 2026-11-20: Auf der PTP-Bahn ab CLEAR_FOV (q4 ~ 0, kleinster
    #:   Singulaerwert 0,001) bleibt die gedaempfte Iteration bei 0,016 mm Rest
    #:   stehen -- die Toleranz des SimRobot (0,01 mm) verwarf dort erreichbare
    #:   Posen; das war die "unerreichbare Pose neben CLEAR_FOV".
    IK_FIRST_ITER = 200
    IK_MAX_ITER = 1000
    IK_CONTINUE_POS_M = 1.0e-3
    IK_CONTINUE_ROT_RAD = 1.0e-2
    IK_STALL_ITER = 25
    IK_STALL_GAIN = 0.99
    IK_ACCEPT_POS_M = 1.0e-4
    IK_ACCEPT_ROT_RAD = 1.0e-3

    def _jacobian(self, q, eps=None):
        """Analytische 6xN-Jacobi-Matrix des Werkzeugs (Position + Drehung).

        Spalte i: Achse a_i (Welt) und a_i x (p_tool - p_i) -- entspricht der
        numerischen Fassung des SimRobot (Rotationsvektor im Welt-KS)."""
        return self._jacobian_from(*self._fk_fast(np.asarray(q, dtype=float)))

    def _jacobian_from(self, T_end, axes):
        p_tool = (T_end @ self._tool)[:3, 3]
        J = np.zeros((6, len(axes)))
        for i, (axis, origin) in enumerate(axes):
            J[:3, i] = np.cross(axis, p_tool - origin)
            J[3:, i] = axis
        return J

    def ik(self, pose_quat, reference_joint, max_iter=None, tol_pos=1e-5, tol_rot=1e-4):
        from .. import geometry
        from ..ports import IKError
        from .sim_robot import _rotation_vector

        self._fault_gate()
        if self._faults.ik_fail_rate > 0 and self._rng.random() < self._faults.ik_fail_rate:
            raise IKError("IK ohne Loesung (simulierter Ausfall)", reason="injected")
        target = np.asarray(pose_quat, dtype=float)
        if target.shape != (7,):
            raise ValueError("ik() erwartet eine Quaternion-Pose mit 7 Werten")
        target_pos = target[:3]
        target_rot = geometry.quat_to_matrix(target[3:7])
        first = self.IK_FIRST_ITER if max_iter is None else int(max_iter)
        limit = max(first, self.IK_MAX_ITER) if max_iter is None else int(max_iter)
        q = np.asarray(reference_joint, dtype=float).copy()
        damping2 = 0.05 ** 2
        best, since = np.inf, 0
        for k in range(limit):
            T_end, axes = self._fk_fast(q)
            T = T_end @ self._tool
            err_pos = target_pos - T[:3, 3]
            err_rot = _rotation_vector(target_rot @ T[:3, :3].T)
            n_pos, n_rot = float(np.linalg.norm(err_pos)), float(np.linalg.norm(err_rot))
            if n_pos < tol_pos and n_rot < tol_rot:
                bad = self._limit_violations(q)
                if bad:
                    raise IKError("IK-Loesung verletzt Achsgrenzen an Gelenk(en) %s" % bad,
                                  reason="joint_limits")
                return q
            score = n_pos + 0.1 * n_rot
            if score < best * self.IK_STALL_GAIN:
                best, since = score, 0
            else:
                since += 1
            near = n_pos < self.IK_CONTINUE_POS_M and n_rot < self.IK_CONTINUE_ROT_RAD
            if since >= self.IK_STALL_ITER or k + 1 >= limit - 1:
                if n_pos < self.IK_ACCEPT_POS_M and n_rot < self.IK_ACCEPT_ROT_RAD:
                    bad = self._limit_violations(q)
                    if bad:
                        raise IKError("IK-Loesung verletzt Achsgrenzen an Gelenk(en) %s" % bad,
                                      reason="joint_limits")
                    return q
                if not near or since >= self.IK_STALL_ITER:
                    break
            if k + 1 >= first and not near:
                break
            J = self._jacobian_from(T_end, axes)
            dq = J.T @ np.linalg.solve(J @ J.T + damping2 * np.eye(6), np.concatenate([err_pos, err_rot]))
            step = float(np.max(np.abs(dq)))
            if step > 0.2:
                dq *= 0.2 / step
            q = q + dq
        raise IKError("IK nicht konvergiert fuer Pose %s" % np.round(target, 4).tolist(),
                      reason="no_convergence")

    # -- Bewegung ---------------------------------------------------------------

    def activate_servo(self, mode="position"):
        self._require_connected()
        self._fault_gate()
        now = self._clock.now()
        self.welt.weiter_bis(now)
        q = self.welt.gelenke
        self.servo_guard.reset(q, now)
        self.welt.sollwert(now, q)
        self._servo_active = True

    def servo_j(self, joint_angles, velocity=None, acceleration=None):
        """Sollwert ins Folgemodell -- der Arm laeuft ihm nach."""
        self._require_connected()
        if not self._servo_active:
            raise RobotError("Servo-Interface ist nicht aktiv")
        if self._stop_requested.is_set():
            raise RobotError("Stopp angefordert -- servo_j verweigert")
        self._fault_gate()
        target = np.asarray(joint_angles, dtype=float)
        if len(target) != self.dof:
            raise ValueError("servo_j erwartet %d Winkel" % self.dof)
        for label, values in (("velocity", velocity), ("acceleration", acceleration)):
            if values is not None and len(values) != self.dof:
                raise ValueError("servo_j: %s braucht %d Werte" % (label, self.dof))
        now = self._clock.now()
        try:
            self.servo_guard.check(target, now)
        except ServoLimitError:
            self.emergency_stop()
            raise
        self.last_servo_command = (target.copy(), velocity, acceleration)
        if self._faults.servo_noise_rad > 0:
            target = target + self._rng.uniform(
                -self._faults.servo_noise_rad, self._faults.servo_noise_rad, self.dof)
        self.welt.sollwert(now, target)

    def online_j(self, joint_angles, velocity_limits, accel_limits):
        raise NotImplementedError("MujocoRobot kennt nur servo_j (Ausfuehrung servo_j)")

    def move_to_joints(self, joints):
        """PTP ausserhalb der Aufzeichnung: Fahrzeit vergeht, dann steht der Arm.

        Fahrzeit = groesster Gelenkweg / ``ptp_speed`` plus 0,5 s Anfahren und
        Ausschwingen. Bild waehrend der Fahrt gibt es nicht (wird nicht
        aufgezeichnet).
        """
        self._require_connected()
        if self._servo_active:
            raise RobotError("move_to_joints bei aktivem Servo-Interface")
        if self._stop_requested.is_set():
            raise RobotError("Stopp angefordert -- move_to_joints verweigert")
        self._fault_gate()
        target = np.asarray(joints, dtype=float)
        if len(target) != self.dof:
            raise ValueError("move_to_joints erwartet %d Winkel" % self.dof)
        bad = self._limit_violations(target)
        if bad:
            raise RobotError("move_to_joints: Ziel verletzt Achsgrenzen an Gelenk(en) %s" % bad)
        self.welt.weiter_bis(self._clock.now())
        dist = float(np.max(np.abs(target - self.welt.gelenke)))
        if dist > 1e-6:
            self._clock.sleep(dist / self.ptp_speed + 0.5)
        self.welt.setze_gelenke(target, self._clock.now())

    def emergency_stop(self):
        """Stopp: Sollwert = Ist (der Arm bremst im Folgemodell ab)."""
        super().emergency_stop()
        try:
            now = self._clock.now()
            self.welt.weiter_bis(now)
            self.welt.sollwert(now, self.welt.gelenke)
        except Exception:
            pass  # darf nie werfen

    def deactivate_servo(self):
        super().deactivate_servo()

    def jog_tick(self):
        velocity = getattr(self, "_jog_velocity", None)
        if velocity is None:
            raise RobotError("jog_tick ohne jog_start")
        q = self.welt.gelenke
        pose = self.fk(q, frame="tool").copy()
        pose[:3] += self.JOG_STEP_M * velocity[:3]
        self.welt.setze_gelenke(np.asarray(self.ik(pose, q), dtype=float), self._clock.now())

    # -- Greifer ----------------------------------------------------------------

    def gripper_command(self, close):
        self._require_connected()
        self._fault_gate()
        now = self._clock.now()
        self._gripper_closed = bool(close)
        self._gripper_cmd_time = now
        self.welt.greifer(bool(close), now)
        self.gripper_log.append((now, bool(close)))

    # -- Sim-Haken ----------------------------------------------------------------

    def objekt_ablegen(self, x, y, yaw_deg):
        """Objekt an (x, y) mit Gier ``yaw_deg`` (Objekt-x, volle 360 Grad) legen."""
        self.welt.objekt_ablegen(float(x), float(y), math.radians(float(yaw_deg)))

    def objekt_an_punkt(self, name="PICK"):
        """Objekt so legen, dass der Greifer am Punkt ``name`` es fasst."""
        self.welt.objekt_an_punkt(joints=self._points[name])

    def objekt_fuer_griff(self, joints):
        """Objekt so legen, dass der Greifer in der Stellung ``joints`` es fasst
        (Testlagen: ``pick_joints`` aus bc/sim_mujoco/testlagen_v1.json)."""
        self.welt.objekt_an_punkt(joints=[float(v) for v in joints])

    def objekt_lage(self):
        """(x, y, Gier in Grad) der Objektmitte -- volle 360 Grad (Fase)."""
        x, y, yaw, _T = self.welt.objekt_lage()
        return x, y, math.degrees(yaw)

    def griff_haelt(self):
        """Haengt das Objekt gerade am Greifer?"""
        return self.welt.angeheftet is not None

    def close(self):
        super().close()
