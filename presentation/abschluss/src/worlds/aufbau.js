// Blätter für das Muster „Aufgabe → Idee → Am Aufbau → Lösung“ (Konzept 26.11.): 1.7, 2.5, 3.7, 3.8, 4.8, 5.7,
// 5.8, 7.1, 7.2, 7.3. Inhalte aus plan/07_erledigt.md (06.10., 12.11.), thesis Kap. 10 (26.11.) und data.json
// (lab, lab2, lab3). Rotstift = was am Aufbau schiefging, Grün = was daraus wurde.
import * as THREE from 'three';
import { T, MODULE_COLOR, color } from '../theme.js';
import { PhotoCard, text, v3 } from '../kit/ink.js';
import { sheetScene, SHEET_W, clamp01 } from '../kit/sheet.js';

const X0 = -SHEET_W / 2 + 0.6;
const fmt = (v, d = 1) => Number(v).toFixed(d).replace('.', ',');
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const smooth = (x) => { const t = clamp01(x); return t * t * (3 - 2 * t); };
const circ = (cx, cy, r, n = 40) => Array.from({ length: n }, (_, i) => [cx + r * Math.cos((i / n) * 2 * Math.PI), cy + r * Math.sin((i / n) * 2 * Math.PI)]);
const arcPts = (cx, cy, r, a0, a1, n = 24) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + ((a1 - a0) * i) / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });
const rot = ([x, y], a, [cx, cy] = [0, 0]) => [cx + (x - cx) * Math.cos(a) - (y - cy) * Math.sin(a), cy + (x - cx) * Math.sin(a) + (y - cy) * Math.cos(a)];
const MONO = { font: 'mono', size: 0.14, hex: T.inkSoft, letterSpacing: 0.06 };
const day = (iso) => iso.split('-').reverse().slice(0, 2).join('.') + '.';

function arrow(api, step, [x0, y0], [x1, y1], opts, timing) {
  const a = Math.atan2(y1 - y0, x1 - x0);
  const h = Math.min(0.16, Math.hypot(x1 - x0, y1 - y0) * 0.45);
  const head = (s) => [x1 - h * Math.cos(a + s * 0.45), y1 - h * Math.sin(a + s * 0.45)];
  return [api.line(step, [[x0, y0], [x1, y1]], opts, timing), api.line(step, [head(1), [x1, y1], head(-1)], opts, timing)];
}
// Haken im Kreis (grün) und Blitz (Rotstift) als Tuschezeichen
const check = (api, step, [x, y], r, timing, hex = T.good) => [
  api.line(step, circ(x, y, r), { closed: true, width: 1.8, hex }, timing),
  api.line(step, [[x - r * 0.45, y + r * 0.02], [x - r * 0.1, y - r * 0.35], [x + r * 0.5, y + r * 0.38]], { width: 2.6, hex }, { ...timing, delay: (timing?.delay ?? 0) + 0.15 }),
];
const bolt = (api, step, [x, y], s, timing, hex = T.signal) =>
  api.line(step, [[x + 0.15 * s, y + 0.6 * s], [x - 0.25 * s, y - 0.02 * s], [x + 0.08 * s, y + 0.02 * s], [x - 0.18 * s, y - 0.6 * s], [x + 0.32 * s, y + 0.12 * s], [x - 0.02 * s, y + 0.1 * s], [x + 0.28 * s, y + 0.6 * s]], { closed: true, width: 2.2, hex }, timing);

function card(api, step, f, [x, y], width, r = 0, timing = {}) {
  if (!f) return null;
  const c = new PhotoCard(f.url, { width, aspect: f.h / f.w });
  c.object.position.set(x, y, 0.05);
  c.object.rotation.z = r;
  c.opacity = 0;
  return api.add(step, c, { dur: 0.6, ...timing });
}

/** Gefülltes Rechteck (Mitte x, y), Deckkraft folgt dem Schritt. */
function fill(api, step, [x, y], w, h, hex, timing, { z = 0.004, opacity = 1 } = {}) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: color(hex), transparent: true, opacity: 0, depthWrite: false }));
  m.position.set(x, y, z);
  m.renderOrder = 1;
  api.scene.add(m);
  api.add(step, (v) => { m.material.opacity = v * opacity; m.visible = v > 0.001; }, timing);
  return m;
}

// Spalte mit Kopf (Rotstift/Grün) und Text; liefert die Objekte für fade()
function note(api, step, [x, y], head, body, { hex = T.ink, width = 4, size = 0.25, delay = 0 } = {}) {
  const h = api.text(step, head, { font: 'sansMedium', size, hex, anchorY: 'top', maxWidth: width }, [x, y], { delay });
  const b = body ? api.text(step, body, { font: 'sans', size: size * 0.8, hex: T.inkSoft, anchorY: 'top', maxWidth: width, lineHeight: 1.3 }, [x, y - size * 1.35], { delay: delay + 0.08 }) : null;
  return [h, b].filter(Boolean);
}

