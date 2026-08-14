
import sys
import os

# Add src to path
sys.path.insert(0, os.getcwd())

print("Attempting to import modules...")
try:
    from src.main import main
    from src.bot import create_bot
    from src.core.config import settings
    print("✅ Core imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("✅ Import check complete.")
