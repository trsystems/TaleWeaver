import pytest
from unittest.mock import AsyncMock, MagicMock
from story_manager import StoryManager, LLMClient
from config import ConfigManager
from database import AsyncDatabaseManager

@pytest.fixture
def mock_config():
    config = MagicMock(spec=ConfigManager)
    config.get = MagicMock(return_value="http://localhost:1234")
    return config

@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncDatabaseManager)
    db.execute_query = AsyncMock(return_value=[{"name": "test_table"}])
    db.execute_write = AsyncMock()
    return db

@pytest.fixture
def mock_llm():
    llm = AsyncMock(spec=LLMClient)
    llm.generate_story = AsyncMock(return_value={
        "stories": [{
            "title": "Test Story",
            "summary": "Test summary",
            "characters": [],
            "locations": []
        }]
    })
    return llm

@pytest.mark.asyncio
async def test_story_manager_initialization(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    await manager.initialize()
    
    assert manager.initialized is True
    assert isinstance(manager.llm, LLMClient)

@pytest.mark.asyncio
async def test_create_new_story(mock_config, mock_db, mock_llm):
    manager = StoryManager(mock_config, mock_db)
    manager.llm = mock_llm
    
    # Mock user input
    import builtins
    original_input = builtins.input
    builtins.input = lambda _: "1"
    
    try:
        story = await manager.create_new_story()
        assert story is not None
        assert "title" in story
        assert "summary" in story
        assert "characters" in story
        assert "locations" in story
        
        # Verify database calls
        mock_db.execute_write.assert_called()
    finally:
        builtins.input = original_input

@pytest.mark.asyncio
async def test_select_genre(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    
    # Mock user input
    import builtins
    original_input = builtins.input
    builtins.input = lambda _: "1"
    
    try:
        genre = await manager._select_genre()
        assert genre == "Fantasia"
    finally:
        builtins.input = original_input

@pytest.mark.asyncio
async def test_generate_story_options(mock_config, mock_db, mock_llm):
    manager = StoryManager(mock_config, mock_db)
    manager.llm = mock_llm
    
    options = await manager._generate_story_options("Fantasia")
    assert len(options) > 0
    assert "title" in options[0]
    assert "summary" in options[0]

@pytest.mark.asyncio
async def test_select_story(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    
    test_options = [{
        "title": "Test Story",
        "summary": "Test summary",
        "characters": [],
        "locations": []
    }]
    
    # Mock user input
    import builtins
    original_input = builtins.input
    builtins.input = lambda _: "1"
    
    try:
        selected = await manager._select_story(test_options)
        assert selected == test_options[0]
    finally:
        builtins.input = original_input

@pytest.mark.asyncio
async def test_create_initial_context(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    
    test_story = {
        "title": "Test Story",
        "summary": "Test summary",
        "characters": [],
        "locations": []
    }
    
    context = await manager._create_initial_context(test_story)
    assert context["title"] == test_story["title"]
    assert context["summary"] == test_story["summary"]
    assert "current_scene" in context
    assert "timeline" in context

@pytest.mark.asyncio
async def test_save_story(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    
    test_context = {
        "title": "Test Story",
        "summary": "Test summary",
        "current_scene": "Introdução",
        "characters": [],
        "locations": [],
        "timeline": []
    }
    
    await manager._save_story(test_context)
    mock_db.execute_write.assert_called()

@pytest.mark.asyncio
async def test_reset_story(mock_config, mock_db):
    manager = StoryManager(mock_config, mock_db)
    manager.current_story = {"test": "data"}
    manager.current_scene = {"test": "scene"}
    
    await manager.reset_story()
    assert manager.current_story is None
    assert manager.current_scene is None
