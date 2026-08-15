"""
🧪 Тесты сервиса экономики.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from src.services.economy_service import EconomyService, InsufficientFundsError, UserNotFoundError, NoKatanaError, CooldownError
from src.core.constants import KATANA_UPGRADE_COST


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB клиента для тестов."""
    client = AsyncMock()
    # Mock database
    db = AsyncMock()
    client.database = db

    # Mock collections
    db.users = AsyncMock()
    db.transactions = AsyncMock()
    db.bank = AsyncMock()
    db.tickets = AsyncMock()

    return client


@pytest.fixture
def economy_service(mock_mongo_client):
    """Создание сервиса экономики с мокнутым MongoDB клиентом."""
    return EconomyService(mock_mongo_client)


@pytest.mark.asyncio
async def test_buy_katana_success(economy_service, mock_mongo_client):
    """Тест успешной покупки катаны."""
    # Prepare mock data
    mock_user = {
        "id": 123,
        "username": "test_user",
        "coins": 2000.0,
        "has_katana": False,
        "katana_length": 0.0
    }

    # We'll make our mocks stateful to track changes
    stored_user = mock_user.copy()
    stored_bank_balance = 5000.0

    # Setup mocks - return values directly (not coroutines) for find operations
    def make_find_one_return_value(collection_name):
        def side_effect(query):
            if collection_name == "users":
                return stored_user.copy() if stored_user else None
            elif collection_name == "bank":
                return {"balance": stored_bank_balance} if stored_bank_balance is not None else None
            return None
        return side_effect

    # Setup mocks for update operations - return AsyncMock result
    def make_update_one_return_value(collection_name):
        def side_effect(query, update_dict, **kwargs):
            nonlocal stored_user, stored_bank_balance
            if collection_name == "users" and query.get("id") == 123:
                if "$inc" in update_dict:
                    if "coins" in update_dict["$inc"]:
                        stored_user["coins"] += update_dict["$inc"]["coins"]
                    if "katana_length" in update_dict["$inc"]:
                        stored_user["katana_length"] += update_dict["$inc"]["katana_length"]
                if "$set" in update_dict:
                    stored_user.update(update_dict["$set"])
            elif collection_name == "bank" and query.get("_id") == "single":
                if "$set" in update_dict and "balance" in update_dict["$set"]:
                    stored_bank_balance = update_dict["$set"]["balance"]
            # Return a mock result object
            result = AsyncMock()
            result.acknowledged = True
            result.matched_count = 1
            result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
            result.upserted_id = None
            return result
        return side_effect

    # Apply the side effects
    mock_mongo_client.database.users.find_one.side_effect = make_find_one_return_value("users")
    mock_mongo_client.database.bank.find_one.side_effect = make_find_one_return_value("bank")
    mock_mongo_client.database.users.update_one.side_effect = make_update_one_return_value("users")
    mock_mongo_client.database.bank.update_one.side_effect = make_update_one_return_value("bank")
    mock_mongo_client.database.transactions.insert_one = AsyncMock()

    # Execute
    result = await economy_service.buy_katana(123)

    # Verify
    assert result["success"] is True
    assert result["cost"] == 1000.0
    assert result["new_balance"] == 1000.0  # 2000 - 1000 = 1000

    # Verify database calls
    assert mock_mongo_client.database.users.find_one.call_count >= 2  # Initial check and final get
    mock_mongo_client.database.users.update_one.assert_any_call(
        {"id": 123}, {"$inc": {"coins": -1000.0}}
    )
    mock_mongo_client.database.users.update_one.assert_any_call(
        {"id": 123}, {"$set": {"has_katana": True, "katana_length": 1.0}}
    )
    mock_mongo_client.database.bank.update_one.assert_called()
    mock_mongo_client.database.transactions.insert_one.assert_called()


