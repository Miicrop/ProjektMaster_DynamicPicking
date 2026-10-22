import './style.css';
import '@fontsource/space-grotesk/500.css';
import '@fontsource/space-grotesk/600.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import { preloadFont } from 'troika-three-text';
import { FONTS } from './theme.js';
import { Stage } from './engine/stage.js';
import { Nav } from './engine/nav.js';
import { Hud } from './engine/hud.js';
import { bindStage } from './kit/ink.js';
import { STORYBOARD } from './storyboard.js';
import { placeholderScene } from './worlds/placeholder.js';
import { createVision, VISION_SCENES } from './worlds/vision.js';
import { createInspect, INSPECT_SCENES } from './worlds/inspect.js';
import { createArch, ARCH_SCENES } from './worlds/arch.js';
import { sheetScenes } from './worlds/sheets.js';
import { createCell, CELL_SCENES } from './worlds/cell.js';
import { loadLara } from './kit/lara.js';

// Welten: Name → createWorld(ctx). Gebaute Szenen: { id, world, steps, cams }. Alles andere wird Entwurfsblatt.
const WORLDS = { vision: createVision, inspect: createInspect, arch: createArch, cell: createCell };
const BUILT = new Map([...CELL_SCENES, ...ARCH_SCENES, ...VISION_SCENES, ...INSPECT_SCENES, ...sheetScenes(STORYBOARD)].map((s) => [s.id, s]));
const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜabcdefghijklmnopqrstuvwxyzäöüß0123456789.,:;–-_·/()[]?!„“"\'%×+=<>~›…°Ø ';

async function boot() {
  const data = await fetch('data/data.json').then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  await Promise.all(Object.values(FONTS).map((font) => new Promise((res) => preloadFont({ font, characters: GLYPHS }, res))));

  const stage = new Stage(document.getElementById('gl'));
  bindStage(stage);
  const ctx = { data, stage, lara: await loadLara('urdf/lara5.urdf') };

  const scenes = STORYBOARD.map((e) => {
    const built = BUILT.get(e.id);
    const base = built ? { ...built, createWorld: built.createWorld ?? WORLDS[built.world] } : placeholderScene(e);
    return { ...base, act: e.act, appendix: e.appendix };
  });

  const hud = new Hud(document.getElementById('ui'), STORYBOARD);
  const nav = new Nav({ stage, ctx, scenes, hud });

  // Start: #1.3.2 → Szene 1.3, Schritt 2; ohne Angabe Szene 1.1 vor dem ersten Schritt
  const m = location.hash.match(/^#([0-9A]+\.[0-9]+)(?:\.(\d+))?$/i);
  const start = m ? Math.max(0, scenes.findIndex((s) => s.id.toLowerCase() === m[1].toLowerCase())) : 0;
  const startK = m ? (m[2] !== undefined ? +m[2] : scenes[start].steps.length) : 0;
  nav.applyInstant(start, Math.min(startK, scenes[start].steps.length));

  // Tastatur (Clicker sendet PageUp/PageDown)
  let buffer = '';
  addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    const k = e.key;
    if (/^[0-9.]$/.test(k) || (k.toLowerCase() === 'a' && buffer === '')) {
      buffer += k.toUpperCase();
      hud.jump(buffer);
      return;
    }
    if (buffer) {
      if (k === 'Enter') {
        const [a, b, c] = buffer.split('.');
        if (!nav.jumpToId(`${a}.${b}`, c !== undefined && c !== '' ? +c : null)) hud.toast(`Blatt ${buffer} gibt es nicht`);
      }
      if (k === 'Backspace') {
        buffer = buffer.slice(0, -1);
        hud.jump(buffer);
        e.preventDefault();
        return;
      }
      if (k === 'Enter' || k === 'Escape') {
        buffer = '';
        hud.jump(buffer);
        return;
      }
    }
    switch (k) {
      case 'ArrowRight': case ' ': case 'PageDown': case 'Enter':
        e.preventDefault();
        nav.next();
        break;
      case 'ArrowLeft': case 'PageUp': case 'Backspace':
        e.preventDefault();
        nav.prev();
        break;
      case 'o': case 'O':
        hud.toggleOverview(nav);
        break;
      case 'Escape':
        hud.toggleOverview(nav, false);
        break;
      case 'b': case 'B':
        nav.back();
        break;
      case 'f': case 'F':
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
        break;
      default:
    }
  });

  window.__nav = nav; // für tools/shoot.mjs
  const loop = () => {
    nav.frame();
    stage.render();
    requestAnimationFrame(loop);
  };
  loop();
  document.body.classList.add('ready');
}

boot();
