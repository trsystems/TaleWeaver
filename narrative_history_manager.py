import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from log_manager import LogManager

class NarrativeHistoryManager:
    def __init__(self, db_path: str = "narrative_history.db"):
        self.db_path = db_path
        self.setup_database()  # Garante criação das tabelas
        LogManager.info("Sistema de histórico narrativo inicializado", "NarrativeHistory")

    def setup_database(self):
        """Configura o banco de dados para armazenar o histórico narrativo"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Primeiro, verifica se a tabela existe
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='character_interactions'
                """)
                table_exists = cursor.fetchone() is not None

                if table_exists:
                    # Se existir, verifica se tem as colunas necessárias
                    cursor = conn.execute('PRAGMA table_info(character_interactions)')
                    columns = {col[1] for col in cursor.fetchall()}
                    
                    # Se faltar alguma coluna necessária, recria a tabela
                    if 'character_name' in columns and 'target_name' in columns:
                        # Renomeia a tabela antiga
                        conn.execute("ALTER TABLE character_interactions RENAME TO old_interactions")
                        
                        # Cria nova tabela com estrutura atualizada
                        conn.execute("""
                            CREATE TABLE character_interactions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                character_name TEXT NOT NULL,
                                target_name TEXT NOT NULL,
                                interaction_type TEXT NOT NULL,
                                content TEXT,
                                emotion TEXT,
                                timestamp TEXT NOT NULL,
                                importance REAL DEFAULT 0.5
                            )
                        """)
                        
                        # Migra os dados
                        conn.execute("""
                            INSERT INTO character_interactions 
                            (character_name, target_name, interaction_type, content, emotion, timestamp, importance)
                            SELECT character_name, target_name, interaction_type, content, emotion, timestamp, 
                                COALESCE(importance, 0.5)
                            FROM old_interactions
                        """)
                        
                        # Remove tabela antiga
                        conn.execute("DROP TABLE old_interactions")

                else:
                    # Se a tabela não existe, cria do zero
                    conn.execute("""
                        CREATE TABLE character_interactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            character_name TEXT NOT NULL,
                            target_name TEXT NOT NULL,
                            interaction_type TEXT NOT NULL,
                            content TEXT,
                            emotion TEXT,
                            timestamp TEXT NOT NULL,
                            importance REAL DEFAULT 0.5
                        )
                    """)

                # Cria índices para otimização
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_char_interactions 
                    ON character_interactions(character_name, target_name)
                """)
                
                conn.commit()
                LogManager.info("Banco de dados narrativo configurado com sucesso", "NarrativeHistory")
                
        except Exception as e:
            LogManager.error(f"Erro ao configurar banco de dados: {e}", "NarrativeHistory")

    def add_narrative_event(self, event_type: str, content: str, location: str,
                          characters: List[str], scene_description: str,
                          important_details: Optional[List[str]] = None):
        """Adiciona um evento narrativo ao histórico"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO narrative_events 
                    (timestamp, event_type, content, location, characters_involved,
                     scene_description, important_details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    event_type,
                    content,
                    location,
                    ','.join(characters),
                    scene_description,
                    ','.join(important_details or [])
                ))
            LogManager.debug(f"Evento narrativo adicionado: {event_type}", "NarrativeHistory")
        except Exception as e:
            LogManager.error(f"Erro ao adicionar evento narrativo: {e}", "NarrativeHistory")

    def add_character_interaction(self, char_a: str, char_b: str,
                                interaction_type: str, content: str,
                                emotional_state: str):
        """Registra uma interação entre personagens"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO character_interactions
                    (timestamp, character_a, character_b, interaction_type,
                     content, emotional_state)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    char_a,
                    char_b,
                    interaction_type,
                    content,
                    emotional_state
                ))
            LogManager.debug(f"Interação registrada entre {char_a} e {char_b}", "NarrativeHistory")
        except Exception as e:
            LogManager.error(f"Erro ao registrar interação: {e}", "NarrativeHistory")

    def get_character_history(self, character_name: str) -> Dict:
        """Obtém histórico completo de um personagem"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Eventos onde o personagem está envolvido
                events = conn.execute("""
                    SELECT timestamp, event_type, content, location, scene_description
                    FROM narrative_events
                    WHERE characters_involved LIKE ?
                    ORDER BY timestamp DESC
                """, (f"%{character_name}%",)).fetchall()

                # Interações do personagem
                interactions = conn.execute("""
                    SELECT timestamp, character_a, character_b, interaction_type,
                           content, emotional_state
                    FROM character_interactions
                    WHERE character_a = ? OR character_b = ?
                    ORDER BY timestamp DESC
                """, (character_name, character_name)).fetchall()

                return {
                    "events": [dict(zip(["timestamp", "type", "content", "location", "scene"], event))
                             for event in events],
                    "interactions": [dict(zip(["timestamp", "char_a", "char_b", "type", "content", "emotion"], inter))
                                   for inter in interactions]
                }
        except Exception as e:
            LogManager.error(f"Erro ao obter histórico do personagem: {e}", "NarrativeHistory")
            return {"events": [], "interactions": []}
        
    def get_characters_interaction_history_sync(self, char_a: str, char_b: str) -> str:
        """Versão síncrona do método get_characters_interaction_history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Obtém interações diretas entre os personagens
                interactions = conn.execute("""
                    SELECT timestamp, interaction_type, content, emotional_state
                    FROM character_interactions
                    WHERE (character_name = ? AND target_name = ?)
                    OR (character_name = ? AND target_name = ?)
                    ORDER BY timestamp DESC
                    LIMIT 5
                """, (char_a, char_b, char_b, char_a)).fetchall()
                
                if not interactions:
                    return f"Nenhuma interação direta registrada com {char_b}."
                    
                formatted_history = []
                for timestamp, type, content, emotion in interactions:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                    formatted_history.append(
                        f"- {formatted_time} [{emotion}]: {content}"
                    )
                
                return "\n".join(formatted_history)
                
        except Exception as e:
            LogManager.error(f"Erro ao obter histórico de interações: {e}", "NarrativeHistory")
            return "Erro ao recuperar histórico de interações."
    
    async def get_characters_interaction_history(self, char_a: str, char_b: str) -> str:
        """Obtém histórico de interações entre dois personagens"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Obtém interações diretas entre os personagens
                interactions = conn.execute("""
                    SELECT timestamp, interaction_type, content, emotional_state
                    FROM character_interactions
                    WHERE (character_a = ? AND character_b = ?)
                    OR (character_a = ? AND character_b = ?)
                    ORDER BY timestamp DESC
                    LIMIT 5
                """, (char_a, char_b, char_b, char_a)).fetchall()
                
                if not interactions:
                    return f"Nenhuma interação direta registrada com {char_b}."
                    
                formatted_history = []
                for timestamp, type, content, emotion in interactions:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                    formatted_history.append(
                        f"- {formatted_time} [{emotion}]: {content}"
                    )
                
                return "\n".join(formatted_history)
                
        except Exception as e:
            LogManager.error(f"Erro ao obter histórico de interações: {e}", "NarrativeHistory")
            return "Erro ao recuperar histórico de interações."

    def get_recent_narrative(self, limit: int = 5) -> List[Dict]:
        """Obtém eventos narrativos recentes"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                events = conn.execute("""
                    SELECT timestamp, event_type, content, location,
                           characters_involved, scene_description
                    FROM narrative_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)).fetchall()

                return [dict(zip(["timestamp", "type", "content", "location", "characters", "scene"], event))
                       for event in events]
        except Exception as e:
            LogManager.error(f"Erro ao obter narrativa recente: {e}", "NarrativeHistory")
            return []

    def get_character_relationships(self, character_name: str) -> Dict[str, List[Dict]]:
        """Obtém histórico de relacionamentos de um personagem"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                interactions = conn.execute("""
                    SELECT character_a, character_b, interaction_type,
                           COUNT(*) as interaction_count,
                           GROUP_CONCAT(emotional_state) as emotional_states
                    FROM character_interactions
                    WHERE character_a = ? OR character_b = ?
                    GROUP BY 
                        CASE 
                            WHEN character_a = ? THEN character_b 
                            ELSE character_a 
                        END
                """, (character_name, character_name, character_name)).fetchall()

                relationships = {}
                for inter in interactions:
                    other_char = inter[1] if inter[0] == character_name else inter[0]
                    if other_char not in relationships:
                        relationships[other_char] = []
                    relationships[other_char].append({
                        "type": inter[2],
                        "count": inter[3],
                        "emotions": inter[4].split(',')
                    })

                return relationships
        except Exception as e:
            LogManager.error(f"Erro ao obter relacionamentos: {e}", "NarrativeHistory")
            return {}