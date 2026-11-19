"""Bounded, read-only view of old player-funded duel reservations."""
from datetime import datetime, timedelta, timezone

LIMIT = 10
MIN_AGE = timedelta(hours=1)


async def read_old_reservations(db, *, now=None):
    now = now or datetime.now(timezone.utc)
    cursor = db.duel_escrows.find(
        {'state': 'reserved', 'created_at': {'$lt': now - MIN_AGE}},
        {'_id': 1, 'challenger_id': 1, 'opponent_id': 1, 'bet': 1, 'created_at': 1},
    ).max_time_ms(2500).limit(LIMIT + 1)
    docs = await cursor.to_list(length=LIMIT + 1)
    return docs[:LIMIT], len(docs) > LIMIT


def _safe(value, limit=80):
    return ' '.join(str(value).split())[:limit]


def format_old_reservations(docs, more):
    lines = [
        '🛡 Дуэли · только просмотр',
        'Показаны резервы старше 1 часа, не более 10; порядок не гарантирован.',
        'Это не доказательство зависания: бой может ещё работать в другом процессе.',
    ]
    if not docs:
        lines.append('Записей с указанной датой не найдено. Записи без даты в выборку не попадают.')
    for doc in docs:
        created = doc.get('created_at')
        date = created.isoformat(sep=' ', timespec='seconds') if isinstance(created, datetime) else 'неизвестно'
        lines.append(f"ID: {_safe(doc.get('_id', '?'))}\n"
                     f"Игроки: {_safe(doc.get('challenger_id', '?'), 24)} / {_safe(doc.get('opponent_id', '?'), 24)}\n"
                     f"Ставка каждого: {_safe(doc.get('bet', '?'), 24)} Coin · дата: {date} UTC")
    if more:
        lines.append('Есть ещё записи; это не полный список.')
    lines.append('Автоматический возврат не выполняется. Нельзя возвращать ставку, пока другой процесс может вести бой.')
    return '\n\n'.join(lines)
