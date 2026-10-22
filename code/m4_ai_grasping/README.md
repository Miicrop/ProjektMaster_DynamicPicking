# M4 – KI-basiertes Greifen

Planung: [plan/05_modul4_ki_greifen.md](../../plan/05_modul4_ki_greifen.md)

Eigenständiger Workspace von Person 4. **Rolle (Stand 2026-10-21):** M4 übernimmt PICK und
PLACE_INSPECT von M2. M1 erkennt weiter, M4 greift das Teil mit der Handgelenkkamera und legt es
in der Prüfung ab; nach M3 greift wieder M2 und sortiert.

Einzige Vorgabe: `AiGrasper` (`ai_grasper.py`) implementiert `common.interfaces.Grasper`
(`pick(pose)`, `place(target)`); Posen im Roboter-Basis-KS. Bewegungen und Greifer über den
übergebenen `RobotController` (M2).
Aktivieren: `implementations.grasper: ai` in `config/system.yaml`, `--grasper ai` oder GUI
*Ablauf* → Greifen „KI (M4)“.

Eigene Abhängigkeiten (z. B. PyTorch) bitte in einer eigenen `requirements.txt` in diesem Ordner pflegen.
