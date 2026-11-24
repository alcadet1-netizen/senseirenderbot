"""Tasks for the /dojo miner.

Admins can add Telegram channel subscriptions and app/bot referral links.
Channel tasks verify the subscription through Telegram before paying; link
tasks are launched by the player and then claimed. Both pay a one-time
SenseiCoin reward plus a one-time energy charge. The charge is spent by one
mining cycle and never raises the permanent energy cap. Every claim is unique
per user/task.
"""
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from pymongo.errors import DuplicateKeyError

from src.services.hedgehog_service import GameError
from src.services.referral_economy import transaction

logger = logging.getLogger(__name__)

DEFAULT_SLUG = 'senseidurova'
DEFAULT_REWARD = 10_000
DEFAULT_ENERGY = 100
MAX_REWARD = 1_000_000
MAX_ENERGY = 1_000
MAX_GRAM_HUNDREDTHS = 100_000
MAX_CHESTS = 1_000

DEFAULT_TASK = {
    '_id': DEFAULT_SLUG,
    'kind': 'channel',
    'username': 'SenseiDurova',
    'title': 'SenseiDurova',
    'url': 'https://t.me/SenseiDurova',
    'channel_id': None,
    'reward_coins': DEFAULT_REWARD,
    'energy_bonus': DEFAULT_ENERGY,
    'active': True,
}

USERNAME_RE = re.compile(r'[A-Za-z][A-Za-z0-9_]{4,31}')
LINK_KIND = 'link'
CHANNEL_KIND = 'channel'
MAX_TITLE = 120


def normalize_username(value: str | None) -> str:
    """Accept @name, name, t.me/name and https://t.me/name."""
    if not isinstance(value, str):
        return ''
    raw = value.strip()
    raw = re.sub(r'^https?://', '', raw, flags=re.I)
    raw = re.sub(r'^t\.me/', '', raw, flags=re.I)
    raw = raw.lstrip('@').strip('/')
    if not USERNAME_RE.fullmatch(raw):
        return ''
    return raw


def normalize_link_url(value: str | None) -> str:
    """Accept an HTTPS app/bot referral link; reject executable schemes."""
    if not isinstance(value, str):
        return ''
    raw = value.strip()
    if re.match(r'^(?:t\.me|telegram\.me|www\.)', raw, flags=re.I):
        raw = 'https://' + raw
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or '').lower()
        if parts.scheme.lower() != 'https' or not host:
            return ''
        if parts.username or parts.password:
            return ''
        # Keep the query (start/startapp/referral params) and fragment, but
        # always use a single canonical HTTPS form.
        return urlunsplit(('https', parts.netloc.lower(), parts.path or '/',
                           parts.query, parts.fragment))
    except ValueError:
        return ''


def channel_link_username(value: str | None) -> str:
    """Return a username only for a plain t.me/<channel> link.

    The same t.me host also carries bot/app links with a query.  Those must be
    treated as launchable link tasks, not as channel subscriptions.
    """
    if not isinstance(value, str):
        return ''
    raw = value.strip()
    if not re.match(r'^https?://(?:www\.)?(?:t\.me|telegram\.me)/', raw,
                    flags=re.I):
        return ''
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ''
    if parts.query or parts.fragment:
        return ''
    path = parts.path.strip('/')
    if not path or '/' in path:
        return ''
    return path if USERNAME_RE.fullmatch(path) else ''


def link_slug(value: str) -> str:
    """Stable task id for a referral URL, so re-adding updates the task."""
    url = normalize_link_url(value)
    if not url:
        return ''
    return 'link-' + hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]


class TaskTargetTaken(GameError):
    """Канал/ссылка уже заняты другим заданием.

    Держит ``slug`` и ``title`` существующей задачи, чтобы мини-апп мог
    предложить переход к ней вместо тупикового сообщения об ошибке.
    """

    def __init__(self, message: str, slug: str = '', title: str = ''):
        super().__init__(message)
        self.slug = slug
        self.title = title


