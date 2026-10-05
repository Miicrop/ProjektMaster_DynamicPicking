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
| Greifer | Montiert ist ein **Zimmer MATCH LWR50L-23-00004-A** (elektrisch, IO-Link) auf dem Robotermodul LWR50F-13-05-A ([docs/greifer/](../../docs/greifer/)). In der Steuerung heißt das Werkzeug **„RobotiQ“** (im Backup als Modbus-Greifer angelegt) **(prüfen: Ansteuerung, Masse, TCP)** |
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
   **Alle Posen in `system.yaml` und alle Fahrziele im Code sind TCP-Posen dieses Werkzeugs
   im Basis-KS**, nicht der Flansch. Ein falscher TCP-Versatz verschiebt also jede Greifhöhe.
   ⚠️ **Die 210 mm aus dem Backup passen nicht zum montierten Zimmer-Greifer.** Laut Datenblatt:
   LWR50L mit Backen 169,5 mm + Robotermodul LWR50F 28 mm = **197,5 mm** (im Labor nachmessen:
   Flansch → Fingerspitzen, geschlossen). Diesen Wert als `offsetZ` des Werkzeugs am Pendant
   eintragen; er steht auch in `robot.tool_tcp_mm`. **Unser Code fährt nicht, solange beide um
   mehr als 1 mm abweichen** (Fehlermeldung nennt beide Werte). Gemessen anders? Pendant **und**
   `tool_tcp_mm` anpassen, dann `poses.home` z = 434,5 − Versatz.
   Kontrolle: `robot_check info` zeigt Werkzeug und TCP-Versatz an.
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
über die Knöpfe *Home*, *Greifer auf/zu*, *Achsen-Test* (±X/±Y/±Z/±rz mit wählbarer Schrittweite) und *Pick-Test*. Posen teachen: Roboter hinfahren, Pose
im Auswahlfeld wählen und *Aktuelle TCP-Pose übernehmen* klicken, danach mit Strg+S speichern.
Die Draufsicht zeigt Posen, Arbeitsbereich und TCP. Der rote *STOPP* sendet einen Software-Stopp,
das ersetzt **nicht** den Not-Halt.

**Mit der Kommandozeile:** Alle Befehle im Ordner `code` mit aktivierter venv (`.venv\Scripts\activate`).

| Schritt | Befehl | Bewegt sich? | Erwartung |
|---|---|---|---|
| 1. Verbindung lesen | `python -m m2_robot_control.robot_check info` | nein | Name, Version `v5.0.8`, aktuelle Pose, Punkte `Home`, `Parking`, keine Fehler |
| 2. Home anfahren | `python -m m2_robot_control.robot_check home` | **ja** | Sicherheitsabfrage mit `j` bestätigen, Roboter fährt langsam nach Home |
| 3. Greifer testen | `python -m m2_robot_control.robot_check gripper` | Greifer | öffnen → schließen → öffnen |
| 4. Achsentest | `python -m m2_robot_control.robot_check axes` | **ja**, je 50 mm | Home → +Z/−Z, +X/−X, +Y/−Y, +rz/−rz 20°, jeder Schritt einzeln mit Enter; beobachtete Richtung eintippen → Protokoll am Ende |
| 5. Posen teachen | siehe Abschnitt 7 | nein | Konfigurationszeile wird ausgegeben |
| 6. Kalibrierung | `python -m m2_robot_control.robot_check calib` | nein | siehe Abschnitt 7a, gibt `workspace_to_robot` + Restfehler aus |
| 7. Zeigetest | `python -m m2_robot_control.robot_check point` | **ja** | siehe Abschnitt 7b: Greifer steht 30 mm über dem erkannten Bauteil, greift nicht |
| 8. Greiftest | `python -m m2_robot_control.robot_check pick-test` | **ja** | Home → greift an der Prüfposition → legt wieder ab → Home |

**Achsentest – worauf achten:** Schrittweite mit `--step 20` verkleinern, Einzelschritte mit
`robot_check jog z 20` (Achsen `x`, `y`, `z` in mm, `rz` in °, max. 100 mm / 45°). Bewegt wird
immer linear und langsam (`approach_speed_mps`) im **Basis-Koordinatensystem**, die
Arbeitsraumgrenzen werden vorher geprüft. Notieren: In welche Richtung im Raum zeigen +X und +Y
(z. B. „zum Fenster“)? Fährt +Z wirklich nach oben? Dreht +rz von oben gesehen gegen den
Uhrzeigersinn? Das klärt auch den offenen Punkt zur yaw-Konvention beim Greifen.

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

## 7a. Kalibrierung Arbeitsbereich → Roboter (`calib`)

Koordinatensysteme: Die Kamera (M1) liefert die Bauteilpose im **Arbeitsraum-KS** (Ursprung
innere Rahmenecke unten links, x nach rechts, y nach oben aus Kamerasicht). `workspace_to_robot`
rechnet sie ins **Basis-KS** des Roboters um. Diese Transformation wird hier eingemessen.

Voraussetzungen: Marker aufgeklebt, ihre Mittelpunkte ausgemessen und in `workspace.markers_mm`
eingetragen, TCP-Versatz des Werkzeugs stimmt (sonst ist jeder Punkt um den Fehler versetzt).

```powershell
python -m m2_robot_control.robot_check calib
```

