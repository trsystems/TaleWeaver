from typing import Dict, List, Tuple, Optional
from character_models import Character
import json
import os
from difflib import get_close_matches
from log_manager import LogManager

class EntityType:
    CHARACTER = "character"
    LOCATION = "location"

class EntityManager:
    def __init__(self, locations_file: str = "locations.json", story_chat=None):
        self.locations_file = locations_file
        self.story_chat = story_chat
        self.locations = self._load_locations()
        self.known_entities = {
            EntityType.CHARACTER: set(),
            EntityType.LOCATION: set()
        }
    
    def _load_locations(self) -> Dict:
        """Carrega locais registrados"""
        try:
            if not isinstance(self.locations_file, str):
                LogManager.error("Caminho de arquivo de locais inválido", "EntityManager")
                return {}
                
            if os.path.exists(self.locations_file):
                with open(self.locations_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            LogManager.error(f"Erro ao carregar locais: {e}", "EntityManager")
            return {}
            
    def save_locations(self):
        """Salva locais no arquivo"""
        try:
            with open(self.locations_file, 'w', encoding='utf-8') as f:
                json.dump(self.locations, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LogManager.error(f"Erro ao salvar locais: {e}", "EntityManager")

    async def analyze_text_for_entities(self, text: str, llm_client) -> Tuple[List[str], List[str]]:
        """Analisa texto em busca de personagens e lugares"""
        try:

            if not text or not isinstance(text, str):
                LogManager.warning("Texto inválido para análise de entidades", "EntityManager")
                return [], []

            text_lower = text.lower()

            # Extrai personagens e locais
            characters = []
            locations = []
            
            # Proteção contra story_chat ou characters não inicializados
            if hasattr(self, 'story_chat') and self.story_chat:
                if hasattr(self.story_chat, 'characters'):
                    for name, character in self.story_chat.characters.items():
                        if isinstance(character, Character):
                            # Acessa profile através do character_manager
                            char_info = self.story_chat.character_manager.get_character_info(name)
                            if char_info and 'profile' in char_info:
                                char_occupation = char_info['profile'].get('occupation', '').lower()
                                if char_occupation in text_lower:
                                    LogManager.debug(f"Referência à ocupação '{char_occupation}' encontrada - pertence a {name}", "EntityManager")
                                    text = text.replace(char_occupation, f"{name}'s role")

            prompt = f"""Analise o texto abaixo e extraia personagens e lugares importantes.

            Texto: {text}

            Regras de análise:
            1. Para PERSONAGENS:
            - Identifique nomes próprios específicos (ex: João Silva, Maria)
            - Ignore títulos genéricos sem nome próprio (ex: doutor, professor)
            - Inclua variações do nome se mencionadas
            - Indique se é um personagem novo ou já conhecido
            - NÃO inclua grupos ou coletivos de pessoas

            2. Para LUGARES:
            - Identifique nomes próprios de locais
            - Inclua locais nomeados mesmo se genéricos (ex: Bosque Negro)
            - Ignore locais sem nome próprio

            Retorne EXATAMENTE neste formato JSON:
            {{
                "characters": [
                    {{
                        "name": "Nome do Personagem",
                        "variations": ["variação1", "variação2"],
                        "is_new": true,
                        "context": "breve contexto sobre o personagem do texto"
                    }}
                ],
                "locations": [
                    {{
                        "name": "Nome do Local",
                        "context": "breve contexto do local"
                    }}
                ]
            }}"""

            LogManager.debug("Enviando prompt para análise de entidades", "EntityManager")
            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": "Você é um analisador de texto que extrai informações sobre personagens e lugares, retornando apenas JSON válido."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            response_text = response.choices[0].message.content.strip()
            # Garante que temos apenas o JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]
                
            result = json.loads(response_text)
            
            for char in result.get("characters", []):
                if char.get("name"):
                    characters.append(char["name"])
                    LogManager.debug(f"Personagem detectado: {char['name']}", "EntityManager")
            
            for loc in result.get("locations", []):
                if loc.get("name"):
                    locations.append(loc["name"])
                    LogManager.debug(f"Local detectado: {loc['name']}", "EntityManager")

            return characters, locations

        except json.JSONDecodeError as e:
            LogManager.error(f"Erro ao decodificar JSON: {e}", "EntityManager")
            return [], []
        except Exception as e:
            LogManager.error(f"Erro ao analisar entidades: {e}", "EntityManager")
            return [], []

    async def register_location(self, name: str, context: str, llm_client) -> bool:
        """Registra um novo local com informações detalhadas"""
        try:
            if name in self.locations:
                return True

            prompt = f"""Analise o local "{name}" no contexto fornecido e crie uma descrição detalhada.

            Contexto: {context}

            Retorne um JSON no seguinte formato:
            {{
                "type": "tipo do local (ex: mansão, taverna, cidade)",
                "description": "descrição detalhada do local",
                "notable_features": ["característica1", "característica2"]
            }}"""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {"role": "system", "content": "Você é um criador de ambientes que retorna apenas JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            try:
                response_text = response.choices[0].message.content.strip()
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    response_text = response_text[json_start:json_end]
                
                location_info = json.loads(response_text)
                self.locations[name] = location_info
                self.known_entities[EntityType.LOCATION].add(name)

                # Salva no arquivo
                try:
                    with open(self.locations_file, 'w', encoding='utf-8') as f:
                        json.dump(self.locations, f, indent=2, ensure_ascii=False)
                    LogManager.info(f"Local {name} registrado com sucesso", "EntityManager")
                    return True
                except Exception as save_error:
                    LogManager.error(f"Erro ao salvar locais: {save_error}", "EntityManager")
                    return False

            except json.JSONDecodeError as e:
                LogManager.error(f"Erro ao decodificar JSON da resposta: {e}", "EntityManager")
                return False

        except Exception as e:
            LogManager.error(f"Erro ao registrar local: {e}", "EntityManager")
            return False

    def find_similar_location(self, name: str) -> Optional[str]:
        """Encontra local com nome similar"""
        matches = get_close_matches(name.lower(), 
                                  [loc.lower() for loc in self.locations.keys()], 
                                  n=1, cutoff=0.8)
        if matches:
            # Retorna o nome original (preserva capitalização)
            return next(k for k in self.locations.keys() 
                       if k.lower() == matches[0])
        return None

    async def _check_if_same_location(self, name1: str, name2: str, 
                                    context: str, llm_client) -> bool:
        """Verifica se dois nomes se referem ao mesmo local"""
        try:
            prompt = f"""Determine se estes dois nomes se referem ao mesmo local:

            Nome 1: {name1}
            Nome 2: {name2}
            
            Contexto: {context}
            
            Detalhes do local registrado:
            {json.dumps(self.locations[name2], indent=2)}

            Responda apenas "sim" ou "não"."""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            return response.choices[0].message.content.strip().lower() == "sim"
            
        except Exception as e:
            LogManager.error(f"Erro ao verificar locais: {e}", "EntityManager")
            return False

    async def _generate_location_info(self, name: str, context: str, llm_client) -> Dict:
        """Gera ou atualiza informações de um local"""
        try:
            # Se local já existe, inclui informações atuais no prompt
            current_info = self.locations.get(name, {})
            
            prompt = f"""Analise o contexto e gere/atualize informações sobre o local {name}.
            
            Contexto atual: {context}
            
            Informações existentes: {json.dumps(current_info, indent=2) if current_info else "Nenhuma"}
            
            Gere um objeto JSON com estas propriedades (mantendo informações existentes quando apropriado):
            {{
                "name": "nome do local",
                "type": "tipo do local (cidade, reino, taverna, etc)",
                "description": "descrição física e atmosfera",
                "notable_features": ["característica1", "característica2"],
                "typical_occupants": ["tipo de pessoas encontradas aqui"],
                "associated_characters": ["personagens mencionados aqui"],
                "importance": "relevância para a história (alta/média/baixa)"
            }}"""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            LogManager.error(f"Erro ao gerar info do local: {e}", "EntityManager")
            return {}

    async def analyze_history(self, story_events: List[Dict], characters_list: List[str], llm_client) -> Dict[str, List[str]]:
        """Analisa histórico em busca de entidades não registradas"""
        try:
            LogManager.debug("Iniciando análise de histórico...", "EntityManager")
            
            # Concatena eventos em chunks gerenciáveis
            chunks = []
            current_chunk = []
            current_size = 0
            chunk_size = 2000  # tokens aproximados
            
            for event in story_events:
                event_text = f"{event['type']}: {event['content']}"
                event_size = len(event_text) // 4
                
                if current_size + event_size > chunk_size:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [event_text]
                    current_size = event_size
                else:
                    current_chunk.append(event_text)
                    current_size += event_size
            
            if current_chunk:
                chunks.append("\n".join(current_chunk))

            # Processa chunks
            all_characters = set()
            all_locations = set()
            
            for chunk in chunks:
                try:
                    chars, locs = await self.analyze_text_for_entities(chunk, llm_client)
                    all_characters.update(chars)
                    all_locations.update(locs)
                except Exception as e:
                    LogManager.error(f"Erro ao analisar chunk: {e}", "EntityManager")
                    continue

            # Filtra personagens já existentes, incluindo o jogador e os já registrados
            existing_characters = set(characters_list)
            
            # Adiciona o jogador à lista de existentes se existir
            if hasattr(self.story_chat, 'player') and self.story_chat.player:
                existing_characters.add(self.story_chat.player.background.name)

            # Adiciona personagens já conhecidos
            existing_characters.update(self.known_entities[EntityType.CHARACTER])
            
            # Filtra apenas personagens realmente novos
            new_characters = [c for c in all_characters 
                            if c not in existing_characters and 
                            not any(c.lower() == x.lower() for x in existing_characters)]
            
            # Filtra lugares não registrados
            new_locations = [l for l in all_locations if l not in self.locations]
            
            return {
                "characters": new_characters,
                "locations": new_locations
            }
                    
        except Exception as e:
            LogManager.error(f"Erro ao analisar histórico: {e}", "EntityManager")
            return {"characters": [], "locations": []}