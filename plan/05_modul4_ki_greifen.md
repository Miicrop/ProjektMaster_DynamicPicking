# 05 – Modul 4: KI-basiertes Greifen (alternativer Ansatz)

**Verantwortlich:** Person 4 · **Code:** `code/m4_ai_grasping/` · **Interface:** `ObjectDetector.detect() -> ObjectPose | None`

> Dieses Modul wird von Person 4 eigenständig konzipiert und implementiert. Diese Datei gibt nur den Rahmen vor; Inhalte bitte selbst ergänzen.

## Rahmen

- Ziel: Die Greifpose wird über einen lernbasierten Ansatz bestimmt statt über klassische Bildverarbeitung (M1).
- **Gleiche Schnittstelle wie M1:** Die Klasse `AiGraspDetector` (`code/m4_ai_grasping/ai_detector.py`) implementiert `ObjectDetector` und liefert eine `ObjectPose` im Roboter-KS. Damit ist M4 gegen M1 austauschbar: GUI-Tab *Ablauf* → Erkennung „KI (M4)“ bzw. `python -m orchestrator --detector ai`.
- Kamerabilder: `common.camera.open_camera(cfg["topdown_camera"])` bzw. die Testfotos unter `code/m1_vision_topdown/tests/data/`.
- Die Transformationen aus `common/transforms.py` (Arbeitsbereich → Roboter) können mitgenutzt werden.
- Vergleich M1 vs. M4 (Genauigkeit, Erfolgsquote, Laufzeit) ist ein möglicher Beitrag zum Evaluationskapitel der Thesis.

## Ideen (zur Orientierung, nicht verbindlich)

- Objektdetektion mit orientierten Bounding Boxes (z. B. YOLO-OBB)
- Greifposen-Netz (z. B. GG-CNN-artige Grasp-Maps)
- Instanzsegmentierung + Hauptachse

## Konzept

_(von Person 4 zu ergänzen)_

## Aufgaben

_(von Person 4 zu ergänzen)_
