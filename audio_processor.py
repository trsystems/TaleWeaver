import os
import traceback
import wave
import torch
import numpy as np
import soundfile as sf
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread
import time
from typing import List, Optional
import threading

import torchaudio
from event_manager import EventType, StoryEvent
from log_manager import LogManager
from character_models import Character
from emotion_system import EmotionalResponse, EmotionParameters
from audio_player import (
    PersistentAudioPlayer,
    InlineAudioPlayer
)
import soundfile as sf
import numpy as np

class AudioProcessor:
    def __init__(self, xtts_model, xtts_config, output_dir, gui_mode=False, event_manager=None):
        self.xtts_model = xtts_model
        self.xtts_config = xtts_config
        self.output_dir = output_dir
        self.gui_mode = gui_mode
        self.event_manager = event_manager
        self.executor = ThreadPoolExecutor(max_workers=4)
        LogManager.debug("AudioProcessor inicializado com executor", "AudioProcessor")
        
        # Escolhe o player baseado no modo
        if gui_mode:
            from audio_player import InlineAudioPlayer
            LogManager.debug("Inicializando player inline...", "AudioProcessor")
            self.player = InlineAudioPlayer(event_manager=event_manager)
        else:
            from audio_player import PersistentAudioPlayer
            LogManager.debug("Inicializando player persistente...", "AudioProcessor")
            self.player = PersistentAudioPlayer()
            self.player_thread = threading.Thread(target=self.player.run, daemon=True)
            self.player_thread.start()

    async def process_segment(self, text: str, character_name: str, voice_file: str):
        try:
            LogManager.debug(f"\nProcessando segmento para {character_name}", "AudioProcessor")
            if not text.strip():
                return None
                
            # Validação do arquivo de voz
            if not os.path.exists(voice_file):
                LogManager.error(f"Arquivo de voz não encontrado para {character_name}: {voice_file}", "AudioProcessor")
                return None

            # Nome do arquivo de saída
            output_path = os.path.join(
                self.output_dir,
                f"{character_name.lower()}_response_{self.current_segment}_{int(time.time())}.wav"
            )
            
            LogManager.debug(f"Gerando áudio em: {output_path}", "AudioProcessor")
            clean_text = self.clean_text_for_tts(text)
            
            # Limpa CUDA cache
            torch.cuda.empty_cache()
            await asyncio.sleep(0.1)
            
            # Gera o áudio
            output = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                lambda: self.xtts_model.synthesize(
                    clean_text,
                    self.xtts_config,
                    speaker_wav=voice_file,
                    gpt_cond_len=30,
                    temperature=0.7,
                    language='pt',
                    speed=1.0
                )
            )
            
            # Salva o áudio
            padded_audio = np.pad(output['wav'], (0, int(self.xtts_config.audio.sample_rate * 0.5)))
            sf.write(output_path, padded_audio, self.xtts_config.audio.sample_rate)
            
            # Registra e retorna
            self.generated_files.append(output_path)
            self.current_segment += 1
            LogManager.info(f"Áudio gerado com sucesso para {character_name}", "AudioProcessor")
            
            return output_path
            
        except Exception as e:
            LogManager.error(f"Erro ao processar segmento de áudio: {e}", "AudioProcessor")
            return None
       
    def segment_response(self, text: str, max_length: int = 150) -> List[str]:
        """Divide o texto em segmentos menores mantendo frases completas."""
        segments = []
        major_stops = ['. ', '! ', '? ', ': ', '\n']
        minor_stops = [', ', '; ', ' - ']
        
        current_text = text
        while current_text:
            if len(current_text) <= max_length:
                segments.append(current_text)
                break
                
            # Procura pelo melhor ponto de parada dentro do limite
            split_point = -1
            
            # Primeiro tenta pontuações principais
            for stop in major_stops:
                pos = current_text[:max_length].rfind(stop)
                if pos > split_point:
                    split_point = pos + len(stop)
            
            # Se não encontrar pontuação principal, tenta pontuações secundárias
            if split_point == -1:
                for stop in minor_stops:
                    pos = current_text[:max_length].rfind(stop)
                    if pos > max_length * 0.5:  # Só usa se estiver depois da metade
                        split_point = pos + len(stop)
                        break
            
            # Se ainda não encontrou, corta no espaço mais próximo
            if split_point == -1:
                split_point = current_text[:max_length].rfind(' ')
                if split_point == -1:
                    split_point = max_length
            
            segment = current_text[:split_point].strip()
            if segment:
                segments.append(segment)
                
            # Move para o próximo segmento
            current_text = current_text[split_point:].strip()
        
        return segments

    def get_generated_files(self):
        return self.generated_files.copy()
    
    async def synthesize_speech(self, response: EmotionalResponse, character: Character) -> Optional[str]:
        """Sintetiza fala com emoção"""
        try:
            LogManager.debug("Iniciando síntese de fala...", "AudioProcessor")
            
            # Reinicializa executor se necessário
            if not self.executor or self.executor._shutdown:
                self.executor = ThreadPoolExecutor(max_workers=1)
                LogManager.debug("Executor reinicializado", "AudioProcessor")

            # Validação dos parâmetros de emoção
            if not hasattr(response, 'params') or not response.params:
                LogManager.warning("Parâmetros de emoção ausentes, usando padrão", "AudioProcessor")
                params = EmotionParameters(
                    speed=1.0,
                    temperature=0.7,
                    intensity=0.5,
                    pitch_shift=1.0
                )
            else:
                params = response.params

            # Processa o texto
            text = response.text.strip()
            if not text:
                return None

            # Verifica arquivo de voz
            voice_file = character.get_voice_path()
            if not os.path.exists(voice_file):
                LogManager.error(f"Arquivo de voz não encontrado: {voice_file}", "AudioProcessor")
                return None

            # Verifica e converte o arquivo de voz se necessário
            temp_voice_file = await self._ensure_valid_wav(voice_file)
            if not temp_voice_file:
                LogManager.error(f"Não foi possível processar o arquivo de voz: {voice_file}", "AudioProcessor")
                return None

            try:
                # Gera nome único para o arquivo
                filename = f"{character.name}_{int(time.time())}.wav"
                output_path = os.path.join(self.output_dir, filename)

                # Garante que o diretório existe
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Sintetiza a fala com os parâmetros emocionais
                await self._synthesize_with_emotion(
                    text=text,
                    output_path=output_path,
                    voice_file=temp_voice_file,
                    emotion_params=params
                )
                LogManager.debug(f"Áudio gerado com sucesso: {output_path}", "AudioProcessor")
                return output_path

            except Exception as e:
                LogManager.error(f"Erro na síntese de voz: {e}", "AudioProcessor")
                LogManager.error(f"Stack trace: {traceback.format_exc()}", "AudioProcessor")
                self._clear_gpu_cache()
                return None

            finally:
                # Limpa arquivo temporário se foi criado
                if temp_voice_file != voice_file and os.path.exists(temp_voice_file):
                    try:
                        os.remove(temp_voice_file)
                    except:
                        pass

        except Exception as e:
            LogManager.error(f"Erro na síntese de voz: {e}", "AudioProcessor")
            LogManager.error(f"Stack trace: {traceback.format_exc()}", "AudioProcessor")
            return None
            
    async def _synthesize_with_emotion(self, text: str, output_path: str, 
                                    voice_file: str, emotion_params: EmotionParameters) -> None:
        """Sintetiza fala com parâmetros emocionais"""
        try:
            LogManager.debug(f"Sintetizando áudio: {text[:50]}...", "AudioProcessor")
            
            # Tenta carregar voz de referência usando soundfile
            try:
                import soundfile as sf
                wav, sampling_rate = sf.read(voice_file, dtype='int16')
                # Converte para mono se necessário
                if len(wav.shape) > 1:
                    wav = wav.mean(axis=1)
            except Exception as sf_error:
                LogManager.warning(f"Falha ao carregar com soundfile: {sf_error}", "AudioProcessor")
                try:
                    import librosa
                    wav, sampling_rate = librosa.load(voice_file, sr=None)
                    # Converte para int16
                    wav = (wav * 32767).astype(np.int16)
                except Exception as librosa_error:
                    LogManager.error(f"Falha ao carregar com librosa: {librosa_error}", "AudioProcessor")
                    raise ValueError(f"Não foi possível carregar o arquivo de voz: {voice_file}")

            # Cria arquivo temporário em formato wav conhecido
            temp_voice_file = os.path.join(os.path.dirname(voice_file), "temp_voice.wav")
            try:
                sf.write(temp_voice_file, wav, sampling_rate, format='WAV', subtype='PCM_16')
            except Exception as temp_error:
                LogManager.error(f"Erro ao criar arquivo temporário: {temp_error}", "AudioProcessor")
                raise

            try:
                # Processa a voz para obter embeddings usando arquivo temporário
                gpt_cond_latent, speaker_embedding = self.xtts_model.get_conditioning_latents(
                    audio_path=temp_voice_file,
                    gpt_cond_len=30,
                    gpt_cond_chunk_len=4,
                    max_ref_length=60
                )
                
                # Gera o áudio com os embeddings e parâmetros emocionais
                output = self.xtts_model.inference(
                    text=text,
                    language="pt",
                    gpt_cond_latent=gpt_cond_latent,
                    speaker_embedding=speaker_embedding,
                    temperature=emotion_params.temperature
                )

                # Processa o áudio resultante
                audio = output['wav']
                
                # Aplica efeitos emocionais
                if emotion_params.speed != 1.0:
                    audio = self._adjust_speed(audio, emotion_params.speed)
                    
                if emotion_params.pitch_shift != 1.0:
                    audio = self._adjust_pitch(audio, emotion_params.pitch_shift)
                
                # Ajusta intensidade se necessário
                if emotion_params.intensity != 0.5:
                    audio = self._adjust_intensity(audio, emotion_params.intensity)
                    
                # Normaliza e converte
                audio = audio / np.abs(audio).max()
                audio = (audio * 32767).astype(np.int16)
                
                # Garante que o diretório existe
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Salva com soundfile
                sf.write(output_path, audio, 24000, format='WAV', subtype='PCM_16')

                LogManager.debug(f"Áudio salvo em: {output_path}", "AudioProcessor")
                
            finally:
                # Limpa arquivo temporário
                if os.path.exists(temp_voice_file):
                    try:
                        os.remove(temp_voice_file)
                    except:
                        pass
            
        except Exception as e:
            LogManager.error(f"Erro ao sintetizar áudio: {e}", "AudioProcessor")
            LogManager.error(f"Stack trace: {traceback.format_exc()}", "AudioProcessor")
            self._clear_gpu_cache()
            raise
    
    async def _ensure_valid_wav(self, voice_file: str) -> str:
        """Garante que o arquivo de voz está em um formato WAV válido"""
        try:
            # Verifica se o arquivo existe
            if not os.path.exists(voice_file):
                raise FileNotFoundError(f"Arquivo de voz não encontrado: {voice_file}")
                
            # Cria um arquivo WAV temporário
            temp_file = f"{voice_file}.temp.wav"
            
            # Tenta ler o arquivo com librosa e salvar como WAV
            try:
                import librosa
                y, sr = librosa.load(voice_file, sr=None)
                librosa.output.write_wav(temp_file, y, sr)
                return temp_file
            except:
                # Se falhar com librosa, tenta com soundfile
                try:
                    import soundfile as sf
                    data, samplerate = sf.read(voice_file)
                    sf.write(temp_file, data, samplerate, 'PCM_16')
                    return temp_file
                except:
                    # Se ambos falharem, retorna o arquivo original
                    return voice_file
                    
        except Exception as e:
            LogManager.error(f"Erro ao processar arquivo de voz: {e}", "AudioProcessor")
            return voice_file
    
    def _adjust_speed(self, audio: torch.Tensor, speed: float) -> torch.Tensor:
        """Ajusta velocidade do áudio"""
        length = int(audio.size(0) / speed)
        return torchaudio.transforms.Resample(
            orig_freq=24000,
            new_freq=int(24000 * speed)
        )(audio)[:length]
    
    def _adjust_pitch(self, audio: torch.Tensor, pitch_shift: float) -> torch.Tensor:
        """Ajusta pitch do áudio"""
        if pitch_shift == 1.0:
            return audio
        # Usa torch.stft e istft para shift de pitch
        n_fft = 2048
        hop_length = n_fft // 4
        
        # Converte para frequência
        stft = torch.stft(
            audio, 
            n_fft=n_fft, 
            hop_length=hop_length,
            return_complex=True
        )
        
        # Aplica shift
        freq_bins = torch.fft.fftfreq(n_fft)
        shifted_bins = torch.round(freq_bins * pitch_shift).long()
        shifted_stft = torch.zeros_like(stft)
        
        valid_bins = (shifted_bins >= 0) & (shifted_bins < n_fft // 2 + 1)
        shifted_stft[:, valid_bins] = stft[:, shifted_bins[valid_bins]]
        
        # Converte de volta para tempo
        return torch.istft(
            shifted_stft,
            n_fft=n_fft,
            hop_length=hop_length,
            length=audio.size(0)
        )

    def _apply_emotion_effects(self, audio: torch.Tensor, 
                            params: EmotionParameters) -> torch.Tensor:
        """Aplica efeitos baseados em emoção no áudio"""
        try:
            # Ajusta pitch
            if params.pitch_shift != 1.0:
                audio = self._pitch_shift(audio, params.pitch_shift)
                
            # Ajusta velocidade
            if params.speed != 1.0:
                audio = self._change_speed(audio, params.speed)
                
            # Ajusta intensidade
            if params.intensity != 0.5:
                audio = self._adjust_intensity(audio, params.intensity)
                
            return audio
            
        except Exception as e:
            LogManager.error(f"Erro ao aplicar efeitos: {e}", "AudioProcessor")
            return audio

    # async def synthesize_speech(self, response: EmotionalResponse, character: Character):
    #     if not os.path.exists(character.voice_file):
    #         LogManager.error(f"Arquivo de voz não encontrado: {character.voice_file}", "AudioProcessor")
    #         return
        
    #     try:
    #         LogManager.debug("Iniciando síntese de fala...", "AudioProcessor")

    #         # Reinicializa o executor se estiver fechado
    #         if self.executor._shutdown:
    #             self.executor = ThreadPoolExecutor(max_workers=4)

    #         if hasattr(self.xtts_config, 'speed'):
    #             self.xtts_config.speed = response.params.speed
    #             LogManager.debug(f"Velocidade ajustada para: {response.params.speed}", "AudioProcessor")
    #         if hasattr(self.xtts_config, 'temperature'):
    #             self.xtts_config.temperature = response.params.temperature
    #             LogManager.debug(f"Temperatura ajustada para: {response.params.temperature}", "AudioProcessor")
            
    #         await self.process_text_to_speech(response, character)
    #         LogManager.info("Síntese de fala concluída com sucesso", "AudioProcessor")
                
    #     except Exception as e:
    #         LogManager.error(f"Erro na síntese de voz: {e}", "AudioProcessor")
    #         raise
    #     finally:
    #         torch.cuda.empty_cache()

    # async def process_text_to_speech(self, response: EmotionalResponse, character: Character):
    #     try:
    #         clean_text = response.text.replace('033', '').replace('[95m', '').replace('[0m', '').strip()
    #         segments = self.segment_response(clean_text)
            
    #         LogManager.debug(f"Processando {len(segments)} segmentos", "AudioProcessor")
    #         self.stop_event.clear()
    #         self.current_segment = 0
    #         self.generated_files = []  # Limpa lista anterior
            
    #         for segment in segments:
    #             if segment.strip():
    #                 output_path = await self.process_segment(segment, character.name, character.voice_file)
    #                 if output_path:
    #                     self.generated_files.append(output_path)
    #                     # Reproduz cada segmento se não estiver em modo GUI
    #                     if not hasattr(self, 'gui_mode') or not self.gui_mode:
    #                         await self.player.play_audio(output_path)
    #                     await asyncio.sleep(0.1)  # Pequena pausa entre segmentos
            
    #         return self.generated_files
            
    #     except Exception as e:
    #         LogManager.error(f"Erro no processamento de fala: {e}", "AudioProcessor")
    #         torch.cuda.empty_cache()

    async def process_text_to_speech(self, response: EmotionalResponse, character: Character, output_path: str):
        """Processa a síntese texto-fala."""
        try:
            # Processa em chunks se o texto for muito longo
            text_chunks = self._split_text(response.text)
            LogManager.debug(f"Processando {len(text_chunks)} segmentos", "AudioProcessor")
            
            for i, chunk in enumerate(text_chunks):
                LogManager.debug(f"\nProcessando segmento para {character.name}", "AudioProcessor")
                
                # Gera áudio para o chunk
                self.xtts_model.tts_to_file(
                    text=chunk,
                    language='pt',
                    speaker_wav=character.voice_file,
                    file_path=output_path if i == 0 else f"{output_path}.temp{i}"
                )
                
                # Se houver mais de um chunk, concatena os arquivos
                if i > 0 and os.path.exists(f"{output_path}.temp{i}"):
                    self._concatenate_audio_files(output_path, f"{output_path}.temp{i}")
                    os.remove(f"{output_path}.temp{i}")
            
        except Exception as e:
            LogManager.error(f"Erro ao processar texto para fala: {e}", "AudioProcessor")
            raise

    def _split_text(self, text: str, max_chars: int = 200) -> List[str]:
        """Divide o texto em chunks menores para processamento."""
        chunks = []
        current_chunk = ""
        
        for sentence in text.split('. '):
            if len(current_chunk) + len(sentence) < max_chars:
                current_chunk += sentence + '. '
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + '. '
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
    
    def _concatenate_audio_files(self, base_file: str, append_file: str):
        """Concatena dois arquivos de áudio."""
        try:
            with wave.open(base_file, 'rb') as wav1:
                with wave.open(append_file, 'rb') as wav2:
                    # Verifica se os parâmetros são compatíveis
                    if wav1.getparams() != wav2.getparams():
                        raise ValueError("Parâmetros de áudio incompatíveis")
                        
                    # Lê os dados
                    data1 = wav1.readframes(wav1.getnframes())
                    data2 = wav2.readframes(wav2.getnframes())
                    
            # Escreve o arquivo concatenado
            with wave.open(base_file, 'wb') as output:
                output.setparams(wav1.getparams())
                output.writeframes(data1)
                output.writeframes(data2)
                
        except Exception as e:
            LogManager.error(f"Erro ao concatenar arquivos de áudio: {e}", "AudioProcessor")
            raise

    def clean_text_for_tts(self, text: str) -> str:
        """Limpa e prepara o texto para síntese de voz, mantendo exclamações e substituindo pontos por vírgulas."""
        # Remove a palavra "Narrador:" e suas variações
        cleaned = re.sub(r'^Narrador:?\s*', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*Narrador:?\s*', ' ', cleaned, flags=re.IGNORECASE)
        
        # Remove marcações de estilo
        cleaned = re.sub(r'\*[^*]*\*', '', cleaned)
        
        # Trata pontuações finais
        cleaned = re.sub(r'\.\s*$', ',', cleaned)  # Substitui ponto final por vírgula
        cleaned = re.sub(r'\.{2,}\s*$', ',', cleaned)  # Substitui múltiplos pontos por vírgula
        cleaned = re.sub(r'!{2,}', '!', cleaned)  # Reduz múltiplas exclamações para uma
        
        # Mantém caracteres essenciais, incluindo exclamação
        cleaned = re.sub(r'[^a-zA-ZáàâãéèêíïóôõöúçñÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ0-9\s.,;:!-]', '', cleaned)
        
        # Normaliza espaços
        cleaned = ' '.join(cleaned.split())
                
        return cleaned

    # def cleanup(self):
    #     """Limpa recursos do processador de áudio"""
    #     try:
    #         if hasattr(self, 'player') and self.player:
    #             # Verifica se o player ainda existe e está ativo
    #             try:
    #                 if getattr(self.player, 'window', None) and not self.player.window._closed:
    #                     self.player.stop()
    #                     self.player.cleanup()
    #             except (RuntimeError, AttributeError):
    #                 pass  # Ignora erros se o player já foi deletado
                
    #         # Limpa outros recursos
    #         if hasattr(self, 'stop_event'):
    #             self.stop_event.set()
    #         if hasattr(self, 'thread_pool'):
    #             self.thread_pool.shutdown(wait=False)
                
    #     except Exception as e:
    #         # Logamos o erro mas não o propagamos para não afetar o encerramento
    #         LogManager.debug(f"Aviso na limpeza do AudioProcessor: {e}", "AudioProcessor")
    def _clear_gpu_cache(self):
        """Limpa cache da GPU"""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                LogManager.debug("Cache da GPU limpo", "AudioProcessor")
        except Exception as e:
            LogManager.error(f"Erro ao limpar cache: {e}", "AudioProcessor")

    def cleanup(self):
        """Limpa recursos do AudioProcessor"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            LogManager.debug("AudioProcessor cleanup concluído", "AudioProcessor")
        except Exception as e:
            LogManager.error(f"Erro no cleanup do AudioProcessor: {e}", "AudioProcessor")

    def __del__(self):
        """Destrutor que chama cleanup de forma segura"""
        try:
            self.cleanup()
        except:
            pass  # Ignora erros durante o encerramento do programa