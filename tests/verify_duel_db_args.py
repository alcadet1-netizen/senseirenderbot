
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.services.duel_service import DuelService, Duel
from src.core.container import Container
from src.infra.database.models import TransactionType

async def verify_duel_args():
    print("🚀 Verifying DuelService DB arguments...")
    
    # Mock Container and DB
    container = MagicMock(spec=Container)
    
    # Mock Session and Repositories
    session = AsyncMock()
    uow = MagicMock()
    uow.session = session
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    
    container.session_factory = MagicMock(return_value=uow)
    
    # We need to patch the Repositories instantiated inside the methods
    # Since they are instantiated like: user_repo = UserRepository(uow.session)
    # We can patch the classes in the module
    
    from src.services import duel_service
    
    # Mock Repositories
    mock_tx_repo = AsyncMock()
    mock_user_repo = AsyncMock()
    mock_bank_repo = AsyncMock()
    
    # Setup User Repo return values
    mock_user = MagicMock()
    mock_user.coins = 1000.0
    mock_user_repo.get_by_id.return_value = mock_user
    
    # Patch the classes
    original_tx_repo = duel_service.TransactionRepository
    original_user_repo = duel_service.UserRepository
    original_bank_repo = duel_service.BankRepository
    
    duel_service.TransactionRepository = MagicMock(return_value=mock_tx_repo)
    duel_service.UserRepository = MagicMock(return_value=mock_user_repo)
    duel_service.BankRepository = MagicMock(return_value=mock_bank_repo)
    
    try:
        service = DuelService(container)
        
        # 1. Verify escrow
        print("\nTesting escrow...")
        duel = Duel(
            id=123, 
            challenger_id=1, 
            opponent_id=2, 
            bet=100, 
            arena_chat_id=999, 
            bot=AsyncMock(), 
            container=container
        )
        
        await service.escrow(duel)
        
        # Verify calls to tx_repo.create
        # We expect 2 calls (one for each user)
        assert mock_tx_repo.create.call_count == 2
        
        # Check arguments of the last call
        call_args = mock_tx_repo.create.call_args
        # create(self, user_id, tx_type, xp_change=0, coins_change=0.0, description=None)
        # We passed keywords: user_id, tx_type, coins_change, description
        # args: (uid, 'purchase')
        # kwargs: coins_change=-100.0, description='Duel #123'
        
        args, kwargs = call_args
        print(f"Escrow call args: {args}, kwargs: {kwargs}")
        
        assert kwargs.get('coins_change') == -100.0, f"Expected coins_change -100.0, got {kwargs.get('coins_change')}"
        assert kwargs.get('description') == "Duel #123", f"Expected description 'Duel #123', got {kwargs.get('description')}"
        assert isinstance(kwargs.get('coins_change'), float), "coins_change must be float"
        
        print("✅ Escrow arguments correct.")
        
        # 2. Verify _process_payout (Winner)
        print("\nTesting _process_payout (Winner)...")
        mock_tx_repo.reset_mock()
        
        # Mock winner user
        mock_user_repo.get_by_id.return_value = mock_user
        
        await service._process_payout(duel, winner_id=1, is_surrender=False)
        
        # Expect 1 call for winner
        assert mock_tx_repo.create.call_count == 1
        args, kwargs = mock_tx_repo.create.call_args
        print(f"Payout call args: {args}, kwargs: {kwargs}")
        
        # Payout = bet*2 - fee (5%) = 200 - 10 = 190
        assert kwargs.get('coins_change') == 190.0
        assert kwargs.get('description') == "Duel win #123"
        
        print("✅ Payout arguments correct.")
        
        # 3. Verify _process_payout (Surrender Refund)
        print("\nTesting _process_payout (Surrender)...")
        mock_tx_repo.reset_mock()
        
        await service._process_payout(duel, winner_id=2, is_surrender=True)
        
        # Expect 2 calls: Winner (payout) + Loser (refund)
        assert mock_tx_repo.create.call_count == 2
        
        # Check last call (loser refund)
        # Winner gets remaining: 200 - 10(fee) - 50(refund) = 140
        # Loser gets refund: 50 (half bet)
        
        calls = mock_tx_repo.create.call_args_list
        loser_call = calls[1]
        l_args, l_kwargs = loser_call
        print(f"Surrender Refund call args: {l_args}, kwargs: {l_kwargs}")
        
        assert l_kwargs.get('coins_change') == 50.0
        assert l_kwargs.get('description') == "Duel surrender refund #123"
        assert l_args[1] == TransactionType.TRANSFER_IN.value
        
        print("✅ Surrender Refund arguments correct.")
        
        # 4. Verify _refund_both
        print("\nTesting _refund_both...")
        mock_tx_repo.reset_mock()
        
        await service._refund_both(1, 2, 100)
        
        assert mock_tx_repo.create.call_count == 2
        args, kwargs = mock_tx_repo.create.call_args
        print(f"RefundBoth call args: {args}, kwargs: {kwargs}")
        
        assert kwargs.get('coins_change') == 100.0
        assert kwargs.get('description') == "Duel refund"
        assert args[1] == TransactionType.TRANSFER_IN.value
        
        print("✅ RefundBoth arguments correct.")
        
    finally:
        # Restore patched classes
        duel_service.TransactionRepository = original_tx_repo
        duel_service.UserRepository = original_user_repo
        duel_service.BankRepository = original_bank_repo

if __name__ == "__main__":
    asyncio.run(verify_duel_args())