// ---------------------------------------------------------------- 1.7 Das Muster
function sheet17(api) {
  const cfg = api.ctx.data.config.inspection;
  const L2 = api.ctx.data.lab2;
  const W = 3.3, GAP = 0.45, XS = X0 + 0.75;
  const cx = (i) => XS + i * (W + GAP);
  const cols = [
    ['Aufgabe', 'Was das Modul liefern muss – und an wen.', T.ink],
    ['Idee', 'Das Verfahren, entwickelt an Testbildern und im Simulator.', T.ink],
    ['Am Aufbau', 'Was am echten Roboter, mit echtem Licht und echten Menschen anders war.', T.signal],
    ['Lösung', 'Was wir geändert haben – und was es gebracht hat.', T.good],
  ];
  const IY = 1.75;
  cols.forEach(([t, b, hex], i) => {
    const d = 0.1 + i * 0.35;
    const x = cx(i), m = x + W / 2;
    api.line(0, [[x, 2.55], [x + W, 2.55], [x + W, -0.95], [x, -0.95]], { closed: true, width: 1.2, hex: i >= 2 ? hex : T.inkSoft }, { delay: d, dur: 0.6 });
    if (i === 0) {
      api.line(0, circ(m, IY, 0.5), { closed: true, width: 1.8 }, { delay: d + 0.1 });
      api.line(0, circ(m, IY, 0.18), { closed: true, width: 1.8, hex: T.part }, { delay: d + 0.2 });
      api.line(0, [[m - 0.72, IY], [m + 0.72, IY]], { width: 1.2 }, { delay: d + 0.15 });
      api.line(0, [[m, IY - 0.72], [m, IY + 0.72]], { width: 1.2 }, { delay: d + 0.15 });
    } else if (i === 1) {
      const tri = [[m - 0.55, IY - 0.38], [m + 0.6, IY - 0.38], [m - 0.1, IY + 0.55]];
      api.line(0, tri, { closed: true, width: 1.8 }, { delay: d + 0.1 });
      api.line(0, circ(m - 0.02, IY - 0.03, 0.66), { closed: true, width: 1.1, hex: T.inkSoft, dashed: true }, { delay: d + 0.2 });
    } else if (i === 2) {
      bolt(api, 0, [m, IY], 0.9, { delay: d + 0.1 });
    } else {
      check(api, 0, [m, IY], 0.55, { delay: d + 0.1 });
    }
    api.text(0, `${i + 1}`, { font: 'mono', size: 0.16, hex: T.inkSoft }, [x + 0.2, 2.3], { delay: d });
    api.text(0, t, { font: 'title', size: 0.42, hex, anchorX: 'center' }, [m, 0.55], { delay: d + 0.2 });
    api.text(0, b, { font: 'sans', size: 0.2, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', maxWidth: W - 0.4, align: 'center', lineHeight: 1.3 }, [m, 0.15], { delay: d + 0.25 });
    if (i < 3) arrow(api, 0, [x + W + 0.06, 0.55], [x + W + GAP - 0.06, 0.55], { width: 1.4 }, { delay: d + 0.3 });
  });
  // Schritt 1: das Beispiel Lochmessung (M3) läuft einmal durch
  const holes = L2 ? L2.cycles.filter((c) => c.ok && c.hole_mm != null).map((c) => c.hole_mm) : [];
  const ex = [
    `Loch messen: ${fmt(cfg.hole_nominal_mm, 0)} ± ${fmt(cfg.hole_tolerance_mm, 1)} mm`,
    'Kontur des Lochs → Ellipse → mm über die Bauteilhöhe',
    holes.length ? `Spiegelung im Loch: ${fmt(Math.min(...holes), 2)}–${fmt(Math.max(...holes), 2)} mm, zu klein` : 'Spiegelung im Loch: zu klein',
    'Kreis-Fit ohne die inneren Punkte: alle Prüfbilder in Toleranz',
  ];
  api.text(1, 'BEISPIEL · M3 SICHTPRÜFUNG', MONO, [XS, -1.45]);
  ex.forEach((t, i) => {
    const hex = i === 2 ? T.signal : i === 3 ? T.good : T.ink;
    api.text(1, t, { font: 'sansMedium', size: 0.22, hex, anchorY: 'top', maxWidth: W - 0.2, lineHeight: 1.3 }, [cx(i) + 0.1, -1.75], { delay: 0.15 + i * 0.3 });
  });
  api.text(1, 'Die vier Schritte stehen ab jetzt unten rechts im Schriftfeld.', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorX: 'right' }, [-X0 - 0.2, -3.3], { delay: 1.5 });
  arrow(api, 1, [-X0 - 0.6, -3.5], [-X0 - 0.2, -3.95], { width: 1.4, hex: T.inkSoft }, { delay: 1.6 });
}

// ---------------------------------------------------------------- 2.5 Das alte Bild
function sheet25(api) {
  const g = new THREE.Group();
  api.scene.add(g);
  // Kamera links
  const KX = X0 + 1.1, KY = 0.85;
  api.line(0, [[KX - 0.55, KY - 0.38], [KX + 0.4, KY - 0.38], [KX + 0.4, KY + 0.38], [KX - 0.55, KY + 0.38]], { closed: true, width: 1.8 }, { delay: 0.05 });
  api.line(0, [[KX + 0.4, KY - 0.2], [KX + 0.75, KY - 0.32], [KX + 0.75, KY + 0.32], [KX + 0.4, KY + 0.2]], { closed: true, width: 1.8 }, { delay: 0.1 });
  api.text(0, 'Kamera läuft frei', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorX: 'center' }, [KX, KY - 0.7], { delay: 0.15 });
  // Puffer als Schacht
  const BX = -3.75, BW = 2.2, BY0 = -0.95, FH = 0.62;
  api.line(0, [[BX - BW / 2 - 0.12, BY0 + 4 * (FH + 0.08) + 0.15], [BX - BW / 2 - 0.12, BY0 - 0.12], [BX + BW / 2 + 0.12, BY0 - 0.12], [BX + BW / 2 + 0.12, BY0 + 4 * (FH + 0.08) + 0.15]], { width: 1.8 }, { delay: 0.15 });
  api.text(0, 'PUFFER IM TREIBER', MONO, [BX - BW / 2 - 0.1, BY0 + 4 * (FH + 0.08) + 0.4], { delay: 0.2 });
  arrow(api, 0, [KX + 0.85, KY], [BX - BW / 2 - 0.25, KY], { width: 1.4 }, { delay: 0.2 });
  // Bild-Kärtchen: Prüfstation leer (vor der Pause) bzw. mit Teil (jetzt)
  const frames = [
    ['10:41:02', false], ['10:41:03', false], ['10:41:04', false], ['10:43:20', true],
  ].map(([time, part]) => {
    const f = new THREE.Group();
    const mk = (w, h, hex, x, y, z) => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: color(hex), transparent: true, depthWrite: false }));
      m.position.set(x, y, z);
      m.renderOrder = 1;
      f.add(m);
      return m;
    };
    mk(BW, FH, '#FBFAF6', 0, 0, 0.001);
    mk(0.95, FH - 0.12, '#D9D3C6', -0.55, 0, 0.002);
    mk(0.7, 0.12, T.board, -0.55, -0.12, 0.003);
    if (part) mk(0.4, 0.16, T.part, -0.55, 0.02, 0.004);
    const t = text(time, { font: 'monoMedium', size: 0.17, hex: part ? T.ink : T.inkSoft });
    t.position.set(0.05, 0.08, 0.005);
    f.add(t);
    const s = text(part ? 'Teil liegt da' : 'Station leer', { font: 'sans', size: 0.13, hex: T.inkSoft });
    s.position.set(0.05, -0.14, 0.005);
    f.add(s);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(BW, FH)), new THREE.LineBasicMaterial({ color: color(T.ink), transparent: true }));
    edge.position.z = 0.006;
    f.add(edge);
    g.add(f);
    return { f, part };
  });
  const setOpacity = (f, o) => f.traverse((c) => {
    if ('fillOpacity' in c) c.fillOpacity = o; // troika-Text
    else if (c.material) c.material.opacity = o;
  });
  // Bildschirm rechts: was M3 sieht
  const SX = 1.9, SY = 0.95, SW = 3.4, SH = 1.9;
  api.line(0, [[SX - SW / 2, SY - SH / 2], [SX + SW / 2, SY - SH / 2], [SX + SW / 2, SY + SH / 2], [SX - SW / 2, SY + SH / 2]], { closed: true, width: 1.8 }, { delay: 0.25 });
  api.text(0, 'M3 BEKOMMT', MONO, [SX - SW / 2, SY + SH / 2 + 0.25], { delay: 0.3 });
  const screen = new THREE.Group();
  const sBg = new THREE.Mesh(new THREE.PlaneGeometry(SW - 0.16, SH - 0.16), new THREE.MeshBasicMaterial({ color: color('#D9D3C6'), transparent: true, depthWrite: false }));
  const sFix = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 0.36), new THREE.MeshBasicMaterial({ color: color(T.board), transparent: true, depthWrite: false }));
  sFix.position.y = -0.38;
  const sPart = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.45), new THREE.MeshBasicMaterial({ color: color(T.part), transparent: true, depthWrite: false }));
  sPart.position.y = 0.03;
  [sBg, sFix, sPart].forEach((m, i) => { m.position.z = 0.002 + i * 0.001; m.renderOrder = 1; screen.add(m); });
  screen.position.set(SX, SY, 0);
  api.scene.add(screen);
  const getLbl = text('get_image() nimmt das älteste', { font: 'monoMedium', size: 0.16, hex: T.signal, opacity: 0, anchorX: 'center', anchorY: 'top' });
  getLbl.position.set(BX, BY0 - 0.28, 0.01);
  api.scene.add(getLbl);
  const pull = arrow(api, 0, [BX + BW / 2 + 0.3, BY0 + FH / 2], [SX - SW / 2 - 0.15, SY - 0.3], { width: 1.4, hex: T.signal, dashed: true }, { delay: 1.5, dur: 0.4 });
  const oldStamp = api.stamp(0, 'ALTES BILD', [SX + SW / 2 + 1.75, SY + 0.1], { size: 0.3, rot: -0.08, hex: T.signal, sub: 'Station leer → Abbruch' }, { delay: 2.2 });
  note(api, 0, [X0 + 0.7, -1.95], 'Nach einer Pause sah M3 die leere Prüfstation', 'Die Kamera läuft frei und füllt ihren Puffer. Ein Lesebefehl liefert das älteste Bild – das von vor der Pause, als noch kein Teil dalag. Am 12.11. brachen so die ersten Zyklen ab.', { hex: T.signal, width: 6.6, delay: 2.3 });
  // Schritt 1: Puffer vor jeder Aufnahme leeren
  api.fade(1, [...pull, oldStamp], { dur: 0.3 });
  api.stamp(1, 'PUFFER LEEREN', [SX + SW / 2 + 1.75, SY + 0.1], { size: 0.3, rot: -0.06, hex: T.good, sub: 'vor jeder Aufnahme' }, { delay: 1.5 });
  note(api, 1, [0.6, -1.95], 'Vor jeder Aufnahme wird der Puffer geleert', 'Betraf beide Kameras – Daheng oben (M1) und Logitech an der Prüfung (M3). Behoben an einer Stelle: in der gemeinsamen Kameraklasse common/camera.py. Am Testbild unsichtbar: dort gibt es weder Puffer noch Pause.', { hex: T.good, width: 6.6, delay: 1.7 });
  return {
    update(S) {
      const a = S.s0, b = S.s1;
      // Schritt 0: Bilder fallen nacheinander in den Puffer, dann wandert das unterste (älteste) auf den Bildschirm
      // Schritt 1: die übrigen alten fliegen nach links raus, das neue rutscht nach unten und auf den Bildschirm
      const take = smooth((a * 2.6 - 1.6) / 0.4);
      const flush = (k) => smooth((b * 2.2 - k * 0.15) / 0.5);
      const fresh = smooth((b * 2.2 - 0.9) / 0.5);
      frames.forEach(({ f }, i) => {
        const tIn = smooth((a * 2.6 - 0.3 - i * 0.28) / 0.35);
        let x = BX;
        let y = BY0 + FH / 2 + i * (FH + 0.08) + (1 - tIn) * 1.2;
        let o = tIn;
        let s = 1;
        const toScreen = (t) => {
          x += (SX - x) * t;
          y += (SY - y) * t;
          s = 1 + 0.4 * t;
          o *= 1 - smooth((t - 0.7) / 0.3);
        };
        if (i === 0) toScreen(take);
        else if (i < 3) {
          x -= flush(i) * 1.4;
          o *= 1 - flush(i);
        } else toScreen(fresh);
        f.position.set(x, y, 0.02 + (i === 0 || i === 3 ? 0.05 : 0));
        f.scale.setScalar(s);
        setOpacity(f, o);
        f.visible = o > 0.001;
      });
      getLbl.opacity = clamp01((a * 2.6 - 1.4) / 0.3) * (1 - clamp01(b * 4));
      // Bildschirm: erst die leere Station (altes Bild), in Schritt 1 das frische Bild mit Teil
      const show = clamp01((take - 0.85) / 0.15);
      sBg.material.opacity = show; sFix.material.opacity = show;
      sPart.material.opacity = fresh * show;
      screen.visible = show > 0.001;
    },
  };
}

