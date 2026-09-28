# 03 – Modul 2: Robotersteuerung (Neura)

**Verantwortlich:** Person 2 · **Code:** `code/m2_robot_control/` · **Interface:** `RobotController`

> **Einstieg:** [code/m2_robot_control/ANLEITUNG_NEURA.md](../code/m2_robot_control/ANLEITUNG_NEURA.md) –
> Laptop einrichten, verbinden, erste Bewegung, Posen teachen, Fehlersuche.
>
> Roboter: Neura **LARA**, 6 Achsen, Software v5.0.8. API: **NeuraPy** – ein dünner JSON-über-TCP-Client
> (Port 65432), Posen `[x, y, z, roll, pitch, yaw]` in m/rad. Wichtig laut Doku: vor Bewegungen
> `init_program()`, am Ende `stop()`. Doku: [docs/neura/](../docs/neura/README.md).
> Das GitHub-Repo mit den bisherigen Tests liegt noch nicht vor.

## Aufgabe

- `ObjectPose` entgegennehmen und das Bauteil **sicher greifen**.
- Bauteil an der **Prüfposition** ablegen und den Sichtbereich der Seitenkamera freigeben.
- Nach der Prüfung Bauteil wieder aufnehmen und auf **Ablage GUT** oder **Ablage SCHLECHT** legen.

## Interface

| Methode | Beschreibung |
|---|---|
| `connect()` / `disconnect()` | Verbindung zur Steuerung, Servo an/aus |
| `home()` | Sichere Ausgangsposition (außerhalb des Kamerabilds) |
| `pick(pose: ObjectPose)` | Greifsequenz an beliebiger Pose |
| `place(target: RobotTarget)` | Ablegesequenz an benannter Pose |
| `stop()` | Sofortiger Stopp (Software), wird im `ERROR`-Zustand aufgerufen |

## Greifsequenz `pick()`

1. Greifer öffnen.
2. **Vorposition** anfahren: (x, y, z + Sicherheitsabstand), TCP-Rotation um z = θ + Greifer-Offset (PTP-Bewegung).
3. Linear auf Greifhöhe absenken (LIN, reduzierte Geschwindigkeit).
4. Greifer schließen, Greiferzustand prüfen (Teil vorhanden? – noch nicht umgesetzt).
5. Linear auf Vorposition anheben.

`place()` analog: Vorposition → absenken → öffnen → anheben.

## Definierte Posen (in `config/system.yaml`)

- `home` – Ruheposition außerhalb der Kamerabilder
- `inspection` – Ablage für die Sichtprüfung (Lage des Teils reproduzierbar, ggf. mechanischer Anschlag)
- `bin_good`, `bin_bad` – Sortierablagen

Die Posen werden am realen Roboter geteacht und in die Config übernommen.

## Sicherheit

- Reduzierte Geschwindigkeit/Beschleunigung im Testbetrieb (konfigurierbar).
- Software-Arbeitsraumgrenzen: Posen außerhalb des erlaubten Quaders werden abgelehnt (`RobotError`).
- Plausibilitätsprüfung der `ObjectPose` (Konfidenz, Lage im Arbeitsbereich).
- Hardware-Not-Halt immer in Reichweite; Betrieb nur unter Aufsicht.

## Kalibrierung (gemeinsam mit M1)

- Roboter-TCP nacheinander auf die vier Marker-Mittelpunkte setzen → `robot_check calib` berechnet `T_ws→robot` per Least Squares (`common.transforms.fit_workspace_to_robot`) samt Restfehler je Marker und gibt die Config-Zeilen aus. Vorgehen in `ANLEITUNG_NEURA.md` Abschnitt 7a.
- Prüfung mit dem Zeigetest `robot_check point` (Abschnitt 7b): Greifer fährt über das erkannte Bauteil, greift nicht; gemessener Versatz → `logs/point_tests.csv` (Positionsgenauigkeit für die Evaluation).
- Greifer-Offset (Winkel zwischen Greiferbacken und Bauteil-Hauptachse) bestimmen.

## Umsetzung (Stand 2026-09-26)

| Schritt | NeuraPy-Aufruf |
|---|---|
| Verbinden | `Robot()` (IP über `SOCKET_ADDRESS`, setzt `NeuraRobot` aus der Config) |
| Vorbereiten | `power_on()`, ggf. `switch_to_automatic_mode()`, `set_tool()`, `set_override()`, `set_joint_speed()`, `init_program()` |
| Große Bewegung | `compute_inverse_kinematics()` + `move_joint()` (PTP) |
| Anfahren/Abheben | `move_linear(target_pose=[start, ziel], speed=…)` (LIN) |
| Greifer | `grasp()` / `release()` |
| Ende / Fehler | `stop()` – beendet das Programm auf der Steuerung; weitere Bewegungen erst nach `reset()` (= erneut `init_program()`), bewusst nicht automatisch |

- `fake_neura_server.py` simuliert die Steuerung (gleiches Protokoll). Die Tests laufen über den
  **unveränderten** Neura-Client, dadurch ist der komplette Codepfad ohne Roboter prüfbar.
- `robot_check.py` (`python -m m2_robot_control …`) für die schrittweise Inbetriebnahme (`info` → `home` → `gripper` → `axes`/`jog` → `pose` → `calib` → `point` → `pick-test`).
- GUI-Tab **M2 Roboter**: dieselben Schritte per Knopf, Posen teachen/anfahren, Draufsicht, STOPP.

## Aufgaben

- [x] Neura-Doku sichten, API-Aufrufe für PTP/LIN/Greifer dokumentieren
- [ ] GitHub-Repo mit bisherigen Tests sichten (liegt noch nicht vor)
- [x] `NeuraRobot(RobotController)` implementieren
- [x] Simulator der Steuerung + Tests
- [x] Anleitung für die Inbetriebnahme vom Laptop
- [ ] Am echten Roboter: IP, Werkzeug, Betriebsartwechsel verifizieren (`robot_check info`)
- [ ] Posen teachen und in Config eintragen
- [ ] Greif-/Ablegesequenz mit reduzierter Geschwindigkeit testen (`robot_check pick-test`)
- [ ] Greiforientierung prüfen (yaw-Konvention bei roll = 180°, Greifer-Offset)
- [x] Arbeitsraumgrenzen und Stopp implementieren
- [ ] Greifer-Rückmeldung (Teil gegriffen?) auswerten
- [~] Kalibrierung Arbeitsbereich → Roboter mit M1: Skript (`calib`) und Zeigetest (`point`) fertig, am Aufbau durchführen
- [ ] Wiederholgenauigkeit an der Prüfposition messen (wichtig für M3)
