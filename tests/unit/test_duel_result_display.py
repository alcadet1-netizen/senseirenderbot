"""Final arena must show the persisted result, not guess it from hits."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.services.duel_service import Duel, DuelService
from tests.unit.test_duel_escrow import setup


def make_service():
    db, _ = setup()
    container = NS(mongo_client=NS(database=db), user_service=NS(), economy_service=NS())
    service = DuelService(container)
    service._archive_duel = AsyncMock()
    bot = NS(send_message=AsyncMock(return_value=NS(message_id=1)), edit_message_text=AsyncMock())
    return db, service, container, bot


@pytest.mark.asyncio
@pytest.mark.parametrize('hits', [(2, 0), (1, 1)])
async def test_surrender_winner_matches_actual_payout_even_if_score_disagrees(hits):
    db, service, container, bot = make_service()
    await service.escrow.reserve('id', 7, 8, 300, 123)
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=300, chat_id=-100,
                bot=bot, container=container, escrow_id='id', challenger_name='Alice', opponent_name='Bob')
    duel.hits = {7: hits[0], 8: hits[1]}
    await service._finish_duel(duel, 8, 'Игрок сдался')
    text = bot.send_message.call_args.args[1]
    assert 'Победитель: @Bob' in text and 'Победитель: @Alice' not in text
    assert '+600 монет' in text and '+50 XP' in text
    assert bot.send_message.call_args.kwargs['reply_markup'] is None
    assert db.users.docs[8]['coins'] == 1300 and db.users.docs[7]['coins'] == 700
    await service._update_arena(duel)
    text = bot.edit_message_text.call_args.kwargs['text']
    assert 'Победитель: @Bob' in text and 'Победитель: @Alice' not in text
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_legacy_payout_does_not_claim_unconfirmed_xp():
    db, service, container, bot = make_service()
    await service.escrow.reserve('legacy', 7, 8, 300, 123)
    db.duel_escrows.docs['legacy'].pop('award_version')
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=300, chat_id=-100,
                bot=bot, container=container, escrow_id='legacy', challenger_name='Alice', opponent_name='Bob')
    await service._finish_duel(duel, 7, 'Победа')
    text = bot.send_message.call_args.args[1]
    assert '+600 монет' in text and 'XP не подтверждено' in text
    assert '+50 XP' not in text
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_names_and_chronicle_are_escaped_in_arena_html():
    _, service, container, bot = make_service()
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=0, chat_id=-100,
                bot=bot, container=container, challenger_name='<Alice>', opponent_name='Bob & Co')
    duel.log_lines = ['<b>Раунд</b>']
    await service._update_arena(duel)
    text = bot.send_message.call_args.args[1]
    assert '&lt;Alice&gt;' in text and 'Bob &amp; Co' in text
    assert '&lt;b&gt;Раунд&lt;/b&gt;' in text


@pytest.mark.asyncio
async def test_zero_bet_xp_write_failure_not_displayed_as_granted():
    db, service, container, bot = make_service()
    db.users.update_one = AsyncMock(side_effect=RuntimeError('database unavailable'))
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=0, chat_id=-100,
                bot=bot, container=container, challenger_name='Alice', opponent_name='Bob')
    await service._finish_duel(duel, 7, 'Победа')
    text = bot.send_message.call_args.args[1]
    assert 'Победитель: @Alice' in text
    assert 'XP не подтверждено' in text and '+50 XP' not in text
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_forbidden_private_message_during_move_does_not_deadlock():
    from aiogram.exceptions import TelegramForbiddenError
    db, service, container, bot = make_service()
    bot.send_message = AsyncMock(side_effect=TelegramForbiddenError(method='sendMessage', message='blocked'))
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=0, chat_id=-100,
                bot=bot, container=container, challenger_name='Alice', opponent_name='Bob')
    duel.accepted = True
    service.duels[123] = duel
    finished = asyncio.Event()
    async def finish(d, winner, reason):
        d.finished = True
        assert winner == 8
        finished.set()
    service._finish_duel = AsyncMock(side_effect=finish)
    assert await asyncio.wait_for(service.process_move(123, 7, 'hit_l'), 1) == 'Принято.'
    await asyncio.wait_for(finished.wait(), 1)
    assert duel.finished


@pytest.mark.asyncio
async def test_failed_settlement_freezes_moves_and_retries_same_winner():
    from unittest.mock import patch
    db, service, container, bot = make_service()
    await service.escrow.reserve('id', 7, 8, 300, 123)
    duel = Duel(id=123, challenger_id=7, opponent_id=8, bet=300, chat_id=-100,
                bot=bot, container=container, escrow_id='id', challenger_name='Alice', opponent_name='Bob')
    duel.accepted = True
    service.duels[123] = duel
    async def fail(*args, **kwargs): raise RuntimeError('journal unavailable')
    with patch.object(service.escrow.transactions, 'insert_one', side_effect=fail):
        with pytest.raises(RuntimeError, match='journal unavailable'):
            await service._finish_duel(duel, 8, 'Соперник сдался')
    text = bot.send_message.call_args.args[1]
    assert 'Выплата пока не подтверждена' in text
    assert 'Победитель:' not in text and '+600 монет' not in text
    assert bot.send_message.call_args.kwargs['reply_markup'] is None
    assert 'подтверждается' in await service.process_move(123, 7, 'hit_l')
    assert 'подтверждается' in await service.surrender(123, 8)
    assert db.users.docs[8]['coins'] == 700
    await service._retry_live_settlements()
    assert duel.finished and duel.winner_id == 8
    assert db.users.docs[8]['coins'] == 1300
    assert db.users.docs[8]['xp'] == 50
    text = bot.edit_message_text.call_args.kwargs['text']
    assert 'Победитель: @Bob' in text and '+600 монет' in text
    await service._retry_live_settlements()
    assert db.users.docs[8]['coins'] == 1300 and db.users.docs[8]['xp'] == 50
    await asyncio.sleep(0)
