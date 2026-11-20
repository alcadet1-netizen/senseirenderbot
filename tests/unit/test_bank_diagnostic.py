from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot.handlers import admin_commands
from src.services.bank_diagnostic import read_bank_diagnostic, format_bank_diagnostic


@pytest.mark.asyncio
async def test_diagnostic_uses_one_snapshot_and_only_aggregate_reads():
    session = object()
    context = NS(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=False))
    class SessionContext:
        async def __aenter__(self): return await context.__aenter__()
        async def __aexit__(self, *args): return await context.__aexit__(*args)
    bank = NS(find_one=AsyncMock(side_effect=[{'coins': 75, 'total_emitted': 120, 'burned': 0}, None]))
    users = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[{'count': 2, 'numeric_sum': 25, 'negative_count': 0, 'non_numeric_count': 0}]))))
    escrows = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[{'bets': 10, 'invalid': 0}]))))
    client = NS(start_session=AsyncMock(return_value=SessionContext()))
    report = await read_bank_diagnostic(NS(client=client, bank=bank, users=users, duel_escrows=escrows))
    client.start_session.assert_awaited_once_with(snapshot=True)
    assert all(call.kwargs['session'] is session for call in bank.find_one.await_args_list)
    for collection in (users, escrows):
        assert collection.aggregate.call_args.kwargs['session'] is session
        assert collection.aggregate.call_args.kwargs['maxTimeMS'] == 10000
    assert report['calculated']['ui_total_supply'] == '120'
    assert report['calculated']['emission_minus_ui_total_supply'] == '0'
    assert 'только чтение' in format_bank_diagnostic(report)


@pytest.mark.asyncio
async def test_command_private_admin_only_and_safe_failure(monkeypatch):
    monkeypatch.setattr(admin_commands, '_bank_diagnostic_last', float('-inf'))
    read = AsyncMock(side_effect=RuntimeError('private connection string'))
    monkeypatch.setattr('src.services.bank_diagnostic.read_bank_diagnostic', read)
    message = NS(from_user=NS(id=2), chat=NS(type='private'), answer=AsyncMock())
    container = NS(settings=NS(admin_ids=[1]), mongo_client=NS(database=object()))
    await admin_commands.cmd_bank_diagnose(message, container)
    message.answer.assert_not_awaited()
    read.assert_not_awaited()
    message.from_user.id = 1
    message.chat.type = 'group'
    await admin_commands.cmd_bank_diagnose(message, container)
    assert 'личном' in message.answer.await_args.args[0]
    read.assert_not_awaited()
    message.chat.type = 'private'
    await admin_commands.cmd_bank_diagnose(message, container)
    assert 'неизвестны' in message.answer.await_args.args[0]
    assert 'private connection string' not in message.answer.await_args.args[0]
    await admin_commands.cmd_bank_diagnose(message, container)
    assert 'через минуту' in message.answer.await_args.args[0]
    assert read.await_count == 1


@pytest.mark.asyncio
async def test_corrected_limit_reserve_is_visible_and_incomplete_is_unknown():
    class Context:
        async def __aenter__(self): return object()
        async def __aexit__(self, *args): pass
    client = NS(start_session=AsyncMock(return_value=Context()))
    bank_doc = {'coins': 75, 'total_emitted': 100, 'burned': 5,
                'emission_correction_reserve': 20, 'emission_correction_applied': True,
                'emission_correction_id': 'counter-baseline-v1'}
    bank = NS(find_one=AsyncMock(side_effect=[bank_doc, None]))
    empty = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[]))))
    db = NS(client=client, bank=bank, users=empty, duel_escrows=empty)
    report = await read_bank_diagnostic(db)
    assert report['limit_reserve'] == '20'
    assert 'Служебный резерв лимита (не Coin): 20' in format_bank_diagnostic(report)
    del bank_doc['emission_correction_id']
    bank.find_one.side_effect = [bank_doc, None]
    report = await read_bank_diagnostic(db)
    assert report['limit_reserve'] is None


@pytest.mark.asyncio
async def test_preview_uses_snapshot_and_never_writes():
    class Context:
        async def __aenter__(self): return object()
        async def __aexit__(self, *args): pass
    client = NS(start_session=AsyncMock(return_value=Context()))
    bank = NS(find_one=AsyncMock(side_effect=[{'coins': 75, 'total_emitted': 120, 'burned': 5}, {'balance': 0}]), update_one=AsyncMock())
    users = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[{'count': 1, 'numeric_sum': 25, 'negative_count': 0, 'non_numeric_count': 0}]))))
    escrows = NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[]))))
    db = NS(client=client, bank=bank, users=users, duel_escrows=escrows)
    report = await read_bank_diagnostic(db, expected_difference='20')
    from src.services.bank_diagnostic import format_correction_preview
    assert report['correction_plan']['current_after'] == '100.00'
    assert 'Деньги и счётчики не изменены' in format_correction_preview(report)
    bank.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_command_access_and_error(monkeypatch):
    monkeypatch.setattr(admin_commands, '_bank_diagnostic_last', float('-inf'))
    read = AsyncMock(side_effect=RuntimeError('secret'))
    monkeypatch.setattr('src.services.bank_diagnostic.read_bank_diagnostic', read)
    message = NS(from_user=NS(id=2), chat=NS(type='private'), text='/coinpreview 20', answer=AsyncMock())
    container = NS(settings=NS(admin_ids=[1]), mongo_client=NS(database=object()))
    await admin_commands.cmd_coin_preview(message, container)
    read.assert_not_awaited()
    message.from_user.id = 1
    message.chat.type = 'group'
    await admin_commands.cmd_coin_preview(message, container)
    read.assert_not_awaited()
    message.chat.type = 'private'
    await admin_commands.cmd_coin_preview(message, container)
    assert 'ничего не изменено' in message.answer.await_args.args[0]
    assert 'secret' not in message.answer.await_args.args[0]
    await admin_commands.cmd_coin_preview(message, container)
    assert 'через минуту' in message.answer.await_args.args[0]
    assert read.await_count == 1
