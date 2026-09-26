# Blueprint – Projektarbeit „Dynamisches Greifen und automatisierte Sichtprüfung mit einem kollaborativen Roboter“

Ergebnis des geführten Planungsdialogs (ARS `academic-paper`, Modus `plan`) vom 2026-09-26.
Dieses Dokument ist die Referenz für alle Kapitelentwürfe. Änderungen an Umfang oder Gliederung bitte hier nachtragen.

---

## 1. Rahmen

| Punkt | Festlegung |
|---|---|
| Art | Projektarbeit (HS Kempten), **begleitend und beschreibend**, keine Forschungsfrage |
| Autoren | Niklas Tollmann, Joshua Junt, Felix Krawczyk, Jeremy Zid |
| Sprache / Stil | Deutsch, rein technisch. Die Teamorganisation wird nicht thematisiert. |
| Zitierstil | IEEE (biblatex `style=ieee`, biber); Quellen nur aus `references.bib`, neue Quellen nur mit geprüfter DOI |
| Umfang | ca. **40–60 Seiten Text**, mit Abbildungen und Tabellen insgesamt 50–80 Seiten |
| Erfolgskriterium des Projekts | Der Ablauf aus Erkennen, Greifen, Prüfen und Sortieren läuft **vollständig automatisch** durch. Messwerte sind nur zur Demonstration da und haben keine echten Toleranzen. |
| Stand | Noch **keine echten Tests**. Ergebnisse, Probleme und Fazit werden nach den Versuchen ergänzt. |
| Arbeitsweise | Claude schreibt Entwürfe für alle Kapitel (außer M4). Die verantwortliche Person passt ihr Kapitel an. |

## 2. INSIGHT Collection

- **[INSIGHT: roter Faden]** (Wortlaut Nutzer) *„Was wir gemacht haben und ob es funktioniert hat und mit welchen Schritten wir damit Erfolg hatten.“*
- **[INSIGHT: Rahmen]** Die Aufgabe ist selbst gewählt, ein Interessensprojekt mit industrienaher Umsetzung.
- **[INSIGHT: industrienah]** (Wortlaut Nutzer) *„Weil die Verfahren absichtlich einfach gewählt wurden und die Inline-Qualitätsprüfung typisch ist etc. Dynamisches Handling ist auch sehr wichtig in der Automatisierung.“*
- **[INSIGHT: Aufteilung Grundlagen/Umsetzung]** Kapitel 03 gibt einen breiten Überblick einschließlich Alternativen. Die Modulkapitel beschreiben nur die umgesetzte Lösung und begründen die Wahl mit einem Verweis auf Kapitel 03.
- **[INSIGHT: contribution_claim]** (Wortlaut Nutzer) *„Das Projekt wird evtl. weiter verwendet. Ein Laboringenieur will damit Mensch ärgere dich nicht gegen Senioren spielen lassen und kann Teile des Projekts gebrauchen. Das ist quasi Teil eines Pflegerobotik-Projekts.“*
  → **Offen:** ob und wo das in der Arbeit erwähnt wird (Einleitung, Fazit oder Ausblick). Das entscheidet das Team.
- **[OFFEN: schwächster Punkt]** Die Frage aus dem Belastungstest (Schritt 3) wurde bewusst zurückgestellt.
- **[Annahme]** ArUco-Marker funktionieren, weil die Marker ersetzt werden. Der Rückfall auf den weißen Rahmen ist nur eine Randnotiz.

## 3. Konventionen für die Entwürfe

