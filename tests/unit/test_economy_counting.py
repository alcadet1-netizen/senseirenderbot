import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.economy_service import EconomyService


@pytest.mark.asyncio
async def test_process_message_reward_counting():
    """Test that message count increments only when apply_rewards=True."""
    # Setup mock mongo client and collections
    mock_mongo_client = AsyncMock()
    db = AsyncMock()
    mock_mongo_client.database = db

    # Mock collections
    db.users = AsyncMock()
    db.transactions = AsyncMock()
    db.bank = AsyncMock()

    # We'll make our mocks stateful to track changes
    # Initial user data
    user_id = 1
    initial_messages_count = 10
    initial_xp = 100
    initial_coins = 100.0

    stored_user = {
        "id": user_id,
        "username": "testuser",
        "first_name": "Test",
        "messages_count": initial_messages_count,
        "xp": initial_xp,
        "coins": initial_coins,
        "is_banned": False,
        "has_katana": False,
        "katana_length": 0.0,
        "wins": 0,
        "losses": 0,
        "daily_streak": 0,
        "last_daily": None,
        "referrer_id": None,
        "referral_count": 0,
        "can_receive_broadcast": True,
        "created_at": MagicMock(),  # We don't need the exact value for this test
        "updated_at": MagicMock(),
    }

    stored_bank_balance = 10000.0

    # Track state for users
    def make_find_one_return_value(collection_name):
        def side_effect(query):
            if collection_name == "users":
                return stored_user.copy() if stored_user else None
            elif collection_name == "bank":
                return {"balance": stored_bank_balance} if stored_bank_balance is not None else None
            return None
        return side_effect

    def make_update_one_return_value(collection_name):
        def side_effect(query, update_dict, **kwargs):
            nonlocal stored_user, stored_bank_balance
            if collection_name == "users" and query.get("id") == user_id:
                if "$inc" in update_dict:
                    if "messages_count" in update_dict["$inc"]:
                        stored_user["messages_count"] += update_dict["$inc"]["messages_count"]
                    if "xp" in update_dict["$inc"]:
                        stored_user["xp"] += update_dict["$inc"]["xp"]
                    if "coins" in update_dict["$inc"]:
                        stored_user["coins"] += update_dict["$inc"]["coins"]
                if "$set" in update_dict:
                    stored_user.update(update_dict["$set"])
            elif collection_name == "bank" and query.get("_id") == "single":
                if "$set" in update_dict and "balance" in update_dict["$set"]:
                    stored_bank_balance = update_dict["$set"]["balance"]
            # Return a mock result
            result = AsyncMock()
            result.acknowledged = True
            result.matched_count = 1
            result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
            result.upserted_id = None
            return result
        return side_effect

    def make_insert_one_return_value(collection_name):
        def side_effect(document):
            if collection_name == "transactions":
                pass  # We don't need to track transactions for this test, but we can if needed
            result = AsyncMock()
            result.acknowledged = True
            result.inserted_id = f"tx_{hash(str(document))}"  # Dummy ID
            return result
        return side_effect

    # Apply the side effects
    db.users.find_one.side_effect = make_find_one_return_value("users")
    db.users.update_one.side_effect = make_update_one_return_value("users")
    db.users.insert_one.side_effect = make_insert_one_return_value("users")
    db.bank.find_one.side_effect = make_find_one_return_value("bank")
    db.bank.update_one.side_effect = make_update_one_return_value("bank")
    db.transactions.insert_one.side_effect = make_insert_one_return_value("transactions")

    # Mock the aggregate operation for total coins in circulation
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"total": 0.0}])
    db.users.aggregate = MagicMock(return_value=mock_cursor)

    # Create service
    service = EconomyService(mock_mongo_client)

    # Test 1: apply_rewards = False
    await service.process_message_reward(user_id=user_id, apply_rewards=False)
    assert stored_user["messages_count"] == initial_messages_count  # Should NOT increment
    assert stored_user["xp"] == initial_xp  # Should NOT change
    assert stored_user["coins"] == initial_coins  # Should NOT change

    # Test 2: apply_rewards = True
    await service.process_message_reward(user_id=user_id, apply_rewards=True)
    assert stored_user["messages_count"] == initial_messages_count + 1  # Should increment
    # Note: XP and coins may change due to rewards, but we don't check the exact values here
    # because they depend on the halving multiplier and bank balance.
    # We just want to ensure that the message count increased.

    # Verify that the user was updated in the database (at least the message count update)
    # We can check that update_one was called with the correct parameters for the message count increment.
    # However, note that when apply_rewards=True, there are multiple updates (message count, xp, coins, etc.)
    # We'll just check that update_one was called at least twice (once for message count, once for rewards)
    assert db.users.update_one.call_count >= 2