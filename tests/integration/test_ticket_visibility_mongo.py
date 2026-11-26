"""Ticket issuance, visibility, redemption and legacy burn flags on Mongo."""
import os
import uuid
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from src.domain.tickets import active_ticket_filter
from src.services.economy_service import EconomyService
from src.services.exchange_service import ExchangeService
from src.services.lottery_service import LotteryService
from src.services.user_service import UserService


@pytest.mark.asyncio
async def test_ticket_views_and_redemption_agree_for_legacy_and_new_records():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_ticket_test_' + uuid.uuid4().hex
    db = client[name]
    mongo = NS(database=db)
    try:
        await db.bank.insert_one({'_id': 'single', 'coins': 10000})
        await db.users.insert_one({'id': 7, 'coins': 0, 'xp': 0, 'messages_count': 299})
        await db.tickets.insert_many([
            {'user_id': 7, 'code': 'legacy-no-flags'},
            {'user_id': 7, 'code': 'legacy-is-false', 'is_burned': False},
            {'user_id': 7, 'code': 'spent-burned', 'burned': True},
            {'user_id': 7, 'code': 'spent-legacy', 'burned': False, 'is_burned': True},
            {'user_id': 7, 'amount': 3, 'source': 'quiz'},  # ambiguous legacy aggregate
        ])
        reward = await EconomyService(mongo).process_message_reward(7)
        assert reward['messages_count'] == 300
        earned = await db.tickets.find_one({'code': reward['ticket_created']})
        assert earned and earned['burned'] is False
        assert str(earned['_id']) != earned['code']
        users, lottery = UserService(mongo), LotteryService(mongo)
        assert (await users.get_profile(7))['tickets'] == 3
        assert (await users.get_top_by_tickets())[0]['tickets'] == 3
        assert (await users.get_ticket_holders_paginated())['items'][0]['tickets'] == 3
        assert (await lottery.get_lottery_stats())['total_active_tickets'] == 3
        assert await db.tickets.count_documents(active_ticket_filter(user_id=7)) == 3
        result = await ExchangeService(mongo).ticket_to_coins(7, request_id='legacy-ticket')
        assert result['success']
        assert (await users.get_profile(7))['tickets'] == 2
        burned = await db.tickets.find_one({'code': 'legacy-no-flags'})
        assert burned['burned'] is True and burned['is_burned'] is True
        member = NS(status='member', user=NS(id=7, first_name='Test', last_name='', username='test', is_bot=False))
        winners = await lottery.run_lottery(10, chat_id=-100, bot=NS(get_chat_member=AsyncMock(return_value=member)))
        assert len(winners) == 2
        assert (await users.get_profile(7))['tickets'] == 0
        assert await db.tickets.count_documents({'source': 'quiz'}) == 1
    finally:
        await client.drop_database(name)
        client.close()
