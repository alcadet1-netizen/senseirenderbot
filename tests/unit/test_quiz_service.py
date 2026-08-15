"""
🧪 Тесты сервиса викторины.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from src.services.quiz_service import QuizService
from src.core.exceptions import BankInsufficientFundsError
from src.core.constants import EXCHANGE_COINS_TO_TICKET


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB клиента для тестов."""
    client = AsyncMock()
    # Mock database
    db = AsyncMock()
    client.database = db

    # Mock collections
    db.quiz_states = AsyncMock()
    db.quiz_questions = AsyncMock()
    db.users = AsyncMock()
    db.transactions = AsyncMock()
    db.bank = AsyncMock()
    db.tickets = AsyncMock()

    return client


@pytest.fixture
def quiz_service(mock_mongo_client):
    """Создание сервиса викторины с мокнутым MongoDB клиентом."""
    return QuizService(mock_mongo_client)


@pytest.mark.asyncio
async def test_start_quiz_success(quiz_service, mock_mongo_client):
    """Тест успешного запуска викторины."""
    # Setup
    chat_id = 123

    # Mock the find_one to return None (no existing quiz state)
    mock_mongo_client.database.quiz_states.find_one.return_value = None

    # Execute
    result = await quiz_service.start_quiz(chat_id)

    # Verify
    assert result is True
    # Verify that update_one was called with upsert=True
    mock_mongo_client.database.quiz_states.update_one.assert_called_once()
    call_args = mock_mongo_client.database.quiz_states.update_one.call_args
    assert call_args[0][0] == {"chat_id": chat_id}  # filter
    assert "$set" in call_args[0][1]  # update contains $set
    assert call_args[1]["upsert"] is True


@pytest.mark.asyncio
async def test_start_quiz_already_running(quiz_service, mock_mongo_client):
    """Тест попытки запустить викторину когда она уже запущена."""
    # Setup
    chat_id = 123
    existing_state = {"status": "running"}

    # Mock the find_one to return existing state
    mock_mongo_client.database.quiz_states.find_one.return_value = existing_state

    # Execute
    result = await quiz_service.start_quiz(chat_id)

    # Verify
    assert result is False
    # Verify that update_one was NOT called
    mock_mongo_client.database.quiz_states.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_check_answer_correct(quiz_service, mock_mongo_client):
    """Тест правильного ответа на вопрос викторины."""
    # Setup
    chat_id = 123
    user_id = 456
    user_name = "TestUser"
    correct_answer = "ответ"

    # Mock quiz state
    quiz_state = {
        "status": "waiting_answer",
        "answer": correct_answer,
        "current_question_id": 1,
        "round": 1,
        "used_questions": [1],
        "stats": {
            "total_questions": 0,
            "total_coins": 0,
            "total_tickets": 0,
            "winners": {}
        }
    }
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Mock user
    user_data = {"id": user_id, "coins": 100}
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Mock bank with sufficient funds
    bank_data = {"_id": "main", "balance": 1000.0}
    mock_mongo_client.database.bank.find_one.return_value = bank_data

    # Execute
    result = await quiz_service.check_answer(chat_id, user_id, user_name, "Ответ")  # Case insensitive

    # Verify
    assert result is not None
    assert result["user_id"] == user_id
    assert result["reward"] == 100.0
    # Balance should be 200 (100 original + 100 reward)
    assert result["balance"] == 200.0

    # Verify database updates
    # 1. Bank update (withdraw 100)
    mock_mongo_client.database.bank.update_one.assert_called_once()
    bank_update_args = mock_mongo_client.database.bank.update_one.call_args
    assert bank_update_args[0][0] == {"_id": "main"}
    assert "$set" in bank_update_args[0][1]
    assert bank_update_args[0][1]["$set"]["balance"] == 900.0  # 1000 - 100

    # 2. User update (deposit 100)
    mock_mongo_client.database.users.update_one.assert_called_once()
    user_update_args = mock_mongo_client.database.users.update_one.call_args
    assert user_update_args[0][0] == {"id": user_id}
    assert "$inc" in user_update_args[0][1]
    assert user_update_args[0][1]["$inc"]["coins"] == 100.0

    # 3. Transaction insert
    mock_mongo_client.database.transactions.insert_one.assert_called_once()
    tx_args = mock_mongo_client.database.transactions.insert_one.call_args
    tx_doc = tx_args[0][0]
    assert tx_doc["user_id"] == user_id
    assert tx_doc["amount"] == 100.0
    assert tx_doc["type"] == "quiz_win"

    # 4. Ticket award (100 coins < 1000, so no ticket)
    mock_mongo_client.database.tickets.insert_one.assert_not_called()

    # 5. Quiz state update (mark as answered, update stats)
    assert mock_mongo_client.database.quiz_states.update_one.call_count == 1  # One for update
    quiz_state_update_args = mock_mongo_client.database.quiz_states.update_one.call_args_list[0]
    assert quiz_state_update_args[0][0] == {"chat_id": chat_id}
    assert "$set" in quiz_state_update_args[0][1]
    update_data = quiz_state_update_args[0][1]["$set"]
    assert update_data["status"] == "answered"
    assert update_data["stats"]["total_questions"] == 1
    assert update_data["stats"]["total_coins"] == 100.0
    assert str(user_id) in update_data["stats"]["winners"]
    assert update_data["stats"]["winners"][str(user_id)]["wins"] == 1
    assert update_data["stats"]["winners"][str(user_id)]["coins"] == 100.0


