// Объёмная оболочка общей симуляции. При отсутствии WebGL остаётся Canvas.
import * as THREE from "./vendor/three.module.js";
const materials = new Map(),
  geometries = new Map();
function mat(color) {
  if (!materials.has(color))
    materials.set(
      color,
      new THREE.MeshStandardMaterial({
        color,
        roughness: 0.55,
        metalness: 0.12,
      }),
    );
  return materials.get(color);
}
function geo(type) {
  if (!geometries.has(type))
    geometries.set(
      type,
      type === "box"
        ? new THREE.BoxGeometry(1, 1, 1)
        : type === "sphere"
          ? new THREE.SphereGeometry(1, 10, 8)
          : new THREE.CylinderGeometry(1, 1, 1, 8),
    );
  return geometries.get(type);
}
function shape(parent, type, color, x, y, z, sx, sy, sz) {
  const m = new THREE.Mesh(geo(type), mat(color));
  m.position.set(x, y, z);
  m.scale.set(sx, sy, sz);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}
const box = (p, c, x, y, z, a, b, d) => shape(p, "box", c, x, y, z, a, b, d);
const ball = (p, c, x, y, z, a, b = a, d = a) =>
  shape(p, "sphere", c, x, y, z, a, b, d);
const cylinder = (p, c, x, y, z, a, b, d = a) =>
  shape(p, "cylinder", c, x, y, z, a, b, d);
const textures = new Map();
function label(text, color = "#ffffff", bg = null) {
  const key = text + color + bg;
  if (!textures.has(key)) {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 128;
    const t = c.getContext("2d");
    if (bg) {
      t.fillStyle = bg;
      t.fillRect(0, 0, 256, 128);
    }
    t.font = "900 70px system-ui";
    t.textAlign = "center";
    t.textBaseline = "middle";
    t.lineWidth = 9;
    t.strokeStyle = "#253c58";
    t.strokeText(String(text), 128, 68);
    t.fillStyle = color;
    t.fillText(String(text), 128, 68);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    textures.set(key, tex);
  }
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: textures.get(key),
      transparent: true,
      depthWrite: false,
    }),
  );
  sprite.scale.set(2.4, 1.2, 1);
  return sprite;
}
function ring(parent, color, r = 0.42) {
  const m = new THREE.Mesh(
    new THREE.RingGeometry(r * 0.88, r, 20),
    new THREE.MeshBasicMaterial({
      color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8,
    }),
  );
  m.rotation.x = -Math.PI / 2;
  m.position.y = 0.035;
  parent.add(m);
  return m;
}
const glowCanvas = document.createElement("canvas");
glowCanvas.width = 64;
glowCanvas.height = 64;
const glowCtx = glowCanvas.getContext("2d"),
  glowGradient = glowCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
