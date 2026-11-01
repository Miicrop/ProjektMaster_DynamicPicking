# 10 – Abschlusspräsentation: Konzept

**Stand:** 2026-11-01 – Akt 6 auf M4 Behavior Cloning umgestellt und erweitert (6.1–6.8), Gerüst in [`presentation/abschluss/`](../presentation/abschluss/README.md).
**Vorlage:** Masterarbeits-Präsentation „Das Zerlegeschema wird lebendig“ (`Masterarbeit_Neu/presentation/abschluss`, Konzept dort in `plan/11-praesentation-konzept.md`). Engine, Bausteine und Werkzeuge sind von dort übernommen.

> **Wiedereinstieg** (Aufgaben: [06_offen.md](06_offen.md) Abschnitt 9, Verlauf: [07_erledigt.md](07_erledigt.md))
>
> - **Stand:** 44 von 45 Szenen gebaut, offen ist nur 7.2 (Messwerte). Akt 6 (M4) ist ein Entwurf aus
>   Jeremys Doku, den er prüft.
> - Die Szenenliste in `src/storyboard.js` ist die maßgebliche Fassung. Änderungen an der Dramaturgie
>   dort **und** hier eintragen.
> - **Welten:**
>   - `cell.js` + `kit/lara.js`: Zelle, Zyklus, Greifsequenz, Grenzen, M4 (6.2, 6.8), Finale mit Schild „Noch Fragen?“ (7.5) und Ausblick-Spielfeld (7.4).
>   - `arch.js`: Akt 2 und 6.1.
>   - `vision.js`: Akt 3.
>   - `inspect.js`: Akt 5, mit Detailblättern unter dem Foto.
>   - `sheets.js`: 1.5, 1.6, 2.4, 4.7, 6.3–6.7, 7.1, 7.3 und der Anhang.
> - **Daten:** `build_data.py` exportiert Config, M1/M3-Ergebnisse auf den Testbildern, Zwischenbilder
>   (`m3.trace`, `m3.notches`), `robot_check` gegen den Simulator (`m2.check`) und die Posen vom
>   Labortag aus Commit 1f5cdc1 (`data.lab`). Der GUI-Screenshot entsteht mit `tools/gui_shot.py`
>   (Qt offscreen).
> - **M4-Daten** (`data.m4`): CLEAR_FOV, PICK, PRE_PLACE samt Gelenkwinkeln aus
>   `m4_behavior_cloning/sequences/points_anlage_2026-10-26.json` (TCP im Basis-KS). Die Bahn folgt
>   `pick_to_station.json`. Die 10 Rauschbahnen kommen aus Jeremys `bc/noise.py` (Streuung 15 mm,
>   Trichter, fester Seed). In `build_data.py` stehen fest, jeweils mit Quellenangabe:
>   - die Zitterwerte für 6.6 (seine Doku 13.–19.10.),
>   - die Kennzahlen des Sim-Durchstichs für 6.5 (`Berichte/2026-09-17_Durchstich_Policy.pdf`),
>   - die Taktwerte für 6.7 (Labortag 16.10.).
>
>   Die Policy-Parameter für 6.4 kommen aus `bc/config.py`. Die Rollout-Abbildung stammt aus
>   `thesis/figures/m4/` und ist unten beschnitten.
>   Die IK in der Zelle startet in jedem Takt von den echten Gelenkwinkeln aus. J6 der URDF ist dabei um +90°
>   gegenüber der Steuerung gedreht. Die FK der echten Winkel trifft die gespeicherte Pose auf 8,5 mm.
>   CLEAR_FOV liegt nahe der J1-Singularität, deshalb fährt die Zelle wie `pick_to_station` per PTP zum Anflug
>   150 mm über PICK. Erst ab dort folgt die 15-Hz-Bahn. Die Ladekontrolle warnt bei Gelenksprüngen über 10°
>   und bei mehr als 15° Abstand zur Stellung der Anlage.
> - **Akt 6 in der Zelle:** Teil B verschwindet beim Betreten von 6.2 und kommt erst in 7.5 zurück. Der
>   Schattenroboter aus 4.6 blendet aus. Die Rückfahrt über Teil B läuft zu Beginn von 7.4 (`m4back`), damit
>   der Arm in 6.8 die Prüfung nicht verdeckt.
> - **LARA** stammt aus der URDF (`public/urdf/lara5.urdf`, Kinematik aus den Gelenken). Die Home-Pose
>   ergibt Flansch-z 434,5 mm wie im Roboter-Backup. Alle Stationsposen sind erreichbar, und der
>   Greifwinkel folgt derselben Formel wie `m2_robot_control.robot.as_target`.
> - **Kontrollen beim Laden:** Jede Zielpose muss erreicht werden, und das Schild hält ≥ 20 mm Abstand
>   zu Arm und Tisch. Sonst kommt eine Warnung in der Konsole (`tools/shoot.mjs` meldet sie).
> - **Achtung:** Das Log vom 05.10. stammt aus der Neura-VM. Vom Labortag liegt kein Log im Repo.

