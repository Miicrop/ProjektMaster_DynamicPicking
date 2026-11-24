"""Action Noise Injection: Rauschprozess, Trichter, Rejection Sampling (AP 2.4).

Setzt die asymmetrische Rauscheinspielung um:

* **Ornstein-Uhlenbeck-Prozess** fuer weiche, realistische Abweichungen
  statt unruhigem Zittern -- zusaetzlich geglaettet, damit auch
  Geschwindigkeit und Beschleunigung der Befehlsbahn stetig bleiben
  (servo_j, Befund VM 2026-09-14, siehe :class:`SmoothedOUProcess`).
* **Trichter-Daempfung**: das Rauschen ist an jedem Ankerpunkt 0 --
  Episodenstart, jeder Greiferwechsel, Episodenende -- und steigt bzw.
  faellt dazwischen ueber die Bahnlaenge weich an (praeziser Griff trotz
  Schlingerns im Transit, kein Ruck direkt nach dem Greifen, Start und
  Uebergabe exakt an den geteachten Punkten).
* **Asymmetrische Begrenzung**: kartesische Box-Grenzen je Achse, z. B.
  kein/kaum Rauschen Richtung Tisch (Sicherheitsanforderung AP 2.4).
* **Rejection Sampling**: jede verrauschte Bahn wird per IK geloest
  (inkl. der vier Absicherungen aus kinematics.py) und gegen das
  Kollisionsmodell geprueft; bei Verletzung wird neu gesampelt.

Das Rauschen wird KARTESISCH aufgepraegt und per IK in Gelenkwinkel
umgerechnet -- nie direkt im Gelenkraum (Begruendung in AP 2.4: nur
kartesisch lassen sich Richtungsgrenzen wie "nicht Richtung Tisch"
garantieren). Die IK laeuft offline bei der Generierung, nicht in der
Echtzeitschleife.
"""

from dataclasses import dataclass, field

import numpy as np

from . import config, geometry
from .kinematics import IKFailure


class OUProcess(object):
    """Ornstein-Uhlenbeck-Prozess in d Dimensionen.

    Stationaere Standardabweichung = ``sigma``, Zeitkonstante ``tau``.
    Grosse tau = traege Schlingerbewegung, kleine tau = nervoeses Zittern.
    """

    def __init__(self, sigma, tau, dt, dims=3, rng=None):
        self.sigma = float(sigma)
        self.tau = float(tau)
        self.dt = float(dt)
        self.dims = dims
        self.rng = rng if rng is not None else np.random.default_rng()
        self.state = np.zeros(dims)

    def reset(self):
        self.state = np.zeros(self.dims)
        return self.state

    def step(self):
        # Exakte Diskretisierung des OU-Prozesses (stabil fuer jedes dt)
        alpha = np.exp(-self.dt / self.tau)
        noise_std = self.sigma * np.sqrt(1.0 - alpha * alpha)
        self.state = alpha * self.state + noise_std * self.rng.standard_normal(self.dims)
        return self.state.copy()


