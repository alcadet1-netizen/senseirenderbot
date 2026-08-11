"""
🚀 Сервис интеграции с xRocket Pay.
"""

import logging
import uuid
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

class XRocketService:
    """Сервис для работы с xRocket Pay API."""
    
    BASE_URL = "https://pay.xrocket.tg/app"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Rocket-Pay-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def transfer(self, user_id: int, currency: str, amount: float) -> bool:
        """
        Перевод средств пользователю Telegram.
        """
        if not self.api_key:
            logger.warning("xRocket API key is missing")
            return False

        url = f"{self.BASE_URL}/transfer"
        transfer_id = str(uuid.uuid4())
        
        payload = {
            "tgUserId": user_id,
            "currency": currency,
            "amount": amount,
            "transferId": transfer_id,
            "description": "Boss Battle Reward from Sensei"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Success response usually contains 'success': true or data
                        # xRocket API often returns { "success": true, "data": { ... } }
                        if data.get("success") is False:
                            logger.error(f"XRocket transfer failed: {data}")
                            return False
                        
                        logger.info(f"XRocket transfer success: {user_id} {amount} {currency}")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"XRocket API Error {response.status}: {text}")
                        return False
        except Exception as e:
            logger.error(f"XRocket connection error: {e}")
            return False
