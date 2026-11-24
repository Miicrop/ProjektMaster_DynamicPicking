# M4-Setup: Einrichtung auf einem neuen Rechner

Richtet die Python-Umgebung von M4 (Behavior Cloning) ein: abgekapselt in
**einem Ordner**, ohne Admin-Rechte und so, dass man jeden Schritt sieht und
einzeln an- oder abwählen kann.

```bat
code\setup_m4.bat
```

Ein Doppelklick öffnet das Fenster. Gebraucht wird nur ein beliebiges Python
ab 3.8; die Umgebung selbst wird mit **Python 3.12** angelegt (Vorgabe von
LeRobot 0.6.1).

Sind `.bat`-Dateien gesperrt, geht dasselbe direkt mit Python:
`code\setup\m4_setup.py` doppelklicken, oder in einer Konsole
`py code\setup\m4_setup.py` (bzw. `python code\setup\m4_setup.py`).

Ohne Git auf dem Rechner: Repo auf GitHub über *Code → Download ZIP* laden und
entpacken. Das Setup braucht kein Git.

## Grundsätze

| | |
|---|---|
| **Abgekapselt** | Alles landet im Zielordner (`venv`). Wird der Ordner gelöscht, ist das System wie vorher. Einzige Ausnahme: die Benutzervariable `BC_PYTHON`, und die nur, wenn der Zielordner nicht der Standard ist. |
| **Kein Admin** | Was Admin-Rechte braucht (NVIDIA-Treiber, VC++ Redistributable, Daheng Galaxy SDK), wird **nie** installiert, nur geprüft. Für den Termin mit dem Laborbetreuer erzeugt *Checkliste Betreuer* eine Liste. |
| **Kontrolle** | Jede Komponente hat ein Häkchen. *Befehle anzeigen* zeigt die exakten Befehle und kann sie als `.bat` speichern, für eine Installation komplett von Hand. Jeder Lauf schreibt ein Log nach `setup/logs/`. |
| **Reproduzierbar** | Jeder pip-Aufruf nutzt `m4_behavior_cloning/Dokumentation/environment-lock.txt` als Constraints-Datei. Auch einzeln installierte Gruppen bekommen so genau die Versionen des abgenommenen Trainings-PCs. |

## Das Fenster

- **Oben:** Zielordner (Standard `code\m4_behavior_cloning\.venv`, findet
  die GUI automatisch), Basis-Python (leer = automatisch suchen),
  Paketquelle (leer = Internet, Ordner = offline), FFmpeg-ZIP, PyTorch-Build
  GPU/CPU.
- **Liste:** 7 Gruppen. Pro Zeile: Häkchen, Status (vorhanden / fehlt /
  abweichend / Admin nötig / wartet) und ein Detail. Fährt man mit der Maus
  über den Titel, sieht man, wofür die Komponente ist und wie man sie von
  Hand installiert. Zeilen mit *Admin* oder *Prüfen* haben kein Häkchen.
- **Knöpfe:** *Fehlende wählen*, *Befehle anzeigen*, *Checkliste Betreuer*,
  *Auswahl installieren*, *Reparieren* (ausgewählte Pakete neu, ohne
  Abhängigkeiten), *Deinstallieren* (ausgewählte Komponenten),
  *Umgebung löschen* (der ganze Zielordner, mit Rückfrage; nur wenn darin eine
  `pyvenv.cfg` liegt).

Was schon passt, wird beim Installieren übersprungen. Die Komponenten selbst
stehen in [komponenten.py](komponenten.py). Dort wird auch etwas hinzugefügt
oder eine Version geändert.

## Kommandozeile (ohne Fenster)

```bat
setup_m4.bat --status
setup_m4.bat --befehle --nur venv,torch
setup_m4.bat --installieren --ja
setup_m4.bat --installieren --nur gui,opencv --cpu
setup_m4.bat --reparieren opencv
setup_m4.bat --deinstallieren ffmpeg,gxipy
setup_m4.bat --umgebung-loeschen
setup_m4.bat --checkliste
```

Weitere Optionen: `--ziel ORDNER`, `--basis-python PFAD`,
`--wheelhouse ORDNER`, `--ffmpeg-zip DATEI`. IDs der Komponenten zeigt
`--status`.

## Ohne Internet auf der Workstation

Auf einem Rechner **mit** Internet (Python 3.12 nicht nötig):

```bat
setup_m4.bat --wheelhouse-befehle D:\m4_wheels
```

Den angezeigten `pip download`-Befehl ausführen und den Ordner (ca. 3–4 GB)
mitnehmen. Auf der Workstation den Ordner als *Paketquelle* wählen, oder:
`setup_m4.bat --installieren --wheelhouse D:\m4_wheels`.
**Noch nicht ausprobiert.** Ob alle Pakete als Wheel vorliegen, zeigt sich
erst beim ersten Lauf.

Läuft das Internet über einen Proxy: vor dem Start `set HTTPS_PROXY=http://host:port`
(pip übernimmt das).

## Tests

```bat
python setup\test_kern.py
```

Die Tests brauchen nur die Standardbibliothek und installieren nichts.

## Offene Punkte

Siehe [Abklaerung_Laborbetreuer.md](Abklaerung_Laborbetreuer.md): Internet und
Proxy, ob `.bat`/PowerShell erlaubt sind, AppLocker, Admin-Termin, `uv`.
