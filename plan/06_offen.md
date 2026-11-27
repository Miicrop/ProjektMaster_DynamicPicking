# 06 – Offen

**Alle offenen Aufgaben und Fragen an einem Ort.** Erledigtes wandert mit Datum nach
[07_erledigt.md](07_erledigt.md). Die Moduldateien (02–05) enthalten nur Wissen, keine Aufgaben.

> **Zum Abhaken mit Teilschritten und Notizen:** https://claude.ai/artifact/5sR6LYytTSzEgksksYpZ1q

`[ ]` offen · `[~]` angefangen · Wer: N = Niklas, J = Jeremy, T = Team, P1–P3 = Person des Moduls

## Stand (2026-11-24)

- **Die Deadline ist früher als geplant.** Deshalb ist die Liste nach Priorität sortiert:
  A = ohne das keine Abgabe, B = wichtig, C = nur wenn Zeit bleibt.
- Alle vier Module laufen am echten Aufbau: Kameras angebunden, feste Belichtung und fester
  Fokus, Positionskorrektur M1 aus Zeigetests, Greifer über Digitalausgänge. Das Teil wurde
  mehrfach an verschiedenen Positionen gegriffen und geprüft. 121 Tests grün.
- M4: echter Datensatz (602 Episoden), Anlagentest am 16.11., erste Griffe am 23.11. Jeremy
  hat eine eigene ausführliche Doku (`code/m4_behavior_cloning/Dokumentation/LaTeX/Ausfuehrlich`, 77 S.).
- Thesis: Laborfotos eingebaut, Kap. 04–07 auf Laborstand, Ausblick geschrieben.
- **Fehlt vor allem:** kleine Versuchsreihe mit Zahlen, Kap. 08 aus Jeremys Doku, Evaluation,
  Fazit und Kurzfassung, Durchsicht, Präsentation auf den Laborstand.

## Labortag 26.11. (ausgewertet am 26.11.)

- Daten: `code/logs/cycles_20261126.csv`, `code/logs/20261126/` (70 Läufe mit Zwischenbildern),
  GUI-Screenshot. Auswertung: `thesis/tools/eval_20261126.py` → `thesis/figures/eval/`.
- Ergebnis: 25 Zyklen mit Prüfung, 7 Abbrüche alle vor dem Greifen (5× Marker 2 von Hand verdeckt,
  1× gewendet erkannt, 1× Hand als Bauteil → Software-Stopp), 48 Abfragen ohne Bauteil ohne Fehlauslösung.
  Lochmessung: Ellipsen-Fit 0/19 in Toleranz, Kreis-Fit 19/19 (9,67–9,81 mm). Nach dem Fix 21/21 gut.
- Eingearbeitet: Kap. 03 (Kreis-Fit), 05 (Form-/Ruheprüfung, gewendetes Teil), 07 (OCR 300 px,
  Kreis-Fit, Abb. Fit-Vergleich), 09 (Screenshot vom Labor), 10 (neu geschrieben), 11, Kurzfassung.
- [x] **N** – Todos Kap. 10 geklärt: Zykluszeiten durch geänderte Robotergeschwindigkeit, Hand-Fall = 10:34 mit Software-Stopp.
- [x] **N** – Präsentation auf den 26.11. gebracht: neue Blätter 7.4 Labortag 26.11. und 7.5 Lochmessung gelöst, 7.6 Was noch fehlt aktualisiert, Ausblick/Finale jetzt 7.7/7.8 (26.11.).
- „Versuchsreihe 1“ und „GUI-Screenshots mit echten Kamerabildern“ (Labortag unten) sind damit erledigt.

## A – Ohne das keine Abgabe

- [ ] **T** – **Deadline, Umfang der Ausarbeitung und Vortragsdauer** festhalten.
- [x] **N** – **Evaluation (Kap. 10) als Funktionsnachweis** mit den Daten vom 12.11. geschrieben
  (Zeigetests, 7 Zyklen: 7/7 gegriffen, 5 vollständig, OCR und Kerbe 5/5, Urteil 2/5 gut wegen
  Lochmaßstab). Kein weiterer Labortag nötig; der Labortag unten ist nur noch optional.
