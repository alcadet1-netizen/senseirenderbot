import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.bot.handlers.duel_commands import router, cmd_duel, _duel_escrow_start
    print("✅ Module imported successfully")
except ImportError as e:
    print(f"❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print(f"Router name: {router.name}")
print(f"Command handler: {cmd_duel}")
print(f"Escrow function: {_duel_escrow_start}")