// ---------------------------------------------------------------- 3.7 Menschen im Arbeitsraum
function sheet37(api) {
  const L = api.ctx.data.lab3;
  if (!L) return;
  const cy = L.cycles;
  const markers = cy.filter((c) => /ArUco/.test(c.error)).length;
  const flipped = cy.filter((c) => /upside/i.test(c.error)).length;
  const stopped = cy.filter((c) => /stopped/i.test(c.error)).length;
  const W = 4.5, XS = X0 + 0.7, GAP = 0.5;
  const cx = (i) => XS + i * (W + GAP);
  const PY = 0.85;
  // Fall 1: Hand über Marker 2
  card(api, 0, L.photos?.hand, [cx(0) + W / 2, PY], 3.3, 0.02, { delay: 0.1 });
  note(api, 0, [cx(0), -0.85], `Marker verdeckt (${markers}×)`, 'Beim Nachlegen liegt eine Hand über Marker 2. Ohne alle vier Marker keine Entzerrung – die Erkennung bricht ab, statt eine ungenaue Pose zu liefern.', { hex: T.signal, width: W, delay: 0.3 });
  // Fall 2: Hand als Bauteil – kein Bild gespeichert, deshalb als Skizze
  const hx = cx(1) + W / 2, hy = PY;
  api.line(0, [[hx - 1.6, hy - 1.2], [hx + 1.6, hy - 1.2], [hx + 1.6, hy + 1.2], [hx - 1.6, hy + 1.2]], { closed: true, width: 1.2, hex: T.inkSoft }, { delay: 0.5 });
  fill(api, 0, [hx, hy], 3.2, 2.4, T.board, { delay: 0.5, dur: 0.5 }, { opacity: 0.9 });
  const hand = [[-1.6, 0.75], [-0.4, 0.45], [0.1, 0.4], [0.55, 0.3], [0.62, 0.12], [0.3, 0.05], [0.6, -0.05], [0.55, -0.22], [0.15, -0.2], [0.4, -0.35], [0.3, -0.5], [-0.2, -0.35], [-0.6, -0.15], [-1.6, -0.1]];
  api.line(0, hand.map(([x, y]) => [hx + x, hy + y, 0.01]), { width: 2, hex: '#E8D9C8' }, { delay: 0.7, dur: 0.6 });
  fill(api, 0, [hx + 0.62, hy - 0.42], 0.55, 0.3, T.part, { delay: 0.9 }, { z: 0.008 });
  api.line(0, [[hx - 0.75, hy - 0.62], [hx + 0.75, hy - 0.62], [hx + 0.75, hy + 0.55], [hx - 0.75, hy + 0.55]], { closed: true, width: 2.2, hex: T.signal, dashed: true }, { delay: 1.1 });
  api.text(0, 'erkannt: „Bauteil“', { font: 'monoMedium', size: 0.15, hex: T.signal }, [hx - 0.75, hy + 0.72], { delay: 1.2 });
  api.text(0, 'Skizze – kein Bild gespeichert', { font: 'mono', size: 0.12, hex: T.inkSoft, anchorX: 'center' }, [hx, hy - 1.38], { delay: 1.2 });
  note(api, 0, [cx(1), -0.85], `Hand als Bauteil (${stopped}×)`, 'Hell genug und groß genug: der Zyklus startet, LARA fährt los. Der Bediener hält sie im Anflug mit dem Software-Stopp an.', { hex: T.signal, width: W, delay: 1.2 });
  // Fall 3: Teil kopfüber
  card(api, 0, L.photos?.kopfueber, [cx(2) + W / 2, PY], 2.5, -0.02, { delay: 1.4 });
  note(api, 0, [cx(2), -0.85], 'Teil kopfüber', 'Zuerst gegriffen und richtig als SCHLECHT aussortiert – Etikett und Kerbe fehlen auf der Rückseite. Das Urteil stimmte, der Zyklus war unnötig.', { hex: T.signal, width: W, delay: 1.6 });
  // Schritt 1: aus jedem Fall eine Prüfung
  const sol = [
    ['Abbruch vor dem Greifen', 'Bleibt so gewollt. Dazu die Ruheprüfung: ein Zyklus startet erst, wenn der Arbeitsraum drei Aufnahmen lang unverändert ist.'],
    ['Form- und Ruheprüfung', 'Nur Konturen mit Maßen und Füllgrad des Bauteils zählen; solange sich etwas bewegt, startet kein Zyklus.'],
    ['Fasenseite prüfen', `Die Fase liegt immer auf derselben Seite der Längsachse. Gespiegelt → „bitte umdrehen“, bevor LARA fährt${flipped ? ` (${flipped}× ausgelöst)` : ''}.`],
  ];
  sol.forEach(([t, b], i) => {
    check(api, 1, [cx(i) + 0.22, -2.95], 0.2, { delay: 0.15 + i * 0.3 });
    note(api, 1, [cx(i) + 0.55, -2.8], t, b, { hex: T.good, width: W - 0.55, size: 0.24, delay: 0.2 + i * 0.3 });
  });
}

