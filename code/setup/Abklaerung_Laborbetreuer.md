# Abklärung mit dem Laborbetreuer: Einrichtung der Workstation

**Zweck:** Vor der Installation der Projektsoftware (zuerst Modul M4 Behavior
Cloning) auf der neuen Workstation klären, was erlaubt ist, was schon da ist
und was im gemeinsamen Admin-Termin erledigt werden muss.

**Grundsatz der Einrichtung:** Alles, was ohne Admin-Rechte geht, landet in
einer abgekapselten Python-Umgebung (`venv`) in einem einzigen Ordner. Das
System selbst wird dabei nicht verändert. Was Admin-Rechte braucht,
installiert das Setup-Programm **nie selbst**: Es zeigt diese Punkte nur als
Checkliste an und prüft danach, ob sie erledigt sind.

Antworten bitte direkt hinter **Antwort:** eintragen.

---

## Stand nach dem Gespräch (10.11.2026)

Der Laborbetreuer hat das Setup-Programm (`setup_m4.bat`) gesehen und ist
grundsätzlich einverstanden.

| Thema | Antwort | Folge für die Einrichtung |
|---|---|---|
| Internet | vorhanden | Installation online über pip, kein Offline-Ordner nötig |
| Git | `git clone` erlaubt, Git **installieren** aber nicht | Repo als ZIP von GitHub laden (Code → Download ZIP), siehe unten |
| `.bat` ausführen | unklar, wird vor Ort probiert | Ausweichweg: `code\setup\m4_setup.py` direkt starten |
| Python | installiert, Version unbekannt | Setup prüft das; fehlt 3.12: „Install for me only“ (ohne Admin) |
| GPU | RTX 5090, Treiber meldet CUDA 13 | passt: Treiber ≥ 580 kann cu128, 5090 ist sm_120 wie die 5070 Ti |
| Daheng Galaxy SDK | fehlt | **Admin-Termin** |
| Laufwerk / Pfad | wird vor Ort festgelegt | Zielordner im Fenster wählen; außerhalb des Standards setzt das Setup `BC_PYTHON` |
| Nutzbar für | nur den eigenen Benutzer | passt: venv, `BC_PYTHON` und Python „for me only“ sind alle benutzerbezogen. Ausnahme: Galaxy SDK (Treiber, systemweit) |
| Roboter | wie gewohnt über Netzwerkkabel | **offen:** Netzwerkadapter braucht vermutlich eine feste IP im Robotersubnetz, das braucht Admin (Frage 5.1) |
| Kameras | USB 3 | keine Jumbo Frames nötig; Treiber kommt mit dem Galaxy SDK |

### Noch offen für den Admin-Termin

1. **Daheng Galaxy SDK** installieren (Treiber für die USB-Kameras).
2. **Feste IP** am Netzwerkadapter für den Roboter (Frage 5.1), falls
   nicht schon eingerichtet. Ggf. Firewall-Freigabe (5.2).
3. Nur falls die Prüfung im Setup es meldet: Visual C++ Redistributable.
4. Falls vor Ort kein Python 3.12 da ist und „Install for me only“ nicht
   erlaubt ist: Python 3.12 durch den Betreuer.

### Repo ohne Git auf die Workstation

`git clone` braucht ein installiertes Git und geht deshalb nicht. Möglich sind:

- **ZIP-Download** (empfohlen): auf GitHub *Code → Download ZIP* (privates Repo:
  vorher im Browser anmelden), entpacken, `code\setup_m4.bat` starten.
  Updates = neues ZIP. Daten, Checkpoints und die `.venv` dabei nicht
  überschreiben.
- **Portable Git** (MinGit, nur entpacken): nur falls der Betreuer das nicht
  als „Installation“ wertet. Vorher fragen.

---

## 1. Netzwerk und Internet

| # | Frage | Antwort |
|---|---|---|
| 1.1 | Hat die Workstation direkten Internetzugang? | |
| 1.2 | Falls über einen Proxy: Adresse, Port, braucht er eine Anmeldung? | |
| 1.3 | Sind diese Adressen erreichbar bzw. freigegeben? *(siehe Liste unten)* | |
| 1.4 | Falls kein Internet: Dürfen die Pakete vorher auf einem anderen Rechner heruntergeladen und per USB-Stick oder Netzlaufwerk übertragen werden (Offline-Installation)? Sind USB-Sticks erlaubt? | |
| 1.5 | Darf das GitHub-Repository direkt auf der Workstation geklont werden (`git clone`), oder muss es anders übertragen werden? | |

Benötigte Download-Quellen:

| Adresse | Wofür | Umfang |
|---|---|---|
| `pypi.org`, `files.pythonhosted.org` | Python-Pakete (pip) | ca. 1–1,5 GB |
| `download.pytorch.org` | PyTorch mit CUDA 12.8 und vortrainierte ResNet-Gewichte | ca. 2,5 GB |
| `github.com` | Projekt-Repository, ggf. FFmpeg-Build | klein / ca. 100 MB |
| `huggingface.co` | evtl. Modell- und Datensatz-Metadaten von LeRobot | klein |
| Daheng-Imaging-Webseite | Galaxy SDK (Kameratreiber), falls nicht vorhanden | ca. 300 MB |

## 2. Ausführen von Programmen und Skripten

