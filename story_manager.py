"""
Módulo de Gerenciamento de Histórias

Este módulo gerencia todas as operações relacionadas a histórias no TaleWeaver,
incluindo:
- Criação de novas histórias
- Gerenciamento de gêneros e temas
- Interação com LLM
- Controle de contexto narrativo
- Gerenciamento de cenas
"""

import asyncio
import json
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple, Union
from config import ConfigManager
from database import AsyncDatabaseManager
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMClient:
    """Cliente para integração com LMStudio"""
    
    def __init__(self, base_url: str = "http://localhost:1234"):
        self.base_url = base_url
        self.session = aiohttp.ClientSession()
        self.cache: Dict[str, Dict[str, Any]] = {}
        
    async def close(self):
        """Fecha a conexão com o LMStudio"""
        await self.session.close()
        
    async def generate_story(self, genre: str, language: str = "pt-BR") -> Dict[str, Any]:
        """Gera uma nova história com base no gênero"""
        cache_key = f"story_{genre}_{language}"
        
        # Verifica cache
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        prompt = f"""
        Crie 3 opções de histórias no gênero {genre}.
        Cada história deve ter:
        - Título
        - Resumo de 3 parágrafos
        - 3 personagens principais com nomes e descrições
        - 2 locais principais
        
        Idioma: {language}
        """
        
        try:
            async with self.session.post(
                f"{self.base_url}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 1500,
                    "temperature": 0.7
                }
            ) as response:
                if response.status != 200:
                    raise Exception(f"Erro na requisição: {response.status}")
                    
                data = await response.json()
                result = self._parse_story_response(data)
                
                # Armazena no cache
                self.cache[cache_key] = result
                return result
                
        except Exception as e:
            print(f"Erro ao gerar história: {e}")
            return {
                "error": str(e),
                "stories": self._get_fallback_stories(genre)
            }
            
    def _parse_story_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa a resposta do LLM"""
        try:
            content = data["choices"][0]["text"]
            return json.loads(content)
        except Exception as e:
            print(f"Erro ao processar resposta: {e}")
            return {"error": str(e)}
            
    def _get_fallback_stories(self, genre: str) -> List[Dict[str, str]]:
        """Retorna histórias padrão em caso de erro"""
        return [
            {
                "title": f"História Padrão 1 - {genre}",
                "summary": "Resumo padrão da história 1...",
                "characters": [
                    {"name": "Personagem 1", "description": "Descrição padrão"},
                    {"name": "Personagem 2", "description": "Descrição padrão"}
                ],
                "locations": [
                    {"name": "Local 1", "description": "Descrição padrão"}
                ]
            }
        ]

class StoryManager:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.genres = {}
        self.current_story: Optional[Dict[str, Any]] = None
        self.current_scene: Optional[Dict[str, Any]] = None
        self.initialized = False
        self.llm: Optional[LLMClient] = None

    async def initialize(self):
        """Inicializa o StoryManager"""
        if self.initialized:
            return
            
        # Carrega os gêneros disponíveis
        self.genres = self._load_genres()
        
        # Verifica se as tabelas necessárias existem
        await self._verify_tables()
        
        # Inicializa cliente LLM
        await self.initialize_llm_client()
        
        self.initialized = True
        print("StoryManager inicializado com sucesso!")

    async def initialize_llm_client(self):
        """Inicializa o cliente LLM"""
        self.llm = LLMClient(self.config.get("llm_base_url", "http://localhost:1234"))
        print("LLMClient inicializado com sucesso!")

    async def _verify_tables(self):
        """Verifica se as tabelas necessárias existem no banco de dados"""
        tables = [
            "story_context",
            "story_scenes",
            "story_characters",
            "story_locations"
        ]
        
        for table in tables:
            query = f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """
            result = await self.db.execute_query(query, (table,))
            if not result:
                raise Exception(f"Tabela {table} não encontrada no banco de dados")

    def _load_genres(self) -> Dict[int, str]:
        """Carrega os gêneros disponíveis"""
        return {
            1: "Fantasia",
            2: "Ficção Científica",
            3: "Terror",
            4: "Romance",
            5: "Mistério",
            6: "Aventura",
            7: "Histórico",
            8: "Distopia",
            9: "Contemporâneo",
            0: "Personalizado"
        }

    async def create_new_story(self) -> Dict[str, Any]:
        """Cria uma nova história"""
        print("\nCriando nova história...")
        
        # Seleciona gênero
        genre = await self._select_genre()
        
        # Gera opções de história com LLM
        story_options = await self._generate_story_options(genre)
        
        # Seleciona história
        selected_story = await self._select_story(story_options)
        
        # Cria contexto inicial
        story_context = await self._create_initial_context(selected_story)
        
        # Cria personagens principais
        await self._create_main_characters(story_context)
        
        # Salva no banco de dados
        await self._save_story(story_context)
        
        print("Nova história criada com sucesso!")
        return story_context

    async def _select_genre(self) -> str:
        """Permite ao usuário selecionar um gênero"""
        print("\nSelecione um gênero:")
        for key, value in self.genres.items():
            print(f"{key}. {value}")
        
        while True:
            try:
                choice = int(input("\nEscolha um gênero (0-9): "))
                if choice in self.genres:
                    return self.genres[choice]
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("\n[ERRO] Por favor, insira um número válido.")

    async def _generate_story_options(self, genre: str) -> List[Dict[str, str]]:
        """Gera opções de história usando LLM"""
        logger.info(f"Gerando opções de história para o gênero: {genre}")
        
        try:
            result = await self.llm.generate_story(genre, self.config.get("language", "pt-BR"))
            
            if "error" in result:
                print(f"Erro ao gerar histórias: {result['error']}")
                return self._get_fallback_stories(genre)
                
            return result.get("stories", self._get_fallback_stories(genre))
            
        except Exception as e:
            print(f"Erro inesperado ao gerar histórias: {e}")
            return self._get_fallback_stories(genre)
            
    def _get_fallback_stories(self, genre: str) -> List[Dict[str, str]]:
        """Retorna histórias padrão em caso de erro"""
        return [
            {
                "title": f"História Padrão 1 - {genre}",
                "summary": "Resumo padrão da história 1...",
                "characters": [
                    {"name": "Personagem 1", "description": "Descrição padrão"},
                    {"name": "Personagem 2", "description": "Descrição padrão"}
                ],
                "locations": [
                    {"name": "Local 1", "description": "Descrição padrão"}
                ]
            },
            {
                "title": f"História Padrão 2 - {genre}",
                "summary": "Resumo padrão da história 2...",
                "characters": [
                    {"name": "Personagem 3", "description": "Descrição padrão"},
                    {"name": "Personagem 4", "description": "Descrição padrão"}
                ],
                "locations": [
                    {"name": "Local 2", "description": "Descrição padrão"}
                ]
            }
        ]

    async def _select_story(self, options: List[Dict[str, str]]) -> Dict[str, str]:
        """Permite ao usuário selecionar uma história"""
        print("\nOpções de história geradas:")
        for i, option in enumerate(options, 1):
            print(f"\n{i}. {option['title']}")
            print(option['summary'])
        
        while True:
            try:
                choice = int(input("\nEscolha uma história (1-3): "))
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("\n[ERRO] Por favor, insira um número válido.")

    async def _create_initial_context(self, story: Dict[str, str]) -> Dict[str, Any]:
        """Cria o contexto inicial da história"""
        return {
            "title": story["title"],
            "summary": story["summary"],
            "current_scene": "Introdução",
            "characters": [],
            "locations": [],
            "timeline": []
        }

    async def _create_main_characters(self, context: Dict[str, Any]) -> None:
        """Cria os personagens principais da história usando CharacterManager"""
        print("\nCriando personagens principais...")
        
        # Cria narrador
        narrator = await self.config.character_manager.create_character(
            name="Narrador",
            role="Narrador",
            description="Narrador onisciente da história"
        )
        context["characters"].append(narrator)
        
        # Cria personagens principais com LLM
        # TODO: Implementar integração com LLM para criação de personagens
        main_characters = [
            {
                "name": "Aragorn",
                "description": "Um ranger misterioso...",
                "role": "Protagonista"
            },
            {
                "name": "Gandalf",
                "description": "Um mago poderoso...",
                "role": "Mentor"
            }
        ]
        
        for char_data in main_characters:
            character = await self.config.character_manager.create_character(
                name=char_data["name"],
                role=char_data["role"],
                description=char_data["description"]
            )
            context["characters"].append(character)

    async def _save_story(self, context: Dict[str, Any]) -> None:
        """Salva a história no banco de dados"""
        query = """
            INSERT INTO story_context (summary, current_scene)
            VALUES (?, ?)
        """
        params = (context["summary"], context["current_scene"])
        
        try:
            await self.db.execute_write(query, params)
            print("História salva no banco de dados.")
        except Exception as e:
            print(f"Erro ao salvar história: {e}")
            raise

    async def get_current_story(self) -> Optional[Dict[str, Any]]:
        """Retorna a história atual"""
        return self.current_story

    async def update_story_context(self, new_context: Dict[str, Any]) -> None:
        """Atualiza o contexto da história"""
        self.current_story = new_context
        await self._save_story(new_context)

    async def advance_story(self) -> None:
        """Avança a história para a próxima cena"""
        if not self.current_story:
            raise ValueError("Nenhuma história ativa")
        
        # TODO: Implementar lógica de avanço de cena
        pass

    async def reset_story(self) -> None:
        """Reseta a história atual"""
        self.current_story = None
        self.current_scene = None
        print("História resetada com sucesso.")

    async def close(self) -> None:
        """Fecha todas as conexões e recursos"""
        if self.llm:
            await self.llm.close()
            logger.info("Conexão LLM fechada com sucesso")
