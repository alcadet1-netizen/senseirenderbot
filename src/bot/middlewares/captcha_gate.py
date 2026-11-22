"""Гейт капчи для личных сообщений.

Первый заход нового игрока в личку бота перехватывается здесь: вместо
обычного обработчика он получает запрос «поставь реакцию». Пока капча не
пройдена, до команд дело не доходит — иначе смысл проверки терялся бы.

Что пропускается всегда:
* групповые чаты (капча — только про личку);
* администраторы из ``settings.admin_ids``;
* само прохождение: кнопка проверки, ``/start``, команда повтора;
* обычные сообщения, когда проверка уже пройдена или сервис недоступен.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from src.bot.presenters.captcha_presenter import CaptchaPresenter
from src.core.config import settings
from src.core.container import Container

logger = logging.getLogger(__name__)

# Команды, которые не открывают доступ, но нужны, чтобы не запереть игрока.
# Список должен совпадать с реально существующими хендлерами: команда из
# этого списка без хендлера молча провалилась бы, и игрок остался бы ни с чем.
ALLOWED_COMMANDS = ("/start", "/captcha")


def _command_of(message: Message) -> str:
    text = (message.text or "").strip()
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@")[0].lower()


class CaptchaGateMiddleware(BaseMiddleware):
    """Не пускает в личку бота, пока не пройдена капча."""

    def __init__(self, container: Container):
        self.container = container

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        container = self.container

        # Кнопки капчи обрабатываются своими хендлерами: здесь мы их только
        # пропускаем, проверку делает обработчик колбэка.
        if isinstance(event, CallbackQuery):
            return await handler(event, data)

        if not isinstance(event, Message):
            return await handler(event, data)

        message: Message = event

        # Капча — только личка. В группах игрок уже подтвердил себя речью.
        if message.chat.type != "private":
            return await handler(event, data)

        user = message.from_user
        if user is None or user.is_bot:
            return await handler(event, data)

        if user.id in settings.admin_ids:
            return await handler(event, data)

        service = getattr(container, "captcha_service", None)
        if service is None:
            return await handler(event, data)

        try:
            passed = await service.is_passed(user.id)
        except Exception as exc:
            # База недоступна — не запираем живых игроков.
            logger.warning("Captcha check failed for %s: %s", user.id, exc)
            return await handler(event, data)

        if passed:
            return await handler(event, data)

        command = _command_of(message)
        if command and command not in ALLOWED_COMMANDS:
            # Команда до прохождения капчи не выполняется: иначе игрок просто
            # обойдёт проверку, вызвав /daily вместо капчи.
            await self._send_challenge(message, service, retry=True, data=data)
            return None

        if command:
            # /start и /help доходят до своих хендлеров: /start сам показывает
            # капчу, /help объясняет, что происходит.
            return await handler(event, data)

        # Любое прочее сообщение непроверенного игрока тоже упирается в капчу:
        # иначе он просто написал бы «привет» и получил доступ к триггерам.
        await self._send_challenge(message, service, retry=True, data=data)
        return None

    async def _send_challenge(
        self, message: Message, service, retry: bool = False, data: Dict[str, Any] | None = None
    ) -> None:
        """Показывает капчу, переиспользуя уже выданную попытку.

        Если у игрока есть действующая капча, показываем ту же реакцию, а не
        выдаём новую. Иначе каждое новое сообщение меняло ожидаемый эмодзи и
        обесценивало кнопку на предыдущем: человек ставил одну реакцию, а
        проверялась уже другая.
        """
        user = message.from_user
        try:
            state = await service.issue(user.id, keep_active=True)
        except Exception as exc:
            logger.error("Unable to issue captcha for %s: %s", user.id, exc)
            return

        reaction = state["reaction"]
        text = CaptchaPresenter.render_request(reaction, user.first_name or "друг")

        if retry:
            text += "\n\n<i>Доступ к боту откроется после проверки.</i>"

        try:
            # Если капча уже висит в переписке, не заваливаем чат копиями:
            # правим прошлое сообщение, чтобы у игрока был один актуальный
            # запрос и одна рабочая кнопка.
            bot = data.get("bot") or message.bot
            previous = state.get("message_id")
            if previous and state.get("status") == "pending" and bot is not None:
                try:
                    await bot.edit_message_text(
                        text=text,
                        chat_id=message.chat.id,
                        message_id=int(previous),
                        parse_mode="HTML",
                        reply_markup=CaptchaPresenter.keyboard(reaction, state["nonce"]),
                    )
                    return
                except Exception:
                    # Сообщение могли удалить — тогда отправим новое ниже.
                    pass

            sent = await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=CaptchaPresenter.keyboard(reaction, state["nonce"]),
            )
            await service.attach_message(user.id, sent.message_id)
        except Exception as exc:
            logger.warning("Unable to send captcha to %s: %s", user.id, exc)
