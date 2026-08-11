import aiohttp
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class AIProvider:
    name: str
    url: str
    api_key: str
    model: str

class AIProviderFactory:
    def __init__(self, settings):
        self.providers: Dict[str, AIProvider] = {
            "groq": AIProvider(
                name="Groq",
                url="https://api.groq.com/openai/v1/chat/completions",
                api_key=settings.groq_api_key, 
                model="llama-3.3-70b-versatile"
            ),
            "openrouter": AIProvider(
                name="OpenRouter",
                url="https://openrouter.ai/api/v1/chat/completions",
                api_key="sk-or-v1-...", 
                model="meta-llama/llama-3.2-3b-instruct:free"
            ),
            "sambanova": AIProvider(
                name="SambaNova",
                url="https://api.sambanova.ai/v1/chat/completions",
                api_key=settings.sambanova_api_key,
                model="Meta-Llama-3.1-70B-Instruct"
            ),
             "gemini": AIProvider(
                name="Gemini",
                url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}",
                api_key=settings.gemini_api_key,
                model="gemini-1.5-flash"
            )
        }
        self.active_provider = "groq" # Default as requested

    def get_provider(self, name: str = None) -> AIProvider:
        name = name or self.active_provider
        return self.providers.get(name)

    async def generate_text(self, system: str, user: str, provider_name: str = None, max_tokens: int = 2000) -> str:
        provider = self.get_provider(provider_name)
        if not provider:
            return "❌ Unknown provider"

        # Gemini has specific payload structure
        if provider.name == "Gemini":
            payload = {
                "contents": [{
                    "parts": [{"text": user}]
                }],
                "system_instruction": {
                    "parts": [{"text": system}]
                },
                "generationConfig": {
                    "temperature": 0.9,
                    "maxOutputTokens": max_tokens
                }
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(provider.url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["candidates"][0]["content"]["parts"][0]["text"]
                        else:
                            error_text = await resp.text()
                            return f"❌ Gemini error: {resp.status} - {error_text}"
            except Exception as e:
                return f"❌ Error: {e}"

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }

        # OpenAI-compatible payload
        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.9,
            "max_tokens": max_tokens
        }
        
        # SambaNova specific adjustments if needed (usually openai compatible)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(provider.url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await resp.text()
                        return f"❌ {provider.name} error: {resp.status} - {error_text}"
        except Exception as e:
            return f"❌ Error: {e}"
