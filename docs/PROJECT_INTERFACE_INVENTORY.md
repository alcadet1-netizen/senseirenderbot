# Инвентарь интерфейсов проекта

Статический AST-инвентарь: показывает охват обзора, НЕ доказывает исполнение всех функций. Динамическая регистрация может не попасть в список.

## Команды и message/callback handlers

### src/bot/handlers/admin_commands.py

- `cmd_cancel` — `router.message(Command('cancel'))`
- `cmd_health` — `router.message(Command('health', 'status'))`
- `cmd_admin_chats` — `router.message(Command('senseichats', 'chats', 'группы'))`
- `cmd_admin_help` — `router.message(Command('senseiadmin', 'adminhelp'))`
- `cmd_admin_stats` — `router.message(Command('adminstats'))`
- `cmd_topticket` — `router.message(Command('topticket'))`
- `cb_topticket` — `router.callback_query(F.data.startswith('topticket:'))`
- `cmd_add_coin` — `router.message(Command('addcoin'))`
- `cmd_amnistia` — `router.message(Command('amnistia'))`
- `cmd_add_xp` — `router.message(Command('addxp'))`
- `cmd_add_ticket` — `router.message(Command('addticket'))`
- `cmd_add_katana` — `router.message(Command('addkatana'))`
- `cmd_burn_tickets` — `router.message(Command('ticketburn'))`
- `cmd_bonus_sensei` — `router.message(Command('bonussensei'))`
- `cmd_ban_list` — `router.message(Command('banlist'))`
- `cmd_ban` — `router.message(Command('бан', 'ban'))`
- `cmd_unban` — `router.message(Command('разбанить', 'unban'))`
- `cmd_sensei_mute_on` — `router.message(Command('senseimuteon', 'addmute', 'mute'))`
- `cmd_sensei_mute_off` — `router.message(Command('senseimuteoff', 'offmute', 'unmute'))`
- `cmd_new_season` — `router.message(Command('senseinewseasons'))`
- `cmd_sansara` — `router.message(Command('senseisansara'))`
- `cmd_govori` — `router.message(Command('govori'))`
- `process_govori_chat_selection` — `router.callback_query(GovoriState.waiting_for_chat_selection, F.data.startswith('govori_select:'))`
- `process_govori_content` — `router.message(GovoriState.waiting_for_content)`
- `cmd_broadcast` — `router.message(Command('broadcast'))`
- `cmd_sensei_visual` — `router.message(Command('senseivisual'))`
- `cb_visuals` — `router.callback_query(VisualsCb.filter())`

### src/bot/handlers/banzai.py

- `cmd_banzai` — `router.message(Command('banzai', 'банзай', 'banzazi', 'банзази'))`
- `cb_set_time` — `router.callback_query(F.data == 'banzai_set_time', StateFilter(BanzaiStates.settings))`
- `process_set_time` — `router.message(StateFilter(BanzaiStates.set_minutes))`
- `cb_set_reward` — `router.callback_query(F.data == 'banzai_set_reward', StateFilter(BanzaiStates.settings))`
- `process_set_reward` — `router.message(StateFilter(BanzaiStates.set_reward))`
- `cb_set_chat` — `router.callback_query(F.data == 'banzai_set_chat', StateFilter(BanzaiStates.settings))`
- `process_set_chat` — `router.message(StateFilter(BanzaiStates.set_chat))`
- `cb_rules` — `router.callback_query(F.data == 'banzai_rules', StateFilter(BanzaiStates.settings))`
- `cb_back_to_settings` — `router.callback_query(F.data == 'banzai_back_to_settings', StateFilter(BanzaiStates.settings))`
- `cb_start` — `router.callback_query(F.data == 'banzai_start', StateFilter(BanzaiStates.settings))`
- `cb_banzai_game` — `router.callback_query(F.data.startswith('banzai:'))`

### src/bot/handlers/bomb.py

- `cmd_senseibomb` — `router.message(Command('senseibomb'))`
- `check_bomb_participant` — `router.message(F.text & ~F.text.startswith('/'), HasActiveBomb())`

### src/bot/handlers/boss_admin.py

