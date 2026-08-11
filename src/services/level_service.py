"""
📊 Сервис уровней.
"""

from typing import Optional, Tuple

from src.core.constants import LEVEL_NAMES, LEVEL_XP_REQUIREMENTS


class LevelService:
    """Сервис для работы с уровнями."""

    def get_level(self, xp: int) -> int:
        """Определить уровень по XP."""
        level = 0
        for lvl, required_xp in sorted(LEVEL_XP_REQUIREMENTS.items()):
            if xp >= required_xp:
                level = lvl
            else:
                break
        return level

    def get_level_name(self, level: int) -> str:
        """Получить название уровня."""
        return LEVEL_NAMES.get(level, LEVEL_NAMES.get(0, "Неизвестный"))

    def get_xp_for_next_level(self, current_level: int) -> int:
        """Получить XP для следующего уровня."""
        next_level = current_level + 1
        return LEVEL_XP_REQUIREMENTS.get(next_level, LEVEL_XP_REQUIREMENTS.get(20, 200000))

    def get_progress(self, xp: int) -> Tuple[int, int, int]:
        """Получить прогресс: (current_level, current_xp_in_level, xp_needed_for_next)"""
        level = self.get_level(xp)
        current_level_xp = LEVEL_XP_REQUIREMENTS.get(level, 0)
        next_level_xp = self.get_xp_for_next_level(level)
        
        xp_in_level = xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        
        return level, xp_in_level, xp_needed

    def check_level_up(self, old_xp: int, new_xp: int) -> Optional[Tuple[int, int, str]]:
        """Проверить повышение уровня. Returns: (old_level, new_level, new_level_name) или None"""
        old_level = self.get_level(old_xp)
        new_level = self.get_level(new_xp)
        
        if new_level > old_level:
            return old_level, new_level, self.get_level_name(new_level)
        return None