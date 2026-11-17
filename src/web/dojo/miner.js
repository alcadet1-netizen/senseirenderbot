// Сервер хранит 3-часовой цикл; интерфейс показывает таймер, энергию, прогресс и сбор.
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
    БОНУСЫ: "BONUSES",
    "Подпишись на канал или запусти приложение и забери SenseiCoin и разовый заряд энергии. Награда за каждое задание — один раз; базовый лимит энергии не растёт.":
      "Subscribe to a channel or launch an app and claim SenseiCoin plus a one-cycle energy charge. Each task reward can be claimed once; the base energy cap does not grow.",
    "ЗАГРУЖАЕМ ЗАДАНИЯ…": "LOADING TASKS…",
    "Подписку проверяет сервер через Telegram. Ссылки на приложения открываются кнопкой «Запустить».":
      "The server verifies subscriptions via Telegram. App links open with the Launch button.",
    "Приложение · {host}": "App · {host}",
    Запустить: "Launch",
    Получить: "Claim",
    УЛУЧШЕНИЯ: "UPGRADES",
    ПРОКАЧКА: "UPGRADES",
    "Улучшения за Telegram Stars. Кирка повышает добычу, энергия держит полную мощность дольше, буст ускоряет фарм на 1 час, автосбор работает без тебя.":
      "Telegram Stars upgrades. The pickaxe boosts mining, energy keeps full power longer, a boost speeds up farming for 1 hour, and auto-collect works without you.",
    "ЗАГРУЖАЕМ УЛУЧШЕНИЯ…": "LOADING UPGRADES…",
    "Оплата Stars · улучшения не сгорают":
      "Stars payment · upgrades never expire",
    ЭМИССИЯ: "EMISSION",
    "Всего в экономике может быть 10 000 000 000 Coin — жёсткий лимит. Новые Coin появляются только при стартовом заполнении SenseiBank и наборе новичка. Майнинг, задания и игры сначала списывают награду из SenseiBank; если банк пуст, начисления нет — лимит не растёт.":
      "The economy can hold at most 10,000,000,000 Coin. New coins appear only in the initial SenseiBank fill and the newcomer kit. Mining, tasks and games debit the reward from SenseiBank first; if the bank is empty, nothing is credited and the cap does not grow.",
    "Roadmap SenseiCoin": "SenseiCoin roadmap",
    AIRDROP: "AIRDROP",
    "СТАРТ МАЙНЕРА": "MINER START",
    "КОГДА ВСЕ МОНЕТЫ ДОБЫТЫ": "WHEN ALL COINS ARE MINED",
    "Лента блоков майнинга": "Mining block feed",
    "Последние найденные блоки": "Latest found blocks",
    "ЖДЁМ ПЕРВЫЙ БЛОК": "WAITING FOR THE FIRST BLOCK",
    "смайнил блок": "mined a block",
    "ты · смайнил блок": "you · mined a block",
    "СЕТЬ · ОЖИДАНИЕ": "NETWORK · IDLE",
    "ЦЕПОЧКА · БЛОК {block}": "CHAIN · BLOCK {block}",
    "БЛОК ГОТОВ · ЖДЁТ СБОРА": "BLOCK READY · WAITING TO COLLECT",
    "ЗАПУСТИ МАЙНИНГ, ЧТОБЫ НАЧАТЬ ДОБЫЧУ БЛОКОВ":
      "Start mining to begin producing blocks",
    "HASH 0x{hash} · NONCE {nonce} · PULSE {bpm} BPM":
      "HASH 0x{hash} · NONCE {nonce} · PULSE {bpm} BPM",
    "100% · HASH 0x{hash} · NONCE {nonce}":
      "100% · HASH 0x{hash} · NONCE {nonce}",
    "ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА": "YOUR REFERRAL LINK",
    "Ссылка на майнер · комиссии 10% / 1% / 0,1%":
      "Link to the miner · 10% / 1% / 0.1% commissions",
    "ПОДЕЛИТЬСЯ ССЫЛКОЙ": "SHARE THE LINK",
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
    "СКОПИРОВАТЬ ПРИГЛАШЕНИЕ": "COPY INVITE",
    ПОДЕЛИТЬСЯ: "SHARE",
    "🎁 Бонус за ученика": "🎁 Referral bonus",
    "10% / 1% / 0,1% с каждого платного апа катаны по трём уровням. Остаток уходит в SenseiBank.":
      "10% / 1% / 0.1% from every paid katana upgrade across three levels. The remainder goes to SenseiBank.",
    ПРОФИЛЬ: "PROFILE",
    "СЕНСЕЙ-МАЙНЕР": "SENSEI MINER",
    Баланс: "Balance",
    Добыча: "Mining rate",
    Энергия: "Energy",
    Цикл: "Cycle",
    "3 часа": "3 hours",
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
    "<b>Запусти цикл.</b> Сенсей уходит в майнинг ровно на 3 часа.":
      "<b>Start a cycle.</b> Sensei goes mining for exactly 3 hours.",
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
    "ЗАГРУЗКА…": "LOADING…",
    "Загрузка SenseiCoin": "Loading SenseiCoin",
    "СЕНСЕЙ ПРОСЫПАЕТСЯ": "SENSEI IS WAKING UP",
    "Проверяем состояние цикла на сервере.":
      "Checking the cycle state on the server.",
    "ЗАБИРАЕМ…": "COLLECTING…",
    "НАГРАДА В ПУТИ": "REWARD IN TRANSIT",
    "Сервер начисляет SenseiCoin из банка.":
      "The server credits SenseiCoin from the bank.",
    "ЗАПУСК…": "STARTING…",
    "3 ЧАСА": "3 HOURS",
    "СЕНСЕЙ УХОДИТ В МАЙНИНГ": "SENSEI GOES MINING",
    "Создаём трёхчасовой цикл на сервере.":
      "Creating a three-hour cycle on the server.",
    "ДО КОНЦА ЦИКЛА": "UNTIL THE CYCLE ENDS",
    "МАЙНИНГ ИДЁТ · {percent}%": "MINING · {percent}%",
    "ЗАБРАТЬ {amount}": "COLLECT {amount}",
    "ЦИКЛ ЗАВЕРШЁН · 100%": "CYCLE COMPLETE · 100%",
    "Награда из SenseiBank ждёт тебя. Забери и начни снова.":
      "Your SenseiBank reward is waiting. Collect it and start again.",
    "НАЧАТЬ МАЙНИНГ": "START MINING",
    "3 ЧАСА · {amount} COIN": "3 HOURS · {amount} COIN",
    "СЕНСЕЙ ГОТОВ": "SENSEI IS READY",
    "Кирка {rate} Coin/ч · энергия {energy} · {hours} ч полной мощности":
      "Pickaxe {rate} Coin/h · energy {energy} · {hours} h at full power",
    "Энергия {energy} / {max} · {rate} Coin/ч · после нуля 10%":
      "Energy {energy} / {max} · {rate} Coin/h · 10% after zero",
    "10 ⭐ · ПОПОЛНИТЬ": "10 ⭐ · REFILL",
    "Пополнить энергию за 10 ⭐": "Refill energy for 10 ⭐",
    "Пополняем энергию": "Refilling energy",
    "Энергия пополнена": "Energy refilled",
    "Пополнить можно только при нулевой энергии.":
      "You can refill only at zero energy.",
    "Майнинг запущен · Сенсей ушёл на 3 часа":
      "Mining started · Sensei left for 3 hours",
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
    "+{amount} SenseiCoin · +{energy} энергии на цикл":
      "+{amount} SenseiCoin · +{energy} energy for one cycle",
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
    "Сам собирает награду и запускает новый цикл каждые 3 часа. Участие не нужно.":
      "Collects the reward and starts a new cycle every 3 hours. No action needed.",
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
    "ЗАГРУЖАЕМ ССЫЛКУ…": "LOADING LINK…",
    "Ссылка недоступна. Открой майнер через /dojo.":
      "Link unavailable. Open the miner via /dojo.",
    "{percent}% до звания {rank}": "{percent}% to {rank}",
    "{emitted} из {cap} Coin": "{emitted} of {cap} Coin",
    "Максимальное звание": "Maximum rank",
    "Приглашение с ссылкой скопировано": "Invite text with the link copied",
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
    "+50% СКОРОСТЬ": "+50% SPEED",
    "СКОРОСТЬ +50%": "SPEED +50%",
    "1 ЧАС": "1 HOUR",
    "КУПЛЕНО В ЦИКЛЕ": "BOUGHT THIS CYCLE",
    "АКТИВЕН · {time}": "ACTIVE · {time}",
    "Ускоряет добычу на 50% на один час. Одна покупка за цикл.":
      "Boosts mining by 50% for one hour. One purchase per cycle.",
    "1 ⭐ · +1 ЧАС · 1 РАЗ ЗА ЦИКЛ": "1 ⭐ · +1 HOUR · ONCE PER CYCLE",
    "{stars} ⭐ · УСКОРИТЬ": "{stars} ⭐ · SPEED UP",
    "Скорость +50% · осталось {time}": "Speed +50% · {time} left",
    "Сожжено {amount} Coin. Эмиссия уменьшена навсегда.":
      "Burned {amount} Coin. Emission is permanently reduced.",
    "Скорость +50% активирована": "Speed +50% activated",
    "СЖИГАЕМ…": "BURNING…",
    "СЖЕЧЬ НАВСЕГДА": "BURN FOREVER",
    "Сжечь SenseiCoin": "Burn SenseiCoin",
    "СЖЕЧЬ ЭМИССИЮ": "BURN EMISSION",
    "Это добровольное и необратимое сжигание твоих Coin. Монеты исчезают навсегда: вернуть их нельзя, отменить операцию после подтверждения тоже.":
      "This is a voluntary and irreversible burn of your own Coin. The coins disappear forever: they cannot be returned and the operation cannot be cancelled after confirmation.",
    "Твой баланс": "Your balance",
    "Сколько Coin сжечь": "How much Coin to burn",
    "Быстрый выбор суммы": "Quick amount selection",
    ВСЁ: "ALL",
    Сгорит: "Burns",
    "Coin · останется": "Coin · left",
    "Всего сожжено сообществом": "Burned by the community",
    ОТМЕНА: "CANCEL",
    "Каждый сожжённый Coin навсегда уменьшает эмиссию SenseiCoin. Меньше предложения — чище токеномика и сильнее история дефицита к TGE. Это твой добровольный вклад в проект, а не инвестиция и не обещание цены или листинга.":
      "Every burned Coin permanently reduces SenseiCoin emission. Less supply means cleaner tokenomics and a stronger scarcity story ahead of the TGE. This is your voluntary contribution to the project, not an investment or a promise of price or listing.",
    "Открой майнер через /dojo.": "Open the miner via /dojo.",
    "Укажи целое количество Coin больше нуля.":
      "Enter a whole Coin amount greater than zero.",
    "Недостаточно Coin для сжигания.": "Not enough Coin to burn.",
    "Баланс изменился. Обнови экран и попробуй снова.":
      "The balance changed. Refresh the screen and try again.",
    "Не удалось сжечь Coin. Попробуй позже.":
      "Could not burn Coin. Try again later.",
    "Эмиссия уже не может быть уменьшена.":
      "Emission cannot be reduced any further.",
    "Сжигание недоступно для этого профиля.":
      "Burning is unavailable for this profile.",
    "Неверный запрос сжигания. Открой окно заново.":
      "Invalid burn request. Reopen the window and try again.",
    "Сжигание уже обрабатывается. Подожди и обнови экран.":
      "The burn is already being processed. Wait and refresh the screen.",
    НАМАЙНЕНО: "MINED",
    "ЭМИССИИ ВЫПУЩЕНО": "OF EMISSION RELEASED",
    "ОСТАЛОСЬ ДО КОНЦА МАЙНИНГА": "LEFT UNTIL MINING ENDS",
    Намайнено: "Mined",
    "Осталось до конца майнинга": "Left until mining ends",
    "Сожжено навсегда": "Burned forever",
    "Вернулось из автобана": "Returned from autoban",
    "Coin забаненных и автобаненных игроков возвращаются в SenseiBank. Сжигание уменьшает эмиссию навсегда и не пополняет банк.":
      "Coins from banned and autobanned players return to SenseiBank. Burning permanently reduces emission and never refills the bank.",
    "Жёсткий лимит: 10 000 000 000 Coin. Награды списываются из SenseiBank, а не печатаются сверх лимита. Пустой банк останавливает начисления.":
      "Hard cap: 10,000,000,000 Coin. Rewards are debited from SenseiBank, never printed above the cap. An empty bank stops payouts.",
    ВЫПУЩЕНО: "RELEASED",
    ЛИМИТ: "CAP",
    ОСТАЛОСТЬ: "LEFT",
    ОСТАЛОСЬ: "LEFT",
    "Автобан возвращает Coin в SenseiBank. Сжигание уменьшает эмиссию навсегда и не пополняет банк.":
      "Autoban returns Coin to SenseiBank. Burning permanently reduces emission and never refills the bank.",
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
    launch: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 3h7v7"/><path d="M10 14 21 3"/>
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>`,
  };

  const TIMER_SEGMENTS = {
    top: "M7 4 H17",
    upperLeft: "M4 7 V19",
    upperRight: "M20 7 V19",
    middle: "M7 22 H17",
    lowerLeft: "M4 25 V37",
    lowerRight: "M20 25 V37",
    bottom: "M7 40 H17",
  };
  const TIMER_DIGITS = {
    0: ["top", "upperLeft", "upperRight", "lowerLeft", "lowerRight", "bottom"],
    1: ["upperRight", "lowerRight"],
    2: ["top", "upperRight", "middle", "lowerLeft", "bottom"],
    3: ["top", "upperRight", "middle", "lowerRight", "bottom"],
    4: ["upperLeft", "upperRight", "middle", "lowerRight"],
    5: ["top", "upperLeft", "middle", "lowerRight", "bottom"],
    6: ["top", "upperLeft", "middle", "lowerLeft", "lowerRight", "bottom"],
    7: ["top", "upperRight", "lowerRight"],
    8: [
      "top",
      "upperLeft",
      "upperRight",
      "middle",
      "lowerLeft",
      "lowerRight",
      "bottom",
    ],
    9: ["top", "upperLeft", "upperRight", "middle", "lowerRight", "bottom"],
  };
  const TIMER_LAYOUT = [
    { kind: "digit", x: 0 },
    { kind: "digit", x: 27 },
    { kind: "colon", x: 56 },
    { kind: "digit", x: 66 },
    { kind: "digit", x: 93 },
    { kind: "colon", x: 122 },
    { kind: "digit", x: 132 },
    { kind: "digit", x: 159 },
  ];
  const timerDigitNodes = [];

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
    const mist = $("ambient-mist");
    const dust = $("ambient-dust");
    if (mist && !mist.childElementCount) {
      for (let i = 0; i < 4; i++) {
        const puff = document.createElement("i");
        puff.className = "ambient-puff";
        puff.style.setProperty("--x", `${rnd(-20, 82)}%`);
        puff.style.setProperty("--y", `${rnd(38, 88)}%`);
        puff.style.setProperty("--size", `${rnd(150, 280)}px`);
        puff.style.setProperty("--duration", `${rnd(13, 22)}s`);
        puff.style.setProperty("--delay", `${rnd(-18, 0)}s`);
        puff.style.setProperty("--drift", `${rnd(-60, 60)}px`);
        mist.appendChild(puff);
      }
    }
    if (dust && !dust.childElementCount) {
      for (let i = 0; i < 22; i++) {
        const mote = document.createElement("i");
        mote.className = "ambient-mote";
        mote.style.setProperty("--x", `${rnd(2, 98)}%`);
        mote.style.setProperty("--size", `${rnd(1, 2.6)}px`);
        mote.style.setProperty("--duration", `${rnd(10, 23)}s`);
        mote.style.setProperty("--delay", `${rnd(-20, 0)}s`);
        mote.style.setProperty("--drift", `${rnd(-42, 42)}px`);
        mote.style.setProperty("--opacity", rnd(0.25, 0.85).toFixed(2));
        dust.appendChild(mote);
      }
    }
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

  function seedMiningParticles() {
    const layer = $("mining-particles");
    if (!layer || layer.childElementCount) return;
    for (let i = 0; i < 14; i++) {
      const node = document.createElement("i");
      node.style.setProperty("--x", `${rnd(6, 94)}%`);
      node.style.setProperty("--size", `${rnd(1.5, 3.6).toFixed(1)}px`);
      node.style.setProperty("--delay", `${-rnd(0, 5).toFixed(2)}s`);
      node.style.setProperty("--duration", `${rnd(3.4, 7.2).toFixed(2)}s`);
      node.style.setProperty("--drift", `${rnd(-18, 18).toFixed(1)}px`);
      layer.appendChild(node);
    }
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
  let burnBusy = false;
  let burnRequest = "";
  let bank = null;
  let referrals = null;
  let referralsLoaded = false;
  let referralLevel = 1;
  let referralBusy = false;
  let referralReload = false;
  let referralAttempted = false;

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
    bootFirstModel();
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
    if (model.phase === "ready") {
      const readyEnergy = Number(model.energy);
      return Number.isFinite(readyEnergy) ? Math.max(0, readyEnergy) : max;
    }
    const energy = Number(model.energy);
    if (!Number.isFinite(energy)) return 0;
    if (model.phase !== "mining") return Math.max(0, energy);
    const drain = Number(model.energy_per_hour) || 100;
    const elapsed = Math.max(
      0,
      (serverNow() - model.server_now * 1000) / 3600000,
    );
    // Task and refill energy may sit above the permanent cap; it must remain
    // visible as 200 / 100 rather than being clipped to the cap.
    return Math.max(0, energy - drain * elapsed);
  }

  function percent() {
    if (!model) return 0;
    if (model.phase === "ready_to_collect") return 100;
    if (model.phase !== "mining") return 0;
    return Math.min(99.9, Math.max(0, miningProgress() * 100));
  }

  function paintBoost() {
    const pill = $("boost-pill");
    const timer = $("boost-timer");
    if (!pill || !timer || !model) return;
    const until = Number(model.boost_until) * 1000;
    const left = Math.max(0, until - serverNow());
    const active = Boolean(initData() && until > serverNow());
    const cardTimer = document.querySelector("[data-boost-timer]");
    if (cardTimer) {
      cardTimer.textContent = left
        ? t("АКТИВЕН · {time}", { time: clock(left) })
        : t("1 ЧАС");
    }
    pill.hidden = !active;
    if (!active) return;
    timer.textContent = clock(left);
    pill.setAttribute(
      "aria-label",
      t("Скорость +50% · осталось {time}", { time: clock(left) }),
    );
  }

  function paintMiningHint() {
    if (!model) return;
    const energy = energyValue();
    const base = Number(model.base_rate) || 0;
    const boostActive =
      Number(model.boost_until) * 1000 > serverNow() && energy > 0;
    const boost = boostActive
      ? 1 + (Number(model.boost_percent) || 50) / 100
      : 1;
    const rate = energy > 0 ? base * boost : base / 10;
    $("hint").textContent = t(
      "Энергия {energy} / {max} · {rate} Coin/ч · после нуля 10%",
      { energy: Math.floor(energy), max: energyMax(), rate: coin(rate) },
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
    const rounded = Math.max(0, Math.floor(value));
    $("energy").textContent = `${rounded} / ${max}`;
    $("energy-bar").style.width = `${Math.min(100, (rounded / max) * 100)}%`;
    $("energy-track").setAttribute("aria-valuemax", String(max));
    $("energy-track").setAttribute(
      "aria-valuenow",
      String(Math.min(max, rounded)),
    );
    $("energy-track").setAttribute("aria-valuetext", `${rounded} / ${max}`);
    const card = $("energy-card");
    if (card) {
      const empty = model?.phase === "mining" && rounded <= 0 && initData();
      card.classList.toggle("is-empty", Boolean(empty));
      card.setAttribute("aria-disabled", empty ? "false" : "true");
      card.setAttribute(
        "aria-label",
        empty ? t("Пополнить энергию за 10 ⭐") : t("Энергия майнера"),
      );
      card.tabIndex = empty ? 0 : -1;
    }
  }

  function paintMeter() {
    const meter = $("mine-meter");
    if (!meter) return;
    meter.hidden = false;
    const active =
      model?.phase === "mining" || model?.phase === "ready_to_collect";
    meter.classList.toggle("is-idle", !active);
    const value = active ? percent() : 0;
    $("mine-bar").style.width = `${value}%`;
    $("mine-percent").textContent = `${value.toFixed(1)}%`;
  }

  let chainSession = "";
  let chainLastBlock = 0;

  function pseudoHash(seed) {
    let value = seed >>> 0 || 1;
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b) >>> 0;
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b) >>> 0;
    return ((value ^ (value >>> 16)) >>> 0).toString(16).padStart(8, "0");
  }

  function currentUserId() {
    const direct = tg?.initDataUnsafe?.user?.id;
    if (direct) return String(direct);
    try {
      const raw = new URLSearchParams(initData()).get("user");
      const user = raw ? JSON.parse(raw) : null;
      return user?.id ? String(user.id) : "";
    } catch {
      return "";
    }
  }

  function maskId(value) {
    const clean = String(value || "").replace(/\D/g, "");
    if (clean.length < 4) return "ID…";
    return `${clean.slice(0, 3)}…${clean.slice(-2)}`;
  }

  function networkId(block) {
    const seed = (block * 2654435761 + 40503) >>> 0;
    const digits = 100000000 + (parseInt(pseudoHash(seed), 16) % 900000000);
    return String(digits);
  }

  function chainTime(at) {
    try {
      return new Date(at * 1000).toLocaleTimeString(
        lang === "en" ? "en-GB" : "ru-RU",
        { hour: "2-digit", minute: "2-digit", second: "2-digit" },
      );
    } catch {
      return "--:--:--";
    }
  }

  function makeChainRow(block, at, mine = false) {
    const row = document.createElement("li");
    row.className = `chain-row${mine ? " is-mine is-new" : " is-new"}`;
    row.dataset.block = String(block);
    const dot = document.createElement("span");
    dot.className = "chain-dot";
    const id = document.createElement("span");
    id.className = "chain-id";
    const local = currentUserId();
    id.textContent = maskId(mine && local ? local : networkId(block));
    const verb = document.createElement("span");
    verb.className = "chain-verb";
    verb.textContent = mine ? t("ты · смайнил блок") : t("смайнил блок");
    const time = document.createElement("time");
    time.className = "chain-time";
    time.dateTime = new Date(at * 1000).toISOString();
    time.textContent = chainTime(at);
    row.append(dot, id, verb, time);
    return row;
  }

  function pushChainRow(feed, block, at, mine = false) {
    feed.prepend(makeChainRow(block, at, mine));
    while (feed.children.length > 3) feed.lastElementChild.remove();
  }

  function resetChainFeed(feed, rows) {
    feed.replaceChildren();
    rows.forEach((row) =>
      feed.appendChild(makeChainRow(row.block, row.at, row.mine)),
    );
  }

  function paintChain() {
    const panel = $("chain-panel");
    const status = $("chain-status");
    const feed = $("chain-feed");
    const bpmNode = $("chain-bpm");
    if (!panel || !status || !feed || !bpmNode) return;
    const mining = initData() && model?.phase === "mining";
    const complete = initData() && model?.phase === "ready_to_collect";
    panel.classList.toggle("is-live", Boolean(mining));
    panel.classList.toggle("is-complete", Boolean(complete));

    const session = `${model?.phase || "none"}|${model?.started_at || ""}|${model?.finish_at || ""}|${lang}`;
    const reset = session !== chainSession;
    chainSession = session;

    if (!mining && !complete) {
      if (reset) {
        const now = serverNow() / 1000;
        resetChainFeed(
          feed,
          [0, 1, 2].map((index) => ({
            block: 184000 + Math.floor(now / 7) - index,
            at: now - index * 7,
            mine: false,
          })),
        );
      }
      status.textContent = t("СЕТЬ · ОЖИДАНИЕ");
      bpmNode.textContent = "— BPM";
      return;
    }

    const started = Number(model.started_at) || serverNow() / 1000;
    const finish = Number(model.finish_at) || serverNow() / 1000;
    const blockAt = (at) =>
      184000 + Math.max(0, Math.floor((at - started) / 7));
    const timeAt = (block) => started + Math.max(0, block - 184000) * 7;

    if (complete) {
      if (reset) {
        const finalBlock = blockAt(finish);
        const rows = [];
        // The finished block is ours and sits at the top of the strip.
        rows.push({ block: finalBlock, at: finish, mine: true });
        for (let i = 1; i <= 2; i += 1) {
          rows.push({
            block: finalBlock - i,
            at: Math.max(started, finish - i * 7),
            mine: false,
          });
        }
        resetChainFeed(feed, rows);
      }
      status.textContent = t("БЛОК ГОТОВ · ЖДЁТ СБОРА");
      bpmNode.textContent = "— BPM";
      return;
    }

    const now = serverNow() / 1000;
    const currentBlock = blockAt(Math.min(now, finish));
    if (reset) {
      const rows = [];
      for (let i = 0; i < 3; i += 1) {
        const block = currentBlock - i;
        rows.push({
          block,
          at: Math.min(now, timeAt(block)),
          mine: false,
        });
      }
      resetChainFeed(feed, rows);
      chainLastBlock = currentBlock;
    } else if (currentBlock > chainLastBlock) {
      const next = Math.min(currentBlock, chainLastBlock + 6);
      for (let block = chainLastBlock + 1; block <= next; block += 1) {
        pushChainRow(feed, block, Math.min(now, timeAt(block)));
      }
      chainLastBlock = next;
    }

    const bpm = 64 + (currentBlock % 9);
    panel.style.setProperty("--beat", `${(60 / bpm).toFixed(2)}s`);
    status.textContent = t("ЦЕПОЧКА · БЛОК {block}", {
      block: coin(currentBlock),
    });
    bpmNode.textContent = `${bpm} BPM`;
  }

  function buildTimerFace() {
    const svg = $("timer-digits");
    const glyphs = $("timer-glyphs");
    if (!svg || !glyphs || timerDigitNodes.length) return;
    const ns = "http://www.w3.org/2000/svg";
    TIMER_LAYOUT.forEach((slot) => {
      if (slot.kind === "colon") {
        const group = document.createElementNS(ns, "g");
        group.setAttribute("transform", `translate(${slot.x} 0)`);
        [16, 31].forEach((cy) => {
          const dot = document.createElementNS(ns, "circle");
          dot.setAttribute("cx", "3");
          dot.setAttribute("cy", String(cy));
          dot.setAttribute("r", "2.8");
          dot.setAttribute("class", "timer-colon-dot");
          group.appendChild(dot);
        });
        glyphs.appendChild(group);
        return;
      }
      const group = document.createElementNS(ns, "g");
      group.setAttribute("transform", `translate(${slot.x} 0)`);
      const segments = {};
      Object.entries(TIMER_SEGMENTS).forEach(([name, pathData]) => {
        const path = document.createElementNS(ns, "path");
        path.setAttribute("d", pathData);
        path.setAttribute("class", "timer-seg");
        group.appendChild(path);
        segments[name] = path;
      });
      glyphs.appendChild(group);
      timerDigitNodes.push(segments);
    });
  }

  function paintTimerFace(value) {
    if (!timerDigitNodes.length) buildTimerFace();
    if (!timerDigitNodes.length) return;
    const digits = String(value).replace(/\D/g, "").slice(0, 6);
    timerDigitNodes.forEach((segments, index) => {
      const active = TIMER_DIGITS[digits[index]] || [];
      Object.entries(segments).forEach(([name, path]) => {
        path.classList.toggle("is-on", active.includes(name));
      });
    });
  }

  function paintAction(icon, label, sub, timer = false, disabled = true) {
    const button = $("action");
    const labelNode = $("action-label");
    const iconNode = $("orb-icon");
    iconNode.innerHTML = ICONS[icon] || ICONS.pickaxe;
    iconNode.classList.toggle("is-hidden", timer);
    iconNode.setAttribute("aria-hidden", timer ? "true" : "false");
    labelNode.textContent = label;
    labelNode.classList.toggle("is-timer", timer);
    labelNode.classList.toggle("is-timer-hidden", timer);
    button.classList.toggle("is-timer", timer);
    const timerFace = $("timer-face");
    if (timerFace) timerFace.hidden = !timer;
    if (timer) paintTimerFace(label);
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
    paintBoost();
    paintBurn();
    paintMeter();
    paintChain();

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
      paintAction("pickaxe", t("ЗАПУСК…"), t("3 ЧАСА"), false, true);
      status.textContent = t("СЕНСЕЙ УХОДИТ В МАЙНИНГ");
      hint.textContent = t("Создаём трёхчасовой цикл на сервере.");
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
      t("3 ЧАСА · {amount} COIN", { amount: coin(model.next_reward) }),
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
    if (!model) return;
    // The boost pill must keep counting down even while a cycle is ready.
    paintBoost();
    if (model.phase !== "mining" || pending) return;
    const left = remaining();
    const label = $("action-label");
    const timerText = clock(left);
    label.textContent = timerText;
    label.classList.add("is-timer");
    paintTimerFace(timerText);
    paintEnergy(energyValue());
    paintBurn();
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

  const bootEl = $("boot");
  const bootBar = $("boot-bar");
  const bootPercentEl = $("boot-percent");
  const bootTrack = $("boot-track");
  const bootStatusEl = $("boot-status");
  const BOOT_MIN_MS = 1600;
  const bootStartedAt = performance.now();
  let bootProgress = 0;
  let bootGoal = 0;
  let bootFinished = false;
  let bootPulseTimer = null;

  function paintBoot() {
    if (!bootBar) return;
    const value = Math.max(0, Math.min(100, bootProgress));
    bootBar.style.width = `${value}%`;
    if (bootPercentEl) bootPercentEl.textContent = `${Math.round(value)}%`;
    if (bootTrack) {
      bootTrack.setAttribute("aria-valuenow", String(Math.round(value)));
    }
  }

  function bootSetGoal(goal, status) {
    if (bootFinished) return;
    bootGoal = Math.max(bootGoal, Math.min(100, goal));
    if (status && bootStatusEl) bootStatusEl.textContent = status;
  }

  function seedBoot() {
    const smoke = $("boot-smoke");
    const sparks = $("boot-sparks");
    if (!smoke || !sparks) return;
    for (let i = 0; i < 9; i++) {
      const puff = document.createElement("i");
      puff.className = "boot-puff";
      puff.style.setProperty("--x", `${rnd(-18, 86)}%`);
      puff.style.setProperty("--y", `${rnd(18, 88)}%`);
      puff.style.setProperty("--size", `${rnd(130, 290)}px`);
      puff.style.setProperty("--opacity", String(rnd(0.16, 0.38)));
      puff.style.setProperty("--dx", `${rnd(-50, 50)}px`);
      puff.style.setProperty("--dy", `${rnd(-90, -24)}px`);
      puff.style.setProperty("--duration", `${rnd(7, 14)}s`);
      puff.style.setProperty("--delay", `${rnd(-12, 0)}s`);
      smoke.append(puff);
    }
    for (let i = 0; i < 20; i++) {
      const spark = document.createElement("i");
      spark.className = "boot-spark";
      spark.style.setProperty("--x", `${rnd(4, 96)}%`);
      spark.style.setProperty("--y", `${rnd(4, 46)}%`);
      spark.style.setProperty("--size", `${rnd(1.5, 3.6)}px`);
      spark.style.setProperty("--drift", `${rnd(-34, 34)}px`);
      spark.style.setProperty("--duration", `${rnd(5, 11)}s`);
      spark.style.setProperty("--delay", `${rnd(-10, 2)}s`);
      sparks.append(spark);
    }
    paintBoot();
    bootSetGoal(8);
    bootPulseTimer = window.setInterval(() => {
      if (bootFinished) return;
      // Fill up to the current milestone, then keep the bar alive with a
      // very slow drift while the server is still answering. Real milestones
      // (26/58/94/100) always jump back ahead, so this never races to 100.
      if (bootGoal < 88) bootGoal += 0.06;
      bootProgress = Math.min(
        bootGoal,
        bootProgress + Math.max(0.18, (bootGoal - bootProgress) * 0.07),
      );
      paintBoot();
    }, 90);
  }

  function bootFirstModel() {
    if (bootFinished) return;
    // The app is already interactive under the fading splash: a player can
    // tap the orb even while the last smoke animation finishes.
    if (bootEl) bootEl.classList.add("is-ready");
    bootSetGoal(58, t("ЗАГРУЗКА…"));
  }

  function finishBoot() {
    if (bootFinished || !bootEl) return;
    bootFinished = true;
    bootProgress = 100;
    paintBoot();
    bootEl.classList.add("is-ready");
    if (bootPulseTimer) window.clearInterval(bootPulseTimer);
    window.setTimeout(() => {
      bootEl.classList.add("is-done");
      window.setTimeout(() => {
        bootEl.hidden = true;
      }, 650);
    }, 320);
  }

  function completeBoot(status) {
    if (bootFinished) return;
    if (status && bootStatusEl) bootStatusEl.textContent = status;
    bootSetGoal(94);
    const elapsed = performance.now() - bootStartedAt;
    window.setTimeout(finishBoot, Math.max(0, BOOT_MIN_MS - elapsed));
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
    paintReferralLink();
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
      showToast(t("Майнинг запущен · Сенсей ушёл на 3 часа"));
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
      const isLink = task.kind === "link";
      const card = document.createElement("article");
      card.className = `task-card${task.claimed ? " claimed" : ""}${isLink ? " is-link" : ""}`;

      const top = document.createElement("div");
      top.className = "task-top";
      const avatar = document.createElement("span");
      avatar.className = "task-avatar";
      avatar.innerHTML = isLink ? ICONS.launch : ICONS.telegram;
      const name = document.createElement("span");
      name.className = "task-name";
      const title = document.createElement("b");
      title.textContent =
        task.title || (isLink ? task.host : `@${task.username}`);
      const handle = document.createElement("span");
      handle.textContent = isLink
        ? t("Приложение · {host}", { host: task.host || task.username || "" })
        : t("@{username} · подписка на канал", { username: task.username });
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
        open.textContent = isLink ? t("Запустить") : t("Подписаться");
        open.addEventListener("click", (event) => {
          if (!tg) return;
          event.preventDefault();
          if (isLink) {
            if (task.url.includes("t.me/") && tg.openTelegramLink) {
              tg.openTelegramLink(task.url);
            } else if (tg.openLink) {
              tg.openLink(task.url);
            } else {
              window.open(task.url, "_blank", "noopener,noreferrer");
            }
            return;
          }
          if (tg.openTelegramLink) tg.openTelegramLink(task.url);
        });
        const claim = document.createElement("button");
        claim.className = "task-claim";
        claim.textContent =
          taskBusy === task.slug
            ? t("Проверяем…")
            : isLink
              ? t("Получить")
              : t("Проверить");
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
        t("+{amount} SenseiCoin · +{energy} энергии на цикл", {
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
    const boostLeft = Math.max(0, Number(upgrades.boost_seconds_left) || 0);
    const boostPurchased = Boolean(upgrades.boost_purchased);
    const boost = upgradeCard(
      "bolt",
      t("СКОРОСТЬ +50%"),
      boostLeft > 0
        ? t("АКТИВЕН · {time}", { time: clock(boostLeft * 1000) })
        : t("1 ЧАС"),
      t("Ускоряет добычу на 50% на один час. Одна покупка за цикл."),
      boostPurchased
        ? t("1 ⭐ · 1 РАЗ ЗА ЦИКЛ")
        : t("1 ⭐ · +1 ЧАС · 1 РАЗ ЗА ЦИКЛ"),
      upgradeBusy === "boost"
        ? t("СЧЁТ…")
        : boostPurchased
          ? t("КУПЛЕНО В ЦИКЛЕ")
          : t("{stars} ⭐ · УСКОРИТЬ", { stars: upgrades.boost_stars }),
      upgradeBusy === "boost" || boostPurchased,
    );
    boost.querySelector(".upgrade-head span").dataset.boostTimer = "1";
    const auto = upgradeCard(
      "clock",
      t("АВТОСБОР"),
      upgrades.auto_collect ? t("АКТИВЕН") : t("ВЫКЛ"),
      t(
        "Сам собирает награду и запускает новый цикл каждые 3 часа. Участие не нужно.",
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
      boost.querySelector(".upgrade-buy"),
      auto.querySelector(".upgrade-buy"),
    ];
    buttons[0].addEventListener("click", () => buyUpgrade("pickaxe"));
    buttons[1].addEventListener("click", () => buyUpgrade("energy"));
    buttons[2].addEventListener("click", () => buyUpgrade("boost"));
    buttons[3].addEventListener("click", () => buyUpgrade("auto"));
    list.append(pickaxe, energy, boost, auto);
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
          showToast(
            t(
              kind === "refill"
                ? "Энергия пополнена"
                : kind === "boost"
                  ? "Скорость +50% активирована на 1 час"
                  : "Оплата получена · включаем улучшение",
            ),
          );
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

  async function refillEnergy() {
    if (!initData() || upgradeBusy) return;
    if (
      !model ||
      model.phase !== "mining" ||
      Math.floor(Number(energyValue()) || 0) > 0
    ) {
      showToast(t("Пополнить можно только при нулевой энергии."), true);
      return;
    }
    await buyUpgrade("refill");
  }

  function burnAvailable() {
    if (!initData() || !model) return 0;
    return Math.max(0, Math.floor(Number(model.balance) || 0));
  }

  function updateBurnPreview() {
    const available = burnAvailable();
    const raw = Math.floor(Number($("burn-amount")?.value) || 0);
    const amount = Math.max(0, Math.min(available, raw));
    $("burn-available").textContent = `${coin(available)} Coin`;
    $("burn-preview").textContent = coin(amount);
    $("burn-left").textContent = coin(Math.max(0, available - amount));
    const confirm = $("burn-confirm");
    if (confirm) {
      confirm.disabled = burnBusy || amount <= 0;
      confirm.textContent = burnBusy ? t("СЖИГАЕМ…") : t("СЖЕЧЬ НАВСЕГДА");
    }
  }

  function paintBurn() {
    const sheet = $("burn-sheet");
    if (!sheet || sheet.hidden) return;
    $("burn-total").textContent = `${coin(bank?.burned)} Coin`;
    updateBurnPreview();
  }

  function newBurnRequest() {
    try {
      if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    } catch {}
    return `burn-${Date.now().toString(36)}-${Math.random()
      .toString(36)
      .slice(2, 12)}`;
  }

  function openBurn() {
    if (!initData()) {
      showToast(t("Открой майнер через /dojo."), true);
      return;
    }
    closeSheet();
    $("roadmap-sheet").hidden = true;
    burnRequest = newBurnRequest();
    $("burn-amount").value = "";
    $("burn-total").textContent = `${coin(bank?.burned)} Coin`;
    $("burn-sheet").hidden = false;
    updateBurnPreview();
    if (!bank) loadBank(true);
    setTimeout(() => $("burn-amount").focus(), 80);
  }

  function closeBurn() {
    const sheet = $("burn-sheet");
    if (sheet) sheet.hidden = true;
  }

  function setBurnPercent(percent) {
    const part = [25, 50, 100].includes(percent) ? percent : 25;
    $("burn-amount").value = String(
      Math.max(1, Math.floor((burnAvailable() * part) / 100)),
    );
    updateBurnPreview();
  }

  async function confirmBurn() {
    if (burnBusy) return;
    const available = burnAvailable();
    const amount = Math.floor(Number($("burn-amount").value) || 0);
    if (amount <= 0) {
      showToast(t("Укажи целое количество Coin больше нуля."), true);
      return;
    }
    if (amount > available) {
      showToast(t("Недостаточно Coin для сжигания."), true);
      return;
    }
    burnBusy = true;
    updateBurnPreview();
    try {
      const data = await api("burn", {
        amount,
        request_id: burnRequest,
      });
      const burned = Number(data.burn?.amount) || amount;
      burnRequest = "";
      if (model) model.balance = Number(data.balance ?? data.burn?.balance);
      closeBurn();
      showToast(
        t("Сожжено {amount} Coin. Эмиссия уменьшена навсегда.", {
          amount: coin(burned),
        }),
      );
      render();
      loadBank(true);
      refresh(true);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      burnBusy = false;
      updateBurnPreview();
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
    const remaining = Number(bank.emission_remaining) || 0;
    // The progress card's compact meta row omits the "Coin" suffix; the
    // labels already say what these values are and this keeps a 10B cap on
    // one line even on a 320px screen.
    $("bank-emitted").textContent = `${coin(emitted)} Coin`;
    $("bank-cap").textContent = `${coin(cap)} Coin`;
    $("bank-remaining").textContent = `${coin(remaining)} Coin`;
    $("bank-supply").textContent = `${coin(bank.total_supply)} Coin`;
    $("bank-balance").textContent = `${coin(bank.bank_balance)} Coin`;
    $("bank-circulation").textContent = `${coin(bank.circulation)} Coin`;
    $("bank-burned").textContent = `${coin(bank.burned)} Coin`;
    $("bank-confiscated").textContent = `${coin(bank.confiscated)} Coin`;
    $("bank-users").textContent = coin(bank.users);
    $("bank-mined-label").textContent = `${coin(emitted)} Coin`;
    $("bank-remaining-label").textContent = `${coin(remaining)} Coin`;
    $("bank-progress-percent").textContent =
      percent > 0 && percent < 0.1 ? "<0.1%" : `${percent.toFixed(1)}%`;
    const burnTotal = $("burn-total");
    if (burnTotal) burnTotal.textContent = `${coin(bank.burned)} Coin`;
    const bar = $("bank-progress");
    if (bar) {
      // A 0.01% emission is mathematically correct but looks like an empty,
      // broken bank bar. Keep a small visible ember for any mined amount.
      bar.style.width = percent > 0 ? `${Math.max(2, percent)}%` : "0%";
      bar.classList.toggle("is-filled", percent > 0);
    }
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

  function paintReferralLink() {
    const node = $("ref-link");
    if (!node) return;
    const link = referrals?.link || "";
    const loading = initData() && !referralAttempted;
    node.textContent =
      link ||
      (loading
        ? t("ЗАГРУЖАЕМ ССЫЛКУ…")
        : t("Ссылка недоступна. Открой майнер через /dojo."));
    node.classList.toggle("is-empty", !link);
    node.title = link;
    const share = $("ref-share");
    if (share) {
      share.setAttribute(
        "aria-label",
        link
          ? `${t("ПОДЕЛИТЬСЯ ССЫЛКОЙ")}: ${link}`
          : t("Ссылка недоступна. Открой майнер через /dojo."),
      );
    }
  }

  function renderReferrals(emptyText = t("ПОКА НЕТ УЧЕНИКОВ")) {
    paintReferralLink();
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
      referralAttempted = false;
      renderReferrals(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
      return;
    }
    if (referralBusy) {
      // A quick level switch must not be silently dropped by an in-flight load.
      referralReload = true;
      return;
    }
    if (referralsLoaded && !force && referrals?.level === referralLevel) return;
    referralAttempted = true;
    referralBusy = true;
    try {
      const data = await api("referrals", { level: referralLevel });
      // A level switched while this request was in flight; the queued reload
      // will render the level the player actually selected.
      if (data.level !== referralLevel) return;
      referrals = data;
      referralsLoaded = true;
      renderReferrals();
      paintReferralLink();
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

  function referralShareBody() {
    return (
      referrals?.share_body ||
      t("Заходи в додзё Сенсея — вместе майним SenseiCoin 🥷")
    );
  }

  function referralShareText() {
    const link = referrals?.link || "";
    return referrals?.share_text || `${referralShareBody()}\n\n${link}`.trim();
  }

  async function copyReferralLink() {
    const link = referrals?.link;
    if (!link) {
      showToast(t("Ссылка недоступна. Открой майнер через /dojo."), true);
      return;
    }
    const text = referralShareText();
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const field = document.createElement("textarea");
        field.value = text;
        field.setAttribute("readonly", "");
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.select();
        document.execCommand("copy");
        field.remove();
      }
      showToast(t("Приглашение с ссылкой скопировано"));
    } catch {
      showToast(text);
    }
  }

  async function shareReferralLink() {
    const link = referrals?.link;
    if (!link) {
      showToast(t("Ссылка недоступна. Открой майнер через /dojo."), true);
      return;
    }
    const text = referralShareBody();
    const url = `https://t.me/share/url?url=${encodeURIComponent(
      link,
    )}&text=${encodeURIComponent(text)}`;
    // A prepared inline message carries the text AND a «Майнинг» button into
    // any chat. Old clients without shareMessage fall back to the URL share.
    if (typeof tg?.shareMessage === "function") {
      try {
        const prepared = await api("share");
        if (prepared?.prepare_id) {
          tg.shareMessage(prepared.prepare_id, () => {});
          return;
        }
      } catch {}
    }
    try {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(url);
        return;
      }
      if (navigator.share) {
        await navigator.share({ title: "SenseiCoin", text, url: link });
        return;
      }
      await copyReferralLink();
    } catch (error) {
      if (error?.name !== "AbortError") showToast(url, true);
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
    $("roadmap-sheet").hidden = true;
    closeBurn();
  }

  function openSheet() {
    $("roadmap-sheet").hidden = true;
    closeBurn();
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

  $("roadmap").addEventListener("click", () => {
    closeSheet();
    closeBurn();
    $("roadmap-sheet").hidden = false;
  });

  $("burn").addEventListener("click", openBurn);
  $("burn-amount").addEventListener("input", updateBurnPreview);
  $("burn-confirm").addEventListener("click", confirmBurn);
  document.querySelectorAll("[data-burn-percent]").forEach((node) => {
    node.addEventListener("click", () =>
      setBurnPercent(Number(node.dataset.burnPercent)),
    );
  });

  document.querySelectorAll("[data-close='roadmap-sheet']").forEach((node) => {
    node.addEventListener("click", () => {
      $("roadmap-sheet").hidden = true;
    });
  });

  document.querySelectorAll("[data-close='burn-sheet']").forEach((node) => {
    node.addEventListener("click", closeBurn);
  });

  $("energy-card").addEventListener("click", () => {
    if ($("energy-card").classList.contains("is-empty")) refillEnergy();
  });

  $("energy-card").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (!$("energy-card").classList.contains("is-empty")) return;
    event.preventDefault();
    refillEnergy();
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
    if (event.key === "Escape") {
      closeSheet();
      closeBurn();
      $("roadmap-sheet").hidden = true;
    }
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
  seedMiningParticles();
  buildTimerFace();
  setInterval(paintChain, 1000);
  applyTranslations();
  seedBoot();
  render();
  if (initData()) {
    bootSetGoal(26, t("ЗАГРУЗКА…"));
    Promise.allSettled([
      refresh(),
      loadTasks(),
      loadUpgrades(),
      loadBank(),
    ]).then(() => completeBoot(t("ЗАГРУЗКА…")));
    // A stalled request must never trap the player on the splash screen.
    window.setTimeout(() => completeBoot(t("ЗАГРУЗКА…")), 9000);
  } else {
    renderTasks(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    renderUpgrades(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    renderReferrals(t("ОТКРОЙ ЧЕРЕЗ /DOJO"));
    if (bootEl) bootEl.classList.add("is-ready");
    completeBoot(t("ТОЛЬКО В TELEGRAM"));
  }
})();
