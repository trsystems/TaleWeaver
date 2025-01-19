import asyncio
from database import AsyncDatabaseManager
from config import ConfigManager

async def reset_characters_table():
    config = ConfigManager()
    db = AsyncDatabaseManager(config)
    
    try:
        await db.initialize()
        
        # Backup existing data
        print("Backing up character data...")
        characters = await db.execute_query("SELECT * FROM characters")
        
        # Drop and recreate table
        print("Recreating characters table...")
        await db.execute_write("DROP TABLE IF EXISTS characters")
        await db.execute_write("""
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
        
        # Restore data
        if characters:
            print(f"Restoring {len(characters)} characters...")
            for char in characters:
                await db.execute_write("""
                    INSERT INTO characters (
                        id, name, description, personality, role, 
                        relationships, voice_file, is_favorite,
                        is_player, is_narrator, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    char['id'], char['name'], char['description'],
                    char['personality'], char['role'], char['relationships'],
                    char['voice_file'], char['is_favorite'],
                    char['is_player'], char['is_narrator'],
                    char['created_at'], char['updated_at']
                ))
        
        print("Characters table reset successfully!")
    except Exception as e:
        print(f"Error resetting characters table: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(reset_characters_table())
