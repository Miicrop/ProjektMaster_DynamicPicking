# 03 – Modul 2: Robotersteuerung (Neura)

**Verantwortlich:** Person 2 · **Code:** `code/m2_robot_control/` · **Interface:** `RobotController`
Aufgaben: [06_offen.md](06_offen.md)

> **Einstieg:** [code/m2_robot_control/ANLEITUNG_NEURA.md](../code/m2_robot_control/ANLEITUNG_NEURA.md)
> erklärt, wie man den Laptop einrichtet, verbindet und die erste Bewegung fährt. Sie beschreibt auch
> das Teachen von Posen, die Kalibrierung, den Zeigetest und die Fehlersuche.
>
> Roboter: Neura **LARA**, 6 Achsen, Software v5.0.8, IP **192.168.2.13** (die .20 auf dem Sockel
> ist falsch). API: **NeuraPy**, ein dünner JSON-über-TCP-Client (Port 65432), Posen
> `[x, y, z, roll, pitch, yaw]` in m/rad. Vor Bewegungen `init_program()`, am Ende `stop()`.
> Doku: [docs/neura/](../docs/neura/README.md).

## Aufgabe

- `ObjectPose` entgegennehmen und das Bauteil **sicher greifen**.
- Bauteil an der **Prüfposition** ablegen und den Sichtbereich der Seitenkamera freigeben.
- Nach der Prüfung das Bauteil wieder aufnehmen und auf **Ablage GUT** oder **Ablage SCHLECHT** legen.
- Greift M4 (`--grasper bc`), übernimmt M2 erst am Übergabepunkt über der Prüfung: `reset()`, dann ablegen.

## Interface

| Methode | Beschreibung |
|---|---|
| `connect()` / `disconnect()` | Verbindung zur Steuerung. Prüft das Werkzeug (TCP ±1 mm), sonst keine Bewegung |
| `home()` | Sichere Ausgangsposition außerhalb des Kamerabilds |
| `pick(pose: ObjectPose)` | Greifsequenz an beliebiger Pose |
| `place(target: RobotTarget)` | Ablegesequenz an einer benannten Pose |
| `stop()` / `reset()` | Sofortiger Stopp (Software) im `ERROR`-Zustand. Danach werden Bewegungen abgelehnt, bis `reset()` (erneut `init_program()`) aufgerufen wird. Das geschieht bewusst nicht automatisch |

## Greifsequenz `pick()`

1. Greifer öffnen.
2. Vorposition 80 mm über dem Ziel anfahren, TCP-Rotation um z = Home + θ + **113°** (PTP).
3. Linear absenken: schnell (0,10 m/s) bis 20 mm über dem Ziel, den Rest langsam (0,03 m/s).
4. Greifer schließen. Eine Rückmeldung, ob ein Teil gegriffen wurde, wird noch nicht ausgewertet.
5. Auf demselben Weg zurück: erst langsam, dann schnell auf die Vorposition.

`place()` läuft analog: Vorposition → absenken → öffnen → anheben. Beim Prüfen gibt es keinen
Home-Umweg. Der Roboter wartet auf Anfahrhöhe über der Prüfvorrichtung, wo der Greifer nicht im
Bild der Seitenkamera ist.

Greifer-Offset 113° = 90° + 23°, weil der Greifer um 23° verdreht montiert ist. An den Ablagen ist
rz = −157° (Home + 23°). Das Teil liegt dort mit der langen Seite entlang der Marker-Kante 0–3.

## Werkzeug und Greifer

- Zimmer MATCH LWR50L-23-00004-A mit Robotermodul LWR50F-13-05-A, Standardbacken (passen für 40 mm).
  Datenblätter und CAD liegen in `docs/greifer/`.
- Werkzeug in der Steuerung: **„ZimmerLWR50“**, TCP 197,5 mm. Soll-Last 1,75 kg, Schwerpunkt
  z ≈ 81 mm (ANLEITUNG_NEURA Abschnitt 4).
- `gripper_enabled` schaltet Öffnen/Schließen. In der Neura-VM ist es immer aus.

## Posen (`config/system.yaml`, TCP im Basis-KS, mm/°)

| Pose | x | y | z | rz |
|---|---|---|---|---|
| `home` | 420,0 | 0,0 | 237,0 | 180 |
| `inspection` (Prüfvorrichtung, Fläche 38 mm über der Platte) | 520,8 | 199,6 | 42,0 | −157 |
| `bin_good` | 299,7 | 185,4 | 4,0 | −157 |
| `bin_bad` | 297,7 | 319,4 | 3,0 | −157 |

Geteacht werden die Posen mit `robot_check teach` oder im Tab M2.

## Sicherheit

- Reduzierte Geschwindigkeit (`override` 0,2 im Testbetrieb).
- Software-Arbeitsraumgrenzen `limits_mm`: Posen außerhalb werden abgelehnt (`RobotError`).
- Plausibilitätsprüfung der `ObjectPose` (Konfidenz, Lage im Arbeitsbereich).
- Hardware-Not-Halt immer in Reichweite, Betrieb nur unter Aufsicht.

## Kalibrierung (gemeinsam mit M1)

- Der Roboter-TCP wird nacheinander auf die vier Markermitten gesetzt. `robot_check calib` berechnet
  daraus `workspace_to_robot` per Least Squares (`common.transforms.fit_workspace_to_robot`), mit
  Restfehler je Marker. Ab 3 mm RMS gibt es eine Warnung. Aktuell: 0,35°, [205,1, −319,7] mm,
  Tisch z 2,1 mm.
- Der Zeigetest `robot_check point` fährt über das erkannte Bauteil, ohne zu greifen. Der Versatz
  landet in `logs/point_tests.csv`.

## Umsetzung

| Schritt | NeuraPy-Aufruf |
|---|---|
| Verbinden | `Robot()` (IP über `SOCKET_ADDRESS`, setzt `NeuraRobot` aus der Config) |
| Vorbereiten | `power_on()`, ggf. `switch_to_automatic_mode()`, `set_tool()`, `set_override()`, `set_joint_speed()`, `init_program()` |
| Große Bewegung | `compute_inverse_kinematics()` + `move_joint()` (PTP) |
| Anfahren/Abheben | `move_linear(target_pose=[start, ziel], speed=…)` (LIN) |
| Greifer | `grasp()` / `release()` |
| Ende / Fehler | `stop()` |

Testen lässt sich das in drei Stufen:

1. `fake_neura_server.py` simuliert die Steuerung mit demselben Protokoll. Die Tests laufen über den
   unveränderten Neura-Client.
2. Die **Neura-VM** (VirtualBox) betreibt die echte Steuerungssoftware ohne Roboter.
3. Danach kommt die Anlage.

Schrittweise Inbetriebnahme mit `python -m m2_robot_control …`:
`info` → `home` → `gripper` → `axes`/`jog` → `pose`/`teach` → `calib` → `point` → `pick-test`.
Der GUI-Tab **M2 Roboter** bietet dieselben Schritte per Knopf, dazu Joggen, Posen und die
Draufsicht. Der Haken *Ohne Rückfrage joggen* ist nur fürs Joggen gedacht und wird nicht gespeichert.
