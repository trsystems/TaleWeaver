from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel, QPushButton
from PyQt6.QtCore import Qt
from queue import Queue
from .player_worker import AudioPlayerWorker

class AudioPlayerWindow(QWidget):
    def __init__(self, audio_queue: Queue):
        super().__init__()
        self.audio_queue = audio_queue
        self.setup_ui()
        self.setup_worker()

    def setup_ui(self):
        self.setWindowTitle("Story Audio Player")
        self.setFixedSize(400, 150)

        layout = QVBoxLayout()

        # Status Label
        self.status_label = QLabel("Aguardando áudio...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Controles
        button_layout = QVBoxLayout()
        
        self.pause_button = QPushButton("Pausar")
        self.pause_button.clicked.connect(self.pause_playback)
        button_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Parar")
        self.stop_button.clicked.connect(self.stop_playback)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def setup_worker(self):
        self.worker = AudioPlayerWorker(self.audio_queue)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.playback_finished.connect(self.playback_finished)
        self.worker.text_updated.connect(self.update_status)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)

    def playback_finished(self):
        self.progress_bar.setValue(0)
        self.status_label.setText("Reprodução finalizada")

    def pause_playback(self):
        self.worker.pause()
        self.pause_button.setText("Continuar" if self.worker.pause_flag else "Pausar")

    def stop_playback(self):
        self.worker.stop()
        self.progress_bar.setValue(0)
        self.status_label.setText("Reprodução interrompida")

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()