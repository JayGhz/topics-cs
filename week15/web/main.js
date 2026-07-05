import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// ---------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------
const STATUS_COLOR = {
  normal: 0x4ea8ff,
  panic: 0xffb454,
  trapped: 0xb23bff,
  casualty: 0x55596b,
  evacuated: 0x33d17a,
};
const MAX_AGENTS = 220;
const MAX_FIRE = 500;
const MAX_SMOKE = 400;
const WALL_HEIGHT = 2.6;
const WALL_THICK = 0.18;
const FIRE_LERP = 0.18;
const SMOKE_LERP = 0.08;
const FLOOR_LERP_RATE = 2.2; // qué tan rápido "sube/baja" visualmente un agente entre pisos

let WIDTH = 30, HEIGHT = 18, cellSize = 0.4, floorHeightThree = 3.2;

// ---------------------------------------------------------------------
// Escena base
// ---------------------------------------------------------------------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070c);
scene.fog = new THREE.FogExp2(0x05070c, 0.011);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 200);
// un poco más lejos y menos corrido que antes, para que el edificio entre
// completo en el encuadre sin pegarse al borde derecho
camera.position.set(2, 30, 40);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 4;
controls.maxDistance = 65;
controls.target.set(-6, 2, 0);

scene.add(new THREE.HemisphereLight(0x8fa6c9, 0x1a1410, 0.6));
const sun = new THREE.DirectionalLight(0xfff2df, 0.85);
sun.position.set(20, 34, 14);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -25; sun.shadow.camera.right = 25;
sun.shadow.camera.top = 20; sun.shadow.camera.bottom = -20;
scene.add(sun);
scene.add(new THREE.AmbientLight(0x40506a, 0.38));

const fireLights = [];
for (let i = 0; i < 4; i++) {
  const l = new THREE.PointLight(0xff6a1f, 0, 9, 2);
  l.position.set(0, 1.4, 0);
  scene.add(l);
  fireLights.push(l);
}

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.6, 0.45, 0.2);
composer.addPass(bloom);
composer.addPass(new OutputPass());

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

// ---------------------------------------------------------------------
// Helpers de coordenadas, etiquetas y primitivas de mobiliario
// ---------------------------------------------------------------------
function toScene(x, y) {
  return [x - WIDTH / 2, y - HEIGHT / 2];
}

function labelSprite(text, color = '#f2f4f8') {
  const el = document.createElement('canvas');
  el.width = 256; el.height = 64;
  const ctx = el.getContext('2d');
  ctx.font = '600 28px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 6;
  ctx.strokeStyle = 'rgba(5, 7, 12, 0.85)';
  ctx.strokeText(text, 128, 32);
  ctx.fillStyle = color;
  ctx.fillText(text, 128, 32);
  const tex = new THREE.CanvasTexture(el);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthWrite: false, transparent: true }));
  sprite.scale.set(4, 1, 1);
  return sprite;
}

function shadowed(group) {
  group.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return group;
}

function boxMesh(w, h, d, color, roughness = 0.85) {
  return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshStandardMaterial({ color, roughness }));
}

function potPlant() {
  const g = new THREE.Group();
  const pot = boxMesh(0.3, 0.26, 0.3, 0x4a3728, 0.95);
  pot.position.y = 0.13;
  const foliage = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.32, 1),
    new THREE.MeshStandardMaterial({ color: 0x2f6b3a, roughness: 0.95, flatShading: true })
  );
  foliage.position.y = 0.5;
  g.add(pot, foliage);
  return shadowed(g);
}

function deskChair() {
  const g = new THREE.Group();
  const top = boxMesh(1.1, 0.05, 0.55, 0x30271c, 0.7);
  top.position.y = 0.72;
  g.add(top);
  [[-0.5, -0.24], [0.5, -0.24], [-0.5, 0.24], [0.5, 0.24]].forEach(([lx, lz]) => {
    const leg = boxMesh(0.05, 0.72, 0.05, 0x1c1712, 0.7);
    leg.position.set(lx, 0.36, lz);
    g.add(leg);
  });
  const seat = boxMesh(0.42, 0.06, 0.42, 0x2c3550, 0.8);
  seat.position.set(0, 0.44, 0.62);
  const back = boxMesh(0.42, 0.42, 0.06, 0x2c3550, 0.8);
  back.position.set(0, 0.68, 0.81);
  g.add(seat, back);
  return shadowed(g);
}

