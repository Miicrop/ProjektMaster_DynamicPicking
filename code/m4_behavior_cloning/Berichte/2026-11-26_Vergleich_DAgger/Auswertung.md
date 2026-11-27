# Anlagenvergleich 26.11.: DAgger-Modelle gegen G2 / G2b

Daten: `vergleiche/2026-11-26_12-06-00`, 15 Lagen im Raster, je Lage jedes der 6 Modelle einmal
(90 Fahrten, 12:06–13:14), `--lage-bekannt`, Probe 1 mm über dem Objekt, Glättung 0,5.
Zum Vergleich: 24.11. (`15-39-34`) und 25.11. (`14-12-31`, `15-07-38`, `15-48-59`), andere Lagen.
Skript: `skripte/auswertung.py`, je Fahrt: `fahrten.csv`.

Erfolg = geometrische Griffprüfung (Spiel ≥ 0,5 mm). quer = senkrecht zu den Backen (entscheidend),
längs = in Backenrichtung (weniger kritisch).

## 1. Überblick heute

| Modell | Erfolg | xy Median | xy p90 | \|quer\| Median | längs Median | \|Drehung\| | Takte | seitl. Weg < 60 mm |
|---|---|---|---|---|---|---|---|---|
| G2 | 4/15 | 5,5 | 9,0 | 2,3 | −3,4 | 0,7° | 103 | 18 mm |
| G2-D fest | **9/15** | 5,3 | 11,5 | **1,3** | −3,8 | 1,2° | 132 | **38 mm** |
| G2-D gemischt | 4/15 | 5,8 | 9,5 | 2,9 | −1,9 | 1,5° | 139 | **48 mm** |
| G2b | **10/15** | **2,2** | **4,8** | **0,8** | −1,0 | 0,5° | 104 | 16 mm |
| G2b-D fest | 7/15 | 5,1 | 8,4 | 1,8 | +2,1 | 0,9° | 127 | 20 mm |
| G2b-D gemischt | 7/15 | 3,4 | 5,9 | 2,3 | −2,1 | 0,6° | 113 | 21 mm |

Abbrüche ohne Griff: G2-D gemischt 6× (2× `max_steps` = hängt über dem Objekt, 3× Tisch-Stopp,
1× abgelehnt), G2-D fest 1×, G2b-D fest 1×, sonst keine.

## 2. Alte Policies heute gegen gestern

| | Fahrten | Erfolg | xy Median | \|quer\| | längs |
|---|---|---|---|---|---|
| G2 25.11. (15-48) | 20 | 9/20 | 5,4 | 1,9 | −4,9 |
| G2 heute | 15 | 4/15 | 5,5 | 2,3 | −3,4 |
| G2b 25.11. (15-48) | 20 | 8/20 | 3,4 | 2,1 | −2,2 |
| G2b heute | 15 | 10/15 | **2,2** | **0,8** | −1,0 |

G2 ist etwa gleich, G2b heute besser als gestern. Ein allgemein schlechteres Verhalten durch das
heutige Licht ist **nicht** zu sehen. Die Erfolgsquote von G2 schwankt stark, weil viele
Misserfolge knapp sind (Spiel 0,1–0,3 mm statt 0,5 mm).

## 3. Fest gegen gemischt

- G2-D: fest 9/15, gemischt 4/15. Gemischt ist in 9 von 15 Lagen quer schlechter und pendelt am stärksten.
- G2b-D: beide 7/15, gemischt quer etwas schlechter (+0,6 mm im Median), aber ohne klares Muster (7 besser / 8 schlechter).

