"""Disposable replica-set verification; no live Telegram payment or production DB."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.star_coin_service import StarCoinService


@pytest.mark.asyncio
async def test_concurrent_stars_purchase_conserves_bank_and_one_journal():
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('CI replica set required')
    client=AsyncIOMotorClient(uri,serverSelectionTimeoutMS=5000)
    name='sensei_star_coin_test_'+uuid.uuid4().hex
    db=client[name]
    try:
        await db.users.insert_one(dict(id=7,coins=100,xp=10))
        await db.bank.insert_one(dict(_id='single',coins=50000))
        workers=[StarCoinService(NS(database=db)) for _ in range(8)]
        p=NS(invoice_payload='coinbuy:v1:7:50',total_amount=50,currency='XTR',telegram_payment_charge_id='charge')
        # Intake persisted first, simulating recovery after interruption.
        await db.star_coin_payments.insert_one(dict(_id='charge',user_id=7,stars=50,coins=45000,
            payload=p.invoice_payload,currency='XTR',state='received'))
        results=await asyncio.gather(*(s.receive(7,p) for s in workers))
        assert all(r['state']=='fulfilled' for r in results)
        user=await db.users.find_one({'id':7});bank=await db.bank.find_one({'_id':'single'})
        assert user['coins']==45100 and user['xp']==10 and bank['coins']==5000
        assert user['coins']+bank['coins']==50100
        assert await db.transactions.count_documents({'tx_type':'star_coin_purchase'})==1
        p.telegram_payment_charge_id='second'
        assert (await workers[0].receive(7,p))['state']=='refund_required'
        assert (await db.bank.find_one({'_id':'single'}))['coins']==5000
    finally:
        await client.drop_database(name)
        client.close()
