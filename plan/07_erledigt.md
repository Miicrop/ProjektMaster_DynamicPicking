# 07 – Erledigt

Neueste Einträge oben. Format: `YYYY-MM-DD – Wer – Was`

## 2026-10-06 (2) – Niklas
- **Labor:** Punkte vermessen, Roboter im M2-Tab und im Automatikbetrieb genutzt, erster vollständiger
  Ablauf (noch ohne Greiferansteuerung und ohne Arbeitsraum-Kamera, M1/M3 mit Testbildern).
- **GUI M2:** Haken *Ohne Rückfrage joggen* (nur Jog, Standard aus, Reset beim Trennen).
- **M2:** Greifwinkel korrigiert: `gripper_angle_offset_deg` 90 → 113 (Greifer 23° verdreht montiert);
  Test, dass Greif- und Ablage-rz zusammenpassen. Pick/Place zweistufig: schnell (`linear_speed_mps`)
  bis `approach_slow_mm` = 20 mm über dem Ziel, Rest langsam.
- **Ablauf:** kein Home-Umweg mehr beim Prüfen (wartet über der Prüfvorrichtung). GUI-Ablauf zeigt
  M1-/M3-Bild und Kurzinfo direkt nach jedem Schritt, bei Fehler das Rohbild.
- **Simulator:** Werkzeug `ZimmerLWR50` (197,5 mm); Robotertests unabhängig von `gripper_enabled`.
  105 Tests grün.

## 2026-09-28 – Niklas
- **GUI:** Roboter-Draufsicht gedreht – Basis oben, x nach unten, y nach rechts (Blick des Bedieners).
- **M1/M3:** Zwischenschritte der Bildverarbeitung speicherbar (`common/trace.py`): GUI-Ablauf
  *+ Zwischenschritte*, CLI `--save-steps` → `logs/<datum>/…/steps/`, 13 Bilder M1, 14 Bilder M3.
  Nebenbei: `last_result`/`last_details` werden je Durchlauf zurückgesetzt (vorher blieben nach
  einem Fehlschlag die Bilder des vorigen Zyklus stehen).
- **M2:** `robot_check calib` (Kalibrierung Arbeitsbereich → Roboter über die Marker-Mitten, mit
  Restfehler) und `robot_check point` (Zeigetest ohne Greifen, Protokoll `logs/point_tests.csv`);
  `NeuraRobot.point_at` / `retreat`.
- **Plan:** Checkliste für den Labortest [09_labortest.md](09_labortest.md). 73 Tests grün.

## 2026-09-27 – Niklas
- **Thesis:** Neues Kapitel `02b_vorprojekt.tex` zum Vorprojekt bei GROB (KI-basierte Roboterbahnen
  in Process Simulate): Aufgabe und Eingrenzung, Kollisionssets, Zell-/Robotersicherheit, manuelle
  Bahnplanung, Vorgehen, Robotic Automatic Path Planner, Bezug zum Demonstrator. Bilder unter
  `thesis/figures/grob/`. Einleitung angepasst.
- **Thesis:** Pseudocode durch Grafiken ersetzt (Vorprojekt, M1-Pose, M2-Greifsequenz, M3-Entscheidung);
  gemeinsame TikZ-Stile `pap …` in `main.tex`.
- **Thesis:** Greifer korrigiert: Zimmer MATCH LWR50L-23-00004-A mit Robotermodul LWR50F-13-05-A
  (Datenblätter und CAD in `docs/greifer/`). Absatz zum bewusst einfachen Bauteil ergänzt.
- **Repo:** Neura-Doku (`docs/neura/`) und NeuraPy-Client (`vendor/neurapy/`) dürfen ins Git;
  nur `resources/` bleibt ausgeschlossen. Hinweise in README, ANLEITUNG und vendor-README angepasst.

## 2026-09-26 (6) – Niklas
- **Thesis:** Gesamtplan im geführten Dialog erstellt (`thesis/blueprint.md`).
- Entwürfe für Kurzfassung, Einleitung, Grundlagen, Systemkonzept, M1–M3 und das neue Kapitel
  „Integration und Bedienung“; Gerüste für Evaluation und Fazit. Offene Stellen als `\todo`.
- Kapitelfolge: `09_integration.tex` neu, Evaluation → `10_evaluation.tex`, Fazit → `11_fazit.tex`.
- `main.tex`: Titelblatt korrigiert, Pakete für TikZ, Pseudocode (deutsch) und `todonotes`.
- 8 Literaturquellen ergänzt (DOI über Crossref geprüft). Baut lokal mit MiKTeX (`latexmk main.tex`).

