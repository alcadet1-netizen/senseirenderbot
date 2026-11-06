"""Widget interface for the existing Bot API transport (GIF/PNG + real buttons).

Do not pretend that sendDocument or sendPhoto produces messageMediaWidget.
Native HTML export is admin-only until a layer-233 transport is available.
"""
import asyncio
import logging
from dataclasses import replace

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaAnimation, InputMediaPhoto, Message,
)

from src.core.container import Container
from src.widgets.cards import Card, profile_card, top_card, to_html, to_png
from src.widgets.animation import to_gif

logger = logging.getLogger(__name__)
router = Router(name='widgets')
# Bound simultaneous Pillow work, even during bursts of callback presses.
_render_slots = asyncio.Semaphore(2)


class WidgetAction(CallbackData, prefix='sw'):
    owner: int
    view: str


def decode_view(value: str, default_motion: bool = True) -> tuple[str, str, bool]:
    """Accept old callback links; new ones carry palette and motion per message."""
    if value in {'profile', 'top', 'open'}:
        return ('profile' if value == 'open' else value, 'dark', default_motion)
    parts = value.split('.')
    if len(parts) != 3 or parts[0] not in {'profile', 'top'} or parts[1] not in {'d', 'l'} or parts[2] not in {'a', 's'}:
        raise ValueError('Unknown widget view')
    return parts[0], ('dark' if parts[1] == 'd' else 'light'), parts[2] == 'a'


def keyboard(owner: int, view: str, *, theme='dark', animate=False, allow_animation=True) -> InlineKeyboardMarkup:
    def button(text, target, palette=theme, motion=animate):
        state = f'{target}.{palette[0]}.{"a" if motion else "s"}'
        return InlineKeyboardButton(text=text, callback_data=WidgetAction(owner=owner, view=state).pack())
    controls = [button('☀ Светлая' if theme == 'dark' else '☾ Тёмная', view,
                       palette='light' if theme == 'dark' else 'dark')]
    if allow_animation:
        controls.append(button('Ⅱ Без движения' if animate else '▷ Анимация', view, motion=not animate))
    return InlineKeyboardMarkup(inline_keyboard=[
        [button('● Профиль' if view == 'profile' else 'Профиль', 'profile'),
         button('● Рейтинг XP' if view == 'top' else 'Рейтинг XP', 'top')],
        controls,
        [button('↻ Обновить', view)],
    ])


# Only one refresh may own a message. Entries disappear even on cancellation.
_inflight: set[tuple[int, int]] = set()


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
    lines = [card.title, card.subtitle, '', *(f'{k}: {v}' for k, v in card.rows)]
    if card.progress is not None:
        lines.append(f'Прогресс уровня: {card.progress}%')
    if card.art:
        lines.append(card.art)
    return '\n'.join(lines)


async def show_card(message: Message, card: Card, owner: int, view: str, *, edit=False, animate=False, allow_animation=True):
    markup = keyboard(owner, view, theme=card.theme, animate=animate, allow_animation=allow_animation)
    caption = f'{card.title}\nСнимок данных. Для актуальных значений нажмите «Обновить».'
    has_media = bool(getattr(message, 'photo', None) or getattr(message, 'animation', None))
    if edit and not has_media:
        # Text fallback must stay editable; never call edit_text on an animation.
        try:
            await message.edit_text(text_fallback(card), parse_mode=None, reply_markup=markup)
        except TelegramBadRequest as exc:
            if 'message is not modified' not in str(exc).lower():
                await message.answer(text_fallback(card), parse_mode=None, reply_markup=markup)
        return
    if animate:
        try:
            async with _render_slots:
                gif = await asyncio.to_thread(to_gif, card)
            animation = BufferedInputFile(gif, filename=f'sensei-{view}.gif')
            if edit:
                await message.edit_media(
                    InputMediaAnimation(media=animation, caption=caption, parse_mode=None), reply_markup=markup,
                )
            else:
                await message.answer_animation(animation, caption=caption, parse_mode=None, reply_markup=markup)
            return
        except TelegramBadRequest as exc:
            if 'message is not modified' in str(exc).lower():
                return
            logger.warning('Widget animation refused; trying PNG', exc_info=True)
        except (OSError, ValueError):
            logger.warning('Widget animation rendering failed; trying PNG', exc_info=True)
    try:
        async with _render_slots:
            png = await asyncio.to_thread(to_png, card)
        photo = BufferedInputFile(png, filename=f'sensei-{view}.png')
        if edit:
            await message.edit_media(InputMediaPhoto(media=photo, caption=caption, parse_mode=None), reply_markup=markup)
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
        await show_card(message, card, message.from_user.id, 'profile',
                        animate=container.settings.widget_animations_enabled,
                        allow_animation=container.settings.widget_animations_enabled)
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
    if not isinstance(getattr(query, "message", None), Message):
        await query.answer('Карточка недоступна.', show_alert=True)
        return
    try:
        view, theme, animate = decode_view(callback_data.view, container.settings.widget_animations_enabled)
    except ValueError:
        await query.answer('Карточка недоступна.', show_alert=True)
        return
    key = (getattr(getattr(query.message, 'chat', None), 'id', 0),
           getattr(query.message, 'message_id', 0))
    if key in _inflight:
        await query.answer('Карточка уже обновляется. Подождите немного.')
        return
    _inflight.add(key)
    try:
        await query.answer()
        card = replace(await load_card(container, query.from_user, view), theme=theme)
        await show_card(query.message, card, query.from_user.id, view, edit=callback_data.view != 'open',
                        animate=animate and container.settings.widget_animations_enabled,
                        allow_animation=container.settings.widget_animations_enabled)
    except Exception:
        logger.exception('Widget refresh failed')
        await query.message.answer('Не удалось обновить карточку. Попробуйте позже.')
    finally:
        _inflight.discard(key)


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
