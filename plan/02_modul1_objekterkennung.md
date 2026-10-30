# 02 – Modul 1: Objekterkennung (Kamera oben)

**Verantwortlich:** Person 1 · **Code:** `code/m1_vision_topdown/` · **Interface:** `ObjectDetector.detect() -> ObjectPose | None`
Aufgaben: [06_offen.md](06_offen.md)

## Aufgabe

- Arbeitsbereich im Bild finden (4 ArUco-Marker an den Ecken).
- Bauteil innerhalb des Arbeitsbereichs finden.
- Position (x, y) und Orientierung θ bestimmen und im **Roboter-Koordinatensystem** an den Orchestrator übergeben.

## Kamera

- **Daheng VEN-161** (1440×1080, Global Shutter, USB3 Vision), angebunden über
  `topdown_camera.source: daheng:<Seriennummer>` (`common/camera.py`, nutzt den Daheng-Code von M4).
  Dafür muss das Galaxy SDK installiert sein. `python -m common.camera` listet die Kameras.
- Belichtung und Gain über `exposure_us`/`gain_db`, `null` = Automatik.
- Die Kamera ist zugleich die Szenenkamera von M4. M1 gibt sie frei, wenn M4 sie braucht
  (`gui/robot_access.py`).
- Die Testfotos in `tests/data/` stammen von einer Handykamera.

## Arbeitsbereich und Marker

- 4 ArUco-Marker `DICT_4X4_50` auf Papier mit weißem Rand (Quiet Zone), erzeugt mit
  `python -m m1_vision_topdown.make_markers`. Das schwarze Quadrat misst 50 mm.
- Die Markermitten liegen 400 mm auseinander. Der Arbeitsbereich ist das Quadrat dazwischen,
  35 mm eingerückt, also **330 × 330 mm**, damit das Markerpapier nicht als Teil erkannt wird.
- **Arbeitsraum-KS:** Der Ursprung liegt in der Ecke unten links (35 mm innerhalb von Marker 0),
  x zeigt nach rechts, y nach oben (aus Kamerasicht). Marker 0–3: (−35, −35), (365, −35),
  (365, 365), (−35, 365) mm.
- `workspace.method: aruco`. Der Rückfall über einen weißen Rahmen (`white_frame`, `auto`) ist noch
  im Code, wird aber nicht genutzt, weil es keinen Rahmen mehr gibt.
- Die Umrechnung ins Roboter-KS (`workspace_to_robot`) wird über die Marker eingemessen
  (siehe [03_modul2](03_modul2_robotersteuerung.md#kalibrierung-gemeinsam-mit-m1)).

## Verarbeitungskette

1. Bild aufnehmen.
2. ArUco-Marker erkennen (`cv2.aruco.ArucoDetector`, IDs 0–3), Homographie aus den Markermitten,
   entzerrte Draufsicht mit 2 px/mm (`cv2.warpPerspective`).
3. Segmentierung relativ zur Platte: Pixel deutlich heller **oder** bunter (Lab-Chroma) als der
   Median der Platte. Dadurch ist sie unabhängig von der Bauteilfarbe und robust gegen Licht.
   Ein Rand von 5 mm wird ignoriert.
4. Größte Kontur mit plausibler Fläche auswählen (300–20 000 mm²).
5. Pose: Schwerpunkt über Bildmomente, Rechteck über `cv2.minAreaRect`. Die Ecke des Rechtecks mit
   dem größten Abstand zur Kontur ist die **Fase**, damit ist θ eindeutig in [0°, 360°).
   Wird die Fase nicht gefunden, ist die Konfidenz 0,5 und θ nur bis auf 180° eindeutig.
6. Umrechnung Arbeitsbereich-mm → Roboter-KS (`common/transforms.py`), Rückgabe `ObjectPose` mit
   Konfidenz und Debug-Bild.

Die Objektivverzerrung wird noch nicht korrigiert (`calibration_file` ungenutzt).

## Anforderungen (Zielwerte)

| Größe | Ziel |
|---|---|
| Positionsgenauigkeit | ≤ ±2 mm |
| Winkelgenauigkeit | ≤ ±2° |
| Laufzeit `detect()` | < 500 ms |
| Robustheit | funktioniert bei Raumlicht, leichten Schatten |

## Bekannte Befunde

- **Parallaxe:** Auf allen 5 Testfotos misst M1 das Bauteil zu groß, 64,5–69,1 × 43,3–46,4 mm
  statt 60 × 40 mm (+8 bis +15 %). Die Homographie gilt für die Tischebene, die 15 mm hohe Oberseite
  und die sichtbaren Seitenflächen erscheinen größer. Die Lage ist bei gleicher Position stabil
  (±0,4 mm), kann aber systematisch nach außen verschoben sein, je weiter das Teil von der Bildmitte
  entfernt liegt. Das prüft der Zeigetest. Abhilfe: Kamera möglichst hoch und mittig.
- **Marker-Zuordnung:** Stimmt die Zuordnung von ID zu Ecke nicht, wird das Bild ohne Fehler falsch
  entzerrt.

## Testen

- GUI: Tab **M1 Erkennung** mit Testbildern, Kamera oder Datei; Overlay im Kamerabild und entzerrtes Bild.
- `python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"` schreibt Debug-Bilder nach
  `logs/m1`. Mit `--save-steps` kommen die 13 Zwischenbilder dazu.
- `pytest m1_vision_topdown` prüft synthetische Szenen mit bekannter Pose (Fehler < 2 mm / 2°)
  und echte Fotos als Regressionstest.