function meetingTable(length) {
  const g = new THREE.Group();
  const top = boxMesh(length, 0.06, 1.2, 0x2a3446, 0.6);
  top.position.y = 0.74;
  g.add(top);
  [-length / 2 + 0.3, length / 2 - 0.3].forEach((lx) => {
    [-0.5, 0.5].forEach((lz) => {
      const leg = boxMesh(0.08, 0.74, 0.08, 0x1c2230, 0.7);
      leg.position.set(lx, 0.37, lz);
      g.add(leg);
    });
  });
  const chairCount = Math.max(2, Math.floor(length / 0.9));
  for (let i = 0; i < chairCount; i++) {
    const cx = -length / 2 + 0.5 + i * ((length - 1.0) / Math.max(1, chairCount - 1));
    [1, -1].forEach((side) => {
      const chair = boxMesh(0.38, 0.38, 0.38, 0x394564, 0.8);
      chair.position.set(cx, 0.19, side * 0.78);
      g.add(chair);
    });
  }
  return shadowed(g);
}

function kitchenIsland() {
  const g = new THREE.Group();
  const island = boxMesh(1.6, 0.9, 0.8, 0x394050, 0.5);
  island.position.y = 0.45;
  g.add(island);
  [-0.9, 0.9].forEach((sx) => {
    const stool = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.18, 0.5, 12),
      new THREE.MeshStandardMaterial({ color: 0x27303f, roughness: 0.7 })
    );
    stool.position.set(sx, 0.25, 0.7);
    g.add(stool);
  });
  return shadowed(g);
}

function loungeSofas() {
  const g = new THREE.Group();
  const table = boxMesh(0.9, 0.32, 0.5, 0x2a2016, 0.6);
  table.position.y = 0.16;
  g.add(table);
  [[-1.0, 0], [1.0, 0], [0, -0.85]].forEach(([sx, sz]) => {
    const sofa = boxMesh(0.85, 0.4, 0.55, 0x33455c, 0.9);
    sofa.position.set(sx, 0.2, sz);
    g.add(sofa);
  });
  return shadowed(g);
}

function furnishRoom(kind, x0, y0, x1, y1, floorY, target) {
  const w = x1 - x0, d = y1 - y0;
  const cx = x0 + w / 2, cy = y0 + d / 2;

  const place = (piece, fx, fy, rotY = 0) => {
    const [sx, sz] = toScene(fx, fy);
    piece.position.x += sx;
    piece.position.z += sz;
    piece.position.y += floorY;
    piece.rotation.y += rotY;
    target.add(piece);
  };

  switch (kind) {
    case 'office': {
      const cols = w >= d ? 3 : 2;
      const rows = w >= d ? 2 : 3;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const fx = x0 + (w * (c + 0.5)) / cols;
          const fy = y0 + (d * (r + 0.5)) / rows;
          place(deskChair(), fx, fy, r % 2 === 0 ? Math.PI : 0);
        }
      }
      break;
    }
    case 'meeting':
      place(meetingTable(Math.min(w, d) * 0.65), cx, cy, w >= d ? 0 : Math.PI / 2);
      place(potPlant(), x0 + 0.6, y0 + 0.6);
      place(potPlant(), x1 - 0.6, y1 - 0.6);
      break;
    case 'kitchen':
      place(kitchenIsland(), cx, cy, w >= d ? 0 : Math.PI / 2);
      place(potPlant(), x0 + 0.6, y1 - 0.6);
      break;
    case 'lounge':
      place(loungeSofas(), cx, cy);
      place(potPlant(), x0 + 0.6, y0 + 0.6);
      place(potPlant(), x1 - 0.6, y0 + 0.6);
      break;
    case 'plants':
    default: {
      const area = w * d;
      const spots = area > 40
        ? [[0.18, 0.25], [0.82, 0.25], [0.18, 0.75], [0.82, 0.75]]
        : [[0.25, 0.25], [0.75, 0.75]];
      spots.forEach(([fx, fy]) => place(potPlant(), x0 + w * fx, y0 + d * fy));
      break;
    }
  }
}

