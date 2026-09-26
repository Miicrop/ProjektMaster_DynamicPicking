# Anleitung: Den Neura-Roboter vom eigenen Laptop steuern

Für alle, die noch nie mit dem Roboter gearbeitet haben. Vorausgesetzt wird nur ein
Windows-Laptop. Am Ende kannst du den Roboter aus Python heraus bewegen und Posen teachen.

> **Stand der Angaben:** Alles hier stammt aus der Neura-Dokumentation v5.0.8
> ([docs/neura/](../../docs/neura/)), dem Roboter-Backup vom 07.11.2025 und den Fotos.
> Punkte mit **(prüfen)** konnten ohne Roboter nicht verifiziert werden – bitte beim ersten
> Termin am Roboter bestätigen und diese Anleitung korrigieren.

---

## 0. Was du wissen musst

| | |
|---|---|
| Roboter | Neura **LARA** (6 Achsen), Steuerungssoftware **v5.0.8** |
| IP-Adresse | **192.168.2.20** (steht auf dem Roboterfuß) **(prüfen)** – Neura-Standard wäre 192.168.2.13 |
| Schnittstelle | Python-Bibliothek **NeuraPy**; der Laptop schickt Befehle per Netzwerk (TCP-Port **65432**) an die Steuerung |
| Greifer | Im Roboter ist ein Werkzeug **„RobotiQ“** (Modbus-Greifer) angelegt **(prüfen, ob montiert)** |
| Gespeicherte Punkte | `Home` und `Parking` |
| Einheiten der API | Meter und Radiant, Pose = `[x, y, z, roll, pitch, yaw]` |
| Einheiten in unserem Code | Millimeter und Grad (die Umrechnung macht `NeuraRobot`) |

**So funktioniert es:** Auf der Steuerung (Control Box) läuft ein Server. Die Datei
`vendor/neurapy/robot.py` ist ein kleiner Client: Jeder Aufruf wie `r.move_joint("Home")`
wird als Nachricht an den Server geschickt, der ihn ausführt. Deshalb braucht der Laptop
keine spezielle Software, nur Python und eine Netzwerkverbindung.

## 1. Sicherheit – vor jedem Einschalten

- Nie allein am Roboter arbeiten. Eine Person hat **immer die Hand am Not-Halt**.
- Niemand steht im Arbeitsraum, solange ein Programm läuft.
- Neue Bewegungen immer zuerst mit **reduzierter Geschwindigkeit** testen (`override: 0.2`
  in `config/system.yaml`, das sind 20 %). Erst erhöhen, wenn der Ablauf sicher funktioniert.
- Neue Posen erst im Simulator (Abschnitt 8) und dann langsam am Roboter anfahren.
- Unsere Software-Arbeitsraumgrenzen (`robot.limits_mm`) ersetzen **keine** Sicherheitstechnik.

## 2. Software auf dem Laptop installieren (einmalig)

1. **Python 3.11** von <https://www.python.org/downloads/> installieren.
   Beim Setup **„Add python.exe to PATH“** anhaken.
   *(Neura empfiehlt offiziell Python 3.8. Der Client ist aber reiner Netzwerk-Code und wurde
   mit 3.11 gegen unseren Simulator getestet. Falls es Probleme gibt: 3.8 probieren.)*
2. **VS Code** von <https://code.visualstudio.com/> installieren, dazu die Erweiterung „Python“.
3. **Projektordner** auf den Laptop kopieren (später per Git).
4. Eingabeaufforderung (PowerShell) im Ordner `code` öffnen und ausführen:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Damit werden auch `pywin32` und `prettytable` installiert, die der Neura-Client braucht.
5. Test ohne Roboter, das muss funktionieren:

   ```powershell
   python -m m2_robot_control.robot_check info --sim
   ```

   Ausgabe: `robot : LARA5-FAKE dof=6 server version=v5.0.8` usw.

## 3. Laptop mit dem Roboter verbinden

1. **Kabel:** Die Control Box mit dem Schlüssel öffnen. Unten links sitzt die Buchse
   **„Ethernet RJ45“**. Ein LAN-Kabel von dort direkt an den Laptop stecken
   (bei Laptops ohne LAN-Buchse einen USB-LAN-Adapter nehmen).
2. **Feste IP-Adresse am Laptop setzen.** Laptop und Roboter müssen im selben Netz
   `192.168.2.x` sein:
   - Windows 11: *Einstellungen → Netzwerk und Internet → Ethernet* (bzw. der USB-Adapter)
     → *IP-Zuweisung → Bearbeiten → Manuell → IPv4 an*
   - IP-Adresse: **192.168.2.50** (eine freie Adresse, **nicht** .11, .12, .13, .14 oder .20)
   - Subnetzmaske: **255.255.255.0**; Gateway und DNS leer lassen → *Speichern*
3. **WLAN prüfen:** Wenn das WLAN selbst ein `192.168.2.x`-Netz ist (manche Router),
   WLAN während der Arbeit am Roboter ausschalten.
