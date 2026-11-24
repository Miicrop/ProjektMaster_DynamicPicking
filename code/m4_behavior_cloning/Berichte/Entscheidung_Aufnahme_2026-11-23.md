# Entscheidungsvorlage Aufnahme 23.11. (Start ~11 Uhr)

Stand 23.11., 8:30. Quellen: MuJoCo-Taktiksimulation (`Dokumentation/MuJoCo-Taktiksimulation-Stand.md`, Abschnitte
9.6–9.24), VM-Läufe G2/G3/G4 (`daten/tabelle_G2_G3_G4.md`), Lernkurve und Datenanalysen in `Testprotokoll.md`.

**Lesart:** Die Sim zeigt **Richtungen**, keine übertragbaren Zahlen. Ein Sim-Unterschied zählt nur, wenn er größer ist
als der Abstand zweier Trainings-Seeds (Basis: 20 und 21 Griffe von 60). VM-Werte streuen zwischen zwei Läufen desselben
Modells stark (G2 am 20.11.: 14,2 mm / 7 Sprünge, am 23.11.: 18,5 mm / 1 Sprung).

## Übersicht

| Punkt | Empfehlung | Beleg | Restrisiko |
|---|---|---|---|
| Endanflug-Tempo | **0,035 m/s durchgehend, keine Abbremsstufe** | **stark** (Sim, 2 Seeds bei 0,05) | Nachlauf/Tischabstand des echten Arms, Bewegungsunschärfe – vorher prüfen |
| Licht Wrist | **beibehalten** (Kameralicht, hell und ruhig) | mittel–stark (Sim V4, Richtung) | keins für heute |
| Export | **nur bis Griff** (`--abschneiden-nach 3`) | stark (real G→G2 und Sim V5) | keins |
| Drehversatz | **Einstellungen wie seit 19.11. 14:27 lassen** (Glättung, 10–20° + Ausreißer) | schwach (Sim V2 ohne Effekt, VM G3/G4 unentschieden) | Sprünge an Gelenk 6 bleiben möglich (7 % der Episoden > 0,35 rad) |
| Alte Daten retten (Kappen/Ausblenden) | **heute nicht entscheiden** – passiert beim Export, später möglich | schwach | – |
| Episodenzahl | **mindestens ~400 mit den neuen Einstellungen**, mehr wenn es zeitlich geht | mittel | Sim flacht ab 400 ab, real stieg die Kurve bis 400 noch |
| Korrektur-Halt (V7) | **nicht übernehmen** | mittel (Sim, 1 Seed) | – |
| Versatz näher am Objekt (V6) | **heute nicht** – Ergebnis gegen 9:00, bei klarem Gewinn erst ab Folgetermin | – | – |

## 1. Endanflug-Tempo – der wichtigste Punkt

| Sim, 60 Testlagen | Griffe | im Trainingsbereich (27) | Annäherung median | nie geschlossen |
|---|---:|---:|---:|---:|
| 0,02 m/s (heute), Seed 0 / 1 | 20 / 21 | 14 / 15 | 10,0 / 10,1 mm | 28 / 37 |
| zweistufig 0,05 → 0,02 | 19 | 13 | 11,7 mm | 34 |
| **0,035 m/s** | **34** | **23** | 5,5 mm | 21 |
| 0,05 m/s, Seed 0 / 1 | 37 / 39 | 23 / 23 | 4,2 / 5,0 mm | 21 / 10 |

- Bei 0,02 m/s bleibt die Policy in der Sim oft 1–2 cm über und ~1 cm neben dem Objekt stehen und schließt nie.
  Zweistufig hilft nicht: Entscheidend ist die Geschwindigkeit auf den **letzten** Millimetern.
- **Real belegt ist nur die Ursache, nicht die Folge:** In den echten Aufnahmen vom 19.11. ändert sich das Wrist-Bild in
  den letzten 10 Takten vor dem Griff relativ halb so stark wie bei C2 (3,6 % gegen 7,2 % der Helligkeit, nach Glättung).
  Ob ein echtes Modell deshalb stehen bleibt, hat noch niemand an der Anlage gesehen.
- 0,035 ≈ 0,05 in der Sim (nicht unterscheidbar, p = 0,13–0,38). 0,035 ist real vorsichtiger:
  Nachlauf beim Experten gemessen 1,1 mm (0,02 m/s) bzw. 3,2 mm (0,05 m/s, p95 4,4) im Abstieg; der Arm kam in **keiner**
  Aufnahme unter die Greifhöhe. Für 0,035 m/s geschätzt ~2 mm (interpoliert, nicht gemessen).
- **Folge:** Daten mit 0,035 m/s passen nicht zum Datensatz vom 19.11. (0,02 m/s). Heute beginnt damit ein **neuer
  Datensatz**; der alte bleibt als Rückfall (G2).