function buildStaircase(sx, sz, rise) {
  const g = new THREE.Group();
  const steps = 12;
  const runDepth = 3.4;
  const stepDepth = runDepth / steps;
  const stepRise = rise / steps;
  const stepWidth = 1.6;
  const treadMat = new THREE.MeshStandardMaterial({ color: 0x3a4152, roughness: 0.75 });
  for (let i = 0; i < steps; i++) {
    const step = new THREE.Mesh(new THREE.BoxGeometry(stepWidth, 0.12, stepDepth), treadMat);
    step.position.set(0, i * stepRise + stepRise / 2, -runDepth / 2 + i * stepDepth + stepDepth / 2);
    g.add(step);
  }
  const railMat = new THREE.MeshStandardMaterial({ color: 0x8a92a6, roughness: 0.4, metalness: 0.3 });
  const railLen = Math.hypot(runDepth, rise);
  const angle = Math.atan2(rise, runDepth);
  [-1, 1].forEach((side) => {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.85, railLen), railMat);
    rail.position.set(side * stepWidth / 2, rise / 2, 0);
    rail.rotation.x = -angle;
    g.add(rail);
  });
  g.position.set(sx, 0, sz);
  return shadowed(g);
}

// ---------------------------------------------------------------------
// Construcción del edificio (2 pisos) a partir del mensaje "floorplan"
// ---------------------------------------------------------------------
const buildingGroup = new THREE.Group();
scene.add(buildingGroup);

const WALL_COLOR = 0xcfd6e6;
// tintes de sala: variaciones claras del mismo tono de las paredes/piso,
// solo para diferenciar el tipo de sala sin romper la paleta del edificio.
const KIND_COLOR = {
  office: 0xc7cfe1, kitchen: 0xe0c6bd, lounge: 0xd5cade, meeting: 0xc2d1e1, plants: 0xc9d6c9,
};

const SILL_H = 0.15;   // zócalo sólido bajo la ventana
const LINTEL_H = 0.35; // dintel sólido sobre la ventana
const GLASS_H = WALL_HEIGHT - SILL_H - LINTEL_H;

const wallMat = new THREE.MeshStandardMaterial({ color: WALL_COLOR, roughness: 0.8 });
const glassMat = new THREE.MeshStandardMaterial({
  color: 0xbfe0ff, transparent: true, opacity: 0.2, roughness: 0.15, side: THREE.DoubleSide,
});

function buildWallSegment(x1, y1, x2, y2, floorY, target) {
  const [sx1, sz1] = toScene(x1, y1);
  const [sx2, sz2] = toScene(x2, y2);
  const dx = sx2 - sx1, dz = sz2 - sz1;
  const length = Math.hypot(dx, dz);
  if (length < 0.05) return;
  const rotY = -Math.atan2(dz, dx);
  const cx = (sx1 + sx2) / 2, cz = (sz1 + sz2) / 2;

  const sill = new THREE.Mesh(new THREE.BoxGeometry(length, SILL_H, WALL_THICK), wallMat);
  sill.position.set(cx, floorY + SILL_H / 2, cz);
  sill.rotation.y = rotY;
  sill.castShadow = true; sill.receiveShadow = true;
  target.add(sill);

  const lintel = new THREE.Mesh(new THREE.BoxGeometry(length, LINTEL_H, WALL_THICK), wallMat);
  lintel.position.set(cx, floorY + WALL_HEIGHT - LINTEL_H / 2, cz);
  lintel.rotation.y = rotY;
  lintel.castShadow = true; lintel.receiveShadow = true;
  target.add(lintel);

  // banda acristalada: deja ver a los agentes dentro de cada sala
  const glass = new THREE.Mesh(new THREE.BoxGeometry(length, GLASS_H, WALL_THICK * 0.55), glassMat);
  glass.position.set(cx, floorY + SILL_H + GLASS_H / 2, cz);
  glass.rotation.y = rotY;
  target.add(glass);
}

function holedPlane(w, d, holes) {
  // rectángulo con recortes rectangulares (para dejar ver la escalera
  // a través del piso de arriba). Coordenadas locales, antes de rotar
  // el plano a horizontal: world_offset = (local_x, -local_y).
  const shape = new THREE.Shape();
  shape.moveTo(-w / 2, -d / 2);
  shape.lineTo(w / 2, -d / 2);
  shape.lineTo(w / 2, d / 2);
  shape.lineTo(-w / 2, d / 2);
  shape.closePath();
  for (const h of holes) {
    const path = new THREE.Path();
    path.moveTo(h.lx - h.w / 2, h.ly - h.d / 2);
    path.lineTo(h.lx + h.w / 2, h.ly - h.d / 2);
    path.lineTo(h.lx + h.w / 2, h.ly + h.d / 2);
    path.lineTo(h.lx - h.w / 2, h.ly + h.d / 2);
    path.closePath();
    shape.holes.push(path);
  }
  return new THREE.ShapeGeometry(shape);
}

