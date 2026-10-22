// Die Roboterzelle: Aufstellungsplan (1.1) → 3D-Zelle (1.2) → Bauteil (1.3) → ein Zyklus (1.4) →
// LARA im Detail (Akt 4: Gelenke, Bauteil → Greifpose, Greifsequenz, 23°, Grenzen) → Simulator (4.6) → Ausblick (7.4) → Finale (7.5). Alle Lagen aus system.yaml (über data.json), LARA aus der URDF.
// Roboter-Basis-KS = Papier-KS: x rechts, y oben, z aus dem Papier; 1 m = 10 Papiereinheiten.
// Bewegungen wie am echten Roboter: PTP in Gelenkkoordinaten, Anfahren/Abheben linear (IK je Bild,
// immer vom Startwert des Abschnitts aus → Sprünge und Rückwärtsschritte bleiben exakt).
import * as THREE from 'three';
import { T, EASE, MODULE_COLOR, color } from '../theme.js';
import { makeWorldScene, LAYER_SOLID } from '../engine/stage.js';
import { InkLine, Balloon, text, solid, v3 } from '../kit/ink.js';
import { clamp01 } from '../kit/tiles.js';
import { arrowPts, arc, circle, setPts } from '../kit/geom.js';
import { Lara, poseMatrix, rpyMatrix } from '../kit/lara.js';

const U = 10; // Papiereinheiten je Meter
const W = (x, y, z = 0) => v3((x / 1000) * U, (y / 1000) * U, (z / 1000) * U); // mm → Papier
const TITLE = 'Dynamisches Greifen und automatisierte Sichtprüfung mit einem kollaborativen Roboter';
const NAMES = ['Felix Krawczyk', 'Joshua Junt', 'Niklas Tollmann', 'Jeremy Zid'];
const DEG = Math.PI / 180;
const wrap = (a) => ((((a + 180) % 360) + 360) % 360) - 180;

const DEFAULTS = {
  plan: 0, title: 0, // 1.1
  extrude: 0, balloons: 0, // 1.2
  partShow: 0, spin: 0, partNotes: 0, // 1.3
  cycle1: 0, // 1.4
  joints: 0, // 4.1
  gp: 0, ik: 0, gpOff: 0, // 4.2
  partB: 0, demo: 0, ruler: 0, // 4.2 / 4.3
  angle: 0, // 4.4
  limits: 0, outside: 0, // 4.5
  ghost: 0, sim: 0, // 4.6
  game: 0, game1: 0, game2: 0, unboard: 0, // 7.4 (unboard: Rückbau zu Beginn von 7.5)
  cycle2: 0, outro: 0, finale: 0, // 7.5
};

// 7.5 Finale: Schild „Noch Fragen?“ steht im Halter rechts der Platte (aus Zuschauersicht), Schrift zur Seite. LARA
// holt es, hebt es heraus und dreht es in einer Bewegung zur Zuschauerkamera (Kollisionsprüfung unten). Lagen in mm im Roboter-Basis-KS (Bühnenbild, nicht aus system.yaml); Handgelenk erreicht max. 0,80 m ab Schulter (z 0,22 m).
const SIGN = { stand: [660, -160], show: [380, -470, 330], audience: [420, -1700, 1250] };

