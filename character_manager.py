"""
Módulo de Gerenciamento de Personagens

Este módulo gerencia todas as operações relacionadas a personagens no TaleWeaver,
incluindo:
- Criação de novos personagens
- Gerenciamento de características
- Relacionamentos entre personagens
- Histórico de interações
- Gerenciamento de vozes
"""

import asyncio
from typing import Dict, List, Optional
from config import ConfigManager
from database import AsyncDatabaseManager

from typing import Any

class CharacterManager:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.available_voices = {}
        self.initialized = False

    async def initialize(self):
        """Inicializa o CharacterManager"""
        if self.initialized:
            return
            
        # Carrega as vozes disponíveis
        self.available_voices = self._load_available_voices()
        
        # Aguarda a inicialização completa do banco de dados
        if not hasattr(self.db, 'initialized') or not self.db.initialized:
            await self.db.initialize()
        
        self.initialized = True
        print("CharacterManager inicializado com sucesso!")

    async def _verify_tables(self):
        """Verifica se as tabelas necessárias existem no banco de dados"""
        try:
            # Verifica apenas se a tabela characters existe
            query = """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='characters'
            """
            result = await self.db.execute_query(query)
            if not result:
                raise Exception("Tabela characters não encontrada no banco de dados")
        except Exception as e:
            print(f"Erro ao verificar tabela characters: {e}")
            raise

    def _load_available_voices(self) -> Dict[str, str]:
        """Carrega as vozes disponíveis"""
        return {
            "narrator_descriptive": "voices/narrator_descriptive.wav",
            "narrator_sassy": "voices/narrator_sassy.wav",
            "male_01": "voices/Liu.wav",
            "female_01": "voices/female_01.wav",
            "female_02": "voices/female_02.wav"
        }

    async def create_character(self, name: str, role: str, description: str, personality: str, voice: Optional[str] = None, is_player: bool = False, is_narrator: bool = False) -> Dict[str, Any]:
        """Cria um novo personagem"""
        # Garante que as colunas necessárias existam
        await self._verify_tables()
        
        # Verifica se o personagem já existe
        existing_char = await self._find_existing_character(name)
        if existing_char:
            print(f"Personagem '{name}' já existe. Retornando registro existente.")
            return existing_char
            
        # Validação de flags
        if is_player and is_narrator:
            raise ValueError("Um personagem não pode ser jogador e narrador ao mesmo tempo")
            
        # Define flags corretamente para narradores
        if role.lower() == "narrador":
            is_player = False
            is_narrator = True
            
        # Cria dicionário do personagem
        character = {
            "name": name,
            "role": role,
            "description": description,
            "personality": personality,
            "voice": voice,
            "relationships": {},
            "memories": [],
            "is_player": is_player,
            "is_narrator": is_narrator
        }
        
        # Validação adicional para narradores
        if is_narrator:
            if role.lower() != "narrador":
                raise ValueError("Personagens marcados como narradores devem ter o papel 'Narrador'")
            if is_player:
                raise ValueError("Narradores não podem ser personagens do jogador")
        
        if voice is None:
            await self._assign_voice(character)
        await self._save_character(character)
        
        return character

    async def _assign_voice(self, character: Dict[str, Any]) -> None:
        """Atribui uma voz ao personagem"""
        # Configuração específica para narradores
        if character["is_narrator"]:
            character["voice"] = "narrator_descriptive"
        else:
            # Atribui uma voz padrão para outros personagens
            character["voice"] = "male_01"

    async def _find_existing_character(self, name: str) -> Optional[Dict[str, Any]]:
        """Verifica se um personagem com o mesmo nome já existe"""
        query = """
            SELECT * FROM characters
            WHERE name = ?
            LIMIT 1
        """
        try:
            result = await self.db.execute_query(query, (name,))
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Erro ao buscar personagem existente: {e}")
            return None

    async def _save_character(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """Salva o personagem no banco de dados e retorna o personagem completo"""
        # Verificação de campos obrigatórios
        required_fields = ["name", "description", "role", "personality", "voice", "is_player", "is_narrator"]
        for field in required_fields:
            if character.get(field) is None:
                print(f"ERRO: Campo obrigatório '{field}' está None no personagem:")
                print(character)
                raise ValueError(f"Campo obrigatório '{field}' não pode ser None")

        print(f"Salvando personagem: {character['name']}")
        print(f"Detalhes do personagem: {character}")

        query = """
            INSERT INTO characters (
                name,
                description,
                role,
                personality,
                voice,
                is_player,
                is_narrator
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            character["name"],
            character["description"],
            character["role"],
            character["personality"],
            character["voice"],
            character["is_player"],
            character["is_narrator"]
        )
        
        try:
            print("Executando query de inserção...")
            character_id = await self.db.execute_write(query, params)
            print(f"Personagem inserido com ID: {character_id}")
            
            character["id"] = character_id  # Armazena o ID no dicionário do personagem
            
            # Recupera o personagem completo do banco de dados
            print("Recuperando personagem do banco de dados...")
            select_query = """
                SELECT * FROM characters WHERE id = ?
            """
            result = await self.db.execute_query(select_query, (character_id,))
            
            if result:
                print("Personagem recuperado com sucesso")
                return result[0]
            
            print("Aviso: Personagem não encontrado após inserção")
            return character
            
        except Exception as e:
            print(f"ERRO ao salvar personagem: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            print(f"Character: {character}")
            raise ValueError(f"Erro ao salvar personagem: {str(e)}")
