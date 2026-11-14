"""
🚀 Сервис интеграции с xRocket Pay.
"""

import logging
import math
import uuid
import re
import json
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class XRocketTransferRejected(Exception):
    """Explicit provider rejection, not a confirmed transfer or retry request."""
    def __init__(self, status, detail):
        self.status = status
        self.detail = detail
        super().__init__(f'xRocket HTTP {status}')


class XRocketService:
    """Сервис для работы с xRocket Pay API."""

    BASE_URL = "https://pay.xrocket.tg/app"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Rocket-Pay-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def safe_detail(self, value):
        text = str(value).replace(self.api_key, '[REDACTED]') if self.api_key else str(value)
        text = re.sub(r'https?://\S+|\b\d{5,}:[A-Za-z0-9_-]+|(?:sk-|vk1\.)\S+', '[REDACTED]', text)
        text = re.sub(r'[A-Za-z0-9_-]{28,}', '[REDACTED]', text)
        return ' '.join(text.split())[:240]

    async def error_detail(self, response):
        # Read a bounded body and only extract the documented error message.
        # Never log arbitrary HTML, response headers, requests or credentials.
        body = await response.content.read(4096)
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError):
            return 'non_json_response'
        if isinstance(data, dict) and isinstance(data.get('message'), str):
            return self.safe_detail(data['message'])
        return 'no_error_message'

    async def access_status(self):
        """Read-only application access check; does not create transfers."""
        if not self.api_key:
            return dict(ok=False, status=None, detail='XROCKET_PAY_TOKEN не настроен')
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(f'{self.BASE_URL}/info', headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        ok = isinstance(data, dict) and data.get('success') is True
                        return dict(ok=ok, status=200, detail='Доступ к приложению подтверждён' if ok else 'Ответ без подтверждения success=true')
                    return dict(ok=False, status=response.status, detail=await self.error_detail(response))
        except Exception as exc:
            return dict(ok=False, status=None, detail=type(exc).__name__)

    async def transfer(self, user_id: int, currency: str, amount: float, transfer_id: Optional[str] = None, *, raise_rejection: bool = False) -> bool:
        """
        Перевод средств пользователю Telegram.
        """
        if not self.api_key or not math.isfinite(amount) or amount <= 0:
            logger.warning("xRocket transfer unavailable: missing key or invalid amount")
            return False

        url = f"{self.BASE_URL}/transfer"
        if transfer_id is None:
            # Generate a short transfer ID (<=20 chars) to satisfy API limits
            transfer_id = uuid.uuid4().hex[:10]  # 10 hex characters

        payload = {
            "tgUserId": user_id,
            "currency": currency,
            "amount": amount,
            "transferId": transfer_id,
            "description": "Boss Battle Reward from Sensei"
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if 200 <= response.status < 300:
                        data = await response.json()
                        # Success response usually contains 'success': true or data
                        # xRocket API often returns { "success": true, "data": { ... } }
                        # Some responses come with status 201 Created but success:true.
                        if not isinstance(data, dict) or data.get("success") is not True:
                            logger.error("XRocket transfer not confirmed")
                            return False

                        logger.info(f"XRocket transfer success: {user_id} {amount} {currency} (status={response.status})")
                        return True
                    else:
                        detail = await self.error_detail(response)
                        logger.error("XRocket transfer rejected status=%s detail=%s", response.status, detail)
                        if raise_rejection and response.status in {400, 401, 403, 422}:
                            raise XRocketTransferRejected(response.status, detail)
                        return False
        except XRocketTransferRejected:
            raise
        except Exception as e:
            logger.error("XRocket request outcome unknown error_type=%s", type(e).__name__)
            return False

    async def get_balance(self) -> float:
        """Get the app balance in GRAM."""
        if not self.api_key:
            logger.warning("xRocket API key is missing")
            return 0.0
        url = f"{self.BASE_URL}/balance"

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Assume response format: {"success": true, "balance": 123.45}
                        if data.get("success"):
                            balance = data.get("balance", 0.0)
                            # Ensure float
                            return float(balance)
                        else:
                            logger.error(f"XRocket balance error: {data}")
                            return 0.0
                    else:
                        text = await response.text()
                        logger.error("XRocket API rejected request status=%s", response.status)
                        return 0.0
        except Exception as e:
            logger.error("XRocket request outcome unknown error_type=%s", type(e).__name__)
            return 0.0