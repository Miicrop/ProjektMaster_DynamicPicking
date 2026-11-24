# MuJoCo-Taktiksimulation — Stand Phase 0, 1 und Vorbereitung Phase 2

Stand: 2026-11-21 (abends) · Plan: [MuJoCo-Taktiksimulation-Plan.md](MuJoCo-Taktiksimulation-Plan.md)
· Phase 2 läuft (Abschnitt 9): Trainings nacheinander auf der GPU, geschlossene Testfahrten wie in der VM.

> **Ergebnis vorweg.** Die Simulation kann aufnehmen **und** geschlossen testen:
>
> - `apps/record.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco`
>   nimmt mit dem Ablauf, den Punkten und den Planer-, Rausch-,
>   Drehversatz- und Varianten-Einstellungen vom 19.11. auf.
> - `apps/infer.py --robot mujoco … --testlagen` fährt eine Policy geschlossen
>   auf einem festen Satz von 60 Testlagen und wertet jede Fahrt mit der
>   Wahrheit der Sim aus.
>
> | Abnahme | Ergebnis |
> |---|---|
> | Szene: Render neben Referenzbild | ArUco-Ecken im Mittel **0,4 px (Szene) / 0,5 px (Wrist)** bei 320 × 240 |
> | Wrist-Objektiv: Lochkamera statt Fisheye (Korrektur des Anwenders) | 3,6-mm-Objektiv als Lochkamera mit k1/k2: Rest **1,15 px**, altes Fisheye-Modell 1,24 px |
> | Folgemodell gegen 399 echte Episoden | Median und p90 des Schleppfehlers je Gelenk wie real; q6 `max\|action − state\|` bei Drehversatz p50 **0,270 rad (real 0,279)**. Die seltenen Überschwinger (> 0,1 rad) fehlen |
> | Tests | Contract-Suite **17/17** gegen MuJoCo, eigene Tests **10/10** |
> | Probeaufnahme | 11 Episoden in `data_sim_mujoco/2026-11-20`, alle gegriffen, `export.py --check` ohne Konflikte |
> | Planung | IK schneller und robuster: **3 Lagen / 9 Episoden in 71 s**, 0 verworfene Planungen (vorher 17 min für 11 Episoden, 6 verworfen) |
> | Auswertung an Expertenfahrten (60 Testlagen, ideale Bahn) | Griff **60/60**, Greif-xy 0,1 mm, Gier-Fehler 0°, Querabweichung p95 1,3 mm |
> | Probelauf G2 geschlossen (Lagen 0–3) | läuft durch; G2 greift nicht (bleibt 38–48 mm über dem Objekt). Erwartet, das Modell kennt keine Sim-Bilder |
> | **Sim-Basisdatensatz** (Abschnitt 5.5) | **408 Episoden in 3,4 min** (8 Prozesse), alle gegriffen; Export nur bis Griff: 42 826 Takte (G2-Datensatz 42 010), Schema wie G2, keine Testlage im Datensatz |
>
> Grob bleiben Optik, Greifkontakt und die Ausläufer des Schleppfehlers
> (Abschnitt 6). Für Phase 2 fehlen nur noch die Trainings (Abschnitt 8).

---

## 1. Was gebaut ist

| Datei | Inhalt |
|---|---|
| `bc/sim_mujoco/szene.py` | MJCF aus der URDF-Kette, Greifer, Kameras, Tisch mit ArUco-Markern, Objekt. Dazu die **Welt**: Arm (Folgemodell), Greifer, Objekt, Renderer, Zeit |
| `bc/sim_mujoco/folgemodell.py` | Nachlauf je Gelenk (zweite Ordnung), Anpassung an Aufnahmen, Vergleich |
| `bc/sim_mujoco/kalibrierung.py` | Lage und Objektiv beider Kameras aus den ArUco-Markern der Referenzbilder, Modellvergleich |
| `bc/sim_mujoco/testlagen.py` + `testlagen_v1.json` | fester Testlagen-Satz (60 Lagen, Seed 77261121) mit Greifpose und idealer Bahn |
| `bc/sim_mujoco/auswertung.py` | geschlossene Auswertung je Fahrt und je Satz |
| `bc/sim_mujoco/abnahme.py` | Abnahmen: Render neben Referenz, Episodenbilder, Expertenfahrten |
| `bc/sim_mujoco/parameter.json` | Maße, Kameralage, Licht, Folgemodell, je Abschnitt mit Quelle |
| `bc/sim_mujoco/punkte_2026-11-19.json` | Punkte-Datenbank wie am 19.11.: CLEAR_FOV, PICK, ID0–8, IGNORE, Tischebene, Stützpunkte |
| `bc/sim_mujoco/texturen/` | ArUco-Marker 0–3 als Textur |
| `bc/adapters/mujoco_robot.py` | `MujocoRobot` (RobotPort, PointSource/-Store, Jog) mit schneller IK |
| `bc/adapters/cam_mujoco.py` | `MujocoCamera` (CameraPort) |
| `tests/test_sim_mujoco.py` | 10 Tests: Kette, Nachlauf, Greifen/Ablegen, Verfehlen, Bilder folgen dem Arm, Zuordnung, Jacobi-Matrix, IK nahe CLEAR_FOV, Testlagen, Auswertung |

Geändert (nur Einträge):

- `bc/adapters/__init__.py`: `open_robot("mujoco")`, Kamera-Backend `mujoco`
  in Fabrik, Parsing, `SOFT_BACKENDS` und `start_cameras`.
- `apps/record.py`: `--robot mujoco`, MuJoCo-Kameras zählen als Simulation,
  Erfolg = Objekt hängt am Greifer.
- `apps/infer.py`: `--robot mujoco`, `--testlagen`, `--testlagen-auswahl`,
  Sim-Auswertung je Fahrt. Abweichende Kamera-Backends sind bei MuJoCo nur ein
  Hinweis, weil eine Anlagen-Policy auf Sim-Bildern laufen darf.
- `tests/_fixtures.py`, `tests/conftest.py`, `tests/run_all.py`: Backend
  `mujoco` für die Contract-Suite.

```
apps/record.py / apps/infer.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco
        │                         │
 MujocoRobot (RobotPort)     MujocoCamera ×2 (CameraPort)
        └──────────┬──────────────┘
          bc.sim_mujoco.welt()   eine Welt je Prozess, dieselbe Uhr (SimClock)
          Folgemodell → q(t), Greifer, Objekt, Renderer (Lochkamera + Verzeichnung)
```

Die Welt rechnet nur, wenn gefragt wird. Vor jedem `read_state` und jedem
Bild wird das Folgemodell bis zur Uhrzeit nachgeführt. Mit der SimClock läuft
das schneller als Echtzeit (`timestamp_source: "sim"` in den Metadaten).

---

## 2. Szene (Phase 0)

**Kinematik.** Die MJCF-Körper werden direkt aus `bc/data/lara5_candidate.urdf`
erzeugt, derselben Kette, die die Pipeline nutzt. An der Anlage stimmt sie mit
der Steuerung auf 1e-11 m überein (`local_fk_check` vom 19.11.). Der TCP liegt
197,5 mm vor dem Flansch. MuJoCo-TCP gegen `KinematicChain.fk · Werkzeug`:
höchstens 1,1e-11 m.

**Optik der Glieder.** Verwendet werden die Meshes aus
`presentation/abschluss/public/urdf/meshes`. Deren URDF hat dieselbe
Nullstellung und Drehrichtung wie die Kette (geprüft mit zufälligen
Stellungen), also hängt jedes Mesh mit einem festen Versatz an seinem Glied.
Am Handgelenk liegen ~8 mm Unterschied, das betrifft nur die Optik.

**Greifer.** Der Zimmer LWR50 ist aus Quadern gebaut: Gehäuse 85 × 60 mm, zwei
Finger 60 × 8 × 14 mm. Die Finger öffnen auf 56 mm und schließen auf 40 mm
(Objekt) bzw. 20 mm (leer). Der Greifer ist um die Werkzeugachse **28° verdreht**
montiert. Im Wrist-Referenzbild liegen die Finger symmetrisch links und rechts
oben, die Kamera sitzt also auf ihrer Mittelsenkrechten (Kamerarichtung 118°
− 90°); `config/system.yaml` nennt 23°. Die Maße sind nach dem Wrist-Bild
gewählt: Breitere oder tiefere Gehäuse erscheinen als Band quer durchs Bild,
das es im Original nicht gibt.

**Kameras** (`python -m bc.sim_mujoco.kalibrierung --schreiben`): Grundlage
sind die 16 ArUco-Ecken in den Vollbild-Referenzbildern vom 19.11. Die
Wrist-Bilder entstehen an CLEAR_FOV, gemittelt wurden 5 Bilder.

**Wrist-Objektiv, Korrektur vom 20.11.:** Verbaut ist ein **3,6-mm-Objektiv,
F8.0, kein Fisheye**. Daheng VEN-161-61U3C mit 3,45 µm Pixeln ergibt nominal
f = 1043 px im Vollbild. Vergleich der Modelle an denselben Markerecken:

| Modell Wrist | f (px) | k1 | k2 | Rest (px, Vollbild) |
|---|---|---|---|---|
| Fisheye (bisher) | 1134 frei | −0,178 | — | 1,24 |
| Lochkamera, k1 | 1079 frei | −0,313 | — | 2,29 |
| **Lochkamera, k1 + k2 (gilt)** | **1147 frei** | **−0,511** | **+0,247** | **1,15** |
| Lochkamera, k1 + k2, f fest | 1043 fest | −0,381 | +0,121 | 1,85 |

Die Lochkamera mit zwei Verzeichnungstermen passt die Ecken etwas besser als
das alte Fisheye. Das freie f liegt 10 % über dem Nennwert; 3,6 mm ist ein
Nennmaß, und die Verzeichnung ist kräftig tonnenförmig. Bildwinkel
78° × 57° (Diagonale 93°). F8 heißt große Schärfentiefe, Unschärfe wird nicht
simuliert. Die Kamera sitzt 45 mm neben dem TCP bei 119° von Werkzeug-x, 72 mm
über den Backenspitzen und ist 19° zur Werkzeugachse hin geneigt
(`hindernisse.json`: 60 mm, 107°).

**Wo im Repo noch „Fisheye“ für die Wrist-Kamera steht** (nur gemeldet, nicht
geändert):

- `bc/config.py` Zeile 910 und 929–932 (`WRIST_CAMERA`: „Objektiv: Fisheye 1.85 mm“)
- `Dokumentation/Kamera-Inbetriebnahme.md` Zeilen 35, 41, 149, 248, 333
- `Requierments/requierments.md` Zeilen 18, 211, 216, 222–228 (Objektiventscheidung)
- `bc/adapters/cam_daheng.py` Zeilen 211–213, 356–358 (Kommentare zum ROI)

| Szene | |
|---|---|
| Modell | Fisheye-Modell, f 1337 px, k1 −0,05 (Bildwinkel 63° × 47°) |
| Lage | (430, −285, 809) mm im Basis-KS |
| Rest | 2,2 px (Vollbild) |

MuJoCo rendert eine ideale Lochkamera in doppelter Auflösung. Die Verzeichnung
wird danach per `cv2.remap` aufgebracht (`szene.Objektiv`), Ausgabe 320 × 240.

**Tisch, Marker, Objekt, Licht.** Die Platte liegt in der geteachten Ebene
(0,49° geneigt), die Marker 0–3 an den Positionen aus `config/system.yaml`.
Das Objekt ist ein lila Quader 60 × 40 × 15 mm mit 10-mm-Fase (Maße
übernommen, nicht gemessen). Decken- und Fensterlicht sind gerichtet und
werfen keine Schlagschatten. Das Wrist-Licht ist ein Spot und schaltbar
(`--camera wrist=mujoco:dunkel`); die Helligkeit an CLEAR_FOV sinkt dann von
67 auf 48.

**Abnahme** (`python -m bc.sim_mujoco.abnahme referenz`, neu erzeugt mit der
Lochkamera): Alle 4 Marker werden in Referenz und Render gefunden, mittlerer
Eckenabstand **0,4 px (Szene) und 0,5 px (Wrist)** bei 320 × 240.

![Render neben Referenz](Bilder/MuJoCo/abnahme_render_referenz.png)

---

## 3. Folgemodell

Je Gelenk arbeitet ein Feder-Dämpfer zweiter Ordnung auf dem verzögerten
Sollwertstrom, mit Grenzen für Beschleunigung und Tempo:

    r(t) = servo_j-Strom (linear zwischen den 60-Hz-Punkten) zur Zeit t − verzug
    a    = ω²·(r − q) − 2ζω·v,   |a| ≤ a_max,  |v| ≤ v_max,  Schritt 1/480 s

Angepasst an jede 6. Episode vom 19.11. (67 Episoden), `aux.joints_command`
gegen `observation.state`, im Zeitraster des Recorders. Die Aufrufkosten an
der Anlage stecken damit im Verzug.

| | q1 | q2 | q3 | q4 | q5 | q6 |
|---|---|---|---|---|---|---|
| Verzug (ms) | 0 | 30 | 31 | 40 | 27 | 0 |
| ω (rad/s) | 14,1 | 20,9 | 23,3 | 20,3 | 22,1 | 9,7 |
| ζ | 0,78 | 0,73 | 0,64 | 0,73 | 0,64 | 0,60 |
| a_max (rad/s²) | 7,9 | 8,1 | 8,1 | 8,1 | 8,1 | 8,1 |
| Rest rms (mrad) | 11,3 | 4,3 | 2,6 | 5,1 | 2,4 | 18,2 |

**Abnahme** (`python -m bc.sim_mujoco.folgemodell --vergleich`): Alle 399
verwendbaren Episoden laufen mit ihren Kommandos durch das Modell.

| \|cmd − state\| (rad) | q1 | q2 | q3 | q4 | q5 | q6 |
|---|---|---|---|---|---|---|
| p50 real / Modell | 0,001 / 0,001 | 0,005 / 0,007 | 0,002 / 0,003 | 0,000 / 0,000 | 0,004 / 0,005 | 0,005 / 0,008 |
| p90 real / Modell | 0,019 / 0,021 | 0,044 / 0,043 | 0,017 / 0,018 | 0,005 / 0,007 | 0,021 / 0,021 | 0,050 / 0,052 |
| p99 real / Modell | 0,083 / 0,040 | 0,058 / 0,052 | 0,039 / 0,033 | 0,039 / 0,019 | 0,042 / 0,035 | 0,133 / 0,082 |
| max real / Modell | 0,26 / 0,09 | 0,24 / 0,07 | 0,16 / 0,06 | 0,17 / 0,05 | 0,11 / 0,05 | 0,30 / 0,11 |

| q6 `max\|action − state\|` je Episode | real | Modell |
|---|---|---|
| mit Drehversatz, p50 | 0,279 | 0,270 |
| mit Drehversatz, p90 | 0,370 | 0,335 |
| ohne Drehversatz, p50 | 0,104 | 0,105 |

![Folgemodell gegen Aufnahmen](Bilder/MuJoCo/folgemodell_schleppfehler.png)

**Es fehlen die Ausläufer.** Bei etwa 1 % der Takte läuft die echte Achse an
einer Umkehr bis 0,4 s weiter und überschwingt. Beispiel ep_00100: q6 steigt
nach der Umkehr der Drehversatz-Korrektur weiter auf 1,359 rad, während das
Kommando schon auf 1,03 fällt. Das ergibt 0,275 rad Schleppfehler, im Modell
höchstens 0,11. Folge: Die Sim sieht weniger große Sprünge als die Anlage, die
Abbruchregel „Sprung > 0,35 rad“ greift seltener.

---

## 4. Adapter und Probeaufnahme (Phase 1)

**`MujocoRobot`**:

- `fk`/`ik` rechnen mit Werkzeug, die Stützpunkte liegen wie an der
  Steuerung.
- `servo_j` prüft erst den ServoGuard, dann geht der Sollwert ins
  Folgemodell.
- `move_to_joints` ist eine PTP-Fahrt: Die Uhr läuft um die Fahrzeit weiter.
- Greifen heftet das Objekt an, wenn es zwischen den Backen liegt (≥ 3 mm
  Überdeckung, Querlage, ≤ 25° verdreht); Öffnen legt es auf den Tisch.
- Sim-Haken: `objekt_ablegen`, `objekt_an_punkt`, `objekt_fuer_griff(joints)`,
  `objekt_lage()` (360°), `griff_haelt()`.

**`MujocoCamera`** rendert synchron im Hauptthread aus derselben Welt,
3–7 ms je Bild.

**Tests:**

- Contract-Suite 17/17.
- `test_sim_mujoco` 10/10.
- Die bestehenden Module, die die Änderungen berühren (`test_apps`,
  `test_camera_assignment`, `test_layering`, `test_put_back`, `test_probe`,
  `test_recorder`), sind grün.

**Probeaufnahme** (aus `data_sim_mujoco/`, damit PICK-Sicherungen nicht im
geteilten `sequences/` landen):

```bash
cd data_sim_mujoco
python ../apps/record.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco --sequence ../sequences/pick_bis_griff.json --episodes 3 --lagen 4 --hindernisse an --randabstand 0.025 --ablage-tempo 0.05 --seed 20261120 --out 2026-11-20 --block B01 --session 2026-11-20-mujoco
```

Die Einstellungen entsprechen dem 19.11. laut Metadaten und Laufprotokollen:

| | 19.11. (Anlage) | Sim |
|---|---|---|
| Ablauf | `pick_bis_griff` | dieselbe Datei |
| Planer | Transit 0,15 m/s, Endanflug 0,02 m/s, PTP 0,5 rad/s | gleich |
| Ausführung | servo_j 60 Hz, 15 Hz Takt | gleich |
| Rauschen | 15 mm / 0,05 rad, gestaffelt bis ×1,0 | gleich |
| Anflug-Versatz | Anteil 0,5, 5–10 mm, 10–20°, 15 % Ausreißer bis 25 mm / 35° | gleich (Standard) |
| Varianten | je Lage 3 Fahrten, bis 15 mm / 15° | gleich |
| Hindernisse | an | `--hindernisse an` |
| Lagenwahl | Randabstand 25 mm, Umlegen ≤ 0,05 m/s | `--randabstand 0.025 --ablage-tempo 0.05` |
| Erste Lage | `--start-lage auto` (von Hand eingelegt) | **`geteacht`** (Objekt per Sim-Haken an PICK) |

Ergebnis: 11 Episoden, alle mit gegriffenem Objekt. `max_follow_error_rad`
liegt bei median 0,062 (Anlage 0,078), die Greifhöhe bei 6,64 mm (Soll 6,58).
`export.py --check` läuft ohne Konflikte.

**Diese Probeaufnahme ist mit dem alten Fisheye-Wrist-Modell und den alten
Greifermaßen gerendert.** Für Phase 2 wird neu aufgenommen.

![Episode](Bilder/MuJoCo/episode_2026-11-20_ep_00005.png)

---

## 5. Vorbereitung Phase 2

### 5.1 Planung beschleunigt

Die IK im `MujocoRobot` hat dieselbe DLS-Iteration und Seed-Semantik wie der
SimRobot, mit drei Änderungen:

1. **Analytische Jacobi-Matrix**, eine Kettenauswertung je Schritt statt sieben,
   feste Gelenk-Ursprünge vorab gerechnet. Abweichung zur numerischen Fassung
   < 3e-7.
2. **Stagnation:** Verbessert sich der Rest 25 Schritte lang nicht, gilt eine
   Lösung mit Rest < 0,1 mm / 0,001 rad als gefunden. Das ist zehnmal strenger
   als die FK-Rückprobe der Pipeline (1 mm / 0,01 rad). Sonst kommt sofort
   `IKError`.
3. **Weiterrechnen bis 1000 Schritte** nur, wenn der Rest schon < 1 mm ist.

**Befund dazu:** Die „unerreichbare Pose neben CLEAR_FOV“ aus der
Probeaufnahme war meist eine **IK-Schwäche**. Auf der PTP-Bahn ab CLEAR_FOV
(q4 ≈ 0, kleinster Singulärwert 0,001) blieb die gedämpfte Iteration bei
0,016 mm Rest stehen, und die Toleranz des SimRobot (0,01 mm) verwarf diese
erreichbaren Posen. Das zeigte die Expertenfahrt zu Testlage 4: Ihre ideale
Bahn ließ sich ohne Rauschen nicht erneut lösen. Eine einzelne Pose aus dem
ersten Lauf bleibt wirklich bei 2,5 mm Rest; sie wird jetzt nach 0,03 s statt
nach Sekunden verworfen.

| gleiche Lage, gleicher Seed | vorher | jetzt |
|---|---|---|
| Planung je Lage bzw. Variante | 19–105 s | **3–4 s** |
| 3 Lagen × 3 Fahrten, Wandzeit gesamt | — | **71 s**, 0 Planungen verworfen, 9/9 gegriffen |
| Lauf 20.11. (4 Lagen) | 17 min Planung, 6 verworfen | — |

400 Episoden dauern damit grob 50–60 min in einem Prozess. **Parallel
aufnehmen** geht ohne weiteren Code: Jeder Prozess hat seine eigene Welt.
Mehrere `record.py` laufen nebeneinander, jeweils mit eigenem `--out`, eigenem
`--seed` und eigenem Block-Bereich (`--block B01`, `B201`, …), jeder aus einem
eigenen Arbeitsordner (wegen der PICK-Sicherungen). Exportiert wird
gemeinsam: `export.py --data <ordner1> <ordner2> …`. Bei mehr Prozessen als
Kernen bremst das Rendern; je Prozess rund ein Kern.

### 5.2 Testlagen-Satz

`python -m bc.sim_mujoco.testlagen --erzeugen` schreibt
`bc/sim_mujoco/testlagen_v1.json`: 60 Lagen, Seed 77261121, **nie für
Aufnahmen verwenden**. Jede Lage entsteht wie eine automatische Lage der
Aufnahme:

- Hülle der Tischpunkte mit 25 mm Rand, nicht in der Sperrzone, ≥ 30 mm
  Abstand untereinander.
- Greifpose mit `auto_layout.place_pose`.
- Ablauf `pick_bis_griff` aufgelöst, ideale Bahn gegen das Kollisionsmodell
  (Tisch, Sperrzone, Zelle) und das Gelenktempo gelöst.

Die Drehung ist **geschichtet** (je Lage ein eigener 6°-Abschnitt), denn reiner
Zufall gab 3 bis 17 Lagen je 60°-Bereich. Ausnahme: Gegen den PICK um
−180…−120° gedreht läuft Gelenk 6 über ±3,14 (IK geseedet am PICK, q6 =
1,28). Dieselbe Grenze gilt in der Aufnahme. Diese 11 Abschnitte wurden frei
neu gezogen, daher sind die Objekt-Gier-Bereiche ungleich besetzt: 11, 12, 5,
7, 13, 12 je 60°.

Je Lage gespeichert:

- Greifpose und Greifgelenke
- Objektlage (x, y, Gier über 360°, so wie die Sim sie hinlegt)
- ideale TCP-Bahn mit Greiftakt, als Bezug für Querabweichung und Welligkeit

![Testlagen](Bilder/MuJoCo/testlagen_v1.png)

### 5.3 Geschlossene Auswertung

`bc/sim_mujoco/auswertung.py` je Fahrt:

| Kennzahl | Bedeutung |
|---|---|
| `griff` | Objekt hängt am Ende am Greifer und ist ≥ 20 mm angehoben |
| `annaeherung_mm` | kleinster Abstand TCP – Soll-Greifpunkt (3D) |
| `greif_xy_mm`, `greif_quer_mm`, `greif_laengs_mm` | TCP gegen Objektmitte beim ersten Schließen, quer = Backenachse |
| `gier_fehler_grad` | Greifer gegen Objekt beim Schließen, −180…180 (mit Fase: 180° verdreht ist ein Fehler) |
| `tisch_min_mm`, `unter_tisch`, `unter_tisch_10` | kleinster Abstand Werkzeugspitze – Tischebene, < 0, < −10 mm |
| `sprung_max_rad`, `sprung_takte` | je Gelenk max \|Ziel − Ist\| und Takte über 0,35 rad |
| `quer_p95_mm`, `welligkeit_mm` | Abstand zur idealen Bahn bis zum Griff (p95) und dessen Welligkeit nach Abzug eines 1-s-Mittels (wie `schwingen.py`) |
| `abbruch` | endstellung, max_steps, sprung (mit Gelenk), servoguard, kollisionsmodell, geofence, stopp |

Je Satz (`zusammenfassen`): Griffquote, Mediane und p90, Anzahl `unter_tisch`,
Fahrten mit Sprung je Gelenk, Abbrüche nach Art.

**Abnahme an Expertenfahrten** (`python -m bc.sim_mujoco.abnahme experte
--lagen 0-59`): Die ideale Bahn jeder Testlage läuft ohne Rauschen durch den
Recorder und wird ausgewertet. Ergebnis: **Griff 60/60**, Greif-xy median
0,1 mm, Gier-Fehler 0,0°, Tischabstand min 6,5 mm (= Greifhöhe),
Querabweichung p95 median 1,3 mm (Nachlauf des Folgemodells), Welligkeit
0,2 mm, keine Sprünge, 60 × `endstellung`. Ein Fehlgriff (4 cm daneben) wird
im Test als „kein Griff, geschlossen, Greif-xy > 35 mm“ erkannt.

### 5.4 Geschlossene Testfahrt mit `infer.py`

```bash
python apps/infer.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco --checkpoint <policy> --testlagen --testlagen-auswahl 0-59 --kamerapruefung aus --keine-live-ansicht --seed 0 --out data_sim_mujoco/rollouts_<modell>
```

- Vor jeder Fahrt: Greifer auf, Objekt an die nächste Testlage
  (`objekt_fuer_griff`), PTP an die Startstellung aus `bc_policy.json`.
- Danach `sim_auswertung.json` und `.csv` im Protokollordner;
  `summary.json` enthält je Fahrt den Eintrag `sim` und
  `sim_zusammenfassung`.
- Uhr: SimClock, die Vorhersage läuft synchron. Die Vorhersagelatenz der
  Anlage (asynchron, ~77 ms) wird also nicht nachgebildet.
- **`--out` immer angeben**, sonst schreibt `infer.py` nach
  `<checkpoint>/rollouts`.

**Probelauf** mit `checkpoints/G2_licht_langsam_nur_griff/policy` auf den
Lagen 0–3 (`data_sim_mujoco/rollouts_G2_probe_2026-11-20`): 4 Fahrten in 2 min,
Vorhersage ~190 ms auf der GPU. Geprüft sind Startfahrt, Testlage,
Abbruch-Einordnung und Auswertungsdateien.

| Lage | Ende | Annäherung | Tisch min | quer p95 |
|---|---|---|---|---|
| 0 | max_steps | 38 mm | 44 mm | 48 mm |
| 1 | max_steps | 48 mm | 48 mm | 36 mm |
| 2 | Kollisionsmodell (Sperrzone IGNORE) | 46 mm | 40 mm | 32 mm |
| 3 | max_steps | 45 mm | 51 mm | 14 mm |

G2 greift in der Sim nicht und bleibt ~40–50 mm über dem Objekt. Das sagt
nichts über G2: Das Modell kennt die Sim-Bilder nicht. Gezeigt ist nur, dass
die Kette geschlossen läuft. Eine geschlossene Testfahrt über 60 Lagen dauert
damit ~30 min je Modell.

### 5.5 Sim-Basisdatensatz (20.11. abends)

Aufnahme mit dem neuen Wrist-Objektiv (Lochkamera, Abschnitt 2), dem Ablauf
`pick_bis_griff` und den Einstellungen nach 14:27. Gemeint ist die Glättung
des Drehversatzes aus Commit `edde16d`; sie steckt im aktuellen Planer. Es
liefen 8 Prozesse nebeneinander, je 17 Lagen × 3 Fahrten, jeder mit eigenem
Seed, Block-Bereich und Arbeitsordner (5.1):

```bash
# je Prozess k = 1..8, aus data_sim_mujoco/2026-11-20_basis/lauf_k
echo j | python <repo>/apps/record.py --robot mujoco --camera wrist=mujoco --camera scene=mujoco \
    --sequence <repo>/sequences/pick_bis_griff.json --episodes 3 --lagen 17 --hindernisse an \
    --randabstand 0.025 --ablage-tempo 0.05 --start-lage pick --seed 202611210k \
    --out daten --block B01|B21|…|B141 --session 2026-11-20-mujoco-basis-k
python tools/export_variante.py --abschneiden-nach 3 --data data_sim_mujoco/2026-11-20_basis/lauf_*/daten \
    --out data_sim_mujoco/datasets/sim_2026-11-20_basis_nur_griff
```

**Erste Lage:** `--start-lage pick` statt `geteacht`. Das Teil liegt am
geteachten PICK und wird unaufgezeichnet an die erste automatische Lage
umgelegt; die Freigabe kommt per `echo j`. Damit beginnt jeder Prozess wie am
19.11. mit einer *vorgeschlagenen* Lage. Mit `geteacht` stünde derselbe PICK
8 × 3 Mal im Datensatz.

| | 19.11. Anlage | Sim-Basis |
|---|---|---|
| Episoden (verwendbar) | 399 (401 aufgenommen) | **408**, alle gegriffen, 0 verworfen |
| Herkunft der Lagen: vorgeschlagen / automatisch / Variante | 8 / 127 / 266 | 8 / 128 / 272 |
| Takte je Episode, Median / p90 | 141 / 161 | 143 / 159 |
| Anflug mit Drehversatz | 51 %, Median 15,3°, max 33,3° | 50 %, Median 16,5°, max 34,7° |
| Objektbereich x / y | 194…545 / −285…−6 mm | 194…546 / −285…−3 mm |
| Gier je 60°-Abschnitt (0…360°) | 56 / 200 / 145 / 0 / 0 / 0 | 37 / 243 / 128 / 0 / 0 / 0 |
| `max_follow_error_rad` Median / p90 | 0,078 / 0,162 | 0,068 / 0,086 |
| Export bis Griff (`--abschneiden-nach 3`) | 57 550 → 42 010 Takte | 59 051 → 42 826 Takte (−27,5 %) |
| Wandzeit | ein Tag | **3,4 min** Aufnahme + 7,5 min Export |

`export.py --check` meldet keinen Konflikt. Planer-, Takt- und
Ausführungswerte sind über alle 408 Episoden gleich und entsprechen dem 19.11.
Die `execution/*`-Felder fehlen dort genauso. Das Schema des Exports
(Merkmale, Formen, 15 Hz) ist identisch mit `datasets/2026-11-19_nur_griff`;
nur `robot_type` heißt `sim_lara5`.

**Testlagen nicht im Datensatz.** Die Lagen der Aufnahme ziehen andere Seeds
als der Testlagen-Satz (77261121). Abstand jeder Episode zur nächsten
Testlage:

| | |
|---|---|
| nur xy | min 0,7 mm, Median 16,3 mm |
| innerhalb 2 mm **und** 2° | 0 Episoden |
| innerhalb 5 mm und 5° | 0 Episoden |
| innerhalb 10 mm und 10° | 1 Episode (`lauf_6/ep_00032`: 0,7 mm, 7,8° neben einer Testlage) |

Die Abdeckung ist ähnlich wie am 19.11. Die Testlagen liegen in denselben
Bereichen, sind aber selbst nie gefahren:

![Lagen 19.11. und Sim-Basis mit Testlagen](Bilder/MuJoCo/basis_2026-11-20_lagen.png)

![Episode aus der Sim-Basis](Bilder/MuJoCo/episode_basis_lauf1_ep_00004.png)

Auffällig:

- **Ausläufer des Schleppfehlers kleiner** (p90 0,086 gegen 0,162 rad). Das
  ist der bekannte Mangel des Folgemodells (Abschnitt 3). Die Sim-Labels liegen
  deshalb seltener weit von der Ist-Stellung entfernt als an der Anlage.
- **Varianten verworfen:** 25 Mal in 8 Läufen „außerhalb des Bereichs“ und
  einmal „keine gültige verrauschte Bahn“. Neu gezogen, wie an der Anlage;
  es fehlt keine Episode.
- Die Lagen der 8 Prozesse kennen einander nicht (`--abdeckung` zählt nur
  beim Start). Die Verteilung ist trotzdem flächig (Bild).
- 408 statt 400: 8 × 17 Lagen × 3 Fahrten. Für einen Vergleich mit genau
  399 lassen sich Episoden beim Export weglassen.

Ort: Rohdaten `data_sim_mujoco/2026-11-20_basis/lauf_1…8/daten`, Export
`data_sim_mujoco/datasets/sim_2026-11-20_basis_nur_griff` (176 MB). Beides
liegt nicht in `datasets/` und ist nicht versioniert.

---

## 6. Was grob ist

- **Optik:** einheitliche Farben, keine Texturen außer den Markern, kein
  Sensorrauschen, keine Bewegungsunschärfe. Kabel, Kamerastange und
  Teststation fehlen im Bild, im Kollisionsmodell sind sie enthalten.
- **Greifer:** Quader, Maße nach dem Kamerabild gewählt. Die 28°
  Montagedrehung stammt aus dem Bild, nicht aus einer Messung.
- **Greifkontakt:** Anheften statt Kontakt; kein Rutschen, kein Verschieben
  beim Anfahren.
- **Folgemodell:** Gelenke entkoppelt; Überschwinger an Umkehrpunkten fehlen
  (Abschnitt 3); keine Steuerkanal-Aussetzer und keine Kameralatenz. Die
  Fehlerprofile lassen sich zuschalten.
- **Objektmaße** sind übernommen, nicht gemessen.
- **Zeit:** `servo_j`, `read_state` und die Vorhersage kosten 0 Sim-Zeit.

---

## 7. Bedienung

```bash
python -m bc.sim_mujoco.kalibrierung --schreiben     # Kameralage neu aus data/2026-11-19/referenzbilder
python -m bc.sim_mujoco.folgemodell --anpassen --schreiben --jede 6
python -m bc.sim_mujoco.folgemodell --vergleich      # Abnahmebild + Zahlen
python -m bc.sim_mujoco.abnahme referenz             # Render neben Referenz
python -m bc.sim_mujoco.abnahme experte --lagen 0-59 # Auswertung an Expertenfahrten
python -m bc.sim_mujoco.abnahme episode --daten data_sim_mujoco/2026-11-20 --episode 0
python -m bc.sim_mujoco.testlagen --zeigen           # Testlagen-Bild
python tests/run_all.py --robot=mujoco --camera=mujoco test_sim_mujoco contract.test_robot_contract contract.test_camera_contract
```

Alles aus `code/m4_behavior_cloning`, Umgebung `bc_env` (MuJoCo 4.0.1).