class SmoothedOUProcess(object):
    """OU-Prozess mit nachgeschalteter Glaettung -- das Rauschen fuer servo_j.

    Beim reinen OU-Prozess ist die Position stetig, die GESCHWINDIGKEIT aber
    weisses Rauschen: jeder Takt bekommt einen unabhaengigen Stoss. Gemessen
    VM 2026-09-14: 0.09 m/s Streuung je Achse (60 % der Transitgeschwindig-
    keit), Befehlsbahn bis 25 rad/s^2 an den Handgelenken, der Arm lief bis
    0.57 rad hinterher. Der SimRobot springt einfach mit, deshalb fiel das
    vorher nicht auf.

    Abhilfe: zwei gleiche Tiefpaesse 1. Ordnung (Zeitkonstante
    ``tau_smooth``) hinter dem OU-Prozess -- ein kritisch gedaempftes Glied
    2. Ordnung. Der Charakter bleibt (traege Drift mit ``tau``), aber
    Geschwindigkeit und Beschleunigung sind endlich. Bei tau_smooth=0.25 s
    und 15 Hz: Geschwindigkeit 0.022 statt 0.09 m/s, Beschleunigung
    0.11 statt 1.95 m/s^2 (je Achse, Std).

    * **Amplitude bleibt ``sigma``:** Die Glaettung senkt die Varianz; der
      Verstaerkungsfaktor dafuer wird exakt aus der stationaeren Kovarianz
      des diskreten Systems berechnet (Lyapunov-Gleichung).
    * **Grenzen ohne Knick:** ``lo``/``hi`` werden auf den OU-Zustand VOR der
      Glaettung angewendet. Die Tiefpaesse mitteln nur (Impulsantwort >= 0,
      Summe 1), der Ausgang bleibt also garantiert in den Grenzen -- ein
      hartes Klemmen des Ausgangs dagegen braechte wieder einen
      Geschwindigkeitssprung.
    * **Stationaerer Start:** Der Anfangszustand wird aus der stationaeren
      Verteilung gezogen, damit die Amplitude nicht erst ueber einige
      Sekunden einschwingt. Am Anker ist das Rauschen trotzdem 0 (Trichter).
    """

    def __init__(self, sigma, tau, tau_smooth, dt, dims=3, rng=None, lo=None, hi=None):
        self.sigma = float(sigma)
        self.dims = dims
        self.rng = rng if rng is not None else np.random.default_rng()
        self.lo = None if lo is None else np.asarray(lo, dtype=float)
        self.hi = None if hi is None else np.asarray(hi, dtype=float)

        self._alpha = np.exp(-dt / float(tau))
        self._beta = np.exp(-dt / float(tau_smooth)) if tau_smooth > 0 else 0.0
        # Zustand je Achse s = [ou, tiefpass1, tiefpass2]. Tiefpaesse in der
        # Form y_neu = beta*y + (1-beta)*u_neu; als lineares System
        # s_neu = A s + b w fuer die stationaere Kovarianz (ohne Grenzen).
        a, beta = self._alpha, self._beta
        g = 1.0 - beta
        A = np.array(
            [
                [a, 0.0, 0.0],
                [g * a, beta, 0.0],
                [g * g * a, g * beta, beta],
            ]
        )
        b = np.array([1.0, g, g * g]) * np.sqrt(1.0 - a * a)
        cov = _stationary_covariance(A, b)
        # Verstaerkung so, dass der AUSGANG die Std sigma hat
        self._gain = self.sigma / np.sqrt(cov[2, 2])
        self._noise_std = self._gain * np.sqrt(1.0 - a * a)
        self._chol = np.linalg.cholesky(cov + 1e-12 * np.eye(3)) * self._gain
        self.state = np.zeros((dims, 3))
        self.reset()

    def reset(self):
        """Neuer Startzustand aus der stationaeren Verteilung."""
        s = self.rng.standard_normal((self.dims, 3)) @ self._chol.T
        # In den Grenzen starten (Tiefpaesse sind Mittelwerte des OU-Zustands)
        self.state = np.stack([self._clip(s[:, k]) for k in range(3)], axis=1)
        return self.state[:, 2].copy()

    def step(self):
        beta = self._beta
        ou = self._alpha * self.state[:, 0]
        ou = self._clip(ou + self._noise_std * self.rng.standard_normal(self.dims))
        y1 = beta * self.state[:, 1] + (1.0 - beta) * ou
        y2 = beta * self.state[:, 2] + (1.0 - beta) * y1
        self.state = np.stack([ou, y1, y2], axis=1)
        return y2.copy()

    def _clip(self, values):
        if self.lo is None and self.hi is None:
            return values
        return np.clip(values, self.lo, self.hi)


def _stationary_covariance(A, b):
    """Loest P = A P A^T + b b^T (diskrete Lyapunov-Gleichung, n klein)."""
    n = A.shape[0]
    rhs = np.outer(b, b).reshape(-1)
    vec = np.linalg.solve(np.eye(n * n) - np.kron(A, A), rhs)
    P = vec.reshape(n, n)
    return 0.5 * (P + P.T)


