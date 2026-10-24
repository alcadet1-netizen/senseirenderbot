"""
🧪 Тесты обмена.
"""

import pytest
from src.core.constants import EXCHANGE_COINS_TO_TICKET, EXCHANGE_TICKET_TO_COINS


class TestExchangeConstants:
    """Тесты констант обмена."""

    def test_coins_to_ticket_rate(self):
        """Курс монеты -> билет."""
        assert EXCHANGE_COINS_TO_TICKET == 3000

    def test_ticket_to_coins_rate(self):
        """Курс билет -> монеты."""
        assert EXCHANGE_TICKET_TO_COINS == 2600

    def test_exchange_spread(self):
        """Спред при обмене."""
        # Покупка билета за 3000, продажа за 2600 = ~13.3% спред
        spread = (EXCHANGE_COINS_TO_TICKET - EXCHANGE_TICKET_TO_COINS) / EXCHANGE_COINS_TO_TICKET
        assert spread == (3000 - 2600) / 3000  # ~0.133