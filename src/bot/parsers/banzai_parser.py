import re
from typing import Optional
from src.domain.banzai.models import BanzaiActionType, BanzaiCommand


class BanzaiCommandParser:
    """Парсер команд БАНЗАЙ."""

    # Паттерн для парсинга аргументов команды /banzai
    # Поддерживает: /banzai [мин] [ревард_тон] или /banzai stop, /banzai status и т.д.
    PATTERN = re.compile(
        r"""^\s*
        (?:(?P<action>\w+))?          # действие (например, stop, status, rules, add_time, set_time, set_reward)
        (?:\s+(?P<minutes>\d+))?      # опциональное число минут
        (?:\s+(?P<reward>[0-9]+(?:\.[0-9]+)?))?  # опциональная награда (целое или дробное число)
        \s*$""",
        re.VERBOSE | re.IGNORECASE
    )

    @classmethod
    def parse(cls, args: Optional[str]) -> BanzaiCommand:
        """Парсит аргументы команды /banzai."""
        if not args:
            # Если нет аргументов, считаем, что это запрос на запуск с параметрами по умолчанию
            # Но в оригинальном коде, если нет аргументов, то это ошибка (нужно указать время)
            # Однако в обработчике мы проверяем, что если действие не SET_TIME и нет минут, то ошибка.
            # Поэтому вернем действие UNKNOWN, чтобы обработчик решил, что делать.
            return BanzaiCommand(action=BanzaiActionType.UNKNOWN)

        match = cls.PATTERN.match(args.strip())
        if not match:
            return BanzaiCommand(action=BanzaiActionType.UNKNOWN)

        action_str = match.group("action")
        minutes_str = match.group("minutes")
        reward_str = match.group("reward")

        # Определяем действие
        action = BanzaiActionType.UNKNOWN
        if action_str:
            action_str_lower = action_str.lower()
            if action_str_lower == "stop":
                action = BanzaiActionType.STOP
            elif action_str_lower == "status":
                action = BanzaiActionType.STATUS
            elif action_str_lower == "rules":
                action = BanzaiActionType.RULES
            elif action_str_lower == "add_time":
                action = BanzaiActionType.ADD_TIME
            elif action_str_lower == "set_time":
                action = BanzaiActionType.SET_TIME
            elif action_str_lower == "set_reward":
                action = BanzaiActionType.SET_REWARD
            elif action_str_lower == "start":
                # Если указано действие start, то считаем, что нужно запустить игру
                # Но в оригинале действие start не используется, запуск происходит без указания действия
                # Поэтому мы будем считать, что если указано start, то это тоже запуск с параметрами
                action = BanzaiActionType.START

        # If action_str looks like a number, treat it as minutes (e.g., user entered "5" without action)
        if action == BanzaiActionType.UNKNOWN and action_str and action_str.isdigit():
            action = BanzaiActionType.SET_TIME
            minutes_str = action_str  # reuse the action_str as minutes
            action_str = None  # clear action_str so it doesn't interfere

        # Если действие не распознано, но указаны минуты и/или награда, то считаем, что это установка времени и запуск игры
        if action == BanzaiActionType.UNKNOWN:
            if minutes_str is not None or reward_str is not None:
                action = BanzaiActionType.SET_TIME

        # Преобразуем минуты и награду в числа, если они есть
        minutes = int(minutes_str) if minutes_str else None
        reward = float(reward_str) if reward_str else None

        return BanzaiCommand(
            action=action,
            minutes=minutes,
            reward=reward
        )