---

## 8. Was für Phase 2 noch fehlt

1. ~~Basisdatensatz aufnehmen~~ erledigt (5.5). Offen sind die drei Trainings
   der Basis mit verschiedenen Seeds für die Streuung; sie werden erst mit
   dem Anwender abgesprochen.
2. **Erste Lage:** `--start-lage pick` ersetzt in der Sim die von Hand
   eingelegte Lage (5.5). Offen ist noch `--abdeckung` über parallele
   Prozesse hinweg.
3. **Überschwinger im Folgemodell** (Abschnitt 3), falls V2 (Drehversatz)
   davon abhängt, wie oft die 0,35-rad-Grenze greift.
4. **Licht-Versuch V4:** Gain-Rauschen und Kontrast „dunkel wie C2“ fehlen,
   bisher gibt es nur Wrist-Licht an/aus.
5. **Vorhersagelatenz:** Bei Bedarf eine künstliche Verzögerung der Chunks wie
   an der Anlage (asynchron, ~77 ms), damit Policies, die darauf empfindlich
   sind, nicht zu gut aussehen.
6. **Doku der Gruppe:** „Fisheye“ für die Wrist-Kamera korrigieren (Stellen in
   Abschnitt 2). Das ist nicht Teil dieser Arbeit.

---

## 9. Phase 2: Trainings und Versuche (ab 21.11.)

Freigabe des Anwenders: Trainings nacheinander auf der GPU, nach jedem sofort
geschlossen auf den 60 Testlagen fahren. Reihenfolge: Basis 400 → Basis 600
→ Glaubwürdigkeit (V5 ganze Episode, Datenmenge 200) → bei passender Richtung
Seed 1 und V2, V3, V4, V1. Die Stopp-Regel nach V5/Datenmenge ist seit dem
21.11. abends aufgehoben: Die Kette läuft bis zum Ende durch (Ziel Montag
früh). V5 und 200 werden trotzdem gegen die reale Richtung bewertet.

### 9.1 Ablauf

- **Training** wie G2: `apps/train.py --steps 10000 --batch-size 128
  --num-workers 6`, Seed 0, Val 10 % lagenweise. Etwa 3 h je Modell.
- **Testfahrt** je Modell: `python -m bc.sim_mujoco.testfahrt --ohne-tisch
  --verzoegerung 2 --robot mujoco … --testlagen --testlagen-auswahl 0-59
  --transport-geplant --seed 0`. Das ist `apps/infer.py` unter den
  Bedingungen der VM-Fahrten von G2 (Abschnitt 9.4). Die Policy fährt bis zum
  Griff, danach hebt der Planer an. Die Testfahrt läuft parallel zum nächsten
  Training; das ist nur Inferenz.
- **Warteschlange:** `data_sim_mujoco/jobs/warteschlange.sh` arbeitet die
  Jobs `jobs/NN_name.job` der Reihe nach ab, Log in
  `jobs/warteschlange.log`.
- **Auswertung:** `python -m bc.sim_mujoco.vergleich <namen…>` liefert die
  Kennzahlen je Modell, das 95-%-Intervall der Griffquote und einen
  McNemar-Test auf die Griffe gleicher Lagen. Dazu kommt die Aufteilung nach
  Drehbedarf.
- **Drehbedarf** heißt |q6 an der Greifpose − q6 an CLEAR_FOV|, getrennt am
  Median der Testlagen (80°). Einen Anflug-Drehversatz gibt es in der
  geschlossenen Fahrt nicht; der Drehbedarf ist die nächste Entsprechung.

**Wie groß muss ein Unterschied sein?** Bei 60 Lagen reicht das
95-%-Intervall einer Griffquote von 50 % von 37 bis 63 %. Unterschiede um
10 Prozentpunkte sind also ohne zweiten Seed nicht von Zufall zu trennen. Der
Paarvergleich auf denselben Lagen ist schärfer: Es zählen nur die Lagen, auf
denen genau ein Modell greift. Die Seed-Streuung kommt mit Seed 1 dazu.

### 9.2 Datensatz 600 (verschachtelt)

- **Aufstockung:** 8 weitere Prozesse mit je 8 Lagen × 3 Fahrten
  (`lauf_9…16`, Seeds 2026112109…16, Blöcke B161…B301), Wandzeit 2 min.
  Das ergab 191 Episoden (eine Variante nach 3 Versuchen aufgegeben), also
  **599** zusammen.
- **Testlagen:** Keine Episode liegt innerhalb von 5 mm und 5° einer
  Testlage, 2 Episoden innerhalb von 10 mm und 10°.
- **Export** bis Griff: 87 044 → 62 958 Takte.
  `data_sim_mujoco/datasets/sim_2026-11-21_basis600_nur_griff`.
- **Val-Split:** `train.py` zieht den Split per Permutation über die Zahl der
  Lagen. Bei 200 statt 136 Lagen ist das ein **ganz neuer Split**: Nur 6 der
  42 Val-Episoden des 400ers wären wieder Val gewesen, 36 wären ins Training
  gerutscht.
- **Verschachtelung:** Der Export liest die Episoden über einen eigenen Index
  (`2026-11-20_basis/verschachtelt_600/index.json`) in einer gewählten
  Reihenfolge. Auf die Val-Plätze der 600er-Permutation fallen genau die 14
  Val-Lagen des 400ers und 6 neue Lagen (Seed 0). Daten und `train.py` bleiben
  unverändert. Geprüft: **Val-400 (42 Ep.) ⊂ Val-600 (60 Ep.), Train-400
  (366) ⊂ Train-600 (539)**.
- **Val-MAE:** Die Zahl aus dem Training gilt je Modell auf der eigenen
  Val-Menge (4 Batches). Für den Vergleich werden beide Modelle zusätzlich
  auf allen Frames der 60 Val-600-Episoden ausgewertet; keines der beiden
  hat sie gesehen.

### 9.3 Vorbereitung der Varianten

- **V5 ganze Episode:** dieselben 408 Episoden, ungekürzt exportiert
  (`sim_2026-11-20_basis_ganz`). Reihenfolge und Lagen-Gruppen sind gleich,
  also auch der Val-Split.
- **Datenmenge 200:** wie die reale Lernkurve über `--episoden-gewichte`
  (`jobs/gewichte_sim_200.json`). Es zählen 50 % der Trainings-Lagen (61 von
  122, Seed 0), das sind 183 Trainingsepisoden; Val bleibt unverändert (42).
  Mit dem Val-Anteil entspricht das einem Datensatz von ~200 Episoden.
- **Seed 1:** `train.py --seed 1` zieht auch den Val-Split neu. Die Streuung
  enthält dann Training *und* Aufteilung. Vergleichbar ist die Testfahrt auf
  den 60 Lagen, die Val-MAE nur eingeschränkt.
- **V2 Drehversatz 10–15° ohne Ausreißer:** `--anflug-drehung 10,15
  --anflug-ausreisser 0`. In `record.py` gilt der Ausreißer-Anteil für
  Drehung **und** seitlichen Versatz zugleich. Mit 0 entfallen also auch die
  seitlichen Ausreißer bis 25 mm (sonst 15 % der Anflüge mit Versatz). Eine
  getrennte Einstellung gibt es ohne Codeänderung nicht.
- **V3 Endanflug 0,05 m/s:** `--approach-speed 0.05`.
- **V4 Wrist dunkel und verrauscht wie C2:** neuer Kameramodus
  `--camera wrist=mujoco:c2`. Das Wrist-Licht ist aus, dazu kommen
  Verstärkung 0,616 und Gauß-Rauschen σ = 1,7 Grauwerte mit festem Seed
  (`kameras.wrist.c2` in `parameter.json`, Test in `test_sim_mujoco`).
  Gemessen an den echten Daten:

  | | Bildmittel | Kontrast (σ) | zeitl. Rauschen im Stillstand |
  |---|---|---|---|
  | C2-Daten 02./03.11. | 20,9 / 20,1 | 21,3 / 17,1 | 0,65 / 0,65 |
  | C2-Daten 09.11. | 5,1 | 6,1 | 0,39 |
  | C2 gewichtet (602 Ep.) | **14,7** | | ~5 % des Mittels |
  | 19.11. (Licht an) | **34,5** | 27,8 | 1,12 |
  | Sim hell (Basis) | 75,1 | 51,5 | 0 |

  Übertragen wird das **Verhältnis** C2 : 19.11. = 0,426, nicht der absolute
  Wert. Licht aus allein ergibt in der Sim nur 0,69 des Licht-an-Bildes, die
  Verstärkung bringt es auf 0,426. Das Rauschen beträgt 5 % der
  Zielhelligkeit.
- **V1 800 Episoden:** Aufstockung des 599ers um ~200 neue Episoden, der
  Split wird wie beim 600er verschachtelt.

**Befund nebenbei:** Das Sim-Wrist-Bild ist im Datensatz **gut doppelt so
hell** wie das echte vom 19.11. (Mittel 75 gegen 34,5) und weniger rot (real
RGB 58/24/28, Sim 93/66/75). Die Abnahme in Abschnitt 2 prüfte Geometrie
(Markerlagen), nicht die Helligkeit. Die Basis bleibt so, sonst wären die
Vergleiche nicht mehr auf derselben Grundlage. Für spätere Aufnahmen lässt
sich die Helligkeit über Lichtstärke oder Verstärkung angleichen.

### 9.4 Testfahrt wie in der VM (Befund 21.11. mittags)

Die erste Testfahrt von Basis 400 (`apps/infer.py` direkt) griff nur
**5 von 60** Mal. In 55 Fahrten schloss die Policy den Greifer nie, obwohl der
Arm oft auf 3–10 mm an den Greifpunkt kam. Das lag an zwei Unterschieden zu
den VM-Fahrten, mit denen G, G2 und die Lernkurve gemessen sind:

1. **Vorhersage-Verzug (entscheidend).** Mit SimClock sagt `infer.py`
   synchron voraus: Der Chunk aus der Beobachtung von Takt s gilt ab Takt s.
   In der VM läuft die Vorhersage asynchron (75–90 ms bei 66,7 ms Takt). In
   G2 `vm_val39` treffen **1715 von 1771 Chunks 2 Takte** nach ihrer
   Beobachtung ein, meist werden 3 Chunks gemittelt. G2 und das Sim-Modell
   sagen das Schließen gleich voraus: `[0,0,0,0,1,1,1,1]`, also „in 4 Takten“.
   Weil der Arm am Greifpunkt steht, bleibt das Takt für Takt so. Gemittelt
   werden die Chunk-Stellen 0/2/4/6 (synchron, 4 Chunks) → **0,50** (gemessen 0,47–0,50).
   Geschlossen wird erst über `GRIPPER_THRESHOLD` = 0,5, der Greifer bleibt offen. Mit
   2 Takten Verzug sind es die Stellen 2/4/6 → **0,67**, der Greifer schließt.
   In der VM steht beim ersten Schließen genau 0,66–0,67 an.
2. **Tischebene im Kollisionsmodell.** Die VM-Fahrten liefen mit
   `GEOFENCE=alt` (`stufe2_vm.py`): Tischebene, Sperrzonen und Hülle aus
   `bc_policy.json` werden nicht geladen. „Tisch < 0“ wird erst danach
   gezählt. Die Sim lud sie: 31 von 60 Fahrten brachen vorab ab („kollision
   vorab: tool an Tischebene“), und „Tisch < 0“ war immer 0.

`bc/sim_mujoco/testfahrt.py` stellt beides wie in der VM ein und lässt
`infer.py` sonst unverändert. `--verzoegerung 2` gibt einen Chunk erst
2 Takte nach seiner Beobachtung frei; die Rechnung bleibt synchron und
reproduzierbar. `--ohne-tisch` lässt Tischebene, Sperrzonen und Hülle weg.
Der Test `test_verzoegerter_ensembler_wie_vm` prüft 3 Chunks, 2 Takte Verzug
und 0,67. In der Sim folgt der Arm ohne Tischebene auch unter den Tisch.
`vergleich.py` zählt deshalb „Griff, Werkzeug nie unter dem Tisch“ getrennt.

| Basis 400 | wie VM (Verzug 2, ohne Tisch) | synchron, ohne Tisch | synchron, mit Tischebene |
|---|---|---|---|
| Griff (95-%-Intervall) | **20/60** (23–46 %) | 5/60 (4–18 %) | 5/60 (4–18 %) |
| Endstellung erreicht | **32** | 5 | 5 |
| Abbrüche | max_steps 28 | max_steps 55 | Kollisionsmodell 31, max_steps 24 |

Paarweise greift die VM-Variante auf 15 Lagen, die synchrone auf keiner, die
sie nicht auch greift (McNemar p < 0,001). Alle Modelle ab hier fahren nur noch
die VM-Variante; die beiden alten Fahrten liegen als
`rollouts_SIM_basis_400_alt_synchron_*` daneben.

**Bedeutung für die Anlage.** Ob G2 schließt, hängt am Vorhersage-Verzug:
2/3 gegen die Schwelle 1/2. Wird die Vorhersage schneller (≤ 1 Takt Verzug)
oder ändern sich `replan_steps` bzw. die Chunk-Länge, kann G2 am Greifpunkt
stehen bleiben, ohne zu schließen. Umgekehrt liegt die Griffentscheidung des
Modells immer „4 Takte in der Zukunft“. Das ist zu prüfen, bevor man
Inferenz-Parameter ändert.

Nebenbei: Beim ersten Start liefen Training 600 und Testfahrt 400 doppelt.
Eine alte Startkette lebte nach dem Abbruch weiter. Beide Ketten sind
beendet, die halben Ausgaben verworfen, Training 600 neu gestartet. Training
400 lief allein und ist davon nicht betroffen.

### 9.5 Ergebnis Basis 400

Training `checkpoints/SIM_basis_400`: 182 min, Val-MAE **0,0043 rad** (p95
0,0158), Greifer 98,1 % (G2 real: 0,0058 rad, 98,2 %). Testfahrt wie VM, zum
Vergleich G2 real in der VM (39 Val-Episoden, andere Lagen, andere Welt):

| | Basis 400 (Sim, 60 Testlagen) | G2 (VM, 39 Val) |
|---|---|---|
| Griff (95-%-Intervall) | **20/60** (23–46 %); 16 davon nie unter dem Tisch | – (VM greift nicht) |
| Griff wenig / viel Drehung (≤ / > 80°) | 14/30 · 6/30 | – |
| Annäherung median / ≤ 10 mm / p90 | 10,0 mm / 50 % / 26,7 mm | 14,2 mm / 44 % / 32 mm |
| Greif-xy median / p90 | 14,8 / 29,1 mm | 16,8 mm (median) |
| Gier-Fehler \|median\| / p90 | 9,6° / 175° | 9,7° / 51° |
| Tisch < 0 / < −10 mm | 27 % / 2 % | 43 % / 17 % |
| Sprung-Abbrüche (> 0,35 rad) | 0 | 7 |
| Endstellung erreicht | 53 % | 64 % |
| Welligkeit median | 2,8 mm | 8,0 mm |

- In der Größenordnung liegt die Sim bei Annäherung, Greif-xy und Gier-Median
  nahe an G2 in der VM. Sie ist ruhiger (Welligkeit, keine Sprünge) und
  seltener tief unter dem Tisch. Das passt zum zu glatten Folgemodell
  (Abschnitt 5.5: Folgefehler p90 0,086 gegen real 0,162).
- **12 Fahrten schließen daneben** (Endstellung 32, Griff 20). Daher ist
  Greif-xy median 14,8 mm. Gier p90 175° heißt: Einige Griffe sind um 180°
  verdreht (Fase, Abschnitt 5.3).
- Viel Drehbedarf greift deutlich seltener (6/30 gegen 14/30). Bei je 30
  Fahrten ist das am Rand dessen, was man vom Zufall trennen kann
  (Fisher-Test p ≈ 0,05).

### 9.6 Ergebnis Basis 600 gegen 400

Training `checkpoints/SIM_basis_600`: 178 min, Val-MAE **0,0042 rad** (p95
0,0154), Greifer 98,3 %. Die Warteschlange stand nach dem Training 3 h still
(14:36–17:35, die Prozessprüfung fand ihre eigene Befehlszeile; behoben).
Testfahrt wie VM, `python -m bc.sim_mujoco.vergleich SIM_basis_400
SIM_basis_600`:

| | Basis 400 | Basis 600 | Paarvergleich (gleiche Lagen) |
|---|---|---|---|
| Griff (95-%-Intervall) | **20/60** (23–46 %) | **17/60** (18–41 %) | nur 400: 6, nur 600: 3, McNemar p = 0,51 |
| davon richtig herum (\|Gier\| ≤ 90°) | 15 | 11 | |
| Griff im Trainingsbereich (27 Lagen, 9.7) | **14/27** (34–69 %) | **11/27** (24–59 %) | 4 : 1, p = 0,38 |
| Griff außerhalb (33 Lagen) | 6/33 | 6/33 | |
| Gier \|median\| im Trainingsbereich / außerhalb | 2,5° / 173° | 2,8° / 176° | |
| Annäherung median / ≤ 10 mm / p90 | 10,0 mm / 30 / 26,7 mm | 8,1 mm / 34 / 32,1 mm | Wilcoxon p = 0,38 |
| Annäherung median im Trainingsbereich | 7,1 mm | 5,5 mm | |
| Greif-xy median / p90 | 14,8 / 29,1 mm | 11,0 / 28,6 mm | |
| Tisch < 0 / < −10 mm | 16 / 1 | **6 / 0** | nur 400: 13, nur 600: 3, **p = 0,02** |
| Sprung-Abbrüche | 0 | 0 | |
| Endstellung erreicht | 32 | 31 | |
| Welligkeit median | 2,8 mm | 1,8 mm | Wilcoxon p = 0,15 |
| Val-MAE (eigene Val, 4 Batches aus dem Training) | 0,0043 rad | 0,0042 rad | |
| Val-MAE gemeinsam: Val-600, alle 6323 Frames | 0,00455 rad | **0,00418 rad** (−8 %) | p95 0,0171 / 0,0152 |
| Val-MAE gemeinsam: nur Val-400 (4388 Frames) | 0,00439 rad | 0,00414 rad (−6 %) | |

