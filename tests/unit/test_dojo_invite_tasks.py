from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services import dojo_invite_tasks as invites
from src.services.hedgehog_service import GameError


@pytest.mark.asyncio
async def test_invite_ladder_pays_only_current_verified_stage(monkeypatch):
    async def tx(_mongo, callback):
        return await callback('session')

    monkeypatch.setattr(invites, 'transaction', tx)
    user = {'id': 42, 'coins': 0}
    async def advance(query, change, session):
        for key, amount in change['$inc'].items():
            user[key] = user.get(key, 0) + amount

    users = SimpleNamespace(find_one=AsyncMock(return_value=user), update_one=AsyncMock(side_effect=advance),
                            count_documents=AsyncMock(return_value=0))
    db = SimpleNamespace(users=users, bank=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1))),
                         transactions=SimpleNamespace(insert_one=AsyncMock()))
    service = invites.InviteTasks(SimpleNamespace(database=db))
    for index, (goal, reward) in enumerate(invites.TIERS):
        task = await service.current(42)
        assert task['goal'] == goal and not task['claimed']
        users.count_documents.return_value = goal - 1
        with pytest.raises(GameError, match='Приглашено'):
            await service.claim(42, task['slug'])
        users.count_documents.return_value = goal
        result = await service.claim(42, task['slug'])
        assert result['reward_coins'] == reward
        assert result['task'] == await service.current(42)
        with pytest.raises(GameError, match='не активен'):
            await service.claim(42, task['slug'])
        assert db.transactions.insert_one.await_count == index + 1
    assert result['task']['claimed'] and user['coins'] == 37000
    users.count_documents.assert_awaited_with({'referrer_id': 42, 'id': {'$ne': 42},
        'is_bot': {'$ne': True}, 'is_banned': {'$ne': True}}, limit=25, session='session')
