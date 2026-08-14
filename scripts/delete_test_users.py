import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Override DATABASE_URL for local execution if needed
# Assuming running on host where DB is exposed on localhost
os.environ["DATABASE_URL"] = "postgresql+asyncpg://sensei:sensei_pass_2024@localhost:5432/sensei_db"

from sqlalchemy import text, select
from src.infra.database.session import session_factory
from src.infra.database.models import User

async def main():
    target_usernames = ["TestMuteUser", "TestDailyUser", "test_economy_use"]
    print(f"Targeting specific users: {target_usernames}")
    print("Also targeting any user with 'test' in username (case insensitive)...")

    async with session_factory() as session:
        async with session.begin():
            # Find users to delete
            # We want specific users OR users starting with 'Test'/'test'
            # Let's just select all and filter or use SQL
            
            # Construct a query to find IDs
            # PostgreSQL ILIKE or similar. Assuming SQLite or Postgres.
            # Let's use generic logic if possible, or SQL.
            
            # Get all users first to be safe and see who we are deleting
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            users_to_delete = []
            for u in users:
                if u.username in target_usernames:
                    users_to_delete.append(u)
                elif u.username and "test" in u.username.lower():
                    users_to_delete.append(u)
            
            if not users_to_delete:
                print("No users found to delete.")
                return

            user_ids = [u.id for u in users_to_delete]
            usernames = [u.username for u in users_to_delete]
            
            print(f"Found {len(users_to_delete)} users to delete: {usernames}")
            
            if not user_ids:
                return

            # Convert list to string for SQL IN clause safely
            # or just iterate. Batch delete is better.
            ids_str = ",".join(map(str, user_ids))
            
            # Delete related data
            tables = [
                "daily_claims",
                "transactions",
                "tickets",
                "user_achievements",
                "muted_users"
                # "duels" is in-memory, no DB table
            ]
            
            for table in tables:
                # Check if table exists or just try delete
                # We'll try/except or just assume they exist based on previous knowledge
                try:
                    # Some tables might have user_id, some might have other FKs.
                    # transactions: user_id
                    # daily_claims: user_id
                    # tickets: user_id
                    # user_achievements: user_id
                    # muted_users: user_id
                    # duels: challenger_id, opponent_id
                    
                    if table == "duels":
                         await session.execute(text(f"DELETE FROM {table} WHERE challenger_id IN ({ids_str}) OR opponent_id IN ({ids_str})"))
                    else:
                        await session.execute(text(f"DELETE FROM {table} WHERE user_id IN ({ids_str})"))
                    print(f"Cleaned {table} for target users.")
                except Exception as e:
                    print(f"Skipping {table} (might not exist or error): {e}")

            # Delete users
            await session.execute(text(f"DELETE FROM users WHERE id IN ({ids_str})"))
            print("✅ Users deleted successfully.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
