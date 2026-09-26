# M4 – KI-basiertes Greifen

Planung: [plan/05_modul4_ki_greifen.md](../../plan/05_modul4_ki_greifen.md)

Eigenständiger Workspace von Person 4. Einzige Vorgabe: `AiGraspDetector` implementiert
`common.interfaces.ObjectDetector` und liefert eine `ObjectPose` im Roboter-KS.
Aktivieren im Gesamtsystem: `implementations.detector: ai` in `config/system.yaml`.

Eigene Abhängigkeiten (z. B. PyTorch) bitte in einer eigenen `requirements.txt` in diesem Ordner pflegen.