- **Kein Quellcode** im Text, nur Ablaufdiagramme und **Pseudocode** zum Verständnis. Pakete: `algorithm` + `algpseudocode`.
- **Offene Punkte** stehen als sichtbare `\todo{…}` im Text (Paket `todonotes`). Fehlende Abbildungen werden als Platzhalter per `\missingfigure{…}` eingefügt.
- **Abkürzungen** nur über `\ac{…}` (`00_abkuerzungen.tex`), z. B. OCR, TCP, PTP, LIN, ROI, HSV, KS.
- **Keine Irrwege und Entwicklungsprobleme** in den Entwürfen. Tatsächliche Probleme werden nach den Tests ergänzt.
- **Freie Gliederung** der Modulkapitel, je nachdem, was das Kapitel braucht.
- Allgemeine Aussagen zur Automatisierung (Motivation) werden entweder **belegt** (Quelle mit DOI) oder als **eigene Motivation** formuliert, nicht als unbelegte Tatsache.

## 4. Kapitelplan

Die neue Kapitelfolge enthält ein zusätzliches Kapitel „Integration und Bedienung“:

| Nr. | Datei (Vorschlag) | Kapitel | Umfang (Seiten) | Verantwortlich |
|---|---|---|---|---|
| 1 | `02_einleitung.tex` | Einleitung | 3–4 | alle / Entwurf Claude |
| 2 | `03_grundlagen.tex` | Grundlagen | 10–14 | alle / Entwurf Claude |
| 3 | `04_systemkonzept.tex` | Systemkonzept | 6–8 | Niklas / Entwurf Claude |
| 4 | `05_objekterkennung.tex` | Objekterkennung (M1) | 5–6 | Person 1 / Entwurf Claude |
| 5 | `06_robotersteuerung.tex` | Robotersteuerung (M2) | 5–6 | Person 2 / Entwurf Claude |
| 6 | `07_sichtpruefung.tex` | Sichtprüfung (M3) | 5–6 | Person 3 / Entwurf Claude |
| 7 | `08_ki_greifen.tex` | KI-basiertes Greifen (M4) | *(Person 4)* | **Person 4, kein Entwurf** |
| 8 | `09_integration.tex` **(neu)** | Integration und Bedienung | 3–5 | Niklas / Entwurf Claude |
| 9 | `10_evaluation.tex` (bisher `09_evaluation.tex`) | Evaluation | 4–6 | alle / Gerüst Claude |
| 10 | `11_fazit.tex` (bisher `10_fazit.tex`) | Fazit (mit Diskussion) | 2–3 | alle / nur Gerüst |
| | | **Summe ohne M4** | **≈ 43–58** | |

---

### Kap. 1 – Einleitung
**Kernaussage:** Ein selbst gewähltes, industrienah umgesetztes Projekt zeigt, wie Erkennen, Greifen, Prüfen und Sortieren automatisch zusammenspielen.
1. **Motivation:** dynamisches Handling (Teile ohne feste Zuführung), Inline-Qualitätsprüfung, bewusst einfache und robuste Verfahren. *Quellen nötig (siehe §5) oder als eigene Motivation formulieren.*
2. **Aufgabenstellung:** vorhandener Text bleibt.
3. **Ziel:** vollautomatischer Durchlauf als Erfolgskriterium, die Messungen sind demonstrativ.
4. **Abgrenzung (neu):** ein Bauteil, flach liegend (2D-Pose x, y, θ), keine sicherheitszertifizierte Anlage (Betrieb unter Aufsicht, reduzierte Geschwindigkeit), M4 optional und nicht Voraussetzung für den Demonstrator.
5. **Aufbau der Arbeit:** an die neue Kapitelfolge anpassen.

