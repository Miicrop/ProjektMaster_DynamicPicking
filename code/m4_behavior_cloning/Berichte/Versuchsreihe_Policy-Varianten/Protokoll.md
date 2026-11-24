# Versuchsreihe Policy-Varianten – Protokoll

> **Verwendung offen:** Ob diese Reihe in den finalen Bericht kommt oder für eine andere Arbeit aufgehoben
> wird, ist noch nicht entschieden (Anwender, 2026-11-13).

Plan und Testlagen: `Versuchsplan.md`, `testlagen.json`. Alle VM-Fahrten mit `is_robot_in_simulation() ==
True`; **keine Anlagenmessung**.

---

## Versuch I – Inferenz-Einstellungen (Checkpoint 2026-11-09, ohne Training)

**Datum:** 2026-11-13, 13:55–14:40

**Zweck:** Weniger Mitteln der überlappenden Chunks (neuere Vorhersagen stärker gewichten, seltener neu
planen) soll das „Mitteln zwischen bleiben und losfahren“ am Greifpunkt verringern.

**Vorgehen:** `skripte/stufe2_vm.py --replay data/2026-11-11 --replay-episode <T60>` mit je einer
Änderung gegenüber Standard (`replan 2`, `decay 0`). Standard = die Fahrten der Hauptreihe vom 13.11.
auf denselben 59 Episoden. Auswertung `skripte/eval_stufe2.py`, `skripte/schwingen.py`, `skripte/vergleich.py`.
Fahrten: `checkpoints/2026-11-09/policy/rollouts/2026-11-13_inferenz_*`, Logs `logs/inferenz_*.log`.

| Lauf | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy beim Schließen median | unter Tisch | tiefer als −10 mm | ServoGuard-Abbruch | Endstellung | Querabw. p95 median | Welligkeit median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Standard (replan 2, decay 0) | 59 | 11,6 mm | 47 % | 49 mm | 18,9 mm | 56 % | 37 % | 20 % | 59 % | 25,0 mm | 10,1 mm |
| decay 0,5 | 59 | 14,7 mm | 37 % | 44 mm | 27,5 mm | 68 % | 56 % | 15 % | 61 % | 38,7 mm | 18,7 mm |
| replan 4 | 56 | 16,1 mm | 27 % | 84 mm | 37,3 mm | 79 % | 59 % | 29 % | 43 % | 72,9 mm | 22,3 mm |
| ohne Mitteln (replan 8) | nur T20, siehe Nachtrag | | | | | | | | | | |

**Störung:** Nach 56 von 59 Fahrten mit `replan 4` antwortete die Robotersoftware in der VM nicht mehr
(„Cross-check whether the robot is reachable…“, Ping zur VM weiter in Ordnung). Die Sicherung im Adapter
verweigerte danach jede Bewegung (`is_robot_in_simulation()` = None). `summary.json` für `replan 4` aus der
Konsolenausgabe nachgebaut (`skripte/summary_aus_log.py`). „Ohne Mitteln“ ist nicht gelaufen.

**Nachtrag 15:25 – „ohne Mitteln“ auf T20** (nach Neustart der VM durch den Anwender; Host hatte laut
Windows-Ereignisprotokoll seit 11:07 keinen Ruhezustand, die VM lief unverändert seit 10:54 – Ursache war
vermutlich ein Hänger der Robotersoftware in der VM nach ~3,5 h Dauerbetrieb, nicht der Standby):

| Lauf (nur T20, je Lage die ruhigste Episode) | Fahrten | nächste Annäherung median | ≤ 10 mm | unter Tisch | tiefer als −10 mm | ServoGuard-Abbruch | Endstellung |
|---|---:|---:|---:|---:|---:|---:|---:|
| Standard (replan 2, decay 0) | 20 | 9,5 mm | 55 % | 50 % | 30 % | 1 | – |
| decay 0,5 | 20 | 12,8 mm | 42 % | 60 % | 60 % | 5 | – |
| replan 4 | 19 | 15,8 mm | 28 % | 79 % | 58 % | 3 | – |
| ohne Mitteln (replan 8, synchron) | 20 | 9,0 mm | 60 % | 55 % | 35 % | 2 | 17/20 |

