"""
🎫 Репозиторий билетов.
"""

import random
import string
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import TICKET_WORDS
from src.infra.database.models import Ticket, User


class TicketRepository:
    """Репозиторий для работы с билетами."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_code(self) -> str:
        """Генерация уникального кода билета."""
        prefix = "".join(random.choices(string.ascii_uppercase, k=3))
        number = "".join(random.choices(string.digits, k=4))
        word = random.choice(TICKET_WORDS)
        return f"{prefix}-{number}-{word}"

    async def create(self, user_id: int) -> Ticket:
        """Создать новый билет."""
        for _ in range(10):
            code = self._generate_code()
            existing = await self.session.execute(
                select(Ticket).where(Ticket.code == code)
            )
            if existing.scalar_one_or_none() is None:
                break
        
        ticket = Ticket(user_id=user_id, code=code)
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def get_user_tickets(
        self,
        user_id: int,
        include_burned: bool = False
    ) -> List[Ticket]:
        """Получить билеты пользователя."""
        query = select(Ticket).where(Ticket.user_id == user_id)
        if not include_burned:
            query = query.where(Ticket.is_burned == False)
        query = query.order_by(desc(Ticket.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_user_tickets(self, user_id: int) -> int:
        """Подсчитать активные билеты пользователя."""
        result = await self.session.execute(
            select(func.count(Ticket.id))
            .where(Ticket.user_id == user_id)
            .where(Ticket.is_burned == False)
        )
        return result.scalar() or 0

    async def burn_ticket(
        self,
        ticket_id: int,
        reason: str = "exchange"
    ) -> bool:
        """Сжечь билет."""
        result = await self.session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .where(Ticket.is_burned == False)
            .values(
                is_burned=True,
                burned_at=datetime.utcnow(),
                burn_reason=reason
            )
        )
        return result.rowcount > 0

    async def burn_user_ticket(
        self,
        user_id: int,
        reason: str = "exchange"
    ) -> Optional[Ticket]:
        """Сжечь один билет пользователя (FIFO)."""
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .where(Ticket.is_burned == False)
            .order_by(Ticket.created_at)
            .limit(1)
            .with_for_update()
        )
        ticket = result.scalar_one_or_none()
        
        if ticket:
            ticket.is_burned = True
            ticket.burned_at = datetime.utcnow()
            ticket.burn_reason = reason
            await self.session.flush()
        
        return ticket

    async def get_random_tickets_for_lottery(self, count: int) -> List[Ticket]:
        """Получить случайные билеты для лотереи."""
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.is_burned == False)
            .order_by(func.random())
            .limit(count)
            .with_for_update(of=Ticket)
            .options(joinedload(Ticket.user, innerjoin=True))
        )
        return list(result.scalars().all())

    async def burn_all_tickets(self, reason: str = "season_reset") -> int:
        """Сжечь все билеты (новый сезон)."""
        result = await self.session.execute(
            update(Ticket)
            .where(Ticket.is_burned == False)
            .values(
                is_burned=True,
                burned_at=datetime.utcnow(),
                burn_reason=reason
            )
        )
        return result.rowcount

    async def burn_all_user_tickets(self, user_id: int, reason: str = "admin_burn") -> int:
        """Сжечь все билеты конкретного пользователя."""
        result = await self.session.execute(
            update(Ticket)
            .where(Ticket.user_id == user_id)
            .where(Ticket.is_burned == False)
            .values(
                is_burned=True,
                burned_at=datetime.utcnow(),
                burn_reason=reason
            )
        )
        return result.rowcount

    async def get_total_active_tickets(self) -> int:
        """Получить общее количество активных билетов."""
        result = await self.session.execute(
            select(func.count(Ticket.id))
            .where(Ticket.is_burned == False)
        )
        return result.scalar() or 0

    async def get_top_by_tickets(self, limit: int = 10) -> List[dict]:
        """Топ по количеству билетов."""
        result = await self.session.execute(
            select(
                Ticket.user_id,
                func.count(Ticket.id).label("ticket_count"),
                User.username,
                User.first_name
            )
            .join(User, User.id == Ticket.user_id)
            .where(Ticket.is_burned == False)
            .group_by(Ticket.user_id, User.username, User.first_name)
            .order_by(desc("ticket_count"))
            .limit(limit)
        )
        
        return [
            {
                "user_id": row[0],
                "tickets": row[1],
                "username": row[2] or row[3] or f"User {row[0]}"
            }
            for row in result.all()
        ]

    async def get_ticket_holders_paginated(self, offset: int, limit: int) -> tuple[List[dict], int]:
        """Пагинированный список держателей активных билетов."""
        total_result = await self.session.execute(
            select(func.count(func.distinct(Ticket.user_id)))
            .where(Ticket.is_burned == False)
        )
        total = total_result.scalar() or 0
        
        result = await self.session.execute(
            select(
                Ticket.user_id,
                func.count(Ticket.id).label("ticket_count"),
                User.username,
                User.first_name
            )
            .join(User, User.id == Ticket.user_id)
            .where(Ticket.is_burned == False)
            .group_by(Ticket.user_id, User.username, User.first_name)
            .order_by(desc("ticket_count"), Ticket.user_id)
            .offset(offset)
            .limit(limit)
        )
        items = [
            {
                "user_id": row[0],
                "tickets": row[1],
                "username": row[2] or row[3] or f"User {row[0]}"
            }
            for row in result.all()
        ]
        return items, total
