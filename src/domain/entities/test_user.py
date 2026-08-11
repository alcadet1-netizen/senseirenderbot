"""
Тесты для улучшенной доменной сущности пользователя.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

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
    UserDomainError,
    InsufficientFundsError,
    UserBannedError,
    DailyAlreadyClaimedError,
    create_new_user,
    create_user_from_telegram,
    DEFAULT_LEVEL_CONFIG,
)


class TestValueObjects:
    """Тесты Value Objects."""
    
    def test_user_level_from_xp(self):
        """Тест создания уровня из XP."""
        # Первый уровень
        level1 = UserLevel.from_xp(0)
        assert level1.level == 1
        assert level1.current_xp == 0
        assert level1.progress_percent == 0.0
        
        # Второй уровень (нужно 150 XP для 2 уровня)
        level2 = UserLevel.from_xp(150)
        assert level2.level == 2
        assert level2.current_xp == 0  # Точно достигли
        
        # Промежуточный уровень
        level_mid = UserLevel.from_xp(75)  # Между 1 и 2
        assert level_mid.level == 1
        assert level_mid.current_xp == 75
        assert level_mid.progress_percent == 75.0
    
    def test_user_level_display(self):
        """Тест отображения уровня."""
        level = UserLevel.from_xp(200)
        assert "Lvl" in level.display
        assert "%" in level.display
        assert level.progress_bar.startswith("[")
        assert level.progress_bar.endswith("]")
    
    def test_katana_upgrade(self):
        """Тест улучшения катаны."""
        katana = Katana(length=10.0)
        
        # Проверяем, что можно улучшить
        assert katana.can_upgrade is True
        assert katana.next_upgrade_time is None
        
        # Улучшаем
        upgraded = katana.upgrade(5.0)
        assert upgraded.length == 15.0
        assert upgraded.last_upgrade is not None
        assert upgraded.can_upgrade is False  # Теперь на кулдауне
        
        # Проверяем ограничения
        max_katana = Katana(length=99.0)
        maxed = max_katana.upgrade(10.0)
        assert maxed.length == 100.0  # Не превышает максимум
    
    def test_daily_reward_calculation(self):
        """Тест расчёта ежедневной награды."""
        reward = DailyReward()
        
        # Без стрика
        coins1, xp1 = reward.calculate(0)
        assert coins1 == 100.0
        assert xp1 == 50
        
        # Со стриком
        coins7, xp7 = reward.calculate(7)
        assert coins7 > 100.0  # Должно быть больше
        assert xp7 > 50
        
        # Максимальный стрик
        coins_max, xp_max = reward.calculate(100)
        assert coins_max == 200.0  # 100% бонус
        assert xp_max == 100


class TestUserEntityCreation:
    """Тесты создания UserEntity."""
    
    def test_create_new_user(self):
        """Тест фабричной функции создания нового пользователя."""
        user = create_new_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            referrer_id=987654321
        )
        
        assert user.id == UserId(123456789)
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.referrer_id == UserId(987654321)
        assert user.xp == XP(0)
        assert user.coins == Coins(0.0)
        assert user.status == UserStatus.ACTIVE
        assert len(user.achievements) == 0
    
    def test_create_user_from_telegram(self):
        """Тест создания пользователя из данных Telegram."""
        telegram_data = {
            "id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
        }
        
        user = create_user_from_telegram(telegram_data, referrer_id=987654321)
        
        assert user.id == UserId(123456789)
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.referrer_id == UserId(987654321)
    
    def test_user_validation(self):
        """Тест валидации пользователя."""
        # Невалидные значения должны вызывать ошибку
        with pytest.raises(ValueError):
            UserEntity(
                id=UserId(1),
                xp=XP(-100),  # Отрицательный XP
                coins=Coins(0.0),
                messages_count=0,
                daily_streak=0,
                tickets_count=0,
                referral_count=0,
            )
        
        with pytest.raises(ValueError):
            UserEntity(
                id=UserId(1),
                xp=XP(0),
                coins=Coins(-10.0),  # Отрицательные монеты
                messages_count=0,
                daily_streak=0,
                tickets_count=0,
                referral_count=0,
            )


class TestUserEntityProperties:
    """Тесты свойств UserEntity."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.user = create_new_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
    
    def test_display_name(self):
        """Тест отображаемого имени."""
        assert self.user.display_name == "@testuser"
        
        # Без username
        user_no_username = create_new_user(user_id=123456789, first_name="Test")
        assert user_no_username.display_name == "Test"
        
        # Без имени и username
        user_empty = create_new_user(user_id=123456789)
        assert user_empty.display_name == "User 123456789"
    
    def test_full_name(self):
        """Тест полного имени."""
        assert self.user.full_name == "Test User"
        
        # Только имя
        user_first_only = create_new_user(user_id=123456789, first_name="Test")
        assert user_first_only.full_name == "Test"
        
        # Без имени
        user_empty = create_new_user(user_id=123456789)
        assert user_empty.full_name == "User 123456789"
    
    def test_mention(self):
        """Тест упоминания."""
        mention = self.user.mention
        assert "tg://user?id=123456789" in mention
        assert "Test User" in mention
    
    def test_level_property(self):
        """Тест свойства уровня."""
        level = self.user.level
        assert isinstance(level, UserLevel)
        assert level.level == 1  # Начальный уровень
        
        # Пользователь с XP
        user_with_xp = self.user.add_xp(200)
        level2 = user_with_xp.level
        assert level2.level > 1
    
    def test_status_properties(self):
        """Тест свойств статуса."""
        assert self.user.is_banned is False
        assert self.user.is_muted is False
        assert self.user.is_active is True
        
        # Забаненный пользователь
        banned_user = self.user.ban("Test reason")
        assert banned_user.is_banned is True
        assert banned_user.is_active is False
        
        # Замьюченный пользователь
        muted_user = self.user.mute(timedelta(hours=1))
        assert muted_user.is_muted is True
        assert muted_user.is_active is False
    
    def test_katana_properties(self):
        """Тест свойств катаны."""
        assert self.user.has_katana is False
        
        # Пользователь с катаной
        user_with_katana = self.user.acquire_katana()
        assert user_with_katana.has_katana is True
        assert user_with_katana.katana.length == 10.0
    
    def test_daily_properties(self):
        """Тест свойств ежедневной награды."""
        assert self.user.can_claim_daily is True
        assert self.user.next_daily_time is None
        
        # После получения награды
        user_with_daily, _, _ = self.user.claim_daily()
        assert user_with_daily.can_claim_daily is False
        assert user_with_daily.next_daily_time is not None


