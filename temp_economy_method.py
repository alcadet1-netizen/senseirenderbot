
    async def fire_drop(
        self,
        sender_id: int,
        amount: float,
        recipients_data: list[tuple[int, float]], # list of (user_id, amount)
        is_admin: bool = False
    ) -> dict:
        """Раздача монет (Fire Drop)."""
        lock = DistributedLock(self.redis)
        
        # Блокируем отправителя, если это не админ
        lock_key = f"fire_drop:{sender_id}" if not is_admin else "fire_drop:admin"
        
        async with lock.acquire(lock_key):
            uow = UnitOfWork(self.session_factory)
            
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                total_amount = sum(a for _, a in recipients_data)
                
                # Списание средств
                if is_admin:
                    bank_balance = await bank_repo.get_balance()
                    if bank_balance < total_amount:
                        return {"success": False, "reason": "insufficient_funds_bank", "balance": bank_balance}
                    await bank_repo.withdraw(total_amount)
                else:
                    sender = await user_repo.get_by_id(sender_id)
                    if not sender:
                         return {"success": False, "reason": "user_not_found"}
                    if sender.coins < total_amount:
                        return {"success": False, "reason": "insufficient_funds", "balance": sender.coins}
                    
                    sender.coins -= total_amount
                    await tx_repo.create(
                        user_id=sender_id,
                        tx_type=TransactionType.SPEND.value, # Или добавить тип FIRE_DROP
                        coins_change=-total_amount,
                        description=f"Fire Drop sent to {len(recipients_data)} users"
                    )

                # Начисление средств получателям
                processed_count = 0
                for uid, amt in recipients_data:
                    recipient = await user_repo.get_by_id(uid)
                    if recipient:
                        recipient.coins += amt
                        processed_count += 1
                        # Создаем транзакцию для получателя
                        await tx_repo.create(
                            user_id=uid,
                            tx_type=TransactionType.GIFT.value, # Или FIRE_DROP_RECEIVED
                            coins_change=amt,
                            description=f"Fire Drop received from {'Admin' if is_admin else sender_id}"
                        )
                
                await uow.commit()
                
                return {"success": True, "processed": processed_count}
