from character_manager import CharacterManager
from config import ConfigManager
from database import AsyncDatabaseManager
import asyncio

async def test():
    config = ConfigManager()
    db = AsyncDatabaseManager(config)
    await db.initialize()
    manager = CharacterManager(config, db)
    await manager.initialize()
    
    # Criar narrador de teste
    result = await manager.create_character(
        name='Narrador Teste',
        role='narrador',
        description='Narrador de teste'
    )
    print(f"Resultado da criação do narrador: {result}")

if __name__ == '__main__':
    asyncio.run(test())
