// Notiz auf einem Papierschild mit feinem Rand. Deckt darunterliegende Fotos ab, damit Text auf
// dunklen oder unruhigen Bildbereichen lesbar bleibt. `opacity` 0..1 steuert Schild und Text.
import * as THREE from 'three';
import { T, color } from '../theme.js';
import { InkLine, text, v3 } from './ink.js';

/** (x, y) = linke obere Ecke des Textes, w = Textbreite, h = Schildhöhe; `center`: Text mittig im Schild. */
export function note(scene, str, x, y, w, h, size, { font = 'sans', hex = T.ink, center = false, border: borderHex = T.inkSoft, borderWidth = 1 } = {}) {
  const g = new THREE.Group();
  const pad = size * 0.9;
  const pw = w + pad * 2;
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(pw, h), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false }));
  plate.position.set(x - pad + pw / 2, y + pad * 0.6 - h / 2, 0.024);
  plate.renderOrder = 2;
  const border = new InkLine([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]].map(([a, b]) => v3(a * pw, b * h, 0.026)), { width: borderWidth, closed: true, hex: borderHex });
  border.object.position.set(plate.position.x, plate.position.y, 0);
  const t = center
    ? text(str, { font, size, hex, anchorX: 'center', anchorY: 'middle', textAlign: 'center', maxWidth: w + pad, lineHeight: 1.35 })
    : text(str, { font, size, hex, anchorY: 'top', maxWidth: w, lineHeight: 1.35 });
  if (center) t.position.set(plate.position.x, plate.position.y, 0.03);
  else t.position.set(x, y, 0.03);
  g.add(plate, border.object, t);
  scene.add(g);
  const api = { text: t, group: g };
  Object.defineProperty(api, 'opacity', {
    get: () => t.opacity,
    set(o) {
      t.opacity = o;
      plate.material.opacity = o;
      border.opacity = o;
      g.visible = o > 0.001;
    },
  });
  api.opacity = 0;
  return api;
}
