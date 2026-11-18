"""Three-hour SenseiCoin miner behind the /dojo Mini App.

A cycle has a fixed power level from the pickaxe and an energy budget. Every
100 energy lasts one hour at full power; after that the pickaxe runs at 10% of
its base rate for the rest of the three-hour cycle. The browser only renders
state; start, collect and automatic cycles are validated and paid here.
"""
import asyncio
import logging
import time
from collections import defaultdict

from src.services.hedgehog_service import GameError

CYCLE_SECONDS = 3 * 60 * 60
CYCLE_HOURS = CYCLE_SECONDS / 3600
BASE_RATE = 15.0
PICKAXE_STEP = 10.0
BASE_ENERGY = 100
ENERGY_PER_HOUR = 100.0
LOW_POWER = 0.1
PICKAXE_MAX_LEVEL = 100
ENERGY_MAX_PURCHASES = 100
ENERGY_REFILL_STARS = 5
ENERGY_REFILL_AMOUNT = 100
SPEED_BOOST_STARS = 1
SPEED_BOOST_SECONDS = 60 * 60
SPEED_BOOST_PERCENT = 50
SPEED_BOOST_BONUS = 0.5
MINING_REWARD = int(BASE_RATE * CYCLE_HOURS)  # 3h at the full base rate; legacy fallback
AUTOCOLLECT_INTERVAL = 60

logger = logging.getLogger(__name__)


def estimate_amount(rate: float, energy: float) -> int:
    """Integrate full power followed by the 10% fallback over one cycle."""
    full_hours = min(CYCLE_HOURS, max(0.0, float(energy)) / ENERGY_PER_HOUR)
    low_hours = CYCLE_HOURS - full_hours
    return int(rate * full_hours + rate * LOW_POWER * low_hours + 0.5)


def _pending_energy(doc: dict) -> int:
    """Energy from tasks claimed while no cycle could accept it yet."""
    return sum(max(0, int(item.get('amount', 0) or 0))
               for item in doc.get('task_energy_pending') or [])


