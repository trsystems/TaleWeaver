import pyaudio
import wave
import time
from PyQt6.QtCore import QThread, pyqtSignal
from queue import Queue

class AudioPlayerWorker(QThread):
    progress_updated = pyqtSignal(int)
    playback_finished = pyqtSignal()
    text_updated = pyqtSignal(str)

    def __init__(self, audio_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.audio = pyaudio.PyAudio()
        self.is_playing = False
        self.current_stream = None
        self.stop_flag = False
        self.pause_flag = False
        self.buffer_size = 4096  # Aumentado para melhor performance

    def run(self):
        while not self.stop_flag:
            try:
                if not self.audio_queue.empty() and not self.pause_flag:
                    audio_file = self.audio_queue.get()
                    self.play_audio_file(audio_file)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Erro na reprodução: {e}")
                time.sleep(0.1)

    def play_audio_file(self, audio_file: str):
        try:
            wf = wave.open(audio_file, 'rb')
            self.text_updated.emit(f"Reproduzindo: {audio_file}")

            self.current_stream = self.audio.open(
                format=self.audio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                frames_per_buffer=self.buffer_size
            )

            total_frames = wf.getnframes()
            frames_read = 0
            self.is_playing = True

            data = wf.readframes(self.buffer_size)
            while data and not self.stop_flag and not self.pause_flag:
                self.current_stream.write(data)
                frames_read += self.buffer_size
                progress = min(100, int((frames_read / total_frames) * 100))
                self.progress_updated.emit(progress)
                data = wf.readframes(self.buffer_size)

            self.current_stream.stop_stream()
            self.current_stream.close()
            wf.close()
            self.is_playing = False
            self.playback_finished.emit()

        except Exception as e:
            print(f"Erro ao reproduzir arquivo: {e}")
            self.is_playing = False
            self.playback_finished.emit()

    def stop(self):
        self.stop_flag = True
        if self.current_stream:
            self.current_stream.stop_stream()
            self.current_stream.close()
        self.is_playing = False

    def pause(self):
        self.pause_flag = not self.pause_flag

    def __del__(self):
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()