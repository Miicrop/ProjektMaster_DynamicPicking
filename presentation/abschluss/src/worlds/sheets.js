// Ruhige Blätter (Baukasten src/kit/sheet.js): 1.5, 1.6, 2.4, 4.7, 7.1, 7.3, A.1–A.4.
// Inhalte aus thesis/blueprint.md, thesis 02b_vorprojekt.tex, plan/06_roadmap.md, plan/07_erledigt.md und
// data.json (config, Zwischenbilder, GUI-Screenshot, Zykluslog, Labortag, Tests).
import * as THREE from 'three';
import { T, MODULE_COLOR, color } from '../theme.js';
import { PhotoCard, Balloon } from '../kit/ink.js';
import { sheetScene, SHEET_W } from '../kit/sheet.js';

const X0 = -SHEET_W / 2 + 0.6;
const fmt = (v, d = 1) => Number(v).toFixed(d).replace('.', ',');

// ---------------------------------------------------------------- 1.5 Erfolgskriterium
function sheet15(api) {
  const cfg = api.ctx.data.config;
  api.text(0, 'Läuft Erkennen, Greifen, Prüfen und Sortieren vollständig automatisch durch?', { font: 'title', size: 0.52, anchorY: 'top', maxWidth: 14.2, lineHeight: 1.15 }, [X0 + 0.7, 2.55], { delay: 0.1 });
  api.text(0, 'Das ist das Erfolgskriterium. Messwerte dienen der Demonstration, nicht echten Toleranzen.', { font: 'sans', size: 0.24, hex: T.inkSoft, anchorY: 'top' }, [X0 + 0.7, 1.15], { delay: 0.3 });
  api.text(1, 'ABGRENZUNG', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.08 }, [X0 + 0.7, 0.3]);
  const rows = [
    ['Ein Bauteil', 'kein Schüttgut, keine Vereinzelung'],
    ['Flach liegend', `Pose in der Ebene: x, y und Winkel – die Greifhöhe ist bekannt`],
    ['Unter Aufsicht', `keine sicherheitszertifizierte Anlage, Override ${Math.round(cfg.robot.override * 100)} %, Not-Halt in Reichweite`],
    ['M4 optional', 'lernbasiertes Greifen aus dem Rahmen bis in die Prüfung (Teil von M2), nicht Voraussetzung für den Demonstrator'],
  ];
  rows.forEach(([t, b], i) => {
    const x = X0 + 0.7 + (i % 2) * 7.3;
    const y = -0.2 - Math.floor(i / 2) * 1.55;
    api.row(1, i + 1, t, b, y, { x, width: 6.3, size: 0.32, delay: 0.1 + i * 0.12 });
  });
  api.stamp(1, 'ERFOLGSKRITERIUM', [4.6, -3.55], { size: 0.34, rot: -0.05, hex: T.ink }, { delay: 0.6 });
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
    api.add(1, card, { delay: i * 0.18, dur: 0.6 });
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
  ];
  const pins = [];
  const shown = rows.map(([t, b, uv], i) => {
    pins.push(pin(0, i + 1, at(...uv), { delay: 0.6 + i * 0.15 }));
    return api.row(0, i + 1, t, b, 2.3 - i * 1.5, { x: RX, width: 3.9, size: 0.28, delay: 0.5 + i * 0.15 });
  });
  // Schritt 1: Logbuch – echte Zeilen aus code/logs (Simulator + Testbilder, 26.09., mit einem STOPP)
  pin(1, 4, at(0.3, 0.77), { delay: 0 });
  api.fade(1, shown.flatMap((r) => [r.t, r.d]), { delay: 0, dur: 0.4 });
  const balloons = [...pins, ...shown.map((r) => r.b)];
  api.add(1, (v) => balloons.forEach((b) => (b.appear = Math.min(b.appear, 1 - v))), { delay: 0, dur: 0.4 });
  const cycles = api.ctx.data.logs.cycles.filter((c) => c.time.startsWith('2026-09-26 22:2'));
  const SW = 4.6;
  const SH = 0.95 + cycles.length * 0.36;
  const top = 2.35;
  const sx = RX - 0.2;
  const strip = new THREE.Mesh(new THREE.PlaneGeometry(SW, SH), new THREE.MeshBasicMaterial({ color: color('#FBFAF6'), transparent: true, opacity: 0 }));
  strip.position.set(sx + SW / 2, top - SH / 2, 0.005);
  api.scene.add(strip);
  api.add(1, (v) => {
    strip.material.opacity = v;
    strip.visible = v > 0;
  }, { delay: 0.3, dur: 0.4 });
  api.line(1, [[sx, top], [sx + SW, top], [sx + SW, top - SH], [sx, top - SH]], { closed: true, width: 1.2 }, { delay: 0.3, dur: 0.5 });
  api.text(1, 'logs/cycles_20260926.csv', { font: 'monoMedium', size: 0.17 }, [sx + 0.2, top - 0.3], { delay: 0.5 });
  api.text(1, 'Simulator + Testbilder', { font: 'mono', size: 0.14, hex: T.inkSoft }, [sx + 0.2, top - 0.56], { delay: 0.55 });
  cycles.forEach((c, i) => {
    const y = top - 0.98 - i * 0.36;
    const ok = c.ok === 'True';
    const pose = `${fmt(c.x_mm)} / ${fmt(c.y_mm)} / ${fmt(c.theta_deg)}°`;
    const body = ok ? `${pose}  ${c.serial}` : c.error.split(' - ')[0];
    const d = { delay: 0.6 + i * 0.12, dur: 0.3 };
    const verdict = ok ? (c.good === 'True' ? 'GUT' : 'SCHLECHT') : 'FEHLER';
    api.text(1, c.time.slice(11), { font: 'mono', size: 0.15, hex: T.inkSoft }, [sx + 0.2, y], d);
    api.text(1, body, { font: 'mono', size: 0.15, hex: ok ? T.ink : T.signal }, [sx + 1.1, y], d);
    api.text(1, verdict, { font: 'monoMedium', size: 0.15, hex: verdict === 'GUT' ? T.good : T.signal, anchorX: 'right' }, [sx + SW - 0.2, y], d);
  });
  api.text(1, 'Jeder Zyklus eine Zeile: Zeit, Pose x / y / Winkel, Seriennummer, Urteil oder Fehler (Auszug).', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', maxWidth: SW }, [sx, top - SH - 0.25], { delay: 1.4 });
}

