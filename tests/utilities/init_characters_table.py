import asyncio
import aiosqlite
from pathlib import Path

async def initialize_characters_table():
    db_path = Path('data/tale_weaver.db')
    if db_path.exists():
        db_path.unlink()
        
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                personality TEXT,
                role TEXT,
                relationships TEXT,
                voice_file TEXT,
                is_favorite BOOLEAN DEFAULT 0,
                is_player BOOLEAN DEFAULT 0,
                is_narrator BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        print(f"Successfully created characters table at {db_path}")

if __name__ == '__main__':
    asyncio.run(initialize_characters_table())