Bewertung (je ein Seed):

- **Griff: kein belastbarer Unterschied.** 20 gegen 17, im Trainingsbereich
  14 gegen 11, liegt weit im Bereich des Zufalls (p = 0,51 / 0,38). Dass 600
  etwas schlechter liegt, ist bei einem Seed nicht zu deuten.
- **Annäherung, Greif-xy, Welligkeit** sind bei 600 etwas besser, aber
  ebenfalls nicht signifikant.
- **Val-MAE auf derselben Val-Menge** (keines der Modelle hat sie gesehen,
  `val_gemeinsam_400_600.log`): 600 liegt 6–8 % unter 400. Das ist die
  erwartete Richtung, aber klein; ohne Seed-Streuung ist offen, ob es mehr
  als Trainingsrauschen ist. Offline-Gewinn und Griffquote laufen hier nicht
  zusammen.
- **Tisch < 0** ist der einzige Unterschied, der im Paarvergleich hält (16
  gegen 6, p = 0,02). Ob das an der Datenmenge oder am Trainingslauf liegt,
  zeigt erst die Seed-Streuung (Basis 400 Seed 1, Job 04).
- Real (Lernkurve G2 50/75/100 %) wurde mit mehr Daten vor allem die
  Annäherung besser. In der Sim ist der Schritt 400 → 600 dafür zu klein
  oder die Sim zu leicht. 800 (V1) und 200 kommen dazu.

### 9.7 Befund: Griffe um 180° verdreht (21.11. abends)

Bei viel Drehbedarf greifen 400 und 600 fast immer um 180° verdreht
(Gier-Fehler außerhalb des Trainingsbereichs im Median 173–176°). Mit Fase
heißt das: Objekt falsch herum. Drei Fragen, Skripte in
`data_sim_mujoco/analyse_gier/`:

**(a) Ist das Label mehrdeutig? Nein. Die Testlagen liegen außerhalb der
Trainingsdaten.**

- Der Experte greift in allen 599 Sim-Episoden gleich: Greifer-y gegen
  Objekt-x am PICK ist konstant (in der Konvention von `object_yaw_deg`
  −118,0° ± 0,05°, in der Sim-Konvention 0°). Es gibt kein Umschlagen
  zwischen +x und −x (`gier_experte.py`).
- Die Aufnahme dreht das Objekt aber nur um ±45° um die Mitte
  (`config.AUTO_YAW_RANGE_DEG = 45`), dazu kommen ±15° für die Varianten.
  Gelenk 6 dreht von CLEAR_FOV zum PICK deshalb nur um **−81…+63°**
  (real 19.11.: −93…+83°).
- Die Testlagen ziehen die Gier über **360°**. Das steht so in
  `testlagen.py`, mit der falschen Begründung, die Aufnahme verteile
  ebenfalls über 360°. Gelenk 6 müsste dort um −197…+114° drehen.
  **33 der 60 Testlagen liegen außerhalb des Trainingsbereichs**
  (q6-Drehung −86…+68°, also mit 5° Rand).
- Außerhalb dreht die Policy den kurzen Weg: Sie fährt die Stellung an, in
  der das Objekt wie in den Trainingsdaten aussieht. Ohne Fase ist das
  dieselbe Lage um 180° gedreht. Beispiel Lage 57: Bedarf 187°, gedreht
  um etwa 7°, Fehler 176°.
- Im Trainingsbereich trifft die Policy den Gier gut (Median 2,5° bzw.
  2,8°, 1–2 Ausreißer > 90°). Die Griffquote dort ist 14/27 bzw. 11/27.

**(b) Ist die Fase im Bild erkennbar? Am Start kaum, über dem Objekt
deutlich.** Das Objekt ist an derselben Stelle mit Gier g und g + 180°
gerendert, 320 × 240 (`fase_im_bild.py`, Lagen 41 und 57):

| Arm | Wrist: Pixel mit Unterschied > 20 | Szene |
|---|---|---|
| CLEAR_FOV (Start der Policy) | 26–35 von 76 800 | 24–25 |
| über dem PICK (~8 cm) | 640–730 | 13–15 |

Am Start ist das Objekt im Wrist-Bild etwa 25 × 15 px groß, die Fase nur
2–3 px. In der Szenenkamera ist sie praktisch unsichtbar. Erst über dem
Objekt zeigt das Wrist-Bild die gefaste Ecke klar. Die Richtung der Drehung
legt die Policy aber zu Beginn des Anflugs fest.

![Fase: Gier g (links), g + 180° (Mitte), Unterschied (rechts); je Lage Wrist und Szene an CLEAR_FOV und über dem PICK](Bilder/MuJoCo/fase_im_bild.png)

**(c) Wie häufig ist das real? Bei G/G2 in der VM nie.** Die Kennzahl der
VM-Auswertung (`eval_stufe2.py`, `d180`) **faltet den Gier-Fehler auf
±90°**, eine 180°-Verdrehung wäre dort also unsichtbar. Ungefaltet
nachgerechnet (`gier_vm_ungefaltet.py`, Werkzeug-x der Fahrt gegen PICK):

| VM, 39 Val-Episoden | Schließen | \|Gier\| median / p90 / max | > 90° |
|---|---|---|---|
| G2 | 25 | 9,7° / 51° / 69° | **0** |
| G | 28 | 15,5° / 50° / 63° | 0 |
| G2 Lernkurve 75 % | 33 | 14,5° / 45° / 66° | 0 |
| G2 Lernkurve 50 % | 30 | 18,7° / 56° / 85° | 0 |

Die realen Val-Lagen liegen im Drehbereich der Aufnahme, deshalb tritt der
Fehler dort nicht auf. Über Lagen außerhalb des Bereichs sagt das nichts.

**Folgen:**

- **Für die Sim-Auswertung:** Die Griffquote über alle 60 Lagen mischt zwei
  Dinge: wie gut die Policy im Trainingsbereich greift und wie oft sie
  außerhalb um 180° verdreht trotzdem anhebt. Hauptkennzahl für die
  Varianten ist ab jetzt **Griff im Trainingsbereich (27 Lagen)**, dazu
  „richtig herum“. `vergleich.py` weist beides aus. Mit 27 Lagen ist das
  Intervall breit (etwa ±18 Prozentpunkte).
- **Für den Aufnahmetermin:** Liegen die Teile an der Anlage beliebig über
  360°, muss die Aufnahme das abdecken. Heute dreht sie nur ±60°. Dann
  braucht es mehr Drehbereich (`AUTO_YAW_RANGE_DEG`, mit der q6-Grenze bei
  −180…−120°) und deutlich mehr Episoden. Die Fase muss dafür schon am
  Start erkennbar sein (in der Sim heute 2–3 px). Liegen die Teile real
  immer im heutigen Bereich, ist die Policy dort richtig. Das sollte vor dem
  Termin geklärt werden.
- **Testlagen-Abstand korrigiert:** Die Prüfung „keine Episode innerhalb
  5 mm und 5° einer Testlage“ (5.5, 9.2) verglich `object_yaw_deg` der
  Aufnahme (andere Konvention, auf 0…180° gefaltet) mit der Sim-Gier der
  Testlagen. Neu (`jobs/testlagen_nah.py`, `jobs/testlagen_abstand2.py`):
  Gier beider Seiten aus der Greifpose. Basis 400/600: weiterhin **0**
  Episoden innerhalb 5 mm/5° (6 innerhalb 10 mm/10°). Die Aussage in 5.5
  bleibt also richtig, nur die Zahlen der 10-mm-Zeile ändern sich.

### 9.8 Aufnahme der Varianten V2, V3, V4, V1

Skript `data_sim_mujoco/jobs/aufnahme_varianten.sh`. Es läuft neben dem
Training auf der CPU, immer nur eine Aufnahme zur Zeit, höchstens 4
Prozesse gleichzeitig (neue erst bei > 3 GB freiem RAM). Je Variante genau
eine Änderung gegen die Basis: dieselben 8 Prozesse, Seeds 2026112101…08,
Blöcke und 17 Lagen × 3 Fahrten. Danach je Variante:

1. Lagen-Gruppen nahe einer Testlage (5 mm und 5°, `testlagen_nah.py`) aus
   dem Index nehmen (ganze Gruppe = alle Fahrten derselben Lage).
2. `apps/export.py --check` ohne Konflikt.
3. Export nur bis Griff (`tools/export_variante.py --abschneiden-nach 3`)
   nach `data_sim_mujoco/datasets/sim_2026-11-21_<variante>_nur_griff`.
4. Erst dann die Job-Datei (05 V2, 06 V3, 07 V4, 08 V1).

| Variante | Änderung | Aufnahme | nahe Testlage ausgeschlossen | im Datensatz |
|---|---|---|---|---|
| V2 Drehversatz 10–15° | `--anflug-drehung 10,15 --anflug-ausreisser 0` | 406 Ep., 13 min | 3 Gruppen / 9 Ep. (eine 1,7 mm / 0,3° neben Testlage 55) | 397, Job 05 (18:20) |
| V3 Endanflug 0,05 m/s (Basis 0,02) | `--approach-speed 0.05` | 408 Ep., 13 min | 1 Gruppe / 3 Ep. | 405, Job 06 (18:49) |
| V4 Wrist dunkel/verrauscht | `--camera wrist=mujoco:c2` | 408 Ep., 19 min | 0 | 408, Job 07 (19:28) |
| V1 800 | `lauf_17…24`, 9 Lagen × 3, Index `verschachtelt_800` | 216 neue Ep., 7 min | 0 | **815** (599 + 216; Train 734, Val 81 = 27 Gruppen), Job 08 (20:28) |

Alle vier `export.py --check` ohne Konflikt (nur Hinweise „fehlt in …
Episoden (ältere Aufzeichnung)“ für Felder, die die Sim nicht schreibt).
Stichprobe V4: Wrist-Bild im Mittel Helligkeit 25 statt 60 (V3), Kanten
(Laplace-Std) 16 statt 27, also dunkel und weich wie C2.

- **V2:** Die Lagen weichen ab Lage 2 von der Basis ab, weil der
  Drehversatz anders zieht. Deshalb liegen hier Lagen nahe an Testlagen,
  die in der Basis nicht vorkamen.
- **V4 wird mit dunklen Bildern getestet.** Die Policy ist auf die dunklen,
  verrauschten Bilder trainiert, also läuft auch die Testfahrt mit ihnen
  (`WRIST=mujoco:c2` in der Job-Datei → `--camera wrist=mujoco:c2`). Mit
  hellen Bildern zu testen hieße, einen Bildwechsel zu messen statt der
  Variante.
- **V1:** Val-600 ⊂ Val-800 und Train-600 ⊂ Train-800 wie beim 600er
  (`jobs/verschachtelt_800.py` prüft das selbst). Neue Gruppen nahe einer
  Testlage fallen vor dem Ordnen heraus.
- **Seed 1** (Job 04) nutzt den Basisdatensatz. `--seed 1` zieht auch den
  Val-Split neu (9.3).

### 9.9 Ergebnis V5 ganze Episode gegen Basis 400 (nur Griff)

Training `checkpoints/SIM_V5_ganz_400`: 188 min, Val-MAE 0,0042 rad (p95
0,0147, eigene Val über die ganze Episode, also nicht direkt mit 400
vergleichbar). Testfahrt wie VM; Paartests mit
`data_sim_mujoco/analyse_gier/paartest.py SIM_basis_400 SIM_V5_ganz_400`:

| | Basis 400 (nur Griff) | V5 ganze Episode | Paarvergleich |
|---|---|---|---|
| Griff (95-%-Intervall) | 20/60 (23–46 %) | 18/60 (20–42 %) | 7 : 5, p = 0,77 |
| Griff im Trainingsbereich (27) | 14/27 (34–69 %) | **15/27** (37–72 %) | 2 : 3, p = 1,0 |
| davon richtig herum | 15 | 15 | 3 : 3 |
| Annäherung median (alle / Trainingsbereich) | 10,0 / 7,1 mm | **12,4 / 10,0 mm** | Diff. +1,6 mm, **Wilcoxon p < 0,001** (im Bereich p = 0,003) |
| Annäherung ≤ 10 mm | 30 | 24 | |
| Greif-xy median / p90 | 14,8 / 29,1 mm | 10,2 / 21,4 mm | gepaart (23 Lagen) p = 0,46 |
| Gier \|median\| im Trainingsbereich | 2,5° | 1,7° | |
| Tisch < 0 / < −10 mm | 16 / 1 | **5 / 0** | 15 : 4, **p = 0,02** |
| Welligkeit median | 2,8 mm | 2,2 mm | p = 0,055 |
| Endstellung erreicht / Sprung-Abbrüche | 32 / 0 | 29 / 0 | |

Bewertung (je ein Seed):

- **Griffquote: kein Unterschied** (auch im Trainingsbereich 14 gegen 15).
- **Annäherung: V5 ist schlechter**, im Median um 1,6 mm, und das über fast
  alle Lagen (p < 0,001). Das ist dieselbe Richtung wie real (G gegen G2:
  Abschneiden nach dem Griff hilft). Der Paartest erfasst aber nur die
  Streuung über die Lagen, nicht die zwischen zwei Trainingsläufen. Ob
  1,6 mm über der Seed-Streuung liegt, zeigt erst Basis 400 Seed 1 (Job 04).
- **Tisch < 0:** 600 (6) und V5 (5) liegen beide deutlich unter Basis 400
  (16). Das spricht eher dafür, dass Basis 400 Seed 0 hier ungünstig
  ausgefallen ist, als für einen Effekt der Variante. Seed 1 klärt das.
- Für die Glaubwürdigkeit der Sim: Richtung passt in der Annäherung, in der
  Griffquote ist die Sim zu unempfindlich (60 Lagen, Intervall ±12
  Prozentpunkte).

### 9.10 Ergebnis Datenmenge 200 gegen Basis 400

Training `checkpoints/SIM_menge_200` (183 Trainingsepisoden über
`--episoden-gewichte`, dieselbe Val wie 400): 160 min. Weil die Val gleich
ist, ist die Val-MAE hier direkt vergleichbar.

| | Basis 400 | Menge 200 | Paarvergleich |
|---|---|---|---|
| Val-MAE / p95 (gleiche Val, 42 Ep.) | 0,0043 / 0,0158 rad | **0,0065 / 0,0247 rad** (+51 %) | |
| Train-Loss am Ende / Val-Loss | 0,0001 / 0,0076 | 0,0000 / 0,0078 | Val-Loss fast gleich, der Abstand zeigt sich erst in der Gelenk-MAE der Rollout-Chunks |
| Griff (95-%-Intervall) | 20/60 (23–46 %) | **12/60** (12–32 %) | 11 : 3, McNemar p = 0,057 |
| Griff im Trainingsbereich (27) | 14/27 (34–69 %) | 11/27 (24–59 %) | 5 : 2, p = 0,45 |
| davon richtig herum | 15 | 11 | 6 : 2, p = 0,29 |
| Annäherung median (alle / Trainingsbereich) | 10,0 / 7,1 mm | **12,8 / 8,9 mm** | +2,0 mm, **Wilcoxon p < 0,001** (im Bereich p = 0,02) |
| Annäherung ≤ 10 mm / p90 | 30 / 26,7 mm | 25 / 30,2 mm | |
| Endstellung erreicht | 32 | **22** | |
| Greif-xy median / p90 | 14,8 / 29,1 mm | 12,2 / 25,8 mm | p = 0,62 |
| Tisch < 0 / < −10 mm | 16 / 1 | 15 / 0 | p = 1,0 |
| Welligkeit median | 2,8 mm | 2,5 mm | p = 0,57 |

Bewertung (je ein Seed):

- **Weniger Daten ist in der Sim schlechter, in allen Kennzahlen mit
  Richtung:** Val-MAE +51 %, Annäherung +2 mm (p < 0,001), Griff 20 → 12
  (knapp nicht signifikant, p = 0,057). Die Endstellung (22 gegen 32)
  schwankt schon zwischen zwei Seeds so stark (32/23, 9.11), dass sie nicht zählt. Das ist die reale Richtung (C3a, Lernkurve G2).
- Die meisten verlorenen Griffe liegen außerhalb des Trainingsbereichs (6 → 1).
  Dort greift 400 nur verdreht. Im Trainingsbereich ist der Abstand kleiner
  (14 → 11).
- **Glaubwürdigkeit (Phase 2) damit erfüllt:** Beide bekannten realen Befunde
  (nur Griff besser in der Annäherung, 9.9; weniger Daten schlechter) zeigen
  sich in der Sim in derselben Richtung. Die Griffquote auf 60 Lagen ist
  dabei das gröbste Maß, die Annäherung das empfindlichste.
