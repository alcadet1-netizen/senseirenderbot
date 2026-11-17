"""Payouts must spend existing bank coins, never recreate an empty bank."""
from types import SimpleNamespace as NS

import pytest

from src.services.economy_service import EconomyService
from tests.unit.test_emission_service import Collection, Users


class UserCollection(Users):
    async def insert_one(self, document):
        self.docs[document.get('_id', document.get('id'))] = document
        return NS(inserted_id=document.get('_id', document.get('id')))


def economy(bank_docs, user_coins=1_000):
    db = NS(
        users=UserCollection([{"_id": 7, "id": 7, "coins": user_coins, "xp": 0,
                           "is_banned": False, "messages_count": 0}]),
        bank=Collection(bank_docs),
        transactions=UserCollection(),
        tickets=Collection(),
    )
    return EconomyService(NS(database=db)), db


@pytest.mark.asyncio
async def test_reading_or_losing_does_not_refill_the_bank():
    economy_service, db = economy([{
        "_id": "single", "coins": 0, "total_emitted": 1_000,
        "emission_cap": 10_000,
    }])
    assert await economy_service._get_bank_balance() == 0
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0

    result = await economy_service.process_game_win(7, coins=100)
    assert result["success"] is False
    assert result["reason"] == "insufficient_bank"
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0
    assert db.users.docs[7]["coins"] == 1_000


@pytest.mark.asyncio
async def test_message_reward_pays_only_what_the_bank_covers():
    economy_service, db = economy([{
        "_id": "single", "coins": 4, "total_emitted": 1_000,
        "emission_cap": 10_000,
    }])
    result = await economy_service.process_message_reward(
        7, username="u", first_name="U", apply_rewards=True)
    assert result["success"] is True
    assert result["coins_earned"] == 4
    assert db.users.docs[7]["coins"] == 1_004
    assert (await db.bank.find_one({"_id": "single"}))["coins"] == 0


@pytest.mark.asyncio
async def test_starter_kit_uses_the_global_reservation():
    economy_service, db = economy([{
        "_id": "single", "coins": 0, "total_emitted": 9_999_999_999,
        "emission_cap": 10_000_000_000,
    }], user_coins=0)
    db.users.docs.clear()
    result = await economy_service.process_game_win(8, coins=0, xp=0)
    assert result["success"] is True
    user = db.users.docs[8]
    assert user["coins"] == 0  # only 1 coin of headroom, not a full 10k kit
    # A reservation that would cross the ceiling is refused, so the counter
    # remains at its previous value instead of being rounded up.
    assert (await db.bank.find_one({"_id": "single"}))["total_emitted"] == 9_999_999_999


@pytest.mark.asyncio
async def test_game_win_moves_bank_coins_without_emission():
    """Mining and game rewards must never increase the emission counter."""
    economy_service, db = economy([{
        "_id": "single", "coins": 1_000.0, "total_emitted": 1_000.0,
        "emission_cap": 10_000_000_000,
    }])
    result = await economy_service.process_game_win(
        7, coins=125, xp=5, description="Dojo miner test")
    assert result["success"] is True
    assert result["new_coins"] == 1_125.0
    bank = await db.bank.find_one({"_id": "single"})
    assert bank["coins"] == 875.0
    # A bank -> player transfer is not minting: the lifetime counter stays put.
    assert bank["total_emitted"] == 1_000.0
    assert bank["emission_cap"] == 10_000_000_000