@pytest.mark.asyncio
async def test_check_answer_incorrect(quiz_service, mock_mongo_client):
    """Тест неправильного ответа на вопрос викторины."""
    # Setup
    chat_id = 123
    user_id = 456
    user_name = "TestUser"
    correct_answer = "ответ"

    # Mock quiz state
    quiz_state = {
        "status": "waiting_answer",
        "answer": correct_answer,
        "current_question_id": 1,
        "round": 1
    }
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    result = await quiz_service.check_answer(chat_id, user_id, user_name, "неверно")  # Incorrect answer

    # Verify
    assert result is None

    # Verify no database updates were made
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()
    mock_mongo_client.database.transactions.insert_one.assert_not_called()
    mock_mongo_client.database.tickets.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_check_answer_insufficient_funds(quiz_service, mock_mongo_client):
    """Тест ответа на вопрос викторины عندما банк не имеет достаточных средств."""
    # Setup
    chat_id = 123
    user_id = 456
    user_name = "TestUser"
    correct_answer = "ответ"

    # Mock quiz state
    quiz_state = {
        "status": "waiting_answer",
        "answer": correct_answer,
        "current_question_id": 1,
        "round": 1
    }
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Mock user
    user_data = {"id": user_id, "coins": 100}
    mock_mongo_client.database.users.find_one.return_value = user_data

    # Mock bank with insufficient funds (less than reward)
    bank_data = {"_id": "main", "balance": 50.0}  # Less than 100 reward
    mock_mongo_client.database.bank.find_one.return_value = bank_data

    # Execute
    result = await quiz_service.check_answer(chat_id, user_id, user_name, "Ответ")  # Correct answer

    # Verify
    assert result is not None
    assert result["user_id"] == user_id
    assert result["reward"] == 100.0
    # Balance should remain 100 (no transfer due to insufficient funds in bank)
    assert result["balance"] == 100.0

    # Verify bank was NOT updated (insufficient funds)
    mock_mongo_client.database.bank.update_one.assert_not_called()

    # Verify user was NOT updated (no coins awarded)
    mock_mongo_client.database.users.update_one.assert_not_called()

    # Verify transaction was NOT recorded
    mock_mongo_client.database.transactions.insert_one.assert_not_called()

    # Verify ticket was NOT awarded
    mock_mongo_client.database.tickets.insert_one.assert_not_called()

    # Verify quiz state was still updated (marked as answered, stats updated)
    assert mock_mongo_client.database.quiz_states.update_one.call_count == 1
    quiz_state_update_args = mock_mongo_client.database.quiz_states.update_one.call_args_list[0]
    assert quiz_state_update_args[0][0] == {"chat_id": chat_id}
    assert "$set" in quiz_state_update_args[0][1]
    update_data = quiz_state_update_args[0][1]["$set"]
    assert update_data["status"] == "answered"
    assert update_data["stats"]["total_questions"] == 1
    assert update_data["stats"]["total_coins"] == 100.0  # Still counted in stats
    assert str(user_id) in update_data["stats"]["winners"]
    assert update_data["stats"]["winners"][str(user_id)]["wins"] == 1
    assert update_data["stats"]["winners"][str(user_id)]["coins"] == 100.0


