
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    import yt_dlp
    from src.bot.handlers.music import _get_yt_dlp_opts, TEMP_DIR
except ImportError:
    print("yt_dlp not installed or module not found")
    sys.exit(1)

def test_init():
    print("Testing yt-dlp init...")
    output_template = str(TEMP_DIR / "test_%(id)s.%(ext)s")
    opts = _get_yt_dlp_opts(output_template)
    print(f"Options: {opts}")
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            print("yt-dlp initialized successfully")
    except Exception as e:
        print(f"Failed to initialize yt-dlp: {e}")

if __name__ == "__main__":
    test_init()
