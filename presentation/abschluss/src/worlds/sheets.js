// Ruhige Blätter (Baukasten src/kit/sheet.js): 1.5, 1.6, 2.4, 3.6, 4.6, 5.9, 6.4, 6.7, 6.9, 6.10, 7.4, A.1–A.9.
// Die Blätter zum Muster „Aufgabe → Idee → Am Aufbau → Lösung“ stehen in aufbau.js.
// Inhalte aus thesis/blueprint.md, thesis 02b_vorprojekt.tex, plan/06_offen.md, plan/07_erledigt.md, der M4-Doku und
// data.json (config, Zwischenbilder, GUI-Screenshot, Zykluslog, Labortag, Tests, M4-Messwerte).
import * as THREE from 'three';
import { T, MODULE_COLOR, color } from '../theme.js';
import { PhotoCard, Balloon, InkLine, text, v3 } from '../kit/ink.js';
import { setPts } from '../kit/geom.js';
import { sheetScene, SHEET_W, clamp01 } from '../kit/sheet.js';

const X0 = -SHEET_W / 2 + 0.6;
const fmt = (v, d = 1) => Number(v).toFixed(d).replace('.', ',');

// ---------------------------------------------------------------- 1.5 Erfolgskriterium
function sheet15(api) {
  api.text(0, 'Läuft Erkennen, Greifen, Prüfen und Sortieren vollständig automatisch durch?', { font: 'title', size: 0.52, anchorY: 'top', maxWidth: 14.2, lineHeight: 1.15 }, [X0 + 0.7, 2.55], { delay: 0.1 });
  api.text(0, 'Das ist das Erfolgskriterium. Messwerte dienen der Demonstration, nicht echten Toleranzen.', { font: 'sans', size: 0.24, hex: T.inkSoft, anchorY: 'top' }, [X0 + 0.7, 1.15], { delay: 0.3 });
  api.text(1, 'ABGRENZUNG', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.08 }, [X0 + 0.7, 0.3]);
  const rows = [
    ['Ein Bauteil', 'kein Schüttgut, keine Vereinzelung'],
    ['Kein Greiferdesign', 'vorhandener Greifer – deshalb ein einfaches Bauteil, das er sicher fassen kann'],
    ['Flach liegend', `Pose in der Ebene: x, y und Winkel – die Greifhöhe ist bekannt`],
  ];
  rows.forEach(([t, b], i) => {
    const x = X0 + 0.7 + (i % 2) * 7.3;
    const y = -0.2 - Math.floor(i / 2) * 1.55;
    api.row(1, i + 1, t, b, y, { x, width: 6.3, size: 0.32, delay: 0.1 + i * 0.12 });
  });
}

// ---------------------------------------------------------------- 1.6 Vorprojekt GROB
function sheet16(api) {
  const rows = [
    ['Vorpose, dann geradlinig', 'Greifen und Ablegen wie bei GROB: Gelenkbewegung zur Vorpose, das Ziel langsam und linear'],
    ['Sichere Bereiche', 'jede Zielpose wird gegen einen Quader geprüft – eine vereinfachte Form des Arbeitsraums'],
    ['Kollisionsprüfung', 'im Demonstrator nicht nötig (freier Raum über dem Tisch), bei Erweiterung per Offline-Simulation'],
    ['Randbedingungen für KI', 'egal welches Modul die Pose liefert: Grenzen und Geschwindigkeiten gelten immer'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.55 - i * 1.5, { width: 7.4, size: 0.3, delay: 0.15 + i * 0.12 }));
  api.text(0, 'Vorprojekt: KI-basierte Roboterbahnen in Process Simulate', { font: 'mono', size: 0.16, hex: T.inkSoft }, [X0 + 0.7, -3.75], { delay: 0.5 });
  const figs = api.ctx.data.figures.grob;
  const pick = ['tool_spheres_anzeige', 'monitoring_space', 'collision_set_anzeige'].map((n) => figs.find((f) => f.name === n)).filter(Boolean);
  pick.forEach((f, i) => {
    const card = new PhotoCard(f.url, { width: 3.6, aspect: f.h / f.w });
    card.object.position.set(4.3 + (i - 1) * 0.9, 1.0 - i * 1.55, 0.05 + i * 0.05);
    card.object.rotation.z = (i - 1) * -0.05;
    card.opacity = 0;
    api.add(1 + i, card, { delay: 0, dur: 0.6 }); // ein Bild pro Klick
  });
}

// ---------------------------------------------------------------- 2.4 Bedienung & Logbuch
function sheet24(api) {
  const f = api.ctx.data.figures.gui[0];
  const card = new PhotoCard(f.url, { width: 9.4, aspect: f.h / f.w, border: 0.06, bottom: 0.06 });
  const CX = X0 + 0.25 + 4.76;
  const CY = -0.55;
  card.object.position.set(CX, CY, 0.03);
  card.opacity = 0;
  api.add(0, card, { delay: 0.1, dur: 0.6 });
  // Positionsnummern auf dem Screenshot (u, v im Bild)
  const at = (u, v) => [CX - card.width / 2 + u * card.width, CY + card.height / 2 - v * card.height];
  const pin = (step, n, [x, y], timing) => {
    const b = new Balloon(String(n), { r: 0.22, size: 0.17, hex: MODULE_COLOR.ORCH });
    b.object.position.set(x, y, 0.08);
    return api.add(step, b, timing);
  };
  const RX = 3.1;
  const rows = [
    ['Zustandskette', 'der laufende Zustand leuchtet, ein Fehler färbt ihn rot', [0.42, 0.14]],
    ['Bild nach jedem Schritt', 'M1 und M3 zeigen Ergebnis und Kurzinfo, sobald der Schritt fertig ist', [0.3, 0.27]],
    ['NOT-STOPP in Software', 'eigener Thread; weiter erst nach „Fehler quittieren“', [0.8, 0.07]],
    ['Logbuch', 'jeder Zyklus eine Zeile: Zeit, Pose, Seriennummer, Urteil oder Fehler', [0.3, 0.77]],
  ];
  rows.forEach(([t, b, uv], i) => {
    pin(0, i + 1, at(...uv), { delay: 0.6 + i * 0.15 });
    api.row(0, i + 1, t, b, 2.3 - i * 1.5, { x: RX, width: 3.9, size: 0.28, delay: 0.5 + i * 0.15 });
  });
}

