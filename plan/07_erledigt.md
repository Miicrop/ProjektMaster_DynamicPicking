# 07 – Erledigt

Neueste Einträge oben. Offenes steht in [06_offen.md](06_offen.md).

## Log

### 2026-10-30 – Niklas
- **Thesis auf Code-Stand** (ARS `academic-paper`):
  - Kap. 08 (M4) aus Jeremys Unterlagen entworfen.
  - Grundlagen „Lernbasiertes Greifen“ geschrieben.
  - 11 neue Quellen mit geprüfter DOI.
  - Kap. 01–11 angepasst.
  - Abbildungen in `thesis/figures/{m1,m3,gui,m4}`.
  - Keine Datumsangaben zu Laborterminen im Text.
  - 94 Seiten, baut fehlerfrei.
- Klargestellt:
  - IP der Steuerung ist 192.168.2.13, die .20 auf dem Sockel ist falsch.
  - Öffnen und Schließen des Greifers funktioniert im Labor (noch nicht gepusht).
  - Greifbacken sind die Standardbacken von Zimmer, 40 mm passt.
  - Die Prüfvorrichtung ist eine erhöhte Ablage mit Kamerahalter und Hintergrund, ohne Formschluss.
  - Ein grober Zeigetest sah vielversprechend aus.
- Checkliste zum Abhaken als Artifact. Planungsdateien aufgeräumt: Roadmap, offene Fragen und
  Labortest sind in 06/07 aufgegangen, die Module enthalten nur noch Wissen.

### 2026-10-28 – Niklas
- **M4 übernommen:** Behavior Cloning (Diffusion Policy) von Jeremy per `git subtree` nach
  `code/m4_behavior_cloning/`.
  - GUI-Reiter „M4 Behavior Cloning“.
  - Im Ablauf Greifer `bc` (`orchestrator/m4_grasper.py`): Die Policy greift bis PRE_PLACE, M2 legt ab.
  - `setup_m4.bat` richtet die zweite Python-Umgebung ein (3.12, torch, lerobot).
- Gemeinsamer Roboter- und Kamerazugriff M2/M1 ↔ M4 (`gui/robot_access.py`).
- Kamera oben = Daheng VEN-161 (`source: daheng:<Seriennummer>`).
- Platzhalter `m4_ai_grasping`/`AiGrasper` und Config `wrist_camera` entfernt.
- **Neura-VM:** Übergabe M2 → M4 → M2 getestet. Zwei gleichzeitige Verbindungen gehen,
  danach laufen `reset()` und Ablegen durch M2 fehlerfrei.
- 118 Tests grün (+ 468 von Jeremy).

### 2026-10-21/22 – Niklas (Präsentation, Klärungen)
- Präsentation `presentation/abschluss/`: 37 von 39 Szenen gebaut. Einzelheiten stehen in
  [10_praesentation_konzept.md](10_praesentation_konzept.md).
- **Bauteil:** 60 × 40 × 15 mm, Loch 10 mm, Toleranz ±0,4 mm (Demonstrationswert).
- **Rolle M4:** übernimmt nur PICK, PLACE_INSPECT macht M2.
- GROB-Bilder für das Vorprojekt dürfen genutzt werden.
- Befund M1: Das Bauteil erscheint auf den Testfotos 8–15 % zu groß (Parallaxe). Die Lage ist
  stabil (±0,4 mm). Die Bewertung ist offen.

### 2026-10-06 – Niklas (Labor)
- **Erster vollständiger Ablauf am echten Roboter.** M1 und M3 liefen mit Testbildern, ohne
  Greiferansteuerung.
- Werkzeug „ZimmerLWR50“ (TCP 197,5 mm) angelegt.
- Posen geteacht: inspection, bin_good, bin_bad, Home.
- Kalibrierung eingemessen (0,35°, [205,1, −319,7] mm, Tisch z 2,1 mm).
- Papier-Marker, Mittenabstand 400 mm, Arbeitsbereich 330 × 330 mm.
- Code:
  - Greifwinkel-Offset 113° (Greifer 23° verdreht montiert).
  - Pick/Place in zwei Stufen.
  - Kein Home-Umweg beim Prüfen.
  - Haken *Ohne Rückfrage joggen*.
  - Schrittbilder im GUI-Ablauf.

### 2026-09-26 bis 09-28 – Niklas (Aufbau ohne Hardware)
- Projektstruktur, Planungsdokumente, Code-Gerüst mit Schnittstellen und Mocks.
- **M1:** Arbeitsbereich über ArUco (anfangs mit Rückfall auf einen weißen Rahmen), Pose mit Fase
  für 0–360°.
- **M2:** `NeuraRobot` auf NeuraPy v5.0.8, eigener Simulator der Steuerung, `robot_check`
  einschließlich `calib` und `point`, `ANLEITUNG_NEURA.md`.
- **M3:** Seriennummer (EasyOCR), Loch (Maßstab über die Bauteilhöhe), Kerbe, Gut/Schlecht.
  Alle Testbilder korrekt.
