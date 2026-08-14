import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    from src.infra.database.models import User
    print("User imported successfully")
except Exception as e:
    print(f"Error importing User: {e}")

try:
    from src.infra.database.session import session_factory
    print("session_factory imported successfully")
except Exception as e:
    print(f"Error importing session_factory: {e}")
