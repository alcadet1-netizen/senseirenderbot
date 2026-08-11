import asyncio
import sys
import os
from sqlalchemy import select, or_

# Add project root to python path
sys.path.append(os.getcwd())

from src.infra.database.session import session_factory
from src.infra.database.models.user import User

async def verify_deletion():
    async with session_factory() as session:
        # Find users
        stmt = select(User).where(
            or_(
                User.username.in_(['KUser_0', 'KUser_1']),
                User.username.like('KUser_%')
            )
        )
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            print("Verification successful: No users found.")
        else:
            print(f"Verification failed: Found {len(users)} users:")
            for user in users:
                print(f"- {user.username} (ID: {user.id})")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_deletion())
