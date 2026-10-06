# 08 – Offene Fragen und Entscheidungen

## Offene Fragen

### Hardware
- [x] Welches Neura-Modell? → **LARA**, 6 Achsen, Software/API **v5.0.8** (aus Neura-Lieferung und Backup)
- [~] IP-Adresse der Steuerung: **192.168.2.20** (steht auf dem Roboterfuß) – Niklas prüft vor Ort
- [~] Greifer: Werkzeug **„ZimmerLWR50“** (TCP 197,5 mm) im Labor angelegt (2026-10-06). **Offen:** Ansteuerung über `grasp()`/`release()` – bisher `gripper_enabled: false`
- [ ] Muss der Wechsel in den Automatikmodus am Pendant bestätigt werden (Schlüsselschalter)?
- [-] Offline-Simulation (Neura-VM): vorerst nicht benötigt, eigener Simulator reicht (2026-09-26)
- [ ] Welche Kameras (Modell, Auflösung, USB/GigE)? Die Testfotos stammen von einer Handykamera (Top-down) bzw. einer 4K-Kamera (seitlich)
- [ ] Beleuchtung an der Prüfstation vorhanden?
- [ ] Handgelenkkamera (für M4): Modell, Anschluss, Montage; Hand-Auge-Kalibrierung nötig?
- [ ] USB-Bandbreite bei drei Kameras (zwei davon ggf. 4K) am Laptop prüfen
- [x] **ArUco-Marker:** Die 3D-gedruckten Marker haben keinen hellen Rand und sind deshalb nicht detektierbar → weißen Rand ergänzen oder Papiermarker (`make_markers.py`). Markergröße und IDs (Dictionary `DICT_4X4_50`) festhalten.
- [~] Innenmaß des weißen Rahmens und Markerpositionen ausmessen (`workspace.size_mm`, `markers_mm`) – Niklas misst vor Ort

### Bauteil
- [~] Geometrie und Abmessungen des Bauteils? Benötigt: Höhe in der Seitenansicht (`part_height_mm`), Loch-Solldurchmesser und Toleranz – Niklas misst vor Ort
- [x] Ist das Teil in der Draufsicht symmetrisch? → Nein, die **abgeschrägte Ecke** macht die Lage eindeutig (360°)
- [x] Was ist die „Kerbe“? → die **kleine eckige Öffnung** rechts in der Seitenansicht (bestätigt 2026-09-26)
- [~] Wie muss das Teil an der Prüfposition liegen (Etikettseite zur Kamera)? → Ablagen geteacht (rz −157°, Teil mit der langen Seite entlang Marker-Kante 0–3). Greifwinkel = Home + θ + 113° → **im Labor mit dem Zeigetest prüfen**; ohne erkannte Fase kann das Teil um 180° verdreht liegen
- [x] Format der Seriennummer → 5 Ziffern (Testteil „69420“), Regex `^[0-9]{5}$` (bestätigen)
- [ ] Wie viele Gut-/Schlechtteile stehen für Tests zur Verfügung? Welche Fehlerarten (fehlende Kerbe, falscher Durchmesser, fehlendes/unlesbares Etikett)?

### Organisation
- [ ] Abgabetermin und Umfang der Ausarbeitung?
- [x] Gemeinsame Thesis oder Einzelteile pro Person? → **gemeinsame** Arbeit, Modulkapitel je Person (2026-09-26)
- [ ] Git-Hosting (GitHub/GitLab der Hochschule)? Neura-Doku und NeuraPy-Client dürfen ins Repo (2026-09-27), nur `resources/` bleibt draußen (Passwort-Hashes)
- [~] Thesis gemeinsam auf Overleaf oder lokal? → baut lokal mit MiKTeX (`latexmk`); Overleaf weiterhin möglich
- [x] Hochschule/Studiengang/Betreuer auf dem Titelblatt eingetragen (2026-09-26)

