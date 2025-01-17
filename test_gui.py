from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
import sys

def test_window():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setGeometry(100, 100, 400, 200)
    window.setWindowTitle('Test Window')
    
    label = QLabel('Hello World', window)
    label.move(100, 80)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    test_window()