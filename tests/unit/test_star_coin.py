from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
import asyncio
import pytest

from src.services.star_coin_service import StarCoinService, PACKAGES, PREFIX
from src.services.hedgehog_service import GameError
from tests.unit.test_paid_hedgehog import fixture, TxCollection


async def setup():
    db,free,paid,base = await fixture()
    db.star_coin_payments = TxCollection()
    return db, StarCoinService(NS(database=db))


def payment(stars=5, charge='charge'):
    return NS(invoice_payload=f'{PREFIX}7:{stars}',currency='XTR',total_amount=stars,
              telegram_payment_charge_id=charge)


@pytest.mark.asyncio
@pytest.mark.parametrize('stars,coins', [(1,500),(5,3500),(10,8000),(50,45000)])
async def test_packages_bank_funded_no_xp_and_duplicate_safe(stars,coins):
    db,svc=await setup()
    before=dict(db.users.docs[7]);bank=db.bank.docs['single']['coins']
    await svc.check(7,stars)
    results=await asyncio.gather(*(svc.receive(7,payment(stars)) for _ in range(8)))
    assert all(r['state']=='fulfilled' for r in results)
    assert db.users.docs[7]['coins']==before['coins']+coins
    assert db.users.docs[7]['xp']==before['xp']
    assert db.users.docs[7]['daily_streak']==before['daily_streak']
    assert db.bank.docs['single']['coins']==bank-coins
    assert len([r for r in db.transactions.docs.values() if r.get('tx_type')=='star_coin_purchase'])==1


@pytest.mark.asyncio
async def test_insufficient_bank_rejects_checkout_and_refunds_late_receipt():
    db,svc=await setup()
    db.bank.docs['single']['coins']=499
    with pytest.raises(GameError,match='недостаточно'): await svc.check(7,1)
    before=dict(db.users.docs[7])
    result=await svc.receive(7,payment(1))
    assert result['state']=='refund_required'
    assert db.users.docs[7]==before
    assert db.bank.docs['single']['coins']==499


@pytest.mark.asyncio
async def test_journal_failure_rolls_back_transfer_receipt_survives_for_recovery():
    db,svc=await setup()
    before=dict(db.users.docs[7]);bank=db.bank.docs['single']['coins']
    with patch.object(db.transactions,'update_one',new=AsyncMock(side_effect=RuntimeError())):
        with pytest.raises(RuntimeError): await svc.receive(7,payment())
    assert db.users.docs[7]==before and db.bank.docs['single']['coins']==bank
    assert db.star_coin_payments.docs['charge']['state']=='received'
    assert (await svc.receive(7,payment()))['state']=='fulfilled'
    assert db.users.docs[7]['coins']==before['coins']+3500


@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[dict(currency='USD'),dict(invoice_payload='coinbuy:v1:8:5'),
                                    dict(total_amount=15),dict(invoice_payload='donate:7:5')])
async def test_invalid_receipts_cannot_buy_coins(changes):
    db,svc=await setup()
    p=payment();p.__dict__.update(changes)
    with pytest.raises(GameError): await svc.receive(7,p)
    assert not db.star_coin_payments.docs


@pytest.mark.asyncio
async def test_command_recovers_durable_pending_without_second_payment():
    from src.bot.handlers.donate import cmd_donate
    db,svc=await setup()
    with patch.object(db.transactions,'update_one',new=AsyncMock(side_effect=RuntimeError())):
        with pytest.raises(RuntimeError): await svc.receive(7,payment())
    with pytest.raises(GameError,match='незавершённый'): await svc.check(7,5)
    msg=NS(from_user=NS(id=7),answer=AsyncMock())
    await cmd_donate(msg,NS(mongo_client=NS(database=db)))
    assert db.star_coin_payments.docs['charge']['state']=='fulfilled'
    assert '3,500' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_new_invoice_and_precheckout_validate_package_and_owner():
    from src.bot.handlers.donate import coin_invoice,coin_checkout
    db,svc=await setup();container=NS(mongo_client=NS(database=db))
    q=NS(data='coinbuy:10',from_user=NS(id=7),message=NS(edit_text=AsyncMock(),chat=NS(id=7,type='private')),answer=AsyncMock(),
         bot=NS(create_invoice_link=AsyncMock(return_value='https://t.me/$test')))
    await coin_invoice(q,container)
    invoice=q.bot.create_invoice_link.call_args.kwargs
    assert invoice['payload']=='coinbuy:v1:7:10' and invoice['currency']=='XTR'
    assert invoice['prices'][0].amount==10
    assert not db.star_coin_payments.docs
    q=NS(invoice_payload=invoice['payload'],from_user=NS(id=8),currency='XTR',total_amount=10,answer=AsyncMock())
    await coin_checkout(q,container)
    assert q.answer.call_args.kwargs['ok'] is False
    q.from_user.id=7;q.answer.reset_mock()
    await coin_checkout(q,container)
    q.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_real_payment_dispatch_transfers_once():
    from aiogram import Bot, Dispatcher
    from aiogram.types import Update
    from src.bot.handlers.donate import DonationPaymentMiddleware
    db,svc=await setup();before=db.users.docs[7]['coins']
    dp=Dispatcher();session=AsyncMock(return_value=True);bot=Bot('123456:TEST',session=session)
    dp.update.outer_middleware(DonationPaymentMiddleware(NS(mongo_client=NS(database=db))))
    user=dict(id=7,is_bot=False,first_name='Test')
    event=Update.model_validate(dict(update_id=1,message=dict(message_id=1,date=1,
        chat=dict(id=7,type='private'),**{'from':user},successful_payment=dict(currency='XTR',
        total_amount=50,invoice_payload='coinbuy:v1:7:50',telegram_payment_charge_id='dispatch',provider_payment_charge_id=''))))
    await dp.feed_update(bot,event);await dp.feed_update(bot,event)
    assert db.users.docs[7]['coins']==before+45000
    await dp.storage.close()


