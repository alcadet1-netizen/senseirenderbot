> Исторический аудит до реализации. Последующее решение пользователя: «старая база с комментариями не нужна, задача реализовать все в MONgo». Миграция старой SQLite-очереди отменена; текущая реализация и порядок переключения описаны в COMMENT_CAMPAIGNS.md. Нижеследующий план сохранён как история рассмотренных рисков, а не инструкция запуска.

# Аудит inbox кампаний и план MongoDB-only (на согласование)

Статус: только аудит исходников/истории PR. Production не подключался, файлы очереди/UUID/содержимое Mongo не прочитаны. Ничего не мигрировано. Runtime-код и настройки не изменены. Этот документ НЕ разрешение на deployment.

## Происхождение

- PR #27, commit `4282e3cb9b16bf35a687fa85fafacec7017886d6`: добавлен durable SQLite WAL ingress для replay при ошибках Mongo. Описание PR прямо вводит требование persistent storage. Это архитектурное решение реализации кампаний, не требование Telegram или MongoDB и не необходимость для экономики.
- PR #28, commits `0390083ecf0c03b3c8a67a9b19dfc4e6463dd49f`, `a7080d08defa81b549c9f97be41880c53a062de0`: добавлены SQLite settlement barrier и привязка UUID в Mongo с отказом независимым очередям. Защита закрывает реальную гонку, но закрепляет зависимость от общего файла.
- `aiosqlite` присутствует в requirements; отдельные legacy SQLAlchemy-скрипты tests/verify_quiz_fix.py и tests/verify_lottery_fix.py используют in-memory SQLite. Это не production очередь. Перед удалением пакета нужно убрать/перевести эти сценарии отдельно; не подменять экономику legacy SQL-моделями.

## Текущее устройство

`src/infra/comment_campaign_inbox.py`:
- `open()` создаёт каталог, SQLite-файл, WAL/FULL, три таблицы и UUID, если его нет.
- `campaign_inbox`: `(bot_id, update_id)` PK, полный JSON Telegram Update; pending updates сортируются по update_id; ack удаляет запись только после ingest в Mongo.
- `campaign_deleted_inbox`: `(bot_id, chat_id, message_id)` PK, неприменённые известные удаления (tombstones).
- `campaign_inbox_identity`: `id=1`, строковый UUID.
- `settlement_barrier()`: asyncio lock + BEGIN IMMEDIATE, проверка обеих очередей на пустоту и блокировка put/ack до завершения Mongo sealing. Это не просто временный кэш.

`src/services/comment_campaign_service.py`:
- initialize открывает SQLite и сравнивает UUID с `settings/_id=campaign_inbox:{bot_id}`. `$setOnInsert` создаёт привязку, но не заменяет имеющуюся. Mismatch запрещает polling.
- capture сохраняет relevant channel_post/message перед обычными handlers; drain делает ingest -> ack; note_deleted сохраняет известные удаления; wait -> plan sealing держит SQLite barrier.
- Комментарии, кампании, маршруты, альбомы/посты, применённые удаления, победитель, правила, bank/wallet/rewards/journal, leases уже в MongoDB. SQLite не хранит балансы.
- Конфигурация `src/core/config.py`, `.env.example`: CAMPAIGN_INBOX_PATH; инструкции и persistent-disk требование — docs/COMMENT_CAMPAIGNS.md; bootstrap/shared tests проверяют SQLite barriers/replay/UUID.
- `scripts/migrate_comment_campaigns.py` создаёт Mongo indexes/schema marker, НЕ импортирует SQLite.

По логам известен mismatch, но не известны фактическое содержимое старой очереди и доступность её файла. Указанный путь `/var/data/comment_campaign_inbox.sqlite3` не доказывает наличие постоянного диска. На предоставленном скриншоте Free не поддерживает persistent disks.

## MongoDB-only возможен

Нужны shared durable inbox collections и транзакционный барьер, а не замена put() на insert_one(). Предлагаемые коллекции:
- `campaign_inbox_updates`: unique `(bot_id, update_id)`, исходный payload без переинтерпретации, hash для проверки импорта.
- `campaign_inbox_deletions`: unique `(bot_id, chat_id, message_id)`.
- `campaign_inbox_control`: один документ на bot с **прежним UUID**, backend/schema/migration state и revision/fence.
- `campaign_inbox_migrations`: manifest, source identity/counts/content hashes, progress/checkpoints, verification/activation status. Без TTL на необработанных данных.

Существующий `settings/campaign_inbox:{bot_id}.identity` сохраняется без изменения. Campaign IDs, pinned channel/discussion IDs, enabled_at, routes, rewards, winner, bank/wallet/journal не сбрасываются и не пересоздаются.

Каждый put/ack/deletion и sealing в своей Mongo transaction пишет общий control fence. Sealing в **той же** transaction проверяет обе очереди и меняет campaign phase с текущим lease fence. Snapshot read без общего write fence недостаточен: возможен phantom insert. Для импорта/активации тот же control документ запрещает worker/startup в незавершённом состоянии. UUID/identity берётся из существующей binding, новый не генерируется для старого проекта.

Параллельное чтение/drain требует сериализации либо fenced claims; старый ack не должен удалить повторно принятый deletion после reclaim. Детальный протокол duplicate/retry/claim/generation должен быть реализован и проверен на реальном replica set. В первой версии допустим один poller и один drainer, но безопасность sealing не должна зависеть только от process lock. Автоперезапуск не может переключиться на пустую очередь при ошибке миграции.

