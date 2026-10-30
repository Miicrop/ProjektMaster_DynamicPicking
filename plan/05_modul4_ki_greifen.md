# 05 – Modul 4: Behavior Cloning (Person 4)

**Verantwortlich:** Person 4 (Jeremy) · **Code:** `code/m4_behavior_cloning/` · **Bedienung:** GUI-Reiter „M4 Behavior Cloning“
Aufgaben: [06_offen.md](06_offen.md) · Thesis: Kap. 08 `thesis/chapters/08_ki_greifen.tex`

Die Pipeline stammt per `git subtree` aus `joshi99999/Dynamic_Robot_Project` (Ordner `Behavior Cloning/`).

## Was M4 ist

Eine lokale Imitation-Learning-Pipeline für den Neura LARA:

- automatisierte Datenaufnahme mit Action Noise Injection (Wegpunkte teachen, Episoden aufzeichnen),
- Training einer Diffusion Policy (LeRobot 0.6.1, torch cu128),
- Live-Inferenz mit 15 Hz, `servo_j` mit 60 Hz, eigene Sicherheitsgrenzen (ServoGuard, Geofence).

Kameras: Handgelenk Daheng VEN-161 mit Fisheye, Szenenkamera = Kamera oben von M1.

Die Hardware ist nur über Ports und Adapter angebunden (`bc/ports.py`, `bc/adapters/`). Deshalb läuft
die Logik auch gegen Simulation und Neura-VM. Maßgeblich ist seine eigene Doku:

- `code/m4_behavior_cloning/README.md`: Architektur, feste Werte
- `code/m4_behavior_cloning/INTEGRATION.md`: Einbau, Umgebung, Start
- `code/m4_behavior_cloning/Requierments/requierments.md`: Anforderungen und Entscheidungen
- `code/m4_behavior_cloning/Dokumentation/`: Kameras, Labortage, Zittern, Training

## Einbindung

- Ein Reiter in der Gruppen-GUI (`code/gui/tab_m4.py`), aufgebaut wie sein eigenes Fenster. Sein
  Code bleibt unverändert (`BC-Oberflaeche.bat` geht weiterhin).
- Zwei Python-Umgebungen:
  - Die GUI läuft in der Gruppen-venv (Python 3.11).
  - Alles mit torch und lerobot läuft als Unterprozess mit `code/m4_behavior_cloning/.venv`
    (Python 3.12) über `BC_PYTHON`.
  - Eingerichtet wird das mit `code/setup_m4.bat`.
- `neurapy` kommt aus `code/m2_robot_control/vendor` (`BC_NEURAPY_DIR`).
- Im automatischen Ablauf (Greifen = „M4 Behavior Cloning“, `--grasper bc`) greift die Policy:
  - `orchestrator/m4_grasper.py` startet `apps/infer.py` für eine Fahrt.
  - Die Fahrt endet am Übergabepunkt PRE_PLACE [512,8, 196,8, 135,7] mm, rz −156°. Das Teil ist
    dann im Greifer, ~9 cm über der Prüfposition.
  - Danach macht M2 `reset()` (Tool, Override, init_program) und legt ab. Es folgen M3 und M2 wie gehabt.
  - Die M1-Pose wird nur protokolliert, die Policy sucht das Teil selbst im Bild.
- Die Freigabe für die echte Anlage gibt die Rückfrage im Ablauf. Auf der Kommandozeile muss man
  weiterhin „ANLAGE“ eintippen.
- Roboter und Kamera oben werden automatisch zwischen M2/M1 und M4 umgeschaltet
  (`gui/robot_access.py`). Läuft auf der anderen Seite etwas, kommt eine Meldung statt der Umschaltung.
- Zwei gleichzeitige Verbindungen zur Steuerung sind kein Problem (in der VM getestet).

## Änderungen von Person 4 nachziehen

```bash
# im Klon von Dynamic_Robot_Project
git subtree split --prefix="Behavior Cloning" -b bc-export
# hier
git subtree pull --prefix=code/m4_behavior_cloning ../Dynamic_Robot_Project bc-export
```
