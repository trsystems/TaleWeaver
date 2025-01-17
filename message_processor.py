from typing import Optional
import time
import asyncio
from PyQt6.QtCore import QObject
from emotion_system import EmotionalResponse
from event_manager import StoryEvent, EventType
from character_models import Character
from log_manager import LogManager

class MessageProcessor(QObject):
   def __init__(self, story_chat, event_manager):
       super().__init__()
       self.story_chat = story_chat
       self.event_manager = event_manager
       self.is_processing = False

   async def process_message(self, text: str, character: Optional[Character] = None):
    try:
        if self.is_processing:
            return
            
        self.is_processing = True
        
        # Validação do personagem
        if not character:
            LogManager.error("Nenhum personagem fornecido para processar mensagem", "MessageProcessor")
            return
            
        sender = character.name or "Narrador"
        avatar_path = f"avatars/{sender.lower()}.png"
        voice_file = character.voice_file
        
        LogManager.info(f"Iniciando processamento como {sender} usando voz: {voice_file}", "MessageProcessor")

        # Gera resposta usando o personagem correto
        response = await self.story_chat.generate_response(text, character)
        if not response:
            raise Exception("Não foi possível gerar uma resposta")

        # Processa segmentos - melhorado para garantir processamento completo
        segments = response.text.split(". ")
        segments = [s.strip() + "." for s in segments if s.strip()]
        
        audio_tasks = []  # Lista para controlar tasks de áudio
        
        for i, segment in enumerate(segments, 1):
            segment_id = f"segment_{int(time.time())}_{i}"
            
            # Emite evento de texto
            await self.event_manager.emit(StoryEvent(
                type=EventType.MESSAGE,
                sender=sender,
                data={
                    "text": segment,
                    "avatar_path": avatar_path,
                    "should_scroll": True,
                    "message_id": f"text_{segment_id}"
                }
            ))

            try:
                # Processa áudio usando a voz correta do personagem
                audio_task = self.story_chat.audio_processor.synthesize_speech(
                    EmotionalResponse(
                        text=segment,
                        emotion=response.emotion,
                        params=response.params
                    ),
                    character
                )
                
                audio_tasks.append(audio_task)
                
                LogManager.debug(f"Task de áudio criada para segmento {i} de {sender}", "MessageProcessor")

            except Exception as e:
                LogManager.error(f"Erro ao criar task de áudio para segmento {i}: {e}", "MessageProcessor")
                continue

        # Aguarda todas as tasks de áudio completarem
        if audio_tasks:
            try:
                # Processa todos os áudios em paralelo
                await asyncio.gather(*audio_tasks)
                LogManager.info(f"Todos os segmentos de áudio processados para {sender}", "MessageProcessor")
            except Exception as e:
                LogManager.error(f"Erro ao processar tasks de áudio: {e}", "MessageProcessor")

    except Exception as e:
        LogManager.error(f"Erro no processamento da mensagem: {str(e)}", "MessageProcessor")
    finally:
        self.is_processing = False