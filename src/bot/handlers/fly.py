"""Opt-in short conversation reactions and a native educational attention lab."""
import logging

from aiogram import BaseMiddleware, Router
from aiogram.filters import Command
from aiogram.types import ReplyParameters

from src.bot.middlewares.group_admin import group_admin_access
from src.bot.native_widgets import send_native_widget
from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure
from src.services.fly_service import FlyService
from src.widgets.fly import fly_html

logger = logging.getLogger(__name__)
router = Router(name='fly')


@router.message(Command('senseifly'))
async def command(message, container):
    args = (message.text or '').split()[1:]
    service = FlyService(container)
    if args:
        if args not in (['on'], ['off'], ['status']) or message.chat.type not in {'group', 'supergroup'}:
            await message.answer('В группе: /senseifly on · off · status. Без аргументов — лаборатория.', parse_mode=None)
            return
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in {'administrator', 'creator'}:
            await message.answer('Настройка доступна администратору чата.', parse_mode=None)
            return
        if args == ['status']:
            cfg = await service.db.fly_settings.find_one({'_id': message.chat.id}) or {}
            enabled = cfg.get('enabled', False) and container.settings.fly_reactions_enabled
        else:
            enabled = args == ['on']
            await service.db.fly_settings.update_one({'_id': message.chat.id}, {'$set': {'enabled': enabled}}, upsert=True)
        globally_disabled = not container.settings.fly_reactions_enabled
        if globally_disabled:
            enabled = False
        await message.answer(('Редкие реплики включены.' if enabled else 'Редкие реплики выключены.') +
            (' Глобальный выключатель активен; настройка чата сохранена.' if globally_disabled else '') +
            ' Лимит: 8 в сутки, пауза 15 минут. Модель внимания, не настоящий мозг мухи.', parse_mode=None)
        return
    try:
        await send_native_widget(message.bot, container, message.chat.id, fly_html(), allow_queries=False)
    except WIDGET_TRANSPORT_ERRORS as exc:
        failure = describe_failure(exc, message.bot)
        await message.answer(
            'Лаборатория Fly не отправлена. ' + failure.advice +
            f' Код: {failure.category} / {failure.reference}. '
            'Реакции в чате настраиваются отдельно: /senseifly status. '
            'Mini App вместо нативного виджета не открываю.', parse_mode=None)


class FlyReactionMiddleware(BaseMiddleware):
    def __init__(self, container):
        self.service = FlyService(container)

    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        try:
            if not self.service.container.settings.fly_reactions_enabled:
                return result
            from src.services.fly_service import features
            if not features(event) or not await group_admin_access.allowed(event.bot, event.chat.id):
                return result
            user = await self.service.db.users.find_one({'id': event.from_user.id})
            if user and user.get('is_banned'):
                return result
            # A deleted command/comment must not receive an orphaned response.
            if await self.service.db.campaign_deleted_messages.find_one({'_id': f'{event.chat.id}:{event.message_id}'}):
                return result
            reserved = await self.service.reserve(event)
            if reserved:
                key, text = reserved
                try:
                    await event.answer(text, parse_mode=None,
                        reply_parameters=ReplyParameters(message_id=event.message_id, allow_sending_without_reply=False))
                except Exception:
                    # No automatic retries after an ambiguous send: avoid duplicates.
                    await self.service.db.fly_decisions.update_one({'_id': key}, {'$set': {'status': 'send_failed_or_unknown'}})
                    return result
                await self.service.db.fly_decisions.update_one({'_id': key}, {'$set': {'status': 'sent'}})
        except Exception:
            logger.warning('Fly reaction skipped: unavailable state or permissions', exc_info=True)
        return result
