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

## Anlagentest 23.11.

**Kernaussagen**

- **Aufnahmetempo: 35 mm/s.** Keine Probeaufnahme (30/35/40 mm/s) schwang unter den tiefsten Soll-Punkt
  (min +0,07 mm). Der Nachlauf lag überall unter 4 mm (35 mm/s: median 1,6, max 2,6 mm). 40 mm/s besteht ebenfalls,
  hat aber doppelten Seitenversatz und lag nach konservativer Umrechnung knapp bei 4 mm.
- **Pendelt die echte Policy? Ja, mäßig. Schleichen im Sinne der Sim gab es nicht.** Die Policies fahren im Bereich 30–60 mm
  mit 50–70 mm/s (Experte dort 15–20 mm/s). Netto nähern sie sich aber nur mit 5–15 mm/s (median je Modell), weil sie
  seitlich und auf und ab pendeln. Das sind 2–4 Umkehrungen der Annäherung je Fahrt (Experte 0), der Weg ist 1,7–2,0-mal so lang
  wie nötig. In keiner Fahrt blieb die Policy über der Grenze stehen (keine Phase < 5 mm/s). Sie wollte jedes Mal tiefer,
  und der Greifer wurde nie vorhergesagt.
- **Zusammenhang mit den vorhergesagten Greifpunkten: ja, für den Umweg, kaum für die Tempo-Umkehrungen.** Fahrten, in
  denen der vorhergesagte Greifpunkt von Chunk zu Chunk stärker springt, pendeln weiter. Für den Umweg ist das deutlich
  (Spearman ρ = 0,72 mit dem größten Sprung, p < 0,001, 20 Fahrten). Die Zahl der Umkehrungen hängt nur schwach daran
  (ρ 0,2–0,4, nicht signifikant). Wer viel pendelt, endet auch mit schlechterem Greifpunkt (ρ = 0,42, p ≈ 0,07).
  Die Ursache lässt sich nicht trennen: Ein springender Greifpunkt kann das Pendeln auslösen, oder das Pendeln
  (anderes Bild) verschiebt den Greifpunkt.
- **Einschränkung:** Die Höhengrenze lag ~32 mm über PICK. Was unterhalb von 30 mm passiert, also im Bereich, wo die Sim
  hängen bleibt, zeigen diese Fahrten nicht. Die Pendel-Messung deckt real nur 30–90 mm und je Fahrt 1–1,5 s ab.

Daten, Skripte und Abweichungen vom Auftrag:

- Den Ordner `Berichte/2026-11-20_Vorlaeufig_2026-11-19/` gibt es lokal nicht. Die Berichtsdateien liegen flach in
  `Berichte/`, deshalb steht dieser Abschnitt hier.
- `nachlauf_stopp.py` und `tempo_profil.py` fehlen. Ersatz: `skripte/nachlauf_ersatz_2026-11-23.py`,
  `skripte/rollouts_anlage_2026-11-23.py`, `skripte/tempo_profil_anlage_2026-11-23.py`. Die Definitionen stehen jeweils
  im Kopf der Datei.
- `data/2026-11-19` (Experte 19.11.) fehlt. Als Vergleich dienen `data_vm/2026-11-19-2` (7 Fahrten, 20 mm/s), die
  26 Probeaufnahmen von heute und die 4 Experten-Fahrten nach dem Policy-Test.
- Dieser Abschnitt ersetzt den vorläufigen Abschnitt „Anlage 23.11.: Tempo-Probeaufnahmen und Vergleichsfahrten“ von
  heute Mittag.

### 1. Tempo-Probeaufnahmen (`data_vm/2026-11-23`, 11:02–11:21)

**Abweichung vom Auftrag:** In diesen Aufnahmen gibt es keinen Stopp über dem Objekt (25 / 13 mm). Alle 26 Fahrten
(`pick_bis_griff`) fahren bis PICK und schließen dort. Höhenprotokoll: Greifer „zu“ bei z_soll = PICK, 6,6 mm über
dem Tisch. Der tiefste Soll-Punkt ist also die Greifhöhe (Abstand Soll-Min zu PICK: 0,00 mm). Eine Trennung nach
25 / 13 mm ist mit diesen Daten nicht möglich. Falls es eigene Stopp-Aufnahmen gibt, liegen sie nicht in `data_vm/`
oder `data/`.

Zuordnung nach Laufprotokoll: 35 mm/s = ep 0–8, 30 mm/s = ep 9–16, 40 mm/s = ep 17–25. Override 0,5, `servo_j` 60 Hz.

| Endanflug | Fahrten | Überschwingen unter tiefsten Soll-Punkt (min / median) | Nachlauf im Abstieg median / p95 / max | seitlich letzte s median / max |
|---|---:|---:|---:|---:|
| 20 mm/s (19.11.) | 7 | nie (+0,07 / +0,07 mm) | 0,86 / 1,10 / 1,38 mm | 0,18 / 0,27 mm |
| 30 mm/s | 8 | nie (+0,07 / +0,09 mm) | 1,46 / 2,45 / 3,21 mm | 0,39 / 1,16 mm |
| **35 mm/s** | 9 | **nie (+0,08 / +0,09 mm)** | **1,59 / 2,06 / 2,59 mm** | 0,42 / 0,76 mm |
| 40 mm/s | 9 | nie (+0,09 / +0,11 mm) | 1,91 / 2,51 / 2,89 mm | 0,88 / 1,33 mm |
| 50 mm/s (17.11.) | 6 | nie (+0,10 / +0,11 mm) | 2,26 / 3,02 / 3,31 mm | 0,62 / 0,79 mm |

- **Wie der Nachlauf gemessen wurde:** z_ist − z_soll im selben Takt, im Abstieg PRE_PICK → PICK. Die Referenzwerte des
  Auftrags (20 mm/s: 1,7 mm, 48 mm/s: 3,3 mm) passen nicht zu diesem Maß. Mit meiner Definition ergibt der 19.11. 0,86 mm.
  Die Werte sind deshalb nur untereinander vergleichbar. Umgerechnet über das Verhältnis bei 50 mm/s (3,3 / 2,26 ≈ 1,46)
  käme 35 mm/s auf max ≈ 3,8 mm und 40 mm/s auf ≈ 4,2 mm.
- Das Höhenprotokoll der Steuerung bestätigt das Überschwingen unabhängig davon: z_ist_min − z_soll liegt bei
  +0,07…+0,14 mm.
- In 7 von 26 Fahrten sinkt der Arm beim Schließen noch mit bis zu 2,4 mm/s. Das ist über die Tempos verteilt und
  hängt nicht am Tempo.