// ---------------------------------------------------------------- 4.6 Roboter einrichten (GUI-Tab M2)
function sheet47(api) {
  const cfg = api.ctx.data.config;
  // links: echter Screenshot des Tabs „M2 Roboter“, mit dem Simulator verbunden (tools/gui_shot.py)
  const f = api.ctx.data.figures.gui.find((g) => g.name === 'robot');
  const card = new PhotoCard(f.url, { width: 9.4, aspect: f.h / f.w, border: 0.06, bottom: 0.06 });
  const CX = X0 + 0.25 + 4.76;
  const CY = -0.55;
  card.object.position.set(CX, CY, 0.03);
  card.opacity = 0;
  api.add(0, card, { delay: 0.1, dur: 0.6 });
  const at = (u, v) => [CX - card.width / 2 + u * card.width, CY + card.height / 2 - v * card.height];
  const pin = (step, n, [x, y], hex, timing) => {
    const b = new Balloon(String(n), { r: 0.22, size: 0.17, hex });
    b.object.position.set(x, y, 0.08);
    return api.add(step, b, timing);
  };
  const RX = 3.1;
  const W = 3.9;
  // Schritt 0: was man damit tut – verbinden, joggen, Checkliste abarbeiten, Posen teachen
  const rows = [
    ['Verbinden', 'Simulator, Neura-VM oder echter Roboter – Status, Freigabe und TCP-Pose live', [-0.03, 0.15]],
    ['Joggen', 'kleine Schritte in x, y, z und rz im Basis-KS, langsam; die Pose wird danach nachgemessen', [-0.03, 0.66]],
    ['Erste Schritte', 'Checkliste von „Verbindung lesen“ über Achsentest bis Greiftest, jeder Schritt mit Haken', [0.275, 0.335]],
    ['Posen teachen', 'Ablage anfahren, mit Joggen genau ausrichten, übernehmen – landet in system.yaml', [0.388, 0.335]],
  ];
  const pins = [];
  const shown = rows.map(([t, b, uv], i) => {
    pins.push(pin(0, i + 1, at(...uv), MODULE_COLOR.M2, { delay: 0.6 + i * 0.15 }));
    return api.row(0, i + 1, t, b, 2.3 - i * 1.3, { x: RX, width: W, size: 0.28, delay: 0.5 + i * 0.15 });
  });
  // Schritt 1: Vorsicht eingebaut – die ersten Nummern weichen
  api.fade(1, shown.flatMap((r) => [r.t, r.d]), { delay: 0, dur: 0.4 });
  const balloons = [...pins, ...shown.map((r) => r.b)];
  api.add(1, (v) => balloons.forEach((b) => (b.appear = Math.min(b.appear, 1 - v))), { delay: 0, dur: 0.4 });
  const safety = [
    ['STOPP in Software', 'eigener Thread, ersetzt nicht den Not-Halt; weiter erst nach „Freigeben“', [-0.03, 0.56]],
    ['Rückfrage vor jeder Fahrt', 'am echten Roboter; „ohne Rückfrage“ gilt nur fürs Joggen und fällt beim Trennen zurück', [-0.03, 0.81]],
    ['Langsam', `Override ${Math.round(cfg.robot.override * 100)} %, Jog höchstens 100 mm / 15°`, [-0.03, 0.48]],
  ];
  safety.forEach(([t, b, uv], i) => {
    const d = { delay: 0.4 + i * 0.15 };
    pin(1, i + 5, at(...uv), T.signal, d);
    api.row(1, i + 5, t, b, 2.3 - i * 1.3, { x: RX, width: W, size: 0.28, ...d });
  });
  // Reihenfolge der Gegenstellen: erst ohne Arm, zuletzt im Labor
  const targets = [['SIM', T.inkSoft], ['VM', MODULE_COLOR.M2], ['ECHT', T.good]];
  targets.forEach(([label, hex], i) => {
    const d = { delay: 0.9 + i * 0.2 };
    api.stamp(1, label, [RX + 0.75 + i * 1.55, -1.75], { size: 0.22, rot: -0.04, hex }, d);
    if (i) api.text(1, '›', { font: 'title', size: 0.3, hex: T.inkSoft, anchorX: 'center', anchorY: 'middle' }, [RX + i * 1.55 - 0.03, -1.75], d);
  });
  api.text(1, 'Erst im Simulator, dann in der Neura-VM, dann im Labor – derselbe Client, nur ein anderer Host.', { font: 'sans', size: 0.19, hex: T.inkSoft, anchorY: 'top', maxWidth: W + 0.3, lineHeight: 1.3 }, [RX - 0.05, -2.35], { delay: 1.4 });
  api.text(1, 'Alle Schritte auch per Kommandozeile: robot_check', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top', maxWidth: W + 0.3 }, [RX - 0.05, -3.2], { delay: 1.5 });
}

// ---------------------------------------------------------------- 6.7 Rauschtrichter (Seitenansicht, echte Episoden der Anlage)
function sheetFunnel(api) {
  const m4 = api.ctx.data.m4;
  const sd = m4.side;
  const n = m4.noise;
  const eps = sd.episodes;
  const HMAX = 420; // mm über PICK
  const PT = sd.pick_above_table_mm; // TCP an PICK steht so hoch über dem Tisch
  const DMAX = 45; // mm seitlich
  const YB = -2.75; // PICK
  const YT = 2.55;
  const XC = X0 + 4.6; // Sollbahn
  const SX = 3.4 / DMAX;
  const Y = (h) => YB + (h / HMAX) * (YT - YB);
  const X = (d) => XC + d * SX;
  const d = (k, dur = 0.6) => ({ delay: k, dur });
  const lab = { font: 'mono', size: 0.12, hex: T.inkSoft };
  // Achsen: Höhe über PICK senkrecht, seitliche Abweichung waagrecht
  api.line(0, [[XC, YB], [XC, YT]], { width: 1.2, dashed: true, dash: 0.08, gap: 0.06, hex: T.ink }, d(0));
  api.text(0, 'Sollbahn', { font: 'monoMedium', size: 0.14, anchorX: 'center', anchorY: 'bottom' }, [XC, YT + 0.08], d(0.05));
  [-DMAX, -20, 20, DMAX].forEach((v) => {
    api.text(0, `${v > 0 ? '+' : '−'}${Math.abs(v)}`, { ...lab, anchorX: 'center', anchorY: 'top' }, [X(v), YB - 0.5], d(0.05));
  });
  api.text(0, 'seitliche Abweichung von der Sollbahn in mm (x und y)', { ...lab, anchorX: 'center', anchorY: 'top' }, [XC, YB - 0.72], d(0.1));
  [100, 200, 300, 400].forEach((ht) => {
    api.line(0, [[X(-DMAX) - 0.25, Y(ht - PT)], [X(-DMAX) - 0.15, Y(ht - PT)]], { width: 1, hex: T.inkSoft }, d(0.05));
    api.text(0, String(ht), { ...lab, anchorX: 'right', anchorY: 'middle' }, [X(-DMAX) - 0.3, Y(ht - PT)], d(0.05));
  });
  api.text(0, 'TCP-Höhe über dem Tisch in mm', { ...lab, anchorX: 'left', anchorY: 'bottom' }, [X(-DMAX) - 0.85, YT + 0.08], d(0.1));
  // Tisch unter dem Greifpunkt
  const yT = Y(-PT);
  api.line(0, [[X(-DMAX), yT], [X(DMAX), yT]], { width: 1.2, hex: T.ink }, d(0.1));
  for (let x = X(-DMAX); x < X(DMAX) - 0.1; x += 0.22) api.line(0, [[x, yT - 0.02], [x + 0.14, yT - 0.24]], { width: 1, hex: T.inkSoft }, d(0.15, 0.3));
  api.text(0, 'Tisch', { font: 'monoMedium', size: 0.14, hex: T.inkSoft, anchorX: 'right', anchorY: 'top' }, [X(-DMAX) - 0.15, yT - 0.02], d(0.2));
  // Wegpunkte gelb: ANFLUG, PRE_PICK, PICK
  [[m4.anflug_mm, 'ANFLUG'], [m4.pre_pick_mm, 'PRE_PICK'], [0, 'PICK']].forEach(([h, name], i) => {
    api.line(0, [[X(-DMAX), Y(h)], [X(DMAX), Y(h)]], { width: 1.4, dashed: true, dash: 0.06, gap: 0.06, hex: T.waypoint }, d(0.2 + i * 0.1));
    api.text(0, `${name} · ${fmt(h + PT, 0)} mm`, { font: 'monoMedium', size: 0.14, hex: T.waypoint, anchorY: 'middle' }, [X(DMAX) + 0.1, Y(h) + (h === 0 ? 0.12 : 0)], d(0.25 + i * 0.1));
  });
  // echte Episoden: von oben nach unten, x und y je eine Linie
  eps.forEach((e, k) => {
    ['dx', 'dy'].forEach((c) => {
      const pts = e.h.map((h, i) => [X(e[c][i]), Y(Math.min(h, HMAX))]);
      const l = api.line(0, pts, { width: 1, hex: MODULE_COLOR.M4 }, { delay: 0.5 + k * 0.02, dur: 1.2 });
      l.opacity = 0.45;
    });
  });
  // Schritt 1: Hülle je Höhenband – unten schmal
  const BAND = 10;
  const hull = [[0, 0]];
  for (let h = 0; h <= HMAX; h += BAND) {
    let m = 0;
    eps.forEach((e) => e.h.forEach((hh, i) => {
      if (hh >= h && hh < h + BAND) m = Math.max(m, Math.abs(e.dx[i]), Math.abs(e.dy[i]));
    }));
    if (m > 0) hull.push([h + BAND / 2, m]);
  }
  [1, -1].forEach((sg) => api.line(1, hull.map(([h, m]) => [X(sg * m), Y(h)]), { width: 1.6, dashed: true, dash: 0.07, gap: 0.05, hex: T.ink }, d(0.1, 1.0)));
  // Schritt 1: Rejection Sampling an einem Beispiel – grün eine echte, angenommene Episode; rot dieselbe Bahn mit einem
  // konstruierten Rest von 6 mm auf den letzten Zentimetern: verworfen und neu gezogen
  const dev = (e) => Math.max(...e.dx.map(Math.abs));
  const good = eps.reduce((a, e) => (Math.abs(dev(e) - 15) < Math.abs(dev(a) - 15) ? e : a));
  const REST = 6;
  const ramp = (h) => (h < 45 ? REST * (1 - Math.max(0, h - 5) / 40) : 0);
  const okPts = good.h.map((h, i) => [X(good.dx[i]), Y(Math.min(h, HMAX))]);
  const badPts = good.h.map((h, i) => [X(good.dx[i] + ramp(h)), Y(Math.min(h, HMAX))]);
  const dOk = { delay: 1.0, dur: 1.0 };
  const dBad = { delay: 1.4, dur: 1.0 };
  api.line(1, badPts, { width: 2.4, hex: T.signal }, dBad);
  api.line(1, okPts, { width: 2.4, hex: T.good }, dOk);
  const bx = X(good.dx[good.dx.length - 1] + REST);
  const by = Y(0);
  api.line(1, [[bx - 0.16, by - 0.16], [bx + 0.16, by + 0.16]], { width: 2.6, hex: T.signal }, { delay: 2.3, dur: 0.2 });
  api.line(1, [[bx - 0.16, by + 0.16], [bx + 0.16, by - 0.16]], { width: 2.6, hex: T.signal }, { delay: 2.4, dur: 0.2 });
  api.text(1, `verworfen: ${REST} mm daneben (erlaubt ${fmt(sd.rest_max_mm, 1)})`, { font: 'monoMedium', size: 0.13, hex: T.signal, anchorX: 'left', anchorY: 'middle' }, [X(-DMAX) + 0.05, Y(22)], { delay: 2.4 });
  api.text(1, 'angenommen (echte Episode)', { font: 'monoMedium', size: 0.13, hex: T.good, anchorX: 'left', anchorY: 'middle' }, [X(-DMAX) + 0.05, Y(38)], { delay: 1.8 });
  // rechts: was der Trichter tut (Punkt 5 noch offen, Jeremy prüft)
  const RX = 2.5;
  const rows = [
    [0, 'Trichter', `volles Rauschen im Transit, ab ${fmt(n.funnel_mm[1], 0)} mm vor dem Greifpunkt abklingend, auf den letzten ${fmt(n.funnel_mm[0], 0)} mm null – genau greifen, im Transit schlingern`],
    [0, 'Rauschfaktor je Episode', 'zufällig 0 bis 1 – von fast ideal bis volle Streuung'],
    [1, 'Asymmetrische Grenzen', `seitlich und nach oben darf das Rauschen bis ${fmt(sd.limit_mm.xy, 0)} mm ausschlagen, nach unten nur ${fmt(-sd.limit_mm.z_down, 0)} mm – es drückt den Greifer nie Richtung Tisch`],
    [1, 'Rejection Sampling', `jede Bahn wird vorab geprüft (IK, Kollision, auf den letzten ${fmt(sd.free_mm, 0)} mm höchstens ${fmt(sd.rest_max_mm, 1)} mm neben der Sollbahn), sonst neu gezogen (bis ${sd.max_rejects}×)`],
    [1, 'Neu: gezielter Versatz', 'im senkrechten Abstieg ist das Rauschen null – jede 2. Episode kommt 5–10 mm und 10–20° versetzt an, die Aktion zeigt zur Mitte'],
  ];
  // je Schritt von oben nach unten: 1, 2 – dann 3, 4, 5
  rows.forEach(([step, t, b], i) => api.row(step, i + 1, t, b, 2.45 - i * 1.22, { x: RX, width: 4.9, size: 0.25, delay: 0.3 + (step ? i - 2 : i) * 0.25 }));
  api.text(0, `${eps.length} echte Episoden der Anlage vom 19.11. bis zum Griff · Quelle: ${sd.source} (pose_ideal, pose_noisy), bc/config.py`, { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 1.0 });
}

// ---------------------------------------------------------------- 6.2 Warum Imitation Learning? (Tabelle)
function sheetIL(api) {
  const LX = X0 + 0.7;
  const MX = 0.35; // Trennlinie
  const RX = MX + 0.5;
  const YH = 2.45;
  const d = (k) => ({ delay: k });
  api.text(0, 'gegenüber dem klassischen Ansatz (M1 erkennt und kalibriert, M2 plant die Bahn)', { font: 'mono', size: 0.15, hex: T.inkSoft, anchorY: 'top' }, [LX, YH + 0.25], d(0));
  api.text(0, 'VORTEILE', { font: 'monoMedium', size: 0.2, hex: T.good, letterSpacing: 0.08, anchorY: 'top' }, [LX, YH - 0.25], d(0.1));
  api.text(0, 'NACHTEILE', { font: 'monoMedium', size: 0.2, hex: T.signal, letterSpacing: 0.08, anchorY: 'top' }, [RX, YH - 0.25], d(0.1));
  api.line(0, [[LX, YH - 0.65], [7.0, YH - 0.65]], { width: 1.4 }, { delay: 0.1, dur: 0.5 });
  api.line(0, [[MX, YH - 0.2], [MX, -2.25]], { width: 1, hex: T.inkSoft }, { delay: 0.2, dur: 0.5 });
  const pros = [
    ['Keine Kalibrierung', 'keine Koordinatensysteme, keine Homographie, keine Positionskorrektur'],
    ['Keine Bildverarbeitung je Merkmal', 'kein Weißabgleich und keine Belichtung fürs Erkennen, Objektgröße egal'],
    ['Kein Bahnprogramm je Teil', 'ein neues Teil braucht neue Daten, keinen neuen Code'],
    ['Korrigiert in jedem Takt', 'schaut 15-mal je Sekunde hin und fährt nach'],
    ['Lernt den Aufbau mit', 'Anlage, Kameras und Greifer gehen implizit ein'],
  ];
  const cons = [
    ['Mehr Hardware', 'GPU für Training und Inferenz, zusätzliche Handkamera'],
    ['Daten und Training', 'Aufnahme an der Anlage und Training kosten Tage'],
    ['Nicht deterministisch', 'gleiche Lage, nicht immer gleiche Bahn – schwer nachzuweisen'],
    ['Nur so gut wie die Daten', 'fern vom Training wird es schlechter'],
    ['Aufbau muss bleiben', 'Licht, Weißabgleich und Kameralage wie bei der Aufnahme'],
    ['Schwer zu erklären', 'man sieht nicht hinein, warum sie etwas tut'],
  ];
  const ROW = 0.66;
  const item = (x, i, [t, b], hex, sign) => {
    const y = YH - 0.95 - i * ROW;
    const k = 0.35 + i * 0.12;
    api.text(0, sign, { font: 'title', size: 0.3, hex, anchorY: 'top' }, [x, y + 0.02], d(k));
    api.text(0, t, { font: 'sansMedium', size: 0.24, anchorY: 'top' }, [x + 0.35, y], d(k));
    api.text(0, b, { font: 'sans', size: 0.16, hex: T.inkSoft, anchorY: 'top', maxWidth: 6.4 }, [x + 0.35, y - 0.32], d(k + 0.05));
  };
  pros.forEach((r, i) => item(LX, i, r, T.good, '+'));
  cons.forEach((r, i) => item(RX, i, r, T.signal, '−'));
  // Schritt 1: Nutzen für das IKR
  api.line(1, [[LX, -2.7], [7.0, -2.7]], { width: 1.4, hex: MODULE_COLOR.M4 }, { delay: 0, dur: 0.5 });
  api.text(1, 'Für das IKR', { font: 'title', size: 0.34, hex: MODULE_COLOR.M4, anchorY: 'top' }, [LX, -2.9], d(0.2));
  api.text(1, 'Erfahrung mit Imitation Learning sammeln: die Pipeline aus Aufnahme, Training, Ausführung und DAgger lässt sich auf andere Roboter, Greifer und Aufgaben übertragen. Behavior Cloning ist der Einstieg, VLA-Modelle bauen auf demselben Prinzip auf.',
    { font: 'sans', size: 0.2, hex: T.ink, anchorY: 'top', maxWidth: 10.6, lineHeight: 1.3 }, [LX + 3.2, -2.9], d(0.35));
}

// ---------------------------------------------------------------- 6.4 Von Bild und Zustand zur Bahn (echtes Beobachtungspaar)
// Die Kästchen aus 6.3 stehen beim Betreten an derselben Stelle und wandern dann um die echten Daten eines Takts
// (Schritt 0). Schritt 1: Netz und Aktionsblock. Schritt 2: wie der Block gefahren wird (8 nutzbar, alle 2 Takte neu,
// überlappende Blöcke gemittelt, Tiefpass).
function sheetObs(api) {
  const m4 = api.ctx.data.m4;
  const o = m4.side.obs;
  const pc = m4.policy;
  const d = (k) => ({ delay: k });
  const ease = (v) => v * v * (3 - 2 * v);
  const lab = { font: 'mono', size: 0.16, hex: T.inkSoft, anchorY: 'bottom' };
  // Rechtecke [x0, y0 (oben), x1, y1 (unten)]
  const rectPts = ([x0, y0, x1, y1]) => [v3(x0, y0), v3(x1, y0), v3(x1, y1), v3(x0, y1), v3(x0, y0)]; // geschlossen, auch nach setPts
  const lerpR = (a, b, v) => a.map((p, i) => p + (b[i] - p) * v);
  // Endlage
  const IW = 3.0;
  const IH = (IW * o.images.wrist.h) / o.images.wrist.w;
  const IX = X0 + 2.1;
  const IY = [1.1, -1.95];
  const SX = IX + IW / 2 + 0.6;
  const RS = 0.32; // Zeilenabstand Zustand
  const BW = 1.9;
  const BX = SX + 5.1;
  const CB = [BX + BW / 2 + 0.55, 2.6, 7.35, -1.95];
  const morph = [
    // [Schema wie 6.3, Ziel, Farbe]
    [[X0 + 0.6, 2.2, X0 + 3.9, 1.25], [IX - IW / 2 - 0.07, IY[0] + IH / 2 + 0.07, IX + IW / 2 + 0.07, IY[0] - IH / 2 - 0.07], MODULE_COLOR.M1],
    [[X0 + 0.6, 1.05, X0 + 3.9, 0.1], [IX - IW / 2 - 0.07, IY[1] + IH / 2 + 0.07, IX + IW / 2 + 0.07, IY[1] - IH / 2 - 0.07], MODULE_COLOR.M4],
    [[X0 + 0.6, -0.1, X0 + 3.9, -1.05], [SX - 0.2, 2.5, SX + 3.75, 2.4 - 13 * RS - 0.4], T.inkSoft],
    [[X0 + 4.6, 2.2, X0 + 7.0, -1.05], [BX - BW / 2, 1.0, BX + BW / 2, -0.4], MODULE_COLOR.M4],
  ].map(([a, b, hex]) => ({ a, b, line: new InkLine(rectPts(a), { width: 1.6, hex, progress: 1 }) }));
  morph.forEach((m) => api.scene.add(m.line.object));
  // Beschriftungen des Schemas weichen, die Kästchen wandern
  const old = [
    api.text(0, 'Kamera oben', { font: 'sansMedium', size: 0.22, anchorY: 'top' }, [X0 + 0.75, 2.06]),
    api.text(0, 'Handgelenkkamera', { font: 'sansMedium', size: 0.22, anchorY: 'top' }, [X0 + 0.75, 0.91]),
    api.text(0, 'Zustand', { font: 'sansMedium', size: 0.22, anchorY: 'top' }, [X0 + 0.75, -0.24]),
    api.text(0, 'Diffusion Policy', { font: 'sansMedium', size: 0.22, anchorY: 'top' }, [X0 + 4.75, 2.06]),
  ];
  old.forEach((t) => (t.opacity = 1));
  api.add(0, (v) => old.forEach((t) => (t.opacity = 1 - clamp01(v * 4))), { delay: 0, dur: 0.6 });
  api.add(0, (v) => morph.forEach((m) => setPts(m.line, rectPts(lerpR(m.a, m.b, ease(v))))), { delay: 0.3, dur: 1.3 });
  // Inhalt erscheint in den Kästchen
  [['scene', 'Kamera oben (Szene)'], ['wrist', 'Handgelenkkamera']].forEach(([k, name], i) => {
    const pcd = new PhotoCard(o.images[k].url, { width: IW, aspect: o.images[k].h / o.images[k].w, border: 0, bottom: 0 });
    pcd.card.visible = false; // nur das Foto – den Rahmen gibt das gewanderte Kästchen
    pcd.object.position.set(IX, IY[i], 0.05);
    pcd.opacity = 0;
    api.add(0, pcd, { delay: 0.9 + i * 0.1, dur: 1.1 }); // blendet ein, während der Rahmen ankommt
    api.text(0, `${name} · ${pc.image[0]} × ${pc.image[1]}`, lab, [IX - IW / 2 - 0.07, IY[i] + IH / 2 + 0.15], { delay: 1.1 + i * 0.1, dur: 0.9 });
  });
  const names = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'x', 'y', 'z', 'qw', 'qx', 'qy', 'qz', 'Greifer'];
  const units = ['rad', 'rad', 'rad', 'rad', 'rad', 'rad', 'm', 'm', 'm', '', '', '', '', ''];
  api.text(0, 'Zustand · 14 Werte', lab, [SX - 0.2, 2.58], d(1.6));
  o.state.forEach((v, i) => {
    const y = 2.3 - i * RS;
    api.text(0, names[i], { font: 'mono', size: 0.17, hex: T.inkSoft, anchorY: 'top' }, [SX, y], { delay: 1.0 + i * 0.05, dur: 0.8 });
    api.text(0, `${v < 0 ? '−' : ''}${fmt(Math.abs(v), 3)} ${units[i]}`, { font: 'monoMedium', size: 0.17, anchorX: 'right', anchorY: 'top' }, [SX + 2.4, y], { delay: 1.0 + i * 0.05, dur: 0.8 });
  });
  [['Gelenke', 0, 5], ['TCP-Pose', 6, 12], ['Greifer', 13, 13]].forEach(([g, a, b], i) => {
    const y0 = 2.3 - a * RS + 0.02;
    const y1 = 2.3 - b * RS - 0.22;
    api.line(0, [[SX + 2.55, y0], [SX + 2.65, y0], [SX + 2.65, y1], [SX + 2.55, y1]], { width: 1, hex: T.inkSoft }, { delay: 1.9 + i * 0.1, dur: 0.3 });
    api.text(0, g, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'middle' }, [SX + 2.75, (y0 + y1) / 2], d(2.0 + i * 0.1));
  });
  api.text(0, 'Diffusion', { font: 'sansMedium', size: 0.26, hex: MODULE_COLOR.M4, anchorX: 'center', anchorY: 'middle' }, [BX, 0.55], d(1.6));
  api.text(0, 'Policy', { font: 'sansMedium', size: 0.26, hex: MODULE_COLOR.M4, anchorX: 'center', anchorY: 'middle' }, [BX, 0.2], d(1.6));
  api.text(0, `${pc.inference_steps} Schritte`, { font: 'mono', size: 0.15, hex: T.inkSoft, anchorX: 'center', anchorY: 'middle' }, [BX, -0.15], d(1.7));
  // Pfeile berühren die Kästen: Bilder → Zustand, Zustand → Netz
  const arrow = (step, x0, x1, y, hex, k) => {
    api.line(step, [[x0, y], [x1, y]], { width: 1.4, hex }, { delay: k, dur: 0.4 });
    api.line(step, [[x1 - 0.14, y + 0.08], [x1, y], [x1 - 0.14, y - 0.08]], { width: 1.4, hex }, { delay: k + 0.3, dur: 0.2 });
  };
  const xImg = IX + IW / 2 + 0.07;
  IY.forEach((y, i) => arrow(0, xImg, SX - 0.2, y, T.inkSoft, 2.1 + i * 0.1));
  arrow(0, SX + 3.75, BX - BW / 2, 0.3, T.inkSoft, 2.3);
  // Schritt 1: Aktionsblock in eigenem Kasten. Vorhergesagt (und gesendet) werden je Takt 6 Gelenk-Sollwinkel + Greifer;
  // gezeigt wird zur Anschauung die TCP-Höhe, die sich aus diesen Sollwinkeln ergibt (ideale Pose = FK der Labels).
  arrow(1, BX + BW / 2, CB[0], 0.3, MODULE_COLOR.M4, 0);
  api.line(1, rectPts(CB), { width: 1.4, hex: MODULE_COLOR.M4 }, { delay: 0.1, dur: 0.6 });
  const CX0 = CB[0] + 0.55;
  const CX1 = CB[2] - 0.3;
  const zs = o.chunk_tcp_z_mm;
  const H = zs.length;
  const zMin = Math.min(...zs, -1);
  const CY0 = -0.85;
  const CY1 = 0.95;
  const Yz = (z) => CY1 + (z / zMin) * (CY0 - CY1);
  const Xk = (k) => CX0 + 0.15 + (k / (H - 1)) * (CX1 - CX0 - 0.25);
  api.text(1, 'Aktionsblock', { font: 'sansMedium', size: 0.3, anchorY: 'top' }, [CB[0] + 0.2, CB[1] - 0.12], d(0.3));
  api.text(1, `${H} Takte · je Takt 6 Gelenk-Sollwinkel + Greifer – das geht an den Roboter`, { font: 'mono', size: 0.15, hex: T.inkSoft, anchorY: 'top', maxWidth: CB[2] - CB[0] - 0.4 }, [CB[0] + 0.2, CB[1] - 0.55], d(0.35));
  api.line(1, [[CX0, CY1 + 0.1], [CX0, CY0 - 0.1], [CX1, CY0 - 0.1]], { width: 1.1, hex: T.inkSoft }, { delay: 0.4, dur: 0.5 });
  [[0, '0'], [zMin, fmt(zMin, 0)]].forEach(([z, t]) => api.text(1, t.replace('-', '−'), { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'right', anchorY: 'middle' }, [CX0 - 0.08, Yz(z)], d(0.5)));
  api.text(1, 'daraus: TCP-Höhe in mm, relativ zu jetzt', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'bottom' }, [CX0 - 0.4, CY1 + 0.42], d(0.5));
  [[0, '1'], [7, '8'], [H - 1, String(H)]].forEach(([k, t]) => api.text(1, t, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'center', anchorY: 'top' }, [Xk(k), CY0 - 0.17], d(0.5)));
  api.text(1, 'Takt (15 Hz)', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'right', anchorY: 'top' }, [CX1, CY0 - 0.42], d(0.6));
  const dot = (x, y, r) => Array.from({ length: 11 }, (_, j) => [x + r * Math.cos((j / 10) * 2 * Math.PI), y + r * Math.sin((j / 10) * 2 * Math.PI)]);
  api.line(1, zs.map((z, k) => [Xk(k), Yz(z)]), { width: 1, hex: T.inkSoft }, { delay: 0.6, dur: 0.8 });
  zs.forEach((z, k) => api.line(1, dot(Xk(k), Yz(z), 0.06), { width: 2, hex: T.inkSoft }, { delay: 0.6 + k * 0.04, dur: 0.2 }));
  api.text(1, 'absenken', { font: 'mono', size: 0.15, hex: T.inkSoft, anchorY: 'middle' }, [Xk(1) + 0.25, Yz(zs[0])], d(1.2));
  api.text(1, 'Endanflug', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'right', anchorY: 'bottom' }, [Xk(H - 1), Yz(zMin) + 0.42], d(1.2));
  api.text(1, 'gezeigt ist die TCP-Höhe, die sich aus den Sollwinkeln ergibt', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorY: 'top', maxWidth: CB[2] - CB[0] - 0.4 }, [CB[0] + 0.2, CY0 - 0.68], d(1.3));
  // Schritt 2: Ausführung in eigenem Kasten unter Netz und Aktionsblock
  const xm = (Xk(pc.n_action - 1) + Xk(pc.n_action)) / 2;
  zs.slice(0, pc.n_action).forEach((z, k) => api.line(2, dot(Xk(k), Yz(z), 0.09), { width: 3.2, hex: MODULE_COLOR.M4 }, { delay: 0.1 + k * 0.06, dur: 0.2 }));
  api.line(2, [[xm, CY1 + 0.05], [xm, CY0 - 0.1]], { width: 1.2, hex: MODULE_COLOR.M4, dashed: true, dash: 0.07, gap: 0.05 }, { delay: 0.5, dur: 0.4 });
  api.text(2, `${pc.n_action} nutzbar`, { font: 'monoMedium', size: 0.15, hex: MODULE_COLOR.M4, anchorX: 'right', anchorY: 'bottom' }, [xm - 0.08, CY1 + 0.05], d(0.6));
  api.text(2, 'Rest ungenutzt', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'left', anchorY: 'bottom' }, [xm + 0.08, CY1 + 0.05], d(0.7));
  const EP = [BX - BW / 2, -2.12, CB[2], -3.2];
  api.line(2, rectPts(EP), { width: 1.4, hex: MODULE_COLOR.M4 }, { delay: 0.6, dur: 0.6 });
  api.text(2, 'Ausführung', { font: 'sansMedium', size: 0.24, anchorY: 'top' }, [EP[0] + 0.15, EP[1] - 0.12], d(0.8));
  const n = Math.ceil(pc.n_action / pc.replan);
  api.text(2, `neuer Block alle ${pc.replan} Takte · je Takt Mittel aus ${n} · Tiefpass ${fmt(pc.lowpass, 1)}`, { font: 'mono', size: 0.13, hex: T.inkSoft, anchorY: 'top', maxWidth: CX0 - EP[0] - 0.55, lineHeight: 1.2 }, [EP[0] + 0.15, EP[1] - 0.45], d(0.9));
  const TY = EP[1] - 0.3;
  const k0 = (n - 1) * pc.replan;
  for (let r = 0; r < n; r++) {
    const a = r * pc.replan;
    const y = TY - r * 0.2;
    api.line(2, [[Xk(a), y], [Xk(a + pc.n_action - 1), y]], { width: 4, hex: MODULE_COLOR.M4 }, { delay: 1.0 + r * 0.2, dur: 0.3 });
    api.text(2, r ? `t+${a}` : 't', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'right', anchorY: 'middle' }, [Xk(0) - 0.1, y], d(1.0 + r * 0.2));
  }
  api.line(2, rectPts([Xk(k0) - 0.08, TY + 0.15, Xk(k0) + 0.08, TY - (n - 1) * 0.2 - 0.15]), { width: 1.2, hex: T.signal }, { delay: 1.8, dur: 0.4 });
  api.text(2, `Mittel aus ${n}`, { font: 'monoMedium', size: 0.13, hex: T.signal, anchorX: 'left', anchorY: 'middle' }, [Xk(pc.n_action - 1) + 0.2, TY], d(1.9));
  api.text(2, `Beispiel: Episode ${o.episode.replace('ep_', '')} vom 19.11., Takt ${o.takt}, TCP ${fmt(o.h_mm, 0)} mm über PICK · Bilder wie aufgenommen (Rotstich)`, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top' }, [X0 + 0.7, -3.85], d(2.0));
}

