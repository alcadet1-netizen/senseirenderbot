"""Read-only emission watch. It never changes money or controls payouts.

The existing counters do not form a verified lifetime issuance ledger. Their
sum is therefore only an accounting estimate, not a proof of historical supply.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation

from bson.decimal128 import Decimal128

from src.core.constants import TOTAL_EMISSION_CAP

logger = logging.getLogger(__name__)
CORRECTION_ID = 'counter-baseline-v1'


def _amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, Decimal128)):
        return None
    try:
        n = value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def correction_reserve(doc):
    """Old documents have no reserve; corrected documents must retain one."""
    keys = ('emission_correction_reserve', 'emission_correction_applied', 'emission_correction_id')
    if not any(key in doc for key in keys):
        return Decimal(0)  # Existing uncorrected documents.
    if doc.get('emission_correction_applied') is not True or doc.get('emission_correction_id') != CORRECTION_ID:
        return None
    reserve = _amount(doc.get('emission_correction_reserve'))
    return reserve if reserve is not None and reserve > 0 else None


def assess(doc):
    """Classify one bank document; missing values are never replaced by zero."""
    doc = doc if isinstance(doc, dict) else {}
    current, burned = _amount(doc.get('total_emitted')), _amount(doc.get('burned'))
    reserve = correction_reserve(doc)
    cap = Decimal(str(TOTAL_EMISSION_CAP))
    stored_cap = _amount(doc.get('emission_cap'))
    result = {'current': current, 'burned': burned, 'cap': cap,
              'stored_cap': stored_cap, 'correction_reserve': reserve, 'estimate': None, 'status': 'unknown'}
    if current is None or burned is None or reserve is None or ('emission_cap' in doc and (stored_cap is None or stored_cap != cap)):
        return result
    estimate = current + burned + reserve
    result['estimate'] = estimate
    # A baseline from available counters is not proof of historical supply.
    if current > cap or estimate > cap:
        result['status'] = 'over_estimate'
    elif estimate >= cap:
        result['status'] = 'limit_reached'
    else:
        result['status'] = 'observing'
    return result


def format_report(result):
    def fmt(n):
        if n is None:
            return 'неизвестно'
        return f'{n:,.2f}'.replace(',', ' ').rstrip('0').rstrip('.')

    status_text = {
        'unknown': 'Недостаточно данных или лимит в документе отличается от настройки.',
        'over_estimate': 'Учтённые показатели превышают предел. Требуется сверка.',
        'limit_reached': 'Расчётная сумма достигла предела; новый выпуск через резервирование недоступен.',
        'observing': 'По доступным счётчикам критический порог не достигнут.',
    }
    status = result['status']
    lines = [
        '🛡 Страж эмиссии · только наблюдение',
        status_text[status],
        f"Текущая эмиссия: {fmt(result['current'])} Coin",
        f"Учтено сжиганий: {fmt(result['burned'])} Coin",
        f"Резерв лимита после коррекции: {fmt(result['correction_reserve'])} Coin",
        f"Расчётная сумма: {fmt(result['estimate'])} Coin",
        f"Предел: {fmt(result['cap'])} Coin",
        f"Осталось по оценке: {fmt(max(Decimal(0), result['cap'] - result['estimate']) if result['estimate'] is not None else None)} Coin",
    ]
    if result['stored_cap'] is not None and result['stored_cap'] != result['cap']:
        lines.append(f"Лимит в документе банка: {fmt(result['stored_cap'])} Coin")
    lines.extend([
        'Резервирование нового выпуска учитывает эмиссию, сжигания и резерв; сжигание не освобождает лимит.',
        'Сумма счётчиков и резерва — оценка по доступным данным, не проверенная история.',
        'Страж не блокирует выпуск и не меняет балансы. История и другие источники начислений могут быть неполными.',
    ])
    return '\n'.join(lines)


async def read_report(db):
    """One projected read; no full collection scan, initialization or writes."""
    doc = await db.bank.find_one({'_id': 'single'},
        {'total_emitted': 1, 'burned': 1, 'emission_cap': 1, 'emission_correction_reserve': 1, 'emission_correction_applied': 1, 'emission_correction_id': 1})
    return assess(doc)


class EmissionWatch:
    """Periodic read and rate-limited private alerts per administrator.

    State is process-local; instances and restarts can produce duplicate alerts.
    Database errors are reported separately and never presented as zeroes.
    """
    def __init__(self, db, bot, admin_ids, *, interval=900, cooldown=21600,
                 clock=time.monotonic):
        self.db, self.bot = db, bot
        self.admin_ids = tuple(dict.fromkeys(x for x in admin_ids if type(x) is int and x > 0))
        self.interval, self.cooldown, self.clock = interval, cooldown, clock
        self._last = {}

    async def tick(self):
        if not self.admin_ids:
            return 'disabled'
        try:
            result = await asyncio.wait_for(read_report(self.db), timeout=10)
            status = result['status']
            text = format_report(result)
        except Exception as exc:
            logger.warning('Emission watch read failed: %s', type(exc).__name__)
            status = 'read_error'
            text = ('🛡 Страж эмиссии · только наблюдение\n'
                    'Не удалось прочитать данные банка. Статус неизвестен; повторим проверку позже.')
        now = self.clock()
        for admin_id in self.admin_ids:
            previous = self._last.get(admin_id)
            # No unsolicited message on a healthy first observation; report a
            # recovery once after a previously delivered warning.
            if status == 'observing' and previous is None:
                continue
            if previous and previous[0] == status and now - previous[1] < self.cooldown:
                continue
            if status == 'observing' and previous and (previous[0] == 'observing' or not previous[2]):
                self._last[admin_id] = ('observing', now, False)
                continue
            try:
                await asyncio.wait_for(self.bot.send_message(admin_id, text, parse_mode=None), timeout=10)
            except Exception as exc:
                # Suppress retries for the same status too, so a blocked bot or
                # unavailable Telegram does not send a request every interval.
                logger.warning('Emission watch alert failed: %s', type(exc).__name__)
                self._last[admin_id] = (status, now, False)
            else:
                self._last[admin_id] = (status, now, True)
        return status

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning('Emission watch tick failed: %s', type(exc).__name__)
            await asyncio.sleep(self.interval)
