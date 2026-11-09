"""Paid-repeat invariants using a rollback-capable transaction fake, not live Mongo."""
import asyncio
import copy
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from src.services.paid_hedgehog_service import PaidHedgehogService, price
from src.services.daily_pet_service import DailyPetService
from src.services.hedgehog_service import GameError, utc_day
from tests.unit.test_hedgehog_game import Collection, services


class TxCollection(Collection):
    async def find_one(self, query, **kwargs):
        return await super().find_one(query)

    async def update_one(self, query, changes, **kwargs):
        result = await self.find_one_and_update(query, changes, **kwargs)
        return NS(matched_count=int(result is not None))


class Session:
    def __init__(self, db): self.db=db
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def with_transaction(self, callback, **kwargs):
        async with self.db.lock:
            backup={name:copy.deepcopy(value.docs) for name,value in vars(self.db).items() if isinstance(value, Collection)}
            try: return await callback(self)
            except Exception:
                for name, docs in backup.items(): getattr(self.db,name).docs=docs
                raise


async def fixture():
    db,daily,_=services()
    for name in ('users','bank','transactions','daily_claims'):
        setattr(db,name,TxCollection(getattr(db,name).docs.values()))
    for name in ('paid_pet_orders','paid_pet_payments','paid_pet_days'):
        setattr(db,name,TxCollection())
    db.lock=asyncio.Lock()
    async def start(): return Session(db)
    async def hello(*args): return dict(setName='rs0',logicalSessionTimeoutMinutes=30)
    db.client=NS(start_session=start);db.command=hello
    mongo=NS(database=db)
    # Recreate daily against replacement collections.
    from src.services.daily_service import DailyService
    daily=DailyService(mongo)
    free=DailyPetService(mongo,daily)
    result,pet=await free.claim(7)
    await free.activate(pet['token'],7,100)
    db.bank.docs['single']={'_id':'single','coins':100000}
    return db,free,PaidHedgehogService(mongo),result


def payment(order, charge='charge1'):
    return NS(invoice_payload='petbuy:'+order['_id'], total_amount=order['stars'],
              currency='XTR', telegram_payment_charge_id=charge)


def test_prices():
    assert [price(i) for i in range(7)]==[1,5,10,20,40,80,160]
    for n in (-1,12,100):
        with pytest.raises(GameError): price(n)


@pytest.mark.asyncio
async def test_paid_rewards_once_no_streak_increase_and_atomic_bank():
    db,free,paid,base=await fixture()
    before=copy.deepcopy(db.users.docs[7]); bank=db.bank.docs['single']['coins']
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        assert order['stars']==1
        await paid.checkout(order['_id'],7,1,'checkout1')
        receipt=await paid.receive(7,payment(order))
        await paid.receive(7,payment(order))
    user=db.users.docs[7]
    assert user['coins']-before['coins']==base['coins']+base['bonus_coins']
    assert user['xp']-before['xp']==base['total_xp']
    assert user['daily_streak']==before['daily_streak']
    assert user['last_daily']==before['last_daily']
    assert bank-db.bank.docs['single']['coins']==receipt['reward']['total_coins']
    assert db.paid_pet_days.docs[f'7:{utc_day()}']['count']==1
    with patch('src.services.daily_pet_service.time.time',return_value=121):
        await free.activate(receipt['pet_token'],7,121)
    with patch('src.services.paid_hedgehog_service.time.time',return_value=125):
        await paid.tap(receipt['pet_token'],7,'tap1')
        await paid.tap(receipt['pet_token'],7,'tap1')
    assert db.users.docs[7]['daily_pet']['taps']==1
    assert bank-db.bank.docs['single']['coins']==db.users.docs[7]['coins']-before['coins']


@pytest.mark.asyncio
async def test_series_of_paid_prices_and_daily_reset():
    db,free,paid,base=await fixture()
    for index,expected in enumerate([1,5,10,20]):
        with patch('src.services.paid_hedgehog_service.time.time',return_value=120+index*20):
            order=await paid.quote(7)
            assert order['stars']==expected
            await paid.checkout(order['_id'],7,expected,f'checkout{index}')
            result=await paid.receive(7,payment(order,f'charge{index}'))
        await free.activate(result['pet_token'],7,120+index*20)
    day='2099-01-02'
    db.users.docs[7]['hedgehog_day']=day
    with patch('src.services.paid_hedgehog_service.utc_day',return_value=day),patch('src.services.paid_hedgehog_service.time.time',return_value=300):
        assert (await paid.quote(7))['stars']==1


