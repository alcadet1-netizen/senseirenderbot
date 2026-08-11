import asyncio
import sys
import os
from sqlalchemy import select, delete, or_

# Add project root to python path
sys.path.append(os.getcwd())

from src.infra.database.session import session_factory
from src.infra.database.models.user import User

async def delete_test_users():
    async with session_factory() as session:
        # Find users to delete
        stmt = select(User).where(
            or_(
                User.username.in_(['KUser_0', 'KUser_1']),
                User.username.like('KUser_%')
            )
        )
        
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            print("No users found matching the criteria.")
            return

        print(f"Found {len(users)} users to delete:")
        for user in users:
            print(f"- {user.username} (ID: {user.id})")

        # Delete users
        delete_stmt = delete(User).where(User.id.in_([u.id for u in users]))
        await session.execute(delete_stmt)
        await session.commit()
        
        print("Deletion complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(delete_test_users())
