// Сервер хранит 8-часовой цикл; интерфейс показывает таймер, энергию, прогресс и сбор.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const app = $("app");
  const stageEl = document.querySelector(".stage");
  const tg = window.Telegram?.WebApp;
  const initData = () => tg?.initData || "";

  const LANG_KEY = "sensei_dojo_language";
  const SUPPORTED_LANGS = ["ru", "en"];
  const EN = {
    "SenseiCoin · Майнер": "SenseiCoin · Miner",
    "Сенсей в тёмном кибер-додзё перед зелёным энсо":
      "Sensei in a dark cyber-dojo before a green enso",
    "Язык интерфейса": "Interface language",
    "Правила майнинга": "Mining rules",
    "Баланс SenseiCoin": "SenseiCoin balance",
    "ТВОИ ОЧКИ": "YOUR POINTS",
    "Энергия майнера": "Miner energy",
    ЭНЕРГИЯ: "ENERGY",
    "Энергия майнинга": "Mining energy",
    "ПРОГРЕСС ЦИКЛА": "CYCLE PROGRESS",
    ЗАДАНИЯ: "TASKS",
    ПОДПИСКИ: "SUBSCRIPTIONS",
    "Подпишись на канал и забери SenseiCoin и энергию. Награда за каждый канал — один раз.":
      "Subscribe to the channel and claim SenseiCoin and energy. Each channel reward can be claimed once.",
    "ЗАГРУЖАЕМ ЗАДАНИЯ…": "LOADING TASKS…",
    "Подписку проверяет сервер через Telegram.":
      "The server verifies the subscription via Telegram.",
    УЛУЧШЕНИЯ: "UPGRADES",
    ПРОКАЧКА: "UPGRADES",
    "Постоянные улучшения за Telegram Stars. Кирка повышает добычу, энергия держит полную мощность дольше, автосбор работает без тебя.":
      "Permanent upgrades for Telegram Stars. The pickaxe boosts mining, energy keeps full power longer, and auto-collect works without you.",
    "ЗАГРУЖАЕМ УЛУЧШЕНИЯ…": "LOADING UPGRADES…",
    "Оплата Stars · улучшения не сгорают":
      "Stars payment · upgrades never expire",
    ЭМИССИЯ: "EMISSION",
    "Всего в экономике может быть 10 000 000 000 Coin — жёсткий лимит. Монеты выпускаются в SenseiBank, добыча переводит их из банка игроку; переводы лимит не меняют.":
      "The economy can hold at most 10,000,000,000 Coin. Coins are emitted into SenseiBank, and mining transfers them from the bank to the player; transfers do not change the cap.",
    "Использование лимита эмиссии": "Emission cap usage",
    Выпущено: "Emitted",
    Лимит: "Cap",
    Осталось: "Remaining",
    "Всего в экономике": "Total in economy",
    "Баланс банка": "Bank balance",
    "В обороте": "In circulation",
    Игроков: "Players",
    "ОБНОВИТЬ ДАННЫЕ": "REFRESH DATA",
    "Баланс игрока один и тот же здесь и в чате (/balance). Данные /senseibank обновляются с задержкой до минуты.":
      "The player balance is the same here and in chat (/balance). /senseibank data may be up to a minute old.",
    "ДОДЗЁ ПРИГЛАШЕНИЙ": "REFERRAL DOJO",
    РЕФЕРАЛЫ: "REFERRALS",
    "Те же цифры, что в /senseireferal: твоя сеть, доход и бонус за активацию учеников.":
      "The same numbers as /senseireferal: your network, income and student activation bonus.",
    "Прогресс до следующего звания": "Progress to the next rank",
    Заработано: "Earned",
    "I уровень": "Level I",
    "II уровень": "Level II",
    "III уровень": "Level III",
    "Уровень сети": "Network level",
    "ЗАГРУЖАЕМ УЧЕНИКОВ…": "LOADING STUDENTS…",
    "СКОПИРОВАТЬ ССЫЛКУ": "COPY LINK",
    ПОДЕЛИТЬСЯ: "SHARE",
    "🎁 Бонус за ученика": "🎁 Referral bonus",
    "10% / 1% / 0,1% с каждого платного апа катаны по трём уровням. Остаток уходит в SenseiBank.":
      "10% / 1% / 0.1% from every paid katana upgrade across three levels. The remainder goes to SenseiBank.",
    ПРОФИЛЬ: "PROFILE",
    "СЕНСЕЙ-МАЙНЕР": "SENSEI MINER",
    "Баланс (как в чате)": "Balance (same as chat)",
    Добыча: "Mining rate",
    Энергия: "Energy",
    Цикл: "Cycle",
    "8 часов": "8 hours",
    Награда: "Reward",
    Автосбор: "Auto-collect",
    ВКЛ: "ON",
    ВЫКЛ: "OFF",
    Банк: "Bank",
    "Разделы майнера": "Miner sections",
    Майнинг: "Mining",
    Задания: "Tasks",
    Улучшения: "Upgrades",
    Рефералы: "Referrals",
    Профиль: "Profile",
    Закрыть: "Close",
    ПРАВИЛА: "RULES",
    "КАК РАБОТАЕТ МАЙНЕР": "HOW THE MINER WORKS",
    "<b>Запусти цикл.</b> Сенсей уходит в майнинг ровно на 8 часов.":
      "<b>Start a cycle.</b> Sensei goes mining for exactly 8 hours.",
    "<b>Следи за энергией.</b> 100 энергии хватает на час полной мощности; потом кирка добывает 10% от базовой скорости.":
      "<b>Watch your energy.</b> 100 energy lasts one hour at full power; after that the pickaxe mines at 10% of its base rate.",
    "<b>Забери награду.</b> Она приходит из SenseiBank только после конца цикла. Процент прогресса виден на экране.":
      "<b>Collect the reward.</b> It comes from SenseiBank only after the cycle ends. The progress percentage is shown on screen.",
    "<b>Начни снова.</b> Следующий цикл открывается сразу после сбора.":
      "<b>Start again.</b> The next cycle opens right after collection.",
    "<b>Улучшай кирку.</b> За Stars: +10 Coin/ч за уровень, +100 энергии или автосбор, который запускает циклы без тебя.":
      "<b>Upgrade your pickaxe.</b> For Stars: +10 Coin/h per level, +100 energy, or auto-collect that starts cycles without you.",
    ПОНЯТНО: "GOT IT",
    "Coin / ч": "Coin / h",
    "Coin/ч": "Coin/h",
    "ОТКРОЙ ЧЕРЕЗ /DOJO": "OPEN VIA /DOJO",
    "ТОЛЬКО TELEGRAM": "TELEGRAM ONLY",
    "ТОЛЬКО В TELEGRAM": "TELEGRAM ONLY",
    "Вне Telegram майнер не начисляет SenseiCoin и не запускает цикл.":
      "Outside Telegram the miner does not credit SenseiCoin or start cycles.",
    ПОДКЛЮЧЕНИЕ: "CONNECTING",
    "СЕНСЕЙ ПРОСЫПАЕТСЯ": "SENSEI IS WAKING UP",
    "Проверяем состояние цикла на сервере.":
      "Checking the cycle state on the server.",
    "ЗАБИРАЕМ…": "COLLECTING…",
    "НАГРАДА В ПУТИ": "REWARD IN TRANSIT",
    "Сервер начисляет SenseiCoin из банка.":
      "The server credits SenseiCoin from the bank.",
    "ЗАПУСК…": "STARTING…",
    "8 ЧАСОВ": "8 HOURS",
    "СЕНСЕЙ УХОДИТ В МАЙНИНГ": "SENSEI GOES MINING",
    "Создаём восьмичасовой цикл на сервере.":
      "Creating an eight-hour cycle on the server.",
    "ДО КОНЦА ЦИКЛА": "UNTIL THE CYCLE ENDS",
    "МАЙНИНГ ИДЁТ · {percent}%": "MINING · {percent}%",
    "ЗАБРАТЬ {amount}": "COLLECT {amount}",
    "ЦИКЛ ЗАВЕРШЁН · 100%": "CYCLE COMPLETE · 100%",
    "Награда из SenseiBank ждёт тебя. Забери и начни снова.":
      "Your SenseiBank reward is waiting. Collect it and start again.",
    "НАЧАТЬ МАЙНИНГ": "START MINING",
    "8 ЧАСОВ · {amount} COIN": "8 HOURS · {amount} COIN",
    "СЕНСЕЙ ГОТОВ": "SENSEI IS READY",
    "Кирка {rate} Coin/ч · энергия {energy} · {hours} ч полной мощности":
      "Pickaxe {rate} Coin/h · energy {energy} · {hours} h at full power",
    "Энергия {energy} / {max} · {rate} Coin/ч · после нуля 10%":
      "Energy {energy} / {max} · {rate} Coin/h · 10% after zero",
    "Майнинг запущен · Сенсей ушёл на 8 часов":
      "Mining started · Sensei left for 8 hours",
    "+{amount} SenseiCoin · баланс {balance}":
      "+{amount} SenseiCoin · balance {balance}",
    "ПОКА НЕТ ЗАДАНИЙ": "NO TASKS YET",
    "@{username} · подписка на канал": "@{username} · channel subscription",
    "+{amount} энергии": "+{amount} energy",
    "✓ Награда получена": "✓ Reward claimed",
    Подписаться: "Subscribe",
    "Проверяем…": "Checking…",
    Проверить: "Check",
    "НЕ УДАЛОСЬ ЗАГРУЗИТЬ ЗАДАНИЯ": "COULD NOT LOAD TASKS",
    "+{amount} SenseiCoin · +{energy} энергии":
      "+{amount} SenseiCoin · +{energy} energy",
    "УЛУЧШЕНИЯ НЕДОСТУПНЫ": "UPGRADES UNAVAILABLE",
    КИРКА: "PICKAXE",
    "Каждый уровень: +10 SenseiCoin в час. Действует со следующего цикла.":
      "Each level: +10 SenseiCoin per hour. Applies from the next cycle.",
    "{rate} Coin/ч · следующий {next} Coin/ч":
      "{rate} Coin/h · next {next} Coin/h",
    "СЧЁТ…": "INVOICE…",
    МАКСИМУМ: "MAXIMUM",
    "{stars} ⭐ · УЛУЧШИТЬ": "{stars} ⭐ · UPGRADE",
    "Навсегда +100 к запасу. 100 энергии — час полной мощности, потом 10%; со следующего цикла.":
      "Permanent +100 to the reserve. 100 energy is one hour at full power, then 10%; applies from the next cycle.",
    "Покупок: {bought} / {max} · база {base}":
      "Purchases: {bought} / {max} · base {base}",
    "{stars} ⭐ · +100 ЭНЕРГИИ": "{stars} ⭐ · +100 ENERGY",
    АВТОСБОР: "AUTO-COLLECT",
    АКТИВЕН: "ACTIVE",
    "Сам собирает награду и запускает новый цикл каждые 8 часов. Участие не нужно.":
      "Collects the reward and starts a new cycle every 8 hours. No action needed.",
    "Один раз · работает всегда": "One-time · always active",
    "УЖЕ ВКЛЮЧЁН": "ALREADY ON",
    "{stars} ⭐ · ВКЛЮЧИТЬ": "{stars} ⭐ · ENABLE",
    "НЕ УДАЛОСЬ ЗАГРУЗИТЬ УЛУЧШЕНИЯ": "COULD NOT LOAD UPGRADES",
    "Счёт Stars создан. Открой его в Telegram.":
      "Stars invoice created. Open it in Telegram.",
    "Оплата получена · включаем улучшение":
      "Payment received · enabling the upgrade",
    "Оплата отменена": "Payment cancelled",
    "Оплата не прошла": "Payment failed",
    "МАКСИМАЛЬНОЕ ЗВАНИЕ": "MAXIMUM RANK",
    "ДО {rank} · {required}": "TO {rank} · {required}",
    "✅ Получено 50 Coin за активацию ученика.":
      "✅ 50 Coin received for student activation.",
    "Твой аккаунт не участвует в бонусной программе активации. Комиссии 10% / 1% / 0,1% продолжают начисляться.":
      "Your account is not part of the activation bonus program. Commissions of 10% / 1% / 0.1% still apply.",
    "Дни активности: {days}/3 · платный ап: {upgrade}. Выплата при наличии средств SenseiBank.":
      "Activity days: {days}/3 · paid upgrade: {upgrade}. Paid when SenseiBank has funds.",
    "ПОКА НЕТ УЧЕНИКОВ": "NO STUDENTS YET",
    "НЕ УДАЛОСЬ ЗАГРУЗИТЬ РЕФЕРАЛОВ": "COULD NOT LOAD REFERRALS",
    Ученик: "Student",
    "Ссылка недоступна. Открой майнер через /dojo.":
      "Link unavailable. Open the miner via /dojo.",
    "{percent}% до звания {rank}": "{percent}% to {rank}",
    "{emitted} из {cap} Coin": "{emitted} of {cap} Coin",
    "Максимальное звание": "Maximum rank",
    "Ссылка приглашения скопирована": "Invite link copied",
    "Заходи в додзё Сенсея — вместе майним SenseiCoin 🥷":
      "Join Sensei's dojo — let's mine SenseiCoin together 🥷",
    "Майнер не ответил. Попробуй ещё раз.":
      "The miner did not respond. Try again.",
    "Майнер недоступен.": "The miner is unavailable.",
    "Сенсей на техобслуживании. Попробуйте позже.":
      "Sensei is under maintenance. Try again later.",
    "Откройте майнер внутри Telegram.": "Open the miner inside Telegram.",
    "Майнинг уже идёт. Дождись конца цикла.":
      "Mining is already running. Wait for the cycle to end.",
    "Сначала забери намайненное и запусти новый цикл.":
      "Collect the mined coins first, then start a new cycle.",
    "Майнер уже запущен. Обнови экран.":
      "The miner is already running. Refresh the screen.",
    "Намайненного пока нет. Сначала запусти майнинг.":
      "Nothing has been mined yet. Start mining first.",
    "Награда уже получена. Запусти новый цикл.":
      "The reward has already been collected. Start a new cycle.",
    "Награда уже получена. Обнови экран.":
      "The reward has already been collected. Refresh the screen.",
    "Майнинг ещё не завершён.": "Mining has not finished yet.",
    "Майнер не смог выплатить награду. Попробуй ещё раз.":
      "The miner could not pay the reward. Try again.",
    "SenseiBank не может выплатить награду. Попробуй позже.":
      "SenseiBank cannot pay the reward. Try again later.",
    "Награда недоступна для этого профиля.":
      "The reward is unavailable for this profile.",
    "Оплата временно недоступна.": "Payment is temporarily unavailable.",
    "Не удалось создать счёт. Попробуй позже.":
      "Could not create the invoice. Try again later.",
    "Некорректный @username канала.": "Invalid channel @username.",
    "Укажи @username канала.": "Enter the channel @username.",
    "Задание не найдено.": "Task not found.",
    "Задание не найдено или уже отключено.":
      "The task was not found or has been disabled.",
    "Награда за это задание уже получена.":
      "The reward for this task has already been claimed.",
    "Не удалось зафиксировать награду. Попробуй ещё раз.":
      "Could not record the reward. Try again.",
    "Не удалось начислить награду. Попробуй ещё раз.":
      "Could not credit the reward. Try again.",
    "Проверка подписки временно недоступна. Попробуй позже.":
      "Subscription checks are temporarily unavailable. Try again later.",
    "Не удалось проверить подписку. Попробуй ещё раз.":
      "Could not verify the subscription. Try again.",
    "Неизвестное улучшение.": "Unknown upgrade.",
    "Профиль недоступен. Сначала открой /start.":
      "Profile unavailable. Open /start first.",
    "Неверный счёт улучшения. Открой «Улучшения» заново.":
      'Invalid upgrade invoice. Reopen "Upgrades".',
    "Счёт уже использован или устарел.":
      "The invoice has already been used or has expired.",
    "Профиль недоступен.": "Profile unavailable.",
    "Неверный платёж улучшения.": "Invalid upgrade payment.",
    "Счёт улучшения не найден. Не оплачивайте повторно.":
      "Upgrade invoice not found. Do not pay again.",
    "Кирка уже прокачана до 100 уровня.":
      "The pickaxe is already at level 100.",
    "Достигнут максимум покупок энергии.":
      "The maximum number of energy purchases has been reached.",
    "Автосбор уже включён навсегда.":
      "Auto-collect is already permanently enabled.",
  };
  const RANK_TITLES_EN = {
    Новичок: "Novice",
    Ученик: "Student",
    Подмастерье: "Apprentice",
    Адепт: "Adept",
    Мастер: "Master",
    Сенсей: "Sensei",
    Легенда: "Legend",
    Император: "Emperor",
    "Бог Рефералов": "Referral God",
  };
  const rankTitle = (rank) =>
    lang === "en" ? RANK_TITLES_EN[rank?.title] || rank?.title : rank?.title;

  const storedLanguage = () => {
    try {
      const saved = window.localStorage.getItem(LANG_KEY);
      return SUPPORTED_LANGS.includes(saved) ? saved : "ru";
    } catch {
      return "ru";
    }
  };
  let lang = storedLanguage();
  const t = (ru, vars = {}) => {
    const template = lang === "en" ? EN[ru] || ru : ru;
    return template.replace(/\{(\w+)\}/g, (match, key) =>
      Object.prototype.hasOwnProperty.call(vars, key) ? vars[key] : match,
    );
  };
  const locale = () => (lang === "en" ? "en-US" : "ru-RU");
  const coin = (value) =>
    Number.isFinite(Number(value))
      ? Math.floor(Number(value)).toLocaleString(locale())
      : "—";
  // Referral commissions include fractions of a coin (10% / 1% / 0,1%).
  const coinExact = (value) =>
    Number.isFinite(Number(value))
      ? Number(value).toLocaleString(locale(), { maximumFractionDigits: 3 })
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
    bolt: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/></svg>`,
    clock: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
  };

  const motionQuery = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;
  const reduceMotion = Boolean(motionQuery?.matches);
  const MATRIX_GLYPHS =
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789";

  const rnd = (min, max) => min + Math.random() * (max - min);
  const matrixText = () =>
    Array.from(
      { length: Math.round(rnd(7, 13)) },
      () => MATRIX_GLYPHS[Math.floor(Math.random() * MATRIX_GLYPHS.length)],
    ).join("");

  function seedAmbient() {
    const sakura = $("sakura");
    const matrix = $("matrix");
    if (!sakura || !matrix || reduceMotion) return;
    const narrow = window.innerWidth < 420;
    const leaves = narrow ? 9 : 13;
    const columns = narrow ? 9 : 13;
    for (let i = 0; i < leaves; i++) {
      const leaf = document.createElement("i");
      leaf.className = "sakura-leaf";
      leaf.style.setProperty("--x", `${rnd(1, 98)}%`);
      leaf.style.setProperty("--size", `${rnd(7, 14)}px`);
      leaf.style.setProperty("--duration", `${rnd(9, 17)}s`);
      leaf.style.setProperty("--delay", `${-rnd(0, 17)}s`);
      leaf.style.setProperty("--sway", `${rnd(18, 72)}px`);
      leaf.style.setProperty("--start", `${rnd(-45, 45)}deg`);
      leaf.style.setProperty("--opacity", rnd(0.38, 0.75).toFixed(2));
      sakura.appendChild(leaf);
    }
    for (let i = 0; i < columns; i++) {
      const column = document.createElement("span");
      column.className = "matrix-col";
      column.style.setProperty("--x", `${rnd(3, 96)}%`);
      column.style.setProperty("--size", `${rnd(8, 13)}px`);
      column.style.setProperty("--duration", `${rnd(8, 15)}s`);
      column.style.setProperty("--delay", `${-rnd(0, 15)}s`);
      column.style.setProperty("--opacity", rnd(0.12, 0.34).toFixed(2));
      column.textContent = matrixText();
      matrix.appendChild(column);
    }
    setInterval(() => {
      if (document.hidden || !matrix.childElementCount) return;
      const column =
        matrix.children[Math.floor(Math.random() * matrix.childElementCount)];
      if (column) column.textContent = matrixText();
    }, 3200);
  }

  let model = null;
  let skew = 0;
  let pending = null;
  let toastTimer = 0;
  let endRetryAt = 0;
  let activeTab = "mining";
  let tasks = [];
  let tasksLoaded = false;
  let taskBusy = null;
  let upgrades = null;
  let upgradesLoaded = false;
  let upgradeBusy = null;
  let bank = null;
  let referrals = null;
  let referralsLoaded = false;
  let referralLevel = 1;
  let referralBusy = false;
  let referralReload = false;

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
      throw Error(data.error || t("Майнер не ответил. Попробуй ещё раз."));
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
    if (!initData() || !model) return 0;
    const max = energyMax();
    if (model.phase === "ready") return max;
    const energy = Number(model.energy);
    if (!Number.isFinite(energy)) return 0;
    if (model.phase !== "mining") return Math.max(0, Math.min(max, energy));
    const drain = Number(model.energy_per_hour) || 100;
    const elapsed = Math.max(
      0,
      (serverNow() - model.server_now * 1000) / 3600000,
    );
    return Math.max(0, Math.min(max, energy - drain * elapsed));
  }

  function percent() {
    if (!model) return 0;
    if (model.phase === "ready_to_collect") return 100;
    if (model.phase !== "mining") return 0;
    return Math.min(99.9, Math.max(0, miningProgress() * 100));
  }

  function paintMiningHint() {
    if (!model) return;
    const energy = energyValue();
    const base = Number(model.base_rate) || 0;
    const rate = energy > 0 ? base : base / 10;
    $("hint").textContent = t(
      "Энергия {energy} / {max} · {rate} Coin/ч · после нуля 10%",
      { energy: Math.round(energy), max: energyMax(), rate: coin(rate) },
    );
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

  function paintMeter() {
    const meter = $("mine-meter");
    if (!meter) return;
    const active =
      model?.phase === "mining" || model?.phase === "ready_to_collect";
    meter.hidden = !active;
    if (!active) return;
    const value = percent();
    $("mine-bar").style.width = `${value}%`;
    $("mine-percent").textContent = `${value.toFixed(1)}%`;
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
    button.setAttribute("aria-label", `${label}. ${sub}`);
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
    $("profile-reward").textContent = `${coin(model?.reward)} Coin`;
    $("profile-rate").textContent =
      `${coin(model?.base_rate)} ${t("Coin / ч")}`;
    $("profile-energy").textContent = coin(model?.energy_max);
    $("profile-auto").textContent = model?.auto_collect ? t("ВКЛ") : t("ВЫКЛ");
    paintEnergy(energyValue());
    paintMeter();

    const status = $("status");
    const hint = $("hint");

    if (current === "phase-offline") {
      paintAction(
        "lock",
        t("ОТКРОЙ ЧЕРЕЗ /DOJO"),
        t("ТОЛЬКО TELEGRAM"),
        false,
        true,
      );
      $("energy").textContent = "— / —";
      renderTasks(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      renderUpgrades(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      status.textContent = t("ТОЛЬКО В TELEGRAM");
      hint.textContent = t(
        "Вне Telegram майнер не начисляет SenseiCoin и не запускает цикл.",
      );
      return;
    }

    if (current === "phase-loading") {
      paintAction("pickaxe", t("ПОДКЛЮЧЕНИЕ"), "SENSEIBANK", false, true);
      status.textContent = t("СЕНСЕЙ ПРОСЫПАЕТСЯ");
      hint.textContent = t("Проверяем состояние цикла на сервере.");
      return;
    }

    if (pending === "collect") {
      paintAction("coin", t("ЗАБИРАЕМ…"), "SENSEIBANK", false, true);
      status.textContent = t("НАГРАДА В ПУТИ");
      hint.textContent = t("Сервер начисляет SenseiCoin из банка.");
      return;
    }

    if (pending === "start") {
      paintAction("pickaxe", t("ЗАПУСК…"), t("8 ЧАСОВ"), false, true);
      status.textContent = t("СЕНСЕЙ УХОДИТ В МАЙНИНГ");
      hint.textContent = t("Создаём восьмичасовой цикл на сервере.");
      return;
    }

    if (current === "phase-mining") {
      paintAction(
        "pickaxe",
        clock(remaining()),
        t("ДО КОНЦА ЦИКЛА"),
        true,
        true,
      );
      status.textContent = t("МАЙНИНГ ИДЁТ · {percent}%", {
        percent: percent().toFixed(1),
      });
      paintMiningHint();
      return;
    }

    if (current === "phase-done") {
      paintAction(
        "coin",
        t("ЗАБРАТЬ {amount}", { amount: coin(model.reward) }),
        "SENSEICOIN",
        false,
        false,
      );
      status.textContent = t("ЦИКЛ ЗАВЕРШЁН · 100%");
      hint.textContent = t(
        "Награда из SenseiBank ждёт тебя. Забери и начни снова.",
      );
      return;
    }

    paintAction(
      "pickaxe",
      t("НАЧАТЬ МАЙНИНГ"),
      t("8 ЧАСОВ · {amount} COIN", { amount: coin(model.next_reward) }),
      false,
      false,
    );
    status.textContent = t("СЕНСЕЙ ГОТОВ");
    hint.textContent = t(
      "Кирка {rate} Coin/ч · энергия {energy} · {hours} ч полной мощности",
      {
        rate: coin(model.base_rate),
        energy: energyMax(),
        hours: energyMax() / 100,
      },
    );
  }

  function tick() {
    if (!model || model.phase !== "mining" || pending) return;
    const left = remaining();
    const label = $("action-label");
    label.textContent = clock(left);
    label.classList.add("is-timer");
    paintEnergy(energyValue());
    paintMeter();
    $("status").textContent = t("МАЙНИНГ ИДЁТ · {percent}%", {
      percent: percent().toFixed(1),
    });
    paintMiningHint();
    if (left <= 0 && Date.now() >= endRetryAt) {
      endRetryAt = Date.now() + 4000;
      refresh(true);
    }
  }

  function showToast(text, error = false) {
    const toast = $("toast");
    toast.textContent = error && lang === "en" ? EN[text] || text : text;
    toast.classList.toggle("error", error);
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
  }

  function applyTranslations() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-html]").forEach((node) => {
      node.innerHTML = t(node.dataset.i18nHtml);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
      node.setAttribute("aria-label", t(node.dataset.i18nAria));
    });
    document.querySelectorAll("[data-i18n-alt]").forEach((node) => {
      node.setAttribute("alt", t(node.dataset.i18nAlt));
    });
    document.querySelectorAll("[data-lang]").forEach((button) => {
      const active = button.dataset.lang === lang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function setLanguage(next) {
    if (!SUPPORTED_LANGS.includes(next) || next === lang) return;
    lang = next;
    try {
      window.localStorage.setItem(LANG_KEY, lang);
    } catch {}
    applyTranslations();
    render();
    if (!initData()) {
      renderTasks(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      renderUpgrades(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      renderReferrals(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    } else {
      renderTasks(tasksLoaded ? undefined : t("ЗАГРУЖАЕМ ЗАДАНИЯ…"));
      renderUpgrades(upgradesLoaded ? undefined : t("ЗАГРУЖАЕМ УЛУЧШЕНИЯ…"));
      renderReferrals(referralsLoaded ? undefined : t("ЗАГРУЖАЕМ УЧЕНИКОВ…"));
    }
    renderBank();
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
      showToast(t("Майнинг запущен · Сенсей ушёл на 8 часов"));
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
      if (bank) loadBank(true);
      celebrate(data.mined || 0);
      showToast(
        t("+{amount} SenseiCoin · баланс {balance}", {
          amount: coin(data.mined),
          balance: coin(data.balance),
        }),
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

  function renderTasks(emptyText = t("ПОКА НЕТ ЗАДАНИЙ")) {
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
      handle.textContent = t("@{username} · подписка на канал", {
        username: task.username,
      });
      name.append(title, handle);
      top.append(avatar, name);

      const chips = document.createElement("div");
      chips.className = "task-chips";
      const coinChip = document.createElement("span");
      coinChip.className = "task-chip";
      coinChip.textContent = `${coin(task.reward_coins)} Coin`;
      const energyChip = document.createElement("span");
      energyChip.className = "task-chip";
      energyChip.textContent = t("+{amount} энергии", {
        amount: task.energy_bonus,
      });
      chips.append(coinChip, energyChip);

      card.append(top, chips);

      if (task.claimed) {
        const done = document.createElement("div");
        done.className = "task-claimed";
        done.textContent = t("✓ Награда получена");
        card.appendChild(done);
      } else {
        const actions = document.createElement("div");
        actions.className = "task-actions";
        const open = document.createElement("a");
        open.className = "task-link";
        open.href = task.url;
        open.target = "_blank";
        open.rel = "noopener noreferrer";
        open.textContent = t("Подписаться");
        open.addEventListener("click", (event) => {
          if (tg?.openTelegramLink) {
            event.preventDefault();
            tg.openTelegramLink(task.url);
          }
        });
        const claim = document.createElement("button");
        claim.className = "task-claim";
        claim.textContent =
          taskBusy === task.slug ? t("Проверяем…") : t("Проверить");
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
      renderTasks(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
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
      renderTasks(t("НЕ УДАЛОСЬ ЗАГРУЗИТЬ ЗАДАНИЯ"));
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
      if (bank) loadBank(true);
      const updated = data.task || { ...task, claimed: true };
      tasks = tasks.map((item) =>
        item.slug === slug ? { ...item, ...updated, claimed: true } : item,
      );
      showToast(
        t("+{amount} SenseiCoin · +{energy} энергии", {
          amount: coin(data.reward_coins),
          energy: data.energy_bonus,
        }),
      );
    } catch (error) {
      showToast(error.message, true);
    } finally {
      taskBusy = null;
      renderTasks();
    }
  }

  function upgradeCard(icon, title, level, copy, stats, button, disabled) {
    const card = document.createElement("article");
    card.className = "upgrade-card";
    const top = document.createElement("div");
    top.className = "upgrade-top";
    const avatar = document.createElement("span");
    avatar.className = "upgrade-icon";
    avatar.innerHTML = ICONS[icon];
    const head = document.createElement("div");
    head.className = "upgrade-head";
    const name = document.createElement("b");
    name.textContent = title;
    const lvl = document.createElement("span");
    lvl.textContent = level;
    head.append(name, lvl);
    top.append(avatar, head);
    const text = document.createElement("p");
    text.className = "upgrade-copy";
    text.textContent = copy;
    const stat = document.createElement("p");
    stat.className = "upgrade-stats";
    stat.textContent = stats;
    const buy = document.createElement("button");
    buy.className = "upgrade-buy";
    buy.textContent = button;
    buy.disabled = disabled;
    card.append(top, text, stat, buy);
    return card;
  }

  function renderUpgrades(emptyText = t("УЛУЧШЕНИЯ НЕДОСТУПНЫ")) {
    const list = $("upgrades-list");
    if (!list) return;
    list.replaceChildren();
    if (!upgrades) {
      const empty = document.createElement("p");
      empty.className = "task-empty";
      empty.textContent = emptyText;
      list.appendChild(empty);
      return;
    }
    const pickaxe = upgradeCard(
      "pickaxe",
      t("КИРКА"),
      `LVL ${upgrades.pickaxe_level} / ${upgrades.pickaxe_max}`,
      t("Каждый уровень: +10 SenseiCoin в час. Действует со следующего цикла."),
      t("{rate} Coin/ч · следующий {next} Coin/ч", {
        rate: coin(upgrades.pickaxe_rate),
        next: coin(upgrades.pickaxe_next_rate),
      }),
      upgradeBusy === "pickaxe"
        ? t("СЧЁТ…")
        : upgrades.pickaxe_level >= upgrades.pickaxe_max
          ? t("МАКСИМУМ")
          : t("{stars} ⭐ · УЛУЧШИТЬ", { stars: upgrades.pickaxe_stars }),
      upgradeBusy === "pickaxe" ||
        upgrades.pickaxe_level >= upgrades.pickaxe_max,
    );
    const energy = upgradeCard(
      "bolt",
      t("ЭНЕРГИЯ"),
      `+${upgrades.energy_bonus}`,
      t(
        "Навсегда +100 к запасу. 100 энергии — час полной мощности, потом 10%; со следующего цикла.",
      ),
      t("Покупок: {bought} / {max} · база {base}", {
        bought: upgrades.energy_purchases,
        max: upgrades.energy_max_purchases,
        base: upgrades.base_energy,
      }),
      upgradeBusy === "energy"
        ? t("СЧЁТ…")
        : t("{stars} ⭐ · +100 ЭНЕРГИИ", { stars: upgrades.energy_stars }),
      upgradeBusy === "energy" ||
        upgrades.energy_purchases >= upgrades.energy_max_purchases,
    );
    const auto = upgradeCard(
      "clock",
      t("АВТОСБОР"),
      upgrades.auto_collect ? t("АКТИВЕН") : t("ВЫКЛ"),
      t(
        "Сам собирает награду и запускает новый цикл каждые 8 часов. Участие не нужно.",
      ),
      t("Один раз · работает всегда"),
      upgrades.auto_collect
        ? t("УЖЕ ВКЛЮЧЁН")
        : upgradeBusy === "auto"
          ? t("СЧЁТ…")
          : t("{stars} ⭐ · ВКЛЮЧИТЬ", { stars: upgrades.auto_stars }),
      upgradeBusy === "auto" || upgrades.auto_collect,
    );
    const buttons = [
      pickaxe.querySelector(".upgrade-buy"),
      energy.querySelector(".upgrade-buy"),
      auto.querySelector(".upgrade-buy"),
    ];
    buttons[0].addEventListener("click", () => buyUpgrade("pickaxe"));
    buttons[1].addEventListener("click", () => buyUpgrade("energy"));
    buttons[2].addEventListener("click", () => buyUpgrade("auto"));
    list.append(pickaxe, energy, auto);
  }

  async function loadUpgrades(force = false) {
    if (!initData()) {
      upgrades = null;
      renderUpgrades(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      return;
    }
    if (upgradesLoaded && !force) return;
    try {
      const data = await api("upgrades");
      upgrades = data.upgrades || null;
      upgradesLoaded = true;
      renderUpgrades();
    } catch (error) {
      upgradesLoaded = false;
      upgrades = null;
      renderUpgrades(t("НЕ УДАЛОСЬ ЗАГРУЗИТЬ УЛУЧШЕНИЯ"));
      showToast(error.message, true);
    }
  }

  async function buyUpgrade(kind) {
    if (!initData() || upgradeBusy) return;
    upgradeBusy = kind;
    renderUpgrades();
    try {
      const data = await api("buy", { kind });
      if (!tg?.openInvoice) {
        upgradeBusy = null;
        renderUpgrades();
        showToast(t("Счёт Stars создан. Открой его в Telegram."), true);
        return;
      }
      tg.openInvoice(data.invoice_url, (status) => {
        upgradeBusy = null;
        renderUpgrades();
        if (status === "paid") {
          showToast(t("Оплата получена · включаем улучшение"));
          setTimeout(() => {
            loadUpgrades(true);
            refresh(true);
          }, 1200);
          setTimeout(() => {
            loadUpgrades(true);
            refresh(true);
          }, 4500);
        } else if (status === "cancelled") {
          showToast(t("Оплата отменена"), true);
        } else if (status === "failed") {
          showToast(t("Оплата не прошла"), true);
        }
      });
    } catch (error) {
      upgradeBusy = null;
      renderUpgrades();
      showToast(error.message, true);
    }
  }

  function renderBank() {
    if (!bank) return;
    const emitted = Number(bank.total_emitted) || 0;
    const cap = Number(bank.emission_cap) || 0;
    const percent = Math.max(
      0,
      Math.min(100, Number(bank.emission_percent) || 0),
    );
    $("bank-emitted").textContent = `${coin(emitted)} Coin`;
    $("bank-cap").textContent = `${coin(cap)} Coin`;
    $("bank-remaining").textContent = `${coin(bank.emission_remaining)} Coin`;
    $("bank-supply").textContent = `${coin(bank.total_supply)} Coin`;
    $("bank-balance").textContent = `${coin(bank.bank_balance)} Coin`;
    $("bank-circulation").textContent = `${coin(bank.circulation)} Coin`;
    $("bank-users").textContent = coin(bank.users);
    const bar = $("bank-progress");
    if (bar) bar.style.width = `${percent}%`;
    const track = $("bank-progress-track");
    if (track) {
      track.setAttribute("aria-valuenow", percent.toFixed(1));
      track.setAttribute(
        "aria-valuetext",
        t("{emitted} из {cap} Coin", {
          emitted: coin(emitted),
          cap: coin(cap),
        }),
      );
    }
  }

  async function loadBank(force = false) {
    if (!initData()) return;
    if (bank && !force) return;
    try {
      bank = await api("bank");
      renderBank();
    } catch (error) {
      showToast(error.message, true);
    }
  }

  function renderReferrals(emptyText = t("ПОКА НЕТ УЧЕНИКОВ")) {
    const members = $("ref-members");
    const bonusText = $("ref-bonus-text");
    if (!referrals) {
      if (members) members.innerHTML = `<p class="task-empty">${emptyText}</p>`;
      if (bonusText) bonusText.textContent = "—";
      return;
    }

    const rank = referrals.rank || {};
    $("ref-rank").textContent =
      rank.emoji && rank.title ? `${rank.emoji} ${rankTitle(rank)}` : "—";
    $("ref-rank-next").textContent = rank.next
      ? t("ДО {rank} · {required}", {
          rank: rankTitle(rank.next).toUpperCase(),
          required: coin(rank.next.required),
        })
      : t("МАКСИМАЛЬНОЕ ЗВАНИЕ");

    const progress = Math.max(0, Math.min(100, Number(rank.progress) || 0));
    const bar = $("ref-progress");
    if (bar) bar.style.width = `${progress}%`;
    const track = $("ref-progress-track");
    if (track) {
      track.setAttribute("aria-valuenow", progress.toFixed(1));
      track.setAttribute(
        "aria-valuetext",
        rank.next
          ? t("{percent}% до звания {rank}", {
              percent: progress.toFixed(1),
              rank: rankTitle(rank.next),
            })
          : t("Максимальное звание"),
      );
    }

    $("ref-earned").textContent = `${coinExact(referrals.earned)} Coin`;
    const levels = referrals.levels || [];
    levels.forEach((item) => {
      const node = $(`ref-level-${item.level}`);
      if (node)
        node.textContent = `${coin(item.count)} · ✅ ${coin(item.active)}`;
    });

    document.querySelectorAll("[data-ref-level]").forEach((button) => {
      button.classList.toggle(
        "active",
        Number(button.dataset.refLevel) === referralLevel,
      );
    });

    const bonus = referrals.bonus || {};
    if (!bonus.eligible) {
      bonusText.textContent = t(
        "Твой аккаунт не участвует в бонусной программе активации. Комиссии 10% / 1% / 0,1% продолжают начисляться.",
      );
    } else if (bonus.paid) {
      bonusText.textContent = t("✅ Получено 50 Coin за активацию ученика.");
    } else {
      const days = Math.min(3, Math.max(0, Number(bonus.activity_days) || 0));
      bonusText.textContent = t(
        "Дни активности: {days}/3 · платный ап: {upgrade}. Выплата при наличии средств SenseiBank.",
        { days, upgrade: bonus.paid_upgrade ? "✅" : "○" },
      );
    }

    if (!members) return;
    if (!referrals.members?.length) {
      members.innerHTML = `<p class="task-empty">${emptyText}</p>`;
      return;
    }
    const list = document.createElement("div");
    list.className = "ref-member-list";
    referrals.members.forEach((member) => {
      const row = document.createElement("div");
      row.className = "ref-member";
      const status = document.createElement("span");
      status.className = "ref-member-status";
      status.textContent = member.active ? "✅" : "💤";
      const name = document.createElement("span");
      name.className = "ref-member-name";
      name.textContent = member.username
        ? `@${member.username}`
        : member.name || t("Ученик");
      row.append(status, name);
      list.appendChild(row);
    });
    members.replaceChildren(list);
  }

  async function loadReferrals(force = false) {
    if (!initData()) {
      referrals = null;
      referralsLoaded = false;
      renderReferrals(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      return;
    }
    if (referralBusy) {
      // A quick level switch must not be silently dropped by an in-flight load.
      referralReload = true;
      return;
    }
    if (referralsLoaded && !force && referrals?.level === referralLevel) return;
    referralBusy = true;
    try {
      const data = await api("referrals", { level: referralLevel });
      // A level switched while this request was in flight; the queued reload
      // will render the level the player actually selected.
      if (data.level !== referralLevel) return;
      referrals = data;
      referralsLoaded = true;
      renderReferrals();
    } catch (error) {
      referralsLoaded = false;
      renderReferrals(t("НЕ УДАЛОСЬ ЗАГРУЗИТЬ РЕФЕРАЛОВ"));
      showToast(error.message, true);
    } finally {
      referralBusy = false;
      if (referralReload) {
        referralReload = false;
        loadReferrals(true);
      }
    }
  }

  async function copyReferralLink() {
    const link = referrals?.link;
    if (!link) {
      showToast(t("Ссылка недоступна. Открой майнер через /dojo."), true);
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(link);
      } else {
        const field = document.createElement("textarea");
        field.value = link;
        field.setAttribute("readonly", "");
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.select();
        document.execCommand("copy");
        field.remove();
      }
      showToast(t("Ссылка приглашения скопирована"));
    } catch {
      showToast(link);
    }
  }

  function shareReferralLink() {
    const link = referrals?.link;
    if (!link) {
      showToast(t("Ссылка недоступна. Открой майнер через /dojo."), true);
      return;
    }
    const text = t("Заходи в додзё Сенсея — вместе майним SenseiCoin 🥷");
    const url = `https://t.me/share/url?url=${encodeURIComponent(
      link,
    )}&text=${encodeURIComponent(text)}`;
    try {
      if (tg?.openTelegramLink) tg.openTelegramLink(url);
      else window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      showToast(url, true);
    }
  }

  function setTab(name) {
    const tabs = [
      "mining",
      "tasks",
      "upgrades",
      "bank",
      "referrals",
      "profile",
    ];
    if (!tabs.includes(name)) return;
    activeTab = name;
    app.classList.toggle("tabs-open", name !== "mining");
    if (stageEl) stageEl.scrollTop = 0;
    document.querySelectorAll(".tab").forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("active", active);
      if (active) tab.setAttribute("aria-current", "page");
      else tab.removeAttribute("aria-current");
    });
    tabs.forEach((key) => {
      $(`view-${key}`).hidden = key !== name;
    });
    if (name === "tasks") loadTasks();
    if (name === "upgrades") loadUpgrades();
    if (name === "bank") loadBank(true);
    if (name === "referrals") loadReferrals(true);
    // Chat games/mining change users.coins outside this WebView; re-read the
    // authoritative server balance whenever the player returns to a view.
    if (name === "mining" || name === "profile") refresh(true);
    closeSheet();
  }

  function openSheet() {
    $("sheet").hidden = false;
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

  $("bank-refresh").addEventListener("click", () => loadBank(true));

  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  });

  document.querySelectorAll("[data-ref-level]").forEach((button) => {
    button.addEventListener("click", () => {
      const level = Number(button.dataset.refLevel);
      if (level === referralLevel || ![1, 2, 3].includes(level)) return;
      referralLevel = level;
      document.querySelectorAll("[data-ref-level]").forEach((node) => {
        node.classList.toggle(
          "active",
          Number(node.dataset.refLevel) === referralLevel,
        );
      });
      const members = $("ref-members");
      if (members)
        members.innerHTML = `<p class="task-empty">${t(
          "ЗАГРУЖАЕМ УЧЕНИКОВ…",
        )}</p>`;
      loadReferrals(true);
    });
  });

  $("ref-copy").addEventListener("click", copyReferralLink);
  $("ref-share").addEventListener("click", shareReferralLink);

  document.querySelectorAll("[data-close='sheet']").forEach((node) => {
    node.addEventListener("click", closeSheet);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSheet();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refresh(true);
      if (activeTab === "referrals") loadReferrals(true);
    }
  });
  setInterval(tick, 250);
  setInterval(() => {
    if (!document.hidden) refresh(true);
  }, 30000);

  seedAmbient();
  applyTranslations();
  render();
  if (initData()) {
    refresh();
    loadTasks();
    loadUpgrades();
    loadBank();
  } else {
    renderTasks(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    renderUpgrades(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    renderReferrals(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
  }
})();