def funnel_scale(
    dist_to_anchor,
    start=config.FUNNEL_START_DIST_M,
    zero=config.FUNNEL_ZERO_DIST_M,
):
    """Trichter-Daempfung: 1.0 im Transit, 0.0 am Ankerpunkt.

    Smoothstep zwischen ``zero`` und ``start`` -- stetig differenzierbar,
    damit die Daempfung selbst keine Spruenge in die Bahn traegt.
    """
    d = np.asarray(dist_to_anchor, dtype=float)
    t = np.clip((d - zero) / (start - zero), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass
class NoiseLimits:
    """Asymmetrische kartesische Grenzen des Rauschens (Weltkoordinaten).

    ``lo``/``hi`` sind je Achse die minimal/maximal zulaessige Auslenkung.
    Default: seitlich und nach oben symmetrisch, nach unten (Richtung
    Tisch) stark reduziert -- die Kernforderung aus AP 2.4.
    """

    lo: np.ndarray = field(
        default_factory=lambda: np.array(
            [
                -3.0 * config.NOISE_TRANS_AMPLITUDE_M,
                -3.0 * config.NOISE_TRANS_AMPLITUDE_M,
                -0.002,  # kaum Auslenkung Richtung Tisch
            ]
        )
    )
    hi: np.ndarray = field(
        default_factory=lambda: np.array(
            [
                3.0 * config.NOISE_TRANS_AMPLITUDE_M,
                3.0 * config.NOISE_TRANS_AMPLITUDE_M,
                3.0 * config.NOISE_TRANS_AMPLITUDE_M,
            ]
        )
    )

    def clip(self, offset):
        return np.clip(offset, self.lo, self.hi)


def _smooth_ramp(x, a, b):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def distance_to_grasp(ideal):
    """Bahnlaenge (m) jedes Schritts bis zum ersten Schliessen des Greifers;
    ab dort und ohne Schliessen: inf."""
    pos = np.asarray(ideal.poses_quat[:, :3], dtype=float)
    grip = np.asarray(ideal.gripper, dtype=float) > config.GRIPPER_THRESHOLD
    closing = np.flatnonzero(grip[1:] & ~grip[:-1])
    out = np.full(len(pos), np.inf)
    if not len(closing):
        return out
    c = int(closing[0]) + 1
    cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pos, axis=0), axis=1))])
    out[:c] = cum[c] - cum[:c]
    return out


def approach_offset_profile(ideal, start_m=None):
    """Anteil 0..1 des Anflug-Versatzes je Schritt (config.APPROACH_OFFSET_*).

    ``start_m``: Bahnlaenge vor dem Greifen, ab der der Versatz einsetzt
    (Default HOLD+RAMP); voll ab HOLD, null ab FREE."""
    d = distance_to_grasp(ideal)
    hold = config.APPROACH_OFFSET_HOLD_M
    start = hold + config.APPROACH_OFFSET_RAMP_M if start_m is None else max(float(start_m), hold + 1e-3)
    rise = _smooth_ramp(d, config.APPROACH_OFFSET_FREE_M, config.APPROACH_OFFSET_FULL_M)
    fall = 1.0 - _smooth_ramp(d, hold, start)
    return np.where(np.isfinite(d), rise * fall, 0.0)


def smooth_limited(target, max_step, window, max_step_hard=None):
    """Wie :func:`rate_limited`, zusaetzlich gleitend gemittelt (``window``
    Schritte) -- begrenzt so auch die Beschleunigung (kein spitzes V). Bleibt
    <= :func:`rate_limited` mit ``max_step_hard`` (Default 2x) und damit null,
    wo ``target`` null ist."""
    r = rate_limited(target, max_step)
    window = int(window)
    if window <= 1 or len(r) < 2:
        return r
    pad = window // 2
    kernel = np.ones(2 * pad + 1) / (2 * pad + 1)
    avg = np.convolve(np.pad(r, (pad, pad), mode="edge"), kernel, mode="valid")
    hard = rate_limited(target, 2.0 * max_step if max_step_hard is None else max_step_hard)
    return np.minimum(avg, hard)


