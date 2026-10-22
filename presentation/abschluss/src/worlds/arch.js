// Akt 2 (Architektur & Integration) und 6.1 (M4 übernimmt PICK/PLACE_INSPECT): Zustandsautomat mit hervorgehobenem Zustand,
// darunter Orchestrator und Modulblöcke mit Datenkarten und Steckern (mock / Wiedergabe / echt).
// Werte der Datenkarten aus data.json (echte M1-Pose, echtes M3-Ergebnis).
import * as THREE from 'three';
import { T, EASE, MODULE_COLOR, color } from '../theme.js';
import { makeWorldScene } from '../engine/stage.js';
import { InkLine, text, v3 } from '../kit/ink.js';
import { clamp01 } from '../kit/tiles.js';
import { note as makeNote } from '../kit/note.js';
import { arrowPts } from '../kit/geom.js';

const DEFAULTS = {
  states: 0, cycle: 0, // 2.1
  blocks: 0, poseCard: 0, resultCard: 0, // 2.2
  plugs: 0, plug: 0, tests: 0, // 2.3
  m4t: 0, m4: 0, // 6.1
};

const fmt = (v, d = 1) => v.toFixed(d).replace('.', ',');
const AY = -13; // Mitte des Architekturbilds

// Zustände des Orchestrators (plan/01_architektur.md) mit ausführendem Modul
const STATES = [
  ['IDLE', 'ORCH'], ['DETECT', 'M1'], ['PICK', 'M2'], ['PLACE_INSPECT', 'M2'], ['INSPECT', 'M3'], ['PICK_INSPECT', 'M2'], ['SORT', 'M2'],
];

