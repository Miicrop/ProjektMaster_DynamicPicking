# 06 – Offen

**Alle offenen Aufgaben und Fragen an einem Ort.** Erledigtes wandert mit Datum nach
[07_erledigt.md](07_erledigt.md). Die Moduldateien (02–05) enthalten nur Wissen, keine Aufgaben.

> **Zum Abhaken mit Teilschritten und Notizen:** https://claude.ai/artifact/5sR6LYytTSzEgksksYpZ1q
> (Stand 30.10., gleiche Punkte wie hier).

`[ ]` offen · `[~]` angefangen · Wer: N = Niklas, J = Jeremy, T = Team, P1–P3 = Person des Moduls

## Stand (2026-10-30)

- Alle vier Module laufen im Code, in einer GUI und im automatischen Ablauf. M4 greift wahlweise
  statt M2. 118 Tests grün.
- Am echten Roboter gab es einen ersten vollständigen Ablauf, noch mit Testbildern statt Kameras.
  Posen sind geteacht, die Kalibrierung ist eingemessen, Öffnen und Schließen des Greifers funktioniert.
- Die Übergabe M4 → M2 ist in der Neura-VM getestet.
- Die Thesis entspricht dem Code-Stand, Kap. 08 (M4) ist entworfen.
- **Fehlt vor allem:** Kameras am Aufbau, ein vollständiger Zyklus mit echtem Teil, Messreihen,
  M4 mit trainiertem Modell und die Durchsicht der Thesis.

## 1. Code und Repo

- [ ] **N** – Laborlaptop-Stand pushen. Öffnen und Schließen des Greifers funktioniert dort,
  im Repo steht noch `gripper_enabled: false`.
- [ ] **N** – Thesis- und Plan-Stand vom 30.10. committen.
- [ ] **T** – Git-Hosting für das Team klären (GitHub oder GitLab der Hochschule).
  `resources/` bleibt draußen, weil es Passwort-Hashes enthält.
- [ ] **P2** – GitHub-Repo mit den bisherigen Robotertests sichten. Es liegt noch nicht vor.

## 2. Labor: Kameras und Inbetriebnahme

Die Befehle laufen im Ordner `code` mit aktivierter venv. Die Anleitung steht in
[ANLEITUNG_NEURA.md](../code/m2_robot_control/ANLEITUNG_NEURA.md), Abschnitte 1, 3, 4, 7a und 7b.
Nach jeder Config-Änderung in der GUI speichern (Strg+S).

**Mitnehmen:** Maßband, Lineal, Klebeband, Gut- und Schlechtteile, Netzteil, USB-Hub, LAN-Kabel.

- [ ] **N** – **Kameras anbinden**
  - Galaxy SDK (Daheng) auf dem Laborrechner installieren.
  - `python -m common.camera` listet die Kameras mit Seriennummer.
  - Seriennummer der Kamera oben eintragen: `topdown_camera.source: daheng:<Seriennummer>`.
  - Seriennummer der Handgelenkkamera bei M4 eintragen.
  - Seitenkamera: Index in `inspection_camera.source` eintragen.
  - USB-Bandbreite mit allen drei Kameras gleichzeitig prüfen.
- [ ] **P1** – **M1 live.** Kamera oben fest montieren. Im Tab M1 mit „Live“ prüfen, ob alle
  vier Marker erkannt werden und die Pose plausibel ist. Das Daheng-Bild hat 1440×1080 Pixel.
  Danach eine feste Belichtung festlegen (`exposure_us`, derzeit Automatik).
- [ ] **P3** – **M3 live.** Seitenkamera und Licht an der Prüfvorrichtung aufbauen. Im Tab M3 mit
  einem Teil prüfen, ob die ROIs passen und die OCR liest. Prüfen, ob an der Prüfstation eine
  Beleuchtung vorhanden ist oder gebraucht wird.
- [~] **N** – **Kalibrierung Arbeitsbereich → Roboter.** Sie ist eingemessen
  (0,35°, [205,1, −319,7] mm). Der Restfehler (RMS) fehlt im Repo. Mit `robot_check calib`
  wiederholen, RMS und Ausgabe notieren. Ab 3 mm warnt das Werkzeug.
- [ ] **N/P1** – **Zeigetest** `robot_check point` an 5–10 Stellen, an Rand- **und** Mittelpositionen:
  - Versatz dx/dy notieren. Er landet in `logs/point_tests.csv`.
  - Wächst der Versatz zum Rand hin, ist das Parallaxe (siehe M1) oder Objektivverzerrung.
  - Greifwinkel prüfen: Bei einem schräg liegenden Teil müssen die Backen quer über der schmalen
    Seite stehen.
  - Ein grober Zeigetest sah bereits vielversprechend aus.
