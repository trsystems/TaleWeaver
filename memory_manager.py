import sqlite3
from datetime import datetime
from dataclasses import dataclass
import numpy as np

from log_manager import LogManager

@dataclass
class Memory:
    timestamp: str
    content: str
    importance: float
    context: str
    emotion: str

class MemoryManager:
    def __init__(self, db_path: str = "character_memories.db"):
        self.db_path = db_path
        self.setup_database()
        LogManager.info(f"Sistema de memória inicializado: {db_path}")

    def setup_database(self):
        LogManager.info(f"Inicializa o banco de dados de memórias.")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        character_name TEXT,
                        timestamp TEXT,
                        content TEXT,
                        importance REAL,
                        context TEXT,
                        emotion TEXT,
                        embedding BLOB
                    )
                """)
                LogManager.info("Banco de dados de memórias configurado com sucesso")
        except Exception as e:
            LogManager.info(f"Erro ao configurar banco de dados: {e}")

    def add_memory(self, character_name: str, memory: Memory, embedding: np.ndarray):
        LogManager.debug(f"Adicionando memória para {character_name}", "Memory")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO memories 
                    (character_name, timestamp, content, importance, context, emotion, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    character_name,
                    memory.timestamp,
                    memory.content,
                    memory.importance,
                    memory.context,
                    memory.emotion,
                    embedding.tobytes()
                ))
                LogManager.info(f"Nova memória adicionada para {character_name}", "Memory")
        except Exception as e:
            LogManager.error(f"Erro ao adicionar memória: {e}", "Memory")

    def get_formatted_memories(self, character_name: str) -> str:
        LogManager.info(f"Recupera memórias em um formato mais estruturado e explícito.")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT content, importance, emotion, timestamp
                    FROM memories
                    WHERE character_name = ?
                    ORDER BY importance DESC, timestamp DESC
                    LIMIT 5
                """, (character_name,))
                
                memories = cursor.fetchall()
                if not memories:
                    return ""
                
                memory_text = "Estas são suas memórias reais de conversas anteriores - use-as para manter consistência:\n\n"
                
                for content, importance, emotion, timestamp in memories:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                    
                    memory_text += f"Em {formatted_time} - {emotion.upper()}:\n"
                    memory_text += f"{content}\n\n"
                
                return memory_text
                
        except Exception as e:
            LogManager.error(f"Erro ao recuperar memórias: {e}")
            return ""
        
    def cleanup(self):
        """Fecha conexões e limpa recursos"""
        try:
            # Fecha conexão com banco de dados se existir
            if hasattr(self, '_conn'):
                self._conn.close()
        except Exception as e:
            LogManager.error(f"Erro ao limpar MemoryManager: {e}", "MemoryManager")