function buildFloorLevel(floorData, floorIndex, stairsXY) {
  const floorY = floorIndex * floorHeightThree;

  // en el piso de arriba, se recorta un hueco en la losa donde está cada
  // escalera, así se ve la estructura de la escalera y el piso de abajo.
  const stairHoles = floorIndex === 1
    ? stairsXY.map(([stx, sty]) => {
        const [ssx, ssz] = toScene(stx, sty);
        return { lx: ssx, ly: -ssz, w: 2.0, d: 3.6 };
      })
    : [];

  const slabGeo = stairHoles.length ? holedPlane(WIDTH, HEIGHT, stairHoles) : new THREE.PlaneGeometry(WIDTH, HEIGHT);
  const slab = new THREE.Mesh(slabGeo, new THREE.MeshStandardMaterial({ color: WALL_COLOR, roughness: 0.95 }));
  slab.rotation.x = -Math.PI / 2;
  slab.position.y = floorY;
  slab.receiveShadow = true;
  buildingGroup.add(slab);

  for (const [name, roomData] of Object.entries(floorData.rooms)) {
    const [x0, y0, x1, y1] = roomData.bounds;
    const w = x1 - x0, d = y1 - y0;
    const [cx, cz] = toScene(x0 + w / 2, y0 + d / 2);

    const roomHoles = stairHoles
      .filter((h) => {
        const wx = h.lx, wz = -h.ly;
        return wx > cx - w / 2 && wx < cx + w / 2 && wz > cz - d / 2 && wz < cz + d / 2;
      })
      .map((h) => ({ lx: h.lx - cx, ly: h.ly + cz, w: h.w, d: h.d }));

    const roomGeo = roomHoles.length
      ? holedPlane(w - 0.05, d - 0.05, roomHoles)
      : new THREE.PlaneGeometry(w - 0.05, d - 0.05);
    const mesh = new THREE.Mesh(
      roomGeo,
      new THREE.MeshStandardMaterial({ color: KIND_COLOR[roomData.kind] ?? WALL_COLOR, roughness: 0.9 })
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(cx, floorY + 0.005, cz);
    mesh.receiveShadow = true;
    buildingGroup.add(mesh);

    const label = labelSprite(name.replace(/_/g, ' '));
    label.position.set(cx, floorY + 3.0, cz);
    buildingGroup.add(label);

    furnishRoom(roomData.kind, x0, y0, x1, y1, floorY, buildingGroup);
  }

  for (const [x1, y1, x2, y2] of floorData.walls) {
    buildWallSegment(x1, y1, x2, y2, floorY, buildingGroup);
  }
}

function buildScene(fp) {
  WIDTH = fp.width; HEIGHT = fp.height; cellSize = fp.cell; floorHeightThree = fp.floor_height;

  while (buildingGroup.children.length) buildingGroup.remove(buildingGroup.children[0]);

  fp.floors.forEach((floorData, floorIndex) => buildFloorLevel(floorData, floorIndex, fp.stairs));

  for (const [ex, ey] of fp.exits) {
    const [sx, sz] = toScene(ex, ey);
    const pad = new THREE.Mesh(
      new THREE.CircleGeometry(1.1, 32),
      new THREE.MeshStandardMaterial({ color: 0x1d5c34, emissive: 0x2fbf6c, emissiveIntensity: 0.9, roughness: 0.5 })
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(sx, 0.01, sz);
    buildingGroup.add(pad);

    const exitLight = new THREE.PointLight(0x33d17a, 1.2, 6, 2);
    exitLight.position.set(sx, 1.6, sz);
    buildingGroup.add(exitLight);

    const label = labelSprite('SALIDA', '#33d17a');
    label.position.set(sx, 2.6, sz);
    buildingGroup.add(label);
  }

  for (const [stx, sty] of fp.stairs) {
    const [sx, sz] = toScene(stx, sty);
    buildingGroup.add(buildStaircase(sx, sz, floorHeightThree));
    const label = labelSprite('escalera', '#9aa4bd');
    label.position.set(sx, floorHeightThree + 1.2, sz);
    buildingGroup.add(label);
  }
}

// ---------------------------------------------------------------------
// Agentes (InstancedMesh de cápsulas)
// ---------------------------------------------------------------------
const agentGeo = new THREE.CapsuleGeometry(0.24, 0.55, 4, 8);
const agentMat = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0.05 });
const agentMesh = new THREE.InstancedMesh(agentGeo, agentMat, MAX_AGENTS);
agentMesh.castShadow = true;
agentMesh.count = 0;
scene.add(agentMesh);