// ---------------------------------------------------------------- 6.11 Nach DAgger an der Anlage (vorher C2, nachher vorläufig G2b)
function sheetAfterDagger(api) {
  const p = api.ctx.data.m4.plant;
  const g = p.g2b;
  const PW = 6.9;
  const LX = X0 + 0.6 + PW / 2;
  const GX = LX + PW + 0.5;
  const fy = 0.85;
  const photo = (step, f, x, w, timing) => {
    const c = new PhotoCard(f.url, { width: w, aspect: f.h / f.w, border: 0.05, bottom: 0.05 });
    c.object.position.set(x, fy, 0.02);
    c.opacity = 0;
    return api.add(step, c, timing);
  };
  photo(0, p.figure, LX, PW, { delay: 0.1, dur: 0.6 });
  photo(0, g.figure, GX, PW, { delay: 0.5, dur: 0.6 });
  const fh = (PW * p.figure.h) / p.figure.w;
  const yb = fy - fh / 2 - 0.25;
  const block = (x, title, big, lines, hex, k) => {
    api.text(0, title, { font: 'monoMedium', size: 0.16, hex: T.inkSoft, anchorY: 'top' }, [x, yb], { delay: k });
    api.text(0, big, { font: 'title', size: 0.42, hex, anchorY: 'top' }, [x, yb - 0.32], { delay: k + 0.1 });
    api.text(0, lines, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', maxWidth: PW - 0.2, lineHeight: 1.3 }, [x, yb - 0.9], { delay: k + 0.2 });
  };
  block(LX - PW / 2, `VORHER · 16.11. · C2 · ${p.demos} EPISODEN · OHNE GLÄTTUNG`, `${fmt(p.plant_median_mm)} mm`,
    `Greifpunkt im Median daneben (vorhergesagt), ${p.plant_le10[0]} von ${p.plant_le10[1]} Probegriffen ≤ 10 mm.`, T.signal, 0.3);
  block(GX - PW / 2, `NACHHER · 26.11. · G2b · NACH DAGGER · GLÄTTUNG ${fmt(g.lowpass, 1)}`, `${fmt(g.xy_median_mm)} mm`,
    `waagrecht im Median daneben (p90 ${fmt(g.xy_p90_mm)} mm), ${g.success} von ${g.runs} Griffen mit Spiel – anderes Modell, andere Aufnahmen.`, T.good, 0.7);
  api.stamp(0, 'OFFEN', [5.2, 3.5], { size: 0.24, rot: -0.04, hex: T.signal, sub: 'rechts: C2 mit DAgger oder G2-Fahrten' }, { delay: 1.2 });
  api.text(0, 'Quelle: Berichte/2026-11-16_Anlagentest_var_C2, Berichte/2026-11-26_Vergleich_DAgger (Rohdaten der Vergleichsfahrten)', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.9 });
}

// ---------------------------------------------------------------- 6.12 Pendeln: dieselbe Policy (G2) mit und ohne Glättung
function sheetSmooth(api) {
  const sm = api.ctx.data.m4.smooth;
  const by = (a) => sm.groups.find((g) => g.alpha === a);
  const panels = [by(1), by(0.5), by(0.25)].filter(Boolean);
  const PW = 4.35;
  const PH = 2.3;
  const PY = 0.15; // Unterkante der Felder
  const lab = { font: 'mono', size: 0.13, hex: T.inkSoft };
  const panel = (step, gr, i, k) => {
    const x0 = X0 + 0.9 + i * (PW + 0.45);
    const X = (h) => x0 + ((120 - Math.min(h, 120)) / 120) * PW;
    const Y = (v) => PY + (Math.min(v, 30) / 30) * PH;
    const d = (dd) => ({ delay: k + dd, dur: 0.5 });
    api.line(step, [[x0, PY + PH], [x0, PY], [x0 + PW, PY]], { width: 1.1, hex: T.inkSoft }, d(0));
    api.line(step, [[x0, Y(10)], [x0 + PW, Y(10)]], { width: 0.9, hex: T.inkFaint, dashed: true, dash: 0.06, gap: 0.05 }, d(0.1));
    if (i === 0) {
      [0, 10, 20, 30].forEach((v) => api.text(step, String(v), { ...lab, anchorX: 'right', anchorY: 'middle' }, [x0 - 0.08, Y(v)], d(0.1)));
    }
    [120, 60, 0].forEach((h) => api.text(step, String(h), { ...lab, anchorX: 'center', anchorY: 'top' }, [X(h), PY - 0.08], d(0.1)));
    const hex = gr.alpha === 1 ? T.signal : MODULE_COLOR.M4;
    gr.runs.forEach((r, j) => {
      const l = api.line(step, r.h.map((h, n) => [X(h), Y(r.xy[n])]), { width: 1.1, hex }, { delay: k + 0.2 + j * 0.02, dur: 0.8 });
      l.opacity = 0.55;
    });
    const name = gr.alpha === 1 ? 'aus (1,0)' : fmt(gr.alpha, 2).replace(/0$/, '');
    api.text(step, `Glättung ${name}`, { font: 'sansMedium', size: 0.24, hex: gr.alpha === 1 ? T.signal : T.ink, anchorY: 'bottom' }, [x0, PY + PH + 0.12], d(0.2));
    api.text(step, `${gr.n} Fahrten · seitlicher Weg unter 60 mm: ${fmt(gr.way_median_mm, 0)} mm`, { ...lab, size: 0.14, anchorY: 'top' }, [x0, PY - 0.35], d(0.4));
  };
  panel(0, panels[0], 0, 0.1);
  api.text(0, 'senkrecht: waagrechter Abstand zu PICK in mm · waagrecht: Höhe des TCP über PICK in mm (Abstieg nach rechts)', { ...lab, anchorY: 'top' }, [X0 + 0.9, PY - 0.72], { delay: 0.5 });
  api.text(0, 'echte Probegriffe an der Anlage, dieselbe Policy G2, 23.11., Stopp ~20 mm über PICK', { ...lab, anchorY: 'top' }, [X0 + 0.9, PY - 0.95], { delay: 0.5 });
  const rows0 = [
    ['Schon ein Block ist ruckig', 'innerhalb eines Aktionsblocks 2,9 mm Ruck (Median), zwei Blöcke liegen für denselben Takt 4,3 mm auseinander'],
    ['Real-Time Chunking hilft nur halb', 'es glättet die Sprünge zwischen den Blöcken, nicht das Zittern innerhalb'],
  ];
  rows0.forEach(([t, b], i) => api.row(0, i + 1, t, b, -1.75, { x: X0 + 0.7 + i * 7.3, width: 6.3, size: 0.25, delay: 0.6 + i * 0.15 }));
  // Schritt 1: Tiefpass auf die Ziele – derselbe Regler, drei Stellungen
  panels.slice(1).forEach((gr, i) => panel(1, gr, i + 1, 0.1 + i * 0.4));
  const o = by(0.75);
  if (o) api.text(1, `0,75: nur ${o.n} Fahrt, nicht gezeigt`, { ...lab, anchorX: 'right', anchorY: 'top' }, [7.3, PY - 0.95], { delay: 1.0 });
  api.stamp(1, 'ENTSCHIEDEN: 0,5', [5.0, 3.5], { size: 0.24, rot: -0.04, hex: T.good, sub: 'Kompromiss Pendeln gegen Nachlauf' }, { delay: 1.4 });
  api.text(1, 'z = a · Ziel + (1 − a) · z vorher   ·   0,5: kein Pendeln mehr, ~1 Takt Nachlauf   ·   0,25: noch ruhiger, ~3 Takte Nachlauf, Transfer ~1/3 langsamer',
    { font: 'mono', size: 0.15, hex: T.ink, anchorY: 'top', maxWidth: 14.4 }, [X0 + 0.7, -2.9], { delay: 1.1 });
  api.text(1, 'Quelle: Rollouts G2 23.11. (checkpoints/G2_…/rollouts, args.glaettung), bc/config.py POLICY_COMMAND_LOWPASS_ALPHA, Berichte/Testprotokoll.md', { ...lab }, [X0 + 0.7, -3.95], { delay: 1.2 });
}

