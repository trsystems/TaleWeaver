import re
import sqlite3
import aiosqlite
import traceback
from dataclasses import dataclass, field
import json
from typing import List, Dict, Set, Optional
from datetime import datetime
from log_manager import LogManager
from memory_manager import MemoryManager
from ui_utils import Colors

@dataclass
class StoryContext:
    """Mantém o contexto atual da história"""
    scene_description: str = ""
    current_location: str = "Indefinido"
    current_mood: str = "Neutro"
    time_of_day: str = "Indefinido"
    present_characters: List[str] = field(default_factory=list)
    last_action: str = ""
    story_events: List[Dict[str, str]] = field(default_factory=list)
    story_theme: str = "" # Campo para o tema
    story_genre: str = "" # Campo para o gênero
    db_path: str = "story_history.db"
    memory_db_path: str = "character_memories.db"
    story_elements: Set[str] = field(default_factory=set)  # Usando typing.Set

    def __init__(self, llm_client=None, **kwargs):
        """Inicializa StoryContext com cliente LLM opcional"""
        try:
            LogManager.debug("Iniciando inicialização do StoryContext", "StoryContext")
            
            # Inicialização explícita dos atributos
            self.scene_description = ""
            self.current_location = "Indefinido"
            self.current_mood = "Neutro"
            self.time_of_day = "Indefinido"
            self.present_characters = []
            self.last_action = ""
            self.story_events = []
            self.story_theme = ""
            self.story_genre = ""
            self.story_elements = set()
            self.client = llm_client
            
            # Configura caminhos de banco de dados
            self.db_path = kwargs.get('db_path', "story_history.db")
            self.memory_db_path = kwargs.get('memory_db_path', "character_memories.db")
            
            # Inicializa o banco de dados
            self.setup_database()
            
            # Carrega eventos existentes
            self.load_events()
            
            LogManager.info("StoryContext inicializado com sucesso", "StoryContext")
            
        except Exception as e:
            LogManager.error(f"Erro na inicialização do StoryContext: {e}", "StoryContext")
            raise

    def __post_init__(self):
        """Inicialização após criação da instância"""
        LogManager.debug("Iniciando post_init do StoryContext", "StoryContext")
        self.setup_database()
        self.load_events()
        if not hasattr(self, 'memory_manager'):
            self.memory_manager = MemoryManager(self.memory_db_path)
        LogManager.debug("StoryContext inicializado com sucesso", "StoryContext")
        
    async def setup_database(self):
        """Configura o banco de dados para armazenar eventos da história"""
        try:
            LogManager.debug(f"Iniciando configuração do banco de dados: {self.db_path}", "StoryContext")
            
            async with aiosqlite.connect(self.db_path) as db:
                # Cria tabela story_events
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS story_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        character TEXT,
                        timestamp TEXT NOT NULL,
                        location TEXT,
                        time_of_day TEXT,
                        mood TEXT,
                        elements TEXT
                    )
                """)
                
                # Cria tabela story_settings
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS story_settings (
                        id INTEGER PRIMARY KEY,
                        theme TEXT,
                        genre TEXT,
                        current_location TEXT,
                        current_time TEXT,
                        current_mood TEXT,
                        present_characters TEXT,
                        created_at TEXT,
                        last_updated TEXT
                    )
                """)
                
                await db.commit()
                
                # Verifica se as tabelas foram criadas
                async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                    tables = [table[0] async for table in cursor]
                    
                LogManager.debug(f"Tabelas existentes: {tables}", "StoryContext")
                
                if 'story_events' not in tables or 'story_settings' not in tables:
                    raise Exception("Falha ao criar tabelas necessárias")
                
                LogManager.info("Banco de dados configurado com sucesso", "StoryContext")
                
        except Exception as e:
            LogManager.error(f"Erro na configuração do banco de dados: {e}", "StoryContext")
            raise

    def load_events(self):
        """Carrega eventos salvos e configurações do banco de dados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Carrega eventos
                cursor = conn.execute("""
                    SELECT event_type, content, character, timestamp, 
                        location, time_of_day, mood, elements
                    FROM story_events 
                    ORDER BY timestamp
                """)
                self.story_events = [
                    {
                        'type': row[0],
                        'content': row[1],
                        'character': row[2],
                        'timestamp': row[3],
                        'location': row[4],
                        'time_of_day': row[5],
                        'mood': row[6],
                        'elements': json.loads(row[7]) if row[7] else {}
                    }
                    for row in cursor.fetchall()
                ]
                
                # Carrega configurações da história
                cursor = conn.execute("""
                    SELECT theme, genre, current_location, current_time, 
                        current_mood, present_characters
                    FROM story_settings
                    WHERE id = 1
                """)
                settings = cursor.fetchone()
                
                if settings:
                    self.story_theme = settings[0]
                    self.story_genre = settings[1]
                    self.current_location = settings[2] or "Indefinido"
                    self.time_of_day = settings[3] or "Indefinido"
                    self.current_mood = settings[4] or "Neutro"
                    try:
                        self.present_characters = json.loads(settings[5]) if settings[5] else []
                    except json.JSONDecodeError:
                        self.present_characters = []
                else:
                    # Se não houver configurações, usa o último evento
                    if self.story_events:
                        last_event = self.story_events[-1]
                        self.current_location = last_event.get('location', self.current_location)
                        self.time_of_day = last_event.get('time_of_day', self.time_of_day)
                        self.current_mood = last_event.get('mood', self.current_mood)
                        
                # Registra o carregamento
                events_count = len(self.story_events)
                LogManager.debug(f"Carregados {events_count} eventos", "StoryContext")
                LogManager.debug(f"Estado atual: Local={self.current_location}, Hora={self.time_of_day}, Humor={self.current_mood}", "StoryContext")
                
                return events_count > 0
                
        except Exception as e:
            LogManager.error(f"Erro ao carregar eventos: {e}", "StoryContext")
            # Garante valores padrão em caso de erro
            self.current_location = "Indefinido"
            self.time_of_day = "Indefinido"
            self.current_mood = "Neutro"
            self.present_characters = []
            return False

    def add_event(self, event_type: str, content: str, character: str):
        """Adiciona um novo evento e atualiza elementos se for narração"""
        try:
            LogManager.debug(f"Iniciando adição de evento: {event_type}", "StoryContext")
            LogManager.debug(f"Personagem: {character}", "StoryContext")
            LogManager.debug(f"Conteúdo: {content[:100]}...", "StoryContext")
            
            # Verifica se tabela existe antes de tentar inserir
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='story_events'
                """)
                
                if cursor.fetchone() is None:
                    LogManager.debug("Tabela story_events não encontrada. Recriando banco...", "StoryContext")
                    self.setup_database()
            
            timestamp = datetime.now().isoformat()
            
            # Se for narração, extrai e processa elementos
            elements_str = '[]'
            if event_type == 'narration':
                if not hasattr(self, 'story_elements'):
                    LogManager.debug("Inicializando story_elements", "StoryContext")
                    self.story_elements = set()
                
                self._extract_story_elements(content)
                elements_str = json.dumps(list(self.story_elements))
                LogManager.debug(f"Elementos extraídos: {elements_str}", "StoryContext")

            # Cria evento para memória local
            event = {
                'type': event_type,
                'content': content,
                'character': character,
                'timestamp': timestamp,
                'location': self.current_location,
                'time_of_day': self.time_of_day,
                'mood': self.current_mood,
                'elements': elements_str
            }

            # Adiciona à lista em memória
            if not hasattr(self, 'story_events'):
                LogManager.debug("Inicializando story_events", "StoryContext")
                self.story_events = []
                
            self.story_events.append(event)
            LogManager.debug(f"Evento adicionado à memória. Total de eventos: {len(self.story_events)}", "StoryContext")

            # Salva no banco de dados
            try:
                with sqlite3.connect(self.db_path) as conn:
                    LogManager.debug("Salvando evento no banco de dados", "StoryContext")
                    
                    conn.execute("""
                        INSERT INTO story_events 
                        (event_type, content, character, timestamp, location, 
                        time_of_day, mood, elements)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_type,
                        content,
                        character,
                        timestamp,
                        self.current_location,
                        self.time_of_day,
                        self.current_mood,
                        elements_str
                    ))
                    
                    # Atualiza configurações da história
                    present_chars_str = json.dumps(self.present_characters)
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO story_settings
                        (id, theme, genre, current_location, current_time, 
                        current_mood, present_characters, last_updated)
                        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.story_theme or '',
                        self.story_genre or '',
                        self.current_location,
                        self.time_of_day,
                        self.current_mood,
                        present_chars_str,
                        timestamp
                    ))
                    
                    conn.commit()
                    LogManager.info(f"Evento {event_type} salvo com sucesso no banco", "StoryContext")
                    
            except sqlite3.Error as e:
                LogManager.error(f"Erro SQLite ao salvar evento: {e}", "StoryContext")
                LogManager.error(f"Stack trace: {traceback.format_exc()}", "StoryContext")
                LogManager.error(f"Valores que falharam: {event}", "StoryContext")
                raise
                
            LogManager.debug("Evento adicionado com sucesso", "StoryContext")
            
        except Exception as e:
            LogManager.error(f"Erro ao adicionar evento: {e}", "StoryContext")
            LogManager.error(f"Stack trace: {traceback.format_exc()}", "StoryContext")
            raise

    async def remove_last_event(self):
        """Remove o último evento do histórico"""
        try:
            if self.story_events:
                event = self.story_events.pop()
                await self._delete_event_from_db(event)
                self._update_context_from_events()
                return True
        except Exception as e:
            LogManager.error(f"Erro ao remover último evento: {e}", "StoryContext")
            return False

    async def remove_event(self, index: int):
        """Remove um evento específico pelo índice"""
        try:
            if 0 <= index < len(self.story_events):
                event = self.story_events.pop(index)
                await self._delete_event_from_db(event)
                self._update_context_from_events()
                return True
        except Exception as e:
            LogManager.error(f"Erro ao remover evento: {e}", "StoryContext")
            return False

    async def _delete_event_from_db(self, event: dict):
        """Remove evento do banco de dados"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM story_events
                    WHERE timestamp = ? AND event_type = ? AND content = ?
                """, (event['timestamp'], event['type'], event['content']))
        except Exception as e:
            LogManager.error(f"Erro ao deletar evento do DB: {e}", "StoryContext")

    def _update_context_from_events(self):
        """Atualiza o contexto atual baseado nos eventos restantes"""
        if not self.story_events:
            self.current_location = "Indefinido"
            self.time_of_day = "Indefinido"
            self.current_mood = "Neutro"
            self.scene_description = ""
            return

        # Pega o último evento de narração
        last_narration = next(
            (event for event in reversed(self.story_events) 
             if event['type'] == 'narration'),
            None
        )

        if last_narration:
            self._update_context_from_narration(last_narration['content'])

    def _update_context_from_narration(self, content: str):
        """Atualiza o contexto baseado no conteúdo das conversas e narrações."""
        content_lower = content.lower()
        
        # Detecta locais
        locations = {
            'casa': ['casa', 'apartamento', 'moradia', 'residência', 'quarto', 'sala', 'cozinha'],
            'trabalho': ['escritório', 'empresa', 'trabalho', 'firma'],
            'rua': ['rua', 'avenida', 'calçada', 'praça', 'parque'],
            'restaurante': ['restaurante', 'café', 'bar', 'lanchonete'],
            'telefone': ['telefone', 'ligação', 'chamada']
        }
        
        for location, indicators in locations.items():
            if any(indicator in content_lower for indicator in indicators):
                self.current_location = location
                break
        
        # Detecta período do dia
        time_indicators = {
            'manhã': ['manhã', 'amanhecer', 'café da manhã', 'nascer do sol'],
            'tarde': ['tarde', 'almoço', 'entardecer', 'pôr do sol'],
            'noite': ['noite', 'anoitecer', 'jantar', 'escuro', 'lua']
        }
        
        for time, indicators in time_indicators.items():
            if any(indicator in content_lower for indicator in indicators):
                self.time_of_day = time
                break
        
        # Se não houver indicação explícita de tempo, tenta inferir
        if not self.time_of_day:
            # Palavras que sugerem horários
            if any(word in content_lower for word in ['trabalho', 'empresa', 'reunião']):
                self.time_of_day = 'tarde'  # Assume horário comercial
            elif any(word in content_lower for word in ['dormir', 'cama', 'descansar']):
                self.time_of_day = 'noite'
        
        # Detecta humor/atmosfera
        mood_indicators = {
            'tenso': ['tenso', 'nervoso', 'apreensivo', 'preocupante', 'ansioso', 'medo'],
            'alegre': ['alegre', 'festivo', 'animado', 'descontraído', 'feliz', 'risos'],
            'romântico': ['romântico', 'íntimo', 'amoroso', 'carinhoso'],
            'triste': ['triste', 'melancólico', 'depressivo', 'choroso', 'solitário'],
            'calmo': ['calmo', 'tranquilo', 'sereno', 'pacífico', 'silencioso']
        }
        
        for mood, indicators in mood_indicators.items():
            if any(indicator in content_lower for indicator in indicators):
                self.current_mood = mood
                break
                
        # Determina personagens presentes pela menção nos diálogos
        if hasattr(self, 'characters'):
            characters = getattr(self, 'characters', [])
            for char in characters:
                if char.lower() in content_lower:
                    if char not in self.present_characters:
                        self.present_characters.append(char)

    def get_recent_events_summary(self) -> str:
        """Retorna um resumo formatado dos eventos recentes"""
        try:
            recent_events = self.story_events[-5:] if self.story_events else []  # Adiciona verificação
            summary = []
            
            for event in recent_events:
                if event['type'] == 'narration':
                    summary.append(f"Narração: {event['content']}")
                elif event['type'] == 'dialogue':
                    summary.append(f"Diálogo - {event['character']}: {event['content']}")
                elif event['type'] == 'user_input':
                    summary.append(f"Ação do jogador: {event['content']}")
                    
            return "\n".join(summary) if summary else "História ainda não começou."
            
        except Exception as e:
            LogManager.error(f"Erro ao gerar resumo de eventos: {e}", "StoryContext")
            return "Erro ao recuperar eventos recentes."
    
    def _extract_story_elements(self, text: str):
        """Extrai elementos importantes do texto"""
        # Lista de palavras-chave para elementos importantes
        key_elements = [
            "porta", "janela", "arma", "luz", "sombra", "chave", 
            "telefone", "livro", "carta", "documento", "foto", 
            "computador", "celular", "carro", "faca", "sangue",
            "porta", "escada", "corredor"
        ]

        text_lower = text.lower()
        for element in key_elements:
            if element in text_lower:
                self.story_elements.add(element)

    def update_scene_description(self, text: str):
        """Atualiza a descrição da cena e extrai elementos"""
        self.scene_description = text
        self._extract_story_elements(text)
    
    async def generate_narrative_summary(self, llm_client) -> str:
        """Gera um resumo narrativo detalhado baseado nos eventos recentes."""
        try:
            if not hasattr(self, 'story_events') or not self.story_events:
                return "A história ainda não começou..."

            events = self.story_events[-10:]  # Últimos 10 eventos
            events_text = "\n".join([
                f"- {'Narrador' if e['type'] == 'narration' else e['character']}: {e['content']}"
                for e in events
            ])

            prompt = f"""Baseado nos eventos abaixo, crie um resumo coeso da história em formato narrativo:

            Gênero: {self.story_genre}
            Tema: {self.story_theme}

            Eventos:
            {events_text}

            INSTRUÇÕES:
            1. Mantenha um tom narrativo fluido
            2. Foque nos eventos mais importantes
            3. Destaque as mudanças significativas
            4. Mantenha o resumo em 3-4 parágrafos
            5. Inclua apenas informações confirmadas nos eventos

            RETORNE APENAS O RESUMO NARRATIVO."""

            response = llm_client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um narrador que cria resumos coesos e envolventes."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            LogManager.error(f"Erro ao gerar resumo narrativo: {e}", "StoryContext")
            return "Não foi possível gerar o resumo da história."
        
    def _format_multiline_text(self, text: str, width: int) -> str:
        """Formata texto em múltiplas linhas com alinhamento correto"""
        if not text:
            return "║     Informação não disponível"
            
        # Quebra o texto em palavras
        words = text.split()
        lines = []
        current_line = []
        current_width = 0
        
        for word in words:
            word_width = len(word)
            if current_width + word_width + 1 <= width:
                current_line.append(word)
                current_width += word_width + 1
            else:
                # Garante espaçamento consistente
                lines.append("║     " + " ".join(current_line))
                current_line = [word]
                current_width = word_width + 1
                
        if current_line:
            lines.append("║     " + " ".join(current_line))
        
        return "\n".join(lines)

    def _format_list_items(self, items: list) -> str:
        """Formata itens de lista com bullets e alinhamento correto"""
        if not items:
            return "║     Informação não disponível"
            
        return "\n".join(f"║     • {item}" for item in items)

    def _extract_time_from_story(self, story: str) -> str:
        """Extrai período do dia da história"""
        story_lower = story.lower()
        
        time_indicators = {
            "noite": ["noite", "escuro", "escuridão", "lua", "estrelas", "anoitecer"],
            "tarde": ["tarde", "pôr do sol", "entardecer", "poente"],
            "manhã": ["manhã", "amanhecer", "aurora", "alvorada"],
            "dia": ["dia", "sol", "meio-dia", "solar"]
        }
        
        for period, indicators in time_indicators.items():
            if any(indicator in story_lower for indicator in indicators):
                return period
                
        return "Indefinido"

    def _extract_mood_from_story(self, story: str) -> str:
        """Extrai atmosfera/humor da história"""
        story_lower = story.lower()
        
        mood_indicators = {
            "tenso": ["tenso", "medo", "perigo", "ansiedade", "apreensivo"],
            "misterioso": ["misterioso", "segredo", "enigma", "descoberta", "oculto"],
            "sombrio": ["sombrio", "escuro", "sinistr", "ameaça", "tenebroso"],
            "aventureiro": ["aventura", "exploração", "descoberta", "desafio"],
            "melancólico": ["triste", "melancolia", "solidão", "pesar"]
        }
        
        # Conta ocorrências de cada humor
        mood_counts = {mood: sum(1 for indicator in indicators if indicator in story_lower)
                    for mood, indicators in mood_indicators.items()}
        
        # Retorna o humor mais frequente, ou "Neutro" se nenhum for encontrado
        max_mood = max(mood_counts.items(), key=lambda x: x[1])
        return max_mood[0] if max_mood[1] > 0 else "Neutro"

    async def _parse_story_options(self, text: str) -> dict:
        """Parse e formata as histórias da resposta da LLM"""
        try:
            LogManager.debug("Processando histórias da LLM", "StoryContext")
            stories = {}
            
            # Tenta decodificar o JSON
            try:
                data = json.loads(text)
                
                # Identifica o formato e extrai histórias
                story_list = None
                if isinstance(data, list):  # Formato [{"id": 1, "title": "..."}]
                    story_list = data
                elif isinstance(data, dict):
                    # Procura por diferentes chaves possíveis
                    for key in ['historias', 'inicioss', 'stories', 'inicials']:
                        if key in data:
                            story_list = data[key]
                            break
                
                if story_list:
                    for idx, story in enumerate(story_list, 1):
                        # Mapeia diferentes nomes de campos possíveis
                        title = story.get('title') or story.get('titulo') or story.get('nome')
                        content = (story.get('description') or story.get('descricao') or 
                                story.get('text') or story.get('escena'))
                        
                        if title and content:
                            formatted_story = self._process_story_content({
                                'title': title,
                                'content': content
                            })
                            stories[str(idx)] = self._format_story_output(formatted_story)
            
            except json.JSONDecodeError:
                # Se não for JSON válido, tenta processar como texto
                LogManager.debug("Texto não é JSON, processando como texto estruturado", "StoryContext")
                story_count = 0
                current_title = None
                current_content = []
                
                lines = text.splitlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Detecta início de nova história
                    if re.match(r'^(\d+\.|\*\*|História \d+:|Cena \d+:)', line):
                        # Salva história anterior se existir
                        if current_title and current_content:
                            story_count += 1
                            formatted_story = self._process_story_content({
                                'title': current_title,
                                'content': ' '.join(current_content)
                            })
                            stories[str(story_count)] = self._format_story_output(formatted_story)
                        
                        # Extrai novo título
                        current_title = re.sub(r'^(\d+\.|\*\*|História \d+:|Cena \d+:)\s*', '', line)
                        current_content = []
                    else:
                        if current_title:  # Se já temos um título, adiciona à história atual
                            current_content.append(line)
                
                # Processa última história
                if current_title and current_content:
                    story_count += 1
                    formatted_story = self._process_story_content({
                        'title': current_title,
                        'content': ' '.join(current_content)
                    })
                    stories[str(story_count)] = self._format_story_output(formatted_story)
            
            # Validação final
            if not stories:
                raise ValueError("Nenhuma história extraída do texto")
            
            LogManager.info(f"Extraídas {len(stories)} histórias com sucesso", "StoryContext")
            return stories
            
        except Exception as e:
            LogManager.error(f"Erro ao processar histórias: {e}", "StoryContext")
            LogManager.debug(f"Texto que causou erro: {text[:200]}...", "StoryContext")
            return {}
        
    def _format_story_output(self, story: dict) -> str:
        """Formata uma história para exibição"""
        # Extrai elementos da história
        title = story.get('title', 'Nova História').strip()
        content = story.get('content', '').strip()
        
        # Extrai informações adicionais
        characters = self._extract_characters_from_text(content)
        setting = self._extract_setting_from_text(content)
        elements = self._extract_unique_elements(content)
        
        return f"""╔═════════════════════════════════════════════════════
    ║ {Colors.BOLD}{title}{Colors.RESET}
    ╠═════════════════════════════════════════════════════
    ║ 
    ║ {Colors.CYAN}Sinopse:{Colors.RESET}
    {self._format_multiline_text(content, 70)}
    ║ 
    ║ {Colors.CYAN}Personagens Principais:{Colors.RESET}
    {self._format_list_items(characters)}
    ║ 
    ║ {Colors.CYAN}Cenário:{Colors.RESET}
    {self._format_multiline_text(setting, 70)}
    ║ 
    ║ {Colors.CYAN}Elementos Únicos:{Colors.RESET}
    {self._format_multiline_text(elements, 70)}
    ║
    ╚═════════════════════════════════════════════════════"""
        
    def _fix_json_format(self, text: str) -> str:
        """Corrige problemas comuns de formatação JSON"""
        try:
            # Log do texto original para debug
            LogManager.debug(f"Texto original para formatação: {text[:200]}...", "StoryContext")
            
            # Remove tags assistente e espaços extras
            text = re.sub(r'assistant<\|end_header_id\|>', '', text.strip())
            
            # Verifica se o texto está em formato numerado (e.g., "1)", "2)", etc.)
            numbered_pattern = r'^\d+\)\s*".*'
            if re.match(numbered_pattern, text):
                stories = []
                # Separa por números
                parts = re.split(r'\d+\)\s*', text)
                # Remove partes vazias e processa cada história
                for part in parts:
                    if part.strip():
                        # Remove aspas extras e formata
                        clean_part = part.strip().strip('"\'')
                        if clean_part:
                            # Cria objeto JSON para cada história
                            story = {
                                "title": clean_part.split('.')[0] if '.' in clean_part else "História sem título",
                                "summary": clean_part
                            }
                            stories.append(story)
                # Converte lista de histórias para JSON
                text = json.dumps({"historias": stories})

            # Tenta carregar como JSON
            try:
                json.loads(text)
                return text
            except json.JSONDecodeError:
                # Se não for JSON válido, tenta encontrar e corrigir problemas comuns
                text = text.replace('"', '"').replace('"', '"').replace("'", '"')
                text = re.sub(r',\s*([}\]])', r'\1', text)
                text = re.sub(r'([{\[]\s*),', r'\1', text)
                
                # Tenta novamente com o JSON corrigido
                try:
                    json.loads(text)
                    return text
                except json.JSONDecodeError:
                    # Se ainda falhar, envolve em estrutura de histórias
                    if not text.startswith('{'):
                        if not text.startswith('['):
                            text = f'[{text}]'
                        text = f'{{"historias": {text}}}'
                    return text
                        
        except Exception as e:
            LogManager.error(f"Erro ao corrigir formato JSON: {e}", "StoryContext")
            LogManager.error(f"Texto que causou erro: {text[:200]}...", "StoryContext")
            # Tenta converter para formato de histórias como último recurso
            try:
                story = {
                    "historias": [{
                        "title": "Nova História",
                        "summary": text.strip().strip('"\'')
                    }]
                }
                return json.dumps(story)
            except:
                raise

    def _extract_story_data(self, text: str) -> List[dict]:
        """Extrai dados das histórias do texto, seja JSON ou markdown"""
        try:
            LogManager.debug(f"Iniciando extração de dados da história", "StoryContext")
            LogManager.debug(f"Texto recebido: {text[:200]}...", "StoryContext")

            processed_stories = []

            # Primeiro tenta processar como JSON
            try:
                data = json.loads(text)
                LogManager.debug("Texto processado como JSON", "StoryContext")
                
                # Identifica a lista de histórias
                stories = []
                if isinstance(data, dict):
                    if 'historias' in data:
                        stories = data['historias']
                    elif 'histórias' in data:
                        stories = data['histórias']
                    elif 'iniciosDeHistoria' in data:
                        stories = data['iniciosDeHistoria']
                    else:
                        stories = [data]
                elif isinstance(data, list):
                    stories = data

                # Processa cada história do JSON
                for story in stories:
                    title = (story.get('title') or story.get('titulo') or 
                            story.get('título') or story.get('nome', ''))
                    summary = (story.get('summary') or story.get('resumo') or
                            story.get('início') or story.get('content') or
                            story.get('conteúdo') or story.get('cenário', ''))
                    
                    # Se não encontrou em campos padrão, procura em outros
                    if not summary:
                        for key, value in story.items():
                            if isinstance(value, str) and len(value) > 50:
                                summary = value
                                break
                    
                    if summary:  # Só processa se tiver conteúdo
                        processed_story = self._process_story_content(title, summary)
                        if processed_story:
                            processed_stories.append(processed_story)

            except json.JSONDecodeError:
                LogManager.debug("Texto não é JSON, processando como markdown", "StoryContext")
                # Processa texto com formato markdown
                stories = []
                current_story = {}
                lines = text.splitlines()
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Detecta título de nova história
                    if line.startswith('**') or re.match(r'^\d+\.', line):
                        if current_story:
                            processed_story = self._process_story_content(
                                current_story.get('title', ''),
                                current_story.get('summary', '')
                            )
                            if processed_story:
                                processed_stories.append(processed_story)
                        
                        current_story = {'title': '', 'summary': ''}
                        # Remove marcadores e extrai título
                        clean_line = line.replace('**', '').strip()
                        if '. ' in clean_line:
                            title_part = clean_line.split('. ', 1)[1]
                            current_story['title'] = title_part
                    
                    # Adiciona linha ao resumo
                    elif current_story:
                        if 'summary' not in current_story:
                            current_story['summary'] = line
                        else:
                            current_story['summary'] += ' ' + line

                # Processa última história
                if current_story:
                    processed_story = self._process_story_content(
                        current_story.get('title', ''),
                        current_story.get('summary', '')
                    )
                    if processed_story:
                        processed_stories.append(processed_story)

            if not processed_stories:
                raise ValueError("Nenhuma história válida extraída")

            LogManager.info(f"Extraídas {len(processed_stories)} histórias válidas", "StoryContext")
            return processed_stories

        except Exception as e:
            LogManager.error(f"Erro ao extrair dados da história: {e}", "StoryContext")
            LogManager.error(f"Texto que causou erro: {text[:200]}...", "StoryContext")
            raise

    def _process_story_content(self, title: str, summary: str) -> Optional[dict]:
        """Processa o conteúdo de uma história extraindo informações relevantes"""
        try:
            if not summary:
                return None

            processed = {
                'title': title.strip() if title else 'História sem título',
                'summary': summary.strip(),
                'characters': self._extract_characters_from_text(summary),
                'setting': self._extract_setting_from_text(summary),
                'unique_elements': self._extract_unique_elements(summary)
            }

            if processed['title'] == 'História sem título':
                LogManager.warning(f"História sem título: {summary[:100]}...", "StoryContext")
            
            return processed

        except Exception as e:
            LogManager.error(f"Erro ao processar conteúdo da história: {e}", "StoryContext")
            return None
    
    def _extract_unique_elements(self, text: str) -> str:
        """Extrai elementos únicos/importantes da história"""
        # Palavras-chave que indicam elementos importantes
        key_elements = [
            "magia", "profecia", "segredo", "mistério", "artefato",
            "poder", "destino", "maldição", "ritual", "criatura"
        ]
        
        elements = []
        for element in key_elements:
            if element in text.lower():
                context = self._get_element_context(text, element)
                if context:
                    elements.append(context)
        
        return "\n".join(elements) if elements else "Elementos únicos serão revelados ao longo da história"

    def _get_element_context(self, text: str, element: str) -> str:
        """Obtém o contexto em que um elemento aparece no texto"""
        # Encontra a sentença que contém o elemento
        sentences = text.split('.')
        for sentence in sentences:
            if element in sentence.lower():
                return sentence.strip()
        return ""

    def _extract_setting_from_text(self, text: str) -> str:
        """Extrai descrição do cenário do texto"""
        # Procura por descrições de lugar no início do texto
        first_sentence = text.split('.')[0]
        
        # Palavras que indicam descrição de cenário
        setting_indicators = [
            "templo", "castelo", "floresta", "cidade", "vila", "palácio",
            "reino", "terra", "mundo", "sala", "campo", "montanha"
        ]
        
        # Procura por indicadores no início do texto
        for indicator in setting_indicators:
            if indicator in first_sentence.lower():
                return first_sentence
        
        return "Cenário não especificado explicitamente no texto"

    def _extract_characters_from_text(self, text: str) -> List[str]:
        """Extrai nomes de personagens do texto"""
        characters = []
        # Procura por nomes capitalizados seguidos de descrições comuns
        name_patterns = [
            r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # Nomes capitalizados
            r'(?:jovem|padre|sacerdote|guerreiro|princesa|rei|rainha)\s+([A-Z][a-z]+)',  # Títulos seguidos de nomes
        ]
        
        for pattern in name_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(0)
                if name not in characters and len(name) > 2:  # Evita falsos positivos
                    characters.append(name)
        
        return characters or ["Personagem não especificado"]
        
    def _process_story_dict(self, story: dict) -> dict:
        """Processa um dicionário de história individual"""
        story_data = {
            'title': None,
            'summary': None,
            'characters': [],
            'setting': None,
            'unique_elements': None
        }
        
        # Mapeamento de diferentes keys possíveis
        mappings = {
            'title': ['titulo', 'title', 'nome'],
            'summary': ['resumo', 'summary', 'descricao', 'início', 'opening'],
            'characters': ['personagens', 'characters', 'personagemPrincipal'],
            'setting': ['ambiente', 'setting', 'localizacao', 'location'],
            'unique_elements': ['elementos_unicos', 'unique_elements', 'elementos', 'features']
        }
        
        for target_key, possible_keys in mappings.items():
            for key in possible_keys:
                if key in story:
                    value = story[key]
                    if target_key == 'characters' and isinstance(value, str):
                        story_data[target_key] = [value]
                    else:
                        story_data[target_key] = value
                    break
                    
        # Processar elementos adicionais
        if 'conflict' in story:
            story_data['unique_elements'] = (story_data['unique_elements'] or '') + f"\nConflito: {story['conflict']}"
        if 'atmosphere' in story:
            story_data['unique_elements'] = (story_data['unique_elements'] or '') + f"\nAtmosfera: {story['atmosphere']}"
                    
        return story_data
        
    async def _regenerate_stories(self) -> dict:
        """Solicita nova geração de histórias com instruções mais claras"""
        LogManager.info("Solicitando nova geração de histórias", "StoryChat")
        
        prompt = """Gere 4 histórias únicas e envolventes.
        IMPORTANTE: Inclua para cada história:
        - Título impactante
        - Resumo detalhado da premissa
        - Lista de personagens principais (3-4)
        - Descrição do ambiente/cenário
        - Atmosfera e tom da história
        - Conflito central
        - Elementos únicos que destacam a história
        
        REGRAS:
        1. Use nomes internacionais variados
        2. Crie cenários em diferentes partes do mundo
        3. Desenvolva temas universais
        4. Mantenha consistência interna
        5. Foque em conflitos interessantes
        
        FORMATO:
        [
            {
                "titulo": "título da história",
                "resumo": "resumo detalhado",
                "personagens": ["nome 1", "nome 2"],
                "ambiente": "descrição do cenário",
                "atmosfera": "descrição do tom e clima",
                "conflito": "descrição do conflito central",
                "elementos_unicos": "elementos especiais da história"
            },
            {...}
        ]"""

        response = self.client.chat.completions.create(
            model="llama-2-13b-chat",
            messages=[
                {
                    "role": "system", 
                    "content": "Você é um autor criativo que gera histórias ricas e originais."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )

        # Tenta novamente o parsing com a nova resposta
        return await self._parse_story_options(response.choices[0].message.content)
    
    def get_character_memories(self) -> Dict[str, List[str]]:
        """Recupera memórias relevantes de todos os personagens."""
        try:
            memories = {}
            with sqlite3.connect(self.memory_db_path) as conn:
                # Primeiro, obtém lista de personagens únicos
                cursor = conn.execute("SELECT DISTINCT character_name FROM memories")
                characters = [row[0] for row in cursor.fetchall()]
                
                # Para cada personagem, recupera suas memórias mais relevantes
                for character in characters:
                    cursor = conn.execute("""
                        SELECT content, importance, timestamp 
                        FROM memories 
                        WHERE character_name = ?
                        ORDER BY importance DESC, timestamp DESC
                        LIMIT 5
                    """, (character,))
                    
                    char_memories = []
                    for content, importance, timestamp in cursor.fetchall():
                        if content and content.strip():
                            char_memories.append(content)
                    
                    if char_memories:
                        memories[character] = char_memories
            
            return memories
            
        except Exception as e:
            LogManager.error(f"Erro ao recuperar memórias: {e}", "StoryContext")
            return {}

    async def get_story_summary(self, llm_client) -> str:
        """Gera um resumo formatado da história e contexto atual."""
        try:
            summary_parts = []
            
            # === Contexto Atual ===
            summary_parts.append("=== Contexto Atual ===")
            summary_parts.append("Contexto atual da cena:")
            summary_parts.append(f"\tLocal: {self.current_location or 'Indefinido'}")
            summary_parts.append(f"\tHorário: {self.time_of_day or 'Indefinido'}")
            summary_parts.append(f"\tAtmosfera: {self.current_mood or 'Neutro'}")
            
            if self.present_characters:
                summary_parts.append(f"\tPersonagens presentes: {', '.join(self.present_characters)}")
                
            # === Resumo da História ===
            summary_parts.append("\n=== Resumo da História ===")
            
            if not self.story_events:
                summary_parts.append("A história ainda não começou...")
                return "\n".join(summary_parts)

            try:
                # Pega os eventos mais relevantes
                recent_events = [event for event in self.story_events[-10:] 
                            if event['type'] in ['narration', 'dialogue', 'context']]

                if recent_events:
                    events_text = "\n".join([
                        f"- {'Narrador' if e['type'] == 'narration' else e['character']}: {e['content']}"
                        for e in recent_events
                    ])

                    prompt = f"""Baseado nos eventos abaixo, crie um resumo coeso da história:

                    Eventos:
                    {events_text}

                    INSTRUÇÕES:
                    1. Mantenha um tom narrativo fluido
                    2. Foque nos eventos mais importantes
                    3. Destaque as mudanças significativas
                    4. Mantenha o resumo em 2-3 parágrafos
                    5. Inclua apenas informações confirmadas nos eventos
                    """

                    response = llm_client.chat.completions.create(
                        model="llama-2-13b-chat",
                        messages=[
                            {"role": "system", "content": "Você é um narrador que cria resumos coesos."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=200
                    )

                    summary_parts.append(response.choices[0].message.content.strip())
                else:
                    summary_parts.append("Nenhum evento significativo registrado ainda.")

            except Exception as e:
                LogManager.error(f"Erro ao gerar resumo com LLM: {e}", "StoryContext")
                # Usa um resumo básico em caso de erro
                summary_parts.append("\n".join([e['content'] for e in recent_events[-3:]]))

            return "\n".join(summary_parts)
                
        except Exception as e:
            LogManager.error(f"Erro ao gerar resumo da história: {e}", "StoryContext")
            return "Erro ao gerar resumo da história."
    
    def _extract_characters(self, story: dict) -> List[str]:
        """Extrai personagens da história considerando diferentes formatos"""
        characters = []
        
        # Tenta diferentes campos possíveis
        char_fields = ['personagens', 'characters', 'protagonistas', 'personagemPrincipal']
        
        for field in char_fields:
            if field in story:
                value = story[field]
                if isinstance(value, list):
                    characters.extend(value)
                elif isinstance(value, str):
                    # Se for string única, assume que podem haver múltiplos personagens separados
                    chars = value.split(',') or [value]
                    characters.extend([c.strip() for c in chars])
                    
        return characters or ["Personagem não especificado"]

    def _process_single_story(self, story: dict) -> dict:
        """Processa dados de uma única história mantendo a lógica original"""
        story_data = {
            'title': None,
            'summary': None,
            'characters': [],
            'setting': None,
            'unique_elements': None
        }
        
        # Mapeamento de diferentes keys possíveis (mantido da versão original)
        title_keys = ['titulo', 'title', 'nome']
        summary_keys = ['resumo', 'summary', 'descricao', 'início', 'opening']
        character_keys = ['personagens', 'characters', 'personagemPrincipal']
        setting_keys = ['ambiente', 'setting', 'localizacao', 'location']
        elements_keys = ['elementos_unicos', 'unique_elements', 'elementos', 'features']
        
        # Extrai título
        for key in title_keys:
            if key in story:
                story_data['title'] = story[key]
                break
                
        # Extrai resumo
        for key in summary_keys:
            if key in story:
                story_data['summary'] = story[key]
                break
                
        # Extrai personagens
        for key in character_keys:
            if key in story:
                if isinstance(story[key], list):
                    story_data['characters'] = story[key]
                elif isinstance(story[key], str):
                    story_data['characters'] = [story[key]]
                break
                
        # Extrai cenário
        for key in setting_keys:
            if key in story:
                story_data['setting'] = story[key]
                break
                
        # Extrai elementos únicos
        for key in elements_keys:
            if key in story:
                story_data['unique_elements'] = story[key]
                break
                
        # Tenta extrair elementos adicionais se disponíveis
        if 'conflict' in story:
            story_data['unique_elements'] = (story_data['unique_elements'] or '') + f"\nConflito: {story['conflict']}"
        if 'atmosphere' in story:
            story_data['unique_elements'] = (story_data['unique_elements'] or '') + f"\nAtmosfera: {story['atmosphere']}"
                
        return story_data
            
    def _create_prompt_from_memories(self, character_memories) -> str:
        """Cria um prompt para o LLM baseado nas memórias dos personagens"""
        memory_context = ""
        for character, memories in character_memories.items():
            if memories:
                memory_context += f"\nMemórias de {character}:\n"
                memory_context += "\n".join(memories) + "\n"

        return f"""Com base nas seguintes memórias dos personagens, crie um resumo coeso e narrativo 
        dos eventos principais da história até agora. Foque nos eventos mais significativos e nas 
        mudanças importantes nas relações entre os personagens.

        {memory_context}

        Diretrizes para o resumo:
        1. Mantenha um tom narrativo e fluido
        2. Foque nos eventos mais importantes e suas consequências
        3. Destaque mudanças significativas nas relações
        4. Mantenha o resumo em 3-4 frases principais
        5. Inclua apenas informações confirmadas nas memórias

        Resumo:"""
    
    def get_current_context(self) -> str:
        """Retorna o contexto atual da história em formato de texto."""
        try:
            context_parts = []
            
            # Inclui localização e hora do dia
            context_parts.append(f"Local atual: {self.current_location}")
            context_parts.append(f"Horário: {self.time_of_day}")
            context_parts.append(f"Atmosfera: {self.current_mood}")
            
            # Adiciona descrição da cena se existir
            if self.scene_description:
                context_parts.append(f"\nDescrição da cena:\n{self.scene_description}")
            
            # Lista personagens presentes
            if self.present_characters:
                context_parts.append(f"\nPersonagens presentes: {', '.join(self.present_characters)}")
            
            # Inclui últimos eventos relevantes (últimos 5)
            relevant_events = []
            for event in self.story_events[-5:]:
                if event['type'] == 'narration':
                    relevant_events.append(f"Narração: {event['content']}")
                elif event['type'] == 'dialogue':
                    relevant_events.append(f"{event['character']}: {event['content']}")
                elif event['type'] == 'user_input':
                    relevant_events.append(f"Você: {event['content']}")
            
            if relevant_events:
                context_parts.append("\nEventos recentes:")
                context_parts.extend(relevant_events)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            LogManager.error(f"Erro ao obter contexto atual: {e}", "StoryContext")
            return "Não foi possível obter o contexto atual."
        
    def _get_main_points(self, events: List[str]) -> List[str]:
        """Seleciona os pontos principais dos eventos para criar um resumo coeso."""
        main_points = []
        
        # Primeiro, procura por eventos significativos
        significant_events = []
        for event in events:
            # Prioriza eventos com palavras-chave importantes
            if any(word in event.lower() for word in ['decidiu', 'revelou', 'descobriu']):
                significant_events.append(event)
        
        # Se encontrou eventos significativos, usa-os como base
        if significant_events:
            main_points.extend(significant_events[:2])  # Limita a 2 eventos significativos
        
        # Adiciona o evento mais recente se ainda não estiver incluído
        if events and events[-1] not in main_points:
            main_points.append(events[-1])
        
        # Limita o número total de pontos
        return main_points[:3]
    
    def cleanup(self):
        """Fecha conexões com banco de dados"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except Exception as e:
            LogManager.error(f"Erro ao limpar StoryContext: {e}", "StoryContext")