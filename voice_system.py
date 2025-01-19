"""
Módulo de Gerenciamento de Voz

Este módulo gerencia a conversão de texto em fala e reprodução de áudio
para o sistema TaleWeaver.
"""

import os
import wave
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import sounddevice as sd

class VoiceSystem:
    def __init__(self, voice_dir: Path, sample_rate: int = 24000, volume: float = 1.0):
        """
        Inicializa o sistema de voz.
        
        Args:
            voice_dir: Diretório contendo arquivos de voz
            sample_rate: Taxa de amostragem do áudio (default: 24000)
            volume: Volume do áudio (0.0 a 1.0)
        """
        self.voice_dir = voice_dir
        self.sample_rate = sample_rate
        self.volume = volume
        self.voice_profiles: Dict[str, Any] = {}
        
        # Verifica se o diretório de vozes existe
        if not self.voice_dir.exists():
            self.voice_dir.mkdir(parents=True)
            
        # Configurações padrão do dispositivo de áudio
        sd.default.samplerate = self.sample_rate
        sd.default.channels = 1

    async def add_voice_profile(self, profile_name: str, voice_file: str) -> None:
        """
        Adiciona um perfil de voz ao sistema.
        
        Args:
            profile_name: Nome do perfil (ex: 'narrator')
            voice_file: Nome do arquivo de voz no diretório de vozes
        """
        try:
            voice_path = self.voice_dir / voice_file
            if not voice_path.exists():
                raise FileNotFoundError(f"Arquivo de voz não encontrado: {voice_path}")
                
            self.voice_profiles[profile_name] = {
                'file': voice_path,
                'config': {
                    'pitch': 0.0,
                    'speed': 1.0,
                    'emphasis': 1.0
                }
            }
            
        except Exception as e:
            print(f"Erro ao adicionar perfil de voz: {e}")
            raise

    async def text_to_speech(self, text: str, voice_profile: str = 'default') -> np.ndarray:
        """
        Converte texto em áudio usando o perfil de voz especificado.
        
        Args:
            text: Texto a ser convertido
            voice_profile: Nome do perfil de voz a ser usado
            
        Returns:
            Array numpy contendo os dados de áudio
        """
        try:
            # Verifica se o perfil de voz existe
            if voice_profile not in self.voice_profiles:
                raise ValueError(f"Perfil de voz '{voice_profile}' não encontrado")
                
            # TODO: Implementar conversão de texto para fala
            # Por enquanto, retornamos um array de silêncio
            duration = len(text) * 0.1  # 100ms por caractere
            samples = int(duration * self.sample_rate)
            return np.zeros(samples, dtype=np.float32)
            
        except Exception as e:
            print(f"Erro ao converter texto em fala: {e}")
            raise

    async def play_audio(self, audio_data: np.ndarray) -> None:
        """
        Reproduz os dados de áudio no dispositivo de saída.
        
        Args:
            audio_data: Array numpy contendo os dados de áudio
        """
        try:
            # Aplica volume
            audio_data = audio_data * self.volume
            
            # Reproduz o áudio
            sd.play(audio_data)
            sd.wait()
            
        except Exception as e:
            print(f"Erro ao reproduzir áudio: {e}")
            raise

    async def stop_audio(self) -> None:
        """Interrompe a reprodução de áudio atual"""
        try:
            sd.stop()
        except Exception as e:
            print(f"Erro ao parar reprodução de áudio: {e}")
            raise

    async def set_volume(self, volume: float) -> None:
        """
        Define o volume do sistema de voz.
        
        Args:
            volume: Novo volume (0.0 a 1.0)
        """
        try:
            if not 0.0 <= volume <= 1.0:
                raise ValueError("Volume deve estar entre 0.0 e 1.0")
                
            self.volume = volume
        except Exception as e:
            print(f"Erro ao definir volume: {e}")
            raise

    async def close(self) -> None:
        """Libera recursos do sistema de voz"""
        try:
            await self.stop_audio()
        except Exception as e:
            print(f"Erro ao fechar sistema de voz: {e}")
            raise

    async def set_narrator_voice(self, voice_file: str) -> None:
        """
        Configura a voz do narrador.
        
        Args:
            voice_file: Caminho do arquivo de voz do narrador
        """
        try:
            # Armazena a configuração da voz do narrador
            self.voice_profiles['narrator'] = {
                'file': self.voice_dir / voice_file,
                'config': {
                    'pitch': 0.0,
                    'speed': 1.0,
                    'emphasis': 1.0
                }
            }
            print(f"Voz do narrador configurada: {voice_file}")
            
        except Exception as e:
            print(f"Erro ao configurar voz do narrador: {e}")
            raise
