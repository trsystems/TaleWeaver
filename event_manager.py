from typing import Callable, Dict, List, Any
from PyQt6.QtCore import QObject, pyqtSignal
import asyncio
from dataclasses import dataclass
from enum import Enum
from log_manager import LogManager

class EventType(Enum):
    MESSAGE = "message"
    CONTEXT_UPDATE = "context_update"
    MEMORY_UPDATE = "memory_update"
    ERROR = "error"
    AUDIO_START = "audio_start"
    AUDIO_END = "audio_end"
    EMOTION_UPDATE = "emotion_update"
    PROCESSING_START = "processing_start"
    PROCESSING_END = "processing_end"
    NEW_CHARACTER = "new_character"        
    CHARACTER_CREATED = "character_created"

@dataclass
class StoryEvent:
    type: EventType
    sender: str
    data: Dict[str, Any]

class EventManager(QObject):
    # Sinais Qt
    message_received = pyqtSignal(str, bool, str, str, bool, str, bool, bool)  # text, is_user, sender, avatar, is_audio, audio_file, is_typing, should_scroll
    typing_started = pyqtSignal(str)  # sender
    typing_ended = pyqtSignal(str)  # sender
    recording_started = pyqtSignal(str)  # sender
    recording_ended = pyqtSignal(str)  # sender
    typing_removed = pyqtSignal(str)  # sender
    recording_removed = pyqtSignal(str)  # sender
    context_updated = pyqtSignal(str)
    memory_updated = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)
    emotion_updated = pyqtSignal(str, str, float)
    processing_started = pyqtSignal()
    processing_ended = pyqtSignal()
    new_character = pyqtSignal(str, dict)  # nome, perfil
    character_created = pyqtSignal(str)     # mensagem de confirmação

    def __init__(self):
        super().__init__()
        self._subscribers = {event_type: [] for event_type in EventType}
        self._processed_events = {}
        self._event_lock = asyncio.Lock()

class EventManager(QObject):
    # Atualizar a definição do signal para incluir todos os parâmetros necessários
    message_received = pyqtSignal(str, bool, str, str, bool, str, bool, bool)  # text, is_user, sender, avatar, is_audio, audio_file, is_typing, should_scroll

    async def emit(self, event: StoryEvent):
        """Emite um evento com controle de duplicação por message_id"""
        async with self._event_lock:
            try:
                if event.type == EventType.MESSAGE:
                    # Ignora mensagens vazias que não são áudio
                    if not (event.data.get("text") or event.data.get("is_audio")):
                        LogManager.debug(f"Ignorando mensagem vazia", "EventManager")
                        return

                    # Emite evento com todos os parâmetros necessários
                    data = event.data
                    self.message_received.emit(
                        data.get("text", ""),                  # text
                        data.get("is_user", False),           # is_user
                        event.sender,                         # sender
                        data.get("avatar_path", ""),          # avatar
                        data.get("is_audio", False),          # is_audio
                        data.get("audio_file", ""),           # audio_file
                        data.get("is_typing", False),         # is_typing
                        data.get("should_scroll", True)       # should_scroll
                    )

                elif event.type == EventType.CONTEXT_UPDATE:
                    self.context_updated.emit(event.data.get("text", ""))

                elif event.type == EventType.MEMORY_UPDATE:
                    self.memory_updated.emit(
                        event.data.get("character_name", ""),
                        event.data.get("text", "")
                    )

                elif event.type == EventType.ERROR:
                    self.error_occurred.emit(event.data.get("text", ""))

                elif event.type == EventType.EMOTION_UPDATE:
                    self.emotion_updated.emit(
                        event.data.get("character", ""),
                        event.data.get("emotion", ""),
                        event.data.get("intensity", 0.0)
                    )

                elif event.type == EventType.PROCESSING_START:
                    self.processing_started.emit()

                elif event.type == EventType.PROCESSING_END:
                    self.processing_ended.emit()

                elif event.type == EventType.NEW_CHARACTER:
                    self.new_character.emit(
                        event.data.get("name", ""),
                        event.data.get("profile", {})
                    )

                elif event.type == EventType.CHARACTER_CREATED:
                    self.character_created.emit(event.data.get("text", ""))

                elif event.type == EventType.AUDIO_START:
                    self.audio_started.emit(event.data.get("audio_file", ""))

                elif event.type == EventType.AUDIO_END:
                    self.audio_ended.emit(event.data.get("audio_file", ""))

            except Exception as e:
                LogManager.error(f"Erro ao emitir evento: {e}", "EventManager")

    def subscribe(self, event_type: EventType, callback: Callable):
        """Registra um callback para um tipo de evento"""
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Remove um callback registrado"""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def clear_subscribers(self):
        """Remove todos os subscribers"""
        for event_type in EventType:
            self._subscribers[event_type].clear()