// Ruhige Blätter (Baukasten src/kit/sheet.js): 1.5, 1.6, 2.4, 4.7, 6.3–6.7, 7.1, 7.3, A.1–A.4.
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
  const cfg = api.ctx.data.config;
  api.text(0, 'Läuft Erkennen, Greifen, Prüfen und Sortieren vollständig automatisch durch?', { font: 'title', size: 0.52, anchorY: 'top', maxWidth: 14.2, lineHeight: 1.15 }, [X0 + 0.7, 2.55], { delay: 0.1 });
  api.text(0, 'Das ist das Erfolgskriterium. Messwerte dienen der Demonstration, nicht echten Toleranzen.', { font: 'sans', size: 0.24, hex: T.inkSoft, anchorY: 'top' }, [X0 + 0.7, 1.15], { delay: 0.3 });
  api.text(1, 'ABGRENZUNG', { font: 'mono', size: 0.15, hex: T.inkSoft, letterSpacing: 0.08 }, [X0 + 0.7, 0.3]);
  const rows = [
    ['Ein Bauteil', 'kein Schüttgut, keine Vereinzelung'],
    ['Flach liegend', `Pose in der Ebene: x, y und Winkel – die Greifhöhe ist bekannt`],
    ['Unter Aufsicht', `keine sicherheitszertifizierte Anlage, Override ${Math.round(cfg.robot.override * 100)} %, Not-Halt in Reichweite`],
    ['M4 optional', 'lernbasiertes Greifen aus dem Rahmen bis über die Prüfung (statt PICK von M2), nicht Voraussetzung für den Demonstrator'],
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

// ---------------------------------------------------------------- 6.3 Rauschtrichter (echte Episoden aus bc/noise.py)
function sheetFunnel(api) {
  const f = api.ctx.data.m4.funnel;
  const n = api.ctx.data.m4.noise;
  const L = f.arc_mm[f.arc_mm.length - 1];
  const PX0 = X0 + 1.2;
  const PX1 = 1.5;
  const S = 1 / 52; // mm → Blatt
  const Xf = (a) => PX0 + (a / L) * (PX1 - PX0);
  const plotDev = (step, y0, devs, hullHi, hullLo, label) => {
    const d = (k) => ({ delay: k, dur: 0.6 });
    api.line(step, [[PX0, y0], [PX1, y0]], { width: 1, hex: T.inkSoft }, d(0));
    api.text(step, label, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'right', anchorY: 'middle' }, [PX0 - 0.15, y0], d(0));
    [f.limit_mm.xy, -f.limit_mm.xy].forEach((v) => api.text(step, `${v > 0 ? '+' : '−'}${fmt(Math.abs(v), 0)}`, { font: 'mono', size: 0.12, hex: T.inkSoft, anchorX: 'right', anchorY: 'middle' }, [PX0 - 0.15, y0 + v * S], d(0.1)));
    const hull = (vals) => vals.map((v, i) => [Xf(f.arc_mm[i]), y0 + v * S]);
    api.line(step, hull(hullHi), { width: 1.2, dashed: true, dash: 0.07, gap: 0.05, hex: T.inkSoft }, d(0.2));
    api.line(step, hull(hullLo), { width: 1.2, dashed: true, dash: 0.07, gap: 0.05, hex: hullLo === f.hull_z_lo ? T.signal : T.inkSoft }, d(0.2));
    devs.forEach((dv, e) => {
      const l = api.line(step, dv.map((v, i) => [Xf(f.arc_mm[i]), y0 + v * S]), { width: 1.2, hex: MODULE_COLOR.M4 }, { delay: 0.4 + e * 0.05, dur: 1.0 });
      l.opacity = 0.7;
    });
  };
  const YT = 1.35;
  const YB = -1.75;
  // Ankerpunkte: dort ist das Rauschen null
  const ANCH = ['Start', 'PICK', 'Übergabe'];
  f.anchors_mm.forEach((a, i) => {
    api.line(0, [[Xf(a), YT + 1.15], [Xf(a), YB - 1.0]], { width: 1, dashed: true, dash: 0.05, gap: 0.06, hex: T.inkSoft }, { delay: 0.1 });
    api.text(0, ANCH[i], { font: 'monoMedium', size: 0.15, anchorX: i === 0 ? 'left' : i === 2 ? 'right' : 'center', anchorY: 'bottom' }, [Xf(a), YT + 1.2], { delay: 0.15 });
  });
  plotDev(0, YT, f.dx, f.hull_hi, f.hull_hi.map((v) => -v), 'x');
  api.text(0, 'Abweichung von der Sollbahn in mm, 10 Episoden über der Bahn', { font: 'mono', size: 0.14, hex: T.inkSoft }, [PX0, YB - 1.35], { delay: 0.2 });
  // Schritt 1: die Höhe – nach unten (Tisch) fast nichts
  plotDev(1, YB, f.dz, f.hull_hi, f.hull_z_lo, 'z');
  const hatch = [];
  for (let x = PX0; x < PX1 - 0.1; x += 0.22) hatch.push([[x, YB - 0.08], [x + 0.18, YB - 0.4]]);
  hatch.forEach((h, i) => api.line(1, h, { width: 1, hex: T.signal }, { delay: 0.6 + i * 0.01, dur: 0.3 }));
  api.text(1, 'Tisch', { font: 'monoMedium', size: 0.15, hex: T.signal, anchorY: 'top' }, [PX1 + 0.1, YB - 0.1], { delay: 0.9 });
  // rechts: was der Trichter tut
  const RX = 2.5;
  const rows = [
    [0, 'Trichter', `null an Start, PICK und Übergabe, ab ${fmt(n.funnel_mm[1], 0)} mm Abstand volle Streuung – genau greifen, im Transit schlingern`],
    [0, 'Rauschfaktor je Episode', 'zufällig 0 bis 1 – von fast ideal bis volle Streuung'],
    [1, 'Asymmetrisch', `seitlich und nach oben bis ${fmt(f.limit_mm.xy, 0)} mm (dreifache Streuung), Richtung Tisch höchstens ${fmt(-f.limit_mm.z_down, 0)} mm`],
    [1, 'Rejection Sampling', `jede Bahn per IK und Kollisionsmodell geprüft, sonst neu gezogen (bis ${f.max_rejects}×)`],
  ];
  rows.forEach(([step, t, b], i) => api.row(step, i + 1, t, b, 2.45 - i * 1.5, { x: RX, width: 4.5, size: 0.26, delay: 0.3 + (i % 2) * 0.15 }));
  api.text(1, 'Quelle: Bahn und Rauschen aus m4_behavior_cloning/bc/noise.py (SmoothedOUProcess, funnel_scale, NoiseLimits)', { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 1.0 });
}

