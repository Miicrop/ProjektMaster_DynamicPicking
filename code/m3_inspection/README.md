# M3 – Sichtprüfung (Seitenkamera)

Planung: [plan/04_modul3_sichtpruefung.md](../../plan/04_modul3_sichtpruefung.md)

| Datei | Inhalt |
|---|---|
| `features.py` | Bauteil finden (Farbe), ROIs relativ zum Bauteil, Loch (Kreisform), Kerbe (Rechteckform) |
| `ocr.py` | Seriennummer mit EasyOCR (Ziffern-Allowlist, Regex-Prüfung) |
| `inspector.py` | `evaluate()` (Gut/Schlecht), `InspectionPipeline` (Bild → Ergebnis), `CameraInspector`, `MockInspector` |
| `run.py` | Prüfung auf Bilddateien/Kamera ausführen, Debug-Bilder speichern |
| `tests/data/` | 3 Seitenansichten des Testteils (Seriennummer 69420), noch nicht final |

```powershell
python -m m3_inspection.run "m3_inspection/tests/data/*.jpg"      # Debug-Bilder in logs/m3
pytest m3_inspection
```

## Verfahren

- **Bauteil:** lila Pixel (HSV) → vertikal über die Bauteilhöhe geschlossen, damit Etikett und
  Löcher dazugehören → Bounding Box. Alle ROIs sind relativ zu dieser Box angegeben
  (`label_roi`, `hole_roi`, `notch_roi`).
- **Maßstab:** Die sichtbare Bauteilhöhe dient als Referenz (`part_height_mm`). Dadurch ist die
  Messung unabhängig vom Abstand zur Kamera.
- **Loch:** Alles, was keine helle Stirnfläche ist (dunkle Bohrungswand ebenso wie heller
  Hintergrund, der durch das Loch scheint) → rundeste Region → Ellipsen-Fit → Durchmesser.
  Auf den 3 Testbildern gilt D/H = 0,647 / 0,663 / 0,649.
- **Kerbe:** Rechteckige Region im Kerben-ROI, gefunden über Helligkeits- oder
  Sättigungsunterschied zur Umgebung oder über geschlossene Kanten.
- **Seriennummer:** EasyOCR auf dem Etikett-ROI, Prüfung gegen `serial_pattern` (`^[0-9]{5}$`).
- **Gut** ⇔ Seriennummer gültig ∧ Durchmesser in Toleranz ∧ Kerbe vorhanden.

## Annahmen / offen

- **„Kerbe“ = die kleine eckige Öffnung rechts** (bestätigt).
- `part_height_mm`, `hole_nominal_mm` und `hole_tolerance_mm` sind Platzhalter (Sollwert aus den
  Testbildern abgeleitet) → aus der Bauteilzeichnung übernehmen.
- Testbilder haben unterschiedliche Abstände und Hintergründe. Am finalen Aufbau mit fester
  Kamera und eigener Beleuchtung wird es robuster; dann ROIs und Schwellwerte nachjustieren.
