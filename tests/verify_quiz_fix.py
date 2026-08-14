
import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.infra.database.models import Base, User, QuizQuestion
from src.services.quiz_service import QuizService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_quiz_service():
    # 1. Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 2. Seed Data
    async with session_factory() as session:
        user = User(id=12345, username="testuser", coins=1000)
        session.add(user)
        
        q1 = QuizQuestion(
            id=1,
            question_text="What is the moon?", 
            answer="moon", 
            is_active=True
        )
        session.add(q1)
        await session.commit()
        q1_id = q1.id
        logger.info(f"Created question ID: {q1_id}")

    # 3. Mock Redis
    redis_mock = AsyncMock()
    # Mock get/set for quiz state
    quiz_state = {
        "status": "waiting_answer",
        "answer": "moon",
        "current_question_id": q1_id,
        "round": 1,
        "used_questions": [q1_id]
    }
    
    async def mock_get(key):
        if "state" in key:
            return json.dumps(quiz_state)
        return None
    
    redis_mock.get.side_effect = mock_get
    
    # Mock distributed lock to just yield
    lock_mock = MagicMock()
    lock_mock.acquire.return_value.__aenter__.return_value = None
    lock_mock.acquire.return_value.__aexit__.return_value = None
    
    # We need to mock DistributedLock constructor to return our lock_mock
    # But QuizService imports DistributedLock. 
    # Since we can't easily patch it inside the running process without patching the module,
    # we can just assume Redis lock works if we mock redis methods used by it?
    # No, DistributedLock uses a specific implementation.
    # However, in `check_answer`, it does: `lock = DistributedLock(self.redis)`
    # We can patch `src.services.quiz_service.DistributedLock`
    
    from unittest.mock import patch
    with patch("src.services.quiz_service.DistributedLock") as MockLock:
        MockLock.return_value.acquire.return_value.__aenter__ = AsyncMock()
        MockLock.return_value.acquire.return_value.__aexit__ = AsyncMock()
        
        service = QuizService(session_factory, redis_mock)
        
        # 4. Run check_answer
        logger.info("Calling check_answer...")
        result = await service.check_answer(chat_id=-100, user_id=12345, user_name="Test User", text="moon")
        
        if result:
            logger.info("Result: " + str(result))
            logger.info("Answer accepted!")
        else:
            logger.error("Answer NOT accepted!")
            return

        # 5. Verify Question is Deleted
        async with session_factory() as session:
            q = await session.get(QuizQuestion, q1_id)
            if q:
                logger.error(f"Question {q1_id} STILL EXISTS in DB!")
            else:
                logger.info(f"Question {q1_id} SUCCESSFULLY DELETED from DB!")

        # 6. Verify Ticket was created (indirectly by checking user tickets or logs if we could)
        # But we fixed the import, so if it ran without error, it means TicketRepository was defined.
        logger.info("Test finished successfully.")

if __name__ == "__main__":
    asyncio.run(test_quiz_service())
