# Причина вылетов Out of Memory — аудит

Дата: 2026-11-26. Область: весь процесс бота (long polling + 3 веб-миниаппа + фоновые задачи),
замеры выполнены на чистом импорте и синтетической нагрузке (Python 3.11, Pillow 11).

## Краткий вывод

OOM — не одна утечка, а сложение четырёх факторов на инстансе Render с ограниченной памятью
(обычно 512 МБ):

1. **Pillow-спайки 60–130 МБ RSS на одно фото** в пути ежедневной выдачи (`normalize_photo_bytes`,
   `to_hedgehog_html`), причём синхронно на event loop (блокирует loop → таймауты Bot API).
2. **Пожизненные per-user словари локов/кэшей** в 5+ сервисах — рост пропорционально числу
   пользователей, вытеснения нет.
3. **Полная экономика с Mongo-транзакцией на КАЖДОЕ сообщение** (троттлинг отключён:
   `THROTTLE_RATE_LIMIT_MESSAGES = 0`) — сотни параллельных in-flight обновлений при всплесках.
4. **Базовый RSS процесса 150–180 МБ** сразу после импорта — на 512-мегабайтном инстансе
   запас прочности ~300 МБ до любых спайков.

Скриншот с Render (таймауты `TelegramNetworkError: Request timeout error`, retry-цикл
`get_chat_member`, `Slow message processing: duration_sec=1.157`) — это одновременно
**симптом** (event loop заблокирован синхронным Pillow/Mongo) и **ускоритель** (in-flight
запросы с медиапейлоадами живут до полного таймаута, очередь апдейтов растёт).

---

## 1. Измеренные факты

| Что | RSS |
|---|---|
| Пустой интерпретатор | ~19 МБ |
| Полный импорт `src.main` (все хендлеры, сервисы, Pillow, huggingface_hub) | **150–180 МБ** |
| Рендер GIF катаны (40 кадров, `to_upgrade_gif`) | пик **+35 МБ** (кэш `lru_cache(8)` до ~5 МБ/шт) |
| Анимация карточки (`to_gif`, 12 кадров) | +10–20 МБ |
| `normalize_photo_bytes`, фото 2560×2560 JPEG без перекодирования | **+26 МБ** |
| `normalize_photo_bytes`, 2560×2560 с перекодированием (`optimize=True`) | пик **+60–90 МБ** (HWM +87 МБ) |
| `to_hedgehog_html` (5 миниатюр, по 2 `.convert('RGB')` на размер) | **+25 МБ** на запрос |
| 2000 пользователей → `economy_service._locks` | +4 МБ (≈2 КБ/юзер, растёт вечно) |

Замер: `/proc/self/status` (VmRSS/VmHWM) и `ru_maxrss`; синтетические сценарии повторяют
реальные пути `src/bot/presenters/daily_hedgehog.py` и `src/widgets/*`.

## 2. Фактор 1 — Pillow в горячем пути выдачи (главный спайк)

Цепочка: `/senseidaily`, платный ёж, обычная выдача награды →
`src/bot/presenters/daily_hedgehog.py:_load_picture_with_reroll` → `picture()` →
`normalize_photo_bytes(content)`.

- `MAX_TELEGRAM_PHOTO_SIDE = 2560` — изображения до 2560px включительно проходят **без**
  даунскейла, но `img.load()` декодирует их целиком (~20 МБ RGB), далее возможны
  `ImageOps.exif_transpose(...).convert('RGB')` (ещё копия) и перекодирование
  `save(..., optimize=True)` (большие scratch-буферы Huffman). Замеренный пик — **до +90 МБ**
  на одно фото; до 4 попыток реролла на доставку.
- `src/widgets/hedgehog.py:to_hedgehog_html` — вызывается на **каждую** выдачу игры/виджета
  (`hedgehog_presenter`, `mtproto/widgets.py`, `user_commands.py:open_pet`):
  `original.convert('RGB')` заново на каждый из 5 размеров миниатюр → +25 МБ/запрос.
- Всё это выполняется **синхронно на event loop** (нет `asyncio.to_thread`, в отличие от
  `widgets.py`/`katana_presenter.py`, где есть `RENDER_SLOTS`). Заблокированный loop →
  ровно те «Request timeout error» и `Slow message processing`, что видны в логе;
  таймауты → повторные попытки → новые доставки → новые спайки (обратная связь).
