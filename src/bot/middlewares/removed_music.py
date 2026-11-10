"""Retired music invocations are silent, including random/AI reactions."""
import re
from aiogram import BaseMiddleware
from aiogram.types import Update

RETIRED = re.compile(
    r'^(?:[/!.](?:music|find|m|mus|музыка)(?:@[a-z0-9_]+)?|найти|найди|скачай|скачать)(?:\s|$)',
    re.IGNORECASE)


class RemovedMusicMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Update) and event.message:
            message = event.message
            if not message.successful_payment and RETIRED.match((message.text or '').lstrip()):
                return None
        return await handler(event, data)
