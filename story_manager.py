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
        logger.info(f"Gerando opções de história para o gênero: {genre}")
        
        prompt = f"""Você é um assistente que gera histórias criativas. Crie 3 opções de histórias completas no gênero {genre}, seguindo rigorosamente estas instruções:

1. Cada história deve ter:
   - Título: Criativo e relevante ao gênero
   - Resumo: 2-3 parágrafos bem escritos
   - Personagens: 2-3 principais com:
     * Nome
     * Descrição física e psicológica
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
                logger.debug(f"Resultado bruto da LLM: {result}")
                
                # Converte string para dict se necessário
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                        logger.debug("JSON convertido com sucesso de string para dict")
                    except json.JSONDecodeError as e:
                        logger.error(f"Falha ao converter JSON string para dict: {e}")
                        raise ValueError(f"Erro ao decodificar JSON: {e}")
                
                # Verifica estrutura básica
                if not isinstance(result, dict):
                    logger.error(f"Resultado não é um dicionário: {type(result)}")
                    raise ValueError("Formato JSON inválido - esperado um objeto/dicionário")
                
                if "stories" not in result:
                    logger.error(f"Chave 'stories' faltando no JSON: {result.keys()}")
                    raise ValueError("Formato JSON inválido - falta chave 'stories'")
                
                stories = result["stories"]
                if not isinstance(stories, list):
                    logger.error(f"Valor de 'stories' não é uma lista: {type(stories)}")
                    raise ValueError("Formato JSON inválido - 'stories' deve ser uma lista")
                
                logger.debug(f"Número de histórias recebidas: {len(stories)}")
                
                # Valida cada história com mais detalhes
                validated_stories = []
                for i, story in enumerate(stories):
                    if not isinstance(story, dict):
                        logger.warning(f"História {i} ignorada - não é um dicionário")
                        continue
                        
                    # Valida campos obrigatórios
                    if "title" not in story:
                        logger.warning(f"História {i} sem título - usando padrão")
                    if "summary" not in story:
                        logger.warning(f"História {i} sem resumo - usando string vazia")
                    
                    validated_story = {
                        "title": story.get("title", "História sem título"),
                        "summary": story.get("summary", ""),
                        "characters": [],
                        "locations": []
                    }
                    
                    # Valida personagens com mais detalhes
                    if "characters" in story:
                        if not isinstance(story["characters"], list):
                            logger.warning(f"Personagens da história {i} não são uma lista")
                        else:
                            logger.debug(f"Validando {len(story['characters'])} personagens")
                            for char in story["characters"]:
                                if not isinstance(char, dict):
                                    logger.warning(f"Personagem inválido na história {i} - ignorado")
                                    continue
                                    
                                if "name" not in char:
                                    logger.warning(f"Personagem sem nome na história {i}")
                                
                                validated_story["characters"].append({
                                    "name": char.get("name", "Sem nome"),
                                    "description": char.get("description", ""),
                                    "role": char.get("role", "Personagem")
                                })
                    
                    # Valida locais com mais detalhes
                    if "locations" in story:
                        if not isinstance(story["locations"], list):
                            logger.warning(f"Locais da história {i} não são uma lista")
                        else:
                            logger.debug(f"Validando {len(story['locations'])} locais")
                            for loc in story["locations"]:
                                if not isinstance(loc, dict):
                                    logger.warning(f"Local inválido na história {i} - ignorado")
                                    continue
                                    
                                if "name" not in loc:
                                    logger.warning(f"Local sem nome na história {i}")
                                
                                validated_story["locations"].append({
                                    "name": loc.get("name", "Local sem nome"),
                                    "description": loc.get("description", "")
                                })
                    
                    validated_stories.append(validated_story)
                    logger.debug(f"História {i} validada com sucesso")
                
                if not validated_stories:
                    logger.error("Nenhuma história válida encontrada após validação")
                    raise ValueError("Nenhuma história válida encontrada")
                
                logger.info(f"Retornando {len(validated_stories)} histórias validadas")
                return validated_stories
                
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON: {e}\nConteúdo: {result}")
                raise ValueError(f"Erro ao decodificar JSON: {e}")
            except ValueError as e:
                logger.error(f"Erro de validação de estrutura: {e}\nConteúdo: {result}")
                raise ValueError(f"Erro de validação de estrutura: {e}")
            else:
                # Se recebemos texto, tenta estruturar manualmente
                content = result.get("content", "")
                logger.warning("Recebido resposta em texto, tentando estruturar manualmente")
                
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
                        logger.error(f"Erro ao processar seção da história: {e}")
                        continue
                
                return stories if stories else self._get_fallback_stories(genre)
                
        except Exception as e:
            logger.error(f"Erro ao gerar histórias: {e}")
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
                    return options[choice - 1]
                print(f"Por favor, escolha um número entre 1 e {len(options)}")
            except ValueError:
                print("Por favor, insira um número válido")

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
        """Cria os personagens principais da história"""
        print("\nCriando personagens principais...")
        
        # Seleciona narrador
        print("\nQual narrador irá seguir com você nessa jornada?")
        print("1) Narrador Descritivo (padrão)")
        print("2) Narrador Sassy")
        
        while True:
            try:
                choice = int(input("\nEscolha (1-2): "))
                if choice == 1:
                    narrator_type = "descriptive"
                    description = "Narrador descritivo que contextualiza e enriquece a história"
                elif choice == 2:
                    narrator_type = "sassy"
                    description = "Narrador sarcástico e debochado que faz comentários irreverentes"
                else:
                    print("Opção inválida. Tente novamente.")
                    continue
                
                # Cria narrador
                narrator = await self.config.character_manager.create_character(
                    name="Narrador",
                    role="Narrador",
                    description=description,
                    voice=f"voices/narrator_{narrator_type}.wav"
                )
                context["characters"].append(narrator)
                break
                
            except ValueError:
                print("Por favor, insira um número válido")
        
        # Cria personagens da história selecionada
        if "characters" in context:
            for char_data in context["characters"]:
                character = await self.config.character_manager.create_character(
                    name=char_data["name"],
                    role=char_data.get("role", "Personagem"),
                    description=char_data["description"]
                )
                context["characters"].append(character)

        # Cria personagem do jogador
        print("\nVamos criar seu personagem!")
        player_name = input("Qual o nome do seu personagem? ")
        player_description = input("Descreva seu personagem (aparência, personalidade): ")
        
        self.player_character = await self.config.character_manager.create_character(
            name=player_name,
            role="Jogador",
            description=player_description,
            is_player=True
        )
        context["characters"].append(self.player_character)
        
        print(f"\nPersonagem {player_name} criado com sucesso!")

    async def _save_story(self, context: Dict[str, Any]) -> None:
        """Salva a história no banco de dados"""
        query = """
            INSERT INTO story_context (summary, current_scene)
            VALUES (?, ?)
        """
        params = (context["summary"], context["current_scene"])
        
        try:
            story_id = await self.db.execute_write(query, params)
            
            # Salva personagens
            for character in context["characters"]:
                await self._save_character(story_id, character)
                
            # Salva locais
            for location in context["locations"]:
                await self._save_location(story_id, location)
                
            print("História salva no banco de dados com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro ao salvar história: {e}")
            raise

    async def _save_character(self, story_id: int, character: Dict[str, Any]) -> None:
        """Salva um personagem no banco de dados"""
        query = """
            INSERT INTO story_characters (story_context_id, character_id, role, relationships)
            VALUES (?, ?, ?, ?)
        """
        params = (
            story_id,
            character.get("id"),
            character.get("role", "Personagem"),
            json.dumps(character.get("relationships", {}))
        )
        
        try:
            await self.db.execute_write(query, params)
        except Exception as e:
            logger.error(f"Erro ao salvar personagem: {e}")
            raise

    async def _save_location(self, story_id: int, location: Dict[str, Any]) -> None:
        """Salva um local no banco de dados"""
        query = """
            INSERT INTO story_locations (story_context_id, location_id, description)
            VALUES (?, ?, ?)
        """
        params = (
            story_id,
            location.get("id"),
            location.get("description", "")
        )
        
        try:
            await self.db.execute_write(query, params)
        except Exception as e:
            logger.error(f"Erro ao salvar local: {e}")
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
                await self.llm_client.close()
                logger.info("Conexão LLM fechada com sucesso")
            except Exception as e:
                logger.error(f"Erro ao fechar LLMClient: {e}")
