import os
import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QLabel,
                            QScrollArea, QFrame, QComboBox, QDialog, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QUrl, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QPixmap, QIcon, QMovie, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtSvg import QSvgRenderer
from typing import Optional
import asyncio

# Imports do projeto
from audio_player.inline_player import InlineAudioPlayer
from narrator_system import  NarratorStyle
from story_utils import NarratorType
from ui_utils import Colors
from character_models import Character
from log_manager import LogManager
from event_manager import StoryEvent, EventType, EventManager
from interface_manager import AsyncProcessingThread, InterfaceManager
from avatar_provider import AvatarProvider

class MessageWidget(QFrame):
    def __init__(self, text: str, is_user: bool = False, sender_name: str = "", 
             avatar_path: str = None, is_audio: bool = False, 
             audio_file: str = None, is_system: bool = False,  # Adicionar este parâmetro 
             segment_index: int = -1):
        super().__init__()
        
        LogManager.debug(f"Criando MessageWidget: {'áudio' if is_audio else 'texto'}", "Interface")
    
        try:
            self.sender_name = sender_name
            self.segment_index = segment_index
            self.audio_file = audio_file
            self.is_audio = is_audio
            
            layout = QHBoxLayout()
            self.setLayout(layout)
            
            # Container da mensagem
            message_container = QFrame()
            message_container.setObjectName("message_container")
            self.message_layout = QVBoxLayout()
            message_container.setLayout(self.message_layout)
            
            # Nome do remetente
            if sender_name:
                name_label = QLabel(sender_name)
                name_label.setStyleSheet("color: #A0A0A0; font-size: 12px;")
                self.message_layout.addWidget(name_label)

            # Configuração do avatar
            avatar_label = self.setup_avatar(avatar_path, sender_name)

            # Conteúdo específico por tipo
            if text:
                message_label = QLabel(text)
                message_label.setWordWrap(True)
                self.message_layout.addWidget(message_label)
            
            if is_audio and audio_file:
                self.setup_audio_widget(audio_file)

            # Layout final
            self._setup_styles(is_user, is_system)
            self._setup_layout(layout, message_container, avatar_label, is_user)
            
        except Exception as e:
            LogManager.error(f"Erro ao criar MessageWidget: {e}", "Interface")
            raise

    def setup_avatar(self, avatar_path: str, sender_name: str) -> QLabel:
        """Configura o avatar do remetente"""
        try:
            avatar_label = QLabel()
            avatar_label.setFixedSize(40, 40)
            
            if avatar_path and os.path.exists(avatar_path):
                pixmap = QPixmap(avatar_path)
                scaled_pixmap = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, 
                                            Qt.TransformationMode.SmoothTransformation)
                avatar_label.setPixmap(scaled_pixmap)
            else:
                # Avatar padrão com inicial do nome
                default_style = """
                    background-color: #666;
                    color: white;
                    border-radius: 20px;
                    padding: 5px;
                    text-align: center;
                """
                avatar_label.setText(sender_name[0].upper() if sender_name else "?")
                avatar_label.setStyleSheet(default_style)
                avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            return avatar_label
            
        except Exception as e:
            LogManager.error(f"Erro ao configurar avatar: {e}", "Interface")
            # Retorna um avatar vazio em caso de erro
            empty_avatar = QLabel()
            empty_avatar.setFixedSize(40, 40)
            return empty_avatar

    def _setup_styles(self, is_user: bool, is_system: bool):
        """Configura os estilos do widget"""
        try:
            style = """
                #message_container {
                    border-radius: 10px;
                    padding: 10px;
                    margin: 2px;
                    color: white;
                }
            """
            
            if is_system:
                style += """
                    #message_container {
                        background: #2C2C2C;
                        color: #888888;
                        font-style: italic;
                    }
                """
            elif is_user:
                style += """
                    #message_container {
                        background: #2C2C2C;
                    }
                """
            else:
                style += """
                    #message_container {
                        background: #1A1A1A;
                    }
                """
            
            self.setStyleSheet(style)
            
        except Exception as e:
            LogManager.error(f"Erro ao configurar estilos: {e}", "Interface")

    def _setup_layout(self, layout: QHBoxLayout, message_container: QFrame, 
                     avatar_label: QLabel, is_user: bool):
        """Configura o layout final do widget"""
        try:
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(10)
            
            if is_user:
                layout.addStretch()
                layout.addWidget(message_container)
                layout.addWidget(avatar_label)
            else:
                layout.addWidget(avatar_label)
                layout.addWidget(message_container)
                layout.addStretch()
                
        except Exception as e:
            LogManager.error(f"Erro ao configurar layout: {e}", "Interface")

    def setup_audio_widget(self, audio_file: str):
        """Configura o widget de áudio estilo WhatsApp"""
        try:
            LogManager.debug(f"Configurando widget de áudio: {audio_file}", "Interface")
            audio_container = QFrame()
            audio_layout = QHBoxLayout()
            
            # Botão de play com ícone
            self.play_button = QPushButton()
            self.play_button.setIcon(QIcon("icons/play.png"))
            self.play_button.setFixedSize(36, 36)
            self.play_button.setStyleSheet("""
                QPushButton {
                    background-color: #00a884;
                    border-radius: 18px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #008c70;
                }
            """)
            self.play_button.clicked.connect(lambda: self.toggle_audio())
            
            # Barra de progresso
            self.progress_bar = QProgressBar()
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background: #d1d7db;
                    border-radius: 4px;
                    height: 4px;
                    margin: 0 10px;
                }
                QProgressBar::chunk {
                    background-color: #00a884;
                    border-radius: 4px;
                }
            """)
            self.progress_bar.setTextVisible(False)
            
            # Label de duração
            self.duration_label = QLabel("0:00")
            self.duration_label.setStyleSheet("color: #8696a0; margin: 0 5px;")
            
            audio_layout.addWidget(self.play_button)
            audio_layout.addWidget(self.progress_bar, 1)  # 1 = stretch factor
            audio_layout.addWidget(self.duration_label)
            
            audio_container.setLayout(audio_layout)
            self.message_layout.addWidget(audio_container)
            
            self.setup_audio_player(audio_file)
            LogManager.info("Widget de áudio configurado com sucesso", "Interface")
            
        except Exception as e:
            LogManager.error(f"Erro ao configurar widget de áudio: {e}", "Interface")
            raise

    def setup_audio_player(self, audio_file: str):
        """Configura o player de áudio"""
        try:
            self.audio_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.audio_player.setAudioOutput(self.audio_output)
            
            self.audio_player.durationChanged.connect(self.update_duration)
            self.audio_player.positionChanged.connect(self.update_position)
            self.audio_player.playbackStateChanged.connect(self.update_play_button)
            
            self.audio_player.setSource(QUrl.fromLocalFile(audio_file))
            
        except Exception as e:
            LogManager.error(f"Erro ao configurar player de áudio: {e}", "Interface")
            raise

    def toggle_audio(self):
        """Alterna entre play e pause do áudio"""
        try:
            if self.audio_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.audio_player.pause()
                self.play_button.setIcon(QIcon("icons/play.png"))
            else:
                self.audio_player.play()
                self.play_button.setIcon(QIcon("icons/pause.png"))
        except Exception as e:
            LogManager.error(f"Erro ao alternar áudio: {e}", "Interface")

    def update_duration(self, duration: int):
        """Atualiza a duração total do áudio"""
        try:
            total_secs = duration // 1000
            mins = total_secs // 60
            secs = total_secs % 60
            self.total_duration = f"{mins}:{secs:02d}"
            self.update_time_label()
        except Exception as e:
            LogManager.error(f"Erro ao atualizar duração: {e}", "Interface")

    def update_position(self, position: int):
        """Atualiza a posição atual do áudio"""
        try:
            current_secs = position // 1000
            mins = current_secs // 60
            secs = current_secs % 60
            self.current_position = f"{mins}:{secs:02d}"
            
            # Atualiza barra de progresso
            if hasattr(self, 'progress_bar'):
                total_duration = self.audio_player.duration()
                if total_duration > 0:
                    progress = (position / total_duration) * 100
                    self.progress_bar.setValue(int(progress))
            
            self.update_time_label()
        except Exception as e:
            LogManager.error(f"Erro ao atualizar posição: {e}", "Interface")

    def update_time_label(self):
        """Atualiza o texto da label de tempo"""
        try:
            if hasattr(self, 'current_position') and hasattr(self, 'total_duration'):
                self.duration_label.setText(f"{self.current_position} / {self.total_duration}")
        except Exception as e:
            LogManager.error(f"Erro ao atualizar label de tempo: {e}", "Interface")

    def update_play_button(self, state):
        """Atualiza o ícone do botão de play/pause"""
        try:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.play_button.setIcon(QIcon("icons/pause.png"))
            else:
                self.play_button.setIcon(QIcon("icons/play.png"))
        except Exception as e:
            LogManager.error(f"Erro ao atualizar botão de play: {e}", "Interface")

class AnimatedButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Cria duas animações, uma para entrada e outra para saída
        self._rotation = 0
        self._animation_enter = QPropertyAnimation(self, b"rotation", self)
        self._animation_enter.setDuration(1000)  # 1 segundo
        self._animation_enter.setStartValue(0)
        self._animation_enter.setEndValue(360)
        
        self._animation_leave = QPropertyAnimation(self, b"rotation", self)
        self._animation_leave.setDuration(1000)  # 1 segundo
        self._animation_leave.setStartValue(360)
        self._animation_leave.setEndValue(0)
        
        # Define o tamanho fixo e estilo inicial
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # Muda o cursor ao passar por cima
        
        # Aplica o estilo base
        self.setStyleSheet("""
            AnimatedButton {
                background-color: #22C55E;
                border: none;
                border-radius: 20px;
                padding: 8px;
            }
            AnimatedButton:hover {
                background-color: #16A34A;
            }
        """)
        
    @pyqtProperty(float)
    def rotation(self):
        return self._rotation
        
    @rotation.setter
    def rotation(self, value):
        self._rotation = value
        self.update()
        
    def enterEvent(self, event):
        # Quando o mouse entra, inicia a animação de entrada
        self._animation_enter.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        # Quando o mouse sai, inicia a animação de saída
        self._animation_leave.start()
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Salva o estado
        painter.save()
        
        # Aplica a rotação
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._rotation)
        painter.translate(-self.width() / 2, -self.height() / 2)
        
        # Desenha o botão base
        super().paintEvent(event)
        
        # Restaura o estado
        painter.restore()

    def mousePressEvent(self, event):
        # Efeito visual ao clicar
        self.setStyleSheet("""
            AnimatedButton {
                background-color: #15803D;  /* Verde mais escuro ao clicar */
                border: none;
                border-radius: 20px;
                padding: 8px;
            }
        """)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Restaura o estilo original
        self.setStyleSheet("""
            AnimatedButton {
                background-color: #22C55E;
                border: none;
                border-radius: 20px;
                padding: 8px;
            }
            AnimatedButton:hover {
                background-color: #16A34A;
            }
        """)
        super().mouseReleaseEvent(event)

class ChatInterface(QMainWindow):
    def __init__(self, narrator_style: int = 1):
        """Inicializa a interface do chat."""
        super().__init__()
        LogManager.debug("Inicializando interface...", "Interface")
        
        # Configurações básicas
        self.narrator_style = NarratorStyle.DESCRIPTIVE if narrator_style == 1 else NarratorStyle.SASSY
        self.event_manager = EventManager()
        
        # Inicializa providers e recursos
        self._ensure_directories()
        self.avatar_provider = AvatarProvider()
        
        # Inicialização dos componentes
        self.setupStoryChat()
        self.initUI()
        self.interface_manager = InterfaceManager(self, self.story_chat, self.event_manager)
        self.setupEventHandlers()
        self.setupMessageHandling()
        self.character_selector.currentIndexChanged.connect(self._on_character_selected)

    def _ensure_directories(self):
        """Garante que os diretórios necessários existam"""
        directories = {
            'avatars': 'avatars',
            'outputs': 'outputs',
            'icons': 'icons',
            'voices': 'voices'
        }
        
        for dir_name, dir_path in directories.items():
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path)
                    LogManager.info(f"Diretório {dir_name} criado: {dir_path}", "Interface")
                except Exception as e:
                    LogManager.error(f"Erro ao criar diretório {dir_name}: {e}", "Interface")

    def get_avatar_path(self, sender_name: str) -> str:
        """Retorna caminho do avatar com fallback para default"""
        if not sender_name:
            return "avatars/default.png"
            
        avatar_path = f"avatars/{sender_name.lower()}.png"
        if not os.path.exists(avatar_path):
            LogManager.warning(f"Avatar não encontrado: {avatar_path}, usando default", "Interface")
            return "avatars/default.png"
            
        return avatar_path
    
    def _on_character_selected(self):
        """Handler para mudança de personagem selecionado"""
        try:
            char_name = self.character_selector.currentText()
            LogManager.info(f"Personagem selecionado alterado para: {char_name}", "Interface")
            
            # Atualiza avatar se necessário
            avatar_path = f"avatars/{char_name.lower()}.png"
            if not os.path.exists(avatar_path):
                LogManager.debug(f"Avatar não encontrado para {char_name}, usando padrão", "Interface")
                avatar_path = "avatars/default.png"

            # Log para debug da mudança de personagem
            if char_name in self.story_chat.characters:
                character = self.story_chat.characters[char_name]
                LogManager.debug(f"Voz selecionada: {character.voice_file}", "Interface")
                LogManager.debug(f"Prompt do personagem: {character.system_prompt_file}", "Interface")
            elif char_name == "Narrador":
                LogManager.debug("Personagem Narrador selecionado", "Interface")
                
        except Exception as e:
            LogManager.error(f"Erro ao mudar personagem: {e}", "Interface")

    def create_message_widget(self, text: str, is_user: bool, sender_name: str, 
                            avatar_path: str = None, is_audio: bool = False, 
                            audio_file: str = None, is_system: bool = False):  # Adicionar aqui também
        """Cria um widget de mensagem"""
        if not text and not is_audio:
            LogManager.debug("Ignorando criação de widget vazio", "Interface")
            return None

        try:
            widget = MessageWidget(
                text=text,
                is_user=is_user,
                sender_name=sender_name,
                avatar_path=avatar_path,
                is_audio=is_audio,
                audio_file=audio_file,
                is_system=is_system
            )

            if is_audio:
                layout = self.create_audio_layout(widget, audio_file)
            else:
                layout = self.create_text_layout(widget, text)

            widget.setLayout(layout)
            LogManager.debug(f"Widget criado: {'audio' if is_audio else 'text'}", "Interface")
            return widget

        except Exception as e:
            LogManager.error(f"Erro ao criar widget: {e}", "Interface")
            return None

    def add_message_widget(self, message: MessageWidget, should_scroll: bool = False):
        """Adiciona widget de mensagem ao layout"""
        try:
            if message is None:
                return

            # Verifica duplicação usando um identificador único
            message_id = f"{message.sender_name}_{message.text}_{time.time()}"
            
            # Verifica se já existe mensagem idêntica recente
            for i in range(self.messages_layout.count()):
                widget = self.messages_layout.itemAt(i).widget()
                if (isinstance(widget, MessageWidget) and 
                    widget.sender_name == message.sender_name and
                    widget.text == message.text):
                    LogManager.debug(f"Mensagem duplicada ignorada: {message_id}", "Interface")
                    return

            self.messages_layout.insertWidget(self.messages_layout.count() - 1, message)
            
            if should_scroll:
                QTimer.singleShot(100, self._scroll_to_bottom)

        except Exception as e:
            LogManager.error(f"Erro ao adicionar widget: {e}", "Interface")

    def remove_message_widget(self, message_widget):
        """Remove um widget de mensagem específico"""
        try:
            message_widget.setParent(None)
            message_widget.deleteLater()
            LogManager.debug("Widget de mensagem removido com sucesso", "Interface")
        except Exception as e:
            LogManager.error(f"Erro ao remover widget: {e}", "Interface")

    def _handle_message(self, text: str, is_user: bool, sender: str, 
                        avatar_path: str, is_audio: bool = False, 
                        audio_file: str = None, should_scroll: bool = False):
        """Manipula mensagens recebidas"""
        try:
            if not text and not audio_file:
                return

            # Se não tiver avatar_path, usa o provider para obter
            if not avatar_path:
                avatar_path = self.avatar_provider.get_avatar_path(sender)

            # Cria e adiciona nova mensagem
            message = MessageWidget(
                text=text,
                is_user=is_user,
                sender_name=sender,
                avatar_path=avatar_path,
                is_audio=is_audio,
                audio_file=audio_file
            )

            # Adiciona ao layout
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, message)
            
            # Faz scroll se necessário
            if should_scroll:
                QTimer.singleShot(100, self._scroll_to_bottom)
                
            LogManager.debug(f"Mensagem de {'áudio' if is_audio else 'texto'} adicionada", "Interface")
                
        except Exception as e:
            LogManager.error(f"Erro ao manipular mensagem: {e}", "Interface")

    def _scroll_to_bottom(self):
        """Rola para a última mensagem"""
        try:
            scroll_area = self.findChild(QScrollArea)
            if scroll_area:
                vsb = scroll_area.verticalScrollBar()
                vsb.setValue(vsb.maximum())
        except Exception as e:
            LogManager.error(f"Erro ao rolar chat: {e}", "Interface")

    def setupStoryChat(self):
        """Inicializa o StoryChat com o EventManager."""
        try:
            from main import StoryChat
            self.story_chat = StoryChat(
                gui_mode=True,
                narrator_style=self.narrator_style,
                event_manager=self.event_manager
            )
            LogManager.info("StoryChat inicializado com sucesso", "Interface")
        except Exception as e:
            LogManager.error(f"Erro ao inicializar StoryChat: {e}", "Interface")
            self.show_error(f"Erro ao inicializar StoryChat: {e}")

    def initUI(self):
        """Inicializa a interface gráfica"""
        self.setWindowTitle('Story Chat')
        self.setMinimumSize(800, 600)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Área superior
        self._setup_top_bar(main_layout)
        
        # Área de mensagens
        self._setup_messages_area(main_layout)
        
        # Área de input
        self._setup_input_area(main_layout)
        
        # Estilo geral
        self._setup_window_style()

    def _setup_top_bar(self, main_layout: QVBoxLayout):
        """Configura a barra superior da interface"""
        top_bar = QHBoxLayout()
        
        # Seletor de narrador (existente)
        narrator_style = QComboBox()
        narrator_style.addItems(["Narrador Descritivo", "Narrador Escrachado"])
        narrator_style.setStyleSheet("""
            QComboBox {
                background: #2C2C2C;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 5px;
            }
        """)
        
        # Seletor de personagens (novo)
        self.character_selector = QComboBox()
        self.character_selector.addItem("Narrador")  # Adiciona narrador como primeira opção
        for char_name in self.story_chat.characters.keys():
            self.character_selector.addItem(char_name)
        self.character_selector.setStyleSheet("""
            QComboBox {
                background: #2C2C2C;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 5px;
                min-width: 120px;
                margin-left: 10px;
            }
        """)
        
        # Botões de contexto e memórias
        self.context_btn = QPushButton("Contexto")
        self.memories_btn = QPushButton("Lembranças")
        
        for btn in [self.context_btn, self.memories_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: #2C2C2C;
                    color: white;
                    padding: 5px 15px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: #3C3C3C;
                }
            """)
        
        top_bar.addWidget(narrator_style)
        top_bar.addWidget(self.character_selector)
        top_bar.addWidget(self.context_btn)
        top_bar.addWidget(self.memories_btn)
        top_bar.addStretch()
        
        main_layout.addLayout(top_bar)
        
        # Conecta os botões
        self.context_btn.clicked.connect(lambda: self._handle_context_click())
        self.memories_btn.clicked.connect(lambda: self._handle_memories_click())
    
    def _handle_context_click(self):
        """Handler para o clique no botão de contexto"""
        try:
            # Cria uma thread para processar a requisição de forma assíncrona
            self.async_helper = AsyncProcessingThread(
                self.interface_manager.show_context(),
                parent=self
            )
            self.async_helper.error.connect(lambda e: self.show_error(str(e)))
            self.async_helper.start()
        except Exception as e:
            self.show_error(f"Erro ao mostrar contexto: {str(e)}")

    def _handle_memories_click(self):
        """Handler para o clique no botão de lembranças"""
        try:
            char_name = self.character_selector.currentText()
            if not char_name or char_name == "Narrador":
                self.show_error("Selecione um personagem primeiro")
                return
                
            # Cria uma thread para processar a requisição de forma assíncrona
            self.async_helper = AsyncProcessingThread(
                self.interface_manager.show_memories(char_name),
                parent=self
            )
            self.async_helper.error.connect(lambda e: self.show_error(str(e)))
            self.async_helper.start()
        except Exception as e:
            self.show_error(f"Erro ao mostrar memórias: {str(e)}")


    def _setup_messages_area(self, main_layout: QVBoxLayout):
        """Configura a área de mensagens"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #121212;
            }
            QScrollBar:vertical {
                border: none;
                background: #1A1A1A;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #2C2C2C;
                border-radius: 5px;
            }
        """)
        
        messages_container = QWidget()
        self.messages_layout = QVBoxLayout(messages_container)
        self.messages_layout.addStretch()
        scroll_area.setWidget(messages_container)
        
        main_layout.addWidget(scroll_area)

    def _setup_input_area(self, main_layout: QVBoxLayout):
        """Configura a área de input"""
        input_area = QHBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Digite sua mensagem...")
        self.text_input.setStyleSheet("""
            QLineEdit {
                background: #2C2C2C;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 20px;
            }
        """)
        
        # Cria o botão animado
        self.send_button = AnimatedButton()
        
        # Define o ícone SVG
        send_icon = QIcon()
        svg_renderer = QSvgRenderer(bytes("""
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z" stroke="white" stroke-width="2"/>
            </svg>
        """, 'utf-8'))
        
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        svg_renderer.render(painter)
        painter.end()
        
        send_icon.addPixmap(pixmap)
        self.send_button.setIcon(send_icon)
        
        input_area.addWidget(self.text_input)
        input_area.addWidget(self.send_button)
        
        main_layout.addLayout(input_area)

    def _setup_window_style(self):
        """Configura o estilo geral da janela"""
        self.setStyleSheet("""
            QMainWindow {
                background: #121212;
            }
            QLabel {
                color: white;
            }
        """)

    def setupEventHandlers(self):
        """Configura handlers para eventos do EventManager"""
        self.event_manager.message_received.connect(self._handle_message)
        self.event_manager.context_updated.connect(self.update_context_display)
        self.event_manager.memory_updated.connect(self.update_memories_display)
        self.event_manager.error_occurred.connect(self.show_error)
        self.event_manager.emotion_updated.connect(self.update_emotion_display)

        self.event_manager.new_character.connect(self._handle_new_character)
        self.event_manager.character_created.connect(self._handle_character_created)

    def _handle_new_character(self, name: str, profile: dict):
        """Handler para novo personagem detectado"""
        try:
            # Cria e mostra diálogo de criação de personagem
            from character_creation_dialog import CharacterCreationDialog
            dialog = CharacterCreationDialog(name, profile, self)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Usuário quer criar o personagem
                voice_file, avatar_file = dialog.get_files()
                
                # Cria uma thread para processar a criação
                self.async_helper = AsyncProcessingThread(
                    self.story_chat.create_character(name, voice_file, avatar_file),
                    parent=self
                )
                self.async_helper.start()
                
        except Exception as e:
            self.show_error(f"Erro ao processar novo personagem: {str(e)}")

    def _handle_character_created(self, text: str):
        """Handler para personagem criado com sucesso"""
        try:
            # Adiciona mensagem do sistema
            self.add_message(
                text=text,
                is_user=False,
                sender_name="Sistema",
                avatar_path="avatars/sistema.png"
            )
            
            # Atualiza o seletor de personagens
            self.update_character_selector()
            
        except Exception as e:
            self.show_error(f"Erro ao atualizar interface: {str(e)}")

    def update_character_selector(self):
        """Atualiza a lista de personagens disponíveis"""
        try:
            current = self.character_selector.currentText()
            
            # Limpa e recria a lista
            self.character_selector.clear()
            self.character_selector.addItem("Narrador")
            
            # Adiciona personagens existentes
            for char_name in sorted(self.story_chat.characters.keys()):
                self.character_selector.addItem(char_name)
                
            # Restaura seleção anterior se possível
            index = self.character_selector.findText(current)
            if index >= 0:
                self.character_selector.setCurrentIndex(index)
                
        except Exception as e:
            LogManager.error(f"Erro ao atualizar seletor: {e}", "Interface")

    def setupMessageHandling(self):
        """Configura o tratamento de mensagens"""
        self.text_input.returnPressed.connect(self.process_message)
        self.send_button.clicked.connect(self.process_message)

    def update_input_state(self, processing: bool):
        """Atualiza o estado visual dos controles de input"""
        self.text_input.setEnabled(not processing)
        
        if processing:
            self.send_button.setStyleSheet("""
                QPushButton {
                    background: #606060;
                    border: none;
                    border-radius: 20px;
                }
            """)
            self.text_input.setPlaceholderText("Processando...")
        else:
            self.send_button.setStyleSheet("""
                QPushButton {
                    background: #404040;
                    border: none;
                    border-radius: 20px;
                }
                QPushButton:hover {
                    background: #505050;
                }
            """)
            self.text_input.setPlaceholderText("Digite sua mensagem...")

    def add_message(self, text: str, is_user: bool = False, sender_name: str = "", 
                    avatar_path: str = None, is_audio: bool = False, 
                    audio_file: str = None, is_typing: bool = False,
                    is_system: bool = False):
        """Adiciona uma nova mensagem ao chat"""
        try:
            LogManager.debug(f"Adicionando mensagem: {'áudio' if is_audio else 'texto'}", "Interface")
            message = MessageWidget(
                text=text,
                is_user=is_user,
                sender_name=sender_name,
                avatar_path=avatar_path,
                is_audio=is_audio,
                audio_file=audio_file,
                is_typing=is_typing,
                is_system=is_system
            )
            self.messages_layout.insertWidget(self.messages_layout.count() - 1, message)
            QTimer.singleShot(100, self._scroll_to_bottom)
            LogManager.info("Mensagem adicionada com sucesso", "Interface")
        except Exception as e:
            LogManager.error(f"Erro ao adicionar mensagem: {e}", "Interface")

    def process_message(self):
        """Processa a mensagem do usuário"""
        try:
            text = self.text_input.text().strip()
            if not text:
                return

            self.text_input.clear()
            character = self._get_current_character()
            
            if not character:
                self.show_error("Não foi possível determinar o personagem para resposta")
                return

            # Cria uma thread para processar a mensagem de forma assíncrona
            self.async_helper = AsyncProcessingThread(
                self.interface_manager.process_message(text, character),
                parent=self
            )
            self.async_helper.error.connect(lambda e: self.show_error(str(e)))
            self.async_helper.start()

        except Exception as e:
            LogManager.error(f"Erro no processamento da mensagem: {e}", "Interface")
            self.show_error(f"Erro ao processar mensagem: {str(e)}")
            self.text_input.setEnabled(True)

    def _get_current_character(self) -> Optional[Character]:
        """Obtém o personagem atual"""
        try:
            if not hasattr(self, 'story_chat'):
                return None
                
            text = self.text_input.text().strip()
            input_type = self.story_chat.detect_input_type(text)
            
            if input_type in [NarratorType.NARRATOR, NarratorType.NARRATOR_DIRECT]:
                narrator_profile = self.story_chat.narrator_system.get_current_profile()
                return Character(
                    name="",
                    voice_file=narrator_profile.voice_file,
                    system_prompt_file="prompts/narrator_prompt.txt",
                    color=Colors.YELLOW
                )
            else:
                # Por enquanto retorna narrador como fallback
                narrator_profile = self.story_chat.narrator_system.get_current_profile()
                return Character(
                    name="",
                    voice_file=narrator_profile.voice_file,
                    system_prompt_file="prompts/narrator_prompt.txt",
                    color=Colors.YELLOW
                )
                
        except Exception as e:
            LogManager.error(f"Erro ao obter personagem atual: {e}", "Interface")
            return None

    def show_context(self):
        """Mostra o contexto atual da história"""
        try:
            async def update_context():
                context_text = await self.story_chat.generate_story_summary()
                await self.event_manager.emit(StoryEvent(
                    type=EventType.CONTEXT_UPDATE,
                    data=context_text
                ))

            from interface_manager import AsyncProcessingThread
            helper = AsyncProcessingThread(update_context())
            helper.error.connect(self._handle_context_error)
            helper.start()

        except Exception as e:
            LogManager.error(f"Erro ao mostrar contexto: {e}", "Interface")
            self.show_error(f"Erro ao mostrar contexto: {str(e)}")

    def show_memories_dialog(self):
        """Mostra diálogo de memórias"""
        try:
            dialog = CharacterSelectionDialog(list(self.story_chat.characters.keys()), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                char_name = dialog.selected_character
                memories = self.story_chat.memory_manager.get_formatted_memories(char_name)
                if memories:
                    self.add_system_message(f"\nMemórias de {char_name}:\n{memories}")
                else:
                    self.add_system_message(f"\n{char_name} ainda não tem memórias registradas.")
        except Exception as e:
            LogManager.error(f"Erro ao mostrar memórias: {e}", "Interface")
            self.show_error(f"Erro ao mostrar memórias: {str(e)}")

    def show_error(self, error_message: str):
        """Mostra uma mensagem de erro"""
        try:
            # Cria uma thread para processar o erro de forma assíncrona
            self.async_helper = AsyncProcessingThread(
                self.interface_manager._show_error(error_message),
                parent=self
            )
            self.async_helper.start()
        except Exception as e:
            print(f"Erro ao mostrar mensagem de erro: {e}")

    def create_text_layout(self, widget, text: str):
        layout = QVBoxLayout()
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: white;")
        layout.addWidget(label)
        return layout

    def create_typing_layout(self, widget):
        layout = QVBoxLayout()
        movie = QMovie("icons/typing.gif")
        label = QLabel()
        label.setMovie(movie)
        movie.start()
        layout.addWidget(label)
        return layout

    def create_audio_layout(self, widget, audio_file: str):
        layout = QVBoxLayout()
        player = InlineAudioPlayer(audio_file, self.event_manager)
        layout.addWidget(player)
        return layout

    def update_context_display(self, context_text: str):
        """Atualiza a exibição do contexto"""
        self.add_message(
            text=context_text,
            is_user=False,
            sender_name="Sistema",
            is_system=True
        )

    def update_memories_display(self, character_name: str, memories: str):
        """Atualiza a exibição das memórias"""
        self.add_message(
            text=f"Memórias de {character_name}:\n{memories}",
            is_user=False,
            sender_name="Sistema",
            is_system=True
        )

    def update_emotion_display(self, character: str, emotion: str, intensity: float):
        """Atualiza a exibição do estado emocional"""
        # Implementar visualização de emoções
        pass
    
    def _handle_context_error(self, error_message: str):
        """Trata erros na obtenção do contexto"""
        self.add_message(
            text=f"Erro ao mostrar contexto: {error_message}",
            is_user=False,
            sender_name="Sistema",
            is_system=True
        )

    def add_system_message(self, text: str):
        """Adiciona uma mensagem do sistema à área de chat"""
        message_widget = QFrame()
        message_widget.setStyleSheet("""
            QFrame {
                background-color: #2C2C2C;
                border-radius: 10px;
                margin: 5px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(message_widget)
        
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: #A0A0A0;")
        layout.addWidget(text_label)
        
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
        QTimer.singleShot(100, self._scroll_to_bottom)

    def closeEvent(self, event):
        """Sobrescreve o evento de fechamento para limpar recursos"""
        try:
            # Cria um loop de eventos temporário para limpar tarefas
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Aguarda todas as tarefas terminarem
            if hasattr(self, 'async_helper'):
                self.async_helper.wait()
            if hasattr(self, 'context_update_helper'):
                self.context_update_helper.wait()
                    
        finally:
            if 'loop' in locals():
                loop.close()
            super().closeEvent(event)


class CharacterSelectionDialog(QDialog):
    """Diálogo para seleção de personagem"""
    
    def __init__(self, characters: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selecionar Personagem")
        self.selected_character = None
        self.setup_ui(characters)
        
    def setup_ui(self, characters: list):
        """Configura a interface do diálogo"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
                color: white;
            }
            QComboBox {
                background-color: #2C2C2C;
                color: white;
                padding: 5px;
                border: none;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        
        layout = QVBoxLayout()
        
        # ComboBox para seleção de personagem
        self.char_combo = QComboBox()
        self.char_combo.addItems(characters)
        layout.addWidget(self.char_combo)
        
        # Botão de confirmação
        confirm_btn = QPushButton("OK")
        confirm_btn.clicked.connect(self.accept)
        layout.addWidget(confirm_btn)
        
        self.setLayout(layout)

    def accept(self):
        """Chamado quando o usuário confirma a seleção"""
        self.selected_character = self.char_combo.currentText()
        super().accept()


class NarratorStyleDialog(QDialog):
    """Diálogo para seleção do estilo do narrador"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Escolha o Estilo do Narrador")
        self.setup_ui()
        
    def setup_ui(self):
        """Configura a interface do diálogo"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
                color: white;
            }
            QComboBox {
                background-color: #2C2C2C;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
                min-width: 200px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QLabel {
                color: white;
                font-size: 14px;
                margin-bottom: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Label com instruções
        label = QLabel("Selecione o estilo de narração:")
        layout.addWidget(label)
        
        # Combo box para seleção
        self.combo = QComboBox()
        self.combo.addItems(["Narrador Descritivo", "Narrador Escrachado"])
        layout.addWidget(self.combo)
        
        # Botão de confirmação
        btn = QPushButton("Confirmar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        
        self.setLayout(layout)
        self.setFixedSize(300, 150)

    def get_selected_style(self) -> int:
        """Retorna o estilo selecionado (1 para Descritivo, 2 para Escrachado)"""
        return self.combo.currentIndex() + 1


def start_gui():
    """Inicializa e executa a interface gráfica"""
    try:
        LogManager.debug("Iniciando modo GUI...", "Interface")
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Mostrar diálogo de seleção do narrador
        dialog = NarratorStyleDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            LogManager.info("Seleção de narrador cancelada", "Interface")
            return 1
            
        narrator_style = dialog.get_selected_style()
        
        LogManager.debug("Criando janela principal...", "Interface")
        window = ChatInterface(narrator_style)
        
        LogManager.debug("Exibindo janela...", "Interface")
        window.show()
        
        LogManager.debug("Iniciando loop de eventos...", "Interface")
        return app.exec()
        
    except Exception as e:
        LogManager.error(f"Erro ao iniciar GUI: {e}", "Interface")
        import traceback
        traceback.print_exc()
        return 1

# Classes auxiliares para tratamento de arquivos de áudio
class AudioFile:
    """Classe auxiliar para gerenciar arquivos de áudio"""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.duration = 0
        self.sample_rate = 0
        self._load_metadata()
    
    def _load_metadata(self):
        """Carrega metadados do arquivo de áudio"""
        try:
            player = QMediaPlayer()
            player.setSource(QUrl.fromLocalFile(self.filepath))
            # Aguarda um momento para os metadados carregarem
            QTimer.singleShot(100, lambda: self._update_metadata(player))
        except Exception as e:
            LogManager.error(f"Erro ao carregar metadados do áudio: {e}", "Interface")
    
    def _update_metadata(self, player: QMediaPlayer):
        """Atualiza os metadados do arquivo"""
        try:
            self.duration = player.duration()
            # Limpa o player após uso
            player.stop()
            player.setSource(QUrl())
        except Exception as e:
            LogManager.error(f"Erro ao atualizar metadados: {e}", "Interface")

class AudioQueue:
    """Gerencia uma fila de arquivos de áudio para reprodução"""
    def __init__(self):
        self.queue = []
        self.current_index = -1
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Conecta sinais
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
    
    def add_file(self, filepath: str):
        """Adiciona um arquivo à fila"""
        try:
            audio_file = AudioFile(filepath)
            self.queue.append(audio_file)
            
            # Se for o primeiro arquivo, começa a reprodução
            if len(self.queue) == 1:
                self.play_next()
        except Exception as e:
            LogManager.error(f"Erro ao adicionar arquivo à fila: {e}", "Interface")
    
    def play_next(self):
        """Reproduz o próximo arquivo na fila"""
        try:
            if self.current_index < len(self.queue) - 1:
                self.current_index += 1
                next_file = self.queue[self.current_index]
                self.player.setSource(QUrl.fromLocalFile(next_file.filepath))
                self.player.play()
        except Exception as e:
            LogManager.error(f"Erro ao reproduzir próximo áudio: {e}", "Interface")
    
    def _on_media_status_changed(self, status):
        """Callback para mudanças no status da mídia"""
        try:
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                self.play_next()
        except Exception as e:
            LogManager.error(f"Erro ao processar mudança de status: {e}", "Interface")
    
    def clear(self):
        """Limpa a fila de reprodução"""
        try:
            self.player.stop()
            self.queue.clear()
            self.current_index = -1
        except Exception as e:
            LogManager.error(f"Erro ao limpar fila: {e}", "Interface")

# Código principal
if __name__ == "__main__":
    try:
        LogManager.info("Iniciando aplicação...", "Interface")
        sys.exit(start_gui())
    except Exception as e:
        LogManager.error(f"Erro fatal na aplicação: {e}", "Interface")
        sys.exit(1)
    finally:
        LogManager.info("Aplicação encerrada", "Interface")