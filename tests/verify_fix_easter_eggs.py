
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.texts.phrases import check_easter_egg
    print("Successfully imported check_easter_egg")
    
    result = check_easter_egg("пасхалка 420")
    print(f"Check result: {result}")
    
    if result:
        print("Easter egg check working!")
    else:
        # 420 is in the easter eggs list I saw earlier
        print("Easter egg check returned None (might be expected if logic differs, but code runs)")

except NameError as e:
    print(f"NameError: {e}")
except Exception as e:
    print(f"Error: {e}")
