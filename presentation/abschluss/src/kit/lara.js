// Neura LARA 5 aus der URDF (public/urdf/lara5.urdf): Szenengraph mit den STL-Meshes, Vorwärts- und
// numerische Rückwärtskinematik (gedämpfte kleinste Quadrate). Einheiten wie in der URDF: Meter, Radiant.
// Geprüft gegen system.yaml: Home (TCP 420/0/237 mm, rx 180, rz 180) ergibt Flansch-z 434,5 mm wie im
// Roboter-Backup; alle Stationsposen sind vom Home-Seed aus erreichbar.
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { solid } from './ink.js';

const vec = (s, d) => (s ? s.trim().split(/\s+/).map(Number) : d);
/** URDF/Neura-Konvention: feste Achsen x, y, z → R = Rz(y) · Ry(p) · Rx(r). */
export const rpyMatrix = (r, p, y) => new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(r, p, y, 'ZYX'));

function originOf(el) {
  const o = el?.querySelector(':scope > origin');
  const [x, y, z] = vec(o?.getAttribute('xyz'), [0, 0, 0]);
  const [r, p, w] = vec(o?.getAttribute('rpy'), [0, 0, 0]);
  return rpyMatrix(r, p, w).setPosition(x, y, z);
}

/** Lädt URDF und alle Visual-Meshes. Ergebnis: { chain, visuals, geos } */
export async function loadLara(url) {
  const base = url.slice(0, url.lastIndexOf('/') + 1);
  const xml = new DOMParser().parseFromString(await (await fetch(url)).text(), 'application/xml');
  const byChild = new Map();
  for (const j of xml.querySelectorAll('robot > joint')) {
    const lim = j.querySelector('limit');
    byChild.set(j.querySelector('child').getAttribute('link'), {
      name: j.getAttribute('name'),
      type: j.getAttribute('type'),
      parent: j.querySelector('parent').getAttribute('link'),
      child: j.querySelector('child').getAttribute('link'),
      origin: originOf(j),
      axis: new THREE.Vector3(...vec(j.querySelector('axis')?.getAttribute('xyz'), [0, 0, 1])).normalize(),
      lower: lim ? +lim.getAttribute('lower') : -Math.PI,
      upper: lim ? +lim.getAttribute('upper') : Math.PI,
    });
  }
  const chain = [];
  for (let link = 'lara5_flange'; byChild.has(link); link = byChild.get(link).parent) chain.unshift(byChild.get(link));
  const visuals = new Map();
  for (const l of xml.querySelectorAll('robot > link')) {
    visuals.set(l.getAttribute('name'), [...l.querySelectorAll(':scope > visual')].map((v) => ({
      file: v.querySelector('mesh')?.getAttribute('filename'),
      origin: originOf(v),
    })).filter((v) => v.file));
  }
  const loader = new STLLoader();
  const files = [...new Set([...visuals.values()].flat().map((v) => v.file))];
  const geos = new Map(await Promise.all(files.map(async (f) => [f, await loader.loadAsync(base + f)])));
  return { chain, visuals, geos };
}

const COLORS = { body: '#ECE9E2', rings: '#A9AEB3', connector: '#5C6166' };

export class Lara {
  /** `tool` = TCP-Abstand vom Flansch entlang Flansch-z [m]. */
  constructor(model, { tool = 0.1975 } = {}) {
    this.chain = model.chain;
    this.tool = tool;
    this.object = new THREE.Group(); // Roboter-Basis-KS in Metern
    this.pivots = [];
    this.meshes = [];
    let parent = this.object;
    for (const j of this.chain) {
      const g = new THREE.Group();
      g.matrixAutoUpdate = false;
      g.matrix.copy(j.origin);
      parent.add(g);
      let holder = g;
      if (j.type === 'revolute') {
        holder = new THREE.Group();
        g.add(holder);
        this.pivots.push({ g: holder, axis: j.axis });
      }
      for (const v of model.visuals.get(j.child) ?? []) {
        const kind = v.file.includes('rings') ? 'rings' : v.file.includes('connector') ? 'connector' : 'body';
        const m = solid(model.geos.get(v.file), COLORS[kind], { roughness: 0.75 });
        m.matrixAutoUpdate = false;
        m.matrix.copy(v.origin);
        holder.add(m);
        this.meshes.push(m);
      }
      parent = holder;
    }
    this.flange = parent; // Flansch-KS: z zeigt aus dem Flansch
    this.q = [0, 0, 0, 0, 0, 0];
  }

