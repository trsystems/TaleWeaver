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
from logger import TaleWeaverLogger
from database import AsyncDatabaseManager
from datetime import datetime
from llm_client import LLMClient, LLMResponse
from dialogue_system import DialogueSystem

class StoryManager:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.logger = TaleWeaverLogger(config)
        self.genres = {}
        self.current_story: Optional[Dict[str, Any]] = None
        self.current_scene: Optional[Dict[str, Any]] = None
        self.initialized = False
        self.llm_client: Optional[LLMClient] = None
        self.dialogue_system: Optional[DialogueSystem] = None
        self.active_story_id: Optional[int] = None  # ID da história ativa
        self.player_character: Optional[Dict[str, Any]] = None  # Personagem do jogador

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
        
        # Inicializa sistema de diálogo
        self.dialogue_system = DialogueSystem(self.config, self.db)
        await self.dialogue_system.initialize()
        
        self.initialized = True
        print("StoryManager inicializado com sucesso!")

    async def initialize_llm_client(self, llm_config: Dict[str, Any]):
        """Inicializa o cliente LLM com as configurações fornecidas"""
        if not llm_config:
            raise ValueError("Configurações LLM não fornecidas")
            
        # Convert LLMConfig to dictionary if needed
        if hasattr(llm_config, 'to_dict'):
            llm_config = llm_config.to_dict()
            
        self.llm_client = LLMClient(llm_config)
        await self.llm_client.initialize()
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
        
        if not story_options:
            raise Exception("Não foi possível gerar opções de história")
        
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
        self.logger.info(f"Gerando opções de história para o gênero: {genre}")
        
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
            # Gera a história
            result = await self.llm_client.generate_story(prompt)
            
            # Valida o formato JSON com mais detalhes
            try:
                self.logger.debug(f"Resultado bruto da LLM: {result}")
                
                # Converte string para dict se necessário
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                        self.logger.debug("JSON convertido com sucesso de string para dict")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Falha ao converter JSON string para dict: {e}")
                        raise ValueError(f"Erro ao decodificar JSON: {e}")
                
                # Verifica estrutura básica
                if not isinstance(result, dict):
                    self.logger.error(f"Resultado não é um dicionário: {type(result)}")
                    raise ValueError("Formato JSON inválido - esperado um objeto/dicionário")
                
                if "stories" not in result:
                    self.logger.error(f"Chave 'stories' faltando no JSON: {result.keys()}")
                    raise ValueError("Formato JSON inválido - falta chave 'stories'")
                
                stories = result["stories"]
                if not isinstance(stories, list):
                    self.logger.error(f"Valor de 'stories' não é uma lista: {type(stories)}")
                    raise ValueError("Formato JSON inválido - 'stories' deve ser uma lista")
                
                self.logger.debug(f"Número de histórias recebidas: {len(stories)}")
                
                # Valida cada história com mais detalhes
                validated_stories = []
                for i, story in enumerate(stories):
                    if not isinstance(story, dict):
                        self.logger.warning(f"História {i} ignorada - não é um dicionário")
                        continue
                        
                    # Valida campos obrigatórios
                    if "title" not in story:
                        self.logger.warning(f"História {i} sem título - usando padrão")
                    if "summary" not in story:
                        self.logger.warning(f"História {i} sem resumo - usando string vazia")
                    
                    validated_story = {
                        "title": story.get("title", "História sem título"),
                        "summary": story.get("summary", ""),
                        "characters": [],
                        "locations": []
                    }
                    
                    # Valida personagens com mais detalhes
                    if "characters" in story:
                        if not isinstance(story["characters"], list):
                            self.logger.warning(f"Personagens da história {i} não são uma lista")
                        else:
                            self.logger.debug(f"Validando {len(story['characters'])} personagens")
                            for char in story["characters"]:
                                if not isinstance(char, dict):
                                    self.logger.warning(f"Personagem inválido na história {i} - ignorado")
                                    continue
                                    
                                if "name" not in char:
                                    self.logger.warning(f"Personagem sem nome na história {i}")
                                
                                validated_story["characters"].append({
                                    "name": char.get("name", "Sem nome"),
                                    "description": char.get("description", ""),
                                    "personality": char.get("personality", ""),
                                    "role": char.get("role", "Personagem")
                                })
                    
                    # Valida locais com mais detalhes
                    if "locations" in story:
                        if not isinstance(story["locations"], list):
                            self.logger.warning(f"Locais da história {i} não são uma lista")
                        else:
                            self.logger.debug(f"Validando {len(story['locations'])} locais")
                            for loc in story["locations"]:
                                if not isinstance(loc, dict):
                                    self.logger.warning(f"Local inválido na história {i} - ignorado")
                                    continue
                                    
                                if "name" not in loc:
                                    self.logger.warning(f"Local sem nome na história {i}")
                                
                                validated_story["locations"].append({
                                    "name": loc.get("name", "Local sem nome"),
                                    "description": loc.get("description", "")
                                })
                    
                    validated_stories.append(validated_story)
                    self.logger.debug(f"História {i} validada com sucesso")
                
                if not validated_stories:
                    self.logger.error("Nenhuma história válida encontrada após validação")
                    raise ValueError("Nenhuma história válida encontrada")
                
                self.logger.info(f"Retornando {len(validated_stories)} histórias validadas")
                return validated_stories
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Erro ao decodificar JSON: {e}\nConteúdo: {result}")
                raise ValueError(f"Erro ao decodificar JSON: {e}")
            except ValueError as e:
                self.logger.error(f"Erro de validação de estrutura: {e}\nConteúdo: {result}")
                raise ValueError(f"Erro de validação de estrutura: {e}")
            else:
                # Se recebemos texto, tenta estruturar manualmente
                content = result.get("content", "")
                self.logger.warning("Recebido resposta em texto, tentando estruturar manualmente")
                
                # Divide o texto em histórias
                story_sections = content.split("\nHistória")[1:]  # Remove texto antes da primeira história
                stories = []
                
                for section in story_sections:
                    try:
                        # Extrai informações básicas
                        lines = section.split("\n")
                        title = next((line for line in lines if line.strip()), "História sem título")
                        
                        # Encontra índices de seções
                        summary_start = content.find("Resumo:")
                        chars_start = content.find("Personagens:")
                        locs_start = content.find("Locais:")
                        
                        # Extrai seções
                        summary = content[summary_start:chars_start].replace("Resumo:", "").strip()
                        chars_section = content[chars_start:locs_start].replace("Personagens:", "").strip()
                        locs_section = content[locs_start:].replace("Locais:", "").strip()
                        
                        # Processa personagens
                        characters = []
                        for char_line in chars_section.split("\n"):
                            if ":" in char_line:
                                name, desc = char_line.split(":", 1)
                                characters.append({
                                    "name": name.strip(),
                                    "description": desc.strip()
                                })
                        
                        # Processa locais
                        locations = []
                        for loc_line in locs_section.split("\n"):
                            if ":" in loc_line:
                                name, desc = loc_line.split(":", 1)
                                locations.append({
                                    "name": name.strip(),
                                    "description": desc.strip()
                                })
                        
                        stories.append({
                            "title": title.strip(),
                            "summary": summary,
                            "characters": characters,
                            "locations": locations
                        })
                    except Exception as e:
                        self.logger.error(f"Erro ao processar seção da história: {e}")
                    continue
                
                return stories if stories else self._get_fallback_stories(genre)
                
        except Exception as e:
            self.logger.error(f"Erro ao gerar histórias: {e}")
            return self._get_fallback_stories(genre)

    def _get_fallback_stories(self, genre: str) -> List[Dict[str, str]]:
        """Retorna histórias padrão em caso de erro"""
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

    async def _select_story(self, options: List[Dict[str, str]]) -> Dict[str, str]:
        """Permite ao usuário selecionar uma história"""
        if not options:
            raise ValueError("Nenhuma opção de história disponível")
            
        print("\nOpções de história geradas:")
        
        for i, option in enumerate(options, 1):
            print(f"\n{i}. {option['title']}")
            print(f"Resumo: {option['summary']}\n")
            print("Personagens:")
            for char in option.get('characters', []):
                print(f"- {char['name']}: {char['description']}")
                if 'role' in char:
                    print(f"  Papel: {char['role']}")
            print("\nLocais:")
            for loc in option.get('locations', []):
                print(f"- {loc['name']}: {loc['description']}")
            print("-" * 50)
        
        while True:
            try:
                choice = int(input(f"\nEscolha uma história (1-{len(options)}): "))
                if 1 <= choice <= len(options):
                    self.selected_story = options[choice - 1]  # Armazena a história selecionada
                    return self.selected_story
                print(f"Por favor, escolha um número entre 1 e {len(options)}")
            except ValueError:
                print("Por favor, insira um número válido")

    async def _create_initial_context(self, selected_story: Dict[str, str]) -> Dict[str, Any]:
        """Cria o contexto inicial da história"""
        if not selected_story:
            raise ValueError("Nenhuma história selecionada")
            
        return {
            "title": selected_story["title"],
            "summary": selected_story["summary"],
            "current_scene": "Introdução",
            "characters": [],
            "locations": [],
            "timeline": []
        }

    def get_current_story(self) -> Optional[Dict[str, Any]]:
        """Retorna a história atual sendo gerenciada"""
        return self.current_story
