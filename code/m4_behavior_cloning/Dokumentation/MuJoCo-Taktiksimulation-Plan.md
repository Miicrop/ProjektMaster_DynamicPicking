# MuJoCo-Taktiksimulation — Plan (Stand 2026-11-20)

**Zweck:** Aufnahme-Einstellungen (Datenmenge, Drehversatz, Tempo, Licht, Episodenende) unter **gleichen
Testbedingungen** vergleichen. Jede Policy fährt **geschlossen** (die Bilder werden aus der aktuellen Stellung
gerendert) auf denselben Testlagen. Das kann das VM-Replay nicht: Dort laufen die Bilder starr nach der Aufnahme ab,
und G2 und C2 hatten verschiedene Testlagen (siehe `Berichte/2026-11-20_Vorlaeufig_2026-11-19/Testprotokoll.md`).

**Nicht der Zweck:** Sim-to-Real. In MuJoCo trainierte Policies laufen nicht an der Anlage. Verglichen werden nur
Unterschiede zwischen Varianten, keine absoluten Werte.

## 1. Reicht ein grobes Setup?

Ja, wenn die Dinge stimmen, die die *Taktik* bestimmen. Fotorealismus braucht es nicht.

| muss stimmen | warum | Quelle |
|---|---|---|
| Kinematik LARA 5 und Werkzeug (TCP 197,5 mm) | Bahnen, Gelenkwinkel, Sprünge an Gelenk 6 | `bc/data/lara5_candidate.urdf`, Meshes `presentation/abschluss/public/urdf` |
| Takt 15 Hz, servo_j 60 Hz, Override-Verhalten | die Policy lernt das Folgeverhalten mit | `bc/config.py`, `bc/servo.py` |
| **Folgeverhalten des Arms** (Nachlauf, Grenzen je Gelenk) | Schleppfehler und Sprünge sind ein Kernproblem | an Aufnahmen angepasst (`aux.joints_command` gegen `observation.state`) |
| Kamera-Lage grob (Wrist am Flansch, Szene von oben) | was die Policy sieht, wenn sie danebenliegt | `einstellungen/hindernisse.json` (Wrist 60 mm, 107°), Szene aus Referenzbild und ArUco |
| Objekt mit **eindeutiger Drehung** (Fase) | die Drehung muss im Bild ablesbar sein | lila Quader, 15 mm hoch, eine Ecke gefast (`m1_vision_topdown/part.py`, `config/system.yaml`) |
| Planer, Rauschen, Drehversatz, Lagenwahl, Recorder | genau das wird variiert | **unverändert** aus `bc/` (läuft schon über Ports) |

Darf grob bleiben: Texturen, Licht (außer im Licht-Versuch), Greifkontakt (Griff = Objekt anheften, wenn es zwischen
den Backen liegt), Hindernisse außerhalb des Tisches, Kabel.

## 2. Architektur

Die Pipeline ist hardwarefrei über Ports gebaut (`bc/ports.py`). Es kommen nur Adapter dazu, Aufnahme, Export,
Training und Inferenz bleiben unverändert.

```
apps/record.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco ...
apps/infer.py  --robot mujoco --camera ... --checkpoint <policy>
        │                         │
 bc/adapters/mujoco_robot.py   bc/adapters/cam_mujoco.py
   (RobotPort)                   (CameraPort, rendert aus derselben Szene)
        └──────────┬──────────────┘
          bc/sim_mujoco/szene.py   MJCF: Arm + Greifer + Wrist-Kamera, Tisch, Objekt, Szenenkamera, Licht
                                   gemeinsamer Zustand, Zeit über SimClock (schneller als Echtzeit)
```

- **mujoco_robot.py:** `read_state` (Gelenke, TCP über die vorhandene `KinematicChain`), `fk`/`ik` wie `SimRobot`
  (DLS-IK übernehmen), `servo_j` → Folgemodell → `qpos`, `move_to_joints` (PTP mit Tempo-Grenze), Greifer (Backen
  schließen; liegt das Objekt zwischen den Backen, wird es angeheftet), `ServoGuard` wie bei der Anlage. Dazu ein
  Sim-Haken „Objekt an Lage X legen“ für Lagenwechsel und Zurücklegen.
- **cam_mujoco.py:** `mujoco.Renderer` 320 × 240 je Kamera. Zeitstempel aus der SimClock, damit Sync-Prüfung und
  Bildalter wie gewohnt laufen.
- **Folgemodell:** je Gelenk Nachlauf erster Ordnung plus Geschwindigkeits- und Beschleunigungsgrenze, angepasst an
  die Aufnahmen vom 19.11. Abnahme: aufgezeichnete Kommandos durch das Modell schicken → Schleppfehler-Verteilung
  wie real (q6-Spitzen bei Drehversatz ~0,3 rad).
- **Punkte und Lagen:** Tischpunkte ID0–8, CLEAR_FOV, Ablauf `pick_bis_griff`, Lagenvarianten aus den Metadaten vom
  19.11. übernehmen, damit Planer und Lagenwahl exakt wie real arbeiten.
- **Testlagen:** ein fester Satz (z. B. 60 Lagen, feste Seeds) für alle Modelle, nie im Training.

