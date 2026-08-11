"""
💰 Репозиторий транзакций.
"""

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.models import Transaction, User


class TransactionRepository:
    """Репозиторий для работы с транзакциями."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        tx_type: str,
        xp_change: int = 0,
        coins_change: float = 0.0,
        description: Optional[str] = None
    ) -> Transaction:
        """Создать транзакцию."""
        transaction = Transaction(
            user_id=user_id,
            type=tx_type if isinstance(tx_type, str) else tx_type.value,
            xp_change=xp_change,
            coins_change=coins_change,
            description=description,
        )
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get_user_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Transaction]:
        """Получить транзакции пользователя."""
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(desc(Transaction.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_total_coins_distributed(self) -> float:
        """Получить общее количество распределённых монет."""
        result = await self.session.execute(
            select(func.sum(Transaction.coins_change))
            .where(Transaction.coins_change > 0)
        )
        return result.scalar() or 0.0

    async def get_total_coins_in_circulation(self) -> float:
        """Получить общее количество монет в обороте."""
        result = await self.session.execute(
            select(func.sum(User.coins))
        )
        return result.scalar() or 0.0

    async def get_stats_by_type(self) -> dict:
        """Статистика по типам транзакций."""
        result = await self.session.execute(
            select(
                Transaction.type,
                func.count(Transaction.id),
                func.sum(Transaction.coins_change)
            )
            .group_by(Transaction.type)
        )
        return {
            row[0]: {"count": row[1], "total_coins": row[2] or 0}
            for row in result.all()
        }