- 40 mm/s: erste Lage verworfen, weil der Planer keine Bahn fand (Konfigurationssprung 0,47 rad, Gelenk 6 0,88 > 0,85 rad/s).

**Empfehlung: mit 35 mm/s aufnehmen.** Das Kriterium (unter den Stopp oder Nachlauf > 4 mm) verletzt keine Stufe.
40 mm/s wäre nach dem Kriterium zulässig, liegt aber umgerechnet an der Grenze und hat den doppelten Seitenversatz.
30 mm/s bringt messbar nichts.

### 2. Policy-Tests G2 / G3 / G4 (11:40–12:00)

**Format** (`checkpoints/<Modell>/policy/rollouts/2026-11-23_HH-MM-SS/`):

- `summary.json`: Argumente, Abbruchgrund, predict_ms, Überläufe und `lage` (PICK-Pose, Werte am Stopp und für den
  vorhergesagten Greifpunkt).
- `rollout_000.npz`: je Policy-Takt `t`, `joints`, `tcp`, `action` (6 Gelenke + Greifer), `pred_chunk` (8 Schritte),
  `predict_s`, `delay_steps`.
- `experte_000.npz`, falls der Experte danach fuhr.

Die Policy-Ziele wurden mit der lokalen URDF-FK in TCP-Posen umgerechnet. Die FK stimmt mit dem geloggten TCP auf
< 1 µm überein.

**Aufbau:** `infer.py --lage-bekannt --probegriff objekt --probe-abstand 25`, Override 0,5, asynchron. Die Höhengrenze
liegt 7 mm (Objektoberkante) + 25 mm über PICK, also ~32 mm. Lagen: A 374/−284 (153°), B 492/−65 (103°),
C 243/−258 (73°), D 512/−53 (172°). Es waren 4 Lagen statt ~10, und keine war gleichmäßig über die Modelle verteilt.

| Modell | Zeit | Lage | gültig | xy / dz am Stopp [mm] | Gier ungefaltet [°] | tiefstes Chunk-Ziel dz [mm] | Greifer max | Soll−Ist max [rad] (Gelenk) | Umkehrungen 30–90 | Umweg | predict ms med/p95/max | Überläufe (je s) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G2 | 11:41 | A | ja | 14,2 / 29,7 | −1,1 | 27,7 | 0,00 | 0,14 (6) | 2 | 1,71 | 99/119/125 | 11 (2,2) |
| G2 | 11:42 | B | ja | 2,5 / 38,0 | 2,1 | 24,3 | 0,00 | 0,22 (2) | 4 | 1,73 | 106/117/131 | 10 (1,8) |
| G2 | 11:50 | C | ja | 7,1 / 38,2 | −2,0 | 25,2 | 0,00 | 0,13 (2) | 5 | 2,78 | 106/115/125 | **34 (6,6)** |
| G2 | 11:51 | C | ja | 6,5 / 37,0 | −1,3 | 28,5 | 0,00 | 0,08 (2) | 4 | 1,51 | 104/119/129 | 6 (1,4) |
| G2 | 11:55 | D | ja | 8,6 / 46,7 | −1,4 | 22,3 | 0,00 | 0,09 (2) | 1 | 1,75 | 106/117/120 | 10 (2,3) |
| G2 | 11:56 | D | ja | 14,3 / 38,9 | −1,3 | 24,7 | 0,00 | 0,09 (2) | 3 | 1,87 | 102/122/131 | 13 (2,7) |
| G2 | 12:00 | C | ja | 7,0 / 22,1 | −0,2 | 18,3 | 0,00 | 0,08 (2) | 4 | 2,13 | 101/121/124 | 11 (2,3) |
| G3 | 11:42 | B | **nein**¹ | 122 / 263 | −0,2 | 49,0 | 0,01 | 0,26 (3) | – | – | 101/117/120 | **29 (5,6)** |
| G3 | 11:43 | B | **nein**² | 262 / 349 | 1,8 | 319 | 0,00 | 0,28 (2) | – | – | 103/113/117 | **17 (6,5)** |
| G3 | 11:51 | C | ja | 4,8 / 39,8 | 0,4 | 27,9 | 0,00 | 0,09 (2) | 2 | 1,68 | 103/121/129 | 6 (1,4) |
| G3 | 11:52 | C | ja | 6,9 / 32,8 | 0,1 | 28,1 | 0,00 | 0,09 (2) | 2 | 1,62 | 100/123/133 | 9 (2,0) |
| G3 | 11:56 | D | ja | 8,9 / 40,1 | −0,9 | 26,4 | 0,00 | 0,14 (6) | 4 | 1,83 | 105/123/131 | 7 (1,4) |
| G4 | 11:46 | B | ja | 5,3 / 52,4 | −0,1 | 28,8 | 0,00 | 0,17 (2) | 1 | 1,84 | 108/118/119 | 8 (1,7) |
| G4 | 11:47 | B | ja | 2,4 / 36,1 | −0,4 | 28,4 | 0,00 | 0,20 (2) | 4 | 1,56 | 105/119/122 | 13 (2,4) |
| G4 | 11:49 | B | ja | 15,2 / 48,4 | 0,5 | 24,2 | 0,00 | 0,24 (2) | 1 | 2,02 | 103/119/181 | 14 (2,5) |
| G4 | 11:52 | C | ja | 9,1 / 35,7 | 0,2 | 28,1 | 0,00 | 0,15 (2) | 4 | 2,11 | 105/113/115 | **28 (6,0)** |
| G4 | 11:53 | C | ja | 6,1 / 49,7 | −0,2 | 24,5 | 0,00 | 0,08 (2) | 1 | 1,97 | 106/122/135 | 4 (1,1) |
| G4 | 11:57 | D | ja | 5,2 / 34,3 | 1,2 | 29,9 | 0,01 | 0,19 (2) | 0 | 1,50 | 100/113/121 | 14 (2,6) |
| G4 | 11:57 | D | ja | 9,3 / 28,6 | −1,5 | 21,9 | 0,00 | 0,09 (2) | 2 | 1,25 | 104/113/129 | 13 (2,4) |
| G4 | 11:58 | D | ja | 16,5 / 43,7 | −1,5 | 16,2 | 0,01 | 0,16 (2) | 4 | 3,98 | 107/121/126 | 20 (3,5) |
| G4 | 11:58 | D | ja | 18,0 / 34,9 | 0,7 | 10,4 | 0,01 | 0,12 (2) | 4 | 2,39 | 106/118/124 | 10 (1,8) |
| G4 | 11:59 | D | ja | 10,5 / 19,4 | −1,9 | 18,9 | 0,00 | 0,10 (2) | 4 | 1,97 | 110/124/125 | 9 (1,8) |

