# Fix the duel service DM fallback logic

with open(r'C:\sensei\src\services\duel_service.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the Send/Edit section and fix the fallback logic
old_send_edit = '''        # Send/Edit
        msg_id = duel.control_message_ids.get(user_id)
        try:
            if not msg_id:
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
            else:
                await duel.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except TelegramForbiddenError:
            # User blocked bot, auto-surrender?
            logger.warning(f"User {user_id} blocked bot during duel {duel.id}")
            # This will trigger surrender from the other side
            await self.surrender(duel.id, user_id)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Duel {duel.id}: Control update for {user_id} failed: {e}")
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Control update for {user_id} failed critically")'''

new_send_edit = '''        # Send/Edit
        msg_id = duel.control_message_ids.get(user_id)
        try:
            if not msg_id:
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
            else:
                await duel.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
        except TelegramForbiddenError:
            # User blocked bot, auto-surrender?
            logger.warning(f"User {user_id} blocked bot during duel {duel.id}")
            # This will trigger surrender from the other side
            await self.surrender(duel.id, user_id)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Duel {duel.id}: Control update for {user_id} failed: {e}")
                # Fall back to sending a new message
                msg = await duel.bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
                duel.control_message_ids[user_id] = msg.message_id
        except Exception as e:
            logger.exception(f"Duel {duel.id}: Control update for {user_id} failed critically")'''

content = content.replace(old_send_edit, new_send_edit)

with open(r'C:\sensei\src\services\duel_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed duel service DM fallback logic")