## Rahmen

Projektabschluss an der HS Kempten. **Alle vier tragen vor**, je Akt ein Sprecher. Dauer noch offen. Es gibt **nur eine Fassung**; die Kürzungskandidaten (k) werden bei Bedarf im Storyboard gestrichen. Akt 6 (M4) ist aus Jeremys Doku gebaut, er prüft ihn.

## Gestaltung (Übertragung der Vorlage)

| Merkmal | Referenz | Übertragung |
|---|---|---|
| Leitidee | „Das Zerlegeschema wird lebendig“: eine technische Zeichnung, die sich selbst zeichnet | „Die Zelle zeichnet sich selbst“: Aufstellungsplan der Roboterzelle wird lebendig |
| Look | Papier `#F4F1EA`, Millimeterraster, Papierkorn, Tusche-Kanten aus Normalen/Tiefe, weiche Schatten | identisch (`engine/stage.js`) |
| Grundverb | Linie zeichnet sich, dann füllt sich die Fläche | identisch (`kit/ink.js` `InkLine`) |
| Übergang | Schnittlinie ✂ teilt das Blatt | identisch, inhaltlich passend zu „Prüfen/Schneiden“ weniger stark → zusätzlich **Blitz** (Kameraaufnahme) als zweiter Übergang, existiert schon in `stage.js` |
| Annotation | Positionsnummern im Kreis, Maßlinien, Schriftfeld unten rechts | Positionsnummern = Komponenten (Roboter, Kameras, Ablagen), Maßlinien = echte mm aus `system.yaml` |
| Farbe = Information | Graphit + Papier, Farbe nur für Teilstücke, Signalrot für Fehler | Farbe nur für das **Bauteil** (Lila, wie der echte Druck), je Modul ein gedämpfter Akzent (M1/M2/M3/M4), Signalrot `#D64933` = Schlechtteil/Fehler/STOPP, Prüfgrün nur für „GUT“-Stempel |
| Schrift | Space Grotesk / IBM Plex Sans / IBM Plex Mono, offline | identisch |
| Navigation | `Akt.Szene`, Schritte mit deterministischem Endzustand, Sprung, Übersicht `O`, `B`, Vollbild | identisch (`engine/nav.js`, `hud.js`) |
| Profil-Schalter | Professor ↔ Unternehmen | entfällt – eine Fassung (21.10.) |
| HUD-Schriftfeld | Titel, Szene, Akt, FF-Badge | FF-Badge → **Sprecher** (Name der vortragenden Person je Akt) |
| Prinzipien | 3–4 Hero-Momente, ruhige 2D-Blätter für Dichtes, immer am gleichen Beispielbild, Ehrlichkeit als Stilmittel | **immer dasselbe Bauteil „69420“** als Protagonist; offene Punkte (Greifer, Kamera live, Evaluation) offen zeigen |

## Roter Faden

Die Reise **eines** Bauteils (Seriennummer 69420) durch die Zelle: liegt irgendwo im Rahmen → Blitz der
Top-down-Kamera → echtes Foto → Pose (x, y, θ) → Koordinaten wandern Bild → Arbeitsraum → Roboter-Basis →
LARA greift → Prüfposition → Blitz der Seitenkamera → drei Prüfungen → GUT/SCHLECHT-Ablage.
Erfolgskriterium aus der Thesis als „Leitfrage“: *Läuft Erkennen, Greifen, Prüfen und Sortieren vollständig automatisch durch?*
Jeder Akt = ein Sprecher, die Zelle ist die gemeinsame Bühne (Rückfahrt in die Gesamtansicht bei jedem Sprecherwechsel).

## Storyboard (Entwurf, ~28 Szenen + Anhang; ★ = Hero, (k) = Kürzungskandidat)

