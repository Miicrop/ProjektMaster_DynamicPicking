// Bausteine im Zeichnungsstil: Tuschelinien (mit Zeichen-Fortschritt), Text, Positionsnummern,
// Maßlinien, Fotokarten, schraffierte Körper. Alles wird über einfache Zahlenwerte gesteuert,
// damit GSAP sie tweenen und progress(1) sie exakt setzen kann.
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { Text } from 'troika-three-text';
import { T, FONTS, color } from '../theme.js';
import { LAYER_SOLID } from '../engine/stage.js';

let stageRef = null;
export function bindStage(stage) {
  stageRef = stage;
}

function densify(points, step) {
  const out = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    const n = Math.max(1, Math.ceil(a.distanceTo(b) / step));
    for (let k = 1; k <= n; k++) out.push(a.clone().lerp(b, k / n));
  }
  return out;
}

/**
 * Tuschelinie. `progress` 0..1 zieht die Linie von Anfang bis Ende, `opacity` blendet.
 * Gestrichelte Linien (dashed) werden segmentweise gezogen, durchgezogene über den Strich-Trick.
 */
export class InkLine {
  constructor(points, { width = 1.6, hex = T.ink, dashed = false, dash = 0.1, gap = 0.07, closed = false, progress = 1 } = {}) {
    let pts = points.map((p) => (p.isVector3 ? p.clone() : new THREE.Vector3(p[0], p[1], p[2] ?? 0)));
    if (closed) pts.push(pts[0].clone());
    if (dashed) pts = densify(pts, 0.04);
    this.length = 0;
    for (let i = 1; i < pts.length; i++) this.length += pts[i - 1].distanceTo(pts[i]);
    this.segments = pts.length - 1;
    this.dashedStyle = dashed;
    const geo = new LineGeometry();
    geo.setPositions(pts.flatMap((p) => [p.x, p.y, p.z]));
    const mat = new LineMaterial({
      color: color(hex),
      linewidth: width,
      dashed: true,
      dashScale: 1,
      dashSize: dashed ? dash : this.length + 1,
      gapSize: dashed ? gap : this.length * 2 + 1,
      transparent: true,
      depthWrite: false,
    });
    stageRef?.registerLineMaterial(mat);
    this.object = new Line2(geo, mat);
    this.object.computeLineDistances();
    this.object.renderOrder = 2;
    this.object.frustumCulled = false;
    this._progress = -1;
    this._opacity = 1;
    this.progress = progress;
  }
  get progress() {
    return this._progress;
  }
  set progress(p) {
    p = Math.min(1, Math.max(0, p));
    if (p === this._progress) return;
    this._progress = p;
    if (this.dashedStyle) {
      this.object.geometry.instanceCount = Math.ceil(this.segments * p);
    } else {
      this.object.material.dashSize = p >= 1 ? this.length + 1 : p * this.length;
    }
    this.object.visible = p > 0 && this._opacity > 0;
  }
  get opacity() {
    return this._opacity;
  }
  set opacity(o) {
    this._opacity = o;
    this.object.material.opacity = o;
    this.object.visible = this._progress > 0 && o > 0;
  }
  set hex(h) {
    this.object.material.color.set(h);
  }
}

// Zeichen außerhalb des Latin-Subsets der Schriften würde troika von einem CDN nachladen (offline: Fehler)
const GLYPH_MAP = { '→': '›', '↔': '/', '≈': '~', '≥': '>=', '≤': '<=', '⟨': '[', '⟩': ']', '✂': '' };
const safe = (str) => str.replace(/[→↔≈≥≤⟨⟩✂]/g, (c) => GLYPH_MAP[c]);

/**
 * Viele Einzelstriche in einem Objekt (z. B. Verbindungen zwischen Bildern).
 * set(i, a, b) setzt Strich i, setColor(i, hex/Color) seine Farbe; commit() nach Änderungen.
 * `progress` zeigt die ersten n·progress Striche, `opacity` blendet alle.
 */
