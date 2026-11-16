"""Eight-hour SenseiCoin miner behind the /dojo Mini App.

A cycle has a fixed power level from the pickaxe and an energy budget. Every
100 energy lasts one hour at full power; after that the pickaxe runs at 10% of
its base rate for the rest of the eight-hour cycle. The browser only renders
state; start, collect and automatic cycles are validated and paid here.
"""
import asyncio
import logging
import time
from collections import defaultdict

from src.services.hedgehog_service import GameError

CYCLE_SECONDS = 8 * 60 * 60
CYCLE_HOURS = CYCLE_SECONDS / 3600
BASE_RATE = 15.0
PICKAXE_STEP = 10.0
BASE_ENERGY = 100
ENERGY_PER_HOUR = 100.0
LOW_POWER = 0.1
PICKAXE_MAX_LEVEL = 100
ENERGY_MAX_PURCHASES = 100
MINING_REWARD = int(BASE_RATE * CYCLE_HOURS)  # legacy reference: 120/cycle
AUTOCOLLECT_INTERVAL = 60

logger = logging.getLogger(__name__)


def estimate_amount(rate: float, energy: float) -> int:
    """Integrate full power followed by the 10% fallback over one cycle."""
    full_hours = min(CYCLE_HOURS, max(0.0, float(energy)) / ENERGY_PER_HOUR)
    low_hours = CYCLE_HOURS - full_hours
    return int(rate * full_hours + rate * LOW_POWER * low_hours + 0.5)


