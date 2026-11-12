# Behavior Cloning — LARA 5 (Diffusion Policy)

Lokale, autarke Pipeline für Imitation Learning am Neura LARA 5:
automatisierte Datenaufzeichnung mit Action Noise Injection, Training
einer Diffusion Policy, Live-Inferenz.

* **Anforderungen und Entscheidungen:** [Requierments/requierments.md](Requierments/requierments.md)
* **Kameras — Inbetriebnahme, Hardware, Mechanik:** [Dokumentation/Kamera-Inbetriebnahme.md](Dokumentation/Kamera-Inbetriebnahme.md)
* **Übernahme ins Repo der Gruppe, Reiter in deren GUI:** [INTEGRATION.md](INTEGRATION.md)

## Architektur (AP 0)

Hardware ist **ausschließlich über Ports/Adapter** angebunden — Roboter
und Kameras sind austauschbar, und die gesamte Logik läuft ohne Hardware:

```
apps/        teach | record | train | infer | eval        (CLI-Einstiege)
bc/          Pipeline: hardwarefrei, importiert nie neurapy/gxipy
bc/ports.py  RobotPort | CameraPort | TeleopPort | ClockPort (ABCs)
bc/adapters/ neura, sim_robot, cam_daheng, cam_uvc, cam_sim, teleop_*
tests/       Unit- + Contract-Tests (sim heute, neura/daheng am Gerät)
tools/       check_gpu, check_ik, check_cameras, selftest
```

Stand 2026-11-11: Aufnahme (Anlage, automatische Lagen, Zurücklegen),
Export (LeRobot 0.6.1), Training (Diffusion Policy) und Inferenz
(`apps/infer.py`, auch aus dem Gruppenablauf über
`code/orchestrator/m4_grasper.py`) laufen. Die ArUco-Rektifizierung
(`bc/rectify.py`) ist **nicht** Teil der Pipeline (Entscheidung revidiert,
siehe Anforderungen, „Zwingend vor Beginn …“, Punkt 3).

Sicherheit in der Inferenz (Analyse 2026-11-11):

* jedes Ziel der Policy wird **vor dem Senden** gegen das Kollisionsmodell
  geprüft (`bc/safety.check_target`), der Geofence-Wächter prüft parallel
  die gemessene Stellung;
* Kollisionsmodell = Tisch und Sperrzonen **live** aus den Tischpunkten der
  Steuerung (Rückfall: Werte der Aufnahme), Hülle der Demonstrationen
  (+3 cm), an der realen Anlage zusätzlich die festen Hindernisse aus
  [`einstellungen/hindernisse.json`](einstellungen/hindernisse.json)
  (Kamerastange, Teststation, Roboterbasis; gilt nur für M4);
* eingefrorenes Kamerabild (älter als 100 ms, 2 Takte in Folge) hält an;
* „Erfolg“ = Übergabepunkt erreicht und Greifer wie aufgezeichnet; der
  Abstand zu den Greifpunkten des Trainings ist nur noch Information.

## Hardwarefrei ausführen

```bash
# Testsuite ohne pytest (nur numpy/opencv/scipy noetig):
python tests/run_all.py

# End-to-End-Demo: Planung + Rauschen + Aufzeichnung -> Datensatz
python apps/record.py --sim --episodes 3 --out data_sim
python apps/eval.py --data data_sim

# Inferenz-Verdrahtung (HoldPolicy, Watchdog, 15-Hz-Takt)
python apps/infer.py --sim --steps 45
```

Mit pytest (`pip install .[dev]`): `pytest` im Ordner „Behavior Cloning".

## Kameras in Betrieb nehmen

```bash
python tools/check_cameras.py --list          # welche Geraete werden gefunden?
python tools/check_cameras.py --backend sim   # Werkzeug ohne Hardware pruefen
python tools/check_cameras.py --only scene    # eine Kamera, Live-Vorschau
python tools/check_cameras.py                 # beide: Rate + Zeitversatz
```