@pytest.mark.asyncio
async def test_buy_katana_insufficient_funds(economy_service, mock_mongo_client):
    """Тест покупки катаны с недостаточными средствами."""
    # Prepare mock data
    mock_user = {
        "id": 124,
        "username": "poor_user",
        "coins": 500.0,
        "has_katana": False
    }

    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = mock_user

    # Execute and verify exception
    with pytest.raises(InsufficientFundsError):
        await economy_service.buy_katana(124)

    # Verify no updates were made
    mock_mongo_client.database.users.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_buy_katana_already_has(economy_service, mock_mongo_client):
    """Тест попытки купить катану когда она уже есть."""
    # Prepare mock data
    mock_user = {
        "id": 125,
        "username": "samurai",
        "coins": 2000.0,
        "has_katana": True
    }

    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = mock_user

    # Execute
    result = await economy_service.buy_katana(125)

    # Verify
    assert result["success"] is False
    assert result["reason"] == "already_has_katana"

    # Verify no database updates
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_buy_katana_user_not_found(economy_service, mock_mongo_client):
    """Тест покупки катаны для несуществующего пользователя."""
    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = None

    # Execute and verify exception
    with pytest.raises(UserNotFoundError):
        await economy_service.buy_katana(999)

    # Verify no updates were made
    mock_mongo_client.database.users.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_upgrade_katana_success(economy_service, mock_mongo_client):
    """Тест успешного улучшения катаны."""
    # Prepare mock data
    mock_user = {
        "id": 126,
        "username": "upgrader",
        "coins": 2000.0,
        "has_katana": True,
        "katana_length": 10.0,
        "last_katana_up": None
    }

    # We'll make our mocks stateful to track changes
    stored_user = mock_user.copy()
    stored_bank_balance = 5000.0

    # Setup mocks - return values directly (not coroutines) for find operations
    def make_find_one_return_value(collection_name):
        def side_effect(query):
            if collection_name == "users":
                return stored_user.copy() if stored_user else None
            elif collection_name == "bank":
                return {"balance": stored_bank_balance} if stored_bank_balance is not None else None
            return None
        return side_effect

    # Setup mocks for update operations - return AsyncMock result
    def make_update_one_return_value(collection_name):
        def side_effect(query, update_dict, **kwargs):
            nonlocal stored_user, stored_bank_balance
            if collection_name == "users" and query.get("id") == 126:
                if "$inc" in update_dict:
                    if "coins" in update_dict["$inc"]:
                        stored_user["coins"] += update_dict["$inc"]["coins"]
                    if "katana_length" in update_dict["$inc"]:
                        stored_user["katana_length"] += update_dict["$inc"]["katana_length"]
                if "$set" in update_dict:
                    stored_user.update(update_dict["$set"])
            elif collection_name == "bank" and query.get("_id") == "single":
                if "$set" in update_dict and "balance" in update_dict["$set"]:
                    stored_bank_balance = update_dict["$set"]["balance"]
            # Return a mock result object
            result = AsyncMock()
            result.acknowledged = True
            result.matched_count = 1
            result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
            result.upserted_id = None
            return result
        return side_effect

    # Apply the side effects
    mock_mongo_client.database.users.find_one.side_effect = make_find_one_return_value("users")
    mock_mongo_client.database.bank.find_one.side_effect = make_find_one_return_value("bank")
    mock_mongo_client.database.users.update_one.side_effect = make_update_one_return_value("users")
    mock_mongo_client.database.bank.update_one.side_effect = make_update_one_return_value("bank")
    mock_mongo_client.database.transactions.insert_one = AsyncMock()

    # Mock random.random() to return a value that guarantees success (less than KATANA_WIN_CHANCE)
    with patch('random.random', return_value=0.5):  # 0.5 < 0.85 (KATANA_WIN_CHANCE)
        # Execute
        result = await economy_service.upgrade_katana(126)

        # Verify
        assert result["is_upgraded"] is True
        assert result["cost"] == KATANA_UPGRADE_COST
        assert result["growth"] > 0

        # Verify database calls for success case
        mock_mongo_client.database.users.update_one.assert_any_call(
            {"id": 126}, {"$inc": {"coins": -KATANA_UPGRADE_COST}}
        )
        mock_mongo_client.database.bank.update_one.assert_called()  # Deposit to bank
        # Should have two update calls: one for coins, one for katana_length and timestamp
        update_calls = mock_mongo_client.database.users.update_one.call_args_list
        assert len(update_calls) >= 2

        # Verify transaction was recorded
        mock_mongo_client.database.transactions.insert_one.assert_called()


