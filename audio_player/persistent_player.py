from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, Qt
import sys
from queue import Queue

from log_manager import LogManager
from .player_window import AudioPlayerWindow
from .audio_player_base import AudioPlayerBase

class PersistentAudioPlayer(AudioPlayerBase):
    _instance = None
    initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PersistentAudioPlayer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not PersistentAudioPlayer.initialized:
            self.audio_queue = Queue()
            self.app = QApplication.instance() or QApplication(sys.argv)
            self.window = AudioPlayerWindow(self.audio_queue)
            self.window.show()
            PersistentAudioPlayer.initialized = True

    def run(self):
        self.app.processEvents()

    async def play_audio(self, audio_file: str):
        """Implementação do método abstrato play_audio"""
        self.add_to_queue(audio_file)

    def add_to_queue(self, audio_file: str):
        """Adiciona um arquivo de áudio à fila de reprodução."""
        self.audio_queue.put(audio_file)
        self.run()  # Processa eventos para garantir atualização da UI

    def stop(self):
        """Para a reprodução e fecha a janela."""
        if hasattr(self, 'window'):
            self.window.close()

    def cleanup(self):
        """Limpa recursos do player"""
        try:
            if hasattr(self, 'window') and not getattr(self.window, '_closed', True):
                self.window.hide()  # Esconde janela antes de fechar
                self.window.close()
                setattr(self.window, '_closed', True)  # Marca como fechado
        except Exception as e:
            LogManager.debug(f"Aviso na limpeza do PersistentPlayer: {e}", "PersistentPlayer")

    def stop(self):
        """Para reprodução de forma segura"""
        try:
            if hasattr(self, 'window') and not getattr(self.window, '_closed', True):
                self.window.stop()
        except Exception:
            pass

    def __del__(self):
        self.stop()
        self.cleanup()