„Ohne Mitteln“ ist etwa gleichauf mit dem Standard, beim Tisch nicht besser. Synchron vorhergesagt steht
der Arm alle 8 Takte für die Vorhersage (~85 ms) – 2116 Takt-Überläufe in 20 Fahrten; an der Anlage
ruckelt das, als Einstellung ungeeignet.

**Ergebnis:** Beide Änderungen sind **schlechter** als der Standard – in jeder Kennzahl bis auf die
Abbrüche bei `decay 0,5`. Weniger Mitteln macht die Fahrt unruhiger (Welligkeit 10 → 19–22 mm) und
tiefer (unter Tisch 56 → 68–79 %). Das Mitteln glättet also eher, als dass es schadet; die Ursache des
Abtauchens liegt nicht in der Inferenz-Einstellung. „Ohne Mitteln“ dürfte nach diesem Trend noch
schlechter sein und hat damit geringe Priorität.

**Folgerung:** Standard-Einstellung beibehalten. Der Hebel liegt bei den Daten (Varianten B, C, D).

---

## Versuche A–D – Datenvarianten (je 10 000 Schritte)

**Datum:** Training 2026-11-13 15:39 – 2026-11-14 04:18, VM 2026-11-14 04:22–05:41

**Vorgehen:** Export `tools/export_variante.py` (Quellen 02., 03., 09., 11.11. ohne Testlagen), Training
`apps/train.py --steps 10000 --batch-size 128` (Seed 0), VM-Replay T60 mit `skripte/stufe2_vm.py`, Auswertung
wie Versuch I. Ketten: `skripte/kette_ABD.sh`, `kette_C.sh`, `kette_vm.sh`; Logs `logs/`.

**Training:** 3,0–3,3 h je Variante statt 77 min beim Checkpoint 2026-11-09 – Datenladen 0,75–1,0 s/Schritt
(AV1-Dekodierung per PyAV auf der CPU, torchcodec lädt nicht), GPU-Schritt unverändert 0,31 s.

| Variante | Episoden | val Gelenk-MAE / p95 | Greifer val |
|---|---:|---:|---:|
| A Basis | 694 | 0,0084 / 0,032 rad | 99,9 % |
| B Pause kurz | 694 | 0,0081 / 0,031 rad | 99,9 % |
| C Nur Griff | 694 | 0,0075 / 0,029 rad | 97,5 % |
| D Eine Drehung | 529 | 0,0082 / 0,029 rad | 100 % |

(C: val-Loss 0,0115 statt 0,0005 – Episoden enden 3 Takte nach dem Schließen, Chunks bestehen am Ende
großteils aus Auffüllung; nicht mit den anderen vergleichbar.)

**Störung VM, erster Lauf (verworfen):** Die neuen Policies bringen `table`/`tcp_envelope` mit. In der VM
(ohne Tool) ordnet der Adapter den Stützpunkt „tool“ dem Flansch zu – der Geofence prüfte einen Punkt
197,5 mm zu hoch, schon die Startstellung lag 135 mm über der Hülle → jede Fahrt im 1. Takt gestoppt.
Behoben in `skripte/stufe2_vm.py` (Stützpunkt „tool“ mit Tool-Versatz), geprüft mit `skripte/probe_geofence.py`
(Start/Griff frei, Spitze beim Griff 7–10 mm über Tisch). Anlage nicht betroffen (Tool eingerichtet).
Fahrten unter `rollouts/verworfen_2026-11-14_geofence-flansch`.

**Bedingungen VM-Vergleich:** `GEOFENCE=alt` – Kollisionsmodell wie beim Checkpoint 2026-11-09 (nur grober
Tischquader, jetzt mit richtigem Werkzeugpunkt: greift ab ~55 mm unter dem Tisch). Zusätzlich der alte
Checkpoint unter genau diesen Bedingungen wiederholt (Streuung zwischen zwei VM-Durchläufen).

