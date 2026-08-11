"""Domain repositories."""

from src.domain.repositories.user_repository import UserRepository
from src.domain.repositories.transaction_repository import TransactionRepository
from src.domain.repositories.ticket_repository import TicketRepository
from src.domain.repositories.achievement_repository import AchievementRepository
from src.domain.repositories.bank_repository import BankRepository

__all__ = [
    "UserRepository",
    "TransactionRepository",
    "TicketRepository",
    "AchievementRepository",
    "BankRepository",
]