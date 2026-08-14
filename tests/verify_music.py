import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

from src.bot.handlers.music import cmd_music, music_cache

async def verify_music():
    print("🧪 Verifying Music Command...")

    # Mock message
    msg = AsyncMock()
    msg.from_user.id = 123456
    msg.text = "Найти test song"
    msg.answer = AsyncMock()
    msg.answer_audio = AsyncMock()
    msg.answer.return_value = AsyncMock() # For status_msg
    msg.answer.return_value.edit_text = AsyncMock()
    msg.answer.return_value.delete = AsyncMock()
    
    bot = AsyncMock()

    # 1. Test Cache Hit
    print("\n1. Testing Cache Hit:")
    music_cache["test song"] = "file_id_123"
    await cmd_music(msg, bot)
    
    if msg.answer_audio.called:
        args, kwargs = msg.answer_audio.call_args
        if kwargs.get('audio') == "file_id_123":
            print("✅ Cache hit worked")
        else:
            print(f"❌ Cache hit failed. Args: {kwargs}")
    else:
        print("❌ Cache hit: answer_audio not called")

    # 2. Test API (Mocked)
    print("\n2. Testing API Search:")
    msg.reset_mock()
    del music_cache["test song"]
    
    # Mock aiohttp
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {
            'audio': [{'url': 'http://example.com/song.mp3'}]
        }
        mock_get.return_value.__aenter__.return_value = mock_resp
        
        await cmd_music(msg, bot)
        
        if msg.answer_audio.called:
            args, kwargs = msg.answer_audio.call_args
            if kwargs.get('audio') == 'http://example.com/song.mp3':
                print("✅ API search worked")
            else:
                 print(f"❌ API search failed. Got: {kwargs.get('audio')}")
        else:
             print("❌ API search: answer_audio not called")

    # 3. Test yt-dlp (Mocked)
    print("\n3. Testing yt-dlp Fallback:")
    msg.reset_mock()
    
    # Force API failure
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_get.return_value.__aenter__.return_value = mock_resp
        
        # Mock run_in_executor and os operations
        loop = asyncio.get_event_loop()
        with patch.object(loop, 'run_in_executor', new=AsyncMock()) as mock_exec:
             mock_exec.return_value = {'entries': [{'id': 'test_id', 'title': 'Test Title', 'ext': 'mp3'}]}
             
             with patch('os.path.exists') as mock_exists:
                 mock_exists.return_value = True # Simulate file exists
                 
                 with patch('src.bot.handlers.music.FSInputFile') as mock_file:
                     await cmd_music(msg, bot)
                     
                     if msg.answer_audio.called:
                         print("✅ yt-dlp fallback worked (mocked)")
                     else:
                         print("❌ yt-dlp fallback failed")

if __name__ == "__main__":
    asyncio.run(verify_music())