¹ „Stopp angefordert, servo_j verweigert“. Vorher schwang der Arm bei 77–108 mm Höhe seitlich bis 89 mm aus; vermutlich
ein Bediener-Stopp, bitte bestätigen. ² Arm steht bei 349 mm („Not-Aus am Handbediengerät?“).
Dazu kommt ein Lauf G2 11:40 ohne Fahrt (0 Episoden).

Spalten: xy / dz am Stopp = gemessener TCP gegen PICK. „Tiefstes Chunk-Ziel“ = tiefster Punkt aller vorhergesagten
Chunk-Schritte über PICK (Grenze ~32 mm). „Umkehrungen“ = Vorzeichenwechsel der Annäherungsrate (Hysterese ±5 mm/s) beim
ersten Durchgang 30–90 mm. „Umweg“ = Weglänge / Abstandsabnahme im selben Abschnitt (1 = gerade). Die Spalte „Umweg“
ersetzt die Welligkeit, deren Definition aus `tabelle_G2_G3_G4.md` mir nicht vorliegt.

**a) Gültigkeit.**

- Die Vorhersage dauert in allen Fahrten median 99–110 ms, p95 113–124 ms, einmal max 181 ms (G4 11:49). Das sind
  **15–20 ms mehr als die erwarteten 85–90 ms** (VM-Wert). Es ist aber derselbe Wert wie bei den C2/C3-Fahrten an der
  Anlage am 17./19.11. (103–114 ms).
- Es gab keine übersprungenen Vorhersagen, der Chunk-Verzug lag immer ≤ 2 Takte.
- Takt-Überläufe: 4–34 je Fahrt, das entspricht den Anlagenfahrten vom 17./19.11. (3–31).
- **Viele Überläufe (> 5 je s):** G2 11:50, G4 11:52 und die beiden ungültigen G3-Fahrten. Die beiden gültigen weichen in
  keiner Kennzahl auffällig ab.
- Gewertet werden G2 7, G3 3 und G4 10 Fahrten.

**b) Lage an der Höhengrenze.**

- Gier, ungefaltet über 360°: |Fehler| ≤ 2,1° in allen 20 gültigen Fahrten. **Es gab keine 180°-Verdrehung.** Allerdings
  enthielten die 4 Lagen kaum große Drehungen gegen die Startstellung.
- xy am Stopp, median: G2 7,1 mm, G3 6,9 mm, G4 9,2 mm (max 14,3 / 8,9 / 18,0 mm).
- Lage D ist für alle Modelle die schlechteste. G4 liegt dort 3-mal über 10 mm.
- Eine Rangfolge der Modelle ist bei 1–5 Fahrten je Lage und ungleicher Verteilung nicht ablesbar.

**c) Wollte die Policy tiefer?**

- **Ja, in allen 20 gültigen Fahrten.** Die Chunk-Ziele lagen unter der Grenze (tiefstes Ziel median 24–28 mm über PICK,
  bis 10 mm).
- Das ist zum Teil zwangsläufig: Der Abbruch „Kollisionsmodell vorab“ wird genau dadurch ausgelöst, dass ein
  vorhergesagtes Ziel unter die Grenze geht.
- Aussagekräftiger ist: **Keine Fahrt blieb über der Grenze stehen.** Es gab keine Phase mit TCP-Tempo < 5 mm/s im Bereich
  20–80 mm, die längste dauerte 0 s.
- Die Fahrt dauert unter 60 mm nur 0,4–1,6 s bis zum Stopp. Ein „Schleichen“ wie in der Sim gibt es bis zur Grenze nicht.

**d) Greifer.** Der Greiferkanal blieb in Aktion und Chunks immer ≤ 0,01. Die Policy hat nie „schließen“ vorhergesagt.
Bei 20–50 mm über PICK ist das aber auch zu erwarten, in den Demos schließt der Greifer erst an PICK.

**e) Sprünge und Welligkeit.**

- Es gab keinen Sprung > 0,35 rad. Soll − Ist je Gelenk lag in gültigen Fahrten bei max 0,24 rad (meist Gelenk 2),
  Takt zu Takt beim Aktionsziel max 0,08 rad.
- Welligkeit siehe f).

**f) Tempo-Profil und Pendeln.** Median je Gruppe, TCP-Tempo 3D [mm/s]. In Klammern die Annäherungsrate
(Abnahme des Abstands zu PICK je s).

| Abstand zu PICK | 80–120 | 60–80 | 45–60 | 30–45 | 20–30 | Umkehrungen 30–90 median (min–max) |
|---|---:|---:|---:|---:|---:|---:|
| Experte 19.11., 20 mm/s (7) | 155 (155) | 129 (127) | 15 (12) | 19 (19) | 19 (19) | 0 (0–0) |
| Experte 23.11., 30 mm/s (8) | 148 (143) | 128 (127) | 25 (21) | 28 (27) | 27 (27) | 0 (0–0) |
| Experte 23.11., 35 mm/s (9) | 151 (149) | 133 (133) | 29 (29) | 32 (32) | 35 (35) | 0 (0–0) |
| Experte 23.11., 40 mm/s (9) | 150 (150) | 131 (128) | 36 (34) | 39 (38) | 38 (37) | 0 (0–0) |
| Experte nach Policy (infer.py, 4) | – | – | 10 (1) | 20 (20) | 19 (19) | 0 (0–1) |
| **G2** (7) | 131 (128) | 136 (135) | **61 (25)** | **69 (15)** | 86 (36)³ | **4 (1–5)** |
| **G3** (3) | 126 (121) | 139 (137) | **56 (29)** | **51 (10)** | – | **2 (2–4)** |
| **G4** (10) | 191 (186) | 144 (138) | **73 (34)** | **58 (5)** | 70 (39)³ | **3 (0–4)** |

³ Nur 2–4 Fahrten erreichen 20–30 mm, jeweils in den letzten Takten vor dem Stopp.

- **Der Experte** bremst bei ~60 mm sauber auf das Endanflug-Tempo, wie in der Sim. Er pendelt nicht (0 Umkehrungen) und
  hält das Tempo bis an das Objekt.
- **Die Policies** (alle mit 20-mm/s-Daten trainiert) bremsen bei 45–60 mm nicht auf 20 mm/s, sondern bewegen sich mit
  50–70 mm/s weiter. Davon geht aber nur ein kleiner Teil zum Objekt hin: Die Annäherung bricht bei 30–45 mm auf
  5–15 mm/s ein, also **unter das Endanflug-Tempo der Demos**. Der Rest ist seitliches und senkrechtes Pendeln
  (Umweg 1,5–4,0, median 1,7–2,0, z steigt zwischendurch um 4–15 mm wieder an).
