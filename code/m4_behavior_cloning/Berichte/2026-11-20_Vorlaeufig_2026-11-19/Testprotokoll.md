# Vorläufiges Modell G auf den Daten vom 19.11. (2026-11-20)

**Daten:** `data/2026-11-19`, neu aufgenommen mit Kamerabeleuchtung, mehr Rauschen im Anflug und langsamerer Fahrt
(Anflug 0,02 m/s). Export nach `datasets/2026-11-19`: 399 Episoden, 57 550 Frames. 2 Episoden wurden wegen
Schleppfehler > 0,30 rad verworfen. Die Meldung „fehlt in 399 Episoden“ betrifft nur `execution/*`-Schlüssel des Modus
„online“. Aufgenommen wurde im Modus `servo_j`, die Meldung ist also harmlos.

**Training:** `checkpoints/G_licht_langsam_2026-11-19`, gleiche Einstellungen wie C2 (10 000 Schritte, Batch 128,
Seed 0, Val 10 % → 360/39 Episoden), Dauer 156 min. Log: `logs/train_G.log`.

| Validierung (eigene Val-Episoden) | Val-Loss | Gelenk-MAE | p95 | Greifer |
|---|---:|---:|---:|---:|
| C2 (var_C2) | 0,0112 | 0,0081 rad | 0,0308 | 97,6 % |
| **G** (2026-11-19) | **0,0002** | **0,0058 rad** | **0,0219** | **99,9 %** |

Die Val-Zahlen sind nur grob vergleichbar, denn die Val-Episoden stammen aus verschiedenen Datensätzen.

## Offline-Test auf `data/2026-11-19-2` (7 Episoden, in keinem Training)

`skripte/test_offline.py`: Bilder und Zustand der Demo, alle 2 Takte ein Chunk (8 Takte), je 4 Ziehungen. Verglichen
werden die Chunks mit den aufgezeichneten Aktionen. „Nah“ = TCP weniger als 60 mm über dem Griff, vor dem Schließen.
„Griffpunkt“ = vorhergesagte Werkzeugspitze am Schließtakt gegen die Demo. Rohdaten: `daten/test_offline.json`.

| | Gelenk-MAE | TCP median / p95 | nah median / p95 | Griffpunkt xy median / p90 | Griff z median | Greifer |
|---|---:|---:|---:|---:|---:|---:|
| **G**, ganze Episode | 0,0065 rad | 4,0 / 12,2 mm | 3,4 / 6,4 mm | 3,3 / 5,6 mm | −0,4 mm | 99,4 % |
| **G**, bis Griff | 0,0066 rad | 3,9 / 11,1 mm | | | | 99,2 % |
| C2, bis Griff | 0,0234 rad | 11,4 / 24,9 mm | 10,3 / 19,5 mm | 6,2 / 12,7 mm | +0,8 mm | 95,9 % |

C2 ist hier benachteiligt: Es kennt die Beleuchtung nicht und hat nur bis 3 Takte nach dem Schließen gelernt. Deshalb
wird C2 nur bis zum Griff verglichen. Der Abstand zu G ist trotzdem groß: Im Nahbereich ist G etwa 3-mal genauer, am
Griffpunkt etwa 2-mal.

**Grenzen:**
- 7 Episoden sind wenig, und sie stammen vom selben Tag wie die Trainingsdaten (gleiches Licht, möglicherweise gleiche Lagen).
- Der Test ist offen: Das Modell sieht immer die Demo-Bahn, Fehler wirken nicht auf die nächsten Bilder zurück.
- Ob G an der Anlage genauer greift, zeigen erst VM-T60 (`stufe2_vm.py`) und die Anlage.

## VM-Replay (12:38–12:53, `skripte/kette_vm_G.sh`, GEOFENCE=alt, `--transport-geplant`)

Die Bilder kommen aus der Aufnahme (je Takt ein Bild, nicht an die Fahrt gekoppelt). Den Zustand liefert die VM.

