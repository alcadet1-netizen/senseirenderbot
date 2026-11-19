from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.duel_commands import cmd_duel


@pytest.mark.asyncio
async def test_duel_command_passes_stable_telegram_message_identity():
    user = NS(id=7, username='a', full_name='A', is_bot=False)
    opponent = NS(id=8, username='b', full_name='B', is_bot=False)
    message = NS(from_user=user, reply_to_message=NS(from_user=opponent),
                 chat=NS(id=-100), message_id=42, text='/duel 300', answer=AsyncMock())
    container = NS(user_service=NS(get_profile=AsyncMock(return_value={'id': 7})),
                   duel_service=NS(create_duel=AsyncMock(return_value='already handled')))
    bot = AsyncMock()
    await cmd_duel(message, container, bot)
    container.duel_service.create_duel.assert_awaited_once_with(
        challenger_id=7, opponent_id=8, bet=300, chat_id=-100, bot=bot, request_id='-100:42')


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['eligibility', 'reservation'])
async def test_duplicate_committed_after_initial_check_beats_stale_insufficient_balance(stage):
    from src.services.duel_service import DuelService
    from tests.unit.test_hedgehog_game import services
    db, _, _ = services()
    db.duel_escrows = NS()
    container = NS(mongo_client=NS(database=db), user_service=NS(), economy_service=NS())
    service = DuelService(container)
    service.escrow.escrows = NS(find_one=AsyncMock(side_effect=[None, {'state': 'reserved'}]))
    service._check_eligibility = AsyncMock(return_value='недостаточно средств' if stage == 'eligibility' else None)
    service._escrow_funds = AsyncMock(return_value=False)
    response = await service.create_duel(7, 8, 300, -100, AsyncMock(), request_id='-100:42')
    assert 'уже обработан' in response
    assert service.escrow.escrows.find_one.await_count == 2
    if stage == 'eligibility':
        service._escrow_funds.assert_not_awaited()
    else:
        service._escrow_funds.assert_awaited_once()
    assert not service.duels


@pytest.mark.asyncio
async def test_failed_receipt_recheck_never_claims_definite_rejection():
    from src.services.duel_service import DuelService
    from tests.unit.test_hedgehog_game import services
    db, _, _ = services()
    db.duel_escrows = NS()
    service = DuelService(NS(mongo_client=NS(database=db), user_service=NS(), economy_service=NS()))
    service.escrow.escrows = NS(find_one=AsyncMock(side_effect=[None, OSError('offline')]))
    service._check_eligibility = AsyncMock(return_value='недостаточно средств')
    response = await service.create_duel(7, 8, 300, -100, AsyncMock(), request_id='-100:42')
    assert 'Не удалось проверить' in response
    assert not service.duels