- **Vergleich mit der Sim:** Die Richtung stimmt, Einbruch der Annäherung bei 30–45 mm und Pendeln. Die Stärke ist
  real geringer: 2–4 statt 5–10 Umkehrungen. Real ist das Fenster aber kürzer (die Grenze schneidet bei ~32 mm ab),
  die Zahlen sind deshalb eher Untergrenzen.
- Die Annäherung streut je Fahrt stark: 4 bis 180 mm/s in 30–60 mm, auch wenn man die letzten 3 Takte vor dem Stopp
  weglässt (2–18 Takte je Fahrt). Ob viel Pendeln real mit Scheitern einhergeht, ist offen, weil keine Fahrt greifen konnte.

**g) Pendeln beim Wechsel und vorhergesagter Greifpunkt** (`skripte/pendeln_greifpunkt_2026-11-23.py`).

Je Chunk ist der Greifpunkt der tiefste vorhergesagte Schritt (FK), gemessen im ersten Durchgang 30–90 mm, also im
Wechsel vom Transit in den Endanflug. Daraus: Sprung des Greifpunkts zwischen aufeinanderfolgenden Chunks in xy, die
Streuung des Greifpunkt-xy gegen PICK und der letzte Greifpunkt vor dem Stopp. „Tempo-Umkehrungen“ zählt
Bremsen/Beschleunigen-Wechsel des Tempobetrags (Hysterese 5 mm/s je Takt).

| je Fahrt (20) | median | Bereich |
|---|---:|---:|
| Umkehrungen der Annäherung | 3 | 0–4 |
| Tempo-Umkehrungen (Betrag)⁴ | 7 | 2–9 |
| Umweg | 1,70 | 1,25–4,04 |
| Greifpunkt-Sprung xy je Chunk, median der Fahrt | 2,0 mm | 0,6–4,5 mm |
| größter Greifpunkt-Sprung xy | 3,3 mm | 1,7–8,8 mm |
| Greifpunkt-Sprung z, median der Fahrt | 3,7 mm | 1,8–10,7 mm |

Experte zum Vergleich: 0 Umkehrungen der Annäherung, Umweg ≈ 1.
⁴ Beim Experten gleich häufig, also kein Pendel-Maß (siehe Korrektur unten).

| Spearman ρ (20 Fahrten) | Sprung xy median | Sprung xy max | Streuung Greifpunkt-xy | letzter Greifpunkt-xy | xy am Stopp |
|---|---:|---:|---:|---:|---:|
| Umkehrungen Annäherung | −0,13 | 0,23 | 0,27 | 0,35 | 0,17 |
| Tempo-Umkehrungen | −0,01 | 0,41 | 0,20 | 0,29 | 0,13 |
| **Umweg** | **0,51** (p 0,02) | **0,72** (p < 0,001) | **0,51** (p 0,02) | 0,42 (p 0,07) | 0,35 |

- **Korrektur (Nachprüfung):** Die „Tempo-Umkehrungen (Betrag)“ unterscheiden Policy und Experte **nicht**. Je Sekunde
  sind sie gleich häufig (30–90 mm: Policy 5,2/s, Experte 35 mm/s 5,3/s, Experte 20 mm/s 4,8/s; weiter weg 7–9/s bei
  beiden). Sie messen das eingespielte Rauschen und Messzittern, kein Pendeln. Aussagekräftig sind nur die
  **Umkehrungen der Annäherung** (zum Objekt hin, wieder weg): Policy 2,4/s im Bereich 30–90 mm, aber **0/s bei
  90–200 und 200–500 mm**. Der Experte hat überall 0/s.
- **Das Pendeln sitzt also nur im Wechselbereich 30–90 mm.** Dort bremst der Experte von ~130 auf das Endanflug-Tempo,
  und dort liegt auch das Objekt nahe. Welche der beiden Ursachen wirkt, lässt sich mit diesen Daten nicht trennen.
- **Der Umweg hängt klar am Greifpunkt.** Springt der vorhergesagte Greifpunkt stärker, fährt die Policy einen
  größeren Umweg. Extremfall G4 11:58: größter Sprung 8,8 mm, Umweg 4,0, letzter Greifpunkt 13,4 mm neben PICK.
  Die ruhigsten Fahrten (G2 11:55, G4 11:46) haben kleine Sprünge (≤ 3 mm) und Umweg < 1,3.
- **Die Zahl der Umkehrungen hängt kaum am Greifpunkt.** Auch innerhalb der Fahrten folgt auf einen Greifpunkt-Sprung
  > 3 mm in den nächsten 3 Takten nur etwas häufiger eine Umkehr der Annäherung als sonst (74 % gegen 62 %,
  Fisher p = 0,22). Das Hin und Her des Tempos sieht eher nach einer Eigenschaft der Policy-Ausführung aus
  (Chunk-Wechsel alle 2 Takte, Verzug 2 Takte) als nach einer Reaktion auf den Greifpunkt.
- **Ursache und Wirkung bleiben offen.** Der Zusammenhang kann in beide Richtungen laufen: Pendeln verändert das
  Wrist-Bild und damit den vorhergesagten Greifpunkt. Bei 20 Fahrten auf 4 Lagen ist das ein Hinweis, kein Beweis.
  Lage D hat die größten Sprünge und Umwege; ein Teil des Zusammenhangs kann also an der Lage hängen.

**Fazit Policy:** Die echte Policy pendelt im Endanflug, schwächer als in der Sim. Ihre Annäherung fällt bei 30–45 mm
unter das Tempo der Demos. Bis 32 mm über dem Objekt bleibt sie aber nicht stehen und will weiter nach unten.
Damit ist der Sim-Befund für 0,02 m/s-Daten real **teilweise bestätigt** (Einbruch und Pendeln). Der eigentliche
Hänger 1–2 cm über dem Objekt ist **nicht geprüft**. Dazu braucht es eine Grenze ≤ 13 mm oder einen echten Griff.

### 3. Nachtrag: Seitenansicht, Einzelfahrten und Ausführung

Abbildungen: `abbildungen_2026-11-23/seitenansicht_trichter.png` (alle Fahrten gegen den Demo-Trichter) und
`abbildungen_2026-11-23/seitenansicht_einzelfahrten.png` (G4 11:46 ruhig, G2 11:50 mittel, G4 11:58 unruhig; Ist,
Soll = FK der Policy-Aktion, Greifpunkt je Chunk). Skripte: `skripte/seitenansicht_trichter_2026-11-23.py`,
`skripte/seitenansicht_einzelfahrten_2026-11-23.py`. Der Demo-Trichter stammt aus 33 Demos (19.11. und 23.11.,
gleiche Rausch- und Versatz-Einstellungen).