| Lauf | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy beim Schließen median | unter Tisch | tiefer als −10 mm | ServoGuard-Abbruch | Endstellung | Querabw. p95 median | Welligkeit median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-09 (13.11.) | 59 | 11,6 mm | 47 % | 49 mm | 18,9 mm | 56 % | 37 % | 20 % | 59 % | 25,0 mm | 10,1 mm |
| 2026-11-09 (14.11. Wdh.) | 59 | 10,2 mm | 50 % | 43 mm | 18,6 mm | 54 % | 34 % | 32 % | 41 % | 25,0 mm | 10,4 mm |
| A Basis | 59 | 15,3 mm | 28 % | 67 mm | 28,4 mm | 58 % | 42 % | 25 % | 64 % | 50,1 mm | 13,1 mm |
| B Pause kurz | 59 | 15,6 mm | 32 % | 64 mm | 20,8 mm | 46 % | 31 % | 29 % | 59 % | 33,4 mm | 10,3 mm |
| C Nur Griff | 59 | 17,5 mm | 20 % | 52 mm | 23,2 mm | 36 % | 24 % | 14 % | 85 % | 43,4 mm | 13,7 mm |
| D Eine Drehung | 59 | 16,6 mm | 33 % | 52 mm | 26,8 mm | 59 % | 42 % | 36 % | 61 % | 47,5 mm | 15,8 mm |

**Streuung zwischen zwei VM-Durchläufen desselben Modells** (Zeilen 1–2): Annäherung und Tisch stabil
(±1,5 mm, ±3 Pp.), ServoGuard-Abbruch und Endstellung schwanken um 12–18 Pp. → diese beiden Spalten nur
bei großen Unterschieden deuten.

**Befunde:**

1. **Alle neuen Varianten treffen schlechter als der alte Checkpoint** (15–17 mm statt 10–12 mm, Querabweichung
   im Anflug doppelt). Export geprüft (`skripte/export_gleich.py`): die 602 gemeinsamen Episoden sind in A
   bitgleich, Normierung praktisch gleich; A = alter Datensatz + 92 Episoden vom 11.11.
2. **Kein „Sog“ zu den gelernten Lagen vom 11.11.** (`skripte/sog.py`): A–D greifen +6…+10 mm in Richtung der
   nächsten gelernten 11.11.-Lage, der alte Checkpoint – der diese Lagen nie gesehen hat – genauso (+6,9 mm).
   Das Maß spiegelt die Lagenverteilung, kein Auswendiglernen.
3. **Tisch:** gegenüber A senken B (58 → 46 %, tiefer als −10 mm 42 → 31 %) und vor allem C (36 % / 24 %) das
   Abtauchen. D ändert nichts.
4. **C:** 85 % Endstellung, wenigste Abbrüche (14 %); der geplante Transport läuft. Ein Fall „Transport nicht
   planbar: Werkzeug am Tisch (−1 mm)“ – die Policy schloss unter Tischhöhe. Greifgenauigkeit am
   schlechtesten (20 % ≤ 10 mm).
5. **D (eine Drehung)** bringt keinen Gewinn bei Genauigkeit, hat aber 165 Demos weniger.

**Offene Frage:** Ist der Abstand zum alten Checkpoint Streuung zwischen Trainings (jede Variante nur einmal
trainiert; anderer Datensatz = andere Aufteilung und Reihenfolge) oder eine Folge der Daten vom 11.11.?
→ Kontrolle: alter Datensatz mit Seed 1 neu trainiert (`skripte/kette_kontrolle.sh`, 6 statt 4 Datenlader),
danach VM T60.

### Kontrolle Trainingsstreuung (2026-11-14 06:06–09:27)

Alter Datensatz `datasets/2026-11-09`, Seed 1 statt 0, sonst gleich (6 statt 4 Datenlader: nur ~15 % schneller,
CPU voll). VM T60 wie oben.

| Lauf | nächste Annäherung median | ≤ 10 mm | p90 | unter Tisch | tiefer als −10 mm | Endstellung | Querabw. p95 median |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-11-09 Seed 0 (Wdh.) | 10,2 mm | 50 % | 43 mm | 54 % | 34 % | 41 % | 25,0 mm |
| 2026-11-09 Seed 1 | 10,6 mm | 50 % | 35 mm | 59 % | 42 % | 59 % | 33,1 mm |

