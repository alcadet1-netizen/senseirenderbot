import aiohttp
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class VKMusicService:
    def __init__(self, token: str):
        self.token = token
        self.api_url = "https://api.vk.com/method/"
        self.v = "5.131"
        # User-Agent, imitating official app or browser to avoid restrictions
        self.user_agent = "VKAndroidApp/5.52-4543 (Android 5.1.1; SDK 22; x86; unknown Android SDK built for x86; en; 320x240)"

    async def search(self, query: str, count: int = 5) -> List[Dict]:
        """
        Asynchronous search for music in VK.
        Returns a list of dictionaries with track information.
        """
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    "access_token": self.token,
                    "v": self.v,
                    "q": query,
                    "count": count,
                    "sort": 2,  # 2 - by popularity
                    "auto_complete": 1
                }
                headers = {
                    "User-Agent": self.user_agent
                }
                async with session.get(f"{self.api_url}audio.search", params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"VK API returned status {resp.status}")
                        return []
                        
                    data = await resp.json()
                    
                    if "error" in data:
                        error_msg = data['error'].get('error_msg', 'Unknown error')
                        logger.error(f"VK API Error: {error_msg}")
                        return []
                        
                    items = data.get("response", {}).get("items", [])
                    tracks = []
                    for item in items:
                        if not item.get("url"):
                            continue
                            
                        duration = item.get("duration", 0)
                        minutes = duration // 60
                        seconds = duration % 60
                        duration_str = f"{minutes}:{seconds:02d}"
                        
                        # Clean up strings
                        artist = item.get("artist", "Unknown")
                        title = item.get("title", "Untitled")
                        
                        tracks.append({
                            "artist": artist,
                            "title": title,
                            "duration": duration,
                            "duration_str": duration_str,
                            "url": item.get("url"),
                            "id": f"{item.get('owner_id')}_{item.get('id')}",
                            "full_title": f"{artist} - {title}"
                        })
                    return tracks
            except Exception as e:
                logger.error(f"VK Search Error: {e}")
                return []
