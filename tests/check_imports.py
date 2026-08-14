
import sys
import os
try:
    print("Checking imports...")
    import aiogram
    print(f"Aiogram version: {aiogram.__version__}")
    from src.bot.middlewares.throttling import ThrottlingMiddleware
    print("ThrottlingMiddleware imported successfully")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
