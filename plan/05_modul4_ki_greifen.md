# 05 – Modul 4: KI-basiertes Greifen (alternativer Ansatz)

**Verantwortlich:** Person 4 · **Code:** `code/m4_ai_grasping/` · **Interface:** `Grasper.pick(pose)`, `Grasper.place(target)`

> Dieses Modul wird von Person 4 eigenständig konzipiert und implementiert. Diese Datei gibt nur den Rahmen vor; Inhalte bitte selbst ergänzen.

> **Änderung 2026-10-21 (Stand Team):** M4 ersetzt **nicht M1**, sondern einen Teil von **M2**. Ablauf mit M4: M1 erkennt das Bauteil → M4 greift es automatisch (Handgelenkkamera) und legt es in der Sichtprüfung ab → M3 klassifiziert → M2 greift aus der Prüfung und sortiert. Code und Plan sind umgestellt; die Thesis (Kap. 4 und 9) beschreibt noch den alten Stand → `thesis/blueprint.md` §6a.

## Rahmen

- Ziel: Das Bauteil wird lernbasiert mit der Handgelenkkamera gegriffen und an der Prüfposition abgelegt. Ausgangspunkt ist die grobe Pose von M1.
- **Schnittstelle `Grasper`** (`common/interfaces.py`): `pick(pose: ObjectPose)` greift das Teil, `place(target: RobotTarget)` legt es an der Prüfposition ab. Beide Posen im **Roboter-Basis-KS**. Die Klasse `AiGrasper` (`code/m4_ai_grasping/ai_grasper.py`) bekommt den `RobotController` von M2 für Bewegungen und Greifer.
- Der Orchestrator ruft den Greifer nur in PICK und PLACE_INSPECT auf; PICK_INSPECT und SORT macht immer M2. Standard ist `RobotGrasper` (M2 direkt).
- Einschalten: GUI-Tab *Ablauf* → Greifen „KI (M4)“, `python -m orchestrator --grasper ai` oder `implementations.grasper: ai` in `config/system.yaml`.
- Kamera: `self.wrist_camera()` (Konfiguration `wrist_camera`). Offen: Hand-Auge-Kalibrierung, d. h. wie Bilder der Handgelenkkamera ins Roboter-Basis-KS kommen ([08](08_offene_fragen.md)).
- Vergleich M2 vs. M4 beim Greifen (Erfolgsquote, Lagefehler an der Prüfung, Zeit) ist ein möglicher Beitrag zum Evaluationskapitel der Thesis.

## Ideen (zur Orientierung, nicht verbindlich)

- Objektdetektion mit orientierten Bounding Boxes (z. B. YOLO-OBB)
- Greifposen-Netz (z. B. GG-CNN-artige Grasp-Maps)
- Instanzsegmentierung + Hauptachse

## Konzept

_(von Person 4 zu ergänzen)_

## Aufgaben

_(von Person 4 zu ergänzen)_
