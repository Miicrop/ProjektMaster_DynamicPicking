# 06 – Roadmap

## Zwischenstand (2026-09-26)

**Läuft ohne Hardware** (mit Testfotos und Roboter-Simulator, 59 automatische Tests grün):

| Bereich | Stand |
|---|---|
| M1 Erkennung | Arbeitsbereich über weißen Rahmen (ArUco implementiert, aktuelle Marker aber nicht erkennbar), Bauteilpose inkl. Orientierung 0–360° – alle 4 Testfotos korrekt |
| M2 Roboter | `NeuraRobot` nach NeuraPy v5.0.8, Greif-/Ablegesequenz, Arbeitsraumgrenzen, Simulator, Inbetriebnahme-Werkzeug + Anleitung |
| M3 Prüfung | Seriennummer (OCR), Lochdurchmesser, Kerbe, Gut/Schlecht – alle 3 Testbilder korrekt, künstliche Fehler werden erkannt |
| M4 KI-Greifen | Platzhalter mit Schnittstelle, Umsetzung durch Person 4 |
| Ablauf | Zustandsautomat, automatischer Betrieb, CSV-Protokoll, Fehlerbehandlung |
| Bedienung | GUI mit Tabs pro Modul, Ablauf und Einstellungen; jedes Modul auch einzeln per Kommandozeile |

**Noch nicht am echten Aufbau erprobt:** Kameras, Roboterverbindung, Greifer, Posen, Kalibrierung.
Alle Maße in `config/system.yaml` sind Platzhalter.

**Nächste Schritte (in dieser Reihenfolge):**

1. Vor Ort messen: Rahmen-Innenmaß, Markerpositionen, Bauteilhöhe, Loch-Soll/Toleranz, Roboter-IP → in die Einstellungen
2. Team: Gerüst vorstellen, Schnittstellen und Aufteilung abstimmen (Anleitung: [../ANLEITUNG.md](../ANLEITUNG.md))
3. Roboter in Betrieb nehmen ([ANLEITUNG_NEURA.md](../code/m2_robot_control/ANLEITUNG_NEURA.md)), Posen teachen
4. Kameras montieren, M1/M3 live testen, ROIs/Schwellwerte nachstellen
5. Kalibrierung Arbeitsbereich → Roboter, dann erster echter Zyklus mit 20 % Geschwindigkeit
6. Git-Repo (privat) für die Zusammenarbeit einrichten

## Meilensteine

| # | Meilenstein | Inhalt | Status |
|---|---|---|---|
| MS1 | Projektsetup | Planung, Ordnerstruktur, Schnittstellen, Mocks, Thesis-Gerüst | `[~]` |
| MS2 | Module einzeln lauffähig | Jedes Modul funktioniert mit echter Hardware isoliert | `[ ]` |
| MS3 | Kalibrierung | Kamera intrinsisch, Arbeitsbereich → Roboter, mm/px Prüfkamera | `[ ]` |
| MS4 | Integration | Kompletter Zyklus mit echter Hardware | `[ ]` |
| MS5 | Evaluation | Messreihen: Greiferfolg, Pose-Genauigkeit, Prüfgenauigkeit | `[ ]` |
| MS6 | Abgabe | Thesis fertig, Code aufgeräumt, Demo | `[ ]` |

## MS1 – Projektsetup

- [x] Planungsdokumente unter `plan/`
- [x] Code-Gerüst: `common/`, `orchestrator/`, Modul-Workspaces mit Interface + Mock
- [x] Thesis-Gerüst (LaTeX, biblatex IEEE)
- [x] Anleitung zur Verwendung für das Team ([../ANLEITUNG.md](../ANLEITUNG.md))
- [ ] Gerüst mit dem Team abstimmen (Schnittstellen, Aufteilung)
- [x] Neura-Doku einarbeiten (NeuraPy v5.0.8) → `NeuraRobot`, Simulator, Anleitung
- [ ] GitHub-Repo mit bisherigen Robotertests einarbeiten
- [x] Beispielbilder einsortieren und erste Implementierung M1 + M3 darauf
- [ ] Offene Hardwarefragen klären ([08_offene_fragen.md](08_offene_fragen.md))
- [ ] Versionsverwaltung einrichten (Git-Repo, gemeinsamer Zugriff)

## Integration / Orchestrator

- [x] Zustandsautomat mit Mocks
- [x] Konfigurationsumschaltung mock/real pro Modul (`--replay`, `--sim-robot`)
- [x] Gesamtablauf ohne Hardware: echte Bildverarbeitung auf Testfotos + Neura-Code gegen Simulator
- [x] Zyklus-Logging: CSV je Tag + optional Debug-Bilder je Zyklus
- [x] Jedes Modul einzeln startbar (`python -m <modul>`), Gesamtablauf `python -m orchestrator`
- [x] GUI: Tabs für M1, M2, M3, automatischen Ablauf und Einstellungen (`python -m gui`)
- [ ] Fehlerbehandlung und Reset am realen System
- [ ] GUI am echten Aufbau erproben (Kameras, Roboter), Rückmeldungen des Teams einarbeiten

## Module

Die detaillierten Aufgaben stehen in den Moduldateien:

- M1: [02_modul1_objekterkennung.md](02_modul1_objekterkennung.md#aufgaben)
- M2: [03_modul2_robotersteuerung.md](03_modul2_robotersteuerung.md#aufgaben)
- M3: [04_modul3_sichtpruefung.md](04_modul3_sichtpruefung.md#aufgaben)
- M4: [05_modul4_ki_greifen.md](05_modul4_ki_greifen.md#aufgaben)

## Thesis

Plan, Stand und Vorgehen fürs Weiterschreiben: [../thesis/blueprint.md](../thesis/blueprint.md).
`[~]` = Entwurf steht, Durchsicht durch die verantwortliche Person offen.

- [x] Gliederung und Gesamtplan (Blueprint)
- [~] Kurzfassung (Ergebnissatz fehlt)
- [~] Einleitung
- [~] Grundlagen (Abschnitt lernbasiertes Greifen: Person 4)
- [~] Systemkonzept / Architektur (Kalibrierung offen)
- [~] Umsetzungskapitel M1, M2, M3 (Durchsicht durch Person 1–3, Zwischenfazits nach den Tests)
- [ ] Umsetzungskapitel M4 (Person 4)
- [~] Integration und Bedienung (Screenshots fehlen)
- [ ] Evaluation mit Messdaten (Gerüst steht)
- [ ] Fazit, Korrekturlesen, Abgabe (Gerüst steht)