**Akt 1 – Aufgabe (Sprecher: Niklas)**
- 1.1 Titel: Blatt leer, Tusche zeichnet den Aufstellungsplan (Rahmen, Marker, Prüfvorrichtung, Ablagen, Roboterfuß) aus echten mm-Werten, Schriftfeld setzt sich (Titel, 4 Namen, Datum).
- 1.2 Die Zelle: Plan extrudiert zu 3D, Positionsnummern ①–⑧ (LARA, Greifer, Kamera oben M1 (Daheng, zugleich Szene für M4), Seitenkamera M3 (USB), Handgelenkkamera M4 (Daheng, Fisheye), Rahmen + ArUco, Prüfposition, Ablagen GUT/SCHLECHT).
- 1.3 Das Bauteil: lila Quader mit Fase dreht sich, Hinweislinien auf Fase, Etikett 69420, Loch, Kerbe.
- 1.4 ★ **Ein Zyklus**: der komplette Ablauf einmal im Zeitraffer (Zustandsnamen erscheinen als Stempel IDLE → DETECT → … → SORT).
- 1.5 Erfolgskriterium + Abgrenzung (ein Teil, flach, 2D-Pose, unter Aufsicht).
- 1.6 (k) Vorprojekt GROB in einem Blatt mit Bildern aus `thesis/figures/grob/` (freigegeben 21.10.).

**Akt 2 – Architektur & Integration (Niklas)**
- 2.1 Zustandsautomat als Tuschezeichnung, aktueller Zustand leuchtet (Rückgriff auf 1.4).
- 2.2 Schnittstellen: `ObjectPose` und `InspectionResult` fliegen als Datenkarten zwischen den Modulblöcken; die Module kennen sich nicht.
- 2.3 Interface + Mock: jeder Block hat drei Stecker (mock / replay / real), Schalter klappt um → „von Tag 1 an lauffähig“; 105 Tests als Zähler.
- 2.4 (k) GUI & Logbuch: Screenshot-Karte der GUI, Zykluslog als Papierstreifen.

**Akt 3 – M1 Objekterkennung (Felix Krawczyk)**
- 3.1 Kamera schräg seitlich an einer Stange, Sichtkegel zeichnet sich, **Blitz** → echtes Foto (`PXL_20261005_*.jpg`) liegt verzerrt auf dem Blatt. Die schräge Montage macht 3.2 zur eigentlichen Pointe.
- 3.2 ★ **Das Bild klappt gerade**: ArUco-Marker werden umkreist, die vier Ecken wandern ins Rechteck, das Foto entzerrt sich live (Mesh-Warp mit echter Homographie).
- 3.3 Segmentierung: Maske frisst den Hintergrund, Kontur zeichnet sich, `minAreaRect` als Maßzeichnung.
- 3.4 θ eindeutig: Quader dreht sich 180°, ohne Fase gleich → mit Fase eindeutig 0–360° (Rotstift-Kreis um die Fase).
- 3.5 ★ **Drei Koordinatensysteme**: Achsenkreuze Bild (px) → Arbeitsraum (mm) → Roboter-Basis (mm); der Punkt wandert durch beide Transformationen; Kalibrierung: TCP fährt die Marker an, Restfehler als Maßpfeile (Least Squares).

**Akt 4 – M2 Robotersteuerung (Joshua Junt)**
- 4.1 LARA zeichnet sich (stilisierter 6-Achser aus Grundkörpern, Tusche-Look), Werkzeug ZimmerLWR50 mit TCP-Maß 197,5 mm.
- 4.2 Vom Bauteil zur Greifpose: Winkelskizze am Teil (Basis-x → Bauteilwinkel → + 113° = rz), Codekarte mit echten Zahlen `as_target()` → `to_neura()` → `compute_inverse_kinematics` → `move_joint`; LARA fährt per PTP zur Vorpose, die Gelenkwinkel laufen an den Positionsnummern mit.
- 4.3 ★ **Die Greifsequenz**: ab der Vorpose schnell bis 20 mm → langsam → Greifer zu → LIN hoch; Geschwindigkeitsprofil als Maßband daneben (0,10 → 0,03 m/s).
- 4.4 23° verdreht: Greiferbacken vs. Bauteilachse, Winkelbemaßung, Offset 90° → 113°.
- 4.5 Sicherheit: Arbeitsraum-Quader (Pose außerhalb → Rotstift), STOPP in eigenem Thread, `stop()` → `reset()`.
- 4.6 Simulator: `fake_neura_server` als Schatten-Roboter, unveränderter NeuraPy-Client.
- 4.7 Roboter einrichten: echter Screenshot des GUI-Tabs „M2 Roboter“ (gegen den Simulator, `tools/gui_shot.py`) mit Positionsnummern – Verbinden, Joggen, Checkliste „Erste Schritte“, Posen teachen; dann „Vorsicht eingebaut“ (STOPP, Rückfrage vor jeder Fahrt, Override/Jog-Grenzen) und Stempel SIM › VM › ECHT. `robot_check` nur noch als Fußzeile.

