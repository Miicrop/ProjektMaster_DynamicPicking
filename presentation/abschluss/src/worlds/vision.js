// Akt 3 (M1 Objekterkennung): Kamera an der Stange → Blitz → echtes Foto → Entzerrung per echter
// Homographie → Segmentierung → Winkel dank Fase → drei Koordinatensysteme.
// Alle Geometrie stammt aus data.json (build_data.py, TopDownPipeline auf den Testfotos).
import * as THREE from 'three';
import { T, EASE, MODULE_COLOR, color } from '../theme.js';
import { makeWorldScene } from '../engine/stage.js';
import { InkLine, Balloon, Dimension, text, tex, v3 } from '../kit/ink.js';
import { clamp01 } from '../kit/tiles.js';
import { note as makeNote } from '../kit/note.js';
import { circle, arc, arrowPts, setPts } from '../kit/geom.js';

const SHOT = 0; // Testfoto mit LARA im Bild
const K = 0.017; // Papiereinheiten je mm
const PW = 10; // Fotobreite in Papiereinheiten (zentriert, vor der Entzerrung)
const PHOTO_SMALL = { x: 4.3, y: -0.2, s: 0.72 }; // Lage des Fotos in 3.1

const DEFAULTS = {
  sketch: 0, photo: 0, // 3.1
  center: 0, markers: 0, quad: 0, warp: 0, crop: 0, frame: 0, // 3.2
  mask: 0, contour: 0, maskOff: 0, parallax: 0, // 3.3
  axis: 0, diagrams: 0, rot: 0, // 3.4
  frames: 0, vectors: 0, calib: 0, tour: 0, // 3.5
};

const fmt = (v, d = 1) => v.toFixed(d).replace('.', ',');