| Modell | Bilder | Fahrten | nächste Annäherung median | ≤ 10 mm | Greif-xy median | unter Tisch | < −10 mm | Endstellung |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C2 | T60 (11.11., eigene Art) | 59 | 15,5 mm | 32 % | 18,7 mm | 47 % | 37 % | 90 % |
| **G** | 19-2 (eigene Art) | 7 | 21,7 mm (n = 4) | 0 | 35,8 mm | 71 % | 57 % | 57 % |
| C2 | 19-2 (fremd) | 7 | 39,1 mm (n = 2) | 0 | 41,1 mm | 86 % | 71 % | 29 % |
| G | T60 (fremd) | 59 | 60,0 mm | 4 % | 72,8 mm | 25 % | 22 % | 44 % |

- Auf den fremden Bildern brechen beide Modelle ein. G auf T60 greift weit daneben (60 mm), bleibt aber öfter über dem
  Tisch. Die alten Bilder zeigen weder die Beleuchtung noch die langsame Fahrt. Bild und Zustand laufen deshalb schnell
  auseinander.
- Auf 19-2 ist G besser als C2, kommt aber nicht an C2 auf T60 heran. Bei nur 7 Fahrten lässt sich nicht trennen, ob
  das an G liegt oder ob diese 7 Lagen im Replay schwierig sind.
- Typisches Fehlerbild von G auf 19-2: Im schnellen Abschnitt läuft der Arm über das Ziel hinaus (Ep. 3: 40 mm, dann
  unter den Tisch) oder liegt 30–50 mm seitlich (Ep. 1). Der Nachlauf von Kommando zu Ist liegt mit bis 0,3 rad im
  Rahmen der Demos.
- **Der Offline-Gewinn (Faktor 2–3) zeigt sich in der VM nicht.** Wie schon am 17.11. festgestellt: Ohne Rückkopplung
  der Bilder sagt das VM-Replay für andere Modelle als C2 wenig vorher. Aussagekräftig wäre ein VM-Lauf auf den
  39 Val-Episoden von G (eigene Art, n größer) oder die Anlage.

## VM-Replay auf den 39 Val-Episoden von G (13:05–13:20)

13 Lagen (B14 … B133) mit je 3 Wiederholungen. Diese Lagen sind in keinem Training, die Bilder sind von derselben Art wie
die Trainingsdaten. Rohdaten-Indizes: `daten/val_episoden_rohdaten.txt`.

Der erste Versuch (`rollouts/vm_val39_ungueltig_arm_steht`) ist ungültig. Die VM nahm `move_to_joints` an, aber keine
servo_j-Ziele (Arm stand in jeder Fahrt ab Takt 1), auch bei der Episode, die um 12:38 noch gefahren war. Nach einem
Neustart der VM lief alles normal.

| | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy median | Gier-Fehler median / p90 | unter Tisch | < −10 mm | ServoGuard | Sprung > 0,35 rad | Endstellung |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C2, T60 | 59 | **15,5 mm** | **32 %** | 45 mm | **18,7 mm** | **10,9° / 29°** | **47 %** | 37 % | 7 % | **0** | **90 %** |
| G, Val 39 | 39 | 19,6 mm | 11 % | **29 mm** | 24,8 mm | 15,5° / 50° | 59 % | 36 % | 10 % | 4 | 72 % |

- **G ist in der VM nicht genauer als C2, eher etwas schlechter.** Nur die Streuung nach oben ist kleiner (p90 29 statt
  45 mm).
- Neues Fehlerbild: 4 Fahrten brechen nach 55–90 Takten ab, weil G ein Ziel mehr als 0,35 rad von der Ist-Stellung
  entfernt kommandiert (meist Gelenk 2 oder 6). C2 hatte das in T60 nie.
- Die Drehung beim Griff ist ungenauer (median 15,5° statt 10,9°, p90 50° statt 29°).
- Vorbehalt: verschiedene Lagen (Val 39 gegen T60). Die Bilder laufen im Replay starr nach der Aufnahme ab. Bei der
  langsamen Fahrt von G passen Bild und Zustand länger nicht zusammen, wenn der Arm abweicht. Das kann G im Replay
  stärker benachteiligen als an der Anlage.

