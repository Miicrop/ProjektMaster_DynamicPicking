# Abschlusspräsentation – „Die Zelle zeichnet sich selbst“

Konzept und Storyboard: [plan/10_praesentation_konzept.md](../../plan/10_praesentation_konzept.md).
Engine und Look stammen aus der Masterarbeits-Präsentation (`Masterarbeit_Neu/presentation/abschluss`).

## Vortrag halten (ohne Node)

`start.bat` startet `dist/` per `vite preview` (Port 8124); ohne Node fällt es auf `serve.py` zurück (statischer Python-Server mit festen MIME-Typen, weil die Windows-Registry `.js` teils als `text/plain` meldet → weiße Seite) und öffnet den Browser. Alles läuft offline.

## Entwickeln

```
npm install          # einmalig
..\..\.venv\Scripts\python build_data.py   # Daten + Bilder aus den echten Pipelines nach public/ (nach Änderungen an Code/Config erneut)
..\..\.venv\Scripts\python tools\gui_shot.py   # GUI-Screenshots für 2.4 und 4.7 (vor build_data.py, wenn sich die GUI geändert hat)
npm run dev          # http://localhost:5180, Live-Reload
npm run build        # erzeugt dist/ für den Vortrag
```

Alle Szenen im Endzustand: `node tools/shoot_all.mjs <ordner>` (Kontaktbogen, meldet Konsolenfehler und externe Requests).

Einzelne Zustände (headless Edge): `node tools/shoot.mjs <ordner> http://localhost:5180/ 1.3.2 play:1.4.0:3`
- `1.3.2` = Szene 1.3 nach Schritt 2, sofort hergestellt
- `play:Z:s` = Zustand Z herstellen, einmal „weiter“, nach s Sekunden fotografieren

## Bedienung

| Taste | Wirkung |
|---|---|
| → / Leertaste / Bild↓ / Enter | weiter (läuft eine Animation, wird sie zuerst beendet) |
| ← / Bild↑ / Backspace | zurück (sofort, exakt) |
| `3.2` Enter, `A.2` Enter, `3.2.1` Enter | Sprung zu Szene (Endzustand) bzw. Schritt |
| `O` | Übersicht aller Szenen, Klick springt |
| `B` | zurück zur Position vor dem letzten Sprung |
| `F` | Vollbild |
| Maus ziehen / Mausrad | frei drehen / zoomen; der nächste Schritt fährt zurück, Doppelklick setzt sofort zurück |

URL-Hash `#3.2.1` hält die Position beim Neuladen. Das Schriftfeld unten rechts zeigt, wer gerade spricht.

## Aufbau

- `src/storyboard.js`: alle Szenen mit Aussage, Bildidee, Daten (es gibt nur eine Fassung); `SPEAKER` ordnet Akte den Vortragenden zu. Eine Szene ohne eigenes Modul erscheint als Entwurfsblatt (`src/worlds/placeholder.js`).
- `src/engine/`: `stage.js` (Renderer, Tusche-Pipeline, Papier, Schnitt-Blende, Blitz), `nav.js` (Schritte mit deterministischem Endzustand), `hud.js` (Schriftfeld, Übersicht, Sprung).
- `src/kit/`: `ink.js` (Tuschelinie, Text, Positionsnummer, Maßlinie, Fotokarte), `sheet.js` (Blatt-Baukasten für ruhige Szenen, Stempel), `tiles.js` (viele Bildkacheln in einem Draw-Call).
- `src/worlds/`: `cell.js` (1.1–1.4, 4.1–4.6, 7.4, 7.5: Zelle mit LARA, Zyklus, Ausblick-Spielfeld, Finale), `arch.js` (2.1–2.3, 6.1), `vision.js` (3.1–3.5, echte Homographie als Gitter-Verformung), `inspect.js` (5.1–5.6), `sheets.js` (1.5, 1.6, 2.4, 4.7, 7.1, 7.3, A.1–A.4), `placeholder.js` (Entwurfsblatt).
- `src/kit/lara.js`: LARA aus der URDF (Meshes, Vorwärts-/Rückwärtskinematik); `src/kit/note.js` (Papierschild für Text über Fotos), `src/kit/geom.js` (Kreis, Bogen, Pfeil).
- `build_data.py`: ruft `TopDownPipeline` und `InspectionPipeline` (EasyOCR) auf den Testbildern auf → `public/data/data.json` (Konfiguration, Posen, Homographie, Konturen, Prüfergebnisse, Testzahlen) und `public/img/`.
- `public/urdf/`: LARA5-URDF mit Meshes; Posen kommen aus `system.yaml` (TCP im Basis-KS), Bewegungen PTP in Gelenkkoordinaten, An-/Abfahrt linear.
- `src/theme.js`: Farben. Lila nur für das Bauteil, `MODULE_COLOR` je Modul, Signalrot für Schlechtteil/Fehler/STOPP, Grün nur für GUT.

Lagen, die nicht in der Konfiguration stehen (Stangen- und Seitenkamera, Ablagenmaße), sind in `cell.js` als Annahme markiert und dort zu verschieben.

Neue Szene bauen: Welt in `src/worlds/` anlegen (`{ scene, S, defaults, update }` + Szenenliste mit `steps`/`cams`), in `src/main.js` bei `WORLDS`/`BUILT` eintragen.

## Regeln

- Texte in 3D nur mit Zeichen aus dem Latin-Satz (Pfeile, ≈, ⟨⟩ werden in `text()` ersetzt; kein θ, kein ✓), sonst lädt troika Schriften aus dem Netz.
- Texte auf dem Papier, die zur Kamera geneigt werden (`rotation.x`), mit `anchorY: 'bottom'` setzen, sonst tauchen sie ins Papier.
- Roboterposen aus `system.yaml` sind TCP-Posen im **Roboter-Basis-KS**; M1 rechnet im Arbeitsraum-KS. Die Zelle wird im Basis-KS aufgebaut.