## 2026-09-26 (5) – Niklas
- **Bugfix:** Nach NOT-STOPP + „Fehler quittieren“ ließ sich der Ablauf nicht neu starten, weil
  `init_program()` fehlte (neurapy `stop()` beendet das Programm auf der Steuerung). Jetzt: nach
  `stop()` lehnt der Roboter Bewegungen ab, `reset()` bereitet ihn neu vor; GUI „Fehler quittieren“
  (Ablauf) bzw. „Freigeben“ (Tab M2). Regressionstests für Simulator, Ablauf und GUI.
- Kameras: dritte Kamera `wrist_camera` (Handgelenk, für M4) vorbereitet, `python -m common.camera`
  listet Kameranummern mit Foto, Fehlermeldung bei doppelt vergebener Kameranummer. 59 Tests grün.

## 2026-09-26 (4) – Niklas
- Zwischenstand dokumentiert: Planungsdateien an den Code angeglichen (Kerbe bestätigt, θ 0–360°,
  Logging, Kalibrierung über Rahmenecken, Konzept vs. Umsetzung), Zwischenstand und nächste Schritte
  in `06_roadmap.md`.
- `ANLEITUNG.md` für das Team: Einrichten, erster Start ohne Hardware, GUI, Arbeit am eigenen Modul,
  Einstellungen, Inbetriebnahme am echten Aufbau, Logs, Tests, Spielregeln, Fehlersuche.

## 2026-09-26 (3) – Niklas
- Offene Punkte geklärt: Kerbe = eckige Öffnung; IP und Maße prüft Niklas vor Ort; Neura-VM vorerst nicht nötig.
- Alle Module einzeln startbar (`python -m m1_vision_topdown | m2_robot_control | m3_inspection`),
  Gesamtablauf `python -m orchestrator` mit frei wählbaren Varianten (`--detector/--robot/--inspector`).
- `orchestrator/factory.py` (gemeinsamer Aufbau für CLI und GUI), `orchestrator/logbook.py`
  (CSV-Protokoll je Zyklus + Debug-Bilder), Zustandsbeobachter und Zyklusdauer im Orchestrator.
- **GUI** (`python -m gui` bzw. `start_gui.bat`, PySide6): Tabs Ablauf, M1, M2, M3, Einstellungen;
  Live-Anzeige von Zustand, Bildern, Roboter-Draufsicht und Ergebnissen; Posen teachen; STOPP;
  Einstellungen bearbeiten und speichern, ohne dass Kommentare in `system.yaml` verloren gehen (ruamel.yaml).
- 56 Tests grün (inkl. GUI-Test ohne Bildschirm).

## 2026-09-26 (2) – Niklas
- Inhalt von `new_input/` einsortiert: Top-down-Fotos → `code/m1_vision_topdown/tests/data/`,
  Seitenbilder → `code/m3_inspection/tests/data/`, Neura-PDFs → `docs/neura/`,
  NeuraPy-Windows-Client → `code/m2_robot_control/vendor/neurapy/`, Steuerungssoftware und
  Roboter-Backup → `resources/neura_controller/` (nicht versioniert).
- **M1:** Arbeitsbereich über ArUco oder weißen Rahmen, Bauteilpose inkl. Fase (0–360°), Marker-Generator.
  Befund: Die gedruckten Marker haben keinen hellen Rand und werden nicht erkannt.
- **M2:** `NeuraRobot` auf Basis von NeuraPy v5.0.8, Simulator der Steuerung, `robot_check`-Werkzeug,
  Einsteiger-Anleitung `ANLEITUNG_NEURA.md`.
- **M3:** Bauteil/ROIs, Lochdurchmesser (Maßstab über Bauteilhöhe), Kerbe, OCR mit EasyOCR →
  alle 3 Testbilder korrekt (Seriennummer 69420, D/H ≈ 0,65, Kerbe erkannt).
- Orchestrator: `--replay`, `--sim-robot`, `--save-images`. 49 Tests grün.
- OpenCV auf `opencv-python-headless` vereinheitlicht (EasyOCR installiert dieses Paket, zwei cv2-Pakete kollidieren).

## 2026-09-26 – Niklas
- Projektstruktur angelegt: `plan/`, `code/`, `thesis/`.
- Planungsdokumente 00–08 erstellt (Übersicht, Architektur, Module, Roadmap, offene Fragen).
- Code-Gerüst: gemeinsame Schnittstellen (`common/interfaces.py`), Konfiguration, Transformationen, Orchestrator mit Zustandsautomat, Modul-Workspaces M1–M4 mit Interfaces und Mocks.
- 16 Unit-Tests (Transformationen, Mocks, Gut/Schlecht-Logik, Zustandsautomat) grün; `python -m orchestrator.main --mock` durchläuft komplette Zyklen.
- Thesis-Gerüst in LaTeX (KOMA `scrreprt`, biblatex `style=ieee`, biber) mit Kapitelstruktur und ersten Literaturquellen (noch nicht kompiliert, keine lokale TeX-Installation).
