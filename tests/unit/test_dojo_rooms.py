"""Комнаты дуэлей: создал со ставкой — подключился любой.

Проверяем именно то, что ломалось в персональных вызовах: ставка не
двигается до подключения, в комнату не входят двое одновременно и хозяйская
комната не даёт хозяину играть с самим собой.
"""
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.dojo_rooms import DojoRooms, ROOM_MIN_BET, ROOM_TTL_SECONDS
from src.services.hedgehog_service import GameError


class Rooms:
    """Минимальное хранилище: курсор и фильтры как в Mongo."""

    def __init__(self, docs=None):
        self.docs = docs if docs is not None else []

    def _matches(self, doc, query):
        for key, value in query.items():
            if key in ('$or',):
                continue
            actual = doc.get(key)
            if isinstance(value, dict):
                for op, operand in value.items():
                    if op == '$ne' and actual == operand:
                        return False
                    if op == '$in' and actual not in operand:
                        return False
                    if op == '$gt' and not (actual is not None and actual > operand):
                        return False
                    if op == '$lte' and not (actual is not None and actual <= operand):
                        return False
            elif actual != value:
                return False
        return True

    async def find_one(self, query, sort=None):
        found = [d for d in self.docs if self._matches(d, query)]
        if sort:
            key, direction = sort[0]
            found.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return found[0] if found else None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return NS(inserted_id=doc.get('token'))

    async def update_one(self, query, update):
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get('$set') or {})
                return NS(matched_count=1, modified_count=1)
        return NS(matched_count=0, modified_count=0)

    async def update_many(self, query, update):
        hits = 0
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get('$set') or {})
                hits += 1
        return NS(matched_count=hits)

    async def delete_many(self, query):
        before = len(self.docs)
        # Мутируем на месте: тест держит ссылку на список и должен видеть
        # изменения так же, как настоящая коллекция.
        keep = [d for d in self.docs if not self._matches(d, query)]
        self.docs[:] = keep
        return NS(deleted_count=before - len(keep))

    async def count_documents(self, query):
        return sum(1 for d in self.docs if self._matches(d, query))

    def find(self, query, projection=None):
        return _Query([d for d in self.docs if self._matches(d, query)])


class _Query:
    """Курсор как в Mongo: sort(...).limit(...) и асинхронный обход."""

    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    def __aiter__(self):
        self._it = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class Database:
    """База-заглушка: доступ к коллекциям как в настоящем Mongo."""

    def __init__(self, coins=5000):
        self.users = NS(find_one=AsyncMock(return_value=(
            {'id': 1, 'coins': coins, 'is_banned': False})))
        self.dojo_duel_rooms = Rooms()

    @property
    def docs(self):
        # Один и тот же список и для сервиса, и для проверок в тесте:
        # иначе тест смотрит в пустую копию.
        return self.dojo_duel_rooms.docs

    def __getitem__(self, name):
        return getattr(self, name)


def build(*, coins=5000, in_duel=False, players=None):
    db = Database(coins)
    engine = NS(
        _is_in_active_duel=Mock(return_value=in_duel),
        create_duel=AsyncMock(return_value=NS(id=42)),
        process_decision=AsyncMock(),
    )
    container = NS(mongo_client=NS(database=db), duel_service=engine,
                   dojo_rooms=None, bot=NS())
    rooms = DojoRooms(container)
    container.dojo_rooms = rooms
    return rooms, db, engine, db.docs


@pytest.mark.asyncio
async def test_create_room_does_not_touch_the_stake():
    rooms, db, engine, docs = build()
    result = await rooms.create(1, 'Вася', 700)
    assert result['bet'] == 700
    assert result['is_mine'] is True
    # Деньги не двигаются, пока нет соперника.
    engine.create_duel.assert_not_awaited()
    assert docs[0]['status'] == 'open'
    assert 0 < result['seconds'] <= ROOM_TTL_SECONDS


@pytest.mark.asyncio
@pytest.mark.parametrize('bet', [299, 0, -100, '500', True, 2**53])
async def test_invalid_stake_is_rejected(bet):
    rooms, _, _, docs = build()
    with pytest.raises(GameError):
        await rooms.create(1, 'Вася', bet)
    assert docs == []


@pytest.mark.asyncio
async def test_stake_above_balance_is_refused_up_front():
    rooms, _, _, docs = build(coins=400)
    with pytest.raises(GameError, match='Недостаточно'):
        await rooms.create(1, 'Вася', 5000)
    assert docs == []


