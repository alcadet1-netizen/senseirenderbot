"""
🏦 Репозиторий банка.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import MAX_BANK_SUPPLY
from src.core.exceptions import BankInsufficientFundsError
from src.infra.database.models import Bank


class BankRepository:
    """Репозиторий для работы с банком."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_bank(self, for_update: bool = False) -> Bank:
        """Получить банк (создаёт если не существует)."""
        stmt = select(Bank).where(Bank.id == 1)
        if for_update:
            stmt = stmt.with_for_update()
            
        result = await self.session.execute(stmt)
        bank = result.scalar_one_or_none()
        
        if bank is None:
            bank = Bank(id=1)
            self.session.add(bank)
            await self.session.flush()
        
        return bank

    async def get_balance(self) -> float:
        """Получить баланс банка."""
        bank = await self.get_bank(for_update=False)
        return bank.coins

    async def withdraw(self, amount: float) -> float:
        """Снять монеты из банка."""
        bank = await self.get_bank(for_update=True)
        
        if bank.coins < amount:
            raise BankInsufficientFundsError(amount, bank.coins)
        
        bank.coins -= amount
        bank.total_coins_distributed += amount
        await self.session.flush()
        return bank.coins

    async def deposit(self, amount: float) -> float:
        """Положить монеты в банк."""
        bank = await self.get_bank(for_update=True)
        
        # Проверяем лимит (хотя в закрытой системе это не должно случаться)
        if bank.coins + amount > MAX_BANK_SUPPLY:
            # Можно рейзить ошибку или просто капнуть.
            # Если рейзить, то транзакция откатится, что безопасно.
            # Но чтобы не ломать игру пользователям, если вдруг банк переполнен (баг?),
            # можно просто обрезать или разрешить (но с предупреждением).
            # Пользователь сказал "всего может существовать 1 миллиард".
            # Если мы примем больше, будет > 1 млрд.
            # Рейзим ошибку.
            raise ValueError(f"Bank overflow: cannot deposit {amount}, max is {MAX_BANK_SUPPLY}")

        bank.coins += amount
        bank.total_coins_collected += amount
        await self.session.flush()
        return bank.coins

    async def get_stats(self) -> dict:
        """Получить статистику банка."""
        bank = await self.get_bank()
        return {
            "balance": bank.coins,
            "total_distributed": bank.total_coins_distributed,
            "total_collected": bank.total_coins_collected,
        }

    async def reset_balance(self, new_balance: float) -> None:
        """Сбросить баланс банка."""
        await self.session.execute(
            update(Bank)
            .where(Bank.id == 1)
            .values(
                coins=new_balance,
                total_coins_distributed=0,
                total_coins_collected=0
            )
        )