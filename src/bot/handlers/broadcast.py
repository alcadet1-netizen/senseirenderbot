from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states.broadcast import BroadcastStates
from src.bot.keyboards.broadcast import broadcast_menu_kb, skip_text_kb, cancel_kb, confirm_kb, BroadcastCb
from src.bot.utils import check_owner
from src.services.broadcast_service import BroadcastMessage, MediaType
from src.core.container import Container

router = Router(name="broadcast")

async def send_msg(bot: Bot, uid: int, m: BroadcastMessage) -> bool:
    try:
        kw = {"caption": m.text, "parse_mode": "HTML"} if m.media_id else {"parse_mode": "HTML"}
        if m.media_type == MediaType.PHOTO:
            await bot.send_photo(uid, photo=m.media_id, **kw)
        elif m.media_type == MediaType.GIF:
            await bot.send_animation(uid, animation=m.media_id, **kw)
        elif m.media_type == MediaType.VIDEO:
            await bot.send_video(uid, video=m.media_id, **kw)
        elif m.media_type == MediaType.DOCUMENT:
            await bot.send_document(uid, document=m.media_id, **kw)
        else:
            await bot.send_message(uid, m.text, parse_mode="HTML")
        return True
    except Exception:
        return False

def preview(m: BroadcastMessage) -> str:
    icons = {MediaType.PHOTO: "🖼", MediaType.GIF: "🎬", MediaType.VIDEO: "🎥",
             MediaType.DOCUMENT: "📎", MediaType.NONE: "📝"}
    txt = f"📋 <b>Превью:</b>\nТип: {icons.get(m.media_type, '❓')}"
    if m.text:
        txt += f"\n\n<i>{m.text[:200]}{'...' if len(m.text) > 200 else ''}</i>"
    return txt

async def to_confirm(msg, state: FSMContext, bc_msg: BroadcastMessage, container: Container):
    container.broadcast_service.set_pending(bc_msg)
    await state.set_state(BroadcastStates.confirm)
    await msg.answer(preview(bc_msg) + "\n\n✅ Подтвердите:", reply_markup=confirm_kb(msg.from_user.id), parse_mode="HTML")

# === МЕНЮ ===
@router.callback_query(F.data == "admin:broadcast")
async def menu(cb: CallbackQuery, state: FSMContext, container: Container):
    await state.clear()
    cnt = await container.broadcast_service.get_count()
    await cb.message.edit_text(f"📢 <b>Рассылка</b>\n\n👥 Получателей: <b>{cnt}</b>", reply_markup=broadcast_menu_kb(cb.from_user.id), parse_mode="HTML")
    await cb.answer()

