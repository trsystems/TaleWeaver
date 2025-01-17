from abc import ABC, abstractmethod

class AudioPlayerBase(ABC):
    @abstractmethod
    async def play_audio(self, audio_file: str):
        pass

    @abstractmethod
    def stop(self):
        pass