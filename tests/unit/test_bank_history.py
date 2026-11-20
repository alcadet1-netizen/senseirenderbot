from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot.handlers import admin_commands
from src.services.bank_history import TYPES, format_bank_history, read_bank_history

NOW = datetime(2026, 1, 31, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_history_reads_only_allowlisted_aggregates_with_timeout():
    rows = [{'_id': 'burn', 'count': 2, 'amount': -15, 'invalid': 0}]
    collection = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=rows))))
    since, now, actual = await read_bank_history(NS(transactions=collection), now=NOW)
    assert since == NOW - timedelta(days=30) and now == NOW and actual == rows
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]['$match']['tx_type']['$in'] == list(TYPES)
    assert pipeline[0]['$match']['created_at'] == {'$gte': since, '$lt': now}
    assert collection.aggregate.call_args.kwargs['maxTimeMS'] == 10000
    assert len(pipeline) == 2 and '$group' in pipeline[1]
    text = format_bank_history(since, now, rows + [{'_id': 'private-secret', 'count': 1, 'amount': 3}])
    assert 'burn: 2' in text and '-15' in text and 'private-secret' not in text
    assert 'неполным' in text and 'не остаток банка' in text


@pytest.mark.asyncio
async def test_command_private_admin_only_error_and_shared_cooldown(monkeypatch):
    monkeypatch.setattr(admin_commands, '_bank_diagnostic_last', float('-inf'))
    read = AsyncMock(side_effect=RuntimeError('sensitive connection'))
    monkeypatch.setattr('src.services.bank_history.read_bank_history', read)
    msg = NS(from_user=NS(id=2), chat=NS(type='private'), answer=AsyncMock())
    container = NS(settings=NS(admin_ids=[1]), mongo_client=NS(database=object()))
    await admin_commands.cmd_bank_history(msg, container)
    msg.answer.assert_not_awaited()
    msg.from_user.id = 1
    msg.chat.type = 'group'
    await admin_commands.cmd_bank_history(msg, container)
    assert 'личном' in msg.answer.await_args.args[0]
    read.assert_not_awaited()
    msg.chat.type = 'private'
    await admin_commands.cmd_bank_history(msg, container)
    assert 'неизвестны' in msg.answer.await_args.args[0]
    assert 'sensitive connection' not in msg.answer.await_args.args[0]
    await admin_commands.cmd_bank_diagnose(msg, container)
    assert 'через минуту' in msg.answer.await_args.args[0]
    assert read.await_count == 1
