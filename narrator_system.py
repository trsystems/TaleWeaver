"""
Módulo de Gerenciamento de Narradores

Este módulo gerencia a seleção e configuração dos narradores disponíveis
no TaleWeaver, incluindo:
- Definição dos perfis de narração
- Seleção do narrador ativo
- Gerenciamento do estilo de narração
"""

from typing import Dict, Any

class NarratorSystem:
    def __init__(self, config):
        self.config = config
        self.current_narrator = None
        self.narrators = {
            "descriptive": {
                "name": "Narrador Descritivo",
                "voice": "voices/narrator_descriptive.wav",
                "system_prompt": """Você é um narrador onisciente que descreve cenas e ações em terceira pessoa.
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
            },
            "sassy": {
                "name": "Narrador Sassy",
                "voice": "voices/narrator_sassy.wav",
                "system_prompt": """Você é um narrador extremamente irreverente, sarcástico e debochado, semelhante ao Coringa.
                IMPORTANTE: Você SEMPRE responde em português brasileiro, usando gírias e expressões brasileiras.
                DIRETRIZES:
                1. Seja MUITO debochado e sarcástico - use humor ácido e provocativo
                2. Faça comentários diretos ao usuário
                3. Use expressões brasileiras
                4. Em cenas românticas seja malicioso
                5. Faça piadas sobre as ações
                6. Use referências da cultura pop brasileira
                7. Em momentos tensos, faça comentários inapropriados
                8. Seja extremamente provocativo
                9. NÃO use a palavra "Narrador:" no início das frases
                10. Mantenha um tom de deboche constante
                11. NUNCA faça monólogos longos - mantenha o ritmo da história"""
            }
        }

    def get_narrator_options(self) -> Dict[str, Dict[str, Any]]:
        """Retorna as opções de narradores disponíveis"""
        return self.narrators

    def select_narrator(self, narrator_type: str) -> None:
        """Seleciona o narrador ativo"""
        if narrator_type in self.narrators:
            self.current_narrator = self.narrators[narrator_type]
        else:
            raise ValueError(f"Tipo de narrador inválido: {narrator_type}")

    def get_current_narrator(self) -> Dict[str, Any]:
        """Retorna o narrador atualmente selecionado"""
        if not self.current_narrator:
            # Retorna o descritivo como padrão se nenhum foi selecionado
            return self.narrators["descriptive"]
        return self.current_narrator

    def get_narrator_prompt(self) -> str:
        """Retorna o prompt do narrador atual"""
        return self.get_current_narrator()["system_prompt"]

    def get_narrator_voice(self) -> str:
        """Retorna o arquivo de voz do narrador atual"""
        return self.get_current_narrator()["voice"]

    async def initialize(self) -> None:
        """Inicializa o sistema de narradores"""
        # Seleciona o narrador padrão (descritivo)
        self.select_narrator("descriptive")
        print("NarratorSystem inicializado com sucesso!")

    async def set_narrator(self, narrator_type: str) -> None:
        """Configura o narrador com base na escolha do usuário"""
        if narrator_type not in self.narrators:
            raise ValueError(f"Tipo de narrador inválido: {narrator_type}")
        
        self.select_narrator(narrator_type)
        print(f"Narrador configurado para: {self.narrators[narrator_type]['name']}")