def rate_limited(target, max_step):
    """Betrag von ``target`` (>= 0) mit hoechstens ``max_step`` Aenderung je
    Schritt, ueberall <= ``target`` -- also null, wo ``target`` null ist, und
    rechtzeitig vorher abgebaut (Vorwaerts- und Rueckwaertsdurchlauf)."""
    m = np.abs(np.asarray(target, dtype=float))
    out = m.copy()
    for i in range(1, len(out)):
        out[i] = min(out[i], out[i - 1] + max_step)
    for i in range(len(out) - 2, -1, -1):
        out[i] = min(out[i], out[i + 1] + max_step)
    return out


def sample_approach_offset(rng, share=config.APPROACH_OFFSET_SHARE,
                           range_m=config.APPROACH_OFFSET_RANGE_M,
                           yaw_range_deg=config.APPROACH_YAW_RANGE_DEG,
                           outlier_share=config.APPROACH_OFFSET_OUTLIER_SHARE,
                           outlier_max_m=config.APPROACH_OFFSET_OUTLIER_MAX_M,
                           outlier_yaw_max_deg=config.APPROACH_YAW_OUTLIER_MAX_DEG):
    """Versatz einer Episode: ``[dx, dy, 0, dyaw_rad]`` oder None (kein Versatz).

    EIN fester Fehler je Episode, der im Abstieg stetig auf 0 abklingt
    (:func:`approach_offset_profile`) -- kein Hin-und-her. Seitlich in
    beliebiger Richtung (gleichverteilt, auch schraeg), Drehung mit zufaelligem
    Vorzeichen. Je Groesse unabhaengig mit ``outlier_share`` ein Ausreisser
    (seitlich bis ``outlier_max_m``, Drehung bis ``outlier_yaw_max_deg``).
    ``yaw_range_deg`` None/(0, 0) = ohne Drehung.

    Zieht nur aus ``rng``, wenn ``share`` > 0 -- abgeschaltet bleibt die
    Zufallsfolge des Rauschens unveraendert.
    """
    if not share or share <= 0 or not range_m or max(range_m) <= 0:
        return None
    if rng.random() >= share:
        return None
    lo, hi = min(range_m), max(range_m)
    if outlier_share and outlier_max_m and outlier_max_m > hi and rng.random() < outlier_share:
        lo, hi = hi, outlier_max_m
    size = rng.uniform(lo, hi)
    angle = rng.uniform(0.0, 2.0 * np.pi)
    yaw = 0.0
    if yaw_range_deg and max(yaw_range_deg) > 0:
        ylo, yhi = min(yaw_range_deg), max(yaw_range_deg)
        if outlier_share and outlier_yaw_max_deg and outlier_yaw_max_deg > yhi \
                and rng.random() < outlier_share:
            ylo, yhi = yhi, outlier_yaw_max_deg
        yaw = np.radians(rng.uniform(ylo, yhi)) * (1.0 if rng.random() < 0.5 else -1.0)
    return np.array([size * np.cos(angle), size * np.sin(angle), 0.0, yaw])


def approach_rest(ideal, poses_noisy, free_m=None):
    """Groesster seitlicher Abstand (m) der gefahrenen Bahn zur Idealbahn auf
    den letzten ``free_m`` vor dem Greifen -- dort tauchen die Backen ums Objekt.
    ``free_m`` None = ``config.APPROACH_OFFSET_FREE_M`` zur Laufzeit (V6 setzt ihn um)."""
    if free_m is None:
        free_m = config.APPROACH_OFFSET_FREE_M
    d = distance_to_grasp(ideal)
    near = np.isfinite(d) & (d <= free_m)
    if not near.any():
        return 0.0
    diff = np.asarray(poses_noisy)[near, :2] - np.asarray(ideal.poses_quat)[near, :2]
    return float(np.max(np.linalg.norm(diff, axis=1)))


