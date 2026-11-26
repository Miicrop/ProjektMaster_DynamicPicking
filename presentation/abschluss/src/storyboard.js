// Storyboard (Quelle: plan/10_praesentation_konzept.md, Abschnitt Storyboard).
// Ungebaute Szenen erscheinen als Platzhalter-Karte mit diesen Angaben.
// speaker: wer spricht (Schriftfeld unten rechts), je Akt aus SPEAKER.

export const ACTS = {
  1: 'Aufgabe',
  2: 'Architektur & Integration',
  3: 'M1 Objekterkennung',
  4: 'M2 Robotersteuerung',
  5: 'M3 Sichtprüfung',
  6: 'M4 Behavior Cloning',
  7: 'Ergebnis & Ausblick',
  A: 'Anhang',
};

// Modulverantwortung: M1 Felix Krawczyk, M2 Joshua Junt, M3 Niklas Tollmann, M4 Jeremy Zid
export const SPEAKER = {
  1: 'Niklas',
  2: 'Niklas',
  3: 'Felix',
  4: 'Joshua',
  5: 'Niklas',
  6: 'Jeremy',
  7: 'alle',
  A: '–',
};

const s = (id, title, statement, visual, data = '') => {
  const act = id.split('.')[0];
  return { id, act, title, statement, visual, data, speaker: SPEAKER[act], appendix: id.startsWith('A') };
};

