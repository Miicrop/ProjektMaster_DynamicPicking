// Ruhige Blätter: Titel, Positionszeilen, Stempel, Tabellen. Jede Szene beschreibt ihren Inhalt
// deklarativ; jedes Element hängt an einem Schritt (0 = Szenenanfang) und blendet sich mit
// kleiner Verzögerung ein. Zustand = S.s0 … S.sN (je 0..1), damit Sprünge exakt bleiben.
import * as THREE from 'three';
import { T, EASE } from '../theme.js';
import { makeWorldScene } from '../engine/stage.js';
import { InkLine, Balloon, text, v3 } from './ink.js';
import { ACTS } from '../storyboard.js';

export const SHEET_W = 16;
export const SHEET_H = 9;
const clamp01 = (x) => Math.min(1, Math.max(0, x));

/**
 * Stempel (Rotstift oder Tusche): doppelter Rahmen + Schrift, „knallt“ beim Erscheinen
 * (startet vergrößert und leicht gedreht). `appear` 0..1.
 */
export class Stamp {
  constructor(label, { hex = T.signal, size = 0.42, rot = 0.1, pad = 0.28, sub = null } = {}) {
    this.object = new THREE.Group();
    this.inner = new THREE.Group();
    this.object.add(this.inner);
    this.t = text(label, { font: 'title', size, hex, anchorX: 'center', anchorY: 'middle', letterSpacing: 0.1, opacity: 0 });
    this.inner.add(this.t);
    this.sub = sub ? text(sub, { font: 'mono', size: size * 0.38, hex, anchorX: 'center', anchorY: 'top', opacity: 0, letterSpacing: 0.04 }) : null;
    // Breite grob aus der Zeichenzahl schätzen (troika misst asynchron)
    const w = Math.max(label.length * size * 0.72, sub ? sub.length * size * 0.25 : 0) + pad * 2;
    const h = size * 1.3 + pad + (sub ? size * 0.6 : 0);
    const cy = sub ? -size * 0.3 : 0;
    this.t.position.y = sub ? size * 0.12 : 0;
    if (this.sub) {
      this.sub.position.y = -size * 0.5;
      this.inner.add(this.sub);
    }
    const rect = (d) => [v3(-w / 2 - d, cy - h / 2 - d), v3(w / 2 + d, cy - h / 2 - d), v3(w / 2 + d, cy + h / 2 + d), v3(-w / 2 - d, cy + h / 2 + d)];
    this.frames = [new InkLine(rect(0), { closed: true, hex, width: 2.6, progress: 0 }), new InkLine(rect(0.07), { closed: true, hex, width: 1.2, progress: 0 })];
    this.frames.forEach((f) => this.inner.add(f.object));
    this.rot = rot;
    this.width = w;
    this._appear = -1;
    this.appear = 0;
  }
  get appear() {
    return this._appear;
  }
  set appear(v) {
    this._appear = v;
    const e = clamp01(v);
    const k = Math.pow(1 - e, 2);
    this.inner.scale.setScalar(1 + 0.7 * k);
    this.inner.rotation.z = this.rot + 0.25 * k;
    const o = clamp01(e * 3);
    this.frames.forEach((f) => {
      f.progress = e > 0 ? 1 : 0;
      f.opacity = o;
    });
    this.t.opacity = o;
    if (this.sub) this.sub.opacity = o;
    this.object.visible = e > 0;
  }
}

/** Element 0..1 sichtbar machen, je nach Art. */
function reveal(obj, v) {
  if (typeof obj === 'function') return obj(v);
  if ('appear' in obj) obj.appear = v;
  else if (obj instanceof InkLine) obj.progress = v;
  else if ('opacity' in obj) obj.opacity = v;
  else obj.visible = v > 0;
}

/**
 * Baut eine Blatt-Welt. `build(api)` legt die Inhalte an:
 *   api.add(step, obj, { delay = 0, dur = 0.5 })   → obj (Text, InkLine, Balloon, Stamp, Funktion v => …)
 *   api.text(step, str, opts, [x, y], timing)       → Text an Position
 *   api.line(step, pts, opts, timing)               → InkLine
 *   api.row(step, n, title, body, y, timing)        → Positionszeile mit Nummer im Kreis
 *   api.stamp(step, label, [x, y], opts, timing)    → Stempel
 *   api.fade(step, objs, timing)                    → blendet früher erschienene Elemente wieder aus
 *   api.scene, api.ctx
 * Rückgabe von build: optional { update(S) } für eigene Animationen.
 */
