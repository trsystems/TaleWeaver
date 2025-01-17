import json
import os
from typing import Dict, Optional, List
from log_manager import LogManager
from event_manager import EventType, StoryEvent
from ui_utils import Colors

class DynamicCharacterManager:
    def __init__(self, llm_client=None, characters_file: str = "characters.json"):
        self.characters_file = characters_file
        self.characters = {}
        self.known_names = set()
        self.client = llm_client  # IMPORTANTE: Armazena o client
        self._load_characters()

        # Tenta carregar arquivo principal
        if os.path.exists(self.characters_file):
            try:
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    self.characters = json.load(f)
            except json.JSONDecodeError:
                # Tenta recuperar do backup
                backup_file = f"{self.characters_file}.bak"
                if os.path.exists(backup_file):
                    LogManager.info("Tentando recuperar do backup", "DynamicCharacterManager")
                    try:
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            self.characters = json.load(f)
                        # Restaura arquivo principal do backup
                        with open(self.characters_file, 'w', encoding='utf-8') as f:
                            json.dump(self.characters, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        LogManager.error(f"Erro ao recuperar backup: {e}", "DynamicCharacterManager")
                        self.characters = {}

        # Inicializa known_names
        self.known_names = set(self.characters.keys())

    def _load_characters(self) -> Dict:
        """Carrega personagens do arquivo JSON"""
        try:
            LogManager.debug("Tentando carregar personagens...", "DynamicCharacterManager")
            
            if os.path.exists(self.characters_file):
                try:
                    with open(self.characters_file, 'r', encoding='utf-8') as f:
                        characters = json.load(f)
                        LogManager.info(f"Carregados {len(characters)} personagens", "DynamicCharacterManager")
                        return characters
                        
                except json.JSONDecodeError as e:
                    LogManager.error(f"Arquivo characters.json corrompido: {e}", "DynamicCharacterManager")
                    
                    # Tenta recuperar backup
                    backup_file = f"{self.characters_file}.bak"
                    if os.path.exists(backup_file):
                        try:
                            LogManager.info("Tentando recuperar do backup...", "DynamicCharacterManager")
                            with open(backup_file, 'r', encoding='utf-8') as f:
                                characters = json.load(f)
                            
                            # Se backup válido, restaura
                            with open(self.characters_file, 'w', encoding='utf-8') as f:
                                json.dump(characters, f, indent=2, ensure_ascii=False)
                            
                            LogManager.info("Arquivo restaurado do backup com sucesso", "DynamicCharacterManager")
                            return characters
                            
                        except Exception as backup_error:
                            LogManager.error(f"Erro ao recuperar backup: {backup_error}", "DynamicCharacterManager")
                    
                    # Se não conseguiu recuperar, cria novo
                    empty_characters = {}
                    with open(self.characters_file, 'w', encoding='utf-8') as f:
                        json.dump(empty_characters, f, indent=2, ensure_ascii=False)
                    LogManager.info("Novo arquivo characters.json criado", "DynamicCharacterManager")
                    return empty_characters
                    
            else:
                # Arquivo não existe, cria novo
                empty_characters = {}
                os.makedirs(os.path.dirname(self.characters_file), exist_ok=True)
                with open(self.characters_file, 'w', encoding='utf-8') as f:
                    json.dump(empty_characters, f, indent=2, ensure_ascii=False)
                LogManager.info("Arquivo characters.json criado", "DynamicCharacterManager")
                return empty_characters

        except Exception as e:
            LogManager.error(f"Erro ao carregar personagens: {e}", "DynamicCharacterManager")
            return {}
            
    def save_characters(self):
        """Salva personagens no arquivo JSON"""
        try:
            # Garante que diretório existe
            directory = os.path.dirname(self.characters_file)
            if directory:  # Se há um diretório (não é apenas um arquivo no diretório atual)
                os.makedirs(directory, exist_ok=True)
                LogManager.debug(f"Garantindo que diretório {directory} existe", "DynamicCharacterManager")

            # Primeiro verifica se já existem personagens salvos
            existing_chars = {}
            if os.path.exists(self.characters_file):
                try:
                    with open(self.characters_file, 'r', encoding='utf-8') as f:
                        existing_chars = json.load(f)
                except json.JSONDecodeError:
                    LogManager.warning("Arquivo de personagens corrompido, criando backup", "DynamicCharacterManager")
                    if os.path.exists(f"{self.characters_file}.bak"):
                        with open(f"{self.characters_file}.bak", 'r', encoding='utf-8') as f:
                            existing_chars = json.load(f)

            # Mescla personagens existentes com novos
            merged_chars = {**existing_chars, **self.characters}

            # Salva no arquivo principal
            with open(self.characters_file, 'w', encoding='utf-8') as f:
                json.dump(merged_chars, f, indent=2, ensure_ascii=False)

            # Cria backup
            with open(f"{self.characters_file}.bak", 'w', encoding='utf-8') as f:
                json.dump(merged_chars, f, indent=2, ensure_ascii=False)

            LogManager.info("Personagens salvos com sucesso", "DynamicCharacterManager")
            return True

        except Exception as e:
            LogManager.error(f"Erro ao salvar personagens: {e}", "DynamicCharacterManager")
            return False

    async def add_favorite_character(self, name: str, data: Dict):
        """Adiciona um personagem favorito ao sistema"""
        try:
            self.characters[name] = {
                'voice_file': data.get('voice_file', ''),
                'system_prompt_file': f'prompts/{name.lower()}_prompt.txt',
                'color': '\u001b[37m',  # Cor padrão (branco)
                'profile': {
                    'appearance': data.get('appearance', ''),
                    'physical_traits': data.get('physical_traits', [])
                },
                'is_favorite': True
            }
            self.save_characters()
            LogManager.info(f"Personagem favorito {name} restaurado", "DynamicCharacterManager")
            return True
        except Exception as e:
            LogManager.error(f"Erro ao restaurar personagem favorito {name}: {e}", "DynamicCharacterManager")
            return False
        
    def is_player_character(self, name: str) -> bool:
        """Verifica se o personagem é o do jogador"""
        if name in self.characters:
            return self.characters[name].get('is_player', False)
        return False

    async def detect_new_characters(self, text: str, llm_client) -> List[str]:
        """Detecta menções a novos personagens no texto"""
        try:
            # Primeiro normaliza os nomes existentes
            existing_names = {self._normalize_name(name): name 
                            for name in self.characters.keys()}

            # Cria um prompt para a LLM identificar personagens
            prompt = f"""Analise o texto abaixo e identifique APENAS personagens CLARAMENTE definidos com:
            1. Nome próprio específico ou codinome único
            2. Título/cargo acompanhado de nome próprio
            3. Descrição detalhada que sugira um novo personagem importante
            
            Texto: {text}
            
            REGRAS ESTRITAS:
            - Ignore palavras genéricas como "homem", "mulher", "pessoa"
            - Ignore títulos sem nome próprio ("doutor", "general", etc) que não parecem ser novos personagens
            - Ignore pronomes e referências vagas
            - Considere apenas entidades claramente identificáveis como novos personagens
            - O personagem deve ter características ou contexto suficiente para ser único
            
            Retorne apenas nomes confirmados, um por linha. Se não houver personagens claros, retorne lista vazia."""
            
            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{
                    "role": "system", 
                    "content": "Você é um detector de personagens que segue regras estritas e evita falsos positivos."
                },
                {"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            # Processa a resposta inicial
            detected_names = [name.strip() for name in response.choices[0].message.content.split('\n') 
                    if name.strip()]

            # Lista para novos personagens únicos
            new_names = []
            
            for detected_name in detected_names:
                normalized_name = self._normalize_name(detected_name)
                
                # Verifica se já existe nome similar
                most_similar = self._find_most_similar_name(normalized_name, existing_names.keys())
                
                if most_similar:
                    LogManager.debug(f"Nome '{detected_name}' identificado como variação de '{existing_names[most_similar]}'", "EntityManager")
                    continue
                
                # Se não encontrou similar e não está nos personagens existentes
                if detected_name not in self.characters:
                    new_names.append(detected_name)
                    LogManager.debug(f"Potencial novo personagem '{detected_name}' detectado. Contexto: {text[:100]}...", "EntityManager")
            
            return new_names
            
        except Exception as e:
            LogManager.error(f"Erro ao detectar personagens: {e}", "EntityManager")
            return []

    def _normalize_name(self, name: str) -> str:
        """Normaliza um nome para comparação"""
        return ''.join(c.lower() for c in name if c.isalnum())

    def _find_most_similar_name(self, name: str, existing_names: List[str], threshold: float = 0.8) -> Optional[str]:
        """Encontra o nome mais similar na lista de nomes existentes"""
        from difflib import SequenceMatcher
        
        best_match = None
        best_ratio = 0
        
        for existing in existing_names:
            ratio = SequenceMatcher(None, name, existing).ratio()
            if ratio > threshold and ratio > best_ratio:
                best_ratio = ratio
                best_match = existing
                
        return best_match
    
    def _generate_character_color(self) -> str:
        """Gera uma cor única para o personagem"""
        available_colors = [
            Colors.PURPLE,
            Colors.CYAN,
            Colors.RED,
            Colors.GREEN,
            Colors.YELLOW
        ]
        # Escolhe uma cor que ainda não está em uso
        used_colors = set(char_config.get('color', '') 
                         for char_config in self.characters.values())
        unused_colors = [c for c in available_colors if c not in used_colors]
        
        if unused_colors:
            return unused_colors[0]
        return Colors.WHITE  # Cor padrão se todas estiverem em uso

    async def generate_character_profile(self, char_name: str, context: str, llm_client) -> Optional[dict]:
        """Gera um perfil detalhado para um personagem"""
        try:
            prompt = f"""IMPORTANTE: RESPONDA SEMPRE EM PORTUGUÊS DO BRASIL.
            Use linguagem natural, gírias e expressões brasileiras quando apropriado.

            Crie um perfil detalhado para o personagem {char_name} baseado no contexto fornecido.

            Contexto: {context}

            Retorne um objeto JSON EXATAMENTE neste formato:
            {{
                "name": "{char_name}",
                "occupation": "ocupação do personagem em português",
                "personality": ["traço1 em português", "traço2 em português", "traço3 em português"],
                "background": "história detalhada do personagem em português",
                "appearance": "descrição física detalhada em português",
                "voice_traits": ["característica1 em português", "característica2 em português", "característica3 em português"]
            }}

            REGRAS IMPORTANTES:
            1. TUDO deve estar em português do Brasil
            2. Use linguagem natural e fluida do português brasileiro
            3. Mantenha estrita consistência com o contexto
            4. Seja detalhado mas conciso
            5. Use apenas aspas duplas (")
            6. Retorne APENAS o JSON, nada mais
            7. Garanta que o JSON está completo e válido
            8. NÃO use aspas simples
            9. Inclua a chave de fechamento }}

            EXEMPLOS DE TRAÇOS EM PORTUGUÊS:
            - Personality: ["determinado", "astuto", "cauteloso"]
            - Voice_traits: ["voz grave", "tom autoritário", "fala pausadamente"]"""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um criador de perfis de personagem que retorna apenas JSON válido e SEMPRE responde em português do Brasil."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            response_text = response.choices[0].message.content.strip()
            # Remove qualquer texto antes ou depois do JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]
                
            try:
                profile = json.loads(response_text)
                LogManager.debug(f"Perfil gerado com sucesso para {char_name}", "CharacterManager")
                return profile
            except json.JSONDecodeError as e:
                LogManager.error(f"JSON inválido no perfil: {str(e)}\nTexto: {response_text}", "CharacterManager")
                
                # Tenta novamente com temperatura mais baixa
                return await self._retry_profile_generation(char_name, context, llm_client)

        except Exception as e:
            LogManager.error(f"Erro ao gerar perfil: {e}", "CharacterManager")
            return None
    
    async def _retry_profile_generation(self, char_name: str, context: str, llm_client, temperature: float = 0.5) -> Optional[dict]:
        """Tenta gerar o perfil novamente com temperatura mais baixa"""
        try:
            prompt = f"""IMPORTANTE: RESPONDA SEMPRE EM PORTUGUÊS DO BRASIL.
            
            Gere um perfil em português do Brasil para {char_name}.
            Contexto: {context}

            FORMATO EXATO REQUERIDO:
            {{
                "name": "{char_name}",
                "occupation": "ocupação em português",
                "personality": ["traço1", "traço2", "traço3"],
                "background": "história em português",
                "appearance": "aparência em português",
                "voice_traits": ["característica1", "característica2", "característica3"]
            }}

            REGRAS:
            - TUDO em português do Brasil
            - Use linguagem natural brasileira
            - Use apenas aspas duplas
            - Garanta JSON completo
            - Inclua todas as chaves
            - Termine com }}"""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": "Você é um gerador de JSON que cria apenas JSON válido em português do Brasil."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )

            response_text = response.choices[0].message.content.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                try:
                    profile = json.loads(response_text[json_start:json_end])
                    LogManager.info(f"Perfil gerado com sucesso na segunda tentativa para {char_name}", "CharacterManager")
                    return profile
                except json.JSONDecodeError as e:
                    LogManager.error(f"Falha na segunda tentativa: {e}", "CharacterManager")
                    return None

            return None

        except Exception as e:
            LogManager.error(f"Erro na segunda tentativa de gerar perfil: {e}", "CharacterManager")
            return None

    async def create_character_prompt(self, profile: Dict, llm_client) -> str:
        """Gera prompt do sistema para o personagem"""
        try:
            prompt = f"""Crie um prompt de sistema para o personagem com o seguinte perfil:
            
            {json.dumps(profile, indent=2)}
            
            O prompt deve:
            1. Definir claramente a personalidade e comportamento
            2. Estabelecer como o personagem se comunica
            3. Incluir suas motivações e objetivos
            4. Definir seu conhecimento do ambiente e outros personagens
            
            O texto deve ser escrito na segunda pessoa ("Você é...")"""
            
            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            LogManager.error(f"Erro ao gerar prompt: {e}", "DynamicCharacterManager")
            return None

    async def add_character(self, name: str, context: str, llm_client, voice_file: Optional[str] = None, profile: Optional[dict] = None) -> bool:
        """Adiciona um novo personagem ao sistema"""
        try:
            if name in self.characters:
                LogManager.warning(f"Personagem {name} já existe", "CharacterManager")
                return False

            # Se não recebeu perfil, gera um novo
            if not profile:
                profile = await self.generate_character_profile(name, context, llm_client)
                if not profile:
                    return False

            # Garante que o perfil tem todas as chaves necessárias
            required_keys = ["name", "occupation", "personality", "background", "appearance", "voice_traits"]
            if not all(key in profile for key in required_keys):
                LogManager.error(f"Perfil incompleto para {name}", "CharacterManager")
                return False

            # Define arquivo de voz e cor
            voice_file = voice_file or "voices/narrator_voice.wav"
            color = self._generate_character_color()

            # Cria entrada do personagem
            self.characters[name] = {
                'profile': profile,
                'voice_file': voice_file,
                'system_prompt_file': f"prompts/{name.lower()}_prompt.txt",
                'color': color
            }

            # Salva os personagens
            self.save_characters()
            LogManager.info(f"Personagem {name} adicionado com sucesso", "CharacterManager")
            return True

        except Exception as e:
            LogManager.error(f"Erro ao adicionar personagem {name}: {e}", "CharacterManager")
            return False

    def get_character_info(self, name: str) -> Optional[Dict]:
        """Retorna informações de um personagem"""
        try:
            # Primeiro tenta encontrar exatamente como fornecido
            if name in self.characters:
                return self.characters[name]
                
            # Tenta encontrar ignorando case
            name_lower = name.lower()
            for char_name, char_data in self.characters.items():
                if char_name.lower() == name_lower:
                    return char_data
                    
            # Verifica se é um nome alternativo/variação
            for char_name, char_data in self.characters.items():
                variations = char_data.get('profile', {}).get('variations', [])
                if any(var.lower() == name_lower for var in variations):
                    return char_data
                    
            return None
        
        except Exception as e:
            LogManager.error(f"Erro ao obter info do personagem {name}: {e}", "DynamicCharacterManager")
            return None

    def list_pending_characters(self) -> List[str]:
        """Lista personagens mencionados mas ainda não criados"""
        return list(self.known_names)

    def update_character_profile(self, name: str, new_info: Dict):
        """Atualiza informações de um personagem existente"""
        try:
            if name.lower() in self.characters:
                self.characters[name.lower()]['profile'].update(new_info)
                self.save_characters()
                return True
        except Exception as e:
            LogManager.error(f"Erro ao atualizar perfil: {e}", "DynamicCharacterManager")
        return False

    async def auto_create_character(self, char_name: str, context: str) -> bool:
        """Cria um novo personagem com perfil detalhado"""
        try:
            LogManager.debug(f"Iniciando criação automática de personagem: {char_name}", "DynamicCharacterManager")
            LogManager.debug(f"Contexto recebido: {context[:100]}...", "DynamicCharacterManager")

            # Verifica se já existe
            if char_name in self.characters:
                LogManager.debug(f"Personagem {char_name} já existe", "DynamicCharacterManager")
                return True

            # Valida nome do personagem
            if not self._validate_character_name(char_name):
                LogManager.error(f"Nome de personagem inválido: {char_name}", "DynamicCharacterManager")
                return False

            # Gera perfil
            profile = await self.generate_character_profile(char_name, context, self.client)
            if not profile:
                return False

            # Configura o personagem
            voice_file = "voices/narrator_voice.wav"
            character_color = self._generate_character_color()
            
            # Adiciona ao dicionário
            self.characters[char_name] = {
                'profile': profile,
                'voice_file': voice_file,
                'system_prompt_file': f"prompts/{char_name.lower()}_prompt.txt",
                'color': character_color,
                'is_favorite': False
            }

            # Salva no arquivo
            try:
                self.save_characters()
                LogManager.info(f"Personagem {char_name} adicionado com sucesso", "DynamicCharacterManager")
                return True
            except Exception as save_error:
                LogManager.error(f"Erro ao salvar personagem {char_name}: {save_error}", "DynamicCharacterManager")
                self.characters.pop(char_name, None)
                return False

        except Exception as e:
            LogManager.error(f"Erro ao criar personagem {char_name}: {e}", "DynamicCharacterManager")
            return False
    
    def _validate_profile(self, profile: dict) -> bool:
        """Valida se o perfil gerado tem todos os campos necessários e conteúdo adequado"""
        try:
            # Verifica campos obrigatórios
            required_fields = ['name', 'occupation', 'personality', 'background']
            if not all(field in profile for field in required_fields):
                return False
                
            # Valida conteúdo mínimo
            if len(profile['background']) < 50:  # Mínimo de 50 caracteres para background
                return False
                
            if not isinstance(profile['personality'], list) or len(profile['personality']) < 2:
                return False  # Mínimo de 2 traços de personalidade
                
            # Validações adicionais
            if not profile['occupation'].strip():
                return False
                
            return True
            
        except Exception as e:
            LogManager.error(f"Erro ao validar perfil: {e}", "DynamicCharacterManager")
            return False
        
    def check_client(self) -> bool:
        """Verifica se o client LLM está configurado corretamente"""
        if not self.client:
            LogManager.error("Cliente LLM não configurado", "DynamicCharacterManager")
            return False
        return True
        
    def _validate_character_name(self, name: str) -> bool:
        """Valida se o nome do personagem é adequado"""
        try:
            # Remove espaços extras
            name = name.strip()
            
            # Verifica comprimento
            if len(name) < 2 or len(name) > 50:
                LogManager.debug(f"Nome '{name}' tem comprimento inválido", "DynamicCharacterManager")
                return False
                
            # Verifica caracteres válidos (agora aceita mais caracteres)
            valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789áàâãéèêíïóôõöúçñÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ -.'")
            if not all(c in valid_chars for c in name):
                LogManager.debug(f"Nome '{name}' contém caracteres inválidos", "DynamicCharacterManager")
                return False
                
            # Verifica palavras genéricas
            generic_terms = ['homem', 'mulher', 'pessoa', 'alguém', 'ninguém']
            if name.lower() in generic_terms:
                LogManager.debug(f"Nome '{name}' é um termo genérico", "DynamicCharacterManager")
                return False
                
            return True
            
        except Exception as e:
            LogManager.error(f"Erro ao validar nome '{name}': {e}", "DynamicCharacterManager")
            return False