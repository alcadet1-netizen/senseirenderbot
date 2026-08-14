# Fix the duel service DM callback data calls

with open(r'C:\sensei\src\services\duel_service.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Replace the keyboard building section
old_keyboard = '''        # Build keyboard
        did = duel.id
        kb_list = [
            [
                InlineKeyboardButton(text="���🛡��️ Увернуться влево", callback_data=DuelMoveCb(did=did, mv='dodge_l').pack()),
                InlineKeyboardButton(text="���🛡��️ Увернуться вправо", callback_data=DuelMoveCb(did=did, mv='dodge_r').pack())
            ],
            [
                InlineKeyboardButton(text="��⚔��️ Ударить влево", callback_data=DuelMoveCb(did=did, mv='hit_l').pack()),
                InlineKeyboardButton(text="��⚔��️ Ударить вправо", callback_data=DuelMoveCb(did=did, mv='hit_r').pack())
            ],
            [
                InlineKeyboardButton(text="���🤖 Автоход", callback_data=DuelUtilityCb(did=did, act='auto').pack()),
                InlineKeyboardButton(text="���🔄 Сброс", callback_data=DuelUtilityCb(did=did, act='reset').pack())
            ],
            [
                InlineKeyboardButton(text="���🏳��️ Сдаться", callback_data=DuelSurrenderCb(did=did).pack())
            ]
        ]'''

new_keyboard = '''        # Build keyboard
        did = duel.id
        kb_list = [
            [
                InlineKeyboardButton(text="���🛡��️ Увернуться влево", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_l').pack()),
                InlineKeyboardButton(text="���🛡��️ Увернуться вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='dodge_r').pack())
            ],
            [
                InlineKeyboardButton(text="��⚔��️ Ударить влево", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_l').pack()),
                InlineKeyboardButton(text="��⚔��️ Ударить вправо", callback_data=DuelMoveCb(id=did, u=user_id, m='hit_r').pack())
            ],
            [
                InlineKeyboardButton(text="���🤖 Автоход", callback_data=DuelUtilityCb(id=did, u=user_id, a='auto').pack()),
                InlineKeyboardButton(text="���🔄 Сброс", callback_data=DuelUtilityCb(id=did, u=user_id, a='reset').pack())
            ],
            [
                InlineKeyboardButton(text="���🏳��️ Сдаться", callback_data=DuelSurrenderCb(id=did, u=user_id).pack())
            ]
        ]'''

content = content.replace(old_keyboard, new_keyboard)

with open(r'C:\sensei\src\services\duel_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed duel service DM callback data calls")