- [x] **N** – Kap. 08 als Grundgerüst aus Jeremys Doku (Stand 19.11.) neu geschrieben (24.11., 20 S.):
  Punkte CLEAR_FOV/ANFLUG/PRE_PICK/PICK/PRE_PLACE, Objektiv 3,6 mm F8 statt Fischauge, Kameralicht,
  gezielter Versatz, Tisch aus Tischpunkten, Sicherheitsstufen, Versuche bis Anlagentest C2 und Drehbias.
  **Offen (Jeremy):** Abgleich mit seiner Endfassung, neuer Datensatz, Totzeit, Override/Betreuer.
- [ ] ~~**N** – **Kap. 08 (M4) aus Jeremys Doku übernehmen.**~~ Seine Fassung ersetzt den Entwurf
  vom 30.10., gekürzt auf Kapitellänge; die ausführliche Doku als Anhang oder eigenes Dokument.
  Danach mit Jeremy abstimmen, was aus „Verwendung offen“-Berichten rein darf.
- [ ] **J/N** – Kap. 10.5 M2/M4-Vergleich nach Klärung mit Jeremy ergänzen.
- [x] **N** – **Fazit und Ergebnissatz der Kurzfassung** auf Stand 26.11. (26.11.).
- [ ] **N** – Gesamte Arbeit durchsehen, dann `/ars-reviewer`, Befunde mit `/ars-revision` einarbeiten.
- [ ] **T** – Korrekturlesen, Abgabe.
- [x] **N** – **Präsentation auf den Laborstand vom 12.11. gebracht** (24.11.): Bauteil mit Fase auf der
  Etikettseite, Seitenkamera auf der vom Roboter abgewandten Seite, Klebeband-Ablagen, neue Blätter
  3.6 Positionskorrektur, 7.2 Labortag 12.11., 7.3 Messwerte, 7.4 Was noch fehlt. Alle Szenen ohne
  Konsolenfehler. **Offen: Niklas schaut drüber.** Ursprüngliche Liste:
  - `python build_data.py` neu laufen lassen. `data.json` enthält noch den Offset 113° und die
    alten Posen (inspection 520,8 / 199,6 / 42,0, Ablagen z 4/3).
  - Szene 4.4 „23° verdreht“: Offset jetzt −67° (90° + 23° − 180°). Das Teil wird um 180°
    gedreht gegriffen, damit Fase und Seriennummer zur M3-Kamera zeigen. Grund: Mit rz 23° an den
    Stationen stünde Achse 6 bei 178°, ohne IK-Lösung zu den Ablagen.
  - **Positionskorrektur M1** aufnehmen (Thesis Kap. 5.6): 21 Zeigetests, Versatz bis 8 mm nach
    außen, lineares Modell je Achse (x 3,7 % um 227 mm, y 2,0 % um 164 mm), danach 9/11 ohne
    Versatz, max. 2 mm. Passt an die Parallaxe-Stelle in `src/worlds/vision.js` (Akt 3).
  - Feste Belichtung Daheng (15 ms, 0 dB) und fester Fokus Logitech (90), beides im Code.
  - Montagehöhe Kamera oben: Klemme 90 cm, Objektiv ca. 94 cm, Sensor ca. 99 cm über der Platte (1.2/3.1).
  - Ablegen 1 mm über der geteachten Pose; Ablageorte nur mit Klebeband markiert, keine Boxen.
  - Lochmessung an der echten Kamera: 9,57–9,68 mm statt 10 mm; vereinzelt Fehlurteil durch
    Spiegelung/Fensterlicht.
  - Laborfotos aus `media/roh/` für 1.2, 7.1 und die Prüfstation.
  - Ausblick 7.4: Pflegerobotik-Idee wie in Thesis Kap. 11 (gleiche ArUco-Marker wie das Spiel).
- [ ] **T** – Präsentation: 7.2 Messwerte nach der Versuchsreihe, Generalprobe und Zeitbudget,
  ggf. (k)-Szenen streichen, endgültigen Titel festlegen.
- [ ] **J** – Akt 6 der Präsentation prüfen (6.1–6.8) gegen seinen aktuellen Stand.