// ---------------------------------------------------------------- 6.4 Diffusion Policy erklärt
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
    ['Handgelenkkamera', `Fisheye, ${pc.image[0]} × ${pc.image[1]}`, MODULE_COLOR.M4],
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
  // Schritt 2: die ersten n_action Takte werden gefahren, dann neu vorhergesagt
  api.add(2, (v) => dots.forEach((m, k) => {
    const used = k < pc.n_action;
    m.scale.setScalar(1 + (used ? 0.5 : 0) * v);
    m.material.opacity *= used ? 1 : 1 - 0.65 * v; // Schritt 0 setzt die Deckkraft in jedem Bild neu
  }), { delay: 0, dur: 0.6 });
  const xm = kx(pc.n_action - 0.5);
  api.line(2, [[kx(0), FY1 - 0.5], [xm - 0.05, FY1 - 0.5]], { width: 2.2, hex: MODULE_COLOR.M4 }, { delay: 0.3 });
  api.text(2, `${pc.n_action} Takte werden gefahren (≈ ${fmt(pc.n_action / 15, 1)} s)`, { font: 'monoMedium', size: 0.15, hex: MODULE_COLOR.M4, anchorY: 'bottom' }, [kx(0), FY1 - 0.42], { delay: 0.35 });
  api.text(2, 'Rest verworfen, neu vorhergesagt', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top' }, [xm + 0.1, FY0 + 0.45], { delay: 0.45 });
  const rows = [
    ['Lernen durch Nachmachen', 'die Policy ahmt die aufgezeichneten Fahrten nach – samt der Korrekturen aus dem Rauschen'],
    ['Takt', `eine Vorhersage dauert ~${sim.predict_ms} ms, länger als ein 15-Hz-Takt – sie läuft deshalb neben dem Servostrom (60 Hz)`],
  ];
  rows.forEach(([t, b], i) => api.row(2, i + 1, t, b, -2.45, { x: IX + i * 7.3, width: 6.2, size: 0.25, delay: 0.6 + i * 0.15 }));
  api.text(2, `Quelle: m4_behavior_cloning/bc/config.py (horizon ${pc.horizon}, n_action_steps ${pc.n_action}, ${pc.inference_steps} DDIM-Schritte), bc/diffusion.py`, { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.9 });
}

