"""
📢 Обработчики команды ZOV (Созыв).
"""

import asyncio
import html
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from src.bot.filters import AdminFilter
from src.core.config import settings
from src.core.container import Container

logger = logging.getLogger(__name__)

router = Router(name="zov")
router.message.filter(AdminFilter())

# One cancellable run per target chat (one polling worker).
_runs = {}


def target(message):
    if message.chat.type in ('group', 'supergroup'):
        return message.chat.id
    return settings.main_chat_id if message.chat.type == 'private' else None


async def telegram(call, *args, **kwargs):
    try:
        return await call(*args, **kwargs)
    except TelegramRetryAfter as delay:
        await asyncio.sleep(delay.retry_after)
        return await call(*args, **kwargs)


def mention(member):
    if member.user.is_bot or member.status not in ('member', 'administrator', 'creator', 'restricted'):
        return None
    if member.status == 'restricted' and not member.is_member:
        return None
    user = member.user
    return (f'@{user.username}' if user.username else
            f'<a href="tg://user?id={user.id}">{html.escape(user.full_name[:64])}</a>')


async def _run(bot, container, chat_id):
    # Bot API cannot enumerate the group. Seed with current admins and stream
    # previously observed IDs for THIS chat, checking membership at send time.
    admins = await telegram(bot.get_chat_administrators, chat_id)
    seen = set()
    batch = []
    sent = rewarded = unchecked = 0

    async def flush():
        nonlocal sent, rewarded
        if sent:
            await asyncio.sleep(5)
        await telegram(bot.send_message, chat_id, '📢 <b>Сбор в чате</b>\n' + ' · '.join(text for _, text in batch), parse_mode='HTML')
        sent += len(batch)
        for uid, _ in batch:
            try:
                if await container.economy_service.distribute_zov_reward(uid, 1.0):
                    rewarded += 1
            except Exception:
                logger.exception('Zov bonus failed chat=%s user=%s', chat_id, uid)
        batch.clear()

    async def add(member):
        text = mention(member)
        if text:
            batch.append((member.user.id, text))
            if len(batch) == 5:
                await flush()

    for admin in admins:
        seen.add(admin.user.id)
        await add(admin)
    cursor = container.mongo_client.database.chat_user_activities.find({'chat_id': chat_id}, {'user_id': 1})
    async for row in cursor:
        uid = row.get('user_id')
        if type(uid) is not int or uid <= 0 or uid in seen:
            continue
        seen.add(uid)
        try:
            member = await telegram(bot.get_chat_member, chat_id, uid)
        except TelegramBadRequest:
            unchecked += 1
            continue
        await add(member)
    if batch:
        await flush()
    await bot.send_message(chat_id, f'Созыв завершён · упомянуто: {sent}\nНачислено бонусов: {rewarded}\nНе удалось проверить: {unchecked}', parse_mode=None)


@router.message(Command('senseizov'))
async def cmd_zov(message: Message, container: Container):
    chat_id = target(message)
    if not chat_id:
        await message.answer('Запусти /senseizov в группе или настрой MAIN_CHAT_ID для запуска из лички.')
        return
    if chat_id in _runs:
        await message.answer('Созыв уже идёт. Для остановки: /senseinezov')
        return

    async def run():
        try:
            me = await telegram(message.bot.get_chat_member, chat_id, message.bot.id)
            if me.status not in ('administrator', 'creator'):
                await message.answer('Для созыва бот должен быть администратором целевой группы.')
                return
            await message.bot.send_message(chat_id, '📢 Начинаю созыв известных участников. Остановка: /senseinezov')
            await _run(message.bot, container, chat_id)
        except Exception:
            logger.exception('Zov interrupted chat=%s', chat_id)
            await message.answer('Созыв прерван. Проверь права бота и доступ к Telegram.')

    task = asyncio.create_task(run())
    _runs[chat_id] = task
    def finished(done):
        _runs.pop(chat_id, None)
        if not done.cancelled() and done.exception():
            logger.error('Could not deliver zov status in chat %s', chat_id)
    task.add_done_callback(finished)


@router.message(Command('senseinezov'))
async def cmd_stop_zov(message: Message):
    task = _runs.get(target(message))
    if not task or task.done():
        await message.answer('Сейчас нет активного созыва.')
        return
    task.cancel()
    await message.answer('Созыв остановлен. Уже отправленные упоминания останутся в чате.')
