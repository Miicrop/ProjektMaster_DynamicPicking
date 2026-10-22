// Schritt-Navigation mit deterministischem Endzustand.
// Szenen derselben Welt sind Kapitel einer durchgehenden Folge: Zustand (Szene i, Schritt k) =
// Welt zurücksetzen + alle Schritte der früheren Szenen dieser Welt + die ersten k Schritte von i.
import gsap from 'gsap';
import { EASE } from '../theme.js';

export class Nav {
  constructor({ stage, ctx, scenes, hud }) {
    this.stage = stage;
    this.ctx = ctx;
    this.scenes = scenes;
    this.hud = hud;
    this.worlds = new Map();
    this.i = 0;
    this.k = 0;
    this.active = null;
    this.history = [];
    this.world = null;
  }

  // ---------- Welten ----------
  worldOf(sc) {
    if (!this.worlds.has(sc.world)) this.worlds.set(sc.world, sc.createWorld(this.ctx));
    return this.worlds.get(sc.world);
  }

  visible(sc) {
    return !sc.appendix;
  }

  // ---------- Zustand ----------
  runInstant(step, W) {
    const tl = gsap.timeline({ paused: true });
    step(tl, W.S, this.ctx);
    tl.progress(1);
    tl.kill();
  }

  /** Szene i im Zustand k (Anzahl ausgeführter Schritte) sofort herstellen. */
  applyInstant(i, k) {
    this.active?.kill();
    this.active = null;
    const sc = this.scenes[i];
    const W = this.worldOf(sc);
    Object.assign(W.S, W.defaults);
    let cam = this.cam(sc, 0);
    for (let j = 0; j < i; j++) {
      const other = this.scenes[j];
      if (other.world !== sc.world) continue;
      for (const st of other.steps) this.runInstant(st, W);
      cam = this.cam(other, other.cams.length - 1);
    }
    for (let s = 0; s < k; s++) this.runInstant(sc.steps[s], W);
    if (k > 0) cam = this.cam(sc, k - 1);
    this.stage.flash.v = 0;
    Object.assign(this.stage.rig, cam);
    Object.assign(this.stage.orbit, { az: 0, el: 0, zoom: 1 });
    this.enterWorld(W);
    this.i = i;
    this.k = k;
    this.changed();
  }

  /** Kameraziel nach Schritt s; Einträge dürfen Funktionen (ctx) => Kamera sein oder
   *  { seq: [[kamera, startzeit], …] } (Kamerafahrt in Etappen innerhalb eines Schritts). */
  cam(sc, s) {
    const segs = this.camSeq(sc, s);
    return segs[segs.length - 1][0];
  }

  camSeq(sc, s) {
    const c = sc.cams[s];
    const one = (x) => (typeof x === 'function' ? x(this.ctx) : x);
    return c?.seq ? c.seq.map(([x, at]) => [one(x), at]) : [[one(c), 0]];
  }

  enterWorld(W) {
    this.world = W;
    this.stage.setScene(W.scene);
    W.update();
  }

  playStep(i, s, delay = 0) {
    const sc = this.scenes[i];
    const W = this.world;
    const tl = gsap.timeline({ delay, onComplete: () => { if (this.active === tl) this.active = null; } });
    sc.steps[s](tl, W.S, this.ctx);
    const segs = this.camSeq(sc, s);
    const camDur = Math.max(1.6, Math.min(2.8, tl.duration() * 0.85));
    segs.forEach(([c, at], j) => {
      const dur = j + 1 < segs.length ? Math.min(camDur, segs[j + 1][1] - at) : segs.length > 1 ? 2.0 : camDur;
      tl.to(this.stage.rig, { ...c, duration: dur, ease: EASE.cam }, at);
    });
    tl.to(this.stage.orbit, { az: 0, el: 0, zoom: 1, duration: camDur, ease: EASE.cam }, 0);
    this.active = tl;
  }

  // ---------- Bedienung ----------
  next() {
    if (this.active) {
      this.active.progress(1);
      this.active = null;
      this.finishTransition();
      return;
    }
    const sc = this.scenes[this.i];
    if (this.k < sc.steps.length) {
      this.playStep(this.i, this.k);
      this.k++;
      this.changed();
      return;
    }
    const j = this.findVisible(this.i, +1);
    if (j < 0) return;
    this.enter(j);
  }

  enter(j) {
    const prev = this.scenes[this.i];
    const sc = this.scenes[j];
    if (prev.world === sc.world) {
      this.i = j;
      this.k = 0;
      this.playStep(j, 0);
      this.k = 1;
      this.changed();
      return;
    }
    const mode = prev.act !== sc.act ? 1 : 2;
    this.stage.snapshot();
    this.applyInstant(j, 0);
    this.startTransition(mode, mode === 1 ? 1.5 : 0.6);
    this.playStep(j, 0, mode === 1 ? 0.55 : 0.15);
    this.k = 1;
    this.changed();
  }

  prev() {
    if (this.active) {
      this.active.progress(1);
      this.active = null;
    }
    this.finishTransition();
    if (this.k > 1) {
      this.applyInstant(this.i, this.k - 1);
      return;
    }
    const j = this.findVisible(this.i, -1);
    if (j < 0) return;
    this.jumpTo(j, this.scenes[j].steps.length, { remember: false });
  }

  /** Sprung zu Szene j (Endzustand oder Schritt k), mit kurzer Blende. */
  jumpTo(j, k = null, { remember = true, fade = true } = {}) {
    if (remember) this.history.push([this.i, this.k]);
    if (fade) this.stage.snapshot();
    this.applyInstant(j, k ?? this.scenes[j].steps.length);
    if (fade) this.startTransition(2, 0.35);
  }

  jumpToId(id, k = null) {
    const j = this.scenes.findIndex((s) => s.id.toLowerCase() === id.toLowerCase());
    if (j < 0) return false;
    this.jumpTo(j, k);
    return true;
  }

  back() {
    const h = this.history.pop();
    if (h) this.jumpTo(h[0], h[1], { remember: false });
  }

  findVisible(from, dir) {
    for (let j = from + dir; j >= 0 && j < this.scenes.length; j += dir) if (this.visible(this.scenes[j])) return j;
    return -1;
  }

  startTransition(mode, duration) {
    this.transitionTween?.kill();
    const t = this.stage.transition;
    t.mode = mode;
    t.progress = 0;
    this.transitionTween = gsap.to(t, { progress: 1, duration, ease: 'none', onComplete: () => (t.mode = 0) });
  }

  finishTransition() {
    if (this.transitionTween) {
      this.transitionTween.progress(1);
      this.transitionTween = null;
    }
  }

  changed() {
    const sc = this.scenes[this.i];
    const hash = `#${sc.id}.${this.k}`;
    if (location.hash !== hash) history.replaceState(null, '', hash);
    this.hud?.update(this);
  }

  frame() {
    this.world?.update();
  }
}