1. Das Werkzeug fragt die Marker der Reihe nach ab (ID 0, 1, 2, 3).
2. Greiferspitze jeweils mittig auf den Marker setzen, sodass sie den Tisch gerade berührt:
   am Pendant, im Freedrive oder mit `robot_check jog …` in einem zweiten Terminal.
3. Enter übernimmt die aktuelle TCP-Pose, `s` überspringt einen Marker (mindestens 3 nötig).
   `calib` selbst bewegt den Roboter nicht.
4. Ausgabe: Restfehler je Marker, RMS und die drei Zeilen für `workspace_to_robot`
   (`rotation_deg`, `translation_mm`, `table_z_mm`) zum Einfügen in `config/system.yaml`.

**RMS > 3 mm** heißt meist: Marker-IDs vertauscht (Zuordnung ID → Ecke muss zur Config passen),
`markers_mm` falsch gemessen oder Spitze nicht mittig. Einzelnen Marker mit großem Restfehler
neu anfahren. Die Ausgabe für die Doku aufheben (Kalibriergenauigkeit).

## 7b. Zeigetest (`point`) – sicherer erster Test nach der Kalibrierung

```powershell
python -m m2_robot_control.robot_check point              # Top-down-Kamera
python -m m2_robot_control.robot_check point --hover 50   # höher bleiben
```

1. Bauteil auf den Tisch legen. Das Werkzeug erkennt es mit M1 (noch ohne Bewegung) und zeigt
   die Pose im Basis-KS. Warnung, wenn die Fase nicht gefunden wurde (Winkel nur bis 180° eindeutig).
2. Nach der Sicherheitsabfrage: Home → Greifer offen über das Bauteil → langsam linear herunter
   bis `--hover` mm (Standard 30) über der Greifposition. Der Greifer schließt **nicht**.
3. Messen: Versatz Bauteilmitte minus Greifermitte in Richtung Basis +X/+Y, z. B. `1.5 -2`.
   Prüfen, ob die Finger quer zur kurzen Seite stehen. Notiz eingeben.
4. Die Zeile landet in `logs/point_tests.csv`, danach fährt der Roboter hoch und nach Home.

An 5–10 Stellen wiederholen, auch am Rand des Arbeitsbereichs und mit verschiedenen Winkeln.
Die CSV ist direkt die Datengrundlage für die Positionsgenauigkeit in der Evaluation.
Ohne Hardware ausprobieren: `robot_check point --sim --detector replay`.

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
   Unter Windows **„VirtualBox Host-Only Ethernet Adapter“** auswählen. Die `.ova` bringt den
   Linux-Namen `vboxnet0` mit, sonst startet die VM mit „Netzinterface vboxnet0 nicht vorhanden“.
5. VM starten, nach ca. 30 s im Browser `http://192.168.2.13:8080` öffnen (Login-Seite).
   Bricht der Start mit `VERR_INTNET_FLT_IF_NOT_FOUND` ab: **PC neu starten** (der
   VirtualBox-Netzwerktreiber ist dann sauber an den Adapter gebunden).
6. Prüfen: `Test-NetConnection 192.168.2.13 -Port 65432` → `TcpTestSucceeded : True`.
   Lesen (`info`) klappt schon jetzt. **Für Bewegungen** muss man sich in der Bedienoberfläche
   einloggen (Zugangsdaten stehen nicht in der Neura-Doku → Betreuer bzw. Neura fragen) und den
   Roboter dort in den Automatikmodus bringen. Sonst lehnt die VM jede Bewegung ab mit
   *„Unable to switch to play mode. Check if robot in automatic mode“*.
7. Die Adresse der VM steht getrennt vom echten Roboter in `config/system.yaml` unter
   `robot.vm_host`. Robotermodus **`vm`** benutzen:

```powershell
python -m m2_robot_control.robot_check info --vm          # ohne Sicherheitsabfrage, es ist ja die VM
python -m m2_robot_control.robot_check home --vm
python -m orchestrator --replay --vm-robot --cycles 1     # Gesamtablauf gegen die VM
$env:NEURA_VM = "1"; python -m pytest m2_robot_control/tests/test_neura_vm.py -v
```

In der GUI heißt der Modus **„Neura-VM“** (Tab Roboter und Tab Ablauf); das IP-Feld zeigt dann `vm_host`.
Die Bewegung sieht man live in der Neura-Bedienoberfläche im Browser.

> ⚠️ VM und Laborroboter haben ab Werk **dieselbe IP** `192.168.2.13`. Ist im Labor der echte
> Roboter angeschlossen, fährt auch der Modus `vm` den **echten** Roboter, und zwar ohne
> Sicherheitsabfrage. Deshalb ist der VM-Test nur mit `NEURA_VM=1` aktiv. Im Labor `vm` nicht benutzen.

In der VM ist das Werkzeug `RobotiQ` bereits auf 197,5 mm gesetzt (per
`update_tool_parameters`). Bei einer neu importierten VM einmal wiederholen, sonst verweigert
unser Code die Bewegung wegen des TCP-Versatzes.

Hinweise: Die VM meldet Server-Version `v5.0.0-alpha.102`, unser Client ist v5.0.8. Die Warnung
dazu beim Verbinden ist bekannt. Die VM ist eine LARA 5 wie im Labor.

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
