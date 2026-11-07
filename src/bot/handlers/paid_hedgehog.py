"""Paid repeat entrypoints; a Stars receipt, not a button press, grants a run."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.exceptions import TelegramAPIError

from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService

router = Router(name='paid_hedgehog')
logger = logging.getLogger(__name__)


def repeat_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='🦔 Ещё попытка за Stars', callback_data='petbuy:offer')]])


@router.callback_query(F.data == 'petbuy:offer')
async def offer(query, container):
    await query.answer()
    if not query.message:
        return
    try:
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            raise GameError('Оплата временно недоступна: обслуживание.')
        order = await container.paid_hedgehog_service.quote(query.from_user.id)
        await query.bot.send_invoice(chat_id=query.message.chat.id, title='Ещё одна Ежа',
            description=f"Повторная награда и 15 секунд ласки. Серия не увеличивается. Попытка №{order['number']}: {order['stars']} ⭐.",
            payload=f"petbuy:{order['_id']}", currency='XTR', provider_token='',
            prices=[LabeledPrice(label='Повторная Ежа', amount=order['stars'])])
    except GameError as exc:
        await query.message.answer(str(exc), parse_mode=None)
    except TelegramAPIError:
        await query.message.answer('Не удалось открыть оплату. Попробуйте позже.', parse_mode=None)
    except Exception:
        logger.error('Paid hedgehog invoice unavailable')
        await query.message.answer('Платные попытки временно недоступны. Деньги не списаны.', parse_mode=None)


async def pre_checkout(query, container):
    try:
        if container.settings.maintenance_mode or MaintenanceService.is_enabled() or query.currency != 'XTR':
            raise GameError('Оплата временно недоступна или неверная валюта.')
        await asyncio.wait_for(container.paid_hedgehog_service.checkout(
            query.invoice_payload.removeprefix('petbuy:'), query.from_user.id, query.total_amount, query.id), timeout=7)
        await query.answer(ok=True)
    except GameError as exc:
        await query.answer(ok=False, error_message=str(exc)[:200])
    except Exception:
        logger.error('Paid hedgehog checkout unavailable')
        await query.answer(ok=False, error_message='Оплата временно недоступна. Попробуйте позже.')


async def deliver(message, container, receipt):
    if receipt['state'] in {'refund_required', 'refunded'}:
        if receipt['state'] != 'refunded':
            try:
                await message.bot.refund_star_payment(user_id=receipt['user_id'], telegram_payment_charge_id=receipt['_id'])
                await container.paid_hedgehog_service.payments.update_one({'_id': receipt['_id']}, {'$set': {'state': 'refunded'}})
            except TelegramAPIError:
                await message.answer('Для этого платежа требуется возврат. Напишите /paysupport с номером платежа.', parse_mode=None)
                return
        await message.answer('Платёж возвращён: повторное начисление не выполнялось.', parse_mode=None)
        return
    try:
        session = await container.daily_pet_service.owned(receipt['pet_token'], receipt['user_id'])
    except GameError:
        await message.answer('Эта оплаченная попытка уже учтена. Повторного начисления нет.', parse_mode=None)
        return
    if session.get('delivered'):
        await message.answer('Эта оплаченная попытка уже выдана. Повторной выплаты нет.', parse_mode=None)
        return
    from src.bot.presenters.daily_hedgehog import send_reward_notice
    await send_reward_notice(message, message.from_user, container, receipt['reward'], session)


async def successful_payment(message, container):
    try:
        receipt = await container.paid_hedgehog_service.receive(message.from_user.id, message.successful_payment)
        await deliver(message, container, receipt)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
    except Exception:
        logger.error('Paid hedgehog fulfillment failed; payment reconciliation required')
        await message.answer('Оплата требует проверки. Повторите /senseidaily; если попытка не появилась — /paysupport. Не оплачивайте повторно.', parse_mode=None)
