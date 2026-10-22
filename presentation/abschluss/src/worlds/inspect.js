// Akt 5 (M3 Sichtprüfung): Seitenkamera → Blitz → echtes Seitenbild → Bauteil finden (Masken) → Box und ROIs →
// Detailblätter Seriennummer, Loch (mit Maßstab über die Bauteilhöhe), Kerbe → drei Prüfungen, ein Urteil:
// GUT; übermalte Kerbe → SCHLECHT. Die Detailblätter liegen unter dem Foto (BOARD), die Kamera fährt hin.
// Alle Werte und Zwischenbilder aus data.json (build_data.py, InspectionPipeline mit EasyOCR auf den Testbildern).
import * as THREE from 'three';
import { T, EASE, MODULE_COLOR, color } from '../theme.js';
import { makeWorldScene } from '../engine/stage.js';
import { InkLine, Dimension, PhotoCard, text, tex, v3 } from '../kit/ink.js';
import { Stamp } from '../kit/sheet.js';
import { clamp01 } from '../kit/tiles.js';
import { note as makeNote } from '../kit/note.js';
import { arrowPts } from '../kit/geom.js';

const PW = 13.5; // Fotobreite (zentriert)
const PY = 0.2;
const SMALL = { x: 4.3, y: -0.2, s: 0.53 }; // Lage des Fotos in 5.1
const M3 = MODULE_COLOR.M3;
const BOARD = { ocr: -12, hole: -24, notch: -36, notchAll: -46 }; // Detailblätter 5.3–5.5 (y der Blattmitte)

const DEFAULTS = {
  sketch: 0, photo: 0, // 5.1
  center: 0, seg: 0, box: 0, rois: 0, // 5.2
  dOcr: 0, dOcr2: 0, // 5.3
  dHole: 0, dHole2: 0, // 5.4
  dNotch: 0, dNotchE: 0, dNotchC: 0, dNotch2: 0, // 5.5
  ocr: 0, hole: 0, notch: 0, good: 0, bad: 0, // 5.6
};

const fmt = (v, d = 1) => v.toFixed(d).replace('.', ',');