**Akt 5 – M3 Sichtprüfung (Niklas Tollmann)**
- 5.1 Bauteil auf der Prüfposition, Seitenkamera, **Blitz** → echtes Seitenbild (`test_img_*.jpg`).
- 5.2 Bauteil finden: echte Masken des Hero-Bilds als Papier über dem Foto (Lila per HSV → geöffnet → senkrecht geschlossen), dann Box und ROIs (Etikett, Loch, Kerbe) – jede Maske, Box und ROIs je ein eigener Klick (5 Schritte).
- 5.3 Seriennummer (Detailblatt): Etikett-ROI → EasyOCR nur Ziffern → Regex; Konfidenz auf allen vier Testbildern.
- 5.4 Loch (Detailblatt): ROI → Maske „keine helle Stirnfläche“ → Kandidaten mit Rundheit → Ellipse; Maßstab über die Bauteilhöhe, D/H auf allen Testbildern.
- 5.5 Kerbe (Detailblatt, 4 Klicks): ROI + Region → Kanten → Kandidat mit Rechteckigkeit; dann alle vier Testbilder als Raster (ROI, Region, Kanten, Kandidaten), der gewinnende Weg umrahmt.
- 5.6 ★ **Drei Prüfungen, ein Urteil**: OCR „69420“ ✓ (Regex), Loch als Maßlinie ✓, Kerbe ✓ → Stempel GUT. Dann übermalte Kerbe → Rotstift, Stempel SCHLECHT mit `reasons`.

**Akt 6 – M4 Behavior Cloning (Jeremy Zid)** – Entwurf aus seiner Doku, Jeremy prüft
- 6.1 M4 übernimmt das Greifen: Im Zustandsring klappt nur PICK auf M4 („Diffusion Policy“) um. Die Policy greift bis PRE_PLACE (~9 cm über der Prüfung), danach legt M2 ab, M3 prüft und M2 sortiert.
- 6.2 ★ Lernen mit Rauschen (Zelle): Teil C an PICK, Wegpunkte CLEAR_FOV, PICK und PRE_PLACE samt Sollbahn. LARA fährt eine Episode mit echtem Rauschen, dahinter zeichnet sich der Fächer aller 10 Episoden. Danach legt sie das Teil zurück, wie `put_back`. Eine Karte zeigt die Kette Teachen → Aufnahme → LeRobotDataset → Diffusion Policy (89,5 M Param.) → Inferenz 15 Hz.
- 6.3 (k) Der Rauschtrichter (Blatt): seitliche Abweichung und Höhe der 10 Episoden über der Bahn, mit Hülle und Ankerpunkten Start, PICK und Übergabe. Nach unten erlaubt das Rauschen höchstens 2 mm (Tisch). Rechts Trichter, Rauschfaktor, Asymmetrie und Rejection Sampling. Daten: `data.m4.funnel` aus `bc/noise.py`.
- 6.4 ★ Diffusion Policy (Blatt, animiert): zwei Kamerabilder 240 × 320 und 14 Zustandswerte gehen ins Netz (U-Net, 89,5 M, ResNet18 je Kamera). Ein Aktionsblock über 16 Takte entrauscht sich in 10 Schritten. Die ersten 8 Takte werden gefahren, dann folgt eine neue Vorhersage (~77 ms, asynchron). Werte aus `bc/config.py`, die Kurve ist ein Schema (ein Gelenk).
- 6.5 Die Policy fährt selbst (Blatt): Rollout-Abbildung aus dem Durchstich vom 17.09. mit 10/10, Greifpunkt 1,3–2,2 mm, Bahn 3,3–4,4 mm und 32 min Training. Stempel SIMULATION. Ehrlich dazu: Die Policy hat nur aus dem Zustand gelernt (Platzhalterbilder), in der VM blieb sie an PRE_GRASP stehen.
- 6.6 (k) Das Zittern (Blatt): Treppe aus 60-Hz-Sollwerten gegen den 1-kHz-Takt der Steuerung, Eigenfrequenz 5,6–6,2 Hz. Rechts die RMS-Werte je Ausführungsart, Stempel ENTSCHIEDEN: servo_j mit Override 0,5.
- 6.7 (k) Takt und Sicherheit (Blatt): Zeitachse mit 15-Hz-Takt, servo_j 60 Hz (Aufruf ~10 ms, selten 21 ms), Vorhersage ~77 ms und Hängern ~210 ms. Dazu ServoGuard, TargetLimiter, Zielabstand, Geofence und Software-Stopp, Stempel IN DER VM AUSGELÖST.
- 6.8 Übergabe M4 → M2 (Zelle): Fahrt bis PRE_PLACE als Sollbahn, Schild ÜBERGABE, dann `reset()` und Ablegen durch M2. Schild „In der Neura-VM getestet · mit trainiertem Modell an der Anlage noch offen“.
- Die Szene „Zwei Python-Welten“ ist verworfen (01.11.), weil sie für die Zuschauer keine Rolle spielt.

