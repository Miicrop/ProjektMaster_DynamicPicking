// Platzhalter-Karte für noch nicht gebaute Szenen: zeigt den Storyboard-Eintrag als Entwurfsblatt.
import * as THREE from 'three';
import { T, EASE } from '../theme.js';
import { makeWorldScene } from '../engine/stage.js';
import { InkLine, Balloon, text, v3 } from '../kit/ink.js';
import { ACTS } from '../storyboard.js';

const FW = 16;
const FH = 9;

export function createPlaceholder(entry) {
  return () => {
    const scene = makeWorldScene();
    const S = { frame: 0, body: 0 };
    const x0 = -FW / 2;
    const y0 = FH / 2;
    const frame = new InkLine([v3(x0, -y0), v3(-x0, -y0), v3(-x0, y0), v3(x0, y0)], { closed: true, dashed: true, dash: 0.16, gap: 0.1, width: 1.4, hex: T.inkSoft, progress: 0 });
    scene.add(frame.object);

    const num = new Balloon(entry.id, { r: 0.55, size: 0.36 });
    num.object.position.set(x0 + 1.15, y0 - 1.15, 0.01);
    scene.add(num.object);

    const items = [];
    const add = (obj, delay) => {
      scene.add(obj);
      items.push({ obj, delay });
      return obj;
    };
    const act = add(text(`AKT ${entry.act}  ·  ${ACTS[entry.act].toUpperCase()}`, { font: 'mono', size: 0.2, hex: T.inkSoft, anchorY: 'top', letterSpacing: 0.08, opacity: 0 }), 0);
    act.position.set(x0 + 2.0, y0 - 0.75, 0.01);
    const title = add(text(entry.title, { font: 'title', size: 0.78, anchorY: 'top', maxWidth: FW - 3.5, opacity: 0 }), 0.05);
    title.position.set(x0 + 2.0, y0 - 1.05, 0.01);
    const statement = add(text(entry.statement, { font: 'sans', size: 0.42, anchorY: 'top', maxWidth: FW - 3.5, lineHeight: 1.3, opacity: 0 }), 0.15);
    statement.position.set(x0 + 2.0, y0 - 2.6, 0.01);

    const k1 = add(text('BILDIDEE', { font: 'mono', size: 0.16, hex: T.inkSoft, anchorY: 'top', letterSpacing: 0.08, opacity: 0 }), 0.3);
    k1.position.set(x0 + 2.0, -0.6, 0.01);
    const visual = add(text(entry.visual, { font: 'sans', size: 0.3, hex: T.ink, anchorY: 'top', maxWidth: FW - 6.5, lineHeight: 1.3, opacity: 0 }), 0.35);
    visual.position.set(x0 + 2.0, -0.95, 0.01);
    if (entry.data) {
      const k2 = add(text('DATEN', { font: 'mono', size: 0.16, hex: T.inkSoft, anchorY: 'top', letterSpacing: 0.08, opacity: 0 }), 0.4);
      k2.position.set(x0 + 2.0, -2.75, 0.01);
      const d = add(text(entry.data, { font: 'mono', size: 0.22, anchorY: 'top', maxWidth: FW - 6.5, opacity: 0 }), 0.45);
      d.position.set(x0 + 2.0, -3.05, 0.01);
    }
    // Sprecher oben rechts
    if (entry.speaker) {
      const sp = add(text(`SPRICHT: ${entry.speaker.toUpperCase()}`, { font: 'mono', size: 0.18, hex: T.inkSoft, anchorX: 'right', anchorY: 'top', letterSpacing: 0.08, opacity: 0 }), 0.2);
      sp.position.set(-x0 - 0.5, y0 - 0.75, 0.01);
    }
    // Entwurfsstempel (Rotstift)
    const stamp = new THREE.Group();
    const sw = 2.9;
    const sh = 0.9;
    const box = new InkLine([v3(-sw / 2, -sh / 2), v3(sw / 2, -sh / 2), v3(sw / 2, sh / 2), v3(-sw / 2, sh / 2)], { closed: true, hex: T.signal, width: 2.4, progress: 0 });
    const st = text('ENTWURF', { font: 'title', size: 0.5, hex: T.signal, anchorX: 'center', anchorY: 'middle', letterSpacing: 0.12, opacity: 0 });
    stamp.add(box.object, st);
    stamp.position.set(-x0 - 2.4, -y0 + 1.3, 0.02);
    stamp.rotation.z = 0.12;
    scene.add(stamp);

    function update() {
      frame.progress = S.frame;
      num.appear = S.frame;
      for (const it of items) it.obj.opacity = Math.min(1, Math.max(0, (S.body - it.delay) / 0.5));
      box.progress = Math.max(0, S.body * 2 - 1);
      st.opacity = Math.max(0, S.body * 2 - 1);
    }
    return { scene, S, defaults: { frame: 0, body: 0 }, update };
  };
}

const CAM = { lx: 0, ly: 0, lz: 0, px: 0, py: -0.01, pz: 19.5, fov: 30 };

export function placeholderScene(entry) {
  return {
    id: entry.id,
    world: `ph:${entry.id}`,
    placeholder: true,
    createWorld: createPlaceholder(entry),
    steps: [
      (tl, S) => {
        tl.to(S, { frame: 1, duration: 1.2, ease: 'power1.inOut' }, 0);
        tl.to(S, { body: 1, duration: 1.4, ease: EASE.appear }, 0.3);
      },
    ],
    cams: [CAM],
  };
}
