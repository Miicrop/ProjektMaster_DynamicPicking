// Renderer, Kamera-Rig und Tusche-Pipeline.
// Pro Frame: (1) Szene farbig in rtColor, (2) nur „Volumenkörper“ (Layer SOLID) als Normalen + Tiefe
// in rtNormal, (3) Composite: Kanten aus Normalen/Tiefe als Tuschelinie + Papierkorn → rtFrame,
// (4) Present: rtFrame auf den Bildschirm, ggf. mit Übergang (Schnitt / Blende) und Blitz.
import * as THREE from 'three';
import { T, color } from '../theme.js';

export const LAYER_SOLID = 1;

const FULLSCREEN_VS = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

const COMPOSITE_FS = /* glsl */ `
uniform sampler2D tColor;
uniform sampler2D tNormal;
uniform sampler2D tDepth;
uniform vec2 resolution;
uniform vec3 ink;
uniform float thickness;
uniform float edgeStrength;
uniform float cameraNear;
uniform float cameraFar;
uniform float grain;
varying vec2 vUv;

float linDepth(vec2 uv) {
  float z = texture2D(tDepth, uv).x * 2.0 - 1.0;
  return (2.0 * cameraNear * cameraFar) / (cameraFar + cameraNear - z * (cameraFar - cameraNear));
}
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
  vec4 c = texture2D(tColor, vUv);
  vec2 px = thickness / resolution;
  vec3 n0 = texture2D(tNormal, vUv).xyz;
  float a0 = texture2D(tNormal, vUv).a;
  float d0 = linDepth(vUv);
  float ne = 0.0;
  float de = 0.0;
  float ae = 0.0;
  for (int i = 0; i < 8; i++) {
    float ang = float(i) * 0.785398;
    vec2 o = vec2(cos(ang), sin(ang)) * px;
    vec4 s = texture2D(tNormal, vUv + o);
    ne = max(ne, length(s.xyz - n0));
    float d = linDepth(vUv + o);
    de = max(de, abs(d - d0) / max(min(d, d0), 0.001));
    ae = max(ae, abs(s.a - a0));
  }
  float edge = max(max(smoothstep(0.35, 0.75, ne), smoothstep(0.012, 0.03, de)), ae);
  edge *= edgeStrength;
  c.rgb = mix(c.rgb, ink, clamp(edge, 0.0, 1.0) * 0.92);
  float g = hash(floor(vUv * resolution)) - 0.5;
  c.rgb *= 1.0 + g * grain;
  gl_FragColor = vec4(c.rgb, 1.0);
}`;

