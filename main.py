"""
Módulo Principal do TaleWeaver

Este módulo gerencia o fluxo principal do programa TaleWeaver,
incluindo:
- Inicialização do sistema
- Menu interativo
- Gerenciamento de histórias
- Interação com personagens
- Gerenciamento de contexto
"""

import asyncio
import sys
from typing import Optional, Dict, Any
from config import ConfigManager
from database import AsyncDatabaseManager
from story_manager import StoryManager

class TaleWeaverApp:
    def __init__(self):
        self.config = ConfigManager()
        self.db: Optional[AsyncDatabaseManager] = None
        self.story_manager: Optional[StoryManager] = None
        self.running = False

    async def initialize(self) -> None:
        """Inicializa o sistema TaleWeaver"""
        try:
            # Configura logger
            from logger import setup_logger
            self.logger = setup_logger(self.config)
            self.logger.info("Inicializando TaleWeaver...")
            
            # Inicializa banco de dados
            self.db = AsyncDatabaseManager(self.config)
            await self.db.initialize()
            
            # Inicializa gerenciador de histórias
            self.story_manager = StoryManager(self.config, self.db)
            await self.story_manager.initialize()
            
            # Inicializa gerenciador de personagens
            await self.config.initialize_character_manager(self.db)
            
            # Inicializa cliente LLM
            await self.story_manager.initialize_llm_client()
            
            # Verifica se há história em andamento
            self.current_story = await self.story_manager.get_current_story()
            
            self.running = True
            print("TaleWeaver inicializado com sucesso!")
        except Exception as e:
            print(f"Erro ao inicializar TaleWeaver: {e}")
            sys.exit(1)


    async def run(self) -> None:
        """Executa o loop principal do programa"""
        try:
            while self.running:
                await self._show_main_menu()
                choice = await self._get_user_choice()
                await self._handle_menu_choice(choice)
        except KeyboardInterrupt:
            print("\nEncerrando TaleWeaver...")
        except Exception as e:
            print(f"Erro durante execução: {e}")
        finally:
            await self.cleanup()

    async def _show_main_menu(self) -> None:
        """Exibe o menu principal"""
        print("\n=== TaleWeaver - Menu Principal ===")
        print("1. Iniciar nova história")
        print("2. Continuar história existente")
        print("3. Gerenciar personagens")
        print("4. Ver contexto atual")
        print("5. Ver lembranças")
        print("6. Configurações")
        print("7. Sair")

    async def _get_user_choice(self) -> int:
        """Obtém a escolha do usuário"""
        while True:
            try:
                choice = input("\nEscolha uma opção: ")
                return int(choice)
            except ValueError:
                print("Por favor, insira um número válido.")

    async def _handle_menu_choice(self, choice: int) -> None:
        """Processa a escolha do menu"""
        handlers = {
            1: self._start_new_story,
            2: self._continue_story,
            3: self._manage_characters,
            4: self._show_current_context,
            5: self._show_memories,
            6: self._show_settings,
            7: self._exit_app
        }
        
        handler = handlers.get(choice, self._invalid_choice)
        await handler()

    async def _start_new_story(self) -> None:
        """Inicia uma nova história"""
        try:
            self.current_story = await self.story_manager.create_new_story()
        except Exception as e:
            print(f"Erro ao criar nova história: {e}")

    async def _continue_story(self) -> None:
        """Continua uma história existente"""
        if not self.current_story:
            print("Nenhuma história ativa encontrada.")
            return
        
        print(f"\nContinuando história: {self.current_story['summary']}")
        await self._interact_with_characters()

    async def _interact_with_characters(self) -> None:
        """Gerencia a interação com os personagens"""
        if not self.current_story:
            print("Nenhuma história ativa.")
            return
        
        print("\n=== Interação com Personagens ===")
        print("1. Falar com personagem")
        print("2. Ver informações do personagem")
        print("3. Voltar ao menu principal")
        
        choice = await self._get_user_choice()
        
        if choice == 1:
            await self._talk_to_character()
        elif choice == 2:
            await self._view_character_info()
        elif choice == 3:
            return
        else:
            print("Opção inválida.")

    async def _talk_to_character(self) -> None:
        """Interage com um personagem específico"""
        if not self.current_story or not self.current_story.get("characters"):
            print("Nenhum personagem disponível.")
            return
        
        print("\nSelecione um personagem:")
        for i, character in enumerate(self.current_story["characters"], 1):
            print(f"{i}. {character['name']} - {character['role']}")
        
        try:
            choice = int(input("\nEscolha um personagem: "))
            if 1 <= choice <= len(self.current_story["characters"]):
                selected_char = self.current_story["characters"][choice - 1]
                await self._start_conversation(selected_char)
            else:
                print("Opção inválida.")
        except ValueError:
            print("Por favor, insira um número válido.")

    async def _start_conversation(self, character: Dict[str, Any]) -> None:
        """Inicia uma conversa com o personagem selecionado"""
        print(f"\nIniciando conversa com {character['name']}...")
        # TODO: Implementar lógica de conversação com LLM
        print(f"{character['name']}: Olá, viajante! Como posso ajudar?")
        
        while True:
            user_input = input("\nVocê: ")
            if user_input.lower() in ["sair", "voltar"]:
                break
            # TODO: Processar input do usuário e gerar resposta do personagem
            print(f"{character['name']}: Isso é interessante...")

    async def _manage_characters(self) -> None:
        """Gerencia os personagens da história"""
        if not self.config.character_manager:
            print("Erro: CharacterManager não inicializado")
            return
        
        await self.config.character_manager.manage_characters_menu(self.current_story)

    async def _show_current_context(self) -> None:
        """Exibe o contexto atual da história"""
        if not self.current_story:
            print("Nenhuma história ativa encontrada.")
            return
        
        print("\n=== Contexto Atual ===")
        print(f"Resumo: {self.current_story['summary']}")
        print(f"Cena atual: {self.current_story['current_scene']}")

    async def _show_memories(self) -> None:
        """Exibe as lembranças dos personagens"""
        print("\nExibindo lembranças...")
        # Implementar lógica de exibição de lembranças
        pass

    async def _show_settings(self) -> None:
        """Exibe e gerencia as configurações"""
        print("\nExibindo configurações...")
        # Implementar lógica de configurações
        pass

    async def _exit_app(self) -> None:
        """Encerra o programa"""
        self.running = False
        print("Encerrando TaleWeaver...")

    async def _invalid_choice(self) -> None:
        """Lida com escolhas inválidas"""
        print("Opção inválida. Por favor, tente novamente.")

    async def cleanup(self) -> None:
        """Limpeza antes de encerrar"""
        if self.db:
            await self.db.close()
        if self.story_manager:
            await self.story_manager.close()
        print("TaleWeaver encerrado com sucesso.")

async def main():
    app = TaleWeaverApp()
    await app.initialize()
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
