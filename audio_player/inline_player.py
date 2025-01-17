import os
from log_manager import LogManager
from .audio_player_base import AudioPlayerBase
from event_manager import StoryEvent, EventType

class InlineAudioPlayer(AudioPlayerBase):
    def __init__(self, event_manager=None):
        self.event_manager = event_manager
        self.current_file = None

    async def add_to_queue(self, audio_file: str):
        if self.event_manager:
            await self.event_manager.emit(StoryEvent(
                type=EventType.MESSAGE,
                data={
                    "text": "",
                    "is_audio": True,
                    "audio_file": audio_file,
                    "is_system": True
                }
            ))

    async def play_audio(self, audio_file: str):
        await self.add_to_queue(audio_file)

    def stop(self):
        self.current_file = None