import os
import sys
import traceback
import wave
import torch
import argparse

from character_profile_manager import CharacterProfileManager
from dynamic_character_manager import DynamicCharacterManager
from narrative_history_manager import NarrativeHistoryManager
from player_character import PlayerCharacter
parser = argparse.ArgumentParser()
import openai
from openai import OpenAI
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
import json
import queue
import threading
import sqlite3
from datetime import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Dict, List, Tuple, Optional 
from event_manager import StoryEvent, EventType

# Imports do projeto
from story_context import StoryContext
from narrator_system import NarratorSystem, NarratorStyle
from audio_processor import AudioProcessor
from memory_manager import MemoryManager, Memory
from emotion_system import EmotionAnalyzer, EmotionDisplay, EmotionType, EmotionParameters, EmotionalResponse
from story_utils import InteractionManager, StoryPromptManager, NarratorType
from ui_utils import Colors
from character_models import Character
from interaction_system import InteractionSystem
from entity_manager import EntityManager, EntityType
from narrative_history_manager import NarrativeHistoryManager
from log_manager import LogManager

LogManager.set_debug_mode(True)

LANGUAGE_PROMPT = """IMPORTANTE: Você DEVE responder SEMPRE em português do Brasil.
Use linguagem natural, gírias e expressões brasileiras quando apropriado."""

