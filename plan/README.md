# Projektplanung – Dynamisches Greifen mit Sichtprüfung

Dieser Ordner beschreibt das Projekt: **was** es ist, **was** zu tun ist, **was** geplant ist und **was** erledigt ist.
Die Dateien sind die gemeinsame Grundlage für Code (`../code`) und Ausarbeitung (`../thesis`).

**Wie man das Projekt benutzt** (Installation, GUI, eigenes Modul testen, echter Aufbau):
[../ANLEITUNG.md](../ANLEITUNG.md) · **Aktueller Stand und alle Aufgaben:** [06_offen.md](06_offen.md)

## Dateien

| Datei | Inhalt |
|---|---|
| [00_projektuebersicht.md](00_projektuebersicht.md) | Aufgabe, Ziel, Ablauf, Hardware, Rollen |
| [01_architektur.md](01_architektur.md) | Systemarchitektur, Zustandsautomat, Schnittstellen, Koordinatensysteme |
| [02_modul1_objekterkennung.md](02_modul1_objekterkennung.md) | M1 – Top-down-Kamera: Arbeitsbereich & Objektpose |
| [03_modul2_robotersteuerung.md](03_modul2_robotersteuerung.md) | M2 – Neura-Roboter: Greifen, Ablegen, Sortieren |
| [04_modul3_sichtpruefung.md](04_modul3_sichtpruefung.md) | M3 – Seitliche Sichtprüfung: Seriennummer, Loch, Kerbe |
| [05_modul4_ki_greifen.md](05_modul4_ki_greifen.md) | M4 – Behavior Cloning (Person 4) |
| [06_offen.md](06_offen.md) | **Alle** offenen Aufgaben und Fragen: Stand, Labor, M4, Evaluation, Thesis, Präsentation |
| [07_erledigt.md](07_erledigt.md) | Log erledigter Arbeiten, geklärte Fragen, Entscheidungen |
| [10_praesentation_konzept.md](10_praesentation_konzept.md) | Abschlusspräsentation: Konzept, Gestaltung, Storyboard |

## Konventionen

**Status in Aufgabenlisten**

- `[ ]` offen
- `[~]` in Arbeit
- `[x]` erledigt
- `[-]` verworfen (mit kurzer Begründung)

**Pflege**

- **Aufgaben und offene Fragen stehen nur in `06_offen.md`**, nicht in den Moduldateien.
- Erledigt: in `06_offen.md` löschen und einen datierten Eintrag in `07_erledigt.md` ergänzen.
  Entscheidungen kommen mit Datum und Begründung in die Tabelle in `07_erledigt.md`.
- Die Moduldateien (02–05) beschreiben nur, was man für das Modul wissen muss. Jede Person pflegt ihre selbst.
- Schnittstellenänderungen (`code/common/interfaces.py`) werden **vorher** in `01_architektur.md` abgestimmt, da sie alle Module betreffen.

**Sprache**

- Planung und Thesis: Deutsch
- Code, Kommentare, Commit-Nachrichten: Englisch