- **Sim-Vorbehalt:** Die Sim heftet das Objekt an, statt es anzustoßen. Geometrisch hätten die Backen in rund der Hälfte
  der Sim-Fahrten das Objekt berührt (9.20) – die Sim-Griffzahlen sind eher zu hoch.

## 2. Drehversatz und die alten Daten

- Nach der Glättung (seit 14:27) liegen 7 % der Episoden über 0,35 rad (vorher 25 %); im Datensatz nur bis Griff 6 %.
- Sim V2 (10–15° ohne Ausreißer): kein Unterschied. Die Sim bildet die seltenen Überschwinger des echten Arms nicht nach,
  kann den Hauptzweck (weniger Sprünge) also nicht prüfen.
- VM, gleiche Bedingungen (GPU frei, 85 ms je Vorhersage, keine Überläufe):

| VM, 39 Val | Annäherung | Gier p90 | Tisch < −10 mm | Sprünge | Endstellung |
|---|---:|---:|---:|---:|---:|
| G2-Kontrolle | 18,5 mm | 49° | 38 % | 1 | 74 % |
| G3 Label gekappt (0,30 rad) | 17,0 mm | 31° | 36 % | 2 | 74 % |
| G4 Takte ausgeblendet | 17,3 mm | 40° | **18 %** | 3 | **85 %** |

  Keiner der beiden Wege senkt die Sprünge nachweisbar; G4 hat die Tendenz zu weniger Tischkontakt und mehr
  Endstellungen, innerhalb der VM-Streuung. **Für heute ohne Bedeutung**, da beides beim Export entschieden wird.
- Empfehlung: Drehversatz-Einstellungen nicht ändern – keine Messung spricht für eine Änderung, die Abdeckung bleibt.

## 3. Licht, Export, Episodenzahl

- **Licht:** dunkle, verrauschte Wrist-Bilder (wie C2) machen die Sim-Policy deutlich schlechter (12 gegen 20/21
  Griffe, p = 0,02), offline sieht man es nicht (Val-MAE gleich). Kameralicht beibehalten.
- **Export nur bis Griff:** real G→G2 deutlich besser, Sim V5 in derselben Richtung.
- **Episodenzahl:** Sim 200 < 400 ≈ 600 ≈ 815 (je 10 000 Trainingsschritte – mit mehr Daten sieht jede Episode weniger
  Training; mehr Schritte nicht getestet). Real (G2 50/75/100 %) stieg die Annäherung bis 400 noch. Mehr Daten helfen
  wahrscheinlich, sind aber nicht die Lösung. Ziel heute: ≥ 400 mit den neuen Einstellungen.

## 4. Vorschlag Anlagentest vor der Aufnahme (~30–60 min)

1. **Pflicht – Tempo prüfen (10–15 min):** 5–10 Probeaufnahmen mit 0,035 m/s auf verschiedenen Lagen.
   Danach rechne ich aus den Aufnahmen in wenigen Minuten Nachlauf, tiefsten Punkt gegen Greifhöhe und Tischabstand aus
   (`nachlauf.py`). Abbruchkriterium: tiefster Punkt < 0 mm oder Nachlauf > 4 mm → auf 0,03 m/s zurück.
2. **Optional – Policy-Test (30–45 min):** G2 und G4 auf ~10 markierten Lagen (±60°, Hälfte mit deutlicher Drehung),
   Override niedrig, Kollisionsmodell aktiv. Notieren: Griff ja/nein. Ich werte Annäherung, Abbruchgrund und vor allem
   **„bleibt über dem Objekt stehen“** aus – das würde die Sim-Erklärung für 0,035 m/s real bestätigen.

## 5. Wenn es schlecht läuft – Folgetermine (max. 4)

| Termin | Ziel | Entscheidung danach |
|---|---|---|
| **heute** | neuer Datensatz 0,035 m/s, ≥ 400 Ep.; Training G5 über Nacht, VM-Test | – |
| **2** | Anlagentest G5 gegen G2 auf festen Lagen; bei Erfolg Datensatz auf ~800 erweitern (gleiche Einstellungen) | greift G5 öfter? schließt es näher am Objekt? |
| **3** | wenn G5 Tischkontakt hat: Tempo 0,03 m/s; wenn es neben dem Objekt hängt: V6 (Versatz bis ~11 mm real), sofern die Sim es bestätigt | – |
| **4** | Reserve / Ergänzung; 360°-Erweiterung erst danach | – |

Was gegen den Plan spräche: Zeigt die Probefahrt bei 0,035 m/s Unterschreitung der Greifhöhe, heute mit 0,03 m/s
aufnehmen. Bestätigt der Policy-Test, dass G2 real **nicht** über dem Objekt hängen bleibt, ist der Tempo-Befund real
weniger sicher – dann wäre ein Teil der Aufnahme mit 0,02 m/s (kompatibel zum alten Datensatz) die vorsichtigere Wahl.
