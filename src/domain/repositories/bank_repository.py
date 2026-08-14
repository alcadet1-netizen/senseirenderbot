"""
🏦 Репозиторий банка.
"""

from motor.motor_asyncio import AsyncIOMotorCollection
from src.core.constants import MAX_BANK_SUPPLY
from src.core.exceptions import BankInsufficientFundsError
from datetime import datetime, timezone


class BankRepository:
    """Репозиторий для работы с банком."""

    def __init__(self, bank_collection: AsyncIOMotorCollection):
        self.collection = bank_collection

    async def get_bank(self, for_update: bool = False) -> dict:
        """Получить банк (создаёт если не существует)."""
        # In MongoDB, we don't have for_update, but we can ignore the flag
        bank = await self.collection.find_one({"_id": "single"})
        if bank is None:
            bank = {
                "_id": "single",
                "coins": 0.0,
                "total_coins_distributed": 0.0,
                "total_coins_collected": 0.0,
            }
            await self.collection.insert_one(bank)
        return bank

    async def get_balance(self) -> float:
        """Получить баланс банка."""
        bank = await self.get_bank()
        return bank.get("coins", 0.0)

    async def withdraw(self, amount: float) -> float:
        """Снять монеты из банка."""
        bank = await self.get_bank()
        if bank.get("coins", 0.0) < amount:
            raise BankInsufficientFundsError(amount, bank.get("coins", 0.0))

        new_balance = bank["coins"] - amount
        await self.collection.update_one(
            {"_id": "single"},
            {"$set": {
                "coins": new_balance,
                "total_coins_distributed": bank.get("total_coins_distributed", 0.0) + amount
            }}
        )
        return new_balance

    async def deposit(self, amount: float) -> float:
        """Положить монеты в банк."""
        bank = await self.get_bank()
        # Проверяем лимит (хотя в закрытой системе это не должно случаться)
        if bank.get("coins", 0.0) + amount > MAX_BANK_SUPPLY:
            raise ValueError(f"Bank overflow: cannot deposit {amount}, max is {MAX_BANK_SUPPLY}")

        new_balance = bank["coins"] + amount
        await self.collection.update_one(
            {"_id": "single"},
            {"$set": {
                "coins": new_balance,
                "total_coins_collected": bank.get("total_coins_collected", 0.0) + amount
            }}
        )
        return new_balance

    async def get_stats(self) -> dict:
        """Получить статистику банка."""
        bank = await self.get_bank()
        return {
            "balance": bank.get("coins", 0.0),
            "total_distributed": bank.get("total_coins_distributed", 0.0),
            "total_collected": bank.get("total_coins_collected", 0.0),
        }

    async def reset_balance(self, new_balance: float) -> None:
        """Сбросить баланс банка."""
        await self.collection.update_one(
            {"_id": "single"},
            {"$set": {
                "coins": new_balance,
                "total_coins_distributed": 0.0,
                "total_coins_collected": 0.0
            }}
        )