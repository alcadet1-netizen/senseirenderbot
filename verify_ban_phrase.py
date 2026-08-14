
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.texts.phrases import get_random_ban_phrase

try:
    phrase = get_random_ban_phrase("Test User")
    print(f"Success: {phrase}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
