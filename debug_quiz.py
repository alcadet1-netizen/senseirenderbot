import asyncio
from unittest.mock import AsyncMock
from src.services.quiz_service import QuizService

async def test_debug():
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

    # Setup test data
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

    # Call the function
    result = await quiz_service.generate_summary(chat_id)
    print(f"Result: '{result}'")
    print(f"Expected to contain: 'Итоги викторины'")
    print(f"Actual result: {repr(result)}")

if __name__ == "__main__":
    asyncio.run(test_debug())