Wichtig für die Deutung: Die beiden Varianten unterscheiden sich **nur in der Aufteilung**:
Gemischt trainiert zusätzlich auf rund 40–60 alten Val-Episoden, sonst sind Daten, Startgewichte und
Schritte gleich. Das Durchsickern der Validierung verfälscht nur die Val-Kennzahl, es macht die
Policy nicht schlechter. Ein Unterschied von 9/15 zu 4/15 ist deshalb vor allem
**Trainingsstreuung** (Zufall in Reihenfolge und Augmentierung). Folge: Mit einem Training je
Variante und einer Fahrt je Lage liegt der Unterschied zweier Modelle bis etwa ±3 Erfolge von 15 im
Rauschen.

## 4. Bringt DAgger etwas? (paarweise je Lage, \|quer\| ± 0,5 mm)

| Vergleich | besser | gleich | schlechter | Δ\|quer\| Median | Erfolg gewonnen / verloren |
|---|---|---|---|---|---|
| G2-D fest gegen G2 | 9 | 1 | 5 | −1,2 mm | +7 / −2 |
| G2-D gemischt gegen G2 | 5 | 2 | 8 | +0,9 mm | +3 / −3 |
| G2b-D fest gegen G2b | 3 | 4 | 8 | +1,0 mm | +1 / −4 |
| G2b-D gemischt gegen G2b | 1 | 5 | 9 | +1,0 mm | +0 / −3 |
| (G2b gegen G2) | 12 | 3 | 0 | −1,4 mm | +6 / −0 |

- **G2 → G2-D fest:** Quer wird klar besser, vor allem in Lagen fern vom Training (Erfolg 6/8 statt 1/8)
  und in der Reihe y = −183 (4/5 statt 0/5). Dafür pendelt das Modell doppelt so viel, braucht
  ~30 Takte mehr und streut längs stärker (−11 bis −14 mm in den Lagen 8, 9, 12).
- **G2b → G2b-D:** keine Verbesserung, eher schlechter, auch fern vom Training (fest 2/6 statt 4/6).
- Der deutlichste Effekt bleibt der zwischen den Grundmodellen: G2b ist in keiner Lage schlechter als G2.

## 5. Tischbereiche

Erfolge je Reihe (Lagen: y −263 = 1–4, y −183 = 5–9, y −104 = 10–13, y −24 = 14–15):

| Reihe | G2 | G2-D fest | G2-D gem | G2b | G2b-D fest | G2b-D gem |
|---|---|---|---|---|---|---|
| y −263 | 1/4 | 2/4 | 0/4 | 1/4 | 2/4 | 0/4 |
| y −183 | 0/5 | **4/5** | 1/5 | 3/5 | 0/5 | 2/5 |
| y −104 | 2/4 | 2/4 | 1/4 | **4/4** | 3/4 | 3/4 |
| y −24 | 1/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |

- Die Reihe y = −263 (Lagen 1–4) ist für **alle** Modelle schwer. Lage 1 und 2 schafft keines.
- Die Lagen 10–15 (y ≥ −104) sind leicht, dort sind G2b und beide G2b-D gut.
- In x zeigt sich kein klares Muster. Die Spalte x = 370 ist eher schwach (höchstens 2/3).

## 6. Pendeln über dem Objekt

Seitlicher Weg (Median) und Takte je Höhenband über dem Griffpunkt:

| Modell | 150–60 mm | 60–30 mm | 30–20 mm | < 20 mm |
|---|---|---|---|---|
| G2 | 6,0 mm / 10 | 10,1 / 25 | 3,4 / 9 | 3,5 / 8 |
| G2-D fest | **11,0 / 13** | **18,1 / 30** | **8,5 / 13** | **8,8 / 12** |
| G2-D gemischt | **10,2 / 13** | **20,2 / 34** | **7,3 / 13** | **12,7 / 17** |
| G2b | 6,3 / 10 | 9,9 / 24 | 3,0 / 9 | 3,5 / 8 |
| G2b-D fest | 6,3 / 12 | 11,7 / 28 | 3,2 / 10 | 3,8 / 10 |
| G2b-D gemischt | 5,6 / 10 | 12,3 / 29 | 3,9 / 10 | 3,6 / 9 |

