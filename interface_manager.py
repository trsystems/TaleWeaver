"""
Interface Manager - Gerencia a interação entre GUI e processamento assíncrono
"""
import asyncio
import time
from typing import Optional, Dict
from PyQt6.QtCore import QThread, pyqtSignal
from character_models import Character
from event_manager import EventType, StoryEvent
from message_processor import MessageProcessor
from log_manager import LogManager
from ui_utils import Colors

class AsyncProcessingThread(QThread):
    """Thread dedicada para processamento assíncrono"""
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, coro, parent=None):
        super().__init__(parent)
        self.coro = coro
        # Mantenha uma referência para evitar garbage collection prematura
        self.setParent(parent)  

    def run(self):
        """Executa o processamento assíncrono"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.coro)
            loop.close()
        except Exception as e:
            LogManager.error(f"Erro na execução assíncrona: {e}", "AsyncThread")
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def __del__(self):
        """Garante que a thread seja finalizada corretamente"""
        self.wait()


class InterfaceManager:
    """
    Gerencia a interação entre a interface gráfica e o processamento assíncrono.
    
    Responsabilidades:
    - Coordenar a comunicação entre GUI e lógica de processamento
    - Gerenciar threads assíncronas
    - Controlar estado da interface durante processamento
    - Manipular mensagens e eventos
    """
    def __init__(self, chat_interface, story_chat, event_manager):
        self.interface = chat_interface
        self.story_chat = story_chat
        self.event_manager = event_manager
        self.message_processor = MessageProcessor(story_chat, event_manager)
        self._processing = False
        self._processed_messages = set()
        self._temp_messages: Dict[str, any] = {}  # Para controle de mensagens temporárias
        self._setup_signals()

    def _setup_signals(self):
        """Configura os sinais do processador de mensagens e gerenciador de eventos"""
        try:
            self.event_manager.message_received.connect(self._handle_message)
            self.event_manager.error_occurred.connect(self._on_error)
            LogManager.debug("Sinais configurados com sucesso", "InterfaceManager")
        except Exception as e:
            LogManager.error(f"Erro ao configurar sinais: {e}", "InterfaceManager")

    def _handle_message(self, text: str, is_user: bool, sender: str, 
                    avatar_path: str, is_audio: bool = False, 
                    audio_file: str = None, is_typing: bool = False,
                    should_scroll: bool = False):
        """Manipula mensagens recebidas"""
        try:
            # Cria uma chave única para a mensagem
            timestamp = int(time.time())
            message_key = f"{sender}_{text}_{timestamp}"
            
            # Verifica se a mensagem já foi processada
            if not is_typing and not is_audio and message_key in self._processed_messages:
                LogManager.debug(f"Mensagem já processada: {message_key}", "InterfaceManager")
                return
                
            # Limpa mensagens temporárias anteriores se necessário
            if is_typing or is_audio:
                self._remove_temp_messages(sender)

            # Cria widget de mensagem
            message = self.interface.create_message_widget(
                text=text,
                is_user=is_user,
                sender_name=sender,
                avatar_path=avatar_path,
                is_audio=is_audio,
                audio_file=audio_file,
                is_typing=is_typing
            )

            if message is None:
                return

            # Armazena referência se for mensagem temporária
            if is_typing or is_audio:
                self._temp_messages[message_key] = message
            else:
                # Adiciona à lista de mensagens processadas
                self._processed_messages.add(message_key)

            # Adiciona à interface
            self.interface.add_message_widget(message, should_scroll)
            
            msg_type = 'de typing' if is_typing else 'de áudio' if is_audio else 'de texto'
            LogManager.debug(f"Mensagem {msg_type} adicionada: {message_key}", "InterfaceManager")

        except Exception as e:
            LogManager.error(f"Erro ao manipular mensagem: {e}", "InterfaceManager")
    
    def _remove_temp_messages(self, sender: str):
        """Remove mensagens temporárias de um remetente"""
        try:
            to_remove = []
            for msg_id, msg in self._temp_messages.items():
                if hasattr(msg, 'sender_name') and msg.sender_name == sender:
                    to_remove.append(msg_id)
            
            for msg_id in to_remove:
                if msg_id in self._temp_messages:
                    message = self._temp_messages.pop(msg_id)
                    self.interface.remove_message_widget(message)
                    LogManager.debug(f"Mensagem temporária removida: {msg_id}", "InterfaceManager")
                        
        except Exception as e:
            LogManager.error(f"Erro ao remover mensagens temporárias: {e}", "InterfaceManager")

    def _remove_typing_message(self, sender: str):
        """Remove mensagem de digitação específica"""
        self._remove_temp_messages(sender)

    def _remove_recording_message(self, sender: str):
        """Remove mensagem de gravação específica"""
        self._remove_temp_messages(sender)

    def get_selected_character(self):
        """Obtém o personagem ou narrador selecionado"""
        try:
            char_name = self.interface.character_selector.currentText()
            LogManager.debug(f"Personagem selecionado: {char_name}", "InterfaceManager")
            
            if char_name == "Narrador":
                narrator_profile = self.story_chat.narrator_system.get_current_profile()
                character = Character(
                    name="Narrador",
                    voice_file=narrator_profile.voice_file,
                    system_prompt_file="prompts/narrator_prompt.txt",
                    color=Colors.YELLOW
                )
            else:
                character = self.story_chat.characters.get(char_name)
                LogManager.info(f"Carregando personagem: {char_name}", "InterfaceManager")
                
            if character:
                LogManager.debug(f"Usando voz: {character.voice_file}", "InterfaceManager")
                return character
            return None
                
        except Exception as e:
            LogManager.error(f"Erro ao obter personagem selecionado: {e}", "InterfaceManager")
            return None

    async def process_message(self, text: str, character: Optional[Character] = None):
        """Processa uma mensagem de forma assíncrona"""
        try:
            if self._processing:
                return

            self._processing = True
            self.interface.update_input_state(True)
            LogManager.debug("Iniciado processamento de mensagem", "InterfaceManager")

            # Se não houver character especificado, usa o selecionado
            if character is None:
                character = self.get_selected_character()
        
            LogManager.debug(f"Processando mensagem para: {character.name if character else 'Narrador'}", "InterfaceManager")

            # Adiciona mensagem do usuário
            await self.event_manager.emit(StoryEvent(
                type=EventType.MESSAGE,
                sender="Você",
                data={
                    "text": text,
                    "is_user": True,
                    "avatar_path": "avatars/user.png",
                    "should_scroll": True,
                    "message_id": f"user_{int(time.time())}"
                }
            ))

            # Processa a mensagem
            await self.message_processor.process_message(text, character)

        except Exception as e:
            LogManager.error(f"Erro ao processar mensagem: {e}", "InterfaceManager")
            await self.event_manager.emit(StoryEvent(
                type=EventType.ERROR,
                sender="Sistema",
                data={
                    "text": f"Erro: {str(e)}", 
                    "should_scroll": True,
                    "message_id": f"error_{int(time.time())}"
                }
            ))
        finally:
            self._processing = False
            self.interface.update_input_state(False)

    def _on_error(self, error_msg: str):
        """Callback para tratamento de erros"""
        try:
            LogManager.error(f"Erro reportado: {error_msg}", "InterfaceManager")
            self.interface.show_error(error_msg)
            self.interface.update_input_state(False)
            self._processing = False
        except Exception as e:
            LogManager.error(f"Erro ao tratar erro: {e}", "InterfaceManager")

    def cleanup(self):
        """Limpa recursos ao encerrar"""
        try:
            if self._current_thread:
                self._current_thread.wait()
                self._current_thread = None
                
            self._processing = False
            LogManager.debug("Recursos limpos com sucesso", "InterfaceManager")
            
        except Exception as e:
            LogManager.error(f"Erro ao limpar recursos: {e}", "InterfaceManager")

    async def show_context(self):
        """Mostra o contexto atual da história"""
        try:
            LogManager.debug("Gerando resumo do contexto", "InterfaceManager")
            context_text = await self.story_chat.story_context.get_story_summary(self.story_chat.client)
            
            if context_text:
                await self.event_manager.emit(StoryEvent(
                    type=EventType.MESSAGE,
                    sender="Sistema",
                    data={
                        "text": context_text,
                        "is_user": False,
                        "avatar_path": "avatars/sistema.png",
                        "should_scroll": True,
                        "message_id": f"context_{int(time.time())}"
                    }
                ))
            else:
                await self.event_manager.emit(StoryEvent(
                    type=EventType.MESSAGE,
                    sender="Sistema",
                    data={
                        "text": "\nNenhum contexto disponível ainda.",
                        "is_user": False,
                        "avatar_path": "avatars/sistema.png",
                        "should_scroll": True,
                        "message_id": f"context_{int(time.time())}"
                    }
                ))
                
        except Exception as e:
            LogManager.error(f"Erro ao mostrar contexto: {e}", "InterfaceManager")
            await self._show_error(f"Erro ao mostrar contexto: {e}")

    async def show_memories(self, character_name: str):
        """Mostra memórias de um personagem"""
        try:
            LogManager.debug(f"Buscando memórias de {character_name}", "InterfaceManager")
            memories = self.story_chat.memory_manager.get_formatted_memories(character_name)
            
            if memories:
                await self.event_manager.emit(StoryEvent(
                    type=EventType.MESSAGE,
                    sender="Sistema",
                    data={
                        "text": f"\n=== Memórias de {character_name} ===\n{memories}",
                        "is_user": False,
                        "avatar_path": "avatars/sistema.png",
                        "should_scroll": True,
                        "message_id": f"memories_{int(time.time())}"
                    }
                ))
            else:
                await self.event_manager.emit(StoryEvent(
                    type=EventType.MESSAGE,
                    sender="Sistema",
                    data={
                        "text": f"\n{character_name} ainda não tem memórias registradas.",
                        "is_user": False,
                        "avatar_path": "avatars/sistema.png",
                        "should_scroll": True,
                        "message_id": f"memories_{int(time.time())}"
                    }
                ))
                
        except Exception as e:
            LogManager.error(f"Erro ao mostrar memórias: {e}", "InterfaceManager")
            await self._show_error(f"Erro ao mostrar memórias: {e}")

    async def _show_error(self, error_message: str):
        """Mostra uma mensagem de erro na interface"""
        await self.event_manager.emit(StoryEvent(
            type=EventType.MESSAGE,
            sender="Sistema",
            data={
                "text": f"\nErro: {error_message}",
                "is_user": False,
                "avatar_path": "avatars/sistema.png",
                "should_scroll": True,
                "message_id": f"error_{int(time.time())}"
            }
        ))