Die **Wrist-Kamera** (Daheng VEN-161-61U3C) ist USB3-Vision/GenICam und über
OpenCV *nicht* erreichbar — sie braucht das Daheng Galaxy SDK. `gxipy` ist
dort nicht installierbar, der Adapter findet es selbst; Details und die
beiden klassischen Stolpersteine in
[Dokumentation/Kamera-Inbetriebnahme.md](Dokumentation/Kamera-Inbetriebnahme.md).

> ⚠️ Die **Szenenkamera** ist die Draufsichtkamera der Gruppe (Daheng) und
> wird je Lauf per `--camera scene=daheng:<Seriennummer>` zugeordnet (die
> Oberfläche und `m4_grasper.py` tun das). `config.SCENE_CAMERA` ist nur noch
> der Platzhalter für Läufe ohne Zuordnung und zeigt auf OpenCV-Index 0 — auf
> einem Laptop die eingebaute Webcam; `apps/record.py` fragt dann nach.

## Am Hardwaretag (Abnahmeliste AP 0.6)

Die Contract-Tests sind die Abnahmeliste der Adapter — unverändert
dieselbe Suite, nur gegen die echte Hardware:

```bash
python tests/run_all.py --camera=uvc    contract.test_camera_contract
python tests/run_all.py --camera=daheng contract.test_camera_contract
python tests/run_all.py --robot=neura   contract.test_robot_contract
```

Mit pytest gleichwertig: `pytest tests/contract -q --camera=daheng`.

Zusätzlich zwingend (Details in AP 0.4/0.6): Kinematik-Kalibrierung
(30–50 `(q → Pose)`-Paare loggen, Konvention NeuraPy↔URDF bestimmen),
Greifer-Totzeit messen, Tool-Offset eintragen, reale Raten/Latenzen gegen
das 30-ms-Budget messen.

## Wichtige Festlegungen (nicht stillschweigend ändern!)

| Was | Wert | Wo |
|---|---|---|
| Regelrate Aufzeichnung = Inferenz | 15 Hz | `config.CONTROL_RATE_HZ` |
| State (14) / Action (7) | Gelenke+TCP+Greifer / ideale Gelenke t+1+Greifer | `dataset.py` |
| Bildgröße | 240 × 320 RGB | `config.IMAGE_*` |
| Greifer-Totzeit | 500 ms (unverifiziert!) | `config.GRIPPER_DWELL_S` |
| Achsgrenzen | aus URDF, unverifiziert! | `config.JOINT_LIMITS_RAD` |
| Planer-Geschwindigkeit | 0.15 / 0.05 m/s (provisorisch) | `config.*_SPEED_MS` |
| Versatz im Anflug | 40 % der Episoden, 3–6 mm an PRE_PICK, 0 auf den letzten 20 mm; Rest ≤ 1,5 mm geprüft | `config.APPROACH_OFFSET_*`, `record.py --anflug-anteil/--anflug-versatz` |
| Feste Hindernisse (nur Anlage, nur M4) | Kamerastange, Teststation, Roboterbasis | `einstellungen/hindernisse.json`, `--hindernisse auto/an/aus` |
| Eingefrorenes Bild (Inferenz) | 100 ms, 2 Takte | `config.INFER_MAX_FRAME_AGE_S/_STEPS` |

Schema-Änderungen ⇒ `config.SCHEMA_VERSION` hochzählen; Datensätze
verschiedener Versionen nie mischen.

## Abhängigkeiten

Deklariert in [pyproject.toml](pyproject.toml), bewusst nicht
auto-installiert. Kern (numpy/opencv/scipy) reicht für alles
Hardwarefreie. torch für die RTX 5070 Ti **zwingend als cu128-Build**
(sm_120!) — Anleitung im pyproject-Kopf, Verifikation mit
`tools/check_gpu.py`. LeRobot-Version vor der ersten echten Aufzeichnung
pinnen (AP 0.9 Punkt 6).
