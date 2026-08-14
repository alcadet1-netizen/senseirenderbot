
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.services.achievement_service import AchievementService
from src.services.slots_service import SlotsService
from src.infra.database.models import User

async def test_economy_atomic():
    print("Testing Economy Atomicity...")

    # Mock Session and UOW
    mock_session = AsyncMock()
    mock_uow = MagicMock()
    mock_uow.session = mock_session
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.commit = AsyncMock()
    mock_uow.rollback = AsyncMock()

    # Mock Session Factory
    session_factory = MagicMock(return_value=mock_session)

    # Mock Container
    container = MagicMock()
    container.session_factory = session_factory
    container.redis = MagicMock()

    # --- Test 1: Achievement Service ---
    print("\n1. Testing Achievement Service...")
    service = AchievementService(session_factory)
    
    # Mock Repositories
    with patch("src.services.achievement_service.UserRepository") as MockUserRepo, \
         patch("src.services.achievement_service.AchievementRepository") as MockAchRepo, \
         patch("src.services.achievement_service.BankRepository") as MockBankRepo, \
         patch("src.services.achievement_service.TransactionRepository") as MockTxRepo, \
         patch("src.services.achievement_service.UnitOfWork", return_value=mock_uow):
        
        user_repo = MockUserRepo.return_value
        ach_repo = MockAchRepo.return_value
        bank_repo = MockBankRepo.return_value
        tx_repo = MockTxRepo.return_value

        user = User(id=1, coins=0, xp=0, messages_count=100, daily_streak=0, tickets=[], has_katana=False)
        user_repo.get_by_id = AsyncMock(return_value=user)
        ach_repo.get_user_achievement_ids = AsyncMock(return_value=[])
        ach_repo.unlock_achievement = AsyncMock(return_value=True)
        tx_repo.create = AsyncMock()
        
        # Test Case A: Bank has funds
        print("  Case A: Bank has funds")
        bank_repo.withdraw = AsyncMock()
        
        # We need to ensure "messages_100" or similar actually gives coins in ACHIEVEMENTS
        # If not, we won't see withdraw call.
        # Let's assume at least one achievement gives coins.
        # But if ACHIEVEMENTS is imported from constants, we should mock it or ensure it has coins.
        # For this test, we trust constants have some coin reward or we patch constants.
        
        with patch.dict("src.services.achievement_service.ACHIEVEMENTS", {
            "messages_100": {"name": "Test", "description": "Desc", "xp_reward": 100, "coin_reward": 50}
        }, clear=True):
            
            await service.check_and_unlock_achievements(1, {"messages_count": 100})
            
            if bank_repo.withdraw.called:
                print("  SUCCESS: Bank withdraw called.")
            else:
                print("  FAILURE: Bank withdraw NOT called.")
                # print(ach_repo.unlock_achievement.call_args_list)

            # Test Case B: Bank empty (raises Exception)
            print("  Case B: Bank empty")
            bank_repo.withdraw.side_effect = Exception("Insufficient funds")
            user.coins = 0 # reset
            ach_repo.get_user_achievement_ids.return_value = [] # Reset unlocked
            
            await service.check_and_unlock_achievements(1, {"messages_count": 100})
            
            if user.coins == 0:
                print("  SUCCESS: User coins not increased when bank empty.")
            else:
                print(f"  FAILURE: User coins increased to {user.coins} despite empty bank!")

    # --- Test 2: Slots Service ---
    print("\n2. Testing Slots Service...")
    slots = SlotsService(container)
    
    with patch("src.services.slots_service.UserRepository") as MockUserRepo, \
         patch("src.services.slots_service.BankRepository") as MockBankRepo, \
         patch("src.services.slots_service.TransactionRepository") as MockTxRepo, \
         patch("src.services.slots_service.UnitOfWork", return_value=mock_uow), \
         patch("src.services.slots_service.DistributedLock") as MockLock, \
         patch("random.random", return_value=0.2): # 0.2 < 0.33 -> Win
        
        user_repo = MockUserRepo.return_value
        bank_repo = MockBankRepo.return_value
        tx_repo = MockTxRepo.return_value
        
        user = User(id=1, coins=1000)
        user_repo.get_by_id = AsyncMock(return_value=user)
        bank_repo.deposit = AsyncMock()
        tx_repo.create = AsyncMock()
        
        lock_ctx = AsyncMock()
        MockLock.return_value.acquire.return_value = lock_ctx
        
        # Case A: Win with funds
        print("  Case A: Win with funds")
        bank_repo.withdraw = AsyncMock()
        
        await slots.play_slots(1, 100)
        
        # In SlotsService, deposit(fee) is called first, then withdraw(prize) if win.
        if bank_repo.withdraw.called:
            print("  SUCCESS: Bank withdraw called for slots win.")
        else:
            print("  FAILURE: Bank withdraw NOT called for slots win.")

        # Case B: Win but bank empty
        print("  Case B: Win but bank empty")
        bank_repo.withdraw.side_effect = Exception("Empty")
        user.coins = 1000 # Reset
        
        res = await slots.play_slots(1, 100)
        
        if res['prize'] == 0:
            print("  SUCCESS: Prize is 0 when bank empty.")
        else:
            print(f"  FAILURE: Prize is {res['prize']} despite empty bank.")

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(test_economy_atomic())