**Seitenansicht.**

- Bis PRE_PICK (50 mm) bleiben die Policy-Fahrten im Demo-Trichter.
- Bei 40–50 mm fahren sie fast waagrecht hin und her und sinken dabei nur mit etwa 10 mm/s. Die Demos bauen dagegen
  den Versatz gleichmäßig beim Absinken ab: p90 9 mm bei 45 mm, 1,6 mm bei 25 mm, null unter 20 mm.
- In 13 von 20 Fahrten geht der Ist-TCP über die Mitte hinaus, bis 18 mm auf die andere Seite.
- In den Demos kommt das nie vor. Der Versatz baut sich dort immer einseitig zur Mitte hin ab, Rauschen gibt es
  unter 50 mm praktisch keines.

**Ausführung: Der Arm folgt der Policy deutlich schlechter als dem Planer.** Gemessen als Abstand des Ist-TCP zur
Soll-Bahn, unabhängig vom Zeitpunkt; eine reine Verzögerung zählt also nicht mit.

| | Policy (20 Fahrten) | Experte (19.11., 7) |
|---|---:|---:|
| Ist → Soll-Bahn unter 60 mm, median / p95 | 3,3 / 14,3 mm | 0,13 / 1,1 mm |
| Ist → Soll-Bahn 60–150 mm, median / p95 | 3,7 / 10,1 mm | 1,9 / 5,5 mm |
| seitliche Spannweite unter 60 mm, Ist / Soll (median) | 11,2 / 4,7 mm | – |
| Soll-TCP-Ruck unter 60 mm (2. Differenz je Takt), median / p95 | 3,0 / 5,7 mm | 0,04 / 0,7 mm |
| Befehls-Ruck je Gelenk p95, J2 / J5 / J6 | 32 / 12 / 20 mrad | 4 / 4 / 6 mrad |

- **Ursache sind die ruckigen Befehle.** Die Soll-Bahn der Policy ist unten etwa 75-mal ruckiger als die des Planers.
  Der Arm schwingt seitlich 2–4-mal weiter aus als befohlen. Der größte Gelenkabstand liegt meist an J5/J6; bei
  ~200 mm Werkzeuglänge werden daraus viele Millimeter seitlich.
- **Der Chunk-Wechsel treibt den Fehler.** Takte mit neuem Chunk: Folgefehler steigt im Median um +0,19 mm.
  Takte dazwischen: Folgefehler sinkt um −0,15 mm.
- **Takt-Jitter ist nicht die Ursache.** Policy-Takt median 67,1 ms, p95 82 ms, 7 % über 80 ms. In diesen Takten
  wächst der Fehler nicht (−0,14 mm). Die Takt-Überläufe je Fahrt hängen nicht erkennbar mit dem Folgefehler zusammen.
- **Folgerung:** Ein großer Teil des Pendelns entsteht in der Ausführung. Glattere Übergänge zwischen den Chunks sind
  ein eigener Hebel, unabhängig vom Datensatz: Real-Time Chunking, decay, Replan-Abstand oder ein Glättungsfilter
  auf die Befehle.

**G4 11:58 (unruhigste Fahrt).**

- Der Start ist normal. Der Befehl liegt immer 2–4 Takte vor dem Arm (20–30 mm bei 120–150 mm/s), genauso wie bei der
  ruhigen Fahrt G4 11:46.
- Der Unterschied: 11:58 durchfährt 150 → 60 mm in 5 Takten mit ~258 mm/s (11:46: 9 Takte mit 141 mm/s, Demos
  150 mm/s). Sie kommt also fast doppelt so schnell in die Bremszone und schießt dort seitlich über.
- Lage D (x 512 / y −53 mm, 172°) liegt im TCP-Bereich der Trainingsdaten (x 174–567 mm), aber nah am Rand.
  Die Dichte der Greiflagen dort ließ sich nicht prüfen (`datasets/2026-11-19_nur_griff` liegt lokal nicht vor).
- Lage D ist für alle Modelle die schwierigste. Dort liegen auch die zwei größten Folgefehler (G4 11:57: 17 mm,
  G2 11:55: 9,5 mm).

**Woher der Ruck kommt** (offline aus den geloggten Chunks; die Nachrechnung des geloggten Befehls aus den Chunks stimmt
bis auf max. 0,04 rad, weil der Ankunftstakt der Chunks nur genähert ist):

| Soll-TCP-Ruck unter 60 mm (2. Differenz je Takt) | median | p95 |
|---|---:|---:|
| Trainings-Labels (Demos 19.11., `action`) | 0,00 mm | 0,27 mm |
| ein einzelner Policy-Chunk, Schritte untereinander | 2,9 mm | 6,7 mm |
| Befehl heute (Mittel über ~3 Chunks, decay 0) | 2,5 mm | 5,1 mm |
| decay 0,5 / 1,5 (neuere Chunks stärker) | 3,9 / 5,1 mm | 7,7 / 10,3 mm |
| Tiefpass auf den Befehl, alpha 0,5 / 0,3 | 0,9 / 0,5 mm | 1,9 / 1,3 mm |

- **Die Labels sind glatt.** Sie entsprechen der Idealbahn (max. 0,03 rad Abweichung) und nicht dem verrauschten
  Befehl. Der Ruck kommt also nicht aus den Daten.
- **Schon ein einzelner Chunk ist ruckig.** Seine Schritte untereinander sind so unruhig wie der gemittelte Befehl.
  Dazu kommt: Zwei aufeinanderfolgende Chunks liegen für denselben Takt im Median 4,3 mm auseinander (p95 9,9 mm).
- **Real-Time Chunking** würde nur den zweiten Teil glätten, die Sprünge zwischen den Chunks. Gegen das Zittern
  innerhalb eines Chunks hilft es nicht.
- **Stärkere Gewichtung neuer Chunks (decay)** macht es schlechter.
- **Ein Tiefpass** glättet um Faktor 3–5, verzögert aber: Bei alpha 0,3 läuft der Befehl etwa 2 Takte (~150 ms)
  hinterher.
- **Noch nicht geprüft:** mehr DDIM-Schritte (heute 10). Das geht offline auf aufgezeichneten Beobachtungen,
  ohne Anlage.

### 4. Offline-Test DDIM-Schritte und Anlagenfahrten 23.11. nachmittags (G2)

