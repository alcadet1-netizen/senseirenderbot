from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot.handlers.duel_commands import accept_dojo_challenge
from src.services.dojo_duel import publish
from src.services.hedgehog_service import GameError


@pytest.mark.asyncio
@pytest.mark.parametrize('bet', [-1, True, '300', 299])
async def test_untrusted_bet_is_rejected(bet):
    with pytest.raises(GameError):
        await publish(None, 1, 'Player', bet)


@pytest.mark.asyncio
@pytest.mark.parametrize('won', [False, True])
async def test_only_winner_of_atomic_accept_creates_duel(won):
    token = 'a' * 24
    duel = NS(id=9)
    engine = NS(_is_in_active_duel=Mock(return_value=False),
                create_duel=AsyncMock(return_value=duel), process_decision=AsyncMock())
    offers = NS(find_one=AsyncMock(return_value={'bet': 300, 'chat': -10}),
                update_one=AsyncMock(return_value=NS(matched_count=int(won))))
    db = NS(dojo_duel_offers=offers, users=NS(find_one=AsyncMock(return_value={'coins': 500})))
    query = NS(data=f'vs:1:{token}', from_user=NS(id=2, is_bot=False), answer=AsyncMock(),
               message=NS(chat=NS(id=-10), message_id=10))
    await accept_dojo_challenge(query, NS(duel_service=engine, mongo_client=NS(database=db)), 'bot')
    if won:
        engine.create_duel.assert_awaited_once_with(1, 2, 300, -10, 'bot', request_id=f'dojo:{token}')
        engine.process_decision.assert_awaited_once_with(9, 2, 'a')
    else:
        engine.create_duel.assert_not_awaited()
