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
    "Открой /dojo заново": "Reopen /dojo",
    "Сессия Telegram завершена. Прогресс хранится на сервере.": "Your Telegram session ended. Progress is saved on the server.",
    "Ожидает выплаты": "Awaiting payout",
    "Последний автосбор": "Last auto-collect",
    "ЭФФ. ВКЛ": "FX ON", "ЭФФ. ВЫКЛ": "FX OFF",
    "БОНУС": "BONUS", "Открыть бонусы": "Open bonuses",
    "{full} ч на полной скорости": "{full} h at full speed",
    " · {slow} ч на 10%": " · {slow} h at 10%",
    "Энергия исчерпана · добыча идёт на 10% · {rate} Coin/ч": "Energy depleted · still mining at 10% · {rate} Coin/h",
    "СБОР В {time}": "COLLECT AT {time}",
    "ПРОВЕРИТЬ": "CHECK STATUS", "ПРОВЕРЯЕМ…": "CHECKING…",
    "ПРОВЕРКА СБОРА": "COLLECTION STATUS",
    "Проверим баланс и цикл без повторного сбора.": "Check your balance and cycle without collecting again.",
    "SenseiCoin · Майнер": "SenseiCoin · Miner",
    "Сенсей в тёмном кибер-додзё перед зелёным энсо":
      "Sensei in a dark cyber-dojo before a green enso",
    "Язык интерфейса": "Interface language",
    "Правила майнинга": "Mining rules",
    "Баланс SenseiCoin": "SenseiCoin balance",
    "ТВОИ ОЧКИ": "YOUR POINTS",
    "Энергия майнера": "Miner energy",
    "Эффекты: включены": "Effects: on",
    "Эффекты: как в системе": "Effects: system default",
    "Эффекты: выключены": "Effects: off",
    "+{amount} энергии": "+{amount} energy",
    ЭНЕРГИЯ: "ENERGY",
    "Энергия майнинга": "Mining energy",
    "ПРОГРЕСС ЦИКЛА": "CYCLE PROGRESS",
    ЗАДАНИЯ: "TASKS",
    ПОДПИСКИ: "SUBSCRIPTIONS",
    БОНУСЫ: "BONUSES",
    "Выполняй задания: подписки и приложения награждаются один раз, задания профиля — каждый день по UTC. Энергия заданий не увеличивает постоянный максимум.":
      "Complete tasks: subscriptions and apps pay once, profile tasks pay daily by UTC. Task energy does not increase the permanent maximum.",
    "ЗАГРУЖАЕМ ЗАДАНИЯ…": "LOADING TASKS…",
    "Профиль и подписку проверяет Telegram. Если профиль недоступен, открой личный чат с ботом и попробуй снова.":
      "Telegram verifies your profile and subscription. If your profile is unavailable, open a private chat with the bot and try again.",
    "Приложение · {host}": "App · {host}",
    "Sensei в имени": "Sensei in name",
    "Реферальная ссылка в BIO": "Referral link in BIO",
    "Добавь Sensei в имя или @username Telegram": "Add Sensei to your Telegram name or @username",
    "Добыча · всего принесено": "Mining · total earned",
    "Бонус за сбор добычи: I — 10%, II — 1%, III — 0,1%. Нажми сумму рядом с именем, чтобы забрать.": "Collected mining bonuses: I — 10%, II — 1%, III — 0.1%. Tap the amount beside a name to claim it.",
    "Размести свою реферальную ссылку в BIO Telegram": "Add your referral link to your Telegram BIO",
    "Каждый день · UTC": "Every day · UTC",
    "✓ Получено сегодня": "✓ Claimed today",
    "+{amount} SenseiCoin": "+{amount} SenseiCoin",
    Запустить: "Launch",
    Получить: "Claim",
    УЛУЧШЕНИЯ: "UPGRADES",
    ПРОКАЧКА: "UPGRADES",
    "Улучшения за Telegram Stars. Кирка повышает добычу, энергия держит полную мощность дольше, буст ускоряет фарм на 1 час, автосбор работает без тебя.":
      "Telegram Stars upgrades. The pickaxe boosts mining, energy keeps full power longer, a boost speeds up farming for 1 hour, and auto-collect works without you.",
    "ЗАГРУЖАЕМ УЛУЧШЕНИЯ…": "LOADING UPGRADES…",
    "Оплата Stars · улучшения не сгорают":
      "Stars payment · upgrades never expire",
    "Где находятся Coin": "Where the Coin is",
    "УЧТЕНО В ЛИМИТЕ": "COUNTED AGAINST CAP",
    "ЛИМИТА УЧТЕНО": "CAP USED",
    "Текущая эмиссия": "Current emission",
    "Движение Coin": "Coin movement",
    "Вехи эмиссии": "Emission milestones",
    "Расчёт по учтённым выпускам, сжиганиям и резерву лимита; история может быть неполной.": "Estimated from recorded issuance, burns and the limit reserve; history may be incomplete.",
    "Обнаружено расхождение": "Accounting discrepancy detected",
    "Превышен лимит": "Emission cap exceeded",
    "Подробнее": "Details",
    "Эмиссия и сумма балансов могут различаться, либо превышен лимит. Причина требует проверки; значения не исправляются автоматически.": "Emission and total balances may differ, or the cap may be exceeded. Investigation is needed; values are not corrected automatically.",
    "Эмиссия минус всего в экономике: {difference} Coin": "Emission minus total in economy: {difference} Coin",
    "Загружаем данные…": "Loading data…",
    "Данные недоступны": "Data unavailable",
    "Не удалось обновить данные. Попробуй ещё раз.": "Could not refresh data. Please try again.",
    "Снимок данных: {time}": "Snapshot: {time}",
    "Время снимка недоступно": "Snapshot time unavailable",
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
    Холдеров: "Holders",
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
    "<b>Улучшай кирку.</b> За Stars: +50 Coin/ч за уровень, +100 энергии или автосбор, который запускает циклы без тебя.":
      "<b>Upgrade your pickaxe.</b> For Stars: +50 Coin/h per level, +100 energy, or auto-collect that starts cycles without you.",
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
    "5 ⭐ · ПОПОЛНИТЬ": "5 ⭐ · REFILL",
    "Пополнить энергию за 5 ⭐": "Refill energy for 5 ⭐",
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
    "Навсегда +50 SenseiCoin в час за уровень. Действует со следующего цикла.":
      "Permanently adds 50 SenseiCoin per hour per level. Applies from the next cycle.",
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
    "Сожжено {amount} Coin. Текущая эмиссия уменьшена.":
      "Burned {amount} Coin. Current emission is reduced.",
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
    "ТЕКУЩАЯ ЭМИССИЯ": "CURRENT EMISSION",
    "ДО ЛИМИТА ЭМИССИИ": "UNTIL EMISSION CAP",
    "Есть расхождение в учёте или превышение лимита. Требуется проверка данных.": "Accounting discrepancy or cap exceeded. The data needs investigation.",
    "Автобан возвращает Coin в SenseiBank. Сжигание уменьшает текущую эмиссию, но освобождённый лимит не может использоваться снова.": "Autoban returns Coin to SenseiBank. Burning reduces current emission, but the freed capacity cannot be used again.",
    "Сожжённые Coin исчезают безвозвратно. Текущая эмиссия уменьшается, но освободившийся лимит не может использоваться снова. Это добровольный вклад, а не инвестиция и не обещание цены или листинга.": "Burned Coin are gone permanently. Current emission decreases, but the freed capacity cannot be used again. This is a voluntary contribution, not an investment or a promise of price or listing.",
    НАМАЙНЕНО: "MINED",
    "ОСТАЛОСЬ ДО КОНЦА МАЙНИНГА": "LEFT UNTIL MINING ENDS",
    Намайнено: "Mined",
    "Осталось до конца майнинга": "Left until mining ends",
    "Сожжено навсегда": "Burned forever",
    "Вернулось из автобана": "Returned from autoban",
    "Coin забаненных и автобаненных игроков возвращаются в SenseiBank. Сжигание уменьшает эмиссию навсегда и не пополняет банк.":
      "Coins from banned and autobanned players return to SenseiBank. Burning permanently reduces emission and never refills the bank.",
    "Предел выпуска: 10 000 000 000 Coin. Учёт опирается на доступные счётчики; история может быть неполной. Награды списываются из банка.":
      "Issuance limit: 10,000,000,000 Coin. The calculation uses available counters; history may be incomplete. Rewards are paid from the bank.",
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

  const motionQuery = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;
  let motionPreference = "full";
  try { motionPreference = localStorage.getItem("sensei_dojo_motion") || "full"; } catch {}
  if (!["full", "off", "auto"].includes(motionPreference)) motionPreference = "full";
  const motionReduced = () => motionPreference === "off" ||
    Boolean(motionPreference === "auto" && motionQuery?.matches);
  function syncMotionClass() {
    document.documentElement.classList.toggle("motion-reduced", motionReduced());
  }
  syncMotionClass();
  function paintMotionControl() {
    const button = $("motion-setting");
    if (!button) return;
    const label = motionPreference === "auto" ? "Эффекты: как в системе" :
      motionPreference === "off" ? "Эффекты: выключены" : "Эффекты: включены";
    const reduced = motionReduced();
    button.textContent = t(reduced ? "ЭФФ. ВЫКЛ" : "ЭФФ. ВКЛ");
    button.setAttribute("aria-label", t(label));
    button.setAttribute("title", t(label));
    button.setAttribute("aria-pressed", reduced ? "false" : "true");
  }
  function changeMotionPreference() {
    motionPreference = motionReduced() ? "full" : "off";
    try { localStorage.setItem("sensei_dojo_motion", motionPreference); } catch {}
    syncMotionClass();
    paintMotionControl();
    if (!motionReduced()) seedAmbient();
    window.dispatchEvent(new Event("sensei-motion-change"));
  }
  const MATRIX_GLYPHS =
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789";

  const rnd = (min, max) => min + Math.random() * (max - min);
  const matrixText = () =>
    Array.from(
      { length: Math.round(rnd(7, 13)) },
      () => MATRIX_GLYPHS[Math.floor(Math.random() * MATRIX_GLYPHS.length)],
    ).join("");

  // The trail is decorative; completed orbits are credited by the server.
  function setupMagicTrail() {
    const canvas = $("magic-trail");
    if (!canvas || !stageEl) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const trail = [];
    const sparks = [];
    const MAX_POINTS = 64;
    const MAX_SPARKS = 90;
    let pointer = null;
    let frame = 0;
    let previous = null;
    let width = 0;
    let height = 0;
    let ratio = 1;
    let appliedRatio = 0;
    let resizePending = false;
    let appLeft = 0, appTop = 0, orbX = 0, orbY = 0;
    let geometryDirty = true;
    let geometryFrame = 0;
    let dirtyRect = null;
    let circlePaintFrame = 0;
    const orb = $("orb");
    const sheets = Array.from(document.querySelectorAll(".sheet"));
    let lastAngle = null;
    let winding = 0;
    let queue = [];
    let sending = false;

    async function sendCircles() {
      if (sending) return;
      sending = true;
      while (queue.length) {
        const item = queue[0];
        try {
          const data = await api("circle", {cycle: item.cycle, request_id: item.request_id});
          queue.shift();
          if (model && data.started_at === model.started_at && data.server_now >= model.server_now) {
            const needsRender = pending || model.phase !== data.phase ||
              ["balance", "base_rate", "energy_max", "auto_collect", "pickaxe_level", "boost_until", "is_admin"]
                .some(key => model[key] !== data[key]);
            if (needsRender) apply(data);
            else {
              // Do not tear down the animated phase or repaint the entire app
              // for every orbit. Coalesce server updates into one frame.
              model = data;
              skew = Date.now() - data.server_now * 1000;
              if (!circlePaintFrame) circlePaintFrame = requestAnimationFrame(() => {
                circlePaintFrame = 0;
                $("profile-reward").textContent = `${coin(model?.reward)} Coin`;
                tick();
              });
            }
          }
          if (data.circle.added) {
            const amount = Number(data.circle.added);
            showToast(t("+{amount} энергии", {amount: amount < 0.001 ? "<0.001" : coinExact(amount)}));
          }
          else queue = queue.filter(next => next.cycle !== item.cycle);
        } catch (error) {
          // Retry with the same id: an interrupted response may already be credited.
          if (!model || model.phase !== "mining" || model.started_at !== item.cycle) { queue.shift(); continue; }
          showToast(error.message, true);
          item.retries = (item.retries || 0) + 1;
          if (item.retries <= 3) setTimeout(sendCircles, 1500);
          break;
        }
      }
      sending = false;
    }
    function recordOrbit(event) {
      if (!model || model.phase !== "mining" || !initData() ||
          circleEnergyValue() >= (model.circle_energy_limit ?? 100)) {
        lastAngle = null; winding = 0; return;
      }
      const x = event.clientX - orbX;
      const y = event.clientY - orbY;
      if (Math.hypot(x, y) < 8) { lastAngle = null; winding = 0; return; }
      const angle = Math.atan2(y, x);
      if (lastAngle !== null) {
        let delta = angle - lastAngle;
        if (delta > Math.PI) delta -= 2 * Math.PI;
        if (delta < -Math.PI) delta += 2 * Math.PI;
        winding += delta;
        if (Math.abs(winding) >= 2 * Math.PI - 0.15) {
          winding -= Math.sign(winding) * 2 * Math.PI;
          queue.push({cycle: model.started_at, request_id: crypto.randomUUID()});
          sendCircles();
        }
      }
      lastAngle = angle;
    }

    function updateGeometry() {
      const rect = app.getBoundingClientRect();
      const box = orb.getBoundingClientRect();
      appLeft = rect.left; appTop = rect.top;
      orbX = box.left + box.width / 2; orbY = box.top + box.height / 2;
      geometryDirty = false;
    }
    function resizeTrail() {
      geometryDirty = true;
      if (pointer !== null) { resizePending = true; return; }
      resizePending = false;
      const rect = app.getBoundingClientRect();
      width = rect.width; height = rect.height;
      geometryDirty = true;
      ratio = Math.min(window.devicePixelRatio || 1, 2);
      const pixelWidth = Math.max(1, Math.round(width * ratio));
      const pixelHeight = Math.max(1, Math.round(height * ratio));
      // Setting canvas dimensions clears it, even if the value is unchanged.
      // Mobile WebViews can emit many viewport-resize events during a swipe.
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth; canvas.height = pixelHeight;
        dirtyRect = null;
        appliedRatio = 0;
      }
      if (appliedRatio !== ratio) {
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        appliedRatio = ratio;
      }
    }
    function enabled() {
      return !document.hidden && activeTab === "mining" &&
        app.classList.contains("phase-mining") &&
        !sheets.some(sheet => !sheet.hidden);
    }
    function resetTrail() {
      pointer = null; previous = null; lastAngle = null; winding = 0; trail.length = 0; sparks.length = 0;
      if (frame) cancelAnimationFrame(frame);
      frame = 0; ctx.clearRect(0, 0, width, height); dirtyRect = null;
      if (resizePending) resizeTrail();
    }
    function addPoint(x, y, now) {
      const old = previous;
      if (old && Math.hypot(x - old.x, y - old.y) < 4) return;
      const steps = old ? Math.min(12, Math.ceil(Math.hypot(x - old.x, y - old.y) / 10)) : 1;
      for (let i = 1; i <= steps; i++) {
        const p = {x: old ? old.x + (x - old.x) * i / steps : x,
                   y: old ? old.y + (y - old.y) * i / steps : y, born: now};
        trail.push(p);
        if (trail.length > MAX_POINTS) trail.shift();
        if (i % 2 === 0 || !old) {
          sparks.push({x: p.x, y: p.y, born: now, dx: rnd(-18, 18),
                       dy: rnd(-28, -5), radius: rnd(1, 2.7), diamond: Math.random() < .25});
          if (sparks.length > MAX_SPARKS) sparks.shift();
        }
      }
      previous = {x, y};
      if (!frame) frame = requestAnimationFrame(drawTrail);
    }
    // The glow for each particle is rasterized once, not blurred on every frame.
    function makeSparkSprite(diamond) {
      const sprite = document.createElement("canvas");
      sprite.width = 32; sprite.height = 32;
      const paint = sprite.getContext("2d");
      const glow = paint.createRadialGradient(16, 16, 0, 16, 16, 16);
      glow.addColorStop(0, "rgba(182,255,209,.9)");
      glow.addColorStop(.25, "rgba(47,255,135,.55)");
      glow.addColorStop(1, "rgba(47,255,135,0)");
      paint.fillStyle = glow; paint.fillRect(0, 0, 32, 32);
      paint.fillStyle = "#b6ffd1"; paint.beginPath();
      if (diamond) {
        paint.moveTo(16, 9); paint.lineTo(20, 16);
        paint.lineTo(16, 23); paint.lineTo(12, 16); paint.closePath();
      } else paint.arc(16, 16, 3, 0, Math.PI * 2);
      paint.fill();
      return sprite;
    }
    const sparkSprites = [makeSparkSprite(false), makeSparkSprite(true)];
    function drawTrail(now) {
      frame = 0;
      if (!enabled()) { resetTrail(); return; }
      if (dirtyRect) ctx.clearRect(dirtyRect.x, dirtyRect.y, dirtyRect.w, dirtyRect.h);
      while (trail.length && now - trail[0].born > 650) trail.shift();
      while (sparks.length && now - sparks[0].born > 800) sparks.shift();
      // Clear only the region painted in this frame next time. The margin
      // covers both blurred strokes and the moving pre-rendered sparks.
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const p of trail) {
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
      }
      for (const s of sparks) {
        const life = Math.max(0, 1 - (now - s.born) / 800);
        const x = s.x + s.dx * (1 - life), y = s.y + s.dy * (1 - life);
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      }
      if (Number.isFinite(minX)) {
        const x = Math.max(0, Math.floor(minX - 36)), y = Math.max(0, Math.floor(minY - 36));
        dirtyRect = {x, y, w: Math.max(0, Math.min(width, Math.ceil(maxX + 36)) - x),
                     h: Math.max(0, Math.min(height, Math.ceil(maxY + 36)) - y)};
      } else dirtyRect = null;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.lineCap = "round"; ctx.lineJoin = "round";
      // Three translucent layers create a luminous trail without per-frame
      // shadow blurs, which are especially expensive in mobile WebViews.
      for (let bucket = 0; bucket < 6; bucket++) {
        const alpha = (bucket + .5) / 6;
        let hasSegments = false;
        ctx.beginPath();
        for (let i = 1; i < trail.length; i++) {
          const p = trail[i], before = trail[i - 1];
          const life = Math.max(0, Math.min(.9999, 1 - (now - p.born) / 650));
          if (Math.floor(life * 6) !== bucket) continue;
          ctx.moveTo(before.x, before.y); ctx.lineTo(p.x, p.y);
          hasSegments = true;
        }
        if (!hasSegments) continue;
        ctx.strokeStyle = `rgba(50, 255, 135, ${alpha * .11})`;
        ctx.lineWidth = 20 * alpha + 4; ctx.stroke();
        ctx.strokeStyle = `rgba(75, 255, 151, ${alpha * .30})`;
        ctx.lineWidth = 10 * alpha + 2; ctx.stroke();
        ctx.strokeStyle = `rgba(220, 255, 234, ${alpha * .88})`;
        ctx.lineWidth = 2.5 * alpha + .5; ctx.stroke();
      }
      ctx.shadowBlur = 0;
      for (const s of sparks) {
        const life = Math.max(0, 1 - (now - s.born) / 800);
        const x = s.x + s.dx * (1 - life), y = s.y + s.dy * (1 - life);
        const size = s.radius * 7;
        ctx.globalAlpha = life * .9;
        ctx.drawImage(sparkSprites[s.diamond ? 1 : 0], x - size / 2, y - size / 2, size, size);
      }
      if (trail.length) {
        const tip = trail[trail.length - 1];
        const life = Math.max(0, 1 - (now - tip.born) / 650);
        ctx.globalAlpha = life * .8;
        ctx.drawImage(sparkSprites[1], tip.x - 14, tip.y - 14, 28, 28);
      }
      ctx.restore();
      if (trail.length || sparks.length) frame = requestAnimationFrame(drawTrail);
    }
    function sample(event, now) {
      recordOrbit(event);
      addPoint(event.clientX - appLeft, event.clientY - appTop, now);
    }
    function begin(event) {
      const control = event.target.closest("button, a, input, textarea, select, [role=button]");
      if (!enabled() || pointer !== null || (event.pointerType === "mouse" && event.button !== 0) ||
          (control && !control.disabled)) return false;
      pointer = event.pointerId; previous = null; lastAngle = null; winding = 0; trail.length = 0;
      updateGeometry();
      try { stageEl.setPointerCapture(pointer); } catch {}
      sample(event, performance.now());
      return true;
    }
    function move(event) {
      if (event.pointerId !== pointer) return;
      if (!enabled()) { resetTrail(); return; }
      if (geometryDirty) updateGeometry();
      const now = performance.now();
      let samples;
      try { samples = event.getCoalescedEvents?.(); } catch { samples = null; }
      if (samples && samples.length) { for (const point of samples) sample(point, now); }
      else sample(event, now);
      if (!geometryFrame) geometryFrame = requestAnimationFrame(() => {
        geometryFrame = 0; geometryDirty = true;
      });
    }
    function stop(event, complete = false) {
      if (event.pointerId !== pointer) return;
      if (complete && enabled()) {
        if (geometryDirty) updateGeometry();
        sample(event, performance.now());
      }
      pointer = null; previous = null; lastAngle = null; winding = 0;
      if (resizePending) resizeTrail();
    }
    if (window.PointerEvent) {
      stageEl.addEventListener("pointerdown", begin);
      // Window listeners also work if pointer capture is missing or fails.
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", event => stop(event, true));
      window.addEventListener("pointercancel", stop);
      stageEl.addEventListener("lostpointercapture", stop);
    } else {
      // Older Telegram WebViews may not implement Pointer Events.
      const touchPoint = (event, id) => Array.from(event.changedTouches || [])
        .find(touch => id === null || touch.identifier === id);
      const asPointer = (event, touch) => ({pointerId: touch.identifier, pointerType: "touch",
        target: event.target, clientX: touch.clientX, clientY: touch.clientY});
      stageEl.addEventListener("touchstart", event => {
        const touch = touchPoint(event, null);
        if (touch && begin(asPointer(event, touch)) && event.cancelable) event.preventDefault();
      }, {passive: false});
      window.addEventListener("touchmove", event => {
        const touch = touchPoint(event, pointer);
        if (!touch || pointer === null) return;
        if (event.cancelable) event.preventDefault();
        move(asPointer(event, touch));
      }, {passive: false});
      window.addEventListener("touchend", event => {
        const touch = touchPoint(event, pointer);
        if (touch && pointer !== null) stop(asPointer(event, touch), true);
      });
      window.addEventListener("touchcancel", event => {
        const touch = touchPoint(event, pointer);
        if (touch && pointer !== null) stop(asPointer(event, touch));
      });
    }
    window.addEventListener("resize", resizeTrail);
    window.addEventListener("scroll", () => { geometryDirty = true; }, {passive: true});
    window.visualViewport?.addEventListener("scroll", () => { geometryDirty = true; }, {passive: true});
    window.visualViewport?.addEventListener("resize", resizeTrail, {passive: true});
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => { geometryDirty = true; });
      observer.observe(orb); observer.observe(stageEl);
    }
    document.addEventListener("visibilitychange", () => { if (document.hidden) resetTrail(); });
    resizeTrail();
  }

  let ambientSeeded = false;
  function seedAmbient() {
    const sakura = $("sakura");
    const matrix = $("matrix");
    if (!sakura || !matrix || motionReduced() || ambientSeeded) return;
    ambientSeeded = true;
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
  let verifyCollection = false;
  let stateRevision = 0;
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
  let bankBusy = false;
  let bankRefreshQueued = false;
  let bankLoadFailed = false;
  let referrals = null;
  let referralsLoaded = false;
  let referralLevel = 1;
  let referralPage = 0;
  let referralBusy = false;
  let referralReload = false;
  let referralAttempted = false;

  try {
    tg?.ready?.();
    tg?.expand?.();
    tg?.setHeaderColor?.("#020806");
    tg?.setBackgroundColor?.("#010503");
  } catch {}

  let sessionEnded = false;
  let needsEntry = true;
  let entryRequest = null;
  $("session-ended").addEventListener("cancel", event => event.preventDefault());
  // The server owns stake, participants, score and both round actions.
  const vsDialog = $("vs-dialog");
  // Sticker-man puppets: two chibi sprites, motion is CSS squash/stretch (no sprite swap)
  const SPRITES = {
    sensei1: "/miniapp/dojo/assets/ninja-sensei-1.png",
    sensei2: "/miniapp/dojo/assets/ninja-sensei-2.png",
  };
  // preload
  Object.values(SPRITES).forEach(u=>{ const im=new Image(); im.src=u; });
  for (const fighter of vsDialog.querySelectorAll(".vs-fighter")) {
    const tpl = fighter.classList.contains("left") ? "vs-puppet" : "vs-puppet-2";
    const src = document.getElementById(tpl);
    fighter.append((src || $("vs-puppet")).content.cloneNode(true));
    fighter.dataset.base = fighter.classList.contains("left") ? "sensei1" : "sensei2";
  }
  // neon slash trail canvas (green energy streak, matches sticker glow)
  const vsTrailCanvas = vsDialog.querySelector(".vs-trail-canvas");
  const vsTrailCtx = vsTrailCanvas ? vsTrailCanvas.getContext("2d", {alpha:true, desynchronized:true}) : null;
  if (vsTrailCtx) vsTrailCtx.globalCompositeOperation = "lighter"; // additive neon, no CSS blend
  // Match the backing store to the element so strokes are not drawn at 640x360 then upscaled.
  // Capped at 1.5x DPR: the trail is a soft glow, extra pixels buy nothing but fill cost.
  let trailDpr = 1;
  function sizeTrail() {
    if (!vsTrailCanvas || !vsTrailCtx) return;
    const rect = vsTrailCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    trailDpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const w = Math.round(rect.width * trailDpr), h = Math.round(rect.height * trailDpr);
    if (vsTrailCanvas.width !== w || vsTrailCanvas.height !== h) {
      vsTrailCanvas.width = w;
      vsTrailCanvas.height = h;
    }
  }
  sizeTrail();
  window.addEventListener("resize", () => { sizeTrail(); clearTrail(); }, {passive:true});
  let trailRaf = 0;
  let shockEl = null;
  function ensureShock(){
    if (shockEl) return shockEl;
    shockEl = document.createElement("i");
    shockEl.className = "vs-shockwave";
    shockEl.setAttribute("aria-hidden","true");
    vsDialog.querySelector(".vs-comic")?.appendChild(shockEl);
    return shockEl;
  }
  function paintBladeTrail(t, side, hit) {
    if (!vsTrailCtx || !vsTrailCanvas) return;
    const w = vsTrailCanvas.width / trailDpr, h = vsTrailCanvas.height / trailDpr;
    vsTrailCtx.setTransform(trailDpr, 0, 0, trailDpr, 0, 0);
    vsTrailCtx.clearRect(0,0,w,h);
    if (t <= 0 || t >= 1) return;
    // Envelope: fade in over the first 22%, fade out over the last 38%.
    // Without it the streak popped on and cut off, which is what made the
    // swing feel choppy rather than like a blade passing through air.
    const fadeIn = Math.min(1, t / 0.22);
    const fadeOut = t < 0.62 ? 1 : 1 - (t - 0.62) / 0.38;
    const fade = Math.max(0, Math.min(fadeIn, fadeOut));
    // bezier from attacker to center
    const fromX = side===0 ? w*0.26 : w*0.74;
    const toX = w*0.5;
    const fromY = h*0.48, toY = h*0.52;
    // ease: fast out then slow
    const e = 1 - Math.pow(1 - t, 3);
    const x = fromX + (toX - fromX) * e + Math.sin(e*Math.PI)* 10 * (side? -1:1);
    const y = fromY + (toY - fromY) * e + Math.sin(e*Math.PI*2)* -6;
    // Length grows into the strike, then trails off — never a hard edge.
    const grow = Math.min(1, t / 0.3);
    const len = 130 * grow * (1 - Math.abs(e-.5)*1.1);
    const ang = (side===0 ? -12 : 12) * Math.PI/180 + Math.sin(e*Math.PI)* .45;
    const dx = Math.cos(ang)*len*.5, dy = Math.sin(ang)*len*.5;
    vsTrailCtx.save();
    vsTrailCtx.lineCap = "round"; vsTrailCtx.lineJoin="round";
    // outer glow (additive via globalCompositeOperation set on the context)
    vsTrailCtx.strokeStyle = `rgba(122,255,170,${0.16 * fade})`;
    vsTrailCtx.lineWidth = 20;
    vsTrailCtx.beginPath(); vsTrailCtx.moveTo(x-dx, y-dy); vsTrailCtx.lineTo(x+dx, y+dy); vsTrailCtx.stroke();
    // mid bloom
    vsTrailCtx.strokeStyle = `rgba(170,255,205,${0.42 * fade})`;
    vsTrailCtx.lineWidth = 8;
    vsTrailCtx.beginPath(); vsTrailCtx.moveTo(x-dx, y-dy); vsTrailCtx.lineTo(x+dx, y+dy); vsTrailCtx.stroke();
    // core
    vsTrailCtx.strokeStyle = `rgba(240,255,248,${0.9 * fade})`;
    vsTrailCtx.lineWidth = 3.2;
    vsTrailCtx.beginPath(); vsTrailCtx.moveTo(x-dx, y-dy); vsTrailCtx.lineTo(x+dx, y+dy); vsTrailCtx.stroke();
    // particles sparkle along trail, fading with the envelope
    if (hit && t > .3 && t < .66) {
      vsTrailCtx.fillStyle = `rgba(255,235,120,${0.8 * fade})`;
      for(let i=0;i<3;i++){ const px = x + (Math.random()-.5)*16; const py = y + (Math.random()-.5)*10; vsTrailCtx.beginPath(); vsTrailCtx.arc(px,py, 1.6,0,Math.PI*2); vsTrailCtx.fill(); }
    }
    vsTrailCtx.restore();
    vsTrailCtx.globalCompositeOperation = "lighter";
  }
  function clearTrail(){ if(vsTrailCtx) vsTrailCtx.clearRect(0,0,vsTrailCanvas.width,vsTrailCanvas.height); cancelAnimationFrame(trailRaf); }
  let vsBattle, vsTimer, vsBusy = false;
  let seenExchange = "", vsPlaying = false, frameTimer;
  function stopVsComic() {
    clearTimeout(frameTimer);
    vsPlaying = false;
    delete vsDialog.dataset.striker;
    delete vsDialog.dataset.sequence;
    delete vsDialog.dataset.evade;
    delete vsDialog.dataset.outcome;
    delete vsDialog.dataset.direction;
    for (const actor of vsDialog.querySelectorAll(".vs-fighter")) { delete actor.dataset.pose; actor.classList.remove("is-dashing","is-charging"); }
    clearTrail();
    const stage = vsDialog.querySelector(".vs-stage");
    stage?.classList.remove("is-storm","is-impact","is-flash","is-shake","is-zoom","is-slash","is-hitstop");
    vsDialog.querySelector(".vs-comic")?.classList.remove("is-striking");
    $("vs-read").hidden = true;
  }
  function describeStrike(s, side) {
    const strike = s.exchange.strikes[side];
    const arrow = strike.attack === "hit_l" ? "←" : "→";
    const dodge = strike.dodge === "dodge_l" ? "←" : "→";
    // Only the server decides the outcome; directions explain it after reveal.
    const outcome = strike.hit ? "Попадание" : "Уклонился!";
    return {arrow, dodge, outcome, line: `${s.names[side]}: удар ${arrow} · ${s.names[1-side]}: уворот ${dodge} · ${outcome}`};
  }
  function playVsComic(s) {
    const exchange = s.exchange;
    seenExchange = `${s.id}:${exchange.round}`;
    vsPlaying = true;
    $("vs-controls").hidden = true;
    $("vs-rematch").hidden = true;
    $("vs-recap").hidden = true;
    const reduced = document.documentElement.classList.contains("motion-reduced") ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const banner = vsDialog.querySelector(".vs-cut-title");
    const caption = vsDialog.querySelector(".vs-cut-label");
    const hits = s.hits.map((n, i) => n - Number(exchange.strikes[i].hit));
    const score = () => {
      ["vs-left", "vs-right"].forEach((id, i) => {
        const node = $(id);
        node.textContent = `${s.side === i ? "Ты · " : ""}${s.names[i]} · ${hits[i]}`;
        node.dataset.health = String(Math.max(0, 2 - hits[1-i]));
      });
    };
    score();
    const stage = vsDialog.querySelector(".vs-stage");
    const sub = vsDialog.querySelector(".vs-cut-sub");
    vsDialog.dataset.sequence = "intro";
    if (stage) { stage.classList.add("is-storm"); stage.classList.remove("is-impact","is-flash","is-shake","is-zoom","is-slash","is-hitstop"); }
    caption.textContent = "ДОДЗЁ  /  ПОЕДИНОК";
    banner.textContent = `Раунд ${exchange.round}`;
    if (sub) sub.textContent = "";
    $("vs-status").textContent = "Ходы приняты · обмен ударами";
    // Intro holds 720ms like anime title card
    const frame = side => {
      $("vs-read").hidden = true;
      vsDialog.dataset.sequence = "strike";
      const strike = exchange.strikes[side];
      const actors = vsDialog.querySelectorAll(".vs-fighter");
      for (const actor of actors) { delete actor.dataset.pose; actor.classList.remove("is-dashing","is-charging"); }
      void actors[0].offsetWidth;
      // Alternate choreography, keep manga posing: sweep = grounded horizontal slash, kick = aerial leap
      const attackerPose = (exchange.round + side) % 2 ? "sweep" : "kick";
      const defenderPose = strike.hit ? "recoil" : "slip";
      actors[side].dataset.pose = attackerPose;
      actors[1-side].dataset.pose = defenderPose;
      actors[side].classList.add("is-dashing");
      // Attacker aura flare: class-driven, animates transform/opacity only.
      // (Animating filter here re-rasterised the whole sprite every frame.)
      for (const actor of actors) actor.classList.remove("is-charging");
      void 0;
      requestAnimationFrame(() => actors[side].classList.add("is-charging"));
      vsDialog.dataset.striker = side ? "right" : "left";
      vsDialog.dataset.evade = strike.dodge === "dodge_l" ? "left" : "right";
      vsDialog.dataset.outcome = strike.hit ? "hit" : "miss";
      vsDialog.dataset.direction = strike.attack === "hit_l" ? "left" : "right";
      // Choose impact typography like shonen
      const impact = vsDialog.querySelector(".vs-impact");
      if (impact) impact.textContent = strike.hit ? (side===0 ? "ДЗАН!" : "БАМ!") : (defenderPose==="slip" ? "УКЛОН!" : "МИМО!");
      // Storm = petals swirl, slash = afterimage + shockwave + volumetric trail
      if (stage) {
        stage.style.setProperty("--slash-dir", side ? "-1" : "1");
        stage.classList.add("is-storm","is-slash");
        stage.classList.remove("is-impact","is-flash","is-shake");
        if (strike.hit) stage.classList.add("is-impact");
        // shockwave center
        ensureShock(); shockEl.style.left = "50%"; shockEl.style.top = "52%";
      }
      // volumetric neon trail animates over 380ms via rAF
      if (!reduced) {
        let start=null;
        const dur = 380;
        const onTrail = (now)=> {
          if(!start) start=now;
          const t = Math.min(1, (now-start)/dur);
          paintBladeTrail(t, side, strike.hit);
          if (t < 1) trailRaf = requestAnimationFrame(onTrail); else { setTimeout(clearTrail, 80); }
        };
        cancelAnimationFrame(trailRaf); trailRaf = requestAnimationFrame(onTrail);
      }
      const comic = vsDialog.querySelector(".vs-comic");
      // Раньше здесь стоял void offsetWidth: принудительный reflow перед
      // каждым ударом. Он гарантировал перезапуск анимации, но на телефоне
      // это давало заметный рывок ровно в момент удара. Хореография теперь
      // на отдельном слое, и перезапуск не нужен.
      comic.classList.add("is-striking");
      comic.addEventListener("animationend", () => comic.classList.remove("is-striking"), { once: true });
      const read = describeStrike(s, side);
      $("vs-status").textContent = `Раунд ${exchange.round} · атакует ${s.names[side]}`;
      // Hit-stop timing: if hit, freeze 90ms at contact (anime impact frame)
      const hitStop = (!reduced && strike.hit) ? 70 : 0;
      const contactAt = reduced ? 0 : 240;
      frameTimer = setTimeout(() => {
        if (hitStop) {
          stage?.classList.add("is-hitstop");
          // burst petals outward from impact point
          vsDialog.querySelectorAll(".vs-petals i").forEach(p=>{
            p.style.setProperty("--burst-x", ((Math.random()-.5)*2).toFixed(2));
            p.style.setProperty("--burst-y", ((Math.random()-.5)*2).toFixed(2));
          });
          // health bar punch
          const defenderCard = side ? $("vs-left") : $("vs-right");
          defenderCard?.classList.add("is-hit"); setTimeout(()=> defenderCard?.classList.remove("is-hit"), 440);
          // flash + shake peak exactly at contact
          stage?.classList.add("is-flash","is-shake");
          if (navigator.vibrate) try { navigator.vibrate([22,18,28]); } catch {}
          frameTimer = setTimeout(() => {
            stage?.classList.remove("is-hitstop","is-flash","is-shake");
            if (!reduced && strike.hit) stage?.classList.add("is-zoom");
            showRead();
          }, hitStop);
        } else {
          if (!reduced && strike.hit) stage?.classList.add("is-shake");
          showRead();
        }
      }, contactAt);
      function showRead() {
        $("vs-read-hit").textContent = read.arrow;
        $("vs-read-dodge").textContent = read.dodge;
        $("vs-read-result").textContent = read.outcome;
        $("vs-read").hidden = false;
        $("vs-status").textContent = read.line;
        hits[side] += Number(strike.hit);
        score();
        // Let the pose play out fully before the readout appears.
        frameTimer = setTimeout(() => {
          stage?.classList.remove("is-zoom","is-shake","is-slash");
          if (!side) return frame(1);
          $("vs-read").hidden = true;
          delete vsDialog.dataset.striker;
          vsDialog.dataset.sequence = "outro";
          stage?.classList.remove("is-storm","is-impact");
          stage?.classList.add("is-zoom");
          caption.textContent = `ИТОГ ОБМЕНА  /  РАУНД ${exchange.round}`;
          banner.textContent = `${hits[0]} : ${hits[1]}`;
          if (sub) sub.textContent = hits[0]===hits[1] ? "НИЧЬЯ В РАУНДЕ" : (hits[side] > hits[1-side] ? "ПРЕИМУЩЕСТВО" : "");
          frameTimer = setTimeout(() => { stage?.classList.remove("is-zoom","is-storm"); stopVsComic(); drawVs(vsBattle); }, reduced ? 180 : 900);
        }, reduced ? 520 : 840);
      }
    };
    frameTimer = setTimeout(() => frame(0), reduced ? 0 : 720);
  }
  let draftKey = "", draft = {};
  function paintDraft() {
    const picked = Object.values(draft);
    for (const btn of vsDialog.querySelectorAll("[data-vs]")) {
      const on = picked.includes(btn.dataset.vs);
      btn.setAttribute("aria-pressed", String(on));
      btn.classList.toggle("is-selected", on);
    }
    const done = Number(Boolean(draft.attack)) + Number(Boolean(draft.dodge));
    const commit = $("vs-commit");
    commit.disabled = done < 2;
    commit.classList.toggle("is-ready", done === 2);
    const label = commit.querySelector(".vs-commit-label");
    if (label) label.textContent = done === 2 ? "В бой!" : done === 1 ? "Остался один ход" : "Выбери удар и уворот";
    commit.querySelectorAll(".vs-commit-dots i").forEach((dot, i) => dot.classList.toggle("is-on", i < done));
  }
  // Write helpers: a no-op write still costs a style pass in a WebView, and
  // reassigning dataset values can restart attribute-driven animations.
  function setText(id, value) {
    const node = $(id);
    if (node && node.textContent !== value) node.textContent = value;
  }
  function setHidden(id, hidden) {
    const node = $(id);
    if (!node) return;
    const next = Boolean(hidden);
    if (node.hidden !== next) node.hidden = next;
  }
  function setData(node, key, value) {
    if (!node) return;
    const next = String(value);
    if (node.dataset[key] !== next) node.dataset[key] = next;
  }
  function setClass(node, name, on) {
    if (node) node.classList.toggle(name, on);
  }
  function drawVs(s) {
    vsBattle = s;
    if (vsPlaying) return; // Polling updates vsBattle, never interrupts the cutscene.
    const key = `${s.id}:${s.round}`;
    if (draftKey !== key) { draftKey = key; draft = {...s.moves}; }
    const fighting = s.phase === "fight", ended = s.phase === "finished";
    setHidden("vs-accept", s.phase !== "invited");
    setHidden("vs-rematch", !ended);
    setHidden("vs-lobby", s.phase !== "lobby" && s.phase !== "room");
    setHidden("vs-controls", !fighting);
    $("vs-left").textContent = s.names ? `${s.side === 0 ? "Ты · " : ""}${s.names[0]} · ${s.hits[0]}` : "Сэнсэй";
    $("vs-right").textContent = s.names ? `${s.hits[1]} · ${s.names[1]}${s.side === 1 ? " · Ты" : ""}` : "Ниндзя";
    if (s.hits) {
      for (const [i, id] of ["vs-left", "vs-right"].entries()) {
        const fighter = $(id);
        fighter.dataset.health = String(Math.max(0, 2 - s.hits[1-i]));
        fighter.classList.toggle("is-me", i === s.side);
      }
    } else for (const id of ["vs-left", "vs-right"]) {
      delete $(id).dataset.health;
      $(id).classList.remove("is-me");
    }
    $("vs-ready").hidden = !fighting;
    setText("vs-ready", s.opponent_ready ? "● Соперник готов" : "○ Соперник выбирает ход");
    if (s.exchange && `${s.id}:${s.exchange.round}` !== seenExchange && vsDialog.open) {
      setHidden("vs-ready", true);
      playVsComic(s); return;
    }
    const recap = $("vs-recap");
    if (recap.hidden === Boolean(s.exchange)) recap.hidden = !s.exchange;
    const replayKey = s.exchange ? `${s.id}:${s.exchange.round}` : "";
    if (recap.dataset.key !== replayKey) {
      recap.dataset.key = replayKey;
      recap.open = false;
      if (s.exchange) {
        recap.querySelector("summary").textContent = `Разбор обмена · раунд ${s.exchange.round}`;
        recap.querySelector("ol").replaceChildren(...s.exchange.strikes.map((_, i) => {
          const li = document.createElement("li");
          li.textContent = describeStrike(s, i).line;
          return li;
        }));
      }
    }
    const resolved = fighting && s.exchange?.round === s.round;
    setHidden("vs-controls", !fighting || resolved || !s.round || Boolean(s.moves?.attack && s.moves?.dodge));
    const statusLine = resolved ? "Судья подводит итог…" : fighting && s.moves?.attack && s.moves?.dodge ? "Ход зафиксирован · ждём соперника" : fighting ? `Раунд ${s.round} · ${s.seconds} с · ${s.bet} Coin` :
      ended ? (s.draw ? "Бой завершён без победителя" : s.winner ? "Победа!" : "Поражение") :
      s.phase === "invited" ? `Приглашение · ${s.chat} · ставка каждого ${s.bet} Coin` :
      s.phase === "room" ? `${s.chat} · ждём соперника · ${s.seconds} с` :
      s.phase === "connecting" ? `Подключаем бойцов · ${s.seconds} с` :
      s.phase === "waiting" ? `Ждём соперника · ${s.chat} · ${s.seconds} с` : "Открытый вызов";
    if ($("vs-status").textContent !== statusLine) $("vs-status").textContent = statusLine;
    paintDraft();
  }
  async function vsRequest(action, args = {}) {
    if (vsBusy || !vsDialog.open) return;
    vsBusy = true;
    clearTimeout(vsTimer);
    try { drawVs(await api(action, args)); }
    catch (err) { $("vs-status").textContent = err.message; }
    finally {
      vsBusy = false;
      if (vsDialog.open && !sessionEnded && !document.hidden) {
        const waiting = vsBattle?.phase === "invited";
        // While the opponent is just picking (no clock pressure) 2.2s is enough;
        // in a live round poll a bit faster so the exchange starts without lag.
        const delay = waiting ? 2400 : vsPlaying ? 3200 : 1600;
        vsTimer = setTimeout(() => vsRequest(waiting ? "vs_invite" : "vs_state"), delay);
      }
    }
  }
  $("vs-open")?.addEventListener("click", () => { vsDialog.showModal(); vsRequest("vs_state"); loadRooms(); });
  $("vs-close")?.addEventListener("click", () => vsDialog.close());
  vsDialog?.addEventListener("close", () => { resumePrivateVs(false); clearTimeout(vsTimer); clearTimeout(roomsTimer); stopVsComic(); });
  $("vs-accept")?.addEventListener("click", () => vsRequest("vs_accept"));
  $("vs-rematch")?.addEventListener("click", () => vsRequest("vs_publish", {bet: vsBattle.bet, rematch: vsBattle.id}));

  // --- Комнаты: создал со ставкой — подключится любой -------------------
  let roomsTimer;
  function roomBet() {
    const bet = Number($("vs-bet")?.value);
    return Number.isSafeInteger(bet) && bet >= 300 ? bet : null;
  }
  async function loadRooms() {
    if (!vsDialog?.open || sessionEnded) return;
    try { drawRooms(await api("vs_rooms")); }
    catch { /* сеть моргнула — повторим на следующем тике */ }
    finally {
      clearTimeout(roomsTimer);
      if (vsDialog?.open && !document.hidden) roomsTimer = setTimeout(loadRooms, 4000);
    }
  }
  // Комната могла истечь, пока игрок смотрел на арену. Молчаливое
  // исчезновение читается как поломка: скажем, что произошло и что делать.
  let hadOwnRoom = false;
  function noteRoomExpired(snapshot) {
    const rooms = snapshot?.rooms || [];
    const mine = rooms.some(r => r.is_mine);
    if (hadOwnRoom && !mine) {
      const hint = $("vs-rooms-hint");
      if (hint) {
        hint.textContent = "Комната закрылась. Создай новую.";
        hint.dataset.sticky = "1";
      }
      showToast("Комната закрылась — 5 минут истекли");
    }
    if (mine) {
      const hint = $("vs-rooms-hint");
      if (hint) delete hint.dataset.sticky;
    }
    hadOwnRoom = mine || (vsBattle?.phase === "room");
  }
  function drawRooms(snapshot) {
    const list = $("vs-room-list");
    if (!list) return;
    noteRoomExpired(snapshot);
    const rooms = snapshot?.rooms || [];
    const hint = $("vs-rooms-hint");
    if (hint && !hint.dataset.sticky) hint.textContent = rooms.length
      ? `${rooms.length} ${rooms.length === 1 ? "комната ждёт" : "комнат ждут"} соперника`
      : "Создай комнату — подключится любой";
    // Перестраиваем только при реальном изменении: иначе кнопки
    // пересоздаются каждые 4 секунды и «мерцают» на слабых устройствах.
    const key = rooms.map(r => `${r.token}:${r.bet}:${r.seconds > 0 ? 1 : 0}`).join("|");
    if (list.dataset.key === key) return;
    list.dataset.key = key;
    if (!rooms.length) {
      list.replaceChildren();
      return;
    }
    list.replaceChildren(...rooms.map(room => {
      const row = document.createElement("div");
      row.className = "vs-room" + (room.is_mine ? " is-mine" : "");
      row.setAttribute("role", "listitem");
      const title = document.createElement("span");
      title.className = "vs-room-name";
      title.textContent = room.is_mine ? "Твоя комната" : room.owner_name;
      const stake = document.createElement("span");
      stake.className = "vs-room-bet";
      stake.textContent = `${room.bet} Coin`;
      const action = document.createElement("button");
      action.type = "button";
      action.className = "vs-room-action";
      if (room.is_mine) {
        action.textContent = "Закрыть";
        action.addEventListener("click", async () => {
          action.disabled = true;
          action.textContent = "Закрываем…";
          try {
            await api("vs_room_close", {token: room.token});
            showToast("Комната закрыта. Ставка не списана.");
            list.dataset.key = "";
            await loadRooms();
          } catch (err) {
            showToast(err.message, true);
            action.disabled = false;
            action.textContent = "Закрыть";
          }
        });
      } else {
        action.textContent = "Войти";
        action.addEventListener("click", async () => {
          action.disabled = true;
          action.textContent = "Входим…";
          try {
            await api("vs_room_join", {token: room.token});
            // Без явного подтверждения игрок не понимает, что вход
            // состоялся: экран просто меняется.
            showToast(`Ты в бою · ставка ${room.bet} Coin`);
            if (navigator.vibrate) try { navigator.vibrate(18); } catch {}
            vsRequest("vs_state");
          } catch (err) {
            showToast(err.message, true);
            action.disabled = false;
            action.textContent = "Войти";
          }
        });
      }
      row.append(title, stake, action);
      return row;
    }));
  }
  $("vs-room-create")?.addEventListener("click", async () => {
    const bet = roomBet();
    if (!bet) return showToast("Минимальная ставка — 300 Coin", true);
    const button = $("vs-room-create");
    button.disabled = true;
    try {
      const result = await api("vs_room_create", {bet});
      $("vs-room-list").dataset.key = "";
      drawRooms({rooms: result.rooms || []});
      showToast(`Комната на ${bet} Coin открыта. Ставка спишется при подключении.`);
    } catch (err) { showToast(err.message, true); }
    finally { button.disabled = false; }
  });
  $("vs-bet")?.addEventListener("input", () => {
    const label = $("vs-room-bet");
    if (label) label.textContent = String(roomBet() ?? "—");
  });
  // Navigation hint only; the actual offer and deadline always come from Mongo.
  function resumePrivateVs(write) {
    const key = `dojo:resume-private-vs:${currentUserId()}`;
    try {
      if (write === false) localStorage.removeItem(key);
      if (write === true) localStorage.setItem(key, String(Date.now() + 120000));
      return Number(localStorage.getItem(key)) > Date.now();
    } catch { return false; }
  }
  function vsBet() {
    const bet = Number($("vs-bet").value);
    if (Number.isSafeInteger(bet) && bet >= 300) return bet;
    showToast("Минимальная ставка — 300 Coin", true);
  }
  $("vs-send")?.addEventListener("click", () => {
    if (vsBet()) $("vs-destinations").hidden = !$("vs-destinations").hidden;
  });
  // Quick bet presets like reference card stakes
  vsDialog?.querySelectorAll(".vs-bet-presets [data-bet]").forEach(btn => {
    btn.addEventListener("click", () => {
      $("vs-bet").value = btn.dataset.bet;
      vsDialog.querySelectorAll(".vs-bet-presets [data-bet]").forEach(b => b.classList.toggle("is-active", b===btn));
    });
  });
  $("vs-bet")?.addEventListener("input", () => {
    const v = $("vs-bet").value;
    vsDialog.querySelectorAll(".vs-bet-presets [data-bet]").forEach(b => b.classList.toggle("is-active", b.dataset.bet===v));
  });
  // Публикация в группу идёт через бота на сервере, а не через
  // switchInlineQuery: тот штатно закрывает мини-апп, и игрок терял арену
  // прямо во время приглашения. Здесь окно остаётся открытым.
  $("vs-group")?.addEventListener("click", async () => {
    const bet = vsBet();
    if (!bet) return;
    const button = $("vs-group");
    button.disabled = true;
    try {
      const snapshot = await api("vs_chats");
      const chats = snapshot?.chats || [];
      if (!chats.length) {
        showToast("Нет доступных групп. Добавь Сенсея администратором в чат.", true);
        return;
      }
      const chatId = await pickChat(chats);
      if (!chatId) return;
      await api("vs_publish", {bet, chat: chatId});
      showToast("Вызов опубликован в чате. Арена остаётся открытой.");
      vsRequest("vs_state");
    } catch (err) {
      showToast(err.message, true);
    } finally {
      button.disabled = false;
    }
  });

  // Выбор группы встроенной панелью: системный picker Telegram закрывает
  // мини-апп так же, как и инлайн-режим.
  function pickChat(chats) {
    return new Promise(resolve => {
      const panel = $("vs-chat-panel");
      if (!panel) return resolve(chats[0].id);
      panel.replaceChildren(...chats.map(chat => {
        const item = document.createElement("button");
        item.type = "button";
        item.textContent = chat.title;
        item.addEventListener("click", () => { panel.hidden = true; resolve(chat.id); });
        return item;
      }));
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "vs-chat-cancel";
      cancel.textContent = "Отмена";
      cancel.addEventListener("click", () => { panel.hidden = true; resolve(null); });
      panel.append(cancel);
      panel.hidden = false;
    });
  }
  $("vs-address")?.addEventListener("click", () => {
    const bet = vsBet(), recipient = $("vs-handle").value.trim();
    if (bet && recipient) vsRequest("vs_publish", {bet, recipient});
  });
  $("vs-dm")?.addEventListener("click", async () => {
    const bet = vsBet();
    if (!bet) return;
    if (!tg?.isVersionAtLeast?.("8.0") || !tg.shareMessage) {
      $("vs-by-name").hidden = false;
      $("vs-handle").focus();
      return;
    }
    const button = $("vs-dm");
    button.disabled = true;
    try {
      const prepared = await api("vs_private_share", {bet});
      resumePrivateVs(true);
      let sent;
      try { sent = await new Promise(resolve => tg.shareMessage(prepared.prepare_id, resolve)); }
      catch (err) { await api("vs_share_result", {token:prepared.token, sent:false}); throw err; }
      await api("vs_share_result", {token:prepared.token, sent:sent === true});
      resumePrivateVs(sent === true);
      vsRequest("vs_state");
      if (!sent) showToast("Отправка отменена. Ставка не списана.");
    } catch (err) { showToast(err.message, true); }
    finally { button.disabled = false; }
  });
  vsDialog?.addEventListener("click", event => {
    const move = event.target.closest("[data-vs]")?.dataset.vs;
    if (move && vsBattle?.phase === "fight" && !vsPlaying) {
      draft[move.startsWith("hit_") ? "attack" : "dodge"] = move;
      paintDraft();
      if (navigator.vibrate) try { navigator.vibrate(12); } catch {}
    }
    if (event.target.closest("#vs-commit") && !vsPlaying) {
      if (vsBusy) return showToast("Обновление арены · нажми ещё раз");
      vsRequest("vs_commit", {id: vsBattle.id, round: vsBattle.round, ...draft});
    }
  });
  async function api(action, extra = {}) {
    if (sessionEnded) throw Error(t("Открой /dojo заново"));
    const response = await fetch(`/miniapp/dojo/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ initData: initData(), ...extra }),
    });
    if (response.status === 401) {
      if (!sessionEnded) {
        sessionEnded = true;
        $("session-ended").showModal();
      }
      throw Error(t("Открой /dojo заново"));
    }
    let data = {};
    try {
      data = await response.json();
    } catch {
      throw Error(t("Майнер не ответил. Попробуй ещё раз."));
    }
    if (!response.ok) {
      const error = Error(data.error || t("Майнер не ответил. Попробуй ещё раз."));
      error.code = data.code || "";
      error.slug = data.slug || "";
      throw error;
    }
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

  // The server computes circle eligibility from the precise, shared reservoir;
  // interpolate it between state responses instead of relying on a stale flag.
  function circleEnergyValue() {
    if (!model || model.phase !== "mining") return energyValue();
    const energy = Number(model.circle_energy);
    if (!Number.isFinite(energy)) return energyValue();
    const elapsed = Math.max(0, (serverNow() - model.server_now * 1000) / 3600000);
    const drain = Number(model.energy_per_hour) || 100;
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
      energy > 0 ? "Энергия {energy} / {max} · {rate} Coin/ч · после нуля 10%" :
        "Энергия исчерпана · добыча идёт на 10% · {rate} Coin/ч",
      { energy: Math.floor(energy), max: energyMax(), rate: coinExact(rate) },
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
    const rounded = Math.max(0, model?.circle_available ? Math.ceil(value) : Math.floor(value));
    $("energy").textContent = `${rounded} / ${max}`;
    // Keep the displayed number readable, but use the unrounded reservoir for
    // a continuously draining bar. Task energy above the cap stays full until
    // it falls below the cap; neither the number nor the server state is changed.
    const fill = Math.max(0, Math.min(1, (Number(value) || 0) / max));
    $("energy-bar").style.transform = `scaleX(${fill})`;
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
        empty ? t("Пополнить энергию за 5 ⭐") : t("Энергия майнера"),
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

  function paintTimerFace(value) {
    const digits = $("timer-digits");
    if (digits) digits.textContent = value;
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
    paintMotionControl();
    const adminOpen = $("admin-open");
    if (adminOpen) {
      adminOpen.hidden = !model?.is_admin;
      if (!model?.is_admin) $("admin-panel").hidden = true;
    }
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
    $("balance").classList.toggle("balance-long", balance.length >= 10);
    $("balance").classList.toggle("balance-extra-long", balance.length >= 15);
    $("profile-balance").textContent = initData() ? `${balance} Coin` : "—";
    $("profile-reward").textContent = `${coin(model?.reward)} Coin`;
    $("profile-rate").textContent =
      `${coin(model?.base_rate)} ${t("Coin / ч")}`;
    $("profile-energy").textContent = coin(model?.energy_max);
    $("profile-auto").textContent = model?.auto_collect ? (model.auto_waiting ? t("Ожидает выплаты") : t("ВКЛ")) : t("ВЫКЛ");
    $("auto-history").hidden = !model?.auto_collect;
    $("auto-last").textContent = model?.last_auto_collect_at ? new Date(model.last_auto_collect_at * 1000).toLocaleString(locale()) : "—";
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

    if (verifyCollection) {
      paintAction("coin", t(pending ? "ПРОВЕРЯЕМ…" : "ПРОВЕРИТЬ"), "SENSEIBANK", false, Boolean(pending));
      status.textContent = t("ПРОВЕРКА СБОРА");
      hint.textContent = t("Проверим баланс и цикл без повторного сбора.");
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
        t("СБОР В {time}", {time: new Date(model.finish_at * 1000).toLocaleTimeString(locale(), {hour: "2-digit", minute: "2-digit", hour12: false})}),
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
    const duration = (model.cycle_seconds || 10800) / 3600;
    const full = Math.min(duration, energyValue() / (model.energy_per_hour || 100));
    hint.textContent = t("{full} ч на полной скорости", { full: coinExact(full) }) +
      (full < duration ? t(" · {slow} ч на 10%", { slow: coinExact(duration - full) }) : "");
  }

  function tick() {
    if (!model || sessionEnded) return;
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
    paintBankStatus();
    paintReferralLink();
  }

  async function refresh(silent = false) {
    if (!initData() || pending || sessionEnded) return;
    const revision = ++stateRevision;
    try {
      const state = await (needsEntry
        ? (entryRequest ??= api("entry").finally(() => { entryRequest = null; }))
        : api("state"));
      needsEntry = false;
      if (revision !== stateRevision) return;
      verifyCollection = false;
      apply(state);
    } catch (error) {
      if (!silent) showToast(error.message, true);
    }
  }

  async function start() {
    if (pending || !model || model.phase !== "ready" || !initData()) return;
    ++stateRevision;
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
    ++stateRevision;
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
      verifyCollection = true;
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
      const invite = task.kind === "invite_friends";
      const isLink = task.kind === "link";
      const isDailyProfile = task.kind === "daily_profile";
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
        invite ? (lang === "en" ? `Invite friends: ${task.goal}` : `Пригласи ${task.goal} ${task.goal === 1 ? "друга" : "друзей"}`) : t(task.title || (isLink ? task.host : `@${task.username}`));
      const handle = document.createElement("span");
      handle.textContent = invite ? `${lang === "en" ? "Direct invites" : "По твоей ссылке"}: ${task.progress} / ${task.goal}` : isDailyProfile ? t(task.description) : isLink
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
      chips.appendChild(coinChip);
      if (task.energy_bonus > 0) chips.appendChild(energyChip);
      if (isDailyProfile) {
        const daily = document.createElement("span"); daily.className = "task-chip";
        daily.textContent = t("Каждый день · UTC"); chips.appendChild(daily);
      }
      if (task.reward_gram_hundredths > 0) {
        const gram = document.createElement("span"); gram.className = "task-chip";
        gram.textContent = `${(task.reward_gram_hundredths / 100).toFixed(2)} виртуальных GRAM`;
        chips.appendChild(gram);
      }
      if (task.reward_chests > 0) {
        const chests = document.createElement("span"); chests.className = "task-chip";
        chests.textContent = `+${task.reward_chests} сундуков`; chips.appendChild(chests);
      }

      card.append(top, chips);

      if (task.claimed) {
        const done = document.createElement("div");
        done.className = "task-claimed";
        done.textContent = isDailyProfile ? t("✓ Получено сегодня") : t("✓ Награда получена");
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
        if (invite) {
          const share = document.createElement("button");
          share.className = "task-link";
          share.textContent = lang === "en" ? "Invite" : "Пригласить";
          share.onclick = async () => { if (!referrals?.link) await loadReferrals(true); await shareReferralLink(); };
          actions.appendChild(share);
        } else if (!isDailyProfile) actions.appendChild(open);
        actions.appendChild(claim);
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
        item.slug === slug ? (task.kind === "invite_friends" ? updated : { ...item, ...updated, claimed: true }) : item,
      );
      const extras = [];
      if (data.reward_gram_hundredths) extras.push(`+${(data.reward_gram_hundredths / 100).toFixed(2)} виртуальных GRAM`);
      if (data.reward_chests) extras.push(`+${data.reward_chests} сундуков`);
      const rewardText = data.energy_bonus > 0 ? t("+{amount} SenseiCoin · +{energy} энергии на цикл", {
        amount: coin(data.reward_coins), energy: data.energy_bonus,
      }) : t("+{amount} SenseiCoin", {amount: coin(data.reward_coins)});
      showToast([rewardText, ...extras].join(" · "));
    } catch (error) {
      showToast(error.message, true);
    } finally {
      taskBusy = null;
      renderTasks();
    }
  }

  // The server authorizes every admin request; the hidden control is only UI.
  let adminTasks = [];
  let adminEditing = "";
  let adminCreateKey = "";
  let adminBusy = false;
  function adminMessage(text, error = false, actionLabel = "", onAction = null) {
    const box = $("admin-message");
    box.textContent = text;
    box.classList.toggle("error", error);
    if (!actionLabel) return;
    // Кнопка живёт внутри сообщения: после перерисовки списка она исчезает,
    // поэтому обработчик заново привязывается при каждом вызове.
    const button = document.createElement("button");
    button.type = "button";
    button.className = "admin-message-action";
    button.textContent = actionLabel;
    button.addEventListener("click", onAction);
    box.appendChild(document.createTextNode(" "));
    box.appendChild(button);
  }
  function renderAdminTasks() {
    const list = $("admin-task-list");
    list.replaceChildren();
    if (!adminTasks.length) { list.textContent = "Заданий пока нет."; return; }
    for (const task of adminTasks) {
      const row = document.createElement("div"); row.className = "admin-task-row";
      const desc = document.createElement("div");
      const title = document.createElement("b"); title.textContent = task.title;
      const detail = document.createElement("small");
      detail.textContent = `${task.active ? "● ВКЛ" : "○ ВЫКЛ"} · ${task.kind === "channel" ? "Канал" : "Приложение"} · ${task.reward_coins} Coin · ${task.energy_bonus} энергии · ${(task.reward_gram_hundredths / 100).toFixed(2)} GRAM · ${task.reward_chests} сундуков`;
      desc.append(title, detail);
      const edit = document.createElement("button"); edit.type = "button"; edit.textContent = "Изменить";
      edit.addEventListener("click", () => editAdminTask(task));
      const toggle = document.createElement("button"); toggle.type = "button";
      toggle.textContent = task.active ? "Выкл" : "Вкл";
      toggle.addEventListener("click", async () => {
        if (adminBusy) return;
        adminBusy = true; toggle.disabled = true;
        try {
          await api("admin_toggle", {slug: task.slug, active: !task.active});
          await loadAdminTasks(); tasksLoaded = false; adminMessage("Статус задания обновлён.");
        } catch (error) { adminMessage(error.message, true); }
        finally { adminBusy = false; toggle.disabled = false; }
      });
      row.append(desc, edit, toggle); list.appendChild(row);
    }
  }
  async function loadAdminTasks() {
    const data = await api("admin_tasks");
    adminTasks = Array.isArray(data.tasks) ? data.tasks : [];
    renderAdminTasks();
  }
  function adminKindLabel() {
    const channel = $("admin-kind").value === "channel";
    $("admin-target-label").firstChild.textContent = channel ? "@username канала" : "HTTPS-ссылка приложения";
    $("admin-target").placeholder = channel ? "@mychannel" : "https://t.me/app?startapp=ref";
    adminTargetHint();
  }
  // Проверяем ввод до отправки: сервер всё равно проверит канал через
  // Telegram, но глупые опечатки лучше ловить сразу, а не по отказу 409.
  function adminTargetHint() {
    const hint = $("admin-target-hint");
    const value = $("admin-target").value.trim();
    const channel = $("admin-kind").value === "channel";
    if (!value) { hint.textContent = channel
      ? "Вставь ссылку на канал или @username — приведём к нужному виду сами."
      : "Ссылка должна начинаться с https://"; hint.classList.remove("error"); return; }
    if (channel) {
      const clean = value.replace(/^https?:\/\//i, "").replace(/^t\.me\//i, "").replace(/^@/, "").replace(/\/+$/, "");
      const ok = /^[A-Za-z][A-Za-z0-9_]{4,31}$/.test(clean);
      hint.textContent = ok
        ? `Задание на @${clean}. Бот должен быть админом канала.`
        : "Не похоже на username: 5–32 символа, латиница, цифры и _, начинается с буквы.";
      hint.classList.toggle("error", !ok);
      return;
    }
    const ok = /^https:\/\/\S+$/i.test(value);
    hint.textContent = ok ? "Ссылка корректна." : "Нужна полная HTTPS-ссылка, например https://t.me/app?startapp=ref";
    hint.classList.toggle("error", !ok);
  }
  $("admin-target").addEventListener("input", adminTargetHint);
  function editAdminTask(task = null) {
    adminEditing = task?.slug || "";
    adminCreateKey = task ? "" : crypto.randomUUID();
    $("admin-form-title").textContent = task ? "Редактировать задание" : "Новое задание";
    $("admin-kind").value = task?.kind || "channel";
    $("admin-title").value = task?.title || "";
    $("admin-target").value = task ? (task.kind === "channel" ? `@${task.username}` : task.url) : "";
    $("admin-coins").value = task?.reward_coins ?? 0;
    $("admin-energy").value = task?.energy_bonus ?? 0;
    $("admin-gram").value = ((task?.reward_gram_hundredths || 0) / 100).toFixed(2);
    $("admin-chests").value = task?.reward_chests ?? 0;
    $("admin-task-form").hidden = false;
    adminKindLabel(); adminMessage("");
    $("admin-title").focus();
  }
  $("admin-open").addEventListener("click", async () => {
    if (!model?.is_admin) return;
    $("admin-panel").hidden = false;
    adminMessage("Загружаем задания…");
    try { await loadAdminTasks(); adminMessage(""); }
    catch (error) { adminMessage(error.message, true); }
  });
  $("admin-close").addEventListener("click", () => { $("admin-panel").hidden = true; $("admin-open").focus(); });
  $("admin-new").addEventListener("click", () => editAdminTask());
  $("admin-cancel").addEventListener("click", () => { $("admin-task-form").hidden = true; });
  $("admin-kind").addEventListener("change", adminKindLabel);
  $("admin-task-form").addEventListener("submit", async event => {
    event.preventDefault(); if (adminBusy) return;
    const gramText = $("admin-gram").value.trim().replace(",", ".");
    if (!/^\d{1,4}(?:\.\d{1,2})?$/.test(gramText)) { adminMessage("GRAM: укажи число с не более чем двумя знаками после запятой.", true); return; }
    const [whole, fraction = ""] = gramText.split(".");
    const gram = Number(whole) * 100 + Number((fraction + "00").slice(0, 2));
    const task = {slug: adminEditing, create_key: adminCreateKey, kind: $("admin-kind").value, title: $("admin-title").value,
      target: $("admin-target").value, reward_coins: Number($("admin-coins").value),
      energy_bonus: Number($("admin-energy").value), reward_gram_hundredths: gram,
      reward_chests: Number($("admin-chests").value)};
    adminBusy = true; $("admin-save").disabled = true;
    try {
      await api("admin_save", {task}); $("admin-task-form").hidden = true;
      await loadAdminTasks(); tasksLoaded = false; adminMessage("Задание сохранено.");
    } catch (error) {
      if (error.code === "task_exists" && error.slug) {
        // Не тупик: сразу предлагаем открыть существующее задание.
        adminMessage(error.message, true, "Открыть его", () => {
          const twin = adminTasks.find(item => item.slug === error.slug);
          if (twin) { editAdminTask(twin); adminMessage(""); }
          else adminMessage("Не нашёл это задание в списке — обнови панель.", true);
        });
      } else adminMessage(error.message, true);
    }
    finally { adminBusy = false; $("admin-save").disabled = false; }
  });
  let grantConfirmation = "";
  function resetGrantConfirmation() {
    grantConfirmation = "";
    $("admin-grant").textContent = "Начислить сундуки";
  }
  $("admin-username").addEventListener("input", resetGrantConfirmation);
  $("admin-count").addEventListener("input", resetGrantConfirmation);
  $("admin-grant-form").addEventListener("submit", async event => {
    event.preventDefault(); if (adminBusy) return;
    const username = $("admin-username").value.trim();
    const amount = Number($("admin-count").value);
    const confirmation = `${username}:${amount}`;
    if (grantConfirmation !== confirmation) {
      grantConfirmation = confirmation;
      $("admin-grant").textContent = "Подтвердить выдачу";
      adminMessage(`Проверь: ${amount} сундуков игроку ${username}. Нажми ещё раз для подтверждения.`);
      return;
    }
    const key = "dojo_admin_grant";
    let request;
    try { request = JSON.parse(sessionStorage.getItem(key) || "null"); } catch { request = null; }
    if (!request || request.username !== username || request.amount !== amount) {
      request = {username, amount, request_id: crypto.randomUUID()};
      try { sessionStorage.setItem(key, JSON.stringify(request)); }
      catch { adminMessage("Не удалось сохранить идентификатор выдачи. Проверь настройки хранения браузера.", true); return; }
    }
    adminBusy = true; $("admin-grant").disabled = true;
    try {
      const result = await api("admin_grant", request);
      sessionStorage.removeItem(key);
      resetGrantConfirmation();
      adminMessage(`Выдано ${result.amount} сундуков игроку @${result.username}.`);
    } catch (error) { adminMessage(`${error.message} При повторе сохранится тот же идентификатор выдачи.`, true); }
    finally { adminBusy = false; $("admin-grant").disabled = false; }
  });

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
      t("Навсегда +50 SenseiCoin в час за уровень. Действует со следующего цикла."),
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
        t("Сожжено {amount} Coin. Текущая эмиссия уменьшена.", {
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

  // Do not display a missing, invalid or non-finite value as a real zero.
  function bankNumber(value) {
    if ((typeof value !== "number" && typeof value !== "string") ||
        (typeof value === "string" && !value.trim())) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function bankCoin(value) {
    const parsed = bankNumber(value);
    return parsed === null ? "—" : `${coinExact(parsed)} Coin`;
  }

  function renderBank() {
    if (!bank) return;
    const emitted = bankNumber(bank.total_emitted);
    const supply = bankNumber(bank.total_supply);
    const cap = bankNumber(bank.emission_cap);
    const lifetime = bankNumber(bank.lifetime_issued_estimate);
    const percent = lifetime !== null && cap !== null && cap > 0
      ? Math.max(0, Math.min(100, lifetime / cap * 100)) : null;
    $("bank-cap").textContent = bankCoin(bank.emission_cap);
    $("bank-remaining").textContent = bankCoin(bank.emission_remaining);
    $("bank-supply").textContent = bankCoin(bank.total_supply);
    $("bank-balance").textContent = bankCoin(bank.bank_balance);
    $("bank-circulation").textContent = bankCoin(bank.circulation);
    $("bank-burned").textContent = bankCoin(bank.burned);
    $("bank-confiscated").textContent = bankCoin(bank.confiscated);
    const holders = bankNumber(bank.holders);
    $("bank-holders").textContent = holders === null ? "—" : coin(holders);
    const difference = emitted !== null && supply !== null ? emitted - supply : null;
    const warning = $("bank-warning");
    const hasDifference = difference !== null && Math.abs(difference) >= 0.009;
    warning.hidden = !bank.supply_over_cap && !(cap !== null && lifetime !== null && cap > 0 && lifetime > cap) && !hasDifference;
    $("bank-warning-title").textContent = t(hasDifference ? "Обнаружено расхождение" : "Превышен лимит");
    $("bank-warning-delta").textContent = difference === null ? "" :
      t("Эмиссия минус всего в экономике: {difference} Coin", { difference: coinExact(difference) });
    $("bank-mined-label").textContent = bankCoin(bank.lifetime_issued_estimate);
    $("bank-current-emission").textContent = bankCoin(bank.total_emitted);
    $("bank-progress-percent").textContent = percent === null ? "—" :
      percent > 0 && percent < 0.1 ? "<0.1%" : `${percent.toFixed(1)}%`;
    document.querySelectorAll("[data-milestone]").forEach((node) => {
      node.classList.toggle("is-reached", percent !== null && percent >= Number(node.dataset.milestone));
    });
    paintBankStatus();
    const burnTotal = $("burn-total");
    if (burnTotal) {
      const burned = bankNumber(bank.burned);
      burnTotal.textContent = burned === null ? "—" : `${coin(burned)} Coin`;
    }
    const bar = $("bank-progress");
    if (bar) {
      bar.style.width = `${percent ?? 0}%`;
      bar.classList.toggle("is-filled", percent !== null && percent > 0);
    }
    const track = $("bank-progress-track");
    if (track) {
      if (percent === null) track.removeAttribute("aria-valuenow");
      else track.setAttribute("aria-valuenow", percent.toFixed(1));
      track.setAttribute("aria-valuetext", percent === null ? t("Данные недоступны") :
        t("{emitted} из {cap} Coin", { emitted: coinExact(lifetime), cap: coinExact(cap) }));
    }
  }

  function paintBankStatus() {
    const status = $("bank-refresh-status");
    const button = $("bank-refresh");
    button.disabled = bankBusy;
    button.setAttribute("aria-busy", String(bankBusy));
    if (bankBusy) status.textContent = t("Загружаем данные…");
    else if (bankLoadFailed) status.textContent = t("Не удалось обновить данные. Попробуй ещё раз.");
    else if (bank) {
      const stamp = bankNumber(bank.snapshot_at);
      const date = stamp !== null && stamp > 0 ? new Date(stamp * 1000) : null;
      status.textContent = date && Number.isFinite(date.getTime())
        ? t("Снимок данных: {time}", { time: date.toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" }) })
        : t("Время снимка недоступно");
    } else status.textContent = "";
  }

  async function loadBank(force = false) {
    if (!initData() || (bank && !force)) return;
    if (bankBusy) {
      // A balance-moving action may complete while an older snapshot is in flight.
      if (force) bankRefreshQueued = true;
      return;
    }
    bankBusy = true;
    bankLoadFailed = false;
    paintBankStatus();
    try {
      bank = await api("bank");
      renderBank();
    } catch (error) {
      bankLoadFailed = true;
      showToast(error.message, true);
    } finally {
      bankBusy = false;
      if (bankRefreshQueued) {
        bankRefreshQueued = false;
        void loadBank(true);
      } else {
        paintBankStatus();
      }
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
      const reward = document.createElement("button");
      reward.type = "button";
      reward.className = "ref-level ref-claim";
      reward.disabled = !(member.pending > 0);
      reward.textContent = `${t("Забрать")} ${coinExact(member.pending || 0)} Coin`;
      reward.onclick = async () => {
        reward.disabled = true;
        try {
          const result = await api("ref_claim", {token: member.token});
          showToast(`+${coinExact(result.claimed)} Coin`);
          await refresh(true);
        } catch (error) { showToast(error.message, true); }
        finally { await loadReferrals(true); }
      };
      const total = document.createElement("small");
      total.textContent = `${t("Добыча · всего принесено")}: ${coinExact(member.lifetime || 0)} Coin`;
      name.append(document.createElement("br"), total);
      row.append(status, name, reward);
      list.appendChild(row);
    });
    if (referralPage || referrals.has_next) {
      const nav = document.createElement("div");
      nav.className = "ref-levels";
      for (const [step, label, enabled] of [[-1, "←", referralPage > 0], [1, "→", referrals.has_next]]) {
        const button = document.createElement("button");
        button.className = "ref-level";
        button.textContent = `${label} ${referralPage + step + 1}`;
        button.hidden = !enabled;
        button.onclick = () => { referralPage += step; members.replaceChildren(); loadReferrals(true); };
        nav.append(button);
      }
      list.append(nav);
    }
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
      const data = await api("referrals", { level: referralLevel, page: referralPage });
      // A level switched while this request was in flight; the queued reload
      // will render the level the player actually selected.
      if (data.level !== referralLevel || (data.page || 0) !== referralPage) return;
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
    if (name === "tasks") loadTasks(true);
    if (name === "upgrades") loadUpgrades();
    if (name === "bank") loadBank(true);
    if (name === "referrals") loadReferrals(true);
    // Chat games/mining change users.coins outside this WebView; re-read the
    // authoritative server balance whenever the player returns to a view.
    if (name === "mining" || name === "profile") refresh(true);
    closeSheet();
    $("roadmap-sheet").hidden = true;
    closeBonus();
    closeBurn();
  }

  function closeBonus(restoreFocus = false) {
    const sheet = $("bonus-sheet");
    if (sheet.hidden) return;
    sheet.hidden = true;
    $("bonus-open").setAttribute("aria-expanded", "false");
    if (restoreFocus) $("bonus-open").focus();
  }
  $("bonus-open").addEventListener("click", () => {
    closeSheet(); closeBurn();
    $("bonus-sheet").hidden = false;
    $("bonus-open").setAttribute("aria-expanded", "true");
    $("bonus-sheet").querySelector(".sheet-close").focus();
  });
  document.querySelectorAll("[data-close-bonus]").forEach(node => {
    node.addEventListener("click", () => closeBonus(true));
  });

  function openSheet() {
    $("roadmap-sheet").hidden = true;
    closeBurn();
    $("sheet").hidden = false;
  }

  function closeSheet() {
    $("sheet").hidden = true;
  }

  $("action").addEventListener("click", () => {
    if (verifyCollection) refresh();
    else if (model?.phase === "ready_to_collect") collect();
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
    closeBonus();
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
      referralPage = 0;
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
      closeBonus(true);
      $("roadmap-sheet").hidden = true;
      $("daily-sheet").hidden = true;
      $("chest-sheet").hidden = true;
    }
  });

  // A retained request id makes retries safe after a lost response.
  let dailyBusy = false;
  function paintDaily(data) {
    $("daily-info").textContent = `День ${data.streak}/90 · ${data.claimed ? "Сегодня получено" : `Сегодня ${data.reward} Coin`}`;
    $("daily-claim").disabled = data.claimed;
    $("daily-claim").textContent = data.claimed ? "СЕГОДНЯ ПОЛУЧЕНО" : `ПОЛУЧИТЬ ${data.reward} COIN`;
    const current = Math.min(90, Math.max(1, Number(data.streak) || 1));
    const weekStart = Math.floor((current - 1) / 7) * 7 + 1;
    const calendar = $("daily-calendar");
    calendar.replaceChildren();
    for (let day = weekStart; day <= Math.min(weekStart + 6, 90); day++) {
      const tile = document.createElement("div");
      tile.className = "daily-day";
      if (day < current || (day === current && data.claimed)) tile.classList.add("is-complete");
      if (day === current) tile.classList.add("is-current");
      const label = document.createElement("span");
      label.textContent = `ДЕНЬ ${day}`;
      const reward = document.createElement("b");
      reward.textContent = `${day === 1 ? 100 : day === 2 ? 200 : 600}`;
      const coin = document.createElement("small");
      coin.textContent = day % 7 === 0 ? `🎁 ×${day / 7}` : "COIN";
      tile.append(label, reward, coin);
      calendar.appendChild(tile);
    }
    const nextChest = data.claimed ? Math.floor(current / 7 + 1) * 7 : Math.ceil(current / 7) * 7;
    $("daily-milestone").textContent = nextChest <= 90
      ? `🎁 День ${nextChest} · ${nextChest / 7} сундук(а)`
      : "🏁 До конца серии остались последние дни";
    $("chest-info").textContent = `Бесплатный сегодня: ${data.free_chest ? "доступен" : "использован"} · бонусных: ${data.bonus_chests}`;
    $("gram-info").textContent = `Внутренний баланс GRAM: ${(data.gram_hundredths / 100).toFixed(2)}`;
    $("chest-spin").disabled = !data.free_chest && !data.bonus_chests && !sessionStorage.getItem("dojo_chest_request");
  }
  async function loadDaily() {
    $("daily-claim").disabled = true;
    $("chest-spin").disabled = true;
    try { paintDaily((await api("daily")).daily); }
    catch (error) {
      $("daily-info").textContent = "Не удалось загрузить. Закрой и открой окно снова.";
      $("chest-info").textContent = "Не удалось загрузить. Закрой и открой окно снова.";
      showToast(error.message, true);
    }
  }
  function alignChestWinner() {
    const reel = $("chest-reel");
    const target = reel.querySelector(".reel-prize.is-winner");
    const track = reel.querySelector(".chest-reel-track");
    if (!target || !track || $("chest-sheet").hidden || dailyBusy) return;
    const offset = target.offsetLeft + target.offsetWidth / 2 - reel.clientWidth / 2;
    track.style.transition = "none";
    track.style.transform = `translateX(${-Math.max(0, offset)}px)`;
  }
  $("daily-open").addEventListener("click", () => { closeBonus(); $("daily-sheet").hidden = false; loadDaily(); });
  $("chest-open").addEventListener("click", () => {
    closeBonus();
    $("chest-sheet").hidden = false;
    requestAnimationFrame(alignChestWinner);
    loadDaily();
  });
  window.addEventListener("resize", alignChestWinner);
  document.querySelectorAll("[data-close-daily]").forEach(el => el.addEventListener("click", () => { $("daily-sheet").hidden = true; }));
  document.querySelectorAll("[data-close-chest]").forEach(el => el.addEventListener("click", () => { $("chest-sheet").hidden = true; }));
  $("daily-claim").addEventListener("click", async () => {
    if (dailyBusy) return;
    dailyBusy = true;
    try { const data = await api("daily_claim"); paintDaily(data.daily); showToast(`+${data.claim.reward} Coin`); refresh(true); }
    catch (error) { showToast(error.message, true); }
    finally { dailyBusy = false; }
  });
  async function animateChest(prize) {
    const reel = $("chest-reel");
    const scene = $("chest-scene");
    const result = $("chest-result");
    const isGram = prize.kind === "gram";
    const isChest = prize.kind === "chest";
    const amount = isGram ? (prize.amount / 100).toFixed(2) : String(prize.amount);
    const winner = prize.kind === "gift" ? "коллекционный подарок Telegram · заявка сохранена, администратор передаст вручную" : isGram ? `${amount} виртуальных GRAM` : isChest ? `${amount} сундука` : `${amount} Coin`;
    result.textContent = "";
    scene.classList.remove("is-win");
    scene.classList.add("is-opening");
    reel.replaceChildren();
    const track = document.createElement("div");
    track.className = "chest-reel-track";
    const prizes = [
      {kind: "COIN", value: "100"}, {kind: "COIN", value: "200"},
      {kind: "COIN", value: "300"}, {kind: "COIN", value: "400"},
      {kind: "COIN", value: "500"}, {kind: "GRAM", value: "0.01"},
      {kind: "GRAM", value: "0.02"}, {kind: "GRAM", value: "0.03"},
      {kind: "GRAM", value: "1"}, {kind: "GRAM", value: "2"},
      {kind: "GRAM", value: "3"},
      {kind: "CHEST", value: "2"},
      {kind: "GIFT", value: "NFT"},
    ];
    // The centre cell always displays the server receipt; other cells are decorative.
    for (let i = 0; i < 25; i++) {
      const cell = document.createElement("div");
      const chosen = i === 22;
      const decoration = prizes[(i * 5 + 1) % prizes.length];
      const kind = chosen ? prize.kind.toUpperCase() : decoration.kind;
      const value = chosen ? (kind === "GIFT" ? "NFT" : amount) : decoration.value;
      cell.className = `reel-prize${chosen ? " is-selected" : ""}${kind === "GRAM" ? " is-gram" : ""}${kind === "GIFT" ? " is-gift" : ""}`;
      const icon = document.createElement("span"); icon.className = "reel-prize-icon";
      icon.textContent = kind === "CHEST" ? "▣" : kind === "GRAM" || kind === "GIFT" ? "✦" : "◈";
      const number = document.createElement("strong"); number.textContent = value;
      const label = document.createElement("small");
      label.textContent = kind === "GIFT" ? "ПОДАРОК" : kind === "GRAM" ? "GRAM" : kind === "CHEST" ? "СУНДУКА" : "SENSEI COIN";
      cell.append(icon, number, label);
      track.appendChild(cell);
    }
    reel.appendChild(track);
    const target = track.children[22];
    // Align the exact server-selected result beneath the fixed centre marker.
    const distance = target.offsetLeft + target.offsetWidth / 2 - reel.clientWidth / 2;
    const reduced = motionReduced();
    if (!reduced && !$("chest-sheet").hidden && distance > 0) {
      let scaling = true;
      const magnify = () => {
        if (!scaling) return;
        const centre = reel.getBoundingClientRect().left + reel.clientWidth / 2;
        for (const cell of track.children) {
          const box = cell.getBoundingClientRect();
          const proximity = Math.max(0, 1 - Math.abs(box.left + box.width / 2 - centre) / 150);
          cell.style.scale = String(1 + proximity * 0.12);
        }
        requestAnimationFrame(magnify);
      };
      requestAnimationFrame(magnify);
      await new Promise(resolve => {
        requestAnimationFrame(() => {
          track.style.transition = "transform 4.4s cubic-bezier(.12,.68,.10,1)";
          track.style.transform = `translateX(${-distance}px)`;
        });
        setTimeout(resolve, 4500);
      });
      scaling = false;
    } else {
      track.style.transform = `translateX(${-Math.max(0, distance)}px)`;
    }
    target.classList.add("is-winner");
    scene.classList.remove("is-opening");
    scene.classList.add("is-win");
    result.textContent = `Твоя награда: ${winner}`;
  }
  $("chest-spin").addEventListener("click", async () => {
    if (dailyBusy) return;
    dailyBusy = true;
    $("chest-spin").disabled = true;
    try {
      const key = "dojo_chest_request";
      let request = sessionStorage.getItem(key);
      if (!request) { request = crypto.randomUUID(); sessionStorage.setItem(key, request); }
      const data = await api("chest", {request_id: request});
      // Keep the receipt key until the animation has displayed its result.
      // A failed/interrupted presentation can then replay the same server receipt.
      await animateChest(data.prize);
      sessionStorage.removeItem(key);
      paintDaily(data.daily); refresh(true);
    } catch (error) { showToast(error.message, true); await loadDaily(); }
    finally { dailyBusy = false; }
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refresh(true);
      if (activeTab === "tasks" && !taskBusy) loadTasks(true);
      if (activeTab === "referrals") loadReferrals(true);
    }
  });
  setInterval(tick, 250);
  setInterval(() => {
    if (!document.hidden) refresh(true);
  }, 30000);

  const onMotionSystemChange = () => {
    syncMotionClass();
    paintMotionControl();
    if (!motionReduced()) seedAmbient();
    window.dispatchEvent(new Event("sensei-motion-change"));
  };
  if (motionQuery?.addEventListener) motionQuery.addEventListener("change", onMotionSystemChange);
  else motionQuery?.addListener?.(onMotionSystemChange);
  $("motion-setting").addEventListener("click", changeMotionPreference);
  paintMotionControl();
  setupMagicTrail();
  seedAmbient();
  seedMiningParticles();
  setInterval(paintChain, 1000);
  setInterval(() => {
    const taskDay = tasks.find((task) => task.daily)?.claim_day;
    const today = new Date(serverNow()).toISOString().slice(0, 10);
    if (taskDay && taskDay !== today && !taskBusy && !$("view-tasks").hidden) loadTasks(true);
  }, 60000);
  applyTranslations();
  seedBoot();
  render();
  if (initData()) {
    bootSetGoal(26, t("ЗАГРУЗКА…"));
    // Other tabs load independently on first open in setTab().
    refresh().finally(() => {
      completeBoot(t("ЗАГРУЗКА…"));
      if (new URLSearchParams(initData()).get("start_param")?.startsWith("vs_") && !sessionEnded) {
        if (!vsDialog.open) vsDialog.showModal();
        vsRequest("vs_invite");
      } else if (!sessionEnded && resumePrivateVs()) {
        if (!vsDialog.open) vsDialog.showModal();
        vsRequest("vs_state");
      }
    });
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