def _boost_bonus(rate: float, start: float, end: float) -> int:
    """Extra reward for the part of a cycle covered by a speed boost."""
    seconds = max(0.0, min(float(end), float(start + CYCLE_SECONDS)) - float(start))
    return int(float(rate) * SPEED_BOOST_BONUS * seconds / 3600 + 0.5)


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

    @staticmethod
    def _energy_at(doc: dict, now: float, finish: float, energy_start: int) -> float:
        """Current energy: base drain plus paid refills and task bonuses.

        Task energy is *used*, not added to the cap.  It therefore decays from
        the moment the task is claimed and adds reward for exactly the extra
        full-power hours it buys, once.
        """
        if doc.get('circle_energy_events'):
            energy, _ = DojoMinerService._energy_timeline(doc, now)
            return max(0.0, energy)
        started = doc.get('started_at')
        elapsed = max(0.0, min(now, finish) - started) if started else 0.0
        energy = max(0, energy_start - ENERGY_PER_HOUR * elapsed / 3600)
        for refill in doc.get('energy_refills') or []:
            since = max(0.0, min(now, finish) - float(refill.get('at', now)))
            energy += max(
                0.0,
                float(refill.get('amount', 0)) - ENERGY_PER_HOUR * since / 3600,
            )
        for bonus in doc.get('task_energy_bonuses') or []:
            since = max(0.0, min(now, finish) - float(bonus.get('at', now)))
            energy += max(
                0.0,
                float(bonus.get('amount', 0)) - ENERGY_PER_HOUR * since / 3600,
            )
        return max(0, int(energy))

    @staticmethod
    def _energy_timeline(doc: dict, now: float, include_circles: bool = True):
        """Integrate a single energy reservoir, including timed additions."""
        start = float(doc.get('started_at') or 0)
        finish = float(doc.get('finish_at') or start)
        end = min(max(now, start), finish)
        energy = max(0.0, float(doc.get('energy_start', BASE_ENERGY)))
        full = 0.0
        cursor = start
        events = list(doc.get('energy_refills') or []) + list(doc.get('task_energy_bonuses') or [])
        if include_circles:
            events += list(doc.get('circle_energy_events') or [])
        for event in sorted(events, key=lambda item: float(item.get('at', start))):
            at = max(start, float(event.get('at', start)))
            if at > end:
                break
            elapsed = max(0.0, at - cursor)
            used = min(elapsed, energy * 3600 / ENERGY_PER_HOUR)
            full += used
            energy = max(0.0, energy - elapsed * ENERGY_PER_HOUR / 3600)
            energy += max(0.0, float(event.get('amount', 0)))
            cursor = at
        elapsed = max(0.0, end - cursor)
        full += min(elapsed, energy * 3600 / ENERGY_PER_HOUR)
        energy = max(0.0, energy - elapsed * ENERGY_PER_HOUR / 3600)
        projected = full + min(finish - end, energy * 3600 / ENERGY_PER_HOUR)
        return energy, projected

    @classmethod
    def _circle_reward(cls, doc: dict, now: float) -> int:
        if not doc.get('circle_energy_events'):
            return 0
        _, with_circles = cls._energy_timeline(doc, now, True)
        _, without_circles = cls._energy_timeline(doc, now, False)
        rate = float(doc.get('base_rate', BASE_RATE))
        return max(0, int(rate * (1.0 - LOW_POWER) * (with_circles - without_circles) / 3600 + 0.5))

    async def add_circle_energy(self, user_id: int, cycle: float, request_id: str) -> dict:
        """Credit one client-reported circle exactly once within the active cycle.

        Gesture recognition runs in the browser and is not proof of a human gesture.
        """
        if type(user_id) is not int or user_id <= 0 or not request_id:
            raise GameError('Неверный запрос пополнения.')
        async with self._locks[user_id]:
            for _ in range(8):
                now = time.time()
                user = await self.users.find_one({'id': user_id})
                doc = await self.miners.find_one({'_id': user_id})
                if not user or user.get('is_banned'):
                    raise GameError('Профиль недоступен.')
                if not doc or float(doc.get('started_at') or 0) != cycle:
                    raise GameError('Цикл изменился. Обнови экран.')
                events = list(doc.get('circle_energy_events') or [])
                if any(item.get('key') == request_id for item in events):
                    return {'added': 1, 'replayed': True}
                finish = float(doc.get('finish_at') or 0)
                if doc.get('collected') or now >= finish:
                    raise GameError('Майнинг не запущен.')
                energy, _ = self._energy_timeline(doc, now)
                if not events and int(energy) > 0:
                    raise GameError('Круги доступны, когда энергия закончилась.')
                cap = max(0, int(doc.get('energy_max', BASE_ENERGY))) / 2
                if energy + 1 > cap + 1e-9:
                    return {'added': 0, 'replayed': False}
                events.append({'key': request_id, 'at': now, 'amount': 1})
                candidate = {**doc, 'circle_energy_events': events}
                bonus = self._circle_reward(candidate, now)
                old_bonus = int(doc.get('circle_reward', 0))
                updated = await self.miners.find_one_and_update(
                    {'_id': user_id, 'version': int(doc.get('version', 0)), 'collected': False},
                    {'$set': {'circle_energy_events': events, 'circle_reward': bonus,
                              'amount': int(doc.get('amount', MINING_REWARD)) + bonus - old_bonus},
                     '$inc': {'version': 1}},
                )
                if updated:
                    return {'added': 1, 'replayed': False}
            raise GameError('Не удалось сохранить энергию. Попробуй ещё раз.')

    @staticmethod
    def _boost_cycle_key(doc: dict | None, now: float) -> str:
        """Stable id for the active cycle, or the next cycle when idle."""
        if not doc or doc.get('collected'):
            return 'upcoming'
        started = float(doc.get('started_at', 0) or 0)
        finish = float(doc.get('finish_at', 0) or 0)
        if started and finish and now < finish:
            return f'c:{int(started * 1000)}'
        return 'upcoming'

    async def boost_cycle_status(self, user_id: int) -> dict:
        """Whether the current cycle has already used its one boost purchase."""
        now = time.time()
        doc = await self.miners.find_one({'_id': user_id}) or {}
        user = await self.users.find_one({'id': user_id}) or {}
        key = self._boost_cycle_key(doc, now)
        return {
            'cycle_key': key,
            'purchased': str(user.get('dojo_boost_cycle') or '') == key,
            'active_cycle': key != 'upcoming',
        }

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
        # Purchases raise the permanent cap.  Task energy is deferred energy:
        # it is shown as energy above the cap and used once, never added to the
        # permanent cap.
        base_cap = BASE_ENERGY + profile['energy_purchases'] * 100
        pending = _pending_energy(doc)
        boost_until = float(user.get('dojo_boost_until', 0) or 0)
        started = doc.get('started_at')
        finish = doc.get('finish_at')
        if doc and not doc.get('collected') and finish:
            phase = 'ready_to_collect' if now >= finish else 'mining'
        else:
            phase = 'ready'
        progress = 0.0
        remaining = 0.0
        energy_cap = base_cap
        projected_boost = 0
        if phase == 'ready':
            energy = base_cap + pending
            energy_start = energy
            energy_cap = base_cap
            base_rate = profile['base_rate']
            current_rate = base_rate
            # A boost bought before start is part of the projected reward.
            projected_boost = _boost_bonus(
                base_rate, now, min(boost_until, now + CYCLE_SECONDS))
            amount = estimate_amount(base_rate, energy) + projected_boost
        else:
            energy_start = max(0, int(doc.get('energy_start', base_cap)))
            energy_cap = max(0, int(doc.get('energy_max', energy_start)))
            base_rate = float(doc.get('base_rate', profile['base_rate']))
            amount = int(doc.get('amount', estimate_amount(base_rate, energy_start)))
            # A refill/task bonus adds energy at the moment it arrives, so it
            # must not be drained retroactively by earlier hours.
            energy = self._energy_at(doc, now, finish, energy_start)
            if phase == 'mining':
                remaining = max(0.0, finish - now)
                progress = min(1.0, max(0.0, (now - started) / (finish - started))) if finish > started else 0.0
            else:
                progress = 1.0
            current_rate = base_rate * (LOW_POWER if energy <= 0 else 1.0)
        boost_active = boost_until > now
        if boost_active and energy > 0:
            current_rate *= 1.0 + SPEED_BOOST_BONUS
        boost_cycle_key = self._boost_cycle_key(doc, now)
        return {
            'phase': phase,
            'server_now': now,
            'balance': balance,
            'reward': amount,
            'next_reward': estimate_amount(profile['base_rate'], base_cap + pending)
            + projected_boost,
            'energy': energy,
            'energy_max': energy_cap,
            'energy_start': energy_start,
            'task_energy_pending': pending,
            'energy_per_hour': ENERGY_PER_HOUR,
            'energy_refill_stars': ENERGY_REFILL_STARS,
            'energy_refill_amount': ENERGY_REFILL_AMOUNT,
            'energy_refill_available': phase == 'mining' and energy <= 0,
            'circle_available': phase == 'mining' and (energy <= 0 or bool(doc.get('circle_energy_events'))),
            'circle_energy_limit': energy_cap // 2,
            'base_rate': base_rate,
            'current_rate': current_rate,
            'pickaxe_level': profile['pickaxe_level'],
            'energy_purchases': profile['energy_purchases'],
            'auto_collect': profile['auto_collect'],
            'boost_until': boost_until,
            'boost_active': boost_active,
            'boost_seconds_left': max(0, int(boost_until - now)),
            'boost_percent': SPEED_BOOST_PERCENT,
            'boost_stars': SPEED_BOOST_STARS,
            'boost_hours': SPEED_BOOST_SECONDS // 3600,
            'boost_cycle_key': boost_cycle_key,
            'boost_purchased': str(user.get('dojo_boost_cycle') or '')
            == boost_cycle_key,
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
            base_cap = BASE_ENERGY + profile['energy_purchases'] * 100
            pending = _pending_energy(doc or {})
            # One task bonus is spent by exactly one cycle.  It is consumed
            # here and never folded into the permanent cap.
            energy_start = base_cap + pending
            base_rate = profile['base_rate']
            finish_at = now + CYCLE_SECONDS
            boost_until = float(user.get('dojo_boost_until', 0) or 0)
            boost_bonus = _boost_bonus(base_rate, now, min(boost_until, finish_at))
            version = int((doc or {}).get('version', 0))
            session = {
                'started_at': now,
                'finish_at': finish_at,
                'collected': False,
                'amount': estimate_amount(base_rate, energy_start) + boost_bonus,
                'base_rate': base_rate,
                'energy_start': energy_start,
                'energy_max': base_cap,
                'energy_refills': [],
                'circle_energy_events': [],
                'circle_reward': 0,
                'task_energy_pending': [],
                'task_energy_bonuses': [],
                'boost_bonus': boost_bonus,
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
            # A boost bought between cycles belongs to this cycle.  Mark it now
            # so the same cycle cannot buy a second one.
            await self.users.update_one(
                {'id': user_id, 'dojo_boost_cycle': 'upcoming'},
                {'$set': {'dojo_boost_cycle': f'c:{int(now * 1000)}'}},
            )
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
                    description='Dojo miner: 3h SenseiCoin cycle',
                )
            except Exception:
                await self._rollback(user_id, version + 1)
                raise GameError('Майнер не смог выплатить награду. Попробуй ещё раз.')
            if not isinstance(result, dict) or not result.get('success'):
                await self._rollback(user_id, version + 1)
                if isinstance(result, dict) and result.get('reason') == 'insufficient_bank':
                    raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
                raise GameError('Награда недоступна для этого профиля.')
            state = await self.state(user_id)
            state['mined'] = amount
            state['balance'] = result.get('new_coins', state['balance'])
            return state

    async def apply_energy_refill(self, user_id: int, charge: str) -> bool:
        """Add purchased energy to the running cycle, once per Telegram charge."""
        if not charge or type(user_id) is not int or user_id <= 0:
            return False
        async with self._locks[user_id]:
            now = time.time()
            doc = await self.miners.find_one({'_id': user_id})
            if not doc or doc.get('collected') or now >= doc.get('finish_at', 0):
                return False
            refills = list(doc.get('energy_refills') or [])
            if any(str(item.get('charge')) == str(charge) for item in refills):
                return True
            finish = float(doc.get('finish_at', now))
            energy_start = max(0, int(doc.get('energy_start', BASE_ENERGY)))
            if self._energy_at(doc, now, finish, energy_start) > 0:
                return False
            version = int(doc.get('version', 0))
            base_rate = float(doc.get('base_rate', BASE_RATE))
            remaining_hours = max(0.0, (finish - now) / 3600)
            # 100 energy buys one hour at full power; the rest of the cycle
            # would have run at 10%, so only that hour is the added reward.
            full_hours = min(remaining_hours, ENERGY_REFILL_AMOUNT / ENERGY_PER_HOUR)
            extra = int(base_rate * full_hours * (1.0 - LOW_POWER) + 0.5)
            amount = int(doc.get('amount', MINING_REWARD)) + extra
            refills.append({
                'charge': str(charge),
                'at': now,
                'amount': ENERGY_REFILL_AMOUNT,
            })
            circle_reward = self._circle_reward({**doc, 'energy_refills': refills}, now)
            amount += circle_reward - int(doc.get('circle_reward', 0))
            updated = await self.miners.find_one_and_update(
                {'_id': user_id, 'version': version, 'collected': False},
                {'$set': {'energy_refills': refills, 'amount': amount, 'circle_reward': circle_reward},
                 '$inc': {'version': 1}},
            )
            if updated:
                return True
            current = await self.miners.find_one({'_id': user_id})
            return bool(current and any(
                str(item.get('charge')) == str(charge)
                for item in current.get('energy_refills') or []))

    @staticmethod
    def _matched(result) -> bool:
        if result is True or isinstance(result, dict):
            return True
        matched = getattr(result, 'matched_count', None)
        return True if not isinstance(matched, int) else matched == 1

    async def apply_task_energy(self, user_id: int, amount: int, key: str) -> bool:
        """Apply a task's +100 energy exactly once.

        While a cycle is running the energy is spent immediately and adds the
        reward for its full-power hours.  If no cycle can accept energy, it is
        parked as pending and folded into the next start.  The permanent cap is
        never changed.
        """
        try:
            amount = max(0, int(amount))
        except (TypeError, ValueError):
            return False
        if type(user_id) is not int or user_id <= 0 or amount <= 0:
            return False
        key = str(key or '')
        async with self._locks[user_id]:
            for _ in range(4):
                now = time.time()
                doc = await self.miners.find_one({'_id': user_id})
                finish = float((doc or {}).get('finish_at', 0) or 0)
                active = bool(doc and not doc.get('collected') and finish and now < finish)
                if active:
                    bonuses = list(doc.get('task_energy_bonuses') or [])
                    if any(str(item.get('key')) == key for item in bonuses):
                        return True
                    bonuses.append({'key': key, 'at': now, 'amount': amount})
                    base_rate = float(doc.get('base_rate', BASE_RATE))
                    hours = min(max(0.0, (finish - now) / 3600),
                                amount / ENERGY_PER_HOUR)
                    extra = int(base_rate * hours * (1.0 - LOW_POWER) + 0.5)
                    circle_reward = self._circle_reward({**doc, 'task_energy_bonuses': bonuses}, now)
                    new_amount = int(doc.get('amount', MINING_REWARD)) + extra + circle_reward - int(doc.get('circle_reward', 0))
                    updated = await self.miners.find_one_and_update(
                        {'_id': user_id, 'version': int(doc.get('version', 0)),
                         'collected': False},
                        {'$set': {'task_energy_bonuses': bonuses,
                                  'amount': new_amount, 'circle_reward': circle_reward},
                         '$inc': {'version': 1}},
                    )
                    if updated:
                        return True
                    continue

                pending = list((doc or {}).get('task_energy_pending') or [])
                if any(str(item.get('key')) == key for item in pending):
                    return True
                pending.append({'key': key, 'at': now, 'amount': amount})
                if doc:
                    updated = await self.miners.find_one_and_update(
                        {'_id': user_id, 'version': int(doc.get('version', 0))},
                        {'$set': {'task_energy_pending': pending},
                         '$inc': {'version': 1}},
                    )
                    if updated:
                        return True
                    continue
                try:
                    await self.miners.insert_one({
                        '_id': user_id,
                        'collected': True,
                        'task_energy_pending': pending,
                        'version': 1,
                    })
                    return True
                except Exception:
                    # A parallel claim created the document first; retry so the
                    # new claim is appended rather than lost.
                    continue
        return False

    async def apply_speed_boost(self, user_id: int, charge: str) -> bool:
        """Apply one +50% speed boost for one hour per mining cycle.

        A cycle may buy at most one boost.  The timestamp is stored as an
        absolute ``dojo_boost_until``; buying before the next cycle is allowed
        once and is consumed by that cycle at start.
        """
        if not charge or type(user_id) is not int or user_id <= 0:
            return False
        charge = str(charge)
        async with self._locks[user_id]:
            for _ in range(4):
                now = time.time()
                user = await self.users.find_one({'id': user_id})
                if not user or user.get('is_banned'):
                    return False
                receipts = list(user.get('dojo_applied_receipts') or [])
                if charge in receipts:
                    return True
                doc = await self.miners.find_one({'_id': user_id}) or {}
                cycle_key = self._boost_cycle_key(doc, now)
                if str(user.get('dojo_boost_cycle') or '') == cycle_key:
                    # One purchase per cycle, even after the first hour ends.
                    return False
                old = user.get('dojo_boost_until')
                old_until = max(0.0, float(old or 0))
                starts_at = max(now, old_until)
                new_until = starts_at + SPEED_BOOST_SECONDS
                query = {
                    'id': user_id,
                    'is_banned': {'$ne': True},
                    'dojo_applied_receipts': {'$ne': charge},
                    'dojo_boost_cycle': {'$ne': cycle_key},
                }
                if old is None:
                    query['dojo_boost_until'] = {'$exists': False}
                else:
                    query['dojo_boost_until'] = old
                updated = await self.users.update_one(
                    query,
                    {'$set': {'dojo_boost_until': new_until,
                              'dojo_boost_cycle': cycle_key,
                              'dojo_boost_updated_at': now},
                     '$addToSet': {'dojo_applied_receipts': charge}},
                )
                if not self._matched(updated):
                    current = await self.users.find_one({'id': user_id}) or {}
                    if charge in (current.get('dojo_applied_receipts') or []):
                        return True
                    if str(current.get('dojo_boost_cycle') or '') == cycle_key:
                        return False
                    continue

                # Reward the part of the running cycle that the boost covers.
                doc = await self.miners.find_one({'_id': user_id})
                finish = float((doc or {}).get('finish_at', 0) or 0)
                if doc and not doc.get('collected') and now < finish:
                    bonus = _boost_bonus(
                        float(doc.get('base_rate', BASE_RATE)),
                        max(now, old_until), min(new_until, finish),
                    )
                    if bonus > 0:
                        version = int(doc.get('version', 0))
                        await self.miners.find_one_and_update(
                            {'_id': user_id, 'version': version, 'collected': False},
                            {'$set': {'boost_bonus': int(doc.get('boost_bonus', 0)) + bonus},
                             '$inc': {'amount': bonus, 'version': 1}},
                        )
                return True
        return False

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
