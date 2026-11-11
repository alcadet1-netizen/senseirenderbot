"""Opt-in short conversation reactions and a native educational attention lab."""
import logging

from aiogram import BaseMiddleware, Router
from aiogram.filters import Command
from aiogram.types import ReplyParameters

from src.bot.middlewares.group_admin import group_admin_access
from src.bot.native_widgets import send_native_widget, send_private_widget_to_chat
from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure
from src.services.fly_service import (FlyService, REPLY_CHANCE_BPS, DAILY_ATTEMPT_LIMIT,
    CHAT_COOLDOWN_SECONDS, USER_COOLDOWN_SECONDS)
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
            f' ИИ-ответы через API «Сенсей мудрец»: выбранное сообщение передаётся провайдеру Groq без истории и имени автора. Шанс: {REPLY_CHANCE_BPS / 100:g}%. Лимит: {DAILY_ATTEMPT_LIMIT} попыток в сутки, пауза {CHAT_COOLDOWN_SECONDS // 60} мин. в чате и {USER_COOLDOWN_SECONDS // 60} мин. для одного автора.', parse_mode=None)
        return
    try:
        if message.chat.type in {'group', 'supergroup'}:
            if not message.from_user or message.from_user.is_bot or message.sender_chat:
                await message.answer('Открой личку бота и вызови /senseifly от своего аккаунта.', parse_mode=None)
                return
            await send_private_widget_to_chat(message.bot, container, message.from_user.id,
                                              message.chat.id, fly_html(), caption='Sensei FLY LAB')
        else:
            await send_native_widget(message.bot, container, message.chat.id, fly_html(), allow_queries=False, caption='Sensei FLY LAB')
    except WIDGET_TRANSPORT_ERRORS as exc:
        failure = describe_failure(exc, message.bot)
        await message.answer(
            'Лаборатория Fly не доставлена в этот чат. ' + failure.advice +
            ' Для вызова из группы сначала открой личку бота и нажми Start. '
            'Если создание прошло, личный экземпляр остаётся у тебя; пересылку Telegram может запретить.' +
            f' Код: {failure.category} / {failure.reference}. '
            'Реакции в чате настраиваются отдельно: /senseifly status. '
            'Mini App вместо нативного виджета не открываю.', parse_mode=None)


class FlyReactionMiddleware(BaseMiddleware):
    def __init__(self, container):
        self.service = FlyService(container)

    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        try:
            if data.get('automatic_reply_attempted') or not self.service.container.settings.fly_reactions_enabled:
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
                key, _ = reserved
                text = await self.service.container.digest_service.chat_sage_reply(event.text)
                if not text:
                    await self.service.db.fly_decisions.update_one({'_id': key}, {'$set': {'status': 'ai_silent_or_unavailable'}})
                    return result
                # Permissions can change while the external model is thinking.
                if not await group_admin_access.allowed(event.bot, event.chat.id):
                    await self.service.db.fly_decisions.update_one({'_id': key}, {'$set': {'status': 'access_lost'}})
                    return result
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
