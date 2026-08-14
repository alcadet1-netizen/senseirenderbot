"""
🧪 Тесты уровней.
"""

import pytest
from src.services.level_service import LevelService
from src.core.constants import LEVEL_NAMES, LEVEL_XP_REQUIREMENTS


class TestLevelService:
    """Тесты сервиса уровней."""

    def setup_method(self):
        self.service = LevelService()

    def test_get_level_zero_xp(self):
        assert self.service.get_level(0) == 0

    def test_get_level_300_xp(self):
        assert self.service.get_level(300) == 1

    def test_get_level_max(self):
        assert self.service.get_level(200000) == 20
        assert self.service.get_level(500000) == 20

    def test_get_level_name(self):
        assert "👻 Призрак чата" in self.service.get_level_name(0)

    def test_check_level_up(self):
        result = self.service.check_level_up(200, 400)
        assert result is not None
        assert result[0] == 0
        assert result[1] == 1

    def test_no_level_up(self):
        result = self.service.check_level_up(100, 200)
        assert result is None


class TestLevelConstants:
    """Тесты констант."""

    def test_level_names_complete(self):
        for level in range(21):
            assert level in LEVEL_NAMES

    def test_level_xp_increasing(self):
        prev_xp = 0
        for level in sorted(LEVEL_XP_REQUIREMENTS.keys()):
            assert LEVEL_XP_REQUIREMENTS[level] > prev_xp
            prev_xp = LEVEL_XP_REQUIREMENTS[level]