- **G2-D pendelt messbar**, und zwar etwa doppelt so viel seitlich wie G2 in **allen** Höhen, nicht erst kurz vor dem Objekt.
  Die beiden `max_steps`-Fahrten von G2-D gemischt (Lagen 1 und 10) hängen bis zum Ende der Fahrt über dem Objekt.
- **G2b-D pendelt kaum mehr** als G2b (+1–2 mm im Band 60–30 mm). Es braucht aber 10–25 Takte mehr,
  sinkt also langsamer bzw. zögert. Das wirkt an der Anlage vermutlich wie Pendeln.

## 7. Sind die Fehlgriffe Ausreißer?

Meist nicht. Die Misserfolge kommen aus der normalen Streuung, nicht von einzelnen Ausreißern (Robustmaß 2,5 × MAD):

- G2b: quer-Streuung (MAD) 1,2 mm. Die 5 Misserfolge sind knapp (Spiel −0,8 … 0,0 mm, einmal −2,5 mm),
  nur Lage 1 und 4 sind Ausreißer.
- G2, G2-D, G2b-D: MAD 2,4–4,2 mm, die Fehlgriffe liegen in der Streuung.
  Echter Ausreißer: Lage 10 bei beiden G2-D (Drehung 8°, quer 5 mm). Bei G2b-D fest sind es Lage 2 (quer 8,5 mm) und Lage 6 (Drehung −5°).

Für G2b heißt das: Schon gut 0,5–1 mm weniger Streuung quer würde mehrere Misserfolge zu Erfolgen machen.

## 8. Korrigieren weiter oben? Aufnahme 23.11. gegen 25.11.

Aus den `meta.json` der DAgger-Episoden:

| | Episoden | Übernahme durch Experten | Experte senkt noch ab | Korrektur xy | Expertentakte |
|---|---|---|---|---|---|
| 23.11. (in G2b, gefahren mit G2) | 44 (40 im Training) | Probe-Abstand 10–25 mm, **~19 mm über PICK** | 19 mm | 3,1 mm | 44 |
| 25.11. G2 (in G2-D) | 50 | Probe-Abstand 1 mm, **~10 mm über PICK** | 10 mm | 3,2 mm | 37 |
| 25.11. G2b (in G2b-D) | 50 | Probe-Abstand 1 mm, ~10 mm über PICK | 10 mm | 2,0 mm | 34 |

Am 25.11. hat der Experte also erst etwa 3 mm über der Objektoberkante übernommen und die
Querkorrektur auf den letzten ~10 mm gemacht. Am 23.11. war es etwa 12 mm über der Oberkante.

Die Daten passen zu deiner Vermutung, beweisen sie aber nicht:
- Die späte Übernahme vom 25.11. bringt der Policy bei, kurz vor dem Objekt noch seitlich nachzusetzen. Folgt sie dem unsicheren Bild, wird daraus Hin und Her.
  G2-D (nur 25.11.-Fahrten) pendelt stark. G2b mit den Fahrten vom 23.11. pendelt nicht mehr als G2.
- Aber: G2 ist das schwächere Grundmodell (399 Episoden, DAgger-Anteil 11 %). G2b-D hat ebenfalls die
  späten Fahrten und pendelt kaum. Sauber trennen lässt sich das nur mit einem Training ohne die Fahrten vom 25.11. (Abschnitt 10).

**Glättung** (Laufliste vom 23.11. vom Nutzer, Ruckeln = Median |Δ²TCP| im Policy-Teil; Tiefpass alpha,
kleiner = stärker geglättet). Alle Fahrten am 23.11. fuhr **G2**, nicht G2b:

