# Debug the failing upgrade_katana test
import asyncio
from unittest.mock import AsyncMock
from src.services.economy_service import EconomyService

async def test_debug():
    # Create mock similar to the test
    mock_mongo_client = AsyncMock()

    # Mock database
    db = AsyncMock()
    mock_mongo_client.database = db

    # Mock collections
    db.users = AsyncMock()
    db.bank = AsyncMock()
    db.transactions = AsyncMock()

    # Create service
    economy_service = EconomyService(mock_mongo_client)

    # Prepare mock data
    mock_user = {
        "id": 126,
        "username": "upgrader",
        "coins": 2000.0,
        "has_katana": True,
        "katana_length": 10.0,
        "last_katana_up": None
    }

    # We'll make our mocks stateful to track changes
    stored_user = mock_user.copy()
    stored_bank_balance = 5000.0

    # Setup mocks - return values directly (not coroutines) for find operations
    def make_find_one_return_value(collection_name):
        def side_effect(query):
            print(f"find_one called on {collection_name} with query: {query}")
            if collection_name == "users":
                result = stored_user.copy() if stored_user else None
                print(f"  returning user: {result}")
                return result
            elif collection_name == "bank":
                result = {"balance": stored_bank_balance} if stored_bank_balance is not None else None
                print(f"  returning bank: {result}")
                return result
            return None
        return side_effect

    # Setup mocks for update operations - return AsyncMock result
    def make_update_one_return_value(collection_name):
        def side_effect(query, update_dict, **kwargs):
            nonlocal stored_user, stored_bank_balance
            print(f"update_one called on {collection_name}")
            print(f"  query: {query}")
            print(f"  update: {update_dict}")
            if collection_name == "users" and query.get("id") == 126:
                if "$inc" in update_dict:
                    if "coins" in update_dict["$inc"]:
                        stored_user["coins"] += update_dict["$inc"]["coins"]
                        print(f"  increased coins by {update_dict['$inc']['coins']}, new total: {stored_user['coins']}")
                if "$set" in update_dict:
                    if "has_katana" in update_dict["$set"]:
                        stored_user["has_katana"] = update_dict["$set"]["has_katana"]
                        print(f"  set has_katana to {stored_user['has_katana']}")
                    if "katana_length" in update_dict["$set"]:
                        stored_user["katana_length"] = update_dict["$set"]["katana_length"]
                        print(f"  set katana_length to {stored_user['katana_length']}")
                    if "last_katana_up" in update_dict["$set"]:
                        stored_user["last_katana_up"] = update_dict["$set"]["last_katana_up"]
                        print(f"  set last_katana_up to {stored_user['last_katana_up']}")
            elif collection_name == "bank" and query.get("_id") == "single":
                if "$set" in update_dict and "balance" in update_dict["$set"]:
                    stored_bank_balance = update_dict["$set"]["balance"]
                    print(f"  set bank balance to {stored_bank_balance}")
            # Return a mock result object
            result = AsyncMock()
            result.acknowledged = True
            result.matched_count = 1
            result.modified_count = 1 if ("$set" in update_dict or "$inc" in update_dict) else 0
            result.upserted_id = None
            print(f"  returning result: matched={result.matched_count}, modified={result.modified_count}")
            return result
        return side_effect

    # Apply the side effects
    mock_mongo_client.database.users.find_one.side_effect = make_find_one_return_value("users")
    mock_mongo_client.database.bank.find_one.side_effect = make_find_one_return_value("bank")
    mock_mongo_client.database.users.update_one.side_effect = make_update_one_return_value("users")
    mock_mongo_client.database.bank.update_one.side_effect = make_update_one_return_value("bank")
    mock_mongo_client.database.transactions.insert_one = AsyncMock()

    # Execute
    print("\n--- Executing upgrade_katana ---")
    result = await economy_service.upgrade_katana(126)
    print(f"Result: {result}")

    # Verify
    print(f"\nExpected is_upgraded: True")
    print(f"Actual is_upgraded: {result.get('is_upgraded') if result else 'None'}")

if __name__ == "__main__":
    asyncio.run(test_debug())