**Akt 7 – Ergebnis & Ausblick (alle)**
- 7.1 Labortag 06.10.: erster vollständiger Ablauf am echten Roboter (ehrlich: noch ohne Greiferansteuerung, M1/M3 mit Testbildern).
- 7.2 Messwerte (Platzhalter, datengetrieben): Kalibrier-RMS, Zeigetest-Versatz, Zyklusdauer, Erkennungs-/Prüfquote.
- 7.3 Erledigt/offen (Stand 01.11.): erledigt sind u. a. „M4 eingebunden, Übergabe in der VM getestet“ und „Greifer öffnet/schließt“. Offen: Kameras live, Greifen im Ablauf, M4 mit Modell, Messreihen samt Vergleich M2/M4.
- 7.4 Ausblick Pflegerobotik: heute spielt ein kleiner Portalroboter mit Senioren „Mensch ärgere Dich nicht“ (gleich großer Arbeitsbereich). In der Zelle wird der Arbeitsraum zum Spielfeld, LARA spielt zwei Züge (6 → raus, 3 → Blau schlagen); Übergang zu 7.5: Spielfeld weg, Teil B zurück in den Greifer.
- 7.5 Finale: zweites Teil → SCHLECHT. „Danke.“ im Schriftfeld; Ein Klick: Die Kamera fährt in die Zuschauersicht, LARA holt das Schild rechts aus dem Halter (Schrift zur Seite), dreht es auf dem Weg nach vorn zur Kamera und hält es leicht geneigt hin: „Noch Fragen?“. Schildlage und Kamera in `SIGN` (`cell.js`), erreichbar und kollisionsfrei laut Kontrolle beim Laden.

**Anhang:** A.1 Konfiguration/Posen-Tabelle, A.2 alle Zwischenbilder M1 (13), A.3 alle Zwischenbilder M3 (14), A.4 Testübersicht.

## Umsetzung (Reihenfolge)

Ort: `presentation/abschluss/` in diesem Repo (Ordner `presentation/` ist leer).

1. **Konzeptdokument** `plan/10_praesentation_konzept.md` (Analogon zu Masterarbeit `plan/11`): Leitidee, Gestaltung, Storyboard-Tabelle, Datenquellen, offene Punkte. Link in `plan/README.md`.
2. **Gerüst kopieren** aus `Masterarbeit_Neu/presentation/abschluss`: `package.json`, `vite.config.js`, `index.html`, `serve.py`, `start.bat`, `.gitignore`, `src/engine/*`, `src/kit/{ink,sheet,tiles}.js`, `src/worlds/placeholder.js`, `tools/shoot.mjs`, `tools/shoot_all.mjs`.
   Nicht übernehmen: alle fleischspezifischen Welten, `build_data.py`, `tools/build_*`, `rind_*`.
3. **Anpassen:**
   - `src/theme.js`: Teilstückpalette → `PART` (Lila), `MODULE_COLOR` (M1–M4 gedämpft), `GOOD`; `palette(data)` entfernen.
   - `src/storyboard.js`: Akte/Szenen oben; Feld `ff` → `speaker` (Profile lang/kurz am 21.10. wieder entfernt).
   - `src/engine/hud.js`: FF-Zelle zeigt Sprecher; Profilanzeige lang/kurz. `nav.js`: Profilnamen.
   - `src/main.js`: neue `WORLDS`/`BUILT`, Datenladen auf `data.json` reduzieren, `?profil=kurz`.