| Episoden | Glättung | im Training von G2b | Ruckeln | Probe-Abstand | Korrektur xy |
|---|---|---|---|---|---|
| 0–3 | aus (1,0) | nein (weggelassen) | 3,22 mm | | |
| 4–11 | 0,25 | ja | 1,19 mm | 20 mm | 5,3 mm |
| 12–28 | 0,5 | ja | 1,49 mm | 10 mm | 2,9 mm |
| 29–43 | 0,25 | ja | 1,00 mm | 10 mm | 2,8 mm |
| 25.11. G2 / G2b (in G2-D / G2b-D) | 0,5 | – | 1,45 / 1,32 mm | 1 mm | 3,2 / 2,0 mm |

Das Ruckeln bestätigt die Liste: Episoden 0–3 ohne Tiefpass sind deutlich unruhiger, 0,25 ist am ruhigsten.
In G2b stecken also zwei Glättungen: 23 Episoden mit 0,25 und 17 mit 0,5. Die ungeglätteten Fahrten sind nicht dabei.
Die Folgen sind vermutlich klein. Die Ziele (Labels) des Policy-Teils werden auf die Idealbahn umgeschrieben
(`bc/dagger.py`, Versatz im Median 3–5 mm), die Glättung steckt also nur in Bildern und Zuständen.
Stärkere Glättung (0,25) lässt die Fahrt etwas mehr hinterherlaufen, das ergibt etwas größere Versätze
zur Idealbahn und damit stärkere Korrekturen in den Labels. Der Experte fährt ohnehin geplant.
Die Fahrten vom 25.11. und die heutigen Tests liefen mit 0,5.

**Warum hat G2b von G2 gelernt, G2b-D aber nicht von G2b?** Hier zählt neben der Höhe auch die Größe der Korrekturen:

| DAgger-Fahrten | gefahren von | Korrektur xy Median | > 3 mm | < 1,5 mm | Griff wäre ohne Experte gelungen |
|---|---|---|---|---|---|
| 23.11. (4–43) | G2 | 2,9 mm | 18 / 40 | 7 / 40 | (nicht bewertet) |
| 25.11. G2 | G2 | 3,2 mm | 27 / 50 | 2 / 50 | 15 / 50 |
| 25.11. G2b | G2b | **2,0 mm** | **5 / 50** | **20 / 50** | **25 / 50** |

G2b macht schon kleine Fehler. Die Hälfte seiner DAgger-Fahrten wäre auch ohne Experten ein Erfolg gewesen,
und 40 % der Korrekturen sind kleiner als 1,5 mm, also etwa so groß wie die Streuung von G2b selbst (MAD 1,2 mm).
Dazu kommt die späte Übernahme: Diese kleinen Korrekturen fallen in die letzten ~10 mm.
Die Policy lernt daraus vor allem „kurz vor dem Objekt noch etwas seitlich nachsetzen“, aber kaum eine bessere Lage.
Das passt dazu, dass G2b-D 10–25 Takte länger braucht und quer nicht besser wird.
G2-D bekam ebenfalls späte, aber große Korrekturen (meist > 3 mm). Es wird quer besser und pendelt dafür.
Die Höhe erklärt also vermutlich das Pendeln und Zögern, die Größe der Korrekturen, ob die Genauigkeit gewinnt.
Ein dritter möglicher Grund: G2b ist von Grund auf mit 10 000 Schritten trainiert, G2b-D nur mit 3000 Schritten nachtrainiert.

**Weißabgleich 23.11.:** Die DAgger-Fahrten vom 23.11. hatten an der Handkamera einen anderen Weißabgleich
(2,609 / 1 / **1,898** statt 2,641 / 1 / 2,609), ihre Bilder sind deutlich weniger blau (B/G 0,66 statt 0,88).
G2b hat also auch Bilder mit anderer Farbe gesehen. Das kann zu seiner Robustheit beitragen (wie eine Farb-Augmentierung).

## 9. Licht

Werte aus der Kamerapruefung (Median [min..max]):

