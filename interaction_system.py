from typing import List, Dict, Optional
from character_models import Character
from emotion_system import EmotionType
from log_manager import LogManager
from story_context import StoryContext  # Corrigido o import
import random

class InteractionSystem:
    def __init__(self, characters: Dict[str, Character]):
        self.characters = characters
        self.recent_interactions: List[str] = []
        self.interaction_threshold = 0.3  # Define limite para reações
        
    def should_character_react(self, character: Character, 
                             context: StoryContext,
                             trigger_emotion: EmotionType) -> bool:
        """Determina se um personagem deve reagir baseado em vários fatores."""
        # Não reage se não estiver presente na cena
        if character.name not in context.present_characters:
            return False
            
        reaction_chance = self.interaction_threshold
        
        # Aumenta chance baseado em fatores
        if trigger_emotion in [EmotionType.EXCITED, EmotionType.ANGRY]:
            reaction_chance += 0.2
        elif trigger_emotion in [EmotionType.WORRIED, EmotionType.SAD]:
            reaction_chance += 0.1
            
        # Aumenta chance se personagem foi mencionado recentemente
        if any(character.name.lower() in interaction.lower() 
               for interaction in self.recent_interactions[-3:]):
            reaction_chance += 0.2
            
        return random.random() < reaction_chance

    def generate_reaction_prompt(self, 
                               character: Character, 
                               context: StoryContext,
                               trigger_text: str,
                               trigger_emotion: EmotionType) -> str:
        """Gera um prompt para reação do personagem."""
        return f"""Como {character.name}, reaja à situação atual:

        O que aconteceu: {trigger_text}
        Emoção demonstrada: {trigger_emotion.value}
        
        Contexto:
        Local: {context.current_location}
        Horário: {context.time_of_day}
        Outros presentes: {[name for name in context.present_characters if name != character.name]}
        
        DIRETRIZES:
        1. Reaja de forma natural e condizente com sua personalidade
        2. Considere sua relação com os outros personagens presentes
        3. Mantenha respostas curtas e diretas
        4. Reaja à emoção demonstrada
        5. Use suas memórias passadas para contexto
        
        Responda como {character.name}:"""

    def update_recent_interactions(self, text: str):
        """Atualiza lista de interações recentes."""
        self.recent_interactions.append(text)
        # Mantém apenas as 5 últimas interações
        if len(self.recent_interactions) > 5:
            self.recent_interactions.pop(0)
        LogManager.debug("Interações recentes atualizadas", "InteractionSystem")

    def get_relevant_characters(self, context: StoryContext, 
                              current_speaker: Optional[str] = None) -> List[Character]:
        """Retorna personagens relevantes para possível interação."""
        relevant_chars = []
        
        for name in context.present_characters:
            if name != current_speaker and name in self.characters:
                relevant_chars.append(self.characters[name])
                
        return relevant_chars