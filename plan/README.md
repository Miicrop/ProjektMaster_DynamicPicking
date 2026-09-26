# Projektplanung – Dynamisches Greifen mit Sichtprüfung

Dieser Ordner beschreibt das Projekt: **was** es ist, **was** zu tun ist, **was** geplant ist und **was** erledigt ist.
Die Dateien sind die gemeinsame Grundlage für Code (`../code`) und Ausarbeitung (`../thesis`).

**Wie man das Projekt benutzt** (Installation, GUI, eigenes Modul testen, echter Aufbau):
[../ANLEITUNG.md](../ANLEITUNG.md) · **Aktueller Stand:** [06_roadmap.md → Zwischenstand](06_roadmap.md#zwischenstand-2026-09-26)

## Dateien

| Datei | Inhalt |
|---|---|
| [00_projektuebersicht.md](00_projektuebersicht.md) | Aufgabe, Ziel, Ablauf, Hardware, Rollen |
| [01_architektur.md](01_architektur.md) | Systemarchitektur, Zustandsautomat, Schnittstellen, Koordinatensysteme |
| [02_modul1_objekterkennung.md](02_modul1_objekterkennung.md) | M1 – Top-down-Kamera: Arbeitsbereich & Objektpose |
| [03_modul2_robotersteuerung.md](03_modul2_robotersteuerung.md) | M2 – Neura-Roboter: Greifen, Ablegen, Sortieren |
| [04_modul3_sichtpruefung.md](04_modul3_sichtpruefung.md) | M3 – Seitliche Sichtprüfung: Seriennummer, Loch, Kerbe |
| [05_modul4_ki_greifen.md](05_modul4_ki_greifen.md) | M4 – KI-basiertes Greifen (alternativer Ansatz) |
| [06_roadmap.md](06_roadmap.md) | Meilensteine und Aufgabenlisten mit Status |
| [07_erledigt.md](07_erledigt.md) | Log erledigter Arbeiten (datiert) |
| [08_offene_fragen.md](08_offene_fragen.md) | Offene Fragen und Entscheidungen |

## Konventionen

**Status in Aufgabenlisten**

- `[ ]` offen
- `[~]` in Arbeit
- `[x]` erledigt
- `[-]` verworfen (mit kurzer Begründung)

**Pflege**

- Jede Person pflegt die Datei ihres Moduls selbst.
- Wird eine Aufgabe erledigt: in `06_roadmap.md` abhaken **und** einen datierten Eintrag in `07_erledigt.md` ergänzen.
- Neue Unklarheiten kommen in `08_offene_fragen.md`; getroffene Entscheidungen werden dort mit Datum und Begründung festgehalten.
- Schnittstellenänderungen (`code/common/interfaces.py`) werden **vorher** in `01_architektur.md` abgestimmt, da sie alle Module betreffen.

**Sprache**

- Planung und Thesis: Deutsch
- Code, Kommentare, Commit-Nachrichten: Englisch
