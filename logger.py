"""
Módulo de Logging para TaleWeaver

Implementa um sistema de logging modular e configurável com:
- Diferentes níveis de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Controle de ativação/desativação por módulo via ConfigManager
- Formatação consistente de logs
- Suporte a arquivo e console
"""

import logging
from typing import Dict, Any
from config import ConfigManager

class TaleWeaverLogger:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configura o sistema de logging"""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=logging.DEBUG if self.config.get("system.log_level", "INFO") == "DEBUG" else logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler("taleweaver.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def get_logger(self, module_name: str) -> logging.Logger:
        """Obtém ou cria um logger para o módulo especificado"""
        if module_name not in self.loggers:
            logger = logging.getLogger(module_name)
            
            # Verifica se o módulo está habilitado para logging
            if not self.config.get_module_logging(module_name):
                logger.disabled = True
                logger.setLevel(logging.CRITICAL)
            else:
                logger.setLevel(self.config.get("system.log_level", "INFO"))
            
            # Adiciona filtro para verificar se o módulo está habilitado
            class ModuleFilter(logging.Filter):
                def __init__(self, config: ConfigManager, module: str):
                    super().__init__()
                    self.config = config
                    self.module = module

                def filter(self, record):
                    return self.config.get_module_logging(self.module)
            
            logger.addFilter(ModuleFilter(self.config, module_name))
            self.loggers[module_name] = logger
            
        return self.loggers[module_name]

    async def close(self) -> None:
        """Limpeza dos handlers de log"""
        for logger in self.loggers.values():
            for handler in logger.handlers:
                handler.close()
                logger.removeHandler(handler)

def setup_logger(config: ConfigManager) -> TaleWeaverLogger:
    """Função factory para criar e configurar o logger principal"""
    return TaleWeaverLogger(config)
