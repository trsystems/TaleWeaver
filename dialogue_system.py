"""
Módulo de Sistema de Diálogo

Este módulo gerencia todas as interações entre personagens no TaleWeaver,
incluindo:
- Diálogos com narrador
- Diálogos diretos com personagens
- Diálogos mistos (narrador + personagem)
- Gerenciamento de histórico de conversas
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from config import ConfigManager
from database import AsyncDatabaseManager
from llm_client import LLMClient

class DialogueSystem:
    def __init__(self, config: ConfigManager, db: AsyncDatabaseManager):
        self.config = config
        self.db = db
        self.llm_client: Optional[LLMClient] = None
        self.current_dialogue: Optional[Dict[str, Any]] = None
        self.dialogue_history: List[Dict[str, str]] = []
        
    async def initialize(self):
        """Inicializa o sistema de diálogo"""
        llm_config = self.config.get('llm')
        if not llm_config:
            raise ValueError("Configurações LLM não encontradas")
            
        self.llm_client = LLMClient(llm_config)
        await self.llm_client.initialize()
        
    async def start_dialogue(self, character_id: int, mode: str = "narrator") -> Dict[str, Any]:
        """Inicia um novo diálogo com um personagem"""
        if mode not in ["narrator", "direct", "mixed"]:
            raise ValueError("Modo de diálogo inválido")
            
        character = await self._get_character(character_id)
        if not character:
            raise ValueError("Personagem não encontrado")
            
        self.current_dialogue = {
            "character_id": character_id,
            "mode": mode,
            "history": []
        }
        
        return self.current_dialogue
        
    async def continue_dialogue(self, player_input: str) -> Dict[str, str]:
        """Continua o diálogo atual com a entrada do jogador"""
        if not self.current_dialogue:
            raise ValueError("Nenhum diálogo ativo")
            
        mode = self.current_dialogue["mode"]
        character = await self._get_character(self.current_dialogue["character_id"])
        
        if mode == "narrator":
            return await self._handle_narrator_dialogue(player_input, character)
        elif mode == "direct":
            return await self._handle_direct_dialogue(player_input, character)
        elif mode == "mixed":
            return await self._handle_mixed_dialogue(player_input, character)
            
    async def _handle_narrator_dialogue(self, player_input: str, character: Dict[str, Any]) -> Dict[str, str]:
        """Processa diálogo com narrador"""
        prompt = f"""
        Você é um narrador que descreve a interação entre {character['name']} e o jogador.
        O jogador disse: "{player_input}"
        
        Descreva a reação de {character['name']} e o que acontece a seguir.
        """
        
        response = await self.llm_client.generate_response(prompt)
        self._add_to_history(player_input, response)
        
        return {
            "type": "narrator",
            "content": response
        }
        
    async def _handle_direct_dialogue(self, player_input: str, character: Dict[str, Any]) -> Dict[str, str]:
        """Processa diálogo direto com personagem"""
        prompt = f"""
        Você é {character['name']}. Responda diretamente ao jogador.
        O jogador disse: "{player_input}"
        
        Responda como {character['name']} responderia.
        """
        
        response = await self.llm_client.generate_response(prompt)
        self._add_to_history(player_input, response)
        
        return {
            "type": "character",
            "content": response,
            "character": character['name']
        }
        
    async def _handle_mixed_dialogue(self, player_input: str, character: Dict[str, Any]) -> Dict[str, str]:
        """Processa diálogo misto (narrador + personagem)"""
        prompt = f"""
        Você é um narrador que descreve a interação entre {character['name']} e o jogador.
        O jogador disse: "{player_input}"
        
        Primeiro descreva a reação de {character['name']} e o que acontece a seguir.
        Em seguida, inclua a resposta direta de {character['name']} entre aspas.
        """
        
        response = await self.llm_client.generate_response(prompt)
        self._add_to_history(player_input, response)
        
        return {
            "type": "mixed",
            "content": response
        }
        
    async def _get_character(self, character_id: int) -> Dict[str, Any]:
        """Obtém informações do personagem"""
        query = "SELECT * FROM characters WHERE id = ?"
        result = await self.db.execute_query(query, (character_id,))
        return result[0] if result else None
        
    def _add_to_history(self, player_input: str, response: str) -> None:
        """Adiciona interação ao histórico"""
        self.dialogue_history.append({
            "input": player_input,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        
    async def save_dialogue_history(self) -> None:
        """Salva o histórico de diálogo no banco de dados"""
        query = """
            INSERT INTO dialogue_history (character_id, input, response, timestamp)
            VALUES (?, ?, ?, ?)
        """
        params = (
            self.current_dialogue["character_id"],
            self.dialogue_history[-1]["input"],
            self.dialogue_history[-1]["response"],
            self.dialogue_history[-1]["timestamp"]
        )
        
        await self.db.execute_write(query, params)
        
    async def close(self) -> None:
        """Fecha o sistema de diálogo"""
        if self.llm_client:
            await self.llm_client.close()