- `cmd_boss_settings` — `router.message(Command('boss_settings'), AdminFilter())`
- `cmd_boss_chance` — `router.message(Command('boss_chance'), AdminFilter())`
- `cmd_boss_reward` — `router.message(Command('boss_reward'), AdminFilter())`
- `cmd_boss_pool` — `router.message(Command('boss_pool'), AdminFilter())`
- `cmd_boss_reset_pool` — `router.message(Command('boss_reset_pool'), AdminFilter())`

### src/bot/handlers/boss_commands.py

- `sensei_boss` — `router.message(Command('senseiboss'), AdminFilter())`
- `kill_boss` — `router.message(Command('killboss'), AdminFilter())`
- `cmd_fight` — `router.message(F.text.lower().in_({'файт', 'fight', 'атака', 'attack', 'бить', 'hit'}))`
- `cmd_ult` — `router.message(F.text.lower().in_({'ульта', 'ult', 'ultra', 'ultimate', '/ulta'}))`
- `hit_boss` — `router.callback_query(F.data == 'hit_boss')`

### src/bot/handlers/boss_editor.py

- `on_set_reward` — `router.callback_query(BossEditorCallback.filter(F.action == 'set_reward'), BossEditorFSM.choosing_action)`
- `on_choose_boss` — `router.callback_query(BossEditorCallback.filter(F.action == 'choose_boss'), BossEditorFSM.choosing_action)`
- `on_set_boss` — `router.callback_query(BossEditorCallback.filter(F.action == 'set_boss'), BossEditorFSM.choosing_boss)`
- `on_reward_set` — `router.message(BossEditorFSM.setting_reward_pool)`
- `on_set_ton_chance` — `router.callback_query(BossEditorCallback.filter(F.action == 'set_ton_chance'), BossEditorFSM.choosing_action)`
- `on_ton_chance_set` — `router.message(BossEditorFSM.setting_ton_chance)`
- `on_start_boss` — `router.callback_query(BossEditorCallback.filter(F.action == 'start'), BossEditorFSM.choosing_action)`
- `handle_initial_editor_message` — `router.message(BossEditorFSM.choosing_action)`
- `on_menu_duration` — `router.callback_query(BossEditorCallback.filter(F.action == 'menu_duration'), BossEditorFSM.choosing_action)`
- `on_set_duration` — `router.callback_query(BossEditorCallback.filter(F.action == 'set_duration'), BossEditorFSM.setting_duration)`
- `on_duration_input` — `router.message(BossEditorFSM.setting_duration)`
- `on_input_duration` — `router.callback_query(BossEditorCallback.filter(F.action == 'input_duration'), BossEditorFSM.choosing_action)`
- `on_menu_chat` — `router.callback_query(BossEditorCallback.filter(F.action == 'menu_chat'), BossEditorFSM.choosing_action)`
- `on_set_chat` — `router.callback_query(BossEditorCallback.filter(F.action == 'set_chat'), BossEditorFSM.choosing_chat)`
- `on_duration_back` — `router.callback_query(BossEditorCallback.filter(F.action == 'noop'), BossEditorFSM.setting_duration)`
- `on_chat_back` — `router.callback_query(BossEditorCallback.filter(F.action == 'noop'), BossEditorFSM.choosing_chat)`
- `on_boss_list_back` — `router.callback_query(F.data == 'boss_edit:back', BossEditorFSM.choosing_boss)`

### src/bot/handlers/broadcast.py

- `menu` — `router.callback_query(F.data == 'admin:broadcast')`
- `stats` — `router.callback_query(BroadcastCb.filter(F.action == 'stats'))`
- `select_type` — `router.callback_query(BroadcastCb.filter(F.action.in_({'text', 'photo', 'gif', 'doc', 'video'})))`
- `on_text` — `router.message(BroadcastStates.waiting_content, F.text)`
- `on_photo` — `router.message(BroadcastStates.waiting_content, F.photo)`
- `on_gif` — `router.message(BroadcastStates.waiting_content, F.animation)`
- `on_video` — `router.message(BroadcastStates.waiting_content, F.video)`
- `on_doc` — `router.message(BroadcastStates.waiting_content, F.document)`
- `add_text` — `router.message(BroadcastStates.waiting_text, F.text)`
- `close` — `router.callback_query(BroadcastCb.filter(F.action == 'close'))`
- `skip` — `router.callback_query(BroadcastCb.filter(F.action == 'skip_text'), BroadcastStates.waiting_text)`
- `edit` — `router.callback_query(BroadcastCb.filter(F.action == 'edit_text'), BroadcastStates.confirm)`
- `send` — `router.callback_query(BroadcastCb.filter(F.action == 'send'), BroadcastStates.confirm)`
- `cancel` — `router.callback_query(BroadcastCb.filter(F.action == 'cancel'))`

