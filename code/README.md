# Code – Dynamisches Greifen mit Sichtprüfung

Architektur und Schnittstellen: [plan/01_architektur.md](../plan/01_architektur.md)

## Struktur

| Ordner | Inhalt | Verantwortlich |
|---|---|---|
| `common/` | Schnittstellen (`interfaces.py`), Konfiguration, Kamerazugriff (`camera.py`), Koordinatentransformationen | alle |
| `orchestrator/` | Zustandsautomat, Factory (Modulauswahl), Logbuch (CSV), CLI | Integration |
| `gui/` | Grafische Oberfläche für Einzeltests und automatischen Ablauf | Integration |
| `config/system.yaml` | Alle Aufbau-/Hardwareparameter | alle |
| `m1_vision_topdown/` | Arbeitsbereich + Objektpose (Top-down-Kamera) | Person 1 |
| `m2_robot_control/` | Neura-Robotersteuerung | Person 2 |
| `m3_inspection/` | Seitliche Sichtprüfung | Person 3 |
| `m4_ai_grasping/` | KI-basiertes Greifen | Person 4 |

Jedes Modul enthält eine Mock-Implementierung, damit das Gesamtsystem ohne Hardware läuft.

## Setup

```bash
cd code
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

EasyOCR (M3) installiert PyTorch (~1 GB) und lädt beim ersten Aufruf ein Modell (~100 MB) aus dem Internet.

## GUI

`start_gui.bat` doppelklicken oder `python -m gui` (direkt in einen Tab: `python -m gui --tab m2`).

| Tab | Wofür |
|---|---|
| **Ablauf (automatisch)** | Erkennung, Roboter und Prüfung jeweils wählbar (Mock, Testbilder, Kamera, Simulator, echter Roboter). 1 Zyklus oder Dauerbetrieb. Zeigt den aktuellen Zustand, M1-/M3-Bilder mit Kurzinfo direkt nach dem jeweiligen Schritt (bei Fehler das Rohbild), eine Roboter-Draufsicht (Basis oben, x nach unten, y nach rechts) und eine Ergebnistabelle mit Gut/Schlecht-Zählern. Jeder Zyklus landet in `logs/cycles_<datum>.csv`, optional mit Bildern und Zwischenschritten. |
| **M1 Erkennung** | Bild holen (Testbilder/Kamera/Datei), Arbeitsbereich und Bauteil im Kamerabild und im entzerrten Bild, Pose in beiden Koordinatensystemen, Live-Modus |
| **M2 Roboter** | Simulator oder echter Roboter: verbinden, Status/TCP-Pose, Home, Greifer, Pick-Test, Posen teachen und anfahren, STOPP |
| **M3 Prüfung** | Bild holen/Datei, Ergebnis GUT/SCHLECHT, Seriennummer, Lochdurchmesser, Kerbe, Prüfbereiche (ROIs) eingezeichnet |
| **Einstellungen** | Alle Werte aus `system.yaml` bearbeiten (mit Kommentaren, Filter). Bildverarbeitung übernimmt Änderungen sofort, `Speichern`/Strg+S schreibt die Datei. |

Unten läuft das Log aller Module mit. Bewegungen mit dem echten Roboter fragen vorher nach.

## Kommandozeile – jedes Modul einzeln

Alle Befehle aus dem Ordner `code/`:

| Modul | Befehl | Was passiert |
|---|---|---|
| M1 | `python -m m1_vision_topdown "m1_vision_topdown/tests/data/*.jpg"` | Pose je Bild, Debug-Bilder in `logs/m1` (`--camera` für ein Live-Bild) |
| M2 | `python -m m2_robot_control info --sim` | Roboter-Check: `info`, `pose`, `home`, `gripper`, `pick-test` (ohne `--sim` = echter Roboter) |
| M3 | `python -m m3_inspection "m3_inspection/tests/data/*.jpg"` | Prüfergebnis je Bild, Debug-Bilder in `logs/m3` |
| alle | `python -m orchestrator --replay --sim-robot --cycles 4` | automatischer Ablauf, siehe unten |

## Kommandozeile – automatischer Ablauf

```bash
python -m orchestrator --mock --cycles 5                      # alles gemockt
python -m orchestrator --replay --cycles 4                    # M1 + M3 auf den Testfotos, Roboter gemockt
python -m orchestrator --replay --sim-robot --save-images     # + Neura-Code gegen Simulator, Bilder speichern
python -m orchestrator --replay --save-steps                  # + Zwischenbilder M1/M3 (Masken, ROIs) für die Doku
python -m orchestrator --detector camera --robot real --inspector camera --cycles 0   # echt, bis Strg+C
python -m orchestrator                                        # Auswahl laut config/system.yaml (implementations)
pytest                                                        # alle Tests (~25 s)
```

Kameras: `source` in `config/system.yaml` ist ein Geräteindex (`0`) oder ein Bildpfad/Glob (Wiedergabe von Dateien).
