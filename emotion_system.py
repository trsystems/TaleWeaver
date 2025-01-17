from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import re

from log_manager import LogManager

class EmotionType(Enum):
    HAPPY = "feliz"
    SAD = "triste"
    ANGRY = "bravo"
    WORRIED = "preocupado"
    EXCITED = "animado"
    NEUTRAL = "neutro"
    THOUGHTFUL = "pensativo"
    PLAYFUL = "brincalhão"

@dataclass
class EmotionParameters:
    speed: float  # Velocidade da fala
    temperature: float  # Variação na voz
    intensity: float  # Intensidade da emoção (0-1)
    pitch_shift: float  # Ajuste de tom
    
    @classmethod
    def get_default_parameters(cls) -> Dict[EmotionType, 'EmotionParameters']:
        return {
            EmotionType.HAPPY: cls(speed=1.1, temperature=0.8, intensity=0.7, pitch_shift=1.05),
            EmotionType.SAD: cls(speed=0.9, temperature=0.5, intensity=0.6, pitch_shift=0.95),
            EmotionType.ANGRY: cls(speed=1.2, temperature=0.9, intensity=0.8, pitch_shift=1.1),
            EmotionType.WORRIED: cls(speed=1.05, temperature=0.6, intensity=0.5, pitch_shift=1.0),
            EmotionType.EXCITED: cls(speed=1.15, temperature=0.85, intensity=0.9, pitch_shift=1.08),
            EmotionType.NEUTRAL: cls(speed=1.0, temperature=0.7, intensity=0.5, pitch_shift=1.0),
            EmotionType.THOUGHTFUL: cls(speed=0.95, temperature=0.6, intensity=0.4, pitch_shift=0.98),
            EmotionType.PLAYFUL: cls(speed=1.08, temperature=0.75, intensity=0.7, pitch_shift=1.03)
        }

@dataclass
class EmotionalResponse:
    text: str
    emotion: EmotionType
    params: EmotionParameters
    
    def __str__(self) -> str:
        return f"[{self.emotion.value.upper()}] {self.text}"

class EmotionAnalyzer:
    def __init__(self):
        self.emotion_patterns = {
            EmotionType.HAPPY: [
                r'\b(feliz|alegr[e|ia]|content[e|a]|satisfeit[o|a]|ador[o|ei]|am[o|ei]|risos?|haha|:D)\b',
                r'!(^[!]+$)',
            ],
            EmotionType.SAD: [
                r'\b(trist[e|eza]|chatea[r|do|da]|deprimid[o|a]|sozinh[o|a]|magoado|dolor[ido|ida]|pena|:\'?[(\(])\b',
                r'\b(saudade|falta|perdi|perdeu)\b'
            ],
            EmotionType.ANGRY: [
                r'\b(raiv[a|oso]|brav[o|a]|irritad[o|a]|furi[a|oso]|ódio|grrr)\b',
                r'([!?!]+$)',
            ],
            EmotionType.WORRIED: [
                r'\b(preocupad[o|a]|nervos[o|a]|ansios[o|a]|medos?|recei[o|oso])\b',
                r'\b(será|talvez|quem sabe|não sei)\b'
            ],
            EmotionType.EXCITED: [
                r'\b(animad[o|a]|empolgad[o|a]|incrível|fantástico|maravilhos[o|a]|uau)\b',
                r'(!{2,})',
            ],
            EmotionType.THOUGHTFUL: [
                r'\b(pens[o|ando]|refleti[r|ndo]|talvez|interessante|compreend[o|er])\b',
                r'\b(hm+|\.{3,})',
            ],
            EmotionType.PLAYFUL: [
                r'\b(brinca[r|ndo]|divertid[o|a]|engracad[o|a]|hehe|rs+)\b',
                r'([:;]-?[)\]}])',
            ]
        }
        
        self.emotion_weights = {
            EmotionType.HAPPY: 1.2,
            EmotionType.SAD: 1.1,
            EmotionType.ANGRY: 1.3,
            EmotionType.WORRIED: 0.9,
            EmotionType.EXCITED: 1.4,
            EmotionType.THOUGHTFUL: 0.8,
            EmotionType.PLAYFUL: 1.1,
            EmotionType.NEUTRAL: 0.5
        }
        
        self.default_params = EmotionParameters.get_default_parameters()
    
    def analyze_text(self, text: str) -> Tuple[EmotionType, float]:
        LogManager.debug(f"Analisando emoção do texto: {text[:50]}...", "Emotion")
        emotion_scores = {emotion: 0.0 for emotion in EmotionType}
    
        # Palavras explícitas de emoção tem peso maior
        explicit_emotions = {
            "apavorad": EmotionType.WORRIED,
            "assustad": EmotionType.WORRIED,
            "aterroriz": EmotionType.WORRIED,
            "med": EmotionType.WORRIED,  # pega medo, medrosa, etc
            "tem": EmotionType.WORRIED,  # pega temor, temendo, etc
            "tremendo": EmotionType.WORRIED,
            "tremula": EmotionType.WORRIED
        }
        
        text_lower = text.lower()
        # Checa primeiro emoções explícitas
        LogManager.debug("Iniciando análise de emoções explícitas...", "Emotion")
        for word, emotion in explicit_emotions.items():
            if word in text_lower:
                emotion_scores[emotion] += 2.0  # Peso maior para emoções explícitas
        
        LogManager.debug("Iniciando análise de padrões...", "Emotion")
        for emotion, patterns in self.emotion_patterns.items():
            emotion_total = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text.lower()))
                if matches:
                    score = matches * self.emotion_weights[emotion]
                    emotion_total += score
                    LogManager.debug(f"Padrão encontrado para {emotion.value}: {pattern} ({matches} matches, score={score:.2f})", "Emotion")
            
            emotion_scores[emotion] = emotion_total
            if emotion_total > 0:
                LogManager.debug(f"Score total para {emotion.value}: {emotion_total:.2f}", "Emotion")
        
        max_score = max(emotion_scores.values())
        if max_score == 0:
            LogManager.info("Nenhuma emoção detectada, usando NEUTRAL como padrão", "Emotion")
            return EmotionType.NEUTRAL, 0.5
            
        dominant_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0]
        intensity = min(1.0, max_score / 3)
        
        LogManager.info(f"Emoção dominante: {dominant_emotion.value} com intensidade {intensity:.2f}", "Emotion")
        return dominant_emotion, intensity

    def get_voice_parameters(self, emotion: EmotionType, intensity: float) -> EmotionParameters:
        """Retorna parâmetros de voz ajustados para a emoção e intensidade."""
        base_params = self.default_params[emotion]
        
        adjusted_params = EmotionParameters(
            speed=1.0 + (base_params.speed - 1.0) * intensity,
            temperature=0.7 + (base_params.temperature - 0.7) * intensity,
            intensity=intensity,
            pitch_shift=1.0 + (base_params.pitch_shift - 1.0) * intensity
        )
        
        return adjusted_params

