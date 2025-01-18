"""
Módulo de Gerenciamento de Banco de Dados

Este módulo gerencia todas as operações de banco de dados do sistema TaleWeaver,
incluindo:
- Conexões assíncronas
- Operações CRUD
- Gerenciamento de transações
- Cache de consultas
- Migrações de esquema
"""

import os
import sqlite3
import aiosqlite
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict
from config import ConfigManager
from datetime import datetime
import hashlib
import asyncio
from functools import wraps

class AsyncDatabaseManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.connection: Optional[aiosqlite.Connection] = None
        self.cache: Dict[str, Any] = {}
        self.cache_enabled = self.config.get('database.cache_enabled', True)
        self.cache_ttl = self.config.get('database.cache_ttl', 300)
        
    async def initialize(self) -> None:
        """Inicializa o banco de dados"""
        try:
            db_path = self._get_db_path()
            self.connection = await aiosqlite.connect(db_path)
            self.connection.row_factory = aiosqlite.Row
            await self._create_tables()
            print(f"Banco de dados inicializado em: {db_path}")
        except Exception as e:
            print(f"Erro ao inicializar banco de dados: {e}")
            raise

    def _get_db_path(self) -> str:
        """Retorna o caminho completo do banco de dados"""
        db_dir = self.config.get('database.path', 'data')
        db_name = self.config.get('database.main_db', 'tale_weaver.db')
        
        # Cria diretório se não existir
        Path(db_dir).mkdir(parents=True, exist_ok=True)
        
        return str(Path(db_dir) / db_name)

    async def _create_tables(self) -> None:
        """Cria as tabelas necessárias"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS story_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                current_scene TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                personality TEXT,
                relationships TEXT,
                voice_file TEXT,
                is_favorite BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER,
                user_input TEXT,
                character_response TEXT,
                emotion TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(character_id) REFERENCES characters(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS story_scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_context_id INTEGER NOT NULL,
                scene_order INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(story_context_id) REFERENCES story_context(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS story_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_context_id INTEGER NOT NULL,
                character_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                relationships TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(story_context_id) REFERENCES story_context(id),
                FOREIGN KEY(character_id) REFERENCES characters(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS story_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_context_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                description TEXT,
                scene_connections TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(story_context_id) REFERENCES story_context(id),
                FOREIGN KEY(location_id) REFERENCES locations(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS character_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_character_id INTEGER NOT NULL,
                target_character_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_character_id) REFERENCES characters(id),
                FOREIGN KEY(target_character_id) REFERENCES characters(id)
            )
            """
        ]
        
        try:
            for table in tables:
                await self.connection.execute(table)
            await self.connection.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")
            raise

    async def execute_query(self, query: str, params: Tuple = (), use_cache: bool = True) -> List[Dict[str, Any]]:
        """Executa uma consulta no banco de dados"""
        cache_key = self._generate_cache_key(query, params)
        
        if use_cache and self.cache_enabled and cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            cursor = await self.connection.execute(query, params)
            rows = await cursor.fetchall()
            result = [dict(row) for row in rows]
            
            if use_cache and self.cache_enabled:
                self.cache[cache_key] = result
                asyncio.create_task(self._clear_cache_after_ttl(cache_key))
                
            return result
        except Exception as e:
            print(f"Erro ao executar query: {e}")
            raise

    async def execute_write(self, query: str, params: Tuple = ()) -> int:
        """Executa uma operação de escrita no banco de dados"""
        try:
            cursor = await self.connection.execute(query, params)
            await self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Erro ao executar escrita: {e}")
            await self.connection.rollback()
            raise

    async def close(self) -> None:
        """Fecha a conexão com o banco de dados"""
        if self.connection:
            await self.connection.close()
            self.connection = None

    def _generate_cache_key(self, query: str, params: Tuple) -> str:
        """Gera uma chave única para cache"""
        key_str = f"{query}{json.dumps(params)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def _clear_cache_after_ttl(self, key: str) -> None:
        """Limpa o cache após o tempo de vida expirar"""
        await asyncio.sleep(self.cache_ttl)
        self.cache.pop(key, None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
