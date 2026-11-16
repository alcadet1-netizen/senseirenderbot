"""Eight-hour SenseiCoin miner behind the /dojo Mini App.

Starting a cycle draws the payout from SenseiBank. The browser only renders
state; start and collect are validated and paid here.
"""
import asyncio
import time
from collections import defaultdict

from src.services.hedgehog_service import GameError

CYCLE_SECONDS = 8 * 60 * 60
MINING_REWARD = 120
BASE_ENERGY = 100


class DojoMinerService:
    def __init__(self, mongo, economy, tasks=None):
        self.mongo = mongo
        self.economy = economy
        self.tasks = tasks
        self.miners = mongo.database.dojo_miners
        self.users = mongo.database.users
        self._locks = defaultdict(asyncio.Lock)

    async def state(self, user_id: int) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Откройте майнер внутри Telegram.')
        now = time.time()
        doc = await self.miners.find_one({'_id': user_id}) or {}
        user = await self.users.find_one({'id': user_id}) or {}
        balance = user.get('coins', 0)
        started = doc.get('started_at')
        finish = doc.get('finish_at')
        if doc and not doc.get('collected'):
            phase = 'ready_to_collect' if now >= finish else 'mining'
        else:
            phase = 'ready'
        energy_bonus = 0
        if self.tasks is not None:
            try:
                energy_bonus = await self.tasks.energy_bonus_total(user_id)
            except Exception:
                energy_bonus = 0
        remaining = max(0.0, (finish or now) - now) if phase == 'mining' else 0.0
        progress = 1.0
        if phase == 'mining' and finish and started and finish > started:
            progress = min(1.0, max(0.0, (now - started) / (finish - started)))
        return {
            'phase': phase,
            'server_now': now,
            'balance': balance,
            'reward': int(doc.get('amount', MINING_REWARD)) if phase != 'ready' else MINING_REWARD,
            'energy_max': BASE_ENERGY + energy_bonus,
            'cycle_seconds': CYCLE_SECONDS,
            'started_at': started,
            'finish_at': finish,
            'remaining_ms': int(remaining * 1000),
            'progress': progress,
        }

    async def start(self, user_id: int) -> dict:
        async with self._locks[user_id]:
            now = time.time()
            doc = await self.miners.find_one({'_id': user_id})
            if doc and not doc.get('collected'):
                if now < doc.get('finish_at', 0):
                    raise GameError('Майнинг уже идёт. Дождись конца цикла.')
                raise GameError('Сначала забери намайненное и запусти новый цикл.')
            version = int((doc or {}).get('version', 0))
            session = {
                'started_at': now,
                'finish_at': now + CYCLE_SECONDS,
                'collected': False,
                'amount': MINING_REWARD,
                'version': version + 1,
            }
            if doc:
                updated = await self.miners.find_one_and_update(
                    {'_id': user_id, 'version': version},
                    {'$set': session},
                )
                if not updated:
                    raise GameError('Майнер уже запущен. Обнови экран.')
            else:
                try:
                    await self.miners.insert_one({'_id': user_id, **session})
                except Exception:
                    raise GameError('Майнер уже запущен. Обнови экран.')
            return await self.state(user_id)

    async def collect(self, user_id: int) -> dict:
        async with self._locks[user_id]:
            now = time.time()
            doc = await self.miners.find_one({'_id': user_id})
            if not doc:
                raise GameError('Намайненного пока нет. Сначала запусти майнинг.')
            if doc.get('collected'):
                raise GameError('Награда уже получена. Запусти новый цикл.')
            if now < doc.get('finish_at', 0):
                raise GameError('Майнинг ещё не завершён.')
            version = int(doc.get('version', 0))
            amount = int(doc.get('amount', MINING_REWARD))
            claimed = await self.miners.find_one_and_update(
                {'_id': user_id, 'version': version, 'collected': False},
                {'$set': {'collected': True, 'collected_at': now},
                 '$inc': {'version': 1}},
            )
            if not claimed:
                raise GameError('Награда уже получена. Обнови экран.')
            try:
                result = await self.economy.process_game_win(
                    user_id=user_id, coins=amount, xp=0,
                    description='Dojo miner: 8h SenseiCoin cycle',
                )
            except Exception:
                await self._rollback(user_id, version + 1)
                raise GameError('Майнер не смог выплатить награду. Попробуй ещё раз.')
            if not result.get('success'):
                await self._rollback(user_id, version + 1)
                raise GameError('Награда недоступна для этого профиля.')
            state = await self.state(user_id)
            state['mined'] = amount
            state['balance'] = result.get('new_coins', state['balance'])
            return state

    async def _rollback(self, user_id: int, version: int) -> None:
        await self.miners.find_one_and_update(
            {'_id': user_id, 'version': version, 'collected': True},
            {'$set': {'collected': False}, '$inc': {'version': 1}},
        )