**Offline-Test** (RTX 5090, G2, `data_vm/2026-11-19-2` ep 0–4; Protokoll
`checkpoints/G2_licht_langsam_nur_griff/policy/offline_ddim/2026-11-23_14-58-25/`):

| DDIM | Vorhersage ms (5090) | Chunk-Ruck mm med/p95 | Chunk-Sprung mm med/p95 | Befehl-Ruck alpha 1 / 0,5 / 0,3 | Abstand Aufnahme mm (med) alpha 1 / 0,5 / 0,3 |
|---:|---:|---:|---:|---:|---:|
| 10 | 47 | 2,52 / 9,67 | 1,6 / 6,6 | 1,65 / 0,59 / 0,33 | 2,0 / 2,4 / 3,7 |
| 20 | 97 | 2,54 / 9,59 | 1,6 / 6,6 | 1,62 / 0,59 / 0,32 | 2,1 / 2,4 / 3,7 |
| 50 | 247 | 2,52 / 9,54 | 1,6 / 6,5 | 1,64 / 0,58 / 0,32 | 2,1 / 2,4 / 3,7 |

- **Mehr DDIM-Schritte glätten nichts.** Chunk-Ruck und Chunk-Sprung bleiben bei 10, 20 und 50 Schritten gleich,
  nur die Vorhersage wird länger. Das Zittern steckt im Modell selbst, nicht im Restrauschen der Entrauschung.
- **Der Tiefpass wirkt.** alpha 0,5 senkt den Befehls-Ruck um Faktor 2,8, der Abstand zur Aufnahme steigt dabei nur
  von 2,0 auf 2,4 mm. alpha 0,3 glättet stärker (Faktor 5), kostet aber mehr Verzug (3,7 mm, p95 8,2 mm).

**Anlage 15:01–15:09** (G2, alle Fahrten an Lage 222/−156 mm, 60°, Override 0,5; **Glättung in keiner Fahrt aktiv**):

| DDIM | Fahrten | Vorhersage ms (Anlage) | Chunk-Verzug | Ist → Soll unter 60 mm (med) | seitl. Spannweite | xy am Ende (med) |
|---:|---:|---:|---:|---:|---:|---:|
| 10 (vormittags, 4 Lagen) | 22 | 104 | 2 Takte | 4,8 mm | 11 mm | 8,8 mm |
| 10 (15:02) | 1 | 101 | 2 Takte | 21 mm | 18 mm | 18,8 mm |
| 20 | 6 | 203 | 3–4 Takte | 10,5 mm | 21 mm | 9,4 mm |
| 25 (inkl. Crash) | 6 | 250 | 4 Takte | 10,5 mm | 36 mm | 31 mm |

- **Die Vorhersagezeit verdoppelt sich am Anlagenrechner gegenüber der 5090.** 10 Schritte brauchen 101 ms, 20 Schritte
  203 ms, 25 Schritte 250 ms. Ab 20 Schritten liegt sie damit über der Grenze von ~133 ms. Die Chunks kommen dann 3–4 statt
  2 Takte zu spät, die Policy reagiert auf veraltete Bilder.
- **Mit 20/25 Schritten werden die Fahrten unruhiger.** Ist → Soll verdoppelt sich, die seitliche Spannweite steigt auf
  21–36 mm. Ausreißer: 15:05:44 (48 mm daneben), 15:07:43 (31 mm), 15:08:13 (91 mm, Abbruch an der Hülle der
  Demonstrationen), 15:09:03 (40 mm). Es gibt aber auch drei gute Fahrten (15:04:06, 15:04:37, 15:07:16 mit
  2,6–3,6 mm am Ende).
- **Vorbehalt:** Alle Nachmittagsfahrten liefen an derselben Lage. Geändert wurden nacheinander die DDIM-Schritte und
  der Probeabstand:

  | Probeabstand | 10 Schritte | 20 Schritte | 25 Schritte |
  |---|---|---|---|
  | 25 mm | 18,8 mm (15:02) | 21,2 mm (15:03) | – |
  | 20 / 15 mm | – | 2,6 / 2,8 mm | – |
  | 10 mm | – | 13,7 / 47,9 / 5,1 mm | 13,8 / 3,6 / 31,4 mm |
  | 8 mm | – | – | 91 / 40 mm, Crash |

  (Werte: xy-Abstand zu PICK am Ende der Fahrt.)

  - Bei gleichem Probeabstand unterscheiden sich 20 und 25 Schritte nicht erkennbar; die Fahrten streuen untereinander
    stärker als zwischen den Einstellungen.
  - Mit 10 Schritten gibt es an dieser Lage nur eine Fahrt, die auch schon 18,8 mm daneben lag.
  - Der Vergleich mit dem Vormittag ist nicht sauber, weil das eine andere Lage war.
  - Dass mehr Schritte an der Anlage schaden, ist damit **nicht belegt**. Belegt ist nur: Sie verlängern die Vorhersage
    über die Grenze (Verzug 3–4 statt 2 Takte) und glätten offline nichts. Deshalb trotzdem: **an der Anlage 10 Schritte**.

**Crash 15:09:41** (G2, Probeabstand 8 mm, also unter der Warnschwelle von 10 mm; Vorhersage 251 ms → mit ~25 Schritten
gefahren; Experte an; kein summary.json, die Fahrt wurde abgebrochen):

- **Was passierte:** In den Takten 69–74 lag das gesendete Ziel 22–35 mm über PICK, der Arm stieg aber auf 56–66 mm.
  Er wich also 30–40 mm von seinen Zielen ab. Danach sackte er schnell ab: Takt 75 bei 47 mm, Takt 76 bei 33 mm.
- **Endstand nach der Policy:** TCP **8,2 mm über PICK** (15 mm über dem Tisch, Objektoberkante 14,9 mm),
  **29,9 mm seitlich** und **−21° Gier**. Mit 44,8 mm offenen Backen steht eine Backe dann über dem Bauteil – der
  Kontakt ist sehr wahrscheinlich hier entstanden. Danach startete der Experte („korrigiert und legt um“).
- **Ursache:** Die Ziele sprangen in den Takten 66–68 seitlich um 7 → 18 → 26 mm, bei 4 Takten Verzug. Der Arm folgte
  ihnen mit 30–40 mm Abweichung und schwang nach dem Stopp 30 mm unter das letzte Ziel (38 mm). Das Kollisionsmodell
  prüft die Ziele, nicht den Weg des Arms dazwischen. Die Reserve für den Nachlauf (bisher gemessen ≤ 7,5–10 mm) reicht
  bei so unruhigen Befehlen nicht.
