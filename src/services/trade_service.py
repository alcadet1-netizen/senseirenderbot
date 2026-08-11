"""
💹 Сервис трейдинга.
"""

import random
import logging
from typing import Dict, Any

from src.core.config import settings
from src.core.container import Container
from src.core.exceptions import BankInsufficientFundsError
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository, BankRepository, TransactionRepository
from src.infra.redis.throttling import ThrottleManager

logger = logging.getLogger(__name__)


class TradeService:
    """Сервис для логики трейдинга."""

    def __init__(self, container: Container):
        self.container = container

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
        # 1. Rate Limit
        throttle = ThrottleManager(self.container.redis)
        key = f"trade:{user_id}"
        # Using a fixed 5s cooldown for now as in the original code
        is_throttled = await throttle.is_throttled(key, 5, scope="game")
        if is_throttled:
            ttl = await throttle.get_ttl(key, scope="game")
            return {"success": False, "error": "rate_limit", "ttl": ttl}

        await throttle.throttle(key, 5, scope="game")

        # 2. Validation
        if bet_amount < 1:
             return {"success": False, "error": "Ставка должна быть больше 0!"}
        
        # Max bet hardcoded in original handler to 1_000_000, maybe move to settings later
        if bet_amount > 1_000_000:
             return {"success": False, "error": "Максимальная ставка: 1 000 000 монет"}

        # 3. Game Logic (Transactional)
        uow = UnitOfWork(self.container.session_factory)
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "Пользователь не найден. Напиши что-нибудь в чат."}
            
            if user.coins < bet_amount:
                return {
                    "success": False, 
                    "error": f"Недостаточно монет! У тебя: {user.coins:.0f}",
                    "balance": user.coins
                }

            # Deduct bet
            user.coins -= bet_amount
            
            # Log purchase transaction
            await tx_repo.create(
                user_id=user_id,
                tx_type=TransactionType.PURCHASE.value,
                coins_change=-float(bet_amount),
                description="Trade bet"
            )

            # Determine Result
            is_win = random.random() < settings.trade_win_chance
            
            fee = int(bet_amount * 0.05)
            base = bet_amount - fee
            
            # Pay fee to Bank
            # Deposit FULL bet to bank (Closed Loop Economy)
            # The fee is implicitly retained because payout = (bet - fee) * 2
            await bank_repo.deposit(bet_amount)

            payout = 0
            profit = -bet_amount
            
            if is_win:
                payout = base * 2
                profit = payout - bet_amount
                
                try:
                    await bank_repo.withdraw(payout)
                except BankInsufficientFundsError:
                    return {"success": False, "error": "Банк пуст! Попробуйте позже."}

                user.coins += payout
                
                await tx_repo.create(
                    user_id=user_id,
                    tx_type=TransactionType.GAME_WIN.value,
                    coins_change=float(payout),
                    description="Trade win"
                )

            # Commit everything
            await uow.commit()
            
            return {
                "success": True,
                "is_win": is_win,
                "profit": profit,
                "balance": user.coins,
                "fee": fee,
                "bet": bet_amount,
                "payout": payout
            }
