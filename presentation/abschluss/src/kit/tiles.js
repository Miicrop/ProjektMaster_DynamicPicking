// Tausende Bild-Kacheln in einem Draw-Call (instanziert). Jede Kachel zeigt ein Thumbnail aus einem
// Atlas (oder einen Ausschnitt eines Fotos), hat einen Rahmen in Teilstückfarbe und Zustände für
// Fehler (Rotstift), Abblenden und Deckkraft. Positionen und Zustände setzt die Welt in update().
import * as THREE from 'three';
import { T, color } from '../theme.js';
import { tex } from './ink.js';

export const TILE_FLAT = 0;      // liegt auf dem Papier (XY)
export const TILE_BILLBOARD = 1; // dreht sich zur Kamera
export const TILE_UPRIGHT = 2;   // steht senkrecht (XZ), schaut nach −y

const VS = /* glsl */ `
attribute vec3 aPos;
attribute float aSize;
attribute float aTile;
attribute vec3 aColor;
attribute vec4 aState;
attribute vec4 aPhotoUv;
uniform float uMode;
uniform float uAspect;
varying vec2 vUv;
varying vec3 vColor;
varying vec4 vState;
varying vec4 vPhotoUv;
varying vec2 vSize;
varying float vTile;
void main() {
  vUv = uv;
  vColor = aColor;
  vState = aState;
  vPhotoUv = aPhotoUv;
  vTile = aTile;
  vec2 size = vec2(aSize, aSize * uAspect);
  vSize = size;
  vec2 c = position.xy * size;
  vec4 mv;
  if (uMode > 0.5 && uMode < 1.5) {
    mv = viewMatrix * vec4(aPos, 1.0);
    mv.xy += c;
  } else if (uMode > 1.5) {
    mv = viewMatrix * vec4(aPos + vec3(c.x, 0.0, c.y), 1.0);
  } else {
    mv = viewMatrix * vec4(aPos + vec3(c, 0.0), 1.0);
  }
  gl_Position = projectionMatrix * mv;
}`;

const FS = /* glsl */ `
uniform sampler2D uAtlas;
uniform sampler2D uPhoto;
uniform float uCols;
uniform float uRows;
uniform float uBorder;
uniform vec3 uPaper;
uniform vec3 uInk;
uniform vec3 uSignal;
uniform float uShadow;
varying vec2 vUv;
varying vec3 vColor;
varying vec4 vState;
varying vec4 vPhotoUv;
varying vec2 vSize;
varying float vTile;
void main() {
  if (vState.z < 0.01) discard;
  if (uShadow > 0.0) {
    vec2 q = abs(vUv - 0.5) * 2.0;
    float a = (1.0 - smoothstep(0.55, 1.0, max(q.x, q.y))) * uShadow * vState.z;
    gl_FragColor = vec4(uInk, a);
    return;
  }
  // +0.5 gegen Rundungsfehler: sonst wird z. B. 25/25 zu 0,99999 und die erste Spalte springt aus dem Atlas
  float row = floor((vTile + 0.5) / uCols);
  float col = floor(vTile + 0.5 - row * uCols);
  vec2 auv = vec2((col + vUv.x) / uCols, 1.0 - (row + 1.0 - vUv.y) / uRows);
  vec3 c = texture2D(uAtlas, auv).rgb;
  if (vState.w > 0.001) {
    vec3 p = texture2D(uPhoto, mix(vPhotoUv.xy, vPhotoUv.zw, vUv)).rgb;
    c = mix(c, p, vState.w);
  }
  // Rahmen: Teilstückfarbe, bei Fehler Rotstift (breiter); auf Fotoausschnitten kein Rahmen
  vec2 d = min(vUv, 1.0 - vUv) * vSize;
  float e = min(d.x, d.y);
  float b = uBorder * (1.0 + vState.x * 1.6) * (1.0 - vState.w);
  vec3 frame = mix(vColor, uSignal, vState.x);
  if (e < b) c = frame;
  c = mix(c, uPaper, vState.y * 0.8);
  gl_FragColor = vec4(c, vState.z);
}`;

export class Tiles {
  constructor({ count, atlas, mode = TILE_FLAT, size = 0.2, aspect = 0.5625, border = 0.012, photo = null, shadow = 0 }) {
    this.count = count;
    const geo = new THREE.InstancedBufferGeometry();
    const base = new THREE.PlaneGeometry(1, 1);
    geo.index = base.index;
    geo.setAttribute('position', base.attributes.position);
    geo.setAttribute('uv', base.attributes.uv);
    const inst = (name, n, fill = 0) => {
      const a = new THREE.InstancedBufferAttribute(new Float32Array(count * n).fill(fill), n);
      a.setUsage(THREE.DynamicDrawUsage);
      geo.setAttribute(name, a);
      return a;
    };
    this.aPos = inst('aPos', 3);
    this.aSize = inst('aSize', 1, size);
    this.aTile = inst('aTile', 1);
    this.aColor = inst('aColor', 3, 0.5);
    this.aState = inst('aState', 4);
    this.aPhotoUv = inst('aPhotoUv', 4);
    for (let i = 0; i < count; i++) this.aTile.array[i] = i;
    geo.instanceCount = count;
    const atlasTex = tex(atlas.file);
    atlasTex.generateMipmaps = true;
    atlasTex.minFilter = THREE.LinearMipmapLinearFilter;
    this.material = new THREE.ShaderMaterial({
      vertexShader: VS,
      fragmentShader: FS,
      uniforms: {
        uAtlas: { value: atlasTex },
        uPhoto: { value: photo ? tex(photo) : atlasTex },
        uCols: { value: atlas.cols },
        uRows: { value: atlas.rows },
        uMode: { value: mode },
        uAspect: { value: aspect },
        uBorder: { value: border },
        uPaper: { value: color(T.paper) },
        uInk: { value: color(T.ink) },
        uSignal: { value: color(T.signal) },
        uShadow: { value: shadow },
      },
      transparent: true,
      depthWrite: !shadow,
      side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(geo, this.material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 1;
  }
  setColor(i, hex) {
    const c = color(hex);
    this.aColor.array.set([c.r, c.g, c.b], i * 3);
  }
  setPos(i, x, y, z) {
    const a = this.aPos.array;
    a[i * 3] = x;
    a[i * 3 + 1] = y;
    a[i * 3 + 2] = z;
  }
  /** Zustand: Fehler (0..1), Abblenden (0..1), Deckkraft (0..1), Fotoanteil (0..1). */
  setState(i, err, dim, opacity, photo = 0) {
    const a = this.aState.array;
    a[i * 4] = err;
    a[i * 4 + 1] = dim;
    a[i * 4 + 2] = opacity;
    a[i * 4 + 3] = photo;
  }
  commit() {
    this.aPos.needsUpdate = true;
    this.aSize.needsUpdate = true;
    this.aState.needsUpdate = true;
    this.aColor.needsUpdate = true;
    this.aPhotoUv.needsUpdate = true;
  }
}

export const clamp01 = (x) => Math.min(1, Math.max(0, x));
export const ease3 = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t) => 1 - Math.pow(1 - t, 3);
/** Gestaffelter Fortschritt: Element mit Verzögerung d∈[0,1] bei globalem p, Fensterbreite w. */
export const stagger = (p, d, w = 0.35) => clamp01((p - d * (1 - w)) / w);
/** deterministische Pseudozufallszahl je Index */
export const rand = (i, k = 0) => {
  const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453;
  return x - Math.floor(x);
};
