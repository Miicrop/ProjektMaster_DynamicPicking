# Versuchsreihe Policy-Varianten – Versuchsplan

> **Verwendung offen:** Ob diese Reihe in den finalen Bericht kommt oder für eine andere Arbeit aufgehoben
> wird, ist noch nicht entschieden (Anwender, 2026-11-13). Deshalb getrennt von der übrigen Doku.

*Angelegt 2026-11-13. Ausgangspunkt: Testprotokoll `Berichte/2026-11-13_VM-Replay_Daten-2026-11-11.pdf`.*

## Ziel

Die im VM-Replay gefundenen Probleme des Checkpoints 2026-11-09 mit den **vorhandenen** Aufnahmen beheben
und jede Maßnahme einzeln messen:

| Problem (Testprotokoll 13.11.) | Vermutete Ursache | Maßnahme |
|---|---|---|
| Abtauchen unter den Tisch, meist ~0,7 s nach dem Schließen beim seitlichen Wegfahren | 0,5-s-Pause am Greifpunkt: gleicher Zustand, mal „bleiben“, mal „los“; Mitteln der Chunks ergibt eine Abkürzung | B: Pause kürzen · C: nach dem Greifen abschneiden, Transport geplant · Inferenz: anders mitteln |
| ServoGuard-Abbrüche, alle im Transport | Transport ist der unsicherste Teil der gelernten Bahn | C |
| Greifpunkt Median ~11 mm, Ausreißer > 40 mm | Mehrdeutige Greifdrehung (2 Lösungen für ein Bild), kurzes Training | D: eine Drehung · E: länger trainieren |
| Geofence wirkungslos | Checkpoint ohne Tischdaten | jeder neue Export schreibt `table`/`tcp_envelope` in `bc_policy.json` |

## Feste Testlagen

`testlagen.json` (`skripte/testlagen.py`): 20 der 50 Lagen vom 11.11., gleichmäßig über Position und Drehung
gewählt. Sie kommen in **keine** Trainingsvariante.

* **T60** – alle 59 nutzbaren Episoden der 20 Lagen (Variantenvergleich)
* **T20** – je Lage die Wiederholung mit dem kleinsten Rauschfaktor (schnelle Vergleiche)
* Testlagen: B03, B05, B11, B12, B13, B15, B16, B20, B25, B32, B33, B34, B35, B37, B38, B39, B40, B42, B43, B48

## Varianten

Gemeinsam: Quellen `data/2026-11-02`, `-03`, `-09`, `-11` ohne Testlagen, Rezept wie Checkpoint 2026-11-09
(Batch 128, lr 1e-4, bf16), Export mit `tools/export_variante.py`. **Je Variante eine Änderung gegenüber A.**

| Variante | Datensatz | Episoden | Training | Prüft |
|---|---|---:|---|---|
| A Basis | alle, ohne Testlagen | 694 | 10 000 Schritte | Bezugspunkt; Effekt der Daten vom 11.11. |
| B Pause kurz | wie A, `--pause-behalten 3` (8 → 3 Stillstands-Takte) | 694 | 10 000 | Mehrdeutigkeit am Greifpunkt |
| C Nur Griff | wie A, `--abschneiden-nach 3` (Episode endet 3 Takte nach dem Schließbefehl; Endstellung im Export = Station PRE_PLACE); Inferenz mit `--transport-geplant` | 694 | 10 000 | Aufgabe teilen |
| D Eine Drehung | wie A, `--eine-drehung` (165 gedrehte Demos weg) | 529 | 10 000 | Mehrdeutige Greifdrehung (Achtung: auch weniger Daten) |
| E Lang | beste aus A–D | – | 40 000 | Trainingslänge |
| I Inferenz | Checkpoint 2026-11-09 (später A) | – | – | `--decay 0.5`, `--replan 4`, ohne Mitteln (`--no-ensemble --replan 8`) |

GPU-Zeit (RTX 5070 Ti, 10 000 Schritte ≈ 77 min): A, B, D ≈ 4 h, E ≈ 5 h; Export je Variante vorab.