Paarweise je Testlage (Median je Lage, 20 Lagen; Vorzeichentest, Bootstrap über Lagen):

| Vergleich | Lagen schlechter | p | Diff. Median (95 %-KI) |
|---|---:|---:|---:|
| Seed 1 gegen Seed 0 | 9/20 | – | −2,2 mm (−9,4…+4,3) |
| A gegen alt (Mittel beider Seeds) | 17/20 | 0,001 | +8,3 mm (+0,7…+19,3) |
| B gegen alt | 13/20 | 0,13 | +5,3 mm (−2,3…+9,9) |
| C gegen alt | 15/20 | 0,02 | +9,4 mm (+1,8…+13,1) |
| D gegen alt | 14/20 | 0,06 | +9,4 mm (−2,2…+13,3) |

**Ergebnis:** Die Streuung zwischen Trainings ist klein. Die 92 Episoden vom 11.11. verschlechtern die
Greifgenauigkeit auf den Testlagen vom 11.11. tatsächlich (A deutlich, C ebenfalls).

**Suche nach der Ursache in den Daten** (`skripte/tage_vergleich.py`, `skripte/bahnform.py`) – ohne Befund:
Label-Vorlauf (2 Takte), Label–Ist-Abstand, Glätte der Labels, Rauschen (ideal–verrauscht p95 20,7 mm am 11.11.
gegen 16,7–18,3 mm), Sync, Bahnform (seitliche Abweichung, Scheitel, Höhe vor dem Griff, Weglänge) und
Sequenzpunkte sind an allen Tagen gleich. Szenekamera am 11.11. an derselben Stelle wie am 09.11.; Bilder
heller (Helligkeit Szene 104 gegen 53 am 09.11. und ~130 am 02./03.11.).

**Verdacht Testverfahren:** Im Replay zeigen die Bilder den Arm dort, wo er bei der Aufnahme war (mit
Rauschen), nicht wo er jetzt ist. Ein Modell, das Bilder vom 11.11. kennt, könnte diesen Bildern stärker folgen
und gegen sie korrigieren – passend zur verdoppelten Querabweichung. Prüfung: Bildwahl nach Position
(`BILDWAHL=position`) für alten Checkpoint und A.

**Prüfung Bildwahl nach Position** (2026-11-14 09:29–10:13, `BILDWAHL=position`, sonst wie oben):

| Lauf | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy median | unter Tisch | Querabw. p95 median |
|---|---:|---:|---:|---:|---:|---:|
| alt, Bild je Takt | 10,2 mm | 50 % | 43 mm | 18,6 mm | 54 % | 25,0 mm |
| alt, Bild nach Position | 11,9 mm | 44 % | 31 mm | 17,5 mm | 54 % | 24,7 mm |
| A, Bild je Takt | 15,3 mm | 28 % | 67 mm | 28,4 mm | 58 % | 50,1 mm |
| A, Bild nach Position | 14,1 mm | 30 % | 35 mm | 28,2 mm | 56 % | 38,9 mm |

A bleibt schlechter (15/20 Lagen, p = 0,02). Die Ausreißer von A (p90 67 → 35 mm) und ein Teil der
Querabweichung sind Replay-Artefakt, der Abstand im Median nicht. **Verdacht Testverfahren damit nicht
bestätigt; Ursache der Verschlechterung offen.**

**Zwischenstand 14.11.:**

* Bestes Modell für die Greifgenauigkeit bleibt der Checkpoint 2026-11-09 (alter Datensatz, beide Seeds
  ~10–11 mm). Er hat die Testlagen vom 11.11. nie gesehen – er generalisiert über den Tag hinweg.
* Nur-Griff mit geplantem Transport (C) senkt das Abtauchen und die Abbrüche deutlich, kostet aber
  Genauigkeit – vermutlich nicht wegen C selbst, sondern weil C wie A die Daten vom 11.11. enthält.
* Naheliegender nächster Versuch: **C′ = C auf dem alten Datensatz** (02./03./09.11., `--abschneiden-nach 3`),
  trennt den Effekt von C vom Effekt der Daten vom 11.11.