const PRESENT_FS = /* glsl */ `
uniform sampler2D tFrame;
uniform sampler2D tSnap;
uniform vec2 resolution;
uniform float mode;      // 0 = nichts, 1 = Schnitt, 2 = Blende
uniform float progress;
uniform float flash;
uniform vec3 ink;
uniform vec3 flashColor;
varying vec2 vUv;

// Schnittlinie: von links unten nach rechts oben (in Bildschirm-Seitenverhältnis)
const vec2 P0 = vec2(-0.05, 0.30);
const vec2 P1 = vec2(1.05, 0.70);

float sideOf(vec2 p, vec2 a, vec2 b) { vec2 d = b - a; return d.x * (p.y - a.y) - d.y * (p.x - a.x); }

float lineDist(vec2 p, vec2 a, vec2 b, float aspect) {
  vec2 d = (b - a) * vec2(aspect, 1.0);
  vec2 q = (p - a) * vec2(aspect, 1.0);
  return abs(d.x * q.y - d.y * q.x) / length(d);
}

vec3 snapCut(vec2 uv, out float covered, out float shade) {
  covered = 0.0;
  shade = 0.0;
  float aspect = resolution.x / resolution.y;
  vec2 dir = normalize((P1 - P0) * vec2(aspect, 1.0));
  vec2 nrm = vec2(-dir.y, dir.x) / vec2(aspect, 1.0);
  float draw = clamp(progress / 0.35, 0.0, 1.0);
  float split = smoothstep(0.35, 1.0, progress);
  split = split * split * (3.0 - 2.0 * split);
  vec2 off = nrm * split * 0.85;
  vec3 col = vec3(0.0);
  // obere Hälfte
  vec2 su = uv - off;
  if (sideOf(su, P0, P1) > 0.0 && su.x > -0.01 && su.x < 1.01 && su.y > -0.01 && su.y < 1.01) {
    col = texture2D(tSnap, su).rgb; covered = 1.0;
  }
  vec2 sl = uv + off;
  if (covered < 0.5 && sideOf(sl, P0, P1) <= 0.0 && sl.x > -0.01 && sl.x < 1.01 && sl.y > -0.01 && sl.y < 1.01) {
    col = texture2D(tSnap, sl).rgb; covered = 1.0;
  }
  // gestrichelte Schnittlinie auf beiden Kanten, wird von links nach rechts gezogen
  vec2 q = covered > 0.5 ? (sideOf(su, P0, P1) > 0.0 ? su : sl) : uv;
  vec2 d = P1 - P0;
  float t = dot(q - P0, d) / dot(d, d);
  vec2 closest = P0 + d * t;
  float dist = length((q - closest) * resolution);
  float dash = step(0.5, fract(t * 38.0));
  float lineMask = (1.0 - smoothstep(1.2, 2.4, dist)) * dash * step(t, draw * 1.0);
  if (covered > 0.5) col = mix(col, ink, lineMask);
  // weicher Schatten der abgehobenen Hälften, nur nahe ihren Kanten
  float dU = lineDist(uv, P0 + off, P1 + off, aspect);
  float dL = lineDist(uv, P0 - off, P1 - off, aspect);
  shade = (1.0 - smoothstep(0.0, 0.05, min(dU, dL))) * 0.2 * smoothstep(0.35, 0.5, progress);
  return col;
}

void main() {
  vec3 frame = texture2D(tFrame, vUv).rgb;
  vec3 col = frame;
  if (mode > 0.5 && mode < 1.5) {
    float covered;
    float shade;
    vec3 s = snapCut(vUv, covered, shade);
    col = covered > 0.5 ? s : frame * (1.0 - shade);
  } else if (mode > 1.5) {
    col = mix(texture2D(tSnap, vUv).rgb, frame, smoothstep(0.0, 1.0, progress));
  }
  col = mix(col, flashColor, flash);
  vec2 v = vUv - 0.5;
  col *= 1.0 - 0.10 * dot(v, v) * 2.0;
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}`;

