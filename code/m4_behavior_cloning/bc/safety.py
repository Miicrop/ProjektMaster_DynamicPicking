"""Watchdog und Geofencing (AP 4.2).

NeuraPy bietet keine 3D-Schutzraeume -- die Ueberwachung laeuft vollstaendig
hier: ein Watchdog prueft zyklisch eine Liste von Checks und loest bei der
ersten Verletzung den Software-Not-Halt aus (``robot.emergency_stop()``).

Der Watchdog laeuft in einem EIGENEN Thread, damit eine blockierende oder
verzoegerte Policy-Inferenz den Stopp nicht verzoegern kann. Fuer
deterministische Tests existiert ``run_once()`` ohne Thread.

WICHTIG: Software-Stopp ersetzt KEINEN zertifizierten Hardware-Not-Aus.
Ein physischer Not-Halt muss waehrend aller Laeufe in Reichweite sein.
"""

import threading
import traceback

import numpy as np

from . import config


class Watchdog(object):
    """Prueft zyklisch Checks und loest den Not-Halt aus.

    ``checks``: Liste von Callables ohne Argumente. Rueckgabe None/leer =
    in Ordnung; alles andere gilt als Verletzung (und wird protokolliert).
    Wirft ein Check selbst eine Exception, gilt das ebenfalls als
    Verletzung -- ein kaputter Waechter darf nie "gruen" bedeuten.
    """

    def __init__(self, robot, checks, clock, period_s=config.SAFETY_CHECK_PERIOD_S):
        self.robot = robot
        self.checks = list(checks)
        self.clock = clock
        self.period_s = period_s
        self.tripped = None  # erste Verletzung (fuer Diagnose/Episode)
        self._thread = None
        self._running = threading.Event()

    # -- Kernpruefung ------------------------------------------------------

    def run_once(self):
        """Fuehrt alle Checks einmal aus. Rueckgabe: Verletzung oder None."""
        for check in self.checks:
            try:
                result = check()
            except Exception as exc:  # kaputter Check == Verletzung
                result = "check-exception: %s\n%s" % (exc, traceback.format_exc())
            if result:
                self.tripped = result
                self.robot.emergency_stop()
                return result
        return None

    # -- Thread-Betrieb ----------------------------------------------------

    def start(self):
        self._running.set()
        self._thread = threading.Thread(
            target=self._loop, name="safety-watchdog", daemon=True
        )
        self._thread.start()
        return self

    def _loop(self):
        while self._running.is_set():
            if self.run_once() is not None:
                return  # Not-Halt ausgeloest, Watchdog-Aufgabe erledigt
            self.clock.sleep(self.period_s)

    def stop(self):
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


class CameraStale(RuntimeError):
    """Ein Kamerabild ist zu lange nicht mehr neu -- die Policy saehe ein Standbild."""


