# 09 – Checkliste Labortest

Erster Test der Zelle mit echter Hardware. Ziel: am Ende des Tages ein vollständiger Zyklus
mit echtem Teil und Material für die Doku. Befehle im Ordner `code` mit aktivierter venv.

**Koordinatensysteme:** Roboterposen, Grenzen und Tipp-Schritte sind im **Basis-KS** des Roboters.
M1 rechnet im **Arbeitsraum-KS** (Ursprung innere Rahmenecke unten links, x rechts, y oben aus
Kamerasicht) und wird über `workspace_to_robot` umgerechnet. Diese Transformation wird in
Schritt 8 eingemessen – vorher greift der Roboter mit Platzhalterwerten daneben.

## Vorher / mitnehmen

- [ ] Aktuellen Code-Stand committen (Rückweg, falls vor Ort etwas kaputtgeht)
- [ ] ArUco-Marker drucken (`python -m m1_vision_topdown.make_markers`), in 100 % gedruckt? Schwarzes Quadrat = 50 mm nachmessen
- [ ] Maßband, Lineal, Klebeband, Schere, Stift
- [ ] Gut- und Schlechtteile (welche Fehlerarten?), Laptop-Netzteil, USB-Hub, LAN-Kabel
- [ ] [ANLEITUNG_NEURA.md](../code/m2_robot_control/ANLEITUNG_NEURA.md) Abschnitte 1, 3, 4 gelesen

## Reihenfolge vor Ort

| # | Schritt | Befehl / Ort | Ergebnis notieren |
|---|---|---|---|
| 1 | Netzwerk, Verbindung lesen | `robot_check info` | IP, Version, Fehler |
| 2 | Not-Halt testen, Override 20 % | Pendant, `robot.override` | – |
| 3 | Home, Greifer, Achsentest | `robot_check home`, `gripper`, `axes` | Richtungen +X/+Y/+rz im Raum |
| 4 | Werkzeug/TCP prüfen | Pendant | Angelegt ist „RobotiQ“ mit 210 mm – passt das zum montierten Zimmer-Greifer? Sonst Offset anpassen, **vor** Schritt 8 |
| 5 | Kameras | `python -m common.camera`, Kameras fest montieren, Licht | Indizes → `source` in der Config |
| 6 | Maße | Maßband | Rahmen-Innenmaß → `workspace.size_mm`, Marker-Mitten → `markers_mm`, Bauteilhöhe, Lochdurchmesser |
| 7 | M1 live | GUI Tab M1, Methode `aruco` | Alle 4 Marker erkannt? Bauteilpose plausibel? |
| 8 | Kalibrierung | `robot_check calib` (Anleitung 7a) | RMS in mm, Ausgabe aufheben |
| 9 | Posen teachen | `robot_check pose inspection` usw. | `inspection`, `bin_good`, `bin_bad`, `limits_mm` |
| 10 | Zeigetest | `robot_check point` an 5–10 Stellen (Anleitung 7b) | Versatz dx/dy, Finger ausgerichtet? |
| 11 | Greiftest | `robot_check pick-test` | Greift und legt sauber ab? |
| 12 | M3 live | GUI Tab M3 mit Teil an der Prüfposition | ROIs passen? OCR liest? |
| 13 | Erster Zyklus | GUI Tab Ablauf, „1 Zyklus“, 1 Teil | – |
| 14 | Serie | GUI Tab Ablauf, Dauerbetrieb, Gut- und Schlechtteile | `cycles_*.csv` |

Nach jedem Schritt mit Config-Änderung: in der GUI speichern (Strg+S).

## Bekannte Risiken – darauf achten

- **Marker-Zuordnung:** Die Zuordnung ID → Ecke muss zur Config passen, sonst wird das Bild falsch
  entzerrt, ohne dass ein Fehler kommt. Test: Teil nahe der Ecke unten links → kleine x/y.
- **Objektivverzerrung** wird nicht korrigiert (`calibration_file` wird noch nicht verwendet). Der
  Fehler wächst zum Bildrand hin → im Zeigetest Randpositionen mit messen.
- **Parallaxe:** M1 sieht die Oberseite des Teils, die über der Tischebene liegt. Das verschiebt die
  Position nach außen, je weiter das Teil von der Bildmitte weg ist. Kamera möglichst hoch und
  mittig über dem Arbeitsbereich.
- **Fase nicht gefunden** (Confidence 0,5): Winkel nur bis auf 180° eindeutig. Dann liegt das Teil
  an der Prüfstation evtl. verdreht und das Etikett zeigt von der Kamera weg.
- **Kamera oder Marker bewegt:** Eine bewegte Kamera ist für M1 unkritisch, weil die Marker in jedem
  Bild neu gefunden werden. Verschobene Marker → neu ausmessen und neu kalibrieren.
- **Greifer:** Wird der Zimmer-Greifer über das Werkzeug „RobotiQ“ korrekt geöffnet/geschlossen?

## Für die Doku festhalten

- [ ] Fotos der Zelle aus mehreren Winkeln (Gesamtaufbau, Kameras, Greifer, Prüfstation, Ablagen)
- [ ] Video eines kompletten Zyklus
- [ ] GUI-Screenshots aller Tabs, möglichst mit echtem Bild
- [ ] 1–2 schöne Zyklen mit „Bilder speichern“ + „+ Zwischenschritte“ (`logs/<datum>/…/steps/`)
- [ ] Kalibrier-Ausgabe (Restfehler, RMS), `logs/point_tests.csv`, `logs/cycles_*.csv`
- [ ] Achsentest-Protokoll, gemessene Maße, eingetragene Config (`config/system.yaml` sichern)
- [ ] Notizen: Was hat nicht geklappt, was wurde vor Ort geändert?

Danach in der Thesis: Blueprint Fall D (Aufbau, Maße, Fotos) und Fall E (Versuche),
siehe [../thesis/blueprint.md](../thesis/blueprint.md) §7.
