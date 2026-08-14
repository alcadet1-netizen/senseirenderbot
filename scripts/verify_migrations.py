import asyncio
import sys
import os
import logging

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup basic logging
logging.basicConfig(level=logging.INFO)

from src.infra.database.migrations.run import run_migrations

async def main():
    print("🚀 Starting migration verification...")
    try:
        await run_migrations()
        print("✅ Migrations verified successfully")
    except ConnectionRefusedError:
        print("⚠️ Connection refused (expected if DB is not running locally)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