### Важная граница гарантий: polling

Сейчас middleware исключение логирует/пробрасывает; main вызывает start_polling без `handle_as_tasks=False`. aiogram может продвинуть offset, пока update обрабатывается в task. Поэтому одно исключение put при недоступной Mongo **не гарантирует** повторную доставку Telegram. Локальная SQLite прежде снижала зависимость ingress от Mongo, но также не делает polling exactly-once.

Mongo-only реализация обязана проверить фактическую версию aiogram и перенести durable admission **до продвижения getUpdates offset**. Просто handle_as_tasks=False недостаточно без проверки, что dispatcher не проглатывает exception и не подтверждает update. Предпочтительно явно контролируемый polling intake: не продвигать offset до majority commit и при ошибке retry/backoff, после durable admission отдавать в обработку. Повторный update дедуплицируется по bot/update. Для mixed batches нельзя подтверждать ещё не сохранённые relevant updates. Поддержать используемые native/widget типы, порядок и существующие handlers без регрессий.

При outage Mongo новые события остаются только у Telegram до успешного commit, с ограниченным сроком хранения; бесконечную недоступность и уже потерянный ephemeral файл восстановить нельзя. Free sleep также не даёт SLA точного завершения через 4 часа.

## Безопасная миграция — только после отдельного согласования

1. Read-only inventory production: фактическая binding/UUID, текущий экземпляр/путь и доступность исходного SQLite, все bot IDs в нём, counts обеих таблиц, integrity check и состояние WAL; Mongo кампании/фазы и текущие pending финансовые записи. Не логировать payload/секреты публично. Отсутствующий файл не открывать через CampaignInbox.open: это создаёт пустой файл.
2. Подготовить read-only dry-run tool. Существующий источник открывать read-only, без mkdir/create/нового UUID. Проверить schema/integrity/identity; получить согласованный snapshot с учётом WAL. Не считать отдельно скопированный живой .sqlite3 полной копией. Источник доступен только там, где он реально сохранился; отсутствие Shell на Free — операционный блокер, а не разрешение очистки binding.
3. Согласовать окно cutover, остановить старые writers/drainers/settlers без удаления экземпляра/источника, сохранить согласованный финальный snapshot. Старые и новые backend не могут одновременно обрабатывать очередь: SQLite и Mongo fences не синхронизируются.
4. Идемпотентный explicit apply импортирует ВСЕ строки updates/deletions/identity, без ingest/payout. Источник остаётся неизменным. Upsert только insert-if-absent; сравнение existing payload hash, конфликт = остановка, не overwrite. Прерванный импорт возобновляется по manifest/checkpoints. Ни очищать источник, ни ack во время импорта.
5. Сверить source/destination keys, payload hashes, counts и tombstones; проверить тот же UUID и Mongo binding. Verification выполняется до начала drain, иначе counts уже несопоставимы. Сохранить manifest результатов. Незавершённый/несовпавший импорт блокирует startup.
6. Отдельно согласовать activation: transaction переключает backend/migration marker, сохраняя identity. Запустить один новый poller/drainer; потом обычный replay через существующие ingest/idempotency и payout fences. Проверить recovery final campaigns без переигрывания winner/наград.
7. Rollback до активации прост: исходник нетронут. После нового ingress в Mongo нельзя просто включить старый SQLite: нужна новая остановка и сверка/обратный перенос delta, иначе потеря событий. Основной путь после активации — forward recovery; backup и manifest сохраняются.
8. После acceptance удалить runtime SQLite, CAMPAIGN_INBOX_PATH и требование Render Disk, переписать runbook/.env/tests. Import reader может временно использовать stdlib sqlite3, только явным migration command; production не открывает локальные очереди. Удаление исходной копии — отдельное разрешение после установленного срока хранения, не часть автоматического cutover.

Если исходная очередь не найдена: не объявлять её пустой и не запускать пустой Mongo inbox с прежним UUID. Инвентаризация Mongo может показать уже принятые комментарии, но не доказать отсутствие утраченных updates. Требуется отдельное явно согласованное решение по невосстановимому хвосту, с фиксацией неизвестного объёма потерь. Без исходника или такого решения безопасная автоматическая миграция невозможна.

## Проверки перед разрешением deployment

- Shared fake/real Mongo tests для existing campaign flow, ingress restart/replay, duplicate updates/deletions, interrupted import/conflict/UUID mismatch, missing source, all-table import and hash checks.
- Реальный replica set: concurrent admission vs empty-check/sealing, two workers, transaction conflicts/retries, cancellation/lease loss, Mongo outage/reconnect, migration activation fence.
- Polling fault injection: outage до commit не продвигает offset; commit+crash before dispatch повторяет без потерь/двойных наград; mixed batch и native/widget handlers.
- Сохранение исходных campaign IDs/rules/winner/rewards/transactions/bank/wallet; отсутствие повторного debit; pending registration/recovery final.
- Startup/readiness блокирует незавершённую миграцию и недоступную Mongo; нет runtime SQLite imports/file creation/path requirement. Full test suite + CI.

Следующий шаг после согласования плана — разработка backend, migration dry-run/apply и тестов в ветке. Production inventory/apply/activation требуют отдельного согласования, не следуют автоматически из согласия на код.