export function sheetWorld(entry, steps, build) {
  return (ctx) => {
    const scene = makeWorldScene();
    const defaults = Object.fromEntries(Array.from({ length: steps }, (_, i) => [`s${i}`, 0]));
    const S = { ...defaults };
    const items = [];
    const add = (step, obj, { delay = 0, dur = 0.5 } = {}) => {
      if (obj.isObject3D) scene.add(obj);
      else if (obj.object?.isObject3D) scene.add(obj.object);
      items.push({ step, obj, delay, dur });
      reveal(obj, 0);
      return obj;
    };
    const api = {
      scene, ctx, add,
      text(step, str, opts, [x, y] = [0, 0], timing) {
        const t = text(str, { opacity: 0, ...opts });
        t.position.set(x, y, 0.01);
        return add(step, t, timing);
      },
      line(step, pts, opts, timing) {
        return add(step, new InkLine(pts.map((p) => (p.isVector3 ? p : v3(p[0], p[1], p[2] ?? 0))), { progress: 0, ...opts }), timing);
      },
      row(step, n, title, body, y, { x = -SHEET_W / 2 + 1.3, width = SHEET_W - 3.2, size = 0.34, ...timing } = {}) {
        const b = new Balloon(String(n), { r: 0.26, size: 0.2 });
        b.object.position.set(x, y - size * 0.55, 0.01);
        add(step, b, timing);
        const t = api.text(step, title, { font: 'title', size, anchorY: 'top', maxWidth: width }, [x + 0.55, y], { ...timing, delay: (timing.delay ?? 0) + 0.08 });
        const d = body ? api.text(step, body, { font: 'sans', size: size * 0.66, hex: T.inkSoft, anchorY: 'top', maxWidth: width, lineHeight: 1.3 }, [x + 0.55, y - size * 1.25], { ...timing, delay: (timing.delay ?? 0) + 0.16 }) : null;
        return { b, t, d };
      },
      stamp(step, label, [x, y], opts, timing) {
        const s = new Stamp(label, opts);
        s.object.position.set(x, y, 0.03);
        return add(step, s, timing);
      },
      // muss nach den Elementen angelegt werden, deren Deckkraft sie danach dämpft
      fade(step, objs, timing) {
        return add(step, (v) => {
          const k = 1 - v; // auch bei v = 0 anwenden, damit Rücksprünge die Deckkraft zurücksetzen
          for (const o of objs) {
            if (o instanceof Stamp) {
              o.t.opacity *= k;
              if (o.sub) o.sub.opacity *= k;
              o.frames.forEach((f) => (f.opacity *= k));
            } else if (typeof o === 'function' && o.mesh) {
              o.mesh.traverse((c) => {
                if (!c.material) return;
                c.material.transparent = true;
                c.material.opacity = k;
              });
              if (k < 0.02) o.mesh.visible = false; // Umriss (Kantenpass) verschwindet nur mit dem Mesh
            } else if ('opacity' in o) o.opacity *= k;
          }
        }, timing);
      },
    };

    // Kopf: Akt + Titel, darunter eine feine Linie
    const x0 = -SHEET_W / 2;
    const y0 = SHEET_H / 2;
    api.text(0, `${entry.id}  ·  AKT ${entry.act}  ·  ${ACTS[entry.act].toUpperCase()}`, { font: 'mono', size: 0.17, hex: T.inkSoft, anchorY: 'top', letterSpacing: 0.08 }, [x0 + 0.6, y0 - 0.3]);
    api.text(0, entry.title, { font: 'title', size: 0.62, anchorY: 'top' }, [x0 + 0.6, y0 - 0.6], { delay: 0.05 });
    api.line(0, [[x0 + 0.6, y0 - 1.55], [-x0 - 0.6, y0 - 1.55]], { width: 1.2 }, { delay: 0.1, dur: 0.7 });

    const custom = build(api) ?? {};

    // Zeitachse je Schritt so strecken, dass das späteste Element bei S = 1 fertig ist
    const span = {};
    function update() {
      if (!span.done) {
        for (const it of items) span[it.step] = Math.max(span[it.step] ?? 1, it.delay + it.dur);
        span.done = true;
      }
      for (const it of items) reveal(it.obj, clamp01((S[`s${it.step}`] * span[it.step] - it.delay) / it.dur));
      custom.update?.(S);
    }
    return { scene, S, defaults, update };
  };
}

const CAM = { lx: 0, ly: 0, lz: 0, px: 0, py: -0.01, pz: 19.5, fov: 30 };

/** Szeneneintrag für ein Blatt mit `steps` Schritten (Schritt 0 = Aufbau). */
export function sheetScene(entry, steps, build, { cams = null, durations = [] } = {}) {
  return {
    id: entry.id,
    world: `sheet:${entry.id}`,
    createWorld: sheetWorld(entry, steps, build),
    steps: Array.from({ length: steps }, (_, i) => (tl, S) => tl.to(S, { [`s${i}`]: 1, duration: durations[i] ?? 1.6, ease: 'power1.out' }, 0)),
    cams: cams ?? Array(steps).fill(CAM),
  };
}

export { clamp01, EASE };
