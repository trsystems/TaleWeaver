from dataclasses import dataclass, field
import json
from typing import Dict, List, Optional
from datetime import datetime

from log_manager import LogManager
from ui_utils import Colors

@dataclass
class PlayerBackground:
    def __init__(self, name: str, gender: str, age: Optional[int] = None, 
                occupation: Optional[str] = None, background_story: Optional[str] = None,
                personality_traits: Optional[List[str]] = None,
                goals: Optional[List[str]] = None,
                is_player: bool = True):
        self.name = name
        self.gender = gender
        self.age = age
        self.occupation = occupation
        self.background_story = background_story
        self.personality_traits = personality_traits or []
        self.goals = goals or []
        self.is_player = is_player

class PlayerCharacter:
    def __init__(self):
        self.background = None
        self.created_at = datetime.now()
        
    async def create_profile(self, basic_info: Dict, llm_client) -> bool:
        """Cria perfil do personagem do jogador"""
        try:
            # Verifica se já existe um perfil
            if self.background is not None:
                LogManager.warning("Tentativa de criar perfil quando já existe um", "PlayerCharacter")
                return False
                
            # Adiciona flag de jogador
            basic_info['is_player'] = True
                
            # Gera uma história de background se não fornecida
            if not basic_info.get('background_story'):
                background_prompt = f"""Crie uma breve história de background para este personagem:
                Nome: {basic_info['name']}
                Gênero: {basic_info['gender']}
                {f"Idade: {basic_info['age']}" if basic_info.get('age') else ""}
                {f"Ocupação: {basic_info['occupation']}" if basic_info.get('occupation') else ""}
                
                Crie um parágrafo curto descrevendo o passado e motivações deste personagem em português do Brasil.
                Inclua também:
                - 3 traços de personalidade principais
                - 2 objetivos ou motivações atuais
                - 1 característica única ou especial
                """
                
                response = llm_client.chat.completions.create(
                    model="llama-2-13b-chat",
                    messages=[
                        {"role": "system", "content": "Você é um criador de histórias que escreve em português do Brasil."},
                        {"role": "user", "content": background_prompt}
                    ],
                    temperature=0.7
                )
                
                generated_text = response.choices[0].message.content.strip()
                
                # Extrai informações do texto gerado usando a LLM
                extraction_prompt = f"""
                Extraia do texto abaixo os seguintes elementos em formato JSON:
                - Lista de 3 traços de personalidade
                - Lista de 2 objetivos principais
                
                Texto: {generated_text}
                
                Formato esperado:
                {{
                    "personality_traits": ["traço1", "traço2", "traço3"],
                    "goals": ["objetivo1", "objetivo2"]
                }}
                """
                
                traits_response = llm_client.chat.completions.create(
                    model="llama-2-13b-chat",
                    messages=[
                        {"role": "system", "content": "Você extrai informações em formato JSON."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    temperature=0.3
                )
                
                try:
                    extracted_data = json.loads(traits_response.choices[0].message.content)
                    basic_info['personality_traits'] = extracted_data.get('personality_traits', ['Determinado', 'Corajoso', 'Sagaz'])
                    basic_info['goals'] = extracted_data.get('goals', ['Fazer justiça', 'Encontrar seu lugar'])
                except json.JSONDecodeError:
                    LogManager.warning("Erro ao extrair traços e objetivos, usando padrões", "PlayerCharacter")
                    basic_info['personality_traits'] = ['Determinado', 'Corajoso', 'Sagaz']
                    basic_info['goals'] = ['Fazer justiça', 'Encontrar seu lugar']
                
                basic_info['background_story'] = generated_text
            
            # Cria o perfil do jogador
            self.background = PlayerBackground(
                name=basic_info['name'],
                gender=basic_info['gender'],
                age=basic_info.get('age'),
                occupation=basic_info.get('occupation'),
                background_story=basic_info.get('background_story'),
                personality_traits=basic_info.get('personality_traits', []),
                goals=basic_info.get('goals', []),
                is_player=True  # Garante que flag está presente no objeto
            )
            
            # Adiciona ao character_manager com flag de jogador
            player_data = {
                'profile': {
                    'name': self.background.name,
                    'gender': self.background.gender,
                    'age': self.background.age,
                    'occupation': self.background.occupation,
                    'background_story': self.background.background_story,
                    'personality_traits': self.background.personality_traits,
                    'goals': self.background.goals
                },
                'voice_file': "voices/narrator_voice.wav",
                'system_prompt_file': f"prompts/{self.background.name.lower()}_prompt.txt",
                'color': Colors.BLUE,
                'is_player': True
            }
            
            if hasattr(self, 'character_manager'):
                self.character_manager.characters[self.background.name] = player_data
                self.character_manager.save_characters()
                LogManager.debug(f"Perfil do jogador {self.background.name} salvo no character_manager", "PlayerCharacter")
            
            LogManager.info(f"Perfil criado para {self.background.name}", "PlayerCharacter")
            return True
            
        except Exception as e:
            LogManager.error(f"Erro ao criar perfil do jogador: {e}", "PlayerCharacter")
            return False
    
    def get_context_for_llm(self) -> str:
        """Retorna o contexto do jogador para a LLM"""
        if not self.background:
            return ""
            
        return f"""IMPORTANTE: O usuário está interpretando o seguinte personagem:
        
        Nome: {self.background.name}
        Gênero: {self.background.gender}
        {f"Idade: {self.background.age}" if self.background.age else ""}
        {f"Ocupação: {self.background.occupation}" if self.background.occupation else ""}
        
        História: {self.background.background_story}
        
        TODAS as ações e falas do usuário devem ser interpretadas como vindas deste personagem.
        Mantenha consistência com o gênero e características do personagem em todas as interações.
        """