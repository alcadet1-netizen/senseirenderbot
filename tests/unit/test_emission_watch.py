import asyncio
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from bson.decimal128 import Decimal128

from src.services.emission_watch import EmissionWatch, assess, format_report, read_report

CAP = 10_000_000_000


@pytest.mark.parametrize('doc,status', [
    ({'total_emitted': 900, 'burned': 100, 'emission_cap': CAP}, 'observing'),
    ({'total_emitted': CAP - 100, 'burned': 100, 'emission_cap': CAP}, 'limit_reached'),
    ({'total_emitted': CAP - 50, 'burned': 100, 'emission_cap': CAP}, 'over_estimate'),
    ({'total_emitted': CAP + 1, 'burned': 0, 'emission_cap': CAP}, 'over_estimate'),
    ({'total_emitted': CAP, 'burned': 0, 'emission_cap': CAP}, 'limit_reached'),
    ({'total_emitted': 0, 'emission_cap': CAP}, 'unknown'),
    ({'total_emitted': None, 'burned': 0}, 'unknown'),
    ({'total_emitted': True, 'burned': 0}, 'unknown'),
    ({'total_emitted': -1, 'burned': 0}, 'unknown'),
    ({'total_emitted': float('nan'), 'burned': 0}, 'unknown'),
    ({'total_emitted': 1, 'burned': 0, 'emission_cap': 1}, 'unknown'),
    ({'total_emitted': 1, 'burned': 0, 'emission_cap': 'invalid'}, 'unknown'),
    (None, 'unknown'),
])
def test_classification_does_not_invent_missing_history(doc, status):
    assert assess(doc)['status'] == status


def test_decimal_values_and_disclaimer():
    result = assess({'total_emitted': Decimal128('900.25'), 'burned': Decimal128('1.50')})
    assert result['estimate'] == Decimal('901.75')
    text = format_report(result)
    assert '901.75 Coin' in text
    assert 'оценка' in text and 'не блокирует' in text
    assert 'сжигание не освобождает лимит' in text


@pytest.mark.asyncio
async def test_report_one_projected_read_never_writes():
    bank = NS(find_one=AsyncMock(return_value={'total_emitted': 900, 'burned': 100}))
    result = await read_report(NS(bank=bank))
    assert result['estimate'] == Decimal(1000)
    bank.find_one.assert_awaited_once_with({'_id': 'single'}, {'total_emitted': 1, 'burned': 1, 'emission_cap': 1})
    assert set(vars(bank)) == {'find_one'}


@pytest.mark.asyncio
async def test_alerts_rate_limited_per_admin_and_recovery():
    time = [0]
    bank = NS(find_one=AsyncMock(return_value={'total_emitted': CAP - 100, 'burned': 100}))
    bot = NS(send_message=AsyncMock())
    watch = EmissionWatch(NS(bank=bank), bot, [1, 2, 2], cooldown=100, clock=lambda: time[0])
    assert await watch.tick() == 'limit_reached'
    assert bot.send_message.await_count == 2
    await watch.tick()
    assert bot.send_message.await_count == 2
    time[0] = 101
    await watch.tick()
    assert bot.send_message.await_count == 4
    bank.find_one.return_value = {'total_emitted': 900, 'burned': 100}
    await watch.tick()
    assert bot.send_message.await_count == 6
    await watch.tick()
    assert bot.send_message.await_count == 6
    assert all(call.kwargs['parse_mode'] is None for call in bot.send_message.await_args_list)


@pytest.mark.asyncio
async def test_failed_read_and_failed_telegram_do_not_look_healthy_or_spam():
    time = [0]
    bank = NS(find_one=AsyncMock(side_effect=RuntimeError('sensitive data')))
    bot = NS(send_message=AsyncMock(side_effect=RuntimeError('blocked')))
    watch = EmissionWatch(NS(bank=bank), bot, [1], cooldown=100, clock=lambda: time[0])
    assert await watch.tick() == 'read_error'
    assert 'неизвестен' in bot.send_message.await_args.args[1]
    assert 'sensitive data' not in bot.send_message.await_args.args[1]
    await watch.tick()
    assert bot.send_message.await_count == 1
    # A message that never arrived must not generate a misleading recovery.
    bank.find_one.side_effect = None
    bank.find_one.return_value = {'total_emitted': 10, 'burned': 0}
    bot.send_message.side_effect = None
    await watch.tick()
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_run_cancels_cleanly():
    bank = NS(find_one=AsyncMock(return_value={'total_emitted': 0, 'burned': 0}))
    watch = EmissionWatch(NS(bank=bank), NS(send_message=AsyncMock()), [], interval=3600)
    task = asyncio.create_task(watch.run())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_admin_command_requires_admin_and_private_chat():
    from src.bot.handlers.admin_commands import cmd_emission_watch
    bank = NS(find_one=AsyncMock(return_value={'total_emitted': 100, 'burned': 10}))
    container = NS(settings=NS(admin_ids=[1]), mongo_client=NS(database=NS(bank=bank)))
    message = NS(from_user=NS(id=2), chat=NS(type='private'), answer=AsyncMock())
    await cmd_emission_watch(message, container)
    message.answer.assert_not_awaited()
    bank.find_one.assert_not_awaited()
    message.from_user.id = 1
    message.chat.type = 'supergroup'
    await cmd_emission_watch(message, container)
    assert 'личном чате' in message.answer.await_args.args[0]
    bank.find_one.assert_not_awaited()
    message.chat.type = 'private'
    await cmd_emission_watch(message, container)
    assert 'Страж эмиссии' in message.answer.await_args.args[0]
    bank.find_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_disabled_with_no_admins_does_not_read_database():
    bank = NS(find_one=AsyncMock())
    watch = EmissionWatch(NS(bank=bank), NS(send_message=AsyncMock()), [])
    assert await watch.tick() == 'disabled'
    bank.find_one.assert_not_awaited()
