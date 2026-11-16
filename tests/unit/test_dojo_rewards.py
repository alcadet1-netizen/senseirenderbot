"""Dojo SenseiCoin payouts stay server-authoritative, capped and one-shot."""
import copy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services import dojo_reward_service as rewards
from src.services.dojo_reward_service import DojoRewardService
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import Collection


class Runs(Collection):
    async def insert_one(self, doc):
        self.docs[doc['_id']] = copy.deepcopy(doc)


def service():
    mongo = SimpleNamespace(database=SimpleNamespace(
        dojo_runs=Runs(), dojo_days=Collection()))
    economy = SimpleNamespace(process_game_win=AsyncMock(return_value={
        'success': True, 'new_coins': 1234}))
    return mongo, DojoRewardService(mongo, economy), economy


def test_reward_table_is_deliberately_small():
    assert DojoRewardService.reward_for(1, False) == 2
    assert DojoRewardService.reward_for(5, False) == 10
    assert DojoRewardService.reward_for(5, True) == 14
    assert rewards.DAILY_CAP == 30
    assert rewards.MIN_RUN_SECONDS == 45


@pytest.mark.asyncio
async def test_fast_run_and_replayed_token_never_pay():
    _, dojo, economy = service()
    with patch.object(rewards.time, 'time', return_value=1000):
        run = (await dojo.start(7))['run']
    with patch.object(rewards.time, 'time', return_value=1030):
        with pytest.raises(GameError, match='Слишком быстрый'):
            await dojo.claim(7, run, 5, True)
        with pytest.raises(GameError, match='Слишком быстрый'):
            await dojo.claim(7, run, 5, True)
    economy.process_game_win.assert_not_awaited()
    assert dojo.runs.docs[run]['claimed'] is False


@pytest.mark.asyncio
async def test_claim_pays_once_and_replay_is_rejected():
    _, dojo, economy = service()
    with patch.object(rewards.time, 'time', return_value=1000):
        run = (await dojo.start(7))['run']
    with patch.object(rewards.time, 'time', return_value=1060):
        result = await dojo.claim(7, run, 5, True)
        assert result['coins'] == 14 and result['daily_earned'] == 14
        assert result['balance'] == 1234
        economy.process_game_win.assert_awaited_once()
        assert economy.process_game_win.await_args.kwargs['coins'] == 14
        with pytest.raises(GameError):
            await dojo.claim(7, run, 5, True)
    assert economy.process_game_win.await_count == 1


@pytest.mark.asyncio
async def test_daily_cap_limits_third_run_payout():
    _, dojo, economy = service()
    runs = []
    with patch.object(rewards.time, 'time', return_value=1000):
        for _ in range(3):
            runs.append((await dojo.start(7))['run'])
    with patch.object(rewards.time, 'time', return_value=1060):
        first = await dojo.claim(7, runs[0], 5, True)
        second = await dojo.claim(7, runs[1], 5, True)
        third = await dojo.claim(7, runs[2], 5, True)
    assert first['coins'] == 14
    assert second['coins'] == 14
    assert third['coins'] == 2
    assert third['daily_earned'] == rewards.DAILY_CAP
    assert economy.process_game_win.await_count == 3


@pytest.mark.asyncio
async def test_wrong_user_and_invalid_result_are_rejected():
    _, dojo, economy = service()
    with patch.object(rewards.time, 'time', return_value=1000):
        run = (await dojo.start(7))['run']
    with patch.object(rewards.time, 'time', return_value=1060):
        for args in ((8, run, 5, True), (7, run, 6, False),
                     (7, 'short', 5, True)):
            with pytest.raises(GameError):
                await dojo.claim(*args)
    economy.process_game_win.assert_not_awaited()