### src/bot/handlers/callbacks.py

- `cb_check_sub` — `router.callback_query(F.data == 'check_sub')`
- `cb_profile` — `router.callback_query(MenuCb.filter(F.action == 'profile'))`
- `cb_back_to_profile` — `router.callback_query(MenuCb.filter(F.action == 'back_to_profile'))`
- `cb_top_katana_page` — `router.callback_query(KatanaTopCb.filter())`
- `cb_top_menu` — `router.callback_query(MenuCb.filter(F.action == 'top_menu'))`
- `cb_daily` — `router.callback_query(MenuCb.filter(F.action == 'daily'))`
- `cb_upgrade_katana_confirm` — `router.callback_query(MenuCb.filter(F.action == 'upgrade_katana_confirm'))`
- `cb_do_upgrade_katana` — `router.callback_query(MenuCb.filter(F.action == 'confirm_upgrade_katana'))`
- `cb_cancel` — `router.callback_query(MenuCb.filter(F.action == 'cancel'))`
- `cb_help` — `router.callback_query(MenuCb.filter(F.action == 'help'))`
- `cb_back_to_start` — `router.callback_query(MenuCb.filter(F.action == 'back_to_start'))`
- `cb_show_top` — `router.callback_query(MenuCb.filter(F.action.in_({'top_xp', 'top_coins', 'top_messages', 'top_tickets', 'top_streak'})))`
- `cb_exchange_menu` — `router.callback_query(MenuCb.filter(F.action == 'exchange_menu'))`
- `cb_achievements` — `router.callback_query(MenuCb.filter(F.action == 'achievements'))`
- `cb_buy_katana` — `router.callback_query(MenuCb.filter(F.action == 'buy_katana'))`
- `cb_exchange_coins_to_ticket` — `router.callback_query(MenuCb.filter(F.action == 'exchange_coins_to_ticket'))`
- `cb_exchange_ticket_to_coins` — `router.callback_query(MenuCb.filter(F.action == 'exchange_ticket_to_coins'))`

### src/bot/handlers/chat_settings.py

- `cmd_offexit` — `router.message(Command('offexit'))`
- `cmd_onexit` — `router.message(Command('onexit'))`
- `cmd_welcomeon` — `router.message(Command('welcomeon'))`
- `cmd_welcomeoff` — `router.message(Command('welcomeoff'))`
- `cmd_autobanon` — `router.message(Command('autobanon'))`
- `cmd_autobanoff` — `router.message(Command('autobanoff'))`
- `cmd_uvedomleniaon` — `router.message(Command('uvedomleniaon'))`
- `cmd_uvedomleniaoff` — `router.message(Command('uvedomleniaoff'))`
- `cmd_captchaon` — `router.message(Command('captchaon'))`
- `cmd_captchaoff` — `router.message(Command('captchaoff'))`
- `cmd_popugai` — `router.message(Command('popugai'))`

### src/bot/handlers/digest.py

- `cmd_digest` — `router.message(Command('senseivesti', 'вестник', 'digest'))`
- `callback_digest_baldoi` — `router.callback_query(DigestCb.filter(F.mode == 'baldoi'))`
- `callback_digest_vestnik` — `router.callback_query(DigestCb.filter(F.mode == 'vestnik'))`
- `cmd_vestnik` — `router.message(Command('senseivestnik'))`
- `cmd_stats` — `router.message(Command('senseistat', 'статс', 'stats'))`
- `cmd_sage` — `router.message(F.text.regexp(SENSEI_MUDRETS_RE))`

### src/bot/handlers/donate.py

- `cmd_donate` — `router.message(Command('donate'))`
- `coin_invoice` — `router.callback_query(F.data.startswith('coinbuy:'))`
- `donate_invoice` — `router.callback_query(F.data.startswith('donate:'))`
- `cmd_paysupport` — `router.message(Command('paysupport'))`