@pytest.mark.asyncio
async def test_check_answer_no_quiz_state(quiz_service, mock_mongo_client):
    """Тест ответа когда нет состояния викторины."""
    # Setup
    chat_id = 123
    user_id = 456
    user_name = "TestUser"

    # Mock quiz state as None (no quiz running)
    mock_mongo_client.database.quiz_states.find_one.return_value = None

    # Execute
    result = await quiz_service.check_answer(chat_id, user_id, user_name, "ответ")

    # Verify
    assert result is None

    # Verify no database operations were performed
    mock_mongo_client.database.users.find_one.assert_not_called()
    mock_mongo_client.database.bank.find_one.assert_not_called()
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()
    mock_mongo_client.database.transactions.insert_one.assert_not_called()
    mock_mongo_client.database.tickets.insert_one.assert_not_called()
    mock_mongo_client.database.quiz_states.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_check_answer_not_waiting_for_answer(quiz_service, mock_mongo_client):
    """Тест ответа когда викторина не ожидает ответ."""
    # Setup
    chat_id = 123
    user_id = 456
    user_name = "TestUser"

    # Mock quiz state with status not waiting for answer
    quiz_state = {"status": "running"}  # Not waiting for answer
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    result = await quiz_service.check_answer(chat_id, user_id, user_name, "ответ")

    # Verify
    assert result is None

    # Verify no database operations were performed beyond the initial find_one
    assert mock_mongo_client.database.quiz_states.find_one.call_count == 1
    mock_mongo_client.database.users.find_one.assert_not_called()
    mock_mongo_client.database.bank.find_one.assert_not_called()
    mock_mongo_client.database.users.update_one.assert_not_called()
    mock_mongo_client.database.bank.update_one.assert_not_called()
    mock_mongo_client.database.transactions.insert_one.assert_not_called()
    mock_mongo_client.database.tickets.insert_one.assert_not_called()
    mock_mongo_client.database.quiz_states.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_generate_summary(quiz_service, mock_mongo_client):
    """Тест генерации итогов викторины."""
    # Setup
    chat_id = 123

    # Mock quiz state with stats
    quiz_state = {
        "stats": {
            "total_questions": 5,
            "total_coins": 500,
            "total_tickets": 5,
            "winners": {
                "111": {"name": "Alice", "wins": 3, "coins": 300},
                "222": {"name": "Bob", "wins": 2, "coins": 200}
            }
        }
    }
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    summary = await quiz_service.generate_summary(chat_id)

    # Verify
    assert "Итоги викторины" in summary
    assert "Вопросов: 5" in summary
    assert "Монет: 500" in summary
    assert "Билетов: 5" in summary
    assert "Топ победителей" in summary
    assert "1. Alice (3)" in summary
    assert "2. Bob (2)" in summary


@pytest.mark.asyncio
async def test_generate_summary_no_winners(quiz_service, mock_mongo_client):
    """Тест генерации итогов когда нет победителей."""
    # Setup
    chat_id = 123

    # Mock quiz state with stats but no winners
    quiz_state = {
        "stats": {
            "total_questions": 5,
            "total_coins": 0,
            "total_tickets": 0,
            "winners": {}
        }
    }
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    summary = await quiz_service.generate_summary(chat_id)

    # Verify
    assert "Итоги викторины" in summary
    assert "Никто не выиграл." in summary