@pytest.mark.asyncio
async def test_upgrade_katana_insufficient_funds(economy_service, mock_mongo_client):
    """Тест улучшения катаны с недостаточными средствами."""
    # Prepare mock data
    mock_user = {
        "id": 127,
        "username": "poor_upgrader",
        "coins": 50.0,
        "has_katana": True,
        "katana_length": 5.0
    }

    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = mock_user

    # Execute and verify exception
    with pytest.raises(InsufficientFundsError):
        await economy_service.upgrade_katana(127)

    # Verify no database updates
    mock_mongo_client.database.users.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_upgrade_katana_no_katana(economy_service, mock_mongo_client):
    """Тест улучшения катаны когда у пользователя нет катаны."""
    # Prepare mock data
    mock_user = {
        "id": 128,
        "username": "no_katana_user",
        "coins": 2000.0,
        "has_katana": False,
        "katana_length": 0.0
    }

    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = mock_user

    # Execute and verify exception
    with pytest.raises(NoKatanaError):
        await economy_service.upgrade_katana(128)

    # Verify no database updates
    mock_mongo_client.database.users.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_upgrade_katana_cooldown(economy_service, mock_mongo_client):
    """Тест улучшения катаны во время перезарядки."""
    # Prepare mock data with recent upgrade
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(minutes=5)  # 5 minutes ago - within cooldown

    mock_user = {
        "id": 129,
        "username": "cooldown_user",
        "coins": 2000.0,
        "has_katana": True,
        "katana_length": 10.0,
        "last_katana_up": recent_time
    }

    # Setup mocks
    mock_mongo_client.database.users.find_one.return_value = mock_user

    # Execute and verify exception
    with pytest.raises(CooldownError):
        await economy_service.upgrade_katana(129)

    # Verify no database updates
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_reward_new_user(economy_service, mock_mongo_client):
    """Тест обработки награды за сообщение для нового пользователя."""
    # Setup mock data - user doesn't exist initially
    initial_user = None  # User doesn't exist yet

    # User data after creation
    created_user = {
        "id": 999,
        "username": "new_user",
        "first_name": "New",
        "last_name": "User",
        "is_bot": False,
        "xp": 0,
        "coins": 0.0,
        "messages_count": 1,  # Will be incremented by 1 for the message
        "wins": 0,
        "losses": 0,
        "daily_streak": 0,
        "last_daily": None,
        "is_banned": False,
        "ban_reason": None,
        "is_muted": False,
        "mute_until": None,
        "has_katana": False,
        "katana_length": 0.0,
        "last_katana_up": None,
        "referrer_id": None,
        "referral_count": 0,
        "can_receive_broadcast": True,
        "created_at": datetime.now(timezone.utc),
    }

    # Track state
    user_created = False

    # Setup mocks for users collection
    async def mock_users_find_one(query):
        if not user_created:
            return None  # User doesn't exist yet
        return created_user.copy()  # User exists after creation

    async def mock_users_insert_one(document):
        nonlocal user_created
        user_created = True  # Mark that user has been created
        # Return mock result
        result = AsyncMock()
        result.acknowledged = True
        result.inserted_id = "mock_id"
        return result

    async def mock_users_update_one(query, update_dict, **kwargs):
        # Return mock result
        result = AsyncMock()
        result.acknowledged = True
        result.matched_count = 1
        result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
        result.upserted_id = None
        return result

    # Setup mocks for bank collection
    async def mock_bank_find_one(query):
        return {"balance": 10000.0}  # Sufficient bank balance

    async def mock_bank_update_one(query, update_dict, **kwargs):
        # Return mock result
        result = AsyncMock()
        result.acknowledged = True
        result.matched_count = 1
        result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
        result.upserted_id = None
        return result

    # Setup mock for transactions
    mock_mongo_client.database.transactions.insert_one = AsyncMock()

    # Setup mock for aggregate operation
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"total": 0.0}])

    # Apply the mocks
    mock_mongo_client.database.users.find_one.side_effect = mock_users_find_one
    mock_mongo_client.database.users.insert_one.side_effect = mock_users_insert_one
    mock_mongo_client.database.users.update_one.side_effect = mock_users_update_one
    mock_mongo_client.database.bank.find_one.side_effect = mock_bank_find_one
    mock_mongo_client.database.bank.update_one.side_effect = mock_bank_update_one
    mock_mongo_client.database.users.aggregate = MagicMock(return_value=mock_cursor)

    # Execute
    result = await economy_service.process_message_reward(
        user_id=999,
        username="new_user",
        first_name="New",
        last_name="User",
        apply_rewards=True
    )

    # Verify
    assert result["success"] is True
    assert "xp_earned" in result
    assert "coins_earned" in result
    assert result["new_xp"] >= 0
    assert result["new_coins"] >= 0

    # Verify user was created
    mock_mongo_client.database.users.insert_one.assert_called()

    # Verify updates were made (at least message count and rewards)
    assert mock_mongo_client.database.users.update_one.call_count >= 2

    # Verify transaction was recorded
    mock_mongo_client.database.transactions.insert_one.assert_called()


@pytest.mark.asyncio
async def test_get_bank_stats(economy_service, mock_mongo_client):
    """Тест получения статистики банка."""
    # Setup mocks
    mock_mongo_client.database.bank.find_one.return_value = {"balance": 5000.0}

    # Mock the aggregate operation
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"total": 15000.0}])
    mock_mongo_client.database.users.aggregate = MagicMock(return_value=mock_cursor)

    # Execute
    result = await economy_service.get_bank_stats()

    # Verify
    assert result["balance"] == 5000.0
    assert result["in_circulation"] == 15000.0
    assert "halving_multiplier" in result