## Bewertung

**VM (alle Varianten):** `skripte/stufe2_vm.py` (= `apps/infer.py --replay` + Tool-Versatz der VM) auf T60,
Auswertung `skripte/eval_stufe2.py` und `skripte/schwingen.py`. Kennzahlen:

1. Nächste Annäherung an PICK (±15 Takte) – Median, Anteil ≤ 10 mm, p90
2. Fahrten unter der Tischfläche, tiefer als −10 mm
3. ServoGuard-Abbrüche
4. Querabweichung/Welligkeit im Anflug
5. Endstellung erreicht

Grenzen wie im Testprotokoll 13.11.: Bilder reagieren nicht auf den Arm; der Greifzeitpunkt kommt mit „Bild
je Takt“ aus dem Bild. Die VM taugt für den **Vergleich** der Varianten, nicht für absolute Anlagenwerte.

**Anlage (beste 1–2 Varianten, fährt der Anwender):** nur mit Tischfläche im Kollisionsmodell (`infer.py`
meldet „Kollisionsmodell: Tisch …“), niedriger Override, zuerst mittige Testlagen. Je Lage gleiche Zahl an
Versuchen; Protokolle (`rollouts/…`) werden mit denselben Skripten ausgewertet, ergänzt um Greiferfolg
(Sichtprüfung) und Schutzstopps.

## Stand

| Schritt | Stand |
|---|---|
| Testlagen festgelegt | erledigt 13.11. |
| Werkzeug `tools/export_variante.py` | erledigt 13.11. (Trockenlauf aller Regeln) |
| I: Inferenz-Vergleich mit Checkpoint 2026-11-09 auf T60 | erledigt 13.11. (decay 0,5 und replan 4 schlechter; „ohne Mitteln“ wegen VM-Ausfall offen) – `Protokoll.md` |
| C: Inferenz-Umschaltung | erledigt 13.11.: `apps/infer.py --transport-geplant` (Policy endet mit dem Schließbefehl, dann 0,5 s Dwell, 5 cm senkrecht anheben, PTP zur Station; Planer, IK und Kollisionsprüfung wie bei der Aufnahme). Probelauf am SimRobot (`skripte/probe_transport.py`): Station exakt, 45 mm Hub mit 3,5 mm seitlich, max. 0,31 rad/s; Tests `test_apps`, `test_replay`, `test_execution` grün |
| Export/Training A–D | erledigt 14.11. 04:18 (je 3,0–3,3 h, Datenladen bremst) |
| VM-Vergleich A–D auf T60 | erledigt 14.11. 05:41 (nach Geofence-Fix in `stufe2_vm.py`) – `Protokoll.md`: alle neuen Varianten ungenauer als 2026-11-09, C/B senken Tisch-Abtauchen |
| Kontrolle Trainingsstreuung (alter Datensatz, Seed 1) | erledigt 14.11. 09:27: Streuung klein (10,6 mm wie Seed 0) – die Daten vom 11.11. verschlechtern A–D wirklich; Ursache offen (Daten unauffällig, Replay-Artefakt nur teilweise) |
| C′: C auf dem alten Datensatz | fertig 14.11. 23:18 (VM in zwei Teilen, 29 + 30 Fahrten): 15,5 mm, Greif-xy 18,7 mm (alt 18,0–18,6), Endstellung 90 %, ServoGuard 7 %; je Lage gegen alt 13/7 (p = 0,26), gegen C 4/16 (p = 0,012) – bisher bester Kandidat |
| F: A + Licht-Augmentierung | fertig 14.11. 23:39 (`skripte/kette_F2.sh`, Schalter `apps/train.py --licht-augment`, Bereiche siehe Protokoll): 14,9 mm, je Lage gegen A 10/10 (p = 1,0) – Augmentierung holt die Genauigkeit nicht zurück, Lichtvermutung nicht bestätigt |
| E | offen – erst nach C′ entscheiden |
| Anlage | offen |