export function createCell(ctx) {
  const { data } = ctx;
  const cfg = data.config;
  const rc = cfg.robot;
  const scene = makeWorldScene();
  const S = { ...DEFAULTS };
  const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 100);

  // Metergruppe für alle Körper (Roboter, Tisch, Stationen, Bauteile)
  const cell = new THREE.Group();
  cell.scale.setScalar(U);
  scene.add(cell);
  const box = (sx, sy, sz, hex, x, y, z0 = 0) => {
    const m = solid(new THREE.BoxGeometry(sx / 1000, sy / 1000, sz / 1000), hex);
    m.position.set(x / 1000, y / 1000, (z0 + sz / 2) / 1000);
    m.receiveShadow = true;
    cell.add(m);
    return m;
  };

  // ---------- Lagen aus der Konfiguration ----------
  const w2r = cfg.workspace_to_robot;
  const rot = w2r.rotation_deg * DEG;
  const [tx, ty] = w2r.translation_mm;
  const ws2r = (x, y) => [Math.cos(rot) * x - Math.sin(rot) * y + tx, Math.sin(rot) * x + Math.cos(rot) * y + ty];
  const [WSW, WSH] = cfg.workspace.size_mm;
  const TZ = w2r.table_z_mm;
  const P = rc.poses;

  // ---------- Roboter ----------
  const lara = new Lara(ctx.lara, { tool: (rc.tool_tcp_mm?.[2] ?? 197.5) / 1000 });
  cell.add(lara.object);
  const homeM = poseMatrix(P.home);
  const qHome = lara.ik(homeM, [0, 0, 90 * DEG, 0, 90 * DEG, 90 * DEG], { iterations: 120 });
  const tcp = (pose) => poseMatrix(pose);
  const up = (pose, dz) => [pose[0], pose[1], pose[2] + dz, pose[3], pose[4], pose[5]];
  // Greifpose wie m2_robot_control.robot.as_target: rz = home.rz + Winkel + Greifer-Offset
  const graspPose = (shot) => [shot.robot.x, shot.robot.y, TZ + (rc.grasp_height_mm ?? 5), P.home[3], P.home[4], wrap(P.home[5] + shot.robot.theta + rc.gripper_angle_offset_deg)];
  const shotA = data.m1.shots[0];
  const shotB = data.m1.shots[4];
  const AH = rc.approach_height_mm;
  const SLOW = rc.approach_slow_mm;

  // Greifer am Flansch: Adapter LWR50F (28 mm) + LWR50L (Backen bis zum TCP). Backenrichtung so, dass sie
  // beim Greifen quer zur langen Bauteilseite schließen (folgt aus dem Offset in system.yaml).
  const gripper = new THREE.Group();
  lara.flange.add(gripper);
  const gA = poseMatrix(graspPose(shotA));
  const shortDir = new THREE.Vector3(-Math.sin(shotA.robot.theta * DEG), Math.cos(shotA.robot.theta * DEG), 0);
  const jawAxis = shortDir.clone().applyMatrix4(new THREE.Matrix4().extractRotation(gA).transpose());
  const gRot = Math.atan2(jawAxis.y, jawAxis.x);
  const gBody = new THREE.Group();
  gBody.rotation.z = gRot;
  gripper.add(gBody);
  const adapter = solid(new THREE.CylinderGeometry(0.032, 0.032, 0.028, 32), '#B9BDC1');
  adapter.rotation.x = Math.PI / 2;
  adapter.position.z = 0.014;
  const gHousing = solid(new THREE.BoxGeometry(0.09, 0.06, 0.1), '#C9CCCF');
  gHousing.position.z = 0.078;
  const jaws = [-1, 1].map((s) => {
    const j = solid(new THREE.BoxGeometry(0.012, 0.03, 0.07), '#6B6F73');
    j.userData.s = s;
    gBody.add(j);
    return j;
  });
  const wristCam = solid(new THREE.BoxGeometry(0.03, 0.035, 0.04), MODULE_COLOR.M4);
  wristCam.position.set(0, 0.05, 0.07);
  gBody.add(adapter, gHousing, wristCam);
  const setGrip = (g) => {
    // offen 52 mm, geschlossen = Bauteilbreite 40 mm
    const half = (0.052 - 0.012 * g) / 2 + 0.006;
    jaws.forEach((j) => j.position.set(j.userData.s * half, 0, lara.tool - 0.035));
  };
  setGrip(0);

  // ---------- Tisch, Platte, Marker, Stationen, Kameras ----------
  const keep = (m) => m;
  const [bx0, by0] = ws2r(-70, -70);
  const [bx1, by1] = ws2r(WSW + 70, WSH + 70);
  const board = keep(box(bx1 - bx0, by1 - by0, 10, T.board, (bx0 + bx1) / 2, (by0 + by1) / 2, TZ - 10));
  board.rotation.z = rot;
  const markers = Object.entries(cfg.workspace.markers_mm).map(([id, [x, y]]) => {
    const [mx, my] = ws2r(x, y);
    const m = keep(box(66, 66, 1, '#F7F5F0', mx, my, TZ));
    m.rotation.z = rot;
    const inner = keep(box(50, 50, 1.2, '#1E2328', mx, my, TZ));
    inner.rotation.z = rot;
    return { id, x: mx, y: my };
  });
  const insp = P.inspection;
  const fixture = keep(box(70, 90, insp[2] - TZ - 4, '#3A3F45', insp[0], insp[1], TZ));
  const bins = [['bin_good', 'GUT', T.good], ['bin_bad', 'SCHLECHT', T.signal]].map(([k, label, hex]) => {
    const p = P[k];
    const floor = keep(box(110, 100, 3, '#E2DDD2', p[0], p[1], TZ));
    const walls = [[110, 4, 0, 48], [110, 4, 0, -48], [4, 100, 53, 0], [4, 100, -53, 0]].map(([sx, sy, dx, dy]) => keep(box(sx, sy, 22, hex, p[0] + dx, p[1] + dy, TZ)));
    return { k, label, hex, p, floor, walls };
  });
  // Kamera M1 an der Stange (Lage angenommen), schaut auf die Arbeitsraummitte
  const [wcx, wcy] = ws2r(WSW / 2, WSH / 2);
  const pole = { x: wcx + 330, y: wcy - 230 };
  keep(box(30, 30, 950, '#9AA0A6', pole.x, pole.y, -10));
  const camTop = new THREE.Vector3((pole.x - 90) / 1000, (pole.y + 60) / 1000, 0.92);
  const armLen = Math.hypot(90, 60) / 1000;
  const arm = keep(solid(new THREE.BoxGeometry(armLen + 0.02, 0.02, 0.02), '#9AA0A6'));
  arm.position.set((pole.x - 45) / 1000, (pole.y + 30) / 1000, 0.93);
  arm.rotation.z = Math.atan2(60, -90);
  cell.add(arm);
  const camM1 = keep(solid(new THREE.BoxGeometry(0.05, 0.05, 0.09), MODULE_COLOR.M1));
  camM1.position.copy(camTop);
  cell.add(camM1);
  // Kamerakörper-z zeigt zur Arbeitsraummitte
  camM1.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(wcx / 1000, wcy / 1000, 0).sub(camTop).normalize());

  // ---------- Bauteile ----------
  const partShape = new THREE.Shape();
  const PL = data.part.length_mm / 1000;
  const PWd = data.part.width_mm / 1000;
  const PHt = data.part.height_mm / 1000;
  const CH = 0.012; // Fase (Draufsicht), Maß angenommen
  partShape.moveTo(-PL / 2, -PWd / 2);
  partShape.lineTo(PL / 2, -PWd / 2);
  partShape.lineTo(PL / 2, PWd / 2 - CH);
  partShape.lineTo(PL / 2 - CH, PWd / 2);
  partShape.lineTo(-PL / 2, PWd / 2);
  partShape.closePath();
  const partGeo = new THREE.ExtrudeGeometry(partShape, { depth: PHt, bevelEnabled: false });
  partGeo.translate(0, 0, -PHt / 2);
  function makePart() {
    const g = new THREE.Group();
    g.matrixAutoUpdate = false;
    g.add(solid(partGeo, T.part, { roughness: 0.6 }));
    // Seitenfläche (-y): Etikett, Loch, Kerbe
    const face = (w, h, hex, x) => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: color(hex) }));
      m.rotation.x = Math.PI / 2;
      m.position.set(x, -PWd / 2 - 0.0004, 0);
      g.add(m);
      return m;
    };
    face(0.026, 0.011, '#F7F5F0', -0.014);
    const hole = new THREE.Mesh(new THREE.CircleGeometry(0.005, 32), new THREE.MeshBasicMaterial({ color: color('#1E2328') }));
    hole.rotation.x = Math.PI / 2;
    hole.position.set(0.012, -PWd / 2 - 0.0005, 0);
    g.add(hole);
    face(0.005, 0.005, '#4B2F66', 0.025);
    const serial = text(data.part.serial, { font: 'monoMedium', size: 0.0075, hex: T.ink, anchorX: 'center', anchorY: 'middle' });
    serial.rotation.x = Math.PI / 2;
    serial.position.set(-0.014, -PWd / 2 - 0.0008, 0);
    g.add(serial);
    cell.add(g);
    return g;
  }
  const partA = makePart();
  // Schild „Noch Fragen?“ mit Griffblock und Halter (7.5)
  const sign = new THREE.Group();
  sign.matrixAutoUpdate = false;
  {
    const plate = solid(new THREE.BoxGeometry(0.28, 0.005, 0.12), '#F7F5F0');
    const knob = solid(new THREE.BoxGeometry(0.03, 0.04, 0.025), '#6B6F73');
    knob.position.z = 0.06 + 0.0125;
    // Schriftseite unbeleuchtet, damit sie auch im Gegenlicht papierhell bleibt
    const face = new THREE.Mesh(new THREE.PlaneGeometry(0.274, 0.114), new THREE.MeshBasicMaterial({ color: color('#F7F5F0') }));
    face.rotation.x = Math.PI / 2;
    face.position.y = -0.0027;
    const t = text('Noch Fragen?', { font: 'title', size: 0.036, hex: T.ink, anchorX: 'center', anchorY: 'middle' });
    t.rotation.x = Math.PI / 2;
    t.position.set(0, -0.0032, -0.004);
    sign.add(plate, knob, face, t);
  }
  cell.add(sign);
  const signStand = solid(new THREE.BoxGeometry(0.06, 0.32, 0.02), '#3A3F45');
  cell.add(signStand);
  const partB = makePart();
  // Lage auf dem Tisch: Mitte unter der Greifpose, Bauteil-x entlang der erkannten Achse
  const tablePose = (shot) => rpyMatrix(0, 0, shot.robot.theta * DEG).setPosition(shot.robot.x / 1000, shot.robot.y / 1000, (TZ + data.part.height_mm / 2) / 1000);

  // ---------- Bewegungsplan ----------
  const solveAt = (pose, seed) => lara.ik(tcp(pose), seed);
  /** Abschnitte: { kind: 'ptp' | 'lin' | 'wait', a, b (Posen), dur, state, grip } → Zeitfunktion */
  function plan(steps, q0) {
    let t = 0;
    let q = q0;
    let grip = steps.startGrip ?? 0;
    const segs = steps.map((s) => {
      const seg = { ...s, t0: t, q0: q, g0: grip };
      if (s.kind === 'ptp' || s.kind === 'lin') seg.q1 = solveAt(s.b, s.seed ?? q);
      else seg.q1 = q;
      seg.g1 = s.grip ?? grip;
      t += s.dur;
      q = seg.q1;
      grip = seg.g1;
      return seg;
    });
    const at = (tt) => {
      const seg = segs.find((s) => tt < s.t0 + s.dur) ?? segs[segs.length - 1];
      const f = clamp01((tt - seg.t0) / seg.dur);
      const e = f * f * (3 - 2 * f);
      let qq;
      if (seg.kind === 'lin') {
        // linear im Raum: z zwischen den Posen, IK vom Startwert des Abschnitts
        const a = seg.a;
        const b = seg.b;
        const pose = a.map((v, i) => v + (b[i] - v) * e);
        qq = f <= 0 ? seg.q0 : f >= 1 ? seg.q1 : solveAt(pose, seg.q0);
      } else qq = seg.q0.map((v, i) => v + (seg.q1[i] - v) * e);
      const g = seg.g0 + (seg.g1 - seg.g0) * clamp01(f * 2);
      return { q: qq, grip: g, state: seg.state, seg };
    };
    return { segs, at, total: t, q1: q };
  }
  const gPA = graspPose(shotA);
  const gPB = graspPose(shotB);
  const bin = (k) => P[k];
  // Linear ab/auf: schnell bis approach_slow_mm über dem Ziel, Rest langsam (Zeiten nach den echten Geschwindigkeiten, gerafft)
  const down = (pose, state, grip) => [
    { kind: 'lin', a: up(pose, AH), b: up(pose, SLOW), dur: 0.75, state },
    { kind: 'lin', a: up(pose, SLOW), b: pose, dur: 0.8, state },
    { kind: 'wait', dur: 0.45, state, grip },
  ];
  const lift = (pose, state) => [
    { kind: 'lin', a: pose, b: up(pose, SLOW), dur: 0.6, state },
    { kind: 'lin', a: up(pose, SLOW), b: up(pose, AH), dur: 0.6, state },
  ];
  function cycleSteps(g, binKey, startAtPart = false) {
    return [
      ...(startAtPart ? [] : [
        { kind: 'wait', dur: 1.2, state: 'DETECT' },
        { kind: 'ptp', b: up(g, AH), dur: 1.6, state: 'PICK' },
        ...down(g, 'PICK', 1),
        ...lift(g, 'PICK'),
      ]),
      { kind: 'ptp', b: up(insp, AH), dur: 1.6, state: 'PLACE_INSPECT' },
      ...down(insp, 'PLACE_INSPECT', 0),
      ...lift(insp, 'PLACE_INSPECT'),
      { kind: 'wait', dur: 1.3, state: 'INSPECT' },
      ...down(insp, 'PICK_INSPECT', 1),
      ...lift(insp, 'PICK_INSPECT'),
      { kind: 'ptp', b: up(bin(binKey), AH), dur: 1.3, state: 'SORT' },
      ...down(bin(binKey), 'SORT', 0),
      ...lift(bin(binKey), 'SORT'),
      { kind: 'ptp', b: P.home, dur: 1.5, state: 'IDLE' },
    ];
  }
  const cyc1 = plan(cycleSteps(gPA, 'bin_good'), qHome);
  // 4.2: PTP von Home zur Vorpose über Teil B; die Greifsequenz (4.3) beginnt dort
  const toPre = plan([{ kind: 'ptp', b: up(gPB, AH), dur: 2.4, state: 'PICK' }], qHome);
  CELL.TP = toPre.total;
  const demoSteps = [
    ...down(gPB, 'PICK', 1),
    ...lift(gPB, 'PICK'),
  ];
  const demo = plan(demoSteps, toPre.q1);
  const steps2 = cycleSteps(gPB, 'bin_bad', true);
  steps2.startGrip = 1;
  const cyc2 = plan(steps2, demo.q1);

  // Ereigniszeiten: Greifer zu/auf (Ende des Warte-Abschnitts), Blitze
  const events = (pl) => pl.segs.filter((s) => s.kind === 'wait' && s.grip !== undefined).map((s) => ({ t: s.t0 + s.dur * 0.5, grip: s.grip }));
  const ev1 = events(cyc1);
  const evDemo = events(demo);
  const ev2 = events(cyc2);
  const flashes = (pl) => pl.segs.filter((s) => s.kind === 'wait' && (s.state === 'DETECT' || s.state === 'INSPECT')).map((s) => s.t0 + 0.25);
  CELL.flash1 = flashes(cyc1).map((t) => t / cyc1.total);
  CELL.flash2 = flashes(cyc2).map((t) => t / cyc2.total);
  CELL.T1 = cyc1.total;
  CELL.T2 = cyc2.total;
  CELL.TD = demo.total;
  // 4.5: dieselben Aufrufe an Roboter und Simulator; endet wieder über Teil B (Start von cyc2)
  const simSteps = [
    { kind: 'wait', dur: 0.7, call: 0 },
    { kind: 'ptp', b: up(insp, AH), dur: 2.4, call: 1 },
    { kind: 'wait', dur: 0.7 },
    { kind: 'ptp', b: up(gPB, AH), seed: demo.q1, dur: 2.4, call: 3 },
    { kind: 'wait', dur: 0.5 },
  ];
  const sim = plan(simSteps, demo.q1);
  CELL.TS = sim.total;

  // ---------- 7.5 Schild ----------
  const SG = { w: 0.28, h: 0.12, t: 0.005, grip: 0.025 };
  const jawL = new THREE.Vector3(Math.cos(gRot), Math.sin(gRot), 0); // Backenachse im TCP-KS
  // Schild-KS: x Breite, z oben, Schrift zeigt nach -y. Gegriffen am Block oben, quer durch die Backen;
  // das Schild hängt entlang +z des TCP, Oberkante 5 mm unter dem TCP.
  const signRel = new THREE.Matrix4()
    .makeBasis(new THREE.Vector3().crossVectors(jawL, v3(0, 0, -1)), jawL, v3(0, 0, -1))
    .setPosition(0, 0, 0.005 + SG.h / 2);
  const signRelInv = signRel.clone().invert();
  /** Schildlage: Mitte c [mm], Schrift zeigt in Richtung `face`. */
  const signM = ([x, y, z], face) => {
    const Y = face.clone().normalize().negate();
    const Z = v3(0, 0, 1).addScaledVector(Y, -Y.z).normalize();
    return new THREE.Matrix4().makeBasis(new THREE.Vector3().crossVectors(Y, Z), Y, Z).setPosition(x / 1000, y / 1000, z / 1000);
  };
  const poseOf = (m) => {
    const p = new THREE.Vector3().setFromMatrixPosition(m).multiplyScalar(1000);
    const e = new THREE.Euler().setFromRotationMatrix(m, 'ZYX');
    return [p.x, p.y, p.z, e.x / DEG, e.y / DEG, e.z / DEG];
  };
  const standC = [...SIGN.stand, TZ + 10 + SG.h * 500];
  // Schrift im Halter zeigt nach +x (für das Publikum seitlich), vor der Kamera zum Publikum
  const toShow = new THREE.Vector3(...SIGN.audience).sub(new THREE.Vector3(...SIGN.show));
  const signRest = signM(standC, v3(1, 0, 0));
  const showM = signM(SIGN.show, toShow);
  const gS = poseOf(signRest.clone().multiply(signRelInv));
  const finSteps = [
    { kind: 'ptp', b: up(gS, AH), dur: 1.8 },
    ...down(gS, null, 1),
    { kind: 'lin', a: gS, b: up(gS, 100), dur: 0.9 },
    { kind: 'ptp', b: poseOf(showM.clone().multiply(signRelInv)), dur: 2.2 },
    { kind: 'wait', dur: 0.5 },
  ];
  const fin = plan(finSteps, cyc2.q1);
  const evFin = events(fin);
  CELL.FIN = fin.total;
  // Kontrolle: jede Zielpose muss erreicht werden (sonst Warnung in der Konsole, tools/shoot.mjs meldet sie)
  for (const [name, pl] of [['cyc1', cyc1], ['demo', demo], ['cyc2', cyc2], ['fin', fin]]) {
    pl.segs.forEach((sg, i) => {
      if (!sg.b) return;
      const d = new THREE.Vector3().setFromMatrixPosition(lara.fk(sg.q1)).distanceTo(new THREE.Vector3().setFromMatrixPosition(tcp(sg.b)));
      if (d > 0.001) console.warn(`IK ${name}[${i}]: ${(d * 1000).toFixed(1)} mm Restfehler`);
    });
  }
  // Kontrolle Finale: Schildfläche gegen Armsegmente (Kapseln r = 70 mm) und Tisch, entlang der ganzen Bahn
  {
    const LINK_R = 0.07;
    const liftEnd = fin.segs[fin.segs.length - 3].t0 + fin.segs[fin.segs.length - 3].dur;
    const grid = [];
    for (const u of [-0.5, -0.25, 0, 0.25, 0.5]) for (const w of [-0.5, 0, 0.5]) grid.push(v3(u * SG.w, 0, w * SG.h));
    const seg = new THREE.Line3();
    const cp = new THREE.Vector3();
    const tcpM = new THREE.Matrix4();
    let worst = { d: Infinity };
    for (let t = evFin[0].t; t <= fin.total; t += 0.05) {
      const { q } = fin.at(t);
      const sm = lara.fk(q, tcpM).multiply(signRel);
      const pts = grid.map((g) => g.clone().applyMatrix4(sm));
      const jp = lara.jointPoints(q);
      for (let k = 1; k < jp.length; k++) {
        seg.set(jp[k - 1], jp[k]);
        for (const p of pts) {
          const d = seg.closestPointToPoint(p, true, cp).distanceTo(p) - LINK_R;
          if (d < worst.d) worst = { d, t, k };
        }
      }
      if (t > liftEnd) {
        const zMin = Math.min(...pts.map((p) => p.z)) - TZ / 1000;
        if (zMin < 0.01) console.warn(`Finale: Schild ${(zMin * 1000).toFixed(0)} mm über dem Tisch bei t = ${t.toFixed(2)} s`);
      }
    }
    if (worst.d < 0.02) console.warn(`Finale: Schild ${(worst.d * 1000).toFixed(0)} mm am Armsegment ${worst.k} bei t = ${worst.t.toFixed(2)} s`);
  }

  // Bauteil relativ zum TCP beim Greifen (bleibt während des Tragens fest)
  const relOf = (g, shot) => new THREE.Matrix4().copy(tcp(g)).invert().multiply(tablePose(shot));
  const relA = relOf(gPA, shotA);
  const relB = relOf(gPB, shotB);
  const placed = (pose, rel) => new THREE.Matrix4().copy(tcp(pose)).multiply(rel);
  const fixA = placed(insp, relA);
  const fixB = placed(insp, relB);
  const binA = placed(bin('bin_good'), relA);
  const binB = placed(bin('bin_bad'), relB);
  const tcpNow = new THREE.Matrix4();

  // ---------- 1.1 Aufstellungsplan (Draufsicht) ----------
  const planLines = [];
  const PLZ = 0.035;
  const pl = (pts, o = {}) => {
    const l = new InkLine(pts.map((p) => (p.isVector3 ? p.setZ(PLZ) : W(p[0], p[1]).setZ(PLZ))), { width: 1.5, progress: 0, ...o });
    planLines.push(l);
    scene.add(l.object);
    return l;
  };
  const wsRect = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([x, y]) => ws2r(x, y));
  const rect = (cx, cy, sx, sy) => [[cx - sx / 2, cy - sy / 2], [cx + sx / 2, cy - sy / 2], [cx + sx / 2, cy + sy / 2], [cx - sx / 2, cy + sy / 2]];
  pl(wsRect(-70, -70, WSW + 70, WSH + 70), { closed: true, width: 2 });
  pl(wsRect(0, 0, WSW, WSH), { closed: true, dashed: true, dash: 0.08, gap: 0.06, hex: MODULE_COLOR.M1 });
  markers.forEach((m) => pl(rect(m.x, m.y, 50, 50), { closed: true, width: 1.2 }));
  pl(rect(insp[0], insp[1], 70, 90), { closed: true, width: 1.6, hex: MODULE_COLOR.M3 });
  bins.forEach((b) => pl(rect(b.p[0], b.p[1], 110, 100), { closed: true, width: 1.6, hex: b.hex }));
  pl(circle(W(0, 0), 0.9, 48, PLZ), { closed: true, width: 2, hex: MODULE_COLOR.M2 });
  pl(arc(W(0, 0), 7.4, -1.15, 1.05, PLZ, 48), { dashed: true, dash: 0.12, gap: 0.09, width: 1, hex: MODULE_COLOR.M2 });
  pl(rect(pole.x, pole.y, 30, 30), { closed: true, width: 1.6, hex: MODULE_COLOR.M1 });
  const planTexts = [];
  const pt = (str, p, o = {}) => {
    const t = text(str, { font: 'mono', size: 0.2, anchorX: 'center', anchorY: 'middle', opacity: 0, ...o });
    t.position.copy(p).setZ(PLZ + 0.005);
    scene.add(t);
    planTexts.push(t);
    return t;
  };
  pt('Arbeitsraum 330 × 330 mm', W(...ws2r(WSW / 2, -110)), { hex: MODULE_COLOR.M1 });
  pt('LARA', W(0, -130), { font: 'title', size: 0.3, hex: MODULE_COLOR.M2 });
  pt('Reichweite ~ 740 mm', W(560, 520), { size: 0.17, hex: MODULE_COLOR.M2 });
  pt('Prüfung', W(insp[0], insp[1] - 75), { size: 0.17, hex: MODULE_COLOR.M3 });
  bins.forEach((b) => pt(b.label, W(b.p[0] - 92, b.p[1]), { size: 0.17, hex: b.hex, anchorX: 'right' }));
  pt('Kamera M1', W(pole.x, pole.y - 50), { size: 0.17, hex: MODULE_COLOR.M1 });

  // Titel und Schriftfeld links neben dem Plan
  const TX = -7.6;
  const title = text(TITLE, { font: 'title', size: 0.52, anchorY: 'top', maxWidth: 6.4, lineHeight: 1.1, opacity: 0 });
  title.position.set(TX, 3.4, 0.03);
  const sub = text('Projektarbeit · Hochschule Kempten', { font: 'titleLight', size: 0.28, anchorY: 'top', opacity: 0 });
  sub.position.set(TX, 0.75, 0.03);
  scene.add(title, sub);
  const FB = { x: TX, y: -0.6, w: 6.4, rows: [['BEARBEITUNG', NAMES.join(' · ')], ['MODULE', 'M1 Felix · M2 Joshua · M3 Niklas · M4 Jeremy'], ['ROBOTER', `Neura LARA 5 · Werkzeug ${rc.tool_name}`]] };
  const fbLines = [];
  const fbTexts = [];
  const rowH = 0.62;
  const fbY = (i) => FB.y - i * rowH;
  for (let i = 0; i <= FB.rows.length; i++) fbLines.push(new InkLine([v3(FB.x, fbY(i), 0.03), v3(FB.x + FB.w, fbY(i), 0.03)], { width: i === 0 || i === FB.rows.length ? 2 : 1, progress: 0 }));
  fbLines.push(new InkLine([v3(FB.x, fbY(0), 0.03), v3(FB.x, fbY(FB.rows.length), 0.03)], { width: 2, progress: 0 }));
  fbLines.push(new InkLine([v3(FB.x + FB.w, fbY(0), 0.03), v3(FB.x + FB.w, fbY(FB.rows.length), 0.03)], { width: 2, progress: 0 }));
  fbLines.forEach((l) => scene.add(l.object));
  FB.rows.forEach(([k, v], i) => {
    const kt = text(k, { font: 'mono', size: 0.12, hex: T.inkSoft, anchorY: 'top', letterSpacing: 0.08, opacity: 0 });
    kt.position.set(FB.x + 0.12, fbY(i) - 0.08, 0.03);
    const vt = text(v, { font: 'sans', size: 0.21, anchorY: 'top', maxWidth: FB.w - 0.25, opacity: 0 });
    vt.position.set(FB.x + 0.12, fbY(i) - 0.27, 0.03);
    scene.add(kt, vt);
    fbTexts.push(kt, vt);
  });
  const thanks = text('Danke.', { font: 'title', size: 0.9, anchorY: 'top', opacity: 0 });
  thanks.position.set(TX, 3.4, 0.03);
  scene.add(thanks);

  // ---------- Beschriftungen in 3D (zur Kamera gedreht, mit Papierschild, immer obenauf) ----------
  const billboards = [];
  const plates = [];
  const bb = (obj) => (billboards.push(obj), scene.add(obj), obj);
  /** Papierschild in Textgröße hinter `t` (gleicher Elternknoten), Deckkraft folgt dem Text. */
  function plated(t, pad = 0.05) {
    const plate = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false, depthTest: false }));
    plate.renderOrder = 8;
    plate.userData.plate = true;
    plate.visible = false;
    plate.scale.set(0.0001, 0.0001, 1);
    t.parent.add(plate);
    // Größe aus dem Textlayout; troika meldet jedes (Neu-)Layout mit „synccomplete“
    const fit = () => {
      const [x0, y0, x1, y1] = t.textRenderInfo.blockBounds;
      plate.scale.set(x1 - x0 + pad * 2, y1 - y0 + pad * 2, 1);
      plate.position.set(t.position.x + (x0 + x1) / 2, t.position.y + (y0 + y1) / 2, t.position.z - 0.002);
    };
    t.addEventListener('synccomplete', fit);
    if (t.textRenderInfo) fit();
    plates.push({ t, plate });
    return t;
  }
  /** Alle Materialien unter `obj` ohne Tiefentest zeichnen (Beschriftung verdeckt nichts und wird nicht verdeckt). */
  function onTop(obj) {
    obj.traverse((o) => {
      if (o.material) {
        o.material.depthTest = false;
        o.renderOrder = o.userData.plate ? 8 : Math.max(o.renderOrder, 10);
      }
    });
    return obj;
  }
  const worldOf = (o) => () => o.getWorldPosition(new THREE.Vector3());
  function callout(n, label, at, off) {
    const getAt = typeof at === 'function' ? at : () => at;
    const g = new THREE.Group();
    const b = new Balloon(String(n), { r: 0.24, size: 0.18 });
    const left = off.x < 0;
    const t = text(label, { font: 'sansMedium', size: 0.24, anchorX: left ? 'right' : 'left', anchorY: 'middle', opacity: 0 });
    t.position.set(left ? -0.34 : 0.34, 0, 0.002);
    g.add(b.object, t);
    bb(g);
    plated(t);
    onTop(g);
    const leader = new InkLine([v3(0, 0, 0), v3(0, 0, 1)], { width: 1.1, progress: 0 });
    scene.add(leader.object);
    return {
      set(v) {
        const a = getAt();
        g.position.copy(a).add(off);
        setPts(leader, [a, g.position.clone()]);
        b.appear = v;
        t.opacity = clamp01(v * 2 - 1);
        leader.progress = clamp01(v * 1.5);
        g.visible = v > 0;
      },
    };
  }
  const C3 = [
    [1, 'LARA (6 Achsen)', worldOf(lara.pivots[1].g), v3(-2.6, -0.6, 1.6)],
    [2, `Greifer ${rc.tool_name}`, worldOf(gHousing), v3(2.2, -0.4, 1.4)],
    [3, 'Kamera M1 an der Stange', worldOf(camM1), v3(1.4, -0.4, 0.9)],
    [4, 'Seitenkamera M3', null, v3(2.6, 0.2, 2.2)],
    [5, 'Handgelenkkamera M4', worldOf(wristCam), v3(-2.6, -0.8, 0.9)],
    [6, 'Arbeitsraum mit ArUco-Markern', W(...ws2r(WSW, 0), TZ), v3(1.6, -1.4, 0.4)],
    [7, 'Prüfposition', W(insp[0], insp[1], insp[2] - 10), v3(2.8, -1.2, 0.3)],
    [8, 'Ablagen GUT / SCHLECHT', W(bin('bin_good')[0] - 55, bin('bin_good')[1], TZ + 20), v3(-3.0, 0.6, 1.0)],
  ];

  // Seitenkamera M3 vor der Etikettseite des abgelegten Bauteils (Lage angenommen)
  const faceN = new THREE.Vector3(0, -1, 0).applyMatrix4(new THREE.Matrix4().extractRotation(fixA)).setZ(0).normalize();
  const sideCamPos = new THREE.Vector3(insp[0] / 1000, insp[1] / 1000, (insp[2] + 10) / 1000).addScaledVector(faceN, 0.12);
  keep(box(12, 12, insp[2] + 10, '#9AA0A6', sideCamPos.x * 1000, sideCamPos.y * 1000, TZ));
  const camM3 = keep(solid(new THREE.BoxGeometry(0.05, 0.05, 0.08), MODULE_COLOR.M3));
  camM3.position.copy(sideCamPos).setZ(sideCamPos.z + 0.02);
  camM3.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), faceN.clone().negate());
  cell.add(camM3);
  C3[3][2] = worldOf(camM3);
  const callouts = C3.map(([n, label, at, off]) => callout(n, label, at, off));

  // ---------- 1.3 Bauteil-Notizen ----------
  const partNoteDefs = [
    ['Fase: macht den Winkel eindeutig', new THREE.Vector3(PL / 2 - CH / 2, PWd / 2 - CH / 2, PHt / 2), v3(0.4, 0.5, 0.45)],
    [`Seriennummer ${data.part.serial}`, new THREE.Vector3(-0.014, -PWd / 2, 0), v3(-0.9, -0.4, 0.35)],
    [`Loch Ø ${data.part.hole_mm} mm`, new THREE.Vector3(0.012, -PWd / 2, 0), v3(-0.2, -0.8, -0.25)],
    ['Kerbe', new THREE.Vector3(0.025, -PWd / 2, 0), v3(0.6, -0.6, -0.2)],
  ];
  const partNotes = partNoteDefs.map(([label, local, off]) => {
    const at = local.clone().applyMatrix4(tablePose(shotA)).multiplyScalar(U);
    const g = new THREE.Group();
    const t = text(label, { font: 'sansMedium', size: 0.12, anchorX: off.x < 0 ? 'right' : 'left', anchorY: 'middle', opacity: 0 });
    g.add(t);
    g.position.copy(at.clone().add(off));
    bb(g);
    plated(t, 0.035);
    onTop(g);
    const leader = new InkLine([at, at.clone().add(off.clone().multiplyScalar(0.97))], { width: 1.1, progress: 0 });
    scene.add(leader.object);
    return { set(v) { t.opacity = clamp01(v * 2 - 1); leader.progress = clamp01(v * 1.5); g.visible = v > 0; } };
  });
  const dimNote = bb(new THREE.Group());
  const dimText = text(`${data.part.length_mm} × ${data.part.width_mm} × ${data.part.height_mm} mm · 3D-Druck`, { font: 'mono', size: 0.15, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0 });
  dimNote.add(dimText);
  dimNote.position.copy(W(shotA.robot.x, shotA.robot.y, -60));

  // ---------- Zustandsanzeige (1.4, 7.5) ----------
  const stateG = bb(new THREE.Group());
  const stateKey = text('ZUSTAND', { font: 'mono', size: 0.16, hex: T.inkSoft, anchorX: 'left', anchorY: 'bottom', letterSpacing: 0.08, opacity: 0 });
  const stateVal = text('IDLE', { font: 'title', size: 0.5, anchorX: 'left', anchorY: 'top', opacity: 0 });
  stateVal.position.y = -0.05;
  stateG.add(stateKey, stateVal);
  const binCount = bins.map((b) => {
    const t = text('', { font: 'monoMedium', size: 0.26, hex: b.hex, anchorX: 'right', anchorY: 'middle', opacity: 0 });
    const g = bb(new THREE.Group());
    g.add(t);
    g.position.copy(W(b.p[0] - 75, b.p[1], TZ + 15));
    plated(t);
    onTop(g);
    return t;
  });
  let lastState = '';

  // ---------- 4.1 Gelenke und TCP-Maß ----------
  const jointBalloons = lara.pivots.map((_, i) => {
    const b = new Balloon(String(i + 1), { r: 0.22, size: 0.17, hex: MODULE_COLOR.M2 });
    bb(b.object);
    onTop(b.object);
    return b;
  });
  const tcpDimLine = new InkLine([v3(0, 0, 0), v3(0, 0, 1)], { width: 1.6, hex: MODULE_COLOR.M2, progress: 0 });
  scene.add(tcpDimLine.object);
  const tcpDimG = bb(new THREE.Group());
  const tcpDimText = text(`Flansch → TCP ${String(rc.tool_tcp_mm?.[2] ?? 197.5).replace('.', ',')} mm`, { font: 'monoMedium', size: 0.26, hex: MODULE_COLOR.M2, anchorX: 'left', anchorY: 'middle', opacity: 0 });
  const tcpDimSub = text('LWR50F 28 mm + LWR50L 169,5 mm', { font: 'mono', size: 0.18, hex: T.inkSoft, anchorX: 'left', anchorY: 'top', opacity: 0 });
  tcpDimSub.position.y = -0.22;
  tcpDimG.add(tcpDimText, tcpDimSub);
  plated(tcpDimText);
  plated(tcpDimSub);
  onTop(tcpDimG);

  // ---------- 4.2 Geschwindigkeitsprofil als eigene Karte (Höhe über der Greifpose, überhöht) ----------
  const fmtV = (v) => `${v.toFixed(2).replace('.', ',')} m/s`;
  const speedG = bb(new THREE.Group());
  const SCW = 3.0;
  const SCH = 2.8;
  const yOf = (mm) => -0.95 + (Math.min(mm, AH) / AH) * 1.7; // 0 … AH mm über der Greifpose
  const AXX = -0.75;
  const speedPlate = new THREE.Mesh(new THREE.PlaneGeometry(SCW, SCH), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false }));
  speedPlate.userData.plate = true;
  speedPlate.layers.enable(LAYER_SOLID); // deckt im Normalenpass die Tuschekanten dahinter ab
  const speedFrame = new InkLine([v3(-SCW / 2, -SCH / 2), v3(SCW / 2, -SCH / 2), v3(SCW / 2, SCH / 2), v3(-SCW / 2, SCH / 2)], { closed: true, width: 1.4, progress: 0 });
  const speedTitle = text('Anfahrt: Höhe über der Greifpose', { font: 'sansMedium', size: 0.16, anchorX: 'left', anchorY: 'top', opacity: 0 });
  speedTitle.position.set(-SCW / 2 + 0.15, SCH / 2 - 0.12, 0.01);
  const speedLines = [
    new InkLine([v3(AXX, yOf(AH), 0.01), v3(AXX, yOf(SLOW), 0.01)], { width: 9, hex: MODULE_COLOR.M2, progress: 0 }),
    new InkLine([v3(AXX, yOf(SLOW), 0.01), v3(AXX, yOf(0), 0.01)], { width: 9, hex: T.signal, progress: 0 }),
    ...[AH, SLOW, 0].map((mm) => new InkLine([v3(AXX - 0.14, yOf(mm), 0.01), v3(AXX + 0.14, yOf(mm), 0.01)], { width: 1.4, progress: 0 })),
  ];
  const speedTexts = [
    [`${AH} mm`, AXX - 0.22, yOf(AH), 'right', T.inkSoft],
    [`${SLOW} mm`, AXX - 0.22, yOf(SLOW), 'right', T.inkSoft],
    ['0', AXX - 0.22, yOf(0), 'right', T.inkSoft],
    [fmtV(rc.linear_speed_mps), AXX + 0.3, (yOf(AH) + yOf(SLOW)) / 2, 'left', MODULE_COLOR.M2],
    [fmtV(rc.approach_speed_mps), AXX + 0.3, (yOf(SLOW) + yOf(0)) / 2, 'left', T.signal],
    ['Vorpose (PTP)', AXX + 0.3, yOf(AH) + 0.02, 'left', T.inkSoft],
    ['greifen', AXX + 0.3, yOf(0) - 0.02, 'left', T.inkSoft],
  ].map(([str, x, y, ax, hex], i) => {
    const t = text(str, { font: i === 3 || i === 4 ? 'monoMedium' : 'mono', size: i === 3 || i === 4 ? 0.2 : 0.14, hex, anchorX: ax, anchorY: i === 5 ? 'bottom' : i === 6 ? 'top' : 'middle', opacity: 0 });
    t.position.set(x, y, 0.01);
    return t;
  });
  const speedDot = new THREE.Mesh(new THREE.CircleGeometry(0.075, 24), new THREE.MeshBasicMaterial({ color: color(T.ink), transparent: true }));
  const speedDotLine = new InkLine([v3(AXX - 0.32, 0, 0.012), v3(AXX + 0.18, 0, 0.012)], { width: 1.6, progress: 0 });
  speedG.add(speedPlate, speedFrame.object, speedTitle, ...speedLines.map((l) => l.object), ...speedTexts, speedDotLine.object, speedDot);
  onTop(speedG);
  const speedAnchor = W(gPB[0], gPB[1], TZ); // Karte steht bildfest rechts, Größe folgt dem Kameraabstand
  const camRight = new THREE.Vector3();
  const camUp = new THREE.Vector3();
  const camFwd = new THREE.Vector3();

  // ---------- 4.2 Vom Bauteil zur Greifpose: as_target → to_neura → IK → move_joint (robot.py) ----------
  // Alles im Roboter-Basis-KS: die ObjectPose von M1 liegt schon dort, die Skizze zeigt nur die rz-Drehung der Zielpose.
  const f1 = (v, d = 1) => v.toFixed(d).replace('.', ',').replace(/^-(0(,0+)?)$/, '$1');
  const thB = shotB.robot.theta;
  const OFF = rc.gripper_angle_offset_deg;
  const M2C = MODULE_COLOR.M2;
  // Karte in Abschnitten: Nummer + Bedeutung links, Funktion rechts, darunter die echten Zahlen.
  // Schritt 0 bis to_neura(), Schritt 1 (Fahrt) ergänzt IK und move_joint.
  const CDW = 4.6;
  const codeG = bb(new THREE.Group());
  const rzSum = P.home[5] + thB + OFF;
  const rzWrap = Math.round((gPB[5] - rzSum) / 360) * 360;
  const SECTIONS = [
    [1, 'Pose von M1', 'ObjectPose, Basis-KS', MODULE_COLOR.M1, 0, [
      `x ${f1(shotB.robot.x)}   y ${f1(shotB.robot.y)} mm   Winkel ${f1(thB)}°`,
    ]],
    [2, 'Zielpose', 'as_target()', M2C, 0, [
      `z    Tisch ${f1(TZ)} + Greifhöhe ${f1(gPB[2] - TZ, 0)} = ${f1(gPB[2])} mm`,
      `rx   ${f1(P.home[3], 0)}°   ry ${f1(P.home[4], 0)}°   wie Home`,
      [`rz   ${f1(P.home[5], 0)}° + ${f1(thB)}° + ${f1(OFF, 0)}°${rzWrap ? ` ${rzWrap < 0 ? '-' : '+'} ${Math.abs(rzWrap)}°` : ''} = ${f1(gPB[5])}°`, 'monoMedium', M2C],
      [`     Home + Bauteilwinkel + Greifer-Offset`, 'mono', T.inkSoft],
    ]],
    [3, 'Für die Steuerung', 'to_neura()', M2C, 0, [
      `m, rad  [${gPB.slice(0, 3).map((v) => f1(v / 1000, 3)).join('  ')}  ${gPB.slice(3).map((v) => f1(v * DEG, 2)).join('  ')}]`,
    ]],
    [4, 'Gelenkwinkel', 'compute_inverse_kinematics()', M2C, 1, [
      `Vorpose ${AH} mm darüber, Start = Gelenke jetzt`,
    ]],
    [5, 'PTP-Fahrt', 'move_joint(q)', M2C, 1, [
      [`q = [${toPre.q1.map((q) => f1(q / DEG, 0)).join('  ')}]°`, 'monoMedium', T.ink],
      ['Gelenkwinkel hier aus der URDF berechnet', 'mono', T.inkSoft],
    ]],
  ];
  const PADX = 0.2;
  const CODE = []; // { t, step, k } – k = Reihenfolge innerhalb des Schritts
  const seps = []; // { l, step, k }
  const order = [0, 0];
  const put = (str, opt, x, y, step) => {
    const t = text(str, { size: 0.13, anchorY: 'top', opacity: 0, ...opt });
    t.position.set(x, y, 0.01);
    CODE.push({ t, step, k: order[step] });
  };
  let cy = -0.2;
  put('m2_robot_control/robot.py', { font: 'mono', size: 0.115, hex: T.inkSoft }, -CDW / 2 + PADX, cy, 0);
  cy -= 0.3;
  SECTIONS.forEach(([n, title, fn, hex, step, lines]) => {
    const l = new InkLine([v3(-CDW / 2 + PADX, cy), v3(CDW / 2 - PADX, cy)], { width: 0.9, hex: T.inkSoft, progress: 0 });
    seps.push({ l, step, k: order[step] });
    cy -= 0.12;
    put(String(n), { font: 'monoMedium', size: 0.15, hex }, -CDW / 2 + PADX, cy, step);
    put(title, { font: 'sansMedium', size: 0.165, hex }, -CDW / 2 + PADX + 0.25, cy, step);
    put(fn, { font: 'mono', size: 0.12, hex: T.inkSoft, anchorX: 'right' }, CDW / 2 - PADX, cy + 0.01, step);
    order[step]++;
    cy -= 0.28;
    lines.forEach((ln) => {
      const [str, font, lhex] = Array.isArray(ln) ? ln : [ln, 'mono', T.ink];
      put(str, { font, hex: lhex }, -CDW / 2 + PADX + 0.25, cy, step);
      cy -= 0.22;
    });
    order[step]++;
    cy -= 0.1;
  });
  const CDH = -cy + 0.05;
  const CARD_FRAC = 0.78; // Anteil der Bildhöhe
  const CARD_SIDE = -0.87 + (CARD_FRAC * CDW) / CDH / 2; // linker Rand knapp im Bild
  CODE.forEach(({ t }) => (t.position.y += CDH / 2));
  seps.forEach(({ l }) => (l.object.position.y += CDH / 2));
  const codePlate = new THREE.Mesh(new THREE.PlaneGeometry(CDW, CDH), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false }));
  codePlate.userData.plate = true;
  codePlate.layers.enable(LAYER_SOLID);
  const codeFrame = new InkLine([v3(-CDW / 2, -CDH / 2), v3(CDW / 2, -CDH / 2), v3(CDW / 2, CDH / 2), v3(-CDW / 2, CDH / 2)], { closed: true, width: 1.4, progress: 0 });
  codeG.add(codePlate, codeFrame.object, ...seps.map((s) => s.l.object), ...CODE.map((c) => c.t));
  onTop(codeG);
  // Winkelskizze am Teil B (in der Tischebene): Basis-x → Bauteilwinkel (M1) → + Greifer-Offset = rz − Home
  const skC = W(shotB.robot.x, shotB.robot.y, TZ + 22);
  const skRay = (deg, len) => [skC.clone(), skC.clone().add(v3(Math.cos(deg * DEG) * len, Math.sin(deg * DEG) * len, 0))];
  const skLines = [
    new InkLine(skRay(0, 1.3), { width: 1.4, dashed: true, dash: 0.06, gap: 0.05, hex: T.inkSoft, progress: 0 }),
    new InkLine(arc(skC, 0.75, 0, thB * DEG, skC.z, 64), { width: 2.2, hex: MODULE_COLOR.M1, progress: 0 }),
    new InkLine(skRay(thB, 1.3), { width: 2.4, hex: MODULE_COLOR.M1, progress: 0 }),
    new InkLine(arc(skC, 1.0, thB * DEG, (thB + OFF) * DEG, skC.z, 40), { width: 2.2, hex: M2C, progress: 0 }),
    new InkLine(skRay(thB + OFF, 1.3), { width: 2.4, hex: M2C, progress: 0 }),
  ];
  skLines.forEach((l) => scene.add(onTop(l.object)));
  const skAt = (deg, r) => skC.clone().add(v3(Math.cos(deg * DEG) * r, Math.sin(deg * DEG) * r, 0));
  const skLabel = (str, pos, hex, ax = 'left') => {
    const g = bb(new THREE.Group());
    const t = text(str, { font: 'monoMedium', size: 0.15, hex, anchorX: ax, anchorY: 'middle', opacity: 0 });
    g.add(t);
    plated(t, 0.04);
    onTop(g);
    g.position.copy(pos);
    return t;
  };
  const skTexts = [
    skLabel('Basis x', skAt(0, 1.42), T.inkSoft),
    skLabel(`Winkel ${f1(thB)}° (M1)`, skAt(thB / 2, 0.88), MODULE_COLOR.M1),
    skLabel(`+ ${f1(OFF, 0)}° Greifer-Offset`, skAt(thB + OFF / 2, 1.2), M2C, 'right'),
  ];
  // Gelenkwinkel an den Positionsnummern (laufen während der Fahrt mit)
  const qTexts = lara.pivots.map((_, i) => {
    const g = bb(new THREE.Group());
    const t = text('', { font: 'monoMedium', size: 0.17, hex: M2C, anchorX: i % 2 === 0 ? 'right' : 'left', anchorY: 'middle', opacity: 0 });
    g.add(t);
    plated(t, 0.04);
    plates[plates.length - 1].plate.layers.enable(LAYER_SOLID); // Schild deckt die Tuschekanten des Arms dahinter ab
    onTop(g);
    return { g, t, last: '' };
  });

  // ---------- 4.4 Greifwinkel als Prinzipskizze neben der Zelle ----------
  const DG = v3(13.6, 0.2, 0.02);
  const thA = shotA.robot.theta * DEG;
  const SCL = 40; // Skizze im Maßstab 40:1 (mm → Papier ×0,04)
  const sk = (x, y) => DG.clone().add(v3((x * SCL) / 1000, (y * SCL) / 1000, 0));
  const rotXY = (x, y, a) => [Math.cos(a) * x - Math.sin(a) * y, Math.sin(a) * x + Math.cos(a) * y];
  const outline = [[-30, -20], [30, -20], [30, 8], [18, 20], [-30, 20]].map(([x, y]) => sk(...rotXY(x, y, thA)));
  const angLines = [
    new InkLine(outline, { width: 2.4, hex: T.part, closed: true, progress: 0 }),
    new InkLine([sk(-48, 0), sk(62, 0)], { width: 1, dashed: true, dash: 0.08, gap: 0.06, progress: 0 }),
    ...arrowPts(sk(0, 0), sk(...rotXY(52, 0, thA)), 0.22).map((p) => new InkLine(p, { width: 2, hex: T.part, progress: 0 })),
    new InkLine(arc(DG, 1.3, 0, thA, 0.02), { width: 1.4, progress: 0 }),
  ];
  const jawA = thA + Math.PI / 2;
  const jawLines = [-1, 1].map((s) => {
    const c = rotXY(0, s * 27, thA);
    return new InkLine([sk(c[0] + Math.cos(thA) * 10, c[1] + Math.sin(thA) * 10), sk(c[0] - Math.cos(thA) * 10, c[1] - Math.sin(thA) * 10)], { width: 6, hex: MODULE_COLOR.M2, progress: 0 });
  });
  const jawAxisLine = new InkLine([sk(...rotXY(0, -42, thA)), sk(...rotXY(0, 42, thA))], { width: 1.2, dashed: true, dash: 0.08, gap: 0.06, hex: MODULE_COLOR.M2, progress: 0 });
  [...angLines, ...jawLines, jawAxisLine].forEach((l) => scene.add(l.object));
  const rzGrip = graspPose(shotA)[5];
  const angTexts = [
    [`Bauteilachse ${String(shotA.robot.theta.toFixed(1)).replace('.', ',')}°`, sk(...rotXY(66, 0, thA)), T.part],
    ['Backen schließen quer zur langen Seite', sk(...rotXY(-8, -50, thA)), MODULE_COLOR.M2, 'right'],
  ].map(([str, p, hex, ax = 'left']) => {
    const t = text(str, { font: 'sansMedium', size: 0.2, hex, anchorX: ax, anchorY: 'middle', opacity: 0 });
    t.position.copy(p).setZ(0.03);
    scene.add(t);
    return t;
  });
  const formula = text(
    `rz = home.rz + Winkel + ${rc.gripper_angle_offset_deg}°  =  ${P.home[5]}° + ${shotA.robot.theta.toFixed(1).replace('.', ',')}° + ${rc.gripper_angle_offset_deg}°  →  ${rzGrip.toFixed(1).replace('.', ',')}°\n` +
      `${rc.gripper_angle_offset_deg}° = 90° (quer zur langen Seite) + 23° (Greifer verdreht montiert, Labor 06.10.: vorher 90°)`,
    { font: 'mono', size: 0.17, anchorX: 'left', anchorY: 'top', lineHeight: 1.5, maxWidth: 10.5, opacity: 0 },
  );
  formula.position.set(DG.x - 5.4, DG.y - 2.6, 0.03);
  scene.add(formula);

  // ---------- 4.4 Arbeitsraumgrenzen ----------
  const L = rc.limits_mm;
  const corners = [];
  for (const z of L.z) for (const y of L.y) for (const x of L.x) corners.push(W(x, y, z));
  const edges = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
  const limitLines = edges.map(([a, b]) => {
    const l = new InkLine([corners[a], corners[b]], { width: 1.4, dashed: true, dash: 0.14, gap: 0.1, hex: MODULE_COLOR.M2, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const limitG = bb(new THREE.Group());
  const limitText = text(`Software-Grenzen: x ${L.x.join('…')} · y ${L.y.join('…')} · z ${L.z.join('…')} mm`, { font: 'mono', size: 0.34, hex: MODULE_COLOR.M2, anchorX: 'left', anchorY: 'bottom', opacity: 0 });
  limitG.add(limitText);
  plated(limitText);
  onTop(limitG);
  limitG.position.copy(W(L.x[0], L.y[1], L.z[1] + 40));
  const outP = W(L.x[1] + 80, -250, 120);
  const crossLines = [[v3(-0.25, 0, -0.25), v3(0.25, 0, 0.25)], [v3(-0.25, 0, 0.25), v3(0.25, 0, -0.25)]].map(([a, b]) => {
    const l = new InkLine([outP.clone().add(a), outP.clone().add(b)], { width: 3, hex: T.signal, progress: 0 });
    scene.add(l.object);
    return l;
  });
  const outG = bb(new THREE.Group());
  const outText = text(`Ziel x = ${L.x[1] + 80} mm > ${L.x[1]} → RobotError`, { font: 'monoMedium', size: 0.32, hex: T.signal, anchorX: 'left', anchorY: 'middle', opacity: 0 });
  outText.position.x = 0.45;
  const stopText = text('STOPP: eigener Thread, nie von einer Bewegung blockiert · stop() beendet das Programm, weiter nur nach reset()', {
    font: 'sans', size: 0.26, anchorX: 'left', anchorY: 'top', maxWidth: 8.5, opacity: 0,
  });
  stopText.position.set(0.45, -0.35, 0);
  outG.add(outText, stopText);
  plated(outText);
  plated(stopText);
  onTop(outG);
  outG.position.copy(outP);

  // ---------- 4.5 Simulator: Schattenroboter ohne Kinematik ----------
  // fake_neura_server spricht das Protokoll der Steuerung, rechnet aber nichts: er merkt sich nur die
  // Zielpose. Deshalb springt der Schatten ans Ziel, während LARA fährt. Lage links hinter dem Roboter.
  const GHOST_X = -1.9; // m im Basis-KS
  const ghost = new Lara(ctx.lara, { tool: lara.tool });
  ghost.object.position.x = GHOST_X;
  // nur Tuschekanten und ein Hauch Fläche: ein Roboter, den es nicht gibt
  const ghostLook = (o) => {
    if (!o.material) return;
    o.material = o.material.clone();
    o.material.color = color(T.paper);
    o.material.transparent = true;
    o.material.opacity = 0.35;
    o.castShadow = false;
  };
  ghost.meshes.forEach(ghostLook);
  const ghostGrip = gBody.clone(true);
  ghostGrip.traverse(ghostLook);
  ghost.flange.add(ghostGrip);
  cell.add(ghost.object);
  const label3d = (title, sub, at, hex = T.ink) => {
    const g = bb(new THREE.Group());
    const t = text(title, { font: 'sansMedium', size: 0.36, hex, anchorX: 'center', anchorY: 'bottom', opacity: 0 });
    const d = text(sub, { font: 'mono', size: 0.2, hex: T.inkSoft, anchorX: 'center', anchorY: 'top', opacity: 0, maxWidth: 6, align: 'center' });
    d.position.y = -0.08;
    g.add(t, d);
    plated(t);
    plated(d);
    onTop(g);
    g.position.copy(at);
    return [t, d];
  };
  const simLabels = [
    ...label3d('NeuraPy-Client, unverändert', 'dasselbe JSON-Protokoll, Port 65432', W(GHOST_X * 500, 0, 1110)),
    ...label3d('LARA 5 · Steuerung', 'fährt wirklich', W(0, 0, 870), MODULE_COLOR.M2),
    ...label3d('fake_neura_server', 'keine Kinematik: merkt sich nur die Zielpose', W(GHOST_X * 1000, 0, 870), T.inkSoft),
  ];
  // Pfeile vom Client zu Steuerung und Simulator (Spitzen in der x-z-Ebene, zur Kamera hin sichtbar)
  const arrowXZ = (a, b, head = 0.35) => {
    const d = b.clone().sub(a).normalize();
    const n = v3(-d.z, 0, d.x);
    const p = (k) => b.clone().addScaledVector(d, -head).addScaledVector(n, k * head * 0.5);
    return [[a, b], [p(1), b, p(-1)]];
  };
  const simArrows = [W(-300, 0, 960), W(GHOST_X * 1000 + 300, 0, 960)].map((b) => arrowXZ(W(GHOST_X * 500, 0, 1050).lerp(b, 0.25), b, 0.3))
    .flat()
    .map((pts) => {
      const l = new InkLine(pts, { width: 1.8, progress: 0 });
      scene.add(l.object);
      return l;
    });
  // Aufrufprotokoll des Simulators (wie fake_neura_server.calls), Zeilen erscheinen mit den Aufrufen
  const CALLS = [
    'set_tool("ZimmerLWR50")  -> True',
    'compute_inverse_kinematics(Vorpose Prüfplatz)',
    'move_joint(q)  -> True',
    'compute_inverse_kinematics(Vorpose Bauteil)',
    'move_joint(q)  -> True',
  ];
  const callG = bb(new THREE.Group());
  const callHead = text('fake_neura_server.calls', { font: 'monoMedium', size: 0.24, hex: T.inkSoft, anchorX: 'left', anchorY: 'top', opacity: 0 });
  const callLines = CALLS.map((c, i) => {
    const t = text(c, { font: 'mono', size: 0.24, anchorX: 'left', anchorY: 'top', opacity: 0 });
    t.position.y = -0.42 - i * 0.36;
    return t;
  });
  callG.add(callHead, ...callLines);
  [callHead, ...callLines].forEach((t) => plated(t));
  onTop(callG);
  callG.position.copy(W(GHOST_X * 1000 + 720, 0, 640)); // freie Mitte zwischen Schatten und LARA
  const testsText = text(`${data.tests.total} automatische Tests laufen so ohne Roboter – Ablauf, Grenzen, STOPP`, { font: 'sans', size: 0.24, anchorX: 'center', anchorY: 'top', opacity: 0 });
  testsText.fontSize = 0.3;
  const testsG = bb(new THREE.Group());
  testsG.add(testsText);
  plated(testsText);
  onTop(testsG);
  testsG.position.copy(W(GHOST_X * 500, -300, 0));
  // Zeitpunkte der Aufrufe (Beginn des Abschnitts) und Zielgelenke des Schattens
  const callAt = [];
  sim.segs.forEach((sg) => {
    if (sg.call === undefined) return;
    callAt[sg.call] = sg.t0;
    if (sg.kind === 'ptp') callAt[sg.call + 1] = sg.t0 + 0.15;
  });

  /** Bildfeste Karte vor allem anderen: Höhe = frac der Bildhöhe, Mitte um side · Bildhöhe nach rechts versetzt. */
  function screenCard(g, h, frac, side) {
    const camera = ctx.stage.camera;
    camRight.set(1, 0, 0).applyQuaternion(camera.quaternion);
    camUp.set(0, 1, 0).applyQuaternion(camera.quaternion);
    camFwd.set(0, 0, -1).applyQuaternion(camera.quaternion);
    const dist = Math.min(3, 0.5 * speedAnchor.distanceTo(camera.position));
    const visH = 2 * dist * Math.tan((camera.fov * Math.PI) / 360);
    g.scale.setScalar((frac * visH) / h);
    g.position.copy(camera.position).addScaledVector(camFwd, dist).addScaledVector(camRight, side * visH).addScaledVector(camUp, 0.02 * visH);
  }

  // ---------- 7.4 Ausblick: „Mensch ärgere Dich nicht“ auf dem Arbeitsraum ----------
  // Spielfeld 11 × 11 Felder à 30 mm liegt genau im Arbeitsraum (330 mm), Lagen in Arbeitsraum-mm → Basis-KS.
  // Spielfarben aus den Modulfarben (kein Rot/Grün/Lila); LARA spielt Ocker (M2), ihr Haus liegt gut in Reichweite.
  const GF = 30;
  const fieldRb = ([c, r]) => ws2r(15 + c * GF, 15 + r * GF);
  const TRACK = [[0, 4], [1, 4], [2, 4], [3, 4], [4, 4], [4, 3], [4, 2], [4, 1], [4, 0], [5, 0], [6, 0], [6, 1], [6, 2], [6, 3], [6, 4], [7, 4], [8, 4], [9, 4], [10, 4], [10, 5],
    [10, 6], [9, 6], [8, 6], [7, 6], [6, 6], [6, 7], [6, 8], [6, 9], [6, 10], [5, 10], [4, 10], [4, 9], [4, 8], [4, 7], [4, 6], [3, 6], [2, 6], [1, 6], [0, 6], [0, 5]];
  const PLAYERS = [
    { hex: MODULE_COLOR.M1, home: [[0, 0], [1, 0], [0, 1], [1, 1]], start: 0, goal: [[1, 5], [2, 5], [3, 5], [4, 5]] },
    { hex: MODULE_COLOR.M3, home: [[9, 0], [10, 0], [9, 1], [10, 1]], start: 10, goal: [[5, 1], [5, 2], [5, 3], [5, 4]] },
    { hex: MODULE_COLOR.M2, home: [[9, 9], [10, 9], [9, 10], [10, 10]], start: 20, goal: [[9, 5], [8, 5], [7, 5], [6, 5]] },
    { hex: T.ink, home: [[0, 9], [1, 9], [0, 10], [1, 10]], start: 30, goal: [[5, 9], [5, 8], [5, 7], [5, 6]] },
  ];
  const LP = 2; // LARA
  const gameTex = (() => {
    const N = 1024;
    const cv = document.createElement('canvas');
    cv.width = cv.height = N;
    const g = cv.getContext('2d');
    const px = N / (11 * GF);
    const at = ([c, r]) => [(15 + c * GF) * px, N - (15 + r * GF) * px];
    g.fillStyle = '#F1E6CC';
    g.fillRect(0, 0, N, N);
    g.strokeStyle = T.ink;
    g.lineWidth = 3;
    g.strokeRect(6, 6, N - 12, N - 12);
    // Verbindungslinie der Laufbahn
    g.lineWidth = 4;
    g.beginPath();
    TRACK.forEach((f, i) => (i ? g.lineTo(...at(f)) : g.moveTo(...at(f))));
    g.closePath();
    g.stroke();
    const dot = (f, fill) => {
      g.beginPath();
      g.arc(...at(f), 11 * px, 0, Math.PI * 2);
      g.fillStyle = fill;
      g.fill();
      g.lineWidth = 3;
      g.strokeStyle = T.ink;
      g.stroke();
    };
    const tint = (hex, a) => {
      const c = color(hex);
      return `rgba(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)},${a})`;
    };
    TRACK.forEach((f) => dot(f, '#FBF8F1'));
    PLAYERS.forEach((p) => {
      dot(TRACK[p.start], p.hex);
      p.home.forEach((f) => dot(f, tint(p.hex, 0.45)));
      p.goal.forEach((f) => dot(f, tint(p.hex, 0.45)));
    });
    const tx = new THREE.CanvasTexture(cv);
    tx.colorSpace = THREE.SRGBColorSpace;
    tx.anisotropy = 8;
    return tx;
  })();
  const gameBoard = new THREE.Mesh(new THREE.PlaneGeometry(WSW / 1000, WSH / 1000), new THREE.MeshBasicMaterial({ map: gameTex, transparent: true, opacity: 0 }));
  const [gbx, gby] = ws2r(WSW / 2, WSH / 2);
  gameBoard.position.set(gbx / 1000, gby / 1000, (TZ + 0.8) / 1000);
  gameBoard.rotation.z = rot;
  gameBoard.visible = false;
  cell.add(gameBoard);

  // Figuren (Drehkörper): Fuß, Körper, Kopf; Ursprung am Fuß, Höhe 38 mm
  const pawnGeo = new THREE.LatheGeometry([[0, 0], [11, 0], [11, 3], [8, 5], [5, 20], [4, 24], [6.5, 26], [8, 31], [6.5, 36], [3, 38], [0, 38]].map(([x, y]) => new THREE.Vector2(x / 1000, y / 1000)), 32);
  pawnGeo.rotateX(Math.PI / 2);
  const pawnAt = (cr) => {
    const [x, y] = fieldRb(cr);
    return new THREE.Matrix4().makeTranslation(x / 1000, y / 1000, TZ / 1000);
  };
  // Spielstand vor LARAs Zug: Blau steht 3 Felder vor LARAs Startfeld, Petrol und Schwarz sind unterwegs
  const START = TRACK[PLAYERS[LP].start];
  const victim = TRACK[PLAYERS[LP].start + 3];
  const pawns = PLAYERS.flatMap((p, pi) => p.home.map((f, k) => {
    let field = f;
    if (pi === 0 && k === 0) field = victim;
    if (pi === 1 && k === 0) field = TRACK[14];
    if (pi === 3 && k === 0) field = p.goal[1];
    const m = solid(pawnGeo, p.hex, { roughness: 0.5 });
    m.matrixAutoUpdate = false;
    m.visible = false;
    cell.add(m);
    return { m, rest: pawnAt(field), field, p: pi, k };
  }));
  const lara0 = pawns.find((pw) => pw.p === LP && pw.k === 0);
  const blue = pawns.find((pw) => pw.p === 0 && pw.k === 0);
  // Würfel rechts neben dem Spielfeld
  const PIPS = { 1: [[1, 1]], 2: [[0, 0], [2, 2]], 3: [[0, 0], [1, 1], [2, 2]], 4: [[0, 0], [2, 0], [0, 2], [2, 2]], 5: [[0, 0], [2, 0], [1, 1], [0, 2], [2, 2]], 6: [[0, 0], [2, 0], [0, 1], [2, 1], [0, 2], [2, 2]] };
  const pipTex = {};
  for (const n of [1, 2, 3, 4, 5, 6]) {
    const cv = document.createElement('canvas');
    cv.width = cv.height = 128;
    const g = cv.getContext('2d');
    g.fillStyle = '#FBF8F1';
    g.fillRect(0, 0, 128, 128);
    g.fillStyle = T.ink;
    PIPS[n].forEach(([i, j]) => {
      g.beginPath();
      g.arc(30 + i * 34, 30 + j * 34, 11, 0, Math.PI * 2);
      g.fill();
    });
    pipTex[n] = new THREE.CanvasTexture(cv);
    pipTex[n].colorSpace = THREE.SRGBColorSpace;
  }
  // Würfelseiten +x −x +y −y +z −z; oben (+z) wird je Wurf gesetzt
  const dieMats = [2, 5, 3, 4, 1, 6].map((n) => new THREE.MeshStandardMaterial({ map: pipTex[n], roughness: 0.6 }));
  const die = new THREE.Mesh(new THREE.BoxGeometry(0.026, 0.026, 0.026), dieMats);
  die.castShadow = true;
  die.layers.enable(LAYER_SOLID);
  const [dx, dy] = ws2r(378, 170);
  die.position.set(dx / 1000, dy / 1000, (TZ + 13) / 1000);
  die.visible = false;
  cell.add(die);

  // LARA greift Figuren am Kopf (24 mm über dem Fuß), Backen auf 16 mm
  const GRIP_PAWN = 3;
  const pawnPose = (cr) => {
    const [x, y] = fieldRb(cr);
    return [x, y, TZ + 24, P.home[3], P.home[4], P.home[5]];
  };
  const movePawn = (from, to) => [
    { kind: 'ptp', b: up(pawnPose(from), AH), dur: 1.4 },
    ...down(pawnPose(from), null, GRIP_PAWN),
    ...lift(pawnPose(from), null),
    { kind: 'ptp', b: up(pawnPose(to), AH), dur: 1.2 },
    ...down(pawnPose(to), null, 0),
    ...lift(pawnPose(to), null),
  ];
  const kickTo = PLAYERS[0].home[0];
  const game1 = plan([{ kind: 'wait', dur: 1.0 }, ...movePawn(lara0.field, START)], sim.q1);
  const game2 = plan([{ kind: 'wait', dur: 1.0 }, ...movePawn(victim, kickTo), ...movePawn(START, victim)], game1.q1);
  const backSteps = [{ kind: 'ptp', b: up(gPB, AH), seed: demo.q1, dur: 1.6 }];
  backSteps.startGrip = 1; // Teil B wächst zurück in den Greifer
  const back = plan(backSteps, game2.q1);
  CELL.G1 = game1.total;
  CELL.G2 = game2.total;
  CELL.BACK = back.total;
  for (const [name, pl] of [['game1', game1], ['game2', game2], ['back', back]]) {
    pl.segs.forEach((sg, i) => {
      if (!sg.b) return;
      const d = new THREE.Vector3().setFromMatrixPosition(lara.fk(sg.q1)).distanceTo(new THREE.Vector3().setFromMatrixPosition(tcp(sg.b)));
      if (d > 0.001) console.warn(`IK ${name}[${i}]: ${(d * 1000).toFixed(1)} mm Restfehler`);
    });
  }
  // Züge: Figur, Plan, Greif-/Ablegezeit, Ziel; Lage relativ zum TCP beim Greifen
  const grabs = (pl) => pl.segs.filter((s) => s.kind === 'wait' && s.grip !== undefined).map((s) => s.t0 + s.dur * 0.5);
  const [g1a, g1b] = grabs(game1);
  const [g2a, g2b, g2c, g2d] = grabs(game2);
  const relPawn = (from) => new THREE.Matrix4().copy(tcp(pawnPose(from))).invert().multiply(pawnAt(from));
  const MOVES = [
    { pw: lara0, pl: 'game1', t0: g1a, t1: g1b, to: START, rel: relPawn(lara0.field) },
    { pw: blue, pl: 'game2', t0: g2a, t1: g2b, to: kickTo, rel: relPawn(victim) },
    { pw: lara0, pl: 'game2', t0: g2c, t1: g2d, to: victim, rel: relPawn(START) },
  ];
  const kickAt = g2b / game2.total; // Anteil von game2, ab dem Blau wieder im Haus steht

  // Karte links: worum es geht
  const LW = 4.7;
  const lookG = bb(new THREE.Group());
  const LOOK = [
    ['Ausblick: Pflegerobotik', 'title', 0.24, T.ink, 0],
    ['Heute spielt ein kleiner Portalroboter mit', 'sans', 0.15, T.ink, 0.5],
    ['Senioren „Mensch ärgere Dich nicht“ – auf', 'sans', 0.15, T.ink, 0.25],
    ['einem Spielfeld so groß wie unser Arbeitsraum.', 'sans', 0.15, T.ink, 0.25],
    ['Mit LARA und unseren Bausteinen:', 'sansMedium', 0.15, T.ink, 0.45],
    ['M1  Spielfeld entzerren, Figuren finden', 'mono', 0.13, MODULE_COLOR.M1, 0.3],
    ['M2  Figur greifen und setzen: PTP + LIN', 'mono', 0.13, MODULE_COLOR.M2, 0.25],
    ['M3  Würfel lesen statt Seriennummer', 'mono', 0.13, MODULE_COLOR.M3, 0.25],
    ['Sicherheit, GUI und Simulator wie gehabt', 'mono', 0.13, T.inkSoft, 0.25],
    [' ', 'monoMedium', 0.16, MODULE_COLOR.M2, 0.5], // Spielansage, je Zug gesetzt
  ];
  let oy = -0.22;
  const lookTexts = LOOK.map(([str, font, size, hex, dy]) => {
    oy -= dy;
    const t = text(str, { font, size, hex, anchorX: 'left', anchorY: 'top', opacity: 0 });
    t.position.set(-LW / 2 + 0.2, oy, 0.01);
    return t;
  });
  const LH = -oy + 0.45;
  lookTexts.forEach((t) => (t.position.y += LH / 2));
  const lookPlate = new THREE.Mesh(new THREE.PlaneGeometry(LW, LH), new THREE.MeshBasicMaterial({ color: color(T.paper), transparent: true, depthWrite: false }));
  lookPlate.userData.plate = true;
  lookPlate.layers.enable(LAYER_SOLID);
  const lookFrame = new InkLine([v3(-LW / 2, -LH / 2), v3(LW / 2, -LH / 2), v3(LW / 2, LH / 2), v3(-LW / 2, LH / 2)], { closed: true, width: 1.4, progress: 0 });
  lookG.add(lookPlate, lookFrame.object, ...lookTexts);
  onTop(lookG);
  const sayT = lookTexts[lookTexts.length - 1];
  let sayLast = ' ';

  // ---------- update ----------
  const tmp = new THREE.Vector3();
  const qCur = { q: qHome, grip: 0 };
  function robotAt() {
    if (S.finale > 0) return fin.at(S.finale * fin.total);
    if (S.cycle2 > 0) return cyc2.at(S.cycle2 * cyc2.total);
    if (S.unboard > 0) return back.at(S.unboard * back.total);
    if (S.game2 > 0) return game2.at(S.game2 * game2.total);
    if (S.game1 > 0) return game1.at(S.game1 * game1.total);
    if (S.sim > 0) return sim.at(S.sim * sim.total);
    if (S.demo > 0) return demo.at(S.demo * demo.total);
    if (S.ik > 0) return toPre.at(S.ik * toPre.total);
    return cyc1.at(S.cycle1 * cyc1.total);
  }
  function partPose(m, holder, t, ev, rel, places, rest) {
    // ev: Greif-/Ablegezeiten in Reihenfolge; places: Lage nach jedem Ablegen
    let held = false;
    let pose = rest;
    let k = 0;
    for (const e of ev) {
      if (t < e.t) break;
      if (e.grip === 1) held = true;
      else {
        held = false;
        pose = places[k++];
      }
    }
    if (held) m.copy(holder).multiply(rel);
    else m.copy(pose);
    return held;
  }

  function update() {
    // 1.1
    planLines.forEach((l, i) => {
      l.progress = clamp01(S.plan * planLines.length * 0.35 - i * 0.3);
      l.opacity = 1 - 0.75 * S.extrude;
    });
    planTexts.forEach((t) => (t.opacity = clamp01(S.plan * 2 - 1) * (1 - S.extrude)));
    const free45 = 1 - S.ghost * (1 - clamp01(S.cycle2 * 20)); // 4.5 braucht den Platz des Schriftfelds
    const ti = clamp01(S.title * 1.5) * (1 - S.outro) * free45;
    title.opacity = ti;
    sub.opacity = clamp01(S.title * 1.5 - 0.3) * (1 - S.outro) * free45;
    fbLines.forEach((l) => (l.progress = clamp01(S.title * 1.6 - 0.4) * free45));
    fbTexts.forEach((t) => (t.opacity = clamp01(S.title * 2 - 1) * free45));
    thanks.opacity = S.outro;

    // 1.2: Körper wachsen von unten (Schnittebene), Roboter gleich mit
    cell.visible = S.extrude > 0;
    scene.userData.clip = S.extrude > 0 && S.extrude < 1 ? [clipPlane] : [];
    clipPlane.constant = S.extrude * 1.25 * U;
    callouts.forEach((c, i) => c.set(clamp01(S.balloons * 1.6 - i * 0.08) * (1 - S.partShow)));

    // Roboter
    const r = robotAt();
    lara.setJoints(r.q);
    setGrip(r.grip);
    lara.fk(r.q, tcpNow);

    // Bauteile
    const tA = S.cycle1 * cyc1.total;
    partPose(partA.matrix, tcpNow, S.cycle1 > 0 ? tA : -1, ev1, relA, [fixA, binA], tablePose(shotA));
    if (S.cycle1 === 0 && S.spin > 0) {
      // 1.3: anheben, einmal drehen, wieder ablegen
      const lift = Math.sin(Math.min(1, S.spin) * Math.PI) * 0.06;
      partA.matrix.copy(tablePose(shotA)).multiply(new THREE.Matrix4().makeTranslation(0, 0, lift)).multiply(new THREE.Matrix4().makeRotationZ(S.spin * Math.PI * 2));
    }
    partA.matrixWorldNeedsUpdate = true;
    const restB = tablePose(shotB);
    if (S.cycle2 > 0) partPose(partB.matrix, tcpNow, S.cycle2 * cyc2.total, [{ t: -1, grip: 1 }, ...ev2], relB, [fixB, binB], restB);
    else partPose(partB.matrix, tcpNow, S.demo > 0 ? S.demo * demo.total : -1, evDemo, relB, [], restB);
    // 7.4: Teil B verschwindet mit dem Spielfeld aus dem Greifer, zu Beginn von 7.5 wächst es zurück
    const kB = clamp01(1 - S.game + S.unboard);
    if (kB < 1) partB.matrix.multiply(new THREE.Matrix4().makeScale(Math.max(kB, 0.001), Math.max(kB, 0.001), Math.max(kB, 0.001)));
    partB.matrixWorldNeedsUpdate = true;
    partB.visible = S.partB > 0 && kB > 0.001;

    // 7.4 Spielfeld, Figuren, Würfel
    const kG = S.game * (1 - S.unboard);
    gameBoard.visible = kG > 0.001;
    gameBoard.material.opacity = clamp01(kG * 2);
    gameBoard.scale.setScalar(0.85 + 0.15 * clamp01(kG * 1.5));
    const tGame = { game1: S.game1 > 0 ? S.game1 * game1.total : -1, game2: S.game2 > 0 ? S.game2 * game2.total : -1 };
    pawns.forEach((pw, i) => {
      let m = pw.rest;
      for (const mv of MOVES) {
        if (mv.pw !== pw || tGame[mv.pl] < mv.t0) continue;
        m = tGame[mv.pl] < mv.t1 ? tcpNow.clone().multiply(mv.rel) : pawnAt(mv.to);
      }
      const kp = clamp01(kG * 2.5 - 0.5 - i * 0.04);
      pw.m.visible = kp > 0.001;
      pw.m.matrix.copy(m).multiply(new THREE.Matrix4().makeScale(1, 1, Math.max(kp, 0.001)));
      pw.m.matrixWorldNeedsUpdate = true;
    });
    die.visible = kG > 0.001;
    die.scale.setScalar(Math.max(clamp01(kG * 2 - 0.6), 0.001));
    const roll = S.game2 > 0 ? tGame.game2 : S.game1 > 0 ? tGame.game1 : -1;
    const tumble = roll >= 0 ? 1 - clamp01(roll / 0.9) : 0;
    die.rotation.set(tumble * 4 * Math.PI, tumble * 3 * Math.PI, 0);
    die.position.z = (TZ + 13 + Math.sin(tumble * Math.PI) * 40) / 1000;
    const pips = S.game2 > 0 ? 3 : S.game1 > 0 ? 6 : 1;
    if (dieMats[4].map !== pipTex[pips]) {
      dieMats[4].map = pipTex[pips];
      dieMats[4].needsUpdate = true;
    }
    const say = S.game2 > 0 ? (S.game2 < kickAt ? 'Würfel 3: Blau wird geschlagen' : 'Blau zurück ins Haus, LARA zieht') : S.game1 > 0 ? 'Würfel 6: raus aufs Startfeld' : ' ';
    if (say !== sayLast) {
      sayT.text = say;
      sayLast = say;
    }
    const ov = clamp01(S.game * 3) * (1 - S.unboard);
    lookG.visible = ov > 0.001;
    if (lookG.visible) screenCard(lookG, LH, 0.46, -0.87 + (0.46 * LW) / LH / 2);
    lookPlate.material.opacity = ov;
    lookFrame.progress = ov;
    lookTexts.forEach((t, i) => (t.opacity = clamp01(S.game * 3 - 0.4 - i * 0.12) * (1 - S.unboard)));
    sayT.opacity = roll >= 0 ? clamp01(roll * 2 - 0.8) * (1 - S.unboard) : 0;
    // 7.5: Schild wächst mit dem ersten Takt aus dem Halter, dann greift LARA es und hält es in die Kamera
    const grow = clamp01(S.finale / 0.05);
    sign.visible = signStand.visible = grow > 0;
    partPose(sign.matrix, tcpNow, S.finale > 0 ? S.finale * fin.total : -1, evFin, signRel, [], signRest);
    if (grow < 1) sign.matrix.multiply(new THREE.Matrix4().makeTranslation(0, 0, -(1 - grow) * SG.h)).multiply(new THREE.Matrix4().makeScale(1, 1, Math.max(0.01, grow)));
    sign.matrixWorldNeedsUpdate = true;
    signStand.position.set(standC[0] / 1000, standC[1] / 1000, (TZ + 10) / 1000);
    signStand.rotation.z = Math.atan2(signRest.elements[1], signRest.elements[0]) - Math.PI / 2; // lange Seite entlang der Schildbreite
    signStand.scale.z = Math.max(0.01, grow);

    // 1.3
    partNotes.forEach((n, i) => n.set(clamp01(S.partNotes * 1.6 - i * 0.15) * clamp01(1 - S.cycle1 * 4)));
    dimText.opacity = clamp01(S.partNotes * 2 - 1) * (1 - clamp01(S.cycle1 * 4));

    // Zustand
    const showState = S.cycle1 > 0 && S.cycle1 < 1 ? 1 : S.cycle2 > 0 && S.cycle2 < 1 ? 1 : 0;
    const st = S.cycle2 > 0 ? cyc2.at(S.cycle2 * cyc2.total).state : r.state;
    const label = S.cycle2 > 0 && st === 'INSPECT' ? 'INSPECT · SCHLECHT' : S.cycle1 > 0 && st === 'INSPECT' ? 'INSPECT · GUT' : st ?? '';
    if (label !== lastState) {
      stateVal.text = label;
      lastState = label;
    }
    stateKey.opacity = stateVal.opacity = showState;
    stateVal.color = color(label.includes('SCHLECHT') ? T.signal : label.includes('GUT') ? T.good : T.ink).getHex();
    stateG.position.copy(W(-150, -560, 0)).setZ(0.5);
    const good = S.cycle1 * cyc1.total > ev1[ev1.length - 1].t ? 1 : 0;
    const bad = S.cycle2 > 0 && S.cycle2 * cyc2.total > ev2[ev2.length - 1].t ? 1 : 0;
    binCount[0].text = good ? 'GUT 1' : 'GUT 0';
    binCount[1].text = bad ? 'SCHLECHT 1' : 'SCHLECHT 0';
    const present = clamp01(S.finale * 10); // Finale: Zähler aus dem Bild
    binCount.forEach((t) => (t.opacity = (clamp01(S.cycle1 * 6) * (1 - clamp01(S.joints * 4)) + clamp01(S.cycle2 * 6)) * (1 - present)));

    // 4.1
    const tmpM = new THREE.Matrix4();
    lara.object.updateMatrixWorld(true);
    lara.pivots.forEach((p, i) => {
      p.g.getWorldPosition(tmp);
      const toCam = ctx.stage.camera.position.clone().sub(tmp).normalize();
      const right = new THREE.Vector3(1, 0, 0).applyQuaternion(ctx.stage.camera.quaternion);
      // Gelenke 1/2 und 3/4 haben in der URDF denselben Ursprung → nebeneinander zeigen
      jointBalloons[i].object.position.copy(tmp).addScaledVector(toCam, 1.3).addScaledVector(right, i % 2 === 0 ? -0.3 : 0.3);
      // 4.2 Schritt 2: Positionsnummern wieder da, daneben der laufende Gelenkwinkel
      const ikV = clamp01(S.ik * 6 - i * 0.3) * (1 - S.gpOff);
      jointBalloons[i].appear = Math.max(clamp01(S.joints * 1.6 - i * 0.1) * (1 - S.partB), ikV);
      const qt = qTexts[i];
      qt.g.position.copy(jointBalloons[i].object.position).addScaledVector(right, i % 2 === 0 ? -0.52 : 0.6);
      const qs = `${f1(r.q[i] / DEG, 0)}°`;
      if (qs !== qt.last) {
        qt.t.text = qs;
        qt.last = qs;
      }
      qt.t.opacity = ikV;
    });
    const flangeP = new THREE.Vector3().setFromMatrixPosition(lara.fk(r.q, tmpM, 0)).multiplyScalar(U);
    const tcpP = new THREE.Vector3().setFromMatrixPosition(tcpNow).multiplyScalar(U);
    const side = v3(1.0, -0.5, 0);
    setPts(tcpDimLine, [flangeP.clone().add(side), tcpP.clone().add(side)]);
    tcpDimLine.progress = clamp01(S.joints * 2 - 0.6) * (1 - S.partB);
    tcpDimG.position.copy(flangeP.clone().lerp(tcpP, 0.5).add(side).add(v3(0.15, 0, 0)));
    tcpDimText.opacity = clamp01(S.joints * 2 - 1) * (1 - S.partB);
    tcpDimSub.opacity = tcpDimText.opacity;

    // 4.2 Codekarte und Winkelskizze (mit der Greifsequenz wieder weg)
    const k42 = 1 - S.gpOff;
    const cv = clamp01(S.gp * 3) * k42;
    codeG.visible = cv > 0.001;
    if (codeG.visible) screenCard(codeG, CDH, CARD_FRAC, CARD_SIDE);
    codePlate.material.opacity = cv;
    codeFrame.progress = cv;
    const codeV = (step, k) => (step ? clamp01(S.ik * 8 - k * 0.6) : clamp01(S.gp * 2 - 0.3 - k * 0.12)) * k42;
    CODE.forEach(({ t, step, k }) => (t.opacity = codeV(step, k)));
    seps.forEach(({ l, step, k }) => (l.progress = codeV(step, k)));
    const kSk = k42 * (1 - clamp01(S.ik * 3)); // Skizze weicht der Fahrt
    skLines.forEach((l, i) => (l.progress = clamp01(S.gp * 2.2 - 0.2 - i * 0.25) * kSk));
    skTexts.forEach((t, i) => (t.opacity = clamp01(S.gp * 2.5 - 0.8 - i * 0.2) * kSk));

    // 4.3
    const sp = clamp01(S.ruler); // 4.4 blendet sie gleich zu Beginn aus
    speedG.visible = sp > 0.001;
    if (speedG.visible) screenCard(speedG, SCH, 0.5, 0.56);
    speedPlate.material.opacity = clamp01(sp * 3) * 0.95;
    speedFrame.progress = clamp01(sp * 2);
    speedTitle.opacity = clamp01(sp * 2 - 0.6);
    speedLines.forEach((l, i) => (l.progress = clamp01(sp * 2 - 0.6 - (i < 2 ? i * 0.3 : 0.4))));
    speedTexts.forEach((t, i) => (t.opacity = clamp01(sp * 3 - 1.6 - i * 0.05)));
    // Punkt folgt dem TCP (nur während der Greifsequenz an Teil B, sonst ausgeblendet)
    const hMm = (tcpP.z / U) * 1000 - gPB[2];
    const dotOn = S.ruler > 0 && S.cycle2 === 0 ? clamp01(sp * 2 - 1) : 0;
    speedDot.position.set(AXX, yOf(Math.max(0, hMm)), 0.014);
    speedDotLine.object.position.y = speedDot.position.y;
    speedDot.material.opacity = dotOn;
    speedDot.visible = dotOn > 0.01;
    speedDotLine.progress = dotOn;

    // 4.3
    angLines.forEach((l, i) => (l.progress = clamp01(S.angle * 2 - i * 0.15) * (1 - S.limits)));
    jawLines.forEach((l) => (l.progress = clamp01(S.angle * 2 - 0.8) * (1 - S.limits)));
    jawAxisLine.progress = clamp01(S.angle * 2 - 0.9) * (1 - S.limits);
    angTexts.forEach((t, i) => (t.opacity = clamp01(S.angle * 2 - 1 - i * 0.2) * (1 - S.limits)));
    formula.opacity = clamp01(S.angle * 2 - 1.2) * (1 - S.limits);

    // 4.4 (blendet mit 4.5 bzw. 7.5 aus)
    const k44 = 1 - Math.max(S.cycle2, S.ghost);
    limitLines.forEach((l) => (l.progress = S.limits * k44));
    limitText.opacity = clamp01(S.limits * 2 - 1) * k44;
    crossLines.forEach((l) => (l.progress = clamp01(S.outside * 2) * k44));
    outText.opacity = clamp01(S.outside * 2 - 0.6) * k44;
    stopText.opacity = clamp01(S.outside * 2 - 1) * k44;

    // 4.5: Schatten springt beim Aufruf ans Ziel des Abschnitts; mit 7.5 wieder weg
    const k45 = S.ghost * (1 - clamp01(S.cycle2 * 20)) * (1 - S.game);
    ghost.object.visible = k45 > 0.5;
    if (ghost.object.visible) {
      const ts = S.sim * sim.total;
      const seg = sim.segs.find((sg) => ts < sg.t0 + sg.dur) ?? sim.segs[sim.segs.length - 1];
      ghost.setJoints(S.sim > 0 && ts >= seg.t0 ? seg.q1 : sim.segs[0].q0);
    }
    simLabels.forEach((t, i) => (t.opacity = clamp01(k45 * 2.5 - (i >> 1) * 0.4)));
    simArrows.forEach((l) => (l.progress = clamp01(k45 * 2 - 0.4)));
    const ts45 = S.sim * sim.total;
    callHead.opacity = clamp01(k45 * 2 - 0.8);
    callLines.forEach((t, i) => (t.opacity = S.sim > 0 && ts45 >= callAt[i] ? k45 : 0));
    testsText.opacity = clamp01(k45 * 2 - 1);

    // Beschriftungen zur Kamera drehen, Schilder folgen der Deckkraft ihres Textes
    const cq = ctx.stage.camera.quaternion;
    billboards.forEach((o) => o.quaternion.copy(cq));
    plates.forEach(({ t, plate }) => {
      plate.material.opacity = t.opacity * 0.9;
      plate.visible = t.visible && t.opacity > 0.01 && plate.scale.x > 0.001;
    });
  }
  return { scene, S, defaults: DEFAULTS, update };
}

// Zeiten des Bewegungsplans (beim Anlegen der Welt gesetzt, für Blitze und Tween-Dauer)
export const CELL = { T1: 18, T2: 14, TD: 6, TP: 2.4, TS: 7, FIN: 10, G1: 8, G2: 16, BACK: 1.6, flash1: [], flash2: [] };

// ---------- Kameras ----------
const cam = (lx, ly, lz, px, py, pz, fov = 30) => ({ lx, ly, lz, px, py, pz, fov });
const C = {
  plan: cam(0.4, 0.1, 0, 0.4, 0.09, 22),
  cell: cam(2.6, 0.2, 2.2, 1.0, -21.5, 13.5),
  part: (ctx) => {
    const s = ctx.data.m1.shots[0].robot;
    return cam(s.x / 100, s.y / 100, 0.15, s.x / 100 + 1.2, s.y / 100 - 5.2, 3.3, 30);
  },
  robot: cam(1.8, 0.0, 4.4, -2.5, -18, 9.5),
  gp: (ctx) => {
    const s = ctx.data.m1.shots[4].robot;
    return cam(s.x / 100 - 2.3, s.y / 100 + 0.1, 0.4, s.x / 100 - 1.7, s.y / 100 - 6.2, 9.8, 30);
  },
  ik: cam(-1.2, -0.8, 3.4, 0.2, -17.5, 9.5),
  seq: (ctx) => {
    const s = ctx.data.m1.shots[4].robot;
    return cam(s.x / 100 + 0.8, s.y / 100 - 0.6, 1.0, s.x / 100 + 2.6, s.y / 100 - 9.5, 4.6, 30);
  },
  angle: cam(12.2, -0.6, 0, 12.2, -0.61, 13.5),
  limits: cam(3.4, 0, 2.8, 4.5, -30, 20),
  sim: cam(-7.5, 0, 5.2, -6.5, -32, 11),
  game: cam(2.75, -1.25, 0.4, 3.3, -8.0, 10.5),
  audience: (() => {
    const [cx, cy, cz] = SIGN.show;
    const [ax, ay, az] = SIGN.audience;
    return cam(cx / 100 - 0.2, cy / 100 + 3.2, cz / 100 - 0.6, ax / 100, ay / 100, az / 100, 30); // Schild unten, Zelle dahinter
  })(),
};

const to = (tl, S, vars, pos = 0) => tl.to(S, { ease: EASE.appear, ...vars }, pos);
const flashAt = (tl, ctx, t) => {
  tl.to(ctx.stage.flash, { v: 0.75, duration: 0.06, ease: 'none' }, t);
  tl.to(ctx.stage.flash, { v: 0, duration: 0.6, ease: 'power2.out' }, t + 0.06);
};

export const CELL_SCENES = [
  {
    id: '1.1', world: 'cell',
    steps: [
      (tl, S) => {
        to(tl, S, { plan: 1, duration: 3.0, ease: 'power1.inOut' }, 0.1);
        to(tl, S, { title: 1, duration: 1.6, ease: 'power2.out' }, 1.6);
      },
    ],
    cams: [C.plan],
  },
  {
    id: '1.2', world: 'cell',
    steps: [
      (tl, S) => to(tl, S, { extrude: 1, duration: 3.2, ease: 'power1.inOut' }, 0.6),
      (tl, S) => to(tl, S, { balloons: 1, duration: 2.0, ease: 'power1.out' }, 0),
    ],
    cams: [C.cell, C.cell],
  },
  {
    id: '1.3', world: 'cell',
    steps: [
      (tl, S) => to(tl, S, { partShow: 1, spin: 1, duration: 4.0, ease: 'power1.inOut' }, 0.8),
      (tl, S) => to(tl, S, { partNotes: 1, duration: 1.6, ease: 'power1.out' }, 0),
    ],
    cams: [C.part, C.part],
  },
  {
    id: '1.4', world: 'cell',
    steps: [
      (tl, S, ctx) => {
        tl.to(S, { cycle1: 1, duration: CELL.T1, ease: 'none' }, 0.6);
        CELL.flash1.forEach((f) => flashAt(tl, ctx, 0.6 + f * CELL.T1));
      },
    ],
    cams: [C.cell],
  },
  {
    id: '4.1', world: 'cell',
    steps: [(tl, S) => to(tl, S, { joints: 1, duration: 2.0, ease: 'power1.out' }, 0.6)],
    cams: [C.robot],
  },
  {
    id: '4.2', world: 'cell',
    steps: [
      (tl, S) => {
        to(tl, S, { partB: 1, duration: 0.6 }, 0.2);
        to(tl, S, { gp: 1, duration: 2.6, ease: 'power1.inOut' }, 0.6);
      },
      (tl, S) => tl.to(S, { ik: 1, duration: CELL.TP, ease: 'none' }, 0.3),
    ],
    cams: [C.gp, C.ik],
  },
  {
    id: '4.3', world: 'cell',
    steps: [
      (tl, S) => {
        to(tl, S, { gpOff: 1, duration: 0.5 }, 0);
        to(tl, S, { ruler: 1, duration: 1.2, ease: 'power1.out' }, 0.6);
      },
      (tl, S) => tl.to(S, { demo: 1, duration: CELL.TD * 1.5, ease: 'none' }, 0),
    ],
    cams: [C.seq, C.seq],
  },
  {
    id: '4.4', world: 'cell',
    steps: [
      (tl, S) => {
        to(tl, S, { ruler: 0, duration: 0.4, ease: 'power1.in' }, 0);
        to(tl, S, { angle: 1, duration: 2.4, ease: 'power1.inOut' }, 0.4);
      },
    ],
    cams: [C.angle],
  },
  {
    id: '4.5', world: 'cell',
    steps: [
      (tl, S) => to(tl, S, { limits: 1, duration: 2.0, ease: 'power1.inOut' }, 0.4),
      (tl, S) => to(tl, S, { outside: 1, duration: 1.2, ease: 'power1.out' }, 0),
    ],
    cams: [C.limits, C.limits],
  },
  {
    id: '4.6', world: 'cell',
    steps: [
      (tl, S) => to(tl, S, { ghost: 1, duration: 1.8, ease: 'power1.out' }, 0.6),
      (tl, S) => tl.to(S, { sim: 1, duration: CELL.TS, ease: 'none' }, 0),
    ],
    cams: [C.sim, C.sim],
  },
  {
    id: '7.4', world: 'cell',
    steps: [
      (tl, S) => to(tl, S, { game: 1, duration: 2.4, ease: 'power1.inOut' }, 0.2),
      (tl, S) => tl.to(S, { game1: 1, duration: CELL.G1, ease: 'none' }, 0.3),
      (tl, S) => tl.to(S, { game2: 1, duration: CELL.G2, ease: 'none' }, 0.3),
    ],
    cams: [C.game, C.game, C.game],
  },
  {
    id: '7.5', world: 'cell',
    steps: [
      (tl, S, ctx) => {
        // Rückbau aus 7.4: Spielfeld weg, Teil B zurück in den Greifer, dann der Schlechtfall
        tl.to(S, { unboard: 1, duration: CELL.BACK, ease: 'none' }, 0.2);
        const t0 = 0.5 + CELL.BACK;
        tl.to(S, { cycle2: 1, duration: CELL.T2, ease: 'none' }, t0);
        CELL.flash2.forEach((f) => flashAt(tl, ctx, t0 + f * CELL.T2));
      },
      (tl, S) => {
        to(tl, S, { outro: 1, duration: 1.4, ease: 'power2.out' }, 0);
        tl.to(S, { finale: 1, duration: CELL.FIN, ease: 'none' }, 1.2); // erst wenn die Kamera steht
      },
    ],
    cams: [C.cell, C.audience],
  },
];
