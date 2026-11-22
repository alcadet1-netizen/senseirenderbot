"""Вид капчи: текст запроса, клавиатура и ответы на попытки."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.visuals import Visuals


class CaptchaPresenter:
    """Тексты и клавиатура для капчи на входе."""

    WIDTH = 32

    @staticmethod
    def render_request(reaction: str, name: str = "друг") -> str:
        """Просит поставить конкретную реакцию на это сообщение."""
        w = CaptchaPresenter.WIDTH
        safe_name = str(name or "друг")[:24]
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🛡 ПРОВЕРКА НА ЧЕЛОВЕКА", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"Привет, {safe_name}!", w),
            Visuals.frame_line_left("Прежде чем пустить в бота,", w),
            Visuals.frame_line_left("докажи, что ты живой человек.", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Поставь реакцию", w),
            Visuals.frame_line_left(f"{reaction}   {reaction}   {reaction}", w, "center"),
            Visuals.frame_line_left("на это сообщение:", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("1. Удерживай это сообщение", w),
            Visuals.frame_line_left("2. Выбери нужный эмодзи", w),
            Visuals.frame_line_left("3. Нажми «Я поставил»", w),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def keyboard(reaction: str, nonce: str) -> InlineKeyboardMarkup:
        """Кнопка проверки. Nonce привязывает кнопку к конкретной попытке."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Я поставил реакцию",
                callback_data=f"captcha:check:{nonce}",
            )],
        ])

    @staticmethod
    def render_success() -> str:
        w = CaptchaPresenter.WIDTH
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("✅ ДОСТУП ОТКРЫТ", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Проверка пройдена.", w),
            Visuals.frame_line_left("Добро пожаловать, сенсей.", w),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def render_wrong_reaction(attempts_left: int) -> str:
        w = CaptchaPresenter.WIDTH
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("❌ РЕАКЦИИ НЕТ", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Я не вижу нужную реакцию.", w),
            Visuals.frame_line_left("Поставь её на сообщение выше", w),
            Visuals.frame_line_left("и нажми кнопку снова.", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"Осталось попыток: {attempts_left}", w),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def render_expired() -> str:
        w = CaptchaPresenter.WIDTH
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("⏳ ПРОВЕРКА ИСТЕКЛА", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Слишком долго.", w),
            Visuals.frame_line_left("Нажми кнопку ниже —", w),
            Visuals.frame_line_left("я дам новую реакцию.", w),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def render_too_many() -> str:
        w = CaptchaPresenter.WIDTH
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🚫 СЛИШКОМ МНОГО ПОПЫТОК", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Проверка не пройдена.", w),
            Visuals.frame_line_left("Нажми кнопку ниже,", w),
            Visuals.frame_line_left("чтобы начать заново.", w),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def retry_keyboard() -> InlineKeyboardMarkup:
        """Кнопка новой попытки: нужна после истечения и после промахов."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать проверку заново", callback_data="captcha:restart")],
        ])