### src/bot/handlers/draw.py

- `command_draw` — `router.message(Command('draw'))`
- `trigger_draw` — `router.message(F.text.regexp(DRAW_PATTERN))`

### src/bot/handlers/duel_commands.py

- `text_duel` — `router.message(F.reply_to_message & F.text.regexp('сенсей\\s+дуэль(?:\\s+(?:№\\s*)?(\\d+))?', flags=re.IGNORECASE))`
- `cmd_duel` — `router.message(Command('duel', 'senseiduel'))`
- `on_duel_decision` — `router.callback_query(DuelDecisionCb.filter())`
- `on_duel_move` — `router.callback_query(DuelMoveCb.filter())`
- `on_duel_surrender` — `router.callback_query(DuelSurrenderCb.filter())`
- `on_duel_utility` — `router.callback_query(DuelUtilityCb.filter())`

### src/bot/handlers/events.py

- `on_new_chat_members` — `router.message(F.new_chat_members)`
- `on_captcha_solve` — `router.callback_query(F.data.startswith('captcha:'))`

### src/bot/handlers/fire.py

- `cmd_fire` — `router.message(F.text.regexp('^\\+fire\\s+(\\d+(?:\\.\\d+)?)', flags=re.IGNORECASE))`

### src/bot/handlers/fly.py

- `command` — `router.message(Command('senseifly'))`

### src/bot/handlers/maintenance.py

- `cmd_sensei` — `router.message(Command('sensei'))`
- `callback_sensei` — `router.callback_query(F.data.startswith('sensei:'))`

### src/bot/handlers/music.py

- `handle_music_callback` — `router.callback_query(F.data.startswith('music_dl_'))`
- `cmd_music` — `router.message(F.text.regexp('^[/!\\.](music / find / m / mus / музыка)\\s+.+', flags=re.IGNORECASE))`; `router.message(F.text.regexp('^(найти / найди / скачай / скачать)\\s+.+', flags=re.IGNORECASE))`
- `cmd_music_help` — `router.message(F.text.regexp('^[/!\\.](music / find / m / mus / музыка)$', flags=re.IGNORECASE))`

### src/bot/handlers/paid_hedgehog.py

- `offer` — `router.callback_query(F.data.regexp('^petbuy:offer(?::[0-9]+)?$'))`

### src/bot/handlers/quiz.py

- `cmd_add_question` — `router.message(Command('addquestion', 'addquest'), F.chat.type == 'private')`
- `process_question_text` — `router.message(AddQuestionStates.waiting_question, F.text)`
- `skip_image` — `router.message(AddQuestionStates.waiting_image, Command('skip'))`
- `process_image` — `router.message(AddQuestionStates.waiting_image, F.photo)`
- `process_answer` — `router.message(AddQuestionStates.waiting_answer, F.text)`
- `cmd_start_quiz` — `router.message(Command('senseiviktorina'), F.chat.type.in_({'group', 'supergroup'}))`
- `cmd_stop_quiz` — `router.message(Command('stopquiz'), F.chat.type.in_({'group', 'supergroup'}))`
- `check_quiz_answer` — `router.message(F.chat.type.in_({'group', 'supergroup'}), F.text, ~F.text.startswith('/'), QuizActiveFilter())`

### src/bot/handlers/referral.py

- `cmd_ref` — `router.message(Command('senseireferal', 'referral', 'ref', 'referal', 'реферал'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseireferal(@\\w+)?\\b'))`
- `cb_menu` — `router.callback_query(RefCb.filter(F.action == 'menu'))`
- `cb_main` — `router.callback_query(RefCb.filter(F.action == 'main'))`
- `cb_stats` — `router.callback_query(RefCb.filter(F.action == 'stats'))`
- `cb_share` — `router.callback_query(RefCb.filter(F.action == 'share'))`
- `cb_top` — `router.callback_query(RefCb.filter(F.action == 'top'))`
- `cb_rewards` — `router.callback_query(RefCb.filter(F.action == 'rewards'))`
- `cb_ranks` — `router.callback_query(RefCb.filter(F.action == 'ranks'))`
- `cb_list` — `router.callback_query(RefCb.filter(F.action == 'list'))`
- `cb_help` — `router.callback_query(RefCb.filter(F.action == 'help'))`
- `cb_empire` — `router.callback_query(RefCb.filter(F.action == 'empire'))`

