import sys
import os
sys.path.append(os.getcwd())

print("Importing Visuals...")
try:
    from src.core.visuals import Visuals
    print("Visuals imported successfully.")
except Exception as e:
    print(f"Error importing Visuals: {e}")
    import traceback
    traceback.print_exc()

print("Importing slots handler...")
try:
    from src.bot.handlers import slots
    print("Slots handler imported successfully.")
except Exception as e:
    print(f"Error importing slots: {e}")
    import traceback
    traceback.print_exc()