### Kameralage und Not-Aus-Läufe (Frage Anwender 14.11.)

**Kamera** (`skripte/kameralage.py`, Abbildung `abbildungen/kameralage_tage.png`): Startbild (Takt 0, gleiche
Startstellung) je Episode gegen das erste Bild vom 09.11., Merkmalsabgleich (ORB + RANSAC, Helligkeit
angeglichen).

| Tag | Szene: Versatz / Drehung | Hand: Versatz / Drehung | Metadaten `camera_pose` / Licht |
|---|---|---|---|
| 02.11. | +8 / −3 px, +3,6° | < 0,5 px, −0,2° | nominal / Decke aus |
| 03.11. | +8 / −10 px, +5,9° | < 0,5 px, −0,3° | nominal aber leicht gedreht / Decke an |
| 09.11. (Bezug) | 0 | 0 | stark gedreht / Decke aus |
| 11.11. | −0,2 / +0,1 px, +0,03° | < 0,5 px, −0,1° | stark gedreht / Decke aus |
| 11.11. Test (4 Ep., 14:45–14:56) | −0,5 / +0,2 px, +0,1° | < 0,5 px | „gedreht“ / Decke an |

**Die Kameras stehen am 11.11. exakt wie am 09.11.** (unter 1 px, unter 0,2°). Der einzige sichtbare
Unterschied ist das Licht: am 11.11. deutlich mehr Tageslicht, das lila Objekt erscheint in der Szenenkamera
fast weiß (wie am 02./03.11.), am 09.11. lila. Die Szenenkamera der Testlagen gleicht damit in der Lage dem
09.11., in der Helligkeit dem 02./03.11.

**Not-Aus-Läufe** (`skripte/notaus_suche.py`, Index, Höhenprotokoll):

| Episode | Befund | im Training |
|---|---|---|
| 11.11. ep_00150 („Test“, 14:45) | bricht nach 119 von 153 Takten ab, Schleppfehler 0,41 rad – Not-Aus-Bild; beim Export automatisch verworfen („arm folgt nicht“) | nein |
| 09.11. ep_00156 (14:02) | 14 von 165 Takten, Schleppfehler 0,50 rad, success = False | nein |
| 09.11. ep_00140 (13:40) | success = False | nein |
| 11.11. ep_00151–153 („Test 2“, 14:54–14:56) | vollständig, success = True, Decke an, andere Lage (x ≈ 0,51 m) | **ja (A–D)** |

Die Not-Aus-Läufe sind in keinem Datensatz. In A–D stecken aber die 3 „Test 2“-Episoden vom Nachmittag
(Licht an) – 3 von 694 Episoden, als Ursache für +8 mm unwahrscheinlich. Sonst am 11.11. nichts
Auffälliges: Schleppfehler median 0,069 rad (andere Tage 0,065–0,075), keine abgebrochenen Fahrten im
Höhenprotokoll. C′ enthält keine Daten vom 11.11. und ist davon ohnehin nicht betroffen.

## Versuch C′ (C auf dem alten Datensatz)

### Teil 1 (29 von 59 Fahrten, vor dem VM-Ausfall)

Export ohne 11.11. (`--abschneiden-nach 3`), 10 000 Schritte, Seed 0, Training 10:38–13:31. VM-Replay T60
mit `--transport-geplant` und `GEOFENCE=alt`. **Die VM fiel um 13:41 bei Fahrt 29 aus** (CORBA
COMM_FAILURE, Robotersoftware nicht erreichbar). `summary.json` der 29 fertigen Fahrten aus dem Log
nachgebaut (`skripte/summary_aus_log.py`). Die übrigen 30 Fahrten holt `skripte/kette_F2.sh` nach dem Training
von F nach (`vm_T60_rest`, zusammengeführt mit `skripte/rollouts_zusammen.py`).

Vergleich auf denselben 29 Replay-Episoden (10 Lagen), `skripte/teilvergleich.py`:

| Lauf | Fahrten mit Wert | nächste Annäherung median | ≤ 10 mm | p90 | unter Tisch | Endstellung |
|---|---:|---:|---:|---:|---:|---:|
| alter Checkpoint, Seed 0 (Wdh.) | 28/29 | 9,7 mm | 54 % | 34 mm | 48 % | 34 % |
| alter Datensatz, Seed 1 | 28/29 | 8,8 mm | 54 % | 29 mm | 66 % | 55 % |
| A | 28/29 | 20,9 mm | 21 % | 74 mm | 55 % | 48 % |
| C | 25/29 | 25,5 mm | 16 % | 80 mm | 34 % | 86 % |
| **C′** | 27/29 | **15,5 mm** | 30 % | 44 mm | 34 % | **93 %** |

Gepaart je Lage (Median der Lage, Vorzeichentest):

| Paar | schlechter / besser | Differenz median | p |
|---|---|---:|---:|
| C′ gegen alt (Mittel Seed 0/1) | 6 / 4 | +4,7 mm | 0,75 |
| C′ gegen C | 0 / 10 | −9,4 mm | 0,002 |
| C′ gegen A | 3 / 7 | −10,2 mm | 0,34 |
| C gegen alt (Kontrolle, dieselben Ep.) | 9 / 1 | +9,9 mm | 0,02 |

Vorläufiger Befund: Ohne die Daten vom 11.11. wird C auf allen 10 Lagen genauer (p = 0,002) – die
Verschlechterung von C kam zum großen Teil aus den Daten. Die Änderungen von C (Abschneiden, geplanter
Transport) behalten ihren Vorteil beim Durchfahren (Endstellung 93 % gegen 34–55 % beim alten Checkpoint, unter
Tisch 34 % gegen 48–66 %). Beim Anfahren liegt C′ mit 15,5 mm noch über dem alten Checkpoint (9–10 mm), der
Unterschied ist bei 10 Lagen aber nicht gesichert. Endgültig erst mit allen 59 Fahrten.

### Vollständig (59 Fahrten)

Rest (Fahrt 29–58) am 14.11. 23:08–23:18 nach VM-Neustart, zusammengeführt (`vm_T60_rest` → `vm_T60`).
Kein VM-Effekt erkennbar: Vorhersage 75–77 ms und Overruns ≈ 0 in beiden Hälften, bei allen Modellen.
`skripte/vergleich.py`:

| Lauf | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy beim Schließen | unter Tisch | ServoGuard-Abbruch | Endstellung | Querabw. p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| alt, Seed 0 (Wdh.) | 10,2 mm | 50 % | 43 mm | 18,6 mm | 54 % | 32 % | 41 % | 25,0 mm |
| alt, Seed 1 | 10,6 mm | 50 % | 35 mm | 18,0 mm | 59 % | 36 % | 59 % | 33,1 mm |
| A | 15,3 mm | 28 % | 67 mm | 28,4 mm | 58 % | 25 % | 64 % | 50,1 mm |
| C | 17,5 mm | 20 % | 52 mm | 23,2 mm | 36 % | 14 % | 85 % | 43,4 mm |
| **C′** | 15,5 mm | 32 % | 45 mm | **18,7 mm** | 47 % | **7 %** | **90 %** | 35,6 mm |

Gepaart je Lage (20 Lagen, `skripte/teilvergleich.py`):

| Paar | schlechter / besser | Differenz median | p |
|---|---|---:|---:|
| C′ gegen alt (Mittel Seed 0/1) | 13 / 7 | +1,4 mm | 0,26 |
| C′ gegen C | 4 / 16 | −2,1 mm | 0,012 |
| C′ gegen A | 8 / 12 | −7,0 mm | 0,50 |
| zum Vergleich: C gegen alt | 16 / 4 | +9,1 mm | 0,012 |

Befund:
- Die zweite Hälfte bestätigt die Richtung, schwächt sie aber ab: Ohne den 11.11. ist C auf 16 von 20 Lagen
  genauer (p = 0,012). Gegen den alten Checkpoint liegt C′ je Lage im Median nur +1,4 mm daneben und ist
  nicht gesichert schlechter (13/7, p = 0,26) – A und C waren es deutlich (17/20 bzw. 16/20).
