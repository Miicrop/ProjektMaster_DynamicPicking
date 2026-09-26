# resources – Rohdaten, nicht für den Code benötigt

| Ordner | Inhalt |
|---|---|
| `neura_controller/LARA-version-5.0.8/` | Installationspaket der **Steuerungssoftware** (Debian-Pakete, Skripte, ~1,4 GB). Wird nur zur Neuinstallation der Robotersteuerung gebraucht, nicht auf dem Laptop. Der Windows-Client daraus liegt unter `code/m2_robot_control/vendor/`, die PDFs unter `docs/neura/`. |
| `neura_controller/backup_2025-11-07/` | Datenbank-Backup der Steuerung (Posen, Werkzeuge, Einstellungen). Enthält u. a. die Punkte `Home`/`Parking` und das Werkzeug `RobotiQ`. **Enthält Passwort-Hashes der Benutzer** → nicht weitergeben. |

Der Ordner ist in `.gitignore` eingetragen (Größe, proprietär, sensible Daten).
