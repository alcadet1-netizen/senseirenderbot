
import sys
import os
from pathlib import Path

# Add current directory to sys.path
sys.path.append(os.getcwd())

try:
    from src.bot.handlers.music import MAX_DURATION_SEC, _get_yt_dlp_opts, TEMP_DIR
    print(f"MAX_DURATION_SEC: {MAX_DURATION_SEC}")
    
    opts = _get_yt_dlp_opts(str(TEMP_DIR / "test.mp3"))
    print("opts keys:", list(opts.keys()))
    
    if 'cookiesfrombrowser' in opts:
        print("FAIL: cookiesfrombrowser is still present")
    else:
        print("PASS: cookiesfrombrowser is absent")
        
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
