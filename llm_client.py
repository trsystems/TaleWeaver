"""
Módulo do Cliente LLM

Este módulo gerencia todas as interações com o modelo de linguagem,
incluindo:
- Geração de texto
- Gerenciamento de streaming
- Formatação de respostas
- Tratamento de erros
"""

import json
import logging
import asyncio
import time
from typing import AsyncGenerator, Optional, Dict, Any
import aiohttp
from pydantic import BaseModel, ValidationError

from log_manager import LogManager

class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    finish_reason: Optional[str] = None
    format: str = "text"

class LLMClient:
    def __init__(self, config: dict, log_manager: LogManager):
        self.base_url = config.get('base_url', 'http://localhost:1234')
        self.base_url = self.base_url.rstrip('/')
        self.api_key = config.get('api_key', 'lm-studio')
        self._session = None
        self.model = config.get('model', 'mistral')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)
        self.timeout = aiohttp.ClientTimeout(total=600, sock_connect=60, sock_read=300)
        self.retry_attempts = config.get('retry_attempts', 5)
        self.retry_delay = config.get('retry_delay', 5)
        self.keepalive_timeout = 300
        self.heartbeat_interval = 30
        self.language = config.get('language', 'pt')
        self.log_manager = log_manager

    async def initialize(self):
        if not self._session:
            connector = aiohttp.TCPConnector(
                keepalive_timeout=self.keepalive_timeout,
                force_close=False,
                enable_cleanup_closed=True
            )
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                headers={"Connection": "keep-alive"}
            )
        return self

    async def _make_request_with_retry(self, url: str, headers: dict, payload: dict) -> Any:
        attempt = 0
        last_error = None
        
        while attempt < self.retry_attempts:
            try:
                async with self._session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        self.log_manager.error("llm_client", f"LLM request failed (attempt {attempt + 1}): {response.status} - {error_msg}")
                        raise Exception(f"Request failed with status {response.status}: {error_msg}")
                    
                    if payload.get("stream", False):
                        return response
                    else:
                        return await response.json()
                        
            except Exception as e:
                last_error = e
                attempt += 1
                if attempt < self.retry_attempts:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    self.log_manager.warning("llm_client", f"Retry attempt {attempt} after {delay}s. Error: {str(e)}")
                    await asyncio.sleep(delay)
                    
        raise Exception(f"Failed after {self.retry_attempts} attempts. Last error: {str(last_error)}")

    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"""Você é um assistente criativo especializado em criar histórias envolventes e bem estruturadas. 
SEMPRE retorne APENAS um JSON válido e bem formatado, sem nenhum texto adicional.

FORMATO EXATO REQUERIDO:
{{
  "title": "Título criativo e descritivo",
  "summary": "Resumo narrativo de 2-3 frases que conta a história principal",
  "characters": [
    {{
      "name": "Nome completo do personagem",
      "description": "Descrição física e psicológica detalhada"
    }}
  ],
  "locations": [
    {{
      "name": "Nome descritivo do local",
      "description": "Descrição atmosférica e detalhes importantes"
    }}
  ]
}}

REGRAS ESTRITAS:
1. O JSON DEVE ser válido e bem formatado
2. O JSON DEVE começar com {{ e terminar com }}
3. O JSON DEVE usar apenas aspas duplas
4. O JSON NÃO pode conter quebras de linha ou espaços extras
5. O JSON NÃO pode conter texto fora da estrutura
6. O campo 'summary' DEVE conter a história completa
7. Cada personagem DEVE ter name e description
8. Cada local DEVE ter name e description
9. NUNCA inclua texto fora do JSON
10. NUNCA inclua comentários ou explicações
11. TODAS as respostas DEVEM estar no idioma {self.language}

Se você não seguir estas regras exatamente, o sistema falhará."""},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **kwargs
        }

        try:
            response = await self._make_request_with_retry(url, headers, payload)
            
            if not isinstance(response, dict) or "choices" not in response:
                raise Exception("Invalid response format from LLM")
                
            choice = response["choices"][0]
            message = choice.get("message", {})
            
            return LLMResponse(
                content=message.get("content", ""),
                tokens_used=response.get("usage", {}).get("total_tokens", 0),
                finish_reason=choice.get("finish_reason")
            )

        except Exception as e:
            self.log_manager.error("llm_client", f"Error in generate: {str(e)}")
            raise

    async def generate_story(self, prompt: str) -> Dict[str, Any]:
        last_error = None
        max_retries = 5
        min_response_length = 100
        
        for attempt in range(max_retries):
            try:
                response = await self.generate(prompt)
                story_content = response.content

                if not story_content.strip():
                    raise Exception("Received empty response from LLM")
                    
                if len(story_content) < min_response_length:
                    raise Exception(f"Response too short: {len(story_content)} chars")

                try:
                    # Tenta encontrar o JSON na resposta
                    json_str = story_content.strip()
                    
                    # Remove possíveis textos antes e depois do JSON
                    if not json_str.startswith('{'):
                        start = json_str.find('{')
                        if start >= 0:
                            json_str = json_str[start:]
                    
                    if not json_str.endswith('}'):
                        end = json_str.rfind('}') + 1
                        if end > 0:
                            json_str = json_str[:end]
                    
                    # Tenta parsear o JSON
                    try:
                        story_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        # Tenta corrigir problemas comuns de formatação
                        json_str = json_str.replace("'", '"')  # Substitui aspas simples por duplas
                        json_str = json_str.replace("True", "true").replace("False", "false")  # Corrige booleanos
                        json_str = json_str.replace("None", "null")  # Corrige valores nulos
                        story_data = json.loads(json_str)
                    
                    # Verifica se é o formato de múltiplas histórias
                    if "stories" in story_data:
                        stories = story_data["stories"]
                        if not isinstance(stories, list) or len(stories) == 0:
                            raise Exception("Invalid stories format in response")
                            
                        # Valida cada história individualmente
                        required_fields = ["title", "summary", "characters", "locations"]
                        for story in stories:
                            if not all(field in story for field in required_fields):
                                raise Exception("Missing required fields in story JSON")
                                
                        return {
                            "stories": stories,
                            "format": "json"
                        }
                    else:
                        # Formato antigo de história única
                        required_fields = ["title", "summary", "characters", "locations"]
                        if not all(field in story_data for field in required_fields):
                            raise Exception("Missing required fields in JSON response")
                            
                        return {
                            "title": story_data.get("title", ""),
                            "summary": story_data.get("summary", ""),
                            "characters": story_data.get("characters", []),
                            "locations": story_data.get("locations", []),
                            "format": "json"
                        }

                except json.JSONDecodeError as e:
                    self.log_manager.error("llm_client", f"Failed to parse JSON from response: {e}\nContent: {story_content}")
                    # Tenta usar uma estratégia de fallback para extrair o JSON
                    try:
                        # Remove possíveis textos antes e depois do JSON
                        json_str = story_content[story_content.find('{'):story_content.rfind('}')+1]
                        # Tenta parsear novamente
                        story_data = json.loads(json_str)
                        return story_data
                    except Exception as fallback_error:
                        self.log_manager.error("llm_client", f"Fallback parsing also failed: {fallback_error}")
                        raise Exception("LLM response was not in the expected JSON format")

            except aiohttp.ClientConnectionError as e:
                last_error = e
                self.log_manager.warning("llm_client", f"Connection error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise Exception(f"Failed after {max_retries} attempts. Last error: {str(e)}")
                
            except Exception as e:
                last_error = e
                self.log_manager.error("llm_client", f"Error generating story (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise Exception(f"Failed after {max_retries} attempts. Last error: {str(e)}")

        raise Exception(f"Failed to generate story after {max_retries} attempts. Last error: {str(last_error)}")

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