export function createArch(ctx) {
  const scene = makeWorldScene();
  const S = { ...DEFAULTS };
  const note = (...a) => makeNote(scene, ...a);

  /** Kasten mit Tuschekante, Füllung und farbiger Kopfleiste; `appear` 0..1, `fill` 0..1 färbt ein. */
  function box(x, y, w, h, title, sub, hex, { titleSize = 0.32 } = {}) {
    const g = new THREE.Group();
    g.position.set(x, y, 0);
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false }));
    plate.position.z = 0.005;
    const bar = new THREE.Mesh(new THREE.PlaneGeometry(w, 0.12), new THREE.MeshBasicMaterial({ color: color(hex), transparent: true, depthWrite: false }));
    bar.position.set(0, h / 2 - 0.06, 0.007);
    const border = new InkLine([v3(-w / 2, -h / 2, 0.01), v3(w / 2, -h / 2, 0.01), v3(w / 2, h / 2, 0.01), v3(-w / 2, h / 2, 0.01)], { width: 1.8, closed: true, progress: 0 });
    const t = text(title, { font: 'title', size: titleSize, anchorX: 'center', anchorY: 'middle', opacity: 0 });
    t.position.set(0, sub ? 0.12 : -0.04, 0.012);
    const st = sub ? text(sub, { font: 'mono', size: 0.16, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 }) : null;
    if (st) st.position.set(0, -0.12, 0.012);
    g.add(plate, bar, border.object, t, ...(st ? [st] : []));
    scene.add(g);
    const paperCol = color(T.paper);
    const inkCol = color(T.ink);
    const hotCol = color(hex);
    const fillCol = hotCol.clone().lerp(paperCol, 0.72);
    return {
      g, w, h, hex,
      recolor(h2) {
        bar.material.color.set(h2);
        hotCol.set(h2);
        fillCol.copy(hotCol).lerp(paperCol, 0.72);
      },
      /** `hot` 0..1: voll eingefärbt und vergrößert (aktueller Zustand), `dim` 0..1: zurückgenommen, `flip`: Höhe (Umklappen). */
      set(appear, fill = 0, { hot = 0, dim = 0, flip = 1 } = {}) {
        border.progress = appear;
        const o = clamp01(appear * 2 - 0.6);
        const m = 1 - 0.65 * dim;
        plate.material.opacity = o;
        plate.material.color.copy(paperCol).lerp(fillCol, fill).lerp(hotCol, hot);
        bar.material.opacity = o * m;
        border.opacity = m;
        t.opacity = o * m;
        t.color = inkCol.clone().lerp(paperCol, hot).getHex();
        if (st) st.opacity = o * m;
        const s = 1 + 0.18 * hot;
        g.scale.set(s, s * flip, 1);
        g.position.z = hot * 0.05;
        g.visible = appear > 0.001;
      },
    };
  }
  const arrowLines = (a, b, o = {}) => arrowPts(a, b, 0.16).map((pts) => {
    const l = new InkLine(pts, { width: 1.6, progress: 0, ...o });
    scene.add(l.object);
    return l;
  });

  // ---------- 2.1 Zustandsautomat als Ring ----------
  const RX = 6.2;
  const RY = 2.75;
  const statePos = STATES.map((_, i) => {
    const a = Math.PI / 2 + (i / STATES.length) * Math.PI * 2 * -1; // IDLE oben, im Uhrzeigersinn
    return v3(Math.cos(a) * RX, Math.sin(a) * RY + 0.2, 0);
  });
  const stateBoxes = STATES.map(([name, mod], i) => {
    const b = box(statePos[i].x, statePos[i].y, Math.max(1.6, name.length * 0.17 + 0.5), 0.72, name, null, MODULE_COLOR[mod], { titleSize: 0.22 });
    return b;
  });
  const modTags = STATES.map(([, mod], i) => {
    const t = text(mod === 'ORCH' ? 'Orchestrator' : mod, { font: 'mono', size: 0.16, hex: MODULE_COLOR[mod], anchorX: 'center', anchorY: statePos[i].y > 0.2 ? 'bottom' : 'top', opacity: 0 });
    t.position.set(statePos[i].x, statePos[i].y + (statePos[i].y > 0.2 ? 0.45 : -0.45), 0.012);
    scene.add(t);
    return t;
  });
  // Pfeile zwischen den Zuständen (gekürzt auf den Kastenrand)
  const edge = (a, b, ba, bb) => {
    const d = b.clone().sub(a).normalize();
    const cut = (bx, dir) => Math.min(bx.w / 2 / Math.max(Math.abs(dir.x), 1e-3), bx.h / 2 / Math.max(Math.abs(dir.y), 1e-3)) + 0.08;
    return [a.clone().addScaledVector(d, cut(ba, d)).setZ(0.01), b.clone().addScaledVector(d, -cut(bb, d)).setZ(0.01)];
  };
  const stateArrows = STATES.map((_, i) => {
    const j = (i + 1) % STATES.length;
    const [a, b] = edge(statePos[i], statePos[j], stateBoxes[i], stateBoxes[j]);
    return arrowLines(a, b);
  });
  const err = box(0, 0.2, 1.7, 0.72, 'ERROR', null, T.signal, { titleSize: 0.22 });
  const errLines = STATES.slice(1).map((_, k) => {
    const i = k + 1;
    const [a, b] = edge(statePos[i], v3(0, 0.2), stateBoxes[i], err);
    const l = new InkLine([a, b], { width: 1, dashed: true, dash: 0.08, gap: 0.06, hex: T.signal, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const ackLabel = text('Quittieren → Home', { font: 'mono', size: 0.16, hex: T.signal, anchorX: 'left', anchorY: 'middle', opacity: 0 });
  ackLabel.position.set(0.15, 1.35, 0.012);
  scene.add(ackLabel);
  const ackArrow = arrowLines(v3(0, 0.62, 0.01), v3(0, statePos[0].y - 0.45, 0.01), { hex: T.signal });
  const smTitle = text('Orchestrator: ein Zustandsautomat', { font: 'title', size: 0.36, anchorY: 'bottom', opacity: 0 });
  smTitle.position.set(-8.6, 3.9, 0.012);
  scene.add(smTitle);
  const smNote = text('jeder Zyklus eine Zeile im Logbuch · jeder Fehler → STOPP, weiter erst nach Quittieren', { font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', opacity: 0 });
  smNote.position.set(-8.6, 3.75, 0.012);
  scene.add(smNote);
  // ---------- 2.2 Orchestrator und Module ----------
  const orch = box(0, AY + 2.9, 5.2, 1.2, 'Orchestrator', 'orchestrator/  ·  Zustandsautomat', MODULE_COLOR.ORCH);
  const MODS = [
    { key: 'M1', x: -6, title: 'M1 Erkennung', sub: 'ObjectDetector.detect()', tabs: ['mock', 'replay', 'camera'], sel: [0, 1, 2] },
    { key: 'M2', x: 0, title: 'M2 Roboter', sub: 'RobotController.pick/place()', tabs: ['mock', 'sim', 'vm', 'real'], sel: [0, 1, 3] },
    { key: 'M3', x: 6, title: 'M3 Prüfung', sub: 'Inspector.inspect()', tabs: ['mock', 'replay', 'camera'], sel: [0, 1, 2] },
  ];
  const mods = MODS.map((m) => ({ ...m, b: box(m.x, AY, 4.4, 1.3, m.title, m.sub, MODULE_COLOR[m.key]) }));
  const common = box(0, AY - 3.25, 16.4, 0.7, 'common/  ·  interfaces · config · camera · transforms', null, T.inkSoft, { titleSize: 0.22 });
  const links = mods.map((m) => {
    const l = new InkLine([v3(m.x * 0.42, AY + 2.3, 0.004), v3(m.x, AY + 0.65, 0.004)], { width: 1.4, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const archTitle = text('Die Module kennen sich nicht – sie tauschen nur Datenklassen', { font: 'title', size: 0.36, anchorY: 'bottom', opacity: 0 });
  archTitle.position.set(-8.6, AY + 4.6, 0.012);
  scene.add(archTitle);

  const m1 = ctx.data.m1.shots[0];
  const m3 = ctx.data.m3.shots[ctx.data.m3.hero];
  const z = ctx.data.config.workspace_to_robot.table_z_mm;
  const poseCard = note(
    `ObjectPose\nx ${fmt(m1.robot.x)}  y ${fmt(m1.robot.y)}  z ${fmt(z)} mm\ntheta ${fmt(m1.robot.theta)}°  ·  confidence 1,0`,
    -8.9, AY + 4.0, 3.95, 1.12, 0.19, { font: 'mono', hex: MODULE_COLOR.M1 },
  );
  const resultCard = note(
    `InspectionResult\nserial ${m3.serial}  ·  hole ${fmt(m3.hole_mm, 2)} mm\nnotch ${m3.notch_present ? 'True' : 'False'}  ·  is_good ${m3.is_good ? 'True' : 'False'}`,
    4.75, AY + 4.0, 3.95, 1.12, 0.19, { font: 'mono', hex: MODULE_COLOR.M3 },
  );
  const poseFrom = v3(-6, AY + 0.6);
  const resultFrom = v3(6, AY + 0.6);
  const POSE_REST = v3(-6.8, AY + 3.45); // ungefähre Kartenmitte am Zielplatz
  const RESULT_REST = v3(6.7, AY + 3.45);
  const cardArrows = [
    arrowLines(v3(-4.9, AY + 2.85, 0.004), v3(-2.75, AY + 2.85, 0.004), { hex: MODULE_COLOR.M1 }),
    arrowLines(v3(4.9, AY + 2.85, 0.004), v3(2.75, AY + 2.85, 0.004), { hex: MODULE_COLOR.M3 }),
  ];
  const pickLabel = text('pick(pose) · place(GUT/SCHLECHT)', { font: 'mono', size: 0.17, hex: MODULE_COLOR.M2, anchorX: 'left', anchorY: 'middle', opacity: 0 });
  pickLabel.position.set(0.2, AY + 1.5, 0.012);
  scene.add(pickLabel);

  // ---------- 2.3 Stecker: mock / Wiedergabe / echt ----------
  const tabs = mods.map((m) => {
    const n = m.tabs.length;
    const tw = 4.2 / n;
    const items = m.tabs.map((name, i) => {
      const x = m.x - 2.1 + tw * (i + 0.5);
      const l = new InkLine([v3(x - tw / 2 + 0.05, AY - 0.75, 0.01), v3(x - tw / 2 + 0.05, AY - 1.3, 0.01), v3(x + tw / 2 - 0.05, AY - 1.3, 0.01), v3(x + tw / 2 - 0.05, AY - 0.75, 0.01)], { width: 1.2, progress: 0, hex: T.inkSoft });
      const t = text(name, { font: 'mono', size: 0.18, anchorX: 'center', anchorY: 'middle', opacity: 0 });
      t.position.set(x, AY - 1.03, 0.012);
      scene.add(l.object, t);
      return { x, l, t };
    });
    const sel = new THREE.Mesh(new THREE.PlaneGeometry(tw - 0.14, 0.5), new THREE.MeshBasicMaterial({ color: color(MODULE_COLOR[m.key]), transparent: true, depthWrite: false }));
    sel.position.set(0, AY - 1.03, 0.008);
    scene.add(sel);
    return { items, sel, m };
  });
  const plugCaptions = [
    'mock: Zufallswerte – der Ablauf läuft von Tag 1 an, ohne Hardware',
    'Wiedergabe + Simulator: echte Bildverarbeitung auf Testfotos, echter Neura-Client gegen den Simulator',
    'echt: Kameras und LARA – derselbe Ablauf, dieselben Schnittstellen',
  ].map((str) => {
    const t = text(str, { font: 'sans', size: 0.26, anchorX: 'center', anchorY: 'top', opacity: 0 });
    t.position.set(0, AY - 1.65, 0.012);
    scene.add(t);
    return t;
  });
  const testLabel = text('', { font: 'monoMedium', size: 0.34, anchorX: 'right', anchorY: 'bottom', opacity: 0 });
  testLabel.position.set(8.6, AY + 4.6, 0.012);
  scene.add(testLabel);
  let lastTests = -1;

  // ---------- 6.1 M4 übernimmt das Greifen aus dem Rahmen ----------
  // M1 erkennt weiter; M4 greift mit der Handgelenkkamera und legt in die Prüfung; nach M3 übernimmt M2 wieder.
  const M4_STATES = [2, 3]; // PICK, PLACE_INSPECT
  const m4Title = text('M4: KI-Greifen übernimmt einen Teil von M2', { font: 'title', size: 0.36, anchorY: 'bottom', opacity: 0 });
  m4Title.position.set(-8.6, 3.9, 0.012);
  scene.add(m4Title);
  const m4Sub = text('M1 erkennt · M4 greift mit der Handgelenkkamera und legt in die Prüfung ·\nM3 prüft · M2 greift aus der Prüfung und sortiert', {
    font: 'sans', size: 0.2, hex: T.inkSoft, anchorY: 'top', lineHeight: 1.35, opacity: 0,
  });
  m4Sub.position.set(-8.6, 3.75, 0.012);
  scene.add(m4Sub);
  const modTagText = modTags.map(() => '');

  function update() {
    // 2.1 / 6.1: Zustandsring; während eines Umlaufs ist der aktuelle Zustand voll eingefärbt, der Rest zurückgenommen
    const n = STATES.length;
    const cycV = S.cycle;
    const cyc = cycV * n; // 0 … n, danach wieder IDLE
    const env = cycV > 0 && cycV < 1 ? clamp01(Math.min(cyc * 4, (n - cyc) * 4)) : 0;
    const hotOf = (i) => {
      const d = cyc - i;
      return env * clamp01(Math.min((d + 0.12) * 6, (1.12 - d) * 6));
    };
    const modOf = (i) => (M4_STATES.includes(i) && S.m4 * 2 - M4_STATES.indexOf(i) * 0.3 > 0.5 ? 'M4' : STATES[i][1]);
    stateBoxes.forEach((b, i) => {
      const k = M4_STATES.indexOf(i);
      const f = k < 0 ? 0 : clamp01(S.m4 * 2 - k * 0.3); // 0 → 1: klappt um, ab der Hälfte in M4-Farbe
      b.recolor(MODULE_COLOR[modOf(i)]);
      b.set(clamp01(S.states * 2.2 - i * 0.16), 0, { hot: hotOf(i), dim: env * (1 - hotOf(i)), flip: Math.max(0.02, Math.abs(Math.cos(Math.PI * f))) });
    });
    modTags.forEach((t, i) => {
      const mod = modOf(i);
      const str = mod === 'ORCH' ? 'Orchestrator' : mod === 'M4' ? 'M4 · Handgelenkkamera' : mod;
      if (str !== modTagText[i]) {
        t.text = str;
        t.color = color(MODULE_COLOR[mod]).getHex();
        modTagText[i] = str;
      }
      t.opacity = clamp01(S.states * 2 - 1) * (1 - S.blocks * (1 - S.m4t)) * (1 - 0.65 * env * (1 - hotOf(i)));
    });
    stateArrows.forEach((ls, i) => {
      const j = (i + 1) % n;
      const h = hotOf(j);
      ls.forEach((l) => {
        l.progress = clamp01(S.states * 2.2 - 0.3 - i * 0.16);
        l.opacity = 1 - 0.65 * env * (1 - h);
        l.hex = color(T.ink).lerp(color(MODULE_COLOR[modOf(j)]), h);
        l.object.material.linewidth = 1.6 + 1.8 * h;
      });
    });
    err.set(clamp01(S.states * 2 - 1), 0, { dim: env });
    errLines.forEach((l) => {
      l.progress = clamp01(S.states * 2.5 - 1.5);
      l.opacity = 1 - 0.65 * env;
    });
    ackArrow.forEach((l) => {
      l.progress = clamp01(S.states * 3 - 2);
      l.opacity = 1 - 0.65 * env;
    });
    ackLabel.opacity = clamp01(S.states * 4 - 3) * (1 - 0.65 * env);
    smTitle.opacity = clamp01(S.states * 3) * (1 - S.m4t);
    smNote.opacity = clamp01(S.states * 2 - 1) * (1 - S.m4t);
    m4Title.opacity = clamp01(S.m4t * 2 - 1);
    m4Sub.opacity = clamp01(S.m4 * 2 - 1);

    // 2.2
    orch.set(S.blocks);
    mods.forEach((m, i) => m.b.set(clamp01(S.blocks * 1.6 - 0.2 - i * 0.15)));
    common.set(clamp01(S.blocks * 1.6 - 0.6));
    links.forEach((l) => (l.progress = clamp01(S.blocks * 2 - 1)));
    archTitle.opacity = clamp01(S.blocks * 2 - 1);
    // Datenkarten fliegen vom Modul an ihren Platz
    // Karte startet über ihrem Modul und gleitet an ihren Platz neben dem Orchestrator
    const fly = (card, from, rest, v) => {
      card.opacity = clamp01(v * 3);
      const t = 1 - Math.pow(1 - clamp01(v), 3);
      card.group.position.set((from.x - rest.x) * (1 - t), (from.y - rest.y) * (1 - t), 0);
    };
    fly(poseCard, poseFrom, POSE_REST, S.poseCard);
    fly(resultCard, resultFrom, RESULT_REST, S.resultCard);
    cardArrows[0].forEach((l) => (l.progress = clamp01(S.poseCard * 2 - 1)));
    cardArrows[1].forEach((l) => (l.progress = clamp01(S.resultCard * 2 - 1)));
    pickLabel.opacity = clamp01(S.resultCard * 2 - 1);

    // 2.3
    tabs.forEach(({ items, sel, m }) => {
      items.forEach((it, i) => {
        const v = clamp01(S.plugs * 2 - i * 0.2);
        it.l.progress = v;
        it.t.opacity = clamp01(v * 2 - 1);
      });
      // Auswahl gleitet: plug 0 → sel[0], 1 → sel[1], 2 → sel[2]
      const a = Math.min(1, Math.floor(S.plug));
      const fr = S.plug - a;
      const xi = m.sel[a] + (m.sel[Math.min(2, a + 1)] - m.sel[a]) * fr;
      const tw = 4.2 / m.tabs.length;
      sel.position.x = m.x - 2.1 + tw * (xi + 0.5);
      sel.material.opacity = clamp01(S.plugs * 2 - 1) * 0.28;
      sel.visible = sel.material.opacity > 0.001;
      items.forEach((it, i) => (it.t.color = Math.abs(i - xi) < 0.5 ? color(MODULE_COLOR[m.key]).getHex() : color(T.ink).getHex()));
    });
    plugCaptions.forEach((t, i) => (t.opacity = clamp01(1 - Math.abs(S.plug - i) * 2) * clamp01(S.plugs * 2 - 1)));
    const tests = Math.round(ctx.data.tests.total * S.tests);
    if (tests !== lastTests) {
      testLabel.text = `${tests} Tests grün`;
      lastTests = tests;
    }
    testLabel.opacity = clamp01(S.tests * 4);
  }
  return { scene, S, defaults: DEFAULTS, update };
}

// ---------- Kameras ----------
const cam = (lx, ly, pz, fov = 30) => ({ lx, ly, lz: 0, px: lx, py: ly - 0.01, pz, fov });
const C = { sm: cam(0, 0.3, 19.5), arch: cam(0, AY + 0.6, 20) };

const to = (tl, S, vars, pos = 0) => tl.to(S, { ease: EASE.appear, ...vars }, pos);

export const ARCH_SCENES = [
  {
    id: '2.1', world: 'arch',
    steps: [
      (tl, S) => to(tl, S, { states: 1, duration: 2.8, ease: 'power1.inOut' }, 0.2),
      (tl, S) => to(tl, S, { cycle: 1, duration: 7, ease: 'none' }, 0),
    ],
    cams: [C.sm, C.sm],
  },
  {
    id: '2.2', world: 'arch',
    steps: [
      (tl, S) => to(tl, S, { blocks: 1, duration: 2.0, ease: 'power1.inOut' }, 0.6),
      (tl, S) => {
        to(tl, S, { poseCard: 1, duration: 1.4, ease: 'power2.out' }, 0);
        to(tl, S, { resultCard: 1, duration: 1.4, ease: 'power2.out' }, 1.0);
      },
    ],
    cams: [C.arch, C.arch],
  },
  {
    id: '2.3', world: 'arch',
    steps: [
      (tl, S) => {
        to(tl, S, { plugs: 1, duration: 1.4, ease: 'power1.inOut' }, 0);
        to(tl, S, { tests: 1, duration: 2.2, ease: 'power2.out' }, 0.6);
      },
      (tl, S) => to(tl, S, { plug: 1, duration: 1.0, ease: EASE.move }, 0),
      (tl, S) => to(tl, S, { plug: 2, duration: 1.0, ease: EASE.move }, 0),
    ],
    cams: [C.arch, C.arch, C.arch],
  },
  {
    id: '6.1', world: 'arch',
    steps: [
      // Betreten (Aktübergang): nur die Überschrift wechselt; das Umklappen kommt auf den Klick
      (tl, S) => to(tl, S, { m4t: 1, duration: 1.0 }, 0.8),
      (tl, S) => to(tl, S, { m4: 1, duration: 2.6, ease: 'power1.inOut' }, 0.1),
    ],
    cams: [C.sm, C.sm],
  },
];
