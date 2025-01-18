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
    def __init__(self, config: dict):
        self.base_url = config.get('base_url')
        self.api_key = config.get('api_key')
        self._session = None

    async def initialize(self):
        """Initialize the LLM client"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()

    async def generate(self, prompt: str, **kwargs) -> AsyncGenerator[LLMResponse, None]:
        url = f"{self.base_url}/chat/completions"
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

                buffer = ""
                async for chunk in response.content:
                    if not chunk:
                        continue

                    # Decode and accumulate chunks
                    buffer += chunk.decode('utf-8')
                    
                    # Process complete JSON objects
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                            
                        try:
                            json_data = line[5:].strip()  # Remove "data:" prefix
                            if json_data == "[DONE]":
                                return
                                
                            data = json.loads(json_data)
                            if "choices" in data:
                                choice = data["choices"][0]
                                yield LLMResponse(
                                    content=choice.get("delta", {}).get("content", ""),
                                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                                    finish_reason=choice.get("finish_reason", "stop")
                                )
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received: {line}")
                        except KeyError:
                            logger.warning(f"Invalid response format: {data}")

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            raise

    async def generate_sync(self, prompt: str, **kwargs) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": "l3-8b-stheno-v3.2-iq-imatrix",
            "messages": [
                {"role": "system", "content": "Você é um assistente de escrita criativa especializado em gerar histórias envolventes."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "stream": False
        }

        try:
            async with self._session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"LLM request failed: {response.status}")
                    return {"error": f"Request failed with status {response.status}"}

                data = await response.json()
                if "choices" not in data:
                    return {"error": "Invalid response format from LLM"}

                content = data["choices"][0]["message"]["content"]
                
                # Try to parse as JSON first
                try:
                    # Remove any text before the first { and after the last }
                    clean_content = content[content.find('{'):content.rfind('}')+1]
                    
                    # Parse the cleaned JSON
                    story_data = json.loads(clean_content)
                    
                    if "stories" not in story_data:
                        return {"error": "Invalid story format in response"}
                    
                    # Format the output for better readability
                    print("\n=== Story Options ===\n")
                    for i, story in enumerate(story_data["stories"], 1):
                        print(f"Option {i}: {story['title']}")
                        print(f"\nSummary: {story['summary']}")
                        
                        print("\nMain Characters:")
                        for character in story['characters']:
                            print(f"- {character['name']}: {character['description']}")
                            
                        print("\nKey Locations:")
                        for location in story['locations']:
                            print(f"- {location['name']}: {location['description']}")
                            
                        print("\n" + "="*40 + "\n")
                    
                    return story_data
                except json.JSONDecodeError:
                    # If JSON parsing fails, treat as plain text
                    print("\n=== Generated Story ===\n")
                    
                    # Split into paragraphs and format
                    paragraphs = content.split('\n\n')
                    formatted_story = []
                    
                    for para in paragraphs:
                        # Remove any leading/trailing whitespace
                        para = para.strip()
                        if para:
                            # Add proper paragraph spacing
                            formatted_story.append(para)
                            formatted_story.append('')
                    
                    # Join with newlines and print
                    formatted_output = '\n'.join(formatted_story)
                    print(formatted_output)
                    print("\n" + "="*40 + "\n")
                    
                    return {
                        "content": formatted_output,
                        "format": "text"
                    }

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return {"error": str(e)}

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
        
        return f"""Generate 3 complete story options in JSON format for a {genre} story in {language}. Each story should include:

1. A creative title
2. A 2-3 paragraph summary of the story
3. 2-3 main characters with names and brief descriptions
4. 1-2 key locations with names and brief descriptions

Return the stories in the following exact JSON format:
{{
  "stories": [
    {{
      "title": "Story Title 1",
      "summary": "2-3 paragraph story summary...",
      "characters": [
        {{
          "name": "Character Name",
          "description": "Brief character description"
        }}
      ],
      "locations": [
        {{
          "name": "Location Name", 
          "description": "Brief location description"
        }}
      ]
    }},
    {{
      "title": "Story Title 2",
      "summary": "2-3 paragraph story summary...",
      "characters": [
        {{
          "name": "Character Name",
          "description": "Brief character description"
        }}
      ],
      "locations": [
        {{
          "name": "Location Name",
          "description": "Brief location description"
        }}
      ]
    }}
  ]
}}

Important rules:
1. Return ONLY valid JSON - no additional text before or after
2. Use double quotes for all JSON properties
3. Include exactly 3 story options
4. Keep character and location descriptions concise (1-2 sentences)
5. Write the story summaries in {language}"""