### Kap. 2 – Grundlagen
**Kernaussage:** Breiter Überblick über die verwendeten und die alternativen Verfahren. Die Modulkapitel verweisen hierher.
1. Digitale Bildverarbeitung: Filter, Schwellwerte (Otsu `otsu1979`), Morphologie, Konturen, Bildmomente; OpenCV `bradski2000opencv`
2. **Farbräume (RGB/HSV)** (neu): Begründung für die farbunabhängige Segmentierung über Helligkeit und Sättigung. *Quelle nötig.*
3. Kameramodell und Kalibrierung: Lochkamera, Verzeichnung, Zhang `zhang2000`, `hartley2004`
4. Fiducial Marker und Homographie: ArUco `garrido2014`, DLT und perspektivische Entzerrung `hartley2004`
5. Koordinatentransformationen: homogene Koordinaten, Starrkörper-Fit nach der Methode der kleinsten Quadrate `umeyama1991`
6. Industrierobotik und Greifen: Basis-/TCP-KS, PTP/LIN, Greifertypen, kollaborative Roboter und Sicherheit `siciliano2016`
7. Optische Messtechnik: Beleuchtung, Kanten, Hough `duda1972`, **Ellipsen- und Kreis-Fit (Least Squares)**, **Template-Matching und Konturanalyse**, Pixel-zu-mm-Umrechnung. *Quellen für Fit und Template nötig.*
8. Texterkennung (OCR): Ablauf einer OCR-Pipeline, Tesseract `smith2007`, lernbasierte Verfahren und EasyOCR `easyocr`
9. Lernbasiertes Greifen: **leerer Platzhalter** `\todo{Person 4}`

*Nicht in Kap. 2:* Zustandsautomat und Interfaces. Das ist Allgemeinwissen und steht direkt in Kap. 3.

### Kap. 3 – Systemkonzept
**Kernaussage:** Ein modulares System mit klaren Schnittstellen und stufenweiser Inbetriebnahme.
1. **Anforderungen:** Tabelle mit funktionalen Anforderungen (Erkennen, Greifen, Prüfen, Sortieren, automatischer Durchlauf) und **qualitativen** nicht-funktionalen Anforderungen (robust bei Raumlicht, Module austauschbar, sichere Bewegung). **Keine Zahlenwerte.**
2. **Hardwareaufbau:** LARA (6 Achsen, v5.0.8), Greifer, Top-down- und Seitenkamera, ArUco-Marker (`DICT_4X4_50`), Bauteil (lila 3D-Druck-Quader mit Fase, Etikett, Loch, Kerbe), Ablagen. `\todo`s für Kameramodelle, Greifermontage und Beleuchtung. Platzhalter für Foto bzw. Skizze.
3. **Softwarearchitektur:** Orchestrator, Zustandsautomat (Diagramm aus `plan/01`), Datenobjekte `ObjectPose`, `InspectionResult`, `RobotTarget` (als Tabelle, nicht als Code), Modul-Interfaces, Austauschbarkeit M1 ↔ M4, Mock-Implementierungen.
4. **Koordinatensysteme:** Bild-KS, Arbeitsbereich-KS und Roboter-KS werden nur beschrieben. **Kalibrierverfahren → `\todo{Verfahren noch offen}`**.
5. **Test- und Inbetriebnahmestrategie (neu):** Mock → Replay (Testfotos) → Simulator (`fake_neura_server`) → Real, pro Modul umschaltbar. Dass das System ohne Roboter getestet werden kann, wird **erwähnt, aber nicht als Anforderung versprochen**.

### Kap. 4 – Objekterkennung (M1)
1. Aufgabe und Schnittstelle (`detect() → ObjectPose`)
2. Verarbeitungskette als Ablaufdiagramm: ArUco-Detektion → Homographie → entzerrte Draufsicht; Rückfall auf den weißen Rahmen nur als kurzer Hinweis
3. Segmentierung relativ zum Median der Platte (Helligkeit/Sättigung), dadurch unabhängig von der Bauteilfarbe. Verweis auf Kap. 2 (Otsu als Alternative)
4. Pose: Schwerpunkt, `minAreaRect`, eindeutiges θ ∈ [0°, 360°) über die Fase. **Pseudocode: Pose- und Fasenbestimmung**
5. Übergabe im Roboter-KS (Verweis auf Kap. 3.4)
6. `\todo`s: intrinsische Kalibrierung, Parallaxe durch die Bauteilhöhe

