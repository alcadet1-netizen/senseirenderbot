import asyncio
from unittest.mock import AsyncMock
from src.services.quiz_service import QuizService

async def test_equality():
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
    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Execute
    summary = await quiz_service.generate_summary(chat_id)

    # Check what we actually got
    expected = "Никто не выиграл"
    print(f"Expected string: {repr(expected)}")
    print(f"Actual string: {repr(summary)}")
    print(f"Expected in actual: {expected in summary}")
    print(f"Actual in expected: {summary in expected}")
    print(f"Length expected: {len(expected)}")
    print(f"Length actual: {len(summary)}")

    # Character by character comparison
    if len(expected) == len(summary):
        print("Strings have same length")
        for i in range(len(expected)):
            if expected[i] != summary[i]:
                print(f"Difference at position {i}: expected {repr(expected[i])} (U+{ord(expected[i]):04X}), got {repr(summary[i])} (U+{ord(summary[i]):04X})")
            else:
                print(f"Position {i}: both have {repr(expected[i])} (U+{ord(expected[i]):04X})")
    else:
        print("Strings have different length")

if __name__ == "__main__":
    asyncio.run(test_equality())