### src/bot/handlers/roulette.py

- `cmd_senseiroulette` — `router.message(Command('senseiroulette'))`
- `check_roulette_response` — `router.message(F.text & ~F.text.startswith('/'), HasActiveRoulette())`

### src/bot/handlers/sensei_check/admin.py

- `cmd_senseicheck` — `router.message(Command('senseicheck'), AdminFilter())`
- `cb_back_menu` — `router.callback_query(F.data == 'scheckult:menu')`
- `cb_presets_list` — `router.callback_query(F.data == 'scheckult:presets')`
- `cb_preset_add` — `router.callback_query(F.data == 'scheckult:preset:add')`
- `step_preset_name` — `router.message(SenseiCheckPresetStates.waiting_name)`
- `step_preset_channels` — `router.message(SenseiCheckPresetStates.waiting_channels)`
- `cb_preset_view` — `router.callback_query(F.data.startswith('scheckult:preset:view:'))`
- `cb_preset_del` — `router.callback_query(F.data.startswith('scheckult:preset:del:'))`
- `cb_create_start` — `router.callback_query(F.data == 'scheckult:create', AdminFilter())`
- `sc_amount_cb` — `router.callback_query(SenseiCheckCreateStates.waiting_amount, F.data.startswith('scheckadm:amt:'))`
- `sc_amount_msg` — `router.message(SenseiCheckCreateStates.waiting_amount)`
- `sc_act_cb` — `router.callback_query(SenseiCheckCreateStates.waiting_activations, F.data.startswith('scheckadm:act:'))`
- `sc_act_msg` — `router.message(SenseiCheckCreateStates.waiting_activations)`
- `sc_channels_msg` — `router.message(SenseiCheckCreateStates.waiting_channels)`
- `sc_ch_del` — `router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data.startswith('scheckadm:chdel:'))`
- `sc_ch_clear` — `router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == 'scheckadm:chclear')`
- `sc_ch_preset_list` — `router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == 'scheckadm:chpreset')`
- `sc_ch_next` — `router.callback_query(SenseiCheckCreateStates.waiting_channels, F.data == 'scheckadm:chnext')`
- `sc_ref_cb` — `router.callback_query(SenseiCheckCreateStates.waiting_referral, F.data.startswith('scheckadm:ref:'))`
- `sc_text_skip` — `router.callback_query(SenseiCheckCreateStates.waiting_text, F.data == 'scheckadm:skip:text')`
- `sc_text_msg` — `router.message(SenseiCheckCreateStates.waiting_text)`
- `sc_photo_skip` — `router.callback_query(SenseiCheckCreateStates.waiting_photo, F.data == 'scheckadm:skip:photo')`
- `sc_photo_msg` — `router.message(SenseiCheckCreateStates.waiting_photo)`
- `sc_pwd_skip` — `router.callback_query(SenseiCheckCreateStates.waiting_password, F.data == 'scheckadm:skip:password')`
- `sc_pwd_gen` — `router.callback_query(SenseiCheckCreateStates.waiting_password, F.data == 'scheckadm:pwd:gen')`
- `sc_pwd_msg` — `router.message(SenseiCheckCreateStates.waiting_password)`
- `sc_edit_field` — `router.callback_query(SenseiCheckCreateStates.confirm, F.data.startswith('scheckadm:edit:'))`
- `sc_back_to_dash` — `router.callback_query(F.data == 'scheckadm:back:dashboard')`
- `sc_create_confirm` — `router.callback_query(SenseiCheckCreateStates.confirm, F.data == 'scheckadm:create')`
- `sc_cancel` — `router.callback_query(F.data == 'scheckadm:cancel')`
- `cb_list_checks` — `router.callback_query(F.data.startswith('scheckult:list:'), AdminFilter())`
- `cb_reflinks` — `router.callback_query(F.data.startswith('scheckult:reflinks:'), AdminFilter())`
- `cb_view_check` — `router.callback_query(F.data.startswith('scheckult:view:'), AdminFilter())`
- `cb_burn` — `router.callback_query(F.data.startswith('scheckult:burn:'))`
- `cb_del` — `router.callback_query(F.data.startswith('scheckult:delete:'))`