@pytest.mark.asyncio
async def test_checkout_owner_amount_day_and_concurrent_charge_guards():
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        for uid,amount in [(8,1),(7,5)]:
            with pytest.raises(GameError): await paid.checkout(order['_id'],uid,amount,'bad')
        await paid.checkout(order['_id'],7,1,'good')
        await paid.checkout(order['_id'],7,1,'good')
        with pytest.raises(GameError): await paid.checkout(order['_id'],7,1,'different')
        first=await paid.receive(7,payment(order))
        second=await paid.receive(7,payment(order,'different-charge'))
        assert first['state']=='fulfilled' and second['state']=='refund_required'
        assert db.paid_pet_days.docs[f'7:{utc_day()}']['count']==1


@pytest.mark.asyncio
async def test_transaction_rolls_back_bank_and_user_on_journal_failure_and_can_resume():
    db,free,paid,base=await fixture()
    user=copy.deepcopy(db.users.docs[7]);bank=db.bank.docs['single']['coins']
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        await paid.checkout(order['_id'],7,1,'checkout')
        with patch.object(db.transactions,'update_one',side_effect=RuntimeError('db down')):
            with pytest.raises(RuntimeError): await paid.receive(7,payment(order))
        assert db.users.docs[7]==user
        assert db.bank.docs['single']['coins']==bank
        assert db.paid_pet_payments.docs['charge1']['state']=='received'
        assert (await paid.pending(7))['state']=='fulfilled'


@pytest.mark.asyncio
async def test_no_invoice_before_free_or_without_transactions_or_during_active_window():
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=105):
        with pytest.raises(GameError): await paid.quote(7)
    async def standalone(*args): return {}
    db.command=standalone
    with pytest.raises(GameError): await paid.quote(7)


@pytest.mark.asyncio
async def test_paid_shared_bank_is_not_overcredited_and_unfunded_payment_refunded():
    db,free,paid,base=await fixture()
    db.users.docs[8]={**copy.deepcopy(db.users.docs[7]),'id':8}
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        first=await paid.quote(7);second=await paid.quote(8)
        await paid.checkout(first['_id'],7,1,'q7');await paid.checkout(second['_id'],8,1,'q8')
        before=sum(db.users.docs[uid]['coins'] for uid in (7,8))
        db.bank.docs['single']['coins']=base['coins']+base['bonus_coins']
        available=db.bank.docs['single']['coins']
        outcomes=await asyncio.gather(paid.receive(7,payment(first,'charge7')),paid.receive(8,payment(second,'charge8')))
    assert sorted(o['state'] for o in outcomes)==['fulfilled','refund_required']
    assert sum(db.users.docs[uid]['coins'] for uid in (7,8))-before==available
    assert db.bank.docs['single']['coins']==0


@pytest.mark.asyncio
async def test_banned_user_or_changed_day_cannot_checkout_and_paid_bank_shortage_refunds():
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        db.users.docs[7]['is_banned']=True
        with pytest.raises(GameError): await paid.checkout(order['_id'],7,1,'q')
        db.users.docs[7]['is_banned']=False
        with patch('src.services.paid_hedgehog_service.utc_day',return_value='2099-02-01'):
            with pytest.raises(GameError): await paid.checkout(order['_id'],7,1,'q')
        await paid.checkout(order['_id'],7,1,'q')
        before=db.users.docs[7]['coins'];db.bank.docs['single']['coins']=0
        result=await paid.receive(7,payment(order))
    assert result['state']=='refund_required'
    assert db.users.docs[7]['coins']==before
    assert not db.paid_pet_days.docs


@pytest.mark.asyncio
async def test_paid_tap_transaction_rolls_back_debit_when_journal_fails():
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7);await paid.checkout(order['_id'],7,1,'q')
        result=await paid.receive(7,payment(order))
    await free.activate(result['pet_token'],7,120)
    before=copy.deepcopy(db.users.docs[7]);bank=db.bank.docs['single']['coins']
    with patch('src.services.paid_hedgehog_service.time.time',return_value=121),patch.object(db.transactions,'update_one',side_effect=RuntimeError('db down')):
        with pytest.raises(RuntimeError): await paid.tap(result['pet_token'],7,'tap-rollback')
    assert db.users.docs[7]==before and db.bank.docs['single']['coins']==bank


