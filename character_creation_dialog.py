import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
from log_manager import LogManager

class CharacterCreationDialog(QDialog):
    def __init__(self, character_name: str, profile: dict, parent=None):
        super().__init__(parent)
        self.character_name = character_name
        self.profile = profile
        self.voice_file = None
        self.avatar_file = None
        self.setupUI()
        
    def setupUI(self):
        self.setWindowTitle(f"Novo Personagem Detectado: {self.character_name}")
        layout = QVBoxLayout()
        
        # Informações do personagem
        info_text = f"""
        Um novo personagem foi detectado na história!
        
        Nome: {self.character_name}
        Ocupação: {self.profile.get('occupation', 'Desconhecida')}
        
        Personalidade:
        {self._format_list(self.profile.get('personality', []))}
        
        História: {self.profile.get('background', 'Desconhecida')}
        
        Aparência: {self.profile.get('appearance', 'Desconhecida')}
        """
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Botões para arquivos
        voice_layout = QHBoxLayout()
        self.voice_label = QLabel("Nenhum arquivo de voz selecionado")
        voice_btn = QPushButton("Selecionar Voz")
        voice_btn.clicked.connect(self._select_voice)
        voice_layout.addWidget(self.voice_label)
        voice_layout.addWidget(voice_btn)
        layout.addLayout(voice_layout)
        
        avatar_layout = QHBoxLayout()
        self.avatar_label = QLabel("Nenhum avatar selecionado")
        avatar_btn = QPushButton("Selecionar Avatar")
        avatar_btn.clicked.connect(self._select_avatar)
        avatar_layout.addWidget(self.avatar_label)
        avatar_layout.addWidget(avatar_btn)
        layout.addLayout(avatar_layout)
        
        # Botões de controle
        btn_layout = QHBoxLayout()
        create_btn = QPushButton("Criar Personagem")
        create_btn.clicked.connect(self.accept)
        skip_btn = QPushButton("Ignorar")
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(create_btn)
        btn_layout.addWidget(skip_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def _format_list(self, items: list) -> str:
        return "\n".join(f"- {item}" for item in items)
        
    def _select_voice(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Voz",
            "voices",
            "Arquivos de Áudio (*.wav *.mp3)"
        )
        if file_name:
            self.voice_file = file_name
            self.voice_label.setText(os.path.basename(file_name))
            
    def _select_avatar(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Avatar",
            "avatars",
            "Imagens (*.png *.jpg)"
        )
        if file_name:
            self.avatar_file = file_name
            self.avatar_label.setText(os.path.basename(file_name))
            
    def get_files(self) -> tuple:
        """Retorna os arquivos selecionados"""
        return self.voice_file, self.avatar_file