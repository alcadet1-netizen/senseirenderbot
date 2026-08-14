import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.bot.handlers import referral
    print("Successfully imported src.bot.handlers.referral")
except Exception as e:
    print(f"Failed to import src.bot.handlers.referral: {e}")
    sys.exit(1)