export class InkSegments {
  constructor(n, { width = 1, hex = T.ink, opacity = 1 } = {}) {
    this.n = n;
    const geo = new LineSegmentsGeometry();
    geo.setPositions(new Float32Array(n * 6));
    const cols = new Float32Array(n * 6);
    const c = color(hex);
    for (let i = 0; i < n * 2; i++) cols.set([c.r, c.g, c.b], i * 3);
    geo.setColors(cols);
    const mat = new LineMaterial({ linewidth: width, vertexColors: true, transparent: true, depthWrite: false, opacity });
    stageRef?.registerLineMaterial(mat);
    this.object = new LineSegments2(geo, mat);
    this.object.frustumCulled = false;
    this.object.renderOrder = 2;
    this.pos = geo.attributes.instanceStart.data;
    this.col = geo.attributes.instanceColorStart.data;
    this._progress = 1;
  }
  set(i, a, b) {
    this.pos.array.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
  }
  setXYZ(i, ax, ay, az, bx, by, bz) {
    const p = this.pos.array;
    const k = i * 6;
    p[k] = ax; p[k + 1] = ay; p[k + 2] = az; p[k + 3] = bx; p[k + 4] = by; p[k + 5] = bz;
  }
  setColor(i, c) {
    const col = c.isColor ? c : color(c);
    this.col.array.set([col.r, col.g, col.b, col.r, col.g, col.b], i * 6);
  }
  commit() {
    this.pos.needsUpdate = true;
    this.col.needsUpdate = true;
    this.object.geometry.computeBoundingSphere();
  }
  get progress() {
    return this._progress;
  }
  set progress(p) {
    this._progress = p;
    this.object.geometry.instanceCount = Math.round(this.n * Math.min(1, Math.max(0, p)));
    this.object.visible = p > 0 && this.object.material.opacity > 0;
  }
  get opacity() {
    return this.object.material.opacity;
  }
  set opacity(o) {
    this.object.material.opacity = o;
    this.object.visible = this._progress > 0 && o > 0;
  }
}

/** Text auf dem Papier. `opacity` steuert die Deckkraft. */
export function text(str, { font = 'sans', size = 0.3, hex = T.ink, anchorX = 'left', anchorY = 'middle', maxWidth = Infinity,
  lineHeight = 1.25, letterSpacing = 0, align = 'left', opacity = 1 } = {}) {
  const t = new Text();
  t.text = safe(str);
  t.font = FONTS[font];
  t.fontSize = size;
  t.color = hex;
  t.anchorX = anchorX;
  t.anchorY = anchorY;
  t.maxWidth = maxWidth;
  t.lineHeight = lineHeight;
  t.letterSpacing = letterSpacing;
  t.textAlign = align;
  t.fillOpacity = opacity;
  t.renderOrder = 3;
  t.material.depthWrite = false;
  t.sync();
  Object.defineProperty(t, 'opacity', {
    get() { return this.fillOpacity; },
    set(v) { this.fillOpacity = v; this.visible = v > 0.001; },
  });
  t.opacity = opacity;
  return t;
}

function circlePoints(r, n = 48) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 + Math.PI / 2;
    pts.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, 0));
  }
  return pts;
}

/** Positionsnummer im Kreis. `appear` 0..1 zeichnet den Kreis und blendet die Zahl ein. */
export class Balloon {
  constructor(label, { r = 0.17, size = 0.15, hex = T.ink, fill = T.paper } = {}) {
    this.object = new THREE.Group();
    this.disc = new THREE.Mesh(new THREE.CircleGeometry(r, 40), new THREE.MeshBasicMaterial({ color: color(fill), transparent: true, depthWrite: false }));
    this.disc.renderOrder = 4;
    this.ring = new InkLine(circlePoints(r), { width: 1.4, hex, closed: true, progress: 0 });
    this.label = text(label, { font: 'monoMedium', size, hex, anchorX: 'center', anchorY: 'middle', opacity: 0 });
    this.label.position.z = 0.002;
    this.ring.object.renderOrder = 5;
    this.label.renderOrder = 6;
    this.object.add(this.disc, this.ring.object, this.label);
    this._appear = -1;
    this.appear = 0;
  }
  get appear() {
    return this._appear;
  }
  set appear(v) {
    this._appear = v;
    this.ring.progress = Math.min(1, v * 1.4);
    this.label.opacity = Math.max(0, (v - 0.5) * 2);
    this.disc.material.opacity = Math.min(1, v * 2);
    this.object.visible = v > 0;
  }
}

/** Pfeilspitze (gefülltes Dreieck) in der Papierebene, Spitze bei (0,0), zeigt nach +x. */
function arrowHead(hex, s = 0.12) {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.lineTo(-s, s * 0.32);
  shape.lineTo(-s, -s * 0.32);
  shape.closePath();
  const m = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: color(hex), transparent: true, depthWrite: false }));
  m.renderOrder = 2;
  return m;
}

/**
 * Maßlinie zwischen a und b (Papierebene, z beliebig), mit Hilfslinien `ext` vom Objekt weg.
 * `appear` 0..1: Hilfslinien, dann Maßlinie mit Pfeilen, dann Beschriftung.
 */
