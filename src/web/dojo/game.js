"use strict";
// Все игровые величины заданы в логических координатах 540 × 960.
const CONFIG = {
  width: 540,
  maxArmy: 11,
  gatePeriod: 3.4,
  gateSpeed: 82,
  crateHp: 138,
  height: 960,
  road: [90, 450],
  playerY: 755,
  lives: 2,
  maxLives: 2,
  army: 6,
  leakArmyLoss: 1,
  damage: 5,
  attackPeriod: 0.28,
  range: 1200,
  enemySpeed: 56,
  shotSpeed: 640,
  comboWindow: 3,
  magnetRadius: 100,
  dropChance: 0.12,
  slowSeconds: 5,
  shopSeconds: 4,
  cost: { warrior: 100, damage: 150, speed: 150 },
  waves: [
    { count: 48, hp: 40, speed: 1.02 },
    { count: 66, hp: 100, speed: 1.2 },
    { count: 84, hp: 190, speed: 1.38, boss: 2200, bossKind: "oni" },
    { count: 102, hp: 300, speed: 1.56 },
    { count: 126, hp: 450, speed: 1.75, boss: 4000, bossKind: "lich" },
  ],
};
const canvas = document.querySelector("#game"),
  ctx = canvas.getContext("2d");
const $ = (s) => document.querySelector(s),
  clamp = (x, a, b) => Math.max(a, Math.min(b, x)),
  rand = (a, b) => a + Math.random() * (b - a);
