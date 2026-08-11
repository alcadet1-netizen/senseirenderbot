"""
💱 Сервис обмена валют.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.constants import EXCHANGE_COINS_TO_TICKET, EXCHANGE_TICKET_TO_COINS
from src.core.exceptions import InsufficientFundsError, InsufficientTicketsError
from src.domain.repositories import (
    BankRepository,
    TicketRepository,
    TransactionRepository,
    UserRepository,
)
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork


class ExchangeService:
    """Сервис обмена валют."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def coins_to_ticket(self, user_id: int) -> dict:
        """Обменять монеты на билет. 1000 монет → 1 билет"""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            if user.coins < EXCHANGE_COINS_TO_TICKET:
                raise InsufficientFundsError(EXCHANGE_COINS_TO_TICKET, user.coins)
            
            user.coins -= EXCHANGE_COINS_TO_TICKET
            await bank_repo.deposit(EXCHANGE_COINS_TO_TICKET)
            ticket = await ticket_repo.create(user.id)
            
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.EXCHANGE_IN.value,
                coins_change=-EXCHANGE_COINS_TO_TICKET,
                description=f"Exchange: {EXCHANGE_COINS_TO_TICKET} coins → 1 ticket"
            )
            
            await uow.commit()
            
            return {
                "success": True,
                "direction": "coins_to_ticket",
                "coins_spent": EXCHANGE_COINS_TO_TICKET,
                "ticket_code": ticket.code,
                "new_coins_balance": user.coins,
            }

    async def ticket_to_coins(self, user_id: int) -> dict:
        """Обменять билет на монеты. 1 билет → 900 монет"""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            ticket_repo = TicketRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            tickets_count = await ticket_repo.count_user_tickets(user.id)
            if tickets_count < 1:
                raise InsufficientTicketsError(1, tickets_count)
            
            bank_balance = await bank_repo.get_balance()
            if bank_balance < EXCHANGE_TICKET_TO_COINS:
                return {"success": False, "error": "Банк временно пуст"}
            
            burned_ticket = await ticket_repo.burn_user_ticket(user.id, "exchange")
            if not burned_ticket:
                return {"success": False, "error": "Не удалось сжечь билет"}
            
            await bank_repo.withdraw(EXCHANGE_TICKET_TO_COINS)
            user.coins += EXCHANGE_TICKET_TO_COINS
            
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.EXCHANGE_OUT.value,
                coins_change=EXCHANGE_TICKET_TO_COINS,
                description=f"Exchange: 1 ticket → {EXCHANGE_TICKET_TO_COINS} coins"
            )
            
            await uow.commit()
            
            return {
                "success": True,
                "direction": "ticket_to_coins",
                "ticket_burned": burned_ticket.code,
                "coins_received": EXCHANGE_TICKET_TO_COINS,
                "new_coins_balance": user.coins,
            }

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