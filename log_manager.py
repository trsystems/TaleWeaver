import logging
from typing import Optional

class LogManager:
    def __init__(self, config: Optional[dict] = None):
        """Inicializa o gerenciador de logs"""
        self.config = config or {}
        self.loggers = {}
        self._setup_logging()

    def _setup_logging(self):
        """Configura o sistema de logging"""
        logging.basicConfig(
            level=self.config.get('log_level', logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.get('log_file', 'taleweaver.log')),
                logging.StreamHandler()
            ]
        )

    def get_logger(self, name: str) -> logging.Logger:
        """Obtém ou cria um logger com o nome especificado
        
        Args:
            name: Nome do logger
            
        Returns:
            Instância do logger configurado
        """
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]

    def error(self, logger_name: str, message: str) -> None:
        """Registra uma mensagem de erro
        
        Args:
            logger_name: Nome do logger
            message: Mensagem de erro
        """
        logger = self.get_logger(logger_name)
        logger.error(message)

    def warning(self, logger_name: str, message: str) -> None:
        """Registra uma mensagem de aviso
        
        Args:
            logger_name: Nome do logger
            message: Mensagem de aviso
        """
        logger = self.get_logger(logger_name)
        logger.warning(message)

    def info(self, logger_name: str, message: str) -> None:
        """Registra uma mensagem informativa
        
        Args:
            logger_name: Nome do logger
            message: Mensagem informativa
        """
        logger = self.get_logger(logger_name)
        logger.info(message)

    def debug(self, logger_name: str, message: str) -> None:
        """Registra uma mensagem de debug
        
        Args:
            logger_name: Nome do logger
            message: Mensagem de debug
        """
        logger = self.get_logger(logger_name)
        logger.debug(message)