- Zusammen mit 600 (9.6) ergibt sich eine flache Kurve ab 400: 200 → 400
  deutlich besser, 400 → 600 in der Testfahrt nicht mehr messbar (Val-MAE
  −6 bis −8 %). V1 (815) zeigt, ob sich das fortsetzt.

### 9.11 Seed-Streuung: Basis 400 Seed 0 gegen Seed 1

Training `checkpoints/SIM_basis_400_seed1`: gleicher Datensatz, `--seed 1`
(andere Initialisierung, Batch-Reihenfolge **und** Val-Split, 9.3). Damit
ist der Abstand zwischen den beiden Läufen die Streuung, die jede Variante
schon allein durch einen neuen Trainingslauf hätte.

| | Seed 0 | Seed 1 | Paarvergleich | taugt als Kennzahl? |
|---|---|---|---|---|
| Griff (95-%-Intervall) | 20/60 (23–46 %) | 21/60 (24–48 %) | 6 : 7, p = 1,0 | **ja**, Summe stabil |
| Griff im Trainingsbereich (27) | 14/27 | 15/27 | 2 : 3, p = 1,0 | **ja** |
| davon richtig herum | 15 | 15 | 3 : 3 | ja |
| Annäherung median (alle 60) | 10,0 mm | 10,1 mm | Diff. +0,8, Wilcoxon p = 0,53 | **ja** |
| Annäherung median im Trainingsbereich | 7,1 mm | **3,8 mm** | −2,1, p = 0,056 | nein, schwankt um ~3 mm |
| Greif-xy median / p90 | 14,8 / 29,1 mm | **4,4** / 24,2 mm | −4,2, **p = 0,006** | **nein** |
| Gier \|median\| im Trainingsbereich | 2,5° | 0,9° | | eingeschränkt |
| Tisch < 0 / < −10 mm | 16 / 1 | 10 / 1 | 11 : 5, p = 0,21 | eingeschränkt (±6) |
| Endstellung erreicht | 32 | **23** | | **nein** |
| Welligkeit median | 2,8 mm | 2,8 mm | p = 0,94 | ja |
| Val-MAE (eigene Val) | 0,0043 rad | 0,0037 rad | anderer Val-Split | nicht vergleichbar |

Was das heißt:

- **Griffquote und Annäherung über alle 60 Lagen sind stabil.** Die Summe
  der Griffe ändert sich um 1. Einzelne Lagen kippen aber durchaus (13 von
  60 werden nur von einem der beiden Läufe gegriffen). Das ist mit dem
  McNemar-Test verträglich (symmetrisch 6 : 7), der Test ist für die
  Griffquote also richtig kalibriert.
- **Greif-xy, Annäherung im Trainingsbereich, Endstellung und Tisch < 0
  schwanken zwischen zwei Trainingsläufen so stark wie zwischen den
  Varianten.** Für Greif-xy meldet der gepaarte Wilcoxon zwischen den beiden
  Seeds sogar p = 0,006. Der Test erfasst nur die Lagen-Streuung, nicht die
  des Trainings, und ist für diese Kennzahlen zu optimistisch.
- Nur wenige Griffe zählen in Greif-xy (17–26 gemeinsame Paare), das macht
  die Kennzahl zusätzlich unruhig.

**Neubewertung der bisherigen Ergebnisse:**

| Vergleich | Unterschied | größer als Seed-Streuung? |
|---|---|---|
| 600 gegen 400 (9.6) | Griff 17 gegen 20/21; Annäherung 8,1 gegen 10,0/10,1 mm; Tisch 6 gegen 16/10 | **nein**. Annäherung −2 mm ist knapp darüber, Tisch und Griff nicht |
| V5 ganze Episode (9.9) | Annäherung 12,4 gegen 10,0/10,1 mm; Griff 18 | **Annäherung ja** (+2,3 mm gegen 0,1 mm Seed-Abstand), Griff nein. Tisch 5 liegt nur 5 unter Seed 1, also nicht belastbar |
| Menge 200 (9.10) | Griff 12 gegen 20/21; Annäherung 12,8 mm | **ja**, beides. Gegen Seed 1 auch im McNemar signifikant (11 : 2, p = 0,02) |

Damit bleiben die beiden Glaubwürdigkeits-Befunde stehen (V5 schlechter in
der Annäherung, weniger Daten schlechter). Der Vorteil von 600 im Tisch
(9.6, p = 0,02) war dagegen mindestens teilweise ein ungünstiger Lauf von
Seed 0; gegen Seed 1 ist er nur noch 10 gegen 6.

**Folge für V2, V3, V4, V1:** Bewertet wird nach Griff (gesamt und im
Trainingsbereich, McNemar) und Annäherung über alle 60 Lagen, verglichen mit
**beiden** Seeds der Basis. Ein Unterschied zählt nur, wenn er gegen beide
Seeds in dieselbe Richtung geht und deutlich größer ist als deren Abstand.
Greif-xy, Endstellung und Tisch werden nur noch berichtet.

### 9.12 Ergebnis V2 Drehversatz 10–15° ohne Ausreißer

Training `checkpoints/SIM_V2_dreh10_15` (397 Episoden, 9.8), Val-MAE
0,0045 rad (eigene Val, nicht vergleichbar). Vergleich mit beiden Seeds der
Basis (9.11), Paartests je gegen Seed 0 / Seed 1:

| | Basis Seed 0 | Basis Seed 1 | V2 | Paarvergleich gegen Seed 0 / Seed 1 |
|---|---|---|---|---|
| Griff (95-%-Intervall) | 20/60 | 21/60 | **18/60** (20–42 %) | p = 0,73 / 0,61 |
| Griff im Trainingsbereich (27) | 14/27 | 15/27 | **11/27** (24–59 %) | 4 : 1, p = 0,38 / 6 : 2, p = 0,29 |
| davon richtig herum | 15 | 15 | 12 | p = 0,38 / 0,51 |
| Annäherung median (alle 60) | 10,0 mm | 10,1 mm | **9,8 mm** | −0,6 mm, p = 0,05 / 0,15 |
| \|Gier\| > 90° | 10 | 6 | 12 | |
| Greif-xy median (nur berichtet) | 14,8 mm | 4,4 mm | 8,6 mm | |
| Tisch < 0 (nur berichtet) | 16 | 10 | 12 | |
| Endstellung (nur berichtet) | 32 | 23 | 27 | |
| Welligkeit median | 2,8 mm | 2,8 mm | 2,5 mm | p = 0,10 / 0,055 |

Bewertung (ein Seed V2):

- **Kein Unterschied, der über die Seed-Streuung hinausgeht.** Griff 18
  liegt 2–3 unter der Basis, im Trainingsbereich 11 gegen 14/15, beides
  weit im Zufallsbereich. Die Annäherung ist gleich (9,8 gegen 10,0/10,1 mm).
- Die Tendenz geht eher leicht gegen V2 (Griff im Trainingsbereich, mehr
  180°-Griffe). Ein Vorteil eines gleichmäßigeren Drehversatzes ist in der
  Sim nicht zu sehen.
- Einschränkung: V2 nimmt mit den Ausreißern auch den seitlichen Versatz bis
  25 mm heraus (9.3). Gemessen ist also „gleichmäßiger Anflug ohne
  Ausreißer“, nicht nur der Drehwinkel.

### 9.13 Ergebnis V3 Endanflug 0,05 m/s (wie C2) gegen 0,02 m/s (Basis)

V3 ist der **schnellere** Endanflug: Die Basis fährt mit
`config.APPROACH_SPEED_MS = 0.02`, V3 mit 0,05 m/s wie bei C2. Die Episoden
werden dadurch kürzer (79 statt 105 Frames im Mittel, 405 Episoden). Training
`checkpoints/SIM_V3_tempo005`, Val-MAE 0,0046 rad (eigene Val).

| | Basis Seed 0 | Basis Seed 1 | **V3 0,05 m/s** | Paarvergleich gegen Seed 0 / Seed 1 |
|---|---|---|---|---|
| Griff (95-%-Intervall) | 20/60 (23–46 %) | 21/60 (24–48 %) | **37/60 (49–73 %)** | **0 : 17 / 0 : 16, p < 0,001** |
| Griff im Trainingsbereich (27) | 14/27 | 15/27 | **23/27 (68–94 %)** | 0 : 9, p = 0,004 / 0 : 8, p = 0,008 |
| davon richtig herum | 15 | 15 | **24** | p = 0,004 / 0,004 |
| Griff außerhalb (33, verdreht) | 6 | 6 | 14 | |
| Annäherung median (alle 60) | 10,0 mm | 10,1 mm | **4,2 mm** | p = 0,33 / 0,026 |
| Annäherung ≤ 10 mm | 30 | 30 | 38 | |
| Greif-xy median / p90 (nur berichtet) | 14,8 / 29,1 mm | 4,4 / 24,2 mm | 3,1 / 9,5 mm | |
| Tisch < 0 (nur berichtet) | 16 | 10 | 2 | |
| Endstellung (nur berichtet) | 32 | 23 | 39 | |
| Welligkeit median | 2,8 mm | 2,8 mm | 1,6 mm | p = 0,002 / 0,005 |

**Das ist der erste Unterschied, der weit über die Seed-Streuung geht.**
Keine einzige Lage wird von der Basis gegriffen und von V3 nicht (0 : 17).
Die Seeds untereinander lagen bei 20 gegen 21.

Woran die Basis scheitert (Aufschlüsselung der Fahrten):

| | Griff | geschlossen, nicht gegriffen | nie geschlossen (Takt-Limit) | Annäherung der nie geschlossenen |
|---|---|---|---|---|
| Basis Seed 0 | 20 | 12 | **28** | 24 mm |
| Basis Seed 1 | 21 | 2 | **37** | 16 mm |
| V2 | 18 | 9 | 33 | 20 mm |
| V3 | 37 | 2 | 21 | 28 mm |

- Die Basis **bleibt meist 1,5–2,5 cm vor dem Objekt stehen und schließt
  nie**, bis das Takt-Limit greift. Das liegt nicht am Limit: Es ist
  1,5 × die längste Episode, also 184 Takte bei der Basis und nur 144 bei
  V3. Griffe der Basis brauchen höchstens 165 Takte. V3 hat damit sogar
  weniger Zeit und greift trotzdem öfter.
- Erklärung (Vermutung, nicht getrennt geprüft): Mit 0,02 m/s ändert sich
  das Bild in den letzten Frames vor dem Griff kaum (1,3 mm je Frame bei
  15 Hz). Die Policy sieht viele fast gleiche Bilder mit fast null
  Bewegung und lernt zu „schleichen“. Mit 2 Takten Verzögerung kommt sie
  aus dem Schleichen nicht heraus. Bei 0,05 m/s ist der Endanflug klar
  gerichtet und der Moment zum Schließen eindeutiger.
- Wo V3 scheitert, scheitert es auf dieselbe Art (nie geschlossen, 21) und
  vor allem außerhalb des Trainingsbereichs.

**Übertragbarkeit:** Die Richtung ist ein starkes Signal, die Größe nicht.
Die Sim kennt keine Bewegungsunschärfe im Wrist-Bild und heftet das Objekt
beim Schließen an (kein Anstoßen oder Wegschieben bei schnellerem Kontakt).
Beides spricht real eher gegen 0,05 m/s. Real ist C2 mit 0,05 m/s
aufgenommen; ein direkter realer Vergleich bei sonst gleichen Einstellungen
fehlt. Die Plan-Frage „macht langsamer genauer?“ beantwortet die Sim mit
**nein, im Gegenteil**.

### 9.14 Ergebnis V4 Wrist dunkel und verrauscht (wie C2)

Training `checkpoints/SIM_V4_wrist_dunkel` (408 Episoden). Die Lagen sind
dieselben wie in der Basis (nur die Kamera ist anders), also auch der
Val-Split. **Die Val-MAE ist hier direkt mit Seed 0 vergleichbar.** Die
Testfahrt läuft mit den dunklen Bildern (`--camera wrist=mujoco:c2`, 9.8).

| | Basis Seed 0 | Basis Seed 1 | **V4 dunkel** | Paarvergleich gegen Seed 0 / Seed 1 |
|---|---|---|---|---|
| Val-MAE / p95 (gleiche Val wie Seed 0) | 0,0043 / 0,0158 rad | (anderer Split) | **0,0043 / 0,0159 rad** | gleich |
| Griff (95-%-Intervall) | 20/60 (23–46 %) | 21/60 (24–48 %) | **12/60 (12–32 %)** | 9 : 1, **p = 0,02** / 11 : 2, **p = 0,02** |
| Griff im Trainingsbereich (27) | 14/27 | 15/27 | **9/27** (19–52 %) | 5 : 0, p = 0,06 / 7 : 1, p = 0,07 |
| davon richtig herum | 15 | 15 | 9 | p = 0,03 / 0,07 |
| Annäherung median (alle 60) | 10,0 mm | 10,1 mm | **13,8 mm** | +2,6 mm, p < 0,001 / +2,3 mm, p = 0,03 |
| Annäherung ≤ 10 mm | 30 | 30 | 17 | |
| nie geschlossen / geschlossen ohne Griff | 28 / 12 | 37 / 2 | 38 / 10 | |
| Greif-xy, Tisch, Endstellung (nur berichtet) | 14,8 mm · 16 · 32 | 4,4 mm · 10 · 23 | 10,2 mm · 15 · 22 | |
| Sprung-Abbrüche | 0 | 0 | 1 (Gelenk 6) | |
| Welligkeit median | 2,8 mm | 2,8 mm | 3,0 mm | p = 0,57 / 0,70 |

Bewertung (ein Seed V4):

- **Dunkle, verrauschte Wrist-Bilder machen die Policy schlechter, und das
  über die Seed-Streuung hinaus.** Griff 12 gegen 20/21 (gegen beide Seeds
  p = 0,02), Annäherung +2,3 bis +2,6 mm gegen beide Seeds in derselben
  Richtung.
- **Offline merkt man davon nichts:** Die Val-MAE ist auf derselben Val
  genau gleich (0,0043 rad). Der Verlust entsteht erst in der geschlossenen
  Fahrt, wenn die Policy ihre eigenen kleinen Fehler aus dem Bild korrigieren
  muss. Das ist der gleiche Hinweis wie bei 600 gegen 400 (9.6): Val-MAE
  allein taugt nicht als Entscheidungsgröße.
- Übertragbarkeit (Plan): Simuliert sind Helligkeit, Gain-Rauschen und
  Kontrast, nicht der echte Sensor. Die **Richtung** (besseres Licht hilft)
  ist belastbar, die Größe (8–9 Griffe von 60) nicht.

### 9.15 V3b zweistufiger Endanflug (Auftrag 22.11.)

Frage: Bringt der schnelle Endanflug (9.13) seinen Vorteil auch dann, wenn
die letzten Millimeter vor dem Griff wieder langsam gefahren werden? Real
ist der Tischabstand bei schnellem Anflug kritisch: Der echte Arm schwingt
selten über, Nachlauf bis ~7 mm bei 3 mm Abstand. Die Sim kennt diese
Überschwinger nicht.

**Planer-Erweiterung** (`bc/trajectory.py`, Standard unverändert):
`build_ideal_trajectory(..., approach_fast_speed=None, approach_slow_m=0.0)`.
Ist beides gesetzt und `approach_fast_speed` > `approach_speed`, bekommt
jedes LIN-Segment zu einem `approach`-Punkt ein eigenes
Geschwindigkeitsprofil (`_TwoSpeedProfile`): Anfahren auf v1, Fahrt mit v1,
Sinus-Übergang v1 → v2 in `SEGMENT_RAMP_S` (0,5 s), Fahrt mit v2, Bremsen.
Die letzten `approach_slow_m` (Fahrt v2 + Bremsen) liegen fest. Es gibt
keinen zusätzlichen Wegpunkt und keinen Halt beim Tempowechsel. Ein erster
Ansatz mit Zwischenpunkt und Überschleifen sackte beim Wechsel auf 8 mm/s ab
(der Planer verlängert die Anfahrrampe des langsamen Stücks einseitig) und
wurde verworfen. Ist das Segment zu kurz, bleibt es einstufig.

- `apps/record.py --anflug-zweistufig V,D`, z. B. `0.05,0.02`. Prüft V gegen
  `PLANNER_APPROACH_SPEED_RANGE_MS`, V > `--approach-speed` ≤ Transit und
  D ≤ 50 mm. Das gilt nur für die Aufnahmebahn, nicht fürs Zurücklegen.
  Meta: `planner.approach_fast_speed_ms`, `planner.approach_slow_m`.
- `bc/known_pose.py` liest beide Werte aus der Meta (gleiche Bahn beim
  Nachplanen).
- Tests: `tests/test_trajectory_zweistufig.py` (Standard bitgleich, monoton
  von v1 auf v2 ohne Absacken, langsam ab 18–24 mm, zu kurzer Anflug bleibt
  einstufig). Dazu laufen die vorhandenen Planer-, Rausch-, Sequenz-,
  Rücklege- und Recorder-Tests weiter grün.

Profil im Ablauf `pick_bis_griff` (PRE_PICK 5 cm über PICK), Sim-Probe:

| Abstand zum Griff [mm] | 49 | 42 | 35 | 29 | 24 | 21 | 20 … 3 | 2 → 0 |
|---|---|---|---|---|---|---|---|---|
| Tempo [mm/s] | 30 | 43 | 49 | 43 | 32 | 22 | **20** | Bremsen |

