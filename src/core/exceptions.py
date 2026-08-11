"""
⚠️ Кастомные исключения приложения.
"""


class SenseiBotError(Exception):
    """Базовое исключение бота."""
    pass


class InsufficientFundsError(SenseiBotError):
    """Недостаточно средств."""
    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"Требуется: {required}, доступно: {available}")


class InsufficientTicketsError(SenseiBotError):
    """Недостаточно билетов."""
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"Требуется билетов: {required}, доступно: {available}")


class UserNotFoundError(SenseiBotError):
    """Пользователь не найден."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"Пользователь {user_id} не найден")


class DailyAlreadyClaimedError(SenseiBotError):
    """Дневной бонус уже получен."""
    def __init__(self, next_claim_time: str):
        self.next_claim_time = next_claim_time
        super().__init__(f"Следующий бонус доступен: {next_claim_time}")


class MaintenanceModeError(SenseiBotError):
    """Бот в режиме обслуживания."""
    pass


class BankInsufficientFundsError(SenseiBotError):
    """В банке недостаточно средств."""
    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"В банке недостаточно: требуется {required}, доступно {available}")


class UserBannedError(SenseiBotError):
    """Пользователь забанен."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"Пользователь {user_id} забанен")


class CooldownError(SenseiBotError):
    """Кулдаун действия."""
    def __init__(self, remaining_seconds: float):
        self.remaining_seconds = remaining_seconds
        hours, rem = divmod(remaining_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        self.formatted_time = f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"
        super().__init__(f"Подождите {self.formatted_time}")


class NoKatanaError(SenseiBotError):
    """У пользователя нет катаны."""
    def __init__(self):
        super().__init__("У вас нет катаны!")