- **Ablauf:** Zustandsautomat, CSV-Logbuch, Zwischenschritte M1/M3 (`--save-steps`), jedes Modul
  einzeln startbar.
- **GUI** (PySide6) mit Tabs für Ablauf, M1–M3 und Einstellungen. STOPP mit `reset()`.
- `ANLEITUNG.md` für das Team.
- Neura-Doku und NeuraPy-Client im Repo.
- **Thesis:**
  - Gesamtplan (`thesis/blueprint.md`) erstellt.
  - Entwürfe aller Kapitel und Kap. 02b Vorprojekt GROB geschrieben.
  - Pseudocode durch TikZ-Grafiken ersetzt.
  - Erste Quellen mit DOI.

## Geklärte Fragen

| Frage | Antwort |
|---|---|
| Roboter | Neura **LARA**, 6 Achsen, Software/API v5.0.8, IP 192.168.2.13 |
| Greifer | Zimmer MATCH LWR50L-23-00004-A mit Robotermodul LWR50F-13-05-A. Werkzeug „ZimmerLWR50“, TCP 197,5 mm, Standardbacken |
| Kameras | Oben und Handgelenk: Daheng VEN-161 (1440×1080, Global Shutter). Seite: einfache USB-Kamera |
| Marker | ArUco `DICT_4X4_50` auf Papier mit weißem Rand. Die 3D-gedruckten Marker waren ohne hellen Rand nicht erkennbar |
| Bauteil | 60 × 40 × 15 mm, Loch 10 mm ±0,4 mm. Die Fase macht die Lage eindeutig (360°). Kerbe = kleine eckige Öffnung, Seriennummer 5 Ziffern |
| Prüfvorrichtung | Gedruckt, Fläche 38 mm über der Platte, mit Kamerahalter und Hintergrund, ohne Formschluss |
| Rolle M4 | Greift (PICK bis PRE_PLACE ~9 cm über der Prüfung), M2 legt ab. Für den Demonstrator nicht nötig |
| Thesis | Gemeinsame Arbeit, Modulkapitel je Person. Baut lokal mit MiKTeX (`latexmk`), Titelblatt eingetragen |

## Entscheidungen

| Datum | Entscheidung | Begründung |
|---|---|---|
| 2026-09-26 | Zentraler Python-Orchestrator mit Datenklassen | Einfach, gut testbar, kein Middleware-Setup |
| 2026-09-26 | Jedes Modul: abstraktes Interface + Mock | Unabhängige Entwicklung ohne Hardware |
| 2026-09-26 | Doku/Thesis Deutsch, Code Englisch | Abgabe auf Deutsch, Code international lesbar |
| 2026-09-26 | LaTeX mit biblatex (`style=ieee`) + biber | IEEE-Zitierstil gefordert |
| 2026-09-26 | Neura-Client unverändert unter `vendor/`, IP per Config | Kein Installationsschritt; Client-Update = Datei tauschen |
| 2026-09-26 | Eigener Simulator der Neura-Steuerung | Tests des Robotercodes ohne Hardware |
| 2026-09-26 | M3: Maßstab über Bauteilhöhe, ROIs relativ zum Bauteil | Unabhängig vom Kameraabstand, keine mm/px-Kalibrierung |
| 2026-09-26 | OCR mit EasyOCR | Läuft per `pip` ohne Tesseract-Installation |
| 2026-09-26 | `opencv-python-headless` statt `opencv-contrib-python` | EasyOCR bringt headless mit, zwei cv2-Pakete kollidieren |
| 2026-09-26 | Thesis als Projektbericht ohne Forschungsfrage; Erfolg = vollautomatischer Durchlauf | Selbst gewähltes Projekt; Details in `thesis/blueprint.md` |
| 2026-09-26 | Thesis: kein Quellcode, nur Diagramme; offene Punkte als `\todo` | Lesbarkeit; Offenes bleibt im PDF sichtbar |
| 2026-10-06 | Jog-Rückfrage per Haken abschaltbar, nur fürs Joggen, nicht gespeichert | Viele kleine Schritte beim Teachen |
| 2026-10-06 | `gripper_angle_offset_deg` = 113° (90° + 23°) | Greifer um 23° verdreht montiert |
| 2026-10-06 | Pick/Place: schnell bis 20 mm über dem Ziel, Rest langsam | Zykluszeit; langsame Endanfahrt bleibt |
| 2026-10-06 | Kein Home-Umweg beim Prüfen, Roboter wartet über der Prüfvorrichtung | Greifer dort nicht im Bild; spart zwei Bewegungen |
| 2026-10-06 | Arbeitsbereich nur über ArUco (Rahmen-Rückfall ungenutzt) | Kein weißer Rahmen mehr auf der Platte |
| 2026-10-28 | M4 als eigener Python-Prozess (3.12) | lerobot braucht 3.12; torch/OpenCV kollidieren mit EasyOCR |
| 2026-10-28 | Neura-VM als Teststufe zwischen Simulator und Anlage | Echte Steuerungssoftware, z. B. für die Übergabe M4 → M2 |
| 2026-10-30 | Thesis ohne Datumsangaben zu Laborterminen | Allgemein halten |
