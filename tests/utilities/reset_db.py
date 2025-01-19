import os
import asyncio
from database import AsyncDatabaseManager
from config import ConfigManager

async def reset_database():
    """Resets the database to a clean state"""
    config = ConfigManager()
    db = AsyncDatabaseManager(config)
    
    # Delete existing database file
    db_path = db._get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database at: {db_path}")
    
    # Reinitialize database
    await db.initialize()
    
    # Explicitly verify character table schema
    await db._verify_character_table()
    print("Database reset and initialized successfully")

if __name__ == "__main__":
    asyncio.run(reset_database())
