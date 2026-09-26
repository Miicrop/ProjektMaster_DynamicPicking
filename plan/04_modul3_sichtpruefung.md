# 04 – Modul 3: Sichtprüfung (Seitenkamera)

**Verantwortlich:** Person 3 · **Code:** `code/m3_inspection/` · **Interface:** `Inspector.inspect() -> InspectionResult`

## Aufgabe

Die Seitenkamera betrachtet das an der Prüfposition abgelegte Bauteil und prüft:

1. **Seriennummer** auslesen (OCR).
2. **Lochdurchmesser** vermessen und mit Soll ± Toleranz vergleichen.
3. **Kerbe** vorhanden?

**Gutteil** ⇔ Seriennummer lesbar und gültig **und** Durchmesser in Toleranz **und** Kerbe vorhanden. Sonst Schlechtteil; die Gründe werden in `InspectionResult.reasons` aufgeführt.

## Aufbau

- Kamera seitlich, fester Abstand und Winkel zur Prüfposition, möglichst senkrecht auf die Prüffläche (vermeidet perspektivische Verzerrung beim Messen).
- Eigene, diffuse Beleuchtung (Ringlicht/Flächenlicht); für die Lochvermessung ggf. Durchlicht.
- Mechanischer Anschlag an der Prüfposition → reproduzierbare Lage, feste ROIs möglich.

## Verarbeitung (Konzept – Umsetzung siehe unten)

### Seriennummer (OCR)
- ROI um das Seriennummernfeld (fest oder über Merkmal lokalisiert).
- Vorverarbeitung: Graustufen, Kontrast (CLAHE), Binarisierung, ggf. Deskew.
- OCR mit **EasyOCR** (gewählt, da ohne separate Installation lauffähig; Tesseract wäre die Alternative), Whitelist der erlaubten Zeichen.
- Validierung per Regex gegen das Seriennummernformat (Config).

### Lochdurchmesser
- ROI um das Loch, Kantenfilter, Kreisdetektion mit `cv2.HoughCircles` oder Kontur + `cv2.fitEllipse`/Kreis-Fit (Least Squares, subpixelgenau).
- Umrechnung px → mm: umgesetzt über die bekannte Bauteilhöhe als Maßstab (statt Kalibrierplatte).
- Vergleich mit `hole_nominal_mm ± hole_tolerance_mm`.

### Kerbe
- ROI an der erwarteten Kerbenposition.
- Variante A: Template-Matching gegen Referenzbild (Score > Schwelle).
- Variante B: Konturanalyse (Konvexitätsdefekte an der Außenkontur).

## Anforderungen (vorläufig)

| Größe | Ziel |
|---|---|
| OCR-Erkennungsrate | ≥ 95 % bei gutem Druck |
| Messunsicherheit Loch | ≤ ±0,1 mm (abhängig von Auflösung) |
| Kerbe | keine Fehlklassifikation im Testset |
| Laufzeit | < 2 s |

## Umsetzung (Stand 2026-09-26)

- Bauteil über Farbe (HSV) finden, alle ROIs **relativ zur Bauteil-Box** → unabhängig vom Abstand.
- **Maßstab über die Bauteilhöhe** (`part_height_mm`) statt fester mm/px-Kalibrierung.
- Loch: Region „nicht helle Stirnfläche“ (dunkle Bohrungswand und durchscheinender Hintergrund),
  rundeste Region, Ellipsen-Fit. Testbilder: D/H = 0,647 / 0,663 / 0,649 (Streuung ±1,2 %).
- Kerbe (= kleine eckige Öffnung, bestätigt): rechteckigste Region über Helligkeit, Sättigung
  **oder** Kanten, weil die Öffnung je nach Licht dunkler, farbiger oder nur an den Kanten sichtbar ist.
- OCR: EasyOCR mit Ziffern-Allowlist + Regex `^[0-9]{5}$` → „69420“ auf allen drei Testbildern.
- Tests: 3 echte Bilder = Gutteil; künstliche Fehler (Kerbe bzw. Loch übermalt) → Schlechtteil.

## Aufgaben

- [ ] Kamera + Beleuchtung aufbauen, Prüfposition mit Anschlag festlegen
- [ ] Referenzbilder von Gut- und **echten** Schlechtteilen aufnehmen (Testset)
- [ ] Bauteilmaße aus Zeichnung: `part_height_mm`, `hole_nominal_mm`, Toleranz
- [x] Klären, was genau die „Kerbe“ ist → eckige Öffnung
- [x] OCR-Pipeline + Regex-Validierung
- [x] Lochvermessung
- [x] Kerbenerkennung
- [x] Gut/Schlecht-Logik
- [x] Protokollierung (CSV je Zyklus, Debug-Bilder optional)
- [x] GUI-Tab **M3 Prüfung** mit eingezeichneten ROIs zum Einstellen
- [ ] Messwiederholbarkeit am festen Aufbau (Thesis)
- [ ] Auswertung: Konfusionsmatrix (Thesis)
