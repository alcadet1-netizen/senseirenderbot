"""Telegram Stars handlers for Dojo upgrades."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.dojo_upgrades import pre_checkout, successful_payment
from src.services.hedgehog_service import GameError


def query():
    return SimpleNamespace(
        invoice_payload='dojobuy:v1:7:pickaxe:10:' + 'a' * 24,
        from_user=SimpleNamespace(id=7),
        currency='XTR',
        total_amount=10,
        answer=AsyncMock(),
    )


def paid_message(charge='charge-1'):
    return SimpleNamespace(
        successful_payment=SimpleNamespace(
            invoice_payload='dojobuy:v1:7:pickaxe:10:' + 'a' * 24,
            currency='XTR',
            total_amount=10,
            telegram_payment_charge_id=charge,
        ),
        from_user=SimpleNamespace(id=7),
        bot=SimpleNamespace(refund_star_payment=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_checkout_answers_ok_and_reports_game_errors():
    service = SimpleNamespace(checkout=AsyncMock())
    item = query()
    await pre_checkout(item, SimpleNamespace(dojo_upgrade_service=service))
    service.checkout.assert_awaited_once_with(
        item.invoice_payload, 7, 'XTR', 10)
    item.answer.assert_awaited_once_with(ok=True)

    service.checkout.side_effect = GameError('Счёт устарел')
    item = query()
    await pre_checkout(item, SimpleNamespace(dojo_upgrade_service=service))
    item.answer.assert_awaited_once()
    assert item.answer.await_args.kwargs == {
        'ok': False, 'error_message': 'Счёт устарел'}


@pytest.mark.asyncio
async def test_fulfilled_payment_is_acknowledged_and_auto_starts_a_cycle():
    service = SimpleNamespace(
        receive=AsyncMock(return_value={
            '_id': 'charge-1', 'state': 'fulfilled', 'kind': 'auto', 'stars': 1000}))
    miner = SimpleNamespace(auto_step=AsyncMock())
    message = paid_message()
    await successful_payment(
        message, SimpleNamespace(dojo_upgrade_service=service,
                                 dojo_miner_service=miner))
    service.receive.assert_awaited_once()
    miner.auto_step.assert_awaited_once_with(7)
    text = message.answer.await_args.args[0]
    assert '✅' in text and '1000 ⭐' in text


@pytest.mark.asyncio
async def test_refund_required_returns_stars_once():
    service = SimpleNamespace(
        receive=AsyncMock(return_value={
            '_id': 'charge-1', 'state': 'refund_required',
            'kind': 'pickaxe', 'stars': 10}),
        mark_refunded=AsyncMock())
    message = paid_message()
    await successful_payment(
        message, SimpleNamespace(dojo_upgrade_service=service,
                                 dojo_miner_service=SimpleNamespace(auto_step=AsyncMock())))
    message.bot.refund_star_payment.assert_awaited_once_with(
        user_id=7, telegram_payment_charge_id='charge-1')
    service.mark_refunded.assert_awaited_once_with('charge-1')
    assert 'возвращены' in message.answer.await_args.args[0]