- [ ] **P1** – **Parallaxe bewerten.** Wenn der Zeigetest einen lageabhängigen Versatz zeigt:
  - Korrektur über die Bauteilhöhe, also die Oberseite statt der Tischebene entzerren,
  - oder nur die Oberseite segmentieren.
- [ ] **P1** – Intrinsische Kalibrierung der Kamera oben (Schachbrett/ChArUco), Ergebnis in
  `config/`. `calibration_file` wird noch nicht verwendet.
- [ ] **N** – **Werkzeuglast** von `ZimmerLWR50` am Pendant ablesen und mit dem Soll vergleichen:
  1,75 kg, Schwerpunkt z ≈ 81 mm (ANLEITUNG_NEURA Abschnitt 4).
- [ ] **N** – Klären, ob der Wechsel in den Automatikmodus am Pendant bestätigt werden muss
  (Schlüsselschalter).
- [ ] **P2** – **Greiftest** `robot_check pick-test` mit Greifer. Den Übergang von schnell auf
  langsam ca. 20 mm über jedem Ziel beobachten.
- [ ] **P2** – Greifer-Rückmeldung auswerten (Teil gegriffen?), z. B. über IO-Link.
- [ ] **P2** – Wiederholgenauigkeit an der Prüfposition messen. Das ist wichtig für M3.
- [ ] **T** – **Erster vollständiger Zyklus** mit echten Kameras, Greifer und echtem Teil
  (Tab Ablauf, „1 Zyklus“, Geschwindigkeit 20 %). Der Greifer darf im M3-Bild nicht zu sehen sein.
- [ ] **T** – Fehlerbehandlung und Reset am realen System erproben (STOPP, Quittieren, Neustart).

**Worauf achten**
- **Marker-Zuordnung:** Passt die Zuordnung von ID zu Ecke nicht zur Config, wird das Bild ohne
  Fehlermeldung falsch entzerrt. Test: Ein Teil nahe der Ecke unten links muss kleine x/y ergeben.
- **Verschobene Marker:** neu ausmessen und neu kalibrieren. Eine bewegte Kamera ist dagegen
  unkritisch.
- **Fase nicht gefunden** (Konfidenz 0,5): Das Teil kann an der Prüfstation um 180° verdreht liegen.

## 3. M4 und Rücksprache Jeremy

- [ ] **J** – Kap. 08 der Thesis durchsehen, übernehmen oder umschreiben und die `\todo{Jeremy}`
  füllen: Totzeit des Greifers, Override 0,5 mit dem Betreuer, Zwischenfazit.
- [ ] **J/N** – **Zykluszeit.** Im Ablauf startet `apps/infer.py` je Zyklus neu: torch und Modell
  laden, Kameras öffnen, verbinden. Das dauert geschätzt mehrere bis ~30 s, gemessen ist es nicht.
  Klären, ob ein Dauerlauf-Modus sinnvoll ist, der zwischen den Zyklen auf das Startsignal wartet.
- [ ] **J** – **Freigabe echte Anlage.** Im Ablauf ersetzt die Rückfrage „Automatischer Ablauf mit
  dem echten Roboter – M4 Behavior Cloning greift“ das Eintippen von „ANLAGE“, wie in seinem
  Betrieb-Reiter. Mit Jeremy bestätigen.
- [ ] **N** – In der Neura-VM das Werkzeug `ZimmerLWR50` anlegen. Dort heißt es `RobotiQ`, deshalb
  scheitert `test_neura_vm.py` an `set_tool`.
- [ ] **J** – Echter Datensatz und Training auf echten Bildern. Die erste echte Aufnahme wurde
  wegen der Bildrate verworfen.
- [ ] **J/N** – M4 mit trainiertem Modell im Ablauf laufen lassen, erst in der VM, dann im Labor.
  Der Hold-Lauf in der VM erreicht PRE_PLACE nicht, und die VM meldet viele Overruns.
  Das an der Anlage prüfen.
- [ ] **J** – Greifversuche mit der Policy für den Vergleich M2/M4 durchführen (Kap. 10).

## 4. Versuche und Evaluation

- [ ] **T** – Festlegen, wie viele Durchläufe je Versuchsreihe und welche Kennzahlen.
- [ ] **T** – Klären, wie viele Gut- und Schlechtteile es gibt und welche Fehlerarten: fehlende
  Kerbe, falscher Durchmesser, fehlendes oder unlesbares Etikett.
- [ ] **T** – **Versuchsreihe 1:** wiederholte Durchläufe mit einem Gutteil in zufälliger Lage.
  Auswerten: Greiferfolg, Positionsgenauigkeit, Zykluszeit (`cycles_*.csv`).
