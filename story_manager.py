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
from typing import Dict, List, Optional, Tuple, Union, Any
from config import ConfigManager
from log_manager import LogManager
from database import AsyncDatabaseManager
from datetime import datetime
from llm_client import LLMClient, LLMResponse
from dialogue_system import DialogueSystem

class StoryManager:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.log_manager = LogManager(config)
        self.genres = {}
        self.current_story: Optional[Dict[str, Any]] = None
        self.current_scene: Optional[Dict[str, Any]] = None
        self.initialized = False
        self.llm_client: Optional[LLMClient] = None
        self.dialogue_system: Optional[DialogueSystem] = None
        self.active_story_id: Optional[int] = None
        self.player_character: Optional[Dict[str, Any]] = None

    async def initialize(self):
        """Inicializa o StoryManager"""
        if self.initialized:
            return
            
        self.genres = self._load_genres()
        await self._verify_tables()
        
        llm_config = self.config.get('llm')
        if not llm_config:
            raise ValueError("Configurações LLM não encontradas")
        await self.initialize_llm_client(llm_config)
        
        self.dialogue_system = DialogueSystem(self.config, self.db, self.log_manager)
        await self.dialogue_system.initialize()
        
        self.initialized = True
        self.log_manager.info("story_manager", "StoryManager inicializado com sucesso!")

    async def initialize_llm_client(self, llm_config: Dict[str, Any]):
        """Inicializa o cliente LLM com as configurações fornecidas"""
        if not llm_config:
            raise ValueError("Configurações LLM não fornecidas")
            
        if hasattr(llm_config, 'to_dict'):
            llm_config = llm_config.to_dict()
            
        self.llm_client = LLMClient(llm_config, log_manager=self.log_manager)
        await self.llm_client.initialize()
        self.log_manager.info("story_manager", "LLMClient inicializado com sucesso!")

    async def _verify_tables(self):
        """Verifica se as tabelas necessárias existem no banco de dados"""
        tables = [
            "story_context",
            "story_scenes",
            "story_characters",
            "story_locations"
        ]
        
        for table in tables:
            query = f"SELECT name FROM sqlite_master WHERE type='table' AND name=?"
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
        self.log_manager.info("story_manager", "Criando nova história...")
        
        genre = await self._select_genre()
        story_options = await self._generate_story_options(genre)
        
        if not story_options:
            raise Exception("Não foi possível gerar opções de história")
        
        selected_story = await self._select_story(story_options)
        story_context = await self._create_initial_context(selected_story)
        
        await self._create_main_characters(story_context)
        await self._save_story(story_context)
        
        self.log_manager.info("story_manager", "Nova história criada com sucesso!")
        return story_context

    async def _select_genre(self) -> str:
        """Permite ao usuário selecionar um gênero"""
        self.log_manager.debug("story_manager", "Iniciando seleção de gênero")
        print("\nSelecione um gênero:")
        for key, value in self.genres.items():
            print(f"{key}. {value}")
        
        while True:
            try:
                choice = int(input("\nEscolha um gênero (0-9): "))
                if choice in self.genres:
                    selected_genre = self.genres[choice]
                    self.log_manager.debug("story_manager", f"Gênero selecionado: {selected_genre}")
                    return selected_genre
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("\n[ERRO] Por favor, insira um número válido.")

    async def _generate_story_options(self, genre: str) -> List[Dict[str, str]]:
        """Gera opções de história usando LLM"""
        self.log_manager.info("story_manager", f"Gerando opções de história para o gênero: {genre}")
        
        prompt = f"""Você é um assistente que gera histórias criativas. Crie 3 opções de histórias completas no gênero {genre}, seguindo rigorosamente estas instruções:

1. Cada história deve ter:
   - Título: Criativo e relevante ao gênero
   - Resumo: 2-3 parágrafos bem escritos
   - Personagens: 2-3 principais com:
     * Nome
     * Descrição física
     * Personalidade (traços psicológicos, comportamento, motivações)
     * Papel na história
   - Locais: 1-2 importantes com:
     * Nome
     * Descrição detalhada
     * Relevância para a trama

2. Formato de resposta:
   - Retorne APENAS um JSON válido
   - Sem comentários ou texto adicional
   - Sempre use aspas duplas
   - Sem trailing commas

3. Exemplo de estrutura:
{{
    "stories": [
        {{
            "title": "Título da História",
            "summary": "Resumo detalhado...",
            "characters": [
                {{
                    "name": "Nome do Personagem",
                    "description": "Descrição completa",
                    "role": "Protagonista/Antagonista/etc"
                }}
            ],
            "locations": [
                {{
                    "name": "Nome do Local",
                    "description": "Descrição detalhada"
                }}
            ]
        }}
    ]
}}

4. Regras adicionais:
   - Cada história deve ser única e criativa
   - Mantenha consistência com o gênero {genre}
   - Desenvolva personagens complexos e interessantes
   - Crie locais memoráveis e relevantes para a trama"""

        try:
            result = await self.llm_client.generate_story(prompt)
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                    self.log_manager.debug("story_manager", "JSON convertido com sucesso de string para dict")
                except json.JSONDecodeError as e:
                    self.log_manager.error("story_manager", f"Falha ao converter JSON string para dict: {e}")
                    raise ValueError(f"Erro ao decodificar JSON: {e}")
            
            return await self._validate_stories(result)
            
        except Exception as e:
            self.log_manager.error("story_manager", f"Erro ao gerar histórias: {e}")
            return self._get_fallback_stories(genre)

    async def _validate_stories(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Valida o formato das histórias retornadas pela LLM"""
        try:
            if not isinstance(result, dict):
                self.log_manager.error("story_manager", f"Resultado não é um dicionário: {type(result)}")
                raise ValueError("Formato JSON inválido - esperado um objeto/dicionário")
            
            if "stories" not in result:
                self.log_manager.error("story_manager", f"Chave 'stories' faltando no JSON: {result.keys()}")
                raise ValueError("Formato JSON inválido - falta chave 'stories'")
            
            stories = result["stories"]
            if not isinstance(stories, list):
                self.log_manager.error("story_manager", f"Valor de 'stories' não é uma lista: {type(stories)}")
                raise ValueError("Formato JSON inválido - 'stories' deve ser uma lista")
            
            self.log_manager.debug("story_manager", f"Número de histórias recebidas: {len(stories)}")
            
            validated_stories = []
            for idx, story in enumerate(stories):
                if not isinstance(story, dict):
                    self.log_manager.warning("story_manager", f"História {idx} ignorada - não é um dicionário")
                    continue
                    
                required_fields = ["title", "summary", "characters", "locations"]
                missing_fields = [field for field in required_fields if field not in story]
                if missing_fields:
                    self.log_manager.warning("story_manager",
                        f"História {idx} ({story.get('title', 'Sem título')}) - campos faltando: {missing_fields}")
                    continue
                
                characters = story.get("characters", [])
                if not isinstance(characters, list):
                    self.log_manager.warning("story_manager", f"História {idx} - personagens não é uma lista")
                    continue
                
                valid_characters = []
                for char in characters:
                    if not isinstance(char, dict):
                        continue
                    if not all(k in char for k in ["name", "description", "role"]):
                        continue
                    valid_characters.append(char)
                
                if not valid_characters:
                    self.log_manager.warning("story_manager", f"História {idx} - nenhum personagem válido")
                    continue
                
                validated_story = {
                    "title": story["title"],
                    "summary": story["summary"],
                    "characters": valid_characters,
                    "locations": story.get("locations", []),
                    "current_scene": "Introdução"
                }
                validated_stories.append(validated_story)
            
            if not validated_stories:
                raise ValueError("Nenhuma história válida após validação")
            
            self.log_manager.info("story_manager", f"Retornando {len(validated_stories)} histórias validadas")
            return validated_stories
            
        except Exception as e:
            self.log_manager.error("story_manager", f"Erro na validação: {str(e)}")
            raise ValueError(f"Erro na validação: {str(e)}")

    def _get_fallback_stories(self, genre: str) -> List[Dict[str, str]]:
        """Retorna histórias padrão em caso de erro"""
        self.log_manager.info("story_manager", "Usando histórias de fallback")
        return [
            {
                "title": f"O Despertar Mágico - {genre}",
                "summary": "Em um mundo onde a magia foi esquecida, uma jovem descobre que possui poderes únicos. Agora ela deve aprender a controlar suas habilidades enquanto enfrenta uma antiga ameaça que ressurge das sombras.",
                "characters": [
                    {"name": "Luna Silva", "description": "Jovem descobrindo seus poderes mágicos", "role": "Protagonista"},
                    {"name": "Mestre Thiago", "description": "Sábio guardião do conhecimento arcano", "role": "Mentor"}
                ],
                "locations": [
                    {"name": "Academia Arcana", "description": "Antiga escola de magia escondida", "type": "Local Principal"}
                ]
            },
            {
                "title": f"A Última Fronteira - {genre}",
                "summary": "Uma equipe de exploradores descobre um portal para uma dimensão paralela. Suas descobertas podem mudar o destino da humanidade, mas também trazem perigos inimagináveis.",
                "characters": [
                    {"name": "Dr. Marco Santos", "description": "Cientista brilhante e líder da expedição", "role": "Protagonista"},
                    {"name": "Ana Costa", "description": "Especialista em física quântica", "role": "Deuteragonista"}
                ],
                "locations": [
                    {"name": "Portal Dimensional", "description": "Gateway entre mundos", "type": "Local Principal"}
                ]
            }
        ]

    async def _select_story(self, stories: List[Dict[str, str]]) -> Dict[str, str]:
        """Permite ao usuário selecionar uma história"""
        if not stories:
            raise ValueError("Nenhuma opção de história disponível")
            
        self.log_manager.debug("story_manager", f"Apresentando {len(stories)} opções de história")
        print("\nOpções de história geradas:")
        
        for idx, story in enumerate(stories, 1):
            print(f"\n{idx}. {story['title']}")
            print(f"Resumo: {story['summary']}\n")
            print("Personagens:")
            for char in story.get('characters', []):
                print(f"- {char['name']}: {char['description']}")
                if 'role' in char:
                    print(f"  Papel: {char['role']}")
            print("\nLocais:")
            for loc in story.get('locations', []):
                print(f"- {loc['name']}: {loc['description']}")
            print("-" * 50)
        
        while True:
            try:
                choice = int(input(f"\nEscolha uma história (1-{len(stories)}): "))
                if 1 <= choice <= len(stories):
                    selected_story = stories[choice - 1]
                    self.log_manager.debug("story_manager", f"História selecionada: {selected_story['title']}")
                    return selected_story
                print(f"Por favor, escolha um número entre 1 e {len(stories)}")
            except ValueError:
                print("Por favor, insira um número válido")

    async def _create_initial_context(self, selected_story: Dict[str, str]) -> Dict[str, Any]:
        """Cria o contexto inicial da história"""
        if not selected_story:
            raise ValueError("Nenhuma história selecionada")
            
        self.log_manager.debug("story_manager", "Criando contexto inicial")
        return {
            "title": selected_story["title"],
            "summary": selected_story["summary"],
            "current_scene": "Introdução",
            "characters": selected_story.get("characters", []),
            "locations": selected_story.get("locations", []),
            "timeline": []
        }

    async def _create_main_characters(self, story_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Cria os personagens principais da história e armazena seus IDs no contexto"""
        if not self.config.character_manager:
            self.log_manager.error("story_manager", "CharacterManager não inicializado")
            return []
            
        characters = []
        for char_data in story_context.get('characters', []):
            try:
                # Cria o personagem e armazena o ID no contexto
                character = await self.config.character_manager.create_character(
                    name=char_data['name'],
                    role=char_data['role'],
                    description=char_data['description'],
                    personality=char_data.get('personality', ''),
                    is_player=False
                )
                
                # Atualiza o char_data com o ID do personagem criado
                char_data['id'] = character['id']
                characters.append(character)
            except Exception as e:
                self.log_manager.error("story_manager", f"Erro ao criar personagem {char_data.get('name')}: {e}")
                
        return characters

    async def _save_story(self, story_context: Dict[str, Any]) -> Dict[str, Any]:
        """Salva a história no banco de dados"""
        try:
            # Salva o contexto da história
            query = """
                INSERT INTO story_context (
                    summary,
                    current_scene,
                    timestamp
                ) VALUES (?, ?, ?)
            """
            params = (
                story_context['summary'],
                story_context['current_scene'],
                datetime.now().isoformat()
            )
            
            story_id = await self.db.execute_write(query, params)
            
            # Salva os personagens da história
            for character in story_context.get('characters', []):
                try:
                    await self._save_story_character(story_id, character)
                except Exception as e:
                    self.log_manager.error("story_manager", f"Erro ao salvar personagem: {e}")
                    raise
            
            # Salva os locais da história
            for location in story_context.get('locations', []):
                await self._save_story_location(story_id, location)
            
            story_context['id'] = story_id
            self.current_story = story_context
            self.active_story_id = story_id
            
            return story_context
            
        except Exception as e:
            self.log_manager.error("story_manager", f"Erro ao salvar história: {e}")
            raise

    async def _save_story_character(self, story_id: int, character: Dict[str, Any]) -> None:
        """Associa um personagem existente à história"""
        # Verifica se o personagem já foi criado
        if 'id' not in character:
            raise ValueError("Personagem deve ser criado antes de ser associado à história")
            
        # Associa o personagem à história com o ID correto
        await self.db.execute_write(
            """
            INSERT INTO story_characters (
                story_context_id,
                character_id,
                role,
                relationships
            ) VALUES (?, ?, ?, ?)
            """,
            (story_id, character['id'], character.get('role'), json.dumps({}))
        )

    async def _save_story_location(self, story_id: int, location: Dict[str, Any]) -> None:
        """Salva um local associado à história"""
        # Primeiro cria o local no banco de dados
        query = """
            INSERT INTO locations (
                name,
                description
            ) VALUES (?, ?)
        """
        params = (
            location['name'],
            location['description']
        )
        
        location_id = await self.db.execute_write(query, params)
        
        # Agora associa o local à história com o ID correto
        await self.db.execute_write(
            """
            INSERT INTO story_locations (
                story_context_id,
                location_id,
                description
            ) VALUES (?, ?, ?)
            """,
            (story_id, location_id, location.get('description'))
        )

    async def get_current_story(self) -> Optional[Dict[str, Any]]:
        """Retorna a história atual sendo gerenciada"""
        if not self.current_story:
            # Se não há história ativa, tenta carregar a última do banco de dados
            try:
                if self.db:
                    query = "SELECT * FROM story_context ORDER BY timestamp DESC LIMIT 1"
                    result = await self.db.execute_query(query)
                    if result:
                        self.current_story = result[0]
                        self.active_story_id = result[0]['id']
                        self.log_manager.debug("story_manager", f"História carregada do banco: {self.current_story.get('title')}")
            except Exception as e:
                self.log_manager.error("story_manager", f"Erro ao carregar história do banco de dados: {e}")
        
        return self.current_story

    async def close(self) -> None:
        """Fecha recursos do StoryManager"""
        if self.llm_client:
            await self.llm_client.close()
            self.log_manager.info("story_manager", "Conexão LLM fechada com sucesso")