def approach_tip_clearance(ideal, poses_noisy, check, substeps=4):
    """Backen-Freiheit im Anflug (``config.APPROACH_TIP_CHECK``, Sim-Versuch V6).

    Solange die gefahrene Bahn seitlich oder gedreht neben der Idealbahn liegt
    (Versatz an den Backenspitzen > ``eps_m``: xy-Abstand + Drehwinkel x
    ``lever_m``), muessen die Backenspitzen (= TCP) auch nach ``overshoot_m``
    Nachlauf nach unten noch ``reserve_m`` ueber der Objektoberkante bleiben
    (``top_above_pick_m`` ueber dem Greifpunkt). Geprueft je Takt und linear
    dazwischen (``substeps``, wie der 60-Hz-Sollwertstrom).

    Rueckgabe: kleinster Freiraum (m) unter diesen Bedingungen -- negativ =
    verletzt, ``inf`` = kein Versatz unterhalb der Grenze.
    """
    d = distance_to_grasp(ideal)
    idx = np.flatnonzero(np.isfinite(d))
    if not len(idx):
        return np.inf
    k = int(idx[-1])
    ideal_q = np.asarray(ideal.poses_quat, dtype=float)
    noisy = np.asarray(poses_noisy, dtype=float)
    z_pick = ideal_q[min(k + 1, len(ideal_q) - 1), 2]
    f = np.linspace(0.0, 1.0, int(substeps), endpoint=False)
    a, b = np.arange(0, k), np.arange(1, k + 1)
    n = (noisy[a, None, :] * (1 - f)[None, :, None] + noisy[b, None, :] * f[None, :, None]).reshape(-1, 7)
    i = (ideal_q[a, None, :] * (1 - f)[None, :, None] + ideal_q[b, None, :] * f[None, :, None]).reshape(-1, 7)
    lat = np.linalg.norm(n[:, :2] - i[:, :2], axis=1)
    qn = n[:, 3:7] / np.linalg.norm(n[:, 3:7], axis=1, keepdims=True)
    qi = i[:, 3:7] / np.linalg.norm(i[:, 3:7], axis=1, keepdims=True)
    rot = 2.0 * np.arccos(np.clip(np.abs(np.sum(qn * qi, axis=1)), 0.0, 1.0))
    on = lat + float(check["lever_m"]) * rot > float(check["eps_m"])
    if not on.any():
        return np.inf
    free = (n[on, 2] - z_pick - float(check["overshoot_m"])) \
        - (float(check["top_above_pick_m"]) + float(check["reserve_m"]))
    return float(np.min(free))


