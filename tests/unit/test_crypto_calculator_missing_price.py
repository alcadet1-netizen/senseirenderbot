"""Regression: every unavailable-price result must produce text, not TypeError."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.crypto_service import CryptoService


@pytest.mark.parametrize('price', [None, 0, -1])
@pytest.mark.asyncio
async def test_calculator_missing_price(price):
    service = CryptoService(SimpleNamespace(ton_api_key=''))
    service._fetch_price_with_fallback = AsyncMock(return_value=price)
    result = await service.get_calculator_message('unknown_coin', 100)
    assert 'Не удалось найти курс' in result


@pytest.mark.asyncio
async def test_calculator_valid_price():
    service = CryptoService(SimpleNamespace(ton_api_key=''))
    service._fetch_price_with_fallback = AsyncMock(return_value=5.5)
    result = await service.get_calculator_message('ton', 100)
    assert '550.0000 USDT' in result