**Fazit vorläufig:** Offline ist G 2–3-mal genauer, in der VM nicht. Ob die neuen Daten an der Anlage helfen, kann nur
ein Anlagentest zeigen. Vorher lohnt ein Blick auf die Sprung-Abbrüche (Ep. 163, 274, 295, 380).

## Ursache der Sprung-Abbrüche: Drehversatz im Anflug

Alle 4 Abbrüche betreffen **Gelenk 6** (Ziel 0,352–0,365 rad von der Ist-Stellung, Grenze `SERVO_MAX_TARGET_GAP_RAD`
= 0,35). Alle 4 Episoden haben den neuen **Drehversatz im Anflug** (12–22°, `anflug_drehung_grad`).

Beim Drehversatz bleibt das Label die Idealbahn (`Training-und-Inferenz.md`). Ist das Werkzeug um 20–35° verdreht,
zeigt das Label für Gelenk 6 also 0,35–0,6 rad von der Ist-Stellung weg. G hat gelernt, genau dahin zu kommandieren. Mit
einem Ziel über 0,35 rad lehnt die Inferenz ab.

| Teil des Datensatzes | Frames | q6 Label − Ist p99 | max | Frames > 0,35 rad |
|---|---:|---:|---:|---:|
| var_C2 (alt) | 52 088 | 0,205 | 0,362 | – |
| 19.11. ohne Drehversatz | 28 490 | 0,172 | 0,360 | 4 |
| 19.11. mit Drehversatz, **vor** 14:27 (ohne Glättung) | 7 723 | 0,401 | 0,506 | 141 |
| 19.11. mit Drehversatz, **nach** 14:27 (Glättung) | 21 337 | 0,321 | 0,519 | 94 |

- Die Glättung im Commit `edde16d` (19.11. 14:27: 12 statt 20 °/s, 0,8 s Glättung, Beginn bei 30 cm) hilft, löst das
  Problem aber nicht. Die Ausreißer bis 35° liegen auch danach über der Grenze. Die 4 abgebrochenen Fahrten stammen alle
  aus der Zeit nach 14:27.
- 108 Episoden (Export 0–107, 13:03–14:27) sind noch ohne Glättung aufgenommen. Von den Val-Episoden gehören nur
  39–41 dazu.
- VM-Ergebnis getrennt nach Drehversatz:

| G, Val 39 | Fahrten | nächste Annäherung median | Greif-xy | Gier-Fehler median / p90 | Sprung | Endstellung |
|---|---:|---:|---:|---:|---:|---:|
| ohne Drehversatz | 16 | 17,5 mm | 25,2 mm | **4,5° / 7°** | 0 | 75 % |
| mit Drehversatz | 23 | 19,6 mm | 24,4 mm | 43,7° / 56° | 4 | 69 % |
| C2, T60 (zum Vergleich) | 59 | 15,5 mm | 18,7 mm | 10,9° / 29° | 0 | 89 % |

  Ohne Drehversatz dreht G deutlich genauer als C2 (4,5° statt 10,9°). Mit Drehversatz liegt der Gier-Fehler bei
  ~40°, unabhängig vom Vorzeichen des Versatzes. Das ist großenteils ein Replay-Artefakt: Die Bilder zeigen den
  Versatz der Demo, den der VM-Arm gar nicht hat.

## Training über die ganze Episode

G wurde auf den **vollständigen** Episoden trainiert, inklusive Anheben nach dem Griff: 29 % der Frames, je Episode
~40 Takte. C2 endet 3 Takte nach dem Schließen (3 % der Frames). In der VM (`--transport-geplant`) wird dieser Teil von G
gar nicht genutzt. Für einen fairen Vergleich mit C2 fehlt also noch eine Variante „G nur Griff“
(`tools/export_variante.py --abschneiden-nach 3`).

## G2: wie G, nur bis 3 Takte nach dem Griff (wie C2)

