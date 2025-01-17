from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtGui import QMovie
import sys

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Teste de GIFs')
        self.setGeometry(100, 100, 400, 200)

        # Label para typing.gif
        typing_label = QLabel(self)
        typing_movie = QMovie('icons/typing.gif')
        typing_label.setMovie(typing_movie)
        typing_movie.start()
        typing_label.move(50, 50)

        # Label para recording.gif
        recording_label = QLabel(self)
        recording_movie = QMovie('icons/recording.gif')
        recording_label.setMovie(recording_movie)
        recording_movie.start()
        recording_label.move(50, 100)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())