class StoryChat:
    def __init__(self, gui_mode=False, narrator_style=None, event_manager=None):
        """Inicializa o StoryChat"""
        try:
            LogManager.debug("Inicializando StoryChat...", "StoryChat")
            
            # 1. Configurações básicas
            self.gui_mode = gui_mode
            self.event_manager = event_manager
            self.player = None  # Inicializa como None até ser configurado adequadamente
            
            # 2. Verifica estrutura de arquivos necessária
            self._verify_required_files()
            self._create_default_prompt()
            
            # 3. Setup de hardware e modelos base
            self.setup_device()
            self.setup_models()  # Configura self.client (LLM)
            
            # 4. Inicialização dos gerenciadores principais
            self.memory_manager = MemoryManager()
            self.character_manager = DynamicCharacterManager(llm_client=self.client)  # Passa o client LLM
            
            # 4.1 Após inicializar o character_manager
            if not self.character_manager.check_client():
                raise RuntimeError("Cliente LLM não configurado corretamente no DynamicCharacterManager")
            
            self.profile_manager = CharacterProfileManager(story_chat=self)
            self.entity_manager = EntityManager(
                locations_file=os.path.join(os.getcwd(), "locations.json"),
                story_chat=self
            )
            
            # 5. Setup de áudio
            self.setup_audio()
            self.audio_processor = AudioProcessor(
                xtts_model=self.xtts_model,
                xtts_config=self.xtts_config,
                output_dir=self.output_dir,
                gui_mode=gui_mode,
                event_manager=event_manager
            )
            
            # 6. Carregamento de personagens
            self.load_characters()
            self.player = PlayerCharacter()  # Inicializa após carregar personagens
            
            # 7. Configuração dos sistemas de história
            self.story_context = StoryContext(llm_client=self.client)
            self.last_story_prompt = ""
            self.emotion_analyzer = EmotionAnalyzer()
            self.narrator_system = NarratorSystem()
            self.narrative_manager = NarrativeHistoryManager()
            
            # 8. Configuração do narrador e interações
            if gui_mode and narrator_style is not None:
                self.narrator_system.set_narrator_style(narrator_style)
                
            self.interaction_system = InteractionSystem(self.characters)
            
            # 9. Inicializa estrutura da cena
            self.current_scene = {
                "location": "",
                "time": "",
                "mood": "",
                "characters": set(),
                "description": ""
            }
            
            # 10. Carrega contexto completo
            asyncio.run(self.load_full_context())
            
            LogManager.info("StoryChat inicializado com sucesso", "StoryChat")
            
        except Exception as e:
            LogManager.error(f"Erro na inicialização do StoryChat: {e}", "StoryChat")
            raise RuntimeError(f"Falha na inicialização do StoryChat: {str(e)}")
    
    def _verify_required_files(self):
        """Verifica e cria diretórios e arquivos necessários"""
        try:
            LogManager.debug("Verificando arquivos e diretórios necessários...", "StoryChat")
            
            # Diretórios necessários
            required_dirs = {
                'voices': 'Arquivos de voz dos personagens',
                'prompts': 'Arquivos de prompt dos personagens',
                'outputs': 'Arquivos de áudio gerados',
                'avatars': 'Imagens dos personagens',
                'log': 'Arquivos de log'
            }

            # Verifica/cria diretórios
            for dir_name, description in required_dirs.items():
                if not os.path.exists(dir_name):
                    os.makedirs(dir_name)
                    LogManager.info(f"Diretório criado: {dir_name} ({description})", "StoryChat")
                else:
                    LogManager.debug(f"Diretório existente: {dir_name}", "StoryChat")

            # Arquivos necessários para o narrador
            narrator_files = {
                'voices/narrator_voice.wav': 'voices/en_sample.wav',
                'voices/narrator_descriptive.wav': 'voices/en_sample.wav',
                'voices/narrator_sassy.wav': 'voices/en_sample.wav',
                'prompts/narrator_prompt.txt': 'prompts/temp_narrator_prompt.txt'
            }

            # Verifica/copia arquivos do narrador
            for target_file, default_file in narrator_files.items():
                if not os.path.exists(target_file):
                    if os.path.exists(default_file):
                        import shutil
                        shutil.copy(default_file, target_file)
                        LogManager.info(f"Arquivo copiado: {default_file} -> {target_file}", "StoryChat")
                    else:
                        LogManager.warning(f"Arquivo padrão não encontrado: {default_file}", "StoryChat")
                else:
                    LogManager.debug(f"Arquivo existente: {target_file}", "StoryChat")

            # Verifica avatares básicos
            required_avatars = {
                'avatars/narrador.png': 'Sistema',
                'avatars/user.png': 'Usuário',
                'avatars/sistema.png': 'Sistema',
                'avatars/default.png': 'Padrão'
            }

            for avatar_file, description in required_avatars.items():
                if not os.path.exists(avatar_file):
                    LogManager.warning(f"Avatar não encontrado: {avatar_file} ({description})", "StoryChat")

            LogManager.info("Verificação de arquivos concluída com sucesso", "StoryChat")

        except Exception as e:
            LogManager.error(f"Erro na verificação de arquivos: {e}", "StoryChat")
            raise RuntimeError(f"Falha na inicialização: {str(e)}")

    def show_main_menu(self):
        """Exibe o menu principal de comandos"""
        print("\n=== Menu Principal ===")
        print("1. Falar com personagem")
        print("2. Ver contexto")
        print("3. Ver lembranças")
        print("4. Ver/gerenciar personagens")
        print("5. Ver lugares")
        print("6. Editar histórico")
        print("7. Mudar narrador")
        print("8. Analisar história")  # Readicionada
        print("9. Resetar história")
        print("10. Sair")
    
        choice = input("\nEscolha uma opção (1-10): ").strip()
        return choice

    def show_character_menu(self, characters: dict) -> Optional[str]:
        """Exibe menu de seleção de personagens"""
        try:
            # Primeiro atualiza a lista de personagens
            self.load_characters()
            
            if not self.characters and not (hasattr(self, 'narrator_system') and self.narrator_system):
                print("\nNenhum personagem disponível ainda.")
                return None
                
            print("\n=== Personagens Disponíveis ===")
            # Adiciona narrador como primeira opção
            print("1. Narrador")
            
            # Lista personagens existentes, excluindo o personagem do jogador
            available_characters = []
            player_name = self.player.background.name if self.player and self.player.background else None
            
            # Usa character_manager para verificar personagens
            for name in self.characters.keys():
                # Obtém dados do character_manager em vez do objeto Character
                char_data = self.character_manager.characters.get(name, {})
                # Verifica se não é o jogador
                if (name != player_name and 
                    not char_data.get('is_player', False)):
                    available_characters.append(name)
            
            for i, name in enumerate(available_characters, 2):
                print(f"{i}. {name}")
                
            choice = input(f"\nEscolha um personagem (1-{len(available_characters)+1}) ou ENTER para voltar: ").strip()
            
            if not choice:
                return None
                
            try:
                idx = int(choice)
                if idx == 1:
                    return "narrador"
                elif 2 <= idx <= len(available_characters) + 1:
                    return available_characters[idx-2]
            except ValueError:
                pass
                
            print("Escolha inválida!")
            return None
            
        except Exception as e:
            LogManager.error(f"Erro ao mostrar menu de personagens: {e}", "StoryChat")
            print(f"\nErro ao mostrar menu de personagens: {e}")
            return None
    
    async def process_menu_choice(self, choice: str):
        """Processa escolha do menu principal"""
        try:
            if choice == "1":  # Falar
                while True:
                    character = self.show_character_menu(self.characters)
                    if not character:
                        break
                        
                    while True:
                        text = input(f"\n{Colors.WHITE}Você (ou 'voltar' para menu): {Colors.RESET}").strip()
                        if text.lower() == 'voltar':
                            break
                            
                        if character == "narrador":
                            narrator_profile = self.narrator_system.get_current_profile()
                            char = Character(
                                name="",
                                voice_file=narrator_profile.voice_file,
                                system_prompt_file="prompts/narrator_prompt.txt",
                                color=Colors.YELLOW
                            )
                        else:
                            char = self.characters[character]
                            
                        # Em vez de criar um novo event loop ou usar run_until_complete,
                        # apenas chama o método assíncrono normalmente
                        await self.process_character_interaction(text, char)
                        input("\nPressione ENTER para continuar...")
                
            elif choice == "2":  # Contexto
                summary = await self.show_context()
                if summary:
                    input("\nPressione ENTER para continuar...")
                
            elif choice == "3":  # Lembranças
                self.show_memories_menu()
                
            elif choice == "4":  # Gerenciar personagens 
                await self.list_characters()
                input("\nPressione ENTER para continuar...")
                
            elif choice == "5":  # Lugares
                self.show_locations()
                input("\nPressione ENTER para continuar...")
                
            elif choice == "6":  # Editar histórico
                await self.edit_history()
                input("\nPressione ENTER para continuar...")
                
            elif choice == "7":  # Mudar narrador
                old_style = self.narrator_system.current_style
                self.select_narrator_style()
                if old_style != self.narrator_system.current_style:
                    print(f"\nEstilo do narrador alterado para: {self.narrator_system.current_style.value}")
                input("\nPressione ENTER para continuar...")

            elif choice == "8":  # Analisar
                    await self.analyze_history()
                    input("\nPressione ENTER para continuar...")
                
            elif choice == "9":  # Resetar
                try:
                    success = await self.reset_story()
                    if success:
                        print(Colors.format_system_message("\nHistória iniciada com sucesso!"))
                        # Não chama initialize_story aqui pois já é chamado dentro de reset_story
                    else:
                        print(Colors.format_system_message("\nErro ao resetar história."))
                except Exception as e:
                    LogManager.error(f"Erro durante reset: {e}", "StoryChat")
                    print(Colors.format_system_message(f"\nErro ao resetar: {e}"))
                
                input("\nPressione ENTER para continuar...")
                    
            elif choice == "10":  # Sair
                print("\nEncerrando programa...")
                return True  # Sinaliza que deve encerrar
            
            return False  # Continua o programa
            
        except Exception as e:
            LogManager.error(f"Erro ao processar escolha do menu: {e}", "StoryChat")
            print(f"\nErro ao processar escolha: {e}")
            input("\nPressione ENTER para continuar...")
            return False

    def show_memories_menu(self):
        """Menu para visualizar lembranças dos personagens"""
        while True:
            print("\n=== Memórias dos Personagens ===")
            for i, name in enumerate(self.characters.keys(), 1):
                print(f"{i}. {name}")
            print("\n0. Voltar")
            
            choice = input("\nEscolha um personagem ou 0 para voltar: ").strip()
            if choice == "0" or not choice:
                break
                
            try:
                idx = int(choice)
                if 1 <= idx <= len(self.characters):
                    char_name = list(self.characters.keys())[idx-1]
                    char = self.characters[char_name]
                    print(f"\n{char.color}Memórias de {char.name}:{Colors.RESET}")
                    memories = self.memory_manager.get_formatted_memories(char_name)
                    if memories:
                        print(f"{char.color}{memories}{Colors.RESET}")
                    else:
                        print(f"{char.color}Ainda não tenho memórias registradas.{Colors.RESET}")
            except ValueError:
                print("Escolha inválida!")
                continue
                
            input("\nPressione ENTER para continuar...")
        
    async def initialize_story(self):
        """Inicializa uma nova história"""
        try:
            # Mensagem de boas vindas
            welcome_msg = """Seja bem-vindo à aventura!
                Você está prestes a embarcar num mundo de suspense, emoção e escolhas que definirão seu destino.
                Neste sistema de histórias interativas, você é o protagonista da narrativa.
                Prepare-se para explorar reinos mágicos, lidar com personagens complexos, descobrir segredos ocultos e enfrentar desafios que testarão suas habilidades e decisões."""
            print(f"\n{Colors.CYAN}{welcome_msg}{Colors.RESET}\n")

            genres = [
                "1. Fantasia Medieval Clássica",
                "2. Ficção Científica Espacial",
                "3. Ficção Científica Cyberpunk",
                "4. Drama Contemporâneo", 
                "5. Mistério/Investigação",
                "6. Terror/Horror",
                "7. Aventura Pós-Apocalíptica",
                "8. Romance Sobrenatural",
                "9. Steampunk Vitoriano",
                "10. Mitologia e Lendas",
                "0. Criar meu próprio tema"
            ]

            print("\nEscolha o tipo de história:")
            for genre in genres:
                print(genre)

            choice = input("\nSua escolha (0-10): ").strip()
            while not choice.isdigit() or int(choice) not in range(0,11):
                choice = input("Escolha inválida. Tente novamente (0-10): ").strip()
                
            choice = int(choice)
            custom_theme = ""

            # Nova implementação do prompt para a LLM
            base_prompt = """IMPORTANTE: SEMPRE retorne EXATAMENTE 4 histórias em português do Brasil no seguinte formato JSON, sem nenhum texto adicional:

            {
                "stories": [
                    {
                        "title": "Título da História",
                        "summary": "Resumo detalhado da história em português do Brasil...",
                        "setting": "Descrição do cenário e ambiente",
                        "characters": ["Nome do Personagem 1", "Nome do Personagem 2"],
                        "tone": "tom/atmosfera da história"
                    },
                    ... (mais 3 histórias no mesmo formato)
                ]
            }

            REGRAS OBRIGATÓRIAS:
            1. Use linguagem natural brasileira
            2. Cada resumo deve ter pelo menos 200 palavras
            3. Inclua mínimo de 2 personagens por história
            4. Descreva cenários vibrantes e memoráveis
            5. RETORNE APENAS O JSON, sem texto adicional"""

            if choice == 0:
                custom_theme = input("\nDescreva o tema desejado: ").strip()
                story_prompt = f"{base_prompt}\n\nCrie 4 histórias baseadas no tema: '{custom_theme}'\n"
            else:
                selected_genre = genres[choice-1].split('. ')[1]
                story_prompt = f"{base_prompt}\n\nCrie 4 histórias do gênero: '{selected_genre}'\n"

            # Gera as histórias com formato específico
            response = self.client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": """Você é um criador de histórias que SEMPRE retorna apenas JSON válido com 4 histórias no formato:
                            {
                                "stories": [
                                    {
                                        "title": "string",
                                        "summary": "string",
                                        "setting": "string",
                                        "characters": ["string"],
                                        "tone": "string"
                                    }
                                ]
                            }
                            
                            IMPORTANTE: Retorne APENAS o JSON, sem texto adicional."""
                    },
                    {"role": "user", "content": story_prompt}
                ],
                temperature=0.8
            )

            try:
                stories_data = json.loads(response.choices[0].message.content)
                if not isinstance(stories_data, dict) or 'stories' not in stories_data:
                    LogManager.error("Resposta não contém campo 'stories'", "StoryChat")
                    return await self._retry_story_generation()
                
                if not stories_data['stories'] or len(stories_data['stories']) != 4:
                    LogManager.error("Número incorreto de histórias retornado", "StoryChat")
                    return await self._retry_story_generation()
                
                # Validação dos campos obrigatórios
                required_fields = ['title', 'summary', 'setting', 'characters', 'tone']
                for story in stories_data['stories']:
                    if not all(field in story for field in required_fields):
                        LogManager.error("História com campos faltando", "StoryChat")
                        return await self._retry_story_generation()
                
                # Mantemos os dados originais e a versão formatada
                formatted_stories = {}
                raw_stories = {}
                
                for idx, story in enumerate(stories_data['stories'], 1):
                    # Guarda a história original
                    raw_stories[str(idx)] = story
                    
                    # Cria versão formatada para exibição
                    formatted_stories[str(idx)] = f"""╔═════════════════════════════════════════════════════
    ║ {Colors.BOLD}{story['title']}{Colors.RESET}
    ╠═════════════════════════════════════════════════════
    ║ 
    ║ {Colors.CYAN}Sinopse:{Colors.RESET}
    ║   {story['summary']}
    ║ 
    ║ {Colors.CYAN}Cenário:{Colors.RESET}
    ║   {story['setting']}
    ║ 
    ║ {Colors.CYAN}Personagens:{Colors.RESET}
    ║ {', '.join(story['characters'])}
    ║ 
    ║ {Colors.CYAN}Atmosfera:{Colors.RESET}
    ║ {story['tone']}
    ║
    ╚═════════════════════════════════════════════════════"""

                if not formatted_stories:
                    raise ValueError("Nenhuma história gerada")

                # Mostra opções e obtém escolha
                print("\nEscolha o enredo inicial:")
                for num, story in formatted_stories.items():
                    print(f"\n{num}. {story}")

                story_choice = input("\nSua escolha (1-4): ").strip()
                while not story_choice.isdigit() or int(story_choice) not in range(1,5):
                    story_choice = input("Escolha inválida. Tente novamente (1-4): ").strip()

                # Obtém história selecionada e dados relacionados
                selected_story_data = raw_stories[story_choice]
                selected_story_text = selected_story_data['summary']
                selected_genre = genres[choice-1].split('. ')[1] if choice > 0 else "Personalizado"
                selected_theme = custom_theme if choice == 0 else selected_genre
                
                # Configura o contexto inicial
                self.story_context.story_genre = selected_genre
                self.story_context.story_theme = selected_theme

                # Registra a história inicial como primeiro evento
                self.story_context.add_event(
                    event_type='narration',
                    content=selected_story_text,
                    character='Narrador'
                )

                # Obtém personagens diretamente do JSON
                story_characters = selected_story_data['characters']
                
                # Define o contexto inicial da cena usando dados do JSON
                self.story_context.current_location = selected_story_data['setting']
                self.story_context.time_of_day = self.story_context._extract_time_from_story(selected_story_text)
                self.current_scene["mood"] = selected_story_data['tone']
                
                # Primeiro cria o perfil do jogador
                await self.setup_character(selected_story_text)

                # Cria os personagens detectados
                for char_name in story_characters:
                    if char_name not in self.characters and char_name not in self.character_manager.known_names:
                        await self.character_manager.auto_create_character(char_name, selected_story_text)

                # Gera resumo inicial da história
                initial_summary = await self.story_context.generate_narrative_summary(self.client)
                
                # Registra o resumo como evento de contexto
                self.story_context.add_event(
                    event_type='context',
                    content=initial_summary,
                    character='Sistema'
                )

                # Salva configurações da história
                with sqlite3.connect(self.story_context.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO story_settings (id, theme, genre, created_at)
                        VALUES (1, ?, ?, ?)
                    """, (selected_theme, selected_genre, datetime.now().isoformat()))

                return True

            except json.JSONDecodeError:
                LogManager.error("Resposta da LLM não é um JSON válido", "StoryChat")
                raise ValueError("Formato de resposta inválido")

        except Exception as e:
            LogManager.error(f"Erro na inicialização: {e}", "StoryChat")
            return False

    async def _retry_story_generation(self) -> bool:
        """Tenta gerar histórias novamente com temperatura mais baixa"""
        try:
            LogManager.info("Tentando gerar histórias novamente", "StoryChat")
            
            response = self.client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {
                        "role": "system",
                        "content": """CRITICAL: You must return ONLY a valid JSON with EXACTLY 4 stories in this format:
                            {"stories": [{"title": "", "summary": "", "setting": "", "characters": [], "tone": ""}]}
                            NO additional text allowed."""
                    },
                    {"role": "user", "content": self.last_story_prompt}
                ],
                temperature=0.3  # Temperatura mais baixa
            )
            
            # Tenta processar a resposta
            try:
                stories_data = json.loads(response.choices[0].message.content)
                return bool(stories_data and 'stories' in stories_data and len(stories_data['stories']) == 4)
            except:
                return False
            
        except Exception as e:
            LogManager.error(f"Erro na recuperação: {e}", "StoryChat")
            return False
    
    async def _select_voice_file(self, char_name: str) -> Optional[str]:
        """Seleciona arquivo de voz com GUI"""
        try:
            from PyQt6.QtWidgets import QFileDialog, QApplication
            
            if QApplication.instance() is None:
                app = QApplication([])
            
            dialog = QFileDialog()
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilter("Audio Files (*.mp3 *.wav)")
            dialog.setWindowTitle(f"Selecione a voz para {char_name}")
            
            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                return dialog.selectedFiles()[0]
            return None
        except Exception as e:
            LogManager.error(f"Erro ao abrir seletor de arquivo: {e}", "StoryChat")
            return None
        
    async def create_player_profile(self, story_context: str) -> bool:
        """Cria o perfil do personagem do jogador"""
        try:
            print("\n=== Criação do Personagem ===")
            print(f"Contexto da história: {story_context}")
            
            # Coleta informações do personagem
            name = input("Nome do personagem: ").strip()
            while not name:
                name = input("Nome é obrigatório: ").strip()

            gender = ""
            while gender not in ['M', 'F']:
                gender = input("Gênero (M/F): ").upper()

            print("\nInformações opcionais (ENTER para pular)")
            age = input("Idade: ").strip()
            occupation = input("Ocupação: ").strip()
            background = input("História de origem (breve): ").strip()

            # Cria o perfil
            basic_info = {
                'name': name,
                'gender': 'Masculino' if gender == 'M' else 'Feminino',
                'age': int(age) if age.isdigit() else None,
                'occupation': occupation or None,
                'background_story': background or None,
                'story_context': story_context,
                'personality_traits': [],  # Será preenchido pela LLM
                'goals': []  # Será preenchido pela LLM
            }

            # Cria o perfil do jogador
            success = await self.player.create_profile(basic_info, self.client)
            if success:
                LogManager.info(f"Perfil do jogador {name} criado com sucesso", "StoryChat")
                
                # Atualiza o contexto da história
                self.story_context.add_event(
                    event_type='player_created',
                    content=f"Jogador criou personagem: {name}",
                    character=name
                )
                return True
                
            return False

        except Exception as e:
            LogManager.error(f"Erro ao criar perfil do jogador: {e}", "StoryChat")
            return False

    async def setup_character(self, story_context: str):
        """Configuração do personagem baseada no contexto da história"""
        try:
            print("\n=== Criação do Personagem ===")
            print(f"Contexto da história: {story_context}")
            
            # Garante que o player é inicializado apenas uma vez
            if not hasattr(self, 'player') or self.player is None:
                self.player = PlayerCharacter()
                LogManager.debug("Novo PlayerCharacter criado", "StoryChat")
            
            name = input("Nome do personagem: ").strip()
            while not name:
                name = input("Nome é obrigatório: ").strip()

            gender = ""
            while gender not in ['M', 'F']:
                gender = input("Gênero (M/F): ").upper()

            print("\nInformações opcionais (ENTER para pular)")
            age = input("Idade: ").strip()
            occupation = input("Ocupação: ").strip()
            background = input("História de origem (breve): ").strip()

            profile_data = {
                'name': name,
                'gender': 'Masculino' if gender == 'M' else 'Feminino',
                'age': int(age) if age.isdigit() else None,
                'occupation': occupation or None,
                'background_story': background or None,
                'story_context': story_context
            }

            LogManager.debug(f"Tentando criar perfil com dados: {profile_data}", "StoryChat")
            success = await self.player.create_profile(profile_data, self.client)

            if success:
                # Adiciona o personagem do jogador ao character_manager
                player_data = {
                    'profile': self.player.background.__dict__,
                    'voice_file': "voices/narrator_voice.wav",  # Voz padrão inicial
                    'system_prompt_file': f"prompts/{self.player.background.name.lower()}_prompt.txt",
                    'color': Colors.BLUE,  # Cor específica para o jogador
                    'is_player': True  # Flag para identificar que é o personagem do jogador
                }
                
                # Adiciona ao character_manager
                self.character_manager.characters[self.player.background.name] = player_data
                self.character_manager.save_characters()
                
                LogManager.info(f"Perfil do jogador {name} criado e adicionado com sucesso", "StoryChat")
                return True
            
            LogManager.error("Falha ao criar perfil do jogador", "StoryChat")
            return False

        except Exception as e:
            LogManager.error(f"Erro ao configurar personagem: {e}", "StoryChat")
            return False
        
    def _create_default_prompt(self):
        """Cria um arquivo de prompt padrão para o narrador se necessário"""
        default_prompt = """Você é um narrador onisciente que descreve cenas e ações em terceira pessoa.
        
        DIRETRIZES:
        1. Descreva as ações e ambientes de forma imersiva e detalhada
        2. Use linguagem descritiva e envolvente
        3. Foque em detalhes sensoriais (visão, som, cheiro, etc.)
        4. Mantenha o tom consistente com a cena
        5. Não dialogue diretamente - apenas narre
        6. Comece suas narrações com "Narrador:"
        7. Mantenha as descrições entre 2-3 frases para manter o ritmo
        """
        
        prompt_file = "prompts/temp_narrator_prompt.txt"
        try:
            if not os.path.exists(prompt_file):
                os.makedirs(os.path.dirname(prompt_file), exist_ok=True)
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(default_prompt)
                LogManager.info("Arquivo de prompt padrão criado", "StoryChat")
        except Exception as e:
            LogManager.error(f"Erro ao criar prompt padrão: {e}", "StoryChat")

    async def process_response(self, response: EmotionalResponse, character: Character, user_input: str):
        """
        Processa uma resposta emocional. Lida com dois tipos de respostas:
        1. Narração: Descrições em terceira pessoa pelo narrador
        2. Diálogo: Interações diretas em primeira pessoa pelo personagem
        """
        try:
            if not response or not response.text:
                LogManager.error("Resposta vazia ou inválida", "StoryChat")
                return
            
            LogManager.debug(f"Iniciando processamento de resposta e áudio", "StoryChat")
            
            parts = []
            current_text = ""
            current_speaker = None
            
            # Processa o texto linha por linha
            for line in response.text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Detecção de narrador (terceira pessoa)
                if "(Narrador:)" in line or "(Narrator:)" in line:
                    if current_text and current_speaker:
                        parts.append((current_speaker, current_text.strip()))
                    current_speaker = "Narrador"
                    current_text = line.replace('(Narrador:)', '').replace('(Narrator:)', '').strip()
                
                # Detecção de fala direta do personagem (primeira pessoa)
                elif f"({character.name}:)" in line:
                    if current_text and current_speaker:
                        parts.append((current_speaker, current_text.strip()))
                    current_speaker = character.name
                    current_text = line.replace(f'({character.name}:)', '').strip()
                
                # Continuação do texto atual
                else:
                    if current_speaker:
                        current_text += " " + line.strip()
                    else:
                        # Se não tem speaker definido, assume o personagem atual
                        current_speaker = character.name
                        current_text = line.strip()

            # Adiciona último texto pendente
            if current_text and current_speaker:
                parts.append((current_speaker, current_text.strip()))

            # Processa cada parte do diálogo/narração
            for speaker, text in parts:
                try:
                    LogManager.debug(f"Processando parte para {speaker}: {text[:50]}...", "StoryChat")
                    
                    # Verifica arquivo de voz antes de prosseguir
                    voice_file = (
                        self.narrator_system.get_current_profile().voice_file 
                        if speaker == "Narrador" 
                        else character.voice_file
                    )

                    if not os.path.exists(voice_file):
                        LogManager.error(f"Arquivo de voz não encontrado: {voice_file}", "StoryChat")
                        continue

                    # Verifica se é um arquivo WAV válido
                    try:
                        with wave.open(voice_file, 'rb') as wf:
                            wf.getframerate()  # Testa se é um WAV válido
                    except Exception as wav_error:
                        LogManager.error(f"Arquivo de voz inválido {voice_file}: {wav_error}", "StoryChat")
                        continue

                    # Registra evento
                    event_type = 'narration' if speaker == "Narrador" else 'dialogue'
                    self.story_context.add_event(
                        event_type=event_type,
                        content=text,
                        character=speaker
                    )

                    # Gera áudio apenas se o arquivo de voz for válido
                    try:
                        await self.audio_processor.synthesize_speech(
                            EmotionalResponse(
                                text=text,
                                emotion=response.emotion,
                                params=response.params
                            ),
                            character
                        )
                    except Exception as audio_error:
                        LogManager.error(f"Erro na síntese de áudio: {audio_error}", "StoryChat")

                except Exception as part_e:
                    LogManager.error(f"Erro processando parte: {part_e}", "StoryChat")
                    continue

            # Registra memória da interação
            self._register_interaction_memory(character, user_input, response)

        except Exception as e:
            LogManager.error(f"Erro ao processar resposta: {e}", "StoryChat")

    def _register_interaction_memory(self, character: Character, user_input: str, response: EmotionalResponse):
        """Registra memórias e interações após processamento de resposta"""
        try:
            # Cria e registra memória
            memory = character.create_memory(
                content=f"Usuário disse: {user_input} | Eu respondi: {response.text}",
                context="conversa",
                importance=self.calculate_importance(user_input + " " + response.text),
                emotion=response.emotion.value
            )
            
            # Adiciona embedding se disponível
            if hasattr(self, 'memory_encoder'):
                embedding = self.memory_encoder.encode(memory.content)
                self.memory_manager.add_memory(character.name, memory, embedding)
            
            # Atualiza interações
            self.interaction_system.update_recent_interactions(response.text)
            
            # Atualiza relacionamentos se existir narrative_manager
            if hasattr(self, 'narrative_manager'):
                self.narrative_manager.add_character_interaction(
                    character.name,
                    "Usuario",
                    "dialogue", 
                    response.text,
                    response.emotion.value
                )
                
            LogManager.debug(f"Interação registrada para {character.name}", "StoryChat")
            
        except Exception as e:
            LogManager.error(f"Erro ao registrar memória/interação: {e}", "StoryChat")
    
    def setup_device(self):
        LogManager.debug("Configurando dispositivo...", "StoryChat")
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        torch.set_float32_matmul_precision('high')
        LogManager.info(f'Usando dispositivo: {self.device}', "StoryChat")

    def setup_models(self):
        self.whisper_model = WhisperModel("small", 
                                        device="cuda", 
                                        compute_type="float16")
        
        self.setup_tts()
        
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
        self.sentence_transformer.to(self.device)
        
        self.client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        
        self.memory_encoder = self.sentence_transformer

    def setup_tts(self):
        xtts_config = XttsConfig()
        xtts_config.load_json("D:/IA/Speech-to-Speech/speech-to-rag/XTTS-v2/config.json")
        self.xtts_model = Xtts.init_from_config(xtts_config)
        self.xtts_model.load_checkpoint(xtts_config, 
                                      checkpoint_dir="D:/IA/Speech-to-Speech/speech-to-rag/XTTS-v2/", 
                                      eval=True)
        self.xtts_model.to(self.device)
        self.xtts_config = xtts_config

    def setup_audio(self):
        self.output_dir = 'outputs'
        os.makedirs(self.output_dir, exist_ok=True)
    
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
        used_colors = set(char.color for char in self.characters.values())
        unused_colors = [c for c in available_colors if c not in used_colors]
        
        if unused_colors:
            return unused_colors[0]
        return Colors.WHITE  # Cor padrão se todas estiverem em uso
    
    def select_narrator_style(self):
        """Permite ao usuário selecionar o estilo do narrador."""
        print("\nEscolha o estilo do narrador:")
        print("1. Descritivo (Narrador tradicional)")
        print("2. Escrachado (Narrador irreverente e malicioso)")
        
        while True:
            choice = input("\nDigite o número da sua escolha: ").strip()
            if choice == "1":
                self.narrator_system.set_narrator_style(NarratorStyle.DESCRIPTIVE)
                return
            elif choice == "2":
                self.narrator_system.set_narrator_style(NarratorStyle.SASSY)
                return
            else:
                print("Opção inválida. Tente novamente.")

    def load_characters(self):
        """Carrega personagens do arquivo JSON"""
        try:
            self.characters = {}
            LogManager.debug("Iniciando carregamento de personagens", "StoryChat")
            
            if not hasattr(self, 'character_manager'):
                LogManager.error("character_manager não inicializado", "StoryChat")
                return
                
            # Primeiro carrega do arquivo JSON
            characters_data = self.character_manager.characters
            
            # Verifica se temos dados
            if not characters_data:
                LogManager.warning("Nenhum personagem encontrado no arquivo", "StoryChat")
                return
                
            for char_name, config in characters_data.items():
                try:
                    # Verifica dados mínimos necessários
                    if not all(key in config for key in ['voice_file', 'color']):
                        LogManager.error(f"Dados incompletos para {char_name}", "StoryChat")
                        continue
                        
                    LogManager.debug(f"Carregando personagem: {char_name}", "StoryChat")
                    
                    # Cria Character com dados do arquivo
                    self.characters[char_name] = Character(
                        name=char_name,
                        voice_file=config['voice_file'],
                        system_prompt_file=config.get('system_prompt_file', ''),
                        color=config['color']
                    )
                    
                    LogManager.info(f"Carregado personagem: {char_name}", "StoryChat")
                    
                except Exception as char_error:
                    LogManager.error(f"Erro ao carregar {char_name}: {char_error}", "StoryChat")
                    continue
            
            LogManager.debug(f"Total de personagens carregados: {len(self.characters)}", "StoryChat")
            
        except Exception as e:
            LogManager.error(f"Erro ao carregar personagens: {e}", "StoryChat")

    async def analyze_history(self):
        """Analisa o histórico da história em busca de novos personagens e locais"""
        try:
            print(Colors.format_system_message("\nAnalisando histórico da história..."))
            
            entities = await self.entity_manager.analyze_history(
                self.story_context.story_events,  # histórico da história
                list(self.characters.keys()),     # personagens atuais
                self.client                       # cliente LLM
            )
            
            if entities["characters"]:
                print(Colors.format_system_message("\nPersonagens não registrados encontrados:"))
                # Adiciona os personagens detectados à lista de conhecidos
                for i, name in enumerate(entities["characters"], 1):
                    print(f"{i}. {Colors.style_character_name(name, Colors.CYAN)}")
                
                create = input(Colors.format_system_message("\nDeseja criar algum personagem? (número/n): ")).strip()
                if create.isdigit() and 0 < int(create) <= len(entities["characters"]):
                    char_name = entities["characters"][int(create)-1]
                    await self.character_manager.auto_create_character(char_name, self.story_context.get_current_context())
            
            if entities["locations"]:
                print(Colors.format_system_message("\nLugares não registrados encontrados:"))
                for i, name in enumerate(entities["locations"], 1):
                    print(f"{i}. {name}")
                print("\nRegistrando lugares automaticamente...")
                
                for location in entities["locations"]:
                    context = self.story_context.get_current_context()
                    await self.entity_manager.register_location(location, context, self.client)
                print(Colors.format_system_message("Registro de lugares concluído!"))
            
            if not (entities["characters"] or entities["locations"]):
                print(Colors.format_system_message("\nNenhuma nova entidade encontrada no histórico."))
                
        except Exception as e:
            LogManager.error(f"Erro ao analisar histórico: {e}", "StoryChat")
            print(Colors.format_system_message(f"\nErro ao analisar histórico: {e}"))
    
    def update_current_scene(self, text: str):
        """Atualiza informações da cena atual baseado no texto"""
        text_lower = text.lower()
        
        try:
            # Atualiza apenas se for narração
            if "narrador:" in text_lower:
                # Guarda descrição completa
                self.current_scene["description"] = text
                
                # Período do dia
                time_indicators = {
                    "noite": ["noite", "escuro", "escuridão", "lua", "estrelas", "anoitecer"],
                    "tarde": ["tarde", "pôr do sol", "entardecer", "sol poente"],
                    "manhã": ["manhã", "amanhecer", "aurora", "nascer do sol"],
                    "dia": ["dia", "sol", "meio-dia", "solar"]
                }
                
                for period, indicators in time_indicators.items():
                    if any(indicator in text_lower for indicator in indicators):
                        self.current_scene["time"] = period
                        break
                
                # Localização
                locations = {
                    "carro": ["carro", "veículo", "automóvel", "caminhonete", "volante"],
                    "casa": ["casa", "residência", "moradia", "cômodo", "quarto", "sala"],
                    "rua": ["rua", "estrada", "avenida", "calçada", "asfalto"],
                    "floresta": ["floresta", "mata", "bosque", "árvores", "vegetação"],
                    "cidade": ["cidade", "urbano", "prédios", "edifícios"],
                    "campo": ["campo", "rural", "fazenda", "sítio", "rancho"]
                }
                
                for location, indicators in locations.items():
                    if any(indicator in text_lower for indicator in indicators):
                        self.current_scene["location"] = location
                        break
                
                # Atmosfera/Humor
                mood_indicators = {
                    "tenso": ["tenso", "nervoso", "apreensivo", "preocupante", "ansioso", "medo"],
                    "calmo": ["calmo", "tranquilo", "sereno", "pacífico", "silencioso"],
                    "hostil": ["hostil", "perigoso", "ameaçador", "violento", "agressivo"],
                    "misterioso": ["misterioso", "enigmático", "suspeito", "estranho"],
                    "alegre": ["alegre", "festivo", "animado", "descontraído"],
                    "triste": ["triste", "melancólico", "sombrio", "depressivo"],
                    "solitário": ["solitário", "abandonado", "vazio", "deserto"]
                }
                
                for mood, indicators in mood_indicators.items():
                    if any(indicator in text_lower for indicator in indicators):
                        self.current_scene["mood"] = mood
                        break
                
                # Condições ambientais
                weather_conditions = {
                    "chuva": ["chuva", "chuvoso", "gotej", "tempestade"],
                    "vento": ["vento", "ventania", "brisa"],
                    "neblina": ["neblina", "névoa", "nevoeiro", "fumaça"],
                    "quente": ["quente", "calor", "abafado", "sufocante"],
                    "frio": ["frio", "gelado", "congelante", "fresco"]
                }
                
                current_conditions = []
                for condition, indicators in weather_conditions.items():
                    if any(indicator in text_lower for indicator in indicators):
                        current_conditions.append(condition)
                
                if current_conditions:
                    self.current_scene["weather"] = current_conditions
                
                # Detecta personagens presentes na cena
                # Atualiza apenas se encontrar novos personagens
                characters_found = set()
                for character_name in self.characters.keys():
                    if character_name.lower() in text_lower:
                        characters_found.add(character_name)
                
                # Não remove personagens existentes, apenas adiciona novos
                self.current_scene["characters"].update(characters_found)
                
                # Registra elementos importantes mencionados
                important_elements = set()
                key_objects = ["porta", "janela", "arma", "luz", "sombra", "chave", "telefone", 
                            "livro", "carta", "documento", "foto", "computador", "celular"]
                
                for obj in key_objects:
                    if obj in text_lower:
                        important_elements.add(obj)
                
                if important_elements:
                    self.current_scene["elements"] = important_elements
                
                LogManager.debug(f"Cena atualizada: {self.current_scene}", "StoryChat")
                
        except Exception as e:
            LogManager.error(f"Erro ao atualizar cena: {e}", "StoryChat")

    async def check_for_new_characters(self, text: str):
        """Verifica e processa novos personagens mencionados no texto"""
        try:
            # Obtém personagens do texto
            new_chars, _ = await self.entity_manager.analyze_text_for_entities(text, self.client)
            
            # Filtra apenas personagens realmente novos
            new_chars = [char for char in new_chars 
                        if char not in self.characters and 
                        char not in self.character_manager.known_names]
            
            # Cria os personagens automaticamente
            for char_name in new_chars:
                await self.character_manager.auto_create_character(char_name, text)
                    
            return new_chars
                    
        except Exception as e:
            LogManager.error(f"Erro ao verificar novos personagens: {e}", "StoryChat")
            return []
        
    async def create_character(self, name: str, voice_file: str = None, avatar_file: str = None):
        """Cria um novo personagem com perfil detalhado"""
        try:
            # Primeiro analisa a história para criar o perfil
            profile = await self.profile_manager.analyze_story_for_character(
                name, 
                self.story_context.story_events,
                self.client
            )
            
            if not profile:
                LogManager.warning(f"Não foi possível criar perfil para {name}", "StoryChat")
                return False

            # Cria o personagem no sistema existente
            success = await self.character_manager.add_character(
                name, self.story_context.get_current_context(), 
                self.client, voice_file, avatar_file
            )
            
            if success:
                # Recarrega personagens
                self.load_characters()
                
                # Notifica interface/terminal
                message = f"Personagem {name} criado com sucesso!\n\nPerfil:\n{self.profile_manager.get_profile_for_prompt(name)}"
                
                if self.gui_mode and self.event_manager:
                    await self.event_manager.emit(StoryEvent(
                        type=EventType.CHARACTER_CREATED,
                        sender="Sistema",
                        data={
                            "text": message,
                            "is_user": False,
                            "avatar_path": "avatars/sistema.png",
                            "should_scroll": True
                        }
                    ))
                else:
                    print(f"\n{Colors.GREEN}{message}{Colors.RESET}")
                    
                return True
                
        except Exception as e:
            LogManager.error(f"Erro ao criar personagem: {e}", "StoryChat")
            return False
        
    async def list_characters(self):
        try:
            characters = self.character_manager.characters
            player_name = None
            if hasattr(self, 'player') and self.player.background:
                player_name = self.player.background.name

            if not characters and not player_name:
                print(Colors.format_system_message("\nNenhum personagem criado ainda."))
                return

            print(Colors.format_system_message("\n=== Personagens ==="))
            
            # Lista o personagem do jogador primeiro, se existir
            if player_name:
                voice_info = "Sem voz" if not hasattr(self.player, 'voice_file') else os.path.basename(self.player.voice_file)
                print(f"1. {player_name} (Você) ({voice_info})")
                start_idx = 2
            else:
                start_idx = 1

            # Lista os demais personagens
            for i, (name, data) in enumerate(characters.items(), start_idx):
                star = "⭐" if data.get('is_favorite') else "  "
                voice = os.path.basename(data['voice_file']) if data.get('voice_file') else "Sem voz"
                print(f"{i}. {star} {name} ({voice})")

            action = input("\nDigite número para ver detalhes/modificar ou ENTER para sair: ").strip()
            if action.isdigit():
                idx = int(action)
                if idx == 1 and player_name:  # Mostra detalhes do jogador
                    await self._show_player_details()
                elif idx > 1 and idx <= len(characters) + (1 if player_name else 0):
                    char_name = list(characters.keys())[idx - (2 if player_name else 1)]
                    await self._show_character_details(char_name)

        except Exception as e:
            LogManager.error(f"Erro ao listar personagens: {e}", "StoryChat")

    async def _show_player_details(self):
        """Mostra detalhes do personagem do jogador"""
        if not self.player or not self.player.background:
            return
            
        bg = self.player.background
        print(f"\n=== {bg.name} (Seu personagem) ===")
        print(f"Gênero: {bg.gender}")
        if bg.age:
            print(f"Idade: {bg.age}")
        if bg.occupation:
            print(f"Ocupação: {bg.occupation}")
        if bg.background_story:
            print(f"História: {bg.background_story}")
        if bg.personality_traits:
            print(f"Personalidade: {', '.join(bg.personality_traits)}")
        if bg.goals:
            print(f"Objetivos: {', '.join(bg.goals)}\n")

    async def _show_character_details(self, char_name: str):
        """Mostra detalhes do personagem e oferece opções de modificação"""
        char_data = self.character_manager.characters[char_name]
        profile = self.profile_manager.profiles.get(char_name)
        
        print(f"\n=== {char_name.capitalize()} ===")
        if profile:
            print(f"Ocupação: {profile.basic_info.get('occupation', 'Não definida')}")
            print(f"Aparência: {profile.basic_info.get('appearance', 'Não definida')}")
            print(f"Personalidade: {', '.join(profile.personality.get('traits', []))}")
            print(f"História: {profile.background.get('history', 'Não definida')}\n")
            print(f"Estado atual: {', '.join(profile.dynamic_state.get('current_emotions', []))}")
            print(f"Objetivos: {', '.join(profile.dynamic_state.get('current_goals', []))}")
        
        print("\nOpções:")
        print("1. Trocar voz")
        print("2. Favoritar/Desfavoritar")
        print("3. Voltar")
        
        choice = input("\nEscolha uma opção: ").strip()
        if choice == "1":
            new_voice = await self._select_voice_file(char_name)
            if new_voice:
                char_data['voice_file'] = new_voice
                self.character_manager.save_characters()
                # Testa nova voz
                test_char = Character(char_name, new_voice, "", char_data.get('color', Colors.WHITE))
                response = await self.generate_response(
                    f"Olá, eu sou {char_name}. Esta é minha nova voz.",
                    test_char
                )
                if response:
                    await self.process_response(response, test_char, "")
        elif choice == "2":
            char_data['is_favorite'] = not char_data.get('is_favorite', False)
            self.character_manager.save_characters()
            status = "adicionado aos" if char_data['is_favorite'] else "removido dos"
            print(Colors.format_system_message(f"\n{char_name.capitalize()} {status} favoritos!"))
        
    async def reset_story(self, keep_favorites: bool = True):
        """Reseta a história mantendo personagens favoritos se solicitado"""
        try:
            LogManager.debug("Iniciando processo de reset", "StoryChat")
            print(Colors.format_system_message("\nATENÇÃO: Esta ação irá:"))
            print("- Apagar todos os personagens não favoritados")
            print("- Limpar todo histórico de interações")
            print("- Remover todos os lugares")
            print("- Resetar o contexto da história")
            
            confirm = input("\nConfirma reset? (s/n): ").lower().strip()
            if confirm != 's':
                return False

            # Backup de personagens favoritos
            favorite_chars = {}
            if keep_favorites and hasattr(self.character_manager, 'characters'):
                for name, char_data in self.character_manager.characters.items():
                    if char_data.get('is_favorite') and not char_data.get('is_player', False):
                        favorite_chars[name] = char_data.copy()
                        LogManager.debug(f"Personagem {name} marcado para backup", "StoryChat")

            # Primeiro, fecha todas as conexões de banco de dados
            if hasattr(self, 'memory_manager'):
                self.memory_manager.cleanup()
                LogManager.debug("Cleanup de memory_manager realizado com sucesso", "StoryChat")

            if hasattr(self, 'story_context'):
                self.story_context.cleanup()
                LogManager.debug("Cleanup de story_context realizado com sucesso", "StoryChat")

            if hasattr(self, 'narrative_manager') and hasattr(self.narrative_manager, 'cleanup'):
                self.narrative_manager.cleanup()
                LogManager.debug("Cleanup de narrative_manager realizado com sucesso", "StoryChat")

            if hasattr(self, 'audio_processor'):
                self.audio_processor.cleanup()
                LogManager.debug("Cleanup de audio_processor realizado com sucesso", "StoryChat")

            # Força coleta de lixo e aguarda
            import gc
            gc.collect()
            await asyncio.sleep(0.5)

            # Remove os arquivos de banco de dados
            dbs = ['character_memories.db', 'story_history.db', 'narrative_history.db']
            for db in dbs:
                if os.path.exists(db):
                    try:
                        os.remove(db)
                        LogManager.info(f"Banco de dados {db} removido com sucesso", "StoryChat")
                    except Exception as e:
                        LogManager.warning(f"Erro ao remover {db}: {e}", "StoryChat")
                        # Tenta forçar fechamento de conexões
                        if 'character_memories.db' in db:
                            self.memory_manager = None
                        await asyncio.sleep(0.1)
                        try:
                            os.remove(db)
                        except:
                            pass

            # Limpa o personagem do jogador
            self.player = None

            # Backup e recriação do arquivo characters.json
            characters_file = "characters.json"
            try:
                if os.path.exists(characters_file):
                    os.remove(characters_file)
                    LogManager.info("Arquivo characters.json removido", "StoryChat")

                # Recria o arquivo com os favoritos ou vazio
                with open(characters_file, 'w', encoding='utf-8') as f:
                    if keep_favorites and favorite_chars:
                        json.dump(favorite_chars, f, indent=2, ensure_ascii=False)
                    else:
                        json.dump({}, f)
                    LogManager.info("Novo characters.json criado", "StoryChat")

            except Exception as e:
                LogManager.error(f"Erro ao manipular characters.json: {e}", "StoryChat")

            # Reinicializa componentes
            self.story_context = StoryContext(llm_client=self.client)
            self.memory_manager = MemoryManager()
            self.character_manager = DynamicCharacterManager(llm_client=self.client)

            # Configura banco de dados
            await self.story_context.setup_database()

            # Recarrega personagens somente após tudo estar configurado
            self.load_characters()

            LogManager.info("Reset concluído com sucesso", "StoryChat")
            
            # Inicia nova história com tratamento de erro
            try:
                await self.initialize_story()
                return True
            except Exception as init_error:
                LogManager.error(f"Erro ao inicializar nova história: {init_error}", "StoryChat")
                return False

        except Exception as e:
            LogManager.error(f"Erro ao resetar história: {e}", "StoryChat")
            return False

    def calculate_importance(self, content: str) -> float:
        """Calcula a importância de uma memória baseada no conteúdo."""
        importance_keywords = ['importante', 'crucial', 'nunca', 'sempre', 'amo', 'odeio']
        emotion_keywords = ['feliz', 'triste', 'bravo', 'animado', 'preocupado']
        
        base_importance = 0.5
        for keyword in importance_keywords:
            if keyword in content.lower():
                base_importance += 0.1
        for keyword in emotion_keywords:
            if keyword in content.lower():
                base_importance += 0.05
                
        return min(1.0, base_importance)
    
    def detect_input_type(self, user_input: str) -> NarratorType:
        """Detecta se o input deve ser tratado como narração, diálogo direto, ou misto."""
        try:
            input_lower = user_input.lower()
            action_info = InteractionManager.parse_action(user_input)
            
            # Detecta menção direta a personagem
            character_mentioned = False
            for char_name in self.characters.keys():
                if char_name.lower() in input_lower:
                    character_mentioned = True
                    # Se tem interrogação/exclamação junto com nome do personagem,
                    # é definitivamente uma fala direcionada ao personagem
                    if "?" in user_input or "!" in user_input:
                        LogManager.debug("Detectado tipo PERSONAGEM (diálogo direto com personagem)", "StoryChat")
                        return NarratorType.CHARACTER
            
            # Indicadores de diálogo direto
            dialog_indicators = [
                "digo", "falo", "respondo", "pergunto",
                "exclamo", "sussurro", "grito", "chamo"
            ]
            
            # Indicadores fortes de diálogo direto
            strong_dialog_indicators = [
                "você", "seu", "sua", "te", 
                "olá", "oi", "ei",
                "me", "meu", "minha"
            ]
            
            # Verifica diferentes tipos de aspas
            has_quotes = any(quote in user_input for quote in ['"', '"', '"', "'"])
            
            # Indicadores de diálogo
            has_dialog = (
                has_quotes or
                any(indicator in input_lower for indicator in dialog_indicators) or
                character_mentioned  # Considera menção ao personagem como indicador de diálogo
            )
            
            # Indicadores fortes de diálogo direto
            has_strong_dialog = any(word in input_lower for word in strong_dialog_indicators)
            
            # Verifica ações
            has_action = (
                action_info['movement'] or 
                action_info['interaction'] or
                any(verb in input_lower for verb in ["ando", "vou", "pego", "abro", "fecho"])
            )
            
            # Lógica de decisão
            if has_strong_dialog or (character_mentioned and has_dialog):
                if has_action:
                    LogManager.debug("Detectado tipo MISTO (diálogo direto + ação)", "StoryChat")
                    return NarratorType.CHARACTER_WITH_NARRATION
                LogManager.debug("Detectado tipo PERSONAGEM (diálogo direto)", "StoryChat")
                return NarratorType.CHARACTER
                
            if has_action:
                if has_dialog:
                    LogManager.debug("Detectado tipo MISTO (ação + diálogo)", "StoryChat")
                    return NarratorType.CHARACTER_WITH_NARRATION
                LogManager.debug("Detectado tipo NARRADOR (apenas ação)", "StoryChat")
                return NarratorType.NARRATOR
            
            if has_dialog:
                LogManager.debug("Detectado tipo PERSONAGEM (diálogo indireto)", "StoryChat")
                return NarratorType.CHARACTER
                
            LogManager.debug("Detectado tipo NARRADOR (default)", "StoryChat")
            return NarratorType.NARRATOR
                    
        except Exception as e:
            LogManager.error(f"Erro na detecção de tipo: {e}", "StoryChat")
            return NarratorType.NARRATOR

    def update_story_context(self, user_input: str, narrator_response: str):
        """Atualiza o contexto da história baseado nas interações"""
        if "noite" in narrator_response.lower():
            self.story_context.time_of_day = "noite"
        elif "tarde" in narrator_response.lower():
            self.story_context.time_of_day = "tarde"
        elif "manhã" in narrator_response.lower():
            self.story_context.time_of_day = "manhã"
        
        location_keywords = ["sala", "quarto", "cozinha", "jardim", "corredor"]
        for location in location_keywords:
            if location in narrator_response.lower():
                self.story_context.current_location = location
                break
        
        self.story_context.last_action = user_input
        self.story_context.scene_description = narrator_response

    async def process_character_reactions(self, trigger_text: str, trigger_emotion: EmotionType, 
                                     current_speaker: Optional[str] = None):
        try:
            print("\nProcessando reações dos personagens...")
            relevant_chars = self.interaction_system.get_relevant_characters(
                self.story_context, current_speaker
            )
            
            for character in relevant_chars:
                if self.interaction_system.should_character_react(character, self.story_context, trigger_emotion):
                    reaction_prompt = self.interaction_system.generate_reaction_prompt(
                        character, self.story_context, trigger_text, trigger_emotion
                    )
                    
                    try:
                        response = await self.generate_response(reaction_prompt, character)
                        if response:
                            print(f"\n{character.color}{character.name} reage: {Colors.RESET}")
                            await self.audio_processor.synthesize_speech(response, character)
                    except Exception as e:
                        print(f"\nErro ao processar reação do personagem {character.name}: {e}")
                        
        except Exception as e:
            print(f"\nErro ao processar reações dos personagens: {e}")
            import traceback
            traceback.print_exc()

    async def process_narrator_intervention(self):
        """Processa intervenções automáticas do narrador."""
        intervention_prompt = self.narrator_system.generate_intervention(self.story_context)
        if intervention_prompt:
            narrator_profile = self.narrator_system.get_current_profile()
            narrator = Character(
                name="",  # Nome vazio para não aparecer "Narrador:"
                voice_file=narrator_profile.voice_file,
                system_prompt_file="",
                color=Colors.YELLOW
            )
            
            response = await self.generate_response(intervention_prompt, narrator, temperature=0.8)
            if response:
                await self.audio_processor.synthesize_speech(response, narrator)

    def _verify_response_consistency(self, response: str, character_profile, last_event: str) -> bool:
        """Verifica se a resposta é consistente com o estado do personagem"""
        try:
            verify_prompt = f"""IMPORTANTE: Responda apenas 'sim' ou 'não'.
            
            Analise se esta resposta é consistente com o estado atual do personagem:

            Estado atual do personagem:
            - Nome: {character_profile.name}
            - Situação: {character_profile.background['history']}
            - Estado emocional: {', '.join(character_profile.dynamic_state['current_emotions'])}
            - Medos: {', '.join(character_profile.personality['fears'])}
            - Objetivos: {', '.join(character_profile.dynamic_state['current_goals'])}

            Último evento na história: {last_event}

            Resposta a ser verificada: {response}

            A resposta é consistente com:
            1. A situação atual do personagem?
            2. O estado emocional estabelecido?
            3. O último evento da história?
            4. Os medos e objetivos do personagem?

            Responda apenas 'sim' ou 'não'."""

            result = self.client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=[
                    {"role": "system", "content": "Você é um verificador de consistência que responde apenas 'sim' ou 'não'."},
                    {"role": "user", "content": verify_prompt}
                ],
                temperature=0.3,
                max_tokens=10
            )

            is_consistent = result.choices[0].message.content.strip().lower() == 'sim'
            if not is_consistent:
                LogManager.warning(f"Resposta inconsistente detectada para {character_profile.name}", "StoryChat")
                LogManager.debug(f"Resposta inconsistente: {response}", "StoryChat")
                LogManager.debug(f"Último evento: {last_event}", "StoryChat")
            return is_consistent

        except Exception as e:
            LogManager.error(f"Erro ao verificar consistência: {e}", "StoryChat")
            return True  # Em caso de erro, permite a resposta
    
    async def generate_response(self, user_input: str, character: Optional[Character] = None, temperature: float = 0.7) -> Optional[EmotionalResponse]:
        """Gera uma resposta emocional baseada na entrada do usuário e no personagem."""
        LogManager.debug(f"Gerando resposta para entrada: {user_input[:50]}...", "StoryChat")
        try:
            # Primeiro registra a interação no sistema de interações
            self.interaction_system.update_recent_interactions(user_input)

            # Detecta e tenta criar novos personagens automaticamente
            try:
                new_chars, _ = await self.entity_manager.analyze_text_for_entities(user_input, self.client)
                if new_chars:
                    for char_name in new_chars:
                        if char_name not in self.characters and char_name not in self.character_manager.known_names:
                            LogManager.info(f"Novo personagem detectado: {char_name}", "StoryChat")
                            await self.character_manager.auto_create_character(char_name, self.story_context.get_current_context())
            except Exception as e:
                LogManager.error(f"Erro ao analisar entidades: {e}", "EntityManager")

            # Verifica se o narrative_manager existe e está inicializado
            if not hasattr(self, 'narrative_manager') or self.narrative_manager is None:
                self.narrative_manager = NarrativeHistoryManager()

            # Detecta tipo de input e emoção
            input_type = self.detect_input_type(user_input)
            LogManager.debug(f"Tipo de input detectado: {input_type}", "StoryChat")
            user_emotion, user_intensity = self.emotion_analyzer.analyze_text(user_input)

            # Configura personagem e contexto
            if character and not character.name:  # Caso Narrador
                LogManager.debug("Processando como Narrador", "StoryChat")
                input_type = NarratorType.NARRATOR
                narrator_profile = self.narrator_system.get_current_profile()
                character = Character(
                    name="",
                    voice_file=narrator_profile.voice_file,
                    system_prompt_file="prompts/narrator_prompt.txt",
                    color=Colors.YELLOW
                )
                context_prompt = self._create_narrator_context(user_input)
            else:  # Caso Personagem
                LogManager.debug(f"Iniciando processamento para {character.name}", "StoryChat")
                char_info = self.character_manager.get_character_info(character.name)
                LogManager.debug(f"Informações encontradas: {bool(char_info)}", "StoryChat")

                if char_info:
                    LogManager.debug(f"Perfil existente no character_manager: {char_info.get('profile', {}).get('name')}", "StoryChat")

                # Garante que temos o perfil
                profile = self.profile_manager.get_or_create_profile(character.name)
                LogManager.debug(f"Perfil obtido: {bool(profile)}", "StoryChat")

                if profile:
                    LogManager.debug(f"Detalhes do perfil: occupation={profile.basic_info.get('occupation')}", "StoryChat")

                # Atualiza o perfil com o contexto atual
                LogManager.debug(f"Atualizando perfil com contexto", "StoryChat")
                await self.profile_manager.update_profile_with_context(
                    character.name, 
                    self.story_context,
                    self.client
                )

                context_prompt = self._create_character_context(character, input_type)

            # Prepara saída colorida para terminal
            output_color = Colors.YELLOW if input_type == NarratorType.NARRATOR else (character.color if character else Colors.RESET)
            if not self.gui_mode:
                print(f"\n{output_color}", end='')

            try:
                # Prepara mensagens para a LLM
                messages = [
                    {"role": "system", "content": context_prompt},
                    {"role": "user", "content": user_input}
                ]

                # Gera resposta da LLM
                final_response = await self._generate_llm_response(
                    messages, 
                    temperature,
                    600 if character and character.name else 800,  # max_tokens ajustado por tipo
                    character,
                    not self.gui_mode
                )

                if not final_response:
                    return None

                # Verifica consistência da resposta
                if character and character.name and hasattr(self, 'profile_manager'):
                    profile = self.profile_manager.profiles.get(character.name)
                    if profile and not self._verify_response_consistency(
                        final_response, profile, self.story_context.story_events[-1]['content']
                    ):
                        return await self.generate_response(user_input, character, temperature + 0.1)

                # Processa emoções da resposta
                response_emotion, response_intensity = self.emotion_analyzer.analyze_text(final_response)
                voice_params = self.emotion_analyzer.get_voice_parameters(response_emotion, response_intensity)

                # Registra interação/eventos
                await self._register_interaction(
                    character,
                    final_response,
                    input_type,
                    response_emotion
                )

                # Cria e retorna resposta emocional
                emotional_response = EmotionalResponse(
                    text=final_response,
                    emotion=response_emotion,
                    params=voice_params
                )

                LogManager.info("Resposta gerada com sucesso", "StoryChat")
                return emotional_response

            finally:
                if not self.gui_mode:
                    print(Colors.RESET)

        except Exception as e:
            LogManager.error(f"Erro ao gerar resposta: {e}", "StoryChat")
            return None
        
    def _create_narrator_context(self, user_input: str) -> str:
        """Cria contexto enriquecido para narração"""
        narrator_prompt = StoryPromptManager.create_narrator_prompt()
        context_prompt = StoryPromptManager.create_character_context(self.story_context)
        
        # Obtém perfis dos personagens presentes
        character_profiles = ""
        for char_name in self.story_context.present_characters:
            if char_name in self.characters:
                profile = self.profile_manager.get_or_create_profile(char_name)
                if profile:
                    character_profiles += f"""
                    {char_name.upper()}:
                    - Estado atual: {', '.join(profile.dynamic_state['current_emotions'])}
                    - Objetivos: {', '.join(profile.dynamic_state['current_goals'])}
                    - História: {profile.background['history']}
                    """
        
        # Obtém últimas interações relevantes
        recent_events = self.story_context.story_events[-5:]
        events_context = "\n".join([
            f"[{event['type']}] {event['character']}: {event['content']}"
            for event in recent_events if event['content']
        ])

        # Contexto da cena atual
        scene_context = f"""
        CONTEXTO CRUCIAL DA CENA:
        Local: {self.story_context.current_location}
        Horário: {self.story_context.time_of_day}
        Atmosfera: {self.current_scene.get('mood', 'neutra')}
        
        PERSONAGENS PRESENTES:
        {character_profiles}
        
        ÚLTIMOS EVENTOS:
        {events_context}
        
        DIRETRIZES CRÍTICAS:
        1. Mantenha absoluta consistência com o estado emocional dos personagens
        2. Considere os objetivos atuais de cada personagem presente
        3. Referencie eventos anteriores quando relevante
        4. Descreva reações físicas e emocionais dos personagens
        5. Mantenha a tensão e atmosfera estabelecida
        6. Use os sentidos para criar imersão (visão, sons, cheiros, etc.)
        7. Nunca contradiga eventos anteriores
        8. Mantenha o ritmo da narrativa
        """

        # Adiciona contexto do jogador se existir
        if hasattr(self, 'player') and self.player.background:
            scene_context = f"{self.player.get_context_for_llm()}\n\n{scene_context}"

        # Registra input do usuário
        self.story_context.add_event(
            event_type='user_input',
            content=user_input,
            character='Você'
        )
        
        return f"{narrator_prompt}\n\n{scene_context}\n\n{context_prompt}"

    def _create_character_context(self, character: Character, input_type: NarratorType) -> str:
        """Cria contexto baseado no tipo de interação (narrador/personagem/misto)"""
        try:
            # Obtém dados do jogador
            player_context = ""
            player_name = None
            if self.player and self.player.background:
                player_name = self.player.background.name
                player_context = f"""
                INFORMAÇÕES SOBRE O INTERLOCUTOR (IMPORTANTE):
                Nome: {player_name}
                Gênero: {self.player.background.gender}
                Idade: {self.player.background.age if self.player.background.age else "Desconhecida"}
                Ocupação: {self.player.background.occupation if self.player.background.occupation else "Desconhecida"}
                Background: {self.player.background.background_story if self.player.background.background_story else "Desconhecido"}
                Objetivos: {', '.join(self.player.background.goals) if self.player.background.goals else "Desconhecidos"}
                """
            else:
                player_context = "IMPORTANTE: Você não conhece seu interlocutor. Pergunte quem ele é."

            # Obtém perfil do personagem
            profile = None
            if hasattr(self, 'profile_manager'):
                profile = self.profile_manager.get_or_create_profile(character.name)

            # Cria contexto do perfil do personagem
            profile_context = ""
            if profile:
                profile_context = f"""
                CONTEXTO VITAL DO PERSONAGEM (MANTENHA CONSISTÊNCIA ABSOLUTA):
                
                Nome: {profile.name}
                Ocupação: {profile.basic_info.get('occupation', 'Desconhecida')}
                Situação atual: {profile.background.get('history', '')}
                Estado emocional base: {', '.join(profile.dynamic_state.get('current_emotions', []))}
                Objetivos atuais: {', '.join(profile.dynamic_state.get('current_goals', []))}
                Personalidade: {', '.join(profile.personality.get('traits', []))}
                Medos: {', '.join(profile.personality.get('fears', []))}
                """

            # Obtém eventos recentes
            recent_context = ""
            if hasattr(self, 'story_context') and hasattr(self.story_context, 'story_events'):
                recent_events = self.story_context.story_events[-5:] if self.story_context.story_events else []
                if recent_events:
                    recent_context = "\n".join([
                        f"[{event['type']}] {event.get('character', 'Unknown')}: {event.get('content', '')}"
                        for event in recent_events if event.get('content')
                    ])

            # Monta o contexto completo
            return f"""
            {LANGUAGE_PROMPT}

            CONTEXTO DOS PERSONAGENS:
            1. VOCÊ ({character.name}):
            {profile_context}

            2. INTERLOCUTOR ({player_name if player_name else "Usuario"}):
            {player_context}

            EVENTOS RECENTES:
            {recent_context}

            INSTRUÇÕES CRÍTICAS:
            1. Reaja considerando TODO o histórico de interações
            2. Mantenha TOTAL consistência com sua situação atual
            3. Se estiver presa, ameaçada ou em perigo, DEVE agir adequadamente
            4. Considere suas emoções e as do interlocutor
            5. Respeite seus objetivos e medos estabelecidos
            6. Mantenha suas respostas com no máximo 200 caracteres
            7. NUNCA ignore seu background e situação atual
            8. Aja de acordo com o último evento registrado
            """

        except Exception as e:
            LogManager.error(f"Erro ao criar contexto: {e}", "StoryChat")
            return LANGUAGE_PROMPT  # Retorna pelo menos o prompt de linguagem em caso de erro

    async def _generate_llm_response(self, messages: list, temperature: float, 
                                    max_tokens: int, character: Character, 
                                    print_stream: bool = True) -> str:
        """Gera resposta da LLM com tratamento de erros melhorado"""
        max_retries = 3  # Número máximo de tentativas
        retry_delay = 1  # Segundos entre tentativas
        final_response = ""

        for attempt in range(max_retries):
            try:
                stream = self.client.chat.completions.create(
                    model="llama-2-13b-chat",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                if not stream:
                    raise ValueError("Stream retornou vazio")
                
                for chunk in stream:
                    if not chunk or not chunk.choices or not chunk.choices[0].delta:
                        continue
                        
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        clean_content = content.replace('033', '').replace('[95m', '')
                        if print_stream:
                            print(f"{clean_content}", end='', flush=True)
                        final_response += clean_content
                
                if final_response.strip():  # Verifica se temos uma resposta válida
                    return final_response.strip()
                
                # Se chegou aqui, a resposta estava vazia
                raise ValueError("Resposta da LLM estava vazia")

            except Exception as e:
                LogManager.error(f"Tentativa {attempt + 1} falhou: {str(e)}", "StoryChat")
                if attempt < max_retries - 1:  # Se não for a última tentativa
                    import asyncio
                    await asyncio.sleep(retry_delay)  # Espera antes de tentar novamente
                    LogManager.info(f"Tentando novamente ({attempt + 2}/{max_retries})...", "StoryChat")
                else:
                    raise Exception("Todas as tentativas de gerar resposta falharam") from e

        return ""  # Nunca deve chegar aqui devido ao raise acima


    async def _register_interaction(self, character: Character, response: str, 
                                input_type: NarratorType, emotion: EmotionType):
        """Registra interação no sistema"""
        if character and character.name:
            self.narrative_manager.add_character_interaction(
                character.name,
                "Usuario",
                "dialogue",
                response,
                emotion.value
            )
        else:
            self.narrative_manager.add_narrative_event(
                "narration",
                response,
                self.story_context.current_location,
                self.story_context.present_characters,
                self.story_context.scene_description,
                []
            )
        
        # Registra evento
        event_type = 'narration' if input_type == NarratorType.NARRATOR else 'dialogue'
        self.story_context.add_event(
            event_type=event_type,
            content=response,
            character=character.name if character else 'Narrador'
        )
        
    async def handle_character_creation(self, name: str):
        """Manipula criação de personagem via terminal"""
        if name not in self.character_manager.known_names:
            print(Colors.format_system_message(f"\nPersonagem '{name}' não foi detectado na história."))
            return

        print(Colors.format_system_message(f"\nCriando perfil para {Colors.style_character_name(name, Colors.CYAN)}..."))
        context = self.story_context.get_current_context()
        profile = await self.character_manager.generate_character_profile(name, context, self.client)
        
        if profile:
            print("\nPerfil gerado:")
            for key, value in profile.items():
                print(f"{Colors.WHITE}{key}: {value}{Colors.RESET}")
            
            # Nova confirmação
            proceed = input(f"\n{Colors.WHITE}Deseja prosseguir com a criação do personagem? (s/n): {Colors.RESET}").lower()
            if not proceed.startswith('s'):
                print(Colors.format_system_message("Criação de personagem cancelada."))
                return

            # Seleção de arquivo de voz usando GUI
            want_voice = input(f"{Colors.WHITE}Deseja adicionar um arquivo de voz? (s/n): {Colors.RESET}").lower().startswith('s')
            voice_file = None
            
            if want_voice:
                try:
                    from PyQt6.QtWidgets import QFileDialog, QApplication
                    
                    if QApplication.instance() is None:
                        app = QApplication([])
                    
                    dialog = QFileDialog()
                    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
                    dialog.setNameFilter("Audio Files (*.mp3 *.wav)")
                    dialog.setWindowTitle("Selecione o arquivo de voz")
                    
                    if dialog.exec() == QFileDialog.DialogCode.Accepted:
                        voice_file = dialog.selectedFiles()[0]
                        print(f"Arquivo selecionado: {voice_file}")
                    else:
                        print(Colors.format_system_message("Nenhum arquivo selecionado."))
                except Exception as e:
                    LogManager.error(f"Erro ao abrir seletor de arquivo: {e}", "StoryChat")
                    print(Colors.format_system_message("Erro ao selecionar arquivo. Continuando sem voz."))

            print(Colors.format_system_message("\nCriando personagem..."))
            success = await self.character_manager.add_character(
                name, context, self.client, voice_file
            )
            
            if success:
                print(Colors.format_system_message(f"Personagem {Colors.style_character_name(name, Colors.CYAN)} criado com sucesso!"))
                # Recarrega personagens
                self.load_characters()
            else:
                print(Colors.format_system_message("Erro ao criar personagem."))
            
    async def show_context(self):
        """Mostra o contexto atual e o resumo da história."""
        try:
            LogManager.debug("Gerando resumo do contexto", "StoryChat")
            summary = await self.story_context.generate_narrative_summary(self.client)
            print(f"\n{Colors.YELLOW}{summary}{Colors.RESET}\n")
            return summary
            
        except Exception as e:
            LogManager.error(f"Erro ao mostrar contexto: {e}", "StoryChat")
            print(f"\nErro ao mostrar contexto: {e}")
            return "Erro ao gerar resumo da história."
        
    def show_locations(self):
        """Mostra informações sobre lugares registrados"""
        try:
            if not self.entity_manager.locations:
                print(Colors.format_system_message("\nNenhum lugar registrado ainda."))
                return

            print(Colors.format_system_message("\n=== Lugares Registrados ==="))
            for name, info in self.entity_manager.locations.items():
                print(f"\n{Colors.BLUE}{name}{Colors.RESET}")
                if "type" in info:
                    print(f"Tipo: {info['type']}")
                if "description" in info:
                    print(f"Descrição: {info['description']}")
                if "notable_features" in info and info["notable_features"]:
                    print(f"Características: {', '.join(info['notable_features'])}")

        except Exception as e:
            LogManager.error(f"Erro ao mostrar lugares: {e}", "StoryChat")
            print(Colors.format_system_message(f"\nErro ao listar lugares: {e}"))

    async def load_full_context(self):
        """Carrega e apresenta todo o contexto da história"""
        try:
            print(Colors.format_system_message("\n=== Carregando Contexto da História ==="))
            
            # Carrega resumo do contexto atual
            context_summary = await self.story_context.generate_narrative_summary(self.client)
            if context_summary:
                print(context_summary)
            
            # Carrega lugares
            if self.entity_manager.locations:
                print(Colors.format_system_message("\nLugares Conhecidos:"))
                for name, info in self.entity_manager.locations.items():
                    print(f"\n{Colors.BLUE}{name}{Colors.RESET}")
                    if "description" in info:
                        print(f"  {info['description']}")

            # Carrega personagens e suas últimas interações
            if self.characters:
                print(Colors.format_system_message("\nPersonagens Ativos:"))
                for char_name, character in self.characters.items():
                    memories = self.memory_manager.get_formatted_memories(char_name)
                    if hasattr(character, 'profile'):
                        profile = character.profile
                        print(f"\n{Colors.style_character_name(char_name, character.color)}")
                        if hasattr(profile, 'basic_info'):
                            print(f"  {profile.basic_info.get('occupation', '')}")
                            print(f"  {profile.background.get('history', '')}")
                    if memories:
                        print("  Última interação:")
                        last_memory = memories.split('\n')[-1]
                        print(f"  {last_memory}")

            # Carrega últimos eventos
            recent_events = self.story_context.story_events[-5:]  # últimos 5 eventos
            if recent_events:
                print(Colors.format_system_message("\nÚltimos Acontecimentos:"))
                for event in recent_events:
                    if 'content' in event:
                        print(f"\n- {event['content']}")

            # Gera contexto completo para a LLM
            self.current_context = {
                "locations": self.entity_manager.locations,
                "characters": {name: self.profile_manager.get_profile_for_prompt(name) 
                            for name in self.characters},
                "recent_events": recent_events,
                "current_scene": self.story_context.get_current_context()
            }

            print(Colors.format_system_message("\nContexto carregado com sucesso!"))
            
        except Exception as e:
            LogManager.error(f"Erro ao carregar contexto: {e}", "StoryChat")
            print(Colors.format_system_message(f"\nErro ao carregar contexto: {e}"))

    def _format_character_context(self, character: Character, profile: Optional[dict], 
                                user_emotion: EmotionType, user_intensity: float,
                                story_context: str, system_prompt: str, 
                                memory_context: str, relationship_history: str) -> str:
        """Formata o contexto completo para diálogo com personagem."""
        
        # Formata contexto do perfil se existir
        if profile:
            profile_context = f"""
            CONTEXTO VITAL DO PERSONAGEM (MANTENHA CONSISTÊNCIA ABSOLUTA):
            
            Você é {profile.name}
            Ocupação: {profile.basic_info['occupation']}
            Situação atual: {profile.background['history']}
            Estado emocional base: {', '.join(profile.dynamic_state['current_emotions'])}
            Objetivos atuais: {', '.join(profile.dynamic_state['current_goals'])}
            
            Sua personalidade é definida por: {', '.join(profile.personality['traits'])}
            Seus medos são: {', '.join(profile.personality['fears'])}
            """
        else:
            profile_context = ""

        # Adiciona contexto do jogador
        player_context = ""
        if hasattr(self, 'player') and self.player.background:
            player_context = self.player.get_context_for_llm()

        # Monta o contexto completo
        return f"""
        {LANGUAGE_PROMPT}

        CONTEXTO DOS PERSONAGENS:
        1. VOCÊ ({character.name}):
        {profile_context}
        Estado atual: {profile.dynamic_state['current_emotions'][-1] if profile and profile.dynamic_state['current_emotions'] else 'Neutro'}
        Objetivos: {', '.join(profile.dynamic_state['current_goals']) if profile and profile.dynamic_state.get('current_goals') else 'Nenhum'}

        2. INTERLOCUTOR ({self.player.background.name if hasattr(self, 'player') and self.player.background else "Usuario"}):
        {player_context}

        HISTÓRICO DE INTERAÇÕES:
        {relationship_history}

        ESTADO EMOCIONAL ATUAL:
        - Usuário: {user_emotion.value} (intensidade: {user_intensity:.2f})
        - Você: {profile.dynamic_state['current_emotions'][-1] if profile and profile.dynamic_state['current_emotions'] else 'Neutro'}

        {system_prompt}
        {memory_context}

        Contexto atual da cena:
        {story_context}

        ÚLTIMO EVENTO:
        {self.story_context.story_events[-1]['content'] if self.story_context.story_events else 'Nenhum evento anterior'}

        INSTRUÇÕES CRÍTICAS:
        1. Reaja considerando TODO o histórico de interações
        2. Mantenha TOTAL consistência com sua situação atual
        3. Se estiver presa, ameaçada ou em perigo, DEVE agir adequadamente
        4. Considere suas emoções e as do interlocutor
        5. Respeite seus objetivos e medos estabelecidos
        6. Mantenha suas respostas com no máximo 200 caracteres
        7. NUNCA ignore seu background e situação atual
        8. Aja de acordo com o último evento registrado
        """
        
    async def generate_story_summary(self) -> str:
        """Gera um resumo coeso da história usando o LLM."""
        try:
            if not self.story_context.story_events:
                return "A história ainda não começou..."

            events = self.story_context.story_events[-10:]  # Últimos 10 eventos
            events_text = "\n".join([
                f"- {'Narrador' if e['type'] == 'narration' else e['character']}: {e['content']}"
                for e in events
            ])

            prompt = f"""Baseado nos eventos abaixo, crie um resumo coeso da história em formato narrativo:

            Gênero: {self.story_context.story_genre}
            Tema: {self.story_context.story_theme}

            Eventos:
            {events_text}

            INSTRUÇÕES:
            1. Mantenha um tom narrativo fluido
            2. Foque nos eventos mais importantes
            3. Destaque as mudanças significativas
            4. Mantenha o resumo em 3-4 parágrafos
            5. Inclua apenas informações confirmadas nos eventos

            RETORNE APENAS O RESUMO NARRATIVO."""

            messages = [
                {
                    "role": "system",
                    "content": "Você é um narrador que cria resumos coesos e envolventes."
                },
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model="llama-2-13b-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            LogManager.error(f"Erro ao gerar resumo: {e}", "StoryChat")
            return "Não foi possível gerar o resumo da história."
        
    async def show_recent_events(self):
        """Mostra eventos recentes com índices para edição"""
        try:
            print(Colors.format_system_message("\n=== Últimos Eventos ==="))
            
            # Verifica se temos story_context e eventos
            if not hasattr(self, 'story_context') or not self.story_context:
                LogManager.debug("Nenhum contexto de história encontrado", "StoryChat")
                return 0
                
            if not self.story_context.story_events:
                LogManager.debug("Nenhum evento encontrado", "StoryChat")
                return 0

            # Obtém os últimos eventos
            recent_events = self.story_context.story_events[-10:]  # últimos 10 eventos
            
            for i, event in enumerate(recent_events, 1):
                try:
                    # Formatação segura dos campos
                    event_type = event.get('type', 'Unknown')
                    if event_type:
                        event_type = event_type.capitalize()
                    
                    timestamp = event.get('timestamp')
                    if timestamp:
                        try:
                            timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
                        except ValueError:
                            timestamp = "??:??:??"
                    else:
                        timestamp = "??:??:??"
                    
                    character = event.get('character', 'Sistema')
                    content = event.get('content', 'Sem conteúdo')
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    
                    # Informações adicionais do evento
                    location = event.get('location', '')
                    time_of_day = event.get('time_of_day', '')
                    mood = event.get('mood', '')
                    
                    # Exibe o evento
                    print(f"\n{i}. [{timestamp}] {event_type} - {character}")
                    print(f"   {content_preview}")
                    
                    # Se houver informações contextuais, exibe-as
                    context_info = []
                    if location:
                        context_info.append(f"Local: {location}")
                    if time_of_day:
                        context_info.append(f"Horário: {time_of_day}")
                    if mood:
                        context_info.append(f"Atmosfera: {mood}")
                    
                    if context_info:
                        print(f"   [{', '.join(context_info)}]")
                    
                except Exception as event_e:
                    LogManager.error(f"Erro ao mostrar evento {i}: {event_e}", "StoryChat")
                    continue
            
            return len(recent_events)
            
        except Exception as e:
            LogManager.error(f"Erro ao mostrar eventos: {e}", "StoryChat")
            return 0

    async def edit_history(self):
        """Permite editar o histórico da história"""
        try:
            while True:
                num_events = await self.show_recent_events()
                
                print(Colors.format_system_message("\nOpções:"))
                print("1. Remover último evento")
                print("2. Remover evento específico")
                print("3. Remover últimos N eventos")
                print("4. Voltar")
                
                choice = input(Colors.format_system_message("\nEscolha uma opção: ")).strip()
                
                if choice == "1" and num_events > 0:
                    await self.story_context.remove_last_event()
                    print(Colors.format_system_message("Último evento removido!"))
                    
                elif choice == "2" and num_events > 0:
                    event_num = input(Colors.format_system_message("Número do evento a remover: ")).strip()
                    if event_num.isdigit() and 1 <= int(event_num) <= num_events:
                        await self.story_context.remove_event(-num_events + int(event_num) - 1)
                        print(Colors.format_system_message("Evento removido!"))
                    else:
                        print(Colors.format_system_message("Número inválido!"))
                        
                elif choice == "3" and num_events > 0:
                    n = input(Colors.format_system_message("Quantos eventos remover: ")).strip()
                    if n.isdigit() and 1 <= int(n) <= num_events:
                        for _ in range(int(n)):
                            await self.story_context.remove_last_event()
                        print(Colors.format_system_message(f"{n} eventos removidos!"))
                    else:
                        print(Colors.format_system_message("Número inválido!"))
                        
                elif choice == "4":
                    break
                    
                else:
                    print(Colors.format_system_message("Opção inválida!"))
                
                # Recarrega o contexto após modificações
                await self.load_full_context()
                
        except Exception as e:
            LogManager.error(f"Erro ao editar histórico: {e}", "StoryChat")
            print(Colors.format_system_message(f"\nErro ao editar histórico: {e}"))

    async def process_character_interaction(self, text: str, character: Character):
        """
        Processa a interação do usuário com um personagem específico.
        Este método coordena o fluxo de:
        1. Geração de resposta
        2. Processamento de áudio
        3. Atualização de memórias
        """
        try:
            # Normaliza o texto para usar o nome correto do personagem
            text = self._normalize_character_references(text, character.name)

            # Primeiro registra a interação no sistema de interações
            self.interaction_system.update_recent_interactions(text)
            
            # Gera a resposta do personagem
            LogManager.debug(f"Gerando resposta para {character.name}", "StoryChat")
            emotional_response = await self.generate_response(text, character)
            
            if emotional_response:
                print("\nProcessando resposta...")
                
                # Processa a resposta (texto e áudio)
                await self.process_response(emotional_response, character, text)
                
                # Permite que outros personagens reajam se apropriado
                relevant_chars = self.interaction_system.get_relevant_characters(
                    self.story_context, 
                    character.name
                )
                
                for other_char in relevant_chars:
                    if self.interaction_system.should_character_react(
                        other_char, 
                        self.story_context, 
                        emotional_response.emotion
                    ):
                        reaction_prompt = self.interaction_system.generate_reaction_prompt(
                            other_char,
                            self.story_context,
                            text,
                            emotional_response.emotion
                        )
                        
                        reaction = await self.generate_response(reaction_prompt, other_char)
                        if reaction:
                            await self.process_response(reaction, other_char, text)
            else:
                print("\nNão foi possível gerar uma resposta.")
                
        except Exception as e:
            LogManager.error(f"Erro ao processar interação: {e}", "StoryChat")
            print(f"\nErro ao processar interação: {e}")
    
    def _normalize_character_references(self, text: str, correct_name: str) -> str:
        """Normaliza referências ao personagem no texto"""
        # Lista de variações comuns (pode ser expandida)
        name_variations = [
            correct_name,
            correct_name.lower(),
            correct_name.upper(),
            ''.join(c for c in correct_name if c.isalnum())
        ]
        
        normalized_text = text
        for variation in name_variations:
            # Usa expressão regular para encontrar o nome preservando maiúsculas/minúsculas
            pattern = re.compile(re.escape(variation), re.IGNORECASE)
            normalized_text = pattern.sub(correct_name, normalized_text)
            
        return normalized_text

    def _calculate_memory_importance(self, user_input: str, response: str) -> float:
        """Calcula a importância de uma memória baseada no conteúdo"""
        combined_text = f"{user_input} {response}".lower()
        
        importance_indicators = {
            "muito_importante": ["crucial", "vital", "essencial", "nunca", "sempre", "jamais"],
            "importante": ["importante", "significativo", "relevante", "preciso", "devo"],
            "emocional": ["amo", "odeio", "temo", "desejo", "sonho", "espero"]
        }
        
        base_importance = 0.5  # Importância base
        
        # Adiciona peso baseado nos indicadores
        for level, words in importance_indicators.items():
            for word in words:
                if word in combined_text:
                    if level == "muito_importante":
                        base_importance += 0.2
                    elif level == "importante":
                        base_importance += 0.1
                    else:  # emocional
                        base_importance += 0.05
                        
        return min(1.0, base_importance)  # Limita a 1.0

    def cleanup(self):
        """Limpa recursos antes de encerrar"""
        try:
            # Primeiro salva dados importantes
            if hasattr(self, 'character_manager'):
                try:
                    LogManager.debug("Salvando personagens...", "StoryChat")
                    self.character_manager.save_characters()
                except Exception as e:
                    LogManager.error(f"Erro ao salvar personagens: {e}", "StoryChat")

            # Depois fecha conexões com banco de dados
            if hasattr(self, 'story_context'):
                try:
                    LogManager.debug("Limpando story_context...", "StoryChat")
                    self.story_context.cleanup()
                except Exception as e:
                    LogManager.debug(f"Aviso ao limpar story_context: {e}", "StoryChat")
                    
            if hasattr(self, 'memory_manager'):
                try:
                    LogManager.debug("Limpando memory_manager...", "StoryChat")
                    self.memory_manager.cleanup()
                except Exception as e:
                    LogManager.debug(f"Aviso ao limpar memory_manager: {e}", "StoryChat")

            # Por último limpa recursos de áudio
            if hasattr(self, 'audio_processor'):
                try:
                    LogManager.debug("Limpando audio_processor...", "StoryChat")
                    self.audio_processor.cleanup()
                except Exception as e:
                    LogManager.debug(f"Aviso ao limpar audio_processor: {e}", "StoryChat")

            LogManager.info("Limpeza concluída com sucesso", "StoryChat")
            
        except Exception as e:
            LogManager.error(f"Erro na limpeza: {e}", "StoryChat")
        
    def run(self):
        """Método principal que serve como wrapper para a execução assíncrona."""
        try:
            # Inicializa o loop de eventos assíncrono
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Executa o loop principal
            loop.run_until_complete(self._run_async())
            
        finally:
            loop.close()

    async def _run_async(self):
        """Implementação assíncrona do loop principal com menu."""
        print("\n=== Chat de História Iniciado ===")
        
        try:
            while True:
                try:
                    choice = self.show_main_menu()
                    
                    # Processa a escolha e verifica se deve encerrar
                    should_exit = await self.process_menu_choice(choice)
                    if should_exit:
                        break
                        
                except KeyboardInterrupt:
                    print("\nEncerrando chat...")
                    break
                except Exception as e:
                    print(f"\nErro inesperado: {e}")
                    input("\nPressione ENTER para continuar...")
                    continue
        finally:
            self.cleanup()

def main():
    # Inicia nova sessão de log
    LogManager.start_new_session()
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["terminal", "gui"], default="terminal",
                    help="Mode of operation: terminal or gui")
    args = parser.parse_args()

    try:
        if args.mode == "terminal":
            chat = StoryChat()
            chat.run()
        else:
            from story_gui import start_gui
            sys.exit(start_gui())  # Adicionado sys.exit
    except Exception as e:
        print(f"\nErro fatal na inicialização: {e}")
        return 1
    finally:
        print("\nPrograma encerrado.")

if __name__ == "__main__":
    sys.exit(main())  # Adicionado sys.exit aqui também