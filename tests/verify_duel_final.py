
import sys
import os

# Add src to path
sys.path.append('/app')

try:
    from src.bot.handlers import duel_commands
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