// ---------------------------------------------------------------- 3.8 Außerdem am Aufbau (M1)
function sheet38(api) {
  const L2 = api.ctx.data.lab2, L3 = api.ctx.data.lab3;
  // Schritt 0: Belichtung – Helligkeit V (0–255) von Platte und Teil
  const AX = X0 + 1.4, AY = -3.2, AH = 4.3, k = AH / 255;
  api.text(0, 'HELLIGKEIT IM BILD DER KAMERA OBEN (V, 0–255)', MONO, [X0 + 0.7, 2.6], { delay: 0.05 });
  api.line(0, [[AX, AY], [AX, AY + AH + 0.1]], { width: 1.2 }, { delay: 0.1 });
  api.line(0, [[AX, AY], [AX + 6.2, AY]], { width: 1.2 }, { delay: 0.1 });
  [0, 64, 128, 192, 255].forEach((v) => {
    api.line(0, [[AX - 0.08, AY + v * k], [AX, AY + v * k]], { width: 1.2 }, { delay: 0.12 });
    api.text(0, String(v), { font: 'mono', size: 0.13, anchorX: 'right' }, [AX - 0.14, AY + v * k], { delay: 0.12 });
  });
  api.line(0, [[AX, AY + AH], [AX + 6.2, AY + AH]], { width: 1, hex: T.signal, dashed: true }, { delay: 0.2 });
  api.text(0, 'Sättigung', { font: 'mono', size: 0.13, hex: T.signal, anchorX: 'right', anchorY: 'bottom' }, [AX + 6.2, AY + AH + 0.05], { delay: 0.2 });
  const bar = (x, v, hex, label, d) => {
    const h = v * k;
    fill(api, 0, [x, AY + h / 2], 0.7, h, hex, { delay: d, dur: 0.6 });
    api.text(0, label, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorX: 'center', anchorY: 'top' }, [x, AY - 0.12], { delay: d });
  };
  api.text(0, 'Automatik', { font: 'sansMedium', size: 0.22, hex: T.signal, anchorX: 'center' }, [AX + 1.4, AY + AH + 0.45], { delay: 0.3 });
  bar(AX + 1.4, 255, T.part, 'Teil', 0.35);
  api.text(0, 'weiß, übersteuert', { font: 'monoMedium', size: 0.14, hex: T.signal, anchorX: 'center', anchorY: 'bottom' }, [AX + 1.4, AY + AH + 0.08], { delay: 0.8 });
  const exp = fmt((L2?.exposure_us ?? 15000) / 1000, 0);
  api.text(0, `fest ${exp} ms, 0 dB`, { font: 'sansMedium', size: 0.22, hex: T.good, anchorX: 'center' }, [AX + 4.4, AY + AH + 0.45], { delay: 0.6 });
  bar(AX + 3.9, 40, T.board, 'Platte', 0.7);
  bar(AX + 4.9, 190, T.part, 'Teil', 0.8);
  api.line(0, [[AX + 3.5, AY + 40 * k], [AX + 5.3, AY + 40 * k]], { width: 1, hex: T.inkSoft, dashed: true }, { delay: 1.1 });
  api.text(0, '150', { font: 'monoMedium', size: 0.16, hex: T.good }, [AX + 5.4, AY + 115 * k], { delay: 1.2 });
  arrow(api, 0, [AX + 5.35, AY + 45 * k], [AX + 5.35, AY + 185 * k], { width: 1.2, hex: T.good }, { delay: 1.2 });
  note(api, 0, [0.6, 2.6], 'Belichtungsautomatik', 'Die dunkle Platte füllt fast das ganze Bild – die Automatik belichtet viel zu lang. Das Teil wird weiß, Kratzer und Schlieren landen in der Maske.', { hex: T.signal, width: 6.6, delay: 0.4 });
  note(api, 0, [0.6, 1.0], 'Fest eingestellt', 'Belichtungsreihe am Aufbau: Platte V 40, Teil V 190 – nichts übersteuert, die Trennung ist eindeutig.', { hex: T.good, width: 6.6, delay: 1.0 });
  // Schritt 1: Bilanz M1 vom 26.11.
  if (!L3) return;
  const cy = L3.cycles;
  const empty = cy.filter((c) => c.ok && !c.part).length;
  const full = cy.filter((c) => c.hole_mm != null).length;
  const aborts = cy.filter((c) => !c.ok).length;
  const before = cy.filter((c) => !c.ok && /^DETECT/.test(c.error)).length;
  api.text(1, `BILANZ M1 AM ${day(L3.date)}`, MONO, [0.6, -0.55], { delay: 0.05 });
  const figs = [
    [`${full}`, 'Zyklen: erkannt\nund gegriffen'],
    [`${empty}`, 'Abfragen ohne Teil,\nkein Fehlstart'],
    [`${before} / ${aborts}`, 'Abbrüche, bevor\nLARA sich bewegt'],
  ];
  figs.forEach(([big, small], i) => {
    const x = 0.6 + i * 2.3;
    api.text(1, big, { font: 'title', size: 0.5 }, [x, -1.1], { delay: 0.15 + i * 0.15 });
    api.text(1, small, { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', lineHeight: 1.3 }, [x, -1.5], { delay: 0.2 + i * 0.15 });
  });
  api.stamp(1, 'KEINE FALSCHE POSE', [3.4, -3.05], { size: 0.32, rot: -0.03, hex: T.good, sub: 'kein Teil daneben gegriffen' }, { delay: 0.8 });
}

// ---------------------------------------------------------------- 4.8 Am Aufbau (M2)
function sheet48(api) {
  const cfg = api.ctx.data.config.robot;
  const lab = api.ctx.data.lab;
  // Panel A: Greifer 23° verdreht (Draufsicht auf den Flansch)
  const AXc = X0 + 2.2, CY = 1.2, R = 0.95;
  api.text(0, `${lab ? day(lab.date) : '06.10.'}`, { font: 'monoMedium', size: 0.18, hex: T.signal }, [X0 + 0.7, 2.6]);
  api.line(0, circ(AXc, CY, R), { closed: true, width: 1.6 }, { delay: 0.1 });
  api.line(0, [[AXc - R - 0.25, CY], [AXc + R + 0.25, CY]], { width: 1, hex: T.inkSoft, dashed: true }, { delay: 0.2 });
  const jaw = (s, a) => [[-0.18, s * 0.28], [0.18, s * 0.28], [0.18, s * 0.62], [-0.18, s * 0.62]].map((p) => rot(p, a)).map(([x, y]) => [AXc + x, CY + y]);
  const A23 = (23 * Math.PI) / 180;
  [1, -1].forEach((s) => api.line(0, jaw(s, Math.PI / 2 + A23 - Math.PI / 2), { closed: true, width: 2.2, hex: MODULE_COLOR.M2 }, { delay: 0.4 }));
  api.line(0, [rot([0, -R - 0.2], A23).map((v, i) => v + [AXc, CY][i]), rot([0, R + 0.2], A23).map((v, i) => v + [AXc, CY][i])], { width: 1, hex: MODULE_COLOR.M2 }, { delay: 0.45 });
  api.line(0, arcPts(AXc, CY, 0.75, Math.PI / 2, Math.PI / 2 + A23), { width: 1.4, hex: T.signal }, { delay: 0.6 });
  api.text(0, '23°', { font: 'monoMedium', size: 0.2, hex: T.signal, anchorX: 'right' }, [AXc - 0.5, CY + 1.05], { delay: 0.65 });
  note(api, 0, [X0 + 0.7, -0.15], 'Greifer verdreht montiert', 'Die Backen stehen 23° schräg zum Flansch. Offset 90° → 113°, die 23° stecken in jeder Pose.', { hex: T.signal, width: 4.2, size: 0.24, delay: 0.7 });
  // Panel B/C: Zifferblatt Achse 6
  const BXc = -0.3;
  api.text(0, '12.11.', { font: 'monoMedium', size: 0.18, hex: T.signal }, [BXc - 2.0, 2.6], { delay: 0.8 });
  api.line(0, circ(BXc, CY, R), { closed: true, width: 1.6 }, { delay: 0.9 });
  [0, 90, 180, 270].forEach((d) => {
    const a = (d * Math.PI) / 180;
    api.line(0, [[BXc + Math.cos(a) * (R - 0.12), CY + Math.sin(a) * (R - 0.12)], [BXc + Math.cos(a) * R, CY + Math.sin(a) * R]], { width: 1.4 }, { delay: 0.95 });
  });
  api.text(0, '0°', { font: 'mono', size: 0.13, hex: T.inkSoft }, [BXc + R + 0.08, CY], { delay: 1.0 });
  api.text(0, '180°', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'right' }, [BXc - R - 0.08, CY], { delay: 1.0 });
  api.text(0, 'ACHSE 6', MONO, [BXc - 0.4, CY - R - 0.3], { delay: 1.0 });
  const needle = (deg, hex, step, timing) => {
    const a = (deg * Math.PI) / 180;
    return api.line(step, [[BXc, CY], [BXc + Math.cos(a) * (R - 0.18), CY + Math.sin(a) * (R - 0.18)]], { width: 3, hex }, timing);
  };
  const n178 = needle(178, T.signal, 0, { delay: 1.1 });
  const l178 = api.text(0, '178°', { font: 'monoMedium', size: 0.2, hex: T.signal, anchorX: 'right' }, [BXc - 0.35, CY + 0.25], { delay: 1.2 });
  note(api, 0, [BXc - 2.0, -0.15], 'Achse 6 bei 178°', 'Mit Seriennummer zur Kamera stand Achse 6 bei 178°: von dort keine IK-Lösung zu den Ablagen – oder die Steuerung klappte um.', { hex: T.signal, width: 4.2, size: 0.24, delay: 1.2 });
  // Schritt 1: Teil um 180° gedreht greifen
  api.fade(1, [n178, l178], { dur: 0.4 });
  api.line(1, arcPts(BXc, CY, R - 0.32, Math.PI * (178 / 180), Math.PI * (-2 / 180) + 0.0001, 40), { width: 1.4, hex: T.good, dashed: true }, { delay: 0.2, dur: 0.8 });
  needle(-2, T.good, 1, { delay: 0.9 });
  const off = cfg.gripper_angle_offset_deg;
  note(api, 1, [3.1, 2.65], 'Um 180° gedreht greifen', `Offset ${fmt(off, 0)}° = 90° + 23° − 180°. Achse 6 steht jetzt nahe 0°, alle Ablagen sind erreichbar – und Fase und Seriennummer zeigen trotzdem zur Seitenkamera.`, { hex: T.good, width: 4.3, size: 0.24, delay: 0.6 });
  // Ablegen: 8 mm → 1 mm
  const DX = 0.2, DY = -3.0;
  api.line(0, [[DX, DY], [DX + 2.2, DY]], { width: 2.6 }, { delay: 1.4 });
  api.text(0, 'Prüfstation', { font: 'mono', size: 0.13, hex: T.inkSoft }, [DX, DY - 0.2], { delay: 1.4 });
  const partOld = fill(api, 0, [DX + 1.1, DY + 0.8 + 0.25], 1.2, 0.5, T.part, { delay: 1.5 });
  const dimOld = api.line(0, [[DX + 2.0, DY], [DX + 2.0, DY + 0.8]], { width: 1.4, hex: T.signal }, { delay: 1.6 });
  const tOld = api.text(0, '8 mm: fällt hörbar', { font: 'monoMedium', size: 0.16, hex: T.signal }, [DX + 2.1, DY + 0.4], { delay: 1.6 });
  note(api, 0, [X0 + 0.7, -1.6], 'Sanft ablegen', 'Die Posen sind mit aufsitzendem Teil geteacht. Öffnet der Greifer 8 mm darüber, fällt das Teil hörbar auf die Prüfstation.', { hex: T.signal, width: 6.4, size: 0.24, delay: 1.5 });
  api.fade(1, [dimOld, tOld], { dur: 0.4 });
  api.add(1, (v) => { partOld.material.opacity *= 1 - v; partOld.visible = partOld.material.opacity > 0.001; }, { dur: 0.4 });
  fill(api, 1, [DX + 1.1, DY + 0.1 + 0.25], 1.2, 0.5, T.part, { delay: 1.1 });
  api.text(1, `${cfg.place_height_mm ?? 1} mm`, { font: 'monoMedium', size: 0.16, hex: T.good }, [DX + 2.1, DY + 0.12], { delay: 1.2 });
  api.text(1, `place_height_mm = ${cfg.place_height_mm ?? 1}`, { font: 'mono', size: 0.15, hex: T.good }, [X0 + 0.7, -2.95], { delay: 1.2 });
  api.stamp(1, 'ALLES IN DER KONFIGURATION', [5.0, -1.9], { size: 0.26, rot: -0.03, hex: T.good, sub: 'gripper_angle_offset_deg · place_height_mm' }, { delay: 1.5 });
}

