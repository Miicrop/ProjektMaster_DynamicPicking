# 10 – Abschlusspräsentation: Konzept

**Stand:** 2026-10-21 – Konzept + Storyboard, Gerüst in [`presentation/abschluss/`](../presentation/abschluss/README.md) (alle Szenen als Entwurfsblätter durchklickbar).
**Vorlage:** Masterarbeits-Präsentation „Das Zerlegeschema wird lebendig“ (`Masterarbeit_Neu/presentation/abschluss`, Konzept dort in `plan/11-praesentation-konzept.md`). Engine, Bausteine und Werkzeuge sind von dort übernommen.

> **Wiedereinstieg** (Aufgaben: [06_offen.md](06_offen.md) Abschnitt 9, Verlauf: [07_erledigt.md](07_erledigt.md))
>
> - **Stand:** 37 von 39 Szenen gebaut. Offen sind 6.2 (Jeremy) und 7.2 (Messwerte). Die M4-Umstellung
>   (6.1, 1.2, 2.4, Architektur, 7.1/7.3) fehlt noch.
> - Die Szenenliste in `src/storyboard.js` ist die maßgebliche Fassung. Änderungen an der Dramaturgie
>   dort **und** hier eintragen.
> - **Welten:**
>   - `cell.js` + `kit/lara.js`: Zelle, Zyklus, Greifsequenz, Grenzen, Finale mit Schild „Noch Fragen?“ (7.5) und Ausblick-Spielfeld (7.4).
>   - `arch.js`: Akt 2 und 6.1.
>   - `vision.js`: Akt 3.
>   - `inspect.js`: Akt 5, mit Detailblättern unter dem Foto.
>   - `sheets.js`: 1.5, 1.6, 2.4, 4.7, 7.1, 7.3 und der Anhang.
> - **Daten:** `build_data.py` exportiert Config, M1/M3-Ergebnisse auf den Testbildern, Zwischenbilder
>   (`m3.trace`, `m3.notches`), `robot_check` gegen den Simulator (`m2.check`) und die Posen vom
>   Labortag aus Commit 1f5cdc1 (`data.lab`). Der GUI-Screenshot entsteht mit `tools/gui_shot.py`
>   (Qt offscreen).
> - **LARA** stammt aus der URDF (`public/urdf/lara5.urdf`, Kinematik aus den Gelenken). Die Home-Pose
>   ergibt Flansch-z 434,5 mm wie im Roboter-Backup. Alle Stationsposen sind erreichbar, und der
>   Greifwinkel folgt derselben Formel wie `m2_robot_control.robot.as_target`.
> - **Kontrollen beim Laden:** Jede Zielpose muss erreicht werden, und das Schild hält ≥ 20 mm Abstand
>   zu Arm und Tisch. Sonst kommt eine Warnung in der Konsole (`tools/shoot.mjs` meldet sie).
> - **Achtung:** Das Log vom 05.10. stammt aus der Neura-VM. Vom Labortag liegt kein Log im Repo.

## Rahmen

Projektabschluss an der HS Kempten. **Alle vier tragen vor**, je Akt ein Sprecher. Dauer noch offen. Es gibt **nur eine Fassung**; die Kürzungskandidaten (k) werden bei Bedarf im Storyboard gestrichen. M4 bekommt eine Platzhalter-Szene, die Jeremy füllt.

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
- 1.2 Die Zelle: Plan extrudiert zu 3D, Positionsnummern ①–⑧ (LARA, Greifer, Übersichtskamera an der Stange (M1), Seitenkamera (M3), Handgelenkkamera (M4), Rahmen + ArUco, Prüfposition, Ablagen GUT/SCHLECHT).
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

**Akt 6 – M4 KI-Greifen (Jeremy Zid)**
- 6.1 M4 übernimmt das Greifen: M1 erkennt weiter, M4 greift mit der Handgelenkkamera aus dem Rahmen und legt in die Prüfung, nach M3 übernimmt wieder M2 (Greifen aus der Prüfung, Sortieren). Im Zustandsring klappen PICK und PLACE_INSPECT auf M4 um, danach ein Umlauf mit der neuen Aufteilung.
- 6.2 Entwurfsblatt (Platzhalter aus dem Storyboard, füllt Jeremy).

**Akt 7 – Ergebnis & Ausblick (alle)**
- 7.1 Labortag 06.10.: erster vollständiger Ablauf am echten Roboter (ehrlich: noch ohne Greiferansteuerung, M1/M3 mit Testbildern).
- 7.2 Messwerte (Platzhalter, datengetrieben): Kalibrier-RMS, Zeigetest-Versatz, Zyklusdauer, Erkennungs-/Prüfquote.
- 7.3 Offen & nächste Schritte (Greifer live, Kameras live, Evaluation).
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
