"""Subscription tasks for the /dojo miner.

Admins add Telegram channels; users subscribe once and claim a one-time
SenseiCoin reward plus a permanent energy bonus. Every check runs on the
server through the bot API and every claim is unique per user and channel.
"""
import re
import time
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from src.services.hedgehog_service import GameError

DEFAULT_SLUG = 'senseidurova'
DEFAULT_REWARD = 10_000
DEFAULT_ENERGY = 100
MAX_REWARD = 1_000_000
MAX_ENERGY = 1_000

DEFAULT_TASK = {
    '_id': DEFAULT_SLUG,
    'username': 'SenseiDurova',
    'title': 'SenseiDurova',
    'url': 'https://t.me/SenseiDurova',
    'channel_id': None,
    'reward_coins': DEFAULT_REWARD,
    'energy_bonus': DEFAULT_ENERGY,
    'active': True,
}

USERNAME_RE = re.compile(r'[A-Za-z][A-Za-z0-9_]{4,31}')


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
            'username': clean,
            'title': (title or clean).strip()[:120] or clean,
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

    async def remove_task(self, slug: str) -> bool:
        await self.ensure_defaults()
        clean = normalize_username(slug)
        if not clean:
            raise GameError('Укажи @username канала.')
        result = await self.tasks.update_one(
            {'_id': clean.lower()},
            {'$set': {'active': False, 'updated_at': datetime.now(timezone.utc)}},
        )
        matched = getattr(result, 'matched_count', None)
        return matched > 0 if matched is not None else bool(result)

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
            items.append(item)
        items.sort(
            key=lambda item: (
                item['slug'] != DEFAULT_SLUG,
                str(item.get('title') or '').lower(),
            )
        )
        return items

    async def energy_bonus_total(self, user_id: int) -> int:
        await self.ensure_defaults()
        total = 0
        async for doc in self.claims.find({'user_id': user_id}):
            total += int(doc.get('energy_bonus', 0))
        return max(0, total)

    async def claim(self, user_id: int, slug: str) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Открой майнер внутри Telegram.')
        clean = normalize_username(slug)
        if not clean:
            raise GameError('Задание не найдено.')
        await self.ensure_defaults()
        task = await self.tasks.find_one({'_id': clean.lower(), 'active': True})
        if not task:
            raise GameError('Задание не найдено или уже отключено.')
        claim_id = f'{user_id}:{clean.lower()}'
        if await self.claims.find_one({'_id': claim_id}):
            raise GameError('Награда за это задание уже получена.')
        if not await self._is_subscribed(task, user_id):
            raise GameError(
                f'Сначала подпишись на @{task["username"]}, потом проверь снова.'
            )
        reward = max(0, min(MAX_REWARD, int(task.get('reward_coins', DEFAULT_REWARD))))
        energy = max(0, min(MAX_ENERGY, int(task.get('energy_bonus', DEFAULT_ENERGY))))
        claim_doc = {
            '_id': claim_id,
            'user_id': user_id,
            'task_slug': clean.lower(),
            'channel_username': task['username'],
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
                description=f'Dojo task: subscription @{task["username"]}',
            )
        except Exception:
            await self.claims.delete_one({'_id': claim_id})
            raise GameError('Не удалось начислить награду. Попробуй ещё раз.')
        if not isinstance(payout, dict) or not payout.get('success'):
            await self.claims.delete_one({'_id': claim_id})
            if isinstance(payout, dict) and payout.get('reason') == 'insufficient_bank':
                raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
            raise GameError('Награда недоступна для этого профиля.')
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
        return {
            'slug': doc.get('_id'),
            'username': doc.get('username'),
            'title': doc.get('title') or doc.get('username'),
            'url': doc.get('url') or f'https://t.me/{doc.get("username", "")}',
            'reward_coins': int(doc.get('reward_coins', DEFAULT_REWARD)),
            'energy_bonus': int(doc.get('energy_bonus', DEFAULT_ENERGY)),
            'claimed': bool(claimed),
        }