### src/bot/handlers/sensei_check/user.py

- `sc_user_activate` — `router.callback_query(F.data.startswith('scheck:activate:'))`
- `sc_cancel_act` — `router.callback_query(F.data == 'scheck:cancel_act')`
- `sc_pwd_input` — `router.message(SenseiCheckActivateStates.waiting_password)`
- `sc_captcha_input` — `router.message(SenseiCheckActivateStates.waiting_captcha)`
- `sc_copy_link` — `router.callback_query(F.data.startswith('scheck:copy:'))`
- `sc_close` — `router.callback_query(F.data == 'scheck:close')`

### src/bot/handlers/slots.py

- `cmd_slots` — `router.message(Command('senseislots', 'senseislot'))`

### src/bot/handlers/trade.py

- `cmd_trade` — `router.message(Command('senseitrade', 'trade'))`

### src/bot/handlers/triggers.py

- `trigger_help` — `router.message(F.text.regexp(HELP_PATTERN))`
- `trigger_pour` — `router.message(F.text.regexp(POUR_PATTERN))`
- `trigger_daily` — `router.message(F.text.regexp(DAILY_PATTERN))`
- `trigger_crypto_top` — `router.message(F.text.regexp(CRYPTO_TOP_PATTERN))`
- `trigger_crypto_calc` — `router.message(F.text.regexp(CRYPTO_CALC_PATTERN))`
- `trigger_crypto_amount` — `router.message(F.text.regexp(CRYPTO_AMOUNT_PATTERN))`
- `trigger_crypto_price` — `router.message(F.text.regexp(CRYPTO_PRICE_PATTERN))`
- `trigger_sage_question` — `router.message(F.text.regexp(SAGE_QUESTION_PATTERN))`
- `trigger_vanga` — `router.message(F.text.regexp(VANGA_PATTERN))`
- `trigger_rulya` — `router.message(F.text.regexp(RULYA_PATTERN))`
- `trigger_sensei` — `router.message(F.text.regexp(SENSEI_PATTERN))`
- `check_easter_eggs_handler` — `router.message(F.text.func(lambda text: text and check_easter_egg(text) is not None))`
- `catch_all_message` — `router.message()`

### src/bot/handlers/user_commands.py

- `cmd_start` — `router.message(CommandStart())`
- `cmd_upkatana` — `router.message(Command('upkatana'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/upkatana(@\\w+)?\\b'))`; `router.message(F.text.lower().in_({'ап катана', '\\upkatana'}))`
- `cmd_mykatana` — `router.message(Command('mykatana'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/mykatana(@\\w+)?\\b'))`; `router.message(F.text.lower().in_({'моя катана'}))`
- `cmd_help` — `router.message(Command('senseihelp', 'помощь', 'help'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseihelp(@\\w+)?\\b'))`; `router.message(F.text.lower().in_({'сенсей помоги', 'сенсей что умеешь?'}))`
- `cmd_profile` — `router.message(Command('mysensei', 'профиль', 'profile'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/mysensei(@\\w+)?\\b'))`; `router.message(F.text.lower() == 'мой сенсей')`; `router.message(F.text == '👤 Профиль', PrivateChatFilter())`
- `cmd_mycoin` — `router.message(Command('mycoin'))`; `router.message(F.text.lower() == 'мой балик')`
- `cmd_top` — `router.message(Command('senseitop', 'топ', 'top', 'рейтинг'))`
- `cmd_topkatana` — `router.message(Command('topkatana'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/topkatana(@\\w+)?\\b'))`
- `cmd_daily` — `router.message(Command('senseidaily', 'бонус', 'daily'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseidaily(@\\w+)?\\b'))`; `router.message(F.text.lower().in_({'ежа', 'фарм', 'фармить', 'фарма', 'ферма'}))`; `router.message(F.text == '🎁 Бонус', PrivateChatFilter())`
- `cmd_exchange` — `router.message(Command('senseiobmen', 'обмен', 'exchange'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseiobmen(@\\w+)?\\b'))`
- `cmd_senseibank` — `router.message(Command('senseibank'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseibank(@\\w+)?\\b'))`
- `cmd_senseiuser` — `router.message(Command('senseiuser'))`; `router.message(F.text.regexp('(?i)(?:^ / \\s)/senseiuser(@\\w+)?\\b'))`