- `PIL.Image.MAX_IMAGE_PIXELS` нигде не задан явно; между предупреждением (178 Мпкс) и
  жёсткой ошибкой (356 Мпкс) изображение успевает занять ~1 ГБ при декодировании.
  Путь `src/bot/sage_vision.py` это уже учитывает (DecompressionBomb), путь ежедневной
  выдачи — нет.

## 3. Фактор 2 — пожизненные словари на пользователя (медленная утечка)

Никогда не чистятся, вытеснения нет:

| Место | Структура | Ключ |
|---|---|---|
| `src/services/economy_service.py:59,68` | `self._locks` | `message_reward:{uid}`, `katana_up:{uid}`, `katana_buy:{uid}`, `game_win:{uid}`, `fire_drop:{uid}` |
| `src/services/daily_service.py:43` | `self._user_locks` | user_id |
| `src/services/daily_pet_service.py:39` | `self._locks = defaultdict(asyncio.Lock)` | user_id |
| `src/services/dojo_miner_service.py:65` | `self._locks = defaultdict(asyncio.Lock)` | user_id |
| `src/services/quiz_service.py:48-49` | `_chat_locks`, `_loop_locks` | chat_id |
| `src/services/banzai_service.py:62` | `_user_display_cache` (TTL 6 ч у значения, ключи не удаляются) | user_id |

Замер: 2000 юзеров → +4 МБ только на локах экономики (~2 КБ/юзер со всеми накладными).
На 100–200 тыс. пользователей это сотни МБ, и процесс умирает «сам по себе», без спайков.
Тот же класс: `src/core/cache.py:SimpleCache` удаляет истёкший ключ только при повторном
чтении (write-and-forget ключи живут вечно; сейчас масштаб мал — `crypto_service`).

## 4. Фактор 3 — транзакция на каждое сообщение

`src/core/constants.py:3339` — `THROTTLE_RATE_LIMIT_MESSAGES = 0` (отключено сознательно,
см. `DEPLOYMENT_SUMMARY.md`), поэтому `user_activity` начисляет награду за **каждое**
сообщение: `economy_service.process_message_reward` делает ~8–10 операций Mongo, включая
**транзакцию** (`settle` → `transaction()`), проверку достижений, 2 insert в
`banzai_chat_activity` (без TTL!), upsert `chat_user_activities`.

При всплеске сообщений сотни обновлений обрабатываются одновременно (aiogram не ограничивает
параллелизм `_handle_update_tasks`); каждое держит Update (Pydantic), фреймы и буферы
отправки. Если Bot API при этом таймаутится (см. скриншот), запросы с `BufferedInputFile`
(гифки/фото до 5 МБ) живут окно таймаута — пик накладывается на Pillow-спайки.

## 5. Фактор 4 — базовый след и «всё в одном процессе»

150–180 МБ после импорта; в одном процессе живут: long polling aiogram, aiohttp-сервер
(3 миниаппа), 5+ фоновых циклов (`dojo_miner.auto_loop`, `emission_watch`, `join_request_watch`,
`dojo_rooms.cleanup_loop`, `chat_activity` монитор, banzai-воркеры, comment campaigns) и,
при `NATIVE_WIDGET_TRANSPORT=mtproto`, второй клиент Telethon с MemorySession.

`src/infra/storage` (250 МБ ассетов боссов) на RSS не влияет (файлы отправляются
`FSInputFile` с диска), но раздувает Docker-образ.

## 6. Что проверено и исключено

- `ThrottleService` — Mongo с TTL, не память.
- `digest_service` — `deque(maxlen=1000)` на чат, ограничено.
- `_roulette_history` — обрезается до 10; `_active_bombs/_active_roulettes/_active_waves` —
  удаляются по завершении; `duel_service.duels` — `_archive_duel` делает pop через 60 с.
- `group_admin_access` — LRU 4096 + `WeakValueDictionary` для локов (образцово).
- `mtproto/bootstrap.py` — лимиты 2/32 МБ, одноразово.
- Рендеры карточек/катан — ограничены `RENDER_SLOTS = Semaphore(2)` + `to_thread`.
- FSM (`MemoryStorage`) — состояния ставят только админ-флоу, объём пренебрежимо мал.
- `HedgehogWidgetMiddleware.model_dump` на каждый update — быстрый (~10 мкс), не утечка.
- `comment_campaign_service.capture` — ранний выход, batch-выборки с `limit`.
- Сессии Mongo (`start_session`) закрываются через `async with`.