### Thesis (Inhalt, siehe [../thesis/blueprint.md](../thesis/blueprint.md))
- [ ] Weiterverwendung im Pflegerobotik-Projekt (Mensch ärgere dich nicht mit Senioren) in der Arbeit erwähnen? Wenn ja: Einleitung, Fazit oder Ausblick?
- [ ] Evaluation: Anzahl Durchläufe je Versuchsreihe und ob/welche Kennzahlen ausgewertet werden
- [ ] Ausblick: welche offenen Punkte werden genannt?
- [ ] Englisches Abstract zusätzlich zur Kurzfassung nötig?
- [ ] Quellen für die Motivation (Kap. 1) und Normen zu Cobots (ISO 10218, ISO/TS 15066) aufnehmen?
- [~] Kalibrierung Arbeitsbereich → Roboter: Verfahren steht (TCP auf die 4 Marker-Mitten, `robot_check calib` → `fit_rigid_2d` + Restfehler; Prüfung mit Zeigetest `robot_check point`). Nach dem Labortest in Kap. 3.4 / 4 / 5 beschreiben
- [ ] GitHub-Repo mit den bisherigen Robotertests bereitstellen
- [~] Greifer: Werkzeug „ZimmerLWR50“ mit 197,5 mm angelegt (2026-10-06). Offen: Öffnen/Schließen des Zimmer-Greifers (IO-Link) aus dem Code
- [ ] Vorprojekt GROB (Kap. 02b): Dürfen Vorprojekt und Bildschirmfotos gezeigt werden (Freigabe GROB)? Wer schreibt den Abschnitt „Alternative Verfahren“?

## Entscheidungen

| Datum | Entscheidung | Begründung |
|---|---|---|
| 2026-09-26 | Kommunikation über zentralen Python-Orchestrator mit Datenklassen | Einfach, gut testbar, kein Middleware-Setup; später auf Netzwerk erweiterbar |
| 2026-09-26 | Jedes Modul: abstraktes Interface + Mock | Unabhängige Entwicklung ohne Hardware |
| 2026-09-26 | Doku/Thesis Deutsch, Code Englisch | Abgabe auf Deutsch, Code international lesbar |
| 2026-09-26 | LaTeX mit biblatex (`style=ieee`) + biber | IEEE-Zitierstil gefordert, biblatex gut für deutschsprachige Arbeiten |
| 2026-09-26 | Vorerst kein Git | Entscheidung vertagt, siehe Organisation |
| 2026-09-26 | Arbeitsbereich: ArUco mit automatischem Rückfall auf den weißen Rahmen | Marker derzeit nicht detektierbar; Rahmen ist kontrastreich und liefert dieselbe Homographie |
| 2026-09-26 | Neura-Client unverändert unter `vendor/` einbinden, IP per Config | Kein Installationsschritt nötig; Client-Update = Datei tauschen |
| 2026-09-26 | Eigener Simulator der Neura-Steuerung | Offizielle VM nicht verfügbar; Tests des Robotercodes ohne Hardware |
| 2026-09-26 | M3: Maßstab über Bauteilhöhe, ROIs relativ zum Bauteil | Unabhängig vom Kameraabstand; keine separate mm/px-Kalibrierung nötig |
| 2026-09-26 | OCR mit EasyOCR | Läuft per `pip` ohne separate Tesseract-Installation; alle Testbilder korrekt |
| 2026-09-26 | Kerbe = eckige Öffnung in der Seitenansicht | Bestätigt durch Niklas |
| 2026-09-26 | Neura-VM vorerst nicht nötig | Eigener Simulator deckt Softwaretests ab |
| 2026-09-26 | Thesis als begleitender Projektbericht ohne Forschungsfrage; Erfolg = vollautomatischer Durchlauf, Messwerte nur demonstrativ | Selbst gewähltes Interessensprojekt; Details in `thesis/blueprint.md` |
| 2026-09-26 | Thesis: kein Quellcode im Text, nur Diagramme und Pseudocode; offene Punkte als `\todo` | Lesbarkeit; offene Stellen bleiben im PDF sichtbar |
| 2026-09-26 | `opencv-python-headless` statt `opencv-contrib-python` | EasyOCR bringt headless mit, zwei cv2-Pakete kollidieren; ArUco ist seit 4.7 im Hauptpaket |
| 2026-10-06 | Jog-Rückfrage am echten Roboter per Haken abschaltbar, nur fürs Joggen, nicht gespeichert | Viele kleine Schritte beim Teachen; Sicherheitsabfrage bleibt Standard |
| 2026-10-06 | `gripper_angle_offset_deg` = 113° (90° + 23° Einbauwinkel) | Greifer im Labor um 23° verdreht montiert; an den Ablagen rz = Home + 23° |
| 2026-10-06 | Pick/Place: schnell bis 20 mm über dem Ziel (`approach_slow_mm`), Rest langsam | Zykluszeit; langsame Endanfahrt bleibt |
| 2026-10-06 | Kein Home-Umweg beim Prüfen: Roboter wartet auf Anfahrhöhe über der Prüfvorrichtung | Greifer dort nicht im Bild der Prüfkamera (Labor); spart zwei Gelenkbewegungen |
