
import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from src.services.quiz_service import QuizService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_quiz_summary():
    # 1. Mock Redis with Stats
    redis_mock = AsyncMock()
    
    chat_id = 123
    
    # State with stats
    quiz_state = {
        "status": "running",
        "stats": {
            "total_questions": 10,
            "total_coins": 1000,
            "total_tickets": 10,
            "winners": {
                "111": {"name": "Alice", "wins": 5, "coins": 500},
                "222": {"name": "Bob", "wins": 3, "coins": 300},
                "333": {"name": "Charlie", "wins": 2, "coins": 200}
            }
        }
    }
    
    async def mock_get(key):
        if f"quiz:state:{chat_id}" in key:
            return json.dumps(quiz_state)
        return None
    
    redis_mock.get.side_effect = mock_get
    
    # Mock session factory (not used for generate_summary but required for init)
    session_factory = MagicMock()
    
    service = QuizService(session_factory, redis_mock)
    
    # 2. Call generate_summary
    logger.info("Generating summary...")
    summary = await service.generate_summary(chat_id)
    
    # 3. Print and Verify
    logger.info(f"Summary Output:\n{summary}")
    
    if "Итоги викторины" in summary and "Alice" in summary and "Bob" in summary:
        logger.info("✅ Summary generated successfully and contains expected data.")
    else:
        logger.error("❌ Summary verification failed!")

if __name__ == "__main__":
    asyncio.run(test_quiz_summary())
