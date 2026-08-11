"""
🎰 Сервис слотов.
"""

import random
from typing import Dict, Any

from src.core.container import Container
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.domain.repositories import UserRepository, BankRepository, TransactionRepository
from src.infra.redis.locks import DistributedLock


class SlotsService:
    """Сервис для игры в слоты."""

    def __init__(self, container: Container):
        self.container = container

    async def play_slots(self, user_id: int, bet_amount: int) -> Dict[str, Any]:
        """
        Игра в слоты.
        1. Списание ставки.
        2. Комиссия 5% в банк.
        3. Розыгрыш (33% шанс).
        4. Начисление выигрыша (если есть).
        """
        lock = DistributedLock(self.container.redis)
        async with lock.acquire(f"slots:{user_id}"):
            uow = UnitOfWork(self.container.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                user = await user_repo.get_for_update(user_id)
                if not user:
                    return {"success": False, "reason": "user_not_found"}
                
                if user.coins < bet_amount:
                    return {"success": False, "reason": "insufficient_funds", "balance": user.coins}
                
                # 1. Списание ставки
                user.coins -= bet_amount
                
                # 2. Все средства идут в банк (экономика закрытого цикла)
                fee = int(bet_amount * 0.05)
                await bank_repo.deposit(bet_amount)
                
                # 3. Розыгрыш
                symbols = ["🍒", "🍋", "🍊", "💎", "⭐", "7️⃣"]
                multipliers = {
                    "🍒": 3,
                    "🍋": 4,
                    "🍊": 5,
                    "💎": 10,
                    "⭐": 15,
                    "7️⃣": 20
                }
                
                # base_bet = bet_amount (без комиссии)
                is_win = False
                prize = 0
                
                # Шансы
                JACKPOT_CHANCE = 0.01 # 1%
                WIN_CHANCE = 0.33     # 33% (включая джекпот)
                
                r = random.random()
                
                result_symbols = []
                
                if r < JACKPOT_CHANCE:
                    # Jackpot 777
                    winning_symbol = "7️⃣"
                    result_symbols = [winning_symbol, winning_symbol, winning_symbol]
                    is_win = True
                    prize = bet_amount * multipliers[winning_symbol]
                elif r < WIN_CHANCE:
                    # Win (3 одинаковых не 777)
                    winning_symbol = random.choice([s for s in symbols if s != "7️⃣"])
                    result_symbols = [winning_symbol, winning_symbol, winning_symbol]
                    is_win = True
                    prize = bet_amount * multipliers.get(winning_symbol, 3)
                else:
                    # Loss (3 разных)
                    result_symbols = random.sample(symbols, 3)
                    is_win = False
                    prize = 0
                
                # 4. Начисление выигрыша
                if is_win:
                    # Выплата выигрыша из банка
                    try:
                        await bank_repo.withdraw(prize)
                        user.coins += prize
                    except Exception:
                        # Если в банке нет денег, откатываем
                        raise
                
                # Лог транзакции
                await tx_repo.create(
                    user_id=user_id,
                    tx_type=TransactionType.CASINO_BET.value,
                    coins_change=float(prize - bet_amount),
                    description=f"Slots result: {''.join(result_symbols)}"
                )
                
                await uow.commit()
                
                return {
                    "success": True,
                    "is_win": is_win,
                    "prize": prize,
                    "bet": bet_amount,
                    "fee": fee,
                    "symbols": result_symbols,
                    "balance": user.coins
                }