| | Hand Hell. | Hand R/G | Szene Hell. | Szene R/G | Szene Sättigung |
|---|---|---|---|---|---|
| Training (Bereich) | 29..50 | 2,15..2,24 | 142..159 | 1,40..1,57 | 105..128 |
| 25.11. 15-48 | 32 | 2,18 | 150 | 1,46 | 116 |
| 26.11. | 35 [33..39] | 2,18 | 158 [150..168] | **1,40** [1,37..1,47] | **102** [92..110] |

- Die Handkamera liegt mitten im Trainingsbereich.
- Die **Szenenkamera** lag heute am Rand: heller, weniger rot, und die Sättigung lag mit 102 **unter** dem
  Trainingsbereich. Die Kamerapruefung meldet trotzdem überall OK, sie ist hier zu großzügig.
- Ein klarer Lichteffekt auf das Ergebnis ist nicht zu sehen: G2b war heute besser als gestern.
  Die Korrelation von \|quer\| mit der Helligkeit der Handkamera (ρ = −0,47) hängt an der Lage auf dem Tisch
  (die Helligkeit ändert sich mit der Position) und lässt sich davon nicht trennen.

**Werden neue DAgger-Daten unter dem heutigen Licht helfen?** Für die Lichtrobustheit ein wenig: Sie
erweitern den Bereich der Szenenkamera (Sättigung ~100). Bei ~7–10 % Anteil im Datensatz ist der Effekt
aber klein. Wirksamer wäre `--licht-augment` beim Training (variiert Helligkeit, Kontrast, Sättigung und Farbton).
Die Lagegenauigkeit verbessert DAgger nur, wenn die Korrekturen selbst nicht neues Pendeln beibringen (Abschnitt 8).

## 10. Vorschlag für das weitere Vorgehen

1. **Basis bleibt G2b.** Es ist das beste und stabilste Modell. G2-D gemischt und G2b-D gemischt nicht weiterverfolgen.
2. **Nächste DAgger-Runde mit G2b, Übernahme weiter oben** wie am 23.11.: Probe-Abstand etwa 10–20 mm,
   also Übernahme etwa 20 mm über PICK. Die Korrektur ist dann während des Absenkens fertig und sieht aus
   wie die Demonstrationen. Schwerpunkt auf schwierigen Lagen: Reihe y = −263, Spalte x = 370, Lagen fern vom Training.
   Weißabgleich fest wie im Training (2,641 / 1 / 2,609), heutiges Licht ist in Ordnung.
   Weil G2b selten weit danebenliegt, gezielt Lagen fahren, in denen es danebengreift.
   Fahrten mit sehr kleiner Korrektur (< 1,5 mm) bringen kaum etwas: Weglassen oder schwächer gewichten
   (`--episoden-gewichte`) wäre einen Versuch wert.
3. **Training als Vergleich mit zwei Varianten**, beide `--init-from G2b --val-wie G2b`, 3000 Schritte:
   - A: G2b-Daten + neue Fahrten mit hoher Übernahme (ohne die Fahrten vom 25.11.)
   - B: wie A + Fahrten vom 25.11.
   Damit lässt sich die Übernahmehöhe von der Datenmenge trennen. Zusätzlich lohnt sich A mit `--licht-augment`.
4. **Streuung messen:** Bevor über ±2 Erfolge entschieden wird, z. B. A mit zwei Seeds trainieren
   oder je Lage zwei Fahrten. Fest gegen gemischt zeigt, dass Trainingsstreuung allein 9/15 gegen 4/15 ergeben kann.
5. G2-D fest ist ein interessanter Nebenbefund: Es greift quer genauer, pendelt aber stark. Ein Weitertrainieren
   lohnt erst, wenn sich in Schritt 3 zeigt, dass eine hohe Übernahme das Pendeln verhindert.

## 11. Nachmittag 26.11.: DAgger mit Stoß und echte Griffe (G2b)

