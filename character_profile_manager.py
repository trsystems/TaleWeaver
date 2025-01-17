from typing import Dict, List, Optional
import json
import os
from datetime import datetime
from log_manager import LogManager
from story_context import StoryContext

class CharacterProfile:
    def __init__(self, name: str):
        self.name = name
        self.basic_info = {
            "occupation": "",
            "appearance": "",
            "voice_traits": "",
            "age": "",
            "origin": ""
        }
        self.personality = {
            "traits": [],
            "values": [],
            "fears": [],
            "desires": []
        }
        self.background = {
            "history": "",
            "key_events": [],
            "relationships": {},
            "traumas": [],
            "achievements": []
        }
        self.abilities = {
            "skills": [],
            "knowledge": [],
            "specialties": []
        }
        self.dynamic_state = {
            "current_emotions": [],
            "current_goals": [],
            "recent_experiences": [],
            "character_development": []
        }
        self.last_updated = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Converte perfil para dicionário"""
        return {
            "name": self.name,
            "basic_info": self.basic_info,
            "personality": self.personality,
            "background": self.background,
            "abilities": self.abilities,
            "dynamic_state": self.dynamic_state,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CharacterProfile':
        """Cria perfil a partir de dicionário"""
        profile = cls(data["name"])
        profile.basic_info = data["basic_info"]
        profile.personality = data["personality"]
        profile.background = data["background"]
        profile.abilities = data["abilities"]
        profile.dynamic_state = data["dynamic_state"]
        profile.last_updated = data["last_updated"]
        return profile

class CharacterProfileManager:
    def __init__(self, profiles_dir: str = "character_profiles", story_chat=None):
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, CharacterProfile] = {}
        self.story_chat = story_chat  # Adiciona referência ao StoryChat
        os.makedirs(profiles_dir, exist_ok=True)
        self._load_profiles()

    def _load_profiles(self):
        """Carrega perfis existentes"""
        for filename in os.listdir(self.profiles_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.profiles_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        profile = CharacterProfile.from_dict(data)
                        self.profiles[profile.name] = profile
                except Exception as e:
                    LogManager.error(f"Erro ao carregar perfil {filename}: {e}", "ProfileManager")

    def save_profile(self, profile: CharacterProfile):
        """Salva perfil em arquivo JSON"""
        try:
            profile_path = os.path.join(self.profiles_dir, f"{profile.name.lower()}.json")
            profile_data = profile.to_dict()
            
            # Faz backup do arquivo existente
            if os.path.exists(profile_path):
                backup_path = f"{profile_path}.bak"
                try:
                    import shutil
                    shutil.copy2(profile_path, backup_path)
                except Exception as e:
                    LogManager.warning(f"Erro ao criar backup de {profile_path}: {e}", "ProfileManager")

            # Salva novo perfil
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            LogManager.info(f"Perfil de {profile.name} salvo com sucesso", "ProfileManager")

        except Exception as e:
            LogManager.error(f"Erro ao salvar perfil de {profile.name}: {e}", "ProfileManager")

    async def analyze_story_for_character(self, name: str, story_events: List[dict], llm_client) -> Optional[CharacterProfile]:
        """Analisa eventos da história para criar/atualizar perfil"""
        try:
            # Filtra eventos relevantes para o personagem
            relevant_events = [
                event for event in story_events
                if name.lower() in event['content'].lower() or
                   (event.get('character', '').lower() == name.lower())
            ]

            if not relevant_events:
                return None

            # Cria prompt para análise
            prompt = f"""Analise os seguintes eventos relacionados ao personagem {name} e 
            crie um perfil detalhado. Extraia todas as informações relevantes sobre:
            
            Eventos a analisar:
            {self._format_events_for_prompt(relevant_events)}
            
            Gere um objeto JSON completo seguindo exatamente esta estrutura:
            {{
                "basic_info": {{
                    "occupation": "",
                    "appearance": "",
                    "voice_traits": "",
                    "age": "",
                    "origin": ""
                }},
                "personality": {{
                    "traits": [],
                    "values": [],
                    "fears": [],
                    "desires": []
                }},
                "background": {{
                    "history": "",
                    "key_events": [],
                    "relationships": {{}},
                    "traumas": [],
                    "achievements": []
                }},
                "abilities": {{
                    "skills": [],
                    "knowledge": [],
                    "specialties": []
                }},
                "dynamic_state": {{
                    "current_emotions": [],
                    "current_goals": [],
                    "recent_experiences": [],
                    "character_development": []
                }}
            }}
            
            Preencha todos os campos baseado nas informações disponíveis nos eventos.
            Para campos sem informação explícita, faça inferências razoáveis baseadas no contexto."""

            # Obtém análise da LLM
            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )

            # Processa resultado
            profile_data = json.loads(response.choices[0].message.content)
            profile_data["name"] = name
            profile_data["last_updated"] = datetime.now().isoformat()

            # Cria ou atualiza perfil
            profile = CharacterProfile.from_dict(profile_data)
            self.profiles[name] = profile
            self.save_profile(profile)

            return profile

        except Exception as e:
            LogManager.error(f"Erro ao analisar história para {name}: {e}", "ProfileManager")
            return None

    def _format_events_for_prompt(self, events: List[dict]) -> str:
        """Formata eventos para o prompt da LLM"""
        formatted = []
        for event in events:
            if event['type'] == 'dialogue':
                formatted.append(f"Diálogo - {event['character']}: {event['content']}")
            else:
                formatted.append(f"Narração: {event['content']}")
        return "\n".join(formatted)

    async def update_profile_with_event(self, name: str, event: dict, llm_client):
        try:
            if name not in self.profiles:
                return

            profile = self.profiles[name]
            prompt = f"""Analise o novo evento e atualize o estado atual do personagem {name}.
            
            Perfil atual:
            {json.dumps(profile.to_dict(), indent=2)}
            
            Novo evento:
            Tipo: {event['type']}
            Conteúdo: {event['content']}
            
            Identifique mudanças em:
            1. Estado emocional atual (medo, desespero, alívio, etc)
            2. Situação física atual (livre, presa, ferida, etc)
            3. Objetivos imediatos baseados na situação
            4. Atitude esperada em interações (hostil, desconfiada, etc)
            5. Experiências recentes
            6. Desenvolvimento do personagem
            7. Possíveis novos traumas ou conquistas
            8. Mudanças em relacionamentos
            
            Retorne apenas as seções que precisam ser atualizadas no formato JSON."""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )

            updates = json.loads(response.choices[0].message.content)
            self._apply_updates(profile, updates)
            self.save_profile(profile)

        except Exception as e:
            LogManager.error(f"Erro ao atualizar perfil de {name}: {e}", "ProfileManager")

    def _apply_updates(self, profile: CharacterProfile, updates: dict):
        """Aplica atualizações ao perfil"""
        for category, data in updates.items():
            if hasattr(profile, category):
                current = getattr(profile, category)
                if isinstance(current, dict):
                    for key, value in data.items():
                        if key in current:
                            if isinstance(current[key], list):
                                # Adiciona novos itens à lista
                                current[key].extend([x for x in value if x not in current[key]])
                            else:
                                current[key] = value

        profile.last_updated = datetime.now().isoformat()

    async def get_character_context(self, name: str, narrative_manager) -> str:
        """Obtém contexto completo do personagem incluindo histórico narrativo"""
        try:
            # Obtém perfil base do personagem
            profile = self.profiles.get(name)
            if not profile:
                return ""

            # Obtém histórico narrativo
            history = narrative_manager.get_character_history(name)
            relationships = narrative_manager.get_character_relationships(name)

            # Formata o contexto completo
            context_parts = []

            # Informações básicas
            context_parts.append(f"=== Perfil de {name} ===")
            context_parts.append(f"Ocupação: {profile.basic_info['occupation']}")
            context_parts.append(f"Aparência: {profile.basic_info['appearance']}")

            # Personalidade atual
            context_parts.append("\n=== Personalidade e Estado Atual ===")
            context_parts.append(f"Traços: {', '.join(profile.personality['traits'])}")
            context_parts.append(f"Valores: {', '.join(profile.personality['values'])}")
            context_parts.append(f"Medos: {', '.join(profile.personality['fears'])}")
            context_parts.append(f"Estado Emocional: {', '.join(profile.dynamic_state['current_emotions'])}")
            context_parts.append(f"Objetivos Atuais: {', '.join(profile.dynamic_state['current_goals'])}")

            # Histórico recente
            context_parts.append("\n=== Histórico Recente ===")
            for event in history['events'][:3]:  # Últimos 3 eventos
                context_parts.append(f"- {event['content']}")

            # Relacionamentos
            context_parts.append("\n=== Relacionamentos ===")
            for other_char, interactions in relationships.items():
                total_interactions = sum(i['count'] for i in interactions)
                emotions = [e for i in interactions for e in i['emotions']]
                context_parts.append(f"Com {other_char} ({total_interactions} interações):")
                context_parts.append(f"- Emoções predominantes: {', '.join(set(emotions))}")

            return "\n".join(context_parts)

        except Exception as e:
            LogManager.error(f"Erro ao obter contexto do personagem: {e}", "ProfileManager")
            return ""

    def get_or_create_profile(self, name: str) -> Optional[CharacterProfile]:
        """Obtém ou cria perfil do personagem"""
        try:
            LogManager.debug(f"Obtendo perfil para {name}", "ProfileManager")
            
            # Primeiro tenta obter do cache
            if name in self.profiles:
                profile = self.profiles[name]
                # Garante que a voz está correta
                if hasattr(self.story_chat, 'characters'):
                    char = self.story_chat.characters.get(name)
                    if char and char.voice_file:
                        profile.basic_info['voice_file'] = char.voice_file
                return profile
                
            # Depois tenta carregar do arquivo
            profile_path = os.path.join(self.profiles_dir, f"{name.lower()}.json")
            if os.path.exists(profile_path):
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
                        profile = CharacterProfile.from_dict(profile_data)
                        self.profiles[name] = profile
                        return profile
                except Exception as e:
                    LogManager.error(f"Erro ao carregar perfil do arquivo para {name}: {e}", "ProfileManager")

            # Se não encontrou, tenta obter do characters.json
            from dynamic_character_manager import DynamicCharacterManager
            char_manager = DynamicCharacterManager()
            char_info = char_manager.get_character_info(name)

            if not char_info or not char_info.get('profile'):
                LogManager.warning(f"Informações do personagem {name} não encontradas", "ProfileManager")
                return None

            # Cria perfil baseado nas informações existentes
            initial_profile = CharacterProfile(name)
            char_profile = char_info['profile']
                
            # Atualiza informações básicas
            initial_profile.basic_info.update({
                "occupation": char_profile.get('occupation', ''),
                "appearance": char_profile.get('appearance', ''),
                "voice_traits": char_profile.get('voice_traits', []),
                "voice_file": char_info.get('voice_file', '')  # Adiciona voz do character_manager
            })

            # Atualiza personalidade
            initial_profile.personality["traits"] = char_profile.get('personality', [])
                
            # Atualiza história
            initial_profile.background["history"] = char_profile.get('background', '')

            # Atualiza estado dinâmico se disponível
            if char_profile.get('current_emotions'):
                initial_profile.dynamic_state["current_emotions"] = char_profile['current_emotions']
            if char_profile.get('current_goals'):
                initial_profile.dynamic_state["current_goals"] = char_profile['current_goals']

            # Salva em cache e arquivo
            self.profiles[name] = initial_profile
            self.save_profile(initial_profile)
            
            # Faz backup do arquivo após salvar
            try:
                if os.path.exists(profile_path):
                    backup_path = f"{profile_path}.bak"
                    import shutil
                    shutil.copy2(profile_path, backup_path)
                    LogManager.debug(f"Backup criado para perfil de {name}", "ProfileManager")
            except Exception as e:
                LogManager.warning(f"Erro ao criar backup para {name}: {e}", "ProfileManager")

            LogManager.info(f"Perfil inicial criado para {name}", "ProfileManager")
            return initial_profile
                    
        except Exception as e:
            LogManager.error(f"Erro ao carregar/criar perfil de {name}: {e}", "ProfileManager")
            return None

    async def update_profile_with_context(self, name: str, story_context: 'StoryContext', llm_client) -> bool:
        """Atualiza o perfil do personagem baseado no contexto atual da história"""
        try:
            # Tenta obter perfil existente ou cria novo
            profile = self.get_or_create_profile(name)
            if not profile:
                # Se não existe perfil, tenta criar um novo
                profile = CharacterProfile(name)
                
                # Obtém informações do character_manager
                from dynamic_character_manager import DynamicCharacterManager
                char_manager = DynamicCharacterManager()
                char_info = char_manager.get_character_info(name)
                
                if char_info and char_info.get('profile'):
                    char_profile = char_info['profile']
                    # Atualiza informações básicas
                    profile.basic_info.update({
                        "occupation": char_profile.get('occupation', ''),
                        "appearance": char_profile.get('appearance', ''),
                        "voice_traits": char_profile.get('voice_traits', []),
                        "age": char_profile.get('age', ''),
                        "origin": char_profile.get('origin', '')
                    })
                    
                    # Atualiza personalidade
                    if isinstance(char_profile.get('personality'), list):
                        profile.personality["traits"] = char_profile['personality']
                    
                    # Atualiza história
                    profile.background["history"] = char_profile.get('background', '')
                    
                    # Salva o novo perfil
                    self.profiles[name] = profile
                    self.save_profile(profile)
                    LogManager.info(f"Novo perfil criado para {name}", "ProfileManager")
                    return True
                    
            return False
                
        except Exception as e:
            LogManager.error(f"Erro ao atualizar perfil: {e}", "ProfileManager")
            return False

    def get_profile_for_prompt(self, name: str, include_context: bool = False) -> str:
        """Retorna perfil formatado para uso em prompts da LLM"""
        if name not in self.profiles:
            return ""

        profile = self.profiles[name]
        base_profile = f"""Perfil de {profile.name}:

        Informações Básicas:
        - Ocupação: {profile.basic_info['occupation']}
        - Aparência: {profile.basic_info['appearance']}
        - Idade: {profile.basic_info['age']}
        - Origem: {profile.basic_info['origin']}

        Personalidade:
        - Traços: {', '.join(profile.personality['traits'])}
        - Valores: {', '.join(profile.personality['values'])}
        - Medos: {', '.join(profile.personality['fears'])}
        - Desejos: {', '.join(profile.personality['desires'])}

        História:
        {profile.background['history']}

        Estado Atual:
        - Emoções: {', '.join(profile.dynamic_state['current_emotions'])}
        - Objetivos: {', '.join(profile.dynamic_state['current_goals'])}
        - Desenvolvimento Recente: {', '.join(profile.dynamic_state['character_development'])}

        Habilidades Notáveis:
        {', '.join(profile.abilities['skills'])}"""

        if include_context:
            # Adiciona contexto adicional se solicitado
            context = f"""
            CONTEXTO VITAL DO PERSONAGEM (MANTENHA CONSISTÊNCIA ABSOLUTA):
            Estado atual: {', '.join(profile.dynamic_state['current_emotions'])}
            Objetivos: {', '.join(profile.dynamic_state['current_goals'])}
            """
            return base_profile + "\n" + context
            
        return base_profile