const dummy = new THREE.Object3D();
const tmpColor = new THREE.Color();
const agentState = Array.from({ length: MAX_AGENTS }, () => ({
  x: 0, z: 0, curX: 0, curZ: 0, floor: 0, curFloorY: 0, status: 'evacuated', fade: 1, init: false,
}));
let agentCount = 0;

function updateAgents(dt) {
  const smoothing = 1 - Math.exp(-dt * 8);
  const floorSmoothing = 1 - Math.exp(-dt * FLOOR_LERP_RATE);
  for (let i = 0; i < agentCount; i++) {
    const st = agentState[i];
    if (!st.init) { st.curX = st.x; st.curZ = st.z; st.curFloorY = st.floor * floorHeightThree; st.init = true; }
    st.curX += (st.x - st.curX) * smoothing;
    st.curZ += (st.z - st.curZ) * smoothing;
    st.curFloorY += (st.floor * floorHeightThree - st.curFloorY) * floorSmoothing;

    if (st.status === 'evacuated') st.fade = Math.max(0, st.fade - dt * 1.2);
    else st.fade = Math.min(1, st.fade + dt * 4);

    let y = 0.5, rotX = 0, scale = st.fade;
    if (st.status === 'casualty') { y = 0.14; rotX = Math.PI / 2; scale = 1; }
    y += st.curFloorY;

    dummy.position.set(st.curX, y, st.curZ);
    dummy.rotation.set(rotX, 0, 0);
    dummy.scale.setScalar(Math.max(0.001, scale));
    dummy.updateMatrix();
    agentMesh.setMatrixAt(i, dummy.matrix);
    tmpColor.set(STATUS_COLOR[st.status] ?? STATUS_COLOR.normal);
    agentMesh.setColorAt(i, tmpColor);
  }
  agentMesh.count = agentCount;
  agentMesh.instanceMatrix.needsUpdate = true;
  if (agentMesh.instanceColor) agentMesh.instanceColor.needsUpdate = true;
}

// ---------------------------------------------------------------------
// Fuego y humo (InstancedMesh + interpolación por celda) — solo planta baja
// ---------------------------------------------------------------------
const fireGeo = new THREE.ConeGeometry(0.22, 0.6, 6);
fireGeo.translate(0, 0.3, 0);
const fireMat = new THREE.MeshStandardMaterial({
  color: 0xff5a1f, emissive: 0xff7a1f, emissiveIntensity: 1.6, roughness: 0.4,
  transparent: true, opacity: 0.92, blending: THREE.AdditiveBlending, depthWrite: false,
});
const fireMesh = new THREE.InstancedMesh(fireGeo, fireMat, MAX_FIRE);
fireMesh.count = 0;
scene.add(fireMesh);

const smokeGeo = new THREE.IcosahedronGeometry(0.35, 0);
const smokeMat = new THREE.MeshStandardMaterial({ color: 0x9099ad, transparent: true, opacity: 0.28, roughness: 1, depthWrite: false });
const smokeMesh = new THREE.InstancedMesh(smokeGeo, smokeMat, MAX_SMOKE);
smokeMesh.count = 0;
scene.add(smokeMesh);

const FIRE_LOW = new THREE.Color(0x4a0e02);
const FIRE_HIGH = new THREE.Color(0xffe37a);
const fireColor = new THREE.Color();

const fireCells = new Map();
const smokeCells = new Map();

function applySparse(list, map) {
  const touched = new Set();
  for (const [i, j, v] of list) {
    const key = i + ',' + j;
    touched.add(key);
    let e = map.get(key);
    if (!e) {
      const [sx, sz] = toScene((i + 0.5) * cellSize, (j + 0.5) * cellSize);
      e = { x: sx, z: sz, cur: 0, target: v, phase: Math.random() * Math.PI * 2 };
      map.set(key, e);
    } else {
      e.target = v;
    }
  }
  for (const [key, e] of map) {
    if (!touched.has(key)) e.target = 0;
  }
}