### Kap. 5 – Robotersteuerung (M2)
1. Aufgabe und Schnittstelle (`connect`, `home`, `pick`, `place`, `stop`)
2. Roboter-API: NeuraPy (JSON über TCP), Posen in m/rad, Programmablauf (`init_program` … `stop`) `neura2025neurapy`
3. Greif- und Ablegesequenz: Vorposition (PTP) → absenken (LIN) → greifen/lösen → anheben. **Pseudocode: `pick()` / `place()`**
4. Benannte Posen: `home`, `inspection`, `bin_good`, `bin_bad`
5. Sicherheit: reduzierte Geschwindigkeit, Software-Arbeitsraumgrenzen, Plausibilitätsprüfung, `stop()` mit Quittierung
6. `\todo`s: Greifer-Rückmeldung, Greifer-Offset/yaw-Konvention, geteachte Posen

### Kap. 6 – Sichtprüfung (M3)
1. Aufgabe, Schnittstelle und Prüfmerkmale (Seriennummer, Lochdurchmesser, Kerbe)
2. Bauteil über HSV finden, ROIs relativ zur Bauteil-Box, Maßstab über die Bauteilhöhe
3. Loch: Region + Ellipsen-Fit → Durchmesser (Hough nur als Alternative in Kap. 2)
4. Kerbe: rechteckigste Region über drei Wege (Helligkeit, Sättigung, Kanten); Template-Matching nur als Alternative in Kap. 2
5. OCR: EasyOCR mit Ziffern-Allowlist + Regex `^[0-9]{5}$` `easyocr`
6. Gut/Schlecht-Logik: alle drei Merkmale erfüllt → Gutteil, sonst Gründe in `reasons`. **Pseudocode: Gut/Schlecht-Entscheidung**
7. `\todo`s: Beleuchtung, mechanischer Anschlag, Bauteilmaße aus der Zeichnung

### Kap. 7 – KI-basiertes Greifen (M4)
**Kein Entwurf.** Nur die Kapitelüberschrift mit `\todo{Person 4}`.

### Kap. 8 – Integration und Bedienung (neu)
1. Ablauf eines Zyklus mit echten Modulen (Sequenzdiagramm aus `plan/00`)
2. Konfiguration: `system.yaml`, Auswahl der Varianten über die Factory (mock/replay/camera/sim/real/ai)
3. Bedienoberfläche: Tabs pro Modul, Tab *Ablauf*, Einstellungen, gemeinsame `Session`. **Platzhalter für GUI-Screenshots.**
4. Fehlerbehandlung und Sicherheit im Ablauf: Zustand `ERROR`, `robot.stop()`, Quittieren, STOPP-Knopf in eigenem Thread
5. Protokollierung: Zyklus-CSV, optional Debug-Bilder, Überleitung zu Kap. 9

### Kap. 9 – Evaluation
**Charakter:** Funktionsnachweis, keine Messkampagne. **Kennzahlen: offen** (ob und welche).
1. Versuchsaufbau und Vorgehen
   - **Versuchsreihe 1 – Wiederholbarkeit:** Ein Gutteil wird mehrfach von Hand an zufällige Stellen gelegt, jeweils mit vollständigem Zyklus.
   - **Versuchsreihe 2 – Aussortierung:** gezielt fehlerhafte Teile: (a) ohne Kerbe, (b) falscher Lochdurchmesser, (c) Seriennummer-Etikett abgerissen
2. Ergebnisse Versuchsreihe 1 → `\todo`
3. Ergebnisse Versuchsreihe 2 → `\todo`
4. Vergleich klassischer und KI-basierter Ansatz → `\todo{Person 4}`
*(Die Diskussion wandert ins Fazit.)*

### Kap. 10 – Fazit
**Inhalt offen.** Nur das Gerüst mit `\todo`s: Zusammenfassung, Diskussion (aus Kap. 9 verschoben), Ausblick (ob und was ist offen).

