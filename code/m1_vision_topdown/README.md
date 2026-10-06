# M1 – Objekterkennung (Top-down-Kamera)

Planung: [plan/02_modul1_objekterkennung.md](../../plan/02_modul1_objekterkennung.md)

| Datei | Inhalt |
|---|---|
| `workspace.py` | Arbeitsbereich finden: ArUco-Marker **oder** Innenkante des weißen Rahmens → Homographie → entzerrtes Bild |
| `part.py` | Bauteil segmentieren (heller/farbiger als die Platte), Schwerpunkt, Orientierung über die **abgeschrägte Ecke** (0–360°) |
| `detector.py` | `TopDownPipeline` (Bild → Pose, ohne Kamera testbar), `TopDownDetector` (mit Kamera), `MockDetector` |
| `run.py` | Pipeline auf Bilddateien/Kamera ausführen und Debug-Bilder speichern |
| `make_markers.py` | Druckbare ArUco-Marker **mit weißem Rand** erzeugen |

Zwischenschritte für die Doku: `TopDownPipeline.process(img, trace)` sammelt mit einem
`common.trace.Trace` alle Zwischenbilder (Originalbild, ArUco/Weiß-Maske, entzerrtes Bild,
Bauteilmaske vor/nach Morphologie, Kandidaten, Pose). Im Ablauf über *+ Zwischenschritte*
bzw. `--save-steps`.
| `tests/data/` | 5 Fotos vom Aufbau mit aufgeklebten ArUco-Markern (05.10.2026, Handykamera, mehrere Höhen; Bilder 1–3 = gleiche Szene) |

```powershell
python -m m1_vision_topdown.run "m1_vision_topdown/tests/data/*.jpg"   # Debug-Bilder in logs/m1
python -m m1_vision_topdown.run --method aruco "m1_vision_topdown/tests/data/*.jpg"
pytest m1_vision_topdown
```

## Koordinaten

Arbeitsbereich-KS: Ursprung = innere **linke untere** Ecke des weißen Rahmens (Kamerasicht),
x nach rechts, y nach oben, mm. θ = Richtung der Bauteil-Längsachse zum **abgeschrägten Ende**,
gegen den Uhrzeigersinn ab der x-Achse. Ohne erkannte Fase: θ nur in [0°, 180°), Konfidenz 0,5.

## Stand / bekannte Probleme

- **Farbsegmentierung über Lab-Chroma statt HSV-Sättigung.** Auf der dunklen Platte gibt es
  bläuliche Spiegelungen (Fotos 05.10.: unten links). HSV-S = (max−min)/max bläht so einen
  schwachen Farbstich bei dunklen Pixeln auf S ≈ 55 auf – fast wie das Bauteil (S ≈ 85). Der
  Reflex wurde dann als Bauteil gewählt oder verschmolz mit ihm. Lab-Chroma: Platte ≈ 2,
  Reflex ≈ 10, Bauteil 40–50 → `part_topdown.chroma_delta: 20`.
- Perspektive: Die Homographie gilt für die Tischebene. Die Oberseite des Bauteils liegt höher und
  erscheint leicht verschoben (Parallaxe), außerdem sind je nach Lage Seitenflächen sichtbar und
  werden mitsegmentiert. Auf den Fotos vom 05.10. schwankt die gemessene Größe dadurch zwischen
  64–69 × 43–46 mm, die Position derselben Szene aus drei Höhen nur um < 1 mm. Die Kamera sollte
  möglichst senkrecht über der Mitte und hoch hängen.
