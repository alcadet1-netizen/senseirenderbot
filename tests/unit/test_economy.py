"""
🧪 Тесты экономики.
"""

import pytest
from src.services.level_service import LevelService
from src.core.constants import HALVING_THRESHOLDS


class TestLevelService:
    """Тесты сервиса уровней."""

    def setup_method(self):
        self.service = LevelService()

    def test_get_level_zero_xp(self):
        """Уровень при 0 XP."""
        assert self.service.get_level(0) == 0

    def test_get_level_300_xp(self):
        """Уровень при 300 XP."""
        assert self.service.get_level(300) == 1

    def test_get_level_1000_xp(self):
        """Уровень при 1000 XP."""
        assert self.service.get_level(1000) == 2

    def test_get_level_max(self):
        """Максимальный уровень."""
        assert self.service.get_level(200000) == 20
        assert self.service.get_level(500000) == 20

    def test_get_level_name(self):
        """Названия уровней."""
        assert "👻 Призрак чата" in self.service.get_level_name(0)
        assert "Сатоши" in self.service.get_level_name(1)

    def test_check_level_up(self):
        """Проверка level up."""
        result = self.service.check_level_up(200, 400)
        assert result is not None
        assert result[0] == 0  # old level
        assert result[1] == 1  # new level

    def test_no_level_up(self):
        """Нет level up."""
        result = self.service.check_level_up(100, 200)
        assert result is None


class TestHalving:
    """Тесты халвинга."""

    def test_halving_thresholds_sorted(self):
        """Пороги халвинга отсортированы."""
        assert HALVING_THRESHOLDS == sorted(HALVING_THRESHOLDS)

    def test_halving_thresholds_count(self):
        """Количество порогов халвинга."""
        assert len(HALVING_THRESHOLDS) >= 5