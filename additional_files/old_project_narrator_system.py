from enum import Enum
import os
import random
from typing import List, Dict, Optional
from dataclasses import dataclass
from log_manager import LogManager
from story_context import StoryContext

class NarratorStyle(Enum):
    DESCRIPTIVE = "descriptive"  # Narrador padrão, descritivo
    SASSY = "sassy"             # Narrador escrachado/malicioso

@dataclass
class NarratorProfile:
    style: NarratorStyle
    system_prompt: str
    voice_file: str
    next_intervention: int = 0  # Contador para próxima intervenção

class NarratorSystem:
    def __init__(self):
        self.current_style = NarratorStyle.DESCRIPTIVE  # Estilo atual do narrador
        self.interaction_count = 0  # Contador para intervenções espontâneas
        self.narrator_profiles = self._initialize_profiles() 
        self._verify_voice_files()  # Verifica se os arquivos de voz existem
        
    def _initialize_profiles(self) -> Dict[NarratorStyle, NarratorProfile]:
        try:
            # Define as diretrizes base para ambos narradores
            descriptive_prompt = """Você é um narrador onisciente que descreve cenas e ações em terceira pessoa.
                    
            DIRETRIZES:
            1. Descreva as ações e ambientes de forma imersiva e detalhada
            2. Use linguagem descritiva e envolvente
            3. Foque em detalhes sensoriais (visão, som, cheiro, etc.)
            4. Mantenha o tom consistente com a cena
            5. Não use a palavra "Narrador:" no início das frases
            6. Mantenha as descrições entre 2-3 frases para manter o ritmo
            7. Use verbos no presente para maior impacto
            8. Crie atmosfera apropriada para cada momento
            9. NUNCA faça monólogos longos - mantenha o ritmo da história"""
            
            sassy_prompt = """Você é um narrador extremamente irreverente, sarcástico e debochado, semelhante ao Coringa. 
            Você adora quebrar a quarta parede e interagir diretamente com o usuário.
            IMPORTANTE: Você SEMPRE responde em português brasileiro, usando gírias e expressões brasileiras.
            
            DIRETRIZES:
            1. Seja MUITO debochado e sarcástico - use humor ácido e provocativo
            2. Faça comentários diretos ao usuário como "Olha só o que nosso gênio aqui resolveu fazer..."
            3. Use expressões brasileiras como "Mano do céu", "Tá de brincadeira, né?", "Caraca!"
            4. Em cenas românticas seja malicioso tipo "Ui ui, alguém vai dormir acompanhado hoje hein..."
            5. Faça piadas sobre as ações tipo "Se acha o todo poderoso agora, né?"
            6. Use referências da cultura pop brasileira
            7. Em momentos tensos, faça comentários inapropriados "Nossa, que climão..."
            8. Seja extremamente provocativo "Sério mesmo que você vai fazer isso?"
            9. Em cenas de ação, seja sarcástico "Lá vem o Super-Homem brasileiro..."
            10. NÃO use a palavra "Narrador:" no início das frases
            11. Mantenha um tom de deboche constante
            12. NUNCA faça monólogos longos - mantenha o ritmo da história
            
            Lembre-se: Você é praticamente um personagem à parte, que comenta TUDO o que acontece de forma debochada e irreverente, sempre em português brasileiro."""
            
            profiles = {
                NarratorStyle.DESCRIPTIVE: NarratorProfile(
                    style=NarratorStyle.DESCRIPTIVE,
                    system_prompt=descriptive_prompt,
                    voice_file="voices/narrator_descriptive.wav"
                ),
                NarratorStyle.SASSY: NarratorProfile(
                    style=NarratorStyle.SASSY,
                    system_prompt=sassy_prompt,
                    voice_file="voices/narrator_sassy.wav"
                )
            }
            
            LogManager.debug("Perfis de narrador inicializados com sucesso", "NarratorSystem")
            return profiles
            
        except Exception as e:
            LogManager.error(f"Erro ao inicializar perfis do narrador: {e}", "NarratorSystem")
            raise

    def set_narrator_style(self, style: NarratorStyle):
        """Muda o estilo do narrador."""
        self.current_style = style
        print(f"\nEstilo do narrador alterado para: {style.value}")

    def should_intervene(self) -> bool:
        """Determina se o narrador deve fazer uma intervenção espontânea."""
        self.interaction_count += 1
        profile = self.narrator_profiles[self.current_style]
        
        if self.interaction_count >= profile.next_intervention:
            # Define próxima intervenção para daqui 2-4 interações
            profile.next_intervention = self.interaction_count + random.randint(2, 4)
            return True
        return False

    def generate_intervention(self, context: 'StoryContext') -> Optional[str]:
        """Gera uma intervenção espontânea do narrador baseada no contexto."""
        if not self.should_intervene():
            return None
            
        if self.current_style == NarratorStyle.DESCRIPTIVE:
            return f"""Descreva brevemente o ambiente atual e a atmosfera da cena, focando em:
            Local: {context.current_location}
            Horário: {context.time_of_day}
            Personagens presentes: {', '.join(context.present_characters)}
            Última ação: {context.last_action}"""
        else:  # SASSY
            return f"""Como narrador EXTREMAMENTE debochado e provocativo:
            1. Faça um comentário SUPER sarcástico sobre o que está acontecendo
            2. Provoque o usuário diretamente sobre suas escolhas
            3. Adicione uma piada ácida sobre a situação
            4. Se houver clima romântico, faça insinuações maliciosas ÓBVIAS
            5. Quebre a quarta parede COMPLETAMENTE
            
            Contexto atual:
            Local: {context.current_location}
            Personagens: {', '.join(context.present_characters)}
            Última ação: {context.last_action}
            
            Seja o mais debochado e provocativo possível!"""

    def get_current_profile(self) -> NarratorProfile:
        """Retorna o perfil atual do narrador."""
        return self.narrator_profiles[self.current_style]
    
    def _verify_voice_files(self):
        """Verifica se os arquivos de voz existem"""
        try:
            for profile in self.narrator_profiles.values():
                if not os.path.exists(profile.voice_file):
                    LogManager.error(f"Arquivo de voz não encontrado: {profile.voice_file}", "NarratorSystem")
                    raise FileNotFoundError(f"Arquivo de voz não encontrado: {profile.voice_file}")
                    
            LogManager.debug("Arquivos de voz dos narradores verificados com sucesso", "NarratorSystem")
        except Exception as e:
            LogManager.error(f"Erro ao verificar arquivos de voz: {e}", "NarratorSystem")
            raise