- **Folgerungen:**
  - Probeabstand nicht unter 15 mm, solange der Arm der Policy so schlecht folgt.
  - DDIM an der Anlage bei 10 lassen.
  - Den Tiefpass (alpha 0,5) als Nächstes testen.

### 5. Glättung an der Anlage (23.11., 15:29–15:50)

G2 und var_C2 an der Lage 222/−156 mm (60°), DDIM 10, Probeabstand 25 → 10 mm, Override 0,5. Skript
`skripte/glaettung_anlage_2026-11-23.py`, Abbildung `abbildungen_2026-11-23/seitenansicht_glaettung.png` (vier
G2-Fahrten: α 1,0 unruhig, α 1,0 ruhig, α 0,5, α 0,25).

**Nicht gewertet:**
- 15:43:30, 15:44:07, 15:44:56, 15:45:21: Der Arm fuhr nicht los („arm steht“, 6–7 Takte, TCP in der Startstellung).
  Dazu gehören 2× α 0,75, 1× α 0,25 und 1× α 1,0.
- 15:28:35 und 15:41:18: nur die Kameraprüfung, keine Fahrt.
- 15:35:38: Not-Aus zum Messen des Abstands über dem Objekt, kein Crash. Ohne summary.json; die Glättung wurde aus
  dem Log geschätzt (α 0,50), die Fahrt wird bei α 0,5 mitgezählt.

| G2, Median je α | Fahrten | Ist → Soll unter 60 mm (p95) | seitl. Spannweite (max) | Annäherungs-Umkehrungen/s | Ruck roh / gesendet / Arm | Takte | xy am Ende |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1,00 | 5 | 4,0 mm (9,8) | 15,7 mm (68) | 1,4 | 2,52 / 2,52 / 2,34 | 59 | 7,5 mm |
| 0,75 | 1 | 2,0 mm (7,8) | 11,3 mm | 2,8 | 1,55 / 1,00 / 2,22 | 72 | 1,7 mm |
| **0,50** | **10** | **0,19 mm (0,9)** | **3,3 mm (5,6)** | **0** | 0,80 / 0,30 / 0,63 | 75 | **4,1 mm** |
| 0,25 | 2 | 0,14 mm (0,5) | 3,3 mm (3,5) | 0 | 1,26 / 0,18 / 0,42 | 92 | 2,8 mm |
| var_C2, 0,50 | 2 | 2,4 mm (4,7) | 8,4 mm | 0 | 4,47 / 1,69 / 3,10 | 66 | 14 mm, Gier 36–41° |

(Ruck = 2. Differenz der TCP-Position je Takt unter 60 mm, in mm: roh = Policy-Ausgabe, gesendet = nach dem Tiefpass,
Arm = gemessener TCP.)

- **Mit α 0,5 ist das Pendeln weg.** Der Arm folgt der gesendeten Bahn auf 0,2 mm genau, statt mit 4 mm wie bei α 1,0
  (vormittags 4,8 mm). Die seitliche Spannweite sinkt von 16 auf 3 mm. Hin-und-her-Fahren zum Objekt gibt es nicht mehr.
- **Alle 10 Fahrten mit α 0,5 waren ruhig**, bei jedem Probeabstand von 20 bis 10 mm (größte Spannweite 5,6 mm).
- **α 1,0 bleibt unberechenbar.** 3 von 5 Fahrten waren ruhig, 2 schwangen stark aus:
  - 15:42:59: Ist → Soll 29 mm, Spannweite 68 mm, 20 mm daneben
  - 15:47:09: 24 mm, Spannweite 55 mm, 37 mm daneben
- **Auch die rohe Ausgabe der Policy wird ruhiger** (Ruck 0,8 statt 2,5 mm). Ein ruhigerer Arm liefert ruhigere Bilder,
  und darauf reagiert die Policy ruhiger. Das Pendeln war also zum Teil ein Aufschaukeln zwischen Arm und Policy.
- **Tempo:** Mit α 0,5 fährt der Arm unter PRE_PICK fast genau das Tempo der Demos (~20 mm/s), ohne Ausreißer (Abbildung).
  α 0,25 ist noch ruhiger, aber schon im Transit langsamer (~100 statt 150 mm/s, 92 statt 75 Takte). Das ist der
  Verzug von ~3 Takten.
- **Systematischer Versatz:** Alle α-0,5-Fahrten enden am selben Punkt neben PICK: dx +0,3…+1,9 mm, dy −2,6…−4,8 mm,
  im Werkzeug-KS etwa −2,7 / +2,1 mm. Das ist kein Zufall, sondern eine feste Abweichung. Gemessen wurde 20–35 mm über
  PICK, wo die Demos schon fast mittig sind. Mögliche Ursachen: ein geteachter PICK, der nicht genau auf der Objektmitte
  liegt, oder ein Bias der Policy an dieser Lage. Unterscheiden lässt sich das nur mit Blick auf das Objekt, zum Beispiel
  Backen gegen Objekt im Wrist-Bild oder der Griff des Experten. In Schließrichtung ist das Spiel nur 2,5 mm je Backe,
  der Versatz ist also nicht harmlos.
- **var_C2 mit α 0,5:** Der Arm ist ebenfalls ruhiger (keine Umkehrungen), C2 steht aber 12–16 mm daneben und 36–41°
  verdreht. Das ist der bekannte Drehbias von C2, den die Glättung nicht behebt.
- **Zeit:** Vorhersage 97–114 ms, Chunk-Verzug 2 Takte, Überläufe 7–32. Die Fahrten sind gültig.

**Fazit:** Die Glättung mit α 0,5 beseitigt an der Anlage das Pendeln vollständig, mit wenig Verzug. Sie sollte der
neue Standard für die Inferenz werden (Vorschlag: als Default in `bc_policy.json`/`inference_defaults` bzw. in
der GUI). Belegt ist das bisher an **einer** Lage mit G2. Es fehlen noch:
- eine zweite und dritte Lage,
- der echte Griff, der zeigt, ob der feste Versatz von ~4 mm stört.

### 6. Glättung 0,5 gegen 0,25 auf vielen Lagen, erste echte Griffe (23.11., 16:13–16:50)

G2, DDIM 10, Probegriff „objekt“ mit Experte, der nach jeder Fahrt umlegt (neue Lage, PICK nachgeführt). Danach
Probeabstand 7 → 4 → 1 mm ohne Experte und vier Griffversuche (Probegriff „tisch“). Skript
`skripte/glaettung_lagen_2026-11-23.py`. Die Glättung wurde je Episode aus dem Log geschätzt, sie stimmt mit den
Einstellungen überein. 16:15:36 und 16:22:20 haben kein summary.json, die Zuordnung kommt aus policy_test.csv.

