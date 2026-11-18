"""Daily, server-verified Telegram profile tasks; paid from SenseiBank."""
import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from pymongo.errors import DuplicateKeyError

from src.services.hedgehog_service import GameError
from src.services.referral_economy import transaction

NAME_TASK = 'daily_sensei_name'
BIO_TASK = 'daily_referral_bio'
TASK_IDS = frozenset((NAME_TASK, BIO_TASK))
REWARD = 1000
URL_RE = re.compile(r'(?<![\w./@?=&%+-])(?:https?://)?(?:t\.me|telegram\.me)/[^\s<>"\']+', re.I)


def has_referral(bio, bot_username, user_id):
    if not isinstance(bio, str) or not bot_username:
        return False
    for match in URL_RE.finditer(bio):
        raw = match.group().rstrip('.,;!?)')
        try:
            url = urlsplit(raw if '://' in raw else 'https://' + raw)
            if (url.scheme.lower() not in ('http', 'https') or
                    url.netloc.lower() not in ('t.me', 'telegram.me') or
                    url.path.strip('/').lower() != bot_username.lower() or url.fragment):
                continue
            pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
            if len(pairs) == 1 and pairs[0] in (('start', f'ref_{user_id}'), ('startapp', f'ref_{user_id}')):
                return True
        except ValueError:
            continue
    return False


class DojoProfileTasks:
    def __init__(self, container):
        self.container = container
        self.db = container.mongo_client.database

    @staticmethod
    def day():
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def public(slug, claimed=False):
        return {'slug': slug, 'kind': 'daily_profile', 'daily': True,
                'title': 'Sensei в имени' if slug == NAME_TASK else 'Реферальная ссылка в BIO',
                'description': ('Добавь Sensei в имя или @username Telegram' if slug == NAME_TASK
                                else 'Размести свою реферальную ссылку в BIO Telegram'),
                'reward_coins': REWARD, 'energy_bonus': 0, 'claimed': claimed}

    async def list_tasks(self, user_id):
        day = self.day()
        items = [self.public(slug, bool(await self.db.dojo_task_claims.find_one(
            {'_id': f'{user_id}:{slug}:{day}'}))) for slug in (NAME_TASK, BIO_TASK)]
        for item in items:
            item['claim_day'] = day
        return items

    async def claim(self, user_id, slug):
        if type(user_id) is not int or user_id <= 0 or slug not in TASK_IDS:
            raise GameError('Задание недоступно.')
        bot = getattr(self.container, 'bot', None)
        if bot is None:
            raise GameError('Проверка профиля Telegram временно недоступна.')
        try:
            profile = await asyncio.wait_for(bot.get_chat(user_id), timeout=5)
            if slug == BIO_TASK:
                me = await asyncio.wait_for(bot.get_me(), timeout=5)
                bot_username = getattr(me, 'username', None)
                if not bot_username:
                    raise ValueError('bot username unavailable')
        except Exception:
            raise GameError('Не удалось проверить профиль Telegram. Открой личный чат с ботом и попробуй снова.')
        if slug == NAME_TASK:
            text = ' '.join(str(getattr(profile, key, '') or '') for key in ('first_name', 'last_name', 'username'))
            if 'sensei' not in text.casefold():
                raise GameError('Добавь Sensei в имя или @username Telegram и проверь снова.')
        elif not has_referral(getattr(profile, 'bio', None), bot_username, user_id):
            raise GameError('Добавь свою реферальную ссылку в BIO Telegram и проверь снова.')
        day = self.day()
        claim_id = f'{user_id}:{slug}:{day}'
        async def work(session):
            if await self.db.dojo_task_claims.find_one({'_id': claim_id}, session=session):
                raise GameError('Награда за сегодня уже получена.')
            user = await self.db.users.find_one({'id': user_id}, session=session)
            if not user or user.get('is_banned'):
                raise GameError('Награда недоступна для этого профиля.')
            await self.db.dojo_task_claims.insert_one({'_id': claim_id, 'user_id': user_id,
                'task_slug': slug, 'day': day, 'reward_coins': REWARD,
                'claimed_at': datetime.now(timezone.utc)}, session=session)
            bank = await self.db.bank.update_one({'_id': 'single', 'coins': {'$gte': REWARD}},
                {'$inc': {'coins': -REWARD}}, session=session)
            if not bank.matched_count:
                raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
            await self.db.users.update_one({'id': user_id}, {'$inc': {'coins': REWARD}}, session=session)
            await self.db.transactions.insert_one({'user_id': user_id, 'tx_type': 'dojo_profile_task',
                'coins_change': REWARD, 'description': f'Dojo daily profile task {slug}',
                'created_at': datetime.now(timezone.utc)}, session=session)
            return {'success': True, 'task': self.public(slug, True), 'reward_coins': REWARD,
                    'energy_bonus': 0, 'new_coins': user.get('coins', 0) + REWARD}
        try:
            return await transaction(self.container.mongo_client, work)
        except DuplicateKeyError:
            raise GameError('Награда за сегодня уже получена.')
