# Инженерный аудит: архитектура, надёжность и быстродействие

База: `94d848a7da3eb5f686eeb5d74b3a6c892fcc703b` (после PR52).
Подход: обзор исходников и зарегистрированных интерфейсов, существующего покрытия, локальные регрессии, измерение числа I/O операций. Это не живой прогон всех функций и не сертификация финансовой безопасности. Production Mongo, платежи, рассылки и модерация не запускались. Мнение «команды» представлено направлениями ревью, а не утверждением о независимых проверках несколькими людьми.

## Краткий вывод
Бот функционально богат; главный риск — неоднородность старой и новой архитектуры. Новые paid/campaign-пути используют транзакции и journal, старые игры/экономика и фоновые задачи часто полагаются на память процесса. Масштабирование несколькими воркерами сейчас нельзя считать безопасным. Не увеличивать число экземпляров ради скорости до аудита денежных путей.

Главная задержка обычного сообщения — последовательная цепочка Mongo/Telegram middleware, а не Canvas. Логи пользователя ранее показывали около 2 секунд на обычное сообщение, но это отдельные примеры, не p95 и не доказательство текущего состояния. Для выводов о production нужны трассировки каждого этапа и метрики с реальной нагрузкой.

## Изменено в этой ветке
1. **EconomyService: single-flight чтение обращения монет.** При истечении существующего 10s кэша один пересчёт обслуживает одновременно пришедшие сообщения. Награды, банк и формула халвинга не менялись. Срок кэша начинается после успешного чтения. Ошибка не кэшируется.
2. **StatsService: один агрегат users вместо count + двух полных суммирований.** Контракт результата сохранён. Холодный refresh — 4 Mongo операции вместо 6; lock теперь покрывает весь refresh, а не только чтение кэша. Ошибка не сохраняется в кэш. Остались прежние нулевые placeholder total_emitted/total_withdrawn — это НЕ финансовый аудит.
3. **ThrottleService: корректное фиксированное окно.** Раньше numeric expiry не подходил для TTL Mongo; insert-only мог навсегда заблокировать повторный запрос. Теперь атомарный conditional upsert проверяет срок сам, сохраняет BSON Date, поддерживает старые numeric документы без массовой миграции. Активное окно — DuplicateKeyError/False; истёкшее доступно сразу, независимо от TTL monitor. TTL индекс ожидается на startup. Существующий fail-open при сбое Mongo сохранён; limiter не является финансовой блокировкой.
4. **Anonymous messages:** DigestMiddleware больше не обращается к отсутствующему from_user; ChatActivityMiddleware обновляет активность чата, но не приписывает anonymous/sender-chat сообщение пользователю Banzai.

Не добавлялись локальные очереди, persistent cache на диске, автоиндексация с удалением дублей или финансовые миграции.

## Измерения и проверки
`BOT_TOKEN=123456:TEST python -m scripts.benchmark_read_refresh`
Скрипт исполняет реальные методы из указанной базы и текущие методы, но Mongo заменена моделью async I/O по 2 ms. Это **не production benchmark**. Он проверяет устранение дублирующих запросов на 32 одновременно пришедших холодных чтениях:

| Чтение | База: операций | После | Один локальный прогон, модель времени |
|---|---:|---:|---|
| Обращение монет | 32 | 1 | 2.67 → 2.47 ms |
| Админ-статистика | 192 | 4 | 14.88 → 9.40 ms |

Ключевой результат — снижение нагрузки, не обещание ускорения каждого сообщения в 32/48 раз. На одном последовательном admin refresh — 6 → 4 операции; на cache hit изменений числа запросов нет. Кэш и single-flight только внутри процесса, Mongo остаётся единственным постоянным хранилищем.

Локально полный pytest: **596 passed, 48 skipped, 2 xfailed, 2 существующих crypto-mock предупреждения**. Пропуски требуют replica set/нативного runtime/специальной среды. Новые unit-тесты покрывают 32 concurrent refresh, ошибки, истечение кэша, форму статистики, анонимные сообщения и limiter. Новый integration-тест `test_throttle_mongo.py` проверяет реальную Mongo: 32 конкурента, один победитель, возврат доступа без TTL job, numeric→Date совместимость. Результат этого интеграционного теста локально НЕ подтверждён (нет тестовой Mongo); должен выполняться CI.