// ---------------------------------------------------------------- 6.13 Die letzten Millimeter: echte Griffe G2b mit bekannter Lage
function sheetLastMm(api) {
  const gs = api.ctx.data.m4.grasps;
  const HMAX = 160;
  const DMAX = 25;
  const YB = -2.6;
  const YT = 2.45;
  const XC = X0 + 4.4;
  const SX = 3.3 / DMAX;
  const Y = (h) => YB + ((h + 8) / (HMAX + 8)) * (YT - YB); // Tisch 8 mm unter PICK
  const X = (dv) => XC + dv * SX;
  const lab = { font: 'mono', size: 0.13, hex: T.inkSoft };
  const d = (k, dur = 0.5) => ({ delay: k, dur });
  api.line(0, [[XC, Y(0)], [XC, YT]], { width: 1.2, dashed: true, dash: 0.08, gap: 0.06, hex: T.ink }, d(0));
  api.text(0, 'PICK', { font: 'monoMedium', size: 0.14, anchorX: 'center', anchorY: 'bottom' }, [XC, YT + 0.08], d(0.05));
  [-20, -10, 10, 20].forEach((v) => api.text(0, `${v > 0 ? '+' : '−'}${Math.abs(v)}`, { ...lab, anchorX: 'center', anchorY: 'top' }, [X(v), YB - 0.35], d(0.05)));
  api.text(0, 'seitlicher Abstand zu PICK in mm (x und y)', { ...lab, anchorX: 'center', anchorY: 'top' }, [XC, YB - 0.58], d(0.1));
  [0, 50, 100, 150].forEach((h) => api.text(0, String(h), { ...lab, anchorX: 'right', anchorY: 'middle' }, [X(-DMAX) - 0.12, Y(h)], d(0.05)));
  api.text(0, 'Höhe des TCP über PICK in mm', { ...lab, anchorY: 'bottom' }, [X(-DMAX) - 0.5, YT + 0.08], d(0.1));
  // Tisch 8 mm unter PICK, Oberkante 7 mm über PICK
  api.line(0, [[X(-DMAX), YB], [X(DMAX), YB]], { width: 1.2, hex: T.ink }, d(0.1));
  for (let x = X(-DMAX); x < X(DMAX) - 0.1; x += 0.22) api.line(0, [[x, YB - 0.02], [x + 0.14, YB - 0.22]], { width: 1, hex: T.inkSoft }, d(0.15, 0.3));
  api.text(0, 'Tisch', { font: 'monoMedium', size: 0.13, hex: T.inkSoft, anchorX: 'right', anchorY: 'middle' }, [X(-DMAX) - 0.12, YB], d(0.2));
  api.line(0, [[X(-DMAX), Y(7)], [X(DMAX), Y(7)]], { width: 1.2, hex: MODULE_COLOR.M4, dashed: true, dash: 0.06, gap: 0.05 }, d(0.2));
  api.text(0, 'Oberkante Teil', { font: 'monoMedium', size: 0.13, hex: MODULE_COLOR.M4, anchorY: 'middle' }, [X(DMAX) + 0.1, Y(7)], d(0.25));
  // Teil (39,9 mm breit, 15 mm hoch) und die Backen, wenn der TCP genau auf PICK steht (innen 44,8 mm)
  const hw = 39.9 / 2;
  const jw = 44.8 / 2;
  api.line(0, [[X(-hw), Y(-8)], [X(-hw), Y(7)], [X(hw), Y(7)], [X(hw), Y(-8)]], { width: 1.8, hex: T.part }, d(0.3));
  api.text(0, '39,9', { font: 'monoMedium', size: 0.13, hex: T.part, anchorX: 'center', anchorY: 'middle' }, [X(-hw / 2), Y(-1)], d(0.35));
  [-1, 1].forEach((sg) => api.line(0, [[X(sg * jw), Y(-5)], [X(sg * jw), Y(32)], [X(sg * (jw + 4)), Y(32)], [X(sg * (jw + 4)), Y(-5)]], { width: 1.6, hex: T.ink }, d(0.4)));
  api.text(0, 'Backen · innen 44,8', { font: 'monoMedium', size: 0.13, anchorX: 'left', anchorY: 'bottom' }, [X(jw), Y(33)], d(0.45));
  api.text(0, '2,45 je Seite', { font: 'monoMedium', size: 0.13, hex: T.signal, anchorX: 'right', anchorY: 'middle' }, [X(-jw) - 0.1, Y(15)], d(0.5));
  api.text(0, 'der TCP darf seitlich höchstens 2,45 mm daneben liegen', { font: 'mono', size: 0.13, hex: T.signal, anchorX: 'center', anchorY: 'top' }, [XC, YB - 0.85], d(0.55));
  gs.runs.forEach((r, k) => ['dx', 'dy'].forEach((c) => {
    const l = api.line(0, r.h.map((h, i) => [X(Math.max(-DMAX, Math.min(DMAX, r[c][i]))), Y(Math.min(h, HMAX))]), { width: 1.6, hex: T.signal }, { delay: 0.5 + k * 0.2, dur: 1.2 });
    l.opacity = c === 'dx' ? 0.9 : 0.5;
  }));
  api.text(0, `${gs.runs.length} echte Griffe von G2b mit bekannter Lage (25./26.11.), bis der Greifer schließt`, { ...lab }, [X0 + 0.7, -3.95], d(1.0));
  const RX = 1.9;
  const rows = [
    ['Oben ruhig, unten Sprünge', 'unterhalb der Oberkante 4–10 mm seitlich in 3–5 Takten, die Höhe springt um ±3 mm'],
    ['Die Policy wird unsicher', 'Streuung der Vorhersagen steigt von ~0,005 auf 0,02–0,1 rad – sie springt zwischen Lösungen'],
    ['Diesen Bereich sieht kein Training', 'Probegriff und DAgger stoppen über der Oberkante, das Rauschen ist dort null'],
    ['Und kaum Spiel', 'Backen öffnen 44,8 mm, das Teil ist 39,9 mm breit: 2,45 mm je Seite'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.45 - i * 1.25, { x: RX, width: 5.3, size: 0.25, delay: 0.4 + i * 0.2 }));
  // Maßskizze Backen und Teil, gleich mit den Punkten
  const BX = 4.6;
  const BY = -3.0;
  const s = 0.045;
  const jaw = (x) => api.line(0, [[x, BY + 0.9], [x, BY], [x + 15 * s * (x < BX ? -1 : 1), BY], [x + 15 * s * (x < BX ? -1 : 1), BY + 0.9]], { width: 1.6, hex: T.ink }, { delay: 1.2, dur: 0.4 });
  jaw(BX - (44.8 / 2) * s);
  jaw(BX + (44.8 / 2) * s);
  api.line(0, [[BX - (39.9 / 2) * s, BY + 0.05], [BX + (39.9 / 2) * s, BY + 0.05], [BX + (39.9 / 2) * s, BY + 0.6], [BX - (39.9 / 2) * s, BY + 0.6], [BX - (39.9 / 2) * s, BY + 0.05]], { width: 1.6, hex: T.part }, { delay: 1.3, dur: 0.4 });
  api.text(0, '44,8', { font: 'mono', size: 0.13, anchorX: 'center', anchorY: 'bottom' }, [BX, BY + 0.95], d(1.4));
  api.text(0, '39,9', { font: 'mono', size: 0.13, hex: T.part, anchorX: 'center', anchorY: 'middle' }, [BX, BY + 0.32], d(1.4));
  api.text(0, '2,45 je Seite', { font: 'monoMedium', size: 0.13, hex: T.signal, anchorX: 'right', anchorY: 'middle' }, [BX - (44.8 / 2) * s - 0.75, BY + 0.32], d(1.5));
}

// ---------------------------------------------------------------- 6.14 Greifgenauigkeit vorher → nachher
function sheetAccuracy(api) {
  const lab = { font: 'mono', size: 0.14, hex: T.inkSoft };
  const W = 6.0;
  // items: [Name, streng 0..1, mit Warnung 0..1 | null, Text, Farbe, Notiz]
  const bars = (step, x0, title, sub, items, k) => {
    api.text(step, title, { font: 'sansMedium', size: 0.3, anchorY: 'top' }, [x0, 2.55], { delay: k });
    api.text(step, sub, { ...lab, anchorY: 'top', maxWidth: W + 0.6 }, [x0, 2.12], { delay: k + 0.1 });
    items.forEach(([name, v, vw, txt, hex, note], i) => {
      const y = 1.2 - i * 1.15;
      const kk = k + 0.2 + i * 0.15;
      api.text(step, name, { font: 'monoMedium', size: 0.16, anchorY: 'bottom' }, [x0, y + 0.27], { delay: kk });
      if (vw) {
        const lw = api.line(step, [[x0, y], [x0 + W * vw, y]], { width: 14, hex }, { delay: kk + 0.1, dur: 0.6 });
        lw.opacity = 0.35;
      }
      api.line(step, [[x0, y], [x0 + W * v, y]], { width: 14, hex }, { delay: kk + 0.1, dur: 0.6 });
      api.text(step, txt, { font: 'monoMedium', size: 0.16, hex, anchorX: 'left', anchorY: 'middle' }, [x0 + W * (vw ?? v) + 0.12, y], { delay: kk + 0.4 });
      if (note) api.text(step, note, { ...lab, size: 0.13, anchorY: 'top' }, [x0, y - 0.26], { delay: kk + 0.4 });
    });
  };
  bars(0, X0 + 0.7, 'DAgger', 'Griffe mit Spiel (streng), 15 Lagen, je 1 Fahrt, 26.11.', [
    ['G2 · ohne DAgger', 4 / 15, null, '27 % (4 von 15) · quer 2,3 mm', T.signal],
    ['G2b · DAgger, Übernahme hoch (23.11.)', 10 / 15, null, '67 % (10 von 15) · quer 0,8 mm', T.good, 'in keiner Lage schlechter als G2'],
    ['G2b-D · DAgger, Übernahme spät (25.11.)', 7 / 15, null, '47 % (7 von 15) · quer 1,8 mm', MODULE_COLOR.M4, 'kein Gewinn: späte Korrekturen lehren Nachsetzen'],
  ], 0.1);
  bars(1, 0.6, 'Geplanter Endabstieg', 'G2b, Vergleichsfahrten 24.–26.11. · voll: streng · hell: mit Warnung', [
    ['Policy bis zum Griff', 0.49, null, '49 % streng', T.signal, 'offizielle Bewertung, 37 Fahrten; unten springt die Policy (6.13)'],
    ['Policy bis 10–15 mm, dann senkrecht', 0.73, 0.86, '73 % streng · 86 % mit Warnung', T.good, '53 Fahrten; quer bleibt ~1,1 mm, nur die Drehung wandert unten'],
  ], 0.1);
  api.stamp(1, 'OFFEN', [5.6, 3.5], { size: 0.24, rot: -0.04, hex: T.signal, sub: 'Bewertung prüfen (62 % aus Jeremys Notizen?)' }, { delay: 1.2 });
  api.text(1, 'Zwischenlösung, offen benannt: dauerhaft hilft ein Greifer mit mehr Hub oder ein Sauggreifer. Mit einem Training je Variante und einer Fahrt je Lage liegen ±3 Erfolge von 15 (±20 %) im Rauschen.',
    { font: 'sans', size: 0.2, hex: T.ink, anchorY: 'top', maxWidth: 14.4, lineHeight: 1.3 }, [X0 + 0.7, -2.55], { delay: 1.0 });
  api.text(1, 'Quelle: Berichte/2026-11-26_Vergleich_DAgger/Auswertung.md §1, §3, §4, §12 (hoehen_g2b.csv)', { ...lab, size: 0.13 }, [X0 + 0.7, -3.95], { delay: 1.1 });
}

// ---------------------------------------------------------------- 6.15 Wo greift die Policy gut? (Lagen, Drehung per Regler)
function sheetHeat(api) {
  const h = api.ctx.data.m4.heat;
  const runs = h.runs;
  const xs = [...runs.map((r) => r.x), ...h.train.map((t) => t[0])];
  const ys = [...runs.map((r) => r.y), ...h.train.map((t) => t[1])];
  const [x0, x1, y0, y1] = [Math.min(...xs) - 25, Math.max(...xs) + 25, Math.min(...ys) - 25, Math.max(...ys) + 25];
  const PX0 = X0 + 0.9;
  const PY0 = -2.9;
  const SC = Math.min(8.2 / (x1 - x0), 5.4 / (y1 - y0));
  const P = (x, y) => [PX0 + (x - x0) * SC, PY0 + (y - y0) * SC];
  const lab = { font: 'mono', size: 0.13, hex: T.inkSoft };
  const [a0, a1] = [P(x0, y0), P(x1, y1)];
  api.line(0, [[a0[0], a0[1]], [a1[0], a0[1]], [a1[0], a1[1]], [a0[0], a1[1]], [a0[0], a0[1]]], { width: 1.2, hex: T.inkSoft }, { delay: 0, dur: 0.5 });
  api.text(0, 'Tisch von oben · x/y im Basis-KS des Roboters in mm', { ...lab, anchorY: 'bottom' }, [a0[0], a1[1] + 0.12], { delay: 0.1 });
  const ring = (x, y, r) => Array.from({ length: 17 }, (_, j) => v3(x + r * Math.cos((j / 16) * 2 * Math.PI), y + r * Math.sin((j / 16) * 2 * Math.PI), 0.02));
  h.train.forEach(([x, y], i) => {
    const [px, py] = P(x, y);
    api.line(0, ring(px, py, 0.05).map((p) => [p.x, p.y]), { width: 1.4, hex: T.inkFaint }, { delay: 0.2 + i * 0.005, dur: 0.2 });
  });
  // je Lage (auf 20 mm gerundet) alle Fahrten aller Modelle zusammen; Farbe = Anteil Griffe mit Spiel
  const CL = [['alle Drehungen', -1e9, 1e9], ['bis 90°', -1e9, 90], ['90–110°', 90, 110], ['über 110°', 110, 1e9]];
  const rateHex = (q) => (q >= 0.67 ? T.good : q >= 0.34 ? T.waypoint : T.signal);
  const layers = CL.map(([, lo, hi]) => {
    const g = new Map();
    runs.filter((r) => r.rot >= lo && r.rot < hi).forEach((r) => {
      const key = `${Math.round(r.x / 20)}|${Math.round(r.y / 20)}`;
      const e = g.get(key) ?? { x: 0, y: 0, n: 0, ok: 0 };
      e.x += r.x; e.y += r.y; e.n += 1; e.ok += r.ok ? 1 : 0;
      g.set(key, e);
    });
    const objs = [];
    let n = 0;
    let ok = 0;
    g.forEach((e) => {
      const [px, py] = P(e.x / e.n, e.y / e.n);
      const q = e.ok / e.n;
      n += e.n;
      ok += e.ok;
      const l = new InkLine(ring(px, py, 0.1 + 0.035 * Math.sqrt(e.n)), { width: 3, hex: rateHex(q), progress: 0 });
      api.scene.add(l.object);
      const t = text(`${Math.round(q * 100)} %`, { font: 'monoMedium', size: 0.12, hex: rateHex(q), anchorX: 'center', anchorY: 'top', opacity: 0 });
      t.position.set(px, py - 0.12 - 0.035 * Math.sqrt(e.n), 0.02);
      api.scene.add(t);
      objs.push(l, t);
    });
    const info = text(`${n} Fahrten · ${Math.round((100 * ok) / Math.max(1, n))} % mit Spiel`, { font: 'monoMedium', size: 0.2, hex: T.ink, anchorY: 'top', opacity: 0 });
    info.position.set(1.0, -0.6, 0.01);
    api.scene.add(info);
    return { objs, info };
  });
  const RX = 1.0;
  api.text(0, 'je Lage alle Fahrten aller Modelle · Größe = Zahl der Fahrten', { font: 'mono', size: 0.15, hex: T.ink, anchorY: 'top' }, [RX, 2.5], { delay: 0.3 });
  api.text(0, 'grün ab 67 % mit Spiel · gelb 34–66 % · rot darunter · grau: Trainingslage (19.11.)', { ...lab, size: 0.14, anchorY: 'top' }, [RX, 2.18], { delay: 0.3 });
  const rows = [
    ['Nah am Roboter leicht', 'oben im Bild (y ≈ −24) greifen fast alle Modelle, ab y ≈ −183 (untere Hälfte) deutlich seltener'],
    ['Fern vom Training schlechter', 'wo kaum Trainingslagen liegen, greifen die Modelle öfter daneben (Modelle: G2, G2b, G2c und DAgger-Varianten)'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 1.6 - i * 1.15, { x: RX, width: 5.6, size: 0.24, delay: 0.6 + i * 0.15 }));
  api.text(1, 'Regler unten: Drehklasse wählen (Testfahrten 58–145°)', { ...lab, size: 0.15, anchorY: 'top' }, [RX, -1.25], { delay: 0.2 });
  api.text(0, `${runs.length} Fahrten 24.–26.11., alle Modelle`, { ...lab }, [X0 + 0.7, -3.95], { delay: 0.8 });
  return {
    update(S) {
      const k = S.s1 > 0 && S.rot !== undefined ? Math.min(CL.length - 1, Math.floor((S.rot ?? 0) * CL.length)) : 0;
      layers.forEach((L, i) => {
        const on = i === k ? S.s0 : 0;
        L.objs.forEach((o) => {
          if (o.isObject3D === undefined && o.object) { o.object.visible = on > 0; o.progress = on; } else o.opacity = on;
        });
        L.info.opacity = on;
      });
    },
  };
}