export class Stage {
  constructor(canvas) {
    this.canvas = canvas;
    const r = (this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' }));
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFShadowMap;
    r.shadowMap.autoUpdate = false;

    this.camera = new THREE.PerspectiveCamera(30, 16 / 9, 0.5, 400);
    this.camera.up.set(0, 1, 0);
    // Kamera-Rig: GSAP tweent pos/look/fov, die Kamera folgt jedes Frame
    this.rig = { px: 0, py: 0, pz: 20, lx: 0, ly: 0, lz: 0, fov: 30 };
    // Freie Kamera per Maus: Abweichung vom Rig (Drehung um den Blickpunkt, Zoom).
    // Wird bei jedem Schritt/Sprung auf 0 zurückgeführt (nav.js), der Ablauf bleibt deterministisch.
    this.orbit = { az: 0, el: 0, zoom: 1 };
    this.bindOrbit(canvas);

    this.lineMaterials = new Set();
    this.scene = null;
    this.flash = { v: 0 };
    this.transition = { mode: 0, progress: 0 };

    const opts = { type: THREE.HalfFloatType };
    this.rtColor = new THREE.WebGLRenderTarget(1, 1, { ...opts, samples: 4 });
    this.rtNormal = new THREE.WebGLRenderTarget(1, 1, { ...opts, depthTexture: new THREE.DepthTexture(1, 1) });
    this.rtFrame = new THREE.WebGLRenderTarget(1, 1, opts);
    this.rtSnap = new THREE.WebGLRenderTarget(1, 1, opts);
    this.normalMaterial = new THREE.MeshNormalMaterial();

    this.quadScene = new THREE.Scene();
    this.quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const geo = new THREE.PlaneGeometry(2, 2);
    this.composite = new THREE.ShaderMaterial({
      vertexShader: FULLSCREEN_VS,
      fragmentShader: COMPOSITE_FS,
      uniforms: {
        tColor: { value: this.rtColor.texture },
        tNormal: { value: this.rtNormal.texture },
        tDepth: { value: this.rtNormal.depthTexture },
        resolution: { value: new THREE.Vector2() },
        ink: { value: color(T.ink) },
        thickness: { value: 1.4 },
        edgeStrength: { value: 1 },
        cameraNear: { value: this.camera.near },
        cameraFar: { value: this.camera.far },
        grain: { value: 0.035 },
      },
      depthTest: false,
      depthWrite: false,
    });
    this.present = new THREE.ShaderMaterial({
      vertexShader: FULLSCREEN_VS,
      fragmentShader: PRESENT_FS,
      uniforms: {
        tFrame: { value: this.rtFrame.texture },
        tSnap: { value: this.rtSnap.texture },
        resolution: { value: new THREE.Vector2() },
        mode: { value: 0 },
        progress: { value: 0 },
        flash: { value: 0 },
        ink: { value: color(T.ink) },
        flashColor: { value: new THREE.Color(1, 1, 1) },
      },
      depthTest: false,
      depthWrite: false,
    });
    this.quad = new THREE.Mesh(geo, this.composite);
    this.quad.frustumCulled = false;
    this.quadScene.add(this.quad);

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    const pr = this.renderer.getPixelRatio();
    const W = Math.floor(w * pr);
    const H = Math.floor(h * pr);
    for (const rt of [this.rtColor, this.rtNormal, this.rtFrame, this.rtSnap]) rt.setSize(W, H);
    this.composite.uniforms.resolution.value.set(W, H);
    this.present.uniforms.resolution.value.set(W, H);
    for (const m of this.lineMaterials) m.resolution.set(W, H);
  }

  registerLineMaterial(m) {
    this.lineMaterials.add(m);
    m.resolution.copy(this.composite.uniforms.resolution.value);
  }

  setScene(scene) {
    this.scene = scene;
  }

  // aktuellen Frame als Ausgangsbild für einen Übergang einfrieren
  snapshot() {
    const t = this.rtSnap;
    this.rtSnap = this.rtFrame;
    this.rtFrame = t;
    this.present.uniforms.tSnap.value = this.rtSnap.texture;
    this.present.uniforms.tFrame.value = this.rtFrame.texture;
  }

  bindOrbit(canvas) {
    let drag = null;
    canvas.addEventListener('pointerdown', (e) => {
      drag = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', (e) => {
      if (!drag) return;
      this.orbit.az -= (e.clientX - drag.x) * 0.006;
      this.orbit.el += (e.clientY - drag.y) * 0.005;
      drag = { x: e.clientX, y: e.clientY };
    });
    const end = () => (drag = null);
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.orbit.zoom = Math.min(3, Math.max(0.25, this.orbit.zoom * Math.exp(e.deltaY * 0.0012)));
    }, { passive: false });
    canvas.addEventListener('dblclick', () => Object.assign(this.orbit, { az: 0, el: 0, zoom: 1 }));
  }

  /** Kameraposition aus Rig + Mausabweichung: um den Blickpunkt drehen (Höhe begrenzt), Abstand skalieren. */
  orbitPosition(out) {
    const { rig, orbit } = this;
    let vx = rig.px - rig.lx, vy = rig.py - rig.ly, vz = rig.pz - rig.lz;
    if (orbit.az === 0 && orbit.el === 0 && orbit.zoom === 1) return out.set(rig.px, rig.py, rig.pz);
    const r = Math.hypot(vx, vy, vz);
    const h = Math.hypot(vx, vy);
    const az = (h > 1e-4 ? Math.atan2(vy, vx) : -Math.PI / 2) + orbit.az;
    const el = Math.min(1.5, Math.max(0.06, Math.atan2(vz, h) + orbit.el));
    const d = r * orbit.zoom;
    return out.set(rig.lx + Math.cos(el) * Math.cos(az) * d, rig.ly + Math.cos(el) * Math.sin(az) * d, rig.lz + Math.sin(el) * d);
  }

  applyRig() {
    const { rig, camera } = this;
    this.orbitPosition(camera.position);
    // Up-Vektor: bei Draufsicht +y (Blatt liegt „richtig herum“), bei schrägen Blicken +z (kein Rollen)
    const dx = rig.lx - camera.position.x, dy = rig.ly - camera.position.y, dz = rig.lz - camera.position.z;
    const vert = Math.abs(dz) / Math.hypot(dx, dy, dz);
    const t = Math.min(1, Math.max(0, (vert - 0.9) / 0.09));
    const k = t * t * (3 - 2 * t);
    camera.up.set(0, k, 1 - k).normalize();
    camera.lookAt(rig.lx, rig.ly, rig.lz);
    if (camera.fov !== rig.fov) {
      camera.fov = rig.fov;
      camera.updateProjectionMatrix();
    }
  }

  render() {
    const { renderer, scene, camera } = this;
    if (!scene) return;
    this.applyRig();
    // Licht folgt dem Blickpunkt, damit Schatten überall scharf genug sind
    if (scene.userData.sun) {
      const sun = scene.userData.sun;
      sun.target.position.set(this.rig.lx, this.rig.ly, 0);
      sun.position.set(this.rig.lx - 4, this.rig.ly + 5, 14);
      sun.target.updateMatrixWorld();
    }
    renderer.shadowMap.needsUpdate = true;
    // Schnittebenen je Welt (z. B. Aufbau von unten nach oben); gilt auch für Normalen- und Schattenpass
    renderer.clippingPlanes = scene.userData.clip ?? [];
    renderer.setRenderTarget(this.rtColor);
    renderer.setClearColor(T.paper, 1);
    renderer.clear();
    renderer.render(scene, camera);

    // Normalen + Tiefe nur der Volumenkörper
    const bg = scene.background;
    scene.background = null;
    scene.overrideMaterial = this.normalMaterial;
    camera.layers.set(LAYER_SOLID);
    renderer.setRenderTarget(this.rtNormal);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    renderer.render(scene, camera);
    camera.layers.set(0);
    camera.layers.enable(LAYER_SOLID);
    scene.overrideMaterial = null;
    scene.background = bg;
    renderer.clippingPlanes = [];

    this.quad.material = this.composite;
    renderer.setRenderTarget(this.rtFrame);
    renderer.render(this.quadScene, this.quadCam);

    const u = this.present.uniforms;
    u.mode.value = this.transition.mode;
    u.progress.value = this.transition.progress;
    u.flash.value = this.flash.v;
    this.quad.material = this.present;
    renderer.setRenderTarget(null);
    renderer.render(this.quadScene, this.quadCam);
  }
}

