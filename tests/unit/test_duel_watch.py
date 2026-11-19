from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.duel_watch import LIMIT, read_old_reservations, format_old_reservations
from src.bot.handlers.admin_commands import cmd_duel_watch


@pytest.mark.asyncio
async def test_read_is_bounded_and_read_only():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    docs = [{'_id': str(n)} for n in range(LIMIT + 1)]
    cursor = NS(max_time_ms=Mock(), limit=Mock(), to_list=AsyncMock(return_value=docs))
    cursor.max_time_ms.return_value = cursor
    cursor.limit.return_value = cursor
    collection = NS(find=Mock(return_value=cursor))
    result, more = await read_old_reservations(NS(duel_escrows=collection), now=now)
    assert len(result) == LIMIT and more
    collection.find.assert_called_once_with(
        {'state': 'reserved', 'created_at': {'$lt': now - timedelta(hours=1)}},
        {'_id': 1, 'challenger_id': 1, 'opponent_id': 1, 'bet': 1, 'created_at': 1})
    cursor.max_time_ms.assert_called_once_with(2500)
    cursor.limit.assert_called_once_with(LIMIT + 1)
    cursor.to_list.assert_awaited_once_with(length=LIMIT + 1)


def test_output_is_bounded_safe_and_does_not_claim_stuck():
    text = format_old_reservations([{'_id': 'x\n' * 100, 'bet': 300}], True)
    assert 'это не полный список' in text.lower()
    assert 'не доказательство зависания' in text.lower()
    assert 'x\nx' not in text and len(text) < 1000
    assert 'без даты' in format_old_reservations([], False)


@pytest.mark.asyncio
async def test_admin_only_private_and_database_failure_is_unknown():
    db = NS(duel_escrows=NS(find=Mock(side_effect=OSError('offline'))))
    container = NS(settings=NS(admin_ids=[1]), mongo_client=NS(database=db))
    message = NS(from_user=NS(id=2), chat=NS(type='private'), answer=AsyncMock())
    await cmd_duel_watch(message, container)
    message.answer.assert_not_awaited()
    db.duel_escrows.find.assert_not_called()
    message.from_user.id = 1
    message.chat.type = 'supergroup'
    await cmd_duel_watch(message, container)
    assert 'личном' in message.answer.await_args.args[0]
    db.duel_escrows.find.assert_not_called()
    message.chat.type = 'private'
    await cmd_duel_watch(message, container)
    assert 'неизвестно' in message.answer.await_args.args[0]
