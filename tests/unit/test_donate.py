"""Stars donations: fixed prices, verified receipts, separate idempotent ledger."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandObject
from aiogram.types import Update

from src.bot.handlers.donate import (AMOUNTS, XROCKET_URL, cmd_donate, donate_invoice,
    donation_pre_checkout, donation_received, DonationPaymentMiddleware, cmd_paysupport)
from tests.unit.test_hedgehog_game import Collection


def container():
    # No economy, user or bank service available to donation code.
    return NS(mongo_client=NS(database=NS(donations=Collection())), settings=NS(admin_ids=[99]))


def message(amount=15, charge='charge-unique'):
    return NS(from_user=NS(id=7), chat=NS(id=7,type='private'), answer=AsyncMock(),bot=AsyncMock(),
        successful_payment=NS(invoice_payload=f'donate:7:{amount}',currency='XTR',
                              total_amount=amount,telegram_payment_charge_id=charge))


@pytest.mark.asyncio
async def test_menu_fixed_amounts_and_exact_xrocket_url():
    msg=message()
    await cmd_donate(msg)
    call=msg.answer.call_args
    buttons=call.kwargs['reply_markup'].inline_keyboard
    assert [[b.callback_data for b in row] for row in buttons[:2]] == [['coinbuy:1','coinbuy:5'],['coinbuy:10','coinbuy:50']]
    assert buttons[2][0].url == XROCKET_URL == 'https://t.me/xrocket?start=inv_uBCMaE7YvzGJYwF'
    assert 'SenseiBank' in call.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('amount', AMOUNTS)
async def test_invoice_stars_not_cents(amount):
    q=NS(data=f'donate:{amount}',from_user=NS(id=7),message=message(),answer=AsyncMock(),bot=AsyncMock())
    await donate_invoice(q)
    invoice=q.bot.send_invoice.call_args.kwargs
    assert invoice['currency']=='XTR' and invoice['provider_token']==''
    assert invoice['payload']==f'donate:7:{amount}'
    assert len(invoice['prices'])==1 and invoice['prices'][0].amount==amount


@pytest.mark.asyncio
@pytest.mark.parametrize('value',['donate:0','donate:1','donate:500','donate:-5','donate:5:100','donate:05'])
async def test_forged_callback_cannot_change_price(value):
    q=NS(data=value,message=message(),answer=AsyncMock(),bot=AsyncMock())
    await donate_invoice(q)
    q.bot.send_invoice.assert_not_called()
    assert q.answer.call_args.kwargs['show_alert']


@pytest.mark.asyncio
@pytest.mark.parametrize('amount', AMOUNTS)
async def test_verified_pre_checkout(amount):
    q=NS(invoice_payload=f'donate:7:{amount}',from_user=NS(id=7),currency='XTR',total_amount=amount,answer=AsyncMock())
    await donation_pre_checkout(q)
    q.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [dict(invoice_payload='donate:8:15'),dict(currency='USD'),dict(total_amount=1500),dict(invoice_payload='fake')])
async def test_mismatched_checkout_refused(changes):
    args=dict(invoice_payload='donate:7:15',from_user=NS(id=7),currency='XTR',total_amount=15,answer=AsyncMock())
    args.update(changes)
    q=NS(**args)
    await donation_pre_checkout(q)
    assert q.answer.call_args.kwargs['ok'] is False


@pytest.mark.asyncio
async def test_receipt_idempotent_but_new_charge_is_new_donation():
    c=container();msg=message()
    await donation_received(msg,c)
    await donation_received(msg,c)
    msg.successful_payment.telegram_payment_charge_id='second-charge'
    await donation_received(msg,c)
    records=c.mongo_client.database.donations.docs
    assert len(records)==2 and sum(r['stars'] for r in records.values())==30
    assert all(r['currency']=='XTR' for r in records.values())


@pytest.mark.asyncio
async def test_forged_success_never_recorded_or_thanked():
    c=container();msg=message()
    msg.successful_payment.currency='USD'
    await donation_received(msg,c)
    assert not c.mongo_client.database.donations.docs
    msg.answer.assert_not_called()


@pytest.mark.asyncio
async def test_financial_updates_bypass_game_message_middlewares():
    c=container();dp=Dispatcher();session=AsyncMock(return_value=True)
    bot=Bot('123456:TEST', session=session)
    dp.update.outer_middleware(DonationPaymentMiddleware(c))
    blocking=AsyncMock(side_effect=AssertionError('Must bypass maintenance/activity rewards'))
    dp.message.outer_middleware(blocking)
    payment=dict(currency='XTR',total_amount=15,invoice_payload='donate:7:15',
                 telegram_payment_charge_id='real-dispatch',provider_payment_charge_id='')
    user=dict(id=7,is_bot=False,first_name='Test')
    update=Update.model_validate(dict(update_id=1,message=dict(message_id=1,date=1,chat=dict(id=7,type='private'),
        **{'from':user},successful_payment=payment)))
    await dp.feed_update(bot,update)
    blocking.assert_not_called()
    assert c.mongo_client.database.donations.docs['real-dispatch']['stars']==15
    check=Update.model_validate(dict(update_id=2,pre_checkout_query=dict(id='checkout',**{'from':user},
        currency='XTR',total_amount=15,invoice_payload='donate:7:15')))
    await dp.feed_update(bot,check)
    assert session.call_args.args[1].ok is True
    await dp.storage.close()


@pytest.mark.asyncio
async def test_paysupport_private_delivery_to_admin():
    msg=message();c=container()
    await cmd_paysupport(msg,c,CommandObject(command='paysupport',args='Вопрос о платеже'))
    msg.bot.send_message.assert_awaited_once()
    assert msg.bot.send_message.call_args.args[0]==99
    assert 'передано' in msg.answer.call_args.args[0]