- [ ] **P3** – **Versuchsreihe 2:** gezielt fehlerhafte Teile. Daraus Konfusionsmatrix und
  Messwiederholbarkeit am festen Aufbau ermitteln.
- [ ] **P1** – Genauigkeitsmessung M1: N Ablagen an bekannten Positionen, Fehlerstatistik.
- [ ] **J/T** – Vergleich PICK mit M2 und PICK mit M4.

## 5. Fotos und Bilder (für Thesis und Präsentation)

- [ ] **N** – Fotos der Zelle aus mehreren Winkeln: Gesamtaufbau, Kameras, Greifer, Prüfstation,
  Ablagen. Für die Thesis das Zellfoto in Kap. 04.
- [ ] **N** – Bild der Prüfvorrichtung, aus dem CAD oder als Foto, für Kap. 07
  (Platzhalter `fig:m3-vorrichtung`).
- [ ] **J** – Foto der Handgelenkkamera am Greifer und Kamerabilder der Policy für Kap. 08.
- [ ] **N** – GUI-Screenshots mit echten Kamerabildern statt Testbildern (Kap. 09).
- [ ] **N** – 1–2 schöne Zyklen mit „Bilder speichern“ und „+ Zwischenschritte“ aufnehmen.
- [ ] **N** – Video eines kompletten Zyklus.

## 6. Thesis: Inhalte nachtragen

Wie man weiterschreibt, steht in [../thesis/blueprint.md](../thesis/blueprint.md) §7.

- [ ] **N** – Kameradaten: Montagehöhe und Objektiv der Kamera oben, Modell, Abstand und Licht der
  Seitenkamera (Kap. 04/05/07).
- [ ] **N** – RMS der Kalibrierung und Versatz aus dem Zeigetest (Kap. 04/06).
- [ ] **P1–P3** – Kapitel 05–07 durchsehen und die Zwischenfazits nach den Labortests ergänzen.
- [ ] **T** – Evaluation (Kap. 10) mit Messdaten, dann den Ergebnissatz in der Kurzfassung.
- [ ] **T** – Vorprojekt GROB (Kap. 02b): Wer schreibt den Abschnitt „Alternative Verfahren“?

## 7. Entscheidungen im Team

- [ ] Pflegerobotik-Projekt („Mensch ärgere dich nicht“ mit Senioren) erwähnen? Wenn ja: in der
  Einleitung, im Fazit oder im Ausblick? Das betrifft auch Szene 7.4 der Präsentation.
- [ ] Welche offenen Punkte nennt der Ausblick? Die Kandidaten stehen als `\todo` in Kap. 11.
- [ ] Englisches Abstract zusätzlich zur Kurzfassung?
- [ ] Quellen für die Motivation (Kap. 1) und Normen zu Cobots (ISO 10218, ISO/TS 15066) aufnehmen?

## 8. Thesis: Durchsicht und Abschluss

- [ ] **N** – Gesamte Arbeit durchsehen.
- [ ] **N** – Danach `/ars-reviewer` für ein simuliertes Gutachten, dann die Befunde mit
  `/ars-revision` einarbeiten.
- [ ] **T** – Fazit, Korrekturlesen, Abgabe.

## 9. Präsentation

Das Konzept steht in [10_praesentation_konzept.md](10_praesentation_konzept.md).

- [ ] **N** – Auf den M4-Stand bringen:
  - **6.1:** M4 = Behavior Cloning, nur PICK klappt auf M4 um, PLACE_INSPECT bleibt bei M2.
  - **1.2:** Kameras (zwei Daheng, eine USB).
  - **2.4:** GUI mit sechs Reitern, neuer Screenshot mit `tools/gui_shot.py`.
  - **Architektur:** zwei Python-Umgebungen.
  - **7.1/7.3:** VM-Übergabetest.
- [ ] **J** – Szene 6.2 füllen. Quellen: `code/m4_behavior_cloning/Berichte/`, `Dokumentation/`.
- [ ] **T** – Offene Szenen: 7.2 Messwerte (nach der Evaluation), 7.4 Ausblick (nach der
  Entscheidung zur Pflegerobotik).
- [ ] **N** – Fotos vom Labor für 7.1, Stand in 7.3 vor dem Vortrag prüfen.
- [ ] **T** – Generalprobe und Zeitbudget, ggf. (k)-Szenen streichen. Montageort der Kamera oben
  in 1.2/3.1 bestätigen.
- [ ] **N** – `public/urdf/collision/` (15 MB) aus `public/` nehmen, dann hat `dist/` ~22 MB.
- [ ] **T** – Endgültigen Titel festlegen.

## 10. Organisation

- [ ] **T** – Abgabetermin, Umfang der Ausarbeitung und Vortragsdauer klären.
