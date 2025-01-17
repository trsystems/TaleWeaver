"""
Gerenciador de Avatares - Responsável por gerenciar avatares e recursos visuais
"""
import os
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from log_manager import LogManager

class AvatarProvider:
    """Gerencia avatares e recursos visuais para a interface"""
    
    DEFAULT_AVATAR = "avatars/default.png"
    AVATAR_SIZE = (40, 40)
    
    def __init__(self, avatar_dir: str = "avatars"):
        """
        Inicializa o provedor de avatares.
        
        Args:
            avatar_dir: Diretório onde os avatares estão armazenados
        """
        self.avatar_dir = avatar_dir
        self._ensure_avatar_dir()
        self._ensure_default_avatar()
        self._avatar_cache = {}
        
    def _ensure_avatar_dir(self):
        """Garante que o diretório de avatares existe"""
        try:
            if not os.path.exists(self.avatar_dir):
                os.makedirs(self.avatar_dir)
                LogManager.info(f"Diretório de avatares criado: {self.avatar_dir}", "AvatarProvider")
        except Exception as e:
            LogManager.error(f"Erro ao criar diretório de avatares: {e}", "AvatarProvider")
        
    def _ensure_default_avatar(self):
        """Garante que existe um avatar default"""
        try:
            if not os.path.exists(self.DEFAULT_AVATAR):
                # Cria um QPixmap cinza básico como avatar default
                pixmap = QPixmap(*self.AVATAR_SIZE)
                pixmap.fill(Qt.GlobalColor.gray)
                pixmap.save(self.DEFAULT_AVATAR)
                LogManager.info("Avatar default criado", "AvatarProvider")
        except Exception as e:
            LogManager.error(f"Erro ao criar avatar default: {e}", "AvatarProvider")

    def get_avatar_path(self, sender_name: str) -> str:
        """
        Retorna caminho do avatar para um remetente.
        
        Args:
            sender_name: Nome do remetente
            
        Returns:
            str: Caminho do avatar (default se não encontrar específico)
        """
        if not sender_name:
            return self.DEFAULT_AVATAR
            
        avatar_path = os.path.join(self.avatar_dir, f"{sender_name.lower()}.png")
        
        if not os.path.exists(avatar_path):
            LogManager.debug(f"Avatar não encontrado: {avatar_path}, usando default", "AvatarProvider")
            return self.DEFAULT_AVATAR
            
        return avatar_path

    def get_avatar_pixmap(self, sender_name: str) -> QPixmap:
        """
        Retorna QPixmap do avatar com cache.
        
        Args:
            sender_name: Nome do remetente
            
        Returns:
            QPixmap: Avatar carregado
        """
        try:
            # Verifica cache
            if sender_name in self._avatar_cache:
                return self._avatar_cache[sender_name]
            
            # Carrega avatar
            avatar_path = self.get_avatar_path(sender_name)
            pixmap = QPixmap(avatar_path)
            
            # Redimensiona se necessário
            if pixmap.width() > self.AVATAR_SIZE[0] or pixmap.height() > self.AVATAR_SIZE[1]:
                pixmap = pixmap.scaled(
                    self.AVATAR_SIZE[0], 
                    self.AVATAR_SIZE[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            # Guarda no cache
            self._avatar_cache[sender_name] = pixmap
            return pixmap
            
        except Exception as e:
            LogManager.error(f"Erro ao carregar avatar: {e}", "AvatarProvider")
            # Retorna o avatar default em caso de erro
            return QPixmap(self.DEFAULT_AVATAR)

    def clear_cache(self):
        """Limpa cache de avatares"""
        self._avatar_cache.clear()
        LogManager.debug("Cache de avatares limpo", "AvatarProvider")