function updateFireSmoke() {
  const t = performance.now() * 0.001;

  let idx = 0;
  for (const [key, e] of fireCells) {
    e.cur += (e.target - e.cur) * FIRE_LERP;
    if (e.cur < 0.004 && e.target === 0) { fireCells.delete(key); continue; }
    if (idx < MAX_FIRE) {
      const scale = 0.35 + e.cur * 1.3;
      dummy.position.set(e.x, 0, e.z);
      dummy.rotation.set(0, e.phase + t * 0.6, 0);
      dummy.scale.set(scale, scale * (0.7 + e.cur * 0.6), scale);
      dummy.updateMatrix();
      fireMesh.setMatrixAt(idx, dummy.matrix);
      fireColor.copy(FIRE_LOW).lerp(FIRE_HIGH, Math.min(1, e.cur));
      fireMesh.setColorAt(idx, fireColor);
      idx++;
    }
  }
  fireMesh.count = idx;
  fireMesh.instanceMatrix.needsUpdate = true;
  if (fireMesh.instanceColor) fireMesh.instanceColor.needsUpdate = true;

  idx = 0;
  for (const [key, e] of smokeCells) {
    e.cur += (e.target - e.cur) * SMOKE_LERP;
    if (e.cur < 0.01 && e.target === 0) { smokeCells.delete(key); continue; }
    if (idx < MAX_SMOKE) {
      const rise = 1.3 + Math.sin(t + e.phase) * 0.15;
      const scale = 0.3 + e.cur * 0.9;
      dummy.position.set(e.x, rise, e.z);
      dummy.rotation.set(e.phase, t * 0.2 + e.phase, 0);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      smokeMesh.setMatrixAt(idx, dummy.matrix);
      idx++;
    }
  }
  smokeMesh.count = idx;
  smokeMesh.instanceMatrix.needsUpdate = true;
}

function updateFireLights() {
  let sx = 0, sz = 0, total = 0;
  for (const e of fireCells.values()) { sx += e.x * e.cur; sz += e.z * e.cur; total += e.cur; }
  if (total < 0.01) {
    fireLights.forEach((l) => { l.intensity = THREE.MathUtils.lerp(l.intensity, 0, 0.1); });
    return;
  }
  const cx = sx / total, cz = sz / total;
  const targetIntensity = Math.min(6, total * 0.35);
  fireLights.forEach((l, i) => {
    const ang = (i / fireLights.length) * Math.PI * 2;
    l.position.x = THREE.MathUtils.lerp(l.position.x, cx + Math.cos(ang) * 1.2, 0.1);
    l.position.z = THREE.MathUtils.lerp(l.position.z, cz + Math.sin(ang) * 1.2, 0.1);
    l.position.y = 1.4;
    const flicker = 0.75 + Math.random() * 0.5;
    l.intensity = THREE.MathUtils.lerp(l.intensity, targetIntensity * flicker, 0.3);
  });
}

// ---------------------------------------------------------------------
// Cámara: orbital / cenital / seguir agente
// ---------------------------------------------------------------------
let cameraMode = 'orbit';
const camButtons = { orbit: 'cam-orbit', top: 'cam-top', follow: 'cam-follow' };

function setCameraMode(mode) {
  cameraMode = mode;
  Object.entries(camButtons).forEach(([m, id]) => document.getElementById(id).classList.toggle('btn-active', m === mode));
  controls.enabled = mode === 'orbit';
  if (mode === 'top') {
    camera.position.set(0.01, 42, 0.01);
    camera.lookAt(0, 0, 0);
  }
}
document.getElementById('cam-orbit').onclick = () => setCameraMode('orbit');
document.getElementById('cam-top').onclick = () => setCameraMode('top');
document.getElementById('cam-follow').onclick = () => setCameraMode('follow');

function updateFollowCamera(dt) {
  let target = null;
  for (let i = 0; i < agentCount; i++) {
    const st = agentState[i];
    if (st.status === 'normal' || st.status === 'panic') { target = st; break; }
  }
  if (!target) return;
  const desired = new THREE.Vector3(target.curX + 2.2, 2.6 + target.curFloorY, target.curZ + 2.2);
  camera.position.lerp(desired, 1 - Math.exp(-dt * 2));
  camera.lookAt(target.curX, 0.6 + target.curFloorY, target.curZ);
}

