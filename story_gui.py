import asyncio
from PyQt6.QtWidgets import QApplication, QDialog
from interface import ChatInterface, NarratorStyleDialog
import sys
from narrator_system import NarratorStyle

def start_gui():
    try:
        print("Iniciando modo GUI...")
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Cria um loop de eventos assíncrono
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Mostrar diálogo de seleção do narrador
        dialog = NarratorStyleDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            print("Seleção de narrador cancelada")
            return 1
            
        narrator_style = dialog.get_selected_style()
        
        print("Criando janela principal...")
        window = ChatInterface(narrator_style)
        
        print("Exibindo janela...")
        window.show()
        
        print("Iniciando loop de eventos...")
        return app.exec()
        
    except Exception as e:
        print(f"Erro ao iniciar GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if 'loop' in locals():
            loop.close()

if __name__ == "__main__":
    sys.exit(start_gui())