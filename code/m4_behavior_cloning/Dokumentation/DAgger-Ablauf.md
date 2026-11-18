# DAgger an der Anlage – Ablauf (Stand 2026-11-16)

Ziel: Die Policy (var_C2) fährt an, hält 3 mm über dem Objekt (Probegriff). Der Planer (Experte)
korrigiert, greift und legt das Teil neu ab. Policy und Korrektur werden **mit Kamerabildern** als
Episode im Aufnahmeformat mitgeschrieben. Die Zustände der Policy bekommen das Label des Planers
(„zurück auf die Idealbahn“). Danach wird mit diesen Episoden nachtrainiert.

Neu in M4 (nichts in M1/M2 geändert):

| Datei | Inhalt |
|---|---|
| `bc/dagger.py` | Mitschrieb, Labels, Episode im Aufnahmeformat |
| `bc/lokalisierung.py` | Anbindung M1 (`TopDownPipeline`) + Greifdrehung nach M2 (`as_target`), nur importiert |
| `apps/infer.py` | `--dagger`, `--pick-quelle m1`, `--foto-punkt`; Violation-Stopp an der Probe-Ebene zählt als Probegriff (Experte hebt erst senkrecht an); Not-Aus-Erkennung |
| `tools/m1_abgleich.py` | M1 gegen PICK prüfen (live oder auf einem Bild) |
| `tools/export_variante.py` | `--dagger-gewicht K` (DAgger-Episoden K-fach) |
| `apps/train.py` | `--init-from <policy>` (Nachtrainieren ab var_C2) |
| GUI Reiter Betrieb | Felder „PICK“ (Steuerung/M1), „Fotostellung“, „DAgger-Ordner“ |

## Vor dem Start

1. **Gleiche Bedingungen wie bei den Aufnahmen:** Kameraeinstellungen nicht ändern (8 ms, Gain
   automatisch), Override 0,5, Licht wie an den Aufnahmetagen. Sonst passen die Episoden nicht zum
   Modell, und der Export meldet „uneinheitlich“.
2. **Kameraprüfung** wie gewohnt (läuft vor der ersten Fahrt automatisch).
3. **Nur bei PICK aus M1 – Fotostellung prüfen:** An `Home` muss der Arm aus dem Bild der
   Draufsichtkamera sein (alle 4 Marker und das Teil sichtbar). In der Startstellung der Policy
   verdeckt er einen Marker. Teil genau an den geteachten PICK legen, dann:

   ```
   python tools/m1_abgleich.py --camera scene=daheng:EBK24100634@60 --fahren --real-robot
   ```

   Erwartet: „Ergebnis: OK“ (≤ 3 mm, ≤ 3°). Das Bild mit der Erkennung liegt in `logs/m1_abgleich/`.
   Offline am 16.11. auf einem Vollbild vom 02.11.: 0,3 mm / 0,3°.

## Aufnahme

GUI, Reiter Betrieb: Modell `var_C2`, „Lage bekannt“ an, Ende „Probegriff (3 mm über Objekt)“,
PICK „Steuerung“ oder „M1“, DAgger-Ordner z. B. `data/2026-11-17_dagger`, Fahrten z. B. 25.

Kommandozeile entsprechend:

```
python apps/infer.py --checkpoint checkpoints/C2_nur_griff_ohne_1111 --robot neura --real-robot --override 0.5 ^
    --camera wrist=daheng:EBK24100633@60 --camera scene=daheng:EBK24100634@60 ^
    --lage-bekannt --probegriff objekt --episodes 25 --dagger data/2026-11-17_dagger ^
    [--pick-quelle m1 --foto-punkt Home]
```

- **Zuerst 1 Fahrt** zum Prüfen. Danach muss es geben: `data/2026-11-17_dagger/index.json` und
  `ep_00000/` sowie die Zeile „DAgger: Episode 0 (Policy … + Experte … Takte …)“.
- Je Fahrt: Policy bis zum Probegriff → Experte (korrigiert, greift, legt neu ab, PICK nachgeführt) →
  Episode geschrieben. Etwa 30–40 s je Fahrt, 100 Fahrten also gut 1–1,5 h.
- **PICK aus M1:** vor jeder Fahrt an die Fotostellung, M1 lokalisiert, PICK wird gesetzt (Sicherung
  wie beim Touch-up). Weil der Experte das Teil selbst ablegt, zeigt „gegen den bisherigen PICK“ im
  Protokoll direkt die Genauigkeit von M1. Legt der Experte außerhalb des M1-Bereichs ab (330×330 mm
  zwischen den Markern), geht es mit seinem PICK weiter.
- **Von Hand hinlegen** geht auch: Teil irgendwo zwischen die Marker legen, mit PICK aus M1 starten.
- **Not-Aus am Handbediengerät:** Die Fahrt endet nach ~0,3 s mit „arm steht“. Sie wird nicht als
  Episode geschrieben, und vor der nächsten Fahrt fragt das Programm nach.
- Abbruch über den Stopp-Knopf der GUI beendet den Prozess. Episoden, die schon geschrieben sind,
  bleiben erhalten (jede einzeln, mit Index).

## Danach: Export und Nachtrainieren (zu Hause, GPU)

```
python tools/export_variante.py --data data/2026-11-02 data/2026-11-03 data/2026-11-09 data/2026-11-17_dagger ^
    --abschneiden-nach 3 --dagger-gewicht 5 --out datasets/var_C2_dagger1
python apps/train.py --dataset datasets/var_C2_dagger1 --out checkpoints/var_C2_dagger1 ^
    --init-from checkpoints/C2_nur_griff_ohne_1111/policy --steps 3000
```

- Aus PowerShell ohne aktiviertes venv vorher `$env:PATH = "E:\Enviroments\bc_env\Scripts;" + $env:PATH`
  setzen. Dort liegen die FFmpeg-DLLs, ohne sie scheitert das Videodekodieren (torchcodec).
- `--abschneiden-nach 3` wie var_C2. `--dagger-gewicht 5`: Jede DAgger-Episode kommt 5-mal in den
  Datensatz. Die Kopien bleiben über `repeat_group` auf derselben Seite der Train/Val-Aufteilung.
- `--init-from` startet mit den Gewichten von var_C2. Die Normierung kommt aus dem neuen Datensatz,
  der praktisch dieselben Wertebereiche hat. Alternativ von vorn mit 10 000 Schritten (~3 h).
- Vergleich: derselbe Probegriff an der Anlage, gleiche Kennzahlen wie im Bericht
  `Berichte/2026-11-16_Anlagentest_var_C2.pdf` (vorhergesagter Greifpunkt, Versatz je Höhe).

## Labels im Detail

- **Policy-Takte:** nächstgelegener Punkt der Idealbahn (monoton, kein Zurückspringen), davon der
  nächste Takt. Der Schritt je Gelenk ist auf den Schritt der Idealbahn + 0,006 rad begrenzt, damit
  die Rückkehr auf die Bahn sich auf mehrere Takte verteilt. Das gesendete Ziel der Policy steht in
  `aux.joints_command`.
- **Experten-Takte:** das Ziel des nächsten Takts (wie die Aufnahme), bis 10 Takte nach dem Schließen.
- `aux.pose_noisy` = gemessene TCP-Pose (nur für die TCP-Hülle beim Export).
- Metadaten wie die Aufnahme (Tempo, Ausführung, Kameras), zusätzlich `mode: dagger`, Lage,
  Korrektur des Experten, Lokalisierung, Abstand der Policy zur Idealbahn.
