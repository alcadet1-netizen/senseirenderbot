import asyncio
from unittest.mock import AsyncMock
from src.services.quiz_service import QuizService

async def test_specific():
    # Setup mock
    mock_mongo_client = AsyncMock()
    db = AsyncMock()
    mock_mongo_client.database = db

    # Mock collections
    db.quiz_states = AsyncMock()
    db.quiz_questions = AsyncMock()
    db.users = AsyncMock()
    db.transactions = AsyncMock()
    db.bank = AsyncMock()
    db.tickets = AsyncMock()

    # Create service
    quiz_service = QuizService(mock_mongo_client)

    # Setup test data - exactly as in the test
    chat_id = 123
    quiz_state = {
        "stats": {
            "total_questions": 5,
            "total_coins": 0,
            "total_tickets": 0,
            "winners": {}
        }
    }
    print(f"Setting quiz_state to: {quiz_state}")
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    summary = await quiz_service.generate_summary(chat_id)

    print(f"Result: {repr(summary)}")
    print(f"Result length: {len(summary)}")

    expected_part = "Никто не выиграл."
    print(f"Expected part: {repr(expected_part)}")
    print(f"Expected part length: {len(expected_part)}")
    print(f"Is expected part in result? {expected_part in summary}")

    # Also check the full expected string from the test
    # The test checks: assert "Итоги викторины" in summary
    # and assert "Никто не выиграл." in summary
    print(f"'Итоги викторины' in summary: {'Итоги викторины' in summary}")

if __name__ == "__main__":
    asyncio.run(test_specific())