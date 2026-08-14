
import sys
import os

# Add src to path
sys.path.append('/app')

try:
    from src.bot.handlers import trade
    from src.core.visuals import Visuals
    from src.core.config import settings
    
    print(f"✅ Trade handler imported: {trade}")
    print(f"✅ Visuals.get_trade_animation exists: {hasattr(Visuals, 'get_trade_animation')}")
    print(f"✅ Visuals.get_trade_result exists: {hasattr(Visuals, 'get_trade_result')}")
    print(f"✅ Settings.TRADE_COST: {settings.trade_cost}")
    print(f"✅ Settings.TRADE_WIN_CHANCE: {settings.trade_win_chance}")
    
except Exception as e:
    print(f"❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()