@pytest.mark.asyncio
async def test_real_payment_dispatch_and_duplicate_receipt_do_not_reset_or_repay():
    from pathlib import Path
    from unittest.mock import AsyncMock
    from aiogram import Bot, Dispatcher
    from aiogram.types import Update
    from src.bot.handlers.donate import DonationPaymentMiddleware
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        await paid.bind_notice(order['_id'],7,7,91)
    container=NS(paid_hedgehog_service=paid,daily_pet_service=free,
        settings=NS(maintenance_mode=False,BASE_DIR=Path('.')))
    dp=Dispatcher();session=AsyncMock(return_value=True)
    bot=Bot('123456:TEST',session=session)
    dp.update.outer_middleware(DonationPaymentMiddleware(container))
    user=dict(id=7,is_bot=False,first_name='Test')
    pre=Update.model_validate(dict(update_id=1,pre_checkout_query=dict(id='q',**{'from':user},
        currency='XTR',total_amount=1,invoice_payload='petbuy:'+order['_id'])))
    await dp.feed_update(bot,pre)
    assert session.call_args.args[1].ok is True
    before=db.users.docs[7]['coins']
    payment_data=dict(currency='XTR',total_amount=1,invoice_payload='petbuy:'+order['_id'],
        telegram_payment_charge_id='dispatch-charge',provider_payment_charge_id='')
    event=Update.model_validate(dict(update_id=2,message=dict(message_id=1,date=1,
        chat=dict(id=7,type='private'),**{'from':user},successful_payment=payment_data)))
    with patch.object(bot,'me',new=AsyncMock(return_value=NS(username='Senseigame_bot'))):
        await dp.feed_update(bot,event)
        deadline=db.users.docs[7]['daily_pet']['deadline']
        assert deadline is not None and db.users.docs[7]['daily_pet']['delivered']
        await dp.feed_update(bot,event)
    assert db.users.docs[7]['daily_pet']['deadline']==deadline
    assert db.users.docs[7]['coins']-before==base['coins']+base['bonus_coins']
    methods=[call.args[1] for call in session.call_args_list]
    assert sum(m.__api_method__=='editMessageMedia' for m in methods)==1
    assert not any(m.__api_method__ in {'sendPhoto','sendInvoice','sendMessage'} for m in methods)
    await dp.storage.close()


@pytest.mark.asyncio
async def test_paid_pending_delivery_and_active_window_survive_day_rollover():
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7);await paid.checkout(order['_id'],7,1,'q')
        result=await paid.receive(7,payment(order))
    with patch('src.services.paid_hedgehog_service.utc_day',return_value='2099-03-02'):
        assert (await paid.pending(7))['pet_token']==result['pet_token']
        await free.activate(result['pet_token'],7,120)
        await free.mark_delivered(result['pet_token'],7)
        with patch('src.services.paid_hedgehog_service.time.time',return_value=125):
            assert (await paid.pending(7))['pet_token']==result['pet_token']
        with patch('src.services.paid_hedgehog_service.time.time',return_value=140):
            assert await paid.pending(7) is None


@pytest.mark.asyncio
async def test_unfunded_paid_order_returns_stars_without_consuming_price():
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import deliver
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7);await paid.checkout(order['_id'],7,1,'q')
        db.bank.docs['single']['coins']=0
        result=await paid.receive(7,payment(order))
    msg=NS(bot=AsyncMock(),answer=AsyncMock(),from_user=NS(id=7))
    await deliver(msg,NS(paid_hedgehog_service=paid),result)
    msg.bot.refund_star_payment.assert_awaited_once_with(user_id=7,telegram_payment_charge_id='charge1')
    assert db.paid_pet_payments.docs['charge1']['state']=='refunded'
    assert not db.paid_pet_days.docs


