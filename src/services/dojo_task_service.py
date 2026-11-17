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

logger = logging.getLogger(__name__)

DEFAULT_SLUG = 'senseidurova'
DEFAULT_REWARD = 10_000
DEFAULT_ENERGY = 100
MAX_REWARD = 1_000_000
MAX_ENERGY = 1_000

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
            {'_id': clean.lower()},
            {'$set': doc, '$setOnInsert': {'created_at': now}},
            upsert=True,
        )
        return self._public({'_id': clean.lower(), **doc}, claimed=False)

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
            'claimed': bool(claimed),
        }
