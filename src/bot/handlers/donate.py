"""Bank-funded Stars coin purchases and compatible legacy voluntary donations."""
import asyncio
import logging
import re
from datetime import datetime, timezone

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update

from src.services.star_coin_service import StarCoinService, PACKAGES, PREFIX, valid
from src.services.hedgehog_service import GameError

router = Router(name='donate')
logger = logging.getLogger(__name__)
AMOUNTS = (5, 15, 50, 100)
XROCKET_URL = 'https://t.me/xrocket?start=inv_uBCMaE7YvzGJYwF'


def valid_payment(payload, user_id, currency, amount):
    return (currency == 'XTR' and amount in AMOUNTS
            and payload == f'donate:{user_id}:{amount}')


@router.message(Command('donate'))
async def cmd_donate(message, container=None):
    if container is not None:
        try:
            service = StarCoinService(container.mongo_client)
            pending = await service.pending(message.from_user.id)
            if pending:
                await coin_received(message, container, payment=pending)
                return
        except Exception:
            logger.error('Stars coin recovery unavailable')
            await message.answer('Не удалось проверить платежи. Повторите /donate позже или /paysupport.', parse_mode=None)
            return
    buttons = [[InlineKeyboardButton(text=f'⭐ {stars} → {PACKAGES[stars]:,} Coin',
                    callback_data=f'coinbuy:{stars}') for stars in list(PACKAGES)[row:row+2]] for row in (0, 2)]
    buttons.append([InlineKeyboardButton(text='💎 Поддержать через xRocket', url=XROCKET_URL)])
    await message.answer(
        '⭐ SenseiCoin за Telegram Stars\n\n'
        '1 ⭐ → 500 Coin\n5 ⭐ → 3 500 Coin\n10 ⭐ → 8 000 Coin\n50 ⭐ → 45 000 Coin\n\n'
        'Монеты переводятся из SenseiBank после подтверждения оплаты. XP не начисляется.\n'
        'xRocket — отдельное добровольное пожертвование без начисления монет.',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=None)


def safe_payment_error(exc):
    # Never stringify the request (it can contain invoice links/credentials).
    detail = getattr(exc, 'message', type(exc).__name__)
    detail = re.sub(r'https?://\S+|[0-9]{5,}:[A-Za-z0-9_-]+|(?:sk-|vk1\.)\S+', '[REDACTED]', detail)
    return detail[:300]


@router.callback_query(F.data.startswith('coinbuy:'))
async def coin_invoice(query, container):
    match = re.fullmatch(r'coinbuy:(1|5|10|50)', query.data or '')
    if not match or not query.message:
        await query.answer('Откройте /donate заново.', show_alert=True)
        return
    stars = int(match[1])
    stage = 'check'
    try:
        await asyncio.wait_for(StarCoinService(container.mongo_client).check(query.from_user.id, stars), timeout=7)
    except GameError as exc:
        await query.answer(str(exc)[:200], show_alert=True)
        return
    except Exception as exc:
        logger.warning('Stars coin preparation failed stage=%s error=%s', stage, safe_payment_error(exc))
        await query.answer('Не удалось проверить оплату. Повторите /donate позже.', show_alert=True)
        return
    await query.answer()
    stage = 'create_invoice_link'
    try:
        link = await asyncio.wait_for(query.bot.create_invoice_link(title='SenseiCoin из SenseiBank',
            description=f'{stars} Stars → {PACKAGES[stars]} SenseiCoin. Без XP.',
            payload=f'{PREFIX}{query.from_user.id}:{stars}', currency='XTR', provider_token='',
            prices=[LabeledPrice(label='SenseiCoin', amount=stars)]), timeout=8)
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f'Оплатить {stars} ⭐', url=link)]])
        text = (f'⭐ {stars} → {PACKAGES[stars]:,} SenseiCoin\n'
            'После оплаты монеты поступят из SenseiBank. Не оплачивайте счёт повторно.')
        stage = 'publish_invoice'
        if query.message.chat.type in {'group', 'supergroup'}:
            # The group menu is shared, not owned by the payer. Editing it makes
            # it disappear for everyone and lets other users overwrite its bill.
            await query.bot.send_message(chat_id=query.message.chat.id,
                message_thread_id=query.message.message_thread_id,
                text=f'Счёт для {query.from_user.first_name or "участника"} (ID {query.from_user.id})\n'+text,
                reply_markup=markup, parse_mode=None)
        else:
            try:
                await query.message.edit_text(text, reply_markup=markup, parse_mode=None)
            except TelegramBadRequest as exc:
                if 'message is not modified' not in exc.message.lower():
                    # Definitive rejection: no edited message was delivered.
                    # Publish the already-created link, never create another bill.
                    logger.info('Stars coin edit rejected; publishing saved link error=%s', safe_payment_error(exc))
                    await query.bot.send_message(chat_id=query.message.chat.id, text=text,
                        reply_markup=markup, parse_mode=None)
        logger.info('Stars coin invoice ready user=%s stars=%s chat=%s',
                    query.from_user.id, stars, query.message.chat.id)
    except Exception as exc:
        logger.warning('Stars coin invoice failed stage=%s user=%s stars=%s error_type=%s detail=%s',
                       stage, query.from_user.id, stars, type(exc).__name__, safe_payment_error(exc))
        # Do not retry an ambiguous publish. This action itself cannot debit Stars.
        try:
            await query.message.answer(
                'Не удалось показать счёт Stars. Если кнопка оплаты появилась — используйте её один раз. '
                'Иначе откройте /donate в личке бота. Если уже подтвердили платёж — /paysupport, не платите повторно.',
                parse_mode=None)
        except TelegramAPIError:
            logger.warning('Stars coin failure notice unavailable')


