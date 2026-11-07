"""Voluntary Telegram Stars donations, strictly separate from game economy."""
import logging
import re
from datetime import datetime, timezone

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update

router = Router(name='donate')
logger = logging.getLogger(__name__)
AMOUNTS = (5, 15, 50, 100)
XROCKET_URL = 'https://t.me/xrocket?start=inv_uBCMaE7YvzGJYwF'


def valid_payment(payload, user_id, currency, amount):
    return (currency == 'XTR' and amount in AMOUNTS
            and payload == f'donate:{user_id}:{amount}')


@router.message(Command('donate'))
async def cmd_donate(message):
    buttons = [[InlineKeyboardButton(text=f'⭐ {amount}', callback_data=f'donate:{amount}')
                for amount in AMOUNTS[row:row+2]] for row in (0, 2)]
    buttons.append([InlineKeyboardButton(text='💎 Поддержать через xRocket', url=XROCKET_URL)])
    await message.answer(
        '❤️ Поддержать проект\n\n'
        'Проект существует в том числе на ваши пожертвования. '
        'Если вам нравится бот, вы можете поддержать автора.\n\n'
        'Выберите сумму в Telegram Stars или воспользуйтесь xRocket. '
        'Пожертвование добровольное и не даёт игровых наград.',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=None,
    )


@router.callback_query(F.data.startswith('donate:'))
async def donate_invoice(query):
    match = re.fullmatch(r'donate:(5|15|50|100)', query.data or '')
    if not match or not query.message:
        await query.answer('Эта сумма недоступна. Откройте /donate заново.', show_alert=True)
        return
    amount = int(match[1])
    await query.answer()
    try:
        # XTR uses whole Stars, not cents; exactly one price, no provider token.
        await query.bot.send_invoice(
            chat_id=query.message.chat.id, title='Поддержка проекта',
            description=f'Добровольное пожертвование: {amount} Telegram Stars. Без игровых наград.',
            payload=f'donate:{query.from_user.id}:{amount}', currency='XTR', provider_token='',
            prices=[LabeledPrice(label='Пожертвование', amount=amount)],
        )
    except TelegramAPIError:
        await query.message.answer('Не удалось открыть оплату Stars. Попробуйте /donate позже.', parse_mode=None)


async def donation_pre_checkout(query):
    if valid_payment(query.invoice_payload, query.from_user.id, query.currency, query.total_amount):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message='Неверный счёт или сумма. Откройте /donate и выберите сумму заново.')


async def donation_received(message, container):
    payment = message.successful_payment
    if (not message.from_user or not valid_payment(payment.invoice_payload, message.from_user.id,
                                                   payment.currency, payment.total_amount)):
        logger.error('Donation receipt rejected: invalid payload/currency/amount')
        return
    # Charge ID is the idempotency key. No player/bank/XP writes, ever.
    try:
        await container.mongo_client.database.donations.update_one(
            {'_id': payment.telegram_payment_charge_id},
            {'$setOnInsert': dict(user_id=message.from_user.id, stars=payment.total_amount,
                currency='XTR', invoice_payload=payment.invoice_payload,
                created_at=datetime.now(timezone.utc))}, upsert=True,
        )
    except Exception:
        # Surface the failure rather than falsely confirming persistence.
        # Polling delivery is not a durable retry queue: charge history may need
        # reconciliation against Telegram's getStarTransactions after an outage.
        logger.error('Donation receipt persistence failed; Stars reconciliation required')
        raise
    await message.answer(f'❤️ Спасибо за поддержку — {payment.total_amount} ⭐!\n'
                         'Ваше пожертвование помогает проекту жить.\n'
                         'Вопросы по оплате: /paysupport', parse_mode=None)


class DonationPaymentMiddleware(BaseMiddleware):
    """Handle financial updates before maintenance, moderation and activity XP."""
    def __init__(self, container):
        self.container = container

    async def __call__(self, handler, event, data):
        if isinstance(event, Update):
            if event.pre_checkout_query:
                return await donation_pre_checkout(event.pre_checkout_query)
            message = event.message
            if message and message.successful_payment and message.successful_payment.invoice_payload.startswith('donate:'):
                return await donation_received(message, self.container)
        return await handler(event, data)


@router.message(Command('paysupport'))
async def cmd_paysupport(message, container, command: CommandObject):
    if message.chat.type != 'private':
        await message.answer('По вопросам оплаты напишите /paysupport в личку боту.', parse_mode=None)
        return
    if not command.args:
        await message.answer('Для связи с автором отправьте:\n/paysupport описание проблемы\n\n'
                             'Можно указать номер платежа из квитанции Telegram. '
                             'Не присылайте пароли, коды или данные карты.', parse_mode=None)
        return
    delivered = False
    for admin_id in container.settings.admin_ids:
        try:
            await message.bot.send_message(admin_id,
                f'Вопрос по оплате от пользователя {message.from_user.id}:\n{command.args[:3000]}', parse_mode=None)
            delivered = True
        except TelegramAPIError:
            logger.warning('Payment support delivery failed')
    await message.answer('Обращение передано автору. Спасибо!' if delivered else
                         'Не удалось передать обращение. Попробуйте /paysupport позже.', parse_mode=None)
