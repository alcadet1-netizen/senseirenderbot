"""Server-authoritative SenseiCoin payouts for the Dojo survival run.

The browser is never trusted with a balance: Telegram initData identifies the
player, the server issues a single-use run token, and a payout is possible only
after the run has really lasted long enough. Daily turnover is deliberately tiny.
"""
import asyncio
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone

from src.services.hedgehog_service import GameError, utc_day

MIN_RUN_SECONDS = 45
RUN_TTL_SECONDS = 30 * 60
DAILY_CAP = 30
COINS_PER_WAVE = 2
VICTORY_BONUS = 4
MAX_WAVE = 5
RUN_RE = re.compile(r'[A-Za-z0-9_-]{24,64}')


class DojoRewardService:
    def __init__(self, mongo, economy):
        self.economy = economy
        self.runs = mongo.database.dojo_runs
        self.days = mongo.database.dojo_days
        self._locks = defaultdict(asyncio.Lock)
        self._indexed = False

    @staticmethod
    def reward_for(wave: int, victory: bool) -> int:
        return wave * COINS_PER_WAVE + (VICTORY_BONUS if victory else 0)

    async def start(self, user_id: int) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Откройте игру внутри Telegram.')
        if not self._indexed:
            await self.runs.create_index('expires_at', expireAfterSeconds=0)
            self._indexed = True
        token = secrets.token_urlsafe(24)
        now = time.time()
        await self.runs.insert_one({
            '_id': token,
            'user_id': user_id,
            'started_at': now,
            'expires_at': datetime.fromtimestamp(now + 3600, timezone.utc),
            'claimed': False,
            'wave': 0,
            'victory': False,
        })
        return {
            'run': token,
            'min_seconds': MIN_RUN_SECONDS,
            'daily_cap': DAILY_CAP,
            'reward_table': [{'wave': w, 'coins': self.reward_for(w, False)} for w in range(1, MAX_WAVE + 1)],
            'victory_bonus': VICTORY_BONUS,
        }

    async def claim(self, user_id: int, run: str, wave: int, victory: bool) -> dict:
        if not isinstance(run, str) or not RUN_RE.fullmatch(run):
            raise GameError('Неверный забег.')
        if type(wave) is not int or not 1 <= wave <= MAX_WAVE:
            raise GameError('Неверная волна.')
        if type(victory) is not bool or (victory and wave != MAX_WAVE):
            raise GameError('Неверный результат забега.')
        reward = self.reward_for(wave, victory)
        now = time.time()
        async with self._locks[user_id]:
            claimed = await self.runs.find_one_and_update(
                {
                    '_id': run,
                    'user_id': user_id,
                    'claimed': False,
                    'started_at': {'$gte': now - RUN_TTL_SECONDS},
                },
                {'$set': {
                    'claimed': True,
                    'finished_at': now,
                    'wave': wave,
                    'victory': victory,
                }},
            )
            if not claimed:
                raise GameError('Забег не найден или награда уже получена.')
            if now - claimed['started_at'] < MIN_RUN_SECONDS:
                await self.runs.update_one({'_id': run}, {'$set': {'claimed': False}})
                raise GameError('Слишком быстрый забег. Награда не выдана.')

            day = utc_day()
            key = f'{user_id}:{day}'
            day_doc = await self.days.find_one({'_id': key})
            used = int((day_doc or {}).get('earned', 0))
            if used >= DAILY_CAP:
                await self.runs.update_one({'_id': run}, {'$set': {'claimed': False}})
                raise GameError('Дневной лимит SenseiCoin исчерпан. Возвращайся завтра.')
            payout = await self._add_day(key, user_id, day, used, reward)
            if not payout:
                await self.runs.update_one({'_id': run}, {'$set': {'claimed': False}})
                raise GameError('Дневной лимит SenseiCoin исчерпан. Возвращайся завтра.')

            description = f'Dojo survival: wave {wave}' + (' victory' if victory else '')
            result = await self.economy.process_game_win(
                user_id=user_id, coins=payout, xp=0, description=description,
            )
            if not result.get('success'):
                await self.days.update_one({'_id': key}, {'$inc': {'earned': -payout, 'runs': -1}})
                await self.runs.update_one({'_id': run}, {'$set': {'claimed': False}})
                raise GameError('Награда недоступна для этого профиля.')

            return {
                'coins': payout,
                'daily_earned': min(DAILY_CAP, used + payout),
                'daily_cap': DAILY_CAP,
                'balance': result.get('new_coins'),
                'wave': wave,
                'victory': victory,
            }

    async def _add_day(self, key: str, user_id: int, day: str, used: int, reward: int) -> int:
        """Compare-and-set the daily total so two tabs cannot beat the cap.

        Returns the amount actually added, capped by what is left for the day.
        """
        for _ in range(3):
            payout = min(reward, DAILY_CAP - used)
            if payout <= 0:
                return 0
            try:
                if used:
                    changed = await self.days.find_one_and_update(
                        {'_id': key, 'earned': used},
                        {'$inc': {'earned': payout, 'runs': 1}},
                    )
                else:
                    changed = await self.days.find_one_and_update(
                        {'_id': key},
                        {
                            '$inc': {'earned': payout, 'runs': 1},
                            '$setOnInsert': {'user_id': user_id, 'day': day,
                                             'created_at': datetime.now(timezone.utc)},
                        },
                        upsert=True,
                    )
            except Exception:
                # A concurrent first claim may lose the unique _id race.
                changed = None
            if changed:
                return payout
            fresh = await self.days.find_one({'_id': key})
            used = int((fresh or {}).get('earned', 0))
        return 0
