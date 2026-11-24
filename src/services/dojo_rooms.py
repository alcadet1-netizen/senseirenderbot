"""Комнаты дуэлей: создал со ставкой — любой игрок видит и подключается.

Отличие от персонального вызова (``dojo_duel.py``): комната никому не
адресована. Она висит в списке, пока не истечёт или пока в неё не войдут.
Деньги, как и в остальных вызовах, двигаются только в момент подключения
второго игрока: до этого комната бесплатна, и никто не может потерять
ставку из-за того, что соперник не нашёлся.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Optional

from pymongo.errors import DuplicateKeyError

from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)

ROOM_MIN_BET = 300
ROOM_MAX_BET = 10_000_000
ROOM_TTL_SECONDS = 300
ROOM_MAX_ACTIVE = 3          # сколько открытых комнат может держать один игрок
ROOM_EXPIRED_KEEP = 3600     # сколько держим истёкшие записи до уборки

COLLECTION = 'dojo_duel_rooms'

STATUS_OPEN = 'open'
STATUS_JOINING = 'joining'
STATUS_PLAYING = 'playing'
STATUS_CLOSED = 'closed'


def _now() -> float:
    return time.time()


def _bet_is_valid(bet) -> bool:
    # bool — подкласс int, поэтому проверяем тип явно: True не должен
    # превращаться в ставку 1.
    return type(bet) is int and ROOM_MIN_BET <= bet <= ROOM_MAX_BET


class DojoRooms:
    """Хранилище комнат; состояние дуэли живёт в DuelService."""

    def __init__(self, container):
        self.container = container

    @property
    def collection(self):
        return self.container.mongo_client.database[COLLECTION]

    async def ensure_indexes(self) -> None:
        try:
            await self.collection.create_index('token', unique=True)
            await self.collection.create_index([('status', 1), ('expires', 1)])
        except Exception as exc:  # настройка индексов не должна ломать старт
            logger.debug('Dojo room indexes unavailable: %s', exc)

    # ------------------------------------------------------------------
    # Создание
    # ------------------------------------------------------------------

    async def create(self, user_id: int, name: str, bet: int) -> dict:
        """Создаёт комнату со ставкой.

        Ставка не резервируется: проверяем только, что игрок в принципе
        может её себе позволить. Если к моменту подключения соперника денег
        уже нет — подключение честно откажет, а не спишет в минус.
        """
        if not _bet_is_valid(bet):
            raise GameError(f'Ставка должна быть целым числом от {ROOM_MIN_BET} до {ROOM_MAX_BET} Coin.')
        db = self.container.mongo_client.database
        await self._expire_old()
        player = await db.users.find_one({'id': int(user_id), 'is_banned': {'$ne': True}})
        if not player:
            raise GameError('Профиль недоступен. Открой /dojo заново.')
        if player.get('coins', 0) < bet:
            raise GameError('Недостаточно Coin для такой ставки.')

        mine = await self.collection.count_documents(
            {'owner_id': int(user_id), 'status': {'$in': [STATUS_OPEN, STATUS_JOINING]}})
        if mine >= ROOM_MAX_ACTIVE:
            raise GameError('У тебя уже открыто несколько комнат. Закрой лишние.')

        if self.container.duel_service._is_in_active_duel(int(user_id)):
            raise GameError('Сначала заверши текущую дуэль.')

        token = secrets.token_hex(8)
        now = _now()
        doc = {
            'token': token,
            'owner_id': int(user_id),
            'owner_name': (name or 'Сэнсэй')[:64],
            'bet': bet,
            'status': STATUS_OPEN,
            'created': now,
            'expires': now + ROOM_TTL_SECONDS,
            'rival_id': None,
            'duel_id': None,
            'chat_id': None,
        }
        await self.collection.insert_one(dict(doc))
        return self._public(doc, viewer=user_id)

    async def close(self, user_id: int, token: str) -> dict:
        """Закрывает свою комнату. Ставка ещё не списана — возвращать нечего."""
        if not isinstance(token, str):
            raise GameError('Комната не найдена.')
        result = await self.collection.update_one(
            {'token': token, 'owner_id': int(user_id), 'status': {'$in': [STATUS_OPEN, STATUS_JOINING]}},
            {'$set': {'status': STATUS_CLOSED, 'closed': _now()}})
        if not result.matched_count:
            raise GameError('Эту комнату уже нельзя закрыть.')
        return {'closed': True, 'token': token}

    # ------------------------------------------------------------------
    # Просмотр
    # ------------------------------------------------------------------

    async def list_open(self, viewer_id: int, limit: int = 20) -> dict:
        # Раньше каждый опрос списка (раз в 4 секунды на игрока) делал два
        # write-запроса: update_many + delete_many. При десяти игроках это
        # пять записей в секунду в никуда. Истёкшие комнаты и так не видны
        # из-за фильтра по expires, поэтому уборку делает отдельная
        # периодическая задача, а не читатель.
        cursor = self.collection.find(
            {'status': STATUS_OPEN, 'expires': {'$gt': _now()}},
            {'token': 1, 'owner_id': 1, 'owner_name': 1, 'bet': 1, 'created': 1, 'expires': 1}
        ).sort('created', -1).limit(max(1, min(int(limit), 50)))
        rooms = [doc async for doc in cursor]
        return {
            'rooms': [self._public(r, viewer=viewer_id) for r in rooms],
            'mine': [self._public(r, viewer=viewer_id) for r in rooms
                     if r['owner_id'] == int(viewer_id)],
            'seconds': ROOM_TTL_SECONDS,
        }

    async def my_room(self, user_id: int) -> Optional[dict]:
        # expires обязателен: без него игрок видел «ждём соперника» у
        # комнаты, в которую уже никто не может войти.
        doc = await self.collection.find_one(
            {'owner_id': int(user_id), 'status': {'$in': [STATUS_OPEN, STATUS_JOINING]},
             'expires': {'$gt': _now()}},
            sort=[('created', -1)])
        return self._public(doc, viewer=user_id) if doc else None

    def _public(self, doc: dict, *, viewer: int) -> dict:
        return {
            'token': doc['token'],
            'owner_id': doc['owner_id'],
            'owner_name': doc.get('owner_name') or 'Сэнсэй',
            'bet': doc.get('bet', ROOM_MIN_BET),
            'status': doc.get('status'),
            'seconds': max(0, int(doc.get('expires', 0) - _now())),
            'is_mine': doc['owner_id'] == int(viewer),
            'duel_id': doc.get('duel_id'),
        }

    # ------------------------------------------------------------------
    # Подключение
    # ------------------------------------------------------------------

    async def join(self, user_id: int, token: str) -> dict:
        """Второй игрок входит в комнату.

        Блокировка статуса атомарна: если двое нажмут «подключиться»
        одновременно, второй получит отказ, а не второй бой поверх первого.
        """
        if not isinstance(token, str) or not token:
            raise GameError('Комната не найдена.')
        if self.container.duel_service._is_in_active_duel(int(user_id)):
            raise GameError('Сначала заверши текущую дуэль.')

        room = await self.collection.find_one({'token': token})
        if not room:
            raise GameError('Комната не найдена.')
        # Раньше на своём токене (сам себе прислал ссылку) игрок получал
        # «В эту комнату уже подключились» — это враньё и путает.
        if room['owner_id'] == int(user_id):
            raise GameError('Это твоя комната. Жди соперника.')

        now = _now()
        if room.get('status') != STATUS_OPEN:
            raise GameError('В эту комнату уже подключились.')
        if room.get('expires', 0) <= now:
            await self.collection.update_one({'token': token, 'status': STATUS_OPEN},
                                             {'$set': {'status': STATUS_CLOSED, 'closed': now}})
            raise GameError('Комната закрылась. Создай свою.')

        bet = room.get('bet', ROOM_MIN_BET)
        # Проверяем входящего ДО захвата комнаты, иначе забаненный или
        # безденежный игрок «сжигает» комнату и получает отказ от эскроу.
        joiner = await self.container.mongo_client.database.users.find_one(
            {'id': int(user_id), 'is_banned': {'$ne': True}})
        if not joiner:
            raise GameError('Профиль недоступен. Открой /dojo заново.')
        if joiner.get('coins', 0) < bet:
            raise GameError('Недостаточно Coin для этой ставки.')

        # Атомарно забираем комнату: matched_count == 0 означает, что её
        # перехватили между find_one и update_one.
        locked = await self.collection.update_one(
            {'token': token, 'status': STATUS_OPEN, 'expires': {'$gt': now}},
            {'$set': {'status': STATUS_JOINING, 'rival_id': int(user_id), 'joined': now}})
        if not locked.matched_count:
            raise GameError('В эту комнату уже подключились.')

        try:
            result = await self.container.duel_service.create_duel(
                room['owner_id'], int(user_id), bet, int(user_id), self.container.bot,
                request_id=f'room:{token}')
            if isinstance(result, str):
                # Денег не хватило у одного из игроков — комната возвращается
                # в список, чтобы её мог взять кто-то другой.
                await self.collection.update_one(
                    {'token': token, 'status': STATUS_JOINING},
                    {'$set': {'status': STATUS_OPEN, 'rival_id': None}})
                raise GameError(result)

            result.dojo_only = True
            result.room_token = token
            await self.collection.update_one(
                {'token': token},
                {'$set': {'status': STATUS_PLAYING, 'duel_id': result.id,
                          'chat_id': int(user_id)}})
            try:
                await self.container.duel_service.process_decision(result.id, int(user_id), 'a')
            except Exception:
                # Бой УЖЕ создан, ставки уже списаны. Откатывать комнату в
                # «open» нельзя: тогда в неё войдёт третий игрок и второй бой
                # поверх первого. Игроку нельзя говорить «не удалось» —
                # он решит, что не вошёл, хотя бой идёт.
                logger.exception('Room duel accepted but announcement failed: token=%s', token)
                raise GameError('Бой создан. Открой арену — соперник уже ждёт.')
        except DuplicateKeyError:
            await self.collection.update_one({'token': token, 'status': STATUS_JOINING},
                                             {'$set': {'status': STATUS_OPEN, 'rival_id': None}})
            raise GameError('Эту комнату уже заняли.')
        except GameError:
            raise
        except Exception:
            logger.exception('Room join failed: token=%s user=%s', token, user_id)
            await self.collection.update_one(
                {'token': token, 'status': STATUS_JOINING},
                {'$set': {'status': STATUS_OPEN, 'rival_id': None}})
            raise GameError('Не удалось подключиться. Попробуй ещё раз.')

        return {'joined': True, 'duel_id': result.id, 'token': token}

    async def sync_result(self, token: str, duel_id: int, finished: bool) -> None:
        """Отмечает комнату завершённой, когда бой закончился."""
        if not isinstance(token, str):
            return
        if finished:
            await self.collection.update_one(
                {'token': token},
                {'$set': {'status': STATUS_CLOSED, 'closed': _now()}})
        else:
            await self.collection.update_one(
                {'token': token, 'status': STATUS_PLAYING},
                {'$set': {'duel_id': int(duel_id)}})

    async def cleanup(self) -> None:
        """Уборка по расписанию: вызывается редко, не на каждом опросе."""
        await self._expire_old()

    async def cleanup_loop(self, every: int = 600) -> None:
        """Фоновая уборка: закрывает протухшие комнаты и метёт старые."""
        while True:
            try:
                await asyncio.sleep(max(60, int(every)))
                await self._expire_old()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug('Room cleanup loop error: %s', exc)

    async def _expire_old(self) -> None:
        """Закрывает истёкшие комнаты; старые записи убирает полностью."""
        try:
            now = _now()
            await self.collection.update_many(
                {'status': {'$in': [STATUS_OPEN, STATUS_JOINING]}, 'expires': {'$lte': now}},
                {'$set': {'status': STATUS_CLOSED, 'closed': now}})
            await self.collection.delete_many(
                {'status': STATUS_CLOSED, 'closed': {'$lte': now - ROOM_EXPIRED_KEEP}})
        except Exception as exc:
            logger.debug('Room cleanup failed: %s', exc)
