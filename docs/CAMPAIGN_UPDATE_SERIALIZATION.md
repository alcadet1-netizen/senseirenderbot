# Campaign ingress: aiogram Default serialization

Симптом: PydanticSerializationError для aiogram.client.default.Default внутри CampaignInbox.put. Polling admission намеренно удерживает offset до durable commit; ошибка повторяется и блокирует продвижение потока. Сообщение «Mongo admission failed» в данном случае не доказывает сбой MongoDB: payload не удалось подготовить ещё до записи.

Воспроизведение: входящий Update с message.link_preview_options={is_disabled:false} либо preview options в reply_to_message. Остальные неуказанные поля LinkPreviewOptions имеют служебные Default, не поддерживаемые прямым model_dump_json(exclude_none=True).

Исправление: aiogram.utils.serialization.deserialize_telegram_object(..., include_api_method_name=False) преобразует объект в JSON-совместимые данные, опуская неразрешённые глобальные defaults. Не передаются default настройки рабочего бота: входящее сообщение не должно приобретать его предпочтения исходящих сообщений. JSON записывается в прежнее поле payload Mongo очереди, схема/ключ bot_id:update_id не меняется. Существующие payload продолжают читаться Update.model_validate_json.

Не используется default=str, пропуск неизвестного update или продвижение offset после ошибки. Неизвестный несериализуемый объект или InputFile по-прежнему отклоняет admission. Тексты, ID, false, вложенный parent и forward_origin проверены roundtrip-тестами. Входящие Telegram даты представлены целыми Unix timestamps штатным сериализатором aiogram; это не byte-identical копия исходного JSON.

Регрессии:
- прямой pydantic dump действительно падает на реальном Default в модели;
- штатный сериализатор сохраняет false/данные и не подставляет default рабочего Bot;
- неизвестный объект не строкифицируется и не записывается;
- реальный aiogram polling listener продвигается только после сохранения событий с preview;
- общие fake/CI replica-set CampaignCases: capture, дедупликация, replay root/комментария и ack.

Production Mongo/очередь не очищались, updates не сбрасывались, drop_pending_updates не вызывается. После deployment ожидающий в Telegram update может пройти исправленный admission при повторной доставке, если Telegram ещё хранит его. Перезапуск старой версии сам по себе дефект не исправляет; Telegram не хранит обновления бесконечно. Боевой backlog/live восстановление отдельно не проверены.
