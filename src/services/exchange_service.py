"""
💱 Сервис обмена валют.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from src.core.config import settings
from src.core.constants import EXCHANGE_COINS_TO_TICKET, EXCHANGE_TICKET_TO_COINS
from src.core.exceptions import InsufficientFundsError, InsufficientTicketsError
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class ExchangeService:
    """Сервис обмена валют."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # {_id: "main", balance: X}
        self.tickets = self.db.tickets  # For ticket tracking

    async def coins_to_ticket(self, user_id: int) -> dict:
        """Обменять монеты на билет. 3000 монет → 1 билет"""
        # Get user
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        user_coins = user.get("coins", 0)
        if user_coins < EXCHANGE_COINS_TO_TICKET:
            raise InsufficientFundsError(EXCHANGE_COINS_TO_TICKET, user_coins)

        # Perform exchange in a logical transaction (individual operations)
        try:
            # Deduct coins from user
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": -EXCHANGE_COINS_TO_TICKET}}
            )

            # Deposit coins to bank
            await self.bank.update_one(
                {"_id": "main"},
                {"$inc": {"balance": EXCHANGE_COINS_TO_TICKET}},
                upsert=True
            )

            # Create ticket
            # Find next ticket ID
            last_ticket = await self.tickets.find_one(sort=[("_id", -1)])
            next_id = (last_ticket.get("_id", 0) + 1) if last_ticket else 1

            ticket_doc = {
                "_id": next_id,
                "user_id": user_id,
                "code": f"TICKET-{next_id:08d}",  # Simple ticket code
                "created_at": datetime.now(timezone.utc),
                "burned": False
            }
            await self.tickets.insert_one(ticket_doc)

            # Create transaction record
            tx_doc = {
                "user_id": user_id,
                "tx_type": "exchange_in",
                "coins_change": -EXCHANGE_COINS_TO_TICKET,
                "description": f"Exchange: {EXCHANGE_COINS_TO_TICKET} coins → 1 ticket",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)

            return {
                "success": True,
                "direction": "coins_to_ticket",
                "coins_spent": EXCHANGE_COINS_TO_TICKET,
                "ticket_code": ticket_doc["code"],
                "new_coins_balance": user_coins - EXCHANGE_COINS_TO_TICKET,
            }

        except Exception as e:
            logger.error(f"Error in coins_to_ticket: {e}")
            return {"success": False, "error": "Internal error"}

    async def ticket_to_coins(self, user_id: int) -> dict:
        """Обменять билет на монеты. 1 билет → 2600 монет"""
        # Get user
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        # Check if user has any tickets
        user_tickets = await self.tickets.count_documents({
            "user_id": user_id,
            "burned": False
        })
        if user_tickets < 1:
            raise InsufficientTicketsError(1, user_tickets)

        # Check bank balance
        bank_doc = await self.bank.find_one({"_id": "main"})
        bank_balance = bank_doc.get("balance", 0) if bank_doc else 0
        if bank_balance < EXCHANGE_TICKET_TO_COINS:
            return {"success": False, "error": "Банк временно пуст"}

        try:
            # Find and burn a user's ticket (mark as burned)
            ticket = await self.tickets.find_one_and_update(
                {
                    "user_id": user_id,
                    "burned": False
                },
                {
                    "$set": {
                        "burned": True,
                        "burned_at": datetime.now(timezone.utc),
                        "burn_reason": "exchange"
                    }
                },
                sort=[("_id", 1)]  # Get the oldest ticket
            )

            if not ticket:
                return {"success": False, "error": "Не удалось сжечь билет"}

            # Withdraw coins from bank
            await self.bank.update_one(
                {"_id": "main"},
                {"$inc": {"balance": -EXCHANGE_TICKET_TO_COINS}}
            )

            # Add coins to user
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": EXCHANGE_TICKET_TO_COINS}}
            )

            # Create transaction record
            tx_doc = {
                "user_id": user_id,
                "tx_type": "exchange_out",
                "coins_change": EXCHANGE_TICKET_TO_COINS,
                "description": f"Exchange: 1 ticket → {EXCHANGE_TICKET_TO_COINS} coins",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)

            return {
                "success": True,
                "direction": "ticket_to_coins",
                "ticket_burned": ticket["code"],
                "coins_received": EXCHANGE_TICKET_TO_COINS,
                "new_coins_balance": user.get("coins", 0) + EXCHANGE_TICKET_TO_COINS,
            }

        except Exception as e:
            logger.error(f"Error in ticket_to_coins: {e}")
            return {"success": False, "error": "Internal error"}

    async def get_exchange_rates(self) -> dict:
        """Получить курсы обмена."""
        return {
            "coins_to_ticket": {
                "from": EXCHANGE_COINS_TO_TICKET,
                "to": 1,
                "from_currency": "coins",
                "to_currency": "ticket",
            },
            "ticket_to_coins": {
                "from": 1,
                "to": EXCHANGE_TICKET_TO_COINS,
                "from_currency": "ticket",
                "to_currency": "coins",
            },
        }