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
        opponent = duel.actions.get(duel.opponent_id if uid == duel.challenger_id else duel.challenger_id, {})
        return dict(opponent_ready=bool(opponent.get('attack') and opponent.get('dodge')), phase='finished' if duel.finished else ('fight' if duel.round_num else 'connecting'), id=duel.id,
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


async def prepare_private_share(container, uid, name, bet):
    """Make the link usable BEFORE the Telegram sheet opens (no inline feedback)."""
    from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, LinkPreviewOptions
    if type(bet) is not int or not 300 <= bet <= 2**53-1:
        raise GameError('Минимальная ставка — 300 Coin.')
    db = container.mongo_client.database
    if container.duel_service._is_in_active_duel(uid) or not await db.users.find_one(
            {'id': uid, 'is_banned': {'$ne': True}, 'coins': {'$gte': bet}}):
        raise GameError('Проверь баланс и заверши текущую дуэль.')
    token = secrets.token_hex(12)
    bot = container.bot
    url = f'https://t.me/{(await bot.me()).username}?startapp=vs_{uid}_{token}'
    card = InlineQueryResultArticle(id=f'dm_{token}', title='Вызов на дуэль',
        input_message_content=InputTextMessageContent(parse_mode=None,
            message_text=f'⚔️ {name} вызывает на дуэль! Ставка каждого: {bet} Coin.\n{url}',
            link_preview_options=LinkPreviewOptions(is_disabled=True)))
    prepared = await bot.save_prepared_inline_message(user_id=uid, result=card,
        allow_user_chats=True, allow_group_chats=False, allow_channel_chats=False, allow_bot_chats=False)
    now = time.time()
    try:
        await db.dojo_duel_offers.update_one({'_id': uid, '$or': [{'expires': {'$lte': now}},
            {'status': {'$in': ['closed', 'draft']}}]}, {'$set': dict(token=token, chat=0,
            title='Личная дуэль', expires=now+120, status='open', bet=bet, rival=None, rematch=None,
            inline_private=True, inline_arena=None, message_id=None, share_pending=True)}, upsert=True)
    except DuplicateKeyError:
        raise GameError('Приглашение уже активно. Дождись соперника.')
    return {'prepare_id': prepared.id, 'token': token}


async def finish_private_share(container, uid, token, sent):
    if not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{24}', token) or type(sent) is not bool:
        raise GameError('Некорректный ответ отправки.')
    now = time.time()
    # A late/cancelled callback must never undo an accepted fight or a newer invitation.
    await container.mongo_client.database.dojo_duel_offers.update_one(
        {'_id': uid, 'token': token, 'status': 'open', 'share_pending': True},
        {'$set': {'share_pending': False, **({'expires': now+120} if sent else {'status': 'closed'})}})
    return await arena(container, uid)


async def open_invitation(container, uid, owner, token, *, accept=False):
    db = container.mongo_client.database
    key = {'_id': owner, 'token': token, 'status': 'open', 'expires': {'$gt': time.time()}}
    offer = await db.dojo_duel_offers.find_one(key)
    if not offer or owner == uid:
        return await arena(container, uid)
    if offer.get('rival') not in (None, uid):
        raise GameError('Это персональный вызов другому игроку.')
    if offer['bet'] < 300:
        raise GameError('Минимальная ставка — 300 Coin.')
    if not accept:
        return {'phase': 'invited', 'bet': offer['bet'], 'chat': offer['title']}
    if offer['chat'] < 0:
        member = await container.bot.get_chat_member(offer['chat'], uid)
        if member.status in ('left', 'kicked') or getattr(member, 'is_member', True) is False:
            raise GameError('Вызов доступен участникам этой группы.')
    player = await db.users.find_one({'id': uid, 'is_banned': {'$ne': True}})
    if not player or player.get('coins', 0) < offer['bet']:
        raise GameError('Недостаточно Coin для ставки.')
    if (offer['chat'] > 0 or offer.get('inline_private')) and (not player.get('has_katana') or player.get('coins', 0) <= 0):
        raise GameError('Для личной дуэли нужны катана и положительный баланс.')
    if container.duel_service._is_in_active_duel(uid):
        raise GameError('Сначала заверши текущую дуэль.')
    key['expires'] = {'$gt': time.time()}
    locked = await db.dojo_duel_offers.update_one(key, {'$set': {'status': 'joining'}})
    if not locked.matched_count:
        raise GameError('Вызов занят или истёк.')
    # A plain inline DM cannot be edited and Telegram does not reveal its peer.
    # Once accepted, use the accepting player's bot DM for the arena chronicle.
    arena_chat = uid if offer.get('inline_private') and not offer.get('inline_arena') else offer['chat']
    result = await container.duel_service.create_duel(owner, uid, offer['bet'], arena_chat, container.bot,
                                                       request_id=f'dojo:{token}')
    if not isinstance(result, str):
        result.inline_arena = offer.get('inline_arena')
        result.inline_private = bool(offer.get('inline_private'))
        result.dojo_only = True
        result.challenge_message_id = offer.get('message_id')
        await container.duel_service.process_decision(result.id, uid, 'a')
    await db.dojo_duel_offers.update_one({'_id': owner, 'token': token}, {'$set': {'status': 'closed'}})
    if isinstance(result, str):
        raise GameError(result)
    return await arena(container, uid)


async def publish(container, uid, name, bet, chat=None, rematch=None, recipient=None):
    if rematch is not None:
        duel = active_battle(container, uid)
        if not duel or not duel.finished or duel.id != rematch or duel.bet != bet:
            raise GameError('Реванш недоступен.')
        rival = duel.opponent_id if uid == duel.challenger_id else duel.challenger_id
        # Both requests share the finished match (and therefore the same lock).
        async with duel.lock:
            invitation = await container.mongo_client.database.dojo_duel_offers.find_one({
                '_id': rival, 'rival': uid, 'rematch': rematch, 'status': 'open', 'expires': {'$gt': time.time()}})
            if invitation:
                return await open_invitation(container, uid, rival, invitation['token'], accept=True)
            return await _publish(container, uid, name, bet, chat, rematch, recipient)
    return await _publish(container, uid, name, bet, chat, rematch, recipient)


async def _publish(container, uid, name, bet, chat=None, rematch=None, recipient=None):
    if type(bet) is not int or not 300 <= bet <= 2**53-1:
        raise GameError('Минимальная ставка — 300 Coin.')
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
    inline_arena = duel.inline_arena if rematch is not None else None
    if inline_arena:
        title = 'Реванш'
    elif chat > 0:
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
    bot_name = (await bot.me()).username
    launch_url = f'https://t.me/{bot_name}?startapp=vs_{uid}_{token}'
    offers = db.dojo_duel_offers
    try:
        await offers.update_one({'_id': uid, '$or': [{'expires': {'$lte': now}}, {'status': 'closed'}]}, {'$set': dict(
            token=token, chat=chat, title=title, expires=now+120, status='open', bet=bet, rival=rival, rematch=rematch, message_id=None, inline_arena=inline_arena,
            inline_private=bool(inline_arena and duel.inline_private))}, upsert=True)
    except DuplicateKeyError:
        raise GameError('Вызов уже опубликован. Новый доступен через две минуты.')
    mode = 'на реванш' if rematch is not None else 'на дуэль'
    terms = ('Только для тебя: нужна катана и положительный баланс, достаточный для ставки.'
             if chat > 0 else 'Прими приглашение, чтобы присоединиться.')
    try:
        text = f'⚔️ {name} приглашает {mode}!\nСтавка каждого: {bet} Coin.\n{terms} Вызов действует 120 секунд.'
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'Открыть дуэль · {bet} Coin', url=launch_url)]])
        if chat > 0 or (inline_arena and duel.inline_private):
            text += f'\n{launch_url}'
            markup = None
        if inline_arena:
            await bot.edit_message_text(inline_message_id=inline_arena, text=text, parse_mode=None, reply_markup=markup)
        else:
            sent = await bot.send_message(chat, text, parse_mode=None, reply_markup=markup)
    except (TelegramBadRequest, TelegramForbiddenError):
        await offers.update_one({'_id': uid, 'token': token}, {'$set': {'status': 'closed'}})
        raise GameError('Не удалось доставить вызов. Проверь доступ бота к чату.')
    if not inline_arena:
        await offers.update_one({'_id': uid, 'token': token}, {'$set': {'message_id': sent.message_id}})
    return {'phase': 'waiting', 'chat': title, 'seconds': 120}