// ---------------------------------------------------------------- 5.7 Die echte Kamera
function sheet57(api) {
  const W = 4.5, XS = X0 + 0.7, GAP = 0.5;
  const cx = (i) => XS + i * (W + GAP);
  const BY = 1.35, BH = 1.9;
  const frame = (i, d) => api.line(0, [[cx(i), BY - BH / 2], [cx(i) + W, BY - BH / 2], [cx(i) + W, BY + BH / 2], [cx(i), BY + BH / 2]], { closed: true, width: 1.2, hex: T.inkSoft }, { delay: d });
  // 1: Autofokus – unscharfe Ziffern als mehrfach versetzte Schrift
  frame(0, 0.05);
  const m0 = cx(0) + W / 2;
  const blur = [];
  [[-0.06, 0.03], [0.05, -0.04], [0.02, 0.06], [-0.04, -0.05], [0.07, 0.01]].forEach(([dx, dy], k) =>
    blur.push(api.text(0, '69420', { font: 'title', size: 0.62, hex: T.ink, anchorX: 'center', opacity: 0 }, [m0 + dx, BY + dy], { delay: 0.15 + k * 0.03 })));
  api.text(1, '69420', { font: 'title', size: 0.62, hex: T.ink, anchorX: 'center' }, [m0, BY], { delay: 0.3 });
  note(api, 0, [cx(0), -0.05], 'Unscharf', 'Die Logitech-Kamera startet im Autofokus und stellt auf den Hintergrund scharf – die Ziffern verschwimmen.', { hex: T.signal, width: W, delay: 0.3 });
  // 2: Rahmen wächst bis zum Bildrand
  frame(1, 0.4);
  const m1 = cx(1) + W / 2;
  fill(api, 0, [m1, BY - 0.15], 2.2, 0.75, T.part, { delay: 0.5 }, { opacity: 0.85 });
  api.line(0, circ(m1 + 0.4, BY - 0.15, 0.2), { closed: true, width: 1.6, hex: T.ink }, { delay: 0.55 });
  const grow = api.line(0, [[cx(1) + 0.05, BY - 0.6], [cx(1) + W - 0.05, BY - 0.6], [cx(1) + W - 0.05, BY + BH / 2 - 0.05], [cx(1) + 0.05, BY + BH / 2 - 0.05]], { closed: true, width: 2.4, hex: T.signal, dashed: true }, { delay: 0.8, dur: 0.6 });
  api.text(0, 'Box bis zum Rand → Loch 6,7 statt 9,5 mm', { font: 'monoMedium', size: 0.13, hex: T.signal }, [cx(1) + 0.1, BY + BH / 2 + 0.18], { delay: 1.0 });
  note(api, 0, [cx(1), -0.05], 'Rahmen bis zum Bildrand', 'Beim Schließen der Maske wertet OpenCV am Bildrand alles als Teil. Die Box wird zu groß, der Maßstab mm/px falsch.', { hex: T.signal, width: W, delay: 0.9 });
  // 3: Kerbe dunkler – Helligkeitsprofil über die Fläche
  frame(2, 0.8);
  const PX0 = cx(2) + 0.3, PX1 = cx(2) + W - 0.3, PY0 = BY - 0.7;
  const prof = Array.from({ length: 41 }, (_, j) => {
    const u = j / 40;
    const x = PX0 + u * (PX1 - PX0);
    const y = PY0 + 1.2 - 0.55 * u - (u > 0.7 && u < 0.85 ? 0.75 : 0);
    return [x, y];
  });
  api.line(0, prof, { width: 2, hex: T.ink }, { delay: 1.0, dur: 0.6 });
  api.text(0, 'Helligkeit über die Fläche → Kerbe', { font: 'monoMedium', size: 0.13, hex: T.inkSoft }, [cx(2) + 0.1, BY + BH / 2 + 0.18], { delay: 1.0 });
  api.line(0, [[PX0, PY0 + 0.75], [PX1, PY0 + 0.75]], { width: 1.4, hex: T.signal, dashed: true }, { delay: 1.3 });
  api.text(0, 'eine Schwelle für alles', { font: 'monoMedium', size: 0.13, hex: T.signal, anchorY: 'top' }, [PX0, PY0 + 0.68], { delay: 1.3 });
  note(api, 0, [cx(2), -0.05], 'Kerbe im Dunkeln', 'Zur Kerbe hin wird die Fläche dunkler. Mit einer gemeinsamen Schwelle gehört der halbe Rand schon zur „Kerbe“.', { hex: T.signal, width: W, delay: 1.3 });
  // Schritt 1: Lösungen
  api.fade(1, blur, { dur: 0.3 });
  api.fade(1, [grow], { dur: 0.3 });
  api.line(1, [[m1 - 1.12, BY - 0.54], [m1 + 1.12, BY - 0.54], [m1 + 1.12, BY + 0.24], [m1 - 1.12, BY + 0.24]], { closed: true, width: 2.4, hex: T.good }, { delay: 0.6 });
  api.line(1, [[PX0 + 0.7 * (PX1 - PX0), PY0 + 0.2], [PX1, PY0 + 0.2]], { width: 1.6, hex: T.good }, { delay: 0.9 });
  const sols = [
    ['Fokus fest', 'Im Programm gesetzt (focus 90), bei jedem Start gleich.'],
    ['Rand vor dem Schließen auffüllen', 'Die Maske bekommt einen schwarzen Rand, die Box liegt wieder eng am Teil.'],
    ['Eigene Schwelle für die Kerbe', 'Relativ zum Rand der Kerben-ROI (75 %) statt einer Schwelle für das ganze Teil.'],
  ];
  sols.forEach(([t, b], i) => {
    check(api, 1, [cx(i) + 0.22, -2.55], 0.2, { delay: 0.3 + i * 0.3 });
    note(api, 1, [cx(i) + 0.55, -2.4], t, b, { hex: T.good, width: W - 0.55, size: 0.24, delay: 0.35 + i * 0.3 });
  });
}