class DojoMinerService:
    def __init__(self, mongo, economy, tasks=None):
        self.mongo = mongo
        self.economy = economy
        self.tasks = tasks
        self.miners = mongo.database.dojo_miners
        self.users = mongo.database.users
        self._locks = defaultdict(asyncio.Lock)

    async def ensure_indexes(self) -> None:
        await self.users.create_index('dojo_auto_collect')

    async def _task_energy(self, user_id: int) -> int:
        if self.tasks is None:
            return 0
        try:
            return max(0, int(await self.tasks.energy_bonus_total(user_id)))
        except Exception:
            logger.warning('Dojo task energy unavailable user=%s', user_id)
            return 0

    @staticmethod
    def _profile(user: dict) -> dict:
        level = max(0, min(PICKAXE_MAX_LEVEL, int(user.get('dojo_pickaxe_level', 0) or 0)))
        purchases = max(0, min(ENERGY_MAX_PURCHASES,
                               int(user.get('dojo_energy_purchases', 0) or 0)))
        return {
            'pickaxe_level': level,
            'energy_purchases': purchases,
            'auto_collect': bool(user.get('dojo_auto_collect')),
            'base_rate': BASE_RATE + level * PICKAXE_STEP,
        }

    async def state(self, user_id: int) -> dict:
        if type(user_id) is not int or user_id <= 0:
            raise GameError('Откройте майнер внутри Telegram.')
        now = time.time()
        doc = await self.miners.find_one({'_id': user_id}) or {}
        user = await self.users.find_one({'id': user_id}) or {}
        balance = user.get('coins', 0)
        profile = self._profile(user)
        energy_cap = (BASE_ENERGY + profile['energy_purchases'] * 100
                      + await self._task_energy(user_id))
        started = doc.get('started_at')
        finish = doc.get('finish_at')
        if doc and not doc.get('collected') and finish:
            phase = 'ready_to_collect' if now >= finish else 'mining'
        else:
            phase = 'ready'
        progress = 0.0
        remaining = 0.0
        energy = energy_cap
        energy_start = energy_cap
        base_rate = profile['base_rate']
        current_rate = base_rate
        amount = estimate_amount(profile['base_rate'], energy_cap) if phase == 'ready' else 0
        if phase != 'ready':
            energy_start = max(0, int(doc.get('energy_start', energy_cap)))
            base_rate = float(doc.get('base_rate', profile['base_rate']))
            amount = int(doc.get('amount', estimate_amount(base_rate, energy_start)))
            elapsed = max(0.0, min(now, finish) - started) if started else 0.0
            energy = max(0, int(energy_start - ENERGY_PER_HOUR * elapsed / 3600))
            if phase == 'mining':
                remaining = max(0.0, finish - now)
                progress = min(1.0, max(0.0, (now - started) / (finish - started))) if finish > started else 0.0
            else:
                progress = 1.0
            current_rate = base_rate * (LOW_POWER if energy <= 0 else 1.0)
        return {
            'phase': phase,
            'server_now': now,
            'balance': balance,
            'reward': amount,
            'next_reward': estimate_amount(profile['base_rate'], energy_cap),
            'energy': energy,
            'energy_max': energy_start if phase != 'ready' else energy_cap,
            'energy_start': energy_start,
            'energy_per_hour': ENERGY_PER_HOUR,
            'base_rate': base_rate,
            'current_rate': current_rate,
            'pickaxe_level': profile['pickaxe_level'],
            'energy_purchases': profile['energy_purchases'],
            'auto_collect': profile['auto_collect'],
            'cycle_seconds': CYCLE_SECONDS,
            'started_at': started,
            'finish_at': finish,
            'remaining_ms': int(remaining * 1000),
            'progress': progress,
            'progress_percent': round(progress * 100, 1),
        }

    async def start(self, user_id: int) -> dict:
        async with self._locks[user_id]:
            now = time.time()
            doc = await self.miners.find_one({'_id': user_id})
            if doc and not doc.get('collected'):
                if now < doc.get('finish_at', 0):
                    raise GameError('Майнинг уже идёт. Дождись конца цикла.')
                raise GameError('Сначала забери намайненное и запусти новый цикл.')
            user = await self.users.find_one({'id': user_id}) or {}
            profile = self._profile(user)
            energy_start = (BASE_ENERGY + profile['energy_purchases'] * 100
                            + await self._task_energy(user_id))
            base_rate = profile['base_rate']
            version = int((doc or {}).get('version', 0))
            session = {
                'started_at': now,
                'finish_at': now + CYCLE_SECONDS,
                'collected': False,
                'amount': estimate_amount(base_rate, energy_start),
                'base_rate': base_rate,
                'energy_start': energy_start,
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
            if not isinstance(result, dict) or not result.get('success'):
                await self._rollback(user_id, version + 1)
                raise GameError('Награда недоступна для этого профиля.')
            state = await self.state(user_id)
            state['mined'] = amount
            state['balance'] = result.get('new_coins', state['balance'])
            return state

    async def auto_step(self, user_id: int) -> None:
        """Collect a finished cycle and immediately start the next one."""
        if type(user_id) is not int or user_id <= 0:
            return
        now = time.time()
        doc = await self.miners.find_one({'_id': user_id})
        if doc and not doc.get('collected') and now < doc.get('finish_at', 0):
            return
        if doc and not doc.get('collected'):
            try:
                await self.collect(user_id)
            except GameError:
                return
        try:
            await self.start(user_id)
        except GameError:
            return

    async def auto_tick(self) -> int:
        """Run one background pass over players with auto-collect enabled."""
        started = 0
        async for user in self.users.find(
                {'dojo_auto_collect': True, 'is_banned': {'$ne': True}}, {'id': 1}):
            user_id = user.get('id')
            if type(user_id) is not int or user_id <= 0:
                continue
            await self.auto_step(user_id)
            started += 1
        return started

    async def auto_loop(self, interval: int = AUTOCOLLECT_INTERVAL) -> None:
        while True:
            try:
                await self.auto_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error('Dojo auto-collect pass failed', exc_info=True)
            await asyncio.sleep(interval)

    async def _rollback(self, user_id: int, version: int) -> None:
        await self.miners.find_one_and_update(
            {'_id': user_id, 'version': version, 'collected': True},
            {'$set': {'collected': False}, '$inc': {'version': 1}},
        )
