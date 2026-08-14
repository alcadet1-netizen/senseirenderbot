
import asyncio
import sys
from src.bot import create_bot
from src.bot.custom_bot import AntiSpamBot
from aiogram import Bot

async def main():
    try:
        bot = create_bot()
        print(f"Bot instance: {bot}")
        print(f"Is instance of AntiSpamBot: {isinstance(bot, AntiSpamBot)}")
        print(f"Is instance of Bot: {isinstance(bot, Bot)}")
        
        if isinstance(bot, AntiSpamBot):
            print("Verification SUCCESS")
        else:
            print("Verification FAILED: Bot is not AntiSpamBot")
            sys.exit(1)
            
    except Exception as e:
        print(f"Verification ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