Daten: `data/2026-11-26_dagger` (40 Episoden, G2b, Glättung 0,5, Probe-Abstand 14 mm), Rollouts
`checkpoints/G2b_580_dagger_nur_griff/policy/rollouts/2026-11-26_14-*` (DAgger-Läufe ohne `summary.json`:
der JSON-Fehler der Stoß-Einstellung, inzwischen behoben; echte Griffe 14-30 bis 14-36).

**Stoß:** 27 der 40 Fahrten mit Stoß, in drei Stufen. Übernahme durch den Experten bei 22–25 mm über PICK.

| Einstellung | Fahrten | xy beim Stopp | \|quer\| | Spiel | Fehlgriff |
|---|---|---|---|---|---|
| ohne Stoß (alle Stufen) | 14 | 2,1 mm | 1,3–1,7 mm | 0,6–0,9 mm | 3 |
| 4–8 mm, 0–4°, 70–110 mm | 9 | 1,7–2,1 mm | 0,5–0,7 mm | 1,7–1,9 mm | 1 |
| 6–10 mm, 0–5°, 50–80 mm | 10 | 2,4 mm | 1,1 mm | 1,3 mm | 0 |
| 10–16 mm, 0–10°, 50–80 mm | 7 | 2,0 mm | 1,2 mm | 1,1 mm | 0 |

G2b fängt auch Stöße bis ~15 mm und 8° vollständig, bevor es 14 mm über der Oberkante ist. Die Fahrten mit Stoß
sind dort nicht schlechter als die ohne. Der Experte korrigiert danach im Median ~2 mm und < 0,5°.

**Griffprüfung bei 14 mm:** 35 von 40 sind „Warnung“, aber fast immer nur wegen der Höhe. Der Rest der
Vorhersage endet 14–19 mm über PICK (Warnung ab 5 mm), die letzten ~15 mm bewertet die Prüfung also nicht.
`--dagger-nur-fehlgriffe` lässt nur „Erfolg“ weg und behält damit hier fast alles.

**Echte Griffe: Das Schwanken sitzt auf den letzten ~10 mm.** Seitlicher Weg und Takte je Band über der Greifhöhe
(Höhe beim Schließen):

| Lauf | 150–60 mm | 60–30 | 30–20 | 20–10 | **10 bis Griff** |
|---|---|---|---|---|---|
| 14-32 (Griff) | 5,8 mm / 10 T | 9,9 / 23 | 2,5 / 9 | 4,9 / 11 | **13,7 / 17** |
| 14-34 (Griff) | 6,4 / 10 | 12,7 / 28 | 3,7 / 10 | 7,1 / 15 | **9,9 / 12** |
| 14-35 (Tisch-Stopp) | 4,7 / 10 | 12,5 / 33 | 3,4 / 10 | 6,6 / 13 | **11,5 / 6** |
| 14-36 (Griff) | 5,7 / 10 | 13,1 / 28 | 3,5 / 9 | 2,8 / 9 | **13,4 / 15** |
| 14-30 (Arm steht) | 6,9 / 11 | 13,9 / 27 | 6,8 / 11 | 6,6 / 11 | **15,9 / 23** |

Unterhalb der Objektoberkante macht die Policy in 3–5 Takten seitliche Sprünge von 4–10 mm (14-32: Takt
119–124 von −5 auf 0 mm, 14-35: Takt 125–129 von +9,6 auf 0 mm), die Höhe springt um ±3 mm, und die Streuung
der Vorhersagen steigt von ~0,005 auf 0,02–0,1 rad. Die Policy ist dort unsicher und springt zwischen Lösungen.
Diesen Bereich sieht kein Test mit Probegriff und keine DAgger-Fahrt, weil beide über der Oberkante stoppen.
Auf den Höhen, auf denen DAgger arbeitet, ist G2b schon gut.

