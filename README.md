# Dynamisches Greifen mit Sichtprüfung

Studienprojekt (4 Personen): Ein Neura-Roboter greift ein kamerabasiert lokalisiertes Bauteil,
führt es einer automatischen Sichtprüfung zu und sortiert es in Gut- und Schlechtteile.

**➜ Einstieg: [ANLEITUNG.md](ANLEITUNG.md)** (Einrichten, GUI, eigenes Modul testen, echter Aufbau) ·
**Stand:** [plan/06_roadmap.md](plan/06_roadmap.md#zwischenstand-2026-09-26)

| Ordner | Inhalt |
|---|---|
| [plan/](plan/README.md) | Projektbeschreibung, Architektur, Module, Roadmap, Erledigtes, offene Fragen |
| [code/](code/README.md) | Python-Code: Orchestrator, gemeinsame Schnittstellen, Modul-Workspaces M1–M4 |
| [thesis/](thesis/README.md) | Ausarbeitung in LaTeX (IEEE-Zitierstil) |
| [docs/neura/](docs/neura/README.md) | Neura-Dokumentation (NeuraPy, Offline-Simulation, Schnittstellen) |
| [docs/greifer/](docs/greifer/) | Zimmer-Greifer LWR50L-23-00004-A, Robotermodul LWR50F-13-05-A, Kamerahalterung (Datenblätter, CAD) |
| [resources/](resources/README.md) | Rohdaten: Neura-Steuerungssoftware, Roboter-Backup (nicht versioniert) |

Schnellstart:

```bash
cd code
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m gui                    # oder Doppelklick auf code/start_gui.bat
```

Roboter vom Laptop steuern: [code/m2_robot_control/ANLEITUNG_NEURA.md](code/m2_robot_control/ANLEITUNG_NEURA.md)