// ---------------------------------------------------------------- 4.7 Roboter einrichten (GUI-Tab M2)
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

// ---------------------------------------------------------------- 7.1 Labortag
function sheet71(api) {
  const lab = api.ctx.data.lab;
  const cfg = api.ctx.data.config;
  const w = lab.workspace_to_robot.after;
  const rows = [
    ['Posen geteacht', 'Prüfplatz und Ablagen direkt am Roboter angefahren und übernommen'],
    ['Arbeitsraum → Roboter kalibriert', `Drehung ${fmt(w.rotation_deg, 2)}°, Verschiebung ${w.translation_mm.map((v) => fmt(v)).join(' / ')} mm, Tisch z ${fmt(w.table_z_mm)} mm`],
    ['Greifer 23° verdreht montiert', `Offset 90° → ${fmt(cfg.robot.gripper_angle_offset_deg, 0)}°, Werkzeug ${lab.tool.after} statt ${lab.tool.before}`],
    ['Erster vollständiger Ablauf', 'im Automatikbetrieb – ehrlich: noch ohne Greiferansteuerung und ohne Arbeitsraumkamera, M1/M3 mit Testbildern'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.3 - i * 1.5, { x: X0 + 0.7, width: 6.4, size: 0.3, delay: 0.1 + i * 0.15 }));
  // Schritt 1: Schätzung aus der Skizze gegen die geteachten Posen
  const TXL = 0.9;
  api.text(1, 'SCHÄTZUNG AUS DER SKIZZE → GETEACHT  (x / y / z in mm)', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.06 }, [TXL, 2.2]);
  const names = { inspection: 'Prüfplatz', bin_good: 'Ablage GUT', bin_bad: 'Ablage SCHLECHT' };
  const xyz = (p) => p.slice(0, 3).map((v) => fmt(v, 0)).join(' / ');
  const dist = Object.values(lab.poses).map(({ before, after }) => Math.hypot(...[0, 1, 2].map((j) => after[j] - before[j])));
  Object.entries(lab.poses).forEach(([k, { before, after }], i) => {
    const y = 1.45 - i * 0.95;
    const t = { delay: 0.15 + i * 0.15 };
    api.text(1, names[k], { font: 'sansMedium', size: 0.26 }, [TXL, y], t);
    api.text(1, `${xyz(before)}  →  ${xyz(after)}`, { font: 'mono', size: 0.2, hex: T.inkSoft }, [TXL, y - 0.36], t);
    api.text(1, `${fmt(dist[i], 0)} mm`, { font: 'monoMedium', size: 0.3, hex: MODULE_COLOR.M2, anchorX: 'right' }, [TXL + 6.4, y - 0.18], { delay: t.delay + 0.1 });
  });
  const rz = lab.poses.inspection;
  api.text(1, `Greiferdrehung rz ${fmt(rz.before[5], 0)}° → ${fmt(rz.after[5], 0)}°: die 23° stecken in jeder Pose.`, { font: 'sans', size: 0.22, anchorY: 'top', maxWidth: 6.4 }, [TXL, -1.55], { delay: 0.7 });
  const cm = (v) => Math.round(v / 10);
  api.stamp(1, 'TEACHEN IST PFLICHT', [TXL + 3.2, -2.75], { size: 0.3, rot: -0.04, hex: MODULE_COLOR.M2, sub: `Schätzungen lagen ${cm(Math.min(...dist))}–${cm(Math.max(...dist))} cm daneben` }, { delay: 0.9 });
  api.text(1, `Quelle: system.yaml vor/nach Commit ${lab.commit} (${lab.date.split('-').reverse().join('.')})`, { font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, -3.85], { delay: 1.0 });
}

