"""
🎰 Сервис лотереи.
"""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.repositories import TicketRepository, UserRepository
from src.infra.database.uow import UnitOfWork


class LotteryService:
    """Сервис для проведения розыгрышей."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def run_lottery(self, winners_count: int) -> List[dict]:
        """Провести розыгрыш."""
        uow = UnitOfWork(self.session_factory)
        winners = []
        
        async with uow:
            ticket_repo = TicketRepository(uow.session)
            
            tickets = await ticket_repo.get_random_tickets_for_lottery(winners_count)
            
            for ticket in tickets:
                ticket.is_burned = True
                ticket.burn_reason = "lottery_win"
                
                user = ticket.user
                
                # Собираем данные для mention
                username = user.username
                first_name = user.first_name or ""
                last_name = user.last_name or ""
                full_name = f"{first_name} {last_name}".strip() or f"User {ticket.user_id}"
                
                winners.append({
                    "user_id": ticket.user_id,
                    "username": username,
                    "full_name": full_name,
                    "ticket_code": ticket.code,
                })
            
            await uow.commit()
        
        return winners

    async def admin_add_ticket(self, user_id: int, admin_id: int) -> dict:
        """Админ выдаёт билет пользователю."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            ticket = await ticket_repo.create(user.id)
            
            await uow.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "username": user.username or user.first_name or f"User {user.id}",
                "ticket_code": ticket.code,
            }

    async def admin_burn_user_tickets(self, user_id: int, admin_id: int) -> dict:
        """Админ сжигает все билеты пользователя."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            burned_count = await ticket_repo.burn_all_user_tickets(user.id, reason=f"admin_burn_by_{admin_id}")
            
            await uow.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "username": user.username or user.first_name or f"User {user.id}",
                "burned_count": burned_count
            }

    async def get_lottery_stats(self) -> dict:
        """Статистика для лотереи."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            ticket_repo = TicketRepository(uow.session)
            
            total_active = await ticket_repo.get_total_active_tickets()
            top_holders = await ticket_repo.get_top_by_tickets(5)
            
            return {
                "total_active_tickets": total_active,
                "top_holders": top_holders,
            }