// ---------------------------------------------------------------- 6.16 Stand, offen, weiter
function sheetOutlook(api) {
  const cols = [
    ['STAND', T.good, [
      ['Die Policy greift an der Anlage', 'G2b mit geplantem Endabstieg, 86–91 % (Bewertung offen)'],
      ['Die Pipeline läuft', 'Aufnahme mit Noise Injection, Training, DAgger, Ausführung mit Glättung'],
      ['619 Episoden', 'echte Bilder, automatisch aufgenommen'],
    ]],
    ['OFFEN', T.signal, [
      ['M4 im Gesamtablauf', 'M4 greift, M2 legt ab – in der VM getestet, an der Anlage noch nicht'],
      ['Bewertung der Greifquote', 'streng oder Erfolg + Warnung'],
      ['VM-Läufe, C2 mit DAgger', 'für 6.9 und 6.11, Daten am PC'],
    ]],
    ['WEITER', MODULE_COLOR.M4, [
      ['Greifer', 'mehr Hub oder Sauggreifer statt 2,45 mm Spiel'],
      ['Neuer Datensatz', 'Endanflug 0,02 m/s, Kameralicht, fester Weißabgleich, Start per M1'],
      ['RTC und Licht-Augmentierung', 'glattere Übergänge zwischen Blöcken, robuster gegen Licht'],
      ['Imitation Learning am IKR', 'andere Arme, Greifer und Objekte mit derselben Pipeline'],
    ]],
  ];
  const CW = 4.75;
  cols.forEach(([title, hex, rows], c) => {
    const x = X0 + 0.7 + c * (CW + 0.2);
    api.text(0, title, { font: 'monoMedium', size: 0.2, hex, letterSpacing: 0.08, anchorY: 'top' }, [x, 2.55], { delay: 0.1 + c * 0.3 });
    api.line(0, [[x, 2.15], [x + CW - 0.2, 2.15]], { width: 1.6, hex }, { delay: 0.15 + c * 0.3, dur: 0.4 });
    rows.forEach(([t, b], i) => {
      const y = 1.85 - i * 1.25;
      api.text(0, t, { font: 'sansMedium', size: 0.24, anchorY: 'top', maxWidth: CW - 0.3 }, [x, y], { delay: 0.3 + c * 0.3 + i * 0.1 });
      api.text(0, b, { font: 'sans', size: 0.18, hex: T.inkSoft, anchorY: 'top', maxWidth: CW - 0.3, lineHeight: 1.3 }, [x, y - 0.38], { delay: 0.35 + c * 0.3 + i * 0.1 });
    });
  });
  api.text(0, 'Weiter in Akt 7: Mögliche Verbesserungen (7.4)', { font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 1.2 });
}

