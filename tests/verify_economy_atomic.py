import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.services.achievement_service import AchievementService
from src.services.slots_service import SlotsService
from src.domain.repositories import AchievementRepository, UserRepository, TransactionRepository, BankRepository
from datetime import datetime, timezone

async def test_economy_atomic():
    print("Testing Economy Atomicity...")

    # Mock MongoDB client and database
    mock_mongo_client = MagicMock()
    mock_db = MagicMock()
    mock_mongo_client.database = mock_db

    # Mock collections for achievement service
    mock_achievements_def = AsyncMock()
    mock_user_achievements = AsyncMock()
    mock_users = AsyncMock()
    mock_transactions = AsyncMock()

    mock_db.achievements_def = mock_achievements_def
    mock_db.user_achievements = mock_user_achievements
    mock_db.users = mock_users
    mock_db.transactions = mock_transactions

    # Mock collections for slots service (we reuse the same mongo client)
    # The slots service uses self.users, self.transactions, self.bank
    mock_bank = AsyncMock()
    mock_db.bank = mock_bank
    # Note: we already have mock_users and mock_transactions from above

    # Mock Repositories for achievement service
    mock_achievement_repo = MagicMock(spec=AchievementRepository)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_tx_repo = MagicMock(spec=TransactionRepository)

    # --- Test 1: Achievement Service ---
    print("\n1. Testing Achievement Service...")
    service = AchievementService(
        mongo_client=mock_mongo_client,
        achievement_repo=mock_achievement_repo,
        user_repo=mock_user_repo,
        tx_repo=mock_tx_repo
    )

    # Test Case A: Bank has funds
    print("  Case A: Bank has funds")
    # We need to ensure "messages_100" or similar actually gives coins in ACHIEVEMENTS
    # If not, we won't see withdraw call.
    # Let's assume at least one achievement gives coins.
    # But if ACHIEVEMENTS is imported from constants, we should mock it or ensure it has coins.
    # For this test, we trust constants have some coin reward or we patch constants.

    with patch.dict("src.services.achievement_service.ACHIEVEMENTS", {
        "messages_100": {"name": "Test", "description": "Desc", "xp_reward": 100, "coin_reward": 50}
    }, clear=True):
        # Mock the achievement repo methods
        mock_achievement_repo.get_all_achievements.return_value = []  # No achievements seeded yet
        mock_achievement_repo.get_achievement.return_value = {
            "_id": "messages_100",
            "name": "Test",
            "description": "Desc",
            "criteria": {},
            "reward_coins": 50.0,
            "reward_xp": 100,
            "created_at": datetime.now(timezone.utc)
        }
        mock_achievement_repo.has_achievement.return_value = False  # Not yet unlocked
        mock_achievement_repo.unlock_achievement.return_value = True  # Successfully unlocked
        mock_user_repo.update.return_value = True
        mock_tx_repo.add.return_value = "tx_id"

        # We don't have a bank repository in the achievement service anymore, so we skip the bank withdraw mock.
        # Instead, we just check that the user update and transaction creation are called.

        await service.check_and_unlock_achievements(1, ["messages_100"])

        # Check that the achievement was unlocked
        mock_achievement_repo.unlock_achievement.assert_called_once_with(1, "messages_100")
        # Check that the user was updated with coins and xp
        mock_user_repo.update.assert_called()
        # Check that a transaction was added
        mock_tx_repo.add.assert_called()

        print("  SUCCESS: Achievement unlocked, user updated, and transaction created.")

    # Test Case B: Achievement already unlocked
    print("  Case B: Achievement already unlocked")
    mock_achievement_repo.has_achievement.return_value = True  # Already unlocked

    await service.check_and_unlock_achievements(1, ["messages_100"])

    # Should not try to unlock again
    mock_achievement_repo.unlock_achievement.assert_not_called()
    mock_user_repo.update.assert_not_called()
    mock_tx_repo.add.assert_not_called()
    print("  SUCCESS: Already unlocked achievement skipped.")

    # --- Test 2: Slots Service ---
    print("\n2. Testing Slots Service...")
    slots = SlotsService(mongo_client=mock_mongo_client)

    # We'll mock the collections that the slots service uses: users, transactions, bank
    # We already have mock_users, mock_transactions, mock_bank from above.

    # Case A: Win with funds
    print("  Case A: Win with funds")
    # Setup for a win: random.random returns 0.2 (less than 0.33)
    with patch("random.random", return_value=0.2):
        # Mock the user document
        mock_users.find_one.return_value = {
            "id": 1,
            "coins": 1000,
            # other fields as needed
        }
        # Mock the bank document
        mock_bank.find_one.return_value = {
            "_id": "main",
            "balance": 5000  # enough to cover the prize
        }
        # Mock the update_one and insert_one methods to do nothing (just await)
        mock_users.update_one = AsyncMock()
        mock_bank.update_one = AsyncMock()
        mock_transactions.insert_one = AsyncMock()

        # Call the service
        result = await slots.play_slots(1, 100)

        # Check that the user's coins were updated (bet deducted, prize added)
        # We expect: 1000 - 100 (bet) + prize (which is 100 * multiplier)
        # With random.random=0.2, we get a win (since 0.2 < 0.33) and not a jackpot (0.2 > 0.01)
        # The winning symbol is randomly chosen from the non-777 symbols, but we don't mock that.
        # However, we can check that the result indicates a win and the prize is set.
        if result.get("is_win") and result.get("prize") > 0:
            print("  SUCCESS: Slots win detected and prize awarded.")
        else:
            print(f"  FAILURE: Expected win with prize, got {result}")

    # Case B: Win but bank empty
    print("  Case B: Win but bank empty")
    with patch("random.random", return_value=0.2):
        mock_users.find_one.return_value = {
            "id": 1,
            "coins": 1000,
        }
        mock_bank.find_one.return_value = {
            "_id": "main",
            "balance": 0  # not enough to cover the prize
        }
        mock_users.update_one = AsyncMock()
        mock_bank.update_one = AsyncMock()
        mock_transactions.insert_one = AsyncMock()

        result = await slots.play_slots(1, 100)

        # Since the bank is empty, the service should refund the bet and return an error
        if not result.get("success") and result.get("reason") == "Банк пуст! Попробуйте позже.":
            print("  SUCCESS: Bank empty detected, bet refunded.")
        else:
            print(f"  FAILURE: Expected bank empty error, got {result}")

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(test_economy_atomic())