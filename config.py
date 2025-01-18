"""
Módulo de Gerenciamento de Configurações

Este módulo gerencia todas as configurações do sistema TaleWeaver,
incluindo:
- Configurações de banco de dados
- Configurações de LLM
- Configurações de interface
- Configurações de áudio
- Configurações de sistema
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    path: str = "data"
    main_db: str = "tale_weaver.db"
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutos

@dataclass
class LLMConfig:
    model: str = "lmstudio"
    temperature: float = 0.7
    max_tokens: int = 1000
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"

@dataclass
class AudioConfig:
    voice_system: str = "xtts2"
    voice_dir: str = "voices"
    sample_rate: int = 24000
    volume: float = 1.0

@dataclass
class SystemConfig:
    log_level: str = "INFO"
    max_log_files: int = 10
    max_log_size: int = 10485760  # 10MB
    auto_save_interval: int = 300  # 5 minutos

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self.default_config = {
            "database": DatabaseConfig().__dict__,
            "llm": LLMConfig().__dict__,
            "audio": AudioConfig().__dict__,
            "system": SystemConfig().__dict__,
            "characters": {
                "max_characters": 20,
                "default_voice": "narrator_voice.wav",
                "voice_dir": "voices"
            },
            "logging": {
                "enabled_modules": {
                    "main": True,
                    "database": True,
                    "story": True,
                    "character": True,
                    "config": True
                },
                "default_level": "INFO"
            }
        }
        
        self.load_config()
        self.character_manager = None
        
    async def initialize_character_manager(self, db_manager):
        """Inicializa o CharacterManager com o DatabaseManager"""
        from character_manager import CharacterManager
        self.character_manager = CharacterManager(
            db=db_manager,
            config=self
        )
        await self.character_manager.initialize()

    def get_module_logging(self, module_name: str) -> bool:
        """Verifica se logging está ativado para um módulo específico"""
        return self.get(f"logging.enabled_modules.{module_name}", True)

    def set_module_logging(self, module_name: str, enabled: bool) -> None:
        """Ativa/desativa logging para um módulo específico"""
        self.set(f"logging.enabled_modules.{module_name}", enabled)

    def load_config(self) -> None:
        """Carrega configurações do arquivo ou usa padrões"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.default_config
                self.save_config()
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
            self.config = self.default_config

    def save_config(self) -> None:
        """Salva configurações no arquivo"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Obtém valor de configuração"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Define valor de configuração"""
        keys = key.split('.')
        current = self.config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
        self.save_config()

    def validate_config(self) -> bool:
        """Valida as configurações atuais"""
        # Implementar validações específicas
        return True

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False
