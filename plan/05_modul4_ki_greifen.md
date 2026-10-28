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
- Nicht an den Zustandsautomaten angebunden: Der automatische Ablauf bleibt M1 → M2 → M3.
- M2 und M4 verbinden sich jeweils selbst mit der Steuerung, deshalb nie beide gleichzeitig verbinden.

## Änderungen von Person 4 nachziehen

```bash
# im Klon von Dynamic_Robot_Project
git subtree split --prefix="Behavior Cloning" -b bc-export
# hier
git subtree pull --prefix=code/m4_behavior_cloning ../Dynamic_Robot_Project bc-export
```
