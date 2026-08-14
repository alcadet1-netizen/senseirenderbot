import asyncio
import pytest
from unittest.mock import AsyncMock
from src.services.quiz_service import QuizService

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
async def test_generate_summary_no_winners_debug(quiz_service, mock_mongo_client):
    """Тест генерации итогов когда нет победителей - DEBUG VERSION."""
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
    print(f"Setting up mock to return: {quiz_state}")
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Let's also add a side effect to see what's being called
    original_method = mock_mongo_client.database.quiz_states.find_one
    call_count = 0

    async def tracked_find_one(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        print(f"find_one call #{call_count}: args={args}, kwargs={kwargs}")
        result = await original_method(*args, **kwargs)
        print(f"find_one call #{call_count} returning: {result}")
        return result

    mock_mongo_client.database.quiz_states.find_one = tracked_find_one

    # Execute
    print("Calling generate_summary...")
    summary = await quiz_service.generate_summary(chat_id)
    print(f"generate_summary returned: {repr(summary)}")
    print(f"find_one was called {call_count} times")

    # Verify
    print(f"Checking if 'Итоги викторины' in summary: {'Итоги викторины' in summary}")
    print(f"Checking if 'Никто не выиграл' in summary: {'Никто не выиграл' in summary}")

if __name__ == "__main__":
    # This won't work as a standalone script because of pytest fixtures
    # But let's try to run it manually
    asyncio.run(test_generate_summary_no_winners_debug(QuizService(AsyncMock()), AsyncMock()))