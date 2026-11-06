"""Widget interface for the existing Bot API transport (PNG + real buttons).

Do not pretend that sendDocument or sendPhoto produces messageMediaWidget.
Native HTML export is admin-only until a layer-233 transport is available.
"""
import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, Message,
)

from src.core.container import Container
from src.widgets.cards import Card, profile_card, top_card, to_html, to_png

logger = logging.getLogger(__name__)
router = Router(name='widgets')
# Bound simultaneous Pillow work, even during bursts of callback presses.
_render_slots = asyncio.Semaphore(2)


class WidgetAction(CallbackData, prefix='sw'):
    owner: int
    view: str


def keyboard(owner: int, view: str) -> InlineKeyboardMarkup:
    def button(text, target):
        return InlineKeyboardButton(text=text, callback_data=WidgetAction(owner=owner, view=target).pack())
    return InlineKeyboardMarkup(inline_keyboard=[
        [button('Профиль', 'profile'), button('Рейтинг XP', 'top')],
        [button('↻ Обновить', view)],
    ])


async def load_card(container: Container, user, view: str) -> Card:
    if view == 'top':
        return top_card(await container.user_service.get_top_by_xp(10))
    profile = await container.user_service.get_profile(user.id)
    if profile is None:
        await container.user_service.get_or_create(
            user_id=user.id, username=user.username, first_name=user.first_name or '',
            last_name=user.last_name, is_bot=user.is_bot,
        )
        profile = await container.user_service.get_profile(user.id)
    if profile is None:
        raise RuntimeError('Profile unavailable')
    return profile_card(profile)


def text_fallback(card: Card) -> str:
    return '\n'.join([card.title, card.subtitle, '', *(f'{k}: {v}' for k, v in card.rows)])


async def show_card(message: Message, card: Card, owner: int, view: str, *, edit=False):
    markup = keyboard(owner, view)
    caption = f'{card.title}\nСнимок данных. Для актуальных значений нажмите «Обновить».'
    try:
        async with _render_slots:
            png = await asyncio.to_thread(to_png, card)
        photo = BufferedInputFile(png, filename=f'sensei-{view}.png')
        if edit and message.photo:
            await message.edit_media(InputMediaPhoto(media=photo, caption=caption, parse_mode=None), reply_markup=markup)
        elif edit:
            # A previous render failed: keep this text message editable.
            await message.edit_text(text_fallback(card), parse_mode=None, reply_markup=markup)
        else:
            await message.answer_photo(photo, caption=caption, parse_mode=None, reply_markup=markup)
    except TelegramBadRequest as exc:
        if 'message is not modified' in str(exc).lower():
            return
        logger.warning('Widget image delivery refused; falling back to text', exc_info=True)
        await message.answer(text_fallback(card), parse_mode=None, reply_markup=markup)
    except (OSError, ValueError):
        logger.warning('Widget image rendering failed; falling back to text', exc_info=True)
        await message.answer(text_fallback(card), parse_mode=None, reply_markup=markup)


@router.message(Command('senseiwidget'))
@router.message(F.text == '🧩 Карточки')
async def cmd_widget(message: Message, container: Container):
    if not container.settings.widgets_enabled:
        await message.answer('Карточки отключены. Используйте /mysensei или /senseitop.')
        return
    if not message.from_user:
        return
    try:
        card = await load_card(container, message.from_user, 'profile')
        await show_card(message, card, message.from_user.id, 'profile')
    except Exception:
        logger.exception('Widget profile unavailable')
        await message.answer('Не удалось загрузить карточку. Попробуйте позже или используйте /mysensei.')


@router.callback_query(WidgetAction.filter())
async def widget_callback(query: CallbackQuery, callback_data: WidgetAction, container: Container):
    if not container.settings.widgets_enabled:
        await query.answer('Карточки отключены.', show_alert=True)
        return
    if callback_data.owner != query.from_user.id:
        await query.answer('Это чужая карточка. Откройте свою: /senseiwidget', show_alert=True)
        return
    if callback_data.view not in {'profile', 'top', 'open'} or not isinstance(query.message, Message):
        await query.answer('Карточка недоступна.', show_alert=True)
        return
    # Acknowledge before database access / image generation.
    await query.answer()
    try:
        view = 'profile' if callback_data.view == 'open' else callback_data.view
        card = await load_card(container, query.from_user, view)
        await show_card(query.message, card, query.from_user.id, view, edit=callback_data.view != 'open')
    except Exception:
        logger.exception('Widget refresh failed')
        await query.message.answer('Не удалось обновить карточку. Попробуйте позже.')


@router.message(Command('widgethtml'))
async def export_html(message: Message, container: Container):
    if (not message.from_user or message.chat.type != 'private'
            or message.from_user.id not in container.settings.admin_ids):
        await message.answer('Экспорт доступен администратору только в личном чате.')
        return
    card = await load_card(container, message.from_user, 'profile')
    source = to_html(card)
    await message.answer_document(
        BufferedInputFile(source.encode('utf-8'), filename='sensei-profile.html'),
        caption='Исходник для widget-sandbox (profile 1). Это файл, не нативный виджет Telegram.',
        parse_mode=None,
    )
