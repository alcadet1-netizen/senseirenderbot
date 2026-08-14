import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.services.duel_service import DuelService, Duel

async def test_timer():
    container = MagicMock()
    service = DuelService(container)
    
    # Mock methods
    service._update_arena = AsyncMock()
    service._update_dm = AsyncMock()
    service._resolve_round_logic = AsyncMock()
    
    duel_id = 1
    duel = Duel(
        id=duel_id,
        challenger_id=10,
        opponent_id=20,
        bet=100,
        arena_chat_id=999,
        bot=MagicMock(),
        container=container
    )
    
    # Set duration to 5 seconds to trigger one update loop
    # Logic: min(4, left) -> sleep 4 -> update -> sleep remaining -> finish
    duel.round_deadline_mono = time.monotonic() + 5
    duel.lock = asyncio.Lock()
    
    service.duels[duel_id] = duel
    
    print("Starting timeout task (5s duration)...")
    task = asyncio.create_task(service._round_timeout(duel_id))
    
    await asyncio.sleep(6)
    
    print(f"Update Arena call count: {service._update_arena.call_count}")
    print(f"Resolve call count: {service._resolve_round_logic.call_count}")
    
    if service._update_arena.call_count >= 1:
        print("SUCCESS: Timer updated arena.")
    else:
        print("FAILURE: Timer did not update arena.")
        
    if service._resolve_round_logic.call_count == 1:
        print("SUCCESS: Round resolved.")
    else:
        print("FAILURE: Round not resolved.")

if __name__ == "__main__":
    asyncio.run(test_timer())
