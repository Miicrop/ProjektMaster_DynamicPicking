# M1 – Objekterkennung (Top-down-Kamera)

Planung: [plan/02_modul1_objekterkennung.md](../../plan/02_modul1_objekterkennung.md)

| Datei | Inhalt |
|---|---|
| `workspace.py` | Arbeitsbereich finden: ArUco-Marker **oder** Innenkante des weißen Rahmens → Homographie → entzerrtes Bild |
| `part.py` | Bauteil segmentieren (heller/farbiger als die Platte), Schwerpunkt, Orientierung über die **abgeschrägte Ecke** (0–360°) |
| `detector.py` | `TopDownPipeline` (Bild → Pose, ohne Kamera testbar), `TopDownDetector` (mit Kamera), `MockDetector` |
| `run.py` | Pipeline auf Bilddateien/Kamera ausführen und Debug-Bilder speichern |
| `make_markers.py` | Druckbare ArUco-Marker **mit weißem Rand** erzeugen |
| `tests/data/` | 4 Fotos vom Aufbau (31.07.2026, Handykamera, noch nicht final) |

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

- **ArUco-Marker werden auf den Fotos nicht erkannt.** Die 3D-gedruckten Marker (schwarzer Block,
  weiße Bits) haben keinen hellen Rand. Der schwarze Markerrand ist fast so hell wie die
  dunkelgraue Platte (Grauwert ~71 zu ~72–85), deshalb findet OpenCV die Markerkontur nicht.
  Erkannt wurde lediglich vereinzelt ID 2 aus `DICT_4X4_50`.
  → Lösung: Marker mit weißem Rand (≥ 1 Bit breit) versehen, z. B. mit `make_markers.py` drucken.
  Bis dahin nutzt `workspace.method: auto` automatisch den weißen Rahmen.
- Maße (`workspace.size_mm`, `markers_mm`) sind Platzhalter → Rahmen ausmessen.
- Perspektive: Die Homographie gilt für die Tischebene. Die Oberseite des Bauteils liegt höher und
  erscheint leicht verschoben (Parallaxe). Die Kamera sollte deshalb möglichst senkrecht und hoch
  hängen.
