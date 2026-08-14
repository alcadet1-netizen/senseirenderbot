import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from src.services.duel_service import DuelService, Duel


@pytest.mark.asyncio
async def test_duel_winner_gets_xp_and_katana_and_loser_loses_katana():
    """Test that winner gets XP and katana upgrade, loser loses katana."""
    # Setup mock mongo client and collections
    mock_mongo_client = AsyncMock()
    db = AsyncMock()
    mock_mongo_client.database = db

    # Mock collections
    db.users = AsyncMock()
    db.transactions = AsyncMock()

    # We'll make our mocks stateful to track changes
    # Initial user data
    winner_id = 1001
    loser_id = 1002

    winner_start_xp = 10
    winner_start_katana = 1.00
    loser_start_katana = 0.50

    winner_coins_before = 0.0
    loser_coins_before = 0.0

    # Track state for users
    stored_users = {
        winner_id: {
            "id": winner_id,
            "username": "winner",
            "first_name": "Winner",
            "xp": winner_start_xp,
            "coins": winner_coins_before,
            "has_katana": True,
            "katana_length": winner_start_katana,
            "wins": 0,
            "losses": 0,
        },
        loser_id: {
            "id": loser_id,
            "username": "loser",
            "first_name": "Loser",
            "xp": 0,  # loser starts with 0 XP in the test
            "coins": loser_coins_before,
            "has_katana": True,
            "katana_length": loser_start_katana,
            "wins": 0,
            "losses": 0,
        }
    }

    # Track state for transactions
    stored_transactions = []

    # Setup mocks for users collection
    def make_find_one_return_value(collection_name):
        def side_effect(query):
            if collection_name == "users":
                user_id = query.get("id")
                if user_id in stored_users:
                    return stored_users[user_id].copy()
                return None
            return None
        return side_effect

    def make_update_one_return_value(collection_name):
        def side_effect(query, update_dict, **kwargs):
            if collection_name == "users":
                user_id = query.get("id")
                if user_id in stored_users:
                    if "$set" in update_dict:
                        stored_users[user_id].update(update_dict["$set"])
                    if "$inc" in update_dict:
                        for key, value in update_dict["$inc"].items():
                            stored_users[user_id][key] = stored_users[user_id].get(key, 0) + value
            elif collection_name == "transactions":
                # For insert, we just record the transaction
                if "tx_type" in update_dict.get("$set", {}):  # Actually, insert_one doesn't use update_dict this way
                    pass
            # Return a mock result
            result = AsyncMock()
            result.acknowledged = True
            if collection_name == "users":
                result.matched_count = 1
                result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
            elif collection_name == "transactions":
                result.inserted_id = f"tx_{len(stored_transactions)}"
            return result
        return side_effect

    def make_insert_one_return_value(collection_name):
        def side_effect(document):
            if collection_name == "transactions":
                stored_transactions.append(document)
            result = AsyncMock()
            result.acknowledged = True
            result.inserted_id = f"tx_{len(stored_transactions)-1}" if collection_name == "transactions" else None
            return result
        return side_effect

    # Apply the side effects
    db.users.find_one.side_effect = make_find_one_return_value("users")
    db.users.update_one.side_effect = make_update_one_return_value("users")
    db.transactions.insert_one.side_effect = make_insert_one_return_value("transactions")

    # Create mock container
    container = SimpleNamespace()
    container.mongo_client = mock_mongo_client
    # We also need to mock user_service and economy_service if they are used, but in _finish_duel they are not.
    # However, DuelService expects them. Let's set them to MagicMock to avoid AttributeError.
    container.user_service = MagicMock()
    container.economy_service = MagicMock()

    # Create service
    service = DuelService(container)

    # Create duel
    duel = Duel(
        id=1,
        challenger_id=winner_id,
        opponent_id=loser_id,
        bet=300,
        chat_id=-100,
        bot=MagicMock(),  # bot is not used in _finish_duel for the checks we care about
        container=container,
    )
    # Set the duel as accepted and finished? Actually, _finish_duel sets finished=True.
    # We just need to set the hits to simulate a win.
    duel.hits[winner_id] = 2  # Winner needs 2 hits to win (as per win condition in _resolve_round)
    duel.hits[loser_id] = 0

    # Execute
    await service._finish_duel(duel, winner_id, "test")

    # Verify winner
    winner_user = stored_users[winner_id]
    assert winner_user["xp"] == winner_start_xp + 50
    assert winner_user["has_katana"] is True
    # Katana length should increase by 0.01 if they had katana
    assert winner_user["katana_length"] == round(winner_start_katana + 0.01, 2)
    assert winner_user["wins"] == 1

    # Verify loser
    loser_user = stored_users[loser_id]
    assert loser_user["has_katana"] is True
    # Katana length should decrease by 0.01
    assert loser_user["katana_length"] == round(loser_start_katana - 0.01, 2)
    assert loser_user["losses"] == 1

    # Verify transactions
    # We expect at least:
    # 1. Transaction for winner's XP (duel_win with xp_change=50)
    # 2. Transaction for winner's katana update? Actually, katana update is done via $set in users, not a transaction.
    # 3. Transaction for loser's loss? (duel_loss with xp_change=0)
    # 4. Transaction for the bet payout? (duel_bet_payout with coins_change=600) because bet=300, so 2*bet=600
    # But note: in the current _finish_duel, we create two transactions for XP (winner and loser) and one for the bet payout.
    # Let's check the stored_transactions.

    # Print for debugging
    print(f"Number of transactions: {len(stored_transactions)}")
    for i, tx in enumerate(stored_transactions):
        print(f"Tx {i}: {tx}")

    # We expect at least 3 transactions: winner XP, loser loss, bet payout
    assert len(stored_transactions) >= 3

    # Check for winner XP transaction
    winner_xp_tx = None
    bet_payout_tx = None
    loser_loss_tx = None
    for tx in stored_transactions:
        if tx.get("user_id") == winner_id and tx.get("tx_type") == "duel_win" and tx.get("xp_change") == 50:
            winner_xp_tx = tx
        if tx.get("user_id") == winner_id and tx.get("tx_type") == "duel_bet_payout":
            bet_payout_tx = tx
        if tx.get("user_id") == loser_id and tx.get("tx_type") == "duel_loss":
            loser_loss_tx = tx

    assert winner_xp_tx is not None, "Winner XP transaction not found"
    assert bet_payout_tx is not None, "Bet payout transaction not found"
    assert loser_loss_tx is not None, "Loser loss transaction not found"

    # Check bet payout amount
    assert bet_payout_tx.get("coins_change") == float(duel.bet * 2)