// gemeinsame Grundausstattung jeder Welt: Papier, Licht, Schattenfänger
export function makeWorldScene() {
  const scene = new THREE.Scene();
  const paper = new THREE.Mesh(
    new THREE.PlaneGeometry(400, 400),
    new THREE.ShaderMaterial({
      uniforms: { paper: { value: color(T.paper) }, grid: { value: color(T.grid) } },
      vertexShader: /* glsl */ `
        varying vec2 vW;
        void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xy; gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: /* glsl */ `
        uniform vec3 paper; uniform vec3 grid; varying vec2 vW;
        float gridLine(vec2 p, float s, float w) {
          vec2 g = abs(fract(p / s - 0.5) - 0.5) / fwidth(p / s);
          return 1.0 - min(min(g.x, g.y) / w, 1.0);
        }
        float noise(vec2 p) {
          vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
          float a = fract(sin(dot(i, vec2(127.1, 311.7))) * 43758.5);
          float b = fract(sin(dot(i + vec2(1.0, 0.0), vec2(127.1, 311.7))) * 43758.5);
          float c = fract(sin(dot(i + vec2(0.0, 1.0), vec2(127.1, 311.7))) * 43758.5);
          float d = fract(sin(dot(i + vec2(1.0, 1.0), vec2(127.1, 311.7))) * 43758.5);
          return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
        }
        void main() {
          float minor = gridLine(vW, 0.25, 1.0) * 0.10;
          float major = gridLine(vW, 1.0, 1.2) * 0.22;
          vec3 c = mix(paper, grid, max(minor, major));
          c *= 0.985 + 0.03 * noise(vW * 0.35);
          gl_FragColor = vec4(c, 1.0);
        }`,
      depthWrite: true,
    }),
  );
  paper.position.z = -0.002;
  paper.renderOrder = -10;
  scene.add(paper);

  const catcher = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.ShadowMaterial({ opacity: 0.16 }));
  catcher.receiveShadow = true;
  catcher.position.z = -0.001;
  scene.add(catcher);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d0bf, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 6;
  sun.shadow.bias = -0.0004;
  Object.assign(sun.shadow.camera, { left: -16, right: 16, top: 16, bottom: -16, near: 1, far: 40 });
  scene.add(sun, sun.target);
  scene.userData.sun = sun;
  return scene;
}
