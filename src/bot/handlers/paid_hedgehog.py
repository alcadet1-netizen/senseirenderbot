"""Paid repeat entrypoints; a Stars receipt, not a button press, grants a run."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest

from src.services.hedgehog_service import GameError
from src.services.maintenance_service import MaintenanceService

router = Router(name='paid_hedgehog')
logger = logging.getLogger(__name__)


def repeat_keyboard(owner_id=None):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='🦔 Ещё попытка за Stars', callback_data=f'petbuy:offer:{owner_id}' if owner_id else 'petbuy:offer')]])


async def edit_notice(bot, notice, text, *, markup=None, photo=False):
    """Edit only the stored bot notification; never fall back to another message."""
    try:
        if photo:
            return await bot.edit_message_caption(**notice, caption=text, reply_markup=markup, parse_mode=None)
        return await bot.edit_message_text(**notice, text=text, reply_markup=markup, parse_mode=None)
    except TelegramBadRequest as exc:
        if 'message is not modified' not in str(exc).lower():
            raise


@router.callback_query(F.data.regexp(r'^petbuy:offer(?::[0-9]+)?$'))
async def offer(query, container):
    owner = query.data.split(':')[2:]
    if owner and int(owner[0]) != query.from_user.id:
        await query.answer('Это чужое уведомление. Вызовите /senseidaily для своей попытки.', show_alert=True)
        return
    if not owner and query.message and query.message.chat.type != 'private':
        await query.answer('Обновите уведомление командой /senseidaily.', show_alert=True)
        return
    await query.answer()
    if not query.message:
        return
    notice = {'chat_id': query.message.chat.id, 'message_id': query.message.message_id}
    photo = bool(query.message.photo)
    try:
        if container.settings.maintenance_mode or MaintenanceService.is_enabled():
            raise GameError('Оплата временно недоступна: обслуживание.')
        order = await container.paid_hedgehog_service.quote(query.from_user.id)
        order = await container.paid_hedgehog_service.bind_notice(
            order['_id'], query.from_user.id, notice['chat_id'], notice['message_id'], photo=photo)
        notice = {k: order['notice'][k] for k in ('chat_id', 'message_id')}
        photo = order['notice'].get('photo', False)
        # Invoice link opens Telegram's mandatory Stars confirmation without a
        # separate invoice message. No reward on this action.
        link = await query.bot.create_invoice_link(title='Ещё одна Ежа',
            description=f"Полная награда и 15 секунд ласки. Попытка №{order['number']}; серия не увеличивается.",
            payload=f"petbuy:{order['_id']}", currency='XTR', provider_token='',
            prices=[LabeledPrice(label='Повторная Ежа', amount=order['stars'])])
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"Оплатить {order['stars']} ⭐", url=link)]])
        await edit_notice(query.bot, notice,
            f"🦔 Повторная Ежа · попытка №{order['number']}\nСтоимость: {order['stars']} ⭐.\n"
            'После подтверждения Telegram это уведомление обновится. Не оплачивайте счёт повторно.',
            markup=markup, photo=photo)
    except GameError as exc:
        await edit_notice(query.bot, notice, str(exc), photo=photo, markup=repeat_keyboard(query.from_user.id))
    except Exception:
        logger.warning('Paid hedgehog invoice preparation unavailable')
        # Do not assert a payment outcome based on an ambiguous transport error.
        try:
            await edit_notice(query.bot, notice,
                'Не удалось обновить оплату. Проверьте статус Stars перед повтором. /paysupport', photo=photo)
        except TelegramAPIError:
            logger.warning('Paid hedgehog notice edit unavailable; no new message sent')


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


async def payment_status(message, container, order_id, text):
    order = await container.paid_hedgehog_service.orders.find_one(
        {'_id': order_id, 'user_id': message.from_user.id})
    notice = (order or {}).get('notice')
    if notice:
        await edit_notice(message.bot, {k: notice[k] for k in ('chat_id', 'message_id')},
                          text, photo=notice.get('photo', False))
    else:
        # Compatibility with invoices issued before this release.
        await message.answer(text, parse_mode=None)


async def deliver(message, container, receipt):
    if receipt['state'] in {'refund_required', 'refunded'}:
        if receipt['state'] != 'refunded':
            try:
                await message.bot.refund_star_payment(user_id=receipt['user_id'], telegram_payment_charge_id=receipt['_id'])
                await container.paid_hedgehog_service.payments.update_one({'_id': receipt['_id']}, {'$set': {'state': 'refunded'}})
            except TelegramAPIError:
                await payment_status(message, container, receipt['order_id'], 'Для этого платежа требуется возврат. Напишите /paysupport с номером платежа.')
                return
        await payment_status(message, container, receipt['order_id'], 'Платёж возвращён: повторное начисление не выполнялось.')
        return
    try:
        session = await container.daily_pet_service.owned(receipt['pet_token'], receipt['user_id'])
    except GameError:
        await payment_status(message, container, receipt['order_id'], 'Эта оплаченная попытка уже учтена. Повторного начисления нет.')
        return
    if session.get('delivered'):
        return
    order = await container.paid_hedgehog_service.orders.find_one(
        {'_id': receipt['order_id'], 'user_id': receipt['user_id']})
    notice = (order or {}).get('notice')
    from src.bot.presenters.daily_hedgehog import send_reward_notice
    await send_reward_notice(message, message.from_user, container, receipt['reward'], session, notice=notice)


async def successful_payment(message, container):
    try:
        receipt = await container.paid_hedgehog_service.receive(message.from_user.id, message.successful_payment)
        await deliver(message, container, receipt)
    except Exception:
        logger.error('Paid hedgehog fulfillment failed; payment reconciliation required')
        try:
            await payment_status(message, container,
                message.successful_payment.invoice_payload.removeprefix('petbuy:'),
                'Оплата требует проверки. Повторите /senseidaily; если попытка не появилась — /paysupport. Не оплачивайте повторно.')
        except Exception:
            logger.error('Paid hedgehog reconciliation notice unavailable; no duplicate sent')