// ---------------------------------------------------------------- 6.5 Policy fährt selbst (Simulation)
function sheetSim(api) {
  const s = api.ctx.data.m4.sim;
  const f = s.figure;
  const card = new PhotoCard(f.url, { width: 13.2, aspect: f.h / f.w, border: 0.05, bottom: 0.05 });
  card.object.position.set(0, 1.0, 0.01); // unter dem Stempel
  card.opacity = 0;
  api.add(0, card, { delay: 0.1, dur: 0.6 });
  api.text(0, 'gestrichelt: aufgezeichnete Sollbahn · grün: 10 Fahrten der trainierten Policy', { font: 'mono', size: 0.14, hex: T.inkSoft, anchorY: 'top' }, [X0 + 0.7, -0.75], { delay: 0.3 });
  const d = (k) => ({ delay: 0.6 + k * 0.15 });
  const facts = [
    [`${s.success[0]} / ${s.success[1]}`, 'Fahrten erfolgreich (gegriffen und übergeben)'],
    [`${fmt(s.grip_mm[0])}–${fmt(s.grip_mm[1])} mm`, 'vom Greifpunkt entfernt'],
    [`${fmt(s.path_p95_mm[0])}–${fmt(s.path_p95_mm[1])} mm`, 'neben der Bahn (95 %)'],
    [`${s.train_min} min`, `Training: ${s.episodes} Episoden, ${s.steps} Schritte, ${s.gpu}`],
  ];
  facts.forEach(([big, small], i) => {
    const x = X0 + 0.7 + i * 3.7;
    api.text(0, big, { font: 'title', size: 0.42, hex: i === 0 ? T.good : T.ink, anchorY: 'top' }, [x, -1.15], d(i));
    api.text(0, small, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', maxWidth: 3.4 }, [x, -1.7], d(i));
  });
  api.stamp(0, 'SIMULATION', [5.4, 3.5], { size: 0.26, rot: -0.05, hex: MODULE_COLOR.M4 }, { delay: 1.0 }); // neben dem Titel
  // Schritt 1: ehrlich – was das noch nicht zeigt
  const rows = [
    ['Nur aus dem Zustand gelernt', 'in der Simulation gab es nur Platzhalterbilder – das Sehen kommt erst mit echten Aufnahmen'],
    ['In der VM: Stillstand vor dem Greifen', 'Ankommen und Losfahren sehen im Zustand gleich aus, die Policy blieb an PRE_GRASP stehen'],
  ];
  rows.forEach(([t, b], i) => api.row(1, i + 1, t, b, -2.6, { x: X0 + 0.7 + i * 7.3, width: 6.2, size: 0.25, delay: 0.1 + i * 0.15 }));
  api.text(1, `Quelle: m4_behavior_cloning/Berichte/2026-09-17_Durchstich_Policy.pdf (Lauf „Sim, echte Uhr, asynchron“)`, { font: 'mono', size: 0.13, hex: T.inkSoft }, [X0 + 0.7, -3.95], { delay: 0.5 });
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
    ['Geofence + Software-Stopp', 'Watchdog prüft den Arbeitsraum (Tisch-Quader), hält in ~100 ms'],
  ];
  rows.forEach(([t, b], i) => api.row(1, i + 1, t, b, -0.85 - Math.floor(i / 2) * 1.3, { x: X0 + 0.7 + (i % 2) * 7.3, width: 6.2, size: 0.25, delay: 0.1 + i * 0.12 }));
  api.stamp(1, 'IN DER VM AUSGELÖST', [3.8, -3.1], { size: 0.24, rot: -0.04, hex: MODULE_COLOR.M4, sub: 'jede Schicht hat in den VM-Läufen korrekt gestoppt · Contract-Suite 12/12' }, { delay: 0.7 });
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

// ---------------------------------------------------------------- 7.1 Labortag
function sheet71(api) {
  const lab = api.ctx.data.lab;
  const cfg = api.ctx.data.config;
  const w = lab.workspace_to_robot.after;
  const rows = [
    ['Posen geteacht', 'Prüfplatz und Ablagen direkt am Roboter angefahren und übernommen'],
    ['Arbeitsraum → Roboter kalibriert', `Drehung ${fmt(w.rotation_deg, 2)}°, Verschiebung ${w.translation_mm.map((v) => fmt(v)).join(' / ')} mm, Tisch z ${fmt(w.table_z_mm)} mm`],
    ['Greifer 23° verdreht montiert', `Offset 90° → 113°, Werkzeug ${lab.tool.after} statt ${lab.tool.before}`],
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

// Pfeil als drei Tuschestriche (Schaft + Spitze)
function arrow(api, step, [x0, y0], [x1, y1], opts, timing) {
  const a = Math.atan2(y1 - y0, x1 - x0);
  const len = Math.hypot(x1 - x0, y1 - y0);
  const h = Math.min(0.13, len * 0.45);
  const head = (s) => [x1 - h * Math.cos(a + s * 0.45), y1 - h * Math.sin(a + s * 0.45)];
  api.line(step, [[x0, y0], [x1, y1]], opts, timing);
  return [api.line(step, [head(1), [x1, y1], head(-1)], opts, timing)];
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

// ---------------------------------------------------------------- 7.2 Labortag 12.11.
function sheet72(api) {
  const L = api.ctx.data.lab2;
  if (!L) return;
  const rows = [
    ['Kameras live, fest eingestellt', `Kamera oben: Belichtung ${fmt((L.exposure_us ?? 15000) / 1000, 0)} ms statt Automatik (Teil war übersteuert). Seitenkamera: Fokus fest ${L.focus ?? 90}, im Programm gesetzt.`],
    ['Greifer im Ablauf', 'über die Digitalausgänge der Steuerung: auf, zu, Freigabe, Reset'],
    ['Zeigetests', 'Versatz bis 8 mm am Rand → lineare Positionskorrektur (3.6)'],
    ['Teil gedreht greifen', 'Seriennummer und Fase zeigen zur Seitenkamera; Offset −67° (4.4)'],
    ['Veraltete Bilder', 'beide Kameras gaben nach einer Pause ein altes Bild aus dem Puffer – jetzt wird er vor jeder Aufnahme geleert'],
    ['Sanft ablegen', 'Greifer öffnet 1 mm über der geteachten Pose, sonst fällt das Teil auf die Prüfung'],
  ];
  rows.forEach(([t, b], i) => api.row(0, i + 1, t, b, 2.65 - i * 1.15, { x: X0 + 0.7, width: 7.0, size: 0.27, delay: 0.1 + i * 0.1 }));
  const ph = L.photos ?? {};
  const pick = [['anlage', 3.0, 0.25, 4.1, 0.04], ['vorrichtung', 5.6, 1.35, 3.3, -0.05], ['handgelenk', 5.4, -2.0, 2.6, 0.06]];
  pick.forEach(([name, x, y, w, rot], i) => {
    const f = ph[name];
    if (!f) return;
    const card = new PhotoCard(f.url, { width: w, aspect: f.h / f.w });
    card.object.position.set(x, y, 0.05 + i * 0.05);
    card.object.rotation.z = rot;
    card.opacity = 0;
    api.add(1, card, { delay: i * 0.2, dur: 0.6 });
  });
  api.stamp(1, 'ERSTER ZYKLUS MIT KAMERAS', [X0 + 4.2, -4.05], { size: 0.26, rot: -0.03, hex: MODULE_COLOR.M2 }, { delay: 0.9 });
}

// ---------------------------------------------------------------- 7.3 Messwerte
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
    [`${fmt(maxBefore, 0)} → ${fmt(worst, 0)} mm`, 'Versatz im Zeigetest\nohne / mit Korrektur', T.good],
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
  api.stamp(1, 'SPIEGELUNG IM LOCH', [4.6, -3.95], { size: 0.26, rot: 0.04, hex: T.signal, sub: 'Fensterlicht · Abhilfe: Faktor + Abschirmung' }, { delay: 1.0 });
}

// ---------------------------------------------------------------- 7.4 Was noch fehlt
function sheet74(api) {
  const t = api.ctx.data.tests;
  const done = [
    ['Ablauf ohne Hardware', `Testfotos + Simulator der Steuerung, ${t.total} automatische Tests, GUI mit Logbuch`],
    ['Kameras und Greifer am Aufbau', 'feste Belichtung und Fokus, Positionskorrektur, Greifer über Digitalausgänge'],
    ['Vollständiger Zyklus', 'erkannt, gegriffen, geprüft und sortiert – mit echten Kameras'],
    ['M4 eingebunden', 'eigener Reiter, Policy greift im Ablauf; Übergabe M4 → M2 in der Neura-VM getestet'],
  ];
  const open = [
    ['Lochmaßstab und Licht', 'Korrekturfaktor mit bekannten Gutteilen, Prüfstation gegen Fensterlicht abschirmen'],
    ['Kalibrierte Kamera', 'intrinsische Kalibrierung und Entzerrung auf Bauteilhöhe statt empirischer Korrektur'],
    ['M4 an der Anlage', 'Ergebnisse und Vergleich mit dem klassischen Greifen (Jeremy)'],
    ['Größere Messreihe', 'mehr Zyklen, echte Fehlerteile, wechselndes Licht'],
  ];
  const col = (step, items, x, n0, label, hex) => {
    api.stamp(step, label, [x + 1.2, 2.4], { size: 0.26, rot: -0.04, hex }, { delay: 0.05 });
    items.forEach(([ti, b], i) => api.row(step, n0 + i, ti, b, 1.65 - i * 1.4, { x, width: 6.0, size: 0.28, delay: 0.15 + i * 0.12 }));
  };
  col(0, done, X0 + 0.7, 1, 'ERLEDIGT', T.good);
  col(1, open, 0.9, 5, 'OFFEN', T.signal);
  api.text(1, 'Stand 24.11. · Quelle: plan/06_offen.md, plan/07_erledigt.md',{ font: 'mono', size: 0.14, hex: T.inkSoft }, [X0 + 0.7, -3.85], { delay: 0.7 });
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
    sheetScene(e('1.6'), 2, sheet16),
    sheetScene(e('2.4'), 2, sheet24),
    sheetScene(e('4.7'), 2, sheet47),
    sheetScene(e('6.3'), 2, sheetFunnel),
    sheetScene(e('6.4'), 3, sheetDiffusion, { durations: [1.6, 4.0, 1.6] }),
    sheetScene(e('6.5'), 2, sheetSim),
    sheetScene(e('6.6'), 2, sheetJitter),
    sheetScene(e('6.7'), 2, sheetTiming),
    sheetScene(e('3.6'), 2, sheet36),
    sheetScene(e('7.1'), 2, sheet71),
    sheetScene(e('7.2'), 2, sheet72),
    sheetScene(e('7.3'), 2, sheet73m),
    sheetScene(e('7.4'), 2, sheet74),
    sheetScene(e('A.1'), 2, sheetA1),
    sheetScene(e('A.2'), 1, stepsSheet('steps_m1', 5, 2.7)),
    sheetScene(e('A.3'), 1, stepsSheet('steps_m3', 5, 2.7)),
    sheetScene(e('A.4'), 1, sheetA4),
  ];
}
