"""Reviewed admin command catalogue; plain text, never clipped decorative frames."""

SECTIONS = (
    ('Справка и диагностика', (
        '/adminhelp · /senseiadmin — полный список команд администратора бота.',
        '/health · /status — состояние сервиса.',
        '/senseichats · /chats · /группы — список чатов и проверка доступности.',
        '/adminstats — статистика администратора.',
        '/topticket — рейтинг билетов.',
        '/senseiwidgetcheck [here] — тест native widget: в личке; here — явно в группе.',
        '/ega — демонстрация Ежа без наград, в личке.',
        '/widgethtml — HTML-диагностика карточек, в личке.',
        '/senseicopycheck — проверка копирования обычного текста в личке (доступна всем).',
        '/cancel — отменить текущий административный ввод.',
    )),
    ('Награды и модерация', (
        'reply = отправить команду ответом на сообщение нужного пользователя.',
        '/addcoin сумма — выдать монеты, reply.',
        '/addxp количество — выдать XP, reply.',
        '/addticket [количество] — выдать билеты, reply; по умолчанию 1, максимум 100.',
        '/addkatana длина — выдать катану указанной длины, reply.',
        '/ticketburn — сжечь все билеты пользователя, reply. Осторожно!',
        '/bonussensei [количество] — розыгрыш билетов.',
        '/banlist — список заблокированных.',
        '/ban · /бан — заблокировать пользователя; аргументы/выбор — по подсказке команды.',
        '/unban · /разбанить — разблокировать пользователя.',
        '/amnistia — массовая амнистия. Осторожно!',
        '/senseimuteon · /addmute · /mute — мут; параметры — по подсказке команды.',
        '/senseimuteoff · /offmute · /unmute — снять мут.',
    )),
    ('Боссы и контент', (
        '/senseiboss [time] — запуск/настройка босса.',
        '/killboss — завершить босса.',
        '/boss_settings — текущие настройки наград.',
        '/boss_chance число — шанс выпадения, от 0 до 1.',
        '/boss_reward min max — диапазон награды.',
        '/boss_pool лимит — лимит пула.',
        '/boss_reset_pool — сбросить использованный пул. Осторожно!',
        '/senseicheck — управление чеками через меню.',
        '/addquestion · /addquest — добавить вопрос викторины, в личке.',
        '/skip — пропустить изображение при добавлении вопроса.',
        '/senseiviktorina — запустить викторину в группе.',
        '/stopquiz — остановить викторину в группе.',
        '/senseivesti · /вестник · /digest — меню дайджеста в группе.',
        '/senseivestnik — сводка вестника в группе.',
        '/senseistat · /статс · /stats — статистика чата (также пользовательская команда).',
        '/draw промпт — генерация изображения (также пользовательская команда).',
    )),
    ('Рассылки и система', (
        '/govori — отправка сообщения от бота, в личке.',
        '/broadcast — меню рассылки.',
        '/senseizov — созыв участников.',
        '/senseinezov — отмена созыва.',
        '+fire сумма [валюта] — текстовый триггер раздачи, БЕЗ слеша.',
        '/senseivisual — выбор оформления.',
        '/senseinewseasons — новый сезон. Осторожно!',
        '/senseisansara — сансара. Осторожно!',
        '/sensei — статус обслуживания.',
        '/sensei work [причина] — включить обслуживание.',
        '/sensei update|fix|deploy|db — пресет причины обслуживания (не запускает деплой).',
        '/sensei минуты [причина] — обслуживание на указанное время.',
        '/sensei done — завершить обслуживание.',
    )),
    ('Настройки администраторов чата', (
        'Права проверяются отдельно каждой командой; админ бота и админ группы — разные роли.',
        '/offexit · /onexit — выключить / включить уведомления о выходе.',
        '/welcomeon · /welcomeoff — приветствия.',
        '/autobanon · /autobanoff — автобан.',
        '/uvedomleniaon · /uvedomleniaoff — уведомления.',
        '/captchaon · /captchaoff — капча.',
        '/popugai [процент|off] — шанс ответа попугая.',
        '/senseifly on|off|status — редкие реакции; только администратор самой группы.',
        '/senseifly без аргументов — визуальная лаборатория, доступна всем.',
        'Общие пользовательские команды: /senseihelp. В группах бот должен быть администратором.',
    )),
)


def admin_help_pages():
    """Whole sections, bounded well below Telegram's 4096 UTF-16 unit limit."""
    pages = []
    current = '🛡 Команды администратора\nДоступ к этой справке: администраторы бота (ADMIN_IDS).'
    for title, rows in SECTIONS:
        block = '\n\n' + title.upper() + '\n' + '\n'.join(rows)
        if len((current + block).encode('utf-16-le')) // 2 > 2800:
            pages.append(current)
            current = '🛡 Команды администратора — продолжение' + block
        else:
            current += block
    pages.append(current)
    return [f'{page}\n\nСтраница {i}/{len(pages)}' for i, page in enumerate(pages, 1)]
