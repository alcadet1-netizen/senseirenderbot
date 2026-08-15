"""
🧪 Тесты ежедневного сервиса.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, date
from src.services.daily_service import DailyService
from src.core.exceptions import DailyAlreadyClaimedError


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB клиента для тестов."""
    client = AsyncMock()
    # Mock database
    db = AsyncMock()
    client.database = db

    # Mock collections
    db.users = AsyncMock()
    db.daily_claims = AsyncMock()
    db.transactions = AsyncMock()
    db.bank = AsyncMock()

    return client


@pytest.fixture
def daily_service(mock_mongo_client):
    """Создание ежедневного сервиса с мокнутым MongoDB клиентом."""
    return DailyService(mock_mongo_client)


@pytest.mark.asyncio
async def test_claim_daily_cooldown_format(daily_service, mock_mongo_client):
    """Тест проверки формата сообщения о перезарядке ежедневного бонуса."""
    user_id = 123

    # Setup mocks
    # Mock user exists
    user_data = {
        "id": user_id,
        "is_banned": False,
        "last_daily": None,
        "daily_streak": 0,
        "xp": 0,
        "coins": 0
    }
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Mock that a claim EXISTS for today (so we get the cooldown message)
    today = datetime.utcnow().date()
    existing_claim = {
        "user_id": user_id,
        "claim_date": today,
        "xp_received": 100,
        "coins_received": 100
    }
    mock_mongo_client.database.daily_claims.find_one.return_value = existing_claim

    # Mock bank with sufficient balance
    bank_data = {"_id": "main", "balance": 1000}
    mock_mongo_client.database.bank.find_one.return_value = bank_data

    # Execute and verify exception
    with pytest.raises(DailyAlreadyClaimedError) as exc_info:
        await daily_service.claim_daily(user_id)

    # Check the error message format
    # Now is current time. Reset is next day 00:00.
    now = datetime.utcnow()
    tomorrow = datetime.combine(
        today + timedelta(days=1),
        datetime.min.time()
    )
    delta = tomorrow - now
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    expected_message = f"через {hours} ч. {minutes} мин."

    assert expected_message in str(exc_info.value)

    # Verify database calls
    mock_mongo_client.database.users.find_one.assert_called_once_with({"id": user_id})
    mock_mongo_client.database.daily_claims.find_one.assert_called_once()

    # Should NOT update anything since already claimed
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()
    mock_mongo_client.database.transactions.insert_one.assert_not_called()
    mock_mongo_client.database.daily_claims.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_claim_daily_success(daily_service, mock_mongo_client):
    """Тест успешного получения ежедневного бонуса."""
    user_id = 123
    username = "testuser"
    first_name = "Test"

    # Setup mocks
    # Mock user does NOT exist yet (will be created)
    mock_mongo_client.database.users.find_one.return_value = None

    # Mock that NO claim exists for today
    mock_mongo_client.database.daily_claims.find_one.return_value = None

    # Mock bank with sufficient balance
    bank_data = {"_id": "main", "balance": 1000}
    mock_mongo_client.database.bank.find_one.return_value = bank_data

    # Execute
    result = await daily_service.claim_daily(
        user_id=user_id,
        username=username,
        first_name=first_name
    )

    # Verify result
    assert result["success"] is True
    assert "xp" in result
    assert "coins" in result
    assert "total_xp" in result
    assert "total_coins" in result
    assert "streak" in result

    # Verify user was created
    mock_mongo_client.database.users.insert_one.assert_called_once()

    # Verify bank was updated (coins deducted)
    mock_mongo_client.database.bank.update_one.assert_called_once()

    # Verify user was updated (xp, coins, last_daily, streak)
    mock_mongo_client.database.users.update_one.assert_called_once()

    # Verify transaction was recorded
    mock_mongo_client.database.transactions.insert_one.assert_called_once()

    # Verify daily claim was recorded
    mock_mongo_client.database.daily_claims.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_claim_daily_user_banned(daily_service, mock_mongo_client):
    """Тест получения ежедневного бонуса забаненным пользователем."""
    user_id = 123

    # Setup mocks - user is banned
    user_data = {
        "id": user_id,
        "is_banned": True,
        "last_daily": None,
        "daily_streak": 0,
        "xp": 0,
        "coins": 0
    }
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Execute
    result = await daily_service.claim_daily(user_id)

    # Verify
    assert result["success"] is False
    assert result["error"] == "banned"

    # Verify no other operations were performed
    mock_mongo_client.database.users.insert_one.assert_not_called()
    mock_mongo_client.database.daily_claims.find_one.assert_not_called()
    mock_mongo_client.database.bank.find_one.assert_not_called()
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()
    mock_mongo_client.database.transactions.insert_one.assert_not_called()
    mock_mongo_client.database.daily_claims.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_can_claim_cooldown_format(daily_service, mock_mongo_client):
    """Тест проверки формата сообщения о возможности получения бонуса."""
    user_id = 123

    # Setup mocks
    # Mock user exists
    user_data = {"id": user_id, "coins": 0}
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Mock that a claim EXISTS for today (so we get cooldown info)
    today = datetime.utcnow().date()
    existing_claim = {
        "user_id": user_id,
        "claim_date": today
    }
    mock_mongo_client.database.daily_claims.find_one.return_value = existing_claim

    # Execute
    can_claim, message = await daily_service.can_claim(user_id)

    # Assert
    assert can_claim is False
    # Message should indicate cooldown time
    assert message is not None
    assert "через" in message
    assert "ч." in message
    assert "мин." in message

    # Verify calls
    mock_mongo_client.database.daily_claims.find_one.assert_called_once()


@pytest.mark.asyncio
async def test_can_claim_available(daily_service, mock_mongo_client):
    """Тест когда пользователь может получить бонус."""
    user_id = 123

    # Setup mocks
    # Mock user exists
    user_data = {"id": user_id, "coins": 0}
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Mock that NO claim exists for today (available to claim)
    mock_mongo_client.database.daily_claims.find_one.return_value = None

    # Execute
    can_claim, message = await daily_service.can_claim(user_id)

    # Assert
    assert can_claim is True
    assert message is None

    # Verify calls
    mock_mongo_client.database.daily_claims.find_one.assert_called_once()