class DojoTaskService:
    def __init__(self, container):
        self.container = container
        self.db = container.mongo_client.database
        self.tasks = self.db.dojo_tasks
        self.claims = self.db.dojo_task_claims
        self.economy = container.economy_service
        self._defaults_ready = False

    @property
    def bot(self):
        return getattr(self.container, 'bot', None)

    async def ensure_defaults(self) -> None:
        if self._defaults_ready:
            return
        now = datetime.now(timezone.utc)
        await self.tasks.update_one(
            {'_id': DEFAULT_SLUG},
            {
                '$setOnInsert': {
                    **DEFAULT_TASK,
                    'created_at': now,
                    'created_by': None,
                    'is_default': True,
                }
            },
            upsert=True,
        )
        await self.claims.create_index('user_id')
        await self.tasks.create_index('active')
        self._defaults_ready = True

    async def task_for_channel(self, username: str) -> dict | None:
        """Публичная обёртка для бота: есть ли уже задание на этот канал."""
        await self.ensure_defaults()
        clean = normalize_username(username)
        if not clean:
            return None
        return await self._find_task_by_target(CHANNEL_KIND, {'username': clean})

    async def add_task(
        self,
        username: str,
        title: str,
        channel_id: int | None,
        reward_coins: int,
        energy_bonus: int,
        created_by: int | None,
    ) -> dict:
        await self.ensure_defaults()
        clean = normalize_username(username)
        if not clean:
            raise GameError('Некорректный @username канала.')
        reward = max(0, min(MAX_REWARD, int(reward_coins)))
        energy = max(0, min(MAX_ENERGY, int(energy_bonus)))
        now = datetime.now(timezone.utc)
        # /task_add пришёл из бота, а задание могло быть создано в мини-аппе
        # под другим _id. Правим существующее, иначе на один канал появятся
        # две записи и награду можно будет получить дважды.
        twin = await self._find_task_by_target(
            CHANNEL_KIND, {'username': clean, 'url': f'https://t.me/{clean}'})
        slug = twin['_id'] if twin else clean.lower()
        doc = {
            'kind': CHANNEL_KIND,
            'username': clean,
            'title': (title or clean).strip()[:MAX_TITLE] or clean,
            'url': f'https://t.me/{clean}',
            'channel_id': int(channel_id) if channel_id is not None else None,
            'reward_coins': reward,
            'energy_bonus': energy,
            'active': True,
            'created_by': created_by,
            'updated_at': now,
        }
        await self.tasks.update_one(
            {'_id': slug},
            {'$set': doc, '$setOnInsert': {'created_at': now}},
            upsert=True,
        )
        return self._public({'_id': slug, **doc}, claimed=False)

    async def add_link(
        self,
        url: str,
        title: str,
        reward_coins: int,
        energy_bonus: int,
        created_by: int | None,
    ) -> dict:
        """Add or update an app/bot referral task."""
        await self.ensure_defaults()
        clean_url = normalize_link_url(url)
        if not clean_url:
            raise GameError('Нужна корректная HTTPS-ссылка на приложение или бота.')
        slug = link_slug(clean_url)
        host = (urlsplit(clean_url).hostname or 'app').lower()
        reward = max(0, min(MAX_REWARD, int(reward_coins)))
        energy = max(0, min(MAX_ENERGY, int(energy_bonus)))
        now = datetime.now(timezone.utc)
        doc = {
            'kind': LINK_KIND,
            'username': host,
            'host': host,
            'title': (title or host).strip()[:MAX_TITLE] or host,
            'url': clean_url,
            'channel_id': None,
            'reward_coins': reward,
            'energy_bonus': energy,
            'active': True,
            'created_by': created_by,
            'updated_at': now,
        }
        await self.tasks.update_one(
            {'_id': slug},
            {'$set': doc, '$setOnInsert': {'created_at': now}},
            upsert=True,
        )
        return self._public({'_id': slug, **doc}, claimed=False)

    async def save_admin_task(self, data: dict, admin_id: int) -> dict:
        """Create or edit a task without changing its stable claim identity."""
        await self.ensure_defaults()
        if not isinstance(data, dict):
            raise GameError('Некорректные данные задания.')
        slug = data.get('slug') or ''
        if not isinstance(slug, str) or (slug and not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', slug)):
            raise GameError('Неверный идентификатор задания.')
        is_create = not slug
        if is_create:
            key = data.get('create_key')
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', key):
                raise GameError('Неверный идентификатор создания задания.')
            slug = 'task-' + hashlib.sha256(f'{admin_id}:{key}'.encode()).hexdigest()[:24]
        existing = await self.tasks.find_one({'_id': slug})
        if not is_create and not existing:
            raise GameError('Задание не найдено.')
        kind = data.get('kind')
        title = data.get('title')
        if kind not in (CHANNEL_KIND, LINK_KIND) or not isinstance(title, str) or not 1 <= len(title.strip()) <= MAX_TITLE:
            raise GameError('Укажи название задания — от 1 до 120 символов.')
        values = {}
        for field, maximum in (('reward_coins', MAX_REWARD), ('energy_bonus', MAX_ENERGY),
                               ('reward_gram_hundredths', MAX_GRAM_HUNDREDTHS), ('reward_chests', MAX_CHESTS)):
            number = data.get(field, 0)
            if type(number) is not int or not 0 <= number <= maximum:
                raise GameError({'reward_coins': 'Coin: целое число от 0 до 1 000 000.',
                               'energy_bonus': 'Энергия: целое число от 0 до 1000.',
                               'reward_gram_hundredths': 'GRAM: не больше 100 (2 знака после запятой).',
                               'reward_chests': 'Сундуки: целое число от 0 до 1000.'}.get(field, f'Некорректное значение: {field}.'))
            values[field] = number
        if not any(values.values()):
            raise GameError('Задание без награды бессмысленно: укажи Coin, энергию, GRAM или сундуки.')
        target = data.get('target')
        if kind == CHANNEL_KIND:
            username = normalize_username(target)
            if not username:
                raise GameError('Нужен @username канала: 5–32 символа, начинается с латинской буквы. Пример: @mychannel.')
            if not self.bot:
                raise GameError('Бот не запущен — проверка канала недоступна. Попробуй позже.')
            try:
                chat = await self.bot.get_chat(f'@{username}')
                member = await self.bot.get_chat_member(chat.id, self.bot.id)
            except Exception:
                raise GameError('Не вижу этот канал. Проверь: 1) @username написан верно; 2) канал публичный; 3) бот добавлен в него администратором.')
            if chat.type not in ('channel', 'supergroup') or member.status not in ('creator', 'administrator'):
                raise GameError('Бот в канале не администратор. Открой канал → Администраторы → добавь бота с правом «Управление» и повтори.')
            fields = {'username': username, 'url': f'https://t.me/{username}',
                      'channel_id': chat.id, 'host': None}
        else:
            url = normalize_link_url(target)
            if not url or len(url) > 2048:
                raise GameError('Нужна корректная HTTPS-ссылка на приложение (до 2048 символов).')
            host = (urlsplit(url).hostname or '').lower()
            fields = {'username': host, 'host': host, 'url': url, 'channel_id': None}
        # Один канал (и одна ссылка) не должны превращаться в несколько
        # заданий: игрок подписывается один раз, а наград становится больше.
        # Раньше каждое нажатие «Новое» создавало ещё одну запись, потому что
        # slug считался от случайного create_key, а не от самого канала.
        twin = await self._find_task_by_target(kind, fields)
        # Повторная отправка той же формы даёт тот же slug — это не дубль,
        # а ретрай: задание находится само собой и должно просто обновиться.
        if twin is not None and twin['_id'] != slug:
            if is_create:
                # Подкласс несёт slug существующего задания: мини-апп по нему
                # сразу открывает форму «Изменить», а не просто ругается.
                raise TaskTargetTaken(
                    f"Такое задание уже есть: «{twin.get('title') or twin['_id']}». "
                    "Открой его кнопкой «Изменить».",
                    slug=twin['_id'], title=twin.get('title') or '')
            raise GameError('Этот канал уже привязан к другому заданию.')
        now = datetime.now(timezone.utc)
        doc = {**fields, **values, 'kind': kind, 'title': title.strip(),
               'reward_schema': 2, 'updated_at': now, 'updated_by': admin_id,
               'active': bool(existing.get('active')) if existing else True}
        await self.tasks.update_one({'_id': slug},
            {'$set': doc, '$setOnInsert': {'created_at': now, 'created_by': admin_id}}, upsert=existing is None)
        result = self._public({'_id': slug, **doc}, claimed=False)
        result['active'] = doc['active']
        return result

    async def _find_task_by_target(self, kind: str, fields: dict) -> dict | None:
        """Ищет уже существующее задание на тот же канал или ту же ссылку.

        Ссылки и каналы сравниваются по нормализованному признаку: username
        в нижнем регистре для каналов, полный URL для приложений. Иначе
        ``@Channel`` и ``channel`` считались бы разными заданиями.
        """
        if kind == CHANNEL_KIND:
            username = fields.get('username')
            if not username:
                return None
            return await self.tasks.find_one(
                {'kind': CHANNEL_KIND, 'username': {'$regex': f'^{re.escape(username)}$',
                                                    '$options': 'i'}})
        url = fields.get('url')
        if not url:
            return None
        return await self.tasks.find_one({'kind': LINK_KIND, 'url': url})

    async def set_admin_task_active(self, slug: str, active: bool, admin_id: int) -> None:
        await self.ensure_defaults()
        if not isinstance(slug, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', slug) or type(active) is not bool:
            raise GameError('Неверное задание или статус.')
        result = await self.tasks.update_one({'_id': slug}, {'$set': {
            'active': active, 'updated_at': datetime.now(timezone.utc), 'updated_by': admin_id}})
        if getattr(result, 'matched_count', 0) != 1:
            raise GameError('Задание не найдено.')

    async def remove_task(self, slug: str) -> bool:
        await self.ensure_defaults()
        raw = (slug or '').strip()
        keys = []
        clean = normalize_username(raw)
        if clean:
            keys.append(clean.lower())
        link = link_slug(raw)
        if link:
            keys.append(link)
        if raw.startswith('link-') and len(raw) > 5:
            keys.append(raw)
        if not keys:
            raise GameError('Укажи @username канала или ссылку задания.')
        for key in keys:
            result = await self.tasks.update_one(
                {'_id': key},
                {'$set': {'active': False,
                          'updated_at': datetime.now(timezone.utc)}},
            )
            matched = getattr(result, 'matched_count', None)
            if matched is not None and matched > 0:
                return True
            if matched is None and result:
                return True
        return False

    async def list_tasks(self, user_id: int) -> list[dict]:
        await self.ensure_defaults()
        claimed = {
            doc.get('task_slug')
            async for doc in self.claims.find({'user_id': user_id})
        }
        items = []
        async for doc in self.tasks.find({'active': True}):
            items.append(self._public(doc, claimed=doc.get('_id') in claimed))
        items.sort(
            key=lambda item: (
                item['slug'] != DEFAULT_SLUG,
                str(item.get('title') or '').lower(),
            )
        )
        return items

    async def all_tasks(self) -> list[dict]:
        await self.ensure_defaults()
        items = []
        async for doc in self.tasks.find({}):
            item = self._public(doc, claimed=False)
            item['active'] = bool(doc.get('active'))
            item['channel_id'] = doc.get('channel_id')
            item['kind'] = doc.get('kind') or CHANNEL_KIND
            items.append(item)
        items.sort(
            key=lambda item: (
                item['slug'] != DEFAULT_SLUG,
                str(item.get('title') or '').lower(),
            )
        )
        return items

    async def energy_bonus_total(self, user_id: int) -> int:
        """Largest single task charge (legacy read-only helper).

        Task energy is not a permanent cap any more: it is applied once by
        :meth:`DojoMinerService.apply_task_energy`.  Returning the maximum
        keeps old callers from accidentally growing a cap with every claim.
        """
        await self.ensure_defaults()
        largest = 0
        async for doc in self.claims.find({'user_id': user_id}):
            largest = max(largest, int(doc.get('energy_bonus', 0) or 0))
        return max(0, largest)

    async def claim(self, user_id: int, slug: str) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Открой майнер внутри Telegram.')
        raw = str(slug or '').strip()
        clean = normalize_username(raw)
        task_id = clean.lower() if clean else raw
        if not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', task_id):
            raise GameError('Задание не найдено.')
        await self.ensure_defaults()
        task = await self.tasks.find_one({'_id': task_id, 'active': True})
        if not task:
            raise GameError('Задание не найдено или уже отключено.')
        claim_id = f'{user_id}:{task_id}'
        if await self.claims.find_one({'_id': claim_id}):
            raise GameError('Награда за это задание уже получена.')
        kind = str(task.get('kind') or CHANNEL_KIND)
        if kind == CHANNEL_KIND and not await self._is_subscribed(task, user_id):
            raise GameError(
                f'Сначала подпишись на @{task["username"]}, потом проверь снова.'
            )
        if task.get('reward_schema') == 2:
            return await self._claim_atomic(user_id, task, claim_id)
        reward = max(0, min(MAX_REWARD, int(task.get('reward_coins', DEFAULT_REWARD))))
        energy = max(0, min(MAX_ENERGY, int(task.get('energy_bonus', DEFAULT_ENERGY))))
        claim_doc = {
            '_id': claim_id,
            'user_id': user_id,
            'task_slug': task_id,
            'kind': kind,
            'channel_username': task.get('username'),
            'reward_coins': reward,
            'energy_bonus': energy,
            'claimed_at': time.time(),
        }
        try:
            await self.claims.insert_one(claim_doc)
        except DuplicateKeyError:
            raise GameError('Награда за это задание уже получена.')
        except Exception:
            raise GameError('Не удалось зафиксировать награду. Попробуй ещё раз.')
        try:
            payout = await self.economy.process_game_win(
                user_id=user_id,
                coins=claim_doc['reward_coins'],
                xp=0,
                description=(
                    f'Dojo task: launch {task.get("host") or task.get("username")}'
                    if kind == LINK_KIND else
                    f'Dojo task: subscription @{task["username"]}'
                ),
            )
        except Exception:
            await self.claims.delete_one({'_id': claim_id})
            raise GameError('Не удалось начислить награду. Попробуй ещё раз.')
        if not isinstance(payout, dict) or not payout.get('success'):
            await self.claims.delete_one({'_id': claim_id})
            if isinstance(payout, dict) and payout.get('reason') == 'insufficient_bank':
                raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
            raise GameError('Награда недоступна для этого профиля.')
        # The energy part is a one-time charge, not a cap upgrade.  It is
        # applied after the payout so a failed claim never leaves free energy
        # behind; a miner error must not roll back coins the user already got.
        miner = getattr(self.container, 'dojo_miner_service', None)
        energy_bonus = int(claim_doc.get('energy_bonus', 0) or 0)
        if miner is not None and energy_bonus > 0:
            try:
                applied = await miner.apply_task_energy(
                    user_id, energy_bonus, claim_id)
                if not applied:
                    logger.warning(
                        'Dojo task energy skipped user=%s claim=%s',
                        user_id, claim_id)
            except Exception:
                logger.exception(
                    'Dojo task energy apply failed user=%s claim=%s',
                    user_id, claim_id)
        public = self._public(task, claimed=True)
        return {
            'success': True,
            'task': public,
            'reward_coins': claim_doc['reward_coins'],
            'energy_bonus': claim_doc['energy_bonus'],
            'new_coins': payout.get('new_coins'),
        }

    async def _claim_atomic(self, user_id: int, task: dict, claim_id: str) -> dict:
        """Credit all reward components and receipt in one MongoDB transaction."""
        from src.services.dojo_miner_service import BASE_RATE, ENERGY_PER_HOUR, LOW_POWER, MINING_REWARD, DojoMinerService
        task_id = task['_id']
        async def work(session):
            current = await self.tasks.find_one({'_id': task_id, 'active': True}, session=session)
            if not current or current != task:
                raise GameError('Задание изменилось. Обнови список и проверь снова.')
            if await self.claims.find_one({'_id': claim_id}, session=session):
                raise GameError('Награда за это задание уже получена.')
            user = await self.db.users.find_one({'id': user_id}, session=session)
            if not user or user.get('is_banned'):
                raise GameError('Награда недоступна для этого профиля.')
            coins = current['reward_coins']
            energy = current['energy_bonus']
            gram = current.get('reward_gram_hundredths', 0)
            chests = current.get('reward_chests', 0)
            now = time.time()
            if coins:
                debit = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': coins}},
                    {'$inc': {'coins': -coins}}, session=session)
                if not debit.matched_count:
                    raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
                await self.db.users.update_one({'id': user_id}, {'$inc': {'coins': coins}}, session=session)
                await self.db.transactions.insert_one({'user_id': user_id, 'tx_type': 'dojo_task',
                    'coins_change': coins, 'description': f'Dojo task {task_id}',
                    'created_at': datetime.now(timezone.utc)}, session=session)
            if gram or chests:
                await self.db.dojo_daily.update_one({'_id': user_id},
                    {'$inc': {'gram_hundredths': gram, 'chests': chests}}, upsert=True, session=session)
            if energy:
                doc = await self.db.dojo_miners.find_one({'_id': user_id}, session=session)
                finish = float((doc or {}).get('finish_at', 0) or 0)
                if doc and not doc.get('collected') and now < finish:
                    bonuses = list(doc.get('task_energy_bonuses') or [])
                    bonuses.append({'key': claim_id, 'at': now, 'amount': energy})
                    rate = float(doc.get('base_rate', BASE_RATE))
                    hours = min(max(0.0, (finish - now) / 3600), energy / ENERGY_PER_HOUR)
                    extra = int(rate * hours * (1.0 - LOW_POWER) + 0.5)
                    circle = DojoMinerService._circle_reward({**doc, 'task_energy_bonuses': bonuses}, now)
                    amount = int(doc.get('amount', MINING_REWARD)) + extra + circle - int(doc.get('circle_reward', 0))
                    changes = {'task_energy_bonuses': bonuses, 'amount': amount, 'circle_reward': circle}
                else:
                    pending = list((doc or {}).get('task_energy_pending') or [])
                    pending.append({'key': claim_id, 'at': now, 'amount': energy})
                    changes = {'task_energy_pending': pending}
                if doc:
                    version = doc.get('version')
                    query = {'_id': user_id, 'version': version if version is not None else {'$exists': False}}
                    updated = await self.db.dojo_miners.update_one(query,
                        {'$set': changes, '$inc': {'version': 1}}, session=session)
                    if not updated.matched_count:
                        raise GameError('Майнер обновился. Попробуй ещё раз.')
                else:
                    await self.db.dojo_miners.insert_one({'_id': user_id, 'collected': True,
                        'version': 1, **changes}, session=session)
            await self.claims.insert_one({'_id': claim_id, 'user_id': user_id, 'task_slug': task_id,
                'kind': current['kind'], 'reward_coins': coins, 'energy_bonus': energy,
                'reward_gram_hundredths': gram, 'reward_chests': chests, 'claimed_at': now}, session=session)
            return {'success': True, 'task': self._public(current, claimed=True),
                    'reward_coins': coins, 'energy_bonus': energy, 'reward_gram_hundredths': gram,
                    'reward_chests': chests, 'new_coins': user.get('coins', 0) + coins}
        try:
            return await transaction(self.container.mongo_client, work)
        except DuplicateKeyError:
            if await self.claims.find_one({'_id': claim_id}):
                raise GameError('Награда за это задание уже получена.')
            raise GameError('Майнер обновился. Попробуй ещё раз.')

    async def _is_subscribed(self, task: dict, user_id: int) -> bool:
        bot = self.bot
        if bot is None:
            raise GameError('Проверка подписки временно недоступна. Попробуй позже.')
        chat_ref = task.get('channel_id') or f'@{task["username"]}'
        try:
            member = await bot.get_chat_member(chat_ref, user_id)
        except Exception:
            raise GameError('Не удалось проверить подписку. Попробуй ещё раз.')
        status = getattr(member, 'status', '')
        if status in ('creator', 'administrator', 'member'):
            return True
        return status == 'restricted' and bool(getattr(member, 'is_member', False))

    @staticmethod
    def _public(doc: dict, claimed: bool) -> dict:
        kind = str(doc.get('kind') or CHANNEL_KIND)
        button = 'Запустить' if kind == LINK_KIND else 'Подписаться'
        return {
            'slug': doc.get('_id'),
            'kind': kind,
            'button_label': button,
            'username': doc.get('username'),
            'host': doc.get('host') or doc.get('username'),
            'title': doc.get('title') or doc.get('username'),
            'url': doc.get('url') or f'https://t.me/{doc.get("username", "")}',
            'reward_coins': int(doc.get('reward_coins', DEFAULT_REWARD)),
            'energy_bonus': int(doc.get('energy_bonus', DEFAULT_ENERGY)),
            'reward_gram_hundredths': int(doc.get('reward_gram_hundredths', 0) or 0),
            'reward_chests': int(doc.get('reward_chests', 0) or 0),
            'claimed': bool(claimed),
        }
