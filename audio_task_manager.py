import asyncio

from event_manager import EventType, StoryEvent

class AudioTaskManager:
    def __init__(self):
        self.active_tasks = set()
        self._cleanup_event = asyncio.Event()

    async def process_audio(self, audio_file: str):
        task = asyncio.create_task(self._play_audio(audio_file))
        self.active_tasks.add(task)
        return task
    
    async def _play_audio(self, audio_file: str):
        try:
            if self.event_manager:
                await self.event_manager.emit(StoryEvent(
                    type=EventType.MESSAGE,
                    sender="Sistema",
                    data={
                        "text": "",
                        "is_audio": True,
                        "audio_file": audio_file
                    }
                ))
        finally:
            self.active_tasks.discard(asyncio.current_task())

    async def add_task(self, coro):
        """Adiciona e gerencia uma nova tarefa."""
        task = asyncio.create_task(self._run_task(coro))
        self.active_tasks.add(task)
        return task

    async def _run_task(self, coro):
        """Executa uma tarefa e faz sua limpeza após conclusão."""
        try:
            await coro
        except Exception as e:
            print(f"Erro na tarefa de áudio: {e}")
        finally:
            # Tarefa será removida do conjunto quando concluída
            self.active_tasks.discard(asyncio.current_task())

    async def cleanup(self):
        """Aguarda todas as tarefas ativas terminarem."""
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
            self.active_tasks.clear()