export function createInspect(ctx) {
  const m3 = ctx.data.m3;
  const shot = m3.shots[m3.hero];
  const bad = m3.bad;
  const ic = ctx.data.config.inspection;
  const scene = makeWorldScene();
  const S = { ...DEFAULTS };
  const note = (...a) => makeNote(scene, ...a);

  // ---------- 5.1 Seitenriss: Prüfvorrichtung und Seitenkamera (schematisch) ----------
  const sketch = [];
  const SL = (pts, o = {}) => {
    const l = new InkLine(pts.map((p) => v3(p[0], p[1], 0.01)), { width: 1.5, progress: 0, ...o });
    sketch.push(l);
    scene.add(l.object);
    return l;
  };
  const TY = -2.6;
  SL([[-8.8, TY], [-1.0, TY]], { width: 2 });
  SL([[-7.6, TY], [-7.6, -1.4], [-5.6, -1.4], [-5.6, TY]], { width: 1.8 }); // Vorrichtung
  SL([[-7.45, -1.4], [-7.45, -0.95], [-5.75, -0.95], [-5.75, -1.4]], { hex: T.part, width: 2.2 }); // Bauteil
  SL([[-2.0, TY], [-2.0, -1.4]], { width: 2 }); // Stativ
  SL([[-2.35, -1.4], [-1.65, -1.4], [-1.65, -0.9], [-2.35, -0.9]], { closed: true, width: 2 }); // Kamera
  SL([[-2.35, -1.05], [-2.55, -1.0], [-2.55, -1.3], [-2.35, -1.25]], { closed: true, width: 1.5 }); // Objektiv
  SL([[-2.55, -1.15], [-7.6, -0.55]], { dashed: true, width: 1, hex: M3 });
  SL([[-2.55, -1.15], [-7.6, -1.75]], { dashed: true, width: 1, hex: M3 });
  const sketchTexts = [
    [text('Seitenkamera M3', { font: 'title', size: 0.3, anchorY: 'bottom', opacity: 0 }), -5.2, 1.0],
    [text('blickt auf Etikett, Loch und Kerbe', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', opacity: 0 }), -5.2, 0.9],
    [text('Prüfposition', { font: 'mono', size: 0.18, anchorX: 'center', anchorY: 'top', opacity: 0 }), -6.6, TY - 0.15],
    [text('Seitenriss, schematisch – Lage angenommen', { font: 'mono', size: 0.15, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 }), -4.9, TY - 0.5],
  ];
  sketchTexts.forEach(([t, x, y]) => {
    t.position.set(x, y, 0.01);
    scene.add(t);
  });

  // ---------- Foto (gut und mit übermalter Kerbe) ----------
  const [iw, ih] = shot.photo_size;
  const PH = (PW * ih) / iw;
  const Pp = ([u, v], z = 0.02) => v3((u - 0.5) * PW, -(v - 0.5) * PH + PY, z);
  const photoGroup = new THREE.Group();
  const card = new THREE.Mesh(new THREE.PlaneGeometry(PW + 0.45, PH + 0.45), new THREE.MeshBasicMaterial({ color: 0xfbfaf6, transparent: true, depthWrite: false }));
  card.position.set(0, PY, 0.004);
  const mk = (url) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(PW, PH), new THREE.MeshBasicMaterial({ map: tex(url), transparent: true, toneMapped: false, depthWrite: false }));
    m.position.set(0, PY, 0.008);
    m.renderOrder = 1;
    return m;
  };
  const photoGood = mk(shot.photo);
  const photoBad = mk(bad.photo);
  photoBad.position.z = 0.009;
  const caption = text(`Testbild · ${shot.file}`, { font: 'mono', size: 0.34, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 });
  caption.position.set(0, PY - PH / 2 - 0.4, 0.01);
  // 5.2 Bauteil finden: invertierte Masken als Papier über dem Foto (Lila-Maske → geöffnet → senkrecht geschlossen)
  const tr = m3.trace;
  const masks = ['part_mask', 'part_opened', 'part_closed'].map((k) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(PW, PH), new THREE.MeshBasicMaterial({ color: color(T.paper), alphaMap: tex(tr.masks[k]), transparent: true, depthWrite: false, opacity: 0 }));
    m.position.set(0, PY, 0.0095);
    m.renderOrder = 2;
    return m;
  });
  photoGroup.add(card, photoGood, photoBad, ...masks, caption);
  scene.add(photoGroup);
  const maskNotes = [
    'Lila per Farbe (HSV): Farbton, Sättigung und Helligkeit im Bereich der Bauteilfarbe',
    'Öffnen mit 7 × 7 px: einzelne Störpixel am Rand verschwinden',
    'Senkrecht schließen über die Bauteilhöhe: Etikett und Loch gehören jetzt zum Bauteil',
  ].map((str, i) => note(`${i + 1} · ${str}`, -6.1, 3.85, 6.0, 0.62, 0.2));

  // ---------- 5.2 Bauteil-Box und ROIs ----------
  const [[bu0, bv0], [bu1, bv1]] = shot.box;
  const boxUV = (rx, ry) => [bu0 + rx * (bu1 - bu0), bv0 + ry * (bv1 - bv0)];
  const rectPts = (r, z = 0.02) => [boxUV(r[0], r[1]), boxUV(r[2], r[1]), boxUV(r[2], r[3]), boxUV(r[0], r[3])].map((uv) => Pp(uv, z));
  // Overlays auf dem Foto: kräftige Farbe mit dunklem Saum, damit sie auf Lila und hellem Hintergrund stehen
  const haloLine = (pts, o) => {
    const halo = new InkLine(pts.map((p) => p.clone().setZ(p.z - 0.0005)), { ...o, width: o.width + 3, hex: T.ink });
    const line = new InkLine(pts, o);
    scene.add(halo.object, line.object);
    return {
      set progress(v) { halo.progress = v; line.progress = v; },
      set opacity(v) { halo.opacity = v * 0.75; line.opacity = v; },
    };
  };
  const boxLine = haloLine(rectPts([0, 0, 1, 1]), { width: 3.4, hex: T.detect, closed: true, progress: 0 });
  const boxBL = Pp(boxUV(0, 1));
  const boxLabel = note('Bauteil-Box: Lila per Farbe (HSV) gefunden', boxBL.x + 0.2, boxBL.y - 0.25, 5.2, 0.46, 0.2, { font: 'mono', center: true, border: T.detect, borderWidth: 2.4 });
  const ROI = [
    { key: 'label_roi', name: 'Etikett', hex: '#FFC21A' },
    { key: 'hole_roi', name: 'Loch', hex: '#1FC2F2' },
    { key: 'notch_roi', name: 'Kerbe', hex: '#FF7A1F' },
  ].map((r, i) => {
    const pts = rectPts(ic[r.key], 0.021 + i * 0.001);
    const line = haloLine(pts, { width: 3.2, hex: r.hex, closed: true, dashed: true, dash: 0.14, gap: 0.07, progress: 0 });
    const top = Pp(boxUV((ic[r.key][0] + ic[r.key][2]) / 2, 0));
    const w = Math.max(1.0, r.name.length * 0.17);
    const lab = note(r.name, top.x - w / 2, top.y + 0.62, w, 0.5, 0.24, { font: 'title', center: true, border: r.hex, borderWidth: 3 });
    return { ...r, line, lab, delay: i * 0.28 };
  });
  const roiNote = note('Alle Prüfbereiche sind Anteile der Bauteil-Box – unabhängig von Abstand und Lage im Bild.', -6.1, 3.85, 6.0, 0.62, 0.2);

  // ---------- 5.3 Drei Prüfungen ----------
  const RES_Y = 3.85;
  const resultCard = (x, title, body, hex = T.ink) => note(`${title}\n${body}`, x, RES_Y, 3.55, 1.05, 0.2, { font: 'mono', hex });
  const ocrCard = resultCard(-6.1, 'SERIENNUMMER', `${shot.serial}  ·  Konfidenz ${fmt(shot.ocr_conf, 2)}\nRegex ${ic.serial_pattern}  ok`);
  const holeCard = resultCard(-1.8, 'LOCH', `Ø ${fmt(shot.hole_mm, 2)} mm  (D/H ${fmt(shot.hole_over_height, 3)})\nSoll ${fmt(ic.hole_nominal_mm, 0)} ± ${fmt(ic.hole_tolerance_mm)} mm  ok`);
  const notchCard = resultCard(2.5, 'KERBE', 'gefunden  ok');
  const notchBadCard = resultCard(2.5, 'KERBE', 'nicht gefunden', T.signal);

  const holePts = shot.hole.map((uv) => Pp(uv, 0.022));
  const holeLine = new InkLine(holePts, { width: 2.4, hex: T.signal, closed: true, progress: 0 });
  scene.add(holeLine.object);
  const hx = holePts.map((p) => p.x);
  const hy = holePts.map((p) => p.y);
  const hc = v3((Math.min(...hx) + Math.max(...hx)) / 2, (Math.min(...hy) + Math.max(...hy)) / 2, 0.023);
  const hr = (Math.max(...hx) - Math.min(...hx)) / 2;
  const holeDim = new Dimension(hc.clone().add(v3(-hr, 0)), hc.clone().add(v3(hr, 0)), `Ø ${fmt(shot.hole_mm, 2)} mm`, { hex: T.paper, size: 0.2, labelOffset: 0.25 });
  scene.add(holeDim.object);

  const notchPts = shot.notch.map((uv) => Pp(uv, 0.022));
  const notchLine = new InkLine(notchPts, { width: 2.4, hex: T.signal, closed: true, progress: 0 });
  scene.add(notchLine.object);
  const ocrFrame = new InkLine(rectPts(ic.label_roi, 0.024), { width: 3, hex: T.signal, closed: true, progress: 0 });
  scene.add(ocrFrame.object);
  // fehlende Kerbe: Rotstift-Kreis um die erwartete Stelle
  const nr = ic.notch_roi;
  const nc = Pp(boxUV((nr[0] + nr[2]) / 2, (nr[1] + nr[3]) / 2), 0.025);
  const missRing = new InkLine(Array.from({ length: 48 }, (_, i) => nc.clone().add(v3(Math.cos((i / 48) * 6.283) * 0.75, Math.sin((i / 48) * 6.283) * 0.75, 0))), { width: 3, hex: T.signal, closed: true, progress: 0 });
  scene.add(missRing.object);

  // Stempel auf Papierschildern unten rechts (über der schwarzen Vorrichtung)
  const stampAt = (label, hex, sub) => {
    const g = new THREE.Group();
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(3.9, 1.6), new THREE.MeshBasicMaterial({ color: 0xf4f1ea, transparent: true, depthWrite: false }));
    plate.renderOrder = 2;
    plate.position.z = 0.026;
    const st = new Stamp(label, { hex, size: 0.6, rot: -0.08, sub });
    st.object.position.z = 0.03;
    g.add(plate, st.object);
    g.position.set(3.4, -2.35, 0);
    scene.add(g);
    return { g, plate, st };
  };
  const goodStamp = stampAt('GUT', T.good, 'alle 3 Prüfungen ok');
  const badStamp = stampAt('SCHLECHT', T.signal, 'Grund: Kerbe fehlt');

  // ---------- 5.3–5.5 Detailblätter (unter dem Foto) ----------
  const crops = tr.crops;
  const pct = (v) => Math.round(v * 100);
  const op = (...objs) => (v) => objs.forEach((o) => (o.opacity = v));
  const pr = (lines) => (v) => lines.forEach((l) => (l.progress = v));
  /** Elemente nacheinander einblenden: Element i ab i/(n-1)·span des Fortschritts v. */
  const reveal = (fns, v, span = 0.75) => fns.forEach((f, i) => f(clamp01((v - (fns.length > 1 ? (i / (fns.length - 1)) * span : 0)) / 0.25)));
  const boardText = (str, x, y, o = {}) => {
    const t = text(str, { opacity: 0, ...o });
    t.position.set(x, y, 0.012);
    scene.add(t);
    return t;
  };
  const boardHead = (y0, title, sub) => [
    boardText(title, -8.3, y0 + 3.9, { font: 'title', size: 0.36, anchorY: 'bottom' }),
    boardText(sub, -8.3, y0 + 3.75, { font: 'mono', size: 0.17, hex: T.inkSoft, anchorY: 'top' }),
  ];
  const photoCard = (c, w, x, y) => {
    const pc = new PhotoCard(c.url, { width: w, aspect: c.h / c.w, border: 0.06, bottom: 0.06 });
    pc.object.position.set(x, y, 0.02);
    pc.opacity = 0;
    scene.add(pc.object);
    return pc;
  };
  const cap = (str, x, y, o = {}) => boardText(str, x, y, { font: 'mono', size: 0.17, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', textAlign: 'center', lineHeight: 1.35, ...o });
  const arrow = (x0, x1, y) => arrowPts(v3(x0, y, 0.012), v3(x1, y, 0.012), 0.16).map((pts) => {
    const l = new InkLine(pts, { width: 1.6, progress: 0 });
    scene.add(l.object);
    return l;
  });

  // 5.3 Seriennummer
  const yO = BOARD.ocr;
  const minConf = ic.ocr_min_confidence ?? 0.4;
  const lr = ic.label_roi;
  const ocrA = [
    op(...boardHead(yO, 'Seriennummer: Etikett lesen, Format prüfen', 'm3_inspection/ocr.py · EasyOCR mit Ziffern-Allowlist, danach Regex aus system.yaml')),
    op(photoCard(crops.label_roi, 5.6, -5.5, yO + 1.6), cap(`Etikett-ROI · ${pct(lr[0])}–${pct(lr[2])} % der Box-Breite, volle Höhe`, -5.5, yO + 0.2)),
    pr(arrow(-2.5, -1.5, yO + 1.6)),
    op(note('EasyOCR\nnur Ziffern 0–9\nunter 64 px Höhe wird\nder Ausschnitt hochskaliert', -1.1, yO + 2.55, 2.9, 1.95, 0.2, { font: 'mono' })),
    pr(arrow(2.75, 3.75, yO + 1.6)),
    op(
      boardText(tr.serial, 6.1, yO + 1.95, { font: 'title', size: 0.75, anchorX: 'center', anchorY: 'middle', hex: M3 }),
      boardText(`Konfidenz ${fmt(tr.ocr_conf, 2)} ≥ ${fmt(minConf, 1)}  ok\nRegex ${ic.serial_pattern}  ok`, 6.1, yO + 1.25, { font: 'mono', size: 0.19, anchorX: 'center', anchorY: 'top', textAlign: 'center', lineHeight: 1.4, hex: T.good }),
    ),
  ];
  const ocrB = [
    op(boardText('Alle vier Testbilder – unterschiedlicher Abstand, Hintergrund und Licht', -8.3, yO - 0.55, { font: 'sansMedium', size: 0.22, anchorY: 'bottom' })),
    ...m3.shots.map((sh, i) => {
      const x = -6.15 + i * 4.1;
      const pc = new PhotoCard(sh.photo, { width: 3.6, aspect: sh.photo_size[1] / sh.photo_size[0], border: 0.05, bottom: 0.05 });
      pc.object.position.set(x, yO - 1.75, 0.02);
      pc.opacity = 0;
      scene.add(pc.object);
      return op(pc, cap(`${sh.file}\n${sh.serial} · Konfidenz ${fmt(sh.ocr_conf, 2)}`, x, yO - 2.9, { hex: i === m3.hero ? M3 : T.inkSoft }));
    }),
    op(boardText(`Format verfehlt oder Konfidenz unter ${fmt(minConf, 1)} → keine gültige Seriennummer → SCHLECHT`, -8.3, yO - 3.85, { font: 'sans', size: 0.21, anchorY: 'top' })),
  ];

  // 5.4 Loch (mit Maßstab über die Bauteilhöhe)
  const yH = BOARD.hole;
  const HW = 4.2;
  const HH = (HW * crops.hole_roi.h) / crops.hole_roi.w;
  const hRowY = yH + 1.2;
  const holeCards = [-5.6, 0, 5.6].map((x, i) => photoCard(crops[['hole_roi', 'hole_mask', 'hole_candidates'][i]], HW, x, hRowY));
  const holeCaps = [
    cap('Loch-ROI · volle Bauteilhöhe', -5.6, hRowY - HH / 2 - 0.2),
    cap('Maske: alles, was keine helle\nlila Stirnfläche ist – Bohrungs-\nwand oder Hintergrund im Loch', 0, hRowY - HH / 2 - 0.2),
    cap(`Kandidaten, Rundheit = Fläche / Umkreis\nbeste ${fmt(tr.hole_score, 2)} ≥ 0,75 → Ellipse`, 5.6, hRowY - HH / 2 - 0.2),
  ];
  const holeArrows = [arrow(-3.35, -2.25, hRowY), arrow(2.25, 3.35, hRowY)];
  const holeA = [
    op(...boardHead(yH, 'Loch: alles, was keine Stirnfläche ist – davon das Rundeste', 'm3_inspection/features.py · find_hole()')),
    op(holeCards[0], holeCaps[0]),
    pr(holeArrows[0]),
    op(holeCards[1], holeCaps[1]),
    pr(holeArrows[1]),
    op(holeCards[2], holeCaps[2]),
  ];
  // Schritt 2: Maßlinien auf der Kandidatenkarte (Lochmitte aus der Kontur, Ø aus der Ellipse)
  const [[ru0, rv0], [ru1, rv1]] = tr.rois.hole_roi;
  const hu = shot.hole.map(([u]) => (u - ru0) / (ru1 - ru0));
  const hv = shot.hole.map(([, v]) => (v - rv0) / (rv1 - rv0));
  const hcx = 5.6 + ((Math.min(...hu) + Math.max(...hu)) / 2 - 0.5) * HW;
  const hcy = hRowY - ((Math.min(...hv) + Math.max(...hv)) / 2 - 0.5) * HH;
  const hrad = (tr.hole_px / 2 / crops.hole_roi.w) * HW;
  const mmPerPx = ic.part_height_mm / tr.box_px_h;
  const hBot = v3(5.6 - HW / 2, hRowY - HH / 2, 0.04);
  const hTop = v3(5.6 - HW / 2, hRowY + HH / 2, 0.04);
  const heightDim = new Dimension(hBot, hTop, `${fmt(ic.part_height_mm, 0)} mm = ${tr.box_px_h} px`, { offset: v3(-0.35, 0), size: 0.18, labelOffset: 0.3, extFrom: [hBot, hTop] });
  const diaDim = new Dimension(v3(hcx - hrad, hcy, 0.04), v3(hcx + hrad, hcy, 0.04), `Ø ${Math.round(tr.hole_px)} px`, { hex: T.paper, size: 0.18, labelOffset: 0.22 });
  scene.add(heightDim.object, diaDim.object);
  const dh = m3.shots.map((sh) => fmt(sh.hole_over_height, 3)).join(' · ');
  const holeCalc = note(
    `Maßstab aus der Bauteilhöhe\n${fmt(ic.part_height_mm, 0)} mm / ${tr.box_px_h} px = ${fmt(mmPerPx, 4)} mm/px\n\n` +
      `Ellipse: ${Math.round(tr.hole_px)} px × ${fmt(mmPerPx, 4)} = ${fmt(shot.hole_mm, 2)} mm\nSoll ${fmt(ic.hole_nominal_mm, 0)} ± ${fmt(ic.hole_tolerance_mm)} mm  ok\n\n` +
      `D/H auf den vier Testbildern\n${dh}\nunabhängig vom Abstand, keine Kalibrierplatte`,
    -8.0, hRowY + 1.9, 7.6, 3.55, 0.21, { font: 'mono' },
  );

  // 5.5 Kerbe
  const yN = BOARD.notch;
  const NW = 2.5;
  const NH = (NW * crops.notch_roi.h) / crops.notch_roi.w;
  const ny = yN + 1.3;
  const nx = [-6.3, -2.15, 1.15, 5.7];
  const nCards = ['notch_roi', 'notch_region_mask', 'notch_edges', 'notch_candidates'].map((k, i) => photoCard(crops[k], NW, nx[i], ny));
  const nr0 = ic.notch_roi;
  const nCaps = [
    `Kerben-ROI · ${pct(nr0[0])}–${pct(nr0[2])} % der Box-Breite`,
    'Region: dunkler oder anders\ngesättigt als der ROI-Rand',
    'Kanten: Canny + Schließen\n→ konvexe Hülle',
    `Rechteckigkeit ${fmt(tr.notch_score, 2)} ≥ 0,7\n→ Kerbe vorhanden`,
  ].map((str, i) => cap(str, nx[i], ny - NH / 2 - 0.2, i === 3 ? { hex: M3 } : {}));
  // drei Klicks: ROI + Region → Kanten → Kandidat
  const notchA = [
    op(...boardHead(yN, 'Kerbe: zwei Wege zum Kandidaten, gewählt wird das Rechteck', 'm3_inspection/features.py · find_notch()')),
    op(nCards[0], nCaps[0]),
    pr(arrow(-4.85, -3.55, ny)),
    op(nCards[1], nCaps[1]),
  ];
  const notchE = [op(boardText('+', -0.5, ny, { font: 'title', size: 0.5, anchorX: 'center', anchorY: 'middle' })), op(nCards[2], nCaps[2])];
  const notchC = [
    pr(arrow(2.55, 4.3, ny)),
    op(nCards[3], nCaps[3]),
    op(boardText(
      'Region findet die Öffnung, wenn sie dunkler ist; Kanten, wenn sie dieselbe Farbe hat wie die Fläche.\n' +
        'Kandidaten beider Wege zählen: Fläche 2–30 % von H², Seitenverhältnis 0,5–2, Rechteckigkeit = Fläche / kleinstes Rechteck.',
      -8.3, yN - 1.6, { font: 'sans', size: 0.2, anchorY: 'top', lineHeight: 1.45, maxWidth: 16.6 },
    )),
  ];

  // 5.5 Schritt 4: alle vier Testbilder mit ihren Zwischenbildern; der Weg, der gewonnen hat, ist umrahmt
  const yG = BOARD.notchAll;
  const GH = 2.0; // Kartenhöhe
  const GK = ['notch_roi', 'notch_region_mask', 'notch_edges', 'notch_candidates'];
  const GCOL = ['ROI', 'Region', 'Kanten', 'Kandidaten'];
  const notchG = [
    op(...boardHead(yG, 'Alle vier Testbilder: mal gewinnt die Region, mal die Kanten', 'gleicher Code, gleiche Schwellen – gezeigt sind die echten Zwischenbilder')),
  ];
  m3.notches.forEach((nb, i) => {
    const bx = i % 2 ? 4.15 : -4.15;
    const by = yG + (i < 2 ? 1.5 : -1.95);
    const ws = GK.map((k) => (GH * nb.crops[k].w) / nb.crops[k].h);
    const gap = 0.28;
    const total = ws.reduce((a, b) => a + b, 0) + gap * 3;
    let x = bx - total / 2;
    const items = [];
    GK.forEach((k, j) => {
      const cx = x + ws[j] / 2;
      const pc = photoCard(nb.crops[k], ws[j], cx, by);
      const lbl = boardText(GCOL[j], cx, by + GH / 2 + 0.24, { font: 'mono', size: 0.14, hex: T.inkSoft, anchorX: 'center', anchorY: 'bottom' });
      items.push(pc, lbl);
      if (GCOL[j] === nb.via) {
        const m = 0.13;
        const [x0, x1, y0, y1] = [cx - ws[j] / 2 - m, cx + ws[j] / 2 + m, by - GH / 2 - m, by + GH / 2 + m];
        const frame = new InkLine([v3(x0, y0, 0.03), v3(x1, y0, 0.03), v3(x1, y1, 0.03), v3(x0, y1, 0.03)], { width: 2.6, hex: M3, closed: true, progress: 0 });
        scene.add(frame.object);
        items.push({ set opacity(v) { frame.progress = v; } });
        lbl.color = M3;
      }
      x += ws[j] + gap;
    });
    const hero = i === m3.hero ? '  (Nahaufnahme aus 5.2)' : '';
    const verdict = nb.score != null ? `Rechteckigkeit ${fmt(nb.score, 2)} über ${nb.via}` : 'keine Kerbe gefunden';
    items.push(cap(`${nb.file}${hero}  ·  ${verdict}`, bx, by - GH / 2 - 0.2, { hex: T.ink }));
    notchG.push(op(...items));
  });

  function update() {
    // 5.1
    sketch.forEach((l, i) => {
      l.progress = clamp01(S.sketch * sketch.length * 0.8 - i * 0.6);
      l.opacity = 1 - S.center;
    });
    sketchTexts.forEach(([t], i) => (t.opacity = clamp01(S.sketch * 2.5 - 1 - i * 0.2) * (1 - S.center)));
    const c = S.center;
    photoGroup.position.set(SMALL.x * (1 - c), SMALL.y * (1 - c), 0);
    photoGroup.scale.setScalar(SMALL.s + (1 - SMALL.s) * c);
    photoGroup.visible = S.photo > 0;
    card.material.opacity = S.photo * (1 - c);
    caption.opacity = S.photo * (1 - c);
    photoGood.material.opacity = S.photo;
    photoBad.material.opacity = S.photo * S.bad;
    photoBad.visible = photoBad.material.opacity > 0.001;

    // 5.2 Bauteil finden: Masken blenden ineinander, mit der Box wieder weg
    masks.forEach((m, k) => {
      const w = (k < 2 ? clamp01(1 - Math.abs(S.seg - (k + 1))) : clamp01(S.seg - 2)) * (1 - S.box);
      m.material.opacity = 0.92 * w;
      m.visible = w > 0.001;
      maskNotes[k].opacity = (k < 2 ? clamp01(1.5 - Math.abs(S.seg - (k + 1)) * 3) : clamp01(S.seg * 3 - 7.5)) * (1 - S.box);
    });

    // 5.2
    boxLine.progress = S.box;
    boxLine.opacity = 1 - S.ocr * 0.6;
    boxLabel.opacity = clamp01(S.box * 2 - 1) * (1 - S.ocr);
    const focus = S.ocr; // ab 5.3 treten die ROIs zurück
    ROI.forEach((r) => {
      const v = clamp01((S.rois - r.delay) / 0.44);
      r.line.progress = v;
      r.line.opacity = 1 - 0.65 * focus;
      r.lab.opacity = clamp01(v * 2 - 1) * (1 - focus);
    });
    roiNote.opacity = clamp01(S.rois * 2 - 1) * (1 - S.ocr);

    // 5.3
    ocrFrame.progress = S.ocr;
    ocrFrame.opacity = 1 - S.hole * 0.75;
    ocrCard.opacity = clamp01(S.ocr * 2 - 0.6);
    holeLine.progress = S.hole;
    holeLine.opacity = 1 - S.notch * 0.5;
    holeDim.appear = clamp01(S.hole * 1.5 - 0.5) * (1 - S.notch);
    holeCard.opacity = clamp01(S.hole * 2 - 0.6);
    notchLine.progress = S.notch;
    notchLine.opacity = 1 - S.bad;
    notchCard.opacity = clamp01(S.notch * 2 - 0.6) * (1 - S.bad);
    goodStamp.st.appear = S.good * (1 - S.bad);
    goodStamp.plate.material.opacity = clamp01(S.good * 3) * (1 - S.bad);
    goodStamp.g.visible = goodStamp.plate.material.opacity > 0.001;
    missRing.progress = clamp01(S.bad * 2 - 0.6);
    notchBadCard.opacity = clamp01(S.bad * 2 - 0.8);
    badStamp.st.appear = clamp01(S.bad * 1.6 - 0.6);
    badStamp.plate.material.opacity = clamp01(S.bad * 3 - 1.5);
    badStamp.g.visible = badStamp.plate.material.opacity > 0.001;

    // 5.3–5.5 Detailblätter
    reveal(ocrA, S.dOcr);
    reveal(ocrB, S.dOcr2, 0.6);
    reveal(holeA, S.dHole);
    const keep = 1 - S.dHole2; // Schritt 2: ROI und Maske weichen der Rechnung
    [0, 1].forEach((i) => {
      holeCards[i].opacity *= keep;
      holeCaps[i].opacity *= keep;
    });
    holeArrows.flat().forEach((l) => (l.opacity = keep));
    heightDim.appear = S.dHole2;
    diaDim.appear = clamp01(S.dHole2 * 2 - 0.5);
    holeCalc.opacity = clamp01(S.dHole2 * 2 - 0.8);
    reveal(notchA, S.dNotch);
    reveal(notchE, S.dNotchE, 0.4);
    reveal(notchC, S.dNotchC);
    reveal(notchG, S.dNotch2, 0.7);
  }
  return { scene, S, defaults: DEFAULTS, update };
}

// ---------- Kameras ----------
const cam = (lx, ly, pz, fov = 30) => ({ lx, ly, lz: 0, px: lx, py: ly - 0.01, pz, fov });
const C = {
  overview: cam(0, 0, 19.5),
  photo: cam(0, 0.25, 18),
  ocr: cam(0, BOARD.ocr + 0.25, 18),
  hole: cam(0, BOARD.hole + 0.25, 18),
  notch: cam(0, BOARD.notch + 0.25, 18),
  notchAll: cam(0, BOARD.notchAll + 0.25, 18),
};

const to = (tl, S, vars, pos = 0) => tl.to(S, { ease: EASE.appear, ...vars }, pos);

export const INSPECT_SCENES = [
  {
    id: '5.1', world: 'inspect',
    steps: [
      (tl, S, ctx) => {
        to(tl, S, { sketch: 1, duration: 2.6, ease: 'power1.inOut' }, 0.1);
        tl.to(ctx.stage.flash, { v: 0.85, duration: 0.06, ease: 'none' }, 2.8);
        tl.to(ctx.stage.flash, { v: 0, duration: 0.7, ease: 'power2.out' }, 2.86);
        to(tl, S, { photo: 1, duration: 0.9, ease: 'power2.out' }, 2.86);
      },
    ],
    cams: [C.overview],
  },
  {
    id: '5.2', world: 'inspect',
    steps: [
      (tl, S) => {
        to(tl, S, { center: 1, duration: 1.6, ease: EASE.move }, 0);
        to(tl, S, { seg: 1, duration: 1.0 }, 1.4);
      },
      // jede Maske ein eigener Klick, damit man sie erklären kann
      (tl, S) => to(tl, S, { seg: 2, duration: 1.2, ease: 'power1.inOut' }, 0),
      (tl, S) => to(tl, S, { seg: 3, duration: 1.2, ease: 'power1.inOut' }, 0),
      (tl, S) => to(tl, S, { box: 1, duration: 1.4, ease: 'power1.inOut' }, 0),
      (tl, S) => to(tl, S, { rois: 1, duration: 2.0, ease: 'power1.inOut' }, 0),
    ],
    cams: [C.photo, C.photo, C.photo, C.photo, C.photo],
  },
  {
    id: '5.3', world: 'inspect',
    steps: [
      (tl, S) => to(tl, S, { dOcr: 1, duration: 2.6, ease: 'power1.inOut' }, 0.8),
      (tl, S) => to(tl, S, { dOcr2: 1, duration: 2.0, ease: 'power1.inOut' }, 0),
    ],
    cams: [C.ocr, C.ocr],
  },
  {
    id: '5.4', world: 'inspect',
    steps: [
      (tl, S) => to(tl, S, { dHole: 1, duration: 2.6, ease: 'power1.inOut' }, 0.8),
      (tl, S) => to(tl, S, { dHole2: 1, duration: 1.8, ease: 'power1.inOut' }, 0),
    ],
    cams: [C.hole, C.hole],
  },
  {
    id: '5.5', world: 'inspect',
    steps: [
      (tl, S) => to(tl, S, { dNotch: 1, duration: 2.0, ease: 'power1.inOut' }, 0.8),
      (tl, S) => to(tl, S, { dNotchE: 1, duration: 1.0, ease: 'power1.inOut' }, 0),
      (tl, S) => to(tl, S, { dNotchC: 1, duration: 1.6, ease: 'power1.inOut' }, 0),
      (tl, S) => to(tl, S, { dNotch2: 1, duration: 2.4, ease: 'power1.inOut' }, 0.6),
    ],
    cams: [C.notch, C.notch, C.notch, C.notchAll],
  },
  {
    id: '5.6', world: 'inspect',
    steps: [
      (tl, S) => to(tl, S, { ocr: 1, duration: 1.6, ease: 'power1.inOut' }, 0.2),
      (tl, S) => to(tl, S, { hole: 1, duration: 1.8, ease: 'power1.inOut' }, 0),
      (tl, S) => {
        to(tl, S, { notch: 1, duration: 1.4, ease: 'power1.inOut' }, 0);
        to(tl, S, { good: 1, duration: 0.6, ease: 'power3.out' }, 1.5);
      },
      (tl, S) => to(tl, S, { bad: 1, duration: 2.0, ease: 'power1.inOut' }, 0),
    ],
    cams: [C.photo, C.photo, C.photo, C.photo],
  },
];
