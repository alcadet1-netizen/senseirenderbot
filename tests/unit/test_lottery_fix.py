import pytest
from unittest.mock import AsyncMock, MagicMock
import random

from src.services.lottery_service import LotteryService


@pytest.mark.asyncio
async def test_get_random_tickets_lottery_fix():
    """Test that the lottery service picks winners correctly."""
    # Setup mock mongo client and collections
    mock_mongo_client = AsyncMock()
    db = AsyncMock()
    mock_mongo_client.database = db

    # Mock collections
    # tickets.find is not awaited, so we use MagicMock for the collection and its find method
    db.tickets = MagicMock()
    # tickets.update_one is awaited, so we make it an AsyncMock
    db.tickets.update_one = AsyncMock()
    # users.find_one is awaited, so we make it an AsyncMock
    db.users.find_one = AsyncMock()

    # We'll make our mocks stateful to track changes
    # Initial ticket data
    stored_tickets = [
        {"_id": 1, "user_id": 99999, "code": "LOTT-1", "burned": False},
        {"_id": 2, "user_id": 99999, "code": "LOTT-2", "burned": False},
        {"_id": 3, "user_id": 88888, "code": "LOTT-3", "burned": False},  # Another user
    ]
    # Initial user data
    stored_users = {
        99999: {"id": 99999, "username": "lottery_test", "first_name": "Lottery"},
        88888: {"id": 88888, "username": "another", "first_name": "Another"},
    }

    # Setup mocks for tickets collection
    # We need to mock the find method to return a cursor object that has a to_list method
    def make_tickets_find():
        def side_effect(filter_dict):
            # We only support the filter {"burned": False} for this test
            if filter_dict == {"burned": False}:
                # Return a mock cursor that has a to_list method
                mock_cursor = MagicMock()
                # Filter the stored_tickets by the burned field
                filtered_tickets = [t for t in stored_tickets if t.get("burned") == False]
                # Make the to_list method an AsyncMock that returns the filtered tickets
                mock_cursor.to_list = AsyncMock(return_value=filtered_tickets)
                return mock_cursor
            # For other filters, return a cursor that returns an empty list
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            return mock_cursor
        return side_effect

    def make_tickets_update_one():
        def side_effect(filter_dict, update_dict, **kwargs):
            nonlocal stored_tickets
            # We expect the filter to be by _id and the update to set burned to True
            if "_id" in filter_dict and "$set" in update_dict and "burned" in update_dict["$set"]:
                ticket_id = filter_dict["_id"]
                # Find the ticket and update it
                for ticket in stored_tickets:
                    if ticket["_id"] == ticket_id:
                        ticket["burned"] = update_dict["$set"]["burned"]
                        break
            # Return a mock result
            result = AsyncMock()
            result.acknowledged = True
            result.matched_count = 1
            result.modified_count = 1 if ("$set" in update_dict) else 0
            result.upserted_id = None
            return result
        return side_effect

    # Setup mocks for users collection
    def make_users_find_one():
        def side_effect(query):
            user_id = query.get("id")
            if user_id in stored_users:
                return stored_users[user_id].copy()
            return None
        return side_effect

    # Apply the side effects
    db.tickets.find.side_effect = make_tickets_find()
    db.tickets.update_one.side_effect = make_tickets_update_one()
    db.users.find_one.side_effect = make_users_find_one()

    # Create service
    service = LotteryService(mock_mongo_client)

    # Execute
    winners = await service.run_lottery(winners_count=1)

    # Verify
    assert len(winners) == 1
    winner = winners[0]
    assert winner["user_id"] in [99999, 88888]  # Should be one of the users we set up
    assert winner["ticket_code"] in ["LOTT-1", "LOTT-2", "LOTT-3"]
    assert winner["username"] in ["lottery_test", "another"]
    assert "full_name" in winner

    # Verify that exactly one ticket was marked as burned
    burned_count = sum(1 for t in stored_tickets if t.get("burned") == True)
    assert burned_count == 1

    # Verify that the update_one was called on the tickets collection
    assert db.tickets.update_one.call_count == 1