| Probefahrten | Fahrten / Lagen | Ist → Soll unter 60 mm (max) | seitl. Spannweite (max) | Umkehrungen/s (max) | Tempo Transit / Endanflug | Takte | xy am Ende (max), Mittel dx/dy | Gier am Ende (max) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| α 0,50 | 17 / 15 | 0,23 mm (0,5) | 4,9 mm (24) | 0 (1,3) | 130 / 16 mm/s | 89 | 2,8 mm (7,9), −1,1/−2,1 | 0,6° (2,4) |
| α 0,25 | 26 / 24 | 0,11 mm (0,2) | 2,3 mm (5,0) | 0 (0) | 104 / 14 mm/s | 111 | 2,9 mm (9,1), +0,3/−1,7 | 0,4° (2,1) |
| Demos 19.11. | – | – | – | 0 | ~150 / ~19 mm/s | – | – | – |

- **Beide Glättungen sind auf vielen Lagen ruhig.** Das Pendeln vom Vormittag kommt nicht mehr vor, auch nicht bei
  Drehungen von 60–147° gegen die Startstellung.
- **α 0,25 ist noch ruhiger** (Spannweite halb so groß, keine einzige Umkehrung), aber langsamer: Transit 104 statt
  130 mm/s, 25 % mehr Takte. Am Ende liegen beide gleich nah am Ziel (median 2,8 / 2,9 mm).
- **Ausreißer bei α 0,5:** 16:24:40 Ep. 13 mit 24 mm Spannweite und sehr langsamem Transit (32 mm/s); die Fahrt endet
  trotzdem 2,1 mm neben PICK.
- **Der feste Versatz vom Nachmittag ist kleiner geworden**, mit beiden Glättungen etwa −2 mm in y. An der Lage
  222/−156 waren es −4 mm. Er hängt also von der Lage ab und ist kein reiner Fehler des geteachten PICK.
- **Beide Glättungen sind im Endanflug langsamer als die Demos** (14–16 statt ~19 mm/s). Die Policy setzt ihr Ziel
  immer ein Stück vor die Stellung, die sie gerade sieht. Hängt der Arm hinterher, setzt sie auch das nächste Ziel
  weiter hinten an und wird so mit gebremst.
- **Kleine Probeabstände mit α 0,25** (Lage 439/−178): 7, 4 und 1 mm verliefen ruhig. Bei 1 mm endete der TCP
  17,8 mm über dem Tisch, 3,3 mm neben PICK.

**Vergleichsgrafik:** `abbildungen_2026-11-23/seitenansicht_vergleich_glaettung.png`, Skript
`skripte/seitenansicht_vergleich_glaettung_2026-11-23.py`. Drei Zeilen mit gleichen Achsen:
- ohne Glättung (die 20 Fahrten vom Vormittag),
- α 0,5 (17 Fahrten),
- α 0,25 (26 Fahrten).

Ohne Glättung fahren die Fahrten bei 40–50 mm waagrecht hin und her. Mit Glättung sinken sie gerade im Trichter ab,
und das Tempo folgt nach PRE_PICK dem der Demos.

Nicht ganz gleiche Bedingungen:
- Vormittag Probeabstand 25 mm (Stopp ~35–45 mm über PICK), nachmittags 10–20 mm.
- Vormittag G2/G3/G4 an 4 Lagen, nachmittags G2 an vielen Lagen.
- Der Ausreißer bei α 0,5 (Schleife bei 140 mm, Ausschlag bis 27 mm bei 60–80 mm) ist 16:24:40 Ep. 13.

**Griffversuche** (α 0,25, Probegriff „tisch“; ab 16:45 lag der PICK in der Steuerung bewusst weit weg (175/−35), die
Lage aus der Steuerung sagt also nichts; Bezug ist die letzte Lage des Experten, 439/−178):

| Lauf | Ergebnis | TCP beim Schließen über dem Tisch | xy gegen 439/−178 | Gier |
|---|---|---:|---:|---:|
| 16:42:10 (PICK richtig) | Griff | 7,6 mm | +3,5 / −2,8 mm | 87° |
| 16:45:02 (PICK weit weg) | Griff | 7,3 mm | +2,9 / −2,1 mm | 87° |
| 16:48:53 (PICK weit weg) | Griff | 7,6 mm | +16 / +20 mm | 93° |
| 16:49:57 (PICK weit weg) | Kontakt an der Kante, „arm steht“ | 13,2 mm | +41 / −9 mm | 96° |

- **Die Policy greift dort, wo das Objekt liegt, nicht dort, wo der PICK steht.** Bei 16:45:02 lag der PICK der
  Steuerung 300 mm entfernt, gegriffen wurde trotzdem 3,6 mm neben der Objektlage. Die Richtung holt sie sich aus dem
  Bild.
- **Die Höhe passt:** Geschlossen wurde 7,3–7,6 mm über dem Tisch, die Demos greifen bei 6,6 mm.
- **Die späteren Versuche lagen woanders**, weil sich das Objekt durch die vorherigen Griffe vermutlich verschoben hat
  (Greifer zu/auf). Das kann ich aus den Daten nicht prüfen.
- **Kontakt 16:49:57:**
  - Das Ziel lag 7–8 mm über dem Tisch, der Arm blieb aber bei 13,2 mm stehen (5 Takte ohne Bewegung,
    Restabstand 0,032 rad). Der Stillstandswächter hat abgebrochen.
  - Eine Backe saß also auf etwas auf, wahrscheinlich auf der Objektkante (Oberkante 14,9 mm über dem Tisch, also ~2 mm
    Überdeckung). Das passt zu „ein paar mm“.
  - Der Greiferkanal der Policy stand bis zuletzt auf ~0 („offen“).

**Greifer geht kurz zu und wieder auf:** Das ist der Programmablauf, nicht die Policy.
- Im Policy-Test (`--lage-bekannt`) endet die Fahrt mit dem Schließen (Stoppgrund „griff“). Danach öffnet
  `retreat_after_test` den Greifer bewusst, hebt senkrecht an und fährt zum Start („danach: am Start“).
- Die Policy selbst sagte in den letzten Chunks 0,99–1,00 voraus, wollte also geschlossen bleiben.
- G2 ist nur bis 3 Takte nach dem Griff trainiert und hat Anheben oder Halten nie gesehen.
- Im normalen Ablauf mit `--transport-geplant` hebt nach dem Griff der Planer mit geschlossenem Greifer an.