`tools/export_variante.py --abschneiden-nach 3` → `datasets/2026-11-19_nur_griff` (399 Episoden, 42 010 statt 57 550
Frames). Endstellung: `UEBER_TISCH`, denn der Ablauf `pick_bis_griff` hat kein `PRE_PLACE`. Das Skript wurde dafür
ergänzt. Training `checkpoints/G2_licht_langsam_nur_griff`: gleiche Einstellungen, gleicher Val-Split wie G, 3 h.
Validierung: Gelenk-MAE 0,0058 rad, Greifer 98,2 %.

**Offline (19-2, bis Griff):** TCP median 3,7 mm, nah 2,6 mm, Griffpunkt xy median 2,2 mm (G 3,3, C2 6,2), Griff z
+3,5 mm (G −0,4).

**VM, 39 Val-Episoden** (17:00–17:12, `skripte/vm_robust.sh`, ohne VM-Hänger. Ein erster Lauf um 16:50 hing ab
Fahrt 9 und liegt als `vm_val39_ungueltig_ab_fahrt9` daneben):

| | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy | Gier median / p90 | Tisch < 0 | < −10 mm | Sprung | Endstellung | Querabw. | Welligkeit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C2, T60 | 59 | 15,5 mm | 32 % | 45 | 18,7 | 10,9° / 29° | 47 % | 37 % | 0 | **89 %** | 35,6 | 14,6 |
| G, Val | 39 | 19,6 mm | 10 % | **29** | 24,8 | 15,5° / 50° | 58 % | 35 % | 4 | 71 % | 42,0 | 11,2 |
| **G2, Val** | 39 | **14,2 mm** | **44 %** | 32 | **16,8** | 9,7° / 51° | **43 %** | **17 %** | 7 | 64 % | **33,5** | **8,0** |
| G2 ohne Drehversatz | 16 | 14,8 mm | 33 % | **19** | 16,1 | **5,5° / 10°** | 37 % | 18 % | 1 | 75 % | 23,2 | 7,8 |
| G2 mit Drehversatz | 23 | 9,5 mm | 53 % | 39 | 18,1 | 34,8° / 65° | 47 % | 17 % | 6 | 56 % | 35,4 | 12,3 |

- **Nur bis zum Griff zu trainieren lohnt sich deutlich** (G → G2): nächste Annäherung 19,6 → 14,2 mm, ≤ 10 mm 10 →
  44 %, unter −10 mm 35 → 17 %, Welligkeit 11,2 → 8,0 mm.
- **G2 gegen C2:** genauer (Annäherung, ≤ 10 mm, Greif-xy), deutlich seltener tief unter dem Tisch (17 statt 37 %) und
  ruhiger (Welligkeit 8,0 statt 14,6 mm). Ohne Drehversatz dreht G2 auch deutlich genauer (5,5° statt 10,9°).
  Vorbehalt: andere Lagen (Val gegen T60).
- **Schwachpunkt bleiben die Sprung-Abbrüche an Gelenk 6:** 7 von 39 (6 davon mit Drehversatz). Deshalb erreichen nur
  64 % die Endstellung (C2 89 %). Ursache wie bei G: Das Label der Idealbahn liegt bei Drehversatz bis 0,52 rad von
  der Ist-Stellung.

## Einordnung: Ist G2 wirklich besser als C2?

**Belastbar ist nur G → G2:** gleiche Daten, gleiche 39 Testfahrten, genau eine Änderung (Episode endet am Griff).

**G2 gegen C2 ist kein sauberer Vergleich.** Beide fahren auf verschiedenen Testlagen mit verschiedenen Bildern. Die
Val-Lagen von G2 sind leichter, was die Drehung angeht:

| Testsatz | Fahrten | nötige Drehung median | p90 | > 90° | Weg xy median | Takte bis Griff |
|---|---:|---:|---:|---:|---:|---:|
| T60 (C2) | 59 | 34° | 83° | 6 % | 248 mm | 77 |
| Val 39 (G/G2) | 39 | 27° | 51° | 0 % | 294 mm | 105 |

