import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infra.database.models import TransactionType
from src.domain.entities.transaction import TransactionTypeEnum

def verify():
    print("🚀 Verifying TransactionType...")
    
    try:
        print(f"✅ GAME_WIN: {TransactionType.GAME_WIN}")
        print(f"✅ QUIZ_WIN: {TransactionType.QUIZ_WIN}")
        print(f"✅ CASINO_BET: {TransactionType.CASINO_BET}")
    except AttributeError as e:
        print(f"❌ TransactionType missing attribute: {e}")
        
    print("\n🚀 Verifying TransactionTypeEnum...")
    try:
        print(f"✅ GAME_WIN: {TransactionTypeEnum.GAME_WIN}")
        print(f"✅ QUIZ_WIN: {TransactionTypeEnum.QUIZ_WIN}")
        print(f"✅ CASINO_BET: {TransactionTypeEnum.CASINO_BET}")
    except AttributeError as e:
        print(f"❌ TransactionTypeEnum missing attribute: {e}")

if __name__ == "__main__":
    verify()
