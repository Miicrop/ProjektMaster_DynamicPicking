# Anleitung – Projekt „Dynamisches Greifen mit Sichtprüfung“

Stand: 26.09.2026 · Für alle im Team. Du brauchst keine Vorkenntnisse zum Projekt, nur einen
Windows-Laptop. Was schon funktioniert und was noch fehlt, steht in
[plan/06_roadmap.md → Zwischenstand](plan/06_roadmap.md#zwischenstand-2026-09-26).

**Inhalt**
1. [Worum es geht](#1-worum-es-geht)
2. [Einrichten (einmalig)](#2-einrichten-einmalig)
3. [Erster Start in 5 Minuten – ohne Hardware](#3-erster-start-in-5-minuten--ohne-hardware)
4. [Die GUI im Detail](#4-die-gui-im-detail)
5. [An deinem Modul arbeiten](#5-an-deinem-modul-arbeiten)
6. [Einstellungen](#6-einstellungen)
7. [Am echten Aufbau: Inbetriebnahme](#7-am-echten-aufbau-inbetriebnahme)
8. [Ergebnisse und Logs](#8-ergebnisse-und-logs)
9. [Tests](#9-tests)
10. [Spielregeln im Team](#10-spielregeln-im-team)
11. [Fehlersuche](#11-fehlersuche)
12. [Befehle auf einen Blick](#12-befehle-auf-einen-blick)

---

## 1. Worum es geht

Ein Neura-Roboter (LARA) greift ein Bauteil, das irgendwo im Arbeitsbereich liegt, legt es an
einer Prüfstation ab und sortiert es danach in **Gut** oder **Schlecht**.

```
 M1 Kamera oben          M2 Roboter               M3 Kamera seitlich        M2 Roboter
 findet Bauteil   ──►    greift, legt an    ──►   liest Seriennummer,  ──►  sortiert in
 (x, y, Winkel)          Prüfposition ab          misst Loch, sucht Kerbe   GUT / SCHLECHT
```

| Modul | Ordner | Wer |
|---|---|---|
| M1 Erkennung (Kamera oben) | `code/m1_vision_topdown/` | Person 1 |
| M2 Robotersteuerung | `code/m2_robot_control/` | Person 2 |
| M3 Sichtprüfung (Kamera seitlich) | `code/m3_inspection/` | Person 3 |
| M4 KI-Greifen (Alternative zu M1) | `code/m4_ai_grasping/` | Person 4 |
| Ablaufsteuerung, GUI, gemeinsamer Code | `code/orchestrator/`, `code/gui/`, `code/common/` | alle |

Weitere Ordner: `plan/` (Planung, Aufgaben, Entscheidungen), `thesis/` (Ausarbeitung in LaTeX),
`docs/neura/` (Herstellerdoku des Roboters), `code/config/system.yaml` (alle Einstellungen).

**Wichtigstes Prinzip:** Jedes Modul hat eine *Mock*-Variante (Attrappe) und eine *Testbild*- bzw.
*Simulator*-Variante. Dadurch läuft das Gesamtsystem jederzeit auf jedem Laptop, auch ohne Roboter
und Kameras, und jede Person kann ihr Modul allein weiterentwickeln.

## 2. Einrichten (einmalig)

1. **Python 3.11** installieren: <https://www.python.org/downloads/>.
   Im Installer **„Add python.exe to PATH“** anhaken.
2. **VS Code** installieren (<https://code.visualstudio.com/>), dazu die Erweiterung „Python“.
3. **Projekt klonen:** `git clone https://github.com/Miicrop/ProjektMaster_DynamicPicking.git`

   Das öffentliche Repo enthält aus Lizenzgründen **nicht** die Neura-PDFs (`docs/neura/`) und den
   Neura-Python-Client (`code/m2_robot_control/vendor/neurapy/robot.py`). Für die Arbeit an M1, M3,
   dem Ablauf mit Mock-/Simulator-Roboter und der GUI wird beides nicht gebraucht. Für den echten
   Roboter (M2) bei eurem Neura-Kontakt anfragen und an die genannten Stellen legen – siehe
   `code/m2_robot_control/vendor/README.md` und `docs/neura/README.md`.
   Der Ordner `resources/` (1,4 GB Steuerungssoftware) ist ebenfalls nicht im Repo und wird zum
   Arbeiten nicht gebraucht.
4. Eingabeaufforderung im Ordner `code` öffnen: im Explorer in den Ordner `code` gehen, in die
   Adresszeile `cmd` tippen und Enter drücken. Dann:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate.bat
   pip install -r requirements.txt
   ```

   Das dauert ein paar Minuten. Die Texterkennung zieht PyTorch nach, insgesamt ca. 1,5 GB.
5. Kontrolle: `pytest` muss am Ende `59 passed` melden (dauert ca. 20 s).
   Beim ersten Lauf lädt die Texterkennung ihr Modell aus dem Internet (~100 MB).

> In **PowerShell** statt cmd heißt der Aktivierungsbefehl `.venv\Scripts\Activate.ps1`. Kommt
> dabei ein Fehler zur „Ausführungsrichtlinie“, einmalig
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ausführen oder einfach cmd benutzen.
>
> In VS Code: Ordner `code` öffnen, dann *Strg+Shift+P → „Python: Select Interpreter“ →
> `.venv`* wählen. Danach ist die venv in jedem neuen Terminal automatisch aktiv.

## 3. Erster Start in 5 Minuten – ohne Hardware

1. Im Ordner `code` auf **`start_gui.bat`** doppelklicken (oder `python -m gui`).
2. Tab **Ablauf (automatisch)** ist offen. Voreingestellt sind:
   Erkennung = *Testbilder*, Roboter = *Simulator*, Prüfung = *Testbilder*.
3. **▶ 1 Zyklus** klicken.

Was du sehen solltest:
- Die Zustandskette *Erkennen → Greifen → … → Sortieren* leuchtet nacheinander blau und wird
  dann grün.
- Links das Foto von oben mit grünem Arbeitsbereich und rot umrandetem Bauteil, in der Mitte die
  Seitenansicht mit Loch (rot) und Kerbe (blau), rechts die Draufsicht auf den Roboter.
- Oben rechts groß **GUTTEIL**, unten eine neue Zeile in der Tabelle (Seriennummer 69420).
- Der erste Zyklus dauert ca. 8 s, weil das Texterkennungsmodell geladen wird. Danach ca. 4 s.

Mit **▶▶ Dauerbetrieb** laufen die Zyklen weiter und nehmen reihum die vier Testfotos.
**■ Stopp nach Zyklus** beendet den Dauerbetrieb nach dem laufenden Zyklus.

## 4. Die GUI im Detail

Unten in jedem Tab läuft das **Log** mit (Fehler rot, Warnungen orange).
**Strg+S** speichert geänderte Einstellungen.

### Tab „Ablauf (automatisch)“

| Element | Bedeutung |
|---|---|
| Erkennung / Roboter / Prüfung | Welche Variante jedes Modul nutzt, siehe Tabelle unten |
| Pause | Wartezeit zwischen zwei Zyklen im Dauerbetrieb |
| Bilder speichern | legt pro Zyklus die Ergebnisbilder in `code/logs/<datum>/` ab |
| Zustandskette | blau = läuft gerade, grün = erledigt, rot = hier ist der Fehler passiert |
| Draufsicht | Roboter-Koordinatensystem von oben: Posen (Quadrate), Arbeitsbereich, Bauteil (lila), Greifer-Position (orange, nur im Simulator bzw. am Roboter) |
| Tabelle / Zähler | ein Eintrag pro Zyklus, dieselben Daten stehen auch in der CSV-Datei (Abschnitt 8) |
| Fehler quittieren | nach einem Fehler **oder NOT-STOPP**: Roboter wird wieder freigegeben (`init_program`) und fährt Home, danach kann es weitergehen |
| NOT-STOPP (Software) | stoppt die Roboterbewegung sofort. Danach lehnt der Roboter jede Bewegung ab („gestoppt – quittieren“), bis quittiert wurde. **Ersetzt nicht den echten Not-Halt!** |

| Variante | Erkennung | Roboter | Prüfung |
|---|---|---|---|
| **Mock** | Zufallspose | tut nur so, schreibt ins Log | Zufallsergebnis (ca. 70 % gut) |
| **Testbilder** | echte Bildverarbeitung auf den Fotos in `m1_vision_topdown/tests/data/` | – | echte Prüfung auf den Fotos in `m3_inspection/tests/data/` |
| **Simulator** | – | echter Robotercode gegen eine simulierte Steuerung | – |
| **Kamera / Echter Roboter** | Live-Kamera | Neura LARA per Netzwerk | Live-Kamera |
| **KI (M4)** | Modul von Person 4 | – | – |

Die Varianten lassen sich frei kombinieren, z. B. echte Kameras mit Roboter-Simulator.

### Tab „M1 Erkennung“

Zum Testen und Einstellen der Erkennung ganz ohne Roboter.
- **Quelle:** *Testbilder* (bei jedem Klick das nächste Foto) oder *Kamera*. Mit **Datei öffnen …**
  lässt sich jedes beliebige Foto laden.
- **Bild holen + analysieren**, **Erneut analysieren** (z. B. nach einer geänderten Einstellung),
  **Live** (holt und analysiert fortlaufend).
- **Arbeitsbereich:** `auto` (ArUco, sonst weißer Rahmen), `aruco` oder `white_frame`.
- Links das Kamerabild mit grünem Arbeitsbereich, gelben Bezugspunkten und rotem Bauteil.
  Rechts der entzerrte Arbeitsbereich: Der Pfeil zeigt die Bauteilrichtung zur abgeschrägten Ecke.
- Rechts die Werte: Position im Arbeitsbereich und im Roboter-KS, Winkel, Größe, Rechenzeit.
  Orange „gefunden (ohne Fase)“ bedeutet: Die Richtung ist nur auf 180° eindeutig.

### Tab „M2 Roboter“

1. **Modus** *Simulator* oder *Echter Roboter*, IP prüfen, **Verbinden**.
2. **Status** zeigt Robotername, Version, Betriebsart, aktuelle Greiferpose (TCP) und Fehler.
   Die Anzeige aktualisiert sich jede Sekunde.
3. **Bewegen:** Override (Geschwindigkeitsanteil, zum Testen 0,20), **Home**, **Greifer auf/zu**,
   **Pick-Test Prüfposition** (Home → greift an der Prüfposition → legt wieder ab → Home).
   Beim echten Roboter kommt vor jeder Bewegung eine Sicherheitsabfrage.
4. **Posen teachen:** Roboter an die gewünschte Stelle bringen (Pendant oder von Hand im
   Freedrive-Modus), rechts die Pose wählen (z. B. `inspection`) und **Aktuelle TCP-Pose übernehmen**
   klicken. Dann mit **Strg+S** speichern. **Pose anfahren** fährt eine Pose zur Kontrolle an
   (erst darüber, dann langsam hinunter).
5. **STOPP** funktioniert jederzeit, auch während einer Bewegung. Danach steht bei *Freigabe*
   „gestoppt“: Mit **Freigeben** wird der Roboter wieder vorbereitet, er fährt dabei nicht.

Details zur Roboter-Inbetriebnahme (Netzwerk, Pendant, Fehlersuche):
[code/m2_robot_control/ANLEITUNG_NEURA.md](code/m2_robot_control/ANLEITUNG_NEURA.md)

### Tab „M3 Prüfung“

Bedienung wie bei M1. Rechts groß **GUTTEIL/SCHLECHTTEIL**, darunter jedes Prüfmerkmal mit ✔/✘:
Seriennummer (mit OCR-Konfidenz), Lochdurchmesser (mit Sollwert), Kerbe. Bei Schlechtteilen
stehen die Gründe in Rot darunter.

Das rechte Bild zeigt das Bauteil vergrößert mit den drei **Prüfbereichen (ROIs)**: türkis =
Etikett, orange = Loch, magenta = Kerbe. Liegt ein Merkmal nicht in seinem Bereich, werden die
ROIs in den Einstellungen verschoben (Abschnitt 6).

### Tab „Einstellungen“

Alle Werte aus `code/config/system.yaml` als Baum, mit den Kommentaren aus der Datei.
- **Filter** oben, z. B. `hole` oder `robot`
- **Doppelklick** auf einen Wert zum Ändern. Listen werden so geschrieben: `[1.0, 2.0]`.
  Geänderte Werte sind gelb hinterlegt.
- **Speichern** (oder Strg+S) schreibt die Datei, die Kommentare bleiben erhalten.
  **Verwerfen / neu laden** holt den Stand aus der Datei zurück.

## 5. An deinem Modul arbeiten

Jedes Modul lässt sich auf drei Wegen einzeln testen: im **GUI-Tab**, über die **Kommandozeile**
und mit **pytest**. Die Befehle laufen im Ordner `code` mit aktivierter venv.

**Grundregel:** Die Module sprechen nur über die Datenklassen und Interfaces in
`code/common/interfaces.py` miteinander. Innerhalb deines Moduls kannst du alles ändern. Die
Schnittstelle selbst änderst du nur nach Absprache (siehe Abschnitt 10).

### Person 1 – M1 Erkennung

| Datei | Inhalt |
|---|---|
| `workspace.py` | Arbeitsbereich finden (ArUco oder weißer Rahmen) → Entzerrung |
| `part.py` | Bauteil segmentieren, Schwerpunkt, Winkel über die abgeschrägte Ecke |
| `detector.py` | `TopDownPipeline` (Bild → Pose), `TopDownDetector` (mit Kamera), `MockDetector` |
| `make_markers.py` | ArUco-Marker mit weißem Rand zum Ausdrucken |

```bat
python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"   & rem Ergebnisbilder in logs\m1
python -m m1_vision_topdown --camera                                 & rem ein Live-Bild
python -m m1_vision_topdown.make_markers --size-mm 50                & rem Marker drucken
pytest m1_vision_topdown
```

Bekanntes Problem: Die aktuellen 3D-gedruckten Marker haben keinen weißen Rand und werden nicht
erkannt. Bis das behoben ist, nimmt die Erkennung automatisch den weißen Rahmen.
Planung und Aufgaben: [plan/02_modul1_objekterkennung.md](plan/02_modul1_objekterkennung.md)

### Person 2 – M2 Robotersteuerung

| Datei | Inhalt |
|---|---|
| `robot.py` | `NeuraRobot` (echter Roboter), `MockRobot`, Greifsequenz, Umrechnung mm/° ↔ m/rad |
| `robot_check.py` | Inbetriebnahme-Werkzeug für die Kommandozeile |
| `fake_neura_server.py` | Simulator der Robotersteuerung |
| `vendor/neurapy/` | Original-Client von Neura (nicht ändern) |
| `ANLEITUNG_NEURA.md` | Schritt für Schritt vom Laptop zum bewegten Roboter |

```bat
python -m m2_robot_control info --sim        & rem ohne --sim: echter Roboter
python -m m2_robot_control pick-test --sim
python -m m2_robot_control pose inspection   & rem aktuelle Pose als Konfigurationszeile
pytest m2_robot_control
```

Planung und Aufgaben: [plan/03_modul2_robotersteuerung.md](plan/03_modul2_robotersteuerung.md)

### Person 3 – M3 Sichtprüfung

| Datei | Inhalt |
|---|---|
| `features.py` | Bauteil finden, Loch vermessen, Kerbe erkennen |
| `ocr.py` | Seriennummer lesen (EasyOCR) |
| `inspector.py` | Gut/Schlecht-Entscheidung, `InspectionPipeline`, `CameraInspector`, `MockInspector` |

```bat
python -m m3_inspection "m3_inspection/tests/data/*.jpg"   & rem Ergebnisbilder in logs\m3
python -m m3_inspection --camera
pytest m3_inspection
```

Neue Testbilder in `m3_inspection/tests/data/` ablegen, dann erscheinen sie im GUI unter *Testbilder*.
Planung und Aufgaben: [plan/04_modul3_sichtpruefung.md](plan/04_modul3_sichtpruefung.md)

### Person 4 – M4 KI-Greifen

Deine Klasse `AiGraspDetector` in `code/m4_ai_grasping/ai_detector.py` muss nur eine Methode
haben: `detect()`. Sie liefert eine `ObjectPose` (x, y in mm und Winkel in ° im
**Roboter-Koordinatensystem**) oder `None`, wenn kein Bauteil da ist. Was du intern machst,
ist dir überlassen. Eigene Pakete (z. B. PyTorch-Modelle) bitte in einer eigenen
`m4_ai_grasping/requirements.txt` festhalten.

- Bilder: Die Kamera oben bekommst du im Ablauf als `camera` übergeben. Die geplante
  **Handgelenkkamera** am Roboter öffnest du mit `self.wrist_camera().read()` (Konfiguration:
  `wrist_camera`). Zum Testen gibt es die Fotos in `m1_vision_topdown/tests/data/`.
- Umrechnung Arbeitsbereich → Roboter: `common.transforms.workspace_to_robot` (wie M1).
- Ausprobieren: im GUI-Tab *Ablauf* Erkennung = **KI (M4)** oder
  `python -m orchestrator --detector ai --robot sim --inspector replay`.
- Vergleich mit M1 für die Thesis: gleiche Bilder, beide Ergebnisse in der CSV (Abschnitt 8).

Rahmen: [plan/05_modul4_ki_greifen.md](plan/05_modul4_ki_greifen.md)

## 6. Einstellungen

Alle Werte stehen in `code/config/system.yaml`. Am bequemsten änderst du sie im GUI-Tab
*Einstellungen*. Die Bildverarbeitung übernimmt Änderungen **sofort**, du kannst im Tab M1/M3
also direkt „Erneut analysieren“ klicken. Eine geänderte Kamera-Quelle gilt ab dem nächsten Bild,
eine geänderte Roboter-IP erst nach erneutem Verbinden.

Die wichtigsten Werte (mit **tbd** = noch zu messen):

| Abschnitt | Wert | Wofür / wann ändern |
|---|---|---|
| `topdown_camera` / `inspection_camera` / `wrist_camera` | `source` | Kameranummer (0, 1, …) oder Bildpfad, z. B. `"m1_vision_topdown/tests/data/*.jpg"`. Jede Kamera braucht eine eigene Nummer |
| `workspace` | `size_mm` **tbd** | Innenmaß des weißen Rahmens [Breite, Höhe] in mm – bestimmt alle mm-Werte von M1 |
| `workspace` | `markers_mm` **tbd** | Markermitten in mm (Ursprung: innere linke untere Rahmenecke) |
| `workspace` | `method` | `auto`, `aruco` oder `white_frame` |
| `part_topdown` | `brightness_delta`, `saturation_delta` | wenn das Bauteil nicht vollständig erkannt wird |
| `workspace_to_robot` | `rotation_deg`, `translation_mm` **tbd** | Kalibrierung Arbeitsbereich → Roboter (Abschnitt 7) |
| `robot` | `host` | IP der Robotersteuerung |
| `robot` | `override` | Geschwindigkeit 0–1, zum Testen 0,2 |
| `robot` | `poses` **tbd** | geteachte Posen (Tab M2) |
| `robot` | `limits_mm` | erlaubter Bereich, alles außerhalb wird abgelehnt |
| `robot` | `grasp_height_mm`, `approach_height_mm` | Greifhöhe über dem Tisch, Anfahrhöhe darüber |
| `inspection` | `label_roi`, `hole_roi`, `notch_roi` | Prüfbereiche relativ zum Bauteil `[x0, y0, x1, y1]` von 0 bis 1 |
| `inspection` | `part_height_mm` **tbd** | Bauteilhöhe in der Seitenansicht = Maßstab für den Lochdurchmesser |
| `inspection` | `hole_nominal_mm`, `hole_tolerance_mm` **tbd** | Soll und Toleranz des Lochs |
| `inspection` | `serial_pattern` | erlaubtes Format der Seriennummer, derzeit 5 Ziffern |

Tipp: `system.yaml` vor größeren Änderungen kopieren, z. B. als `system_backup.yaml`.

## 7. Am echten Aufbau: Inbetriebnahme

Reihenfolge für den ersten Termin im Labor. Immer zu zweit, eine Person hat die Hand am Not-Halt.

1. **Messen** und in die Einstellungen eintragen: `workspace.size_mm`, `markers_mm`,
   `inspection.part_height_mm`, `hole_nominal_mm`, `hole_tolerance_mm`.
2. **Kameras zuordnen:** alle Kameras anschließen, dann `python -m common.camera` ausführen. Das
   Werkzeug listet alle gefundenen Kameranummern und speichert je ein Foto nach `code/logs/cameras/`.
   So siehst du, welche Nummer die Kamera oben, die seitliche und (später) die am Roboterhandgelenk
   hat. Windows vergibt die Nummern nach der Reihenfolge beim Einstecken, also immer dieselben
   USB-Buchsen benutzen. Nummern in die Einstellungen eintragen (`topdown_camera.source` usw.).
   **Kamera oben:**
   Im Tab **M1** Quelle *Kamera* wählen und *Live* einschalten. Der grüne Rahmen muss sauber auf der
   Innenkante liegen, das Bauteil rot umrandet sein.
3. **Kamera seitlich:** analog im Tab **M3**. Liegt ein Merkmal nicht in seinem farbigen
   Prüfbereich, die ROIs in den Einstellungen nachziehen.
4. **Roboter** nach [ANLEITUNG_NEURA.md](code/m2_robot_control/ANLEITUNG_NEURA.md) verbinden
   (Tab **M2**): *Info* → *Home* → *Greifer auf/zu*.
5. **Posen teachen** (Tab M2): `inspection`, `bin_good`, `bin_bad`, danach `limits_mm` prüfen und
   speichern.
6. **Kalibrierung Arbeitsbereich → Roboter:**
   - Mit der Greiferspitze nacheinander die vier Innenecken des weißen Rahmens antippen und jeweils
     mit `python -m m2_robot_control pose ecke` die Roboterkoordinate notieren.
   - Reihenfolge wie im Kamerabild: unten links, unten rechts, oben rechts, oben links.
     Auf den Fotos ist „unten“ die Seite mit dem T-förmigen Steg.
   - Dann rechnen:

     ```python
     from common.transforms import fit_rigid_2d
     W, H = 400.0, 400.0                                  # workspace.size_mm
     ws = [[0, 0], [W, 0], [W, H], [0, H]]                # Ecken im Arbeitsbereich-KS
     robot = [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]     # gemessene Roboterkoordinaten (mm)
     theta, t = fit_rigid_2d(ws, robot)
     print(theta, t)   # -> workspace_to_robot.rotation_deg und translation_mm
     ```

   - Die z-Koordinate beim Antippen ist `workspace_to_robot.table_z_mm`.
7. **Erster Zyklus:** Tab **Ablauf**, Erkennung = Kamera, Roboter = *Simulator*, Prüfung = Kamera.
   Stimmt die Bauteilposition in der Draufsicht? Erst dann Roboter = **Echter Roboter**,
   Override 0,2, **▶ 1 Zyklus**.

## 8. Ergebnisse und Logs

- Jeder Zyklus (GUI oder Kommandozeile) wird eine Zeile in **`code/logs/cycles_<datum>.csv`**.
  Trennzeichen `;`, Excel öffnet die Datei direkt. Spalten: Zeit, Zyklus, ok, Fehler, Dauer,
  Position x/y/θ, Seriennummer, Lochdurchmesser, Kerbe, gut, Gründe, Bildordner.
- Mit *Bilder speichern* (GUI) bzw. `--save-images` (CLI) kommen pro Zyklus die Ergebnisbilder
  von M1 und M3 nach `code/logs/<datum>/<uhrzeit>_c<nr>/`.
- Die Einzelmodule auf der Kommandozeile schreiben ihre Bilder nach `code/logs/m1` bzw. `logs/m3`.

Diese Daten sind die Grundlage für das Evaluationskapitel der Thesis, z. B. Genauigkeit,
Gut/Schlecht-Trefferquote und Taktzeit. Messreihen deshalb immer mit Datum und Notiz zum Aufbau
festhalten.

## 9. Tests

`pytest` im Ordner `code` führt alle 59 Tests aus (ca. 20 s). Einzelne Module: `pytest m3_inspection`.

| Bereich | Was geprüft wird |
|---|---|
| M1 | 8 künstliche Szenen mit bekannter Lage (Genauigkeit < 2 mm / 2°), die 4 echten Fotos |
| M2 | kompletter Robotercode über den Original-Neura-Client gegen den Simulator, Grenzen, Umrechnung |
| M3 | 3 echte Bilder = Gutteil; Kerbe bzw. Loch wegretuschiert = Schlechtteil; Texterkennung |
| Ablauf | Zustandsautomat, Fehlerfall, NOT-STOPP → Quittieren → weiter, CSV |
| GUI | Einstellungen speichern ohne Kommentarverlust, Fenster-Test ohne Bildschirm |

Bitte vor dem Weitergeben von Änderungen einmal `pytest` laufen lassen. Neue Funktionen bekommen
einen Test im `tests/`-Ordner des Moduls.

## 10. Spielregeln im Team

- **Planung pflegen:** Wer eine Aufgabe erledigt, hakt sie in `plan/0x_…` bzw.
  `plan/06_roadmap.md` ab (`[x]`) und schreibt eine Zeile in `plan/07_erledigt.md`.
  Offene Fragen und Entscheidungen kommen nach `plan/08_offene_fragen.md`.
- **Schnittstellen** (`code/common/interfaces.py`) betreffen alle. Änderungen erst in
  `plan/01_architektur.md` vorschlagen und absprechen.
- **Einstellungen** gehören in `system.yaml`, nicht als feste Zahlen in den Code.
- **Sprache:** Planung und Thesis auf Deutsch, Code und Kommentare auf Englisch.
- **Vertraulich:** Neura-Client (`vendor/`), `docs/neura/` und `resources/` sind proprietär bzw.
  enthalten Passwort-Hashes → nicht öffentlich teilen. Ein künftiges Git-Repo muss **privat** sein.
- **Roboter:** nie allein, Hand am Not-Halt, neue Bewegungen erst im Simulator, dann mit 20 %.

## 11. Fehlersuche

| Problem | Lösung |
|---|---|
| `python` wird nicht gefunden | Python neu installieren mit „Add to PATH“, neues Terminal öffnen |
| `No module named …` | venv nicht aktiv → `.venv\Scripts\activate.bat`, ggf. `pip install -r requirements.txt` |
| GUI startet nicht per Doppelklick | `start_gui.bat` zeigt die Fehlermeldung an. Meist fehlt die venv (Abschnitt 2) |
| Erster Zyklus / erste Prüfung sehr langsam | Texterkennungsmodell wird geladen (einmalig pro Start, beim allerersten Mal Download) |
| M1: „White workspace frame not found“ | Rahmen nicht vollständig im Bild oder stark überstrahlt → Kamera ausrichten, Licht |
| M1: „No part found“ | Bauteil liegt am Rand/auf dem Rahmen oder ist zu klein/groß → `part_topdown` prüfen |
| M1: Maße und Positionen stimmen nicht | `workspace.size_mm` ist noch ein Platzhalter → ausmessen |
| M3: Seriennummer `None` | Etikett nicht im türkisen ROI, unscharf oder Konfidenz < `ocr_min_confidence` |
| M3: Loch/Kerbe nicht gefunden | ROI verschieben (Tab M3 zeigt die Bereiche), Beleuchtung prüfen |
| Kamera öffnet nicht | `python -m common.camera` zeigt die verfügbaren Nummern. Anderes Programm (Teams, Kamera-App) schließen |
| „Kamera X ist schon für … geöffnet“ | Zwei Module haben dieselbe `source`-Nummer → Nummern prüfen |
| „Robot stopped – acknowledge first“ / „gestoppt – quittieren“ | Nach NOT-STOPP oder Fehler: **Fehler quittieren** (Ablauf) bzw. **Freigeben** (Tab M2) |
| Mehrere 4K-Kameras ruckeln/fallen aus | USB-Bandbreite: Kameras auf verschiedene USB-Controller verteilen oder Auflösung (`width`/`height`) senken |
| Roboter verbindet nicht | [ANLEITUNG_NEURA.md, Abschnitt 9](code/m2_robot_control/ANLEITUNG_NEURA.md#9-fehlersuche) |
| „outside limits“ | Zielpose liegt außerhalb `robot.limits_mm` → Pose oder Grenzen prüfen |
| Ablauf bleibt auf rot stehen | Fehler im Log lesen, Ursache beheben, **Fehler quittieren** |

## 12. Befehle auf einen Blick

Alle Befehle im Ordner `code` mit aktivierter venv:

```bat
start_gui.bat                                   & rem GUI (oder: python -m gui --tab m1|m2|m3|auto|settings)

python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"
python -m m2_robot_control info --sim           & rem info | pose NAME | home | gripper | pick-test
python -m m3_inspection "m3_inspection/tests/data/*.jpg"

python -m orchestrator --replay --sim-robot --cycles 4          & rem Ablauf ohne Hardware
python -m orchestrator --detector camera --robot real --inspector camera --cycles 1
python -m orchestrator --help

python -m common.camera                          & rem welche Kameranummer ist welche Kamera?

pytest
```