**Folgerung:** Mehr DAgger über dem Objekt bringt wenig. Am wirksamsten wäre ein **geplanter Endabstieg**:
Die Policy führt bis etwa 10–15 mm über die Oberkante, dann wird senkrecht auf die Greifhöhe abgesenkt
(Tischhöhe + Greifhöhe sind bekannt, PICK wird nicht gebraucht) und geschlossen, wie beim geplanten Transport.
Nach den DAgger-Stopps von heute (xy ~2 mm, Spiel meist > 0,5 mm) gelänge das in ~36 von 40 Fahrten.

## 12. In welcher Höhe ist G2b am genauesten? (Endabstieg, 27.11.)

Skript `skripte/hoehen_g2b.py`, Werte je Fahrt und Höhe: `hoehen_g2b.csv`. Grundlage sind alle G2b-Fahrten mit bekanntem PICK
(180 Fahrten: 77 aus Vergleichen, 14 Policy-Tests, 89 DAgger). Echte Griffe ohne PICK fehlen.
Je Höhe über der Objektoberkante (Oberkante = PICK + 7 mm) wird die Lage des TCP genommen und geprüft,
ob der Griff gelänge, wenn man von dort **senkrecht** abstiege (geometrische Griffprüfung, Spiel ≥ 0,5 mm = Erfolg,
0–0,5 mm = Warnung). „mit pick“ heißt: Endabstieg auf PICK, wenn er höchstens 6 mm und 5° neben der Policy liegt, sonst senkrecht.

Die Vergleichsfahrten sind auf 1 mm Probe-Abstand eingestellt. Der TCP stoppt aber schon **~4–5 mm über der Oberkante**,
weil der Stopp mit Vorausschau ausgelöst wird. Darunter gibt es nur die Vorhersage der Policy, daraus entsteht die offizielle Bewertung.
Verglichen wird in jeder Zeile **dieselbe Menge an Fahrten**: alle, die bis 5 mm über die Oberkante kamen.

**Vergleiche 24.–26.11.** (53 Fahrten). quer = senkrecht zu den Backen (entscheidend, Spiel je Seite ~2,5 mm),
längs = in Backenrichtung (unkritischer). Beides als Betrag.

| Höhe über Oberkante | quer Median | quer p90 | längs Median | längs p90 | Drehung | Erfolg | Warnung | Fehlgriff | Erfolg+Warnung | mit pick |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 mm | 1,3 mm | 2,9 mm | 2,1 mm | 4,3 mm | 0,52° | 66 % | 15 % | 19 % | 81 % | 92 % |
| 8 mm | 1,1 mm | 2,9 mm | 2,2 mm | 4,4 mm | 0,44° | 68 % | 17 % | 15 % | 85 % | 94 % |
| 10 mm | 1,1 mm | 2,6 mm | 2,3 mm | 4,0 mm | 0,49° | 70 % | 17 % | 13 % | 87 % | 96 % |
| 12 mm | 1,1 mm | 2,8 mm | 2,1 mm | 4,2 mm | 0,46° | 74 % | 13 % | 13 % | 87 % | 96 % |
| 13 mm | 1,2 mm | 2,9 mm | 2,0 mm | 4,0 mm | 0,40° | 72 % | 13 % | 15 % | 85 % | 94 % |
| 14 mm | 1,2 mm | 2,7 mm | 2,0 mm | 4,0 mm | 0,33° | 74 % | 9 % | 17 % | 83 % | 96 % |
| 15 mm | 1,1 mm | 2,4 mm | 1,9 mm | 4,0 mm | 0,36° | 75 % | 13 % | 11 % | 89 % | 96 % |
| 18 mm | 1,0 mm | 2,9 mm | 2,3 mm | 4,0 mm | 0,39° | 81 % | 6 % | 13 % | 87 % | 96 % |
| 20 mm | 1,0 mm | 2,3 mm | 2,2 mm | 4,1 mm | 0,41° | 74 % | 17 % | 9 % | 91 % | 98 % |
| 10–15 mm zusammen | 1,1 mm | 2,7 mm | 2,0 mm | 4,1 mm | 0,43° | 73 % | 13 % | 14 % | 86 % | 96 % |
| 12–14 mm zusammen | 1,1 mm | 2,8 mm | 2,1 mm | 4,1 mm | 0,41° | 73 % | 12 % | 15 % | 85 % | 96 % |
| **am Stopp (~4–5 mm)** | 1,3 mm | 2,8 mm | 2,3 mm | 4,4 mm | 0,52° | 68 % | 11 % | 21 % | 79 % | – |
| **offiziell** (Policy bis zum Griff, 37 bewertet) | – | – | – | – | – | 49 % | 0 % | 51 % | 49 % | – |