@pytest.mark.asyncio
async def test_offer_updates_notice_with_stars_link_using_real_bank_schema():
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import offer
    db,free,paid,base=await fixture()
    # No parallel main.balance bank may be necessary to buy a repeat.
    db.bank.docs.pop('main')
    query=NS(data='petbuy:offer:7',answer=AsyncMock(),from_user=NS(id=7),
        message=NS(chat=NS(id=-100222,type='supergroup'),message_id=91,photo=[],answer=AsyncMock()),
        bot=NS(send_invoice=AsyncMock(),create_invoice_link=AsyncMock(return_value='https://t.me/$invoice'),
               edit_message_text=AsyncMock()))
    container=NS(settings=NS(maintenance_mode=False),paid_hedgehog_service=paid)
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        await offer(query,container)
    query.bot.send_invoice.assert_not_awaited()
    query.bot.edit_message_text.assert_awaited_once()
    assert query.bot.edit_message_text.call_args.kwargs['message_id']==91
    invoice=query.bot.create_invoice_link.call_args.kwargs
    assert invoice['currency']=='XTR' and invoice['prices'][0].amount==1
    query.message.answer.assert_not_awaited()
    assert db.bank.docs['single']['coins']==100000  # quote is not a debit


@pytest.mark.asyncio
async def test_paid_does_not_use_or_refill_legacy_bank():
    db,free,paid,base=await fixture()
    db.bank.docs['single']['coins']=0
    db.bank.docs['main']['balance']=10**9
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        with pytest.raises(GameError,match='недостаточно'): await paid.quote(7)
    assert db.bank.docs['single']['coins']==0
    assert not db.paid_pet_orders.docs


@pytest.mark.asyncio
async def test_payment_edits_one_persisted_notice_and_replay_is_silent():
    from pathlib import Path
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import deliver
    db,free,paid,base=await fixture()
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        order=await paid.quote(7)
        bound=await paid.bind_notice(order['_id'],7,-100222,91)
        # Repeated click from another message cannot redirect the receipt.
        assert (await paid.bind_notice(order['_id'],7,7,999))['notice']==bound['notice']
        await paid.checkout(order['_id'],7,1,'checkout')
        receipt=await paid.receive(7,payment(order))
    bot=NS(me=AsyncMock(return_value=NS(username='bot')),edit_message_media=AsyncMock())
    message=NS(bot=bot,from_user=NS(id=7,first_name='Test'),answer_photo=AsyncMock(),answer=AsyncMock())
    container=NS(paid_hedgehog_service=paid,daily_pet_service=free,settings=NS(BASE_DIR=Path('.')))
    await deliver(message,container,receipt)
    deadline=(await free.owned(receipt['pet_token'],7))['deadline']
    await deliver(message,container,receipt)
    bot.edit_message_media.assert_awaited_once()
    assert bot.edit_message_media.call_args.kwargs['chat_id']==-100222
    assert bot.edit_message_media.call_args.kwargs['message_id']==91
    message.answer_photo.assert_not_awaited()
    message.answer.assert_not_awaited()
    assert (await free.owned(receipt['pet_token'],7))['deadline']==deadline


@pytest.mark.asyncio
async def test_other_user_cannot_open_owned_repeat_button():
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import offer
    q=NS(data='petbuy:offer:7',from_user=NS(id=8),answer=AsyncMock())
    await offer(q,NS())
    assert q.answer.call_args.kwargs['show_alert'] is True


@pytest.mark.asyncio
async def test_precheckout_wrong_currency_is_rejected_without_settlement():
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import pre_checkout
    q=NS(currency='USD',answer=AsyncMock())
    service=NS(checkout=AsyncMock())
    await pre_checkout(q,NS(settings=NS(maintenance_mode=False),paid_hedgehog_service=service))
    assert q.answer.call_args.kwargs['ok'] is False
    service.checkout.assert_not_awaited()


@pytest.mark.asyncio
async def test_invoice_api_failure_edits_existing_message_only():
    from unittest.mock import AsyncMock
    from src.bot.handlers.paid_hedgehog import offer
    db,free,paid,base=await fixture()
    q=NS(data='petbuy:offer:7',from_user=NS(id=7),answer=AsyncMock(),
        message=NS(chat=NS(id=7,type='private'),message_id=91,photo=[],answer=AsyncMock()),
        bot=NS(create_invoice_link=AsyncMock(side_effect=TimeoutError()),edit_message_text=AsyncMock()))
    with patch('src.services.paid_hedgehog_service.time.time',return_value=120):
        await offer(q,NS(settings=NS(maintenance_mode=False),paid_hedgehog_service=paid))
    q.message.answer.assert_not_awaited()
    q.bot.edit_message_text.assert_awaited_once()
    assert q.bot.edit_message_text.call_args.kwargs['message_id']==91
    assert not db.paid_pet_payments.docs
