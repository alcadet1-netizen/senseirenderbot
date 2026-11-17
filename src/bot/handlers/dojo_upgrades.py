"""Telegram Stars checkout and receipt delivery for /dojo upgrades."""
import logging

from aiogram.exceptions import TelegramAPIError

from src.services.dojo_upgrade_service import KINDS
from src.services.hedgehog_service import GameError

logger = logging.getLogger(__name__)


async def pre_checkout(query, container):
    try:
        await container.dojo_upgrade_service.checkout(
            query.invoice_payload, query.from_user.id,
            query.currency, query.total_amount)
        await query.answer(ok=True)
    except GameError as exc:
        await query.answer(ok=False, error_message=str(exc)[:200])
    except Exception:
        logger.error('Dojo upgrade checkout unavailable')
        await query.answer(ok=False, error_message='Оплата временно недоступна. Попробуйте позже.')


async def successful_payment(message, container):
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        receipt = await container.dojo_upgrade_service.receive(user_id, payment)
    except Exception:
        logger.error('Dojo upgrade payment requires reconciliation')
        await message.answer(
            'Оплата улучшения требует проверки. Открой /dojo → «Улучшения»; '
            'если улучшение не появилось — /paysupport. Не оплачивай повторно.',
            parse_mode=None)
        return
    if receipt['state'] == 'fulfilled':
        kind = receipt.get('kind')
        if kind == 'refill':
            await message.answer(
                '✅ Энергия пополнена на +100 в текущем цикле.\n'
                f'Оплачено: {receipt["stars"]} ⭐.\n'
                'Открой /dojo и продолжай майнинг.',
                parse_mode=None)
            return
        title = KINDS.get(kind, {}).get('title', 'Улучшение')
        await message.answer(
            f'✅ {title} активировано навсегда.\n'
            f'Оплачено: {receipt["stars"]} ⭐.\n'
            'Открой /dojo → «Улучшения», чтобы увидеть новый уровень.',
            parse_mode=None)
        if kind == 'auto':
            try:
                await container.dojo_miner_service.auto_step(user_id)
            except Exception:
                logger.error('Dojo auto-collect activation pass failed user=%s', user_id)
        return
    if receipt['state'] in {'refund_required', 'refunded'}:
        if receipt['state'] != 'refunded':
            try:
                await message.bot.refund_star_payment(
                    user_id=user_id,
                    telegram_payment_charge_id=receipt['_id'])
                await container.dojo_upgrade_service.mark_refunded(receipt['_id'])
            except TelegramAPIError:
                logger.error('Dojo upgrade refund unavailable charge=%s', receipt['_id'])
                await message.answer(
                    'Улучшение не было активировано. Возврат Stars требует проверки: /paysupport.',
                    parse_mode=None)
                return
        await message.answer(
            'Улучшение не активировано, Stars возвращены. '
            'Если не пришли — /paysupport.',
            parse_mode=None)