class EmotionDisplay:
    """Gerencia a exibição visual de estados emocionais"""
    
    EMOTION_COLORS = {
        EmotionType.HAPPY: '\033[92m',      # Verde brilhante
        EmotionType.SAD: '\033[94m',        # Azul
        EmotionType.ANGRY: '\033[91m',      # Vermelho
        EmotionType.WORRIED: '\033[93m',    # Amarelo
        EmotionType.EXCITED: '\033[95m',    # Magenta
        EmotionType.NEUTRAL: '\033[97m',    # Branco
        EmotionType.THOUGHTFUL: '\033[96m', # Ciano
        EmotionType.PLAYFUL: '\033[92m',    # Verde
    }
    
    EMOTION_SYMBOLS = {
        EmotionType.HAPPY: "😊",
        EmotionType.SAD: "😢",
        EmotionType.ANGRY: "😠",
        EmotionType.WORRIED: "😟",
        EmotionType.EXCITED: "😃",
        EmotionType.NEUTRAL: "😐",
        EmotionType.THOUGHTFUL: "🤔",
        EmotionType.PLAYFUL: "😄"
    }
    
    @classmethod
    def show_emotion_state(cls, emotion: EmotionType, intensity: float, previous_emotion: Optional[EmotionType] = None):
        """Exibe o estado emocional atual com barra de intensidade e transição."""
        emotion_color = cls.EMOTION_COLORS.get(emotion, '\033[0m')
        emotion_symbol = cls.EMOTION_SYMBOLS.get(emotion, '')
        
        bars = "█" * int(intensity * 10)
        spaces = "░" * (10 - int(intensity * 10))
        
        transition = ""
        if previous_emotion and previous_emotion != emotion:
            transition = f" (Mudança de {cls.EMOTION_SYMBOLS[previous_emotion]} {previous_emotion.value} → {emotion_symbol})"
        
        print("\n" + "─" * 40)
        print(f"{emotion_color}Estado Emocional: {emotion.value.upper()} {emotion_symbol}{transition}")
        print(f"Intensidade: |{bars}{spaces}| {intensity:.2f}")
        print("─" * 40 + '\033[0m')