---

## 5. Quellen-Sammelliste (noch zu beschaffen)

Aus `references.bib` sind bereits verwendbar: `garrido2014`, `zhang2000`, `hartley2004`, `umeyama1991`, `otsu1979`, `duda1972`, `smith2007`, `bradski2000opencv`, `siciliano2016`, `morrison2018` (für Person 4), `neura2025neurapy`, `neura2024offlinesim`, `easyocr`.

**Neue Quellen**, die bei Bedarf beschafft werden müssen. Die Kandidaten sind **unverifiziert**, deshalb vor der Übernahme die DOI prüfen (z. B. mit `/ars-lit-review`):

| Thema | Kapitel | Kandidat (unverifiziert) |
|---|---|---|
| Flexible Automatisierung, dynamisches Handling | 1 | offen, Literatursuche nötig |
| Inline-Qualitätsprüfung / industrielle Bildverarbeitung | 1, 2.7 | offen, z. B. ein Lehrbuch zur industriellen Bildverarbeitung |
| Farbräume / HSV | 2.2 | A. R. Smith, „Color gamut transform pairs“, SIGGRAPH 1978 |
| Ellipsen-Fit | 2.7 | Fitzgibbon, Pilu, Fisher, „Direct least square fitting of ellipses“, IEEE TPAMI 1999 |
| Template-Matching | 2.7 | Brunelli, *Template Matching Techniques in Computer Vision*, Wiley 2009 |
| Lernbasierte OCR (Grundlage für EasyOCR) | 2.8 | Baek et al., CRAFT (CVPR 2019); Shi et al., CRNN (IEEE TPAMI 2017) |
| Kollaborative Roboter / Sicherheit | 2.6 | ISO 10218 / ISO/TS 15066 (Norm, keine DOI) |

## 6. Nebenbefunde in `main.tex` (vor dem Schreiben korrigieren)

- `\thesiscourse`: „Automatisierungstechik“ → „Automatisierungstechnik“
- `\thesissupervisor`: „Prof.~Dr.~Tobias.~Weiser.“ → „Prof.~Dr.~Tobias~Weiser“
- `\thesisauthors`: „Felix Krawczyk ,“ → „Felix Krawczyk,“
- Präambel: `todonotes`, `algorithm`, `algpseudocode` ergänzen; `09_integration` in die Kapitelfolge einfügen

## 6a. Stand der Entwürfe (2026-09-26)

- Erledigt: §6 (main.tex), Kapitel 02, 03, 04, 05, 06, 07 und 09 (Integration) als Entwurf. Kapitel 10 (Evaluation) und 11 (Fazit) nur als Gerüst mit `\todo`s. Kapitel 08 (M4) unverändert.
- In `references.bib` ergänzt, DOI jeweils über Crossref geprüft: `fitzgibbon1999`, `smith1978`, `brunelli2009`, `suzuki1985`, `hu1962`, `canny1986`, `baek2019`, `shi2017`.
- Noch offen aus §5: Quellen für die Motivation (Kap. 1) und die Normen zu kollaborativen Robotern (Kap. 2.6).

## 7. Nächste Schritte

1. Nebenbefunde (§6) korrigieren, neue Kapiteldatei anlegen und umbenennen.
2. Kapitel für Kapitel entwerfen, in dieser Reihenfolge: Kap. 3 Systemkonzept → Kap. 4–6 Module → Kap. 8 Integration → Kap. 2 Grundlagen → Kap. 1 Einleitung → Gerüste für Kap. 9/10. Pro Kapitel optional vorher `/ars-outline`.
3. Quellen aus §5 beschaffen und prüfen, bevor die entsprechenden Absätze final werden.
4. Nach den Versuchen: Kap. 9 und 10 füllen, Probleme in den Modulkapiteln ergänzen, den offenen Beitrag (§2) einordnen.
