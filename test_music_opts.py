
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.getcwd())

try:
    import yt_dlp
    from src.bot.handlers.music import _get_yt_dlp_opts, TEMP_DIR
except ImportError:
    print("yt_dlp not installed or module not found")
    sys.exit(1)

def test_opts():
    print("Testing yt-dlp options...")
    output_template = str(TEMP_DIR / "test_%(id)s.%(ext)s")
    opts = _get_yt_dlp_opts(output_template)
    
    print("Http headers present:", 'http_headers' in opts)
    print("Extractor args present:", 'extractor_args' in opts)
    
    if 'http_headers' in opts:
        print("User-Agent:", opts['http_headers'].get('User-Agent'))
    
    if 'extractor_args' in opts:
        print("Youtube player client:", opts['extractor_args'].get('youtube', {}).get('player_client'))

if __name__ == "__main__":
    test_opts()
