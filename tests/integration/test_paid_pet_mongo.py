"""Stars receipt settlement on CI disposable Mongo, no real Telegram payments."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.paid_hedgehog_service import PaidHedgehogService
from src.services.hedgehog_service import utc_day


@pytest.mark.asyncio
async def test_paid_receipt_concurrency_and_anchor_preserve_bank_total():
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('CI replica set required')
    client=AsyncIOMotorClient(uri,serverSelectionTimeoutMS=5000)
    name='sensei_paid_test_'+uuid.uuid4().hex
    db=client[name]
    try:
        reward=dict(ordinary_daily=True,total_coins=15,coins=10,bonus_coins=5,total_xp=20,streak=3)
        await db.users.insert_one(dict(id=7,coins=100,xp=50,hedgehog_day=utc_day(),
            hedgehog_result=reward,daily_streak=3,daily_pet=dict(state='active',deadline=1,delivered=True)))
        await db.bank.insert_one(dict(_id='single',coins=1000))
        services=[PaidHedgehogService(NS(database=db)) for _ in range(8)]
        svc=services[0]
        order=await svc.quote(7)
        assert order['stars']==1
        bound=await asyncio.gather(*(s.bind_notice(order['_id'],7,7,90+i) for i,s in enumerate(services)))
        assert (await db.paid_pet_orders.find_one({'_id':order['_id']}))['notice']['message_id']==97
        await svc.checkout(order['_id'],7,1,'q')
        # Durable receipt, then concurrent workers all reconcile the same charge.
        await db.paid_pet_payments.insert_one(dict(_id='charge',user_id=7,order_id=order['_id'],
                                                  stars=1,currency='XTR',state='received'))
        receipts=await asyncio.gather(*(s.settle('charge',7) for s in services))
        assert all(r['state']=='fulfilled' for r in receipts)
        user=await db.users.find_one({'id':7})
        bank=await db.bank.find_one({'_id':'single'})
        assert user['coins']==115 and user['xp']==70 and user['daily_streak']==3
        assert bank['coins']==985 and bank['coins']+user['coins']==1100
        assert await db.transactions.count_documents({'tx_type':'paid_pet_reward'})==1
        assert (await db.paid_pet_days.find_one({'_id':f'7:{utc_day()}'}))['count']==1
    finally:
        await client.drop_database(name)
        client.close()
