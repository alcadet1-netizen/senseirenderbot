from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultPhoto, InlineQueryResultArticle, InputTextMessageContent, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import html
import secrets
from src.core.visuals import Visuals
from PIL import Image, ImageDraw, ImageFont

class SenseiCheckPresenter:
    """Presenter for Sensei Check (Wizard & Inline)."""


    @classmethod
    def render_checked_announcement(cls, amount: float, message_text: str = None, remaining: int = None, referral_percent: int | None = None) -> str:
        """Красивое объявление для чека (Clean Style)."""
        lines = [
            "🎁 <b>SENSEI CHECK</b>",
            "",
            f"💰 <b>{amount} GRAM</b>",
        ]

        if remaining is not None:
            lines.append(f"{Visuals.fire()} Осталось активаций: <b>{remaining}</b>")

        if referral_percent is not None and referral_percent > 0:
            lines.append(f"🤝 Реферальный бонус: <b>{referral_percent}%</b>")

        if message_text:
            lines.append("")
            lines.append(f"💬 <i>{html.escape(message_text)}</i>")

        lines.append("")
        lines.append("👇 <b>Нажми кнопку ниже, чтобы забрать!</b>")

        return "\n".join(lines)

    @classmethod
    def get_activation_keyboard(cls, url: str, amount: float) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 ЗАБРАТЬ {amount} GRAM", url=url)]
        ])

    @classmethod
    def build_inline_results(cls, view: dict, amount: float, url: str) -> list:
        remaining = None
        if "activation_limit" in view and "activations_used" in view:
             remaining = max(0, int(view["activation_limit"]) - int(view["activations_used"]))

        # Render clean caption
        caption = cls.render_checked_announcement(amount, view.get("message_text"), remaining, view.get("referral_percent"))
        kb = cls.get_activation_keyboard(url, amount)
        results = []

        # Add "Share" option via Article
        results.append(
            InlineQueryResultArticle(
                id=secrets.token_hex(4),
                title=f"🎁 Чек на {amount} GRAM",
                description=f"{Visuals.fire_raw()} Осталось: {remaining} • Реф: {view.get('referral_percent', 0)}%",
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML"
                ),
                reply_markup=kb,
                thumbnail_url="https://emojigraph.org/media/apple/money-bag_1f4b0.png", # Optional: neat icon
            )
        )
        return results

    @classmethod
    def render_fast_confirm(cls, amount: str, count: int) -> str:
        """Быстрое создание чека."""
        try:
            total = float(amount) * count
        except:
            total = 0

        return (
            "⚡ <b>БЫСТРОЕ СОЗДАНИЕ ЧЕКА</b>\n\n"
            f"💰 Сумма: <b>{amount} GRAM</b>\n"
            f"👥 Активаций: <b>{count}</b>\n"
            f"💳 Итого к оплате: <b>{total:.4f} GRAM</b>\n\n"
            "👇 Нажми <b>Создать</b> для подтверждения."
        )

    @classmethod
    def fast_confirm_kb(cls) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Создать", callback_data="scheckadm:create")
        builder.button(text="⚙️ Настройки", callback_data="scheckadm:edit:settings") # Goes to dashboard
        builder.button(text=f"{Visuals.cross_raw()} Отмена", callback_data="scheckadm:cancel")
        builder.adjust(1)
        return builder.as_markup()

    @classmethod
    def render_share(cls, amount: float, remaining: int, ref_link: str, referral_percent: int | None = None) -> str:
        """Красивая карточка для шаринга реферальной ссылки (Clean)."""
        lines = [
            "🎁 <b>ПОДЕЛИСЬ И ЗАРАБОТАЙ</b>",
            "",
            f"💰 <b>{amount} GRAM</b> за каждого приглашенного",
            f"{Visuals.fire()} Осталось чеков: <b>{remaining}</b>",
        ]

        if referral_percent and referral_percent > 0:
            lines.append(f"💸 Твой бонус: <b>{referral_percent}%</b>")

        lines.append("")
        lines.append(f"🔗 <b>Твоя ссылка:</b>\n<code>{ref_link}</code>")
        lines.append("")
        lines.append("👆 Нажми кнопку ниже, чтобы отправить друзьям!")

        return "\n".join(lines)


    @classmethod
    def share_kb(cls, code: str, ref_link: str) -> InlineKeyboardMarkup:
        """Клавиатура для максимально быстрого шаринга."""
        builder = InlineKeyboardBuilder()

        # Прямая ссылка - самый быстрый способ активации
        builder.button(
            text="💰 ОТКРЫТЬ И ЗАБРАТЬ",
            url=ref_link
        )

        # Вставить как медиа в чат
        builder.button(
            text="📎 В ЧАТЕ",
            switch_inline_query_current_chat=code
        )

        builder.adjust(1, 1)
        return builder.as_markup()

    @classmethod
    def share_direct_kb(cls, ref_link: str, code: str) -> InlineKeyboardMarkup:
        """Премиум клавиатура для шаринга с максимальным удобством"""
        builder = InlineKeyboardBuilder()

        # Основное действие - забрать чек
        builder.button(text="💰 ЗАБРАТЬ ЧЕК", url=ref_link)

        # Вставить в чат
        builder.button(text="📎 ПОДЕЛИТЬСЯ В ЧАТЕ", switch_inline_query_current_chat=code)

        # Скопировать ссылку
        builder.button(text="📋 СКОПИРОВАТЬ ССЫЛКУ", callback_data=f"scheck:copy:{code}")

        builder.adjust(1)
        return builder.as_markup()

    @classmethod
    def profiles_kb(cls) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="🟢 Без подписки • Без пароля • Реф 0%", callback_data="scheckadm:applyprof:a")
        builder.button(text="🔵 @SenseiDurova • Без пароля • Реф 25%", callback_data="scheckadm:applyprof:b")
        builder.button(text="🟣 @SenseiDurova • Пароль • Реф 50%", callback_data="scheckadm:applyprof:c")
        builder.adjust(1)
        nav = cls.nav_kb(back="scheckadm:back:dashboard")
        return InlineKeyboardMarkup(inline_keyboard=builder.export() + nav.inline_keyboard)

    @classmethod
    def render_profiles_prompt(cls) -> str:
        return "⚙️ <b>Профили чека</b>\nВыбери преднастройку."

    @classmethod
    def build_promo_banner(cls, amount: float, remaining: int, is_referral: bool = False, referrer_username: str | None = None) -> BufferedInputFile:
        """Создает красивый баннер для чека или реф-ссылки."""
        W, H = 1024, 512

        # Выбираем цвета в зависимости от типа
        if is_referral:
            bg_color = (25, 45, 85)  # Синий для реф
            accent_color = (100, 200, 255)
            button_color = (0, 180, 255)
            title_text = "🎁 ЗАРАБОТАЙ НА ЧЕКЕ 🎁" if not referrer_username else f"🎁 {referrer_username} ЗОВЕТ 🎁"
        else:
            bg_color = (20, 20, 24)  # Темный для обычного чека
            accent_color = (200, 220, 255)
            button_color = (0, 140, 255)
            title_text = "🎁 SENSEI CHECK"

        img = Image.new("RGB", (W, H), color=bg_color)
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 72 if not is_referral else 60)
            font_text = ImageFont.truetype("arial.ttf", 48)
            font_sub = ImageFont.truetype("arial.ttf", 36)
            font_btn = ImageFont.truetype("arial.ttf", 52)
        except Exception:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_btn = ImageFont.load_default()

        # Title
        draw.text((60, 30), title_text, font=font_title, fill=(255, 255, 255))

        # Main amount
        draw.text((60, 140), f"💰 {amount} GRAM", font=font_text, fill=accent_color)

        if is_referral and remaining > 0:
            draw.text((60, 200), f"{Visuals.fire_raw()} {remaining} осталось", font=font_sub, fill=(255, 200, 100))
        elif remaining > 0:
            draw.text((60, 200), f"Осталось: {remaining}", font=font_text, fill=accent_color)

        # Button
        btn_x, btn_y, btn_w, btn_h = 60, 320, 900, 120
        draw.rounded_rectangle(
            (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
            radius=20,
            fill=button_color
        )

        if is_referral:
            btn_text = "💸 ЗАРАБАТЫВАЙ"
        else:
            btn_text = "💰 ЗАБРАТЬ"

        # Пытаемся центрировать текст кнопки
        text_bbox = draw.textbbox((0, 0), btn_text, font=font_btn)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = btn_x + (btn_w - text_width) // 2
        text_y = btn_y + (btn_h - 50) // 2
        draw.text((text_x, text_y), btn_text, font=font_btn, fill=(255, 255, 255))

        from io import BytesIO
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return BufferedInputFile(bio.getvalue(), filename="check_banner.png")

    @classmethod
    def nav_kb(cls, *, back: str | None = None, skip: str | None = None, cancel: str = "scheckadm:cancel") -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if back:
            rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back)])
        if skip:
            rows.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip)])
        rows.append([InlineKeyboardButton(text=f"{Visuals.cross_raw()} Отмена", callback_data=cancel)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @classmethod
    def amount_kb(cls) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        presets = ["0.001", "0.01", "0.05", "0.1", "0.5", "1", "5", "10"]
        for p in presets:
            builder.button(text=f"{p} GRAM", callback_data=f"scheckadm:amt:{p}")
        builder.adjust(4)

        nav = cls.nav_kb(back="scheckadm:back:dashboard", cancel="scheckadm:cancel")
        return InlineKeyboardMarkup(inline_keyboard=builder.export() + nav.inline_keyboard)

    @classmethod
    def activations_kb(cls) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        presets = ["1", "5", "10", "50", "100", "500", "1000", "5000"]
        for p in presets:
            builder.button(text=p, callback_data=f"scheckadm:act:{p}")
        builder.adjust(4)

        nav = cls.nav_kb(back="scheckadm:back:dashboard")
        return InlineKeyboardMarkup(inline_keyboard=builder.export() + nav.inline_keyboard)

    @classmethod
    def password_kb(cls) -> InlineKeyboardMarkup:
        """Старая версия - совместимость. Используй password_input_kb()"""
        return cls.password_input_kb()

    @classmethod
    def channels_kb(cls, channels: list[str]) -> InlineKeyboardMarkup:
        """Клавиатура управления каналами."""
        rows: list[list[InlineKeyboardButton]] = []
        if channels:
            for idx, ch in enumerate(channels[:15]):
                rows.append([InlineKeyboardButton(text=f"{Visuals.cross_raw()} {ch}", callback_data=f"scheckadm:chdel:{idx}")])
            if len(channels) > 15:
                rows.append([InlineKeyboardButton(text=f"… ещё {len(channels) - 15}", callback_data="scheckadm:noop")])

        nav_row = []
        nav_row.append(InlineKeyboardButton(text="🧹 Очистить", callback_data="scheckadm:chclear"))
        nav_row.append(InlineKeyboardButton(text="✅ Готово", callback_data="scheckadm:chnext"))
        rows.append(nav_row)

        return InlineKeyboardMarkup(inline_keyboard=rows)

    @classmethod
    def referral_kb(cls) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for pct in (0, 25, 50, 75, 100):
            title = "🚫 Без реф" if pct == 0 else f"{pct}%"
            builder.button(text=title, callback_data=f"scheckadm:ref:{pct}")
        builder.adjust(3, 2)

        nav = cls.nav_kb(back="scheckadm:back:dashboard")
        return InlineKeyboardMarkup(inline_keyboard=builder.export() + nav.inline_keyboard)

    @classmethod
    def dashboard_kb(cls, data: dict) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        amount = data.get("amount_ton") or "?"
        limit = data.get("activation_limit") or "?"

        builder.button(text=f"💰 {amount} GRAM", callback_data="scheckadm:edit:amount")
        builder.button(text=f"👥 {limit} шт.", callback_data="scheckadm:edit:activations")

        channels = data.get("channels") or []
        ch_text = f"📢 Каналы ({len(channels)})" if channels else "📢 Каналы"
        builder.button(text=ch_text, callback_data="scheckadm:edit:channels")

        password = data.get("password")
        pwd_text = "🔒 Пароль ✅" if password else "🔒 Пароль"
        builder.button(text=pwd_text, callback_data="scheckadm:edit:password")

        has_content = data.get("message_text") or data.get("photo_file_id")
        cont_text = "🖼 Медиа ✅" if has_content else "🖼 Медиа"
        builder.button(text=cont_text, callback_data="scheckadm:edit:text")

        ref = data.get("referral_percent") or 0
        ref_text = f"🤝 Реф: {ref}%"
        builder.button(text=ref_text, callback_data="scheckadm:edit:referral")

        req_cpt = data.get("requires_captcha")
        cpt_text = "🛡 Капча ✅" if req_cpt else "🛡 Капча ❌"
        builder.button(text=cpt_text, callback_data="scheckadm:edit:captcha")

        builder.adjust(2, 2, 2, 1)

        builder.button(text="⚙️ Профили", callback_data="scheckadm:profiles")
        builder.adjust(1)

        presets = InlineKeyboardBuilder()
        presets.button(text="0.1×10", callback_data="scheckadm:preset:0.1:10")
        presets.button(text="0.5×100", callback_data="scheckadm:preset:0.5:100")
        presets.button(text="1×100", callback_data="scheckadm:preset:1:100")
        presets.adjust(3)

        nav = InlineKeyboardBuilder()
        nav.button(text="✅ Создать чек", callback_data="scheckadm:create")
        nav.button(text=f"{Visuals.cross_raw()} Отмена", callback_data="scheckadm:cancel")
        nav.adjust(1)

        return InlineKeyboardMarkup(inline_keyboard=builder.export() + presets.export() + nav.export())

    @classmethod
    def render_activations_prompt(cls) -> str:
        return (
            "📌 <b>SenseiCheck</b>\n\n"
            "👥 <b>Количество активаций</b>\n"
            "Сколько человек смогут активировать чек?"
        )

    @classmethod
    def render_amount_prompt(cls) -> str:
        return (
            "📌 <b>SenseiCheck</b>\n\n"
            "💰 <b>Сумма одного чека</b>\n"
            "Введи сумму в GRAM (например, <code>0.1</code>) или выбери из списка:"
        )

    @classmethod
    def render_channels_status(cls, channels: list[str]) -> str:
        pretty = "каналы не добавлены" if not channels else "\n".join([f"• <code>{c}</code>" for c in channels])
        return (
            "📣 <b>Подписка на каналы</b>\n\n"
            f"Текущие каналы:\n{pretty}\n\n"
            "Пришлите юзернеймы/ID каналов или перешлите сообщение, чтобы добавить каналы.\n"
            "<i>(Или выберите действие на клавиатуре)</i>"
        )

    @classmethod
    def render_admin_password_prompt(cls) -> str:
        return (
            "🔒 <b>Пароль для чека</b>\n\n"
            "Пришлите текст, который станет паролем: любое слово, фразу или набор цифр.\n"
            "<i>Или нажмите «Сгенерировать», чтобы создать случайный пароль.</i>"
        )

    @classmethod
    def render_user_password_prompt(cls) -> str:
        return (
            "🔒 <b>Чек защищён паролем</b>\n\n"
            "Пожалуйста, отправьте пароль ответным сообщением, чтобы забрать награду."
        )

    @classmethod
    def password_input_kb(cls) -> InlineKeyboardMarkup:
        """Клавиатура для ввода пароля с опциями"""
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Сгенерировать пароль", callback_data="scheckadm:pwd:gen")
        builder.button(text="⏭️ Пропустить пароль", callback_data="scheckadm:skip:password")
        builder.adjust(1)

        # Добавляем кнопку "Назад" для навигации
        nav = cls.nav_kb(back="scheckadm:back:dashboard", skip=None)
        return InlineKeyboardMarkup(inline_keyboard=builder.export() + nav.inline_keyboard)

    @classmethod
    def render_text_prompt(cls) -> str:
        return (
            "💬 <b>Сообщение к чеку</b>\n\n"
            "Пришлите текст, который будет показан пользователям вместе с чеком.\n"
            "<i>Чтобы пропустить, нажмите соответствующую кнопку.</i>"
        )

    @classmethod
    def render_photo_prompt(cls) -> str:
        return (
            "🖼 <b>Медиа к чеку</b>\n\n"
            "Пришлите фото или видео, которое украсит ваш чек.\n"
            "<i>Чтобы пропустить этот шаг, нажмите кнопку ниже.</i>"
        )

    @classmethod
    def render_referral_prompt(cls) -> str:
        return (
            "🤝 <b>Реферальная система</b>\n\n"
            "Выберите, какой процент от чека получит пригласивший пользователя рефовод."
        )

    @classmethod
    def render_dashboard(cls, data: dict) -> str:
        amount = data.get("amount_ton", "?")
        limit = data.get("activation_limit", "?")
        channels = data.get("channels") or []
        password = data.get("password")

        content_txt = "Отсутствует"
        if data.get("message_text") or data.get("photo_file_id") or data.get("video_file_id"):
            content_txt = "Добавлено ✅"

        ref_pct = data.get("referral_percent", 0)

        total = "?"
        try:
             total = f"{float(amount) * int(limit):.4f}"
        except:
             pass

        pwd_display = f"<code>{password}</code> ✅" if password else "Не установлен"
        ch_display = f"{len(channels)} ✅" if channels else "Нет"
        cpt_display = "✅ Включена" if data.get("requires_captcha") else "❌ Отключена"

        return (
            f"⚡️ <b>СОЗДАНИЕ ЧЕКА</b>\n\n"
            f"💰 <b>Сумма 1 активации:</b> {amount} GRAM\n"
            f"👥 <b>Количество активаций:</b> {limit}\n\n"
            f"⚙️ <b>НАСТРОЙКИ:</b>\n"
            f"├ 📣 <b>Каналы:</b> {ch_display}\n"
            f"├ 🔒 <b>Пароль:</b> {pwd_display}\n"
            f"├ 🛡 <b>Капча:</b> {cpt_display}\n"
            f"├ 🤝 <b>Реферальные:</b> {ref_pct}%\n"
            f"└ 💬 <b>Медиа и текст:</b> {content_txt}\n\n"
            f"💎 <b>ИТОГО: {total} GRAM</b>\n\n"
            f"<i>Настройте чек с помощью кнопок или сразу жмите «Создать».</i>"
        )
    # ==================== ULTIMATE МЕНЮ ====================

    @classmethod
    def render_main_menu(cls) -> str:
        """Главное меню управления чеками"""
        w = 35
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🎯 SENSEI CHECK ULTIMATE", w, align="center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left("📋 Управление чеками", w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left("1️⃣  Создать новый чек", w),
            Visuals.frame_line_left("2️⃣  Список всех чеков", w),
            Visuals.frame_line_left("3️⃣  Мои реферальные ссылки", w),
            Visuals.frame_line_left("", w),
            Visuals.frame_bottom_left(w),
        ]
        return Visuals._render_block(lines)

    @classmethod
    def render_checks_list(cls, checks: list, offset: int = 0, limit: int = 5) -> str:
        """Список всех чеков с пагинацией"""
        w = 40
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("📋 ВСЕ ЧЕКИ", w, align="center"),
            Visuals.frame_separator_left(w),
        ]

        # Handle case where checks is not a list (e.g., if it's an integer due to bug)
        if not isinstance(checks, list):
            checks = []

        if not checks:
            lines.append(Visuals.frame_line_left("Нет чеков", w, align="center"))
            lines.append(Visuals.frame_bottom_left(w))
            return Visuals._render_block(lines)

        for i, check in enumerate(checks[offset:offset+limit], 1):
            # Handle case where check might not be a dict with callable .get method
            if isinstance(check, dict):
                code = str(check.get("code", "?"))[:8]
                amount = check.get("amount_ton", "?")
                remaining = check.get("activation_limit", 0) - check.get("activations_used", 0)
                is_active = "✅" if check.get("is_active") else "🔴"
            else:
                # Fallback for non-dict objects (e.g., if check is an ORM model)
                code = str(getattr(check, "code", "?"))[:8]
                amount = getattr(check, "amount_ton", "?")
                remaining = getattr(check, "activation_limit", 0) - getattr(check, "activations_used", 0)
                is_active = "✅" if getattr(check, "is_active", False) else "🔴"

            lines.append(Visuals.frame_line_left("", w))
            lines.append(Visuals.frame_line_left(f"{is_active} Чек #{i}", w))
            lines.append(Visuals.frame_line_left(f"Сумма: {amount} GRAM", w))
            lines.append(Visuals.frame_line_left(f"Осталось: {remaining}", w))
            lines.append(Visuals.frame_line_left(f"Код: {code}...", w))

        lines.append(Visuals.frame_line_left("", w))

        total = len(checks)
        pages = (total + limit - 1) // limit
        current_page = (offset // limit) + 1
        lines.append(Visuals.frame_line_left(f"Стр. {current_page}/{pages} | Всего: {total}", w, align="center"))

        lines.append(Visuals.frame_bottom_left(w))
        return Visuals._render_block(lines)

    @classmethod
    def render_check_detail(cls, check: dict, ref_link: str = None) -> str:
        """Детальная информация о чеке с реферальной ссылкой"""
        code = check.get("code", "?")
        amount = check.get("amount_ton", "?")
        total_limit = check.get("activation_limit", 0)
        used = check.get("activations_used", 0)
        remaining = total_limit - used
        is_active = check.get("is_active", False)
        created = check.get("created_at", "?")
        ref_percent = check.get("referral_percent", 0)

        status = "✅ Активен" if is_active else "🔴 Деактивирован"

        w = 42
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🎁 ДЕТАЛИ ЧЕК А", w, align="center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"Статус: {status}", w),
            Visuals.frame_line_left(f"Сумма: {amount} GRAM", w),
            Visuals.frame_line_left(f"Итого: {float(amount) * total_limit} GRAM", w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"📊 Статистика:", w),
            Visuals.frame_line_left(f"  Всего: {total_limit} чеков", w),
            Visuals.frame_line_left(f"  Забрано: {used}", w),
            Visuals.frame_line_left(f"  Осталось: {remaining}", w),
        ]

        views = check.get("views_count")
        if views is not None:
            dropoff = check.get("dropoff_subs", 0)
            lines.append(Visuals.frame_line_left(f"  Просмотров: {views}", w))
            if dropoff > 0:
                lines.append(Visuals.frame_line_left(f"  Отвалились на подписке: {dropoff}", w))

        recent = check.get("recent_claims", [])
        if recent:
            lines.append(Visuals.frame_line_left("", w))
            lines.append(Visuals.frame_line_left(f"👥 Последние активации:", w))
            for r in recent:
                name_clean = r['name'][:20]
                lines.append(Visuals.frame_line_left(f"  👤 {name_clean} ({r['time']})", w))

        lines.extend([
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"🤝 Реф. отчисление: {ref_percent}%", w),
            Visuals.frame_line_left(f"📅 Создан: {created}", w),
        ])

        if ref_link:
            lines.append(Visuals.frame_line_left("", w))
            lines.append(Visuals.frame_line_left("🔗 РЕФ.ССЫЛКА:", w))
            lines.append(Visuals.frame_line_left("", w))
            # Split link for readability
            if len(ref_link) > 38:
                lines.append(Visuals.frame_line_left(ref_link[:38], w, align="left"))
                lines.append(Visuals.frame_line_left(ref_link[38:], w, align="left"))
            else:
                lines.append(Visuals.frame_line_left(ref_link, w))

        lines.append(Visuals.frame_line_left("", w))
        lines.append(Visuals.frame_bottom_left(w))

        return Visuals._render_block(lines)

    @classmethod
    def main_menu_kb(cls) -> InlineKeyboardMarkup:
        """Клавиатура главного меню"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый чек", callback_data="scheckult:create")],
            [InlineKeyboardButton(text="📋 Все чеки", callback_data="scheckult:list:0")],
            [InlineKeyboardButton(text="🔗 Реф.ссылки", callback_data="scheckult:reflinks:0")],
        ])

    @classmethod
    def checks_list_kb(cls, checks: list, total: int, offset: int = 0, limit: int = 5) -> InlineKeyboardMarkup:
        """Клавиатура списка чеков с пагинацией и выбором"""
        # Handle case where checks is not a list (e.g., if it's an integer due to bug)
        if not isinstance(checks, list):
            checks = []

        builder = InlineKeyboardBuilder()

        # Select option from list
        for i, check in enumerate(checks[offset:offset+limit], 1):
            if isinstance(check, dict):
                builder.button(text=f"👁 Чек #{i}", callback_data=f"scheckult:view:{check.get('code')}")
            else:
                builder.button(text=f"👁 Чек #{i}", callback_data=f"scheckult:view:{getattr(check, 'code', None)}")

        pages_amount = len(checks[offset:offset+limit])
        if pages_amount > 0:
            builder.adjust(*[1]*pages_amount) # 1 per row for check selects

        # Prev/Next
        nav_row = []
        if offset > 0:
            nav_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"scheckult:list:{max(0, offset-limit)}"))

        if offset + limit < total:
            nav_row.append(InlineKeyboardButton(text="Далее ▶", callback_data=f"scheckult:list:{offset+limit}"))

        if nav_row:
             builder.row(*nav_row)

        builder.row(InlineKeyboardButton(text="↩️ В меню", callback_data="scheckult:menu"))

        return builder.as_markup()

    @classmethod
    def check_detail_kb(cls, check_id: str, can_delete: bool = True) -> InlineKeyboardMarkup:
        """Клавиатура детального просмотра чека"""
        builder = InlineKeyboardBuilder()

        builder.button(text="📋 Назад к списку", callback_data="scheckult:list:0")

        if can_delete:
            builder.button(text="🔥 Сжечь (вернут остаток)", callback_data=f"scheckult:burn:{check_id}")
            builder.button(text="🗑 Удалить без следа", callback_data=f"scheckult:delete:{check_id}")

        builder.button(text="↩️ В меню", callback_data="scheckult:menu")

        builder.adjust(1)
        return builder.as_markup()

    @classmethod
    def reflinks_kb(cls, total: int, offset: int = 0, limit: int = 5) -> InlineKeyboardMarkup:
        """Клавиатура для реф.ссылок"""
        builder = InlineKeyboardBuilder()

        if offset > 0:
            builder.button(text="◀ Назад", callback_data=f"scheckult:reflinks:{max(0, offset-limit)}")

        if offset + limit < total:
            builder.button(text="Далее ▶", callback_data=f"scheckult:reflinks:{offset+limit}")

        builder.adjust(2)

        builder.button(text="↩️ В меню", callback_data="scheckult:menu")

        return builder.as_markup()

    @classmethod
    def render_referral_earned(cls, amount: float, referral_percent: int, ref_link: str) -> str:
        """Красивое показание реф-ссылки и заработка после активации"""
        w = 50
        earned_amount = amount * referral_percent / 100

        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🎉 АКТИВИРОВАНО! ВКУСНАЯ ВОЗМОЖНОСТЬ! 🎉", w, align="center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left("Ты получил:", w, align="left"),
            Visuals.frame_line_left(f"  💰 {amount} GRAM за активацию чека", w, align="left"),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left("✨ А ТЕПЕРЬ ЗАРАБОТАЙ БОЛЬШЕ ✨", w, align="center"),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"Каждая активация по твоей ссылке:", w, align="left"),
            Visuals.frame_line_left(f"  💸 +{earned_amount:.6f} GRAM ({referral_percent}%)", w, align="left"),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"🔗 ТВОЯ РЕФЕРАЛЬНАя ССЫЛКА 🔗", w, align="center"),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(f"{ref_link[:45]}...", w, align="center"),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left("👇 ПОДЕЛИСЬ И ЗАРАБОТАЙ 👇", w, align="center"),
            Visuals.frame_line_left("", w),
            Visuals.frame_bottom_left(w),
        ]

        return Visuals._render_block(lines)

    @classmethod
    def referral_share_kb(cls, ref_link: str, code: str) -> InlineKeyboardMarkup:
        """Клавиатура для быстрого шаринга реф-ссылки"""
        builder = InlineKeyboardBuilder()

        # Прямая ссылка
        builder.button(text="💰 ОТКРЫТЬ МОЮ РЕФЕРАЛЬНУЮ ССЫЛКУ", url=ref_link)

        # Вставить в чат
        builder.button(text="📎 ПОДЕЛИТЬСЯ В ЧАТЕ", switch_inline_query_current_chat=code)

        # Скопировать
        builder.button(text="📋 СКОПИРОВАТЬ", callback_data=f"scheck:copy:{code}")

        # Закрыть
        builder.button(text="✅ ЗАКРЫТЬ", callback_data=f"scheck:close")

        builder.adjust(1)
        return builder.as_markup()

    @classmethod
    def render_activation_success(cls, amount: float, is_referral: bool = False, ref_amount: float | None = None) -> str:
        """Красивое уведомление об успешной активации"""
        lines = [
            "🎉 <b>ОТЛИЧНО! АКТИВИРОВАНО!</b>",
            "",
            f"✅ Выплачено: <b>{amount} GRAM</b>",
            "🚀 Средства зачислены в xRocket",
        ]

        if is_referral and ref_amount:
            lines.append("")
            lines.append(f"💸 Реф. выплата: <b>+{ref_amount:.6f} GRAM</b>")

        lines.append("")
        lines.append("⏱️ <i>Оплата придёт в течение 5 минут</i>")

        return "\n".join(lines)

    @classmethod
    def render_password_error(cls, error_type: str = "wrong") -> str:
        """Красивое уведомление об ошибке при вводе пароля"""
        w = 42

        if error_type == "wrong":
            title = f"{Visuals.cross()} НЕВЕРНЫЙ ПАРОЛЬ {Visuals.cross()}"
            message = "Введённый пароль не подходит"
            hint = "Попробуйте ещё раз"
        else:
            title = "⚠️ ОШИБКА ПАРОЛЯ ⚠️"
            message = "Пожалуйста, попробуй ещё раз"
            hint = "Свяжись со службой поддержки если нужна помощь"

        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left(title, w, align="center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("", w),
            Visuals.frame_line_left(message, w, align="center"),
            Visuals.frame_line_left(hint, w, align="center"),
            Visuals.frame_line_left("", w),
            Visuals.frame_bottom_left(w),
        ]

        return Visuals._render_block(lines)

    @classmethod
    async def render_reflinks_list(cls, bot, user_id: int, all_checks: list[dict], offset: int = 0, limit: int = 3) -> str:
        """Красивое отображение реф-ссылок для всех чеков"""
        w = 42
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🔗 РЕФЕРАЛЬНЫЕ ССЫЛКИ", w, align="center"),
            Visuals.frame_separator_left(w),
        ]

        total = len(all_checks)

        if not all_checks:
            lines.append(Visuals.frame_line_left("Нет чеков", w, align="center"))
        else:
            for i, check in enumerate(all_checks[offset:offset+limit], 1):
                code = check.get("code", "?")
                amount = check.get("amount_ton", "?")
                remaining = check.get("activation_limit", 0) - check.get("activations_used", 0)

                # Generate ref link
                me = await bot.get_me()
                bot_username = me.username
                ref_link = f"https://t.me/{bot_username}?start=check_{code}_{user_id}"

                lines.append(Visuals.frame_line_left("", w))
                lines.append(Visuals.frame_line_left(f"💰 {amount} GRAM | Осталось: {remaining}", w))

                # Short ref link display
                short_ref = ref_link[:35] + "..." if len(ref_link) > 35 else ref_link
                lines.append(Visuals.frame_line_left(f"🔗 {short_ref}", w, align="left"))

        lines.append(Visuals.frame_line_left("", w))

        if total > 0:
            pages = (total + limit - 1) // limit
            current_page = (offset // limit) + 1
            lines.append(Visuals.frame_line_left(f"Стр. {current_page}/{pages}", w, align="center"))

        lines.append(Visuals.frame_line_left("", w))
        lines.append(Visuals.frame_bottom_left(w))

        return Visuals._render_block(lines)