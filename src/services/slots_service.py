"""
🎰 Сервис слотов.
"""

import random
import asyncio
import time
from typing import Dict, Any
from datetime import datetime, timezone

from src.core.config import settings
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class SlotsService:
    """Сервис для игры в слоты."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # {_id: "main", balance: X}
        # For rate limiting, we'll use a simple in-memory cache with timestamps
        self._slots_timestamps = {}  # user_id -> last_slots_time
        self._throttle_lock = asyncio.Lock()  # Lock for managing the timestamps dict

    async def play_slots(self, user_id: int, bet_amount: int) -> Dict[str, Any]:
        """
        Игра в слоты.
        1. Списание ставки.
        2. Комиссия 5% в банк.
        3. Розыгрыш (33% шанс).
        4. Начисление выигрыша (если есть).
        """
        # Rate Limit - Simple implementation using timestamps (5 second cooldown)
        async with self._throttle_lock:
            now = time.time()
            last_slots = self._slots_timestamps.get(user_id, 0)
            if now - last_slots < 5:  # 5 second cooldown
                ttl = int(5 - (now - last_slots))
                return {"success": False, "error": "rate_limit", "ttl": ttl}
            self._slots_timestamps[user_id] = now

        # 2. Validation
        if bet_amount < 1:
            return {"success": False, "reason": "Ставка должна быть больше 0!"}

        # Max bet (could move to settings)
        if bet_amount > 1_000_000:
            return {"success": False, "reason": "Максимальная ставка: 1 000 000 монет"}

        try:
            # Get user
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "reason": "Пользователь не найден"}

            user_coins = user.get("coins", 0)
            if user_coins < bet_amount:
                return {"success": False, "reason": "Недостаточно монет!", "balance": user_coins}

            # 1. Deduct bet from user
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": -bet_amount}}
            )

            # Log bet transaction (deduction)
            bet_tx = {
                "user_id": user_id,
                "tx_type": "slots_bet",
                "coins_change": -float(bet_amount),
                "description": f"Slots bet",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(bet_tx)

            # 2. All funds go to bank (closed-loop economy)
            fee = int(bet_amount * 0.05)
            base = bet_amount - fee  # Not actually used in payout calculation but kept for clarity

            await self.bank.update_one(
                {"_id": "main"},
                {"$inc": {"balance": bet_amount}},
                upsert=True
            )

            # 3. Determine outcome
            symbols = ["🍒", "🍋", "🍊", "💎", "⭐", "7️⃣"]
            multipliers = {
                "🍒": 3,
                "🍋": 4,
                "🍊": 5,
                "💎": 10,
                "⭐": 15,
                "7️⃣": 20
            }

            # Chances
            JACKPOT_CHANCE = 0.01  # 1%
            WIN_CHANCE = 0.33      # 33% (including jackpot)

            r = random.random()

            result_symbols = []
            is_win = False
            prize = 0

            if r < JACKPOT_CHANCE:
                # Jackpot 777
                winning_symbol = "7️⃣"
                result_symbols = [winning_symbol, winning_symbol, winning_symbol]
                is_win = True
                prize = bet_amount * multipliers[winning_symbol]
            elif r < WIN_CHANCE:
                # Win (3 identical non-777)
                winning_symbol = random.choice([s for s in symbols if s != "7️⃣"])
                result_symbols = [winning_symbol, winning_symbol, winning_symbol]
                is_win = True
                prize = bet_amount * multipliers.get(winning_symbol, 3)
            else:
                # Loss (3 different)
                result_symbols = random.sample(symbols, 3)
                is_win = False
                prize = 0

            # 4. Award winnings if won
            if is_win:
                # Check bank balance before paying out
                bank_doc = await self.bank.find_one({"_id": "main"})
                bank_balance = bank_doc.get("balance", 0) if bank_doc else 0
                if bank_balance < prize:
                    # Not enough in bank - refund the bet and return error
                    await self.users.update_one(
                        {"id": user_id},
                        {"$inc": {"coins": bet_amount}}  # Refund the bet
                    )
                    # Also reverse the bank deposit
                    await self.bank.update_one(
                        {"_id": "main"},
                        {"$inc": {"balance": -bet_amount}}
                    )
                    # Reverse the bet transaction (simplified - in reality we'd need to handle this better)
                    # For now, just return error without perfect rollback
                    return {"success": False, "reason": "Банк пуст! Попробуйте позже."}

                # Pay out winnings
                await self.users.update_one(
                    {"id": user_id},
                    {"$inc": {"coins": prize}}
                )

                await self.bank.update_one(
                    {"_id": "main"},
                    {"$inc": {"balance": -prize}}
                )

                # Log win transaction
                win_tx = {
                    "user_id": user_id,
                    "tx_type": "slots_win",
                    "coins_change": float(prize),
                    "description": f"Slots win: {''.join(result_symbols)}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(win_tx)

            # Get final balance
            user_updated = await self.users.find_one({"id": user_id})
            final_balance = user_updated.get("coins", 0) if user_updated else 0

            return {
                "success": True,
                "is_win": is_win,
                "prize": prize,
                "bet": bet_amount,
                "fee": fee,
                "symbols": result_symbols,
                "balance": final_balance
            }

        except Exception as e:
            logger.error(f"Error in slots service play_slots: {e}")
            return {"success": False, "reason": "Внутренняя ошибка игры"}