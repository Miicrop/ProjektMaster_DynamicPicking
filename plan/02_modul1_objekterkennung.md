# 02 – Modul 1: Objekterkennung (Top-down-Kamera)

**Verantwortlich:** Person 1 · **Code:** `code/m1_vision_topdown/` · **Interface:** `ObjectDetector.detect() -> ObjectPose | None`

## Aufgabe

- Arbeitsbereich im Bild finden (4 ArUco-Marker an den Ecken).
- Bauteil innerhalb des Arbeitsbereichs finden.
- Position (x, y) und Orientierung θ bestimmen und im **Roboter-Koordinatensystem** an den Orchestrator übergeben.

## Verarbeitungskette (Konzept – Abweichungen in der Umsetzung siehe unten)

1. **Bildaufnahme** – Kamera mit fester Belichtung (kein Auto-Exposure, reproduzierbare Ergebnisse).
2. **Entzerrung** – Linsenverzeichnung mit intrinsischer Kalibrierung korrigieren (`cv2.undistort`, Kalibrierung per Schachbrett/ChArUco, Verfahren nach Zhang).
3. **ArUco-Detektion** – `cv2.aruco.ArucoDetector` mit festem Dictionary (z. B. `DICT_4X4_50`), Marker-IDs 0–3. Fehlt ein Marker → `VisionError` bzw. letzte gültige Homographie wiederverwenden (konfigurierbar).
4. **Homographie** – Aus den vier Markerzentren (bzw. Innenecken) und deren bekannten Positionen in mm: `cv2.findHomography` → Vogelperspektive des Arbeitsbereichs (`cv2.warpPerspective`) mit festem Maßstab (z. B. 1 px = 0,5 mm).
5. **Segmentierung** – Im entzerrten Arbeitsbereichsbild: Graustufen → Glättung → Schwellwert (Otsu) oder Hintergrundsubtraktion gegen Leerbild → Morphologie → Konturen. Marker-Bereiche ausmaskieren.
6. **Objektauswahl** – Größte Kontur mit plausibler Fläche (min/max aus Config).
7. **Pose** – Schwerpunkt über Bildmomente, Orientierung über `cv2.minAreaRect` oder Hauptachse (Momente 2. Ordnung). Bei symmetrischen Teilen θ auf [0°, 180°) normieren; falls eine Kerbe/ein Merkmal die Richtung eindeutig macht → [0°, 360°).
8. **Transformation** – Arbeitsbereich-mm → Roboter-KS über `common/transforms.py`.
9. **Rückgabe** – `ObjectPose` inkl. Konfidenz und Debug-Bild.

## Anforderungen (vorläufig)

| Größe | Ziel |
|---|---|
| Positionsgenauigkeit | ≤ ±2 mm |
| Winkelgenauigkeit | ≤ ±2° |
| Laufzeit `detect()` | < 500 ms |
| Robustheit | funktioniert bei Raumlicht, leichten Schatten |

## Umsetzung (Stand 2026-09-26)

- Arbeitsbereich wahlweise über **ArUco** (Markermittelpunkte → Homographie) oder die **Innenkante
  des weißen Rahmens** (4-Eck-Kontur → Homographie); `workspace.method: auto` versucht ArUco und
  fällt auf den Rahmen zurück.
- Segmentierung relativ zur Platte (Median von Helligkeit/Sättigung), dadurch unabhängig von der
  Bauteilfarbe und robust gegen Lichtänderungen.
- Orientierung über die **abgeschrägte Ecke**: Die Ecke des minimalen Rechtecks mit dem größten
  Abstand zur Kontur ist die Fase → θ eindeutig in [0°, 360°).
- **Befund:** Die aktuellen 3D-gedruckten Marker werden nicht erkannt. Es fehlt der helle Rand
  (Quiet Zone), der schwarze Markerrand verschmilzt mit der dunklen Platte. → Marker mit weißem
  Rand drucken (`python -m m1_vision_topdown.make_markers`).
- Tests: 8 synthetische Szenen (ArUco und Rahmen, perspektivisch verzerrt) mit Fehler < 2 mm / 2°,
  4 echte Fotos als Regressionstest.

## Aufgaben

- [ ] Kamera auswählen/anbinden, feste Belichtung einstellen
- [ ] Intrinsische Kalibrierung durchführen, Ergebnis in `config/` speichern
- [ ] Marker mit weißem Rand versehen/neu drucken, Rahmen und Markerpositionen vermessen (`workspace.size_mm`, `markers_mm`)
- [x] ArUco-Detektion + Homographie implementieren
- [x] Alternative: Arbeitsbereich über den weißen Rahmen
- [x] Segmentierung + Pose (inkl. Fasenerkennung für 360°) implementieren
- [ ] Kalibrierung Arbeitsbereich → Roboter (gemeinsam mit M2)
- [ ] Parallaxe durch die Bauteilhöhe bewerten und ggf. korrigieren
- [ ] Genauigkeitsmessung: N Ablagen an bekannten Positionen, Fehlerstatistik
- [x] Unit-Tests mit synthetischen Bildern und Beispielfotos (`tests/data/`)

## Testen

- GUI: Tab **M1 Erkennung** – Testbilder, Kamera oder Datei; Overlay im Kamerabild + entzerrtes Bild
- `python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"` – Debug-Bilder in `logs/m1`
- `pytest m1_vision_topdown` – synthetische Szenen mit bekannter Pose + echte Fotos

## Nächste Schritte

1. Rahmen und Marker ausmessen → `workspace.size_mm`, `markers_mm` (danach Regressionswerte in `tests/test_topdown.py` anpassen)
2. Top-down-Kamera fest montieren, im Tab M1 mit „Live“ prüfen
3. Marker mit weißem Rand versehen, dann `workspace.method: aruco` testen
4. Kalibrierung Arbeitsbereich → Roboter mit Person 2 (siehe `ANLEITUNG.md`, Abschnitt 7)