def sample_noisy_poses(
    ideal,
    rng,
    sigma_pos=config.NOISE_TRANS_AMPLITUDE_M,
    sigma_rot=config.NOISE_ROT_AMPLITUDE_RAD,
    tau=config.NOISE_OU_TAU_S,
    limits=None,
    tau_smooth=config.NOISE_SMOOTH_TAU_S,
    approach_offset=None,
):
    """Erzeugt EINE verrauschte Posenbahn T_ist = T_soll + N_t.

    Rauschen: geglaetteter OU-Prozess (:class:`SmoothedOUProcess`), die
    asymmetrischen Grenzen wirken innerhalb des Prozesses.
    Daempfung: Trichter (Naehe zu einem Ankerpunkt) UND Dwell-Schritte
    (Greifer schliesst -- dort wird still gehalten, Rauschen = 0).
    ``approach_offset``: fester Versatz im Anflug, ``[dx, dy, dz]`` oder
    ``[dx, dy, dz, dyaw_rad]`` (Drehung um die Senkrechte), verteilt nach
    :func:`approach_offset_profile` (0 auf den letzten Zentimetern).
    """
    if limits is None:
        limits = NoiseLimits()
    dt = 1.0 / ideal.rate_hz
    ou_pos = SmoothedOUProcess(
        sigma_pos, tau, tau_smooth, dt, dims=3, rng=rng, lo=limits.lo, hi=limits.hi
    )
    ou_rot = SmoothedOUProcess(sigma_rot, tau, tau_smooth, dt, dims=3, rng=rng)

    scale = funnel_scale(ideal.dist_to_anchor)
    scale = np.where(ideal.dwell_mask, 0.0, scale)
    offset = np.zeros((len(scale), 3))
    yaw_offset = np.zeros(len(scale))
    if approach_offset is not None:
        values = np.asarray(approach_offset, dtype=float)
        profile = approach_offset_profile(ideal)
        # Tempo begrenzen und glaetten (config.APPROACH_*_RATE_*, _SMOOTH_S):
        # Anstieg liegt im Transfer, Gelenk 6 verkraftet keine spitzen Umkehrungen
        window = int(round(config.APPROACH_OFFSET_SMOOTH_S / dt))
        size = float(np.linalg.norm(values[:3]))
        if size > 0:
            lateral = smooth_limited(profile * size, config.APPROACH_OFFSET_RATE_M_S * dt, window)
            offset = (lateral / size)[:, None] * values[None, :3]
        if len(values) > 3 and values[3]:
            yaw_profile = approach_offset_profile(ideal, start_m=config.APPROACH_YAW_START_M)
            yaw_offset = np.sign(values[3]) * smooth_limited(
                yaw_profile * abs(values[3]), np.radians(config.APPROACH_YAW_RATE_DEG_S) * dt,
                window)

    noisy = ideal.poses_quat.copy()
    for i in range(len(noisy)):
        n_pos = ou_pos.step() * scale[i]
        n_rot = ou_rot.step() * scale[i]
        noisy[i, :3] = ideal.poses_quat[i, :3] + n_pos + offset[i]
        if yaw_offset[i]:
            # Anflug-Drehung um die Senkrechte (Basis-z)
            dq = geometry.quat_from_axis_angle(np.array([0.0, 0.0, 1.0]), float(yaw_offset[i]))
            noisy[i, 3:7] = geometry.quat_normalize(geometry.quat_multiply(dq, noisy[i, 3:7]))
        angle = float(np.linalg.norm(n_rot))
        if angle > 1e-12:
            dq = geometry.quat_from_axis_angle(n_rot / angle, angle)
            noisy[i, 3:7] = geometry.quat_normalize(
                geometry.quat_multiply(dq, noisy[i, 3:7])
            )
    return noisy


@dataclass
class TrajectoryPlan:
    """Fertige, geprueft ausfuehrbare Episode (Ergebnis der Generierung).

    Enthaelt bewusst BEIDE Bahnen (AP 0.9 Punkt 2): die verrauschte
    Ist-Bahn wird gefahren und ist die Observation, die ideale Soll-Bahn
    liefert die Action-Labels (t+1). Beide werden auch aufgezeichnet,
    damit die Label-Logik spaeter ueberpruef- und umlabelbar bleibt.
    """

    joints_ideal: np.ndarray  # (N, dof)
    joints_noisy: np.ndarray  # (N, dof)
    poses_ideal: np.ndarray  # (N, 7)
    poses_noisy: np.ndarray  # (N, 7)
    gripper: np.ndarray  # (N,)
    dwell_mask: np.ndarray  # (N,)
    rate_hz: float
    rejects: int = 0  # verworfene Samples bis zur gueltigen Bahn
    #: fester Versatz im Anflug (3,) oder None (config.APPROACH_OFFSET_*)
    approach_offset: object = None
    #: verworfene Samples je Grund, z. B. {"backen": 1} (leer ohne Verwerfen)
    reject_kinds: dict = None

    def __len__(self):
        return len(self.joints_ideal)


class PlanRejected(RuntimeError):
    """Auch nach NOISE_MAX_REJECTS Versuchen keine gueltige Bahn gefunden."""

    def __init__(self, message, reasons):
        super().__init__(message)
        self.reasons = reasons


