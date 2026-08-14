"""
Демонстрация улучшенной доменной сущности пользователя.
"""

import asyncio
from datetime import datetime, timedelta

from src.domain.entities.user import (
    UserEntity,
    UserId,
    Coins,
    XP,
    Achievement,
    UserStatus,
    UserLevel,
    Katana,
    DailyReward,
    create_new_user,
    create_user_from_telegram,
)


def demo_value_objects():
    """Демонстрация Value Objects."""
    print("=== Value Objects Demo ===")
    
    # UserLevel
    print("\n📊 UserLevel (система уровней):")
    level1 = UserLevel.from_xp(0)
    print(f"  Новичок (0 XP): {level1.display}")
    print(f"  Прогресс-бар: {level1.progress_bar}")
    
    level2 = UserLevel.from_xp(150)
    print(f"  Опытный (150 XP): {level2.display}")
    
    level_advanced = UserLevel.from_xp(500)
    print(f"  Продвинутый (500 XP): {level_advanced.display}")
    
    # Katana
    print("\n⚔️ Katana (система катаны):")
    katana = Katana(length=10.0)
    print(f"  Начальная катана: {katana.display}")
    print(f"  Можно улучшить: {katana.can_upgrade}")
    
    upgraded_katana = katana.upgrade(5.0)
    print(f"  Улучшенная катана: {upgraded_katana.display}")
    print(f"  Можно улучшить: {upgraded_katana.can_upgrade}")
    
    if upgraded_katana.time_until_upgrade:
        print(f"  Время до следующего улучшения: {upgraded_katana.time_until_upgrade}")
    
    # DailyReward
    print("\n🎁 DailyReward (ежедневная награда):")
    reward = DailyReward()
    
    coins1, xp1 = reward.calculate(0)  # Без стрика
    print(f"  Без стрика: {coins1} монет, {xp1} XP")
    
    coins7, xp7 = reward.calculate(7)  # 7 дней стрика
    print(f"  7 дней стрика: {coins7} монет, {xp7} XP")
    
    coins30, xp30 = reward.calculate(30)  # 30 дней стрика
    print(f"  30 дней стрика: {coins30} монет, {xp30} XP")


def demo_user_creation():
    """Демонстрация создания пользователя."""
    print("\n=== User Creation Demo ===")
    
    # Создание нового пользователя
    print("\n👤 Создание нового пользователя:")
    user = create_new_user(
        user_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
        referrer_id=987654321
    )
    
    print(f"  ID: {user.id}")
    print(f"  Имя: {user.display_name}")
    print(f"  Полное имя: {user.full_name}")
    print(f"  Упоминание: {user.mention}")
    print(f"  Уровень: {user.level.display}")
    print(f"  Монеты: {user.coins}")
    print(f"  XP: {user.xp}")
    print(f"  Сообщений: {user.messages_count}")
    print(f"  Рефералов: {user.referral_count}")
    
    # Создание из Telegram данных
    print("\n📱 Создание из Telegram данных:")
    telegram_data = {
        "id": 987654321,
        "username": "telegram_user",
        "first_name": "Telegram",
        "last_name": "User",
    }
    
    tg_user = create_user_from_telegram(telegram_data)
    print(f"  Telegram пользователь: {tg_user.display_name}")


def demo_user_operations():
    """Демонстрация операций с пользователем."""
    print("\n=== User Operations Demo ===")
    
    # Создаём пользователя
    user = create_new_user(
        user_id=123456789,
        username="testuser",
        first_name="Test"
    )
    
    print(f"\n📝 Начальное состояние: {user.display_name}")
    print(f"  Монеты: {user.coins}, XP: {user.xp}, Уровень: {user.level.display}")
    
    # Добавляем XP и монеты
    print("\n💰 Добавляем награды:")
    user = user.add_xp(150).add_coins(75.5)
    print(f"  После наград: Монеты {user.coins}, XP: {user.xp}, Уровень: {user.level.display}")
    
    # Увеличиваем счётчик сообщений
    print("\n📨 Увеличиваем счётчик сообщений:")
    user = user.increment_messages()
    print(f"  Сообщений: {user.messages_count}")
    
    # Получаем ежедневную награду
    print("\n🎁 Получаем ежедневную награду:")
    try:
        user, daily_coins, daily_xp = user.claim_daily()
        print(f"  Получено: {daily_coins} монет, {daily_xp} XP")
        print(f"  Стрик: {user.daily_streak} дней")
        print(f"  Следующая награда: {user.next_daily_time}")
    except Exception as e:
        print(f"  Ошибка: {e}")
    
    # Получаем катану
    print("\n⚔️ Получаем катану:")
    user = user.acquire_katana(12.0)
    print(f"  Катана: {user.katana.display}")
    print(f"  Можно улучшить: {user.katana.can_upgrade}")
    
    # Улучшаем катану
    print("\n⬆️ Улучшаем катану:")
    user = user.upgrade_katana(3.5)
    print(f"  Улучшенная катана: {user.katana.display}")
    print(f"  Можно улучшить: {user.katana.can_upgrade}")


def demo_achievement_system():
    """Демонстрация системы достижений."""
    print("\n=== Achievement System Demo ===")
    
    # Создаём пользователя
    user = create_new_user(user_id=123456789, first_name="Test")
    
    print(f"\n🏆 Начальные достижения: {len(user.achievements)}")
    
    # Симулируем активность для получения достижений
    print("\n📈 Симулируем активность:")
    
    # Первое сообщение
    user = user.increment_messages()
    print(f"  Отправлено сообщений: {user.messages_count}")
    
    # Добавляем много монет для достижения "Rich"
    user = user.add_coins(15000)
    print(f"  Монеты: {user.coins}")
    
    # Добавляем много сообщений для достижения "Grinder"
    for _ in range(1000):
        user = user.increment_messages()
    print(f"  Сообщений: {user.messages_count}")
    
    # Добавляем рефералов для достижения "Social Butterfly"
    for _ in range(10):
        user = user.add_referral()
    print(f"  Рефералов: {user.referral_count}")
    
    # Проверяем и выдаём достижения
    print("\n🔍 Проверяем достижения:")
    user = user.check_achievements()
    
    print(f"  Получено достижений: {len(user.achievements)}")
    for achievement in user.achievements:
        print(f"  - {achievement.value}")