// Единая перспективная проекция. Бой остаётся в координатах мира;
// дальность, снаряды, телеграфы и указатель используют одну геометрию.
function project(x, y) {
  if (window.dojoRenderer) return window.dojoRenderer.project(x, y);
  const depth = clamp((y + 60) / 960, 0, 1.2),
    scale = 0.28 + 0.82 * depth;
  return {
    x: 270 + (x - 270) * scale,
    y: 108 + 800 * Math.pow(depth, 1.45),
    scale,
  };
}
function worldDraw(x, y, draw) {
  const p = project(x, y);
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.scale(p.scale, p.scale);
  ctx.translate(-x, -y);
  draw();
  ctx.restore();
}
function lanePath(x, width, from, to) {
  const pts = [
    project(x - width, from),
    project(x + width, from),
    project(x + width, to),
    project(x - width, to),
  ];
  ctx.beginPath();
  pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  ctx.closePath();
}
class Sound {
  constructor() {
    this.on = true;
  }
  play(kind) {
    if (!this.on) return;
    try {
      this.audio ??= new (window.AudioContext || window.webkitAudioContext)();
      this.audio.resume();
      const o = this.audio.createOscillator(),
        g = this.audio.createGain(),
        t = this.audio.currentTime;
      o.type = kind === "hit" ? "triangle" : "sine";
      o.frequency.setValueAtTime(
        { hit: 150, pick: 700, kill: 240, hurt: 70 }[kind],
        t,
      );
      o.frequency.exponentialRampToValueAtTime(55, t + 0.12);
      g.gain.setValueAtTime(0.035, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.14);
      o.connect(g);
      g.connect(this.audio.destination);
      o.start();
      o.stop(t + 0.15);
    } catch {}
  }
}
class Player {
  constructor() {
    this.x = 270;
    this.target = 270;
    this.y = CONFIG.playerY;
    this.lives = CONFIG.lives;
    this.army = CONFIG.army;
    this.damage = CONFIG.damage;
    this.period = CONFIG.attackPeriod;
    this.cooldown = 0;
    this.shuriken = false;
  }
  update(dt, g) {
    this.x += (this.target - this.x) * Math.min(1, dt * 13);
    this.cooldown -= dt;
    if (this.cooldown <= 0) {
      const targets = g.enemies
        .filter(
          (e) =>
            !e.dead && Math.hypot(e.x - this.x, e.y - this.y) < CONFIG.range,
        )
        .sort(
          (a, b) => (a.type === "crate") - (b.type === "crate") || b.y - a.y,
        );
      {
        this.cooldown = this.period;
        for (let i = 0; i < this.army; i++) {
          const e = targets.length ? targets[i % targets.length] : null;
          if (!e || !e.dead) {
            g.shots.push(
              new Projectile(
                this.x + ((i % 5) - 2) * 15,
                this.y + 35,
                e,
                this.damage,
                this.shuriken,
              ),
            );
          }
        }
        g.sound.play("hit");
      }
    }
  }
  draw(t) {
    for (let i = this.army - 1; i >= 0; i--) {
      const row = Math.floor(i / 6),
        x = this.x + ((i % 6) - 2.5) * 22,
        y = this.y + 45 + row * 23;
      worldDraw(x, y, () => warrior(x, y, Math.sin(t * 6 + i) * 1.5));
    }
    worldDraw(this.x, this.y, () => samurai(this.x, this.y));
  }
}
// Снаряд наносит урон при попадании, а не при запуске.
class Projectile {
  constructor(x, y, target, damage, star) {
    Object.assign(this, {
      x,
      y,
      target,
      damage,
      star,
      life: 2.5,
      dead: false,
      angle: 0,
    });
  }
  update(dt, g) {
    this.life -= dt;
    if (this.target?.dead) this.target = null;
    if (!this.target) {
      const nextY = this.y - CONFIG.shotSpeed * dt;
      const hit = g.enemies.find(
        (e) =>
          !e.dead &&
          Math.abs(e.x - this.x) < e.r &&
          e.y <= this.y &&
          e.y >= nextY - e.r,
      );
      if (hit) {
        hit.hit(this.damage, g);
        this.dead = true;
        g.burst(this.x, hit.y, "#69eaff", 3);
        return;
      }
      this.y = nextY;
      if (this.life <= 0 || this.y < -100) this.dead = true;
      return;
    }
    if (this.life <= 0) {
      this.dead = true;
      return;
    }
    const dx = this.target.x - this.x,
      dy = this.target.y - this.y,
      d = Math.hypot(dx, dy);
    this.angle = Math.atan2(dy, dx);
    if (d < CONFIG.shotSpeed * dt + this.target.r * 0.7) {
      this.target.hit(this.damage, g);
      this.dead = true;
      g.burst(this.x, this.y, this.star ? "#9eeaff" : "#ffe4ad", 3);
    } else {
      this.x += (dx / d) * CONFIG.shotSpeed * dt;
      this.y += (dy / d) * CONFIG.shotSpeed * dt;
    }
  }
  draw(t) {
    ctx.save();
    ctx.translate(this.x, this.y);
    ctx.rotate(this.star ? t * 23 : this.angle);
    ctx.shadowColor = this.star ? "#75d7ff" : "#ffff90";
    ctx.shadowBlur = 12;
    if (this.star) {
      ctx.fillStyle = "#b4ecff";
      ctx.beginPath();
      for (let i = 0; i < 8; i++) {
        const a = (i * Math.PI) / 4,
          r = i % 2 ? 2 : 8;
        i
          ? ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r)
          : ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.fill();
    } else {
      ctx.strokeStyle = "#fff9a6";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-23, 0);
      ctx.lineTo(7, 0);
      ctx.stroke();
    }
    ctx.restore();
  }
}
class Enemy {
  constructor(wave, type = "normal") {
    this.type = type;
    this.castTimer = rand(3, 5);
    this.castWarning = 0;
    this.castX = 270;
    this.x = rand(110, 430);
    this.y = -45;
    this.maxHp =
      wave.hp *
      (type === "armored"
        ? 2.8
        : type === "fast"
          ? 0.55
          : type === "skeleton"
            ? 0.8
            : type === "shaman"
              ? 1.2
              : 1);
    this.hp = this.maxHp;
    this.speed =
      CONFIG.enemySpeed *
      wave.speed *
      (type === "fast" ? 1.8 : type === "armored" ? 0.65 : 1);
    this.r = type === "armored" ? 23 : 19;
    this.dead = false;
    this.flash = 0;
    this.phase = rand(0, 6);
  }
  hit(d, g) {
    if (this.dead) return;
    this.hp -= d;
    g.floatText(this.x, this.y - 20, Math.ceil(d), "#fff0c7");
    this.flash = 0.12;
    if (this.hp <= 0 && !this.dead) {
      this.dead = true;
      g.combo = g.comboTime > 0 ? g.combo + 1 : 1;
      g.comboTime = CONFIG.comboWindow;
      const bonus = Math.min(3, Math.floor(g.combo / 5));
      const bounty = (this.type === "boss" ? 60 : 9) + bonus;
      g.coins += bounty;
      g.floatText(this.x, this.y, "+" + bounty + " ◉", "#ffd978");
      g.kills++;
      g.burst(this.x, this.y, "#ffcf7c", 12);
      g.sound.play("kill");
      if (Math.random() < CONFIG.dropChance || this.type === "boss")
        g.pickups.push(new Pickup(this.x, this.y));
    }
  }
  update(dt, g) {
    // Быстрые разведчики виляют, но остаются в пределах дороги.
    if (this.type === "fast")
      this.x = clamp(
        this.x + Math.sin(g.time * 3 + this.phase) * 30 * dt,
        105,
        435,
      );
    this.y += this.speed * dt * (g.slow > 0 ? 0.42 : 1);
    this.flash = Math.max(0, this.flash - dt);
    if (this.type === "shaman" && this.y > 220 && this.y < 640) {
      this.castTimer -= dt;
      if (this.castTimer <= 0 && this.castWarning <= 0) {
        this.castWarning = 1.1;
        this.castX = g.player.x;
      }
      if (this.castWarning > 0) {
        this.castWarning -= dt;
        if (this.castWarning <= 0) {
          this.castTimer = 5;
          g.hazards.push(new EnemyBolt(this.x, this.y, this.castX));
        }
      }
    }

    if (this.y > CONFIG.playerY + 12) {
      this.dead = true;
      g.player.lives--;
      g.player.army = Math.max(0, g.player.army - CONFIG.leakArmyLoss);
      g.combo = 0;
      g.comboTime = 0;
      g.shake = 9;
      g.sound.play("hurt");
      g.burst(this.x, this.y, "#ef6475", 16);
    }
  }
  draw(t) {
    drawMonster(
      this.x,
      this.y + Math.sin(t * 5 + this.phase) * 3,
      this.r,
      this.type,
      this.flash > 0,
    );
    if (this.hp < this.maxHp) {
      ctx.fillStyle = "#231720";
      ctx.fillRect(this.x - 20, this.y - 35, 40, 4);
      ctx.fillStyle = "#ef6b70";
      ctx.fillRect(
        this.x - 20,
        this.y - 35,
        40 * Math.max(0, this.hp / this.maxHp),
        4,
      );
    }
  }
}
class Boss extends Enemy {
  constructor(w) {
    super(w, "boss");
    this.x = 270;
    this.kind = w.bossKind || "oni";
    this.name =
      this.kind === "lich"
        ? "АРХИЛИЧ · ПОВЕЛИТЕЛЬ ПЕПЛА"
        : "ОНИ · РАЗРУШИТЕЛЬ ВРАТ";
    this.summonTimer = 8;
    this.maxHp = this.hp = w.boss;
    this.r = 65;
    this.speed = 16 * w.speed;
    this.charge = 4;
    this.enraged = false;
    this.warning = 0;
    this.attackX = 270;
  }
  update(dt, g) {
    super.update(dt, g);
    this.y = Math.min(500, this.y);
    this.x = 270 + Math.sin(g.time * 0.55) * 120;
    if (this.hp < this.maxHp * 0.45 && !this.enraged) {
      this.enraged = true;
      g.ui.toast("ВОЖДЬ В ЯРОСТИ · УДАРЫ ЧАЩЕ!");
      g.burst(this.x, this.y, "#ff697e", 25);
    }
    // Вождь сначала должен появиться на поле, а не бить из-за экрана.
    if (this.y < 180) return;
    if (this.kind === "lich") {
      this.summonTimer -= dt;
      if (this.summonTimer <= 0) {
        this.summonTimer = this.enraged ? 6 : 9;
        for (const offset of [-40, 40]) {
          const minion = new Enemy({ hp: 20, speed: 1.2 }, "skeleton");
          minion.x = clamp(this.x + offset, 110, 430);
          minion.y = this.y + 20;
          g.enemies.push(minion);
        }
        g.ui.toast("АРХИЛИЧ ПРИЗЫВАЕТ СКЕЛЕТОВ!");
      }
    }
    this.charge -= dt;
    if (this.charge <= 0 && this.warning <= 0) {
      this.warning = 1.25;
      this.attackX = g.player.x;
      g.ui.toast(
        this.kind === "lich"
          ? "⚠ Веер заклинаний — ищи просвет!"
          : "⚠ Вождь замахивается — уходи с красной линии!",
      );
    }
    if (this.warning > 0) {
      this.warning -= dt;
      if (this.warning <= 0) {
        this.charge = this.enraged ? 2.7 : 4;
        if (this.kind === "lich") {
          for (const offset of [-85, 0, 85])
            g.hazards.push(
              new EnemyBolt(
                this.x,
                this.y,
                clamp(this.attackX + offset, 90, 450),
              ),
            );
        }
        if (this.kind !== "lich" && Math.abs(g.player.x - this.attackX) < 62) {
          g.player.army = Math.max(0, g.player.army - 2);
          g.shake = 12;
          g.sound.play("hurt");
        }
        g.burst(this.attackX, CONFIG.playerY, "#ff5e61", 25);
      }
    }
  }
  draw(t) {
    if (this.kind === "lich") {
      lich(this.x, this.y + Math.sin(t * 3) * 6, this.r, this.flash > 0);
    } else super.draw(t);
  }
}
const PICKUPS = {
  sword: ["刀", "#ffad3f"],
  star: ["✦", "#60caff"],
  heart: ["✚", "#8aff76"],
  slow: ["⌛", "#df83ff"],
  army: ["⇈", "#ffe17a"],
  coin: ["◉", "#ffd361"],
};
class Pickup {
  constructor(x, y, type) {
    this.x = x;
    this.y = y;
    this.type = type || Object.keys(PICKUPS)[Math.floor(Math.random() * 6)];
    this.dead = false;
  }
  update(dt, g) {
    this.y += 65 * dt;
    if (
      Math.hypot(this.x - g.player.x, this.y - g.player.y) < CONFIG.magnetRadius
    ) {
      this.x += (g.player.x - this.x) * Math.min(1, dt * 5);
      this.y += (g.player.y - this.y) * Math.min(1, dt * 5);
    }
    if (
      Math.abs(this.x - g.player.x) < 46 &&
      Math.abs(this.y - g.player.y) < 45
    ) {
      this.dead = true;
      const p = g.player;
      switch (this.type) {
        case "sword":
          p.damage += 2;
          break;
        case "star":
          p.period = Math.max(0.16, p.period * 0.9);
          p.shuriken = true;
          break;
        case "heart":
          p.lives = Math.min(CONFIG.maxLives, p.lives + 1);
          break;
        case "slow":
          g.slow = CONFIG.slowSeconds;
          break;
        case "army":
          p.army = Math.min(CONFIG.maxArmy, p.army + 1);
          break;
        case "coin":
          g.coins += 20;
      }
      g.sound.play("pick");
      g.ui.toast(
        {
          sword: "Урон +2",
          star: "Быстрее атаки · сюрикены!",
          heart: "Сердце восстановлено",
          slow: "Враги замедлены на 5 секунд",
          army: "Стрелок вступил в отряд",
          coin: "+20 монет",
        }[this.type],
      );
      g.burst(this.x, this.y, PICKUPS[this.type][1], 14);
    }
    if (this.y > 1000) this.dead = true;
  }
  draw(t) {
    const [icon, color] = PICKUPS[this.type];
    ctx.save();
    const beam = ctx.createLinearGradient(0, this.y - 130, 0, this.y);
    beam.addColorStop(0, "transparent");
    beam.addColorStop(1, color + "88");
    ctx.fillStyle = beam;
    ctx.fillRect(this.x - 12, this.y - 130, 24, 130);
    ctx.shadowColor = color;
    ctx.shadowBlur = 22;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(this.x, this.y, 18 + Math.sin(t * 4) * 2, 0, 7);
    ctx.fill();
    ctx.shadowBlur = 0;
    drawPickupIcon(this.type, this.x, this.y);
    ctx.restore();
  }
}
// Снаряд мага летит к заранее отмеченной полосе, не преследуя игрока.
class EnemyBolt {
  constructor(x, y, targetX) {
    Object.assign(this, { x, y, targetX, dead: false });
    this.vx = (targetX - x) / 2.6;
    this.vy = (CONFIG.playerY - y) / 2.6;
  }
  update(dt, g) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    if (this.y >= CONFIG.playerY) {
      this.dead = true;
      if (Math.abs(this.x - g.player.x) < 30) {
        g.player.army = Math.max(0, g.player.army - 1);
        g.shake = 6;
        g.sound.play("hurt");
        g.burst(this.x, this.y, "#d9a0ff", 12);
      }
    }
  }
  draw(t) {
    ctx.save();
    ctx.shadowColor = "#bd66ff";
    ctx.shadowBlur = 18;
    ellipse(this.x, this.y, 9, 14, "#be75ff");
    ellipse(this.x - 2, this.y - 3, 3, 6, "#f9e4ff");
    ctx.restore();
  }
}
// Ворота набора: выбирай край тропы, чтобы усилить строй.
class RecruitGate {
  constructor(x, y, value = 1) {
    Object.assign(this, { x, y, value, dead: false });
  }
  update(dt, g) {
    if (this.dead) return;
    this.y += CONFIG.gateSpeed * dt;
    if (
      this.y >= CONFIG.playerY - 30 &&
      this.y <= CONFIG.playerY + 30 &&
      Math.abs(g.player.x - this.x) < 45
    ) {
      this.dead = true;
      const added = Math.min(this.value, CONFIG.maxArmy - g.player.army);
      g.player.army += added;
      g.floatText(
        this.x,
        this.y,
        added ? "+" + added + " БОЕЦ" : "ОТРЯД ПОЛОН",
        "#57f2d1",
      );
      g.sound.play("pick");
      g.burst(this.x, this.y, "#7cfff1", 16);
    }
    if (this.y > CONFIG.playerY + 45) this.dead = true;
  }
  draw(t) {
    drawRecruitGate(this.x, this.y, this.value);
  }
}
// Ящик имеет собственный HP и гарантированную награду за разрушение.
class SupplyCrate extends Enemy {
  constructor(w) {
    super(w, "crate");
    this.x = 430;
    this.y = 140;
    this.hp = this.maxHp = CONFIG.crateHp;
    this.r = 30;
    this.speed = 13;
  }
  hit(d, g) {
    if (this.dead) return;
    this.hp -= d;
    this.flash = 0.1;
    g.floatText(this.x, this.y - 35, Math.ceil(d), "#fff5ba");
    if (this.hp <= 0) {
      this.dead = true;
      g.coins += 25;
      g.player.damage += 1;
      g.floatText(this.x, this.y, "УРОН +1 · +25 ◉", "#ffe384");
      g.burst(this.x, this.y, "#f9b34e", 25);
      g.sound.play("pick");
    }
  }
  update(dt, g) {
    this.y += this.speed * dt;
    this.flash = Math.max(0, this.flash - dt);
    if (this.y > CONFIG.playerY + 20) this.dead = true;
  }
  draw() {
    drawSupplyCrate(this.x, this.y, this.hp, this.flash);
  }
}
class WaveManager {
  constructor(g) {
    this.g = g;
    this.index = 0;
    this.spawned = 0;
    this.timer = 0;
    this.bossSpawned = false;
    this.crateSpawned = false;
    this.cleared = false;
  }
  get spec() {
    return CONFIG.waves[this.index];
  }
  update(dt) {
    if (this.cleared) return;
    const g = this.g;
    if (
      !this.crateSpawned &&
      this.spawned >= Math.ceil(this.spec.count * 0.3)
    ) {
      this.crateSpawned = true;
      g.enemies.push(new SupplyCrate(this.spec));
    }
    this.timer -= dt;
    if (this.spawned < this.spec.count && this.timer <= 0) {
      // Крупные пачки с первого кадра волны, а не очередь одиночных врагов.
      const batch = Math.min(
        this.spec.count - this.spawned,
        this.index < 2 ? 10 : 12,
      );
      this.timer = Math.max(0.65, 1.05 - this.index * 0.08);
      for (let i = 0; i < batch; i++) {
        const n = Math.random();
        const type =
          n < 0.22
            ? "fast"
            : n < 0.4
              ? "skeleton"
              : n < 0.57
                ? "armored"
                : n < 0.7 && this.index > 0
                  ? "shaman"
                  : "normal";
        const enemy = new Enemy(this.spec, type);
        enemy.x = clamp(
          120 + ((this.spawned * 71) % 300) + rand(-12, 12),
          110,
          430,
        );
        enemy.y = -15 - Math.floor(i / 4) * 28;
        g.enemies.push(enemy);
        this.spawned++;
      }
    }
    if (
      this.spec.boss &&
      !this.bossSpawned &&
      this.spawned >= Math.ceil(this.spec.count * 0.6)
    ) {
      this.bossSpawned = true;
      g.enemies.push(new Boss(this.spec));
      g.ui.toast(
        this.spec.bossKind === "lich"
          ? "АРХИЛИЧ ВОЗГЛАВИЛ ОРДУ"
          : "ОНИ · РАЗРУШИТЕЛЬ ВРАТ ПРИБЛИЖАЕТСЯ",
      );
    }
    if (this.spawned === this.spec.count && g.enemies.every((e) => e.dead)) {
      this.cleared = true;
      if (this.index === 4) g.end(true);
      else g.shop();
    }
  }
  next() {
    this.index++;
    this.spawned = 0;
    this.timer = 0;
    this.bossSpawned = false;
    this.crateSpawned = false;
    this.cleared = false;
  }
}
class UIScene {
  constructor(g) {
    this.g = g;
    this.toastTime = 0;
  }
  toast(text) {
    $("#toast").textContent = text;
    this.toastTime = 3;
  }
  update(dt) {
    this.toastTime -= dt;
    if (this.toastTime <= 0) $("#toast").textContent = "";
    const g = this.g;
    $("#combo").textContent =
      g.combo >= 3
        ? "СЕРИЯ ×" +
          g.combo +
          " · БОНУС +" +
          Math.min(3, Math.floor(g.combo / 5)) +
          " ◉"
        : "";
    $("#hearts").textContent = "♥ " + g.player.lives;
    $("#coins").textContent = "◉ " + g.coins;
    $("#wave").textContent = `Волна ${g.waves.index + 1}/5`;
    $("#army").textContent =
      `ОТРЯД ${g.player.army} · УРОН ${g.player.damage} · ${g.player.period.toFixed(2)} СЕК`;
    const boss = g.enemies.find((e) => e.type === "boss" && !e.dead);
    $("#bossname").textContent = boss ? boss.name : "";
    $("#bar").style.width =
      (boss
        ? boss.hp / boss.maxHp
        : clamp(
            (g.waves.spawned +
              (g.waves.bossSpawned ? 1 : 0) -
              g.enemies.filter((e) => !e.dead).length) /
              (g.waves.spec.count + (g.waves.spec.boss ? 1 : 0)),
            0,
            1,
          )) *
        100 +
      "%";
  }
  panel(html) {
    $("#overlay").innerHTML = html;
    $("#overlay").classList.remove("hidden");
  }
  hide() {
    $("#overlay").classList.add("hidden");
  }
}
class MenuScene {
  constructor(g) {
    this.g = g;
  }
  show() {
    this.g.state = "menu";
    this.g.ui.panel(
      '<div class="eyebrow">SENSEI GAMES · SHADOW PATH</div><div class="seal">⚔</div><h1>Последний<br><em>рубеж</em></h1><p>Прорывай орду. Собирай отряд.<br>Пять волн на тропе древнего храма.</p><button class="primary" id="play">В бой →</button><div class="hint">Веди пальцем по дороге · атака автоматическая<br>Два сердца и никакого рывка: прорыв стоит бойца<br>Победа даёт до 14 SenseiCoin · дневной лимит 30<br><b>Фарм намеренно жестокий: пятая волна решает всё.</b></div>',
    );
    $("#play").onclick = () => this.g.start();
  }
}
class GameScene {
  constructor() {
    this.sound = new Sound();
    this.keys = new Set();
    this.reset();
    this.ui = new UIScene(this);
    this.menu = new MenuScene(this);
    this.menu.show();
    this.bind();
    this.last = performance.now();
    requestAnimationFrame((t) => this.loop(t));
  }
  reset() {
    this.player = new Player();
    this.enemies = [];
    this.pickups = [];
    this.shots = [];
    this.hazards = [];
    this.gates = [];
    this.gateTimer = 0.8;
    this.gateSerial = 0;
    this.particles = [];
    this.waves = new WaveManager(this);
    this.coins = 0;
    this.kills = 0;
    this.time = 0;
    this.slow = 0;
    this.shake = 0;
    this.labels = [];
    this.combo = 0;
    this.comboTime = 0;
    this.resultSerial = 0;
  }
  start() {
    this.reset();
    this.resultSerial++;
    if (window.DojoEconomy) window.DojoEconomy.begin();
    this.state = "game";
    this.ui.hide();
    this.sound.play("pick");
    this.ui.toast("ЗАЩИТИ ДОДЗЁ · ВОЛНА 1");
  }
  bind() {
    const move = (e) => {
      if (this.state !== "game") return;
      const r = canvas.getBoundingClientRect();
      this.player.target = clamp(
        270 +
          (((e.clientX - r.left) / r.width) * 540 - 270) /
            project(270, CONFIG.playerY).scale,
        ...CONFIG.road,
      );
    };
    canvas.onpointerdown = (e) => {
      canvas.setPointerCapture(e.pointerId);
      move(e);
    };
    canvas.onpointermove = (e) => {
      if (e.buttons || e.pointerType === "touch") move(e);
    };
    window.addEventListener("keydown", (e) => {
      if (["ArrowLeft", "ArrowRight", " "].includes(e.key)) e.preventDefault();
      this.keys.add(e.key);
      if ((e.key === "Escape" || e.key === " ") && !e.repeat) this.pause();
    });
    window.addEventListener("keyup", (e) => this.keys.delete(e.key));
    window.addEventListener("blur", () => {
      this.keys.clear();
      if (this.state === "game") this.pause();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && this.state === "game") this.pause();
    });
    $("#pause").onclick = () => this.pause();
    $("#sound").onclick = () => {
      this.sound.on = !this.sound.on;
      $("#sound").textContent = this.sound.on ? "♪" : "×";
    };
  }
  pause() {
    if (this.state === "game") {
      this.state = "pause";
      this.ui.panel(
        '<div class="seal">Ⅱ</div><h1>Затишье<br><em>перед бурей</em></h1><p>Вдохни. Отряд ждёт твоего приказа.</p><button class="primary" id="resume">Продолжить бой</button><button class="secondary" id="restart">Начать заново</button>',
      );
      $("#resume").onclick = () => {
        this.state = "game";
        this.ui.hide();
      };
      $("#restart").onclick = () => this.start();
    } else if (this.state === "pause") {
      this.state = "game";
      this.ui.hide();
    }
  }
  shop() {
    // Между волнами не оставляем летящих заклинаний и снарядов.
    this.hazards = [];
    this.shots = [];
    this.gates = [];
    this.state = "shop";
    this.shopWait = CONFIG.shopSeconds;
    this.showShop();
  }
  showShop() {
    this.ui.panel(
      `<div class="eyebrow">ВОЛНА ${this.waves.index + 1} ПОКОРЕНА</div><div class="seal">⚒</div><h1>Привал<br><em>у кузнеца</em></h1><p>Отряд держит строй. Усиль его перед новой волной.<br>Кошелёк: <b>${this.coins} ◉</b></p><div class="shop">${[
        ["warrior", "⚔ Ещё один стрелок"],
        ["damage", "⚔ Урон армии +2"],
        ["speed", "✦ Скорость атак +10%"],
      ]
        .map(
          ([id, name]) =>
            `<button data-buy="${id}" ${this.coins < CONFIG.cost[id] || (id === "warrior" && this.player.army >= CONFIG.maxArmy) || (id === "speed" && this.player.period <= 0.16) ? "disabled" : ""}>${name}<small>${CONFIG.cost[id]} ◉</small></button>`,
        )
        .join(
          "",
        )}</div><button class="primary" id="next" ${this.shopWait > 0 ? "disabled" : ""}>${this.shopWait > 0 ? "Отдых · " + Math.ceil(this.shopWait) + " сек" : "Следующая волна →"}</button><div class="hint">Магазин не закрывается без твоего решения.</div>`,
    );
    document
      .querySelectorAll("[data-buy]")
      .forEach((b) => (b.onclick = () => this.buy(b.dataset.buy)));
    $("#next").onclick = () => {
      if (this.shopWait > 0) return;
      this.waves.next();
      this.state = "game";
      this.ui.hide();
      this.ui.toast("ВОЛНА " + (this.waves.index + 1));
    };
  }
  buy(type) {
    const price = CONFIG.cost[type];
    if (this.state !== "shop" || this.coins < price) return;
    if (
      (type === "warrior" && this.player.army >= CONFIG.maxArmy) ||
      (type === "speed" && this.player.period <= 0.16)
    )
      return;
    this.coins -= price;
    if (type === "warrior") this.player.army++;
    if (type === "damage") this.player.damage += 2;
    if (type === "speed")
      this.player.period = Math.max(0.16, this.player.period * 0.9);
    this.sound.play("pick");
    this.showShop();
  }
  end(win) {
    this.state = win ? "victory" : "defeat";
    const wave = this.waves.index + 1;
    const serial = ++this.resultSerial;
    this.ui.panel(
      `<div class="eyebrow">${win ? "ПЯТЬ ВОЛН · ОДНА ЛЕГЕНДА" : "ТВОЙ ПУТЬ ЕЩЁ НЕ ОКОНЧЕН"}</div><div class="seal">${win ? "🏆" : "⚔"}</div><h1>${win ? "Додзё<br><em>выстояло</em>" : "Последний<br><em>павший лист</em>"}</h1><p>${win ? "Стихия отступила. Стражи стали легендой." : "Даже великий воин однажды падает.<br>Встань и попробуй снова."}<br>Волна ${wave}/5 · Побеждено они: ${this.kills} · Монеты: ${this.coins}</p><div class="reward" id="dojo-reward">Считаем SenseiCoin…</div><button class="primary" id="again">Новый поход →</button>`,
    );
    $("#again").onclick = () => this.start();
    this.claimSenseiCoins(win, wave, serial);
  }
  claimSenseiCoins(win, wave, serial) {
    const slot = () => document.getElementById("dojo-reward");
    if (!window.DojoEconomy) {
      if (slot()) slot().textContent = "SenseiCoin: только внутри Telegram";
      return;
    }
    window.DojoEconomy.finish(wave, win)
      .then((result) => {
        if (serial !== this.resultSerial || !slot()) return;
        if (result?.coins !== undefined) {
          slot().classList.add("won");
          slot().textContent = `SenseiCoin +${result.coins} · сегодня ${result.daily_earned}/${result.daily_cap}`;
        } else {
          slot().textContent = `SenseiCoin: ${result?.error || "награда не выдана"}`;
        }
      })
      .catch(() => {
        if (serial === this.resultSerial && slot())
          slot().textContent = "SenseiCoin: сервер недоступен";
      });
  }
  burst(x, y, color, n) {
    for (let i = 0; i < n; i++)
      this.particles.push({
        x,
        y,
        vx: rand(-100, 100),
        vy: rand(-100, 100),
        life: 0.5,
        color,
      });
  }
  floatText(x, y, text, color) {
    this.labels.push({ x, y, text, color, life: 0.8 });
    if (this.labels.length > 65) this.labels.shift();
  }
  update(dt) {
    if (this.state === "shop") {
      const old = Math.ceil(this.shopWait);
      this.shopWait = Math.max(0, this.shopWait - dt);
      if (old !== Math.ceil(this.shopWait)) this.showShop();
      return;
    }
    if (this.state !== "game") return;
    this.time += dt;
    this.gateTimer -= dt;
    if (this.gateTimer <= 0) {
      this.gateTimer = CONFIG.gatePeriod;
      this.gates.push(
        new RecruitGate(
          this.gateSerial++ % 2 ? 430 : 110,
          80,
          this.gateSerial % 5 === 0 ? 3 : 1,
        ),
      );
    }
    for (const gate of this.gates) gate.update(dt, this);
    this.gates = this.gates.filter((g) => !g.dead);
    this.comboTime = Math.max(0, this.comboTime - dt);
    if (!this.comboTime) this.combo = 0;
    for (const l of this.labels) {
      l.y -= 28 * dt;
      l.life -= dt;
    }
    this.labels = this.labels.filter((l) => l.life > 0);
    this.slow = Math.max(0, this.slow - dt);
    if (this.keys.has("ArrowLeft") || this.keys.has("a"))
      this.player.target = clamp(this.player.target - 320 * dt, ...CONFIG.road);
    if (this.keys.has("ArrowRight") || this.keys.has("d"))
      this.player.target = clamp(this.player.target + 320 * dt, ...CONFIG.road);
    this.player.update(dt, this);
    for (const e of this.enemies) if (!e.dead) e.update(dt, this);
    for (const p of this.pickups) p.update(dt, this);
    this.enemies = this.enemies.filter((e) => !e.dead);
    this.pickups = this.pickups.filter((p) => !p.dead);
    for (const shot of this.shots) shot.update(dt, this);
    for (const bolt of this.hazards) bolt.update(dt, this);
    this.hazards = this.hazards.filter((b) => !b.dead);
    this.shots = this.shots.filter((shot) => !shot.dead);
    this.enemies = this.enemies.filter((e) => !e.dead);
    for (const p of this.particles) {
      p.life -= dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    this.particles = this.particles.filter((p) => p.life > 0);
    this.shake = Math.max(0, this.shake - dt * 25);
    if (this.player.lives <= 0 || this.player.army <= 0) {
      this.player.lives = Math.max(0, this.player.lives);
      this.end(false);
      return;
    }
    this.waves.update(dt);
  }
  loop(now) {
    const dt = Math.min(0.04, (now - this.last) / 1000);
    this.last = now;
    this.update(dt);
    this.draw();
    this.ui.update(this.state === "game" ? dt : 0);
    requestAnimationFrame((t) => this.loop(t));
  }
  draw() {
    if (window.dojoRenderer) {
      window.dojoRenderer.render(this);
      return;
    }
    ctx.save();
    ctx.translate(rand(-this.shake, this.shake), rand(-this.shake, this.shake));
    background(this.time);
    for (const e of this.enemies) {
      const warning = e.type === "boss" ? e.warning : e.castWarning;
      if (warning > 0) {
        const x = e.type === "boss" ? e.attackX : e.castX;
        ctx.fillStyle =
          e.kind === "lich" || e.type === "shaman" ? "#b66bff30" : "#ff485b35";
        lanePath(x, e.type === "boss" ? 62 : 28, e.y, CONFIG.playerY + 35);
        ctx.fill();
        ctx.strokeStyle =
          e.kind === "lich" || e.type === "shaman" ? "#cd8bff" : "#ff6b72";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
    for (const gate of this.gates)
      worldDraw(gate.x, gate.y, () => gate.draw(this.time));
    for (const p of this.pickups) worldDraw(p.x, p.y, () => p.draw(this.time));
    for (const e of [...this.enemies].sort((a, b) => a.y - b.y))
      worldDraw(e.x, e.y, () => e.draw(this.time));
    this.player.draw(this.time);
    for (const bolt of this.hazards)
      worldDraw(bolt.x, bolt.y, () => bolt.draw(this.time));
    for (const shot of this.shots)
      worldDraw(shot.x, shot.y, () => shot.draw(this.time));
    for (const l of this.labels) {
      ctx.save();
      ctx.globalAlpha = Math.min(1, l.life * 3);
      ctx.textAlign = "center";
      ctx.font = "bold 15px system-ui";
      ctx.shadowColor = "#000";
      ctx.shadowBlur = 3;
      ctx.fillStyle = l.color;
      const pos = project(l.x, l.y);
      ctx.fillText(l.text, pos.x, pos.y);
      ctx.restore();
    }
    for (const p of this.particles) {
      ctx.globalAlpha = p.life * 2;
      ctx.fillStyle = p.color;
      const pos = project(p.x, p.y);
      ctx.fillRect(pos.x, pos.y, 3 * pos.scale, 3 * pos.scale);
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }
}
// Рисованные объёмные фигурки: тени, градиенты и слои без внешних ассетов.
// Векторные значки не требуют системного набора emoji.
function drawPickupIcon(type, x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.strokeStyle = "#372635";
  ctx.fillStyle = "#372635";
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  if (type === "sword") {
    ctx.moveTo(-8, 10);
    ctx.lineTo(9, -10);
    ctx.moveTo(-7, 0);
    ctx.lineTo(1, 7);
    ctx.moveTo(-8, 10);
    ctx.lineTo(-12, 14);
    ctx.stroke();
  }
  if (type === "star") {
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4;
      const r = i % 2 ? 4 : 14;
      const px = Math.cos(a) * r,
        py = Math.sin(a) * r;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    ellipse(0, 0, 2, 2, "#bcecff");
  }
  if (type === "heart") {
    ctx.fillRect(-4, -12, 8, 24);
    ctx.fillRect(-12, -4, 24, 8);
  }
  if (type === "slow") {
    ctx.moveTo(-9, -12);
    ctx.lineTo(9, -12);
    ctx.lineTo(4, -4);
    ctx.lineTo(-4, 4);
    ctx.lineTo(-9, 12);
    ctx.lineTo(9, 12);
    ctx.lineTo(4, 4);
    ctx.lineTo(-4, -4);
    ctx.closePath();
    ctx.stroke();
  }
  if (type === "army") {
    for (const a of [-7, 7]) {
      ctx.moveTo(a, 11);
      ctx.lineTo(a, -10);
      ctx.moveTo(a - 4, -5);
      ctx.lineTo(a, -10);
      ctx.lineTo(a + 4, -5);
    }
    ctx.stroke();
  }
  if (type === "coin") {
    ctx.arc(0, 0, 11, 0, 7);
    ctx.stroke();
    ctx.fillRect(-2, -7, 4, 14);
    ctx.fillRect(-6, -2, 12, 4);
  }
  ctx.restore();
}
function ellipse(x, y, rx, ry, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, 7);
  ctx.fill();
}
// Слоистые миниатюры: оружие, ламеллярные доспехи, блики и контактные тени.
function samurai(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(1.2, 1.2);
  warrior(0, 0, 0, true);
  ctx.restore();
}
function warrior(x, y, bob, leader = false) {
  ctx.save();
  ctx.translate(x, y + bob);
  ellipse(7, 21, 14, 5, "#33465544");
  ctx.strokeStyle = leader ? "#d6ff8f" : "#92ff82";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(0, 19, 12, 5, 0, 0, 7);
  ctx.stroke();
  ctx.fillStyle = "#354b69";
  ctx.fillRect(-7, 7, 6, 12);
  ctx.fillRect(2, 7, 6, 12);
  ctx.fillStyle = "#f5f4eb";
  ctx.fillRect(-8, 16, 7, 4);
  ctx.fillRect(2, 16, 7, 4);
  const jacket = ctx.createLinearGradient(-10, -5, 10, 12);
  jacket.addColorStop(0, "#7af4f9");
  jacket.addColorStop(0.6, "#17a4ca");
  jacket.addColorStop(1, "#176ba2");
  ellipse(0, 1, 10, 12, jacket);
  ctx.fillStyle = "#ff554f";
  ctx.fillRect(-9, 5, 18, 5);
  ctx.fillStyle = "#fff6c5";
  ctx.fillRect(-2, -5, 4, 12);
  ellipse(-9, 0, 4, 6, "#efc899");
  ellipse(9, 0, 4, 6, "#efc899");
  ellipse(0, -14, 7, 8, "#dcae85");
  ellipse(0, -20, 7, 6, leader ? "#f0bb3a" : "#253446");
  ctx.fillStyle = "#172c48";
  ctx.fillRect(-6, -15, 12, 3);
  ctx.strokeStyle = "#dba927";
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(8, 0);
  ctx.lineTo(9, -17);
  ctx.stroke();
  ctx.strokeStyle = "#fff6b2";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(9, -13);
  ctx.lineTo(9, -23);
  ctx.stroke();
  ctx.restore();
}
function drawRecruitGate(x, y, value) {
  ellipse(x + 10, y + 12, 30, 8, "#263c5140");
  ctx.fillStyle = "#edac39";
  ctx.fillRect(x - 32, y - 65, 5, 77);
  ctx.fillRect(x + 27, y - 65, 5, 77);
  const panel = ctx.createLinearGradient(x, y - 65, x, y);
  panel.addColorStop(0, "#46e6fd");
  panel.addColorStop(0.6, "#15aee5");
  panel.addColorStop(1, "#1678d2");
  ctx.fillStyle = panel;
  ctx.fillRect(x - 26, y - 62, 52, 60);
  ctx.strokeStyle = "#b4ffff";
  ctx.lineWidth = 2;
  ctx.strokeRect(x - 26, y - 62, 52, 60);
  ctx.font = "900 30px system-ui";
  ctx.textAlign = "center";
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#173e70";
  ctx.strokeText("+" + value, x, y - 20);
  ctx.fillStyle = "#fff";
  ctx.fillText("+" + value, x, y - 20);
}
function drawSupplyCrate(x, y, hp, flash) {
  ellipse(x + 8, y + 22, 34, 10, "#26354533");
  ctx.fillStyle = flash ? "#fff6c2" : "#a5662c";
  ctx.fillRect(x - 30, y - 21, 60, 42);
  ctx.fillStyle = "#edb25d";
  ctx.beginPath();
  ctx.moveTo(x - 30, y - 21);
  ctx.lineTo(x - 18, y - 34);
  ctx.lineTo(x + 40, y - 34);
  ctx.lineTo(x + 30, y - 21);
  ctx.fill();
  ctx.fillStyle = "#c38842";
  ctx.beginPath();
  ctx.moveTo(x + 30, y - 21);
  ctx.lineTo(x + 40, y - 34);
  ctx.lineTo(x + 40, y + 9);
  ctx.lineTo(x + 30, y + 21);
  ctx.fill();
  ctx.strokeStyle = "#644827";
  ctx.lineWidth = 2;
  for (const d of [-12, 2, 15]) {
    ctx.beginPath();
    ctx.moveTo(x - 30, y + d);
    ctx.lineTo(x + 30, y + d);
    ctx.stroke();
  }
  ctx.fillStyle = "#e3e7dc";
  ctx.fillRect(x - 18, y - 23, 5, 45);
  ctx.fillRect(x + 13, y - 23, 5, 45);
  ctx.font = "900 27px system-ui";
  ctx.textAlign = "center";
  ctx.strokeStyle = "#412b25";
  ctx.lineWidth = 4;
  ctx.strokeText(Math.max(0, Math.ceil(hp)), x, y + 10);
  ctx.fillStyle = "#fff";
  ctx.fillText(Math.max(0, Math.ceil(hp)), x, y + 10);
}
function drawMonster(x, y, r, type, flash) {
  if (type === "fast") {
    spider(x, y, r, flash);
    return;
  }
  if (type === "skeleton") {
    skeleton(x, y, r, flash);
    return;
  }
  if (type === "shaman") {
    lich(x, y, r, flash);
    return;
  }
  if (type === "armored") {
    golem(x, y, r, flash);
    return;
  }
  boar(x, y, r, type, flash);
}
function spider(x, y, r, flash) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(r / 22, r / 22);
  ellipse(0, 13, 28, 7, "#0a061b66");
  for (const side of [-1, 1])
    for (let i = 0; i < 4; i++) {
      const j = i - 1.5;
      ctx.strokeStyle = "#282637";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(side * 8, j * 6);
      ctx.lineTo(side * (23 + Math.abs(j) * 3), j * 13);
      ctx.lineTo(side * 34, j * 16 + 10);
      ctx.stroke();
      ctx.strokeStyle = "#a778b9";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  const body = ctx.createRadialGradient(-4, -6, 1, 0, 0, 21);
  body.addColorStop(0, flash ? "#fff8d8" : "#ac5ea0");
  body.addColorStop(1, "#30233f");
  ellipse(0, -7, 16, 19, body);
  ellipse(0, 9, 13, 10, "#41314e");
  for (let i = 0; i < 4; i++) ellipse(-8 + i * 5, 8, 2, 3, "#ff8c8d");
  ctx.strokeStyle = "#e8c0e8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-6, 15);
  ctx.lineTo(-9, 22);
  ctx.moveTo(6, 15);
  ctx.lineTo(9, 22);
  ctx.stroke();
  ctx.restore();
}
function skeleton(x, y, r, flash) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(r / 22, r / 22);
  ellipse(0, 25, 18, 5, "#0006");
  ctx.strokeStyle = flash ? "#fff" : "#d0cbb2";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(0, -4);
  ctx.lineTo(0, 15);
  ctx.moveTo(-11, -1);
  ctx.lineTo(11, -1);
  ctx.moveTo(-9, 4);
  ctx.lineTo(9, 4);
  ctx.moveTo(-7, 9);
  ctx.lineTo(7, 9);
  ctx.moveTo(0, 14);
  ctx.lineTo(-8, 25);
  ctx.moveTo(0, 14);
  ctx.lineTo(9, 25);
  ctx.moveTo(-10, 0);
  ctx.lineTo(-17, 13);
  ctx.moveTo(10, 0);
  ctx.lineTo(19, -10);
  ctx.stroke();
  ellipse(0, -15, 12, 13, flash ? "#fff9e1" : "#d3cdb7");
  ellipse(-5, -17, 3, 4, "#302a3a");
  ellipse(5, -17, 3, 4, "#302a3a");
  ctx.fillStyle = "#75dfb6";
  ctx.fillRect(-6, -18, 2, 2);
  ctx.fillRect(4, -18, 2, 2);
  ctx.fillStyle = "#9c4850";
  ctx.fillRect(-11, -27, 22, 5);
  ctx.strokeStyle = "#eff5f4";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(17, -3);
  ctx.lineTo(23, -30);
  ctx.stroke();
  ctx.restore();
}
function golem(x, y, r, flash) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(r / 26, r / 26);
  ellipse(0, 27, 31, 9, "#0006");
  const stone = ctx.createLinearGradient(-25, -20, 25, 20);
  stone.addColorStop(0, flash ? "#fff5df" : "#a3a4ae");
  stone.addColorStop(0.4, "#606c7d");
  stone.addColorStop(1, "#30374d");
  for (const [x, y, w, h] of [
    [-23, 12, 16, 21],
    [8, 12, 16, 21],
    [-23, -18, 46, 39],
    [-40, -13, 17, 30],
    [24, -13, 17, 30],
    [-14, -37, 28, 25],
  ]) {
    ctx.fillStyle = stone;
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#282b43";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.strokeStyle = "#b6bec577";
    ctx.beginPath();
    ctx.moveTo(x + 2, y + 2);
    ctx.lineTo(x + w - 3, y + 2);
    ctx.stroke();
  }
  ctx.strokeStyle = "#9bf1d5";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-4, -13);
  ctx.lineTo(6, -2);
  ctx.lineTo(-2, 5);
  ctx.lineTo(4, 15);
  ctx.stroke();
  ctx.fillStyle = "#b5ffe6";
  ctx.fillRect(-10, -28, 7, 3);
  ctx.fillRect(3, -28, 7, 3);
  ctx.restore();
}
function lich(x, y, r, flash) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(r / 30, r / 30);
  ellipse(0, 29, 27, 7, "#09061c66");
  const robe = ctx.createLinearGradient(-24, -10, 28, 35);
  robe.addColorStop(0, flash ? "#f9e8ff" : "#b47edc");
  robe.addColorStop(0.5, "#57447e");
  robe.addColorStop(1, "#201f3f");
  ctx.fillStyle = robe;
  ctx.beginPath();
  ctx.moveTo(-12, -16);
  ctx.lineTo(12, -16);
  ctx.lineTo(29, 28);
  ctx.lineTo(10, 23);
  ctx.lineTo(0, 32);
  ctx.lineTo(-11, 25);
  ctx.lineTo(-29, 29);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "#bba2d0";
  ctx.lineWidth = 2;
  ctx.stroke();
  ellipse(0, -21, 16, 18, robe);
  ellipse(0, -20, 10, 11, "#20182f");
  ctx.fillStyle = "#f0d9bd";
  ctx.fillRect(-8, -19, 16, 9);
  ctx.fillStyle = "#d184ff";
  ctx.fillRect(-7, -20, 4, 3);
  ctx.fillRect(3, -20, 4, 3);
  ctx.strokeStyle = "#8573a1";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(27, 28);
  ctx.lineTo(30, -39);
  ctx.stroke();
  ctx.shadowColor = "#b565ff";
  ctx.shadowBlur = 16;
  ellipse(30, -42, 8, 11, "#ba83f5");
  ellipse(28, -45, 3, 4, "#fff1ff");
  ctx.restore();
}
function boar(x, y, r, type, flash) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(r / 30, r / 30);
  const armored = type === "armored",
    boss = type === "boss",
    fast = type === "fast";
  ellipse(0, 30, 34, 10, "#100b1877");
  // Булава и руки читаются по силуэту даже в маленьком масштабе.
  ctx.save();
  ctx.translate(-34, 5);
  ctx.rotate(-0.45);
  ctx.fillStyle = "#7b5841";
  ctx.fillRect(-3, -13, 6, 43);
  ellipse(0, 25, 9, 13, "#34303e");
  ctx.strokeStyle = "#ad9b8a";
  ctx.lineWidth = 2;
  for (let i = 0; i < 4; i++) {
    ctx.beginPath();
    ctx.moveTo(-11, 17 + i * 6);
    ctx.lineTo(11, 17 + i * 6);
    ctx.stroke();
  }
  ctx.restore();
  ctx.fillStyle = "#24232c";
  ctx.fillRect(-24, 18, 16, 18);
  ctx.fillRect(9, 18, 16, 18);
  ctx.fillStyle = "#7b5345";
  ctx.fillRect(-25, 31, 18, 5);
  ctx.fillRect(9, 31, 18, 5);
  const body = ctx.createLinearGradient(-30, -15, 30, 28);
  body.addColorStop(0, armored ? "#8893a2" : "#9c5149");
  body.addColorStop(0.45, armored ? "#434853" : "#50323d");
  body.addColorStop(1, "#25212d");
  ellipse(0, 9, 29, 24, body);
  ellipse(-29, 7, 10, 15, body);
  ellipse(29, 7, 10, 15, body);
  ctx.strokeStyle = boss ? "#e5b65d" : "#9a7c66";
  ctx.lineWidth = 2;
  for (let row = 0; row < 3; row++) {
    ctx.fillStyle = armored ? "#414954" : "#342a35";
    ctx.fillRect(-24, 5 + row * 7, 48, 6);
    ctx.strokeRect(-24, 5 + row * 7, 48, 6);
    for (let col = -19; col < 23; col += 8) {
      ctx.fillStyle = "#c69a6c";
      ctx.fillRect(col, 7 + row * 7, 2, 2);
    }
  }
  for (const side of [-1, 1]) {
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.moveTo(side * 17, -19);
    ctx.lineTo(side * 24, -39);
    ctx.lineTo(side * 30, -16);
    ctx.fill();
    ctx.stroke();
  }
  const face = ctx.createRadialGradient(-9, -20, 1, 0, -9, 30);
  face.addColorStop(0, flash ? "#fff5c7" : fast ? "#bd9365" : "#b86d5c");
  face.addColorStop(1, "#4a2935");
  ellipse(0, -10, 24, 24, face);
  // Ирокез и красная повязка.
  ctx.fillStyle = "#211e2a";
  for (let i = -3; i <= 3; i++) {
    ctx.beginPath();
    ctx.moveTo(i * 5, -29);
    ctx.lineTo(i * 5 + 3, -40 + Math.abs(i) * 2);
    ctx.lineTo(i * 5 + 7, -27);
    ctx.fill();
  }
  ctx.fillStyle = fast ? "#4d846d" : "#b52f40";
  ctx.fillRect(-23, -25, 46, 6);
  ctx.fillStyle = "#2c1a25";
  ctx.beginPath();
  ctx.moveTo(-19, -16);
  ctx.lineTo(-5, -12);
  ctx.lineTo(-7, -7);
  ctx.lineTo(-19, -10);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(19, -16);
  ctx.lineTo(5, -12);
  ctx.lineTo(7, -7);
  ctx.lineTo(19, -10);
  ctx.fill();
  ctx.fillStyle = "#ffe19a";
  ctx.fillRect(-16, -12, 8, 3);
  ctx.fillRect(8, -12, 8, 3);
  ellipse(0, 4, 13, 9, "#d7977a");
  ellipse(-5, 4, 3, 4, "#552f3a");
  ellipse(5, 4, 3, 4, "#552f3a");
  ctx.fillStyle = "#ffe3ab";
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(side * 12, 9);
    ctx.quadraticCurveTo(side * 27, 9, side * 20, -9);
    ctx.quadraticCurveTo(side * 18, 3, side * 10, 4);
    ctx.fill();
  }
  if (armored || boss) {
    ctx.fillStyle = "#343642";
    ctx.strokeStyle = "#d0aa67";
    ctx.lineWidth = 2;
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(side * 24, -7);
      ctx.lineTo(side * 40, -1);
      ctx.lineTo(side * 38, 12);
      ctx.lineTo(side * 26, 9);
      ctx.fill();
      ctx.stroke();
    }
    if (boss) {
      ctx.beginPath();
      ctx.arc(0, -24, 25, Math.PI, Math.PI * 2);
      ctx.stroke();
    }
  }
  if (flash) {
    ctx.globalAlpha = 0.25;
    ellipse(0, 0, 30, 36, "#fff3c9");
  }
  ctx.restore();
}
// Декорации детерминированы: каменная тропа, огни, сакура, ворота.
const scenery = document.createElement("canvas");
scenery.width = 540;
scenery.height = 960;
function makeScenery() {
  const c = scenery.getContext("2d");
  c.fillStyle = "#182231";
  c.fillRect(0, 0, 540, 960);
  const quad = (points, color) => {
    c.fillStyle = color;
    c.beginPath();
    points.forEach((p, i) => (i ? c.lineTo(p.x, p.y) : c.moveTo(p.x, p.y)));
    c.closePath();
    c.fill();
  };
  quad(
    [
      project(65, -100),
      project(475, -100),
      project(475, 1000),
      project(65, 1000),
    ],
    "#47434a",
  );
  for (let y = -100; y < 1050; y += 42)
    for (let col = 0; col < 9; col++) {
      const x = 65 + col * 45 + (Math.floor(y / 42) % 2) * 6;
      quad(
        [
          project(x, y),
          project(x + 43, y),
          project(x + 43, y + 40),
          project(x, y + 40),
        ],
        ["#5a5560", "#655c60", "#4c5357"][
          Math.abs(col + Math.floor(y / 42)) % 3
        ],
      );
    }
  for (const side of [-1, 1])
    for (let y = -50; y < 1050; y += 130) {
      const p = project(side < 0 ? 42 : 498, y),
        k = p.scale;
      c.fillStyle = "#50303c";
      c.fillRect(p.x - 4 * k, p.y - 150 * k, 8 * k, 150 * k);
      c.fillStyle = "#a02849";
      c.fillRect(p.x - 24 * k, p.y - 135 * k, 48 * k, 85 * k);
      c.fillStyle = "#ecd3a0";
      c.font = `bold ${30 * k}px serif`;
      c.textAlign = "center";
      c.fillText("侍", p.x, p.y - 85 * k);
      c.fillStyle = "#b14d86";
      for (let n = 0; n < 16; n++) {
        c.beginPath();
        c.arc(
          p.x + Math.sin(n * 7) * 45 * k,
          p.y - 170 * k + Math.cos(n * 3) * 30 * k,
          (8 + (n % 4)) * k,
          0,
          Math.PI * 2,
        );
        c.fill();
      }
      c.fillStyle = "#ffc77c";
      c.shadowColor = "#ffb84c";
      c.shadowBlur = 12;
      c.fillRect(p.x - 6 * k, p.y - 26 * k, 12 * k, 18 * k);
      c.shadowBlur = 0;
    }
}
makeScenery();
function background(t) {
  ctx.drawImage(scenery, 0, 0);
  ctx.fillStyle = "#f9b5d5aa";
  for (let i = 0; i < 24; i++) {
    const x = (i * 83 + Math.sin(t + i) * 25) % 540,
      y = (i * 137 + t * 17) % 960;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(t + i);
    ctx.fillRect(-2, -1, 5, 3);
    ctx.restore();
  }
}
const game = new GameScene();