class FrameAgeGuard(object):
    """Erkennt eingefrorene Kamerabilder in der Inferenz (Anwender 2026-11-11).

    ``capture.ThreadedCapture.latest()`` liefert bei einem Kamerafehler
    stillschweigend weiter das letzte Bild. Der Recorder faengt das ueber das
    Latenzbudget ab (Episode verworfen); die Inferenz wuerde dagegen auf einem
    Standbild weiterfahren -- etwa dorthin, wo das Objekt im alten Bild lag.

    Je Takt :meth:`check` mit den Frames (Name -> Frame oder None) und der
    aktuellen Zeit derselben Uhr, mit der die Kameras stempeln. Ist ein Bild
    ``max_age_s`` aelter, zaehlt der Takt als schlecht; nach ``max_steps``
    schlechten Takten in Folge wirft er :class:`CameraStale`. Ein einzelnes
    verspaetetes Bild bricht nichts ab.
    """

    def __init__(self, max_age_s=config.INFER_MAX_FRAME_AGE_S,
                 max_steps=config.INFER_FRAME_AGE_STEPS):
        if max_age_s <= 0 or int(max_steps) < 1:
            raise ValueError("max_age_s > 0 und max_steps >= 1 noetig")
        self.max_age_s = float(max_age_s)
        self.max_steps = int(max_steps)
        self.bad_steps = 0
        self.worst_age_s = 0.0

    def reset(self):
        self.bad_steps = 0
        self.worst_age_s = 0.0

    def check(self, frames, now):
        """Rueckgabe: groesstes Bildalter (s). Wirft CameraStale nach zu vielen Takten."""
        ages = {}
        for name, frame in frames.items():
            ages[name] = float("inf") if frame is None else float(now) - float(frame.timestamp)
        oldest = max(ages, key=ages.get) if ages else None
        age = ages[oldest] if oldest is not None else 0.0
        if age != float("inf"):
            self.worst_age_s = max(self.worst_age_s, age)
        if age > self.max_age_s:
            self.bad_steps += 1
            if self.bad_steps >= self.max_steps:
                raise CameraStale(
                    "kamera %s: neuestes Bild %s alt, %d Takte in Folge ueber %.0f ms"
                    % (oldest, "nie geliefert" if age == float("inf") else "%.0f ms" % (1e3 * age),
                       self.bad_steps, 1e3 * self.max_age_s))
        else:
            self.bad_steps = 0
        return age


def geofence_check(robot, collision_model):
    """Baut einen Watchdog-Check aus dem Kollisionsmodell (AP 4.2).

    Dieselben Quader wie bei der Offline-Vorabpruefung (AP 2.4) -- online
    wiederverwendet: aktuelle Gelenkstellung lesen, Stuetzpunkte gegen die
    Quader pruefen.
    """

    def check():
        state = robot.read_state()
        violations = collision_model.check_positions(
            collision_model.positions_for(robot, state.joints)
        )
        return violations or None

    return check


class TargetRejected(RuntimeError):
    """Ein Ziel der Policy wuerde ins Kollisionsmodell fuehren -- nicht gesendet."""


class ArmStalled(RuntimeError):
    """Der Arm steht, das Ziel nicht -- Not-Aus am Handbediengeraet oder
    toter Steuerkanal. Die Fahrt endet, statt weiter Ziele zu senden."""