@pytest.mark.asyncio
async def test_second_player_joins_and_duel_starts():
    rooms, db, engine, docs = build()
    created = await rooms.create(1, 'Вася', 500)

    joined = await rooms.join(2, created['token'])

    assert joined['joined'] is True
    assert joined['duel_id'] == 42
    # Бой создаётся между хозяином и вошедшим, в личке вошедшего:
    # у хозяина не спрашивают ничего, ставка списывается только сейчас.
    engine.create_duel.assert_awaited_once()
    args = engine.create_duel.await_args.args
    assert args[:3] == (1, 2, 500)
    assert docs[0]['status'] == 'playing'


@pytest.mark.asyncio
async def test_owner_cannot_join_his_own_room():
    rooms, _, engine, _ = build()
    created = await rooms.create(1, 'Вася', 500)
    with pytest.raises(GameError, match='твоя комната'):
        await rooms.join(1, created['token'])
    engine.create_duel.assert_not_awaited()


@pytest.mark.asyncio
async def test_room_can_be_taken_by_only_one_player():
    """Второй одновременный вход не должен запускать второй бой."""
    rooms, _, engine, _ = build()
    created = await rooms.create(1, 'Вася', 500)
    await rooms.join(2, created['token'])
    engine.create_duel.reset_mock()

    with pytest.raises(GameError, match='уже подключились'):
        await rooms.join(3, created['token'])
    engine.create_duel.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_room_cannot_be_joined():
    rooms, _, engine, docs = build()
    created = await rooms.create(1, 'Вася', 500)
    docs[0]['expires'] = time.time() - 1
    with pytest.raises(GameError):
        await rooms.join(2, created['token'])
    engine.create_duel.assert_not_awaited()
    assert docs[0]['status'] == 'closed'


@pytest.mark.asyncio
async def test_failed_join_returns_room_to_the_list():
    """Если у вошедшего не хватило денег, комната не должна «сгореть»."""
    rooms, _, engine, docs = build()
    engine.create_duel.return_value = '❜ Недостаточно средств для ставки.'
    created = await rooms.create(1, 'Вася', 500)

    with pytest.raises(GameError):
        await rooms.join(2, created['token'])

    assert docs[0]['status'] == 'open'
    assert docs[0]['rival_id'] is None


@pytest.mark.asyncio
async def test_owner_can_close_room_without_losing_coins():
    rooms, _, engine, docs = build()
    created = await rooms.create(1, 'Вася', 500)
    result = await rooms.close(1, created['token'])
    assert result['closed'] is True
    assert docs[0]['status'] == 'closed'
    engine.create_duel.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_player_cannot_close_someone_elses_room():
    rooms, _, _, _ = build()
    created = await rooms.create(1, 'Вася', 500)
    with pytest.raises(GameError):
        await rooms.close(2, created['token'])


@pytest.mark.asyncio
async def test_busy_player_gets_room_list_without_his_mark():
    """Список комнат показывает ставку и владельца — этого хватает, чтобы решить."""
    rooms, _, _, _ = build()
    await rooms.create(1, 'Вася', 800)
    listing = await rooms.list_open(viewer_id=2)
    assert listing['rooms'][0]['owner_name'] == 'Вася'
    assert listing['rooms'][0]['bet'] == 800
    assert listing['rooms'][0]['is_mine'] is False
    assert listing['mine'] == []


@pytest.mark.asyncio
async def test_player_already_in_a_duel_cannot_open_or_join_rooms():
    rooms, _, engine, _ = build(in_duel=True)
    with pytest.raises(GameError, match='заверши'):
        await rooms.create(1, 'Вася', 500)
    with pytest.raises(GameError, match='заверши'):
        await rooms.join(2, 'aaaa')


@pytest.mark.asyncio
async def test_too_many_open_rooms_are_capped():
    rooms, _, _, _ = build()
    for _ in range(3):
        await rooms.create(1, 'Вася', 300)
    with pytest.raises(GameError):
        await rooms.create(1, 'Вася', 300)


@pytest.mark.asyncio
async def test_finished_duel_closes_the_room():
    rooms, _, _, docs = build()
    created = await rooms.create(1, 'Вася', 500)
    await rooms.sync_result(created['token'], 42, True)
    assert docs[0]['status'] == 'closed'
