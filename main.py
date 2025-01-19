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
from narrator_system import NarratorSystem

class TaleWeaverApp:
    def __init__(self):
        self.config = ConfigManager()
        self.db: Optional[AsyncDatabaseManager] = None
        self.story_manager: Optional[StoryManager] = None
        self.narrator_system: Optional[NarratorSystem] = None
        self.running = False

    async def initialize(self) -> None:
        """Inicializa o sistema TaleWeaver"""
        try:
            # Configura logger
            from logger import setup_logger
            self.logger = setup_logger(self.config)
            self.logger.get_logger("main").info("Inicializando TaleWeaver...")
            
            # Inicializa banco de dados
            self.db = AsyncDatabaseManager(self.config)
            if not self.db:
                raise ValueError("Falha ao criar instância do banco de dados")
            await self.db.initialize()
            print("Banco de dados inicializado com sucesso")
            
            # Inicializa gerenciador de personagens
            print("Inicializando gerenciador de personagens...")
            await self.config.initialize_character_manager(self.db)
            print("Gerenciador de personagens inicializado")
            
            # Inicializa gerenciador de histórias
            print("Inicializando gerenciador de histórias...")
            self.story_manager = StoryManager(self.config, self.db)
            if not self.story_manager:
                raise ValueError("Falha ao criar gerenciador de histórias")
            await self.story_manager.initialize()
            print("Gerenciador de histórias inicializado")
            
            # Inicializa sistema de voz
            print("Inicializando sistema de voz...")
            await self.config.initialize_voice_system()
            print("Sistema de voz inicializado")
            
            # Inicializa sistema de narradores
            print("Inicializando sistema de narradores...")
            self.narrator_system = NarratorSystem(self.config)
            if not self.narrator_system:
                raise ValueError("Falha ao criar sistema de narradores")
            await self.narrator_system.initialize()
            print("Sistema de narradores inicializado")
            
            # Configura narrador padrão
            print("Configurando narrador padrão...")
            await self.narrator_system.set_narrator('descriptive')
            print("Narrador configurado com sucesso")
            
            # Verifica se há história em andamento
            print("Verificando história atual...")
            self.current_story = await self.story_manager.get_current_story()
            if self.current_story:
                print(f"História atual: {self.current_story.get('summary', 'Sem resumo')}")
            else:
                print("Nenhuma história ativa encontrada")
            
            self.running = True
            print("TaleWeaver inicializado com sucesso!")
        except Exception as e:
            print(f"\nERRO CRÍTICO ao inicializar TaleWeaver: {e}")
            print("Detalhes do erro:")
            print(f"- Tipo: {type(e).__name__}")
            print(f"- Mensagem: {str(e)}")
            print("\nEstado do sistema antes do erro:")
            print(f"- Banco de dados: {'OK' if self.db else 'Falha'}")
            print(f"- Gerenciador de histórias: {'OK' if self.story_manager else 'Falha'}")
            print(f"- Sistema de narradores: {'OK' if self.narrator_system else 'Falha'}")
            print(f"- Sistema de voz: {'OK' if hasattr(self.config, 'voice_system') else 'Falha'}")
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
        print("4. Selecionar narrador")
        print("5. Ver contexto atual")
        print("6. Ver lembranças")
        print("7. Configurações")
        print("8. Sair")

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
            4: self._select_narrator,
            5: self._show_current_context,
            6: self._show_memories,
            7: self._show_settings,
            8: self._exit_app
        }
        
        handler = handlers.get(choice, self._invalid_choice)
        await handler()

    async def _start_new_story(self) -> None:
        """Inicia uma nova história"""
        try:
            # Cria a nova história
            self.current_story = await self.story_manager.create_new_story()
            
            # Cria os personagens principais
            await self._create_main_characters()
            
            # Cria o personagem do player
            await self._create_player_character()
            
            # Inicia a interação
            await self._interact_with_characters()
            
        except Exception as e:
            print(f"Erro ao criar nova história: {e}")

    async def _create_main_characters(self) -> None:
        """Cria os personagens principais da história"""
        if not self.current_story or not self.config.character_manager:
            return
            
        for character_data in self.current_story.get('characters', []):
            await self.config.character_manager.create_character(
                name=character_data['name'],
                role=character_data['role'],
                description=character_data['description'],
                personality=character_data.get('personality', 'Personalidade padrão'),
                is_player=False
            )

    async def _create_player_character(self) -> None:
        """Cria o personagem do jogador"""
        if not self.config.character_manager:
            return
            
        player_name = input("\nDigite o nome do seu personagem: ")
        player_role = "Player"
        player_desc = "O protagonista controlado pelo jogador"
        player_personality = input("Descreva a personalidade do seu personagem: ")
        
        await self.config.character_manager.create_character(
            name=player_name,
            role=player_role,
            description=player_desc,
            personality=player_personality,
            is_player=True
        )

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
        
        # Configuração inicial do contexto
        context = {
            'character': character,
            'history': await self._get_conversation_history(character['id']),
            'scene': self.current_story['current_scene'],
            'relationships': await self._get_character_relationships(character['id'])
        }
        
        # Mensagem inicial do personagem
        initial_message = await self._generate_llm_response(
            context=context,
            prompt=f"Como {character['name']}, dê as boas-vindas ao jogador de forma apropriada para o contexto atual"
        )
        print(f"{character['name']}: {initial_message}")
        await self._play_character_voice(character, initial_message)
        
        while True:
            try:
                user_input = input("\nVocê: ")
                if user_input.lower() in ["sair", "voltar"]:
                    break
                    
                # Atualiza contexto com nova interação
                context['user_input'] = user_input
                
                # Gera resposta do personagem
                response = await self._generate_llm_response(
                    context=context,
                    prompt=f"Como {character['name']}, responda ao jogador mantendo a personalidade e contexto"
                )
                
                # Processa resposta para separar narração e diálogo
                narration, dialogue = self._process_llm_response(response)
                
                if narration:
                    print(f"\nNarrador: {narration}")
                    await self._play_narrator_voice(narration)
                
                print(f"{character['name']}: {dialogue}")
                await self._play_character_voice(character, dialogue)
                
                # Atualiza histórico da conversa
                await self._update_conversation_history(
                    character['id'],
                    user_input,
                    response
                )
                
            except Exception as e:
                print(f"Erro durante a conversa: {e}")
                self.logger.error(f"Erro na conversa com {character['name']}: {str(e)}")
                break

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

    async def _select_narrator(self) -> None:
        """Permite ao usuário selecionar o narrador"""
        if not self.narrator_system:
            print("Erro: Sistema de narradores não inicializado")
            return
            
        print("\n=== Seleção de Narrador ===")
        print("1. Narrador Descritivo (padrão)")
        print("   - Narra a cena de forma neutra e descritiva")
        print("   - Voz: narrator_descriptive.wav")
        print("2. Narrador Sassy")
        print("   - Adiciona comentários irônicos e humorísticos")
        print("   - Voz: narrator_sassy.wav")
        
        try:
            choice = int(input("\nEscolha um narrador: "))
            if choice == 1:
                await self.narrator_system.set_narrator('descriptive')
                print("Narrador Descritivo selecionado!")
            elif choice == 2:
                await self.narrator_system.set_narrator('sassy')
                print("Narrador Sassy selecionado!")
            else:
                print("Opção inválida. Mantendo narrador atual.")
        except ValueError:
            print("Entrada inválida. Por favor, insira 1 ou 2.")

    async def _invalid_choice(self) -> None:
        """Lida com escolhas inválidas"""
        print("Opção inválida. Por favor, tente novamente.")

    async def _generate_llm_response(self, context: Dict[str, Any], prompt: str) -> str:
        """Gera resposta do LLM com base no contexto e prompt
        
        Args:
            context: Dicionário com contexto atual da conversa
            prompt: Instrução específica para o LLM
            
        Returns:
            Resposta gerada pelo LLM
        """
        try:
            if not self.story_manager or not self.story_manager.llm_client:
                raise ValueError("Cliente LLM não inicializado")
                
            # Prepara mensagem do sistema com contexto
            system_message = (
                f"Você é {context['character']['name']}, um personagem com as seguintes características:\n"
                f"- Personalidade: {context['character']['personality']}\n"
                f"- Papel na história: {context['character']['role']}\n"
                f"- Relacionamentos: {', '.join(context['relationships'])}\n"
                f"\nContexto atual:\n"
                f"- Cena: {context['scene']}\n"
                f"- Histórico recente: {context['history'][-3:] if context['history'] else 'Nenhum'}"
            )
            
            # Prepara histórico de conversa
            messages = [
                {"role": "system", "content": system_message},
                *[
                    {"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                    for i, msg in enumerate(context['history'])
                ],
                {"role": "user", "content": context.get('user_input', '')}
            ]
            
            # Gera resposta do LLM
            response = await self.story_manager.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar resposta LLM: {str(e)}")
            return f"Desculpe, estou tendo dificuldades para responder. Erro: {str(e)}"

    def _process_llm_response(self, response: str) -> tuple[str, str]:
        """Processa a resposta do LLM separando narração de diálogo
        
        Args:
            response: Resposta completa do LLM
            
        Returns:
            Tupla contendo (narração, diálogo)
        """
        try:
            # Separa narração (se existir) do diálogo
            if "Narrador:" in response:
                narration_part, dialogue_part = response.split("Narrador:", 1)
                narration = narration_part.strip()
                dialogue = dialogue_part.strip()
            else:
                narration = ""
                dialogue = response.strip()
                
            # Limpa formatação básica
            narration = narration.replace("*", "").strip()
            dialogue = dialogue.replace("*", "").strip()
            
            # Valida tamanho mínimo
            if len(dialogue) < 2:
                dialogue = "..."
                
            return narration, dialogue
            
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta LLM: {str(e)}")
            return "", f"Desculpe, houve um erro ao processar minha resposta."

    async def _get_conversation_history(self, character_id: str) -> list[str]:
        """Recupera o histórico de conversas de um personagem
        
        Args:
            character_id: ID do personagem
            
        Returns:
            Lista de mensagens formatadas
        """
        try:
            if not self.db:
                raise ValueError("Banco de dados não inicializado")
                
            # Recupera histórico do banco de dados
            history = await self.db.get_conversation_history(character_id)
            
            # Formata as mensagens
            formatted_history = []
            for entry in history[-10:]:  # Limita a 10 interações mais recentes
                formatted_history.append(f"Jogador: {entry['user_input']}")
                formatted_history.append(f"{entry['character_name']}: {entry['character_response']}")
                
            return formatted_history
            
        except Exception as e:
            self.logger.error(f"Erro ao recuperar histórico de conversas: {str(e)}")
            return []

    async def _get_character_relationships(self, character_id: str) -> list[str]:
        """Recupera os relacionamentos de um personagem
        
        Args:
            character_id: ID do personagem
            
        Returns:
            Lista de relacionamentos formatados
        """
        try:
            if not self.db:
                raise ValueError("Banco de dados não inicializado")
                
            # Recupera relacionamentos do banco de dados
            relationships = await self.db.get_character_relationships(character_id)
            
            # Formata os relacionamentos
            formatted_relationships = []
            for rel in relationships:
                if rel['type'] == 'primary':
                    formatted_relationships.append(
                        f"{rel['target_name']} ({rel['relationship']})"
                    )
                else:
                    formatted_relationships.append(
                        f"{rel['target_name']} ({rel['relationship']}, secundário)"
                    )
                    
            return formatted_relationships
            
        except Exception as e:
            self.logger.error(f"Erro ao recuperar relacionamentos: {str(e)}")
            return []

    async def _update_conversation_history(
        self,
        character_id: str,
        user_input: str,
        character_response: str
    ) -> None:
        """Atualiza o histórico de conversas no banco de dados
        
        Args:
            character_id: ID do personagem
            user_input: Entrada do usuário
            character_response: Resposta do personagem
        """
        try:
            if not self.db:
                raise ValueError("Banco de dados não inicializado")
                
            if not character_id or not user_input or not character_response:
                raise ValueError("Dados inválidos para atualização do histórico")
                
            await self.db.update_conversation_history(
                character_id=character_id,
                user_input=user_input,
                character_response=character_response
            )
            
        except Exception as e:
            self.logger.error(f"Erro ao atualizar histórico de conversas: {str(e)}")

    async def _play_character_voice(self, character: Dict[str, Any], text: str) -> None:
        """Reproduz a voz do personagem para o texto fornecido
        
        Args:
            character: Dicionário com informações do personagem
            text: Texto a ser convertido em fala
        """
        try:
            if not self.config.voice_system:
                raise ValueError("Sistema de voz não configurado")
                
            # Verifica se o personagem tem uma voz específica
            voice_profile = character.get('voice_profile', 'default')
            
            # Converte texto em áudio
            audio_data = await self.config.voice_system.text_to_speech(
                text=text,
                voice_profile=voice_profile
            )
            
            # Reproduz o áudio
            await self.config.voice_system.play_audio(audio_data)
            
        except Exception as e:
            self.logger.error(f"Erro ao reproduzir voz do personagem: {str(e)}")
            print(f"Erro ao reproduzir voz: {str(e)}")

    async def _play_narrator_voice(self, text: str) -> None:
        """Reproduz a voz do narrador para o texto fornecido
        
        Args:
            text: Texto a ser convertido em fala
        """
        try:
            if not self.config.voice_system:
                raise ValueError("Sistema de voz não configurado")
                
            # Usa perfil de voz específico para narração
            audio_data = await self.config.voice_system.text_to_speech(
                text=text,
                voice_profile='narrator'
            )
            
            # Reproduz o áudio
            await self.config.voice_system.play_audio(audio_data)
            
        except Exception as e:
            self.logger.error(f"Erro ao reproduzir voz do narrador: {str(e)}")
            print(f"Erro ao reproduzir narração: {str(e)}")

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