export function createVision(ctx) {
  const shot = ctx.data.m1.shots[SHOT];
  const cfg = ctx.data.config;
  const [WS_W, WS_H] = cfg.workspace.size_mm;
  const scene = makeWorldScene();
  const S = { ...DEFAULTS };

  // Arbeitsraum-mm → Papier (Mitte des Arbeitsraums im Ursprung)
  const P = (x, y, z = 0.02) => v3((x - WS_W / 2) * K, (y - WS_H / 2) * K, z);
  // entzerrtes Bild (0..1, v nach unten) → Arbeitsraum-mm
  const rectMm = ([u, v]) => [u * WS_W, WS_H - v * WS_H];
  const PR = (uv, z) => P(...rectMm(uv), z);

  const note = (...a) => makeNote(scene, ...a);

  // ---------- 3.1 Seitenriss: Kamera an der Stange (schematisch, Lage angenommen) ----------
  const sketch = [];
  const SL = (pts, o = {}) => {
    const l = new InkLine(pts.map((p) => v3(p[0], p[1], 0.01)), { width: 1.5, progress: 0, ...o });
    sketch.push(l);
    scene.add(l.object);
    return l;
  };
  const TY = -2.6;
  SL([[-8.8, TY], [-1.0, TY]], { width: 2 }); // Tisch
  SL([[-7.4, TY], [-7.4, TY + 0.12], [-2.4, TY + 0.12], [-2.4, TY]], {}); // Platte
  SL([[-5.3, TY + 0.12], [-5.3, TY + 0.42], [-4.6, TY + 0.42], [-4.6, TY + 0.12]], { hex: T.part, width: 2 }); // Bauteil
  SL([[-8.5, TY], [-8.5, 3.3]], { width: 2.4 }); // Stange
  SL([[-8.5, 3.0], [-6.9, 3.0]], { width: 2 }); // Ausleger
  const camC = v3(-6.6, 2.75);
  const camAng = Math.atan2(TY - camC.y, -4.9 - camC.x); // Blick auf die Plattenmitte
  const cd = v3(Math.cos(camAng), Math.sin(camAng));
  const cn = v3(-cd.y, cd.x);
  const box = [[-0.35, -0.22], [0.25, -0.22], [0.25, 0.22], [-0.35, 0.22]].map(([a, b]) => camC.clone().addScaledVector(cd, a).addScaledVector(cn, b));
  SL(box.map((p) => [p.x, p.y]), { closed: true, width: 2 });
  const lens = camC.clone().addScaledVector(cd, 0.25);
  SL([[-6.9, 3.0], [camC.x, camC.y + 0.22]], { width: 1.5 });
  SL([[lens.x, lens.y], [-7.4, TY + 0.12]], { dashed: true, width: 1, hex: MODULE_COLOR.M1 });
  SL([[lens.x, lens.y], [-2.4, TY + 0.12]], { dashed: true, width: 1, hex: MODULE_COLOR.M1 });
  const sketchTexts = [
    [text('Kamera M1 an der Stange', { font: 'title', size: 0.3, anchorY: 'bottom', opacity: 0 }), -6.3, 3.35],
    [text('schräg seitlich über dem Arbeitsraum', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', opacity: 0 }), -6.3, 3.25],
    [text('Arbeitsraum 330 × 330 mm', { font: 'mono', size: 0.18, anchorX: 'center', anchorY: 'top', opacity: 0 }), -4.9, TY - 0.15],
    [text('Seitenriss, schematisch – Lage angenommen', { font: 'mono', size: 0.15, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 }), -4.9, TY - 0.5],
  ];
  sketchTexts.forEach(([t, x, y]) => {
    t.position.set(x, y, 0.01);
    scene.add(t);
  });

  // ---------- Foto als verformbares Gitter ----------
  const [iw, ih] = shot.photo_size;
  const PH = (PW * ih) / iw;
  const cu = shot.markers_img.reduce((s, m) => s + m[0], 0) / 4;
  const cv = shot.markers_img.reduce((s, m) => s + m[1], 0) / 4;
  const H = shot.H_img2rect;
  const ppm = shot.px_per_mm;
  const flatPos = ([u, v]) => v3((u - cu) * PW, -(v - cv) * PH, 0);
  const warpPos = ([u, v]) => {
    const x = u * iw;
    const y = v * ih;
    const w = H[2][0] * x + H[2][1] * y + H[2][2];
    const ur = (H[0][0] * x + H[0][1] * y + H[0][2]) / w;
    const vr = (H[1][0] * x + H[1][1] * y + H[1][2]) / w;
    const mx = ur / ppm;
    const my = WS_H - vr / ppm;
    return { p: P(mx, my, 0), rc: [mx / WS_W, my / WS_H] };
  };

  const NX = 64;
  const NY = 48;
  const nv = (NX + 1) * (NY + 1);
  const flat = new Float32Array(nv * 3);
  const warped = new Float32Array(nv * 3);
  const rc = new Float32Array(nv * 2);
  const uvs = new Float32Array(nv * 2);
  for (let j = 0; j <= NY; j++) {
    for (let i = 0; i <= NX; i++) {
      const k = j * (NX + 1) + i;
      const uv = [i / NX, j / NY];
      const f = flatPos(uv);
      const w = warpPos(uv);
      flat.set([f.x, f.y, 0], k * 3);
      warped.set([w.p.x, w.p.y, 0], k * 3);
      rc.set(w.rc, k * 2);
      uvs.set([uv[0], 1 - uv[1]], k * 2);
    }
  }
  const idx = [];
  for (let j = 0; j < NY; j++) {
    for (let i = 0; i < NX; i++) {
      const a = j * (NX + 1) + i;
      idx.push(a, a + NX + 1, a + 1, a + 1, a + NX + 1, a + NX + 2);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(flat.slice(), 3));
  geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
  geo.setAttribute('rc', new THREE.BufferAttribute(rc, 2));
  geo.setIndex(idx);
  // Zuschnitt auf den Arbeitsraum je Fragment (rc = Arbeitsraumkoordinate 0..1 des Fotopunkts)
  const cropU = { value: 0 };
  const photoMat = new THREE.MeshBasicMaterial({ map: tex(shot.photo), transparent: true, toneMapped: false, depthWrite: false });
  photoMat.onBeforeCompile = (sh) => {
    sh.uniforms.uCrop = cropU;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec2 rc;\nvarying vec2 vRc;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvRc = rc;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uCrop;\nvarying vec2 vRc;')
      .replace('#include <opaque_fragment>', 'float outside = max(max(-vRc.x, vRc.x - 1.0), max(-vRc.y, vRc.y - 1.0));\ndiffuseColor.a *= 1.0 - uCrop * smoothstep(0.0, 0.004, outside);\n#include <opaque_fragment>');
  };
  const photo = new THREE.Mesh(geo, photoMat);
  photo.position.z = 0.008;
  photo.renderOrder = 1;
  photo.frustumCulled = false;

  // weißer Kartenrand nur in 3.1
  const card = new THREE.Mesh(new THREE.PlaneGeometry(PW + 0.4, PH + 0.4), new THREE.MeshBasicMaterial({ color: 0xfbfaf6, transparent: true, depthWrite: false }));
  card.position.set((0.5 - cu) * PW, -(0.5 - cv) * PH, 0.004);
  card.renderOrder = 0;
  const caption = text(`Testfoto 05.10. · ${shot.file}`, { font: 'mono', size: 0.3, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 });
  caption.position.set((0.5 - cu) * PW, -(0.5 - cv) * PH - PH / 2 - 0.35, 0.01);
  const photoGroup = new THREE.Group();
  photoGroup.add(card, photo, caption);
  scene.add(photoGroup);

  // Maske (3.3): invertierte Teilmaske über dem Arbeitsraum – deckt alles außer dem Bauteil ab
  const maskMat = new THREE.MeshBasicMaterial({ color: color(T.paper), alphaMap: tex(shot.mask_inv), transparent: true, depthWrite: false, opacity: 0 });
  const mask = new THREE.Mesh(new THREE.PlaneGeometry(WS_W * K, WS_H * K), maskMat);
  mask.position.set(0, 0, 0.012);
  mask.renderOrder = 1;
  scene.add(mask);

  // ---------- 3.2 Marker, Viereck, Rahmen ----------
  const ids = Object.keys(cfg.workspace.markers_mm).sort();
  const mFlat = shot.markers_img.map(flatPos);
  const mWarp = ids.map((id) => P(...cfg.workspace.markers_mm[id], 0));
  const markerRings = ids.map(() => {
    const l = new InkLine(circle(v3(0, 0), 0.5), { width: 3, hex: T.detect, closed: true, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const markerIds = ids.map((id) => {
    const b = new Balloon(id, { r: 0.24, size: 0.18, fill: T.detect });
    scene.add(b.object);
    return b;
  });
  const MS = 29; // halbe Markergröße inkl. Rand [mm]
  const markerSquares = ids.map((id) => {
    const [x, y] = cfg.workspace.markers_mm[id];
    const l = new InkLine([P(x - MS, y - MS), P(x + MS, y - MS), P(x + MS, y + MS), P(x - MS, y + MS)], { width: 2.2, hex: T.detect, closed: true, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const quad = new InkLine([v3(0, 0), v3(1, 0), v3(1, 1), v3(0, 1)], { width: 2.6, hex: T.detect, closed: true, progress: 0 });
  scene.add(quad.object);
  const quadNote = note('Homographie: die 4 Markermitten im Bild werden auf ihre bekannte Lage in mm abgebildet.', -8.9, 4.75, 4.0, 1.12, 0.22);

  const frame = new InkLine([P(0, 0), P(WS_W, 0), P(WS_W, WS_H), P(0, WS_H)], { width: 2, closed: true, progress: 0 });
  scene.add(frame.object);
  const dimW = new Dimension(P(0, 0), P(WS_W, 0), `${WS_W} mm`, { offset: v3(0, -0.45), labelOffset: -0.25, size: 0.2 });
  const dimH = new Dimension(P(WS_W, 0), P(WS_W, WS_H), `${WS_H} mm`, { offset: v3(0.45, 0), labelOffset: -0.25, size: 0.2 });
  scene.add(dimW.object, dimH.object);
  const pxNote = text(`entzerrt: ${ppm} px/mm`, { font: 'mono', size: 0.18, hex: T.inkSoft, anchorY: 'top', opacity: 0 });
  pxNote.position.copy(P(0, -45, 0.03));
  scene.add(pxNote);

  // ---------- 3.3 Kontur, Rechteck, Maße ----------
  const contourPts = shot.contour_rect.map((uv) => PR(uv, 0.02));
  const contour = new InkLine(contourPts, { width: 2.4, hex: T.signal, closed: true, progress: 0 });
  const boxPts = shot.box_rect.map((uv) => PR(uv, 0.02));
  const boxLine = new InkLine(boxPts, { width: 1.2, closed: true, dashed: true, dash: 0.05, gap: 0.035, hex: T.paper, progress: 0 });
  scene.add(contour.object, boxLine.object);
  const e1 = boxPts[1].clone().sub(boxPts[0]);
  const e2 = boxPts[2].clone().sub(boxPts[1]);
  const [la, lb, sa, sb] = e1.length() >= e2.length() ? [boxPts[0], boxPts[1], boxPts[1], boxPts[2]] : [boxPts[1], boxPts[2], boxPts[0], boxPts[1]];
  const centre = PR(shot.centre_rect, 0.02);
  const away = (a, b, d) => {
    const m = a.clone().add(b).multiplyScalar(0.5);
    return m.sub(centre).setZ(0).normalize().multiplyScalar(d);
  };
  const dimL = new Dimension(la, lb, `${fmt(shot.length_mm)} mm`, { offset: away(la, lb, 0.22), labelOffset: 0.12, size: 0.1, extFrom: [la, lb], hex: T.paper });
  const dimS = new Dimension(sa, sb, `${fmt(shot.width_mm)} mm`, { offset: away(sa, sb, 0.22), labelOffset: 0.12, size: 0.1, extFrom: [sa, sb], hex: T.paper });
  scene.add(dimL.object, dimS.object);
  // Die Dimension-Beschriftung sitzt auf der Normalen; nach außen zeigen lassen
  for (const [d, a, b] of [[dimL, la, lb], [dimS, sa, sb]]) {
    const m = a.clone().add(b).multiplyScalar(0.5).add(away(a, b, 0.22));
    d.label.position.copy(m.add(away(a, b, 0.13))).setZ(0.03);
  }
  const part = ctx.data.part;
  const segNote = note('Bauteil = deutlich heller oder bunter als der Median der Platte', centre.x + 1.0, centre.y + 1.2, 2.1, 0.42, 0.1);
  const parallax = note(
    `Soll ${part.length_mm} × ${part.width_mm} mm. Die Homographie gilt für die Tischebene – die ${part.height_mm} mm hohe Oberseite und die sichtbaren Seitenflächen erscheinen größer (Parallaxe, offener Punkt).`,
    centre.x + 1.0, centre.y + 0.62, 2.1, 0.72, 0.1,
  );

  // ---------- 3.4 Achse, Winkel, Fase ----------
  const th = (-shot.theta_img_deg * Math.PI) / 180; // Bild-y nach unten → Papier-y nach oben
  const dir = v3(Math.cos(th), Math.sin(th));
  const axisLines = arrowPts(centre, centre.clone().addScaledVector(dir, 0.95)).map((pts) => {
    const l = new InkLine(pts, { width: 2.2, hex: MODULE_COLOR.M1, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const refLine = new InkLine([centre, centre.clone().add(v3(1.05, 0))], { width: 1, dashed: true, dash: 0.04, gap: 0.03, hex: T.paper, progress: 0 });
  const angArc = new InkLine(arc(centre, 0.55, 0, ((((shot.ws.theta % 360) + 360) % 360) * Math.PI) / 180), { width: 1.4, hex: T.paper, progress: 0 });
  scene.add(refLine.object, angArc.object);
  const midA = (((shot.ws.theta % 360) * Math.PI) / 180) / 2;
  const angLabel = text(`${fmt(shot.ws.theta)}°`, { font: 'monoMedium', size: 0.12, hex: T.paper, anchorX: 'left', anchorY: 'middle', opacity: 0 });
  angLabel.position.set(centre.x + Math.cos(midA) * 0.7, centre.y + Math.sin(midA) * 0.7, 0.03);
  scene.add(angLabel);
  const chamferC = PR(shot.chamfer_rect, 0.02);
  const chamferRing = new InkLine(circle(chamferC, 0.13), { width: 2.4, hex: T.signal, closed: true, progress: 0 });
  scene.add(chamferRing.object);
  const chamferLabel = text('Fase', { font: 'title', size: 0.12, hex: T.signal, anchorX: 'center', anchorY: 'top', opacity: 0 });
  chamferLabel.position.set(chamferC.x, chamferC.y - 0.17, 0.03);
  scene.add(chamferLabel);

  // zwei Prinzipskizzen: ohne / mit Fase, je um 180° gedreht
  const DX = 4.4;
  const sketchPart = (chamfer) => {
    const w = 1.5;
    const h = 1.0;
    const c = 0.3;
    const pts = chamfer
      ? [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2 - c], [w / 2 - c, h / 2], [-w / 2, h / 2]]
      : [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]];
    return pts.map(([x, y]) => v3(x, y, 0.02));
  };
  const diagram = (chamfer, y) => {
    const g = new THREE.Group();
    g.position.set(DX, y, 0);
    const ghost = new InkLine(sketchPart(chamfer), { width: 1, closed: true, dashed: true, dash: 0.05, gap: 0.04, hex: T.inkSoft, progress: 0 });
    const rotG = new THREE.Group();
    const body = new InkLine(sketchPart(chamfer), { width: 2.2, closed: true, hex: chamfer ? T.part : T.ink, progress: 0 });
    const ax = arrowPts(v3(0, 0, 0.02), v3(0.62, 0, 0.02), 0.12).map((pts) => new InkLine(pts, { width: 1.6, hex: MODULE_COLOR.M1, progress: 0 }));
    rotG.add(body.object, ...ax.map((a) => a.object));
    g.add(ghost.object, rotG);
    const label = text(chamfer ? 'mit Fase: 180° sieht anders aus → 0–360° eindeutig' : 'ohne Fase: 0° und 180° sehen gleich aus', {
      font: 'sans', size: 0.16, anchorX: 'left', anchorY: 'middle', maxWidth: 2.2, opacity: 0, hex: chamfer ? T.ink : T.inkSoft,
    });
    label.position.set(1.05, 0, 0.03);
    g.add(label);
    scene.add(g);
    return { ghost, rotG, body, ax, label };
  };
  const dNo = diagram(false, 1.55);
  const dYes = diagram(true, -0.55);

  // ---------- 3.5 Drei Koordinatensysteme ----------
  const rot = (cfg.workspace_to_robot.rotation_deg * Math.PI) / 180;
  const [tx, ty] = cfg.workspace_to_robot.translation_mm;
  // Roboterbasis im Arbeitsraum: ws = R^T (0 - t)
  const bx = Math.cos(rot) * -tx + Math.sin(rot) * -ty;
  const by = -Math.sin(rot) * -tx + Math.cos(rot) * -ty;
  const baseP = P(bx, by);
  const FR = {
    img: { o: P(0, WS_H).add(v3(-0.14, 0.14)), x: v3(1, 0), y: v3(0, -1), lx: 'u', ly: 'v', name: 'Bild (px)', hex: T.inkSoft },
    ws: { o: P(0, 0).add(v3(-0.14, -0.14)), x: v3(1, 0), y: v3(0, 1), lx: 'x', ly: 'y', name: 'Arbeitsraum (mm)', hex: MODULE_COLOR.M1 },
    rb: { o: baseP, x: v3(Math.cos(rot), Math.sin(rot)), y: v3(-Math.sin(rot), Math.cos(rot)), lx: 'x', ly: 'y', name: 'Roboter-Basis (mm)', hex: MODULE_COLOR.M2 },
  };
  const AX = 1.3;
  const frameObjs = Object.values(FR).map((f, i) => {
    const o = f.o.clone().setZ(0.025);
    const lines = [...arrowPts(o, o.clone().addScaledVector(f.x, AX)), ...arrowPts(o, o.clone().addScaledVector(f.y, AX))].map((pts) => {
      const l = new InkLine(pts, { width: 2.4, hex: f.hex, progress: 0 });
      scene.add(l.object);
      return l;
    });
    const tx_ = text(f.lx, { font: 'monoMedium', size: 0.22, hex: f.hex, anchorX: 'center', anchorY: 'middle', opacity: 0 });
    tx_.position.copy(o.clone().addScaledVector(f.x, AX + 0.25)).setZ(0.03);
    const ty_ = text(f.ly, { font: 'monoMedium', size: 0.22, hex: f.hex, anchorX: 'center', anchorY: 'middle', opacity: 0 });
    ty_.position.copy(o.clone().addScaledVector(f.y, AX + 0.25)).setZ(0.03);
    const isBase = f === FR.rb;
    const name = text(f.name, { font: 'title', size: 0.24, hex: f.hex, anchorX: isBase ? 'center' : 'right', anchorY: f.y.y < 0 || isBase ? 'top' : 'bottom', opacity: 0 });
    name.position.copy(o.clone().add(isBase ? v3(0, -95 * K - 0.15) : f === FR.ws ? v3(-0.2, 1.1) : v3(-0.2, -0.25))).setZ(0.03);
    scene.add(tx_, ty_, name);
    return { lines, texts: [tx_, ty_, name], delay: i * 0.25 };
  });
  const baseRing = new InkLine(circle(baseP, 95 * K), { width: 1.4, dashed: true, dash: 0.1, gap: 0.07, hex: MODULE_COLOR.M2, progress: 0 });
  scene.add(baseRing.object);
  const baseLabel = text('LARA', { font: 'title', size: 0.3, hex: MODULE_COLOR.M2, anchorX: 'center', anchorY: 'bottom', opacity: 0 });
  baseLabel.position.set(baseP.x, baseP.y + 95 * K + 0.15, 0.03);
  scene.add(baseLabel);

  const ru = shot.centre_rect[0] * shot.rect_size[0];
  const rv = shot.centre_rect[1] * shot.rect_size[1];
  const coords = [
    [FR.img, `u ${Math.round(ru)} · v ${Math.round(rv)} px`],
    [FR.ws, `x ${fmt(shot.ws.x)} · y ${fmt(shot.ws.y)} mm · ${fmt(shot.ws.theta)}°`],
    [FR.rb, `x ${fmt(shot.robot.x)} · y ${fmt(shot.robot.y)} mm · ${fmt(shot.robot.theta)}°`],
  ];
  const vecObjs = coords.map(([f, label], i) => {
    const line = new InkLine([f.o.clone().setZ(0.022), centre.clone().setZ(0.022)], { width: 1.6, dashed: true, dash: 0.1, gap: 0.07, hex: f.hex, progress: 0 });
    scene.add(line.object);
    const t = text(label, { font: 'monoMedium', size: 0.2, hex: f.hex, anchorX: 'left', anchorY: 'middle', opacity: 0 });
    t.position.set(4.0, 1.85 - i * 0.55, 0.03);
    const b = new Balloon(String(i + 1), { r: 0.17, size: 0.14, hex: f.hex });
    b.object.position.set(3.7, 1.85 - i * 0.55, 0.03);
    scene.add(t, b.object);
    return { line, t, b, delay: i * 0.33 };
  });
  const vecHead = text('Bauteilmitte in drei Systemen', { font: 'title', size: 0.26, anchorY: 'bottom', opacity: 0 });
  vecHead.position.set(3.55, 2.25, 0.03);
  scene.add(vecHead);

  // eine Zeile, Farbe je Abschnitt (troika colorRanges)
  const parts = [['Bild', FR.img.hex], ['  – Homographie H (4 Marker) →  ', T.ink], ['Arbeitsraum', FR.ws.hex], ['  – R, t (Kalibrierung) →  ', T.ink], ['Roboter-Basis', FR.rb.hex]];
  const chainText = text(parts.map((p) => p[0]).join(''), { font: 'title', size: 0.26, anchorY: 'middle', opacity: 0 });
  const ranges = {};
  parts.reduce((at, [str, hex]) => ((ranges[at] = color(hex).getHex()), at + str.length), 0);
  chainText.colorRanges = ranges;
  chainText.position.set(-8.6, -4.45, 0.03);
  scene.add(chainText);
  const chain = [chainText];
  const calibNote = text(
    `robot_check calib: der TCP fährt die vier Marker-Mitten an, R und t folgen per Least Squares (hier: ${fmt(cfg.workspace_to_robot.rotation_deg, 2)}°, ${fmt(tx)} / ${fmt(ty)} mm).`,
    { font: 'sans', size: 0.17, hex: T.inkSoft, anchorY: 'top', maxWidth: 13, opacity: 0 },
  );
  calibNote.position.set(-8.6, -4.8, 0.03);
  scene.add(calibNote);
  // TCP-Rundgang über die Marker
  const tcp = new THREE.Group();
  const tcpRing = new InkLine(circle(v3(0, 0), 0.22, 32, 0.03), { width: 2.2, hex: MODULE_COLOR.M2, closed: true });
  const tcpX = new InkLine([v3(-0.32, 0, 0.03), v3(0.32, 0, 0.03)], { width: 1.4, hex: MODULE_COLOR.M2 });
  const tcpY = new InkLine([v3(0, -0.32, 0.03), v3(0, 0.32, 0.03)], { width: 1.4, hex: MODULE_COLOR.M2 });
  tcp.add(tcpRing.object, tcpX.object, tcpY.object);
  scene.add(tcp);
  const tourPts = [baseP, ...mWarp, baseP];
  const visited = mWarp.map((m) => {
    const l = new InkLine(circle(m, 0.42, 40, 0.025), { width: 1.4, hex: MODULE_COLOR.M2, closed: true, progress: 0 });
    scene.add(l.object);
    return l;
  });

  // ---------- update ----------
  const pos = geo.attributes.position;
  let lastWarp = -1;

  function update() {
    // 3.1
    sketch.forEach((l, i) => {
      l.progress = clamp01(S.sketch * sketch.length * 0.8 - i * 0.6);
      l.opacity = 1 - S.center;
    });
    sketchTexts.forEach(([t], i) => (t.opacity = clamp01(S.sketch * 2.5 - 1 - i * 0.2) * (1 - S.center)));

    const c = S.center;
    const s = PHOTO_SMALL.s + (1 - PHOTO_SMALL.s) * c;
    photoGroup.position.set(PHOTO_SMALL.x * (1 - c), PHOTO_SMALL.y * (1 - c), 0);
    photoGroup.scale.setScalar(s);
    photoGroup.visible = S.photo > 0;
    card.material.opacity = S.photo * (1 - c);
    caption.opacity = S.photo * (1 - c);

    // Foto: Verformung und Zuschnitt (nur bei Änderung neu rechnen)
    if (S.warp !== lastWarp) {
      const w = S.warp;
      for (let k = 0; k < nv * 3; k++) pos.array[k] = flat[k] + (warped[k] - flat[k]) * w;
      pos.needsUpdate = true;
      lastWarp = S.warp;
    }
    photoMat.opacity = S.photo;
    cropU.value = S.crop;

    // 3.2 Marker folgen der Verformung
    const mPos = mFlat.map((m, i) => m.clone().lerp(mWarp[i], S.warp).setZ(0.02));
    const outward = (i) => mPos[i].clone().setZ(0).normalize();
    markerRings.forEach((l, i) => {
      l.object.position.copy(mPos[i]).setZ(0);
      l.progress = clamp01(S.markers * 1.4 - i * 0.12);
      l.opacity = 1 - S.crop;
    });
    markerSquares.forEach((l) => (l.progress = S.frame));
    markerIds.forEach((b, i) => {
      b.object.position.copy(mPos[i].clone().addScaledVector(outward(i), 0.85)).setZ(0.03);
      b.appear = clamp01(S.markers * 1.8 - 0.3 - i * 0.12) * (1 - S.frames);
    });
    setPts(quad, [...mPos, mPos[0]].map((p) => p.clone().setZ(0.021)));
    quad.progress = S.quad;
    quad.opacity = 1 - S.crop;
    quadNote.opacity = clamp01(S.quad * 2 - 0.5) * (1 - S.crop);

    frame.progress = S.frame;
    frame.opacity = 1 - S.mask * 0.6;
    dimW.appear = S.frame * (1 - S.mask);
    dimH.appear = S.frame * (1 - S.mask);
    pxNote.opacity = clamp01(S.frame * 2 - 1) * (1 - S.mask);

    // 3.3
    maskMat.opacity = S.mask * (1 - S.maskOff);
    mask.visible = maskMat.opacity > 0.001;
    contour.progress = S.contour;
    contour.opacity = 1;
    boxLine.progress = clamp01(S.contour * 1.6 - 0.4);
    boxLine.opacity = 1 - S.axis * 0.5;
    dimL.appear = clamp01(S.contour * 1.5 - 0.5) * (1 - S.axis);
    dimS.appear = clamp01(S.contour * 1.5 - 0.6) * (1 - S.axis);
    parallax.opacity = S.parallax * (1 - S.axis);
    segNote.opacity = clamp01(S.mask * 2 - 0.6) * (1 - S.axis);

    // 3.4
    axisLines.forEach((l) => (l.progress = clamp01(S.axis * 2)));
    refLine.progress = clamp01(S.axis * 2 - 0.4);
    angArc.progress = clamp01(S.axis * 2 - 0.7);
    angLabel.opacity = clamp01(S.axis * 2 - 1.3) * (1 - S.frames);
    chamferRing.progress = clamp01(S.axis * 1.6 - 0.6);
    chamferLabel.opacity = clamp01(S.axis * 2 - 1.2) * (1 - S.frames);
    [refLine, angArc].forEach((l) => (l.opacity = 1 - S.frames));
    for (const d of [dNo, dYes]) {
      const vis = S.diagrams * (1 - S.frames);
      d.ghost.progress = clamp01(S.diagrams * 2 - 0.2);
      d.body.progress = clamp01(S.diagrams * 2);
      d.ax.forEach((a) => (a.progress = clamp01(S.diagrams * 2 - 0.6)));
      d.rotG.rotation.z = S.rot * Math.PI;
      d.label.opacity = clamp01(S.rot * 1.6 - 0.4) * vis;
      for (const l of [d.ghost, d.body, ...d.ax]) l.opacity = vis;
    }

    // 3.5
    frameObjs.forEach((f) => {
      const v = clamp01((S.frames - f.delay) / 0.5);
      f.lines.forEach((l) => (l.progress = v));
      f.texts.forEach((t) => (t.opacity = clamp01(v * 2 - 1)));
    });
    baseRing.progress = S.frames;
    baseLabel.opacity = clamp01(S.frames * 2 - 1);
    vecHead.opacity = clamp01(S.vectors * 3);
    vecObjs.forEach((o) => {
      const v = clamp01((S.vectors - o.delay) / 0.34);
      o.line.progress = v;
      o.t.opacity = clamp01(v * 2 - 1);
      o.b.appear = v;
    });
    chain.forEach((t, i) => (t.opacity = clamp01(S.calib * 3 - i * 0.4)));
    calibNote.opacity = clamp01(S.calib * 2 - 1);
    // TCP: Basis → Marker 0 … 3 → Basis
    const seg = S.tour * (tourPts.length - 1);
    const si = Math.min(tourPts.length - 2, Math.floor(seg));
    tcp.position.copy(tourPts[si].clone().lerp(tourPts[si + 1], EASE_IO(seg - si))).setZ(0);
    tcp.visible = S.tour > 0 && S.tour < 1;
    visited.forEach((l, i) => (l.progress = clamp01((seg - i - 0.6) * 3)));
  }
  return { scene, S, defaults: DEFAULTS, update };
}

const EASE_IO = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

// ---------- Kameras ----------
const cam = (lx, ly, pz, fov = 30) => ({ lx, ly, lz: 0, px: lx, py: ly - 0.01, pz, fov });
const C = {
  overview: cam(0, 0, 19.5),
  center: cam(0, -0.2, 19.5),
  part: (ctx) => partCam(ctx, 0, 7),
  angle: (ctx) => partCam(ctx, 2.6, 12),
  frames: cam(-2.2, -0.3, 21),
};
function partCam(ctx, dx, pz) {
  const shot = ctx.data.m1.shots[SHOT];
  const [W, Hh] = ctx.data.config.workspace.size_mm;
  const x = (shot.centre_rect[0] * W - W / 2) * K + dx;
  const y = (Hh - shot.centre_rect[1] * Hh - Hh / 2) * K;
  return cam(x + 0.5, y + 0.15, pz);
}

const to = (tl, S, vars, pos = 0) => tl.to(S, { ease: EASE.appear, ...vars }, pos);

export const VISION_SCENES = [
  {
    id: '3.1', world: 'vision',
    steps: [
      (tl, S, ctx) => {
        to(tl, S, { sketch: 1, duration: 2.8, ease: 'power1.inOut' }, 0.1);
        tl.to(ctx.stage.flash, { v: 0.85, duration: 0.06, ease: 'none' }, 3.0);
        tl.to(ctx.stage.flash, { v: 0, duration: 0.7, ease: 'power2.out' }, 3.06);
        to(tl, S, { photo: 1, duration: 0.9, ease: 'power2.out' }, 3.06);
      },
    ],
    cams: [C.overview],
  },
  {
    id: '3.2', world: 'vision',
    steps: [
      (tl, S) => {
        to(tl, S, { center: 1, duration: 1.6, ease: EASE.move }, 0);
        to(tl, S, { markers: 1, duration: 1.4, ease: 'power1.out' }, 1.4);
      },
      (tl, S) => {
        to(tl, S, { quad: 1, duration: 1.0, ease: 'power1.inOut' }, 0);
        to(tl, S, { warp: 1, duration: 3.0, ease: 'power2.inOut' }, 1.1);
      },
      (tl, S) => {
        to(tl, S, { crop: 1, duration: 1.4, ease: 'power1.inOut' }, 0);
        to(tl, S, { frame: 1, duration: 1.6, ease: 'power1.inOut' }, 0.6);
      },
    ],
    cams: [C.center, C.center, C.center],
  },
  {
    id: '3.3', world: 'vision',
    steps: [
      (tl, S) => to(tl, S, { mask: 1, duration: 1.8, ease: 'power1.inOut' }, 0.6),
      (tl, S) => {
        to(tl, S, { maskOff: 1, duration: 1.0, ease: 'power1.out' }, 0);
        to(tl, S, { contour: 1, duration: 2.2, ease: 'power1.inOut' }, 0.2);
      },
      (tl, S) => to(tl, S, { parallax: 1, duration: 1.2 }, 0),
    ],
    cams: [C.part, C.part, C.part],
  },
  {
    id: '3.4', world: 'vision',
    steps: [
      (tl, S) => to(tl, S, { axis: 1, duration: 2.0, ease: 'power1.inOut' }, 0.3),
      (tl, S) => {
        to(tl, S, { diagrams: 1, duration: 1.2, ease: 'power1.inOut' }, 0);
        to(tl, S, { rot: 1, duration: 2.2, ease: 'power2.inOut' }, 1.3);
      },
    ],
    cams: [C.part, C.angle],
  },
  {
    id: '3.5', world: 'vision',
    steps: [
      (tl, S) => to(tl, S, { frames: 1, duration: 2.2, ease: 'power1.inOut' }, 0.4),
      (tl, S) => to(tl, S, { vectors: 1, duration: 2.6, ease: 'power1.inOut' }, 0),
      (tl, S) => {
        to(tl, S, { calib: 1, duration: 1.8, ease: 'power1.out' }, 0);
        to(tl, S, { tour: 1, duration: 4.5, ease: 'none' }, 0.6);
      },
    ],
    cams: [C.frames, C.frames, C.frames],
  },
];
