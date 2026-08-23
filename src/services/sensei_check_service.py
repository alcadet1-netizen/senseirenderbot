async def burn_check(self, code: str, user_id: int) -> tuple[bool, str, float]:
        """Сжечь чек (вернуть средств создателю)."""

        check = await self._get_check(code)
        if not check:
            return False, "Чек не найден", 0.0

        if check["creator_id"] != user_id:
            return False, "Вы не являетесь создателем этого чека", 0.0

        if not check.get("is_active", False):
            return False, "Чек уже неактивен", 0.0

        # Вычисляем сумму возврата
        amount_ton = Decimal(str(check["amount_ton"]))
        remaining_activations = check["activation_limit"] - check["activations_used"]
        refund_ton = amount_ton * Decimal(str(remaining_activations))

        # Деактивируем чек
        await self._repo.deactivate(check)

        if refund_ton > 0:
            success = await self.xrocket_service.transfer(
                user_id=user_id,
                currency="GRAM",
                amount=float(refund_ton)
            )
            if not success:
                logger.error(f"Failed to refund {refund_ton} GRAM for check {code}")
                return False, "🔌 Произошла ошибка при возврате средств P2P.", float(refund_ton)

        await self._cache_delete(f"scheck:info:{code}")
        return True, "🔥 Чек успешно сожжен!", float(refund_ton)

    async def get_all_checks(self) -> List[Dict[str, Any]]:
        """Получить все чеки (для админского списка)."""
        checks, _ = await self._repo.get_all_checks()
        # Convert to plain dictionaries to avoid issues with decorated objects
        return [dict(check) if not isinstance(check, dict) else check for check in checks]

    async def _cache_set(self, key: str, value: str, ex: int = 3600):