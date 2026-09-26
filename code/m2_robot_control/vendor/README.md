# vendor/neurapy – Neura-Python-Client (Windows)

`neurapy/robot.py` ist der **unveränderte** Windows-Client aus der Neura-Lieferung
(`LARA-version-5.0.8/Neurapy-windows/robot.py`, Version v5.0.8).

- Der Client ist nur ein dünner TCP-Client: Jeder Methodenaufruf wird als JSON
  (`{"function": ..., "args": ..., "kwargs": ...}`) an die Robotersteuerung auf Port **65432**
  geschickt. Die Liste der Methoden holt er sich beim Start vom Roboter (`get_functions`).
- Die Ziel-IP liest er beim Import aus der Umgebungsvariable `SOCKET_ADDRESS`
  (Standard `192.168.2.13`). `NeuraRobot` setzt sie automatisch aus `config/system.yaml`.
- Abhängigkeiten: `pywin32` und `prettytable` (stehen in `requirements.txt`).
- Doku der Methoden: [docs/neura/neurapy_v5.0.8.pdf](../../../docs/neura/neurapy_v5.0.8.pdf), Kapitel 4.

Proprietäre Software von Neura Robotics. **Das öffentliche GitHub-Repo enthält diese Datei nicht**
(`.gitignore`: `code/m2_robot_control/vendor/neurapy/`). Für die echte Robotersteuerung und die
zugehörigen Tests (`pytest m2_robot_control`) `robot.py` von eurem Neura-Kontakt besorgen und hier
ablegen: `code/m2_robot_control/vendor/neurapy/robot.py`. Ohne die Datei werden diese Tests und
die GUI-Tests mit dem Roboter-Simulator übersprungen (`pytest` zeigt sie als `skipped`), der Rest
des Projekts (M1, M3, Ablauf mit Mock-Roboter, GUI) funktioniert unverändert.
