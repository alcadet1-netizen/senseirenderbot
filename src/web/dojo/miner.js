// Сервер хранит 8-часовой цикл; интерфейс показывает таймер, энергию и сбор.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const app = $("app");
  const tg = window.Telegram?.WebApp;
  const initData = () => tg?.initData || "";
  const coin = (value) =>
    Number.isFinite(Number(value))
      ? Math.floor(Number(value)).toLocaleString("ru-RU")
      : "—";

  const ICONS = {
    pickaxe: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m14 13-8.381 8.38a1 1 0 0 1-3.001-3L11 9.999"/>
      <path d="M15.973 4.027A13 13 0 0 0 5.902 2.373c-1.398.342-1.092 2.158.277 2.601a19.9 19.9 0 0 1 5.822 3.024"/>
      <path d="M16.001 11.999a19.9 19.9 0 0 1 3.024 5.824c.444 1.369 2.26 1.676 2.603.278A13 13 0 0 0 20 8.069"/>
      <path d="M18.352 3.352a1.205 1.205 0 0 0-1.704 0l-5.296 5.296a1.205 1.205 0 0 0 0 1.704l2.296 2.296a1.205 1.205 0 0 0 1.704 0l5.296-5.296a1.205 1.205 0 0 0 0-1.704z"/>
      </svg>`,
    coin: `<svg class="icon" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r="17"/><path d="M15 19h18M18 19v4M30 19v4M17 23h14"/>
      <path d="M20 23v10M28 23v10"/></svg>`,
    lock: `<svg class="icon" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="12" y="21" width="24" height="18" rx="4"/>
      <path d="M17 21v-4a7 7 0 0 1 14 0v4"/></svg>`,
    telegram: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`,
  };

  let model = null;
  let skew = 0;
  let pending = null;
  let toastTimer = 0;
  let endRetryAt = 0;
  let activeTab = "mining";
  let tasks = [];
  let tasksLoaded = false;
  let taskBusy = null;

  try {
    tg?.ready?.();
    tg?.expand?.();
    tg?.setHeaderColor?.("#020806");
    tg?.setBackgroundColor?.("#010503");
  } catch {}

  async function api(action, extra = {}) {
    const response = await fetch(`/miniapp/dojo/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ initData: initData(), ...extra }),
    });
    let data = {};
    try {
      data = await response.json();
    } catch {}
    if (!response.ok)
      throw Error(data.error || "Майнер не ответил. Попробуй ещё раз.");
    return data;
  }

  function serverNow() {
    return Date.now() - skew;
  }

  function apply(data) {
    model = data;
    skew = Date.now() - data.server_now * 1000;
    render();
    tick();
  }

  function phase() {
    if (!initData()) return "phase-offline";
    if (!model) return "phase-loading";
    if (model.phase === "mining") return "phase-mining";
    if (model.phase === "ready_to_collect") return "phase-done";
    return "phase-ready";
  }

  function remaining() {
    if (!model || model.phase !== "mining") return 0;
    return Math.max(0, (model.finish_at || 0) * 1000 - serverNow());
  }

  function miningProgress() {
    if (!model || model.phase !== "mining") return 0;
    if (!model.started_at || !model.finish_at) return 0;
    const span = (model.finish_at - model.started_at) * 1000;
    if (span <= 0) return 0;
    return Math.max(
      0,
      Math.min(1, (serverNow() - model.started_at * 1000) / span),
    );
  }

  function energyMax() {
    const max = Number(model?.energy_max);
    return Number.isFinite(max) && max > 0 ? max : 100;
  }

  function energyValue() {
    if (!initData()) return 0;
    if (!model) return 0;
    const max = energyMax();
    if (model.phase === "mining")
      return Math.round(max * (1 - miningProgress()));
    if (model.phase === "ready_to_collect") return 0;
    return max;
  }

  function clock(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
  }

  function paintEnergy(value) {
    const max = energyMax();
    const rounded = Math.max(0, Math.min(max, Math.round(value)));
    $("energy").textContent = `${rounded} / ${max}`;
    $("energy-bar").style.width = `${(rounded / max) * 100}%`;
    $("energy-track").setAttribute("aria-valuemax", String(max));
    $("energy-track").setAttribute("aria-valuenow", String(rounded));
  }

  function paintAction(icon, label, sub, timer = false, disabled = true) {
    const button = $("action");
    const labelNode = $("action-label");
    $("orb-icon").innerHTML = ICONS[icon] || ICONS.pickaxe;
    $("orb-icon").hidden = timer;
    labelNode.textContent = label;
    labelNode.classList.toggle("is-timer", timer);
    $("orb-sub").textContent = sub;
    button.disabled = disabled;
    button.setAttribute(
      "aria-label",
      timer ? `${label}. ${sub}` : `${label}. ${sub}`,
    );
  }

  function render() {
    const current = phase();
    app.classList.remove(
      "phase-ready",
      "phase-mining",
      "phase-done",
      "phase-offline",
      "phase-loading",
    );
    app.classList.add(current);

    const balance = initData() ? coin(model?.balance) : "—";
    $("balance").textContent = balance;
    $("profile-balance").textContent = initData() ? `${balance} Coin` : "—";
    $("profile-reward").textContent = `${model?.reward ?? 120} Coin`;
    paintEnergy(energyValue());

    const status = $("status");
    const hint = $("hint");

    if (current === "phase-offline") {
      paintAction("lock", "ОТКРОЙ ЧЕРЕЗ /DOJO", "ТОЛЬКО TELEGRAM", false, true);
      $("energy").textContent = "— / —";
      renderTasks("ОТКРОЙ ЧЕРЕЗ /DOJO");
      status.textContent = "ТОЛЬКО В TELEGRAM";
      hint.textContent =
        "Вне Telegram майнер не начисляет SenseiCoin и не запускает цикл.";
      return;
    }

    if (current === "phase-loading") {
      paintAction("pickaxe", "ПОДКЛЮЧЕНИЕ", "SENSEIBANK", false, true);
      status.textContent = "СЕНСЕЙ ПРОСЫПАЕТСЯ";
      hint.textContent = "Проверяем состояние цикла на сервере.";
      return;
    }

    if (pending === "collect") {
      paintAction("coin", "ЗАБИРАЕМ…", "SENSEIBANK", false, true);
      status.textContent = "НАГРАДА В ПУТИ";
      hint.textContent = "Сервер начисляет SenseiCoin из банка.";
      return;
    }

    if (pending === "start") {
      paintAction("pickaxe", "ЗАПУСК…", "8 ЧАСОВ", false, true);
      status.textContent = "СЕНСЕЙ УХОДИТ В МАЙНИНГ";
      hint.textContent = "Создаём восьмичасовой цикл на сервере.";
      return;
    }

    if (current === "phase-mining") {
      paintAction("pickaxe", clock(remaining()), "ДО КОНЦА ЦИКЛА", true, true);
      status.textContent = "МАЙНИНГ ИДЁТ";
      hint.textContent =
        "Цикл идёт на сервере · приложение можно закрыть · 8 часов";
      return;
    }

    if (current === "phase-done") {
      paintAction(
        "coin",
        `ЗАБРАТЬ ${model.reward}`,
        "SENSEICOIN",
        false,
        false,
      );
      status.textContent = "ЦИКЛ ЗАВЕРШЁН";
      hint.textContent =
        "Награда из SenseiBank ждёт тебя. Забери и начни снова.";
      return;
    }

    paintAction(
      "pickaxe",
      "НАЧАТЬ МАЙНИНГ",
      "8 ЧАСОВ · 120 COIN",
      false,
      false,
    );
    status.textContent = "СЕНСЕЙ ГОТОВ";
    hint.textContent = "Один цикл — 8 часов · 120 SenseiCoin из SenseiBank";
  }

  function tick() {
    if (!model || model.phase !== "mining" || pending) return;
    const left = remaining();
    const label = $("action-label");
    label.textContent = clock(left);
    label.classList.add("is-timer");
    paintEnergy(energyValue());
    if (left <= 0 && Date.now() >= endRetryAt) {
      endRetryAt = Date.now() + 4000;
      refresh(true);
    }
  }

  function showToast(text, error = false) {
    const toast = $("toast");
    toast.textContent = text;
    toast.classList.toggle("error", error);
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
  }

  async function refresh(silent = false) {
    if (!initData() || pending) return;
    try {
      apply(await api("state"));
    } catch (error) {
      if (!silent) showToast(error.message, true);
    }
  }

  async function start() {
    if (pending || !model || model.phase !== "ready" || !initData()) return;
    pending = "start";
    render();
    let failed = false;
    try {
      const data = await api("start");
      apply(data);
      showToast("Майнинг запущен · Сенсей ушёл на 8 часов");
    } catch (error) {
      failed = true;
      showToast(error.message, true);
    } finally {
      pending = null;
      render();
    }
    if (failed) refresh(true);
  }

  async function collect() {
    if (pending || model?.phase !== "ready_to_collect" || !initData()) return;
    pending = "collect";
    render();
    let failed = false;
    try {
      const data = await api("collect");
      apply(data);
      celebrate(data.mined || 0);
      showToast(
        `+${coin(data.mined)} SenseiCoin · баланс ${coin(data.balance)}`,
      );
    } catch (error) {
      failed = true;
      showToast(error.message, true);
    } finally {
      pending = null;
      render();
    }
    if (failed) refresh(true);
  }

  function celebrate(amount) {
    if (!amount) return;
    const layer = $("coins");
    for (let i = 0; i < 18; i++) {
      const node = document.createElement("span");
      node.className = "coin-fly";
      node.textContent = "◉";
      node.style.left = `${8 + Math.random() * 84}%`;
      node.style.setProperty("--dx", `${(Math.random() - 0.5) * 170}px`);
      node.style.animationDelay = `${Math.random() * 0.2}s`;
      layer.appendChild(node);
      setTimeout(() => node.remove(), 1900);
    }
  }

  function renderTasks(emptyText = "ПОКА НЕТ ЗАДАНИЙ") {
    const list = $("tasks-list");
    if (!list) return;
    list.replaceChildren();
    if (!tasks.length) {
      const empty = document.createElement("p");
      empty.className = "task-empty";
      empty.textContent = emptyText;
      list.appendChild(empty);
      return;
    }
    tasks.forEach((task) => {
      const card = document.createElement("article");
      card.className = `task-card${task.claimed ? " claimed" : ""}`;

      const top = document.createElement("div");
      top.className = "task-top";
      const avatar = document.createElement("span");
      avatar.className = "task-avatar";
      avatar.innerHTML = ICONS.telegram;
      const name = document.createElement("span");
      name.className = "task-name";
      const title = document.createElement("b");
      title.textContent = task.title || `@${task.username}`;
      const handle = document.createElement("span");
      handle.textContent = `@${task.username} · подписка на канал`;
      name.append(title, handle);
      top.append(avatar, name);

      const chips = document.createElement("div");
      chips.className = "task-chips";
      const coinChip = document.createElement("span");
      coinChip.className = "task-chip";
      coinChip.textContent = `${coin(task.reward_coins)} Coin`;
      const energyChip = document.createElement("span");
      energyChip.className = "task-chip";
      energyChip.textContent = `+${task.energy_bonus}% энергии`;
      chips.append(coinChip, energyChip);

      card.append(top, chips);

      if (task.claimed) {
        const done = document.createElement("div");
        done.className = "task-claimed";
        done.textContent = "✓ Награда получена";
        card.appendChild(done);
      } else {
        const actions = document.createElement("div");
        actions.className = "task-actions";
        const open = document.createElement("a");
        open.className = "task-link";
        open.href = task.url;
        open.target = "_blank";
        open.rel = "noopener noreferrer";
        open.textContent = "Подписаться";
        open.addEventListener("click", (event) => {
          if (tg?.openTelegramLink) {
            event.preventDefault();
            tg.openTelegramLink(task.url);
          }
        });
        const claim = document.createElement("button");
        claim.className = "task-claim";
        claim.textContent = taskBusy === task.slug ? "Проверяем…" : "Проверить";
        claim.disabled = Boolean(taskBusy);
        claim.addEventListener("click", () => claimTask(task.slug));
        actions.append(open, claim);
        card.appendChild(actions);
      }

      list.appendChild(card);
    });
  }

  async function loadTasks(force = false) {
    if (!initData()) {
      tasks = [];
      renderTasks("ОТКРОЙ ЧЕРЕЗ /DOJO");
      return;
    }
    if (tasksLoaded && !force) return;
    try {
      const data = await api("tasks");
      tasks = Array.isArray(data.tasks) ? data.tasks : [];
      tasksLoaded = true;
      renderTasks();
    } catch (error) {
      tasksLoaded = false;
      tasks = [];
      renderTasks("НЕ УДАЛОСЬ ЗАГРУЗИТЬ ЗАДАНИЯ");
      showToast(error.message, true);
    }
  }

  async function claimTask(slug) {
    if (!initData() || pending || taskBusy) return;
    const task = tasks.find((item) => item.slug === slug);
    if (!task || task.claimed) return;
    taskBusy = slug;
    renderTasks();
    try {
      const data = await api("task", { slug });
      apply(data);
      const updated = data.task || { ...task, claimed: true };
      tasks = tasks.map((item) =>
        item.slug === slug ? { ...item, ...updated, claimed: true } : item,
      );
      showToast(
        `+${coin(data.reward_coins)} SenseiCoin · +${data.energy_bonus}% энергии`,
      );
    } catch (error) {
      showToast(error.message, true);
    } finally {
      taskBusy = null;
      renderTasks();
    }
  }

  function setTab(name) {
    if (!["mining", "tasks", "upgrades", "profile"].includes(name)) return;
    activeTab = name;
    document.querySelectorAll(".tab").forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active);
      if (active) tab.setAttribute("aria-current", "page");
      else tab.removeAttribute("aria-current");
    });
    ["mining", "tasks", "upgrades", "profile"].forEach((key) => {
      $(`view-${key}`).hidden = key !== name;
    });
    if (name === "tasks") loadTasks();
    closeSheet();
  }

  function openSheet() {
    const sheet = $("sheet");
    sheet.hidden = false;
  }

  function closeSheet() {
    $("sheet").hidden = true;
  }

  $("action").addEventListener("click", () => {
    if (model?.phase === "ready_to_collect") collect();
    else start();
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => setTab(tab.dataset.tab));
  });

  $("info").addEventListener("click", () => {
    if (activeTab !== "mining") setTab("mining");
    openSheet();
  });

  document.querySelectorAll("[data-close='sheet']").forEach((node) => {
    node.addEventListener("click", closeSheet);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSheet();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh(true);
  });
  setInterval(tick, 250);
  setInterval(() => {
    if (!document.hidden) refresh(true);
  }, 30000);

  render();
  if (initData()) {
    refresh();
    loadTasks();
  } else {
    renderTasks("ОТКРОЙ ЧЕРЕЗ /DOJO");
  }
})();