// ---------------------------------------------------------------------
// HUD: estadísticas, gráfico y controles
// ---------------------------------------------------------------------
const statsEls = {
  elapsed: document.querySelector('[data-stat="elapsed"] b'),
  evacuated: document.querySelector('[data-stat="evacuated"] b'),
  active: document.querySelector('[data-stat="active"] b'),
  trapped: document.querySelector('[data-stat="trapped"] b'),
  casualties: document.querySelector('[data-stat="casualties"] b'),
};
const chartCanvas = document.getElementById('evac-chart');
const chartCtx = chartCanvas.getContext('2d');
const history = [];

function updateStatsUI(stats, t) {
  statsEls.elapsed.textContent = stats.elapsed.toFixed(1) + 's';
  statsEls.evacuated.textContent = stats.evacuated;
  statsEls.active.textContent = stats.active;
  statsEls.trapped.textContent = stats.trapped;
  statsEls.casualties.textContent = stats.casualties;

  history.push({ t, ...stats });
  if (history.length > 400) history.shift();
  drawChart();
}

function drawChart() {
  const w = chartCanvas.width, h = chartCanvas.height;
  chartCtx.clearRect(0, 0, w, h);
  if (history.length < 2) return;
  const total = history[history.length - 1].total || 1;
  const minT = history[0].t, maxT = history[history.length - 1].t || 1;
  const span = Math.max(1, maxT - minT);
  const series = [
    { key: 'evacuated', color: '#33d17a' },
    { key: 'casualties', color: '#ff4d5e' },
    { key: 'trapped', color: '#b23bff' },
  ];
  for (const s of series) {
    chartCtx.beginPath();
    history.forEach((pt, idx) => {
      const x = ((pt.t - minT) / span) * (w - 8) + 4;
      const y = h - 4 - (pt[s.key] / total) * (h - 10);
      if (idx === 0) chartCtx.moveTo(x, y); else chartCtx.lineTo(x, y);
    });
    chartCtx.strokeStyle = s.color;
    chartCtx.lineWidth = 2;
    chartCtx.stroke();
  }
}

function onStateMessage(msg) {
  agentCount = msg.people.length;
  for (let i = 0; i < msg.people.length; i++) {
    const p = msg.people[i];
    const [sx, sz] = toScene(p.x, p.y);
    const st = agentState[i];
    st.x = sx; st.z = sz; st.floor = p.floor; st.status = p.status;
  }
  applySparse(msg.fire, fireCells);
  applySparse(msg.smoke, smokeCells);
  updateStatsUI(msg.stats, msg.t);
}

function setActivePause(paused) {
  document.getElementById('btn-pause').classList.toggle('btn-active', paused);
  document.getElementById('btn-resume').classList.toggle('btn-active', !paused);
}

const agentsSlider = document.getElementById('agents-slider');
const agentsValue = document.getElementById('agents-value');
agentsSlider.oninput = () => { agentsValue.textContent = agentsSlider.value; };
agentsSlider.onchange = () => send({ cmd: 'agents', n: Number(agentsSlider.value) });

const speedSlider = document.getElementById('speed-slider');
const speedValue = document.getElementById('speed-value');
speedSlider.oninput = () => {
  speedValue.textContent = Number(speedSlider.value).toFixed(2) + '×';
  send({ cmd: 'speed', value: Number(speedSlider.value) });
};

document.getElementById('btn-spark').onclick = () => send({ cmd: 'spark' });
document.getElementById('btn-reset').onclick = () => send({ cmd: 'reset', agents: Number(agentsSlider.value) });
document.getElementById('btn-pause').onclick = () => { send({ cmd: 'pause' }); setActivePause(true); };
document.getElementById('btn-resume').onclick = () => { send({ cmd: 'resume' }); setActivePause(false); };

// ---------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------
let ws;
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onclose = () => setTimeout(connect, 1500);
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'floorplan') buildScene(msg);
    else if (msg.type === 'state') onStateMessage(msg);
  };
}
function send(cmd) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(cmd));
}
connect();

// ---------------------------------------------------------------------
// Bucle de render
// ---------------------------------------------------------------------
let lastTime = performance.now();
function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  const dt = Math.min(0.1, (now - lastTime) / 1000);
  lastTime = now;

  updateAgents(dt);
  updateFireSmoke();
  updateFireLights();

  if (cameraMode === 'orbit') controls.update();
  else if (cameraMode === 'follow') updateFollowCamera(dt);

  composer.render();
}
animate();