4. **Verbindung testen** (Roboter-Steuerung muss eingeschaltet sein):

   ```powershell
   ping 192.168.2.20
   Test-NetConnection 192.168.2.20 -Port 65432
   ```

   `ping` muss antworten und `TcpTestSucceeded : True` erscheinen.
   Wenn nur der Port-Test scheitert, läuft auf der Steuerung der NeuraPy-Server nicht
   → Abschnitt 9.

## 4. Roboter vorbereiten (am Teach-Pendant)

1. Control Box einschalten, warten bis das Teach-Pendant hochgefahren ist (einige Minuten).
2. Not-Halt entriegeln (Pilz-Taster drehen) und Fehler quittieren bzw. zurücksetzen.
3. Anmelden. Zugangsdaten gibt es beim Laborbetreuer, sie gehören **nicht** ins Repository.
4. **Werkzeug prüfen:** Unter den Werkzeugen muss der montierte Greifer ausgewählt sein
   (im Backup heißt er `RobotiQ`, TCP-Versatz 210 mm in z). Der Name muss mit
   `robot.tool_name` in `config/system.yaml` übereinstimmen.
5. **Punkt `Home` prüfen:** Der Punkt existiert und ist frei anfahrbar.
6. Betriebsart: Unser Code schaltet vom Teach- in den Automatikmodus
   (`switch_to_automatic_mode()`). **(prüfen:** Muss das am Pendant zusätzlich bestätigt
   werden, oder braucht es einen Schlüsselschalter?)

## 5. Konfiguration eintragen

In `code/config/system.yaml`, Abschnitt `robot`:

```yaml
robot:
  host: 192.168.2.20      # IP der Steuerung
  tool_name: RobotiQ      # Werkzeugname wie im Pendant
  home_point: Home
  override: 0.2           # 20 % Geschwindigkeit zum Testen
```

Die IP muss **nicht** als Umgebungsvariable gesetzt werden (wie in der Neura-Doku
beschrieben), das macht unser Code automatisch aus `host`.

## 6. Erste Schritte – in genau dieser Reihenfolge

**Mit der GUI:** `start_gui.bat` doppelklicken (oder `python -m gui --tab m2`), Tab **M2 Roboter** öffnen.
Modus „Echter Roboter“, IP prüfen, *Verbinden*. Danach dieselbe Reihenfolge wie in der Tabelle unten
über die Knöpfe *Home*, *Greifer auf/zu* und *Pick-Test*. Posen teachen: Roboter hinfahren, Pose
im Auswahlfeld wählen und *Aktuelle TCP-Pose übernehmen* klicken, danach mit Strg+S speichern.
Die Draufsicht zeigt Posen, Arbeitsbereich und TCP. Der rote *STOPP* sendet einen Software-Stopp,
das ersetzt **nicht** den Not-Halt.

**Mit der Kommandozeile:** Alle Befehle im Ordner `code` mit aktivierter venv (`.venv\Scripts\activate`).

| Schritt | Befehl | Bewegt sich? | Erwartung |
|---|---|---|---|
| 1. Verbindung lesen | `python -m m2_robot_control.robot_check info` | nein | Name, Version `v5.0.8`, aktuelle Pose, Punkte `Home`, `Parking`, keine Fehler |
| 2. Home anfahren | `python -m m2_robot_control.robot_check home` | **ja** | Sicherheitsabfrage mit `j` bestätigen, Roboter fährt langsam nach Home |
| 3. Greifer testen | `python -m m2_robot_control.robot_check gripper` | Greifer | öffnen → schließen → öffnen |
| 4. Posen teachen | siehe Abschnitt 7 | nein | Konfigurationszeile wird ausgegeben |
| 5. Greiftest | `python -m m2_robot_control.robot_check pick-test` | **ja** | Home → greift an der Prüfposition → legt wieder ab → Home |

Wenn `info` mit einer Warnung zur Version kommt („client version is not compatible“),
läuft auf dem Roboter eine andere Softwareversion als v5.0.8. Dann bei Neura bzw. dem
Betreuer den passenden Client besorgen und `vendor/neurapy/robot.py` ersetzen.

## 7. Posen teachen (Prüfposition, Ablagen)

1. Den Roboter von Hand an die gewünschte Stelle bringen: am Pendant verfahren oder im
   Freedrive-Modus mit der Hand führen. Der Greifer zeigt nach unten und die Finger stehen
   so, wie das Teil gegriffen werden soll.
2. Pose auslesen:

   ```powershell
   python -m m2_robot_control.robot_check pose inspection
   ```

   Ausgabe z. B. `    inspection: [702.3, 298.1, 51.0, 180.0, 0.0, 180.0]`
3. Die Zeile unter `robot.poses` in `config/system.yaml` einfügen.
   Gleiches für `bin_good` und `bin_bad`.
4. Danach die `limits_mm` so setzen, dass alle Posen plus Anfahrhöhe darin liegen.