- Der kleinere Gier-Fehler von G2 (5,5° gegen 10,9°) liegt also zumindest teilweise an den leichteren Lagen.
- Die Fehlerwerte offline und die Val-Werte des Trainings (Gelenk-MAE) sind bei langsamerer Fahrt von selbst
  kleiner, weil sich pro Takt weniger bewegt. Für den Vergleich G2 gegen C2 taugen sie nicht.
- Seltener unter dem Tisch (17 gegen 37 %) und ruhiger: Das passt zur langsameren Fahrt, ist also vermutlich ein
  echter Effekt der neuen Einstellungen. Im Replay ist es aber nicht von den Testlagen zu trennen.
- Fazit: G2 ist **nicht schlechter** als C2 und bei Tisch und Welligkeit vermutlich besser. „Genauer als C2“ lässt
  sich daraus nicht belegen. Belegen kann das nur ein Test unter gleichen Bedingungen: an der Anlage auf denselben
  Lagen oder in einer Simulation mit gerenderten Bildern.

## Wie viele Daten enthalten die Sprünge an Gelenk 6?

Je Episode: größter Abstand zwischen Label und Ist-Stellung an Gelenk 6 (Grenze der Inferenz 0,35 rad).

| Teil | Episoden | größter Abstand median | Episoden > 0,35 rad | Episoden > 0,25 rad | Frames > 0,35 rad |
|---|---:|---:|---:|---:|---:|
| ohne Drehversatz | 197 | 0,10 rad | 1 (1 %) | 4 | 0,01 % |
| Drehversatz, **vor** Glättung (13:03–14:27) | 55 | 0,31 rad | **14 (25 %)** | 42 (76 %) | 1,83 % |
| Drehversatz, **nach** Glättung | 147 | 0,27 rad | 10 (7 %) | 98 (67 %) | 0,44 % |
| – davon \|Dreh\| < 15° | 64 | 0,23 rad | 2 (3 %) | 16 (25 %) | 0,16 % |
| – davon 15–20° | 60 | 0,29 rad | 5 (8 %) | 59 (98 %) | 0,45 % |
| – davon 20–25° | 10 | 0,32 rad | 1 (10 %) | 10 | 0,67 % |
| – davon ≥ 25° (Ausreißer) | 13 | 0,31 rad | 2 (15 %) | 13 | 1,58 % |

- Die Glättung wirkt: Der Versatz wird langsamer aufgebaut und erreicht seine volle Größe nicht ganz (0,0074 rad je
  Grad statt 0,0175). Episoden über der Grenze: 25 % → 7 %.
- Mit Glättung **und** Versatz unter 15° liegen nur noch 3 % der Episoden über 0,35 rad, aber 25 % über 0,25 rad.
  Ab 15° liegt fast jede Episode über 0,25 rad.
- Für die neue Aufnahme: Glättung beibehalten und den Drehversatz auf etwa 10–15° begrenzen, ohne Ausreißer bis 35°.
  Alternativ das Label an Gelenk 6 beim Training begrenzen. Das müsste man vorher an einem Modell prüfen.
- Ob die Sprünge an der Anlage schaden, ist offen. Im Replay zeigen die Bilder den Versatz der Demo, den der VM-Arm
  nicht hat. Die Policy will dann einen Versatz korrigieren, den es gar nicht gibt. Das übertreibt den Effekt.

## Lernkurve: 50 % und 75 % der G2-Daten

Gleich wie G2 (Datensatz `datasets/2026-11-19_nur_griff`, Val-Split, Seed 0, 10 000 Schritte, Batch 128), nur ein Teil
der **Trainings-Lagen** (`lernkurve/gewichte_50.json` und `gewichte_75.json`; ganze Lagen, verschachtelt, die 50 % sind
in den 75 % enthalten). Die 39 Val-Episoden sind bei allen drei gleich. `skripte/kette_lernkurve.sh`, Trainings je
~3 h, VM 23:14–23:37 ohne VM-Hänger. Tabelle mit `skripte/tabelle_val39.py --split`.

