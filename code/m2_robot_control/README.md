# M2 – Robotersteuerung (Neura LARA)

Planung: [plan/03_modul2_robotersteuerung.md](../../plan/03_modul2_robotersteuerung.md) ·
**Einstieg: [ANLEITUNG_NEURA.md](ANLEITUNG_NEURA.md)** (Laptop einrichten, verbinden, erste Bewegung)

| Datei | Inhalt |
|---|---|
| `robot.py` | `NeuraRobot` (echte Implementierung über NeuraPy, inkl. `jog` für kleine Relativschritte und `point_at`/`retreat` für den Zeigetest), `MockRobot`, Umrechnung mm/° ↔ m/rad, Greifsequenz |
| `robot_check.py` | Kommandozeilen-Werkzeug: `info`, `pose`, `home`, `gripper`, `axes`, `jog`, `pick-test`, `calib` (Kalibrierung Arbeitsbereich → Roboter), `point` (Zeigetest ohne Greifen) (jeweils auch `--sim`) |
| `fake_neura_server.py` | Simulator der Neura-Steuerung (gleiches JSON-Protokoll, Port 65432) für Tests ohne Roboter |
| `vendor/neurapy/robot.py` | Unveränderter NeuraPy-Windows-Client v5.0.8 aus der Neura-Lieferung |
| `tests/` | Tests gegen den Simulator (über den echten Client); `test_neura_vm.py` gegen die offizielle Neura-VM (nur mit `NEURA_VM=1`, siehe ANLEITUNG §8b) |

Neura-Dokumentation: [docs/neura/](../../docs/neura/)

## Greifsequenz (`NeuraRobot.pick`)

1. Greifer öffnen (`release`)
2. Gelenkbewegung (IK) auf Vorposition = Ziel + `approach_height_mm`
3. Linear absenken mit `approach_speed_mps`
4. `grasp`, `grip_wait_s` warten
5. Linear anheben

Greiforientierung = Orientierung von `Home` (Werkzeug nach unten), um die Basis-z-Achse gedreht
um θ des Bauteils + `gripper_angle_offset_deg` (90° → Finger greifen über die schmale Seite).
Vorzeichen von yaw bei roll = 180°: in der Neura-VM bestätigt (+rz = gegen den Uhrzeigersinn von oben,
2026-10-06); **am echten Roboter noch prüfen.**

## Noch offen

- IP, Werkzeugname und Betriebsartwechsel am echten Roboter bestätigen
- Posen `inspection`, `bin_good`, `bin_bad` teachen, `limits_mm` anpassen
- Greifer-Rückmeldung (Teil gegriffen?) – API bietet `io`/Tool-Eingänge, noch nicht genutzt
- Kalibrierung (`calib`) und Zeigetest (`point`) am echten Aufbau durchführen
