"""Public challenges: no money moves until a second player accepts."""
import secrets
import time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo.errors import DuplicateKeyError

from src.bot.middlewares.group_admin import group_admin_access
from src.services.hedgehog_service import GameError


def active_battle(container, uid):
    matches = [d for d in container.duel_service.duels.values()
               if d.accepted and uid in (d.challenger_id, d.opponent_id)]
    return max(matches, key=lambda d: (not d.finished, d.created_at), default=None)


async def arena(container, uid):
    duel = active_battle(container, uid)
    if duel:
        return dict(phase='finished' if duel.finished else 'fight', id=duel.id,
                    round=duel.round_num, bet=duel.bet, exchange=duel.last_exchange,
                    side=int(uid == duel.opponent_id),
                    names=[duel.challenger_name or 'Сэнсэй', duel.opponent_name or 'Ниндзя'],
                    hits=[duel.hits[duel.challenger_id], duel.hits[duel.opponent_id]],
                    seconds=max(0, int(duel.round_deadline_mono - time.monotonic())),
                    moves=duel.actions.get(uid, {}), winner=duel.winner_id == uid,
                    draw=duel.winner_id is None)
    offer = await container.mongo_client.database.dojo_duel_offers.find_one(
        {'_id': uid, 'expires': {'$gt': time.time()}, 'status': {'$in': ['open', 'joining']}})
    return {'phase': 'waiting' if offer else 'lobby', 'chat': (offer or {}).get('title', ''),
            'seconds': max(0, int((offer or {}).get('expires', 0) - time.time()))}


async def publish(container, uid, name, bet):
    if type(bet) is not int or bet not in (0, 300, 500, 1000):
        raise GameError('Выбери ставку из списка.')
    db = container.mongo_client.database
    player = await db.users.find_one({'id': uid, 'is_banned': {'$ne': True}})
    if not player or player.get('coins', 0) < bet:
        raise GameError('Профиль недоступен или недостаточно Coin.')
    if container.duel_service._is_in_active_duel(uid):
        raise GameError('Сначала заверши текущую дуэль.')
    activity = await db.chat_user_activities.find_one({'user_id': uid, 'chat_id': {'$lt': 0}}, sort=[('last_activity', -1)])
    chat = (activity or {}).get('chat_id') or container.settings.main_chat_id
    bot = container.bot
    if not chat or not await group_admin_access.allowed(bot, chat):
        raise GameError('Напиши в игровой группе, где Сенсей — администратор.')
    member = await bot.get_chat_member(chat, uid)
    if member.status in ('left', 'kicked') or getattr(member, 'is_member', True) is False:
        raise GameError('Ты больше не состоишь в этой группе.')
    title = (await bot.get_chat(chat)).title or 'Игровой чат'
    now = time.time()
    token = secrets.token_hex(12)
    offers = db.dojo_duel_offers
    try:
        await offers.update_one({'_id': uid, 'expires': {'$lte': now}}, {'$set': dict(
            token=token, chat=chat, title=title, expires=now+120, status='open', bet=bet)}, upsert=True)
    except DuplicateKeyError:
        raise GameError('Вызов уже опубликован. Новый доступен через две минуты.')
    await bot.send_message(chat, f'⚔️ {name} приглашает на дуэль!\nСтавка каждого: {bet} Coin.\nПервый соперник может принять за 120 секунд. Управление: /dojo → VS или личка бота.',
        parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text=f'Принять дуэль · {bet} Coin', callback_data=f'vs:{uid}:{token}')]]))
    return {'phase': 'waiting', 'chat': title, 'seconds': 120}
