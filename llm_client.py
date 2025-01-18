import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    content: str
    tokens_used: int
    finish_reason: str

class LLMClient:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()

    async def generate(self, prompt: str, **kwargs) -> AsyncGenerator[LLMResponse, None]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            **kwargs
        }

        try:
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"LLM request failed: {response.status}")
                    return

                async for chunk in response.content:
                    if not chunk:
                        continue

                    try:
                        data = json.loads(chunk.decode('utf-8'))
                        if "choices" in data:
                            choice = data["choices"][0]
                            yield LLMResponse(
                                content=choice.get("message", {}).get("content", ""),
                                tokens_used=data.get("usage", {}).get("total_tokens", 0),
                                finish_reason=choice.get("finish_reason", "stop")
                            )
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON chunk received")
                    except KeyError:
                        logger.warning("Invalid response format received")

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            raise

    async def generate_sync(self, prompt: str, **kwargs) -> LLMResponse:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            **kwargs
        }

        try:
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"LLM request failed: {response.status}")
                    return None

                data = await response.json()
                if "choices" in data:
                    choice = data["choices"][0]
                    return LLMResponse(
                        content=choice.get("message", {}).get("content", ""),
                        tokens_used=data.get("usage", {}).get("total_tokens", 0),
                        finish_reason=choice.get("finish_reason", "stop")
                    )
                return None

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            raise

    async def generate_story_prompt(self, params: dict) -> str:
        """Generate a structured story prompt based on genre and language
        
        Args:
            params: Dictionary containing:
                - genre: The story genre (e.g., Fantasy, Sci-Fi)
                - language: The language for the story (e.g., 'pt-BR')
        
        Returns:
            A formatted prompt string for the LLM
        """
        genre = params.get('genre', 'Fantasy')
        language = params.get('language', 'pt-BR')
        
        return f"""Generate 3 creative story options in {language} for a {genre} narrative. Each option should include:
1. A unique title
2. A 2-3 sentence summary
3. 2-3 main characters with brief descriptions
4. 1-2 key locations with brief descriptions

Format the response as a JSON array with the following structure:
{{
    "stories": [
        {{
            "title": "Story Title",
            "summary": "Story summary...",
            "characters": [
                {{
                    "name": "Character Name",
                    "description": "Character description..."
                }}
            ],
            "locations": [
                {{
                    "name": "Location Name",
                    "description": "Location description..."
                }}
            ]
        }}
    ]
}}"""