**Alle Fahrten** (94, Vergleiche + Policy-Tests + DAgger 25.11.):

| Höhe | quer Median | quer p90 | längs Median | längs p90 | Drehung | Erfolg+Warnung | mit pick |
|---|---|---|---|---|---|---|---|
| 5 mm | 1,1 mm | 2,7 mm | 1,3 mm | 4,1 mm | 0,63° | 86 % | 94 % |
| 10 mm | 1,1 mm | 2,5 mm | 1,5 mm | 3,8 mm | 0,56° | 88 % | 96 % |
| 12 mm | 1,1 mm | 2,8 mm | 1,3 mm | 3,9 mm | 0,50° | 88 % | 96 % |
| 15 mm | 1,1 mm | 2,4 mm | 1,4 mm | 3,6 mm | 0,38° | 89 % | 96 % |
| 20 mm | 1,1 mm | 2,4 mm | 1,2 mm | 3,8 mm | 0,37° | 90 % | 97 % |
| 10–15 mm zusammen | 1,1 mm | 2,7 mm | 1,4 mm | 3,8 mm | 0,46° | 88 % | 95 % |
| am Stopp (~4–5 mm) | 1,0 mm | 2,8 mm | 1,5 mm | 4,4 mm | 0,70° | 84 % | – |
| offiziell (70 bewertet) | – | – | – | – | – | 54 % | – |

DAgger 26.11. (Stopp ~15–18 mm, nur 18–20 mm auswertbar, 33 Fahrten): Senkrecht von 18–20 mm ergäbe 94 % mit Stoß (21) und
81 % ohne Stoß (12). Mit pick wären es 100 %. Die offizielle Bewertung ist dort fast immer „Warnung“ wegen der Höhe und
lässt sich hier nicht vergleichen.

**Ergebnis:**
- Senkrecht abzusteigen statt die Policy bis unten fahren zu lassen, hebt Erfolg+Warnung von **~50 % auf ~85–90 %**, mit pick auf **~95 %**.
- Zwischen 9 und 20 mm über der Oberkante ändert sich kaum etwas (85–91 %, eine Fahrt = 2 %). Es gibt **keine scharf beste Höhe**.
  Unter ~8 mm wird es schlechter (5 mm: 81 %, am Stopp: 79 %), vor allem die Drehung wandert dann weg (0,52° statt ~0,4°).
- Für den Endabstieg passen **10–15 mm** (Standard 12 mm). Wer mehr Abstand zur unruhigen Zone will, nimmt 15 mm.
- Quer bleibt von 20 mm bis 5 mm praktisch gleich (Median ~1,1 mm, p90 ~2,5–2,9 mm). Was sich nach unten verschlechtert, ist
  vor allem die **Drehung** (0,36–0,41° oben, 0,52–0,70° am Stopp), und am Stopp auch längs (p90 4,4 mm).
- Die verbleibenden ~10–15 % Fehlgriffe sind die Fahrten mit großem quer (p90 ~2,7 mm, bei ~2,5 mm Spiel je Seite). Sie liegen
  schon hoch oben daneben. Senkrecht behebt das nicht, nur pick.