Endanflug ab 5 cm: 31 Takte (einstufig 0,02 m/s: 46, V3 0,05 m/s: ~20).

**Aufnahme** `data_sim_mujoco/jobs/aufnahme_v3b.sh`: dieselben 8
Prozesse, Seeds 2026112101…08, Blöcke und 17 Lagen × 3 wie V3 und Basis,
einzige Änderung `--anflug-zweistufig 0.05,0.02`. Danach wie immer: Lagen
nahe einer Testlage raus, `export.py --check`, Export nur bis Griff nach
`datasets/sim_2026-11-22_V3b_zweistufig_nur_griff`, erst dann Job
`085_SIM_V3b_zweistufig.job`. Das Skript schreibt ihn als `11_…`, ein
Wächter benennt ihn sofort um: Nach der neuen Priorität (echte Aufnahme
Montag ~11 Uhr) läuft V3b direkt nach V1, vor G3/G4 (09/10). Dazu kommt Job
`11_SIM_V3_tempo005_seed1.job` (V3-Datensatz, `--seed 1`), weil der
V3-Effekt der größte der Reihe ist, aber auf einem Seed steht.

Ergebnis der Aufnahme: 408 Episoden in 11 min, 8/8 Prozesse ok, 1 Gruppe / 3
Episoden nahe einer Testlage ausgeschlossen (wie V3), **405 im Datensatz**,
`export.py --check` ohne Konflikt. Im Mittel 90,5 Frames je Episode (Basis
105, V3 79). Job 085 steht seit 12:39.

**Ergebnis der Testfahrt: 9.17.** Kurz: 19/60 Griffe, im Trainingsbereich
13/27, 34-mal nie geschlossen, also wie die Basis (McNemar p = 1,0); V3 greift
18 Lagen, die V3b nicht greift, umgekehrt keine. Der Vorteil von V3 hängt an
der Geschwindigkeit auf den letzten ~2 cm, nicht am Anflug davor. Job 12
(V3b Seed 1) entfällt; stattdessen V3c mit durchgehend 0,035 m/s (9.18).

### 9.16 Ergebnis V1 Datenmenge 815 (verschachtelt) und Lernkurve

Training `checkpoints/SIM_V1_menge_800` (815 Episoden: 599 aus dem 600er
plus 216 neue, Train 734 / Val 81, 9.8), 189 min, Val-MAE 0,0039 rad (eigene
Val-800, enthält Val-600; nicht direkt vergleichbar).

| | 200 | Basis 400 Seed 0 / Seed 1 | 600 | **815** | 815 gegen 400 S0 / S1 / 600 |
|---|---|---|---|---|---|
| Griff (95-%-Intervall) | 12/60 | 20 / 21 | 17 | **21/60** (24–48 %) | 4 : 5, p = 1,0 / 8 : 8, p = 1,0 / 4 : 8, p = 0,39 |
| Griff im Trainingsbereich (27) | 11 | 14 / 15 | 11 | **16** (41–76 %) | p = 0,69 / 1,0 / 0,13 |
| davon richtig herum | 11 | 15 / 15 | 11 | 17 | p = 0,69 / 0,75 / 0,07 |
| Annäherung median (alle 60) | 12,8 mm | 10,0 / 10,1 mm | 8,1 mm | **9,8 mm** | p = 0,05 / 0,18 / 0,06 |
| Tisch < 0 (nur berichtet) | 15 | 16 / 10 | 6 | 9 | |
| Welligkeit median | 2,5 mm | 2,8 / 2,8 mm | 1,8 mm | 1,9 mm | |

Bewertung (ein Seed 815):

- **815 ist nicht besser als 400.** Griff 21 gegen 20/21, im Trainingsbereich
  16 gegen 14/15, Annäherung 9,8 gegen 10,0/10,1 mm. Alles liegt innerhalb
  der Seed-Streuung.
- **Lernkurve in der Sim:** 200 → 400 deutlich besser (9.10), ab 400 flach
  (600: 17, 815: 21). Die Unterschiede zwischen 400, 600 und 815 sind kleiner
  als der Abstand zweier Seeds.
- Einschränkung: Alle Trainings laufen 10 000 Schritte mit Batch 128. Mit 815
  Episoden sieht die Policy jede Episode etwa halb so oft wie mit 400. Ein
  Teil der flachen Kurve kann daran liegen. Mehr Schritte für 815 wurden
  nicht getestet.
- **V1b (1200) entfällt** nach der Vorgabe („nur wenn 800 klar besser ist
  als 400“). Job 13 wird nicht angelegt.
- Übertragbarkeit: Die Sim ist leichter als die Anlage (kein Sensorrauschen
  des echten Arms, gleichmäßiges Licht, keine Kalibrierfehler). Real kann
  die Sättigung später einsetzen; die reale Lernkurve G2 50/75/100 % stieg
  in der Annäherung bis 100 % noch an.

### 9.17 Ergebnis V3b zweistufiger Endanflug (0,05 → 0,02 m/s ab ~20 mm)

Training `checkpoints/SIM_V3b_zweistufig` (405 Episoden, 9.15), Val-MAE
0,0046 rad (eigene Val). Testfahrt wie immer; Takt-Limit 162 (1,5 × längste
Episode).

| | Basis Seed 0 | Basis Seed 1 | V3 0,05 m/s | **V3b zweistufig** | V3b gegen Seed 0 / Seed 1 / V3 |
|---|---|---|---|---|---|
| Griff (95-%-Intervall) | 20/60 (23–46 %) | 21/60 (24–48 %) | 37/60 (49–73 %) | **19/60 (21–44 %)** | 7 : 6, p = 1,0 / 7 : 5, p = 0,77 / **18 : 0, p < 0,001** |
| Griff im Trainingsbereich (27) | 14 | 15 | 23 | **13** | p = 1,0 / 0,75 / **0,002** |
| davon richtig herum | 15 | 15 | 24 | 14 | p = 1,0 / 1,0 / 0,002 |
| Annäherung median (alle 60) | 10,0 mm | 10,1 mm | 4,2 mm | **11,7 mm** | p = 0,001 / 0,04 / 0,23 |
| Annäherung ≤ 10 mm | 30 | 30 | 38 | 27 | |
| nie geschlossen / geschlossen ohne Griff | 28 / 12 | 37 / 2 | 21 / 2 | **34 / 7** | |
| Annäherung der nie geschlossenen (median, Quartile) | 24 mm (12–26) | 16 mm (11–29) | 28 mm (25–31) | **16 mm (12–20)** | |
| Tisch < 0 (nur berichtet) | 16 | 10 | 2 | 6 | p = 0,01 / 0,39 / 0,22 |
| Greif-xy, Endstellung (nur berichtet) | 14,8 mm · 32 | 4,4 mm · 23 | 3,1 mm · 39 | 5,5 mm · 26 | |
| Sprung-Abbrüche | 0 | 0 | 0 | 0 | |
| Welligkeit median | 2,8 mm | 2,8 mm | 1,6 mm | 2,4 mm | p = 0,71 / 0,61 / 0,009 |

Bewertung (ein Seed V3b):

- **V3b verliert den ganzen Vorteil von V3.** Griff 19 statt 37, gleichauf
  mit der Basis (20/21). Gegen V3 greift keine Lage nur mit V3b (18 : 0).
- **Die „Schleich“-Abbrüche verschwinden nicht.** 34 Fahrten schließen nie
  (Basis 28/37, V3 21). Die Policy bleibt dabei im Median 16 mm vor dem
  Objekt stehen, die Hälfte zwischen 12 und 20 mm. **Das ist genau die
  Strecke, ab der die Daten auf 0,02 m/s wechseln** (langsam ab ~21 mm,
  9.15). Bei V3 halten die nie geschlossenen Fahrten viel weiter weg (28 mm);
  das sind eher Lagen, die die Policy gar nicht findet.
- Damit ist die Vermutung aus 9.13 gestützt: Es liegt nicht an der Gesamtdauer
  des Anflugs, sondern am **langsamen Stück direkt vor dem Griff**. Dort
  ändert sich das Bild je Frame kaum, die Policy lernt dort Stillstand und
  kommt mit 2 Takten Verzögerung nicht heraus. Der schnelle erste Teil
  (bis ~20 mm) hilft dabei nicht.
- Tisch < 0: 6 gegen 16/10. Gegen Seed 0 p = 0,01, gegen Seed 1 nicht
  (p = 0,39). Die Größe ist nach 9.11 nicht belastbar; der Grund ist ohnehin
  eher, dass V3b seltener bis zum Tisch kommt.
- **Job 12 (V3b Seed 1) wird nicht angelegt** („nur wenn V3b klar besser als
  die Basis ist“).

**Übertragbarkeit:** Der schnelle Endanflug (V3) ist in der Sim klar besser,
aber gerade sein heikler Teil fehlt der Sim: Der echte Arm schwingt selten
über, Nachlauf bis ~7 mm bei 3 mm Tischabstand. Die Sim kennt weder diese
Überschwinger noch Bewegungsunschärfe, und sie heftet das Objekt beim
Schließen an. Die Sim sagt nur: **Ein langsames Stück von ~2 cm direkt vor
dem Griff kostet so viel wie ganz langsam fahren.** Wenn real aus
Sicherheitsgründen langsam angefahren werden muss, ist die Sim-Empfehlung
eher, das langsame Stück sehr kurz zu halten (nur Bremsweg) oder den
Tischabstand im Plan zu vergrößern, statt 2 cm zu schleichen. Beides ist
nicht getestet.

### 9.18 V3c Endanflug 0,035 m/s und Endanflug aus Planersicht (Auftrag 22.11. abends)

Nach 9.17 hängt der Vorteil von V3 am Tempo auf den letzten ~2 cm. V3c prüft
den Mittelweg zwischen dem Stillstand-Risiko bei 0,02 m/s (Policy schleicht)
und dem Nachlauf-Risiko bei 0,05 m/s (echter Arm): Endanflug **durchgehend
0,035 m/s**, sonst exakt wie Basis/V3.

**Aufnahme** `data_sim_mujoco/jobs/aufnahme_v3c.sh` (Kopie von
`aufnahme_v3b.sh`, einzige Änderung `--approach-speed 0.035`): 408 Episoden in
12 min, 8/8 Prozesse ok, keine Lage nahe einer Testlage, `export.py --check`
ohne Konflikt, Export nur bis Griff nach
`datasets/sim_2026-11-22_V3c_tempo0035_nur_griff`, danach Job
`12_SIM_V3c_tempo0035.job` (nach 11 V3 Seed 1).

Einschränkung, gilt für alle Tempo-Varianten (V3, V3b, V3c gegen die Basis):
Die Seeds sind gleich, die **Lagen aber nicht**. Nur 8 von 408 Objektlagen
stimmen zwischen V3 und V3b/V3c überein (je Prozess die erste). Das Tempo
ändert die Episodenlänge und damit, wie viele Zufallszahlen das Rauschen
verbraucht; danach laufen die Lagen auseinander. Es ist dieselbe Verteilung,
nicht dieselben Lagen. V4 (nur Kamera anders) hat dagegen dieselben Lagen.

**Endanflug aus Planersicht** (`data_sim_mujoco/analyse_gier/anflug_nachlauf.py`,
nur CPU, jede 4. Episode, je 102): Planer = `aux.pose_ideal`; Folgemodell
fein (480 Hz, Parameter aus `parameter.json`, angepasst an die echten
Aufnahmen vom 19.11., Override 0,5) auf `aux.joints_command`, TCP per FK.
Die feine Rechnung trifft die aufgezeichneten Ist-Gelenke exakt.

| | Basis 0,02 | V3b 0,05 → 0,02 | **V3c 0,035** | V3 0,05 |
|---|---|---|---|---|
| Planer-Tempo 20 / 10 / 5 / 2 mm vor dem Griff [mm/s] | 20 / 20 / 20 / 16 | 20 / 20 / 20 / 16 | 34 / 34 / 32 / 22 | 48 / 48 / 40 / 27 |
| letzte 20 mm: Dauer (Frames bei 15 Hz) | 1,20 s (18) | 1,27 s (19) | 0,80 s (12) | 0,67 s (10) |
| geplanter Abstand Greifpunkt – Tisch | 6,6 mm | 6,6 mm | 6,6 mm | 6,6 mm |
| Schleppfehler max in den letzten 20 mm, median / p90 / max | 1,8 / 1,9 / 2,1 mm | 3,1 / 3,4 / 4,3 mm | 3,2 / 3,4 / 4,5 mm | 4,6 / 4,9 / 6,2 mm |
| Restweg beim Greifbefehl (Ist über Soll) | 0,06 mm | 0,06 mm | 0,10 mm | 0,13 mm |
| Überschwingen unter das Soll danach | 0,01 mm | 0,01 mm | 0,02 mm | 0,03 mm |
| Tischabstand Ist minimal | 6,6 mm | 6,6 mm | 6,6 mm | 6,6 mm |
| **Halt aus voller Fahrt:** Weg nach dem Halt | 1,9 mm | 2,0 mm | **3,3 mm** | 4,7 mm |
| davon über den Halte-Sollwert hinaus | 0,08 mm | 0,09 mm | 0,14 mm | 0,20 mm |

(V3b: Der Schleppfehler-Höchstwert liegt am Beginn der letzten 20 mm, noch
aus dem schnellen Teil. „Halt aus voller Fahrt“: Sollwert ab dem schnellsten
Takt der letzten 20 mm eingefroren, wie bei Stopp oder Aussetzer des
Sollwertstroms.)

- **Mit dem geplanten Weg gibt es in der Sim keinen Nachlauf.** Die Bahn
  bremst in `SEGMENT_RAMP_S` = 0,5 s auf null, das Folgemodell holt dabei
  auf. Beim Greifbefehl steht der Arm 0,1 mm über dem Ziel und schwingt
  höchstens 0,03 mm darunter. Das gilt für alle vier Tempi.
- **Schleppfehler ≈ Tempo × ~0,095 s.** So weit fährt der Arm weiter, wenn
  der Sollwert abrupt stehen bleibt: 1,9 mm bei 0,02, 3,3 mm bei 0,035,
  4,7 mm bei 0,05 m/s. Über den Halte-Sollwert hinaus schwingt das Modell
  dabei kaum (≤ 0,2 mm, Dämpfung 0,6–0,8).
- **Grobe Hochrechnung auf real:** Real wurden bis ~7 mm Nachlauf
  beobachtet. Das ist mehr als jeder Sim-Wert, also fehlt dem Folgemodell
  dort etwas (es ist je Gelenk linear, ohne Kopplung, Last und Aussetzer;
  angepasst bei Override 0,5). Nimmt man an, dass der reale Nachlauf wie in
  der Sim proportional zum Tempo wächst, und dass die 7 mm bei 0,05 m/s
  auftraten (reale Zeitkonstante ~0,14 s statt 0,095 s), dann sind bei
  0,035 m/s **~4,9 mm** und bei 0,02 m/s ~2,8 mm zu erwarten. Bei 3 mm
  Tischabstand reicht damit auch 0,035 m/s **nicht** für einen
  Halt aus voller Fahrt, 0,02 m/s gerade so. Traten die 7 mm schon bei
  langsamerem Anflug auf, ist es entsprechend schlimmer. Das muss an der
  Anlage zugeordnet werden (bei welchem Tempo und welchem Ereignis die 7 mm
  kamen).
- Der geplante Abstand Greifpunkt – Tisch ist in der Sim 6,6 mm, real 3 mm.
  Für die Sim-Testfahrten ist das gleichgültig (Tisch < 0 kommt dort aus den
  Policy-Befehlen, nicht aus dem Folgemodell). Für die reale Aufnahme ist der
  Abstand der Hebel, der unabhängig vom Tempo Sicherheit bringt.

Testfahrt V3c: nach Job 11 (V3 Seed 1), Ergebnis folgt.

### 9.19 V6 Anflug-Versatz näher am Objekt (Auftrag 22.11. abends, vom Anwender freigegeben)

**Befund dahinter:** In allen Aufnahmen (echt 19.11., C2, Sim) liegt der TCP
unter 20 mm über dem Greifpunkt nie mehr als 0,2 mm seitlich daneben
(`APPROACH_OFFSET_FREE_M = 0,020`). Die Sim-Policies, die nie schließen,
stehen aber 10–19 mm hoch und ~12 mm seitlich (9.13, 9.17). Für diese Lage
gibt es kein Trainingsbeispiel. V6 = Basis, nur der Versatz bleibt näher am
Objekt: **voll bis 25 mm (FULL), null ab 12 mm (FREE)** vor dem Griff. Alles
andere bleibt unverändert, auch die Ratengrenze 0,03 m/s.

**Sicherheitsregel (Bedingung des Anwenders):** Solange noch versetzt wird,
müssen die Backenspitzen auch mit Nachlauf mindestens 1 mm über der
Objektoberkante bleiben:

FREE ≥ Oberkante über PICK + 2,4 mm Nachlauf + 1 mm Reserve

- 2,4 mm ist der größte gemessene Nachlauf des Experten im Abstieg
  (Anlage 19.11., 0,02 m/s, Median 1,1 mm).
- **Sim:** PICK liegt 6,6 mm über dem Tisch, das Objekt ist 15 mm hoch, die
  Oberkante also 8,4 mm über PICK → 11,8 → **12 mm**.
- **Real:** Oberkante 7 mm über PICK (`PROBE_OBJECT_TOP_ABOVE_PICK_M`)
  → 10,4 → **11 mm**.
