
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.services.duel_service import DuelService, Duel, DuelMoveCb
from src.core.container import Container

async def test_duel_flow():
    print("Testing Duel Flow...")
    
    # Mock Container
    container = MagicMock(spec=Container)
    
    # We don't need to patch UOW if we mock the methods that use it.
    service = DuelService(container)
    
    # Mock DB methods to bypass DB
    service.escrow = AsyncMock(return_value=True)
    service._process_payout = AsyncMock(return_value=(200, 0, 0))
    # We also need to mock _get_names_map because resolve_round uses it
    service._get_names_map = AsyncMock(return_value={1: "UserOne", 2: "UserTwo"})
    
    # Mock Bot
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock(message_id=123)
    bot.edit_message_text.return_value = True
    
    # 1. Create Duel
    print("1. Creating duel...")
    duel = await service.create_duel(bot, challenger_id=1, opponent_id=2, bet=100, chat_id=999)
    print(f"Duel created: ID={duel.id}, Flavor={duel.flavor[0]}")
    
    # 2. Accept
    print("2. Accepting duel...")
    res = await service.process_decision(duel.id, 2, 'a')
    print(f"Decision result: {res}")
    assert duel.accepted
    assert duel.round == 1
    
    # 3. Round 1 Moves
    print("3. Making moves (Round 1)...")
    res1 = await service.process_move(duel.id, 1, "hit_l")
    res2 = await service.process_move(duel.id, 2, "dodge_r")
    await service.process_move(duel.id, 1, "dodge_l")
    await service.process_move(duel.id, 2, "hit_r") 
    
    # Now round should resolve.
    await asyncio.sleep(0.1)
    
    print(f"Round 1 Result: Hits {duel.hits}")
    # 1 attacks 2: 1(hit_l) vs 2(dodge_r) -> Hit
    # 2 attacks 1: 2(hit_r) vs 1(dodge_l) -> Hit
    assert duel.hits[1] == 1
    assert duel.hits[2] == 1
    assert duel.round == 2
    
    # 4. Surrender
    print("4. Surrender...")
    res_sur = await service.process_move(duel.id, 1, "sur")
    print(f"Surrender result: {res_sur}")
    
    assert duel.id not in service.duels
    print("Duel finished and cleaned up.")
    
    print("\nSUCCESS: Duel flow verified.")

if __name__ == "__main__":
    asyncio.run(test_duel_flow())