// ---------------------------------------------------------------- 6.3 Diffusion Policy erklärt
function sheetDiffusion(api) {
  const pc = api.ctx.data.m4.policy;
  const sim = api.ctx.data.m4.sim;
  const box = (step, x, y, w, h, title, sub, hex, d) => {
    api.line(step, [[x, y], [x + w, y], [x + w, y - h], [x, y - h]], { closed: true, width: 1.4, hex }, d);
    api.text(step, title, { font: 'sansMedium', size: 0.22, anchorY: 'top', maxWidth: w - 0.3 }, [x + 0.15, y - 0.14], d);
    if (sub) api.text(step, sub, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top', maxWidth: w - 0.3, lineHeight: 1.3 }, [x + 0.15, y - 0.48], d);
  };
  const arrow = (step, a, b, d) => {
    api.line(step, [a, b], { width: 1.4 }, d);
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l = Math.hypot(dx, dy);
    const [ux, uy] = [dx / l, dy / l];
    api.line(step, [[b[0] - 0.18 * ux + 0.1 * uy, b[1] - 0.18 * uy - 0.1 * ux], b, [b[0] - 0.18 * ux - 0.1 * uy, b[1] - 0.18 * uy + 0.1 * ux]], { width: 1.4 }, d);
  };
  // Schritt 0: Eingänge → Netz
  const IX = X0 + 0.6;
  const IW = 3.3;
  api.text(0, `EINGANG · LETZTE ${pc.n_obs} TAKTE`, { font: 'mono', size: 0.14, hex: T.inkSoft, letterSpacing: 0.06 }, [IX, 2.5]);
  const inputs = [
    ['Kamera oben', `Bild ${pc.image[0]} × ${pc.image[1]}`, MODULE_COLOR.M1],
    ['Handgelenkkamera', `3,6 mm, F8, ${pc.image[0]} × ${pc.image[1]}`, MODULE_COLOR.M4],
    ['Zustand', '14 Werte: 6 Gelenke, TCP, Greifer', T.inkSoft],
  ];
  inputs.forEach(([t, s, hex], i) => box(0, IX, 2.2 - i * 1.15, IW, 0.95, t, s, hex, { delay: 0.1 + i * 0.12 }));
  const NX = IX + IW + 0.7;
  const NW = 2.4;
  box(0, NX, 2.2, NW, 3.25, 'Diffusion Policy', `U-Net\n${fmt(sim.params_m)} M Param.\nResNet18 je Kamera`, MODULE_COLOR.M4, { delay: 0.5 });
  inputs.forEach((_, i) => arrow(0, [IX + IW + 0.05, 1.72 - i * 1.15], [NX - 0.05, 1.72 - i * 1.15 + (i - 1) * -0.2], { delay: 0.6 }));
  // Feld: ein Gelenk über die nächsten Takte (Schema)
  const FX0 = NX + NW + 0.9;
  const FX1 = -X0 - 0.3;
  const FY0 = -0.95;
  const FY1 = 2.2;
  arrow(0, [NX + NW + 0.05, 0.6], [FX0 - 0.15, 0.6], { delay: 0.7 });
  api.line(0, [[FX0, FY1], [FX0, FY0], [FX1, FY0]], { width: 1.1, hex: T.inkSoft }, { delay: 0.7 });
  api.text(0, `AKTIONSBLOCK · ${pc.horizon} TAKTE (SCHEMA: EIN GELENK)`, { font: 'mono', size: 0.14, hex: T.inkSoft, letterSpacing: 0.06 }, [FX0, 2.5], { delay: 0.7 });
  api.text(0, 'Takt →', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'right', anchorY: 'top' }, [FX1, FY0 - 0.08], { delay: 0.8 });
  const H = pc.horizon;
  const kx = (k) => FX0 + 0.25 + (k / (H - 1)) * (FX1 - FX0 - 0.5);
  const target = Array.from({ length: H }, (_, k) => 0.7 + 0.75 * (1 + Math.tanh((k - 7) / 3.2)));
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
  // Startwerte im Feld halten (über der Achse, unter dem Zähler); Zwischenschritte liegen zwischen Start und Ziel
  const LO = 0.25;
  const HI = FY1 - FY0 - 0.55;
  const noise = target.map((y) => Math.min(HI, Math.max(LO, y + (rnd() + rnd() + rnd()) * 0.6)) - y);
  const dots = target.map(() => {
    const m = new THREE.Mesh(new THREE.CircleGeometry(0.07, 20), new THREE.MeshBasicMaterial({ color: color(MODULE_COLOR.M4), transparent: true, opacity: 0, depthWrite: false }));
    api.scene.add(m);
    return m;
  });
  const curve = new InkLine(target.map((y, k) => v3(kx(k), FY0 + y)), { width: 1.6, hex: MODULE_COLOR.M4, progress: 0 });
  api.scene.add(curve.object);
  const counter = text(' ', { font: 'monoMedium', size: 0.18, hex: MODULE_COLOR.M4, anchorX: 'right', opacity: 0 });
  counter.position.set(FX1, FY1 - 0.05, 0.01);
  api.scene.add(counter);
  let level = 0;
  const place = () => {
    const ys = target.map((y, k) => y + noise[k] * Math.pow(1 - level, 1.3));
    dots.forEach((m, k) => m.position.set(kx(k), FY0 + ys[k], 0.02));
    setPts(curve, ys.map((y, k) => v3(kx(k), FY0 + y, 0.015)));
  };
  api.add(0, (v) => {
    dots.forEach((m) => (m.material.opacity = v));
    curve.progress = v;
    curve.opacity = 0.35 + 0.65 * level;
  }, { delay: 0.9, dur: 0.6 });
  // Schritt 1: Entrauschen in DDIM-Schritten
  let lastCount = '';
  api.add(1, (v) => {
    const p = v * pc.inference_steps;
    const s = Math.min(pc.inference_steps, Math.floor(p));
    const fr = clamp01((p - s) / 0.4);
    level = Math.min(1, (s + fr * fr * (3 - 2 * fr)) / pc.inference_steps);
    place();
    curve.opacity = 0.35 + 0.65 * level;
    const c = v > 0 ? `Entrauschen: Schritt ${Math.min(pc.inference_steps, Math.ceil(p))} / ${pc.inference_steps}` : 'zufälliges Rauschen';
    if (c !== lastCount) {
      counter.text = c;
      lastCount = c;
    }
    counter.opacity = clamp01(v * 8) || dots[0].material.opacity;
  }, { delay: 0, dur: 3.2 });
  api.text(1, `Das Netz sagt in ${pc.inference_steps} Schritten vorher, welches Rauschen weg muss – aus Zufall wird eine glatte Bahn, passend zu Bild und Zustand.`, { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', maxWidth: FX1 - FX0 }, [FX0, FY0 - 0.45], { delay: 0.4 });
  // Schritt 2: die ersten n_action Takte sind nutzbar; alle replan Takte kommt ein neuer Block (Mittel in 6.4)
  api.add(2, (v) => dots.forEach((m, k) => {
    const used = k < pc.n_action;
    m.scale.setScalar(1 + (used ? 0.5 : 0) * v);
    m.material.opacity *= used ? 1 : 1 - 0.65 * v; // Schritt 0 setzt die Deckkraft in jedem Bild neu
  }), { delay: 0, dur: 0.6 });
  const xm = kx(pc.n_action - 0.5);
  api.line(2, [[kx(0), FY1 - 0.5], [xm - 0.05, FY1 - 0.5]], { width: 2.2, hex: MODULE_COLOR.M4 }, { delay: 0.3 });
  api.text(2, `${pc.n_action} Takte nutzbar (≈ ${fmt(pc.n_action / 15, 1)} s)`, { font: 'monoMedium', size: 0.15, hex: MODULE_COLOR.M4, anchorY: 'bottom' }, [kx(0), FY1 - 0.42], { delay: 0.35 });
  api.text(2, `Rest ungenutzt · alle ${pc.replan} Takte ein neuer Block, Überlappungen gemittelt`, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top', maxWidth: FX1 - xm - 0.2 }, [xm + 0.1, FY0 + 0.6], { delay: 0.45 });
  const rows = [
    ['Lernen durch Nachmachen', 'die Policy ahmt die aufgezeichneten Fahrten nach – samt der Korrekturen aus dem Rauschen'],
    ['Takt', `eine Vorhersage dauert ~${sim.predict_ms} ms, länger als ein 15-Hz-Takt – sie läuft deshalb neben dem Servostrom (60 Hz)`],
  ];
  rows.forEach(([t, b], i) => api.row(2, i + 1, t, b, -2.45, { x: IX + i * 7.3, width: 6.2, size: 0.25, delay: 0.6 + i * 0.15 }));
  api.text(2, `Quelle: m4_behavior_cloning/bc/config.py (horizon ${pc.horizon}, n_action_steps ${pc.n_action}, ${pc.inference_steps} DDIM-Schritte), bc/diffusion.py`, { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.9 });
  api.text(2, 'Was steckt in den Kästchen? Ein echter Takt der Anlage.', { font: 'sansMedium', size: 0.24, hex: MODULE_COLOR.M4, anchorX: 'right', anchorY: 'bottom' }, [7.3, -3.7], { delay: 1.2 });
}

// ---------------------------------------------------------------- 6.5 Policy fährt selbst (Simulation)
function sheetSim(api) {
  const s = api.ctx.data.m4.sim;
  const p = api.ctx.data.m4.plant;
  const photo = (step, f, x, y, w, timing) => {
    const c = new PhotoCard(f.url, { width: w, aspect: f.h / f.w, border: 0.05, bottom: 0.05 });
    c.object.position.set(x, y, 0.02);
    c.opacity = 0;
    return api.add(step, c, timing);
  };
  // Schritt 0: Simulation – nur die Höhe des TCP über der Zeit
  const simObjs = [];
  const SW = 8.2;
  simObjs.push(photo(0, s.figure, X0 + 0.7 + SW / 2, 0.75, SW, { delay: 0.1, dur: 0.6 }));
  simObjs.push(api.text(0, 'Simulation (Durchstich 17.09., Platzhalterbilder) · gestrichelt: Sollbahn · grün: 10 Fahrten der Policy', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top', maxWidth: SW }, [X0 + 0.7, -1.4], { delay: 0.3 }));
  simObjs.push(api.text(0, 'Die Fahrten haben die Form der Sollbahn, laufen ihr aber zeitlich hinterher – der Ort stimmt trotzdem.', { font: 'sans', size: 0.22, hex: T.ink, anchorY: 'top', maxWidth: SW }, [X0 + 0.7, -1.95], { delay: 0.5 }));
  const RX = X0 + SW + 1.3;
  const facts = [
    [`${s.success[0]} / ${s.success[1]}`, 'Fahrten erfolgreich', T.good],
    [`${fmt(s.grip_mm[0])}–${fmt(s.grip_mm[1])} mm`, 'vom Greifpunkt entfernt', T.ink],
    [`${fmt(s.path_p95_mm[0])}–${fmt(s.path_p95_mm[1])} mm`, 'neben der Bahn (95 %)', T.ink],
    [`${s.train_min} min`, `Training: ${s.episodes} Episoden, ${s.gpu}`, T.ink],
  ];
  facts.forEach(([big, small, hex], i) => {
    const y = 2.45 - i * 1.25;
    simObjs.push(api.text(0, big, { font: 'title', size: 0.42, hex, anchorY: 'top' }, [RX, y], { delay: 0.6 + i * 0.15 }));
    simObjs.push(api.text(0, small, { font: 'sans', size: 0.18, hex: T.inkSoft, anchorY: 'top', maxWidth: 3.4 }, [RX, y - 0.52], { delay: 0.7 + i * 0.15 }));
  });
  simObjs.push(api.stamp(0, 'SIMULATION', [5.4, 3.5], { size: 0.26, rot: -0.05, hex: MODULE_COLOR.M4 }, { delay: 1.0 }));
  // Schritt 1: an der Anlage, C2 ohne Glättung (16.11.)
  api.fade(1, simObjs, { dur: 0.5 });
  const PW = 6.9;
  const LX = X0 + 0.6 + PW / 2;
  const GX = LX + PW + 0.5;
  const fy = 0.85;
  photo(1, p.figure, LX, fy, PW, { delay: 0.4, dur: 0.6 });
  const fh = (PW * p.figure.h) / p.figure.w;
  const yb = fy - fh / 2 - 0.25;
  const block = (step, x, title, big, lines, hex, k) => {
    api.text(step, title, { font: 'monoMedium', size: 0.16, hex: T.inkSoft, anchorY: 'top' }, [x, yb], { delay: k });
    api.text(step, big, { font: 'title', size: 0.42, hex, anchorY: 'top' }, [x, yb - 0.32], { delay: k + 0.1 });
    api.text(step, lines, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', maxWidth: PW - 0.2, lineHeight: 1.3 }, [x, yb - 0.9], { delay: k + 0.2 });
  };
  const x1 = LX - PW / 2;
  block(1, x1, `16.11. · MODELL C2 · ${p.demos} EPISODEN · OHNE GLÄTTUNG`, `${fmt(p.plant_median_mm)} mm`,
    `Greifpunkt im Median daneben (vorhergesagt), ${p.plant_le10[0]} von ${p.plant_le10[1]} Probegriffen ≤ 10 mm. Bis PRE_PICK folgt die Policy, im Abstieg driftet sie ${p.drift_mm[0]}–${p.drift_mm[1]} mm zur Seite. VM-Replay vorher: ${fmt(p.vm_median_mm)} mm.`, T.signal, 0.7);
  api.stamp(1, 'AN DER ANLAGE', [5.4, 3.5], { size: 0.26, rot: -0.05, hex: T.good }, { delay: 1.0 });
  api.text(1, 'Quelle: Berichte/2026-09-17_Durchstich_Policy, Berichte/2026-11-16_Anlagentest_var_C2, Berichte/2026-11-13_VM-Replay', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.9 });
}

// ---------------------------------------------------------------- 6.7 Takt & Sicherheit
function sheetTiming(api) {
  const tm = api.ctx.data.m4.timing;
  const T0 = X0 + 2.6;
  const END = 230; // gezeigter Ausschnitt in ms
  const MS = (2.9 - T0) / END; // Blatt je ms; rechts bleibt Platz für die Beschriftung
  const tx = (ms) => T0 + ms * MS;
  const lane = (step, y, label, d) => {
    api.text(step, label, { font: 'sansMedium', size: 0.2, anchorX: 'right', anchorY: 'middle' }, [T0 - 0.2, y], d);
    api.line(step, [[T0, y - 0.22], [tx(END), y - 0.22]], { width: 0.8, hex: T.inkSoft }, d);
  };
  const bar = (step, y, a, b, hex, d, h = 0.26) => api.line(step, [[tx(a), y], [tx(Math.min(b, END)), y]], { width: h * 40, hex }, d);
  api.text(0, 'ZEITACHSE IN ms', { font: 'mono', size: 0.14, hex: T.inkSoft, letterSpacing: 0.06 }, [X0 + 0.7, 2.55]);
  [0, 50, 100, 150, 200].forEach((ms) => api.text(0, String(ms), { font: 'mono', size: 0.12, hex: T.inkSoft, anchorX: 'center' }, [tx(ms), 2.55]));
  // Takt 15 Hz
  const Y = [2.0, 1.3, 0.6, -0.1];
  lane(0, Y[0], 'Takt 15 Hz', { delay: 0.1 });
  for (let k = 0; k * tm.cycle_ms < END; k++) {
    const a = tx(k * tm.cycle_ms);
    const b = tx(Math.min(END, (k + 1) * tm.cycle_ms));
    api.line(0, [[a + 0.03, Y[0] - 0.16], [a + 0.03, Y[0] + 0.16], [b - 0.03, Y[0] + 0.16], [b - 0.03, Y[0] - 0.16]], { closed: true, width: 1.4 }, { delay: 0.2 + k * 0.1 });
  }
  api.text(0, `${fmt(tm.cycle_ms)} ms je Takt`, { font: 'monoMedium', size: 0.15, anchorX: 'center', anchorY: 'middle' }, [tx(tm.cycle_ms / 2), Y[0]], { delay: 0.4 });
  // Servostrom 60 Hz mit Aufrufzeit
  lane(0, Y[1], 'servo_j 60 Hz', { delay: 0.3 });
  for (let k = 0; k * tm.servo_ms < END - 5; k++) bar(0, Y[1], k * tm.servo_ms, k * tm.servo_ms + (k === 5 ? tm.rpc_p95_ms : tm.rpc_median_ms), k === 5 ? T.inkSoft : MODULE_COLOR.M2, { delay: 0.4 + k * 0.04 });
  api.text(0, `Aufruf ~${tm.rpc_median_ms} ms, selten ${tm.rpc_p95_ms} ms`, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'middle' }, [tx(END) + 0.2, Y[1]], { delay: 0.8 });
  // Vorhersage
  lane(0, Y[2], 'Vorhersage', { delay: 0.5 });
  for (let k = 0; k * tm.predict_ms < END; k++) bar(0, Y[2], k * tm.predict_ms + 2, (k + 1) * tm.predict_ms - 2, MODULE_COLOR.M4, { delay: 0.6 + k * 0.12 });
  api.text(0, `~${tm.predict_ms} ms > Takt → asynchron`, { font: 'mono', size: 0.14, hex: MODULE_COLOR.M4, anchorY: 'middle' }, [tx(END) + 0.2, Y[2]], { delay: 1.0 });
  // Hänger
  lane(0, Y[3], 'Hänger', { delay: 0.7 });
  bar(0, Y[3], 15, 15 + tm.hang_ms, T.signal, { delay: 0.9, dur: 0.8 });
  api.text(0, `~${tm.hang_ms} ms, 1–2× je Lauf`, { font: 'mono', size: 0.14, hex: T.signal, anchorY: 'middle' }, [tx(END) + 0.2, Y[3]], { delay: 1.2 });
  // Schritt 1: Schutzschichten
  const rows = [
    ['ServoGuard (hart)', 'lehnt jeden Sollwert ab, der ein Gelenk schneller als 1,0 rad/s bewegen würde'],
    ['TargetLimiter (weich)', 'kappt Vorhersagen auf 0,8 rad/s, bevor der ServoGuard eingreift'],
    ['Zielabstand', 'Ziel mehr als 0,35 rad neben der Ist-Stellung → Fahrt endet'],
    ['Zielprüfung mit Nachlauf', 'Ziel und Ziel + 1 Takt gegen Tisch, Hindernisse und Hülle der Demos – bevor gesendet wird'],
    ['Geofence + Software-Stopp', 'Watchdog prüft alle 50 ms die gemessene Stellung, hält in ~100 ms'],
    ['Bild zu alt, Arm steht', 'Bild > 100 ms alt oder Arm steht trotz Ziel → Fahrt endet (der Not-Halt wurde sonst nicht bemerkt)'],
  ];
  rows.forEach(([t, b], i) => api.row(1, i + 1, t, b, -0.75 - Math.floor(i / 2) * 1.05, { x: X0 + 0.7 + (i % 2) * 7.3, width: 6.2, size: 0.24, delay: 0.1 + i * 0.1 }));
  api.stamp(1, 'IN DER VM AUSGELÖST', [5.4, 3.5], { size: 0.24, rot: -0.04, hex: MODULE_COLOR.M4, sub: 'jede Schicht hat in den VM-Läufen korrekt gestoppt' }, { delay: 0.7 });
  api.text(1, 'Quelle: Labortag-2026-10-16-Uebergabe.md, Berichte/2026-09-17_Durchstich_Policy.pdf, bc/servo.py, bc/safety.py', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.9 });
}

// ---------------------------------------------------------------- 6.6 Das Zittern (M4 an der Anlage)
function sheetJitter(api) {
  const m4 = api.ctx.data.m4;
  // Schritt 0: links die Treppe – 60-Hz-Sollwerte, die Steuerung fährt jeden an und wartet auf den nächsten
  const L = { x0: X0 + 0.7, x1: -1.0, y0: -1.5, y1: 1.7 };
  api.text(0, 'SOLLWERT ÜBER DER ZEIT (SCHEMA)', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [L.x0, 2.45]);
  api.line(0, [[L.x0, L.y1 + 0.3], [L.x0, L.y0], [L.x1, L.y0]], { width: 1.2, hex: T.inkSoft }, { delay: 0.1 });
  const s = (u) => u * u * (3 - 2 * u);
  const X = (u) => L.x0 + 0.15 + u * (L.x1 - L.x0 - 0.3);
  const Y = (u) => L.y0 + 0.15 + s(u) * (L.y1 - L.y0 - 0.3);
  const N = 9;
  api.line(0, Array.from({ length: 41 }, (_, i) => [X(i / 40), Y(i / 40)]), { width: 1.4, dashed: true, dash: 0.08, gap: 0.06, hex: T.inkSoft }, { delay: 0.2, dur: 0.8 });
  const stairs = [];
  for (let k = 0; k < N; k++) stairs.push([X(k / N), Y(k / N)], [X(k / N) + 0.12, Y((k + 1) / N)], [X((k + 1) / N), Y((k + 1) / N)]);
  api.line(0, stairs, { width: 2.2, hex: MODULE_COLOR.M4 }, { delay: 0.5, dur: 1.2 });
  // Legende oben links (dort ist die Kurve noch flach): gestrichelt = gewünscht, orange = was der Arm tut
  const LX = L.x0 + 0.35;
  api.line(0, [[LX, 1.75], [LX + 0.6, 1.75]], { width: 1.4, dashed: true, dash: 0.08, gap: 0.06, hex: T.inkSoft }, { delay: 0.6 });
  api.text(0, 'Sollbahn: so soll der Arm fahren', { font: 'mono', size: 0.15, hex: T.inkSoft, anchorY: 'middle' }, [LX + 0.8, 1.75], { delay: 0.6 });
  api.line(0, [[LX, 1.35], [LX + 0.6, 1.35]], { width: 2.2, hex: MODULE_COLOR.M4 }, { delay: 1.2 });
  api.text(0, 'Ist: anfahren, warten, anfahren …', { font: 'mono', size: 0.15, hex: MODULE_COLOR.M4, anchorY: 'middle' }, [LX + 0.8, 1.35], { delay: 1.2 });
  const rows = [
    ['Wir senden 60 Sollwerte je Sekunde', 'servo_j, Gelenkwinkel alle 16,7 ms'],
    ['Die Steuerung rechnet mit 1 kHz', 'sie erreicht jeden Sollwert und wartet – eine Treppe statt einer Bahn'],
    ['Arm und Aufbau schwingen mit', 'Eigenfrequenz 5,6–6,2 Hz, das Teil rutscht – in der VM nicht zu sehen'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, -1.85 - i * 0.68, { x: L.x0 - 0.1, width: 6.8, size: 0.24, delay: 0.9 + i * 0.15 }));
  // Schritt 1: rechts gemessen – Zittern am Unterarm je Ausführungsart, gewählt: servo_j mit Override 0,5
  const RX = 0.9;
  api.text(1, 'ZITTERN AM UNTERARM (ACHSE 5) · RMS IN m/s²', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [RX, 2.45]);
  const max = Math.max(...m4.jitter.map((j) => j.hi));
  const BX = RX + 3.6;
  const BW = 2.4;
  m4.jitter.forEach((j, i) => {
    const y = 1.75 - i * 0.62;
    const d = { delay: 0.1 + i * 0.12 };
    const hex = j.chosen ? MODULE_COLOR.M4 : i === 0 ? T.signal : T.inkSoft;
    api.text(1, j.name, { font: j.chosen ? 'sansMedium' : 'sans', size: 0.2, anchorY: 'middle' }, [RX, y], d);
    api.line(1, [[BX, y], [BX + (j.hi / max) * BW, y]], { width: 9, hex }, d);
    const v = j.lo === j.hi ? fmt(j.lo, 2) : `${fmt(j.lo, 2)}–${fmt(j.hi, 2)}`;
    api.text(1, v, { font: 'monoMedium', size: 0.19, hex, anchorY: 'middle' }, [BX + (j.hi / max) * BW + 0.15, y], { delay: d.delay + 0.1 });
  });
  api.stamp(1, 'ENTSCHIEDEN', [RX + 3.4, -1.75], { size: 0.3, rot: -0.04, hex: MODULE_COLOR.M4, sub: 'servo_j mit Override 0,5 · so ruhig wie Neura · Bahn bis 1,2 mm genau' }, { delay: 0.8 });
  api.text(1, 'online war ebenso ruhig, lief aber bis 1,3 s hinterher und kehrte 27 mm über PICK um.', { font: 'sans', size: 0.19, hex: T.inkSoft, anchorY: 'top', maxWidth: 6.4, lineHeight: 1.3 }, [RX, -2.55], { delay: 1.0 });
  api.text(1, 'Quelle: m4_behavior_cloning/Dokumentation/Zittern-an-der-Anlage.md, Labortag-2026-10-16-Uebergabe.md (13.–19.10.)', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 1.1 });
}

// ---------------------------------------------------------------- A.5 Labortag
function sheet71(api) {
  const lab = api.ctx.data.lab;
  const w = lab.workspace_to_robot.after;
  const rows = [
    ['Posen geteacht', 'Prüfplatz und Ablagen direkt am Roboter angefahren und übernommen'],
    ['Arbeitsraum → Roboter kalibriert', `Drehung ${fmt(w.rotation_deg, 2)}°, Verschiebung ${w.translation_mm.map((v) => fmt(v)).join(' / ')} mm, Tisch z ${fmt(w.table_z_mm)} mm`],
    ['Greifer 23° verdreht montiert', `Offset 90° → 113°, Werkzeug ${lab.tool.after} statt ${lab.tool.before}`],
    ['Erster vollständiger Ablauf', 'im Automatikbetrieb – ehrlich: noch ohne Greiferansteuerung und ohne Arbeitsraumkamera, M1/M3 mit Testbildern'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.3 - i * 1.5, { x: X0 + 0.7, width: 6.4, size: 0.3, delay: 0.1 + i * 0.15 }));
  api.text(0, `Quelle: system.yaml vor/nach Commit ${lab.commit} (${lab.date.split('-').reverse().join('.')})`, { font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, -3.85], { delay: 1.0 });
}

// Pfeil als drei Tuschestriche (Schaft + Spitze)
function arrow(api, step, [x0, y0], [x1, y1], opts, timing) {
  const a = Math.atan2(y1 - y0, x1 - x0);
  const len = Math.hypot(x1 - x0, y1 - y0);
  const h = Math.min(0.13, len * 0.45);
  const head = (s) => [x1 - h * Math.cos(a + s * 0.45), y1 - h * Math.sin(a + s * 0.45)];
  return [api.line(step, [[x0, y0], [x1, y1]], opts, timing), api.line(step, [head(1), [x1, y1], head(-1)], opts, timing)];
}
const dot = (api, step, [x, y], r, opts, timing) =>
  api.line(step, Array.from({ length: 13 }, (_, i) => [x + r * Math.cos((i / 12) * 2 * Math.PI), y + r * Math.sin((i / 12) * 2 * Math.PI)]), opts, timing);
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

// ---------------------------------------------------------------- 3.6 Positionskorrektur
function sheet36(api) {
  const L = api.ctx.data.lab2;
  if (!L) return;
  const WS = Array.isArray(L.workspace_mm) ? L.workspace_mm[0] : L.workspace_mm;
  // Arbeitsraum als Quadrat links, x nach rechts, y nach oben (Arbeitsraum-KS)
  const SQ = 5.9, OX = X0 + 0.9, OY = -3.75, k = SQ / WS;
  const P = (x, y) => [OX + x * k, OY + y * k];
  const AK = 0.075; // Pfeillänge je mm Versatz
  api.line(0, [P(0, 0), P(WS, 0), P(WS, WS), P(0, WS), P(0, 0)], { width: 1.6 }, { delay: 0.05 });
  api.text(0, `Arbeitsraum ${fmt(WS, 0)} × ${fmt(WS, 0)} mm (Draufsicht)`, { font: 'mono', size: 0.14, hex: T.inkSoft }, [OX, OY + SQ + 0.32], { delay: 0.1 });
  const c = L.correction;
  if (c) {
    const [cx, cy] = P(...c.center_mm);
    api.line(0, [[cx - 0.14, cy], [cx + 0.14, cy]], { width: 1.2, hex: T.inkSoft }, { delay: 0.2 });
    api.line(0, [[cx, cy - 0.14], [cx, cy + 0.14]], { width: 1.2, hex: T.inkSoft }, { delay: 0.2 });
  }
  // Schritt 0: ohne Korrektur – Pfeil zeigt, wohin die erkannte Mitte gegenüber der echten verschoben ist
  const before = [];
  L.points_before.forEach((p, i) => {
    const s = P(p.x, p.y);
    const timing = { delay: 0.3 + i * 0.04, dur: 0.4 };
    before.push(dot(api, 0, s, 0.05, { width: 1.4, hex: T.ink }, timing));
    if (p.dx || p.dy) before.push(...arrow(api, 0, s, [s[0] - p.dx * AK, s[1] - p.dy * AK], { width: 2.2, hex: T.signal }, timing));
  });
  api.text(0, 'Pfeil: erkannte Mitte gegenüber der echten, 7,5-fach vergrößert', { font: 'mono', size: 0.13, hex: T.inkSoft }, [OX, OY - 0.28], { delay: 1.2 });
  const n = L.points_before.length, maxX = Math.max(...L.points_before.map((p) => Math.abs(p.dx))), maxY = Math.max(...L.points_before.map((p) => Math.abs(p.dy)));
  const RX = 0.6;
  api.row(0, 1, 'Ohne Korrektur: Versatz wächst nach außen', `${n} Zeigetests: bis ${fmt(maxX, 0)} mm in x, bis ${fmt(maxY, 0)} mm in y. Die 15 mm hohe Oberseite liegt über der entzerrten Tischebene (Parallaxe), dazu das unkorrigierte Objektiv.`, 2.6, { x: RX, width: 6.6, size: 0.3, delay: 0.4 });
  if (c) {
    const pct = (v) => `${fmt(v * 100, 1)} %`;
    api.row(0, 2, 'Lineares Modell je Achse', `x' = x − ${pct(c.scale[0])} · (x − ${fmt(c.center_mm[0], 0)} mm)\ny' = y − ${pct(c.scale[1])} · (y − ${fmt(c.center_mm[1], 0)} mm)\nRestfehler des Modells 0,5 mm (x) / 1,2 mm (y)`, 0.75, { x: RX, width: 6.6, size: 0.3, delay: 0.9 });
  }
  // Schritt 1: mit Korrektur
  api.fade(1, before, { dur: 0.5 });
  const after = L.points_after;
  after.forEach((p, i) => {
    const s = P(p.x, p.y);
    const off = p.dx || p.dy;
    const timing = { delay: 0.4 + i * 0.05, dur: 0.4 };
    dot(api, 1, s, 0.07, { width: 2.2, hex: off ? T.signal : T.good }, timing);
    if (off) arrow(api, 1, s, [s[0] - p.dx * AK, s[1] - p.dy * AK], { width: 2.2, hex: T.signal }, timing);
  });
  const zero = after.filter((p) => !p.dx && !p.dy).length;
  const worst = Math.max(...after.map((p) => Math.hypot(p.dx, p.dy)));
  api.row(1, 3, 'Mit Korrektur', `${zero} von ${after.length} Kontrollmessungen ohne sichtbaren Versatz, sonst höchstens ${fmt(worst, 0)} mm. Gegriffen hätte der Greifer überall, in den Ecken knapp.`, -1.4, { x: RX, width: 6.6, size: 0.3, delay: 0.5 });
  api.stamp(1, `HÖCHSTENS ${fmt(worst, 0)} mm`, [RX + 3.4, -3.35], { size: 0.32, rot: -0.04, hex: T.good, sub: 'gilt nur für diese Kameraposition' }, { delay: 1.0 });
}

// ---------------------------------------------------------------- A.6 Labortag 12.11.
function sheet72(api) {
  const L = api.ctx.data.lab2;
  if (!L) return;
  const rows = [
    ['Kameras live, fest eingestellt', `Kamera oben: Belichtung ${fmt((L.exposure_us ?? 15000) / 1000, 0)} ms statt Automatik (Teil war übersteuert). Seitenkamera: Fokus fest ${L.focus ?? 90}, im Programm gesetzt.`],
    ['Greifer im Ablauf', 'über die Digitalausgänge der Steuerung: auf, zu, Freigabe, Reset'],
    ['Zeigetests', 'Versatz bis 8 mm am Rand → lineare Positionskorrektur (3.6)'],
    ['Teil gedreht greifen', 'Seriennummer und Fase zeigen zur Seitenkamera; Offset −67°'],
    ['Veraltete Bilder', 'beide Kameras gaben nach einer Pause ein altes Bild aus dem Puffer – jetzt wird er vor jeder Aufnahme geleert'],
    ['Sanft ablegen', 'Greifer öffnet 1 mm über der geteachten Pose, sonst fällt das Teil auf die Prüfung'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.7 - i * 1.08, { x: X0 + 0.7, width: 6.3, size: 0.27, delay: 0.1 + i * 0.1 }));
  const ph = L.photos ?? {};
  const pick = [['anlage', 2.75, 0.3, 3.4, 0.04], ['vorrichtung', 5.75, 1.45, 3.1, -0.05], ['handgelenk', 5.6, -1.85, 2.4, 0.06]];
  pick.forEach(([name, x, y, w, rot], i) => {
    const f = ph[name];
    if (!f) return;
    const card = new PhotoCard(f.url, { width: w, aspect: f.h / f.w });
    card.object.position.set(x, y, 0.05 + i * 0.05);
    card.object.rotation.z = rot;
    card.opacity = 0;
    api.add(1, card, { delay: i * 0.2, dur: 0.6 });
  });
  api.stamp(1, 'ERSTER ZYKLUS MIT KAMERAS', [X0 + 3.6, -4.0], { size: 0.26, rot: -0.03, hex: MODULE_COLOR.M2 }, { delay: 0.9 });
}

// ---------------------------------------------------------------- A.7 Messwerte 12.11.
function sheet73m(api) {
  const L = api.ctx.data.lab2;
  if (!L) return;
  const cy = L.cycles;
  const full = cy.filter((c) => c.ok);
  const good = full.filter((c) => c.good).length;
  const readOk = full.filter((c) => c.serial && c.notch).length;
  const dur = median(full.map((c) => c.duration_s));
  const after = L.points_after;
  const worst = Math.max(...after.map((p) => Math.hypot(p.dx, p.dy)));
  const maxBefore = Math.max(...L.points_before.map((p) => Math.hypot(p.dx, p.dy)));
  const figs = [
    [`${cy.length} / ${cy.length}`, 'gegriffen und an der\nPrüfung abgelegt', T.ink],
    [`${readOk} / ${full.length}`, 'Seriennummer und Kerbe\nrichtig erkannt', T.ink],
    [`${good} / ${full.length}`, 'als Gutteil sortiert\n(Rest: Loch zu klein)', T.signal],
    [`${fmt(worst, 0)} mm`, `Versatz im Zeigetest mit\nKorrektur (ohne: ${fmt(maxBefore, 0)} mm)`, T.good],
    [`${fmt(dur, 0)} s`, 'Zykluszeit (Median),\nbewusst langsam', T.ink],
  ];
  figs.forEach(([big, small, hex], i) => {
    const x = X0 + 0.7 + i * 3.0;
    api.text(0, big, { font: 'title', size: 0.58, hex }, [x, 2.15], { delay: 0.1 + i * 0.12 });
    api.text(0, small, { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', lineHeight: 1.3 }, [x, 1.6], { delay: 0.18 + i * 0.12 });
  });
  api.text(0, `${cy.length} Zyklen am ${L.date.split('-').reverse().join('.')} mit dem Gutteil · die ersten zwei brachen bei der Prüfung ab (veraltetes Bild, danach behoben)`, { font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, 0.55], { delay: 0.8 });
  // Schritt 1: Lochdurchmesser gegen die Toleranz
  const nom = L.hole_nominal_mm, tol = L.hole_tolerance_mm;
  const A0 = 9.3, A1 = 10.6, AX = X0 + 0.9, AW = 7.6, AY = -1.9;
  const X = (v) => AX + ((v - A0) / (A1 - A0)) * AW;
  api.text(1, 'LOCHDURCHMESSER JE ZYKLUS (mm)', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [AX, -0.35], { delay: 0.05 });
  api.line(1, [[X(nom - tol), AY], [X(nom + tol), AY]], { width: 26, hex: '#D6EBD8' }, { delay: 0.1 });
  api.line(1, [[X(A0), AY - 0.45], [X(A1), AY - 0.45]], { width: 1.2 }, { delay: 0.1 });
  [9.4, 9.6, 9.8, 10.0, 10.2, 10.4].forEach((v) => {
    api.line(1, [[X(v), AY - 0.52], [X(v), AY - 0.38]], { width: 1.2 }, { delay: 0.15 });
    api.text(1, fmt(v, 1), { font: 'mono', size: 0.15, anchorX: 'center', anchorY: 'top' }, [X(v), AY - 0.62], { delay: 0.15 });
  });
  api.text(1, `Toleranz ${fmt(nom, 0)} ± ${fmt(tol, 1)} mm`, { font: 'sans', size: 0.18, hex: T.good, anchorX: 'center' }, [X(nom), AY + 0.35], { delay: 0.2 });
  full.forEach((c, i) => {
    const y = AY + 0.18 - (i % 3) * 0.17;
    dot(api, 1, [X(c.hole_mm), y], 0.07, { width: 2.6, hex: c.good ? T.good : T.signal }, { delay: 0.3 + i * 0.1, dur: 0.3 });
  });
  const holes = full.map((c) => c.hole_mm);
  const lo = Math.min(...holes), hi = Math.max(...holes);
  api.text(1, `Alle ${holes.length} Messungen ${fmt(lo, 2)}–${fmt(hi, 2)} mm: gut wiederholbar, aber rund ${fmt((1 - (lo + hi) / 2 / nom) * 100, 0)} % zu klein – drei liegen knapp unter der Grenze.`, { font: 'sans', size: 0.21, anchorY: 'top', maxWidth: 7.6, lineHeight: 1.3 }, [AX, AY - 1.05], { delay: 0.8 });
  const f = L.photos?.m3_live;
  if (f) {
    const card = new PhotoCard(f.url, { width: 5.6, aspect: f.h / f.w });
    card.object.position.set(4.6, -1.75, 0.05);
    card.object.rotation.z = -0.03;
    card.opacity = 0;
    api.add(1, card, { delay: 0.4, dur: 0.6 });
  }
  api.stamp(1, 'SPIEGELUNG IM LOCH', [2.2, -3.95], { size: 0.26, rot: 0.04, hex: T.signal, sub: 'Fensterlicht · gelöst am 26.11. (5.9)' }, { delay: 1.0 });
}

// Fotokarte, die mit dem Schritt einblendet
function card(api, step, f, [x, y], width, rot = 0, timing = {}) {
  if (!f) return null;
  const c = new PhotoCard(f.url, { width, aspect: f.h / f.w });
  c.object.position.set(x, y, 0.05);
  c.object.rotation.z = rot;
  c.opacity = 0;
  return api.add(step, c, { dur: 0.6, ...timing });
}

// ---------------------------------------------------------------- A.8 Labortag 26.11.
function sheet74lab(api) {
  const L = api.ctx.data.lab3;
  if (!L) return;
  const cy = L.cycles;
  const empty = cy.filter((c) => c.ok && !c.part).length;
  const full = cy.filter((c) => c.hole_mm != null);
  const fast = full.map((c) => c.duration_s).filter((d) => d > 30 && d < 50);
  const markers = cy.filter((c) => /ArUco/.test(c.error)).length;
  const rows = [
    ['Dauerbetrieb', `Das System wartet selbst auf das nächste Teil: ${empty} Abfragen ohne Teil, keine startete einen Zyklus.`],
    [`${full.length} Zyklen mit Prüfung`, 'jedes Mal erkannt, gegriffen, geprüft und einsortiert – mit echten Kameras und Greifer'],
    [`${fmt(median(fast), 0)} s je Zyklus`, `Median im Dauerbetrieb (${fmt(Math.min(...fast), 0)}–${fmt(Math.max(...fast), 0)} s), Geschwindigkeit im Lauf des Tages angepasst`],
    ['Lochmessung neu', 'Spiegelung im Loch nicht mehr kompensiert per Faktor, sondern im Kreis-Fit (5.9)'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.75 - i * 1.4, { x: X0 + 0.7, width: 6.2, size: 0.3, delay: 0.1 + i * 0.12 }));
  const gui = card(api, 0, L.photos?.gui, [3.95, 0.55], 7.4, -0.02, { delay: 0.3 });
  const guiCap = api.text(0, 'Bedienoberfläche nach einem Zyklus am Aufbau: alle Schritte grün, Urteil GUTTEIL', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'center' }, [3.95, -2.05], { delay: 0.6 });
  // Schritt 1: was im Dauerbetrieb schiefging und was daraus wurde
  api.fade(1, gui ? [gui, guiCap] : [guiCap], { dur: 0.4 });
  api.text(1, 'WAS DER DAUERBETRIEB GEZEIGT HAT', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [0.65, 2.75], { delay: 0.3 });
  card(api, 1, L.photos?.hand, [2.35, 1.0], 3.3, 0.025, { delay: 0.4 });
  card(api, 1, L.photos?.rueckseite, [6.0, 1.6], 3.6, -0.03, { delay: 0.6 });
  const cap = { font: 'sans', size: 0.19, hex: T.inkSoft, anchorY: 'top', maxWidth: 3.4, lineHeight: 1.3 };
  const head = { font: 'sansMedium', size: 0.22, anchorY: 'top', maxWidth: 3.4 };
  api.text(1, 'Hand als Teil erkannt', head, [0.7, -0.5], { delay: 0.7 });
  api.text(1, `Roboter per Software-Stopp angehalten. Neu: Form- und Ruheprüfung. Verdeckter Marker beim Nachlegen (${markers}x): sauberer Abbruch.`, cap, [0.7, -0.85], { delay: 0.75 });
  api.text(1, 'Teil kopfüber eingelegt', head, [4.25, 0.6], { delay: 0.9 });
  api.text(1, 'Rückseite ohne Etikett und Kerbe, richtig als SCHLECHT. Neu: die Fase verrät die Lage, Abbruch vor dem Greifen.', cap, [4.25, 0.25], { delay: 0.95 });
  api.stamp(1, 'KEIN TEIL FALSCH SORTIERT', [4.4, -3.2], { size: 0.28, rot: -0.04, hex: T.good, sub: 'jeder Fehlerfall wurde zu einer neuen Prüfung' }, { delay: 1.1 });
  api.text(1, 'Quelle: logs/cycles_20261126.csv, logs/20261126/ (Zwischenbilder aller Läufe)', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 1.2 });
}

// ---------------------------------------------------------------- 5.9 Lochmessung gelöst
function sheet75(api) {
  const L = api.ctx.data.lab3;
  if (!L) return;
  const nom = L.hole_nominal_mm, tol = L.hole_tolerance_mm;
  const rows = [
    ['Spiegelung schneidet das Loch an', 'Die helle Bohrungswand sieht aus wie die Seitenfläche – die Kontur läuft unten nach innen, der Ellipsen-Fit wird zu klein.'],
    ['Fehler wirkt nur in eine Richtung', 'Er kann die Kontur nur verkleinern. Also: Punkte deutlich innerhalb des Kreises verwerfen, Kreis neu anpassen.'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.75 - i * 1.55, { x: X0 + 0.7, width: 6.3, size: 0.3, delay: 0.1 + i * 0.15 }));
  card(api, 0, L.photos?.fit, [4.2, 0.95], 6.9, -0.015, { delay: 0.3 });
  // Schritt 1: alle Prüfbilder des Tages mit beiden Verfahren nachgerechnet
  const R = L.reeval;
  const right = R.filter((r) => !r.upside_down);
  const inTol = (v) => Math.abs(v - nom) <= tol;
  const A0 = 9.3, A1 = 10.1, CX0 = X0 + 1.3, CX1 = 0.9, CY0 = -3.35, CY1 = -0.25;
  const Y = (v) => CY0 + ((v - A0) / (A1 - A0)) * (CY1 - CY0);
  const X = (i) => CX0 + ((i + 0.5) / R.length) * (CX1 - CX0);
  api.text(1, 'LOCHDURCHMESSER ALLER PRÜFBILDER VOM 26.11. (mm)', { font: 'mono', size: 0.14, hex: T.inkSoft, letterSpacing: 0.05 }, [CX0 - 0.6, CY1 + 0.3], { delay: 0.05 });
  api.line(1, [[CX0, (Y(nom - tol) + Y(A1)) / 2], [CX1, (Y(nom - tol) + Y(A1)) / 2]], { width: 112, hex: '#D6EBD8' }, { delay: 0.1 });
  api.line(1, [[CX0, Y(nom - tol)], [CX1, Y(nom - tol)]], { width: 1.4, hex: T.good }, { delay: 0.1 });
  api.text(1, `untere Grenze ${fmt(nom - tol, 1)}`, { font: 'mono', size: 0.13, hex: T.good, anchorX: 'right', anchorY: 'bottom' }, [CX1, Y(nom - tol) + 0.05], { delay: 0.2 });
  api.line(1, [[CX0 - 0.1, CY0], [CX0 - 0.1, CY1]], { width: 1.2 }, { delay: 0.1 });
  [9.4, 9.6, 9.8, 10.0].forEach((v) => {
    api.line(1, [[CX0 - 0.18, Y(v)], [CX0 - 0.1, Y(v)]], { width: 1.2 }, { delay: 0.15 });
    api.text(1, fmt(v, 1), { font: 'mono', size: 0.14, anchorX: 'right', anchorY: 'middle' }, [CX0 - 0.24, Y(v)], { delay: 0.15 });
  });
  R.forEach((r, i) => {
    const t = { delay: 0.3 + i * 0.04, dur: 0.3 };
    dot(api, 1, [X(i), Y(r.ellipse)], 0.07, { width: 2.2, hex: T.signal }, t);
    dot(api, 1, [X(i), Y(r.circle)], 0.07, { width: 3.2, hex: r.upside_down ? T.inkSoft : T.good }, { ...t, delay: t.delay + 0.5 });
  });
  api.text(1, 'Ellipse (bisher)', { font: 'sansMedium', size: 0.18, hex: T.signal }, [CX0 + 0.1, Y(9.36)], { delay: 0.9 });
  api.text(1, 'Kreis-Fit (neu)', { font: 'sansMedium', size: 0.18, hex: T.good }, [CX0 + 0.1, Y(9.92)], { delay: 1.1 });
  // Kennzahlen unter dem Bild
  const ell = right.filter((r) => inTol(r.ellipse)).length, cir = right.filter((r) => inTol(r.circle)).length;
  const c = right.map((r) => r.circle);
  const m = c.reduce((a, b) => a + b, 0) / c.length;
  const sd = Math.sqrt(c.reduce((a, b) => a + (b - m) ** 2, 0) / (c.length - 1));
  const cyc = L.cycles.filter((x) => x.hole_mm != null && x.serial && x.time >= '10:20');
  const figs = [
    [`${cir} / ${right.length}`, `Prüfbilder in Toleranz\n(mit Ellipse: ${ell} / ${right.length})`, T.good],
    [`${cyc.filter((x) => x.good).length} / ${cyc.length}`, 'Gutteile im Betrieb\nals GUT sortiert', T.good],
    [`± ${fmt(sd, 2)} mm`, `Streuung, Mittel ${fmt(m, 2)} mm\n(Rest ~${fmt((1 - m / nom) * 100, 1)} % unter Soll)`, T.ink],
  ];
  figs.forEach(([big, small, hex], i) => {
    const x = 1.75 + i * 2.35;
    api.text(1, big, { font: 'title', size: 0.42, hex }, [x, -1.35], { delay: 1.0 + i * 0.12 });
    api.text(1, small, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', lineHeight: 1.3 }, [x, -1.75], { delay: 1.05 + i * 0.12 });
  });
  api.stamp(1, 'GELÖST IM ALGORITHMUS', [4.3, -3.35], { size: 0.27, rot: -0.04, hex: T.good, sub: 'die Ursache bleibt: Prüfstation gegen Fensterlicht abschirmen' }, { delay: 1.4 });
  api.text(1, 'grau: Teil kopfüber, Rückseite geprüft · gleiche Kontur, nur das Verfahren unterscheidet sich', { font: 'mono', size: 0.12, hex: T.inkSoft }, [CX0 - 0.6, CY0 - 0.42], { delay: 1.2 });
}

// ---------------------------------------------------------------- 7.4 Mögliche Verbesserungen
function sheet74(api) {
  const aufbau = [
    ['Sauggreifer', 'fasst das Teil von oben, unabhängig vom Winkel – kein knappes Backenspiel am 40 mm breiten Teil'],
    ['Prüfvorrichtung mit Anschlag', 'das Teil liegt formschlüssig und immer gleich vor der Seitenkamera'],
    ['Licht abschirmen', 'Einhausung und eigene Beleuchtung an der Prüfstation statt Ausgleich im Algorithmus'],
  ];
  const software = [
    ['Kalibrierte Kamera', 'intrinsische Kalibrierung und Entzerrung auf Bauteilhöhe statt empirischer Korrektur'],
    ['M4 mit Daten der Anlage', 'Policy mit Aufnahmen vom echten Aufbau trainieren statt nur in der Simulation'],
    ['Echte Fehlerteile', 'gezielt gefertigte Teile ohne Kerbe, mit falschem Loch, ohne Etikett; wechselndes Licht'],
  ];
  const col = (step, items, x, n0, label) => {
    api.stamp(step, label, [x + 1.2, 2.4], { size: 0.26, rot: -0.04, hex: T.ink }, { delay: 0.05 });
    items.forEach(([ti, b], i) => api.row(step, n0 + i, ti, b, 1.65 - i * 1.4, { x, width: 6.0, size: 0.28, delay: 0.15 + i * 0.12 }));
  };
  col(0, aufbau, X0 + 0.7, 1, 'AUFBAU');
  col(1, software, 0.9, aufbau.length + 1, 'SOFTWARE & TEST');
}

// ---------------------------------------------------------------- A.1 Konfiguration
function sheetA1(api) {
  const cfg = api.ctx.data.config;
  const r = cfg.robot;
  const w2r = cfg.workspace_to_robot;
  api.text(0, 'POSEN (TCP IM ROBOTER-BASIS-KS, mm / °)', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [X0 + 0.7, 2.55]);
  Object.entries(r.poses).forEach(([name, p], i) => {
    const y = 2.0 - i * 0.48;
    api.text(0, name, { font: 'sansMedium', size: 0.26 }, [X0 + 0.7, y], { delay: 0.1 + i * 0.05 });
    api.text(0, p.map((v, k) => fmt(v, k < 3 ? 1 : 0)).join('   '), { font: 'mono', size: 0.24 }, [X0 + 3.0, y], { delay: 0.12 + i * 0.05 });
  });
  const lines = [
    ['Werkzeug', r.tool_name],
    ['Arbeitsraum → Roboter', `${fmt(w2r.rotation_deg, 2)}°  ·  ${w2r.translation_mm.map((v) => fmt(v)).join(' / ')} mm  ·  Tisch z ${fmt(w2r.table_z_mm)} mm`],
    ['Arbeitsraum', `${cfg.workspace.size_mm.join(' × ')} mm  ·  ArUco ${cfg.workspace.dictionary}`],
    ['Geschwindigkeit', `${fmt(r.linear_speed_mps, 2)} m/s, ab ${r.approach_slow_mm} mm über dem Ziel ${fmt(r.approach_speed_mps, 2)} m/s  ·  Anfahrhöhe ${r.approach_height_mm} mm`],
    ['Greifer-Offset', `${fmt(r.gripper_angle_offset_deg, 0)}°`],
    ['Prüfung', `Bauteilhöhe ${fmt(cfg.inspection.part_height_mm, 0)} mm  ·  Loch ${fmt(cfg.inspection.hole_nominal_mm, 0)} ± ${fmt(cfg.inspection.hole_tolerance_mm)} mm  ·  Seriennummer ${cfg.inspection.serial_pattern}`],
  ];
  lines.forEach(([k, v], i) => {
    const y = -0.2 - i * 0.55;
    api.text(1, k, { font: 'sansMedium', size: 0.24 }, [X0 + 0.7, y], { delay: i * 0.06 });
    api.text(1, v, { font: 'mono', size: 0.22 }, [X0 + 4.3, y], { delay: 0.04 + i * 0.06 });
  });
  api.text(1, 'Quelle: code/config/system.yaml', { font: 'mono', size: 0.15, hex: T.inkSoft }, [X0 + 0.7, -3.75], { delay: 0.4 });
}

// ---------------------------------------------------------------- A.2 / A.3 Zwischenbilder
function stepsSheet(key, cols, width) {
  return (api) => {
    const figs = api.ctx.data.figures[key];
    const rows = Math.ceil(figs.length / cols);
    const gx = (SHEET_W - 1.4) / cols;
    const gy = 6.3 / rows;
    figs.forEach((f, i) => {
      const c = i % cols;
      const r = Math.floor(i / cols);
      const x = X0 + 0.1 + gx * (c + 0.5);
      const y = 1.8 - gy * r;
      const w = Math.min(width, ((gy - 0.6) * f.w) / f.h);
      const card = new PhotoCard(f.url, { width: w, aspect: f.h / f.w, border: 0.05, bottom: 0.05 });
      card.object.position.set(x, y + 0.1, 0.03);
      card.opacity = 0;
      api.add(0, card, { delay: 0.1 + i * 0.05, dur: 0.4 });
      api.text(0, f.name.replace(/^m[13]_/, ''), { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'center', anchorY: 'top' }, [x, y + 0.1 - (w * f.h) / f.w / 2 - 0.1], { delay: 0.15 + i * 0.05 });
    });
  };
}

// ---------------------------------------------------------------- A.4 Tests
function sheetA4(api) {
  const t = api.ctx.data.tests;
  const files = Object.entries(t.files);
  const modOf = (f) => (f.startsWith('m1') ? 'M1' : f.startsWith('m2') ? 'M2' : f.startsWith('m3') ? 'M3' : f.startsWith('m4') ? 'M4' : 'ORCH');
  const max = Math.max(...files.map(([, n]) => n));
  files.forEach(([f, n], i) => {
    const y = 2.45 - i * 0.5;
    api.text(0, f, { font: 'mono', size: 0.2 }, [X0 + 0.7, y], { delay: 0.05 * i });
    api.line(0, [[X0 + 7.6, y], [X0 + 7.6 + (n / max) * 5, y]], { width: 7, hex: MODULE_COLOR[modOf(f)] }, { delay: 0.05 * i + 0.1 });
    api.text(0, String(n), { font: 'monoMedium', size: 0.2 }, [X0 + 7.75 + (n / max) * 5, y], { delay: 0.05 * i + 0.2 });
  });
  api.text(0, `${t.total} Tests – ohne Hardware: synthetische Szenen, echte Testfotos, Simulator der Neura-Steuerung, GUI ohne Bildschirm`, { font: 'sans', size: 0.22, hex: T.inkSoft, anchorY: 'top', maxWidth: 14 }, [X0 + 0.7, -3.35], { delay: 0.6 });
}

export function sheetScenes(storyboard) {
  const e = (id) => storyboard.find((s) => s.id === id);
  return [
    sheetScene(e('1.5'), 2, sheet15),
    sheetScene(e('1.6'), 4, sheet16),
    sheetScene(e('2.4'), 1, sheet24),
    sheetScene(e('4.6'), 2, sheet47),
    sheetScene(e('6.2'), 2, sheetIL),
    sheetScene(e('6.4'), 3, sheetObs),
    sheetScene(e('6.7'), 2, sheetFunnel),
    sheetScene(e('6.3'), 3, sheetDiffusion, { durations: [1.6, 4.0, 1.6] }),
    sheetScene(e('6.9'), 2, sheetSim),
    sheetScene(e('6.11'), 1, sheetAfterDagger),
    sheetScene(e('6.12'), 2, sheetSmooth),
    sheetScene(e('6.13'), 1, sheetLastMm),
    sheetScene(e('6.14'), 2, sheetAccuracy),
    { ...sheetScene(e('6.15'), 2, sheetHeat), scrub: { 2: 'rot' }, scrubLabel: 'ziehen: Drehklasse wählen' },
    sheetScene(e('6.16'), 1, sheetOutlook),
    sheetScene(e('6.8'), 2, sheetJitter),
    sheetScene(e('A.9'), 2, sheetTiming),
    sheetScene(e('3.6'), 2, sheet36),
    sheetScene(e('5.9'), 2, sheet75),
    sheetScene(e('7.4'), 2, sheet74),
    sheetScene(e('A.1'), 2, sheetA1),
    sheetScene(e('A.2'), 1, stepsSheet('steps_m1', 5, 2.7)),
    sheetScene(e('A.3'), 1, stepsSheet('steps_m3', 5, 2.7)),
    sheetScene(e('A.4'), 1, sheetA4),
    sheetScene(e('A.5'), 1, sheet71),
    sheetScene(e('A.6'), 2, sheet72),
    sheetScene(e('A.7'), 2, sheet73m),
    sheetScene(e('A.8'), 2, sheet74lab),
  ];
}