class TestUserEntityBusinessMethods:
    """Тесты бизнес-методов UserEntity."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.user = create_new_user(user_id=123456789)
    
    def test_add_xp(self):
        """Тест добавления XP."""
        user = self.user.add_xp(100)
        assert user.xp == XP(100)
        assert user != self.user  # Новый объект
        
        # Отрицательное XP должно вызывать ошибку
        with pytest.raises(ValueError):
            self.user.add_xp(-50)
    
    def test_add_coins(self):
        """Тест добавления монет."""
        user = self.user.add_coins(100.5)
        assert user.coins == Coins(100.5)
        assert user != self.user
        
        # Отрицательные монеты должны вызывать ошибку
        with pytest.raises(ValueError):
            self.user.add_coins(-10.0)
    
    def test_spend_coins(self):
        """Тест траты монет."""
        user_with_coins = self.user.add_coins(100.0)
        
        # Успешная трата
        user = user_with_coins.spend_coins(50.0)
        assert user.coins == Coins(50.0)
        
        # Недостаточно монет
        with pytest.raises(InsufficientFundsError) as exc_info:
            user.spend_coins(100.0)
        assert exc_info.value.required == 100.0
        assert exc_info.value.available == 50.0
    
    def test_transfer_coins(self):
        """Тест перевода монет."""
        sender = self.user.add_coins(100.0)
        recipient = create_new_user(user_id=987654321)
        
        sender_new, recipient_new = sender.transfer_coins(50.0, recipient)
        
        assert sender_new.coins == Coins(50.0)
        assert recipient_new.coins == Coins(50.0)
        
        # Недостаточно монет для перевода
        with pytest.raises(InsufficientFundsError):
            sender_new.transfer_coins(100.0, recipient_new)
    
    def test_increment_messages(self):
        """Тест увеличения счётчика сообщений."""
        user = self.user.increment_messages()
        assert user.messages_count == 1
        
        user2 = user.increment_messages()
        assert user2.messages_count == 2
    
    def test_claim_daily(self):
        """Тест получения ежедневной награды."""
        user, coins, xp = self.user.claim_daily()
        
        assert user.daily_streak == 1
        assert user.last_daily is not None
        assert coins > 0
        assert xp > 0
        assert user.coins == Coins(coins)
        assert user.xp == XP(self.user.xp + xp)
        
        # Повторное получение должно вызывать ошибку
        with pytest.raises(DailyAlreadyClaimedError):
            user.claim_daily()
    
    def test_daily_streak_reset(self):
        """Тест сброса стрика."""
        # Получаем награду
        user1, _, _ = self.user.claim_daily()
        assert user1.daily_streak == 1
        
        # Симулируем прошедшее время (больше 1 дня)
        old_last_daily = user1.last_daily - timedelta(days=2)
        user_old = user1._update(last_daily=old_last_daily)
        
        # Новая награда должна сбросить стрик
        user2, _, _ = user_old.claim_daily()
        assert user2.daily_streak == 1  # Сбросился
    
    def test_ban_unban(self):
        """Тест бана и разбана."""
        # Бан
        banned = self.user.ban("Test reason")
        assert banned.status == UserStatus.BANNED
        assert banned.ban_reason == "Test reason"
        assert banned.is_banned is True
        
        # Разбан
        unbanned = banned.unban()
        assert unbanned.status == UserStatus.ACTIVE
        assert unbanned.ban_reason is None
        assert unbanned.is_banned is False
    
    def test_mute_unmute(self):
        """Тест мута и размута."""
        # Мут
        muted = self.user.mute(timedelta(hours=1))
        assert muted.status == UserStatus.MUTED
        assert muted.mute_until is not None
        assert muted.is_muted is True
        
        # Размут
        unmuted = muted.unmute()
        assert unmuted.status == UserStatus.ACTIVE
        assert unmuted.mute_until is None
        assert unmuted.is_muted is False
    
    def test_katana_operations(self):
        """Тест операций с катаной."""
        # Получение катаны
        user = self.user.acquire_katana(15.0)
        assert user.has_katana is True
        assert user.katana.length == 15.0
        
        # Повторное получение должно вызывать ошибку
        with pytest.raises(UserDomainError):
            user.acquire_katana()
        
        # Улучшение катаны
        upgraded = user.upgrade_katana(5.0)
        assert upgraded.katana.length == 20.0
        assert upgraded.katana.last_upgrade is not None
        
        # Улучшение без катаны
        with pytest.raises(UserDomainError):
            self.user.upgrade_katana(5.0)
    
    def test_achievement_operations(self):
        """Тест операций с достижениями."""
        # Добавление достижения
        user = self.user.add_achievement(Achievement.FIRST_MESSAGE)
        assert Achievement.FIRST_MESSAGE in user.achievements
        assert len(user.achievements) == 1
        
        # Повторное добавление не должно изменять достижения
        user2 = user.add_achievement(Achievement.FIRST_MESSAGE)
        assert user2.achievements == user.achievements
    
    def test_referral_operations(self):
        """Тест реферальных операций."""
        user = self.user.add_referral()
        assert user.referral_count == 1
        
        user2 = user.add_referral()
        assert user2.referral_count == 2
    
    def test_ticket_operations(self):
        """Тест операций с билетами."""
        # Добавление билетов
        user = self.user.add_tickets(5)
        assert user.tickets_count == 5
        
        # Трата билетов
        user2 = user.spend_tickets(2)
        assert user2.tickets_count == 3
        
        # Недостаточно билетов
        with pytest.raises(UserDomainError):
            user2.spend_tickets(5)
        
        # Отрицательное количество
        with pytest.raises(ValueError):
            self.user.add_tickets(-1)
    
    def test_profile_update(self):
        """Тест обновления профиля."""
        user = self.user.update_profile(
            username="newusername",
            first_name="NewFirst",
            last_name="NewLast"
        )
        
        assert user.username == "newusername"
        assert user.first_name == "NewFirst"
        assert user.last_name == "NewLast"
        
        # Обновление без изменений
        user2 = user.update_profile()
        assert user2 == user


class TestAchievementSystem:
    """Тесты системы достижений."""
    
    def setup_method(self):
        """Настройка тестов."""
        self.user = create_new_user(user_id=123456789)
    
    def test_first_message_achievement(self):
        """Тест достижения первого сообщения."""
        user = self.user.increment_messages()
        user_with_achievements = user.check_achievements()
        
        assert Achievement.FIRST_MESSAGE in user_with_achievements.achievements
    
    def test_week_streak_achievement(self):
        """Тест достижения недельного стрика."""
        user = self.user._update(daily_streak=7)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.WEEK_STREAK in user_with_achievements.achievements
    
    def test_month_streak_achievement(self):
        """Тест достижения месячного стрика."""
        user = self.user._update(daily_streak=30)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.MONTH_STREAK in user_with_achievements.achievements
    
    def test_rich_achievement(self):
        """Тест достижения богатства."""
        user = self.user.add_coins(10000)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.RICH in user_with_achievements.achievements
    
    def test_grinder_achievement(self):
        """Тест достижения мельничника."""
        user = self.user._update(messages_count=1000)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.GRINDER in user_with_achievements.achievements
    
    def test_social_butterfly_achievement(self):
        """Тест достижения социального бабочки."""
        user = self.user._update(referral_count=10)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.SOCIAL_BUTTERFLY in user_with_achievements.achievements
    
    def test_veteran_achievement(self):
        """Тест достижения ветерана."""
        old_user = self.user._update(
            created_at=datetime.now() - timedelta(days=365)
        )
        user_with_achievements = old_user.check_achievements()
        
        assert Achievement.VETERAN in user_with_achievements.achievements
    
    def test_katana_master_achievement(self):
        """Тест достижения мастера катаны."""
        user = self.user.acquire_katana(50.0)
        user_with_achievements = user.check_achievements()
        
        assert Achievement.KATANA_MASTER in user_with_achievements.achievements
    
    def test_multiple_achievements(self):
        """Тест получения нескольких достижений."""
        user = (
            self.user
            .increment_messages()  # FIRST_MESSAGE
            .add_coins(10000)      # RICH
            ._update(messages_count=1000)  # GRINDER
        )
        
        user_with_achievements = user.check_achievements()
        
        assert Achievement.FIRST_MESSAGE in user_with_achievements.achievements
        assert Achievement.RICH in user_with_achievements.achievements
        assert Achievement.GRINDER in user_with_achievements.achievements
        assert len(user_with_achievements.achievements) == 3


class TestSerialization:
    """Тесты сериализации и десериализации."""
    
    def test_to_dict(self):
        """Тест сериализации в словарь."""
        user = create_new_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        
        user = (
            user
            .add_xp(100)
            .add_coins(50.5)
            .increment_messages()
            .add_achievement(Achievement.FIRST_MESSAGE)
            .acquire_katana(15.0)
        )
        
        data = user.to_dict()
        
        assert data["id"] == 123456789
        assert data["username"] == "testuser"
        assert data["xp"] == 100
        assert data["coins"] == 50.5
        assert data["messages_count"] == 1
        assert Achievement.FIRST_MESSAGE.value in data["achievements"]
        assert data["katana"]["length"] == 15.0
        assert data["status"] == "ACTIVE"
    
    def test_from_dict(self):
        """Тест десериализации из словаря."""
        original_data = {
            "id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "xp": 100,
            "coins": 50.5,
            "messages_count": 5,
            "daily_streak": 3,
            "last_daily": "2024-01-01T12:00:00",
            "status": "ACTIVE",
            "ban_reason": None,
            "mute_until": None,
            "katana": {
                "length": 20.0,
                "last_upgrade": "2024-01-01T12:00:00"
            },
            "referrer_id": 987654321,
            "referral_count": 2,
            "tickets_count": 3,
            "achievements": ["first_message", "rich"],
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T15:00:00",
        }
        
        user = UserEntity.from_dict(original_data)
        
        assert user.id == UserId(123456789)
        assert user.username == "testuser"
        assert user.xp == XP(100)
        assert user.coins == Coins(50.5)
        assert user.messages_count == 5
        assert user.daily_streak == 3
        assert user.katana.length == 20.0
        assert user.referrer_id == UserId(987654321)
        assert Achievement.FIRST_MESSAGE in user.achievements
        assert Achievement.RICH in user.achievements
        assert user.status == UserStatus.ACTIVE
    
    def test_roundtrip_serialization(self):
        """Тест полного цикла сериализации."""
        original = create_new_user(
            user_id=123456789,
            username="testuser",
            first_name="Test"
        )
        
        original = (
            original
            .add_xp(200)
            .add_coins(100.0)
            .increment_messages()
            .claim_daily()[0]
            .add_achievement(Achievement.FIRST_MESSAGE)
            .acquire_katana(15.0)
        )
        
        # Сериализуем и десериализуем
        data = original.to_dict()
        restored = UserEntity.from_dict(data)
        
        # Проверяем, что данные совпадают
        assert restored.id == original.id
        assert restored.username == original.username
        assert restored.xp == original.xp
        assert restored.coins == original.coins
        assert restored.messages_count == original.messages_count
        assert restored.achievements == original.achievements
        assert restored.katana.length == original.katana.length


class TestComplexScenarios:
    """Тесты сложных сценариев."""
    
    def test_full_user_journey(self):
        """Тест полного пути пользователя."""
        # Создаём нового пользователя
        user = create_new_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            referrer_id=987654321
        )
        
        # Пользователь отправляет первое сообщение
        user = user.increment_messages()
        
        # Пользователь получает XP и монеты за активность
        user = user.add_xp(50).add_coins(25.0)
        
        # Пользователь получает ежедневную награду
        user, daily_coins, daily_xp = user.claim_daily()
        
        # Пользователь получает катану
        user = user.acquire_katana(10.0)
        
        # Пользователь улучшает катану
        user = user.upgrade_katana(5.0)
        
        # Пользователь получает достижения
        user = user.check_achievements()
        
        # Проверяем итоговое состояние
        assert user.messages_count == 1
        assert user.xp == XP(50 + daily_xp)
        assert user.coins == Coins(25.0 + daily_coins)
        assert user.daily_streak == 1
        assert user.has_katana is True
        assert user.katana.length == 15.0
        assert Achievement.FIRST_MESSAGE in user.achievements
        assert user.is_active is True
    
    def test_user_level_progression(self):
        """Тест прогрессии уровней пользователя."""
        user = create_new_user(user_id=123456789)
        
        initial_level = user.level.level
        
        # Добавляем достаточно XP для повышения уровня
        user = user.add_xp(200)  # Должно хватить для 2 уровня
        
        new_level = user.level.level
        assert new_level > initial_level
        assert user.level.current_xp >= 0
    
    def test_error_recovery(self):
        """Тест восстановления после ошибок."""
        user = create_new_user(user_id=123456789)
        
        # Пытаемся потратить больше монет, чем есть
        try:
            user.spend_coins(100.0)
            assert False, "Должна быть ошибка"
        except InsufficientFundsError:
            pass  # Ожидаемая ошибка
        
        # Пользователь всё ещё валиден
        assert user.coins == Coins(0.0)
        assert user.is_active is True
        
        # Добавляем монеты и успешно тратим
        user = user.add_coins(200.0)
        user = user.spend_coins(100.0)
        assert user.coins == Coins(100.0)


if __name__ == "__main__":
    # Запускаем тесты
    pytest.main([__file__, "-v", "-s"])