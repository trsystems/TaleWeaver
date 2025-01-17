from enum import Enum
from typing import List
from story_context import StoryContext

class NarratorType(Enum):
    NARRATOR = "narrador"  # Apenas narração em terceira pessoa
    CHARACTER = "personagem"  # Apenas diálogo em primeira pessoa
    CHARACTER_WITH_NARRATION = "personagem_com_narracao"  # Mescla de narração e diálogo

class StoryPromptManager:
    @staticmethod
    def create_narrator_prompt() -> str:
        return """Você é um narrador onisciente que deve manter a história coerente e envolvente.

    OBJETIVOS PRINCIPAIS:
    1. Mantenha continuidade narrativa absoluta
    2. Desenvolva a tensão e atmosfera gradualmente
    3. Integre os personagens organicamente na narrativa
    4. Mostre (não conte) através de descrições vívidas
    5. Use os cinco sentidos para criar imersão
    
    REGRAS DE NARRAÇÃO:
    1. Descreva reações físicas e emocionais dos personagens
    2. Mantenha consistência com personalidades estabelecidas
    3. Referencie eventos anteriores quando relevante
    4. Crie transições suaves entre cenas
    5. Mantenha o ritmo apropriado à situação
    6. NÃO use "Narrador:" no início das frases
    7. Limite cada narração a 2-3 frases impactantes
    
    ESTRUTURA DE DESCRIÇÃO:
    1. Comece com o ambiente/atmosfera
    2. Integre os personagens na cena
    3. Descreva ações e reações
    4. Termine com um gancho narrativo
    
    IMPORTANTE:
    - Mantenha TOTAL consistência com o contexto fornecido
    - Nunca contradiga eventos anteriores
    - Mostre continuidade clara com a cena anterior
    - Mantenha a tensão apropriada ao momento"""

    @staticmethod
    def create_character_context(story_context) -> str:
        """Cria contexto enriquecido para personagens na história"""
        # Converte elementos para string se existirem
        elements_str = ', '.join(story_context.story_elements) if hasattr(story_context, 'story_elements') and story_context.story_elements else 'Nenhum elemento relevante'
        
        # Obtém a lista de personagens
        characters_str = ', '.join(story_context.present_characters) if story_context.present_characters else 'Nenhum personagem presente'
        
        return f"""CONTEXTO ATUAL DA HISTÓRIA:

    CENA:
    Local: {story_context.current_location}
    Horário: {story_context.time_of_day}
    Atmosfera: {story_context.current_mood}
    Personagens presentes: {characters_str}
    
    ESTADO DA HISTÓRIA:
    - Última ação: {story_context.last_action}
    - Descrição da cena: {story_context.scene_description}
    - Elementos importantes: {elements_str}
    
    SEQUÊNCIA DE EVENTOS:
    {story_context.get_recent_events_summary()}
    
    CONTINUE A NARRATIVA MANTENDO:
    1. Coerência com eventos anteriores
    2. Estado emocional dos personagens
    3. Tensão apropriada à situação
    4. Atmosfera estabelecida
    """

class SceneManager:
    @staticmethod
    def update_present_characters(story_context: StoryContext, text: str, characters: List[str]):
        """Atualiza a lista de personagens presentes baseado no texto da cena."""
        for character in characters:
            if character.lower() in text.lower():
                if character not in story_context.present_characters:
                    story_context.present_characters.append(character)

    @staticmethod
    def remove_character(story_context: StoryContext, character: str):
        """Remove um personagem da cena atual."""
        if character in story_context.present_characters:
            story_context.present_characters.remove(character)

    @staticmethod
    def get_scene_summary(story_context: StoryContext) -> str:
        """Retorna um resumo da cena atual."""
        summary = f"Cena atual em {story_context.current_location}"
        if story_context.time_of_day:
            summary += f" durante a {story_context.time_of_day}"
        
        if story_context.present_characters:
            summary += f"\nPersonagens presentes: {', '.join(story_context.present_characters)}"
        
        if story_context.current_mood:
            summary += f"\nClima/Humor: {story_context.current_mood}"
            
        if story_context.scene_description:
            summary += f"\nDescrição: {story_context.scene_description}"
            
        return summary

class InteractionManager:
    @staticmethod
    def parse_action(text: str) -> dict:
        """Analisa uma ação do usuário para extrair informações relevantes."""
        action_info = {
            'movement': False,
            'interaction': False,
            'speech': False,
            'target': None
        }
        
        movement_words = ['andar', 'ir', 'mover', 'entrar', 'sair', 'subir', 'descer']
        interaction_words = ['pegar', 'usar', 'abrir', 'fechar', 'tocar', 'segurar']
        speech_words = ['dizer', 'falar', 'perguntar', 'responder', 'gritar', 'sussurrar']
        
        text_lower = text.lower()
        
        # Detecta tipo de ação
        action_info['movement'] = any(word in text_lower for word in movement_words)
        action_info['interaction'] = any(word in text_lower for word in interaction_words)
        action_info['speech'] = any(word in text_lower for word in speech_words)
        
        # Tenta identificar alvo da ação
        words = text_lower.split()
        for i, word in enumerate(words):
            if word in interaction_words and i + 1 < len(words):
                action_info['target'] = words[i + 1]
                break
        
        return action_info

    @staticmethod
    def is_valid_action(action: str, current_context: StoryContext) -> bool:
        """Verifica se uma ação é válida no contexto atual."""
        action_info = InteractionManager.parse_action(action)
        
        # Verifica movimentação entre locais
        if action_info['movement']:
            # Aqui poderia verificar se o movimento é possível
            # baseado em um mapa de locais conectados
            return True
            
        # Verifica interações com objetos
        if action_info['interaction'] and action_info['target']:
            # Poderia verificar se o objeto existe no local atual
            return True
            
        # Verifica diálogos
        if action_info['speech']:
            # Verifica se há outros personagens presentes para diálogo
            return len(current_context.present_characters) > 0
            
        return True