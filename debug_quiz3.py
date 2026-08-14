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
    print(f"quiz_state type: {type(quiz_state)}")
    print(f"bool(quiz_state): {bool(quiz_state)}")
    print(f"quiz_state is None: {quiz_state is None}")
    print(f"len(quiz_state): {len(quiz_state)}")

    mock_mongo_client.database.quiz_states.find_one.return_value = quiz_state

    # Let's manually call what generate_summary does
    state = await mock_mongo_client.database.quiz_states.find_one({"chat_id": chat_id})
    print(f"After find_one, state: {state}")
    print(f"After find_one, state type: {type(state)}")
    print(f"After find_one, bool(state): {bool(state)}")
    print(f"After find_one, state is None: {state is None}")

    if not state:
        print("state is falsy - would return 'Викторина не найдена.'")
    else:
        print("state is truthy - would continue processing")

        # Continue with the rest of the function
        stats = state.get("stats", {
            "total_questions": 0,
            "total_coins": 0,
            "total_tickets": 0,
            "winners": {}
        })
        print(f"stats: {stats}")

        total_questions = stats.get("total_questions", 0)
        total_coins = stats.get("total_coins", 0)
        total_tickets = stats.get("total_tickets", 0)
        winners = stats.get("winners", {})
        print(f"winners: {winners}")
        print(f"bool(winners): {bool(winners)}")

        if not winners:
            print("Would return 'Никто не выиграл.'")
        else:
            print("Would continue to build summary")

if __name__ == "__main__":
    asyncio.run(test_debug())