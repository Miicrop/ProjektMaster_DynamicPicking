# 05 – Modul 4: Behavior Cloning (Person 4)

**Verantwortlich:** Person 4 · **Code:** `code/m4_behavior_cloning/` · **Bedienung:** GUI-Reiter „M4 Behavior Cloning“

> **Stand 2026-10-28:** Die Pipeline von Person 4 ist per `git subtree` aus `joshi99999/Dynamic_Robot_Project` (Ordner `Behavior Cloning/`) übernommen und als M4 in die GUI eingebaut. Der frühere Platzhalter `m4_ai_grasping` (`AiGrasper`, `--grasper ai`) ist entfernt. Thesis (Kap. 4 und 9) und Präsentation (6.1) beschreiben noch den alten Stand → [08](08_offene_fragen.md).

## Was M4 ist

Lokale Imitation-Learning-Pipeline für den Neura LARA 5:

- automatisierte Datenaufnahme mit Action Noise Injection (Wegpunkte teachen, Episoden aufzeichnen),
- Training einer Diffusion Policy (LeRobot 0.6.1, torch cu128),
- Live-Inferenz mit 15 Hz.

Hardware wird nur über Ports und Adapter angebunden (`bc/ports.py`, `bc/adapters/`). Die Logik läuft deshalb auch gegen Simulation und Neura-VM. Details stehen in seiner Doku, die maßgeblich ist:

- `code/m4_behavior_cloning/README.md`: Architektur, feste Werte
- `code/m4_behavior_cloning/INTEGRATION.md`: Einbau, Umgebung, Start
- `code/m4_behavior_cloning/Requierments/requierments.md`: Anforderungen und Entscheidungen
- `code/m4_behavior_cloning/Dokumentation/`: Kameras, Labortage, Zittern, Training

## Einbindung

- Ein Reiter in der Gruppen-GUI (`code/gui/tab_m4.py`), aufgebaut wie sein eigenes Fenster. Sein Code bleibt unverändert.
- Zwei Python-Umgebungen. Die GUI läuft in der Gruppen-venv (Python 3.11). Alles mit torch und lerobot läuft als Unterprozess mit `code/m4_behavior_cloning/.venv` (Python 3.12) über `BC_PYTHON`.
- `neurapy` kommt aus `code/m2_robot_control/vendor` (`BC_NEURAPY_DIR`).
- Im automatischen Ablauf (Greifen = „M4 Behavior Cloning“, `--grasper bc`) greift die Policy: `orchestrator/m4_grasper.py` startet `apps/infer.py` für eine Fahrt. Sie endet am Übergabepunkt PRE_PLACE [512.8, 196.8, 135.7] mm, rz −156°, das Teil ist dann im Greifer, ~9 cm über der Prüfposition [520.8, 199.6, 42.0]. M2 macht `reset()` (Tool, Override, init_program), legt ab, danach M3 und M2 wie gehabt. Die M1-Pose wird nur protokolliert; die Policy sucht das Teil selbst im Bild.
- Roboter und Draufsichtkamera (= Szenenkamera von M4) werden automatisch zwischen M2/M1 und M4 umgeschaltet (`gui/robot_access.py`); läuft auf der anderen Seite etwas, gibt es eine Meldung statt der Umschaltung.
- Einrichten der Umgebung: `code/setup_m4.bat`.
- Offen (Rücksprache Person 4, VM-Test): siehe [08](08_offene_fragen.md).

## Änderungen von Person 4 nachziehen

```bash
# im Klon von Dynamic_Robot_Project
git subtree split --prefix="Behavior Cloning" -b bc-export
# hier
git subtree pull --prefix=code/m4_behavior_cloning ../Dynamic_Robot_Project bc-export
```