### Labortag – entfällt (kein Labortermin mehr, Stand 26.11.)

- [x] Versuchsreihe 1 → am 26.11. gefahren (25 Zyklen, Kap. 10).
- [x] Lochmaßstab → durch Kreis-Fit gelöst statt Korrekturfaktor (19/19 in Toleranz).
- [x] GUI-Screenshot mit echten Kamerabildern (Kap. 09, Reiter Ablauf).
- [x] `point_tests.csv` liegt in `code/logs/`.
- [x] Fehlerbehandlung real erprobt (Software-Stopp, Quittieren, 26.11.).
- Entfällt, in Kap. 10 „Grenzen“ bzw. Ausblick benannt: Versuchsreihe 2 mit Fehlerteilen,
  Kalibrierung wiederholen, Wiederholgenauigkeit Prüfposition, Ablesen Objektiv/Logitech-Modell
  (Thesis hat dort keine offenen Lücken), Lastdaten `ZimmerLWR50` (nur Anlagensicherheit, nicht Thesis).
- Abbrüche durch verdeckten Marker im Dauerbetrieb: Systemeigenschaft, vernachlässigt.

**Worauf achten**
- **Marker-Zuordnung:** Passt die Zuordnung von ID zu Ecke nicht zur Config, wird das Bild ohne
  Fehlermeldung falsch entzerrt. Test: Ein Teil nahe der Ecke unten links muss kleine x/y ergeben.
- **Fase nicht gefunden** (Konfidenz 0,5): Das Teil kann an der Prüfstation um 180° verdreht liegen.
- **Fensterlicht** an der Prüfstation: kann das Loch kleiner wirken lassen.

## B – Wichtig

- [ ] **J** – Kap. 08 der Thesis (nach der Übernahme) durchsehen und freigeben; Totzeit des
  Greifers und Override 0,5 (Sicherheitsthema) mit dem Betreuer klären.
- [~] **P1–P3** – Kapitel 05–07 durchsehen; Zwischenfazits mit Zahlen vom 26.11. ergänzt (26.11.).
- [ ] **J** – Freigabe echte Anlage: Im Ablauf ersetzt die Rückfrage „Automatischer Ablauf mit
  dem echten Roboter – M4 Behavior Cloning greift“ das Eintippen von „ANLAGE“. Bestätigen.
- [x] **T** – Fehlerbehandlung am realen System erprobt (26.11.: Software-Stopp, Quittieren).

## C – Nur wenn Zeit bleibt

- [ ] **N** – Vorprojekt GROB (Kap. 02b): Kommilitonen fragen, ob er noch etwas ergänzt. Die
  `\todo`s sind entfernt (24.11.).
- [ ] **T** – Quellen für die Motivation (Kap. 1) und Normen zu Cobots (ISO 10218, ISO/TS 15066):
  vorerst weggelassen, `\todo`s entfernt.
- [x] **N** – GUI-Screenshot Ablauf ersetzt, `\todo` in Kap. 09 entfernt (26.11.).
- [ ] ~~**N** – Video eines kompletten Zyklus.~~ Entfällt, kein Labortermin mehr.
- [ ] **N** – `public/urdf/collision/` (15 MB) aus `public/` der Präsentation nehmen.
- [ ] **J/N** – M4 im Gesamtablauf mit trainiertem Modell (im Ausblick als Dauerlauf-Inferenz erwähnt).

## Verworfen (2026-11-24)

- Intrinsische Kalibrierung / Positionskorrektur ablösen: wäre korrekter, wird nicht mehr
  gemacht; steht im Ausblick.
- Greifer-Rückmeldung (IO-Link): nicht umgesetzt; steht im Ausblick.
- Alles zum Robotiq-Standardgreifer in der Neura-VM. Das Werkzeug `ZimmerLWR50` ist in der VM angelegt.
- USB-Bandbreite aller drei Kameras, Schlüsselschalter Automatikmodus, Belichtung bei Sonne,
  Genauigkeitsmessung M1 (Zeigetest deckt das ab), Spielraum der Greiferbacken als eigener Test.
- Englisches Abstract (nicht benötigt). Pflegerobotik: entschieden, nur im Ausblick.