- Beim Schließen des Greifers liegt C′ so nah am Objekt wie der alte Checkpoint (Greif-xy 18,7 gegen
  18,0–18,6 mm), die nächste Annäherung median bleibt mit 15,5 mm aber über 10–11 mm.
- C′ fährt am zuverlässigsten durch: ServoGuard-Abbrüche 7 % (alt 32–36 %), Endstellung 90 % (alt 41–59 %),
  weniger unter Tisch als der alte Checkpoint (47 % gegen 54–59 %).
- Damit ist C′ bisher der beste Kandidat für die Anlage: Greifgenauigkeit etwa wie der alte Checkpoint, Ablauf
  deutlich robuster.

## Versuch F (A + Licht-Augmentierung)

Datensatz `var_A` (mit 11.11.), Seed 0, 10 000 Schritte, `apps/train.py --licht-augment` (Helligkeit 0,6–1,5,
Kontrast 0,7–1,3, Sättigung 0,6–1,4, Farbton ±0,04; nur Trainingsbilder). Training 14.11. 13:43–19:02
(5 h 20 min statt 3 h 20 min bei A – die Augmentierung läuft wie die Videodekodierung auf der CPU, data
1,5 statt 1,1 s/Schritt). Validierung minimal besser als A (Gelenk-MAE 0,0078 gegen 0,0084 rad).
VM-Replay T60 23:18–23:39 (`skripte/kette_F2.sh`), `GEOFENCE=alt`, ohne `--transport-geplant` wie A.

| Lauf | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy beim Schließen | unter Tisch | ServoGuard-Abbruch | Endstellung | Querabw. p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| alt, Seed 0 (Wdh.) | 10,2 mm | 50 % | 43 mm | 18,6 mm | 54 % | 32 % | 41 % | 25,0 mm |
| alt, Seed 1 | 10,6 mm | 50 % | 35 mm | 18,0 mm | 59 % | 36 % | 59 % | 33,1 mm |
| A | 15,3 mm | 28 % | 67 mm | 28,4 mm | 58 % | 25 % | 64 % | 50,1 mm |
| **F** | 14,9 mm | 29 % | 41 mm | 26,9 mm | 63 % | 34 % | 39 % | 48,1 mm |
| C′ | 15,5 mm | 32 % | 45 mm | 18,7 mm | 47 % | 7 % | 90 % | 35,6 mm |

Gepaart je Lage (20 Lagen):

| Paar | schlechter / besser | Differenz median | p |
|---|---|---:|---:|
| F gegen A | 10 / 10 | −0,8 mm | 1,00 |
| F gegen alt (Mittel Seed 0/1) | 13 / 7 | +6,1 mm | 0,26 |
| F gegen C′ | 11 / 9 | +0,1 mm | 0,82 |

Befund:
- **Die Licht-Augmentierung holt die Genauigkeit nicht zurück.** F ist je Lage nicht von A zu unterscheiden
  (10/10, −0,8 mm); Greif-xy beim Schließen bleibt mit 26,9 mm bei A (28,4 mm), weit über dem alten
  Checkpoint (18 mm). Einziger Gewinn: weniger grobe Fehlanfahrten (p90 41 statt 67 mm).
- Damit ist die Lichtvermutung für die Verschlechterung durch den 11.11. **nicht bestätigt**. Entweder
  unterscheiden sich die Daten vom 11.11. anders als in Helligkeit/Farbe (z. B. Sättigung bis Weiß, die
  ColorJitter auf Trainingsbildern nicht nachbildet), oder die Ursache liegt nicht im Bild. Bisher
  ausgeschlossen: Export, Seed, Sog, Labels/Zeitbasis/Bahnform, Kameralage, Not-Aus-Läufe.
- Ablauf bei F schlechter als bei A (Endstellung 39 % gegen 64 %, ServoGuard 34 % gegen 25 %) – bei
  einem Seed und den bekannten ±12–18 Prozentpunkten Streuung zwischen Wiederholungen nicht belastbar.
- Ein Seed, eine VM-Wiederholung; die Aussage „F ≈ A“ stützt sich auf den gepaarten Lagenvergleich.
