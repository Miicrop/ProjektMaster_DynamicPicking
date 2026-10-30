# 04 – Modul 3: Sichtprüfung (Seitenkamera)

**Verantwortlich:** Person 3 · **Code:** `code/m3_inspection/` · **Interface:** `Inspector.inspect() -> InspectionResult`
Aufgaben: [06_offen.md](06_offen.md)

## Aufgabe

Die Seitenkamera betrachtet das an der Prüfposition abgelegte Bauteil und prüft:

1. **Seriennummer** auslesen (OCR, 5 Ziffern).
2. **Lochdurchmesser** vermessen und mit Soll ± Toleranz vergleichen (10 mm ±0,4 mm).
3. **Kerbe** vorhanden? Die Kerbe ist die kleine eckige Öffnung in der Seitenansicht.

**Gutteil** ⇔ Seriennummer lesbar und gültig **und** Durchmesser in Toleranz **und** Kerbe
vorhanden. Sonst ist es ein Schlechtteil, und die Gründe stehen in `InspectionResult.reasons`.

## Aufbau

- **Prüfvorrichtung:** gedruckte, erhöhte Ablage (Fläche 38 mm über der Platte) mit Kamerahalter
  für einen festen Abstand und einem Hintergrund, vor dem das Loch gut zu erkennen ist. Es gibt keinen
  Formschluss, die Lage des Teils hängt also von der Ablagegenauigkeit des Roboters ab.
- Kamera: einfache USB-Kamera (`inspection_camera.source` = Index). Die Testbilder haben 3840×2160 Pixel.
- Die Kamera sollte möglichst senkrecht auf die Prüffläche schauen, sonst entsteht perspektivische
  Verzerrung beim Messen. Licht möglichst diffus.
- Der Greifer wartet über der Vorrichtung außerhalb des Bilds.

## Verarbeitung

- Bauteil über die Farbe (HSV) finden. Alle ROIs liegen **relativ zur Bauteil-Box** und sind damit
  unabhängig vom Abstand.
- **Maßstab über die Bauteilhöhe** (`part_height_mm` = 15) statt einer festen mm/px-Kalibrierung.
- **Seriennummer:** ROI um das Etikett, Vorverarbeitung (Graustufen, Kontrast), **EasyOCR** mit
  Ziffern-Allowlist, Prüfung per Regex `^[0-9]{5}$`. EasyOCR läuft ohne separate Installation,
  Tesseract wäre die Alternative.
- **Loch:** Region „nicht helle Stirnfläche“, also dunkle Bohrungswand und durchscheinender
  Hintergrund. Davon wird die rundeste Region per Ellipse angepasst. Testbilder:
  D/H = 0,647 / 0,663 / 0,649 (Streuung ±1,2 %).
- **Kerbe:** rechteckigste Region über Helligkeit, Sättigung **oder** Kanten, weil die Öffnung je
  nach Licht dunkler, farbiger oder nur an den Kanten sichtbar ist.
- Liegt das Teil um 180° verdreht (Fase in M1 nicht erkannt), zeigt das Etikett von der Kamera weg.

## Anforderungen (Zielwerte)

| Größe | Ziel |
|---|---|
| OCR-Erkennungsrate | ≥ 95 % bei gutem Druck |
| Messunsicherheit Loch | ≤ ±0,1 mm (abhängig von der Auflösung) |
| Kerbe | keine Fehlklassifikation im Testset |
| Laufzeit | < 2 s |

## Testen

- GUI: Tab **M3 Prüfung** mit eingezeichneten ROIs zum Einstellen.
- `python -m m3_inspection` mit Testbildern. Mit `--save-steps` kommen die 14 Zwischenbilder dazu.
- `pytest m3_inspection` prüft, dass echte Bilder Gutteile ergeben und künstliche Fehler (Kerbe oder
  Loch übermalt) Schlechtteile. „69420“ wird auf allen Testbildern richtig gelesen.