// ---------------------------------------------------------------- 5.8 Loch zu klein (12.11.)
function sheet58(api) {
  const L = api.ctx.data.lab2;
  if (!L) return;
  const full = L.cycles.filter((c) => c.ok);
  const good = full.filter((c) => c.good).length;
  const nom = L.hole_nominal_mm, tol = L.hole_tolerance_mm;
  api.row(0, 1, 'Die Kette läuft durch', `${day(L.date)}: Seriennummer und Kerbe in allen ${full.length} vollständigen Zyklen erkannt – aber nur ${good} von ${full.length} als Gutteil sortiert.`, 2.65, { x: X0 + 0.7, width: 6.6, size: 0.3, delay: 0.1 });
  const A0 = 9.3, A1 = 10.6, AX = X0 + 0.9, AW = 6.8, AY = -0.4;
  const X = (v) => AX + ((v - A0) / (A1 - A0)) * AW;
  api.text(0, 'LOCHDURCHMESSER JE ZYKLUS (mm)', MONO, [AX, 0.75], { delay: 0.3 });
  api.line(0, [[X(nom - tol), AY], [X(nom + tol), AY]], { width: 26, hex: '#D6EBD8' }, { delay: 0.35 });
  api.line(0, [[X(A0), AY - 0.45], [X(A1), AY - 0.45]], { width: 1.2 }, { delay: 0.35 });
  [9.4, 9.6, 9.8, 10.0, 10.2, 10.4].forEach((v) => {
    api.line(0, [[X(v), AY - 0.52], [X(v), AY - 0.38]], { width: 1.2 }, { delay: 0.4 });
    api.text(0, fmt(v, 1), { font: 'mono', size: 0.15, anchorX: 'center', anchorY: 'top' }, [X(v), AY - 0.62], { delay: 0.4 });
  });
  api.text(0, `Toleranz ${fmt(nom, 0)} ± ${fmt(tol, 1)} mm`, { font: 'sans', size: 0.18, hex: T.good, anchorX: 'center' }, [X(nom), AY + 0.35], { delay: 0.45 });
  full.forEach((c, i) => {
    const y = AY + 0.18 - (i % 3) * 0.17;
    api.line(0, circ(X(c.hole_mm), y, 0.07, 13), { closed: true, width: 2.6, hex: c.good ? T.good : T.signal }, { delay: 0.6 + i * 0.12, dur: 0.3 });
  });
  const holes = full.map((c) => c.hole_mm);
  const lo = Math.min(...holes), hi = Math.max(...holes);
  api.text(0, `Alle ${holes.length} Messungen ${fmt(lo, 2)}–${fmt(hi, 2)} mm: gut wiederholbar, aber rund ${fmt((1 - (lo + hi) / 2 / nom) * 100, 0)} % zu klein – knapp an der Grenze.`, { font: 'sans', size: 0.21, anchorY: 'top', maxWidth: 6.8, lineHeight: 1.3 }, [AX, AY - 1.05], { delay: 1.1 });
  card(api, 0, L.photos?.m3_live, [4.0, 0.9], 6.0, -0.02, { delay: 0.5 });
  // Schritt 1: Ursache
  api.line(1, circ(5.14, 0.2, 0.5).map(([x, y]) => [x, y, 0.12]), { closed: true, width: 2.8, hex: T.signal }, { delay: 0.1, dur: 0.6 });
  api.row(1, 2, 'Spiegelung in der Bohrung', 'Fensterlicht fällt in das Loch. Die helle Bohrungswand sieht aus wie die Seitenfläche – die Kontur läuft unten nach innen.', -2.75, { x: 0.6, width: 6.6, size: 0.28, delay: 0.4 });
  api.stamp(1, 'SPIEGELUNG IM LOCH', [-3.6, -3.5], { size: 0.3, rot: 0.04, hex: T.signal, sub: 'am Testbild nicht da' }, { delay: 0.9 });
}