**Validierung beim Training (gleiche Val-Episoden):**

| Modell | Trainings-Episoden | Gelenk-MAE | p95 | Greifer |
|---|---:|---:|---:|---:|
| L50 (`checkpoints/G2_lernkurve_50`) | 179 | 0,0090 rad | 0,0347 | 98,1 % |
| L75 (`checkpoints/G2_lernkurve_75`) | 272 | 0,0069 rad | 0,0272 | 98,2 % |
| G2 (100 %) | 360 | 0,0058 rad | 0,0228 | 98,2 % |

**VM, 39 Val-Episoden:**

| | Fahrten | nächste Annäherung median | ≤ 10 mm | p90 | Greif-xy | Gier median / p90 | Tisch < 0 | < −10 mm | Sprung > 0,35 | andere Abbrüche | Endstellung | Querabw. | Welligkeit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| L50 | 39 | 23,2 mm | 7 % | 39 | 27,5 | 18,6° / 56° | 41 % | 26 % | 4 | 4 | 77 % | 42,0 | 10,1 |
| L75 | 39 | 16,8 mm | 21 % | 40 | 18,8 | 14,5° / 45° | 41 % | 23 % | 4 | 2 | 85 % | 32,5 | 8,5 |
| G2 (100 %) | 39 | **14,2 mm** | **44 %** | **32** | **16,8** | **9,7°** / 51° | 44 % | **18 %** | 7 | 4 | 64 % | 33,5 | **8,0** |
| L50 ohne Drehversatz | 16 | 19,9 mm | 15 % | 29 | 22,7 | 7,8° / 17° | 38 % | 25 % | 0 | 2 | 81 % | 30,4 | 7,9 |
| L75 ohne Drehversatz | 16 | 10,6 mm | 40 % | 47 | 15,7 | 2,9° / 12° | 38 % | 19 % | 0 | 1 | 94 % | 17,6 | 6,3 |
| G2 ohne Drehversatz | 16 | 14,8 mm | 33 % | 19 | 16,1 | 5,5° / 10° | 38 % | 19 % | 1 | 3 | 75 % | 23,2 | 7,8 |
| L50 mit Drehversatz | 23 | 29,7 mm | 0 % | 45 | 38,1 | 31,1° / 72° | 43 % | 26 % | 4 | 2 | 74 % | 55,4 | 13,0 |
| L75 mit Drehversatz | 23 | 19,5 mm | 6 % | 37 | 20,2 | 35,5° / 60° | 43 % | 26 % | 4 | 1 | 78 % | 37,4 | 10,9 |
| G2 mit Drehversatz | 23 | 9,5 mm | 54 % | 39 | 18,1 | 34,8° / 65° | 48 % | 17 % | 6 | 1 | 57 % | 35,4 | 12,3 |

„Sprung > 0,35“: die Inferenz lehnt ein Ziel ab, das mehr als 0,35 rad von der Ist-Stellung liegt. „Andere Abbrüche“:
die VM verweigert servo_j („Stopp angefordert“, „Servo-Interface ist nicht aktiv“). Die G2-Zeile weicht bei Tisch < 0
und < −10 mm um einen Prozentpunkt von der Tabelle oben ab (Rundung), sonst gleich.

- **Mehr Daten helfen, und die Kurve flacht bis 400 Episoden noch nicht ab.** Val-MAE 0,0090 → 0,0069 → 0,0058 rad.
  In der VM sinkt die nächste Annäherung von 23,2 über 16,8 auf 14,2 mm, und ≤ 10 mm steigt von 7 über 21 auf 44 %.
  Greif-xy und Gier-Fehler werden ebenfalls kleiner, Tisch < −10 mm geht von 26 auf 18 % zurück.