### src/bot/handlers/wave.py

- `cmd_senseiwave` — `router.message(Command('senseiwave'))`
- `count_wave_message` — `router.message(F.text & ~F.text.startswith('/'), HasActiveWave())`

### src/bot/handlers/widget_check.py

- `cmd_widget_check` — `router.message(Command('senseiwidgetcheck'))`
- `cmd_ega` — `router.message(Command('ega'))`
- `cmd_copy_check` — `router.message(Command('senseicopycheck'))`

### src/bot/handlers/widgets.py

- `cmd_widget` — `router.message(Command('senseiwidget'))`; `router.message(F.text == '🧩 Карточки')`
- `widget_callback` — `router.callback_query(WidgetAction.filter())`
- `export_html` — `router.message(Command('widgethtml'))`

### src/bot/handlers/zov.py

- `cmd_zov` — `router.message(Command('senseizov'))`
- `cmd_stop_zov` — `router.message(Command('senseinezov'))`

## Публичные интерфейсы сервисов

### src/services/achievement_service.py

- `AchievementService`: `check_and_unlock_achievements`, `get_user_achievements`, `unlock_achievement`, `seed_achievements`

### src/services/banzai_service.py

- `BanzaiService`: `update_user_activity`, `start_game`, `update_duration`, `update_reward`, `stop_game`, `is_active`, `get_status`, `restore_workers`, `get_game_keyboard`, `get_live_state`, `refresh_window`, `set_game_message_id`, `get_game_message_id`, `pin_game_message`, `unpin_game_message`

### src/services/boss_service.py

- `BossService`: `get_reward_settings`, `update_setting`, `check_pool_availability`, `increment_pool_used`, `reset_pool`, `get_state`, `save_state`, `start_boss`, `set_message_data`, `stop_boss`, `attack_boss`, `get_leaderboard`, `get_boss_image`, `get_hp_bar`

### src/services/broadcast_service.py

- `BroadcastMessage`: `is_valid`
- `BroadcastResult`: `success_rate`
- `BroadcastService`: `get_users`, `get_count`, `set_pending`, `get_pending`, `clear_pending`, `broadcast`

### src/services/captcha_service.py

- `CaptchaService`: `set_lock`, `get_solved`, `set_solved`

### src/services/chat_activity_service.py

- `ChatActivityService`: `update_activity`, `start_monitoring`, `stop_monitoring`, `get_chat_activity`, `get_active_chats_count`, `get_all_chat_ids`, `remove_chat`, `update_user_activity`, `get_active_user_ids`

### src/services/chat_settings_service.py

- `ChatSettingsService`: `set_setting`, `get_setting`, `delete_setting`

### src/services/comment_campaign_service.py

- `CommentCampaignService`: `now`, `transaction`, `ensure_indexes`, `initialize`, `health_snapshot`, `close_failed_inbox`, `start`, `stop`, `campaign_id`, `observe_post`, `observe_root`, `collect`, `capture`, `drain_inbox`, `note_deleted`, `mark_deleted`, `ingest`, `claim_work`, `fence`, `update_owned`, `touch`, `plan_batch`, `reward_operations`, `debit_bank`, `credit`, `payout_batch`, `start_text`, `final_text`, `block_final_delivery`, `deliver_final`, `process`, `resume_pending_reward`, `tick`, `run`

### src/services/crypto_service.py

- `CryptoService`: `get_top_10_message`, `get_price_message`, `get_calculator_message`, `format_price_message`

### src/services/daily_pet_service.py

- `DailyPetService`: `claim`, `owned`, `activate`, `reserve_notice`, `mark_delivered`, `widget_action`, `tap`

### src/services/daily_service.py

- `DailyService`: `claim_daily`, `can_claim`, `settle_hedgehog`

### src/services/digest_service.py