@pytest.mark.asyncio
async def test_group_purchase_does_not_edit_shared_menu_or_redirect_payer():
    from src.bot.handlers.donate import coin_invoice
    db,svc=await setup();container=NS(mongo_client=NS(database=db))
    before=db.bank.docs['single']['coins']
    message=NS(chat=NS(id=-100222,type='supergroup'),message_thread_id=33,
               edit_text=AsyncMock(),answer=AsyncMock())
    bot=NS(create_invoice_link=AsyncMock(return_value='https://t.me/$test'),send_message=AsyncMock())
    for uid in (7,8):
        if uid==8: db.users.docs[8]={'id':8,'coins':0}
        q=NS(data='coinbuy:50',from_user=NS(id=uid,first_name='Buyer'),message=message,answer=AsyncMock(),bot=bot)
        await coin_invoice(q,container)
    message.edit_text.assert_not_awaited()
    assert bot.send_message.await_count==2
    assert [c.kwargs['payload'] for c in bot.create_invoice_link.call_args_list]==[
        'coinbuy:v1:7:50','coinbuy:v1:8:50']
    assert bot.send_message.call_args.kwargs['message_thread_id']==33
    assert bot.send_message.call_args.kwargs['chat_id']==-100222
    assert db.bank.docs['single']['coins']==before
    assert not db.star_coin_payments.docs


@pytest.mark.asyncio
async def test_definitive_private_edit_failure_publishes_same_invoice_once():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import EditMessageText
    from src.bot.handlers.donate import coin_invoice
    db,svc=await setup();container=NS(mongo_client=NS(database=db))
    error=TelegramBadRequest(method=EditMessageText(text='x',chat_id=7,message_id=1),
        message="Bad Request: message can't be edited")
    q=NS(data='coinbuy:5',from_user=NS(id=7),answer=AsyncMock(),
        message=NS(chat=NS(id=7,type='private'),edit_text=AsyncMock(side_effect=error)),
        bot=NS(create_invoice_link=AsyncMock(return_value='https://t.me/$same'),send_message=AsyncMock()))
    await coin_invoice(q,container)
    q.bot.create_invoice_link.assert_awaited_once()
    q.bot.send_message.assert_awaited_once()
    assert q.bot.send_message.call_args.kwargs['reply_markup'].inline_keyboard[0][0].url=='https://t.me/$same'


@pytest.mark.asyncio
async def test_invoice_api_rejection_has_stage_and_user_feedback(caplog):
    import logging
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import CreateInvoiceLink
    from src.bot.handlers.donate import coin_invoice
    db,svc=await setup();container=NS(mongo_client=NS(database=db))
    error=TelegramBadRequest(method=CreateInvoiceLink(title='x',description='x',payload='x',currency='XTR',prices=[]),
                            message='Bad Request: PAYMENT_PROVIDER_INVALID https://secret.test/token')
    q=NS(data='coinbuy:50',from_user=NS(id=7),answer=AsyncMock(),
        message=NS(chat=NS(id=7,type='private'),edit_text=AsyncMock(),answer=AsyncMock()),
        bot=NS(create_invoice_link=AsyncMock(side_effect=error),send_message=AsyncMock()))
    with caplog.at_level(logging.WARNING): await coin_invoice(q,container)
    assert 'stage=create_invoice_link' in caplog.text
    assert 'PAYMENT_PROVIDER_INVALID' in caplog.text
    assert 'https://secret.test/token' not in caplog.text
    q.message.answer.assert_awaited_once()
    q.message.edit_text.assert_not_awaited();q.bot.send_message.assert_not_awaited()
    assert not db.star_coin_payments.docs


@pytest.mark.asyncio
async def test_ambiguous_publish_is_not_retried_or_new_invoice_created():
    from src.bot.handlers.donate import coin_invoice
    db,svc=await setup()
    q=NS(data='coinbuy:1',from_user=NS(id=7,first_name='Buyer'),answer=AsyncMock(),
         message=NS(chat=NS(id=-100222,type='supergroup'),message_thread_id=None,answer=AsyncMock()),
         bot=NS(create_invoice_link=AsyncMock(return_value='https://t.me/$once'),send_message=AsyncMock(side_effect=TimeoutError())))
    await coin_invoice(q,NS(mongo_client=NS(database=db)))
    q.bot.create_invoice_link.assert_awaited_once();q.bot.send_message.assert_awaited_once()
    q.message.answer.assert_awaited_once()
    assert not db.star_coin_payments.docs