## Матрица продуктовых направлений
| Направление | Источники/оценка | Что улучшать далее |
|---|---|---|
| Запуск, polling, health | src/main.py, infra/mongo; pre_checkout подписка сохранена | readiness отдельно от HTTP liveness; явный номер сборки; бюджет времени startup и graceful shutdown |
| Профиль, регистрация, уровни, достижения | user/level/achievement + user_activity | трассировка DB round-trips; убрать повторные чтения профиля только с доказательством сохранности наград |
| SenseiBank, сообщения, катана, exchange | economy/exchange; финансовый P0 ниже | транзакционные bank/user/journal, единые деньги/округление, idempotency для каждого начисления |
| Бесплатная Ежа, ласка, native widgets | daily/daily_pet/presenters/widgets/mtproto | сохранить 15s и at-most-once; метрики publish/transition/input; live проверки клиентов, без редизайна |
| Повтор Ежа за Stars | paid_hedgehog handler/service | persisted receipt есть; тестировать удалённый anchor, запоздалый receipt, refund и неоднозначную доставку |
| /donate → Coin, legacy donations | star_coin + donate middleware | восстановление /donate есть; автоматическая сверка getStarTransactions и journal reconciliation |
| Комментарии/кампании/розыгрыши | comment_campaign_service, worker, integration suite | наблюдаемость backlog/lease/retry и deadline; fault injection; не менять завершённые кампании |
| Банзай | banzai_service, chat_activity | запись активности + update игры на каждое сообщение; timestamp TTL числовой, Mongo TTL его не очистит — отдельная миграция с сохранением читателей |
| Дуэли | duel_service, duel_resources, tasks | несколько state/task в памяти; restart/concurrent settlement аудит, единый task registry |
| Боссы и редактор | boss_service/handlers + admin gates | внешние выплаты, idempotency и конкуренция редактирования; полный happy-path редактора |
| Slots, roulette, bomb, wave, trade | handlers/services, текущие unit tests | общий transactional payout слой; durable game ownership; не распараллеливать деньги на asyncio.gather |
| Лотерея, tickets, сезоны | lottery/stats/admin | выбор из полного списка билетов и destructive reset требуют отдельного контроля и подтверждения |
| Викторина | quiz.py + QuizService | P0 доступ /addquestion; изоляция FSM админа, обычные ответы не закрывать |
| Digest, Sage, Fly AI | digest/fly/providers | журнал/таймеры digest в памяти, задачи create_task; bounded task registry + общий HTTP session lifecycle, timeouts/quotas; тестировать лимиты провайдера |
| Popugai | сервис/ middleware + Mongo integration | per-chat media, sample, at-most-once уже есть; мониторинг недействительных file_id и размера коллекций |
| Модерация, captcha, подписка | middleware/services/events | P0 ошибочный subscription cache; разрешения fail-closed там, где это необходимо; mutation-event invalidation |
| Chat settings, inactive reminders | settings/activity | аудит всех индексов и их await; streaming курсоры вместо unbounded materialization; не терять последнюю активность ради debounce |
| Рассылка и zov | broadcast.py/service, zov | P0 глобальный pending; Mongo drafts/jobs, cursor batching, Telegram RetryAfter, restart recovery |
| Музыка, crypto, draw, VK/xRocket | внешние клиенты/handlers | HTTP pooling, общий timeout/backoff/circuit breaker; отсутствие ключа — явная деградация; live доступ не проверен |
| Admin/help/access | admin_help, filters, docs/ADMIN_FUNCTION_AUDIT | права на каждое FSM-состояние, audit trail; не путать наличие команды с исполнением happy path |
| Observability/PII | logging middleware, многочисленные INFO | trace IDs, p50/p95, slow-step logs; не писать текст сообщений/username и env ADMIN_IDS на каждый проход |
| Хранилище/репозиторий | infra, многочисленные legacy scripts | inventory индексов и schema versions; archive неиспользуемых скриптов после проверки ссылок; Mongo-only для новых durable jobs |