def demo_status_management():
    """Демонстрация управления статусом пользователя."""
    print("\n=== Status Management Demo ===")
    
    # Создаём пользователя
    user = create_new_user(user_id=123456789, first_name="Test")
    
    print(f"\n✅ Начальный статус: {user.status.name}")
    print(f"  Активен: {user.is_active}")
    print(f"  Забанен: {user.is_banned}")
    print(f"  Замьючен: {user.is_muted}")
    
    # Баним пользователя
    print("\n🔒 Баним пользователя:")
    user = user.ban("Нарушение правил")
    print(f"  Статус: {user.status.name}")
    print(f"  Причина: {user.ban_reason}")
    print(f"  Активен: {user.is_active}")
    
    # Разбаниваем
    print("\n🔓 Разбаниваем:")
    user = user.unban()
    print(f"  Статус: {user.status.name}")
    print(f"  Активен: {user.is_active}")
    
    # Мьютим
    print("\n🔇 Мьютим на 1 час:")
    user = user.mute(timedelta(hours=1))
    print(f"  Статус: {user.status.name}")
    print(f"  Замьючен: {user.is_muted}")
    print(f"  Активен: {user.is_active}")
    
    # Размьючиваем
    print("\n🔊 Размьючиваем:")
    user = user.unmute()
    print(f"  Статус: {user.status.name}")
    print(f"  Активен: {user.is_active}")


def demo_serialization():
    """Демонстрация сериализации."""
    print("\n=== Serialization Demo ===")
    
    # Создаём сложного пользователя
    user = create_new_user(
        user_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    
    # Накапливаем данные
    user = (
        user
        .add_xp(500)
        .add_coins(250.75)
        .increment_messages()
        .add_tickets(5)
        .acquire_katana(15.0)
        .add_achievement(Achievement.FIRST_MESSAGE)
        .add_referral()
    )
    
    print("\n📊 Исходный пользователь:")
    print(f"  Имя: {user.display_name}")
    print(f"  XP: {user.xp}, Уровень: {user.level.display}")
    print(f"  Монеты: {user.coins}")
    print(f"  Катана: {user.katana.display}")
    print(f"  Достижения: {len(user.achievements)}")
    
    # Сериализуем
    print("\n💾 Сериализация:")
    user_data = user.to_dict()
    print(f"  Сериализовано {len(user_data)} полей")
    
    # Десериализуем
    print("\n📤 Десериализация:")
    restored_user = UserEntity.from_dict(user_data)
    
    print(f"  Восстановленный: {restored_user.display_name}")
    print(f"  XP совпадает: {restored_user.xp == user.xp}")
    print(f"  Монеты совпадают: {restored_user.coins == user.coins}")
    print(f"  Катана совпадает: {restored_user.katana.length == user.katana.length}")
    print(f"  Достижения совпадают: {restored_user.achievements == user.achievements}")


def demo_error_handling():
    """Демонстрация обработки ошибок."""
    print("\n=== Error Handling Demo ===")
    
    user = create_new_user(user_id=123456789, first_name="Test")
    
    print("\n❌ Проверяем обработку ошибок:")
    
    # Попытка потратить больше монет, чем есть
    try:
        user.spend_coins(100.0)
    except Exception as e:
        print(f"  Ошибка при трате монет: {e}")
    
    # Попытка получить вторую катану
    user = user.acquire_katana()
    try:
        user.acquire_katana()
    except Exception as e:
        print(f"  Ошибка при получении катаны: {e}")
    
    # Попытка улучшить катану без катаны
    user2 = create_new_user(user_id=987654321)
    try:
        user2.upgrade_katana(5.0)
    except Exception as e:
        print(f"  Ошибка при улучшении катаны: {e}")
    
    # Попытка получить ежедневную награду дважды
    user3 = create_new_user(user_id=555555555)
    user3, _, _ = user3.claim_daily()
    try:
        user3.claim_daily()
    except Exception as e:
        print(f"  Ошибка при повторной награде: {e}")


async def main():
    """Главная функция демонстрации."""
    print("🚀 Демонстрация улучшенной доменной сущности пользователя")
    print("=" * 70)
    
    # Запускаем демонстрации
    demo_value_objects()
    demo_user_creation()
    demo_user_operations()
    demo_achievement_system()
    demo_status_management()
    demo_serialization()
    demo_error_handling()
    
    print("\n" + "=" * 70)
    print("✅ Демонстрация завершена!")
    print("\n🎯 Ключевые возможности улучшенного UserEntity:")
    print("• Иммутабельные операции с автоматическим обновлением времени")
    print("• Система уровней с прогресс-барами и расчётом XP")
    print("• Система катаны с кулдаунами и улучшениями")
    print("• Ежедневные награды с бонусами за стрик")
    print("• Система достижений с автоматической проверкой")
    print("• Управление статусом (активен/забанен/замьючен)")
    print("• Комплексная валидация и обработка ошибок")
    print("• Сериализация/десериализация с сохранением всех данных")
    print("• Типизированные Value Objects (UserId, Coins, XP)")
    print("• Поддержка реферальной системы и билетов")


if __name__ == "__main__":
    asyncio.run(main())