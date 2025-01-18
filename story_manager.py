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
from llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

class StoryManager:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.genres = {}
        self.current_story: Optional[Dict[str, Any]] = None
        self.current_scene: Optional[Dict[str, Any]] = None
        self.initialized = False
        self.llm_client: Optional[LLMClient] = None

    async def initialize(self):
        """Inicializa o StoryManager"""
        if self.initialized:
            return
            
        # Carrega os gêneros disponíveis
        self.genres = self._load_genres()
        
        # Verifica se as tabelas necessárias existem
        await self._verify_tables()
        
        # Inicializa cliente LLM com as configurações corretas
        llm_config = self.config.get('llm')
        if not llm_config:
            raise ValueError("Configurações LLM não encontradas")
        await self.initialize_llm_client(llm_config)
        
        self.initialized = True
        print("StoryManager inicializado com sucesso!")

    async def initialize_llm_client(self, llm_config: Dict[str, Any]):
        """Inicializa o cliente LLM com as configurações fornecidas
        
        Args:
            llm_config: Dicionário com as configurações do LLM
        """
        if not llm_config:
            raise ValueError("Configurações LLM não fornecidas")
            
        # Convert LLMConfig to dictionary if needed
        if hasattr(llm_config, 'to_dict'):
            llm_config = llm_config.to_dict()
            
        self.llm_client = await LLMClient(llm_config).__aenter__()
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
            # Gera prompt estruturado
            prompt = await self.llm_client.generate_story_prompt({
                "genre": genre,
                "language": self.config.get("language", "pt-BR")
            })
            
            # Gera histórias
            stories = []
            async for response in self.llm_client.generate(prompt):
                if response.finish_reason == "stop":
                    try:
                        story_data = json.loads(response.content)
                        stories.extend(story_data.get("stories", []))
                    except json.JSONDecodeError:
                        logger.error("Erro ao decodificar resposta do LLM")
                        continue
                        
            return stories if stories else self._get_fallback_stories(genre)
            
        except Exception as e:
            logger.error(f"Erro ao gerar histórias: {e}")
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
        if self.llm_client:
            try:
                await self.llm_client.__aexit__(None, None, None)
                logger.info("Conexão LLM fechada com sucesso")
            except Exception as e:
                logger.error(f"Erro ao fechar LLMClient: {e}")
