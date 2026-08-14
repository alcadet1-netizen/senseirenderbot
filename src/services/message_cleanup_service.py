class MessageCleanupService:
    def __init__(self):
        self.ttl = 86400  # 24 hours (unused)

    async def cleanup_previous(self, chat_id: int, user_id: int, key: str, bot):
        """
        Удаляет предыдущее сообщение бота для данного ключа (команды).
        (Отключено по требованию: все сообщения должны оставаться в чате)
        """
        # Logic disabled
        pass

    async def set_last(self, chat_id: int, user_id: int, key: str, msg_id: int):
        """
        Сохраняет ID последнего сообщения.
        (Отключено по требованию)
        """
        # Logic disabled
        pass
