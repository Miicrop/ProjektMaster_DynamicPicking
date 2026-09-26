# 08 – Offene Fragen und Entscheidungen

## Offene Fragen

### Hardware
- [x] Welches Neura-Modell? → **LARA**, 6 Achsen, Software/API **v5.0.8** (aus Neura-Lieferung und Backup)
- [~] IP-Adresse der Steuerung: **192.168.2.20** (steht auf dem Roboterfuß) – Niklas prüft vor Ort
- [ ] Greifer: Im Backup ist das Werkzeug **„RobotiQ“** (Modbus, TCP-Versatz 210 mm) angelegt. Ist er montiert und über `grasp()`/`release()` ansteuerbar?
- [ ] Muss der Wechsel in den Automatikmodus am Pendant bestätigt werden (Schlüsselschalter)?
- [-] Offline-Simulation (Neura-VM): vorerst nicht benötigt, eigener Simulator reicht (2026-09-26)
- [ ] Welche Kameras (Modell, Auflösung, USB/GigE)? Die Testfotos stammen von einer Handykamera (Top-down) bzw. einer 4K-Kamera (seitlich)
- [ ] Beleuchtung an der Prüfstation vorhanden?
- [ ] Handgelenkkamera (für M4): Modell, Anschluss, Montage; Hand-Auge-Kalibrierung nötig?
- [ ] USB-Bandbreite bei drei Kameras (zwei davon ggf. 4K) am Laptop prüfen
- [ ] **ArUco-Marker:** Die 3D-gedruckten Marker haben keinen hellen Rand und sind deshalb nicht detektierbar → weißen Rand ergänzen oder Papiermarker (`make_markers.py`). Markergröße und IDs (Dictionary `DICT_4X4_50`) festhalten.
- [~] Innenmaß des weißen Rahmens und Markerpositionen ausmessen (`workspace.size_mm`, `markers_mm`) – Niklas misst vor Ort

### Bauteil
- [~] Geometrie und Abmessungen des Bauteils? Benötigt: Höhe in der Seitenansicht (`part_height_mm`), Loch-Solldurchmesser und Toleranz – Niklas misst vor Ort
- [x] Ist das Teil in der Draufsicht symmetrisch? → Nein, die **abgeschrägte Ecke** macht die Lage eindeutig (360°)
- [x] Was ist die „Kerbe“? → die **kleine eckige Öffnung** rechts in der Seitenansicht (bestätigt 2026-09-26)
- [ ] Wie muss das Teil an der Prüfposition liegen (Etikettseite zur Kamera)? → Der Roboter muss es mit der passenden Orientierung ablegen (θ aus M1)
- [x] Format der Seriennummer → 5 Ziffern (Testteil „69420“), Regex `^[0-9]{5}$` (bestätigen)
- [ ] Wie viele Gut-/Schlechtteile stehen für Tests zur Verfügung? Welche Fehlerarten (fehlende Kerbe, falscher Durchmesser, fehlendes/unlesbares Etikett)?

### Organisation
- [ ] Abgabetermin und Umfang der Ausarbeitung?
- [ ] Gemeinsame Thesis oder Einzelteile pro Person?
- [ ] Git-Hosting (GitHub/GitLab der Hochschule)? Achtung: Neura-Client und -Doku sind proprietär → Repo **privat** halten
- [ ] Thesis gemeinsam auf Overleaf oder lokal (MiKTeX installieren)? Das Gerüst wurde noch nicht kompiliert.
- [ ] Hochschule/Studiengang/Betreuer auf dem Titelblatt (`thesis/main.tex`) eintragen.
- [ ] GitHub-Repo mit den bisherigen Robotertests bereitstellen

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
| 2026-09-26 | `opencv-python-headless` statt `opencv-contrib-python` | EasyOCR bringt headless mit, zwei cv2-Pakete kollidieren; ArUco ist seit 4.7 im Hauptpaket |
