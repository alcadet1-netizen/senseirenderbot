
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    from src.bot.handlers import music
    print("Successfully imported src.bot.handlers.music")
except Exception as e:
    print(f"Failed to import src.bot.handlers.music: {e}")
    sys.exit(1)