def joint_speed(joints, rate_hz):
    """Hoechste Gelenkgeschwindigkeit einer Bahn -> (rad/s, Gelenk 0.., Schritt).

    Zwischen zwei 15-Hz-Schritten interpoliert servo_j linear
    (bc/servo.py), die Geschwindigkeit ist dort also konstant
    |q[i+1] - q[i]| * rate. Genau das prueft der ServoGuard im Adapter.
    """
    joints = np.asarray(joints, dtype=float)
    if len(joints) < 2:
        return 0.0, 0, 0
    speed = np.abs(np.diff(joints, axis=0)) * float(rate_hz)
    step, joint = np.unravel_index(int(np.argmax(speed)), speed.shape)
    return float(speed[step, joint]), int(joint), int(step) + 1


def solve_ideal(kin, collision_model, ideal, seed_joints, collision_stride=1,
                max_joint_speed=config.PLAN_MAX_JOINT_SPEED_RADS):
    """Ideale Bahn per IK loesen und gegen das Kollisionsmodell pruefen.

    Schlaegt DAS fehl, sind die Wegpunkte selbst unbrauchbar -- ein neues
    Rauschsample hilft nicht (:class:`PlanRejected`).
    """
    try:
        joints_ideal = kin.solve_path(
            ideal.poses_quat, seed_joints, fixed_joints=ideal.joints
        )
    except IKFailure as exc:
        raise PlanRejected(
            "Bereits die IDEALE Bahn ist nicht loesbar (Schritt %s: %s) -- "
            "Wegpunkte pruefen." % (exc.index, exc),
            reasons=[("ideal_ik", exc)],
        ) from exc
    speed, joint, step = joint_speed(joints_ideal, ideal.rate_hz)
    if max_joint_speed and speed > max_joint_speed:
        raise PlanRejected(
            "Bereits die IDEALE Bahn ist zu schnell: Gelenk %d %.2f rad/s bei "
            "Schritt %d (Grenze %.2f) -- Wegpunkte in Singularitaetsnaehe? "
            "Planer-Tempo senken oder Punkte pruefen."
            % (joint + 1, speed, step, max_joint_speed),
            reasons=[("ideal_speed", speed)],
        )
    ideal_violations = collision_model.check_path(
        kin.robot, joints_ideal, stride=collision_stride
    )
    if ideal_violations:
        raise PlanRejected(
            "Bereits die IDEALE Bahn verletzt das Kollisionsmodell -- "
            "Wegpunkte pruefen: %s" % ideal_violations[0],
            reasons=[("ideal_collision", ideal_violations)],
        )
    return joints_ideal


