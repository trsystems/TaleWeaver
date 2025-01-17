import os
from datetime import datetime

class LogManager:
    debug_mode = False  # Controle global de logs
    log_file = "log/last_execution.log"  # Arquivo de log
    
    @classmethod
    def _ensure_log_directory(cls):
        """Garante que o diretório de log existe"""
        os.makedirs(os.path.dirname(cls.log_file), exist_ok=True)
    
    @classmethod
    def _write_to_log(cls, level: str, module: str, message: str):
        """Escreve uma mensagem no arquivo de log"""
        try:
            cls._ensure_log_directory()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}][{level}][{module}] {message}\n"
            
            # Se for a primeira mensagem, limpa o arquivo
            mode = "a" if os.path.exists(cls.log_file) else "w"
            with open(cls.log_file, mode, encoding='utf-8') as f:
                f.write(log_line)
        except Exception as e:
            print(f"Erro ao escrever no log: {e}")

    @classmethod
    def start_new_session(cls):
        """Inicia uma nova sessão de log"""
        try:
            cls._ensure_log_directory()
            # Limpa o arquivo de log anterior
            with open(cls.log_file, 'w', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"=== Nova Sessão Iniciada em {timestamp} ===\n")
        except Exception as e:
            print(f"Erro ao iniciar nova sessão de log: {e}")

    @staticmethod
    def set_debug_mode(enabled: bool):
        """Ativa ou desativa o modo debug."""
        LogManager.debug_mode = enabled

    @classmethod
    def debug(cls, message: str, module: str = "Sistema"):
        """Registra uma mensagem de debug se o modo debug estiver ativo."""
        if cls.debug_mode:
            print(f"[DEBUG][{module}] {message}")
            cls._write_to_log("DEBUG", module, message)

    @classmethod
    def info(cls, message: str, module: str = "Sistema"):
        """Registra uma mensagem de informação."""
        if cls.debug_mode:
            print(f"[INFO][{module}] {message}")
        cls._write_to_log("INFO", module, message)

    @classmethod
    def warning(cls, message: str, module: str = "Sistema"):
        """Registra um aviso."""
        print(f"[WARNING][{module}] {message}")
        cls._write_to_log("WARNING", module, message)

    @classmethod
    def error(cls, message: str, module: str = "Sistema"):
        """Registra um erro."""
        print(f"[ERROR][{module}] {message}")
        cls._write_to_log("ERROR", module, message)