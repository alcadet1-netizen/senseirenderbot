
import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Use the same DB URL as in .env but with localhost
DATABASE_URL = "postgresql+asyncpg://sensei:sensei_pass_2024@localhost:5432/sensei_db"

async def check_columns():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("Checking 'users' table columns...")
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"
        ))
        columns = [row[0] for row in result.fetchall()]
        print(f"Found columns: {columns}")
        
        if "wins" in columns and "losses" in columns:
            print("✅ SUCCESS: 'wins' and 'losses' columns exist.")
        else:
            print("❌ FAILURE: 'wins' or 'losses' columns are MISSING.")
            
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_columns())
