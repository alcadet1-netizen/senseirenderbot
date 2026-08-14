
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select, text
from src.core.config import settings
from src.core.container import Container
from src.infra.database import session_factory, engine
from src.infra.redis import redis_client
from src.infra.database.models import Base, User, Transaction, TransactionType, Achievement
from src.infra.database.uow import UnitOfWork

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_economy_notifications():
    """Verify economy notifications and achievement unlocking."""
    logger.info("🧪 Starting economy verification...")

    # Connect to Redis
    redis = await redis_client.connect()
    
    # Create Container
    container = Container(
        settings=settings,
        session_factory=session_factory,
        redis=redis,
    )
    
    # Initialize DB (create tables if not exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed achievements
    await container.achievement_service.seed_achievements()

    uow = UnitOfWork(session_factory)
    test_user_id = 123456789
    
    # 1. Create/Reset Test User
    logger.info("👤 Creating/Resetting test user...")
    async with uow:
        # Delete existing test user transactions and achievements
        await uow.session.execute(
            text("DELETE FROM transactions WHERE user_id = :uid"), 
            {"uid": test_user_id}
        )
        await uow.session.execute(
            text("DELETE FROM user_achievements WHERE user_id = :uid"), 
            {"uid": test_user_id}
        )
        await uow.session.execute(
            text("DELETE FROM users WHERE id = :uid"), 
            {"uid": test_user_id}
        )
        
        user = User(
            id=test_user_id,
            username="test_economy_user",
            first_name="Test",
            coins=0,
            xp=0,
            messages_count=0
        )
        uow.session.add(user)
        await uow.commit()

    # 2. Simulate User Activity (Gain Coins)
    logger.info("💰 Simulating coin gain (10,000 coins)...")
    async with uow:
        user = await uow.session.get(User, test_user_id)
        user.coins = 10000  # Threshold for 'rich_10000' achievement
        await uow.commit()

    # 3. Check Achievements (Simulate Middleware)
    logger.info("🏆 Checking achievements...")
    unlocked = await container.achievement_service.check_and_unlock_achievements(
        user_id=test_user_id,
        context={
            "coins": 10000,
            "xp": 0,
            "messages_count": 0
        }
    )

    logger.info(f"✨ Unlocked achievements: {[a['id'] for a in unlocked]}")

    # 4. Verify Results
    assert len(unlocked) > 0, "❌ No achievements unlocked!"
    
    rich_10000_unlocked = any(a['id'] == 'rich_10000' for a in unlocked)
    assert rich_10000_unlocked, "❌ 'rich_10000' achievement not unlocked!"

    # 5. Verify Transaction
    logger.info("🔍 Verifying transaction creation...")
    async with uow:
        result = await uow.session.execute(
            select(Transaction)
            .where(Transaction.user_id == test_user_id)
            .where(Transaction.type == TransactionType.ACHIEVEMENT_REWARD.value)
        )
        transactions = result.scalars().all()
        
        logger.info(f"📝 Found {len(transactions)} achievement transactions.")
        assert len(transactions) > 0, "❌ No achievement reward transaction found!"
        
        for tx in transactions:
            logger.info(f"   - Tx ID: {tx.id}, Type: {tx.type}, Coins: {tx.coins_change}, Desc: {tx.description}")

    logger.info("✅ Economy and Achievement Notifications Verified Successfully!")

    # Cleanup
    await redis_client.disconnect()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_economy_notifications())
