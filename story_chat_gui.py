from interface import ChatInterface, QApplication
from main import StoryChat
import sys
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
from character_models import Character
from story_utils import NarratorType
from ui_utils import Colors

class ChatWorker(QThread):
    """Thread worker para processamento assíncrono do chat."""
    message_received = pyqtSignal(str, bool, str, str)  # texto, is_user, sender_name, avatar_path
    context_updated = pyqtSignal(str)
    
    def __init__(self, story_chat):
        super().__init__()
        self.story_chat = story_chat
        self.message_queue = asyncio.Queue()
        self.running = True
    
    async def process_messages(self):
        while self.running:
            message = await self.message_queue.get()
            if message is None:
                break
                
            text, character = message
            response = await self.story_chat.generate_response(text, character)
            
            if response:
                avatar_path = f"avatars/{character.name.lower()}.png" if character else None
                self.message_received.emit(response.text, False, character.name if character else "", avatar_path)
    
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.process_messages())
        loop.close()
    
    def stop(self):
        self.running = False
        self.message_queue.put_nowait(None)

class StoryChatGUI:
    def __init__(self, story_chat):  # Recebe o StoryChat já criado
        self.window = ChatInterface()
        self.story_chat = story_chat  # Usa o StoryChat existente
        
        self.setup_worker()
        self.connect_signals()
        
    def setup_worker(self):
        self.worker = ChatWorker(self.story_chat)
        self.worker.message_received.connect(self.add_message)
        self.worker.context_updated.connect(self.show_context)
        self.worker.start()
    
    def connect_signals(self):
        self.window.text_input.returnPressed.connect(self.send_message)
        # Conectar outros sinais (botões, etc)
    
    def add_message(self, text: str, is_user: bool, sender_name: str, avatar_path: str):
        self.window.add_message(text, is_user, sender_name, avatar_path)
    
    def show_context(self, context_text: str):
        self.window.show_context(context_text)
    
    async def send_message(self):
        text = self.window.text_input.text()
        if not text:
            return
            
        # Adiciona mensagem do usuário
        self.add_message(text, True, "Você", "avatars/user.png")
        self.window.text_input.clear()
        
        # Processa a mensagem
        input_type = self.story_chat.detect_input_type(text)
        character = None
        
        if input_type == NarratorType.CHARACTER:
            # Implementar seleção de personagem via GUI
            pass
        elif input_type == NarratorType.NARRATOR:
            narrator_profile = self.story_chat.narrator_system.get_current_profile()
            character = Character(
                name="",
                voice_file=narrator_profile.voice_file,
                system_prompt_file="prompts/narrator_prompt.txt",
                color=Colors.YELLOW
            )
        
        await self.worker.message_queue.put((text, character))
    
    def run(self):
        self.window.show()
        return self.app.exec()
    
    def cleanup(self):
        self.worker.stop()
        self.worker.wait()

def main():
    gui = StoryChatGUI()
    try:
        return gui.run()
    finally:
        gui.cleanup()

if __name__ == "__main__":
    sys.exit(main())