// ---------------------------------------------------------------- 7.1 Drei Labortage
function sheet71t(api) {
  const L2 = api.ctx.data.lab2, L3 = api.ctx.data.lab3;
  // drei Spalten im gleichen Abstand (nicht maßstäblich); M4-Tage anteilig zwischen 06.10. und 12.11.
  const COL = [X0 + 0.85, -0.95, 4.05], CW = 3.9, AY = 0.05;
  const dd = (iso) => (Date.parse(iso) - Date.parse('2026-10-06')) / 864e5;
  const between = (iso) => COL[0] + (dd(iso) / dd('2026-11-12')) * (COL[1] - COL[0]);
  api.line(0, [[COL[0] - 0.4, AY], [-X0 - 0.2, AY]], { width: 2 }, { delay: 0.05, dur: 1.0 });
  api.text(0, 'nicht maßstäblich', { font: 'mono', size: 0.12, hex: T.inkSoft, anchorX: 'right', anchorY: 'top' }, [-X0 - 0.2, AY - 0.12], { delay: 0.5 });
  [['2026-10-16', 'M4: Zittern gemessen'], ['2026-10-26', 'M4: Punkte geteacht']].forEach(([d, t], i) => {
    const x = between(d);
    api.line(0, circ(x, AY, 0.08, 16), { closed: true, width: 1.8, hex: MODULE_COLOR.M4 }, { delay: 0.6 + i * 0.1 });
    api.text(0, day(d), { font: 'monoMedium', size: 0.13, hex: MODULE_COLOR.M4, anchorX: 'center', anchorY: 'bottom' }, [x, AY + 0.18], { delay: 0.65 + i * 0.1 });
    api.text(0, t, { font: 'mono', size: 0.12, hex: MODULE_COLOR.M4, anchorX: 'center', anchorY: 'top' }, [x, AY - 0.2 - i * 0.22], { delay: 0.65 + i * 0.1 });
  });
  const main = (step, i, iso, head, big, body, hex) => {
    const x = COL[i];
    api.line(step, circ(x, AY, 0.14, 20), { closed: true, width: 2.6, hex }, { delay: 0.05 });
    api.text(step, day(iso), { font: 'monoMedium', size: 0.22, hex, anchorX: 'center', anchorY: 'bottom' }, [x, AY + 0.25], { delay: 0.1 });
    api.text(step, big, { font: 'title', size: 0.55, hex, anchorY: 'top' }, [x - 0.15, AY - 0.75], { delay: 0.5 });
    api.text(step, head, { font: 'sansMedium', size: 0.24, anchorY: 'top', maxWidth: CW }, [x - 0.15, AY - 1.5], { delay: 0.55 });
    api.text(step, body, { font: 'sans', size: 0.19, hex: T.inkSoft, anchorY: 'top', maxWidth: CW, lineHeight: 1.3 }, [x - 0.15, AY - 1.9], { delay: 0.6 });
  };
  main(0, 0, '2026-10-06', 'Erster Ablauf am Roboter', '1. Ablauf', 'Posen geteacht, Kalibrierung eingemessen. M1 und M3 noch mit Testbildern, Greifer nicht angesteuert.', T.ink);
  api.stamp(0, 'OHNE KAMERAS', [COL[0] + 1.6, 1.75], { size: 0.28, rot: -0.05, hex: T.inkSoft, sub: 'und ohne Greifer' }, { delay: 0.9 });
  if (L2) {
    const full = L2.cycles.filter((c) => c.ok);
    main(1, 1, L2.date, 'Erstmals mit Kameras und Greifer', `${L2.cycles.length} Zyklen`, `Alle gegriffen und abgelegt, ${full.length} vollständig geprüft – nur ${full.filter((c) => c.good).length} als Gutteil: das Loch wurde zu klein gemessen.`, MODULE_COLOR.M2);
    card(api, 1, L2.photos?.anlage, [COL[1] + 1.7, 1.75], 1.3, 0.04, { delay: 0.3 });
  }
  if (L3) {
    const full = L3.cycles.filter((c) => c.hole_mm != null).length;
    main(2, 2, L3.date, 'Dauerbetrieb', `${full} Zyklen`, 'Das System wartet selbst auf das nächste Teil. Fehlerfälle abgefangen, kein Teil falsch sortiert.', T.good);
    card(api, 2, L3.photos?.gui, [COL[2] + 2.1, 1.65], 2.9, -0.03, { delay: 0.3 });
  }
}