  setJoints(q) {
    this.q = q;
    this.pivots.forEach((p, i) => p.g.quaternion.setFromAxisAngle(p.axis, q[i]));
  }

  /** TCP (bzw. Flansch mit `tool = 0`) im Basis-KS für Gelenkwinkel q. */
  fk(q, out = new THREE.Matrix4(), tool = this.tool) {
    out.identity();
    const r = _m;
    let k = 0;
    for (const j of this.chain) {
      out.multiply(j.origin);
      if (j.type === 'revolute') out.multiply(r.makeRotationAxis(j.axis, q[k++]));
    }
    return out.multiply(r.makeTranslation(0, 0, tool));
  }

  /** Ursprünge aller Gelenke und der Flansch im Basis-KS [m] (für grobe Kollisionsprüfungen). */
  jointPoints(q) {
    const m = new THREE.Matrix4();
    const pts = [new THREE.Vector3()];
    let k = 0;
    for (const j of this.chain) {
      m.multiply(j.origin);
      if (j.type === 'revolute') m.multiply(_m.makeRotationAxis(j.axis, q[k++]));
      const p = new THREE.Vector3().setFromMatrixPosition(m);
      if (p.distanceTo(pts[pts.length - 1]) > 1e-6) pts.push(p);
    }
    return pts;
  }

  /** Rückwärtskinematik vom Startwert `seed` aus; `target` = TCP-Matrix im Basis-KS. */
  ik(target, seed, { iterations = 60, tol = 1e-9 } = {}) {
    const q = seed.slice();
    const P = new THREE.Vector3().setFromMatrixPosition(target);
    const R = new THREE.Matrix4().extractRotation(target);
    const err = (qq) => poseError(this.fk(qq, _a), P, R);
    for (let it = 0; it < iterations; it++) {
      const e = err(q);
      if (e.reduce((s, v) => s + v * v, 0) < tol) break;
      const J = [];
      for (let k = 0; k < 6; k++) {
        const dq = q.slice();
        dq[k] += 1e-6;
        const e2 = err(dq);
        J.push(e.map((v, i) => (v - e2[i]) / 1e-6)); // Spalte k
      }
      // dq = J^T (J J^T + λI)^-1 e
      const A = Array.from({ length: 6 }, (_, i) => Array.from({ length: 6 }, (_, k) => J.reduce((s, col) => s + col[i] * col[k], 0) + (i === k ? 1e-4 : 0)));
      const x = solve(A, e.slice());
      for (let k = 0; k < 6; k++) q[k] += J[k].reduce((s, v, i) => s + v * x[i], 0);
    }
    return q;
  }
}

const _m = new THREE.Matrix4();
const _a = new THREE.Matrix4();
const _R = new THREE.Matrix4();

/** 6er-Fehler: Position [m] und gewichtete Orientierung (Achse·Winkel aus R_ziel · R_istᵀ). */
function poseError(M, P, R) {
  const p = new THREE.Vector3().setFromMatrixPosition(M);
  _R.extractRotation(M).transpose().premultiply(R);
  const e = _R.elements; // spaltenweise
  const m00 = e[0], m11 = e[5], m22 = e[10];
  const ang = Math.acos(Math.min(1, Math.max(-1, (m00 + m11 + m22 - 1) / 2)));
  let w = [0, 0, 0];
  if (ang > 1e-9) {
    const f = ang / (2 * Math.sin(ang));
    w = [(e[6] - e[9]) * f, (e[8] - e[2]) * f, (e[1] - e[4]) * f];
  }
  return [P.x - p.x, P.y - p.y, P.z - p.z, 0.3 * w[0], 0.3 * w[1], 0.3 * w[2]];
}

function solve(A, b) {
  const n = b.length;
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    [A[c], A[p]] = [A[p], A[c]];
    [b[c], b[p]] = [b[p], b[c]];
    for (let r = c + 1; r < n; r++) {
      const f = A[r][c] / A[c][c];
      for (let k = c; k < n; k++) A[r][k] -= f * A[c][k];
      b[r] -= f * b[c];
    }
  }
  const x = new Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let s = b[r];
    for (let k = r + 1; k < n; k++) s -= A[r][k] * x[k];
    x[r] = s / A[r][r];
  }
  return x;
}

/** Pose [x, y, z, rx, ry, rz] in mm/° (system.yaml) → TCP-Matrix in Metern. */
export function poseMatrix([x, y, z, rx, ry, rz]) {
  const d = Math.PI / 180;
  return rpyMatrix(rx * d, ry * d, rz * d).setPosition(x / 1000, y / 1000, z / 1000);
}