glowGradient.addColorStop(0, "#ffffffff");
glowGradient.addColorStop(0.15, "#ffffffdd");
glowGradient.addColorStop(0.4, "#ffffff55");
glowGradient.addColorStop(1, "#ffffff00");
glowCtx.fillStyle = glowGradient;
glowCtx.fillRect(0, 0, 64, 64);
const glowTexture = new THREE.CanvasTexture(glowCanvas);
function glow(color, size) {
  const s = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: glowTexture,
      color,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      transparent: true,
    }),
  );
  s.scale.set(size, size, 1);
  return s;
}
function fighter(leader = false) {
  const g = new THREE.Group();
  ring(g, 0x88ff78, 0.45);
  const shirt = leader ? "#1d2736" : "#333a50";
  // Раздельные ноги и оружие создают читаемый силуэт, а не плоскую иконку.
  const legs = [];
  for (const side of [-1, 1]) {
    const leg = box(g, "#30435e", side * 0.15, 0.3, 0, 0.19, 0.5, 0.22);
    legs.push(leg);
    box(g, "#f4fbff", side * 0.15, 0.08, 0.08, 0.22, 0.13, 0.35);
  }
  box(g, shirt, 0, 0.85, 0, 0.6, 0.66, 0.36);
  box(g, "#ff4d57", 0, 0.57, 0, 0.65, 0.17, 0.4);
  box(g, "#f6fae7", 0, 0.87, 0.2, 0.12, 0.5, 0.06);
  ball(g, "#e9b88e", 0, 1.4, 0, 0.23, 0.26, 0.23);
  ball(g, leader ? "#f7d45a" : "#22334a", 0, 1.61, -0.015, 0.24, 0.18, 0.25);
  box(g, "#1a4e71", 0, 1.43, 0.21, 0.4, 0.1, 0.06);
  for (const side of [-1, 1]) {
    const arm = box(g, "#f0c49b", side * 0.37, 0.95, 0.12, 0.16, 0.45, 0.19);
    arm.rotation.x = -0.6;
  }
  box(g, "#f2c738", 0.3, 0.98, -0.26, 0.18, 0.22, 0.68);
  box(g, "#34404c", 0.3, 1, -0.75, 0.1, 0.12, 0.48);
  if (leader) {
    const hat = new THREE.Mesh(
      new THREE.ConeGeometry(0.55, 0.22, 12),
      mat("#b78e51"),
    );
    hat.position.y = 1.88;
    g.add(hat);
    box(g, "#202536", 0, 0.65, -0.23, 0.75, 0.6, 0.15);
    const sword = box(g, "#d3ecff", -0.32, 1, -0.35, 0.05, 1.6, 0.07);
    sword.rotation.z = -0.6;
  }
  g.userData.legs = legs;
  return g;
}
function monster(type, kind) {
  const g = new THREE.Group();
  const limbs = [];
  if (type === "fast") {
    ball(g, "#973c85", 0, 0.5, 0, 0.55, 0.35, 0.7);
    ball(g, "#46283e", 0, 0.42, 0.55, 0.4, 0.24, 0.3);
    for (let i = 0; i < 4; i++)
      for (const side of [-1, 1]) {
        const leg = box(
          g,
          "#52243e",
          side * 0.65,
          0.29,
          (i - 1.5) * 0.32,
          0.8,
          0.1,
          0.11,
        );
        leg.rotation.z = side * 0.35;
        limbs.push(leg);
      }
    for (const side of [-1, 1])
      ball(g, "#ffbc5b", side * 0.13, 0.51, 0.79, 0.08);
  } else if (type === "shaman" || kind === "lich") {
    const robe = new THREE.Mesh(
      new THREE.ConeGeometry(0.6, 1.5, 8),
      mat("#8b45c6"),
    );
    robe.position.y = 0.8;
    robe.castShadow = true;
    g.add(robe);
    ball(g, "#4a275c", 0, 1.55, 0, 0.38);
    box(g, "#e8d5b0", 0, 1.5, 0.3, 0.42, 0.26, 0.08);
    for (const side of [-1, 1])
      ball(g, "#fd6aff", side * 0.12, 1.56, 0.37, 0.06);
    box(g, "#5e3677", 0.65, 1, 0, 0.09, 2, 0.09);
    ball(g, "#e29aff", 0.65, 2.05, 0, 0.21);
    ring(g, 0xbf74ff, 0.6);
  } else if (type === "armored") {
    box(g, "#6c8791", 0, 0.92, 0, 1.05, 1.1, 0.7);
    box(g, "#97adb0", 0, 1.67, 0, 0.58, 0.5, 0.54);
    for (const side of [-1, 1]) {
      box(g, "#576d7c", side * 0.73, 0.85, 0, 0.42, 0.85, 0.48);
      const l = box(g, "#546777", side * 0.3, 0.25, 0, 0.4, 0.5, 0.43);
      limbs.push(l);
      box(g, "#7ffff0", side * 0.13, 1.7, 0.29, 0.14, 0.08, 0.03);
    }
    box(g, "#86ffe5", 0, 1, 0.38, 0.12, 0.65, 0.04);
  } else {
    const bone = type === "skeleton",
      color = bone ? "#dcd9bf" : type === "boss" ? "#ff743d" : "#d83f54";
    for (const side of [-1, 1]) {
      const l = box(
        g,
        bone ? "#d7d6b8" : "#34384f",
        side * 0.23,
        0.28,
        0,
        0.25,
        0.5,
        0.3,
      );
      limbs.push(l);
      ball(g, color, side * 0.52, 0.94, 0, 0.23, 0.45, 0.25);
    }
    if (bone) {
      box(g, color, 0, 0.85, 0, 0.14, 0.8, 0.15);
      for (let i = 0; i < 4; i++)
        box(g, color, 0, 0.65 + i * 0.14, 0, 0.66, 0.07, 0.19);
    } else {
      ball(g, color, 0, 0.97, 0, 0.55, 0.6, 0.38);
      box(g, "#34364d", 0, 0.54, 0, 0.92, 0.22, 0.66);
    }
    ball(g, color, 0, 1.64, 0, 0.37, 0.4, 0.32);
    for (const side of [-1, 1]) {
      box(
        g,
        bone ? "#282b3c" : "#ffec93",
        side * 0.14,
        1.73,
        0.29,
        0.14,
        0.09,
        0.05,
      );
      if (!bone) {
        const horn = new THREE.Mesh(
          new THREE.ConeGeometry(0.12, 0.45, 6),
          mat("#fff1ce"),
        );
        horn.position.set(side * 0.3, 1.99, 0);
        horn.rotation.z = side * -0.4;
        g.add(horn);
      }
    }
    if (!bone) {
      ball(g, "#f5b389", 0, 1.51, 0.32, 0.22, 0.13, 0.12);
      box(g, "#25283a", 0, 2, 0, 0.45, 0.2, 0.26);
    } else box(g, "#bc4056", 0, 1.98, 0, 0.68, 0.09, 0.6);
  }
  for (const side of [-1, 1]) {
    const eye = glow(type === "shaman" ? "#e566ff" : "#ff3b22", 0.3);
    eye.position.set(side * 0.14, 1.73, 0.34);
    g.add(eye);
  }
  g.userData.legs = limbs;
  return g;
}
class BridgeRenderer {
  constructor() {
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.setSize(540, 960, false);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    const el = this.renderer.domElement;
    el.id = "world3d";
    el.style.cssText =
      "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;";
    document
      .querySelector("#frame")
      .insertBefore(el, document.querySelector("#hud"));
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#29354a");
    this.scene.fog = new THREE.Fog("#29354a", 47, 100);
    this.camera = new THREE.PerspectiveCamera(47, 9 / 16, 0.1, 160);
    this.camera.position.set(0, 23, 22);
    this.camera.lookAt(0, 0, -12);
    this.scene.add(new THREE.HemisphereLight("#b9dcff", "#24182b", 1.5));
    const sun = new THREE.DirectionalLight("#ffe1bb", 2.7);
    sun.position.set(-12, 30, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, {
      left: -22,
      right: 22,
      top: 40,
      bottom: -38,
      near: 1,
      far: 90,
    });
    sun.shadow.bias = -0.001;
    this.scene.add(sun);
    this.world = new THREE.Group();
    this.scene.add(this.world);
    this.actors = new Map();
    this.gates = new Map();
    this.props = new Map();
    this.effectGroups = [];
    this.squad = [];
    this.squadGroup = new THREE.Group();
    this.world.add(this.squadGroup);
    this.buildTemplePath();
    this.vector = new THREE.Vector3();
    this.renderer.domElement.addEventListener("webglcontextlost", (e) => {
      e.preventDefault();
      this.failed = true;
      el.style.display = "none";
      window.dojoRenderer = null;
    });
  }
  pos(x, y) {
    return [(x - 270) / 25, 0, (y - 755) / 24];
  }
  project(x, y) {
    this.camera.updateMatrixWorld();
    this.vector.set(...this.pos(x, y)).project(this.camera);
    const a = (this.vector.x + 1) * 270,
      b = (1 - this.vector.y) * 480;
    this.vector.set(...this.pos(x + 1, y)).project(this.camera);
    return { x: a, y: b, scale: (this.vector.x + 1) * 270 - a };
  }
  buildTemplePath() {
    box(this.world, "#17232d", 0, -2, -30, 150, 0.2, 230);
    box(this.world, "#393b3c", 0, -0.4, -17, 17, 0.7, 72);
    // Uneven stone slabs, mossy shoulders, lanterns and shrine banners.
    for (let row = 0; row < 48; row++)
      for (let col = 0; col < 9; col++) {
        const k = row * 9 + col;
        box(
          this.world,
          ["#605d60", "#59595c", "#646062", "#585b5b"][(k * 13 + row * 3) % 4],
          (col - 4) * 1.82 + (row % 2) * 0.12,
          -0.015,
          -53 + row * 1.5,
          1.79,
          0.14,
          1.47,
        );
        if (k % 11 === 0)
          box(
            this.world,
            "#46533a",
            (col - 4) * 1.82,
            0.065,
            -53 + row * 1.5,
            0.8,
            0.025,
            0.35,
          );
      }
    for (const side of [-1, 1]) {
      box(this.world, "#3b4a3c", side * 9, -0.15, -17, 1.4, 0.55, 72);
      for (let j = 0; j < 12; j++) {
        const z = -51 + j * 6;
        const rock = ball(
          this.world,
          "#37404b",
          side * (10 + (j % 3)),
          0.1,
          z,
          1.6,
          1.7,
          2.8,
        );
        rock.rotation.z = side * 0.4;
        box(this.world, "#44313c", side * 9.1, 2.1, z, 0.23, 4.2, 0.23);
        box(this.world, "#9f253d", side * 9.1, 2.4, z + 1.2, 0.07, 2.8, 2.2);
        box(this.world, "#e1b993", side * 9.15, 2.4, z + 1.2, 0.09, 1.65, 0.12);
        if (j % 2 === 0) {
          box(this.world, "#312f3a", side * 8.2, 0.8, z, 0.55, 1.6, 0.55);
          const lamp = ball(this.world, "#ffc97b", side * 8.2, 1.65, z, 0.3);
          lamp.material = new THREE.MeshBasicMaterial({ color: "#ffd296" });
          box(this.world, "#252a32", side * 8.2, 2, z, 0.9, 0.17, 0.9);
        }
        if (j % 2 === 1) {
          const x = side * (12 + (j % 3));
          const trunk = box(this.world, "#4d343d", x, 2, z, 0.5, 5, 0.5);
          trunk.rotation.z = side * 0.2;
          for (let n = 0; n < 8; n++)
            ball(
              this.world,
              ["#f490bd", "#b94d85", "#f5b2ce"][n % 3],
              x + Math.sin(n * 2) * 2.1,
              4 + (n % 3) * 0.6,
              z + Math.cos(n * 2) * 2,
              1.6,
              0.8,
              1.5,
            );
        }
      }
    }
    // Temple silhouette at the vanishing point.
    for (const x of [-6, 6])
      box(this.world, "#a33142", x, 4, -52, 0.65, 8, 0.65);
    for (const y of [6, 8]) box(this.world, "#472c3d", 0, y, -52, 15, 0.5, 1.2);
    this.water = [];
  }
  gate(gate) {
    const g = new THREE.Group();
    for (const x of [-0.85, 0.85])
      box(g, "#ffbd42", x, 1.05, 0, 0.1, 2.1, 0.15);
    box(g, "#16c6fa", 0, 1.3, 0, 1.6, 1.35, 0.1);
    box(g, "#8af4ff", 0, 2, 0, 1.7, 0.07, 0.13);
    const text = label("+" + gate.value);
    text.position.set(0, 1.33, 0.11);
    text.scale.set(1.5, 0.75, 1);
    g.add(text);
    return g;
  }
  crate(e) {
    const g = new THREE.Group();
    box(g, "#cf8c3d", 0, 0.7, 0, 1.5, 1.3, 1.25);
    box(g, "#f0b458", 0, 1.39, 0, 1.55, 0.13, 1.3);
    for (const x of [-0.48, 0.48]) {
      box(g, "#c4d6d9", x, 0.75, 0.64, 0.09, 1.4, 0.03);
      box(g, "#b2c8cd", x, 1.47, 0, 0.1, 0.04, 1.3);
    }
    const text = label(String(Math.ceil(e.hp)));
    text.position.set(0, 0.78, 0.68);
    g.add(text);
    g.userData.text = text;
    g.userData.hp = e.hp;
    return g;
  }
  sync(map, items, builder, updater) {
    const keep = new Set();
    for (const item of items) {
      if (item.dead) continue;
      keep.add(item);
      let group = map.get(item);
      if (!group) {
        group = builder(item);
        this.world.add(group);
        map.set(item, group);
      }
      group.position.set(...this.pos(item.x, item.y));
      updater?.(group, item);
    }
    for (const [item, group] of map)
      if (!keep.has(item)) {
        this.world.remove(group);
        map.delete(item);
      }
  }
  render(g) {
    if (this.failed) return;
    const t = g.time;
    this.sync(
      this.actors,
      g.enemies,
      (e) => (e.type === "crate" ? this.crate(e) : monster(e.type, e.kind)),
      (group, e) => {
        const size =
          e.type === "boss"
            ? e.kind === "lich"
              ? 2.9
              : 3.2
            : e.type === "armored"
              ? 1.45
              : 1.3;
        group.scale.setScalar(size);
        if (e.type === "crate") group.scale.setScalar(1);
        group.position.y = Math.sin(t * 6 + (e.phase || 0)) * 0.04;
        if (e.type === "boss") {
          if (!group.userData.health) {
            box(group, "#5e293b", 0, 2.65, 0, 2, 0.12, 0.12);
            group.userData.health = box(
              group,
              "#ff4747",
              0,
              2.66,
              0.08,
              2,
              0.1,
              0.1,
            );
          }
          group.userData.health.scale.x = Math.max(0.01, (2 * e.hp) / e.maxHp);
        }

        group.userData.legs?.forEach(
          (leg, i) => (leg.rotation.x = Math.sin(t * 8 + i * 3) * 0.18),
        );
        if (e.type === "crate" && group.userData.hp !== Math.ceil(e.hp)) {
          group.remove(group.userData.text);
          group.userData.text.material.dispose();
          const text = label(String(Math.max(0, Math.ceil(e.hp))));
          text.position.set(0, 0.78, 0.68);
          group.add(text);
          group.userData.text = text;
          group.userData.hp = Math.ceil(e.hp);
        }
      },
    );
    this.sync(this.gates, g.gates, (e) => this.gate(e));
    this.sync(
      this.props,
      g.pickups,
      (e) => {
        const p = new THREE.Group();
        const colors = {
          sword: "#ffb338",
          star: "#38aaff",
          heart: "#60ee65",
          slow: "#c17cff",
          army: "#fae147",
          coin: "#ffd34b",
        };
        const orb = ball(p, colors[e.type], 0, 0.45, 0, 0.3);
        orb.material = new THREE.MeshStandardMaterial({
          color: colors[e.type],
          emissive: colors[e.type],
          emissiveIntensity: 0.4,
        });
        ring(p, colors[e.type], 0.48);
        const beam = box(p, colors[e.type], 0, 1.4, 0, 0.08, 2.7, 0.08);
        beam.material = new THREE.MeshBasicMaterial({
          color: colors[e.type],
          transparent: true,
          opacity: 0.38,
        });
        return p;
      },
      (p, e) => {
        p.rotation.y = t;
        p.position.y = Math.sin(t * 4) * 0.08;
      },
    );
    while (this.squad.length < g.player.army + 1) {
      const f = fighter(this.squad.length === 0);
      this.squad.push(f);
      this.squadGroup.add(f);
    }
    this.squad.forEach((f, i) => {
      f.visible = i <= g.player.army;
      if (!f.visible) return;
      const row = i === 0 ? -1 : Math.floor((i - 1) / 6),
        col = i === 0 ? 0 : ((i - 1) % 6) - 2.5;
      const pos = this.pos(g.player.x + col * 19, g.player.y + 26 + row * 24);
      f.position.set(...pos);
      f.userData.legs.forEach(
        (l, j) => (l.rotation.x = Math.sin(t * 9 + i + j * 3) * 0.12),
      );
    });
    // Эффекты переиспользуются: число объектов ограничено текущим боем.
    for (const f of this.effectGroups) {
      this.world.remove(f);
      f.geometry?.dispose();
      f.material?.dispose();
    }
    this.effectGroups = [];
    for (const shot of g.shots) {
      const m = new THREE.Mesh(
        new THREE.BoxGeometry(0.045, 0.045, shot.star ? 0.75 : 2.2),
        new THREE.MeshBasicMaterial({
          color: shot.star ? "#bf71ff" : "#73eaff",
        }),
      );
      m.position.set(...this.pos(shot.x, shot.y));
      m.position.y = 1;
      this.world.add(m);
      this.effectGroups.push(m);
      const halo = glow("#38cdff", 1);
      halo.scale.set(0.35, 1.1, 1);
      halo.position.copy(m.position);
      this.world.add(halo);
      this.effectGroups.push(halo);
    }
    for (const bolt of g.hazards) {
      const m = new THREE.Mesh(
        geo("sphere"),
        new THREE.MeshBasicMaterial({ color: "#d45bff" }),
      );
      m.scale.set(0.19, 0.2, 0.4);
      m.position.set(...this.pos(bolt.x, bolt.y));
      m.position.y = 0.6;
      this.world.add(m);
      this.effectGroups.push(m);
    }
    for (const p of g.particles.slice(-180)) {
      const spark = glow(p.color, 0.2 + p.life * 0.9);
      spark.position.set(...this.pos(p.x, p.y));
      spark.position.y = 0.5;
      this.world.add(spark);
      this.effectGroups.push(spark);
    }
    for (const e of g.enemies) {
      const warning = e.type === "boss" ? e.warning : e.castWarning;
      if (warning > 0) {
        const x = e.type === "boss" ? e.attackX : e.castX,
          w = e.type === "boss" ? 124 : 56;
        const near = this.pos(x, CONFIG.playerY + 30),
          far = this.pos(x, e.y);
        const m = new THREE.Mesh(
          new THREE.PlaneGeometry(w / 25, near[2] - far[2]),
          new THREE.MeshBasicMaterial({
            color: e.kind === "lich" ? "#c450fa" : "#fa4550",
            transparent: true,
            opacity: 0.28,
            side: THREE.DoubleSide,
          }),
        );
        m.rotation.x = -Math.PI / 2;
        m.position.set(near[0], 0.025, (near[2] + far[2]) / 2);
        this.world.add(m);
        this.effectGroups.push(m);
      }
    }
    this.water.forEach((m, i) => (m.scale.x = 1 + Math.sin(t * 1.5 + i) * 0.2));
    this.camera.position.x = g.shake ? Math.sin(t * 90) * g.shake * 0.012 : 0;
    this.camera.lookAt(0, 0, -12);
    this.renderer.render(this.scene, this.camera);
  }
}
try {
  const renderer = new BridgeRenderer();
  window.dojoRenderer = renderer;
} catch (error) {
  console.warn("WebGL unavailable; Canvas renderer retained.");
}