def generate_plan(
    kin,
    collision_model,
    ideal,
    seed_joints,
    rng=None,
    max_rejects=config.NOISE_MAX_REJECTS,
    limits=None,
    collision_stride=1,
    noise_scale=1.0,
    joints_ideal=None,
    max_joint_speed=config.PLAN_MAX_JOINT_SPEED_RADS,
    approach_offset=None,
    path_check=None,
):
    """Vollstaendige Episodengenerierung mit Rejection Sampling (AP 2.4).

    ``path_check``: optionale zusaetzliche Pruefung der verrauschten Bahn,
    ``path_check(poses_noisy) -> None`` (ok) oder ein Grund (str) -- dann wird
    neu gezogen (Grund ``pfad``; Sim-Versuch V7, bc/korrektur_halt.py).

    1. Ideale Bahn einmalig per IK loesen (Warm-Start, vier Absicherungen)
       und gegen das Kollisionsmodell pruefen -- schlaegt DAS fehl, sind
       die Wegpunkte selbst unbrauchbar (kein Resampling sinnvoll).
    2. Verrauschte Bahn samplen, loesen, pruefen; bei IKFailure oder
       Kollisionsverletzung neu samplen (max. ``max_rejects`` Versuche).

    ``kin``: :class:`bc.kinematics.Kinematics`;
    ``collision_model``: :class:`bc.collision.CollisionModel`.
    ``noise_scale``: Faktor auf beide Rauschamplituden -- 0 ergibt eine
    Referenzfahrt exakt auf der idealen Bahn (Diagnose, z. B. Folgeverhalten
    des Controllers ohne Rauscheinfluss).
    ``max_joint_speed``: verrauschte Bahnen, deren Gelenke schneller
    wuerden, werden verworfen (``config.PLAN_MAX_JOINT_SPEED_RADS``, unter
    dem ServoGuard) -- None schaltet ab.
    ``joints_ideal``: Ergebnis von :func:`solve_ideal` fuer dieselbe ``ideal``
    -- dann entfaellt Schritt 1. Fuer Wiederholungen derselben Lage: die
    ideale Bahn ist jedes Mal dieselbe, und an der Anlage kostet jeder
    IK/FK-Schritt einen Aufruf an die Steuerung.
    ``approach_offset``: fester Versatz im Anflug (:func:`sample_approach_offset`).
    Jede Bahn -- mit oder ohne -- muss auf den letzten Zentimetern vor dem
    Greifen innerhalb ``config.APPROACH_REST_MAX_M`` der Idealbahn liegen.
    """
    rng = rng if rng is not None else np.random.default_rng()

    if joints_ideal is None:
        joints_ideal = solve_ideal(kin, collision_model, ideal, seed_joints,
                                   collision_stride=collision_stride,
                                   max_joint_speed=max_joint_speed)

    reasons = []
    for attempt in range(max_rejects):
        poses_noisy = sample_noisy_poses(
            ideal,
            rng,
            sigma_pos=config.NOISE_TRANS_AMPLITUDE_M * noise_scale,
            sigma_rot=config.NOISE_ROT_AMPLITUDE_RAD * noise_scale,
            limits=limits,
            approach_offset=approach_offset,
        )
        rest = approach_rest(ideal, poses_noisy)
        if rest > config.APPROACH_REST_MAX_M:
            reasons.append(("anflug", "%.1f mm neben der Idealbahn vor dem Greifen" % (1e3 * rest)))
            continue
        tip_check = getattr(config, "APPROACH_TIP_CHECK", None)
        if tip_check:
            frei = approach_tip_clearance(ideal, poses_noisy, tip_check)
            if frei < 0:
                reasons.append(("backen", "Backen %.1f mm zu tief ueber der Objektoberkante, solange "
                                "noch versetzt" % (-1e3 * frei)))
                continue
        if path_check is not None:
            grund = path_check(poses_noisy)
            if grund:
                reasons.append(("pfad", grund))
                continue
        try:
            joints_noisy = kin.solve_path(poses_noisy, seed_joints)
        except IKFailure as exc:
            reasons.append(("ik", exc))
            continue

        # Vor der Kollisionspruefung: kostet keinen Aufruf an die Steuerung
        if max_joint_speed:
            speed, joint, step = joint_speed(joints_noisy, ideal.rate_hz)
            if speed > max_joint_speed:
                reasons.append(("speed", "Gelenk %d %.2f rad/s bei Schritt %d"
                                % (joint + 1, speed, step)))
                continue

        violations = collision_model.check_path(
            kin.robot, joints_noisy, stride=collision_stride
        )
        if violations:
            reasons.append(("collision", violations[0]))
            continue

        return TrajectoryPlan(
            joints_ideal=joints_ideal,
            joints_noisy=joints_noisy,
            poses_ideal=ideal.poses_quat,
            poses_noisy=poses_noisy,
            gripper=ideal.gripper,
            dwell_mask=ideal.dwell_mask,
            rate_hz=ideal.rate_hz,
            rejects=attempt,
            approach_offset=None if approach_offset is None else [float(v) for v in approach_offset],
            reject_kinds={kind: sum(1 for r in reasons if r[0] == kind) for kind in {r[0] for r in reasons}},
        )

    raise PlanRejected(
        "Keine gueltige verrauschte Bahn nach %d Versuchen. Letzte Gruende: %s"
        % (max_rejects, ["%s (%s)" % (r[0], str(r[1])[:80]) for r in reasons[-3:]]),
        reasons=reasons,
    )
