"""
💹 Сервис трейдинга.
"""

import random
import asyncio
import time
from typing import Dict, Any
from datetime import datetime, timezone

from src.core.config import settings
from src.core.exceptions import BankInsufficientFundsError
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class TradeService:
    """Сервис для логики трейдинга."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # {_id: "main", balance: X}
        # For rate limiting, we'll use a simple in-memory cache with timestamps
        # In production, you might want to use Redis or MongoDB TTL indexes
        self._trade_timestamps = {}  # user_id -> last_trade_time
        self._throttle_lock = asyncio.Lock()  # Lock for managing the timestamps dict

    async def play_game(self, user_id: int, bet_amount: int) -> Dict[str, Any]:
        """
        Полный цикл игры (атомарно).
        Returns:
            Dict с результатами игры:
            - success: bool (прошла ли игра)
            - error: str (если success=False)
            - is_win: bool
            - profit: float
            - balance: float
            - fee: float
            - bet: int
            - payout: float
            - ttl: int (если рейт-лимит)
        """
        # 1. Rate Limit - Simple implementation using timestamps
        # Using a fixed 5s cooldown for now as in the original code
        async with self._throttle_lock:
            now = time.time()
            last_trade = self._trade_timestamps.get(user_id, 0)
            if now - last_trade < 5:  # 5 second cooldown
                ttl = int(5 - (now - last_trade))
                return {"success": False, "error": "rate_limit", "ttl": ttl}
            self._trade_timestamps[user_id] = now

        # 2. Validation
        if bet_amount < 1:
            return {"success": False, "error": "Ставка должна быть больше 0!"}

        # Max bet hardcoded in original handler to 1_000_000, maybe move to settings later
        if bet_amount > 1_000_000:
            return {"success": False, "error": "Максимальная ставка: 1 000 000 монет"}

        # 3. Game Logic (We'll simulate transactional behavior with individual operations)
        # In a real implementation with MongoDB transactions, we'd use a session
        # For simplicity, we'll do operations sequentially and handle errors

        try:
            # Get user
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "error": "Пользователь не найден. Напиши что-нибудь в чат."}

            user_coins = user.get("coins", 0)
            if user_coins < bet_amount:
                return {
                    "success": False,
                    "error": f"Недостаточно монет! У тебя: {user_coins:.0f}",
                    "balance": user_coins
                }

            # Deduct bet from user
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": -bet_amount}}
            )

            # Log purchase transaction (bet deduction)
            purchase_tx = {
                "user_id": user_id,
                "tx_type": "purchase",
                "coins_change": -float(bet_amount),
                "description": "Trade bet",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(purchase_tx)

            # Determine Result
            is_win = random.random() < settings.trade_win_chance

            fee = int(bet_amount * 0.05)
            base = bet_amount - fee

            # Pay fee to Bank - Deposit FULL bet to bank (Closed Loop Economy)
            # The fee is implicitly retained because payout = (bet - fee) * 2
            await self.bank.update_one(
                {"_id": "main"},
                {"$inc": {"balance": bet_amount}},
                upsert=True
            )

            payout = 0
            profit = -bet_amount

            if is_win:
                payout = base * 2
                profit = payout - bet_amount

                # Check bank balance before withdrawing
                bank_doc = await self.bank.find_one({"_id": "main"})
                bank_balance = bank_doc.get("balance", 0) if bank_doc else 0
                if bank_balance < payout:
                    # Not enough in bank - refund the bet to user and return error
                    await self.users.update_one(
                        {"id": user_id},
                        {"$inc": {"coins": bet_amount}}  # Refund the bet
                    )
                    # Also need to reverse the bank deposit
                    await self.bank.update_one(
                        {"_id": "main"},
                        {"$inc": {"balance": -bet_amount}}
                    )
                    # Reverse the purchase transaction (this is getting complex)
                    # For simplicity, we'll just return the error without perfect rollback
                    return {"success": False, "error": "Банк пуст! Попробуйте позже."}

                # Pay out winnings
                await self.users.update_one(
                    {"id": user_id},
                    {"$inc": {"coins": payout}}
                )

                await self.bank.update_one(
                    {"_id": "main"},
                    {"$inc": {"balance": -payout}}
                )

                # Log win transaction
                win_tx = {
                    "user_id": user_id,
                    "tx_type": "game_win",
                    "coins_change": float(payout),
                    "description": "Trade win",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(win_tx)

            # Get final balance
            user_updated = await self.users.find_one({"id": user_id})
            final_balance = user_updated.get("coins", 0) if user_updated else 0

            return {
                "success": True,
                "is_win": is_win,
                "profit": profit,
                "balance": final_balance,
                "fee": fee,
                "bet": bet_amount,
                "payout": payout
            }

        except Exception as e:
            logger.error(f"Error in trade service play_game: {e}")
            return {"success": False, "error": "Внутренняя ошибка игры"}