// ---------------------------------------------------------------- 7.2 Was der Aufbau uns gelehrt hat
function sheet72t(api) {
  const rows = [
    ['ORCH', 'Altes Bild nach einer Pause', 'Kamera puffert, das älteste Bild kommt zuerst', 'Puffer vor jeder Aufnahme leeren', '2.5'],
    ['M1', 'Teil weiß übersteuert', 'Belichtungsautomatik auf dunkler Platte', 'Belichtung fest eingestellt', '3.8'],
    ['M1', 'Mitte bis 8 mm zu weit außen', 'Parallaxe der Oberseite, Objektiv unkalibriert', 'Lineare Korrektur: höchstens 2 mm', '3.6'],
    ['M1', 'Hand, verdeckter Marker, Teil kopfüber', 'Ein Mensch legt im Dauerbetrieb nach', 'Ruhe-, Form- und Fasenprüfung', '3.7'],
    ['M2', 'Keine IK-Lösung zu den Ablagen', 'Achse 6 bei 178°', 'Teil um 180° gedreht greifen', '4.8'],
    ['M2', 'Teil fällt auf die Prüfstation', 'Posen mit aufsitzendem Teil geteacht', 'Greifer öffnet 1 mm darüber', '4.8'],
    ['M3', 'Unscharf, Loch 6,7 statt 9,5 mm', 'Autofokus; Maske am Bildrand geschlossen', 'Fokus fest; Rand vor dem Schließen auffüllen', '5.7'],
    ['M3', 'Loch knapp zu klein', 'Spiegelung in der Bohrung', 'Kreis-Fit ohne die inneren Punkte', '5.9'],
    ['M4', 'Arm zittert', '60 Sollwerte je Sekunde werden zur Treppe', 'servo_j mit Override 0,5', '6.6'],
    ['M4', 'Greifpunkt im Median 8,7 mm daneben', 'Policy aus der Simulation, nur aus dem Zustand gelernt', 'offen: Training mit Daten der Anlage', '6.5'],
  ];
  const C = [X0 + 0.7, X0 + 1.7, X0 + 5.6, X0 + 10.0, X0 + 14.1];
  const Y0 = 2.35, DY = 0.6;
  ['MODUL', 'AM AUFBAU', 'URSACHE', 'LÖSUNG', 'SZENE'].forEach((h, j) => api.text(j < 2 ? 0 : 1, h, MONO, [C[j], Y0 + 0.3], { delay: 0.05 }));
  api.text(0, 'SZENE', MONO, [C[4], Y0 + 0.3], { delay: 0.05 });
  rows.forEach(([m, p, u, l, sc], i) => {
    const y = Y0 - 0.15 - i * DY;
    const d0 = 0.15 + i * 0.1;
    if (i > 0 && rows[i - 1][0] !== m) api.line(0, [[C[0], y + 0.3], [-X0 - 0.2, y + 0.3]], { width: 0.8, hex: T.inkFaint }, { delay: d0 });
    api.text(0, m === 'ORCH' ? 'Ablauf' : m, { font: 'monoMedium', size: 0.17, hex: MODULE_COLOR[m] }, [C[0], y], { delay: d0 });
    api.text(0, p, { font: 'sansMedium', size: 0.19, hex: T.signal, maxWidth: 3.8 }, [C[1], y], { delay: d0 });
    api.text(0, sc, { font: 'mono', size: 0.16, hex: T.inkSoft }, [C[4], y], { delay: d0 });
    const d1 = 0.15 + i * 0.12;
    api.text(1, u, { font: 'sans', size: 0.18, hex: T.inkSoft, maxWidth: 4.3 }, [C[2], y], { delay: d1 });
    api.text(1, l, { font: 'sansMedium', size: 0.19, hex: l.startsWith('offen') ? T.inkSoft : T.good, maxWidth: 4.0 }, [C[3], y], { delay: d1 + 0.05 });
  });
  api.text(1, 'Keiner dieser Fehler zeigte sich an Testbildern oder im Simulator – sie kamen erst mit echtem Licht, echter Mechanik und Menschen im Arbeitsraum.', { font: 'sans', size: 0.21, anchorY: 'top', maxWidth: 14.4 }, [X0 + 0.7, -3.75], { delay: 1.5 });
}

// ---------------------------------------------------------------- 7.3 Bilanz 26.11.
function sheet73b(api) {
  const L = api.ctx.data.lab3;
  if (!L) return;
  const cy = L.cycles;
  const empty = cy.filter((c) => c.ok && !c.part).length;
  const full = cy.filter((c) => c.hole_mm != null);
  const fast = full.map((c) => c.duration_s).filter((d) => d > 30 && d < 50);
  const after = full.filter((c) => c.serial && c.time >= '10:20');
  const aborts = cy.filter((c) => !c.ok).length;
  const figs = [
    [`${full.length}`, 'Zyklen erkannt, gegriffen,\ngeprüft und einsortiert', T.ink],
    [`${after.filter((c) => c.good).length} / ${after.length}`, 'Gutteile als GUT sortiert\n(nach dem Kreis-Fit)', T.good],
    [`${empty}`, 'Abfragen ohne Teil –\nkein Zyklus ausgelöst', T.ink],
    [`${aborts}`, 'Abbrüche, alle\nvor dem Greifen', T.ink],
    [fast.length ? `${fmt(median(fast), 0)} s` : '–', 'je Zyklus (Median),\nbewusst langsam', T.ink],
  ];
  figs.forEach(([big, small, hex], i) => {
    const x = X0 + 0.7 + (i % 2) * 3.4;
    const y = 2.45 - Math.floor(i / 2) * 1.75;
    api.text(0, big, { font: 'title', size: 0.62, hex, anchorY: 'top' }, [x, y], { delay: 0.1 + i * 0.15 });
    api.text(0, small, { font: 'sans', size: 0.19, hex: T.inkSoft, anchorY: 'top', lineHeight: 1.3 }, [x, y - 0.8], { delay: 0.15 + i * 0.15 });
  });
  card(api, 0, L.photos?.gui, [3.95, 0.45], 6.9, -0.02, { delay: 0.3 });
  api.text(0, 'Bedienoberfläche nach einem Zyklus am Aufbau: alle Schritte grün, Urteil GUTTEIL', { font: 'mono', size: 0.13, hex: T.inkSoft, anchorX: 'center' }, [3.95, -1.95], { delay: 0.6 });
  api.stamp(1, 'KEIN TEIL FALSCH SORTIERT', [3.85, -3.1], { size: 0.34, rot: -0.04, hex: T.good, sub: `${day(L.date)} · logs/cycles_20261126.csv` }, { delay: 0.2 });
}

export function aufbauScenes(storyboard) {
  const e = (id) => storyboard.find((s) => s.id === id);
  return [
    sheetScene(e('1.7'), 2, sheet17, { durations: [2.2, 2.0] }),
    sheetScene(e('2.5'), 2, sheet25, { durations: [3.6, 2.6] }),
    sheetScene(e('3.7'), 2, sheet37, { durations: [2.4, 1.8] }),
    sheetScene(e('3.8'), 2, sheet38),
    sheetScene(e('4.8'), 2, sheet48, { durations: [2.2, 2.0] }),
    sheetScene(e('5.7'), 2, sheet57, { durations: [2.0, 1.8] }),
    sheetScene(e('5.8'), 2, sheet58),
    sheetScene(e('7.1'), 3, sheet71t),
    sheetScene(e('7.2'), 2, sheet72t, { durations: [1.8, 2.2] }),
    sheetScene(e('7.3'), 2, sheet73b),
  ];
}
