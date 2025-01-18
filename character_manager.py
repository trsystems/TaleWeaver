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
        
        # Verifica se as tabelas necessárias existem
        await self._verify_tables()
        
        self.initialized = True
        print("CharacterManager inicializado com sucesso!")

    async def _verify_tables(self):
        """Verifica se as tabelas necessárias existem no banco de dados"""
        tables = [
            "characters",
            "character_relationships",
            "memories"
        ]
        
        for table in tables:
            query = f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """
            result = await self.db.execute_query(query, (table,))
            if not result:
                raise Exception(f"Tabela {table} não encontrada no banco de dados")

    def _load_available_voices(self) -> Dict[str, str]:
        """Carrega as vozes disponíveis"""
        return {
            "narrator_descriptive": "voices/narrator_descriptive.wav",
            "narrator_sassy": "voices/narrator_sassy.wav",
            "male_01": "voices/Liu.wav",
            "female_01": "voices/female_01.wav",
            "female_02": "voices/female_02.wav"
        }

    async def create_character(self, name: str, role: str, description: str) -> Dict[str, Any]:
        """Cria um novo personagem"""
        print(f"\nCriando novo personagem: {name}")
        
        character = {
            "name": name,
            "role": role,
            "description": description,
            "voice": None,
            "relationships": {},
            "memories": []
        }
        
        await self._assign_voice(character)
        await self._save_character(character)
        
        print(f"Personagem {name} criado com sucesso!")
        return character

    async def _assign_voice(self, character: Dict[str, Any]) -> None:
        """Atribui uma voz ao personagem"""
        print("\nAtribuindo voz ao personagem...")
        
        # TODO: Implementar lógica de seleção de voz
        if character["role"].lower() == "narrador":
            character["voice"] = self.available_voices["narrator_descriptive"]
        else:
            character["voice"] = self.available_voices["male_01"]

    async def _save_character(self, character: Dict[str, Any]) -> None:
        """Salva o personagem no banco de dados"""
        query = """
            INSERT INTO characters (name, role, description, voice)
            VALUES (?, ?, ?, ?)
        """
        params = (
            character["name"],
            character["role"],
            character["description"],
            character["voice"]
        )
        
        try:
            await self.db.execute_write(query, params)
            print("Personagem salvo no banco de dados.")
        except Exception as e:
            print(f"Erro ao salvar personagem: {e}")
            raise

    async def get_character(self, character_id: int) -> Optional[Dict[str, Any]]:
        """Obtém um personagem pelo ID"""
        query = """
            SELECT * FROM characters
            WHERE id = ?
        """
        params = (character_id,)
        
        try:
            result = await self.db.execute_query(query, params)
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Erro ao buscar personagem: {e}")
            raise

    async def update_character(self, character_id: int, updates: Dict[str, Any]) -> None:
        """Atualiza um personagem existente"""
        query = """
            UPDATE characters
            SET name = ?, role = ?, description = ?, voice = ?
            WHERE id = ?
        """
        params = (
            updates.get("name"),
            updates.get("role"),
            updates.get("description"),
            updates.get("voice"),
            character_id
        )
        
        try:
            await self.db.execute_write(query, params)
            print("Personagem atualizado com sucesso.")
        except Exception as e:
            print(f"Erro ao atualizar personagem: {e}")
            raise

    async def delete_character(self, character_id: int) -> None:
        """Remove um personagem"""
        query = """
            DELETE FROM characters
            WHERE id = ?
        """
        params = (character_id,)
        
        try:
            await self.db.execute_write(query, params)
            print("Personagem removido com sucesso.")
        except Exception as e:
            print(f"Erro ao remover personagem: {e}")
            raise

    async def add_relationship(self, character_id: int, target_id: int, relationship_type: str) -> None:
        """Adiciona um relacionamento entre personagens"""
        query = """
            INSERT INTO character_relationships (character_id, target_id, relationship_type)
            VALUES (?, ?, ?)
        """
        params = (character_id, target_id, relationship_type)
        
        try:
            await self.db.execute_write(query, params)
            print("Relacionamento adicionado com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar relacionamento: {e}")
            raise

    async def get_relationships(self, character_id: int) -> List[Dict[str, Any]]:
        """Obtém os relacionamentos de um personagem"""
        query = """
            SELECT * FROM character_relationships
            WHERE character_id = ?
        """
        params = (character_id,)
        
        try:
            return await self.db.execute_query(query, params)
        except Exception as e:
            print(f"Erro ao buscar relacionamentos: {e}")
            raise

    async def add_memory(self, character_id: int, memory: Dict[str, Any]) -> None:
        """Adiciona uma memória ao personagem"""
        query = """
            INSERT INTO memories (character_id, memory_type, content)
            VALUES (?, ?, ?)
        """
        params = (
            character_id,
            memory.get("type"),
            memory.get("content")
        )
        
        try:
            await self.db.execute_write(query, params)
            print("Memória adicionada com sucesso.")
        except Exception as e:
            print(f"Erro ao adicionar memória: {e}")
            raise

    async def get_memories(self, character_id: int) -> List[Dict[str, Any]]:
        """Obtém as memórias de um personagem"""
        query = """
            SELECT * FROM memories
            WHERE character_id = ?
            ORDER BY timestamp DESC
        """
        params = (character_id,)
        
        try:
            return await self.db.execute_query(query, params)
        except Exception as e:
            print(f"Erro ao buscar memórias: {e}")
            raise

    async def manage_characters_menu(self, current_story: Dict[str, Any]) -> None:
        """Exibe e gerencia o menu de personagens"""
        if not current_story:
            print("Nenhuma história ativa.")
            return
        
        while True:
            print("\n=== Gerenciamento de Personagens ===")
            print("1. Criar novo personagem")
            print("2. Editar personagem existente")
            print("3. Ver detalhes do personagem")
            print("4. Remover personagem")
            print("5. Voltar ao menu principal")
            
            choice = input("Escolha uma opção: ")
            
            if choice == "1":
                await self._create_character_menu()
            elif choice == "2":
                await self._edit_character_menu(current_story)
            elif choice == "3":
                await self._view_character_details_menu(current_story)
            elif choice == "4":
                await self._remove_character_menu(current_story)
            elif choice == "5":
                return
            else:
                print("Opção inválida.")

    async def _create_character_menu(self) -> None:
        """Exibe menu para criação de personagem"""
        print("\nCriando novo personagem...")
        
        name = input("Nome do personagem: ")
        role = input("Papel do personagem: ")
        description = input("Descrição do personagem: ")
        
        try:
            character = await self.create_character(name, role, description)
            print(f"Personagem {name} criado com sucesso!")
            return character
        except Exception as e:
            print(f"Erro ao criar personagem: {e}")

    async def _edit_character_menu(self, current_story: Dict[str, Any]) -> None:
        """Exibe menu para edição de personagem"""
        if not current_story.get("characters"):
            print("Nenhum personagem disponível.")
            return
        
        print("\nSelecione o personagem para editar:")
        for i, character in enumerate(current_story["characters"], 1):
            print(f"{i}. {character['name']} - {character['role']}")
        
        try:
            choice = int(input("\nEscolha um personagem: "))
            if 1 <= choice <= len(current_story["characters"]):
                selected_char = current_story["characters"][choice - 1]
                await self._perform_character_edit(selected_char)
            else:
                print("Opção inválida.")
        except ValueError:
            print("Por favor, insira um número válido.")

    async def _perform_character_edit(self, character: Dict[str, Any]) -> None:
        """Realiza a edição do personagem"""
        print(f"\nEditando personagem: {character['name']}")
        print("Deixe em branco para manter o valor atual")
        
        updates = {
            "name": input(f"Nome [{character['name']}]: ") or character["name"],
            "role": input(f"Papel [{character['role']}]: ") or character["role"],
            "description": input(f"Descrição [{character['description']}]: ") or character["description"]
        }
        
        try:
            await self.update_character(character["id"], updates)
            print("Personagem atualizado com sucesso!")
        except Exception as e:
            print(f"Erro ao atualizar personagem: {e}")

    async def _view_character_details_menu(self, current_story: Dict[str, Any]) -> None:
        """Exibe menu para visualização de detalhes do personagem"""
        if not current_story.get("characters"):
            print("Nenhum personagem disponível.")
            return
        
        print("\nSelecione o personagem para ver detalhes:")
        for i, character in enumerate(current_story["characters"], 1):
            print(f"{i}. {character['name']} - {character['role']}")
        
        try:
            choice = int(input("\nEscolha um personagem: "))
            if 1 <= choice <= len(current_story["characters"]):
                selected_char = current_story["characters"][choice - 1]
                await self._show_character_info(selected_char)
            else:
                print("Opção inválida.")
        except ValueError:
            print("Por favor, insira um número válido.")

    async def _show_character_info(self, character: Dict[str, Any]) -> None:
        """Exibe informações detalhadas do personagem"""
        print(f"\n=== Detalhes do Personagem ===")
        print(f"Nome: {character['name']}")
        print(f"Papel: {character['role']}")
        print(f"Descrição: {character['description']}")
        print(f"Voz: {character['voice']}")
        
        # Mostrar relacionamentos
        relationships = await self.get_relationships(character["id"])
        if relationships:
            print("\nRelacionamentos:")
            for rel in relationships:
                print(f"- {rel['relationship_type']} com {rel['target_id']}")
        
        # Mostrar memórias
        memories = await self.get_memories(character["id"])
        if memories:
            print("\nÚltimas memórias:")
            for mem in memories[:3]:  # Mostrar apenas as 3 últimas
                print(f"- {mem['content']}")

    async def _remove_character_menu(self, current_story: Dict[str, Any]) -> None:
        """Exibe menu para remoção de personagem"""
        if not current_story.get("characters"):
            print("Nenhum personagem disponível.")
            return
        
        print("\nSelecione o personagem para remover:")
        for i, character in enumerate(current_story["characters"], 1):
            print(f"{i}. {character['name']} - {character['role']}")
        
        try:
            choice = int(input("\nEscolha um personagem: "))
            if 1 <= choice <= len(current_story["characters"]):
                selected_char = current_story["characters"][choice - 1]
                confirm = input(f"Tem certeza que deseja remover {selected_char['name']}? (s/n): ")
                if confirm.lower() == 's':
                    await self.delete_character(selected_char["id"])
                    current_story["characters"].pop(choice - 1)
                    print("Personagem removido com sucesso.")
            else:
                print("Opção inválida.")
        except ValueError:
            print("Por favor, insira um número válido.")