- Den größten Gewinn haben die Fahrten **mit Drehversatz**: Annäherung 29,7 → 19,5 → 9,5 mm, ≤ 10 mm 0 → 6 → 54 %.
  Fahrten ohne Versatz sind schon mit 75 % etwa so gut wie mit 100 % (10,6 gegen 14,8 mm, Gier 2,9° gegen 5,5°).
  Bei 16 Fahrten liegt das innerhalb der Streuung. Korrekturen nach einem Versatz brauchen also mehr Beispiele als
  die gerade Anfahrt.
- **Die Endstellung erreichen L50 und L75 häufiger** (77 und 85 % gegen 64 %), weil weniger Sprung-Abbrüche
  auftreten (4, 4 gegen 7). Bei so wenigen Fällen ist das nicht von Zufall zu trennen. Eine Erklärung wäre, dass G2
  stärker auf die Versatz-Korrekturen reagiert und dabei die Labels mit großem Abstand an Gelenk 6 nachbildet.
  Die neuen Sprünge an Gelenk 2 und 5 (L50, L75) liegen knapp über der Grenze (0,351–0,397 rad).
- **Vorbehalte:** ein Seed je Stufe, 39 Fahrten, VM-Replay mit starren Bildern. Die Richtung ist über alle Kennzahlen
  gleich und bei 50 → 100 % deutlich (≤ 10 mm 7 gegen 44 %). Der Schritt 75 → 100 % ist kleiner und einzeln unsicher.
- **Für den Aufnahmetermin:** 400 Episoden sind eher zu wenig. Wie viele genug sind, sagt diese Kurve nicht, weil
  sie noch nicht flach wird. Das soll V1 der MuJoCo-Taktiksimulation klären (100 / 200 / 400 / 800 Episoden). Der
  Bedarf hängt vor allem am Drehversatz: Wird er wie empfohlen auf 10–15° begrenzt, braucht es vermutlich weniger
  Korrektur-Beispiele.

## Anlagentest 24.11. – Vergleich G2 / G2c / G2b (Reiter Vergleich)

Lauf `vergleiche/2026-11-24_15-39-34`: 8 Lagen, je Modell 2 Fahrten, Weißabgleich fest (Rotstich-Werte), Glättung neu.
G2c auf Lage 8 fehlt (Abbruch: Arm fuhr nicht los). Messpunkt ist der Probe-Stopp, kein echter Griff.
Strenges Maß (`skripte/backen_spiel.py`): Rest je Backe = 2,55 mm − |Versatz in Schließrichtung| − 7,5 mm·|sin ΔGier|.

| Modell | Fahrten | xy median / max | quer median / max | Rest median | Erfolg alt (xy ≤ 10) | Rest ≥ 0,5 mm | Backe auf Objekt (Rest < 0) |
|---|---:|---:|---:|---:|---:|---:|---:|
| G2 (399 Ep.) | 16 | 3,8 / 13,1 mm | 2,1 / 7,5 | +0,3 | 14 | **7** | 5 |
| G2c (579 Ep.) | 14 | 3,6 / 11,6 mm | 1,9 / 6,2 | +0,6 | 12 | **8** | 4 |
| G2b (579 + 40 DAgger) | 16 | 2,2 / 7,6 mm | 1,4 / 7,2 | +1,0 | 16 | **13** | 2 |

- Das alte Erfolgslabel (xy ≤ 10 mm) ist zu großzügig: 14/16 bei G2, aber nur 7/16 mit genug Backen-Spiel.
- Wiederholbarkeit Fahrt 1 ↔ 2 je Lage 1–2 mm: Die Fehler sind lagenabhängig (systematisch), kein Rauschen.
- G2 und G2c scheitern an denselben Lagen (3 und 5, 5–6 mm quer), G2b greift dort sauber; G2b scheitert an Lage 7 (7 mm quer).
- Ergebnis unabhängig von der angenommenen Backenachse (23°/28°/118°: G2b 12–13, G2 6–7, G2c 6–8 von 16/14).
- Nur 8 Lagen: Tendenz G2b > G2c ≈ G2, nicht abgesichert. Vorhersage ~115 ms, ~16 Überläufe je Fahrt (gültig).
