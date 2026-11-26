"""Three-hour SenseiCoin miner behind the /dojo Mini App.

A cycle has a fixed power level from the pickaxe and an energy budget. Every
100 energy lasts one hour at full power; after that the pickaxe runs at 10% of
its base rate for the rest of the three-hour cycle. The browser only renders
state; start, collect and automatic cycles are validated and paid here.
"""
import asyncio
import logging
import time
from uuid import uuid4
from datetime import datetime, timezone
from collections import defaultdict

from src.services.hedgehog_service import GameError
from src.services.referral_economy import RATES, ancestors, transaction

CYCLE_SECONDS = 3 * 60 * 60
CYCLE_HOURS = CYCLE_SECONDS / 3600
BASE_RATE = 75.0
PICKAXE_STEP = 50.0
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
        await self.mongo.database.dojo_ref_rewards.create_index([('owner', 1), ('token', 1)])

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
                existing = next((item for item in events if item.get('key') == request_id), None)
                if existing is not None:
                    return {'added': existing.get('amount', 1), 'replayed': True}
                finish = float(doc.get('finish_at') or 0)
                if doc.get('collected') or now >= finish:
                    raise GameError('Майнинг не запущен.')
                energy, _ = self._energy_timeline(doc, now)
                cap = BASE_ENERGY
                added = min(1.0, max(0.0, cap - energy))
                if added <= 1e-9:
                    return {'added': 0, 'replayed': False}
                events.append({'key': request_id, 'at': now, 'amount': added})
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
                    return {'added': added, 'replayed': False}
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
        circle_energy = self._energy_timeline(doc, now)[0] if phase == 'mining' else energy
        return {
            'phase': phase,
            'server_now': now,
            'balance': balance,
            'reward': amount,
            'next_reward': estimate_amount(profile['base_rate'], base_cap + pending)
            + projected_boost,
            'energy': energy,
            'energy_max': energy_cap,  # current cycle's frozen cap
            'permanent_energy_max': base_cap,  # purchased cap for the next cycle
            'energy_start': energy_start,
            'task_energy_pending': pending,
            'energy_per_hour': ENERGY_PER_HOUR,
            'energy_refill_stars': ENERGY_REFILL_STARS,
            'energy_refill_amount': ENERGY_REFILL_AMOUNT,
            'energy_refill_available': phase == 'mining' and energy <= 0,
            'circle_energy': circle_energy,
            'circle_available': phase == 'mining' and circle_energy < BASE_ENERGY,
            'circle_energy_limit': BASE_ENERGY,
            'base_rate': base_rate,
            'current_rate': current_rate,
            'pickaxe_level': profile['pickaxe_level'],
            'energy_purchases': profile['energy_purchases'],
            'auto_collect': profile['auto_collect'],
            'last_auto_collect_at': doc.get('last_auto_collect_at'),
            'auto_waiting': phase == 'ready_to_collect' and bool(doc.get('auto_waiting')),
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
                'auto_waiting': False,
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

    async def claim_referral_mining(self, owner, token):
        if not isinstance(token, str) or len(token) != 32:
            raise GameError('Неверная награда.')
        db = self.mongo.database

        async def work(session):
            row = await db.dojo_ref_rewards.find_one({'owner': owner, 'token': token}, session=session)
            if not row or row['pending'] <= 0:
                raise GameError('Нет доступного бонуса. Обнови список.')
            reset = await db.dojo_ref_rewards.update_one(
                {'_id': row['_id'], 'pending': row['pending']}, {'$set': {'pending': 0}}, session=session)
            if not reset.matched_count:
                raise GameError('Сумма изменилась. Обнови список.')
            amount = row['pending'] / 1000
            result = await self.users.update_one(
                {'id': owner, 'is_banned': {'$ne': True}},
                {'$inc': {'coins': amount, 'referral_earned': amount}}, session=session)
            if not result.matched_count:
                raise GameError('Награда недоступна для этого профиля.')
            await db.transactions.insert_one(dict(user_id=owner, source_user_id=row['source'],
                coins_change=amount, xp_change=0, tx_type='dojo_referral_claim',
                created_at=datetime.now(timezone.utc)), session=session)
            return {'claimed': amount}

        return await transaction(self.mongo, work)

    async def collect(self, user_id: int, *, automatic=False) -> dict:
        """Commit the cycle, bank debit, player credit and receipt together."""
        async with self._locks[user_id]:
            now = time.time()

            async def work(session):
                doc = await self.miners.find_one({'_id': user_id}, session=session)
                if not doc:
                    raise GameError('Намайненного пока нет. Сначала запусти майнинг.')
                if doc.get('collected'):
                    raise GameError('Награда уже получена. Запусти новый цикл.')
                if now < doc.get('finish_at', 0):
                    raise GameError('Майнинг ещё не завершён.')
                user = await self.users.find_one({'id': user_id}, session=session)
                if not user or user.get('is_banned'):
                    raise GameError('Награда недоступна для этого профиля.')
                version = int(doc.get('version', 0))
                amount = max(0, int(doc.get('amount', MINING_REWARD)))
                settled = {'collected': True, 'collected_at': now}
                if automatic:
                    settled['last_auto_collect_at'] = now
                claimed = await self.miners.find_one_and_update(
                    {'_id': user_id, 'version': version, 'collected': False},
                    {'$set': settled,
                     '$inc': {'version': 1}}, session=session)
                if not claimed:
                    raise GameError('Награда уже получена. Обнови экран.')
                # Reserve bonuses with the mining payout. Integer thousandths
                # keep pending balances exact across repeated small cycles.
                bonus_units = 0
                if amount and user.get('referrer_id'):
                    db = self.mongo.database
                    for parent, rate in zip(await ancestors(db, user_id, session), RATES):
                        if parent.get('is_banned') or parent.get('is_bot'):
                            continue
                        units = int(amount * rate * 1000)
                        owner = parent['id']
                        await db.dojo_ref_rewards.update_one(
                            {'_id': f'{owner}:{user_id}'},
                            {'$setOnInsert': {'owner': owner, 'source': user_id, 'token': uuid4().hex},
                             '$inc': {'pending': units, 'lifetime': units}},
                            upsert=True, session=session)
                        bonus_units += units
                remaining = amount + bonus_units / 1000
                # Both pre-migration bank accounts are spent in the same
                # transaction; failure to cover the full reward aborts all.
                for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                    if not remaining:
                        break
                    account = await self.mongo.database.bank.find_one({'_id': bank_id}, session=session) or {}
                    take = min(remaining, max(0, float(account.get(field, 0) or 0)))
                    if take:
                        debit = await self.mongo.database.bank.update_one(
                            {'_id': bank_id, field: {'$gte': take}},
                            {'$inc': {field: -take}}, session=session)
                        if not debit.matched_count:
                            raise GameError('Баланс банка изменился. Попробуй снова.')
                        remaining -= take
                if remaining > 0:
                    raise GameError('SenseiBank не может выплатить награду. Попробуй позже.')
                credited = await self.users.update_one(
                    {'id': user_id, 'is_banned': {'$ne': True}},
                    {'$inc': {'coins': amount}}, session=session)
                if not credited.matched_count:
                    raise GameError('Награда недоступна для этого профиля.')
                await self.mongo.database.transactions.insert_one({
                    'user_id': user_id, 'tx_type': 'game_win', 'xp_change': 0,
                    'coins_change': amount, 'description': 'Dojo miner: 3h SenseiCoin cycle',
                    'created_at': datetime.now(timezone.utc)}, session=session)
                return amount, float(user.get('coins', 0) or 0) + amount

            try:
                amount, balance = await transaction(self.mongo, work)
            except GameError:
                raise
            except Exception:
                logger.exception('Dojo miner collection failed user=%s', user_id)
                raise GameError('Майнер не смог выплатить награду. Попробуй ещё раз.')
            state = await self.state(user_id)
            state['mined'] = amount
            state['balance'] = balance
            return state

    async def apply_energy_refill(self, user_id: int, charge: str) -> bool:
        """Add purchased energy to the running cycle, once per Telegram charge."""
        if not charge or type(user_id) is not int or user_id <= 0:
            return False
        async with self._locks[user_id]:
            for _ in range(8):
                now = time.time()
                doc = await self.miners.find_one({'_id': user_id})
                refills = list((doc or {}).get('energy_refills') or [])
                # A replay must succeed even if the cycle finished after credit.
                if any(str(item.get('charge')) == str(charge) for item in refills):
                    return True
                if not doc or doc.get('collected') or now >= doc.get('finish_at', 0):
                    return False
                finish = float(doc.get('finish_at', now))
                energy_start = max(0, int(doc.get('energy_start', BASE_ENERGY)))
                if self._energy_at(doc, now, finish, energy_start) > 0:
                    return False
                version = int(doc.get('version', 0))
                base_rate = float(doc.get('base_rate', BASE_RATE))
                remaining_hours = max(0.0, (finish - now) / 3600)
                full_hours = min(remaining_hours, ENERGY_REFILL_AMOUNT / ENERGY_PER_HOUR)
                extra = int(base_rate * full_hours * (1.0 - LOW_POWER) + 0.5)
                amount = int(doc.get('amount', MINING_REWARD)) + extra
                refills.append({'charge': str(charge), 'at': now, 'amount': ENERGY_REFILL_AMOUNT})
                circle_reward = self._circle_reward({**doc, 'energy_refills': refills}, now)
                amount += circle_reward - int(doc.get('circle_reward', 0))
                updated = await self.miners.find_one_and_update(
                    {'_id': user_id, 'version': version, 'collected': False},
                    {'$set': {'energy_refills': refills, 'amount': amount, 'circle_reward': circle_reward},
                     '$inc': {'version': 1}},
                )
                if updated:
                    return True
            # A version conflict is not proof that the purchase was ineligible.
            # Leave the receipt pending rather than refunding an uncertain payment.
            raise RuntimeError('Energy refill update conflicted repeatedly')

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
            async def apply(session):
                # The boost entitlement and its cycle reward must commit together.
                # Otherwise a process crash or a concurrent circle/refill update
                # can mark the Stars receipt applied without crediting the reward.
                now = time.time()
                user = await self.users.find_one({'id': user_id}, session=session)
                if not user or user.get('is_banned'):
                    return False
                if charge in (user.get('dojo_applied_receipts') or []):
                    return True
                doc = await self.miners.find_one({'_id': user_id}, session=session) or {}
                cycle_key = self._boost_cycle_key(doc, now)
                if str(user.get('dojo_boost_cycle') or '') == cycle_key:
                    return False
                old = user.get('dojo_boost_until')
                old_until = max(0.0, float(old or 0))
                starts_at = max(now, old_until)
                new_until = starts_at + SPEED_BOOST_SECONDS
                query = {'id': user_id, 'is_banned': {'$ne': True},
                         'dojo_applied_receipts': {'$ne': charge},
                         'dojo_boost_cycle': {'$ne': cycle_key}}
                query['dojo_boost_until'] = {'$exists': False} if old is None else old
                updated = await self.users.update_one(
                    query, {'$set': {'dojo_boost_until': new_until,
                                     'dojo_boost_cycle': cycle_key,
                                     'dojo_boost_updated_at': now},
                            '$addToSet': {'dojo_applied_receipts': charge}}, session=session)
                if not self._matched(updated):
                    raise RuntimeError('Boost entitlement changed during transaction')
                finish = float(doc.get('finish_at', 0) or 0)
                if doc and not doc.get('collected') and now < finish:
                    bonus = _boost_bonus(float(doc.get('base_rate', BASE_RATE)),
                                         starts_at, min(new_until, finish))
                    if bonus > 0:
                        updated_cycle = await self.miners.find_one_and_update(
                            {'_id': user_id, 'version': int(doc.get('version', 0)),
                             'collected': False},
                            {'$set': {'boost_bonus': int(doc.get('boost_bonus', 0)) + bonus},
                             '$inc': {'amount': bonus, 'version': 1}}, session=session)
                        if not updated_cycle:
                            raise RuntimeError('Boost cycle changed during transaction')
                return True
            return await transaction(self.mongo, apply)

    async def auto_step(self, user_id: int) -> str:
        """Collect a finished cycle and immediately start the next one."""
        if type(user_id) is not int or user_id <= 0:
            return 'invalid'
        now = time.time()
        doc = await self.miners.find_one({'_id': user_id})
        if doc and not doc.get('collected') and now < doc.get('finish_at', 0):
            return 'mining'
        collecting = bool(doc and not doc.get('collected'))
        if collecting:
            try:
                await self.collect(user_id, automatic=True)
            except GameError:
                if not doc.get('auto_waiting'):
                    await self.miners.find_one_and_update(
                        {'_id': user_id, 'version': doc.get('version', 0), 'collected': False},
                        {'$set': {'auto_waiting': True}})
                return 'waiting'
        try:
            await self.start(user_id)
        except GameError:
            return 'not_started'
        return 'renewed' if collecting else 'started'

    async def auto_tick(self) -> int:
        """Run one background pass over players with auto-collect enabled."""
        started = 0
        async for user in self.users.find(
                {'dojo_auto_collect': True, 'is_banned': {'$ne': True}}, {'id': 1}):
            user_id = user.get('id')
            if type(user_id) is not int or user_id <= 0:
                continue
            if await self.auto_step(user_id) in ('started', 'renewed'):
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
