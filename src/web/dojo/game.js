"use strict";
// Все игровые величины заданы в логических координатах 540 × 960.
const CONFIG = {
  width: 540,
  height: 960,
  road: [90, 450],
  playerY: 755,
  lives: 3,
  army: 6,
  damage: 9,
  attackPeriod: 0.65,
  range: 230,
  enemySpeed: 30,
  dropChance: 0.37,
  slowSeconds: 5,
  shopSeconds: 4,
  cost: { hedgehog: 50, damage: 75, speed: 75 },
  waves: [
    { count: 10, hp: 20, speed: 1 },
    { count: 15, hp: 26, speed: 1.13 },
    { count: 18, hp: 30, speed: 1.2, boss: 650 },
    { count: 23, hp: 38, speed: 1.36 },
    { count: 25, hp: 44, speed: 1.48, boss: 1100 },
  ],
};
const canvas = document.querySelector("#game"),
  ctx = canvas.getContext("2d");
const $ = (s) => document.querySelector(s),
  clamp = (x, a, b) => Math.max(a, Math.min(b, x)),
  rand = (a, b) => a + Math.random() * (b - a);
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
        .sort((a, b) => b.y - a.y);
      if (targets.length) {
        this.cooldown = this.period;
        for (let i = 0; i < this.army; i++) {
          const e = targets[i % targets.length];
          if (!e.dead) {
            g.shots.push({
              x: this.x + ((i % 5) - 2) * 15,
              y: this.y + 35,
              tx: e.x,
              ty: e.y,
              life: 0.22,
            });
            e.hit(this.damage, g);
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
      hedgehog(x, y, Math.sin(t * 6 + i) * 1.5);
    }
    samurai(this.x, this.y);
  }
}
class Enemy {
  constructor(wave, type = "normal") {
    this.type = type;
    this.x = rand(110, 430);
    this.y = -45;
    this.maxHp =
      wave.hp * (type === "armored" ? 3 : type === "fast" ? 0.55 : 1);
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
    this.hp -= d;
    this.flash = 0.12;
    if (this.hp <= 0 && !this.dead) {
      this.dead = true;
      g.coins += this.type === "boss" ? 60 : 9;
      g.kills++;
      g.burst(this.x, this.y, "#ffcf7c", 12);
      g.sound.play("kill");
      if (Math.random() < CONFIG.dropChance || this.type === "boss")
        g.pickups.push(new Pickup(this.x, this.y));
    }
  }
  update(dt, g) {
    this.y += this.speed * dt * (g.slow > 0 ? 0.42 : 1);
    this.flash = Math.max(0, this.flash - dt);
    if (this.y > CONFIG.playerY + 12) {
      this.dead = true;
      g.player.lives--;
      g.shake = 9;
      g.sound.play("hurt");
      g.burst(this.x, this.y, "#ef6475", 16);
    }
  }
  draw(t) {
    boar(
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
    this.maxHp = this.hp = w.boss;
    this.r = 48;
    this.speed = 16 * w.speed;
    this.charge = 4;
    this.warning = 0;
    this.attackX = 270;
  }
  update(dt, g) {
    super.update(dt, g);
    this.y = Math.min(500, this.y);
    this.x = 270 + Math.sin(g.time * 0.55) * 120;
    this.charge -= dt;
    if (this.charge <= 0 && this.warning <= 0) {
      this.warning = 1.25;
      this.attackX = g.player.x;
      g.ui.toast("⚠ Вождь замахивается — уходи с красной линии!");
    }
    if (this.warning > 0) {
      this.warning -= dt;
      if (this.warning <= 0) {
        this.charge = 4;
        if (Math.abs(g.player.x - this.attackX) < 62) {
          g.player.army = Math.max(0, g.player.army - 2);
          g.shake = 12;
          g.sound.play("hurt");
        }
        g.burst(this.attackX, CONFIG.playerY, "#ff5e61", 25);
      }
    }
  }
  draw(t) {
    if (this.warning > 0) {
      ctx.fillStyle = `rgba(255,60,75,${0.13 + 0.12 * Math.sin(t * 25)})`;
      ctx.fillRect(
        this.attackX - 62,
        this.y,
        124,
        CONFIG.playerY - this.y + 45,
      );
      ctx.strokeStyle = "#ff636c";
      ctx.strokeRect(this.attackX - 62, CONFIG.playerY - 35, 124, 80);
    }
    super.draw(t);
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
          p.lives = Math.min(3, p.lives + 1);
          break;
        case "slow":
          g.slow = CONFIG.slowSeconds;
          break;
        case "army":
          p.army = Math.min(24, p.army + 1);
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
          army: "Ёж вступил в отряд",
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
class WaveManager {
  constructor(g) {
    this.g = g;
    this.index = 0;
    this.spawned = 0;
    this.timer = 1;
    this.bossSpawned = false;
    this.cleared = false;
  }
  get spec() {
    return CONFIG.waves[this.index];
  }
  update(dt) {
    if (this.cleared) return;
    const g = this.g;
    this.timer -= dt;
    if (this.spawned < this.spec.count && this.timer <= 0) {
      this.spawned++;
      this.timer = Math.max(0.6, 1.55 - this.index * 0.14);
      const n = Math.random();
      g.enemies.push(
        new Enemy(this.spec, n < 0.2 ? "fast" : n < 0.4 ? "armored" : "normal"),
      );
    }
    if (
      this.spec.boss &&
      !this.bossSpawned &&
      this.spawned >= Math.ceil(this.spec.count * 0.6)
    ) {
      this.bossSpawned = true;
      g.enemies.push(new Boss(this.spec));
      g.ui.toast("👹 ВОЖДЬ ОНИ ВСТУПАЕТ В БОЙ");
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
    this.timer = 1;
    this.bossSpawned = false;
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
    $("#hearts").textContent = "♥ " + g.player.lives;
    $("#coins").textContent = "◉ " + g.coins;
    $("#wave").textContent = `Волна ${g.waves.index + 1}/5`;
    $("#army").textContent =
      `ОТРЯД ${g.player.army} · УРОН ${g.player.damage} · ${g.player.period.toFixed(2)} СЕК`;
    const boss = g.enemies.find((e) => e.type === "boss" && !e.dead);
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
      '<div class="eyebrow">SENSEI GAMES · 生き残れ</div><div class="seal">道場</div><h1>Последний<br><em>рубеж</em></h1><p>Один самурай. Отряд верных ежей.<br>Пять волн, чтобы защитить додзё.</p><button class="primary" id="play">В бой →</button><div class="hint">Веди пальцем по дороге · атака автоматическая<br>Монеты только игровые, без выплат и ставок.</div>',
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
    this.particles = [];
    this.waves = new WaveManager(this);
    this.coins = 0;
    this.kills = 0;
    this.time = 0;
    this.slow = 0;
    this.shake = 0;
  }
  start() {
    this.reset();
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
        ((e.clientX - r.left) / r.width) * 540,
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
  }
  pause() {
    if (this.state === "game") {
      this.state = "pause";
      this.ui.panel(
        '<div class="seal">休</div><h1>Затишье<br><em>перед бурей</em></h1><p>Вдохни. Отряд ждёт твоего приказа.</p><button class="primary" id="resume">Продолжить бой</button><button class="secondary" id="restart">Начать заново</button>',
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
    this.state = "shop";
    this.shopWait = CONFIG.shopSeconds;
    this.showShop();
  }
  showShop() {
    this.ui.panel(
      `<div class="eyebrow">ВОЛНА ${this.waves.index + 1} ПОКОРЕНА</div><div class="seal">鍛</div><h1>Привал<br><em>у кузнеца</em></h1><p>Отряд держит строй. Усиль его перед новой волной.<br>Кошелёк: <b>${this.coins} ◉</b></p><div class="shop">${[
        ["hedgehog", "🦔 Ещё один воин"],
        ["damage", "⚔ Урон армии +2"],
        ["speed", "✦ Скорость атак +10%"],
      ]
        .map(
          ([id, name]) =>
            `<button data-buy="${id}" ${this.coins < CONFIG.cost[id] || (id === "hedgehog" && this.player.army >= 24) || (id === "speed" && this.player.period <= 0.16) ? "disabled" : ""}>${name}<small>${CONFIG.cost[id]} ◉</small></button>`,
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
      (type === "hedgehog" && this.player.army >= 24) ||
      (type === "speed" && this.player.period <= 0.16)
    )
      return;
    this.coins -= price;
    if (type === "hedgehog") this.player.army++;
    if (type === "damage") this.player.damage += 2;
    if (type === "speed")
      this.player.period = Math.max(0.16, this.player.period * 0.9);
    this.sound.play("pick");
    this.showShop();
  }
  end(win) {
    this.state = win ? "victory" : "defeat";
    this.ui.panel(
      `<div class="eyebrow">${win ? "ПЯТЬ ВОЛН · ОДНА ЛЕГЕНДА" : "ТВОЙ ПУТЬ ЕЩЁ НЕ ОКОНЧЕН"}</div><div class="seal">${win ? "勝" : "忍"}</div><h1>${win ? "Додзё<br><em>выстояло</em>" : "Последний<br><em>павший лист</em>"}</h1><p>${win ? "Стихия отступила. Ежи стали легендой." : "Даже великий воин однажды падает.<br>Встань и попробуй снова."}<br>Побеждено они: ${this.kills} · Монеты: ${this.coins}</p><button class="primary" id="again">Новый поход →</button>`,
    );
    $("#again").onclick = () => this.start();
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
  update(dt) {
    if (this.state === "shop") {
      const old = Math.ceil(this.shopWait);
      this.shopWait = Math.max(0, this.shopWait - dt);
      if (old !== Math.ceil(this.shopWait)) this.showShop();
      return;
    }
    if (this.state !== "game") return;
    this.time += dt;
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
    for (const s of this.shots) s.life -= dt;
    this.shots = this.shots.filter((s) => s.life > 0);
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
    ctx.save();
    ctx.translate(rand(-this.shake, this.shake), rand(-this.shake, this.shake));
    background(this.time);
    for (const p of this.pickups) p.draw(this.time);
    for (const e of [...this.enemies].sort((a, b) => a.y - b.y))
      e.draw(this.time);
    this.player.draw(this.time);
    for (const s of this.shots) {
      ctx.strokeStyle = this.player.shuriken ? "#8edaff" : "#ffdba2";
      ctx.lineWidth = 2;
      const t = 1 - s.life / 0.22;
      ctx.beginPath();
      ctx.moveTo(s.x + (s.tx - s.x) * t, s.y + (s.ty - s.y) * t);
      ctx.lineTo(
        s.x + (s.tx - s.x) * Math.min(1, t + 0.18),
        s.y + (s.ty - s.y) * Math.min(1, t + 0.18),
      );
      ctx.stroke();
    }
    for (const p of this.particles) {
      ctx.globalAlpha = p.life * 2;
      ctx.fillStyle = p.color;
      ctx.fillRect(p.x, p.y, 3, 3);
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
function samurai(x, y) {
  ellipse(x, y + 23, 22, 7, "#0007");
  ctx.fillStyle = "#211e29";
  ctx.fillRect(x - 12, y - 4, 24, 25);
  ctx.fillStyle = "#c14245";
  ctx.fillRect(x - 14, y + 6, 28, 6);
  ctx.fillRect(x - 23, y + 7, 12, 5);
  ellipse(x, y - 10, 11, 12, "#181922");
  ctx.fillStyle = "#d8ae70";
  ctx.beginPath();
  ctx.moveTo(x - 27, y - 12);
  ctx.lineTo(x, y - 32);
  ctx.lineTo(x + 27, y - 12);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "#ffe1a2";
  ctx.stroke();
  ctx.strokeStyle = "#d8e1e8";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x + 10, y + 12);
  ctx.lineTo(x + 31, y - 8);
  ctx.stroke();
}
function hedgehog(x, y, bob) {
  y += bob;
  ellipse(x, y + 10, 12, 5, "#0005");
  ellipse(x, y, 12, 13, "#684538");
  ctx.fillStyle = "#bb9871";
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(x + Math.cos(a) * 8, y + Math.sin(a) * 9);
    ctx.lineTo(x + Math.cos(a + 0.2) * 15, y + Math.sin(a + 0.2) * 16);
    ctx.lineTo(x + Math.cos(a + 0.4) * 8, y + Math.sin(a + 0.4) * 9);
    ctx.fill();
  }
  ctx.fillStyle = "#bd4249";
  ctx.fillRect(x - 12, y + 3, 24, 4);
  ellipse(x, y + 7, 6, 5, "#d3ab82");
}
function boar(x, y, r, type, flash) {
  ctx.save();
  ctx.translate(x, y);
  ellipse(0, r * 0.8, r * 0.9, r * 0.25, "#0005");
  const body = ctx.createRadialGradient(-r * 0.3, -r * 0.4, 1, 0, 0, r);
  body.addColorStop(
    0,
    flash
      ? "#fff4c3"
      : type === "armored"
        ? "#8893a1"
        : type === "fast"
          ? "#a17950"
          : "#ac534b",
  );
  body.addColorStop(1, type === "armored" ? "#303541" : "#45272f");
  ellipse(0, 0, r * 0.9, r, body);
  ctx.fillStyle = "#2a2330";
  ctx.fillRect(-r * 0.9, r * 0.4, r * 0.6, r * 0.55);
  ctx.fillRect(r * 0.3, r * 0.4, r * 0.6, r * 0.55);
  ctx.fillStyle = "#e0b17e";
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(side * r * 0.4, -r * 0.55);
    ctx.lineTo(side * r * 0.8, -r * 1.2);
    ctx.lineTo(side * r * 0.8, -r * 0.4);
    ctx.fill();
  }
  ellipse(0, -r * 0.1, r * 0.7, r * 0.65, body);
  ctx.strokeStyle = type === "boss" ? "#e9b757" : "#b58f64";
  ctx.lineWidth = 3;
  ctx.strokeRect(-r * 0.7, r * 0.2, r * 1.4, r * 0.35);
  ellipse(0, r * 0.1, r * 0.38, r * 0.25, "#c98d70");
  ellipse(-r * 0.13, r * 0.1, r * 0.07, r * 0.1, "#40242b");
  ellipse(r * 0.13, r * 0.1, r * 0.07, r * 0.1, "#40242b");
  ctx.fillStyle = "#ffe8ae";
  ctx.fillRect(-r * 0.5, -r * 0.3, r * 0.26, 3);
  ctx.fillRect(r * 0.24, -r * 0.3, r * 0.26, 3);
  ctx.strokeStyle = "#fff0c9";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(-r * 0.4, r * 0.25);
  ctx.lineTo(-r * 0.48, -r * 0.02);
  ctx.moveTo(r * 0.4, r * 0.25);
  ctx.lineTo(r * 0.48, -r * 0.02);
  ctx.stroke();
  ctx.restore();
}
// Декорации детерминированы: каменная мостовая, огни, сакура, ворота.
const scenery = document.createElement("canvas");
scenery.width = 540;
scenery.height = 960;
function makeScenery() {
  const c = scenery.getContext("2d");
  c.fillStyle = "#302835";
  c.fillRect(0, 0, 540, 960);
  for (let row = 0; row < 30; row++)
    for (let col = 0; col < 12; col++) {
      const x = 64 + col * 35 + (row % 2) * -17,
        y = row * 34;
      c.fillStyle = ["#59505e", "#635665", "#514957", "#71616b"][
        (row * 17 + col * 7) % 4
      ];
      c.fillRect(x + 1, y + 1, 33, 31);
      c.strokeStyle = "#b99a8b22";
      c.strokeRect(x + 2, y + 2, 31, 28);
      c.fillStyle = "#c9aaa51a";
      c.fillRect(x + 3, y + 3, 24, 2);
      c.strokeStyle = "#211d2838";
      c.beginPath();
      c.moveTo(x + 7, y + 31);
      c.lineTo(x + 13, y + 24);
      c.lineTo(x + 11, y + 20);
      c.stroke();
    }
  for (const side of [0, 1]) {
    const x = side ? 481 : 0;
    c.fillStyle = "#251f2b";
    c.fillRect(x, 0, 59, 960);
    for (let y = 0; y < 960; y += 18) {
      c.fillStyle = "#61413e";
      c.fillRect(x + 8, y, 43, 4);
    }
    for (let y = 120; y < 930; y += 180) {
      const lx = side ? 477 : 63;
      const glow = c.createRadialGradient(lx, y, 1, lx, y, 80);
      glow.addColorStop(0, "#ff9a3b55");
      glow.addColorStop(1, "transparent");
      c.fillStyle = glow;
      c.fillRect(lx - 80, y - 80, 160, 160);
      c.fillStyle = "#2b202b";
      c.fillRect(lx - 13, y - 20, 26, 42);
      c.fillStyle = "#ffb35a";
      c.fillRect(lx - 8, y - 15, 16, 25);
      c.fillStyle = "#ffe4a1";
      c.fillRect(lx - 3, y - 12, 6, 22);
    }
    for (let i = 0; i < 95; i++) {
      const y = (i * 71) % 960,
        bx = (i * 37) % 66;
      const sx = side ? 540 - bx : bx;
      c.fillStyle = ["#a74c79", "#e98cb5", "#f7b2ce", "#69334e"][i % 4];
      c.beginPath();
      c.arc(sx, y, 7 + (i % 7), 0, 7);
      c.fill();
      for (let k = 0; k < 4; k++) {
        const fx = sx + Math.sin(i * 3 + k) * 12,
          fy = y + Math.cos(i + k) * 10;
        c.fillStyle = ["#f3b0cd", "#d97da8", "#ffc5d9"][k % 3];
        c.beginPath();
        c.ellipse(fx, fy, 3, 5, k, 0, 7);
        c.fill();
        c.fillStyle = "#ffdab8";
        c.fillRect(fx, fy, 1.5, 1.5);
      }
    }
  } // Ворота находятся позади позиции игрока, не закрывая поле боя.
  c.fillStyle = "#603b32";
  c.fillRect(83, 850, 25, 110);
  c.fillRect(432, 850, 25, 110);
  c.fillStyle = "#211f2a";
  c.beginPath();
  c.moveTo(62, 839);
  c.quadraticCurveTo(270, 875, 478, 839);
  c.lineTo(459, 878);
  c.quadraticCurveTo(270, 905, 81, 878);
  c.fill();
  c.strokeStyle = "#be9563";
  c.lineWidth = 3;
  c.stroke();
  c.fillStyle = "#c4a27b";
  c.fillRect(234, 872, 72, 36);
  c.fillStyle = "#26212b";
  c.font = "bold 17px Georgia";
  c.textAlign = "center";
  c.fillText("DOJO", 270, 896);
}
makeScenery();
function background(t) {
  ctx.drawImage(scenery, 0, 0);
  const shade = ctx.createLinearGradient(0, 0, 0, 960);
  shade.addColorStop(0, "#16121d99");
  shade.addColorStop(0.5, "transparent");
  shade.addColorStop(1, "#110d1833");
  ctx.fillStyle = shade;
  ctx.fillRect(0, 0, 540, 960);
  ctx.fillStyle = "#f1a4caaa";
  for (let i = 0; i < 30; i++) {
    const x = (i * 97 + Math.sin(t * 0.5 + i) * 55 + t * 7) % 540,
      y = (i * 137 + t * (15 + (i % 4))) % 960;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(t + i);
    ctx.fillRect(0, 0, 5, 2);
    ctx.restore();
  }
}
const game = new GameScene();