| # | Frage | Antwort |
|---|---|---|
| 2.1 | Dürfen `.bat`-Dateien (cmd) ausgeführt werden? | |
| 2.2 | Dürfen PowerShell-Skripte ausgeführt werden? Welche Execution Policy ist gesetzt (`Get-ExecutionPolicy -List`)? | |
| 2.3 | Gibt es AppLocker, Smart App Control o. Ä., das Programme in Benutzerordnern blockiert? **Wichtig:** Eine `venv` legt eine Kopie von `python.exe` im Projektordner ab, und PyTorch bringt viele DLLs mit. | |
| 2.4 | Prüft ein Virenscanner jede neu geschriebene Datei? Wäre eine Ausnahme für den Umgebungsordner möglich (pip schreibt mehrere zehntausend Dateien, das kann sehr langsam werden)? | |

## 3. Was ist auf der Workstation schon installiert?

| # | Frage | Antwort |
|---|---|---|
| 3.1 | Ist Python installiert? Welche Version(en)? Ist der Python Launcher `py` dabei (`py --list`)? | |
| 3.2 | Wird **Python 3.12** benötigt (Vorgabe durch LeRobot 0.6.1)? Falls nicht vorhanden: Darf ich es selbst als „nur für mich“-Installation (ohne Admin) einrichten, oder installieren Sie es systemweit? | |
| 3.3 | Ist Git installiert? | |
| 3.4 | Welche Grafikkarte ist verbaut, welcher NVIDIA-Treiber (`nvidia-smi`)? Für PyTorch cu128 wird ein Treiber mit CUDA 12.8 oder neuer gebraucht (ab Treiber 570). | |
| 3.5 | Ist das Microsoft Visual C++ Redistributable 2015–2022 (x64) installiert? (PyTorch braucht es.) | |
| 3.6 | Ist das Daheng Galaxy SDK installiert? Welche Version? | |

## 4. Speicherort und Daten

| # | Frage | Antwort |
|---|---|---|
| 4.1 | Auf welchem Laufwerk/Pfad dürfen Projekt und Umgebung liegen (lokal, ohne OneDrive)? | |
| 4.2 | Platzbedarf: Umgebung ca. 8–10 GB, dazu Datensätze und Checkpoints (mehrere 10 GB möglich). Ist so viel Platz frei? | |
| 4.3 | Wird der Ordner gesichert (Backup), oder sollen Datensätze/Checkpoints anderswo abgelegt werden? | |
| 4.4 | Arbeiten weitere Personen/Benutzerkonten an der Workstation? Soll die Umgebung für alle nutzbar sein oder nur für mein Konto? | |

## 5. Punkte für den Admin-Termin

Diese Schritte brauchen Admin-Rechte und werden **gemeinsam** erledigt. Das
Setup-Programm prüft vorher, welche davon überhaupt nötig sind, und zeigt nur
die fehlenden an.

| Punkt | Wofür | nötig? |
|---|---|---|
| NVIDIA-Treiber ≥ 570 (CUDA 12.8) | Training und Policy-Fahrt auf der GPU | wird geprüft |
| Visual C++ Redistributable 2015–2022 x64 | PyTorch | wird geprüft |
| Daheng Galaxy SDK (Treiber + `gxipy`) | Draufsicht- und Wrist-Kamera | wird geprüft |
| Netzwerkadapter für den Roboter: feste IP im Robotersubnetz | Verbindung zum Neura LARA 5 | **Frage 5.1** |
| Firewall-Freigabe für die Roboterverbindung | Verbindung zum Neura LARA 5 | **Frage 5.2** |
| Windows „lange Pfade“ (`LongPathsEnabled`) | einzelne pip-Pakete mit tiefen Pfaden | nur falls Fehler |

| # | Frage | Antwort |
|---|---|---|
| 5.1 | Ist an der Workstation schon ein Netzwerkadapter für das Roboternetz eingerichtet (feste IP)? | |
| 5.2 | Blockiert die Windows-Firewall ausgehende/eingehende Verbindungen ins Robotersubnetz? | |
| 5.3 | Sind die Kameras per USB 3 oder GigE angeschlossen? (GigE braucht ggf. Jumbo Frames am Netzwerkadapter, Admin.) | |
| 5.4 | Wann ist ein gemeinsamer Termin möglich? | |

## 6. Freigabe von Software

| # | Frage | Antwort |
|---|---|---|
| 6.1 | Reicht diese Liste der Komponenten (Datei `komponenten.py` bzw. die Checkliste aus dem Setup-Programm) als Freigabe, oder braucht es eine andere Form? | |
| 6.2 | Darf statt `pip` das Werkzeug **uv** (Astral, eine einzelne `.exe` ohne Admin) verwendet werden? Vorteile: deutlich schneller, kann Python 3.12 ohne Admin bereitstellen, exakte Lockfiles. | |
| 6.3 | Darf FFmpeg als portable Version (nur DLLs im Umgebungsordner, kein PATH-Eintrag, LGPL-Build) verwendet werden? | |

---

## Mit dem Team zu klären (nicht mit dem Betreuer)

- Soll das Setup-Programm später auch die Umgebung für GUI und M1–M3
  (`code/requirements.txt`, inkl. EasyOCR) einrichten? Der Code ist nach dem
  Klonen schon da, es fehlen nur die Abhängigkeiten.
- Hat jemand weitere Systemvoraussetzungen (Treiber, SDKs), die in Abschnitt 5
  fehlen?