- `DigestService`: `add_message`, `get_messages`, `get_new_messages_count`, `mark_digest_done`, `format_for_llm`, `get_stats`, `get_active_users`, `get_topics`, `get_time_range`, `can_generate`, `generate_digest`, `trigger_digest`, `chat_sage_reply`, `ask_sage`, `get_vanga_prediction`, `generate_short_reaction`, `ask_sensei`, `roast_user`, `generate_vestnik`, `trigger_vestnik`

### src/services/duel_service.py

- `DuelService`: `shutdown`, `create_duel`, `process_decision`, `process_move`, `process_utility`, `surrender`

### src/services/economy_service.py

- `EconomyService`: `process_message_reward`, `admin_add_coins`, `upgrade_katana`, `admin_add_xp`, `confiscate_on_ban`, `buy_katana`, `get_bank_stats`, `get_bank_balance`, `distribute_zov_reward`, `distribute_boss_reward`, `process_boss_loss`, `process_game_win`, `fire_drop`

### src/services/exchange_service.py

- `ExchangeService`: `coins_to_ticket`, `ticket_to_coins`, `get_exchange_rates`

### src/services/fly_service.py

- `FlyService`: `ensure_indexes`, `transaction`, `reserve`

### src/services/hedgehog_service.py

- `HedgehogService`: `ensure_indexes`, `issue`, `owned`, `start`, `tap`, `finish`

### src/services/level_service.py

- `LevelService`: `get_level`, `get_level_name`, `get_xp_for_next_level`, `get_progress`, `check_level_up`

### src/services/lottery_service.py

- `LotteryService`: `run_lottery`, `admin_add_ticket`, `admin_burn_user_tickets`, `add_ticket`, `get_lottery_stats`

### src/services/maintenance_service.py

- `MaintenanceService`: `enable`, `disable`, `is_enabled`, `get_state`, `get_random_phrase`, `get_suffering_time`

### src/services/message_cleanup_service.py

- `MessageCleanupService`: `cleanup_previous`, `set_last`

### src/services/moderation_service.py

- `ModerationService`: `load_muted_users_cache`, `handle_user_left`, `ban_user`, `unban_user`, `unban_if_active_in_chat`, `get_banned_users`, `unban_all_users`, `mute_user`, `unmute_user`, `is_muted`, `get_muted_users`, `mute_user_by_username`, `unmute_user_by_username`

### src/services/paid_hedgehog_service.py

- `PaidHedgehogService`: `available`, `transaction`, `quote`, `bind_notice`, `checkout`, `receive`, `pending`, `settle`, `tap`

### src/services/popugai_service.py

- `PopugaiService`: `ensure_indexes`, `get_reply_chance`, `set_reply_chance`, `add_media`, `get_random_media`, `reserve_reply`

### src/services/quiz_service.py

- `QuizService`: `run_quiz_loop`, `add_question`, `start_quiz`, `stop_quiz`, `is_quiz_running`, `get_next_question`, `check_answer`, `generate_summary`

### src/services/referral_service.py

- `ReferralService`: `process_referral`, `get_stats`, `get_top`, `get_referrals_list`

### src/services/sensei_check_service.py

- `SenseiCheckService`: `create_check`, `activate_check`, `burn_check`, `get_all_checks`, `get_check_info`, `get_check_public_view`, `get_advanced_stats`, `admin_delete_check`

### src/services/slots_service.py

- `SlotsService`: `play_slots`

### src/services/star_coin_service.py

- `StarCoinService`: `check`, `pending`, `receive`

### src/services/stats_service.py

- `StatsService`: `get_admin_stats`, `reset_new_season`, `reset_sansara`

### src/services/throttle_service.py

- `ThrottleService`: `ensure_indexes`, `throttle`

### src/services/trade_service.py

- `TradeService`: `play_game`

### src/services/user_service.py

- `UserService`: `get_profile`, `get_or_create`, `get_user_by_username`, `get_random_user`, `process_referral`, `get_active_users`, `get_top_by_xp`, `get_top_by_coins`, `get_top_by_messages`, `get_top_by_tickets`, `get_ticket_holders_paginated`, `get_top_by_streak`, `get_top_by_katana`, `get_all_for_broadcast`, `admin_add_katana`

### src/services/vk_music.py

- `VKMusicService`: `search`

### src/services/xrocket_service.py

- `XRocketService`: `transfer`, `get_balance`