@router.callback_query(BroadcastCb.filter(F.action == "stats"))
async def stats(cb: CallbackQuery, callback_data: BroadcastCb, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    cnt = await container.broadcast_service.get_count()
    await cb.answer(f"👥 Пользователей: {cnt}", show_alert=True)

# === ВЫБОР ТИПА ===
@router.callback_query(BroadcastCb.filter(F.action.in_({"text", "photo", "gif", "doc", "video"})))
async def select_type(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext):
    if not await check_owner(cb, callback_data.user_id):
        return

    type_map = {"text": MediaType.NONE, "photo": MediaType.PHOTO,
                "gif": MediaType.GIF, "doc": MediaType.DOCUMENT, "video": MediaType.VIDEO}
    mt = type_map[callback_data.action]
    await state.update_data(media_type=mt.value, waiting_media=mt != MediaType.NONE)
    await state.set_state(BroadcastStates.waiting_content)
    
    prompts = {MediaType.NONE: "📝 Отправьте текст:", MediaType.PHOTO: "🖼 Отправьте фото:",
               MediaType.GIF: "🎬 Отправьте GIF:", MediaType.DOCUMENT: "📎 Отправьте файл:",
               MediaType.VIDEO: "🎥 Отправьте видео:"}
    await cb.message.edit_text(prompts[mt], reply_markup=cancel_kb(cb.from_user.id))
    await cb.answer()

# === КОНТЕНТ ===
@router.message(BroadcastStates.waiting_content, F.text)
async def on_text(msg: Message, state: FSMContext, container: Container):
    data = await state.get_data()
    if data.get("waiting_media"):
        await msg.answer("❌ Ожидался файл", reply_markup=cancel_kb(msg.from_user.id))
        return
    bc = BroadcastMessage(text=msg.html_text, media_type=MediaType(data.get("media_type", "none")))
    await to_confirm(msg, state, bc, container)

async def handle_media(msg: Message, state: FSMContext, media_id: str, mtype: MediaType, container: Container):
    caption = msg.caption # Note: aiogram Message doesn't have .html_caption by default, but let's check if we need html
    # The user code used msg.caption. I'll stick to that.
    # Actually, for text it used msg.html_text.
    
    await state.update_data(media_id=media_id, media_type=mtype.value, text=caption, waiting_media=False)
    if caption:
        await to_confirm(msg, state, BroadcastMessage(caption, mtype, media_id), container)
    else:
        await state.set_state(BroadcastStates.waiting_text)
        await msg.answer("✅ Получено! Добавьте текст:", reply_markup=skip_text_kb(msg.from_user.id))

@router.message(BroadcastStates.waiting_content, F.photo)
async def on_photo(msg: Message, state: FSMContext, container: Container):
    await handle_media(msg, state, msg.photo[-1].file_id, MediaType.PHOTO, container)

@router.message(BroadcastStates.waiting_content, F.animation)
async def on_gif(msg: Message, state: FSMContext, container: Container):
    await handle_media(msg, state, msg.animation.file_id, MediaType.GIF, container)

@router.message(BroadcastStates.waiting_content, F.video)
async def on_video(msg: Message, state: FSMContext, container: Container):
    await handle_media(msg, state, msg.video.file_id, MediaType.VIDEO, container) # User mapped VIDEO to VIDEO

@router.message(BroadcastStates.waiting_content, F.document)
async def on_doc(msg: Message, state: FSMContext, container: Container):
    await handle_media(msg, state, msg.document.file_id, MediaType.DOCUMENT, container)

# === ТЕКСТ К МЕДИА ===
@router.message(BroadcastStates.waiting_text, F.text)
async def add_text(msg: Message, state: FSMContext, container: Container):
    data = await state.get_data()
    bc = BroadcastMessage(msg.html_text, MediaType(data["media_type"]), data.get("media_id"))
    await to_confirm(msg, state, bc, container)

@router.callback_query(BroadcastCb.filter(F.action == "close"))
async def close(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    container.broadcast_service.clear_pending()
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        await cb.message.edit_text("❌ Закрыто")
    try:
        await cb.answer()
    except TelegramBadRequest:
        pass

@router.callback_query(BroadcastCb.filter(F.action == "skip_text"), BroadcastStates.waiting_text)
async def skip(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    data = await state.get_data()
    bc = BroadcastMessage(None, MediaType(data["media_type"]), data["media_id"])
    container.broadcast_service.set_pending(bc)
    await state.set_state(BroadcastStates.confirm)
    await cb.message.edit_text(preview(bc) + "\n\n✅ Подтвердите:", reply_markup=confirm_kb(cb.from_user.id), parse_mode="HTML")
    try:
        await cb.answer()
    except TelegramBadRequest:
        pass

@router.callback_query(BroadcastCb.filter(F.action == "edit_text"), BroadcastStates.confirm)
async def edit(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext):
    if not await check_owner(cb, callback_data.user_id):
        return
    await state.set_state(BroadcastStates.waiting_text)
    await cb.message.edit_text("✏️ Новый текст:", reply_markup=cancel_kb(cb.from_user.id))
    try:
        await cb.answer()
    except TelegramBadRequest:
        pass

# === ОТПРАВКА ===
@router.callback_query(BroadcastCb.filter(F.action == "send"), BroadcastStates.confirm)
async def send(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext, bot: Bot, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    svc = container.broadcast_service
    bc = svc.get_pending()
    if not bc or not bc.is_valid():
        try:
            await cb.answer("❌ Ошибка", show_alert=True)
        except TelegramBadRequest:
            pass
        return
    
    await cb.message.edit_text("⏳ <b>Отправка...</b>", parse_mode="HTML")
    
    async def progress(cur, tot):
        try: await cb.message.edit_text(f"⏳ Прогресс: {cur}/{tot} ({cur*100//tot}%)", parse_mode="HTML")
        except: pass
    
    res = await svc.broadcast(bc, lambda u, m: send_msg(bot, u, m), on_progress=progress)
    svc.clear_pending()
    await state.clear()
    
    await cb.message.edit_text(
        f"✅ <b>Готово!</b>\n\n📊 Всего: {res.total}\n✅ Успех: {res.success}\n"
        f"🚫 Блок: {res.blocked}\n❌ Ошибки: {res.failed}\n📈 {res.success_rate:.1f}%",
        reply_markup=broadcast_menu_kb(cb.from_user.id),
        parse_mode="HTML"
    )

@router.callback_query(BroadcastCb.filter(F.action == "cancel"))
async def cancel(cb: CallbackQuery, callback_data: BroadcastCb, state: FSMContext, container: Container):
    if not await check_owner(cb, callback_data.user_id):
        return
    container.broadcast_service.clear_pending()
    await state.clear()
    await cb.message.edit_text("❌ Отменено", reply_markup=broadcast_menu_kb(cb.from_user.id))
    try:
        await cb.answer()
    except TelegramBadRequest:
        pass
