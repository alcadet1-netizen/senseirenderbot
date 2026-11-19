import pytest
from tests.unit.test_economy_emission import economy


@pytest.mark.asyncio
async def test_process_message_reward_counting(monkeypatch):
    async def tx(mongo, callback):
        return await callback('test-session')
    monkeypatch.setattr('src.services.economy_service.transaction', tx)
    service, db = economy([{'_id': 'single', 'coins': 10000, 'total_emitted': 10000}], user_coins=100)
    db.users.docs[7]['messages_count'] = 10
    db.users.docs[7]['xp'] = 100
    await service.process_message_reward(user_id=7, apply_rewards=False)
    assert db.users.docs[7]['messages_count'] == 10
    assert db.users.docs[7]['xp'] == 100
    assert db.users.docs[7]['coins'] == 100
    await service.process_message_reward(user_id=7, apply_rewards=True)
    assert db.users.docs[7]['messages_count'] == 11
    assert db.users.docs[7]['xp'] > 100
    assert db.users.docs[7]['coins'] > 100