4. **Datenexport** `build_data.py` (Python, nutzt das Projekt-venv `code/.venv`):
   - liest `code/config/system.yaml` (Posen, `workspace_to_robot`, Marker, Rahmenmaß, Werkzeug, Geschwindigkeiten) → `public/data/data.json`;
   - ruft `TopDownPipeline` und `InspectionPipeline` auf den Testbildern auf und exportiert Ecken, Homographie, Kontur, `minAreaRect`, θ, ROIs, OCR-Text, D/H (Wiederverwendung von `common/trace.py` für die Zwischenbilder);
   - kopiert die Zwischenbilder aus `overview/img/m1|m3` bzw. erzeugt sie neu → `public/img/`;
   - liest `code/logs/cycles_*.csv` (und später Messreihen) für Akt 7.
5. **Welten** (`src/worlds/`), in dieser Reihenfolge, weil 1 die Bühne für alle liefert:
   - `cell.js` – Aufstellungsplan + 3D-Zelle + Bauteil + Zyklus (1.1–1.5, 7.5, Rückfahrten); Layout aus `data.json`.
   - `robot.js` – stilisierter LARA mit einfacher analytischer IK (TCP nach unten: Basisdrehung + 2-Glied-Ebene + Handgelenk), Greifer, Greifsequenz (1.4, 4.1–4.6). Wird von `cell.js` eingebunden.
   - `vision.js` – Foto-Ebene mit Mesh-Warp (Homographie), Maske/Kontur, θ, Koordinatensysteme (3.1–3.5).
   - `inspect.js` – Seitenbild, ROIs, Masken, Detailblätter, drei Prüfungen, Stempel (5.1–5.6); `Stamp` aus `kit/sheet.js`.
   - `arch.js` – Zustandsautomat und Modulblöcke mit Steckern (2.1–2.3, 6.1).
   - `sheets.js` – ruhige Blätter (1.5, 1.6, 2.4, 7.1–7.4, Anhang).
   Bis eine Szene gebaut ist, erscheint sie automatisch als Entwurfsblatt → die Dramaturgie ist ab Schritt 3 komplett durchklickbar.
6. **README** in `presentation/abschluss/` (Bedienung, Entwickeln, Aufbau, Regeln – wie Referenz), Eintrag in Haupt-`README.md`.

Hinweis Koordinatensysteme: Posen in `system.yaml` sind **TCP im Roboter-Basis-KS**; M1 rechnet im Arbeitsraum-KS. Die Zelle wird im Basis-KS aufgebaut (Arbeitsraum über `workspace_to_robot` platziert), Szene 3.5 macht genau diesen Unterschied sichtbar.

## Annahmen im Bild

Aufgaben zur Präsentation stehen in [06_offen.md](06_offen.md), Abschnitt 9.

- **Kameras:** Die Übersicht hängt an einer Stange schräg seitlich (M1, Daheng VEN-161, zugleich
  Szenenkamera von M4). Dazu kommen die Seitenkamera (M3, USB) und die Handgelenkkamera
  (M4, Daheng VEN-161 Fisheye). Die Lage der Stangenkamera und der Seitenkamera ist angenommen und
  in `cell.js` leicht verschiebbar, ebenso die Maße der Ablagen und die Fase (12 mm).
- **Bauteil:** 60 × 40 × 15 mm, Loch 10 mm.
- **Arbeitstitel:** „Dynamisches Greifen und automatisierte Sichtprüfung mit einem kollaborativen Roboter“.
- **Optional:** Greifer-CAD (`docs/greifer/**/*.stp`) per FreeCAD/cadquery als glb statt Grundkörper.

## Kontrolle vor dem Vortrag

- `npm install`, `python build_data.py`, `npm run dev` → alle Szenen durchklicken (vor/zurück, Sprung `3.2` Enter, Übersicht `O`).
- `node tools/shoot_all.mjs shots` → Kontaktbogen aller Endzustände, **keine Konsolenfehler, keine externen Requests**.
- `node tools/shoot.mjs shots http://localhost:5180/ play:1.4.0:3` für die Hero-Animationen.
- Plausibilität: Zellenlayout gegen `system.yaml` und die Draufsicht der GUI (M2-Tab) vergleichen; θ/Ecken in 3.2–3.4 gegen `python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"`.
- `npm run build`, `start.bat` aus `dist/` offline testen.