## 3. Auswertung (geschlossen, je Modell gleiche 60 Testlagen)

Dieselben Kennzahlen wie bisher (`eval_stufe2.py`, `schwingen.py`), dazu Erfolg im eigentlichen Sinn:

- Griff gelungen (Objekt angeheftet und angehoben), nächste Annäherung, Greif-xy, Gier-Fehler (mit Fase, also 360°)
- Tischabstand (< 0, < −10 mm), Welligkeit, Querabweichung
- Abbrüche: Sprung > 0,35 rad (je Gelenk), ServoGuard, Geofence
- **Streuung:** die Basis-Variante mit 3 Seeds trainieren. Unterschiede kleiner als diese Streuung gelten als gleich.

## 4. Vorgehen

| Phase | Inhalt | Abnahme | Aufwand (Arbeit / GPU) |
|---|---|---|---|
| **0 Szene** | MJCF aus URDF + Greifer (Quader) + Kameras + Tisch + Objekt; Szenenkamera-Pose aus Referenzbild (ArUco) | gerenderte Bilder sehen in Ausschnitt und Blickwinkel wie die Referenzbilder aus (Gegenüberstellung) | ½ Tag |
| **1 Adapter** | `mujoco_robot.py`, `cam_mujoco.py`, Folgemodell, `open_robot("mujoco")`; Contract-Tests (`tests/contract`) gegen MuJoCo | Contract-Tests grün; `record.py` nimmt 10 Episoden auf, `export.py --check` ohne Konflikte | 1 Tag |
| **2 Glaubwürdigkeit** | Basisdatensatz (Einstellungen nach 14:27, 400 Ep.) aufnehmen; **bekannte reale Befunde nachstellen**: G gegen G2 (nur Griff besser), weniger Daten schlechter (wie C3a) | beide Effekte zeigen sich in der Sim in derselben Richtung. Sonst: Folgemodell und Bilder nachschärfen, bevor neue Fragen beantwortet werden | ½ Tag + ~3 Trainings |
| **3 Versuche** | je eine Änderung gegen die Basis (Tabelle unten) | Bericht je Versuch | ~10–12 Trainings |

Aufnahme in der Sim: ~400 Episoden in Minuten (SimClock, kein Warten auf den Arm), Export ~10 min. Engpass ist das
Training (10 000 Schritte ≈ 2–3 h). Zu prüfen ist, ob 5 000 Schritte für Vergleiche reichen; das halbiert die
GPU-Zeit. Geschlossene Testfahrten: ~10 min je Modell.

### Versuche (Basis = Einstellungen nach 14:27, nur Griff, 400 Episoden)

| # | Frage | Varianten | beantwortet |
|---|---|---|---|
| V1 | Wie viele Episoden? | 100 / 200 / 400 / 800 | Datenmenge für den Aufnahmetermin |
| V2 | Drehversatz | aus / 10–15° / 10–20° + Ausreißer bis 35° (aktuell) / aktuell + Label an Gelenk 6 begrenzt | Sprünge gegen Korrekturfähigkeit |
| V3 | Endanflug-Tempo | 0,05 m/s (C2) / 0,02 m/s (aktuell) | ob „langsamer“ wirklich genauer macht |
| V4 | Wrist-Licht | dunkel und verrauscht (wie C2) / hell (aktuell) | ob das Licht die Genauigkeit treibt |
| V5 | Episodenende | ganze Episode / nur Griff | Gegenprobe zu G/G2 (zugleich Phase 2) |

V4 ist nur eingeschränkt übertragbar. Simuliert werden Helligkeit, Gain-Rauschen und Kontrast, nicht der echte Sensor.
Die Richtung ist aussagekräftig, die Größe nicht.

## 5. Grenzen

- Absolute Zahlen (mm, Erfolgsquote) sind nicht auf die Anlage übertragbar, nur Rangfolge und Richtung.
- Greifkontakt, Rutschen und Objektverschiebung beim Anfahren fehlen (Objekt bleibt bis zum Anheften liegen).
- Das Folgemodell ist eine Näherung. Anlagenspezifisches (Steuerkanal-Abbrüche, Kameralatenz) fehlt, ließe sich aber
  über die vorhandenen Fehlerprofile (`cam_sim.CameraFaultProfile`) zuschalten.
- Ein Versuch, der in der Sim keinen Unterschied zeigt, beweist nicht, dass es real keinen gibt (z. B. Licht).

## 6. Offene Punkte vor dem Start

1. Objektmaße (Länge × Breite, Fase): aus M1 (`part.py`-Protokoll) oder kurz messen.
2. Szenenkamera: Höhe und Lage. Wird aus dem Referenzbild mit den ArUco-Markern geschätzt (Marker 400 mm Abstand,
   `config/system.yaml`).
3. GPU-Plan: Trainings laufen nacheinander. Die Lernkurve auf echten Daten (G2 mit 50/75 %) und die Sim-Trainings
   teilen sich die GPU.
4. Ob die Sim als eigener Ordner (`bc/sim_mujoco/`) ins Repo der Gruppe soll oder nur lokal bleibt.
