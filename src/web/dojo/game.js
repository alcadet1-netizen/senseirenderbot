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
  range: 300,
  enemySpeed: 38,
  shotSpeed: 640,
  dashCooldown: 4,
  dashDistance: 120,
  dashInvulnerability: 0.3,
  comboWindow: 3,
  magnetRadius: 100,
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
    this.dashCooldown = 0;
    this.invulnerable = 0;
    this.direction = 1;
    this.trails = [];
  }
  dash(g) {
    if (g.state !== "game" || this.dashCooldown > 0) return false;
    const direction =
      Math.abs(this.target - this.x) > 8
        ? Math.sign(this.target - this.x)
        : this.direction;
    const dest = clamp(
      this.x + direction * CONFIG.dashDistance,
      ...CONFIG.road,
    );
    if (Math.abs(dest - this.x) < 10) return false;
    for (let i = 0; i < 5; i++)
      this.trails.push({ x: this.x + ((dest - this.x) * i) / 5, life: 0.35 });
    this.x = this.target = dest;
    this.invulnerable = CONFIG.dashInvulnerability;
    this.dashCooldown = CONFIG.dashCooldown;
    g.burst(this.x, this.y, "#a5efff", 16);
    g.sound.play("pick");
    return true;
  }
  update(dt, g) {
    this.dashCooldown = Math.max(0, this.dashCooldown - dt);
    this.invulnerable = Math.max(0, this.invulnerable - dt);
    this.trails.forEach((t) => (t.life -= dt));
    this.trails = this.trails.filter((t) => t.life > 0);
    if (Math.abs(this.target - this.x) > 2)
      this.direction = Math.sign(this.target - this.x);
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
    for (const trail of this.trails) {
      ctx.save();
      ctx.globalAlpha = trail.life * 0.9;
      samurai(trail.x, this.y);
      ctx.restore();
    }
    if (this.invulnerable > 0) {
      ctx.strokeStyle = "#9fe8ff";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.ellipse(this.x, this.y + 14, 36, 46, 0, 0, 7);
      ctx.stroke();
    }
    for (let i = this.army - 1; i >= 0; i--) {
      const row = Math.floor(i / 6),
        x = this.x + ((i % 6) - 2.5) * 22,
        y = this.y + 45 + row * 23;
      hedgehog(x, y, Math.sin(t * 6 + i) * 1.5);
    }
    samurai(this.x, this.y);
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
      life: 1.5,
      dead: false,
      angle: 0,
    });
  }
  update(dt, g) {
    this.life -= dt;
    if (this.target.dead || this.life <= 0) {
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
    ctx.shadowColor = this.star ? "#75d7ff" : "#ffd37a";
    ctx.shadowBlur = 7;
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
      ctx.strokeStyle = "#ffe9c1";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-12, 0);
      ctx.lineTo(5, 0);
      ctx.stroke();
    }
    ctx.restore();
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
    if (this.y > CONFIG.playerY + 12) {
      this.dead = true;
      if (g.player.invulnerable <= 0) g.player.lives--;
      g.combo = 0;
      g.comboTime = 0;
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
    this.charge -= dt;
    if (this.charge <= 0 && this.warning <= 0) {
      this.warning = 1.25;
      this.attackX = g.player.x;
      g.ui.toast("⚠ Вождь замахивается — уходи с красной линии!");
    }
    if (this.warning > 0) {
      this.warning -= dt;
      if (this.warning <= 0) {
        this.charge = this.enraged ? 2.7 : 4;
        if (
          Math.abs(g.player.x - this.attackX) < 62 &&
          g.player.invulnerable <= 0
        ) {
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
    $("#dash").disabled = g.state !== "game" || g.player.dashCooldown > 0;
    $("#dash").textContent =
      g.player.dashCooldown > 0
        ? "Рывок " + g.player.dashCooldown.toFixed(1)
        : "↔ РЫВОК";
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
      '<div class="eyebrow">SENSEI GAMES · 生き残れ</div><div class="seal">⚔</div><h1>Последний<br><em>рубеж</em></h1><p>Один самурай. Отряд верных ежей.<br>Пять волн, чтобы защитить додзё.</p><button class="primary" id="play">В бой →</button><div class="hint">Веди пальцем по дороге · атака автоматическая<br>Рывок — кнопка ↔ или Shift · уходи от красной зоны<br>Монеты только игровые, без выплат и ставок.</div>',
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
    this.labels = [];
    this.combo = 0;
    this.comboTime = 0;
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
      if (e.key === "Shift" && !e.repeat) {
        e.preventDefault();
        this.player.dash(this);
      }
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
    $("#dash").onclick = () => this.player.dash(this);
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
    this.state = "shop";
    this.shopWait = CONFIG.shopSeconds;
    this.showShop();
  }
  showShop() {
    this.ui.panel(
      `<div class="eyebrow">ВОЛНА ${this.waves.index + 1} ПОКОРЕНА</div><div class="seal">⚒</div><h1>Привал<br><em>у кузнеца</em></h1><p>Отряд держит строй. Усиль его перед новой волной.<br>Кошелёк: <b>${this.coins} ◉</b></p><div class="shop">${[
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
      `<div class="eyebrow">${win ? "ПЯТЬ ВОЛН · ОДНА ЛЕГЕНДА" : "ТВОЙ ПУТЬ ЕЩЁ НЕ ОКОНЧЕН"}</div><div class="seal">${win ? "🏆" : "⚔"}</div><h1>${win ? "Додзё<br><em>выстояло</em>" : "Последний<br><em>павший лист</em>"}</h1><p>${win ? "Стихия отступила. Ежи стали легендой." : "Даже великий воин однажды падает.<br>Встань и попробуй снова."}<br>Побеждено они: ${this.kills} · Монеты: ${this.coins}</p><button class="primary" id="again">Новый поход →</button>`,
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
    ctx.save();
    ctx.translate(rand(-this.shake, this.shake), rand(-this.shake, this.shake));
    background(this.time);
    for (const p of this.pickups) p.draw(this.time);
    for (const e of [...this.enemies].sort((a, b) => a.y - b.y))
      e.draw(this.time);
    this.player.draw(this.time);
    for (const shot of this.shots) shot.draw(this.time);
    for (const l of this.labels) {
      ctx.save();
      ctx.globalAlpha = Math.min(1, l.life * 3);
      ctx.textAlign = "center";
      ctx.font = "bold 15px system-ui";
      ctx.shadowColor = "#000";
      ctx.shadowBlur = 3;
      ctx.fillStyle = l.color;
      ctx.fillText(l.text, l.x, l.y);
      ctx.restore();
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
// Слоистые миниатюры: оружие, ламеллярные доспехи, блики и контактные тени.
function samurai(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ellipse(0, 27, 28, 9, "#100b1899");
  const coat = ctx.createLinearGradient(-16, 0, 18, 20);
  coat.addColorStop(0, "#4b4657");
  coat.addColorStop(0.5, "#242530");
  coat.addColorStop(1, "#11141f");
  ctx.fillStyle = "#181520";
  ctx.fillRect(-13, 14, 10, 15);
  ctx.fillRect(4, 14, 10, 15);
  ctx.fillStyle = coat;
  ctx.beginPath();
  ctx.moveTo(-12, -8);
  ctx.lineTo(11, -8);
  ctx.lineTo(20, 21);
  ctx.lineTo(-20, 21);
  ctx.fill();
  ctx.strokeStyle = "#957b72";
  ctx.lineWidth = 1;
  for (let y = 0; y < 19; y += 5) {
    ctx.beginPath();
    ctx.moveTo(-13, y);
    ctx.lineTo(14, y);
    ctx.stroke();
  }
  ctx.fillStyle = "#c84249";
  ctx.fillRect(-17, 6, 34, 5);
  ctx.beginPath();
  ctx.moveTo(-12, 7);
  ctx.lineTo(-36, 2);
  ctx.lineTo(-28, 10);
  ctx.lineTo(-39, 18);
  ctx.lineTo(-12, 12);
  ctx.fill();
  ellipse(0, -12, 10, 12, "#181a24");
  ctx.fillStyle = "#d8ad81";
  ctx.fillRect(-6, -11, 12, 4);
  ctx.fillStyle = "#fbe3b5";
  ctx.fillRect(-5, -10, 3, 1);
  ctx.fillRect(3, -10, 3, 1);
  const hat = ctx.createLinearGradient(0, -37, 0, -10);
  hat.addColorStop(0, "#f7d490");
  hat.addColorStop(1, "#9a693f");
  ctx.fillStyle = hat;
  ctx.beginPath();
  ctx.moveTo(-31, -13);
  ctx.quadraticCurveTo(-14, -19, 0, -37);
  ctx.quadraticCurveTo(14, -19, 31, -13);
  ctx.quadraticCurveTo(0, -5, -31, -13);
  ctx.fill();
  ctx.strokeStyle = "#dfb77b";
  ctx.lineWidth = 1;
  ctx.stroke();
  for (let i = -24; i < 25; i += 6) {
    ctx.beginPath();
    ctx.moveTo(0, -34);
    ctx.lineTo(i, -13);
    ctx.stroke();
  }
  ctx.strokeStyle = "#4d3438";
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(10, 15);
  ctx.lineTo(31, -7);
  ctx.stroke();
  ctx.strokeStyle = "#e4edf5";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(17, 8);
  ctx.quadraticCurveTo(31, -5, 36, -18);
  ctx.stroke();
  ctx.restore();
}
function hedgehog(x, y, bob) {
  y += bob;
  ctx.save();
  ctx.translate(x, y);
  ellipse(0, 12, 13, 5, "#0006");
  const fur = ctx.createRadialGradient(-4, -5, 1, 0, 0, 16);
  fur.addColorStop(0, "#c3976d");
  fur.addColorStop(1, "#3c2831");
  ellipse(0, 0, 14, 15, fur);
  for (let ring = 0; ring < 3; ring++)
    for (let i = 0; i < 10; i++) {
      const a = i * 0.63 + ring * 0.3,
        r = 5 + ring * 3,
        px = Math.cos(a) * r,
        py = Math.sin(a) * r;
      ctx.strokeStyle = (i + ring) % 2 ? "#dfb184" : "#876451";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px + Math.cos(a) * 5, py - 5 + Math.sin(a) * 3);
      ctx.stroke();
    }
  ctx.fillStyle = "#b83c46";
  ctx.fillRect(-13, 3, 26, 4);
  ellipse(0, 9, 7, 5, "#bd926d");
  ellipse(0, 12, 2.4, 1.8, "#241e28");
  ctx.fillStyle = "#ffe6a3";
  ctx.fillRect(-5, 7, 2, 2);
  ctx.fillRect(3, 7, 2, 2);
  ctx.strokeStyle = "#dbd9d2";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(13, 4);
  ctx.lineTo(17, -9);
  ctx.stroke();
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
