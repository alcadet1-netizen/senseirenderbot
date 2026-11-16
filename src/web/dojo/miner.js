// Сервер хранит 8-часовой цикл; интерфейс только показывает таймер и просит пинок/сбор.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const frame = $("frame");
  const tg = window.Telegram?.WebApp;
  const initData = () => tg?.initData || "";
  const coin = (value) =>
    Number.isFinite(Number(value))
      ? Math.floor(Number(value)).toLocaleString("ru-RU")
      : "—";

  let model = null;
  let skew = 0;
  let busy = false;
  let kicking = false;
  let celebrating = false;
  let endRetryAt = 0;
  let toastTimer = 0;

  try {
    tg?.ready?.();
    tg?.expand?.();
    tg?.setHeaderColor?.("#0b2b52");
    tg?.setBackgroundColor?.("#050d19");
  } catch {}

  async function api(action) {
    const response = await fetch(`/miniapp/dojo/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ initData: initData() }),
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
    $("balance").textContent = coin(data.balance);
    render();
    tick();
  }

  function visualMode() {
    if (kicking) return "mode-kicking";
    if (celebrating) return "mode-done";
    if (!model) return "mode-ready";
    if (model.phase === "mining") return "mode-mining";
    if (model.phase === "ready_to_collect") return "mode-done";
    return "mode-ready";
  }

  function remaining() {
    if (!model || model.phase !== "mining") return 0;
    return Math.max(0, (model.finish_at || 0) * 1000 - serverNow());
  }

  function progress() {
    if (!model) return 0;
    if (model.phase === "ready_to_collect") return 1;
    if (model.phase !== "mining" || !model.finish_at || !model.started_at)
      return 0;
    const span = (model.finish_at - model.started_at) * 1000;
    if (span <= 0) return 0;
    return Math.max(
      0,
      Math.min(1, (serverNow() - model.started_at * 1000) / span),
    );
  }

  function clock(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
  }

  function render() {
    frame.classList.remove(
      "mode-ready",
      "mode-kicking",
      "mode-mining",
      "mode-done",
    );
    frame.classList.add(visualMode());
    const phase = model?.phase;
    const action = $("action");
    const status = $("status");
    const note = $("note");
    const rate = $("rate");
    const subtitle = $("subtitle");
    const title = $("title");

    if (kicking) title.innerHTML = "ПНИ<br><em>ПАШУ ДУРОВА</em>";
    else if (phase === "mining") title.innerHTML = "ПАША<br><em>ЛЕТИТ!</em>";
    else if (phase === "ready_to_collect")
      title.innerHTML = "МАЙНИНГ<br><em>ГОТОВ!</em>";
    else title.innerHTML = "ПНИ<br><em>ПАШУ ДУРОВА</em>";

    if (!initData()) {
      $("balance").textContent = "—";
      status.textContent = "ТОЛЬКО В TELEGRAM";
      rate.textContent = "+120 ◉ / 8 Ч";
      subtitle.textContent =
        "Майнер открывается из /dojo внутри Telegram: там подпись и баланс.";
      $("timer").textContent = "—:—";
      $("timer-hint").textContent = "нет доступа";
      action.textContent = "ОТКРОЙ ЧЕРЕЗ /DOJO";
      action.className = "primary";
      action.disabled = true;
      note.textContent =
        "Вне Telegram майнер не начисляет SenseiCoin и не запускает цикл.";
      updateProgress(0);
      return;
    }

    if (kicking) {
      status.textContent = "ПАША В ПОЛЁТЕ";
      action.textContent = "ПНЁС!";
      action.className = "primary";
      action.disabled = true;
      note.textContent =
        "Пинок принят. Майнер запускается на сервере — таймер не зависит от телефона.";
    } else if (!model) {
      status.textContent = "ЗАГРУЖАЕМ МАЙНЕР";
      action.textContent = "ПОДКЛЮЧЕНИЕ…";
      action.className = "primary";
      action.disabled = true;
      note.textContent = "Проверяем состояние цикла.";
    } else if (phase === "mining") {
      status.textContent = "ПАША ЛЕТИТ · МАЙНИНГ ИДЁТ";
      rate.textContent = `+${model.reward} ◉ / 8 Ч`;
      action.textContent = "МАЙНИНГ ИДЁТ";
      action.className = "primary";
      action.disabled = true;
      note.innerHTML =
        "Можно закрыть приложение: таймер идёт на сервере. Вернись, когда <b>08:00:00</b> закончится.";
      subtitle.textContent =
        "Майнинг растёт! 15 SenseiCoin в час прямо из SenseiBank.";
    } else if (phase === "ready_to_collect") {
      status.textContent = "МАЙНИНГ ЗАВЕРШЁН";
      rate.textContent = `+${model.reward} ◉ НАМАЙНЕНО`;
      action.textContent = `ЗАБРАТЬ ${model.reward} ◉`;
      action.className = "primary collect";
      action.disabled = busy;
      note.innerHTML = `Майнер отдал <b>${model.reward} SenseiCoin</b>. Забери их, чтобы открыть следующий пинок.`;
      subtitle.textContent = `Восемь часов прошли. Забирай ${model.reward} SenseiCoin.`;
    } else {
      status.textContent = "ПАША ЖДЁТ ПИНКА";
      rate.textContent = `+${model.reward} ◉ / 8 Ч`;
      action.textContent = "ПНУТЬ ПАШУ";
      action.className = "primary kick";
      action.disabled = busy || celebrating;
      note.innerHTML =
        "Один пинок запускает <b>8 часов майнинга</b> из SenseiBank. Следующий пинок — после сбора.";
      subtitle.textContent =
        "Один пинок запускает майнинг из SenseiBank на 8 часов.";
    }
    if (phase === "mining" && !kicking)
      $("timer").textContent = clock(remaining());
    else if (phase === "ready_to_collect") $("timer").textContent = "00:00:00";
    else if (phase === "ready") $("timer").textContent = "08:00:00";
    else if (!model) $("timer").textContent = "—:—";
    if (!initData()) $("timer").textContent = "—:—";
    updateProgress(progress() * 100);
  }

  function updateProgress(percent) {
    const value = Math.max(0, Math.min(100, percent));
    $("bar").style.width = `${value}%`;
    $("progress").setAttribute("aria-valuenow", String(Math.round(value)));
    const hint = $("timer-hint");
    if (!initData()) hint.textContent = "нет доступа";
    else if (model?.phase === "mining") hint.textContent = "до конца майнинга";
    else if (model?.phase === "ready_to_collect")
      hint.textContent = "готово к сбору";
    else hint.textContent = "8 часов майнинга";
  }

  function tick() {
    if (!model || model.phase !== "mining") return;
    const left = remaining();
    $("timer").textContent = clock(left);
    updateProgress(progress() * 100);
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
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
  }

  async function refresh(silent = false) {
    if (!initData() || busy) return;
    try {
      apply(await api("state"));
    } catch (error) {
      if (!silent) showToast(error.message, true);
    }
  }

  async function kick() {
    if (busy || celebrating || !model || model.phase !== "ready" || !initData())
      return;
    busy = true;
    render();
    try {
      const data = await api("kick");
      apply(data);
      kicking = true;
      render();
      setTimeout(() => {
        kicking = false;
        render();
      }, 1500);
    } catch (error) {
      showToast(error.message, true);
      await refresh(true);
    } finally {
      busy = false;
      render();
    }
  }

  async function collect() {
    if (busy || model?.phase !== "ready_to_collect" || !initData()) return;
    busy = true;
    render();
    try {
      const data = await api("collect");
      apply(data);
      celebrating = true;
      render();
      celebrate(data.mined || 0);
      showToast(
        `+${coin(data.mined)} SenseiCoin · баланс ${coin(data.balance)}`,
      );
      setTimeout(() => {
        celebrating = false;
        render();
      }, 1600);
    } catch (error) {
      showToast(error.message, true);
      await refresh(true);
    } finally {
      busy = false;
      render();
    }
  }

  function celebrate(amount) {
    if (!amount) return;
    const layer = $("coins");
    for (let i = 0; i < 16; i++) {
      const node = document.createElement("span");
      node.className = "coin-fly";
      node.textContent = "◉";
      node.style.left = `${8 + Math.random() * 84}%`;
      node.style.setProperty("--dx", `${(Math.random() - 0.5) * 160}px`);
      node.style.animationDelay = `${Math.random() * 0.18}s`;
      layer.appendChild(node);
      setTimeout(() => node.remove(), 1700);
    }
  }

  $("action").addEventListener("click", () => {
    if (visualMode() === "mode-done" || model?.phase === "ready_to_collect")
      collect();
    else kick();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh(true);
  });
  setInterval(tick, 250);
  setInterval(() => {
    if (!document.hidden) refresh(true);
  }, 30000);

  if (!initData()) render();
  else refresh();
})();