async def coin_checkout(query, container):
    try:
        if not valid(query.invoice_payload, query.from_user.id, query.currency, query.total_amount):
            raise GameError('Неверный счёт. Откройте /donate заново.')
        await asyncio.wait_for(StarCoinService(container.mongo_client).check(
            query.from_user.id, query.total_amount), timeout=7)
        await query.answer(ok=True)
    except GameError as exc:
        await query.answer(ok=False, error_message=str(exc)[:200])
    except Exception:
        await query.answer(ok=False, error_message='Оплата временно недоступна.')


async def coin_received(message, container, *, payment=None):
    service = StarCoinService(container.mongo_client)
    try:
        receipt = await service.receive(message.from_user.id, payment or message.successful_payment)
        if receipt['state'] == 'fulfilled':
            await message.answer(f"✅ Платёж учтён: {receipt['stars']} ⭐ → {receipt['coins']:,} SenseiCoin из SenseiBank.\n"
                                 'Повторная обработка квитанции не начисляет монеты снова.', parse_mode=None)
        elif receipt['state'] in {'refund_required', 'refunded'}:
            if receipt['state'] != 'refunded':
                await message.bot.refund_star_payment(user_id=receipt['user_id'],
                    telegram_payment_charge_id=receipt['_id'])
                await service.receipts.update_one({'_id': receipt['_id']}, {'$set': {'state': 'refunded'}})
            await message.answer('Stars возвращены: пакет не выдан, монеты не начислялись.', parse_mode=None)
    except Exception:
        logger.error('Stars coin payment requires reconciliation')
        await message.answer('Платёж требует проверки. Повторите /donate для восстановления или /paysupport. Не оплачивайте повторно.', parse_mode=None)


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
                if event.pre_checkout_query.invoice_payload.startswith('coinbuy:'):
                    return await coin_checkout(event.pre_checkout_query, self.container)
                if event.pre_checkout_query.invoice_payload.startswith('petbuy:'):
                    from src.bot.handlers.paid_hedgehog import pre_checkout
                    return await pre_checkout(event.pre_checkout_query, self.container)
                return await donation_pre_checkout(event.pre_checkout_query)
            message = event.message
            if message and message.successful_payment and message.successful_payment.invoice_payload.startswith('coinbuy:'):
                return await coin_received(message, self.container)
            if message and message.successful_payment and message.successful_payment.invoice_payload.startswith('petbuy:'):
                from src.bot.handlers.paid_hedgehog import successful_payment
                return await successful_payment(message, self.container)
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