- Mit 11 mm in der Sim bliebe zwischen 11,8 und 11 mm TCP-Höhe ein Restversatz
  von 0,2–0,5 mm. Die Backen lägen dort nach Nachlauf nur ≥ 0,2 mm statt
  ≥ 1 mm über der Kante. Darum 12 mm (Absprache 22.11.).

**Planer-Erweiterung** (Standard unverändert):
- `apps/record.py --anflug-versatz-nah FULL,FREE,OBERKANTE` (mm), hier
  `25,12,8.4`. Setzt `APPROACH_OFFSET_FULL_M/FREE_M` und schaltet
  `config.APPROACH_TIP_CHECK` ein. Meta: `planner.approach_offset_full_m`,
  `approach_offset_free_m`, `approach_tip_check`.
- `bc/noise.approach_tip_clearance`: je Takt und linear dazwischen (4
  Zwischenschritte, wie der 60-Hz-Sollwertstrom). Solange der Versatz an den
  Backenspitzen > 0,1 mm ist (xy-Abstand + Drehwinkel × 29 mm Hebel), muss
  gelten: TCP-Höhe − 2,4 mm ≥ Oberkante + 1 mm (Backenspitze = TCP).
  Verletzt eine Bahn das, zieht `generate_plan` neu (Grund `backen`, wie
  `APPROACH_REST_MAX_M`).
- `approach_rest` liest FREE jetzt zur Laufzeit statt beim Import.
  Standardwert unverändert.
- Neu in der Meta jeder Episode: `noise_reject_kinds` (Verwürfe je Grund).
- Tests: `tests/test_versatz_nah.py` (Standard ohne Prüfung; FREE 12 frei,
  auch mit 35° Drehung; FREE 8 verletzt). Planer-, Rausch-, Sequenz-,
  Rücklege-, Recorder- und Trajektorien-Tests grün.

**Planer-Probe vorab** (`data_sim_mujoco/analyse_gier/versatz_nah_probe.py`,
1500 Proben):
- Die Ratengrenze schafft den Abbau immer, weil sie den Versatz notfalls
  früher abbaut (`rate_limited` bleibt überall ≤ Ziel). Es muss nie neu
  gezogen werden.
- Das Rauschen ist unter 20 mm vor dem Greifpunkt ohnehin 0 (Trichter).

**Aufnahme** `data_sim_mujoco/jobs/aufnahme_v6.sh 25,12,8.4`:
- 408 Episoden in 12 min, 8/8 Prozesse ok, keine Lage nahe einer Testlage.
- `export.py --check` ohne Konflikt, Export nur bis Griff nach
  `datasets/sim_2026-11-22_V6_versatz_nah_nur_griff`.
- Job `13_SIM_V6_versatz_nah.job` (später auf 14 umbenannt, V7 hat Vorrang, 9.20) beginnt mit der VM-Sperre
  `until [ -f data_sim_mujoco/jobs/VM_FERTIG ]; do sleep 60; done`.
- **Lagen und gezogene Versätze sind identisch mit der Basis** (408/408).
  Größe und Richtung ändern den Zufallsverbrauch nicht, nur das
  Höhenprofil ist anders. Das ist ein echter Paarvergleich, anders als bei
  den Tempo-Varianten (9.18). Auch die Planer-Verwürfe sind dieselben (202
  Samples in 103 Episoden, Gründe Gelenktempo und IK).

**Nachprüfung auf den aufgenommenen Bahnen**
(`data_sim_mujoco/analyse_gier/versatz_nah_pruefen.py`, `aux.pose_noisy`
gegen `aux.pose_ideal`):

| | Basis (FREE 20, FULL 50; ganze Aufnahme) | **V6 (FREE 12, FULL 25)** |
|---|---|---|
| Episoden / davon mit Versatz | 815 / 427 (die ersten 408 = V6-Lagen) | 408 / 203 |
| Backenregel verletzt | 0 | **0** |
| kleinster Freiraum nach Nachlauf und Reserve | 8,9 mm | **0,6 mm** |
| Verwürfe wegen Backenregel | – | **0** |
| seitlicher Versatz bei 10 mm Höhe (median / p90 / max) | 0 / 0 / 0 | 0 / 0 / 0 |
| … bei 12 mm | 0 / 0 / 0 | 0 / 0 / 0 |
| … bei 15 mm | 0 / 0 / 0 | 1,1 / 1,8 / 3,3 mm |
| … bei 20 mm | 0 / 0 / 0 | 4,7 / 7,9 / 10,8 mm |
| … bei 25 mm | 0,6 / 1,1 / 1,8 mm | 6,9 / 11,4 / 17,3 mm |

Damit gibt es Trainingsbeispiele für „15–25 mm hoch, bis ~11 mm daneben,
zurück zur Mitte“. Die Hänger bei 10–12 mm Höhe deckt V6 bewusst nicht ab,
das verbietet die Sicherheitsregel.

**Für die reale Aufnahme:** gleiche Option mit `25,11,7`. Die Prüfung
rechnet dort mit 7 mm Oberkante über PICK; der Nachlauf von 2,4 mm ist bei 0,02 m/s
gemessen. Bei schnellerem Endanflug ist er größer (9.18), dann FREE
entsprechend höher.

Testfahrt: nach den VM-Läufen (Job 13 wartet auf `VM_FERTIG`), Auswertung
wie V3 (nie geschlossen, Höhe/xy der Hänger, Griff, Tisch, Sprünge).

### 9.20 V7 Korrektur-Halt (Auftrag 22.11. abends, vom Anwender freigegeben, vor V6)

**Idee:** Die Policies, die nie schließen, stehen 10–19 mm hoch und ~12 mm
seitlich neben dem Objekt. V6 (9.19) bringt Versatz bis 12 mm Höhe, darf aber
nicht tiefer. V7 zeigt in 40 % der Episoden ausdrücklich, wie man aus genau
dieser Lage herauskommt: **versetzt ankommen, in Haltehöhe abbremsen, auf
gleicher Höhe seitlich (und in der Gier) korrigieren, dann senkrecht
absenken.** Die übrigen 60 % sind unverändert Basis, auch mit deren
Anflug-Versatz. Job `13_SIM_V7_korrektur_halt.job` läuft nach V3c; V6 wurde
zu Job 14.

**Bahn einer Korrektur-Episode** (`bc/korrektur_halt.py`, Option
`apps/record.py --korrektur-halt ANTEIL,MIN,MAX,HOEHE,OBERKANTE`, hier
`0.4,10,20,14,8.4`; Standard unverändert):

| Wegpunkt | Lage | Bewegung | Tempo |
|---|---|---|---|
| CLEAR_FOV, ANFLUG | wie Basis | PTP | wie Basis |
| PRE_PICK_VERSETZT | PRE_PICK + Versatz (10–20 mm, Richtung gleichverteilt), in 50 % der Episoden zusätzlich 10–20° um die Senkrechte gedreht | LIN, Überschleifen wie PRE_PICK | Transit |
| HALT_VERSETZT | über dem versetzten Punkt, **14 mm über PICK** | LIN senkrecht, Überschleifen 5 mm | Endanflug 0,02 m/s |
| HALT | über PICK, 14 mm, Gier wie PICK | LIN waagrecht (SLERP der Drehung), Überschleifen 1 mm | Endanflug 0,02 m/s |
| PICK, dann wie Basis | | LIN senkrecht | Endanflug 0,02 m/s |

- **Haltehöhe:** 14 mm = Oberkante über PICK (Sim 8,4 mm) + 3 mm Reserve
  + 2,4 mm Nachlauf (aufgerundet von 13,8 mm).
- **Kein Stillstand:** Beide Ecken werden überschliffen (Überlagerung der
  Rampen, `bc/trajectory.py`). An der Ecke fällt das Tempo auf ~5 mm/s,
  nicht auf 0.
- **Ecke HALT_VERSETZT:** Der verrundete Weg liegt innerhalb der Ecke, also
  nie unter der Haltehöhe.
- **Ecke HALT:** Der Radius ist mit 1 mm klein. Beim Absenken liegt die Bahn
  daher höchstens noch 1 mm neben der Mitte, gemessen 0,15 mm.
- Der normale Anflug-Versatz entfällt in diesen Episoden; das Rauschen kommt
  wie immer obendrauf.

**So wird das Label gebildet:** Für jede Korrektur-Episode erzeugt der Planer
aus den Wegpunkten oben eine eigene Idealbahn (`build_ideal_trajectory`,
gleiche Tempi und Rampen wie die Basis) und löst sie in Gelenke auf
(`solve_ideal`). Diese L-Bahn ist die `ideal`-Bahn des Plans:

- `action[t]` = ideale Gelenkstellung der L-Bahn bei t+1 plus
  Greiferbefehl (`bc/recorder.py`, unverändert);
- `aux.pose_ideal` und `aux.joints_ideal` = die L-Bahn;
- die gefahrene Bahn = L-Bahn + Rauschen (`sample_noisy_poses`), wie in jeder
  Episode.

Das Label zeigt also in jedem Takt auf den nächsten Punkt der L-Bahn: oberhalb
der Haltehöhe senkrecht nach unten (versetzt), in Haltehöhe waagrecht zur
Mitte, danach senkrecht zum Griff. **Es zeigt nie schräg zur Mitte nach
unten.** In den Basis-Episoden ist das Label wie bisher die Idealbahn zum
geteachten PICK.

**Sicherheitsprüfung** (`korrektur_halt.clearance`):

- **Regel:** Solange die Backen gegen PICK mehr als das Spiel von 2,5 mm
  versetzt sind, muss gelten: TCP-Höhe über PICK − 2,4 mm Nachlauf ≥
  Oberkante 8,4 mm + 3 mm. Der Versatz ist dabei der xy-Abstand plus
  Drehwinkel × 29 mm Hebel.
- **Geprüft** werden je Takt und drei Zwischenschritte die Idealbahn (vor dem
  Planen) und jede verrauschte Bahn (`generate_plan(path_check=…)`).
  Verletzt eine verrauschte Bahn die Regel, wird das Rauschen neu gezogen
  (Grund `pfad`). Ist auch nach 20 Versuchen keine gültig, wird die Korrektur
  neu gezogen, höchstens 5 Mal.
- **Tests:** `tests/test_korrektur_halt.py` prüft: kein Anteil heißt keine
  Korrektur; die L-Bahn ist sicher, greift am PICK und hat keinen
  Stillstand; das Label läuft erst seitlich, dann senkrecht; die Prüfung
  meldet einen zu tiefen Versatz. Die Planer-Tests bleiben grün.

**Aufnahme** `data_sim_mujoco/jobs/aufnahme_v7.sh`:

- 407 Episoden in 13 min, 8/8 Prozesse ok. Eine Episode fehlt, weil eine
  Variante außerhalb des Bereichs lag (Lagen-Ziehung, nicht V7).
- Keine Lage nahe einer Testlage, `export.py --check` ohne Konflikt, Export
  nur bis Griff nach `datasets/sim_2026-11-22_V7_korrektur_halt_nur_griff`.
- Der Job beginnt mit `while [ -f data_sim_mujoco/jobs/VM_LAEUFT ]; do sleep
  60; done`.

Nachprüfung auf den aufgenommenen Bahnen
(`data_sim_mujoco/analyse_gier/korrektur_pruefen.py`):

| | Korrektur-Episoden | Basis-Episoden in V7 | Basis-Aufnahme |
|---|---|---|---|
| Anzahl | **162 (40 %)** | 245 | 815 |
| Versatz median (Spanne), mit Drehung | 14,6 mm (10,1–20,0), 76 mit median 14,9° | – | – |
| Backenregel verletzt (Label-Bahn / gefahrene Soll-Bahn) | **0 / 0**, kleinster Freiraum 0,20 / 0,19 mm | – | – |
| Label unter der Haltehöhe seitlich max | **0,15 mm** | – | – |
| Label 2 mm über der Haltehöhe noch voll versetzt | 162/162 | – | – |
| Ist-Bahn (Folgemodell): kleinste Höhe, solange > 2,5 mm daneben | median 14,0, min 13,6 mm | – | – |
| Takte bis Griff median (max) | 116 (136) | 100 (117) | 100 (119) |
| Schleppfehler max je Episode median / p95 | 0,068 / 0,087 rad | 0,068 / 0,096 rad | 0,068 / 0,093 rad |

- Die Ist-Bahn sinkt an der Ecke bis 0,4 mm unter die Haltehöhe. Das liegt
  im Schleppfehler des Folgemodells und ist durch die 2,4 mm Nachlauf der
  Regel gedeckt.
- Korrektur-Episoden sind ~16 Takte (~1 s) länger. Das Takt-Limit der
  Testfahrt (1,5 × längste Episode) wird dadurch größer. In der Auswertung
  wird darum auch gezählt, wie viele Griffe innerhalb des Basis-Limits
  (184 Takte) liegen.

**Objektkontakt durch die Backen** (für die Auswertung, auch rückwirkend):
Die Sim kennt keinen Kontakt. `data_sim_mujoco/analyse_gier/backen_kontakt.py`
rechnet ihn geometrisch nach:

- Je Testfahrt und Takt vor dem ersten Schließbefehl wird geprüft, ob ein
  Punkt der offenen Backen (untere 2 cm) im Objektquader liegt (60 × 40 ×
  15 mm, ohne Fase).
- Zwei Backenabstände: Sim offen 56 mm, real 44,8 mm.
- Kontrolle: Am idealen PICK berührt keine Backe das Objekt (0/60 Lagen bei
  beiden Abständen).

| Testfahrt | Kontakt bei 56 mm (Sim) | bei 44,8 mm (real) |
|---|---|---|
| Basis Seed 0 | 16/60 | 32/60 |
| V3 0,05 m/s | 12/60 | 24/60 |
| V3b zweistufig | 26/60 | 37/60 |

Das heißt: In der Sim fahren die Policies oft mit den Backen ins Objekt. Am
echten Arm wäre das Anstoßen oder Wegschieben, die Sim heftet trotzdem an
oder fährt durch. Das ist ein zusätzlicher Grund, warum Sim-Griffzahlen real
eher zu hoch sind.

Testfahrt V7: nach V3c (Job 12), Auswertung wie V3/V6 plus Kontakt und Griffe
im Basis-Takt-Limit.

### 9.21 Seed-Streuung V3: Endanflug 0,05 m/s Seed 0 gegen Seed 1

Training `checkpoints/SIM_V3_tempo005_seed1` (Job 11): V3-Datensatz, `--seed 1`
(auch neuer Val-Split). Testfahrt 23.11. 00:12, gleiche 60 Testlagen.

| | Basis Seed 0 | Basis Seed 1 | V3 Seed 0 | **V3 Seed 1** | V3 S0 gegen S1 |
|---|---|---|---|---|---|
| Griff | 20/60 | 21/60 | 37/60 | **39/60** | 0 : 2, p = 0,5 |
| Griff im Trainingsbereich | 14/27 | 15/27 | 23/27 | **23/27** | 0 : 0 |
| Annäherung median (alle / Trainingsbereich) | 10,0 / 7,1 mm | 10,1 / 3,8 mm | 4,2 / 2,8 mm | **5,0 / 3,0 mm** | Wilcoxon p = 0,23 / 0,78 |
| Tisch < 0 | 16 | 10 | 2 | **3** | 1 : 2 |
| Welligkeit median | 2,8 mm | 2,8 mm | 1,6 mm | **1,8 mm** | p = 0,008 (0,2 mm) |
| Backenkontakt Sim / real Abstand | 16 / 32 | 21 / 32 | 12 / 24 | **14 / 29** | – |

V3 Seed 1 gegen Basis: Griff 19 : 0 (Seed 0) und 18 : 0 (Seed 1), beide p < 0,001;
im Trainingsbereich 9 : 0 / 8 : 0 (p = 0,004 / 0,008).

- **Der V3-Effekt ist seed-fest.** Die Griffzahl streut zwischen den Seeds
  um 2 (Basis 1), der Abstand zur Basis ist 16–19. Im Trainingsbereich
  greifen beide V3-Seeds exakt dieselben 23 Lagen.
- Annäherung und Tisch bleiben ebenfalls auf V3-Niveau. Die Welligkeit ist
  mit Seed 1 0,2 mm höher (signifikant, aber klein und weiter deutlich unter
  der Basis).
- Backenkontakt bleibt auch mit V3 hoch: bei realem Backenabstand stößt etwa
  jede zweite Fahrt an (24 bzw. 29/60). Das Tempo senkt die Kontaktzahl nur
  wenig; Sim-Griffzahlen bleiben real eher zu optimistisch (9.20).
- Damit ist für die Tempo-Frage die Sicherheit „hoch“ (zwei Seeds, beide
  weit über der Basis-Streuung). Offen bleibt der Vergleich mit V3c 0,035 m/s
  (Job 12, Training läuft seit 00:04).

### 9.22 Ergebnis V3c Endanflug durchgehend 0,035 m/s

Training `checkpoints/SIM_V3c_tempo0035` (Job 12, Seed 0), Testfahrt 23.11. 02:54.
Der Datensatz hat andere Lagen-Ziehungen als Basis/V3 (9.18), die 60 Testlagen
sind dieselben.

