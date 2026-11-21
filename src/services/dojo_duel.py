"""Public challenges: no money moves until a second player accepts."""
import re
import secrets
import time

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo.errors import DuplicateKeyError

from src.bot.middlewares.group_admin import group_admin_access
from src.services.hedgehog_service import GameError


def active_battle(container, uid):
    matches = [d for d in container.duel_service.duels.values()
               if d.dojo_only and d.accepted and uid in (d.challenger_id, d.opponent_id)]
    return max(matches, key=lambda d: (not d.finished, d.created_at), default=None)


async def arena(container, uid):
    duel = active_battle(container, uid)
    offer = None
    if not duel or duel.finished:
        offer = await container.mongo_client.database.dojo_duel_offers.find_one(
            {'_id': uid, 'expires': {'$gt': time.time()}, 'status': {'$in': ['open', 'joining']}})
    if duel and not offer:
        if not duel.round_num and time.monotonic() < duel.round_deadline_mono:
            duel.connected.add(uid)
        return dict(phase='finished' if duel.finished else ('fight' if duel.round_num else 'connecting'), id=duel.id,
                    round=duel.round_num, bet=duel.bet, exchange=duel.last_exchange,
                    side=int(uid == duel.opponent_id),
                    names=[duel.challenger_name or 'Сэнсэй', duel.opponent_name or 'Ниндзя'],
                    hits=[duel.hits[duel.challenger_id], duel.hits[duel.opponent_id]],
                    seconds=max(0, int(duel.round_deadline_mono - time.monotonic())),
                    moves=duel.actions.get(uid, {}), winner=duel.winner_id == uid,
                    draw=duel.winner_id is None)
    return {'phase': 'waiting' if offer else 'lobby', 'chat': (offer or {}).get('title', ''),
            'seconds': max(0, int((offer or {}).get('expires', 0) - time.time()))}


async def chat_ids(container, uid):
    rows = await container.mongo_client.database.chat_user_activities.find(
        {'user_id': uid, 'chat_id': {'$lt': 0}}, {'chat_id': 1}).sort('last_activity', -1).limit(30).to_list(30)
    return {i for i in [container.settings.main_chat_id, *(r['chat_id'] for r in rows)] if i < 0}


async def chat_choices(container, uid):
    from aiogram.exceptions import TelegramAPIError
    choices = []
    for chat in await chat_ids(container, uid):
        try:
            if not await group_admin_access.allowed(container.bot, chat):
                continue
            member = await container.bot.get_chat_member(chat, uid)
            if member.status in ('left', 'kicked') or getattr(member, 'is_member', True) is False:
                continue
            choices.append({'id': chat, 'title': (await container.bot.get_chat(chat)).title})
        except TelegramAPIError:
            continue
    return {'chats': choices}


async def publish(container, uid, name, bet, chat=None, rematch=None, recipient=None):
    if type(bet) is not int or bet not in (0, 300, 500, 1000):
        raise GameError('Выбери ставку из списка.')
    db = container.mongo_client.database
    player = await db.users.find_one({'id': uid, 'is_banned': {'$ne': True}})
    if not player or player.get('coins', 0) < bet:
        raise GameError('Профиль недоступен или недостаточно Coin.')
    if container.duel_service._is_in_active_duel(uid):
        raise GameError('Сначала заверши текущую дуэль.')
    rival = None
    if recipient is not None and (chat is not None or rematch is not None):
        raise GameError("Выбери один способ приглашения.")
    if rematch is not None:
        duel = active_battle(container, uid)
        if not duel or not duel.finished or duel.id != rematch or duel.bet != bet:
            raise GameError('Реванш недоступен.')
        chat = duel.chat_id
        rival = duel.opponent_id if uid == duel.challenger_id else duel.challenger_id
        if chat > 0:
            chat = rival  # A private rematch always goes to the other player.
    elif recipient is not None:
        if not isinstance(recipient, str) or not re.fullmatch(r'@?[A-Za-z0-9_]{1,32}', recipient):
            raise GameError('Укажи @username игрока.')
        handle = recipient.lstrip('@')
        profile = await db.users.find_one({'username': {'$regex': f'^{handle}$', '$options': 'i'},
                                           'is_banned': {'$ne': True}, 'is_bot': {'$ne': True}})
        if not profile or profile['id'] == uid:
            raise GameError('Выбери другого зарегистрированного игрока.')
        chat = rival = profile['id']
    elif type(chat) is not int or chat not in await chat_ids(container, uid):
        raise GameError('Выбери свою игровую группу.')
    bot = container.bot
    if chat > 0:
        try:
            private = await bot.get_chat(chat)
        except (TelegramBadRequest, TelegramForbiddenError):
            raise GameError('Личка недоступна. Сопернику нужно открыть бота и нажать /start.')
        if private.type != 'private' or (recipient is not None and
                (private.username or '').lower() != handle.lower()):
            raise GameError('Ник игрока изменился. Проверь @username.')
        title = private.first_name or 'Личный вызов'
    else:
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
        await offers.update_one({'_id': uid, '$or': [{'expires': {'$lte': now}}, {'status': 'closed'}]}, {'$set': dict(
            token=token, chat=chat, title=title, expires=now+120, status='open', bet=bet, rival=rival)}, upsert=True)
    except DuplicateKeyError:
        raise GameError('Вызов уже опубликован. Новый доступен через две минуты.')
    mode = 'на реванш' if rematch is not None else 'на дуэль'
    terms = ('Только для тебя: нужна катана и положительный баланс, достаточный для ставки.'
             if chat > 0 else 'Прими приглашение, чтобы присоединиться.')
    try:
        await bot.send_message(chat, f'⚔️ {name} приглашает {mode}!\nСтавка каждого: {bet} Coin.\n{terms} Вызов действует 120 секунд. Управление: /dojo → VS.',
            parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text=f'Принять дуэль · {bet} Coin', callback_data=f'vs:{uid}:{token}')]]))
    except (TelegramBadRequest, TelegramForbiddenError):
        await offers.update_one({'_id': uid, 'token': token}, {'$set': {'status': 'closed'}})
        raise GameError('Не удалось доставить вызов. Проверь доступ бота к чату.')
    return {'phase': 'waiting', 'chat': title, 'seconds': 120}
