import os
from datetime import datetime
from log_manager import LogManager
from memory_manager import Memory

class Character:
    def __init__(self, name: str, voice_file: str = "", system_prompt_file: str = "", color: str = ""):
        self.name = name
        self.voice_file = voice_file if voice_file and os.path.exists(voice_file) else "voices/narrator_voice.wav"  # Usa voz padrão se arquivo não existir
        self.system_prompt_file = system_prompt_file
        self.color = color
        LogManager.debug(f"Character {name} initialized with voice: {self.voice_file}", "Character")

    def _normalize_path(self, path: str, base_folder: str) -> str:
        """Normaliza caminhos para relativos"""
        if os.path.isabs(path):
            filename = os.path.basename(path)
            return os.path.join(base_folder, filename)
        return path

    def get_voice_path(self) -> str:
        """Retorna o caminho completo do arquivo de voz"""
        if not os.path.exists(self.voice_file):
            LogManager.error(f"Voice file not found: {self.voice_file}", "Character")
            return None
        return self.voice_file

    def get_prompt_path(self) -> str:
        """Retorna o caminho completo do arquivo de prompt"""
        if not os.path.exists(self.system_prompt_file):
            LogManager.error(f"Prompt file not found: {self.system_prompt_file}", "Character")
            return None
        return self.system_prompt_file

    

    def load_system_prompt(self) -> str:
        """Carrega o prompt do sistema para o personagem."""
        with open(self.system_prompt_file, 'r', encoding='utf-8') as f:
            return f.read()

    def create_memory(self, 
                     content: str, 
                     context: str, 
                     importance: float = 0.5,
                     emotion: str = "neutral") -> Memory:
        """Cria uma nova memória para o personagem."""
        return Memory(
            timestamp=datetime.now().isoformat(),
            content=content,
            importance=importance,
            context=context,
            emotion=emotion
        )