## 7. Рекомендации (по убыванию эффекта)

1. **Нормализация фото**: декодировать через `Image.open(...).draft('RGB', (1280,1280))`
   (даунскейл на этапе декодера) или сразу ограничить `MAX_TELEGRAM_PHOTO_SIDE = 1280`;
   убрать `optimize=True` при перекодировании; гонять через `asyncio.to_thread` под
   общим `RENDER_SLOTS`; нормализовать **один раз при загрузке** в GridFS, а не на каждую
   выдачу. В `to_hedgehog_html` — один `convert('RGB')` и `ImageOps.contain` от него.
   Явно задать `Image.MAX_IMAGE_PIXELS` и отклонять бомбы (как в `sage_vision.py`).
2. **Ограничить per-user словари**: полосатые локи (`locks[uid % 256]`) — нулевой рост при
   той же корректности; либо `cachetools.TTLCache(maxsize=...)`. Для
   `SimpleCache` — периодическая чистка истёкших ключей.
3. **Вернуть троттлинг наград** (например, 60 с на юзера, как было в `ActivityConfig`) или
   вынести начисление в фоновую очередь с ограниченной глубиной — снять транзакцию с
   горячего пути каждого сообщения.
4. **Лимит параллелизма обновлений** (семафор в outer middleware) + мониторинг:
   периодически логировать RSS/`tracemalloc` top-10, алерт при росте.
5. Добавить TTL-индекс (или чистку) `banzai_chat_activity` — растёт на каждое сообщение
   вне игр (Mongo-side, но влияет на кэш БД).
6. Рассмотреть вынос миниаппов в отдельный сервис или инстанс ≥1 ГБ — базовый след
   процесса почти не оставляет запаса на 512 МБ.

## 8. Обновление 2026-11-26: пункт 1 (картинки) реализован

`src/bot/presenters/daily_hedgehog.py` и `src/widgets/hedgehog.py`:

- `normalize_photo_bytes`: JPEG декодируется через `draft` сразу в финальном масштабе
  (без полноразмерной промежуточной копии); файлы, которые отдаются без пережатия,
  валидируются декодом в 1/8 масштаба (пик ≈ +2 МБ вместо +27 МБ); `optimize=True`
  убран; `exif_transpose(..., in_place=True)` без лишней копии; лимит
  `MAX_IMAGE_PIXELS = 20 Мпкс` + `DecompressionBombWarning → ошибка` (как в `sage_vision`).
- Новая обёртка `normalize_photo_bytes_async`: Pillow работает в `asyncio.to_thread`
  под общим `RENDER_SLOTS` (не блокирует event loop, не более 2 декодов одновременно).
- `to_hedgehog_html`: одна конвертация `convert('RGB')` вместо пяти, `draft` для
  крупных JPEG, битая/огромная картинка деградирует до виджета без фото вместо падения.

Замеры пика RSS (чистый процесс, один вызов; HWM − база ≈155 МБ):

| Вход | было | стало |
|---|---|---|
| JPEG 5856×2849 (пережатие) | +193 МБ | **+42 МБ** |
| JPEG 4032×3024 + ICC (пережатие) | +152 МБ | **+105 МБ** |
| JPEG 2560×2560 (транзит, без пережатия) | +27 МБ | **+2 МБ** |
| `to_hedgehog_html` от 2560px | ~+25 МБ | **+7 МБ** |

Тесты: 137 passed по затронутым модулям (daily_pet, hedgehog_game, hedgehog_gallery,
inline_hedgehog, starter_kit, paid_hedgehog, daily_pet_miniapp). Полный `tests/unit`:
1548 passed; 2 падения (`mtproto bootstrap`, `test_miner_assets_and_csp`) падают
и без этих правок — особенности среды, не регрессия.

Остаточный риск: PNG/WebP Pillow декодирует только целиком (draft не применим) —
держится лимитом `MAX_IMAGE_PIXELS` и `RENDER_SLOTS`. Пункты 2–4 (локи, троттлинг) не тронуты.