export const STORYBOARD = [
  s('1.1', 'Titel', 'Dynamisches Greifen und automatisierte Sichtprüfung mit einem kollaborativen Roboter', 'Leeres Blatt. Tusche zeichnet den Aufstellungsplan der Zelle (Rahmen, Marker, Prüfvorrichtung, Ablagen, Roboterfuß) in echten mm. Das Schriftfeld setzt sich: Titel, vier Namen, Datum.', 'system.yaml: poses, workspace_to_robot, workspace.size_mm'),
  s('1.2', 'Die Zelle', 'Ein Roboter, drei Kameras, ein Rahmen, eine Prüfstation, zwei Ablageorte.', 'Der Plan extrudiert zu 3D. Positionsnummern: LARA, Greifer, Übersichtskamera an der Stange (M1), Seitenkamera (M3), Handgelenkkamera (M4), Rahmen mit ArUco, Prüfposition, Ablagen GUT/SCHLECHT.', 'system.yaml'),
  s('1.3', 'Das Bauteil', 'Ein lila Quader mit Fase, Etikett 69420, Loch und Kerbe.', 'Der Quader dreht sich, Hinweislinien auf Fase, Seriennummer, Durchgangsloch, Kerbe. Etikett, Loch und Fase liegen auf derselben Längsseite, die Kerbe auf der Fasenfläche (wie am echten Teil).', 'Testbilder M1/M3'),
  s('1.4', 'Ein Zyklus', 'Erkennen → Greifen → Prüfen → Sortieren, ohne Eingriff.', 'Hero: der komplette Ablauf einmal im Zeitraffer, die Zustände erscheinen als Stempel IDLE → DETECT → PICK → PLACE_INSPECT → INSPECT → PICK_INSPECT → SORT.', 'Zustandsautomat (orchestrator/)'),
  s('1.5', 'Erfolgskriterium', 'Läuft der Ablauf vollständig automatisch durch?', 'Erfolgskriterium als Schriftfeld, darunter die Abgrenzung als Positionszeilen: ein Teil, flach liegend (x, y, Winkel), Betrieb unter Aufsicht mit reduzierter Geschwindigkeit, M4 optional.', 'thesis/blueprint.md §1'),
  s('1.6', 'Vorprojekt', 'Was wir aus der Bahnplanung bei GROB mitgenommen haben.', 'Ein ruhiges Blatt: Vorpose + LIN, Arbeitsraumgrenzen, Kollisionsprüfung, dazu Bildschirmfotos aus Process Simulate.', 'thesis 02b_vorprojekt.tex'),

  s('2.1', 'Zustandsautomat', 'Ein Orchestrator, acht Zustände, ein Fehlerpfad.', 'Der Automat zeichnet sich als Tuschediagramm; der Zustand aus 1.4 leuchtet. ERROR in Rotstift, Quittieren führt zurück nach IDLE.', 'plan/01_architektur.md'),
  s('2.2', 'Schnittstellen', 'Die Module kennen sich nicht – sie tauschen nur Datenkarten.', 'ObjectPose (x, y, z, Winkel, Konfidenz) und InspectionResult (Seriennummer, Ø, Kerbe, gut/schlecht, Gründe) fliegen als Karten zwischen den Modulblöcken.', 'common/interfaces.py'),
  s('2.3', 'Von Tag 1 an lauffähig', 'Jedes Modul hat Mock, Wiedergabe und echte Hardware hinter derselben Schnittstelle.', 'Jeder Block hat drei Stecker (mock / replay / real). Ein Schalter klappt um, der Ablauf läuft weiter. Testzähler zählt hoch.', 'orchestrator/factory.py, 105 Tests'),
  s('2.4', 'Bedienung & Logbuch', 'Eine GUI für Einzeltests und Ablauf, jeder Zyklus landet im Logbuch.', 'Echter Screenshot der GUI nach drei Zyklen (tools/gui_shot.py) mit Positionsnummern; dann das Zykluslog als Papierstreifen (Auszug 26.09., Simulator, mit einem STOPP).', 'gui/, logs/cycles_*.csv'),

  s('3.1', 'Blick von der Stange', 'Die Kamera hängt schräg seitlich an einer Stange – sie sieht den Rahmen verzerrt.', 'Kamera an der Stange schräg über dem Rahmen, Sichtkegel zeichnet sich, Blitz → das echte Foto liegt verzerrt auf dem Blatt.', 'm1_vision_topdown/tests/data/PXL_20261005_*.jpg'),
  s('3.2', 'Das Bild klappt gerade', 'Vier ArUco-Marker genügen, um das Bild zu entzerren.', 'Hero: Marker werden umkreist, die vier Ecken wandern ins Rechteck 330 × 330 mm, das Foto entzerrt sich live (echte Homographie).', 'TopDownPipeline: Ecken, Homographie'),
  s('3.3', 'Bauteil finden', 'Segmentierung relativ zur Platte – unabhängig von Bauteilfarbe und Licht.', 'Maske frisst den Hintergrund, die Kontur zeichnet sich, das minimale Rechteck als Maßzeichnung.', 'Zwischenbilder m1_04 … m1_09'),
  s('3.4', 'Eindeutig dank Fase', 'Ein Rechteck ist bei 180° gleich – die Fase macht den Winkel eindeutig (0–360°).', 'Quader dreht sich um 180°; ohne Fase identisch, mit Fase nicht. Rotstift-Kreis um die Fase, Winkelbemaßung.', 'Pose aus TopDownPipeline'),
  s('3.5', 'Drei Koordinatensysteme', 'Bild (px) → Arbeitsraum (mm) → Roboter-Basis (mm).', 'Hero: drei Achsenkreuze. Der Bauteilpunkt wandert durch Homographie und Kalibrierung. Der TCP fährt die Marker an, Restfehler als Maßpfeile (Least Squares).', 'workspace_to_robot, robot_check calib'),
  s('3.6', 'Positionskorrektur', 'Am Aufbau lag die erkannte Mitte bis 8 mm zu weit außen – eine lineare Korrektur bringt sie auf höchstens 2 mm.', 'Arbeitsraum von oben mit den Zeigetests: rote Pfeile zeigen den Versatz ohne Korrektur (wächst nach außen). Rechts Ursache und Modell je Achse. Klick: die Kontrollmessungen mit Korrektur, grün ohne Versatz; Stempel HÖCHSTENS 2 mm.', 'logs/point_tests.csv (12.11.), part_topdown.position_correction'),

  s('4.1', 'LARA', 'Ein 6-Achs-Cobot mit elektrischem Parallelgreifer, TCP 197,5 mm unter dem Flansch.', 'Der Roboter zeichnet sich als Tuschezeichnung, Maßlinie Flansch → TCP.', 'tool ZimmerLWR50, Datenblätter docs/greifer/'),
  s('4.2', 'Vom Bauteil zur Greifpose', 'Aus x, y und Winkel von M1 wird eine Zielpose – und daraus sechs Gelenkwinkel.', 'Winkelskizze am Teil B (Basis-x → Bauteilwinkel → − 67° Offset = rz) und eine Codekarte mit echten Zahlen: as_target() → to_neura() → compute_inverse_kinematics → move_joint. Dann fährt LARA per PTP zur Vorpose, an den Gelenken laufen die Winkel mit.', 'm2_robot_control/robot.py, grasp_height_mm, gripper_angle_offset_deg'),
  s('4.3', 'Die Greifsequenz', 'Vorpose, schnell bis 20 mm über dem Ziel, dann langsam.', 'Hero: von der Vorpose LIN mit 0,10 m/s → ab 20 mm mit 0,03 m/s → greifen → LIN hoch. Geschwindigkeitsprofil als Maßband daneben.', 'linear_speed_mps, approach_speed_mps, approach_slow_mm'),
  s('4.4', 'Greifwinkel', 'Quer greifen, 23° Montagewinkel ausgleichen, und um 180° gedreht – damit die Seriennummer zur Kamera zeigt.', 'Draufsicht: Greiferbacken gegen Bauteilachse, Winkelbemaßung; Formel Offset −67° = 90° + 23° − 180° und warum nicht die Ablage gedreht wird (Achse 6).', 'gripper_angle_offset_deg'),
  s('4.5', 'Sicherheit', 'Grenzen in Software, STOPP in eigenem Thread, Neustart nur bewusst.', 'Arbeitsraum-Quader; eine Pose außerhalb wird mit Rotstift abgelehnt. STOPP-Knopf, stop() → reset().', 'limits_mm, gui/'),
  s('4.6', 'Roboter ohne Roboter', 'Ein Simulator spricht dasselbe Protokoll wie die Steuerung.', 'Ein Schattenroboter (nur Kanten) neben LARA; der unveränderte NeuraPy-Client spricht mit beiden. LARA fährt, der Schatten springt ans Ziel – der Simulator hat keine Kinematik und merkt sich nur die Pose; daneben sein Aufrufprotokoll.', 'fake_neura_server.py'),
  s('4.7', 'Roboter einrichten', 'Verbinden, joggen, Posen teachen, testen – Schritt für Schritt in der GUI, vorsichtig.', 'Echter Screenshot des Tabs „M2 Roboter“ (Simulator, tools/gui_shot.py) mit Positionsnummern: Verbinden, Joggen, Checkliste „Erste Schritte“, Posen teachen. Dann Vorsicht eingebaut: STOPP, Rückfrage, Override; Stempel SIM › VM › ECHT.', 'gui/tab_robot.py, gui/robot_pages.py, robot_check.py'),

  s('5.1', 'Blick von der Seite', 'An der Prüfposition sieht die Seitenkamera Etikett, Loch und Kerbe.', 'Bauteil auf der Prüfvorrichtung, Seitenkamera, Blitz → echtes Seitenbild.', 'm3_inspection/tests/data/test_img_*.jpg'),
  s('5.2', 'Bauteil finden', 'Erst das Bauteil per Farbe, dann alle Prüfbereiche relativ zu seiner Box.', 'Echte Masken des Hero-Bilds legen sich als Papier über das Foto: Lila (HSV) → geöffnet → senkrecht über die Bauteilhöhe geschlossen; dann die Box, dann die ROIs für Etikett, Loch und Kerbe.', 'locate_part(), Zwischenbilder aus build_data.py (m3.trace)'),
  s('5.3', 'Seriennummer', 'EasyOCR liest nur Ziffern, ein Regex prüft das Format.', 'Detailblatt: Etikett-ROI → EasyOCR (Allowlist 0–9, Hochskalieren) → 69420 mit Konfidenz und Regex. Dann alle vier Testbilder mit ihrer Konfidenz.', 'm3_inspection/ocr.py, ocr_min_confidence, serial_pattern'),
  s('5.4', 'Loch', 'Was keine helle Stirnfläche ist, ist Loch – das Rundeste davon wird gemessen.', 'Detailblatt: Loch-ROI → Maske → Kandidaten mit Rundheit. Dann Maßlinien: Bauteilhöhe 15 mm = px liefert mm/px, Ellipse → Ø in mm; D/H auf allen vier Testbildern.', 'find_hole(), part_height_mm, hole_nominal_mm'),
  s('5.5', 'Kerbe', 'Zwei Wege liefern Kandidaten, gewählt wird das Rechteck.', 'Detailblatt in drei Klicks: Kerben-ROI → Region (dunkler/anders gesättigt als der Rand) → + Kanten (Canny) → Kandidat mit Rechteckigkeit. Dann alle vier Testbilder mit ihren echten Zwischenbildern; der Weg, der gewonnen hat, ist umrahmt (2× Kanten, 2× Region).', 'find_notch(), m3.notches aus build_data.py'),
  s('5.6', 'Drei Prüfungen, ein Urteil', 'Gut nur, wenn Seriennummer, Loch und Kerbe stimmen.', 'Hero: OCR „69420“ ok, Loch als Maßlinie ok, Kerbe ok → Stempel GUT. Dann übermalte Kerbe → Rotstift, Stempel SCHLECHT mit Grund.', 'InspectionResult, evaluate()'),

  s('6.1', 'M4 übernimmt das Greifen', 'M1 erkennt, M4 greift aus dem Rahmen bis über die Prüfung, ab dort macht M2 weiter.', 'Beim Betreten (Aktübergang) wechselt nur die Überschrift; auf Klick klappt im Zustandsring PICK von M2 auf M4 (Diffusion Policy) um.', 'orchestrator/m4_grasper.py, --grasper bc'),
  s('6.2', 'Lernen mit Rauschen', '3 Punkte teachen, ein Planer fährt die Bahn mit Rauschen ab, daraus lernt die Policy.', 'Hero in der Zelle: Teil C an PICK, Wegpunkte CLEAR_FOV, PICK, PRE_PLACE und die Sollbahn. Klick: LARA fährt eine Episode mit echtem Rauschen, dahinter zeichnet sich der Fächer aller Episoden; danach legt sie das Teil zurück. Klick: Karte mit der Kette Teachen → Aufnahme → LeRobotDataset → Diffusion Policy → Inferenz 15 Hz.', 'data.m4 (Punkte der Anlage 26.10., bc/noise.py)'),
  s('6.3', 'Der Rauschtrichter', 'Viel Rauschen im Transit, keins am Greifpunkt, kaum Richtung Tisch.', 'Oben die seitliche Abweichung der 10 Episoden über der Bahn mit Hülle, Ankerpunkte Start, PICK, Übergabe. Klick: unten die Höhe – nach unten höchstens 2 mm (Tisch); rechts Trichter, Rauschfaktor, Asymmetrie, Rejection Sampling.', 'data.m4.funnel aus bc/noise.py'),
  s('6.4', 'Diffusion Policy', 'Aus Zufall wird eine Bahn – passend zu Bild und Zustand.', 'Eingänge (zwei Kamerabilder, Zustand) → Netz → Aktionsblock über 16 Takte. Klick: zufällige Punkte entrauschen sich in 10 Schritten zur glatten Kurve. Klick: die ersten 8 Takte werden gefahren, dann neu vorhergesagt; Vorhersage ~77 ms, asynchron.', 'bc/config.py, bc/diffusion.py, Durchstich-Bericht'),
  s('6.5', 'Von der Simulation zur Anlage', 'In der Simulation 10 von 10 – an der Anlage trifft die Policy den Greifpunkt im Median auf 8,7 mm.', 'Rollout-Abbildung (Draufsicht, Höhe über der Zeit) mit Kennzahlen: 10/10, Greifpunkt 1,3–2,2 mm, Bahn 3–4 mm, 32 min Training; Stempel SIMULATION. Klick: ehrlich – nur aus dem Zustand gelernt, in der VM Stillstand vor dem Greifen.', 'Berichte/2026-09-17_Durchstich_Policy.pdf'),
  s('6.6', 'Das Zittern', 'An der Anlage zitterte der Arm – 60 Sollwerte je Sekunde werden zur Treppe.', 'Links die Treppe: Sollbahn gegen anfahren, warten, anfahren; drei Zeilen zur Ursache. Klick: rechts die gemessenen RMS-Werte je Ausführungsart, Stempel ENTSCHIEDEN: servo_j mit Override 0,5.', 'Dokumentation/Zittern-an-der-Anlage.md, Labortag-2026-10-16-Uebergabe.md'),
  s('6.7', 'Takt und Sicherheit', 'Alle 66,7 ms ein Sollwert – und sechs Schichten, die eingreifen.', 'Zeitachse: Takt 15 Hz, servo_j 60 Hz mit Aufrufzeit, Vorhersage ~77 ms (asynchron), Hänger ~210 ms. Klick: ServoGuard, TargetLimiter, Zielabstand, Geofence + Software-Stopp; Stempel IN DER VM AUSGELÖST.', 'Labortag 16.10., Durchstich-Bericht, bc/servo.py, bc/safety.py'),
  s('6.8', 'Übergabe M4 → M2', 'Die Policy bringt das Teil bis über die Prüfung, M2 legt es ab.', 'In der Zelle: LARA fährt von CLEAR_FOV über PICK nach PRE_PLACE, an der Handgelenkkamera „Policy, 15 Hz“; Schild ÜBERGABE. Klick: M2 macht reset(), legt in die Prüfung und fährt zurück; Schild: in der Neura-VM getestet, mit Modell an der Anlage offen.', 'm4_grasper.py, PRE_PLACE aus der Punktedatei'),

  s('7.1', 'Labortag 06.10.', 'Am 06.10. lief der erste vollständige Ablauf am echten Roboter.', 'Was am 06.10. geschah (Posen, Kalibrierung, Greifer-Offset, erster Ablauf – ehrlich: ohne Greifer, ohne Arbeitsraumkamera); dann Schätzung gegen geteachte Posen (7–11 cm daneben). Fotos vom Labor können dazu.', 'plan/07_erledigt.md 2026-10-06, Commit 1f5cdc1'),
  s('7.2', 'Labortag 12.11.', 'Am 12.11. lief der Ablauf zum ersten Mal mit beiden Kameras und Greifer.', 'Sechs Positionen: Kameras fest eingestellt, Greifer über Digitalausgänge, Zeigetests, Teil gedreht greifen, veraltete Bilder, sanft ablegen. Klick: Fotos vom Aufbau, Stempel ERSTER ZYKLUS MIT KAMERAS.', 'plan/07_erledigt.md 2026-11-12, thesis/figures'),
  s('7.3', 'Messwerte', 'Die Kette läuft durch – nur der Lochdurchmesser wird zu klein gemessen.', 'Fünf Kennzahlen aus dem Zykluslog und den Zeigetests. Klick: Lochdurchmesser je Zyklus gegen das Toleranzband, daneben das echte Prüfbild mit der Spiegelung im Loch.', 'logs/cycles_20261112.csv, logs/point_tests.csv'),
  s('7.4', 'Labortag 26.11.', 'Dauerbetrieb: 25 Zyklen am Stück, und jeder Fehlerfall wurde zu einer neuen Prüfung.', 'Vier Positionen (Dauerbetrieb, Zyklen, Zykluszeit, Lochmessung) neben dem GUI-Screenshot mit GUTTEIL. Klick: Screenshot weicht den zwei Fehlerbildern (Hand über Marker, Teil kopfüber) mit dem, was daraus wurde; Stempel KEIN TEIL FALSCH SORTIERT.', 'logs/cycles_20261126.csv, logs/20261126/, Screenshot GUI'),
  s('7.5', 'Lochmessung gelöst', 'Die Spiegelung zieht die Kontur nur nach innen – also werden diese Punkte verworfen: alle Prüfbilder in Toleranz.', 'Zwei Positionen zur Ursache neben dem Fit-Vergleich am selben Loch. Klick: alle Prüfbilder des Tages mit Ellipse und Kreis-Fit nachgerechnet, Toleranzband, Kennzahlen 0 → 19/19, 21/21 GUT, Streuung; Stempel GELÖST IM ALGORITHMUS.', 'thesis/tools/eval_20261126.py, build_data.py export_lab3'),
  s('7.6', 'Was noch fehlt', 'Licht abschirmen, kalibrierte Kamera, M4 an der Anlage, echte Fehlerteile.', 'Zwei Spalten mit Stempel: erledigt (Schritt 1), offen (Schritt 2).', 'plan/06_offen.md, plan/07_erledigt.md'),
  s('7.7', 'Ausblick', 'Pflegerobotik: „Mensch ärgere Dich nicht“ mit Senioren gibt es schon mit einfacherer Kinematik – mit denselben ArUco-Markern könnten LARA und unsere Bausteine das übernehmen.', 'In der Zelle: der Arbeitsraum wird zum Spielfeld (11 × 11 Felder à 30 mm = 330 mm), Figuren wachsen heraus, Karte links mit Idee und Bausteinen M1–M3. Klick: Würfel 6 → LARA setzt ihre Figur aufs Startfeld. Klick: Würfel 3 → LARA wirft Blau zurück ins Haus und zieht. Beim Übergang zu 7.8 verschwindet das Spielfeld, Teil B wächst zurück in den Greifer.', 'Bühnenbild in cell.js (Spielfeld, Figuren, Würfel); Bewegungen PTP + LIN wie im Zyklus'),
  s('7.8', 'Finale', 'Erkennen, Greifen, Prüfen, Sortieren – automatisch.', 'Zweites Teil läuft durch und landet in SCHLECHT. Dann holt LARA in einer Bewegung das Schild rechts aus dem Halter, dreht es zur Zuschauerkamera und hält es leicht geneigt hin: „Noch Fragen?“; die Zelle bleibt im Bild.', 'Bühnenbild: SIGN in cell.js'),

  s('A.1', 'Konfiguration', 'Posen, Grenzen und Kalibrierwerte aus system.yaml.', 'Tabelle.', 'config/system.yaml'),
  s('A.2', 'Zwischenbilder M1', 'Alle Schritte der Top-down-Verarbeitung.', 'Bildreihe m1_01 … m1_10.', 'overview/img/m1'),
  s('A.3', 'Zwischenbilder M3', 'Alle Schritte der Sichtprüfung.', 'Bildreihe m3_01 … m3_14.', 'overview/img/m3'),
  s('A.4', 'Tests', 'Was automatisch geprüft wird.', 'Tabelle der Testgruppen je Modul.', 'pytest'),
];
