"""Quiz answer conservation and actual displayed reward."""
import asyncio
import copy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.services.quiz_service import QuizService
from tests.unit.test_hedgehog_game import Collection, services


class Insertable(Collection):
    async def insert_one(self, doc, **kwargs):
        self.docs[doc.get('_id', len(self.docs))] = copy.deepcopy(doc)


def setup():
    db, _, _ = services()
    db.users.docs[8] = {'id': 8, 'coins': 1000}
    db.bank.docs = {'single': {'_id': 'single', 'coins': 40, 'total_emitted': 10000},
                    'main': {'_id': 'main', 'balance': 60}}
    db.quiz_states = Collection([{'_id': 'q', 'chat_id': 11, 'status': 'waiting_answer',
                                  'answer': 'hello', 'current_question_id': 1, 'round': 1}])
    db.quiz_questions = Collection()
    db.tickets = Insertable()
    db.transactions = Insertable()
    return db, QuizService(NS(database=db))


@pytest.mark.asyncio
async def test_one_winner_across_workers_and_bank_accounts():
    db, quiz = setup()
    other = QuizService(quiz.mongo_client)
    results = await asyncio.gather(quiz.check_answer(11, 7, 'A', ' HELLO '),
                                   other.check_answer(11, 8, 'B', 'hello'))
    winners = [x for x in results if x]
    assert len(winners) == 1 and winners[0]['reward'] == 100 and winners[0]['tickets'] == 0
    assert db.users.docs[7]['coins'] + db.users.docs[8]['coins'] == 2100
    assert db.bank.docs['single']['coins'] == db.bank.docs['main']['balance'] == 0
    assert db.bank.docs['single']['total_emitted'] == 10000
    assert len(db.transactions.docs) == 1 and not db.tickets.docs
    assert db.quiz_states.docs['q']['stats']['total_coins'] == 100


@pytest.mark.asyncio
async def test_no_bank_funds_returns_zero_not_promised_coins_or_ticket():
    db, quiz = setup()
    db.bank.docs['main']['balance'] = 0
    result = await quiz.check_answer(11, 7, 'A', 'hello')
    assert result['reward'] == 0 and result['tickets'] == 0 and result['balance'] == 1000
    assert db.users.docs[7]['coins'] == 1000 and db.bank.docs['single']['coins'] == 40
    assert db.quiz_states.docs['q']['status'] == 'answered'
    assert not db.transactions.docs and not db.tickets.docs


@pytest.mark.asyncio
async def test_failed_quiz_journal_rolls_back_bank_user_and_question():
    db, quiz = setup()
    before = copy.deepcopy(db.quiz_states.docs['q'])
    async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
    with patch.object(db.transactions, 'insert_one', side_effect=fail):
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await quiz.check_answer(11, 7, 'A', 'hello')
    assert db.quiz_states.docs['q'] == before and db.users.docs[7]['coins'] == 1000
    assert db.bank.docs['single']['coins'] == 40 and db.bank.docs['main']['balance'] == 60
    assert (await quiz.check_answer(11, 7, 'A', 'hello'))['reward'] == 100
    assert await quiz.check_answer(11, 7, 'A', 'hello') is None


@pytest.mark.asyncio
async def test_quiz_loop_does_not_block_answer_lock():
    db, quiz = setup()
    entered = asyncio.Event()
    release = asyncio.Event()
    async def question(chat_id):
        entered.set()
        await release.wait()
        return None
    quiz.get_next_question = question
    quiz.is_quiz_running = AsyncMock(return_value=True)
    quiz.generate_summary = AsyncMock(return_value='done')
    quiz.stop_quiz = AsyncMock()
    # Skip only loop's initial sleep.
    async def immediate(_): return None
    with patch('src.services.quiz_service.asyncio.sleep', side_effect=immediate):
        loop = asyncio.create_task(quiz.run_quiz_loop(11, NS(send_message=AsyncMock())))
        await asyncio.wait_for(entered.wait(), 1)
        result = await asyncio.wait_for(quiz.check_answer(11, 7, 'A', 'hello'), 1)
        assert result['reward'] == 100
        release.set()
        await asyncio.wait_for(loop, 1)


@pytest.mark.asyncio
async def test_quiz_reply_shows_only_confirmed_reward_and_tickets():
    from src.bot.handlers.quiz import check_quiz_answer
    msg = NS(chat=NS(id=11), from_user=NS(id=7, full_name='Alice'), text='hello', reply=AsyncMock())
    service = NS(check_answer=AsyncMock(return_value={'user_id': 7, 'reward': 0, 'tickets': 0}))
    await check_quiz_answer(msg, NS(), NS(quiz_service=service))
    sent = msg.reply.call_args.args[0]
    assert '+0 монет' in sent and 'билет' not in sent


@pytest.mark.asyncio
async def test_quiz_ticket_awards_are_individual_coded_active_records():
    db, quiz = setup()
    quiz.QUIZ_REWARD = 6000
    db.bank.docs['single']['coins'] = 6000
    result = await quiz.check_answer(11, 7, 'A', 'hello')
    assert result['tickets'] == 2
    rows = list(db.tickets.docs.values())
    assert len(rows) == 2 and len({row['code'] for row in rows}) == 2
    assert all(row['user_id'] == 7 and row['source'] == 'quiz' and
               row['burned'] is False and row['is_burned'] is False for row in rows)
