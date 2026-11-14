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
                model="openai/gpt-oss-120b"
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
        self.vision_model = getattr(settings, "groq_vision_model", "")

    def get_provider(self, name: str = None) -> AIProvider:
        name = name or self.active_provider
        return self.providers.get(name)

    async def generate_text(self, system: str, user: str, provider_name: str = None, max_tokens: int = 2000, json_mode: bool = False) -> str:
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
        
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
            if provider.name == 'Groq' and provider.model.startswith('openai/gpt-oss'):
                payload['reasoning_effort'] = 'low'

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


    async def generate_vision(self, system, user, image):
        """Use configured Groq vision model; never forward Telegram file URLs/tokens."""
        import base64
        provider = self.get_provider('groq')
        if not self.vision_model or not provider.api_key:
            raise ValueError('vision_not_configured')
        if not image or len(image) > 4 * 1024 * 1024:
            raise ValueError('vision_image_size')
        payload = {'model': self.vision_model, 'max_tokens': 1000, 'temperature': 0.5,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': [
                {'type': 'text', 'text': user},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode('ascii')}}]}]}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as session:
            async with session.post(provider.url, headers={'Authorization': f'Bearer {provider.api_key}'}, json=payload) as response:
                if response.status != 200:
                    # Provider bodies may contain request data. Do not echo/log them.
                    raise RuntimeError('vision_provider_rejected')
                data = await response.json()
        result = data['choices'][0]['message']['content']
        if not isinstance(result, str) or not result.strip():
            raise ValueError('vision_empty_response')
        return result
