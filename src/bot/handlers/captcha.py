"""Капча на входе: кнопка проверки и обновления реакций.

Два входа:
* ``callback_data="captcha:check:<nonce>"`` — игрок нажал «Я поставил»;
* ``MessageReactionUpdated`` — Telegram сам сообщил о реакции.

Как это работает вместе:

* Telegram присылает ``message_reaction`` — записываем увиденную реакцию в
  состояние и, если она правильная, открываем доступ сразу.
* Игрок нажимает «Я поставил» — сравниваем сохранённое с ожидаемым.
* Ничего не пришло — честно просим поставить реакцию и нажать ещё раз.

Проверить реакции сообщения запросом нельзя: в Bot API такого метода нет.
Поэтому единственный источник правды — само обновление от Telegram. Кнопка
существует на случай, когда обновление задержалось или не дошло: она
перечитывает состояние и повторяет сравнение.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, MessageReactionUpdated

from src.bot.presenters.captcha_presenter import CaptchaPresenter
from src.core.container import Container

logger = logging.getLogger(__name__)

router = Router(name="captcha")


async def _grant_access(bot, chat_id: int, message_id: int | None, user_name: str = "сенсей") -> None:
    """Сообщает об успехе и убирает кнопку, чтобы её нельзя было нажать снова."""
    try:
        await bot.edit_message_text(
            text=CaptchaPresenter.render_success(),
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception as exc:
        logger.debug("Unable to edit captcha message after success: %s", exc)

    # Доступ открыт — сразу показываем обычное приветствие, чтобы игрок не
    # остался с пустым экраном после проверки.
    try:
        from src.bot.keyboards.reply import get_main_keyboard
        from src.core.visuals import Visuals

        await bot.send_message(
            chat_id,
            Visuals.start_menu(user_name),
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
    except Exception as exc:
        logger.debug("Unable to send post-captcha menu: %s", exc)


@router.callback_query(F.data.startswith("captcha:check:"))
async def cb_captcha_check(callback: CallbackQuery, container: Container) -> None:
    """Кнопка «Я поставил»: смотрим, видит ли бот нужную реакцию.

    Bot API не умеет запрашивать реакции сообщения, поэтому источник один —
    обновление ``message_reaction``, которое мы сохранили в состояние. Если
    реакции так и не дождались, честно просим поставить её ещё раз, а не
    пускаем вслепую.
    """
    user = callback.from_user
    service = getattr(container, "captcha_service", None)
    if service is None:
        await callback.answer("Проверка временно недоступна", show_alert=True)
        return

    nonce = (callback.data or "").split(":")[-1]
    state = await service.get_state(user.id)

    if state is None:
        await callback.answer("Проверка не найдена. Начни заново.", show_alert=True)
        return
    if state.get("nonce") and state.get("nonce") != nonce:
        # Кнопка от старой попытки: уже выдана новая.
        await callback.answer("Эта проверка устарела. Возьми новую.", show_alert=True)
        return
    if state.get("status") == "passed":
        await callback.answer("Уже пройдено ✅")
        return

    expected = state.get("reaction")
    seen = state.get("seen_reactions") or []
    seen_message = state.get("seen_message_id")
    same_message = seen_message is None or seen_message == state.get("message_id")

    if expected and expected in seen and same_message:
        await service.mark_passed(user.id)
        await callback.answer("Проверка пройдена ✅")
        await _grant_access(
            callback.bot, callback.message.chat.id,
            state.get("message_id"), user.first_name or "сенсей",
        )
        return

    result = await service.verify(user.id)
    reason = result.get("reason")

    if reason == "expired":
        await callback.answer("Время вышло", show_alert=True)
        await _replace_with_expired(callback, container)
        return
    if reason == "too_many":
        await callback.answer("Слишком много попыток", show_alert=True)
        await _replace_with_blocked(callback)
        return

    left = int(result.get("attempts_left") or 0)
    await callback.answer("Не вижу нужную реакцию", show_alert=True)
    try:
        await callback.bot.edit_message_text(
            text=CaptchaPresenter.render_wrong_reaction(left),
            chat_id=callback.message.chat.id,
            message_id=state.get("message_id") or callback.message.message_id,
            parse_mode="HTML",
            reply_markup=CaptchaPresenter.keyboard(expected, nonce),
        )
    except Exception as exc:
        logger.debug("Unable to update captcha message: %s", exc)




async def _replace_with_expired(callback: CallbackQuery, container: Container) -> None:
    try:
        await callback.bot.edit_message_text(
            text=CaptchaPresenter.render_expired(),
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            parse_mode="HTML",
            reply_markup=CaptchaPresenter.retry_keyboard(),
        )
    except Exception:
        pass


async def _replace_with_blocked(callback: CallbackQuery) -> None:
    try:
        await callback.bot.edit_message_text(
            text=CaptchaPresenter.render_too_many(),
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            parse_mode="HTML",
            reply_markup=CaptchaPresenter.retry_keyboard(),
        )
    except Exception:
        pass


@router.callback_query(F.data == "captcha:restart")
async def cb_captcha_restart(callback: CallbackQuery, container: Container) -> None:
    """Новая попытка после истечения или после исчерпания промахов."""
    user = callback.from_user
    service = getattr(container, "captcha_service", None)
    if service is None:
        await callback.answer("Проверка временно недоступна", show_alert=True)
        return

    state = await service.issue(user.id)
    text = CaptchaPresenter.render_request(state["reaction"], user.first_name or "друг")
    try:
        await callback.bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            parse_mode="HTML",
            reply_markup=CaptchaPresenter.keyboard(state["reaction"], state["nonce"]),
        )
        await service.attach_message(user.id, callback.message.message_id)
    except Exception as exc:
        logger.debug("Unable to restart captcha: %s", exc)
    await callback.answer("Новая проверка выдана")


@router.message_reaction()
async def on_reaction(event: MessageReactionUpdated, container: Container) -> None:
    """Обновление реакции: если она правильная, открываем доступ сразу.

    Работает там, где Telegram вообще доставляет ``message_reaction``.
    Ошибки игнорируем: основной путь — кнопка, и она никуда не делась.
    """
    service = getattr(container, "captcha_service", None)
    user = event.user
    if service is None or user is None or user.is_bot:
        return

    state = await service.get_state(user.id)
    if state is None or state.get("status") == "passed":
        return

    # Запоминаем увиденное: кнопка потом прочитает именно это, потому что
    # Bot API не даёт запросить реакции сообщения напрямую.
    await service.record_reaction(user.id, event.message_id, event.new_reaction)

    result = await service.verify(
        user.id,
        new_reactions=event.new_reaction,
        message_id=event.message_id,
    )
    if result.get("ok"):
        logger.info("Captcha passed via reaction update: user=%s", user.id)
        await _grant_access(
            event.bot,
            event.chat.id,
            state.get("message_id") or event.message_id,
            user.first_name or "сенсей",
        )