| | Basis S0 / S1 | V3 0,05 S0 / S1 | **V3c 0,035** | V3b zweistufig |
|---|---|---|---|---|
| Griff | 20 / 21 | 37 / 39 | **34** | 19 |
| Griff im Trainingsbereich / außerhalb | 14 · 6 / 15 · 6 | 23 · 14 / 23 · 16 | **23 · 11** | 13 · 6 |
| Annäherung median (alle / Trainingsbereich) | 10,0 · 7,1 / 10,1 · 3,8 mm | 4,2 · 2,8 / 5,0 · 3,0 mm | **5,5 · 3,7 mm** | 11,7 · 5,6 mm |
| Tisch < 0 | 16 / 10 | 2 / 3 | **3** | 6 |
| Welligkeit median | 2,8 / 2,8 mm | 1,6 / 1,8 mm | **1,6 mm** | 2,4 mm |
| nie geschlossen (Annäherung der Hänger median) | 28 (24 mm) | 21 / 10 (28 / 25 mm) | **21 (25 mm)** | 34 (16 mm) |
| Backenkontakt Sim / realer Abstand | 16/32 · 21/32 | 12/24 · 14/29 | **15/30** | 26/37 |

Paartests V3c gegen …

| | Griff | im Trainingsbereich | Tisch < 0 | Annäherung |
|---|---|---|---|---|
| Basis Seed 0 | 1 : 15, p = 0,001 | 1 : 10, p = 0,01 | 15 : 2, p = 0,002 | p = 0,01 |
| Basis Seed 1 | 1 : 14, p = 0,001 | 1 : 9, p = 0,02 | 9 : 2, p = 0,07 | p = 0,04 |
| V3 Seed 0 | 4 : 1, p = 0,38 | 1 : 1 | 2 : 3 | p = 0,14 |
| V3 Seed 1 | 6 : 1, p = 0,13 | 1 : 1 | 2 : 2 | p = 0,10 |

- **V3c ist klar besser als die Basis und nicht unterscheidbar von V3.** Im
  Trainingsbereich greift V3c dieselbe Zahl (23/27) wie beide V3-Seeds.
- Außerhalb des Trainingsbereichs (viel Drehung) liegt V3c mit 11 knapp
  unter V3 (14/16). Gegen beide V3-Seeds geht das in dieselbe Richtung, ist
  aber nicht signifikant (p = 0,38 / 0,13). Grenzwertig ist allein Greif-xy
  gegen V3 Seed 0 (+1,4 mm, p = 0,02), gegen Seed 1 nicht (p = 0,17).
- Die Hänger von V3c bleiben wie bei V3 bei ~25 mm Annäherung stehen (Policy
  wird vor dem Objekt unsicher), nicht wie bei V3b knapp über dem Objekt
  (16 mm, „Schleichen“).
- Backenkontakt wie V3 (real ~jede zweite Fahrt).
- **Folgerung für die Tempo-Frage:** Der Gewinn kommt aus dem gleichmäßigen,
  zügigen Endanflug ohne Abbremsstufe. Zwischen 0,035 und 0,05 m/s zeigt die
  Sim keinen belastbaren Unterschied; 0,035 m/s kostet höchstens wenige
  Griffe bei großer Drehung. Real spricht für 0,035 m/s der kleinere
  Nachlauf (9.18: hochgerechnet ~4,9 statt ~7 mm Überschwinger), was die Sim
  nicht modelliert.

### 9.23 Ergebnis V7 Korrektur-Halt

Training `checkpoints/SIM_V7_korrektur_halt` (Job 13, Seed 0), Testfahrt 23.11.
05:33, gleiche 60 Testlagen. V7 fährt sonst wie die Basis (Endanflug
0,02 m/s), daher ist die Basis die Vergleichsgröße, nicht V3. Die Korrektur-
Episoden sind länger, deshalb lag das Takt-Limit der Testfahrt bei 256 statt 184.

| | Basis S0 / S1 | **V7 Korrektur-Halt** | V7 gegen Basis S0 / S1 |
|---|---|---|---|
| Griff | 20 / 21 | **23** | 10 : 7 (p = 0,63) / 8 : 6 (p = 0,79) |
| davon innerhalb 184 Takte | 20 / 21 | **21** | – |
| Griff im Trainingsbereich / außerhalb | 14 · 6 / 15 · 6 | **16 · 7** | 5 : 3 / 5 : 4, n. s. |
| Griff richtig herum / um 180° verdreht | 15 · 5 / 15 · 6 | **16 · 7** | – |
| Annäherung median (alle / Trainingsbereich) | 10,0 · 7,1 / 10,1 · 3,8 mm | **7,2 · 3,7 mm** | p < 0,001 / p = 0,001 (alle) |
| Tisch < 0 | 16 / 10 | **6** | 5 : 15 (p = 0,04) / 5 : 9 (p = 0,42) |
| Welligkeit median | 2,8 / 2,8 mm | **2,3 mm** | n. s. |
| nie geschlossen | 28 / – | **21** | – |
| geschlossen, aber kein Griff | 12 / – | **16** | – |
| Takte bis Griff median / max | 94 / 112 | **109 / 204** | – |
| Backenkontakt Sim / realer Abstand | 16/32 · 21/32 | **26/37** | – |
| Val-MAE / p95 | 0,0043 / 0,0158 rad | **0,0088 / 0,0314 rad** | doppelt so hoch |

Höhe und xy der Hänger (Werkzeugspitze im Objekt-KS am Ende der Fahrt, Höhe
über PICK):

| | nie geschlossen | davon Ende in 10–20 mm Höhe | xy-Abstand dieser Hänger |
|---|---|---|---|
| Basis S0 | 28 | 6 | median ~20 mm |
| V3c | 21 | 7 | median ~20 mm |
| **V7** | **21** | **14** | **median 7 mm** (2–30) |

Die Fahrten, die geschlossen haben, ohne zu greifen (16), schließen in
PICK-Höhe (median 3,8 mm unter PICK) mit median 15 mm xy daneben. Am echten
Arm hieße das: Backe auf dem Objekt.

- **Kein Gewinn bei den Griffen.** 23 gegen 20/21, paarweise nicht
  signifikant. Innerhalb des Basis-Takt-Limits sind es 21, also gleich viel
  wie die Basis.
- **Annäherung und Tisch besser.** Die Policy bleibt öfter über dem Tisch
  (6 gegen 16, gegen Seed 0 signifikant) und kommt näher ans Objekt. Das
  passt zum gelernten Halt in Haltehöhe.
- **Neue Hänger-Art: Stehenbleiben in Haltehöhe.** 14 der 21 nie
  geschlossenen Fahrten enden 10–20 mm über PICK, also genau um die
  Haltehöhe (14 mm). Meist stehen sie fast mittig (median 7 mm). Die Policy
  hat den Halt gelernt, aber nicht zuverlässig das anschließende senkrechte
  Absenken. Vermutliche Ursache: In Haltehöhe ist das Label mehrdeutig, je
  nach Versatz seitlich oder nach unten, mit sehr langsamem Übergang
  (~5 mm/s an der Ecke). Die Policy mittelt daraus ein „fast Stehen“. Darauf
  passt auch der doppelte Val-MAE.
- **Mehr Backenkontakt** (26/37 gegen 16/32). Die Korrektur hält in der
  Testfahrt die Backen nicht vom Objekt fern, weil die Policy oft ohne
  Korrektur absenkt und in PICK-Höhe daneben schließt.
- **Folgerung:** V7 in dieser Form bringt in der Sim keinen Vorteil und
  erzeugt eine neue Hänger-Art. Für die reale Aufnahme würde ich den
  Korrektur-Halt nicht übernehmen. Offen und nicht getestet ist die
  Kombination mit dem schnelleren Endanflug (0,035 m/s) und ein Halt mit
  zügigerer Ecke. Das wäre ein eigener Versuch, falls das Thema weiter
  interessiert.

### 9.24 Entscheidungstabelle für die reale Aufnahme (Stand 23.11. früh)

Bewertungsregel wie 9.11: Ein Unterschied zählt nur, wenn er gegen **beide**
Basis-Seeds in dieselbe Richtung geht und deutlich größer ist als deren
Abstand (Griff 20/21, Annäherung 10,0/10,1 mm). V6 (Anflug-Versatz näher am
Objekt, Job 14) ist um 08:56 nachgetragen (9.25).

| Frage | Ergebnis Sim | Sicherheit (Seed-Streuung) | Was die Sim nicht abbildet |
|---|---|---|---|
| **Tempo Endanflug** 0,02 / 0,035 / 0,05 m/s / zweistufig | 0,035 (34) ≈ 0,05 (37 / 39) **≫** 0,02 (20 / 21) ≈ zweistufig 0,05 → 0,02 (19). Gleichmäßig zügig ist entscheidend, ein Abbremsen vor dem Objekt führt zu „Schleichen“ und Hängern. | **hoch**: 0,05 mit zwei Seeds (37/39, 0 : 2), beide 16–19 Griffe über der Basis; 0,035 gegen 0,05 nicht unterscheidbar (p = 0,13–0,38). | Nachlauf/Überschwinger und Tischabstand des echten Arms (Planer: ~4,9 mm bei 0,035 statt ~7 mm bei 0,05, hochgerechnet, 9.18); Bewegungsunschärfe im Wrist-Bild; Anstoßen/Wegschieben beim Schließen (Sim heftet an). |
| **Drehversatz** 10–15° ohne Ausreißer (V2) | kein Unterschied (18 gegen 20/21, Annäherung gleich) | mittel (ein Seed, Abstand im Zufallsbereich) | echte Gier-Schätzung der Kamera; V2 nimmt auch die seitlichen Ausreißer heraus. |
| **Licht Wrist** dunkel/verrauscht wie C2 (V4) | **schlechter**: Griff 12 gegen 20/21 (p = 0,02 gegen beide), Annäherung +2,3–2,6 mm; Val-MAE unverändert | mittel–hoch (ein Seed, aber gegen beide Basis-Seeds signifikant) | echter Sensor (Rauschen, Belichtungsregelung, Reflexe); die Größe ist nicht übertragbar, nur die Richtung. |
| **Episodenzahl** 200 / 400 / 600 / 815 | 200 klar schlechter (12, Annäherung +2 mm); ab 400 flach (17 / 20–21 / 21) | hoch für 200 < 400; mittel für „ab 400 flach“ (je ein Seed, feste 10 000 Schritte) | Die Sim ist leichter als die Anlage; real stieg die Lernkurve G2 bis 100 % noch an. |
| **Nur Griff** gegen ganze Episode (V5) | ganze Episode schlechter in der Annäherung (+2,3 mm), Griff gleich | mittel–hoch (Annäherung über der Seed-Streuung) | – (gleiche Richtung wie real G gegen G2) |
| **Korrektur-Halt** (V7) | kein Gewinn (23 gegen 20/21, n. s.), neue Hänger in Haltehöhe (14 von 21), mehr Backenkontakt (37/60 real) | mittel (ein Seed) | Kontakt/Anstoßen (geometrisch nachgerechnet, 9.20); echte Haltezeit am Arm. |
| **Anflug-Versatz näher** (V6, FULL 25 / FREE 12 mm) | kein Gewinn bei den Griffen (19 gegen 20/21); Annäherung −3 mm gegen beide Seeds, aber mehr Backenkontakt (40/60 real) und etwas mehr Welligkeit | mittel (ein Seed; Annäherung über der Seed-Streuung, Griff nicht) | Kontakt/Anstoßen (geometrisch nachgerechnet); Nachlauf in Objektnähe nur über die 2,4-mm-Reserve. |

Gesamttabelle aller Sim-Testfahrten (60 Testlagen, Testfahrt wie VM):

| Variante | Griff | im Trainingsbereich (27) | Annäherung median | Tisch < 0 | Backenkontakt real Abstand | Seeds |
|---|---|---|---|---|---|---|
| Basis 400 (0,02 m/s) | 20 / 21 | 14 / 15 | 10,0 / 10,1 mm | 16 / 10 | 32 / 32 | 2 |
| Menge 200 | 12 | 11 | 12,8 mm | 15 | – | 1 |
| Basis 600 | 17 | 11 | 8,1 mm | 6 | – | 1 |
| V1 Menge 815 | 21 | 16 | 9,8 mm | 9 | – | 1 |
| V5 ganze Episode | 18 | 15 | 12,4 mm | 5 | – | 1 |
| V2 Drehversatz 10–15° | 18 | 11 | 9,8 mm | 12 | – | 1 |
| **V3 0,05 m/s** | **37 / 39** | **23 / 23** | **4,2 / 5,0 mm** | 2 / 3 | 24 / 29 | 2 |
| V3b zweistufig 0,05 → 0,02 | 19 | 13 | 11,7 mm | 6 | 37 | 1 |
| **V3c 0,035 m/s** | **34** | **23** | **5,5 mm** | 3 | 30 | 1 |
| V4 Wrist dunkel | 12 | 9 | 13,8 mm | 15 | – | 1 |
| V7 Korrektur-Halt | 23 | 16 | 7,2 mm | 6 | 37 | 1 |
| V6 Versatz näher | 19 | 12 | 7,3 mm | 15 | 40 | 1 |

Seed-Streuung (zwei Paare): Basis 20 / 21 (6 : 7 diskordant), V3 37 / 39
(0 : 2). Griff gesamt und Annäherung über alle 60 Lagen sind stabil, Greif-xy,
Endstellung und Tisch nicht (9.11).

**Empfehlung für die Aufnahme am Montag (ehrlich):**

1. **Endanflug durchgehend 0,035 m/s, ohne Abbremsstufe.** Das ist das
   einzige Ergebnis der Sim, das weit über die Seed-Streuung geht. 0,035 und
   0,05 sind in der Sim gleich gut; 0,035 ist real der vorsichtigere Wert
   (weniger Nachlauf und Unschärfe). Vor der Aufnahme lohnt eine kurze
   Probefahrt am Arm, die den Überschwinger und den Tischabstand bei
   0,035 m/s misst, denn genau das kann die Sim nicht.
2. **Licht am Wrist so hell und ruhig wie möglich.** Das ist die zweite
   belastbare Richtung (V4). Die Größe ist offen.
3. **Nur bis zum Griff exportieren** (V5), wie bisher.
4. **Drehversatz und Korrektur-Halt nicht ändern bzw. nicht übernehmen.**
   V2 zeigt keinen Effekt, V7 keinen Gewinn und eine neue Fehlerart.
5. **Episodenzahl:** Die Sim sagt „400 reichen, 200 nicht“. Real ist die
   Kurve noch nicht flach (G2), also so viele wie im Termin gut gehen,
   mindestens ~400.
6. **Termin:** Aus Sicht der Sim spricht nichts gegen Montag. Die
   entscheidende Einstellung (Tempo) ist gesichert, V6 bringt keinen Griff-Gewinn
   (9.25), der Anflug-Versatz bleibt also wie bisher. Unsicher
   bleibt, wie viel vom Sim-Gewinn real ankommt: Die Sim-Griffzahlen sind
   wegen Anheften statt Anstoßen eher zu hoch (Backenkontakt real in der
   Hälfte der Fahrten, 9.20).

### 9.25 Ergebnis V6 Anflug-Versatz näher am Objekt (FULL 25 / FREE 12 mm)

Training `checkpoints/SIM_V6_versatz_nah` (Job 14, Seed 0, nach dem VM-Lauf
06:12–08:50), Testfahrt 08:56. Gleiche Lagen und gleiche Versatz-Ziehungen
wie die Basis (9.19), gleiche Val, nur das Versatz-Profil liegt näher am Objekt.
Die Val-MAE ist deshalb direkt mit Seed 0 vergleichbar.

| | Basis S0 / S1 | **V6** | V6 gegen Basis S0 / S1 |
|---|---|---|---|
| Griff | 20 / 21 | **19** | 6 : 5 (p = 1,0) / 7 : 5 (p = 0,77) |
| Griff im Trainingsbereich / außerhalb | 14 · 6 / 15 · 6 | **12 · 7** | 4 : 2 / 6 : 3, n. s. |
| davon richtig herum | 15 / 15 | 12 | n. s. |
| Annäherung median (alle 60) | 10,0 / 10,1 mm | **7,3 mm** | −3,1 mm, p < 0,001 / p = 0,001 |
| Tisch < 0 (nur berichtet) | 16 / 10 | 15 | n. s. |
| nie geschlossen (Annäherung) / geschlossen ohne Griff | 28 (24 mm) · 12 | 24 (21 mm) · 17 | – |
| Welligkeit median | 2,8 / 2,8 mm | **3,2 mm** | +0,4 mm, p = 0,007 / 0,04 |
| Backenkontakt Sim / realer Abstand | 16/32 · 21/32 | **25/40** | – |
| Val-MAE (gleiche Val wie S0) | 0,0043 rad | 0,0045 rad | – |

- **Kein Gewinn bei den Griffen.** 19 gegen 20/21, auch im Trainingsbereich
  eher weniger (12 gegen 14/15). Alles liegt im Zufallsbereich.
- **Die Annäherung wird kleiner (−3 mm gegen beide Seeds), aber das hilft
  nicht.** Dasselbe gilt für V7 (7,2 mm). Beide Varianten lehren, mit Versatz
  näher ans Objekt heranzufahren. Die Policy kommt dadurch näher, aber öfter
  daneben: 17 Fahrten schließen ohne Griff, und Backenkontakt bei realem
  Abstand gibt es in 40/60 Fahrten (Basis 32).
- Die Welligkeit steigt leicht (+0,4 mm). Das passt zum späteren Ausblenden
  des Versatzes, der jetzt näher am Griff abgebaut wird.
- **Folgerung:** Den Anflug-Versatz für die reale Aufnahme nicht näher ans
  Objekt legen. Die bisherige Einstellung bleibt.
