// Kleine Geometrie-Helfer für Tuschezeichnungen: Kreis, Bogen, Pfeil, Linie nachträglich verschieben.
import { v3 } from './ink.js';

export function circle(c, r, n = 48, z = 0.02) {
  return Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2;
    return v3(c.x + Math.cos(a) * r, c.y + Math.sin(a) * r, z);
  });
}

export function arc(c, r, a0, a1, z = 0.02, n = 32) {
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = a0 + ((a1 - a0) * i) / n;
    return v3(c.x + Math.cos(a) * r, c.y + Math.sin(a) * r, z);
  });
}

/** Pfeil als zwei Tuschelinien: Schaft und offene Spitze. */
export function arrowPts(a, b, head = 0.14) {
  const d = b.clone().sub(a).normalize();
  const n = v3(-d.y, d.x, 0);
  const l = b.clone().addScaledVector(d, -head).addScaledVector(n, head * 0.45);
  const r = b.clone().addScaledVector(d, -head).addScaledVector(n, -head * 0.45);
  return [[a, b], [l, b, r]];
}

/** Punkte einer InkLine nachträglich setzen (Fortschritt bleibt erhalten). */
export function setPts(line, pts) {
  line.object.geometry.setPositions(pts.flatMap((p) => [p.x, p.y, p.z]));
  line.object.computeLineDistances();
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += pts[i - 1].distanceTo(pts[i]);
  line.length = len;
  const p = line.progress;
  line._progress = -1;
  line.progress = p;
}
