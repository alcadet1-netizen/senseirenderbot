"""
🌱 Скрипт для заполнения начальных данных.
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.core.constants import ACHIEVEMENTS
from src.infra.database.session import engine, session_factory
from src.infra.database.models import Base, Achievement, Bank
from src.infra.database.uow import UnitOfWork
from sqlalchemy import select


async def seed_achievements() -> int:
    """Заполнить достижения."""
    uow = UnitOfWork(session_factory)
    count = 0
    
    async with uow:
        for ach_id, ach_data in ACHIEVEMENTS.items():
            result = await uow.session.execute(
                select(Achievement).where(Achievement.id == ach_id)
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                achievement = Achievement(
                    id=ach_id,
                    name=ach_data["name"],
                    description=ach_data["description"],
                    xp_reward=ach_data.get("xp_reward", 0),
                    coin_reward=ach_data.get("coin_reward", 0),
                )
                uow.session.add(achievement)
                count += 1
        
        await uow.commit()
    
    return count


async def seed_bank() -> bool:
    """Создать банк если не существует."""
    uow = UnitOfWork(session_factory)
    
    async with uow:
        result = await uow.session.execute(
            select(Bank).where(Bank.id == 1)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            bank = Bank(
                id=1,
                name="Sensei Bank",
                coins=settings.bank_initial_coins,
            )
            uow.session.add(bank)
            await uow.commit()
            return True
    
    return False


async def main():
    """Главная функция."""
    print("🌱 Seeding database...")
    
    # Создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")
    
    # Заполняем достижения
    ach_count = await seed_achievements()
    print(f"✅ Seeded {ach_count} achievements")
    
    # Создаём банк
    bank_created = await seed_bank()
    if bank_created:
        print(f"✅ Bank created with {settings.bank_initial_coins:,.0f} coins")
    else:
        print("ℹ️ Bank already exists")
    
    print("🎉 Seeding complete!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())