// ---------------------------------------------------------------- 7.3 Was noch fehlt
function sheet73(api) {
  const t = api.ctx.data.tests;
  const done = [
    ['Ablauf ohne Hardware', `Testfotos + Simulator der Steuerung, ${t.total} automatische Tests`],
    ['GUI und Logbuch', 'Einzeltests je Modul, automatischer Ablauf, ein CSV je Tag'],
    ['Roboter am Aufbau', 'Posen geteacht, kalibriert, erster vollständiger Ablauf (06.10.)'],
    ['Prüfung M3', 'Seriennummer, Loch und Kerbe auf allen Testbildern richtig, Fehler erkannt'],
  ];
  const open = [
    ['Greifer live', 'Greiferansteuerung am echten Roboter – bisher lief der Ablauf ohne Greifen'],
    ['Kameras live', 'Stangen- und Seitenkamera montieren; M1 misst das Bauteil noch zu groß (64–69 statt 60 mm)'],
    ['Messreihen', 'Greiferfolg, Posengenauigkeit, Prüfquote – Grundlage für die Evaluation'],
    ['M4 KI-Greifen', 'Handgelenkkamera, Greifen aus dem Rahmen bis in die Prüfung (Jeremy)'],
  ];
  const col = (step, items, x, n0, label, hex) => {
    api.stamp(step, label, [x + 1.2, 2.4], { size: 0.26, rot: -0.04, hex }, { delay: 0.05 });
    items.forEach(([ti, b], i) => api.row(step, n0 + i, ti, b, 1.65 - i * 1.4, { x, width: 6.0, size: 0.28, delay: 0.15 + i * 0.12 }));
  };
  col(0, done, X0 + 0.7, 1, 'ERLEDIGT', T.good);
  col(1, open, 0.9, 5, 'OFFEN', T.signal);
  api.text(1, 'Stand 21.10. · Quelle: plan/06_roadmap.md, plan/07_erledigt.md', { font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, -3.85], { delay: 0.7 });
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
  const modOf = (f) => (f.startsWith('m1') ? 'M1' : f.startsWith('m2') ? 'M2' : f.startsWith('m3') ? 'M3' : 'ORCH');
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
    sheetScene(e('1.6'), 2, sheet16),
    sheetScene(e('2.4'), 2, sheet24),
    sheetScene(e('4.7'), 2, sheet47),
    sheetScene(e('7.1'), 2, sheet71),
    sheetScene(e('7.3'), 2, sheet73),
    sheetScene(e('A.1'), 2, sheetA1),
    sheetScene(e('A.2'), 1, stepsSheet('steps_m1', 5, 2.7)),
    sheetScene(e('A.3'), 1, stepsSheet('steps_m3', 5, 2.7)),
    sheetScene(e('A.4'), 1, sheetA4),
  ];
}