## Приоритеты — не исправлено в этой ветке
### P0: деньги и доступ
- **Эмиссия в economy_service**: `_get_bank_balance`, `_withdraw_from_bank`, process_message_reward и другие reward-пути сбрасывают пустой/недостаточный банк к bank_initial_coins. Новый lock чтения НЕ устраняет это. Удаление reset без аудита всех callers может приводить к частичным выдачам: нужен отдельный transactional payout слой и тесты conservation/rollback. Не выполнять reset production.
- **Подписка**: subscription.py трактует первый успешный throttle=True как «подписка уже подтверждена», не проверив Telegram. Затем делает повторные Telegram запросы на cache hit. Нужен отдельный Mongo-кэш фактического membership (включая restricted.is_member), а не limiter. Также callback check_sub проверяет restricted без is_member.
- **Рассылка**: BroadcastService._pending один на все чаты/админов. Права уже закрыты, межадминская гонка и потеря draft при рестарте остаются.
- **Quiz**: /addquestion и FSM административного добавления не ограничены ролью. Закрыть точечно, не root-gate весь игровой роутер.

### P1: память, фоновые задачи, внешние вызовы
- Mongo TTL работает только с BSON Date. Проверить все TTL-поля, не только throttle: banzai timestamp — int. Нельзя просто поменять тип без адаптации существующих timestamp сравнений.
- `chat_settings_service` и ряд других сервисов вызывают Motor create_index из sync __init__ без явного ожидания/обработки startup. Нужен единый async index manifest с проверкой существующих дублей (без удаления).
- Digest chats/cooldowns и game state в памяти: конфликт с Mongo-only durability, потеря после рестарта. Перенести отдельно с совместимой схемой и правилами хранения текста.
- На каждом сообщении много последовательных round-trips: mute, user activity/reward, group activity, banzai, popugai. Сначала трассировка; кэшировать только неавторитетные чтения с bounded TTL/invalidation. Не кэшировать баланс и права бессрочно.
- `to_list(length=None)` в рассылках, lottery и maintenance — риск больших выделений памяти. Streaming/batching, где не меняется справедливость выбора победителя.
- Фоновые create_task часто не регистрируются и не дожидаются shutdown. Нужен bounded registry, cancel+await, отчёт исключений; никакой локальной persistent очереди.
- HTTP ClientSession создаётся многими API-клиентами на каждый вызов. Connection pooling полезен, но требует явного close и тестов cancel/restart; не применять механически ко всем SDK.

### P2: измерение и эксплуатация
- p50/p95/p99 времени update и каждого middleware; Mongo queries/update и slow query, event-loop lag, API latency/error, task count, queue depth, размер RSS.
- Индексы выбирать по explain() на обезличенном staging датасете. Большой индекс может замедлить запись; не добавлять все возможные индексы вслепую.
- Load test отдельным стендом: 1/10/50 сообщений в секунду, разнообразие пользователей, горячий/холодный кэш, перезапуск, медленная Mongo/Telegram. Производительность на искусственном sleep не переносится в production.
- Проверять pinned runtime/Telegram QuickJS в CI. Локальные skipped тесты не записывать в «прошли».

## Безопасный порядок дальнейших работ
1. Отдельный P0 PR для единого bank-funded transactional reward API; audit потребителей, replica-set fault/concurrency tests, сверка журналов без исправления балансов задним числом.
2. Отдельные небольшие PR: subscription factual cache; quiz admin FSM guards; Mongo broadcast drafts/jobs.
3. Index/schema manifest и TTL миграции с dry-run/совместимостью, затем durable game/task recovery.
4. Обсервабельность и staging нагрузка, только потом оптимизация middleware и HTTP pool на основании p95.

Ни одна из этих рекомендаций не означает разрешения на удаление БД, пересчёт наград, ретроначисления или изменение игровой механики.