**Kalibrierung Arbeitsbereich → Roboter (mit Person 1):** Mit der Greiferspitze
nacheinander die vier Innenecken des weißen Rahmens anfahren, jeweils `pose` auslesen und
die vier Punkte notieren. Daraus berechnet `common.transforms.fit_rigid_2d` Rotation und
Verschiebung für `workspace_to_robot` (Skript folgt, siehe Roadmap).

## 8. Ohne Roboter arbeiten

**a) Eingebauter Simulator (sofort nutzbar)**, nur für Software-Tests, keine Kinematik:

```powershell
python -m m2_robot_control.robot_check info --sim
python -m m2_robot_control.robot_check pick-test --sim
python -m orchestrator.main --replay --sim-robot --cycles 4   # Gesamtablauf mit Testbildern
```

Er versteht dieselben Nachrichten wie die echte Steuerung, prüft aber nur, ob die
Reihenfolge stimmt (Power an, Automatikmodus, `init_program` vor Bewegungen).

**b) Offizielle Neura-Simulation (virtuelle Maschine).** Dort gibt es die echte Bedienoberfläche
und echte Kinematik. Anleitung: [docs/neura/offline_simulation_setup.pdf](../../docs/neura/offline_simulation_setup.pdf).
Kurzfassung:

1. VirtualBox **7.1.4** installieren (andere Versionen laut Neura nicht getestet).
2. Die VM-Datei (`.ova`) importieren. **Sie ist nicht in unseren Unterlagen** → bei Neura
   bzw. dem Betreuer anfragen. Benötigt ≥ 30 GB Platz und ≥ 10 GB RAM.
3. *Datei → Tools → Network Manager*: Host-only-Adapter anlegen, IPv4 `192.168.2.11` /
   `255.255.255.0`; DHCP-Server an: Server `192.168.2.12`, Bereich `192.168.2.13`–`192.168.2.13`.
4. VM-Einstellungen → Netzwerk: Adapter 1 aus, Adapter 2 = Host-only-Adapter.
5. VM starten, nach ca. 30 s im Browser `http://192.168.2.13:8080` öffnen (Login-Seite).
6. In `config/system.yaml` `host: 192.168.2.13` eintragen, dann wie am echten Roboter arbeiten.

## 9. Fehlersuche

| Problem | Ursache / Lösung |
|---|---|
| `ping` geht nicht | Kabel an der richtigen Buchse? Feste IP gesetzt (Abschnitt 3)? Richtiger Adapter? WLAN im gleichen Netz → aus |
| `ping` geht, Port 65432 nicht | NeuraPy-Server auf der Steuerung nicht aktiv → Steuerung neu starten bzw. am Pendant „Reset Control“, sonst Betreuer fragen |
| `Robot controller ... not reachable` | wie oben; auch `robot.host` in der Konfiguration prüfen |
| `ModuleNotFoundError: win32api` | venv nicht aktiviert oder `pip install -r requirements.txt` fehlt |
| `power_on failed` | Not-Halt gedrückt oder Fehler nicht quittiert → am Pendant zurücksetzen |
| Bewegung startet nicht / „init_program“ | `connect()` wurde nicht aufgerufen (unser Code macht das automatisch) |
| `IKNotFound` | Pose nicht erreichbar (zu weit, falsche Orientierung) → Pose/Grenzen prüfen |
| Roboter stoppt mit Kollision | Kollisionserkennung hat ausgelöst → Pendant quittieren, Geschwindigkeit/Weg prüfen |
| Warnung zur Client-Version | Softwareversion am Roboter ≠ v5.0.8 → passenden Client besorgen |
| Strg+C im Programm | stoppt die Bewegung (der Neura-Client ruft dann `stop()` auf) |
| Nach STOPP bewegt sich nichts mehr | Gewollt: `stop()` beendet laut Neura-Doku das Programm auf der Steuerung. Erst nach `init_program()` gehen wieder Bewegungen. Unser Code verlangt dafür eine bewusste Freigabe: GUI *Fehler quittieren* / *Freigeben*, im Code `robot.reset()` |

Fehlerliste des Roboters abfragen: `python -m m2_robot_control.robot_check info` (Zeile `errors`).

## 10. Die wichtigsten NeuraPy-Befehle (für eigene Experimente)

```python
from m2_robot_control.robot import load_neurapy_client
r = load_neurapy_client("192.168.2.20")
r.power_on(); r.switch_to_automatic_mode(); r.set_override(0.2); r.init_program()
r.move_joint("Home")                                  # gespeicherten Punkt anfahren
p = r.get_tcp_pose()                                  # [x, y, z, r, p, y] in m / rad
q = list(p); q[2] += 0.05                             # 5 cm höher
r.move_linear(target_pose=[p, q], speed=0.05)        # linear, 5 cm/s
r.grasp(); r.release()                                # Greifer zu / auf
r.stop()                                              # am Ende genau einmal
```

Vollständige Referenz: [docs/neura/neurapy_v5.0.8.pdf](../../docs/neura/neurapy_v5.0.8.pdf),
Kapitel 4 (API), Kapitel 6.2 (Pick & Place für LARA).