class StallGuard(object):
    """Erkennt "Arm steht, Ziel nicht" (Anwender 2026-11-16).

    Der Not-Aus am Handbediengeraet haelt den Arm an, ohne dass servo_j einen
    Fehler meldet. Ohne diese Pruefung sendet die Fahrt weiter Ziele, die
    Luecke zur Messung waechst, und nach dem Entriegeln laege ein altes Ziel
    an. ``check`` je Takt mit der gemessenen Stellung und dem gesendeten Ziel;
    wirft :class:`ArmStalled` nach ``steps`` Takten in Folge, in denen sich
    die Messung um weniger als ``move_rad`` bewegt hat und das Ziel mehr als
    ``gap_rad`` entfernt ist. Steht der Arm AM Ziel (Dwell, Zoegern der
    Policy), loest nichts aus.
    """

    def __init__(self, move_rad=config.STALL_MOVE_RAD, gap_rad=config.STALL_GAP_RAD,
                 steps=config.STALL_STEPS):
        self.move_rad = float(move_rad)
        self.gap_rad = float(gap_rad)
        self.steps = int(steps)
        self.reset()

    #: "Seit dem Start unbewegt": Messrauschen der Anlage ~2e-4 rad (Fahrten vom
    #: 24.11.); eine echte Anfahrt ist nach 5 Takten weit darueber
    NEVER_MOVED_RAD = 2e-3

    def never_moved(self, measured):
        """Seit dem ersten Takt dieser Fahrt unbewegt?"""
        return self._first is not None and float(
            np.max(np.abs(np.asarray(measured, dtype=float) - self._first))) < self.NEVER_MOVED_RAD

    def reset(self):
        self._prev = None
        self._first = None
        self.count = 0
        self.since = None      # erster Takt der laufenden Folge (Zaehler der Aufrufe)
        self._calls = 0
        return self

    def check(self, measured, target):
        """Rueckgabe: Takte in Folge "steht". Wirft ArmStalled an der Grenze."""
        measured = np.asarray(measured, dtype=float)
        target = np.asarray(target, dtype=float)[:len(measured)]
        moved = (float("inf") if self._prev is None
                 else float(np.max(np.abs(measured - self._prev))))
        gap = float(np.max(np.abs(target - measured)))
        self._prev = measured
        if self._first is None:
            self._first = measured
        if moved < self.move_rad and gap > self.gap_rad:
            if self.count == 0:
                self.since = self._calls
            self.count += 1
        else:
            self.count, self.since = 0, None
        self._calls += 1
        if self.count >= self.steps and self.never_moved(measured):
            # Befund 2026-11-24: am Anfang einer Fahrt, Arm seit dem Einschalten
            # unbewegt -- die Steuerung nahm die Servo-Sollwerte nicht an (15x
            # in Fahrt 1 ohne Experte). Text beginnt mit "arm steht" (Auswertungen)
            raise ArmStalled(
                "arm steht (faehrt nicht los): seit dem Einschalten des Servo-Interface "
                "keine Bewegung, Ziel %.3f rad entfernt -- die Steuerung nimmt die "
                "Servo-Sollwerte nicht an (PTP-Fahrten davor zaehlen nicht, die laufen "
                "ueber move_joint), oder Not-Aus schon vor dem Start. Bleibt das im "
                "naechsten Lauf so: Steuerungsreset (half am 24.11. und 25.11.), dann neu "
                "verbinden; Zustand der Steuerung steht unter STEUERUNG im Protokoll"
                % gap)
        if self.count >= self.steps:
            raise ArmStalled(
                "arm steht: %d Takte ohne Bewegung (< %.0e rad), Ziel %.3f rad entfernt "
                "-- Not-Aus am Handbediengeraet oder Steuerkanal weg? Anlage pruefen, "
                "Not-Aus erst nach dem Ende der Fahrt entriegeln"
                % (self.count, self.move_rad, gap))
        return self.count


def check_target(collision_model, robot, joints, previous=None, lookahead=0.0):
    """Vorabpruefung eines Ziels VOR dem Senden (Inferenz, Analyse 2026-11-11).

    Der Watchdog prueft die GEMESSENE Stellung, reagiert also erst, wenn der
    Arm schon dort ist (bei 20 Hz plus ~0,1 s Stopp einige mm zu spaet). Hier
    wird das Ziel selbst geprueft: ein verbotenes Ziel geht gar nicht erst
    raus. Wirft :class:`TargetRejected` mit der ersten Verletzung.

    ``previous`` + ``lookahead`` (Anlage 2026-11-17): zusaetzlich das um
    ``lookahead`` Takte linear verlaengerte Ziel ``joints + lookahead *
    (joints - previous)`` pruefen. Nach einem abgelehnten Ziel laeuft der Arm
    noch nach (gemessen bis 7,5 mm bei 150 mm/s, ~50 ms) -- so wird schon
    abgelehnt, solange der Nachlauf bei der aktuellen Geschwindigkeit noch
    vor der Grenze endet.
    """
    joints = np.asarray(joints, dtype=float)
    candidates = [("", joints)]
    if previous is not None and lookahead > 0:
        ahead = joints + float(lookahead) * (joints - np.asarray(previous, dtype=float)[:len(joints)])
        candidates.append((" (Nachlauf)", ahead))
    for tag, q in candidates:
        violations = collision_model.check_positions(collision_model.positions_for(robot, q))
        if violations:
            v = violations[0]
            raise TargetRejected("kollision vorab%s: %s an %s (Rest %.0f mm)"
                                 % (tag, v.frame, v.box, 1e3 * v.clearance))