export class Dimension {
  constructor(a, b, label, { offset = new THREE.Vector3(), hex = T.ink, size = 0.26, font = 'monoMedium', labelOffset = 0.22,
    extFrom = null, labelRot = null } = {}) {
    this.object = new THREE.Group();
    const A = a.clone().add(offset);
    const B = b.clone().add(offset);
    this.exts = [];
    if (extFrom) {
      this.exts.push(new InkLine([extFrom[0], A], { width: 1, hex, progress: 0 }));
      this.exts.push(new InkLine([extFrom[1], B], { width: 1, hex, progress: 0 }));
    }
    this.main = new InkLine([A, B], { width: 1.4, hex, progress: 0 });
    const dir = B.clone().sub(A).normalize();
    const ang = Math.atan2(dir.y, dir.x);
    this.headA = arrowHead(hex);
    this.headA.position.copy(A);
    this.headA.rotation.z = ang + Math.PI;
    this.headB = arrowHead(hex);
    this.headB.position.copy(B);
    this.headB.rotation.z = ang;
    const mid = A.clone().add(B).multiplyScalar(0.5);
    const nrm = new THREE.Vector3(-dir.y, dir.x, 0);
    this.label = text(label, { font, size, hex, anchorX: 'center', anchorY: 'middle', opacity: 0 });
    this.label.position.copy(mid).addScaledVector(nrm, labelOffset);
    let rot = ang;
    if (rot > Math.PI / 2) rot -= Math.PI;
    if (rot < -Math.PI / 2) rot += Math.PI;
    this.label.rotation.z = labelRot ?? rot;
    if (labelRot !== null && labelRot !== undefined) {
      this.label.anchorX = labelOffset < 0 ? 'left' : 'right';
      this.label.position.copy(mid).addScaledVector(nrm, labelOffset);
    }
    this.object.add(...this.exts.map((e) => e.object), this.main.object, this.headA, this.headB, this.label);
    this._appear = -1;
    this.appear = 0;
  }
  get appear() {
    return this._appear;
  }
  set appear(v) {
    this._appear = v;
    const e = Math.min(1, v * 3);
    for (const x of this.exts) x.progress = e;
    this.main.progress = Math.min(1, Math.max(0, (v - 0.2) * 2.2));
    const h = v > 0.65 ? 1 : 0;
    this.headA.visible = this.headB.visible = h > 0;
    this.label.opacity = Math.max(0, (v - 0.65) / 0.35);
    this.object.visible = v > 0;
  }
}

const texLoader = new THREE.TextureLoader();
const texCache = new Map();
export function tex(url) {
  if (!texCache.has(url)) {
    const t = texLoader.load(url);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    texCache.set(url, t);
  }
  return texCache.get(url);
}

/** Fotokarte: Bild mit weißem Rand, wirft Schatten, Kontur über die Tuschekanten. */
export class PhotoCard {
  constructor(url, { width = 4, aspect = 708 / 1266, border = 0.12, bottom = 0.12 } = {}) {
    const h = width * aspect;
    this.object = new THREE.Group();
    const cardGeo = new THREE.BoxGeometry(width + border * 2, h + border + bottom, 0.03);
    this.card = new THREE.Mesh(cardGeo, new THREE.MeshStandardMaterial({ color: 0xfbfaf6, roughness: 0.95, transparent: true, emissive: 0xb4b2ac }));
    this.card.position.y = (border - bottom) / 2 * -1;
    this.card.castShadow = true;
    this.card.layers.enable(LAYER_SOLID);
    this.photo = new THREE.Mesh(new THREE.PlaneGeometry(width, h), new THREE.MeshBasicMaterial({ map: tex(url), transparent: true, toneMapped: false }));
    this.photo.position.z = 0.0155;
    this.object.add(this.card, this.photo);
    this.width = width;
    this.height = h;
    this._opacity = 1;
  }
  get opacity() {
    return this._opacity;
  }
  set opacity(o) {
    this._opacity = o;
    this.card.material.opacity = o;
    this.photo.material.opacity = o;
    this.object.visible = o > 0.001;
  }
}

/** Schraffur-Textur (45°-Linien) für Querschnitte und die „Black Box“. */
export function hatchTexture(hex = T.ink, bg = T.paper, spacing = 14, width = 2) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = bg;
  g.fillRect(0, 0, 128, 128);
  g.strokeStyle = hex;
  g.lineWidth = width;
  for (let i = -128; i < 256; i += spacing) {
    g.beginPath();
    g.moveTo(i, 128);
    g.lineTo(i + 128, 0);
    g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Volumenkörper mit Tuschekante (Layer SOLID) und Schatten. */
export function solid(geometry, hex, { roughness = 0.9, map = null } = {}) {
  const m = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: color(hex), roughness, metalness: 0, map }));
  m.castShadow = true;
  m.layers.enable(LAYER_SOLID);
  return m;
}

export const v3 = (x, y, z = 0) => new THREE.Vector3(x, y, z);
