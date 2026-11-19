"""Real replica-set quiz payout, contention and rollback tests."""
import asyncio
import os
import uuid
from types import SimpleNamespace as NS

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.quiz_service import QuizService


@pytest.mark.asyncio
async def test_quiz_one_winner_funded_and_rollback():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_quiz_' + uuid.uuid4().hex
    db = client[name]
    try:
        await db.users.insert_many([{'id': uid, 'coins': 1000} for uid in (7, 8)])
        await db.bank.insert_many([{'_id': 'single', 'coins': 40, 'total_emitted': 10000},
                                   {'_id': 'main', 'balance': 60}])
        await db.quiz_states.insert_one({'chat_id': 11, 'status': 'waiting_answer',
                                         'answer': 'hello', 'current_question_id': 1, 'round': 1})
        workers = [QuizService(NS(database=db)) for _ in range(8)]
        results = await asyncio.gather(*(w.check_answer(11, 7 + i % 2, str(i), 'hello')
                                         for i, w in enumerate(workers)))
        winning = [r for r in results if r is not None]
        assert len(winning) == 1 and winning[0]['reward'] == 100 and winning[0]['tickets'] == 0
        users = await db.users.find({}).to_list(length=None)
        assert sum(u['coins'] for u in users) == 2100
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 0
        assert (await db.bank.find_one({'_id': 'main'}))['balance'] == 0
        assert (await db.bank.find_one({'_id': 'single'}))['total_emitted'] == 10000
        assert await db.transactions.count_documents({'type': 'quiz_win'}) == 1
        assert (await db.quiz_states.find_one({'chat_id': 11}))['stats']['total_questions'] == 1
        assert await db.tickets.count_documents({}) == 0
        # Fail after bank and player writes; all changes, including state, abort.
        await db.quiz_states.update_one({'chat_id': 11}, {'$set': {
            'status': 'waiting_answer', 'current_question_id': 2, 'round': 2}})
        await db.bank.update_one({'_id': 'single'}, {'$set': {'coins': 100}})
        before_user = await db.users.find_one({'id': 7})
        before_state = await db.quiz_states.find_one({'chat_id': 11})
        broken = QuizService(NS(database=db))
        async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
        broken.transactions = NS(insert_one=fail)
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await broken.check_answer(11, 7, 'A', 'hello')
        assert await db.users.find_one({'id': 7}) == before_user
        assert await db.quiz_states.find_one({'chat_id': 11}) == before_state
        assert (await db.bank.find_one({'_id': 'single'}))['coins'] == 100
        assert (await workers[0].check_answer(11, 7, 'A', 'hello'))['reward'] == 100
        assert await db.transactions.count_documents({'type': 'quiz_win'}) == 2
        # An empty bank still marks the answer but must never claim a payout.
        await db.quiz_states.update_one({'chat_id': 11}, {'$set': {
            'status': 'waiting_answer', 'current_question_id': 3, 'round': 3}})
        no_money = await workers[0].check_answer(11, 8, 'B', 'hello')
        assert no_money['reward'] == 0 and no_money['tickets'] == 0
        assert await db.transactions.count_documents({'type': 'quiz_win'}) == 2
    finally:
        await client.drop_database(name)
        client.close()
