# /donate — пакеты SenseiCoin за Stars

Новые пакеты: 1 XTR → 500 Coin; 5 → 3500; 10 → 8000; 50 → 45000. XP, серия и игровые попытки не выдаются. xRocket остаётся добровольной поддержкой без автоматической выдачи монет.

Новые callback coinbuy:<stars> создают createInvoiceLink с versioned payload coinbuy:v1:<uid>:<stars>. Суммы в целых Stars, один LabeledPrice, provider_token пустой. Меню заменяется кнопкой оплаты. Старые callback/payload donate: продолжают обслуживать ранее выставленные добровольные донаты без начисления монет: прошлые пожертвования не переоцениваются.

Pre-checkout валидирует payload, валюту XTR, владельца и сумму; проверяет профиль, достаточность bank.single.coins и транзакционный MongoDB. Сам check не резервирует банк: остаток может измениться до оплаты. Обязательное подтверждение Telegram остаётся.

Successful_payment сначала сохраняет star_coin_payments по уникальному charge (_id), затем snapshot/majority транзакцией переводит монеты из bank.single.coins в users.coins, пишет transactions star_coin:<charge> и fulfilled. Нет автопополнения банка и эмиссии; не используется legacy main.balance. Повтор charge не переводит монеты снова. При недостатке банка или недоступном профиле после оплаты — refund_required, вызов refundStarPayment, затем refunded. При неоднозначном возврате нельзя обещать пользователю, что он завершён: /paysupport и сверка Telegram.

Состояния received/refund_required восстанавливаются пользователем через /donate без нового платежа. Пока есть такой платёж, новый checkout отклоняется. Фоновой очереди нет; при сбое до записи receipt необходима сверка getStarTransactions через поддержку. Подтверждение в чате может повториться при повторной доставке payment, но финансовый перевод идемпотентен.

Тесты с rollback fake проверяют все тарифы, отсутствие XP/серии, восемь повторов charge, rollback журнала и recovery через /donate, невалидный payload и владельца, недостаток банка; реальный aiogram dispatch проверяет маршрутизацию receipt. Disposable Mongo CI тест проверяет параллельную обработку charge, один журнал и сохранение банк+пользователь. Это не live Stars checkout/возврат; production БД не изменяется тестами.
