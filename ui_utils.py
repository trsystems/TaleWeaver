class Colors:
    # Cores básicas
    WHITE = '\033[37m'
    BLUE = '\033[34m'
    
    # Cores para personagens (exemplos)
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    RED = '\033[91m'
    GREEN = '\033[32m'
    YELLOW = '\033[93m'
    
    # Estilos de texto
    BOLD = '\033[1m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    
    # Cores de fundo
    BG_GRAY = '\033[100m'
    BG_PURPLE = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    
    # Reset
    RESET = '\033[0m'
    
    @staticmethod
    def style_character_name(name: str, color: str) -> str:
        """Formata nome do personagem com negrito, itálico, underscore e cor de fundo"""
        return f"{Colors.BOLD}{Colors.ITALIC}{Colors.UNDERLINE}{color}{name}{Colors.RESET}"

    @staticmethod
    def format_system_message(text: str) -> str:
        """Formata mensagem do sistema em azul escuro"""
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def format_character_text(text: str) -> str:
        """Formata texto do personagem em branco"""
        return f"{Colors.WHITE}{text}{Colors.RESET}"

class TextFormatter:
    @staticmethod
    def format_character_name(name: str, color: str) -> str:
        """Formata o nome do personagem com cor."""
        return f"{color}{name}{Colors.RESET}"

    @staticmethod
    def format_scene_description(text: str) -> str:
        """Formata descrição de cena."""
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def format_dialogue(text: str) -> str:
        """Formata texto de diálogo."""
        return f'"{text}"'

    @staticmethod
    def format_action(text: str) -> str:
        """Formata descrição de ação."""
        return f"*{text}*"

class ConsoleUI:
    @staticmethod
    def print_separator(char: str = "─", length: int = 40):
        """Imprime uma linha separadora."""
        print(char * length)

    @staticmethod
    def print_header(text: str, color: str = Colors.CYAN):
        """Imprime um cabeçalho formatado."""
        ConsoleUI.print_separator()
        print(f"{color}{text}{Colors.RESET}")
        ConsoleUI.print_separator()

    @staticmethod
    def print_menu(options: dict):
        """Imprime um menu de opções."""
        ConsoleUI.print_separator()
        for key, value in options.items():
            print(f"{Colors.CYAN}{key}{Colors.RESET}: {value}")
        ConsoleUI.print_separator()

    @staticmethod
    def print_error(message: str):
        """Imprime uma mensagem de erro."""
        print(f"\033[91mErro: {message}{Colors.RESET}")

    @staticmethod
    def print_success(message: str):
        """Imprime uma mensagem de sucesso."""
        print(f"{Colors.NEON_GREEN}✓ {message}{Colors.RESET}")

    @staticmethod
    def print_info(message: str):
        """Imprime uma mensagem informativa."""
        print(f"{Colors.CYAN}ℹ {message}{Colors.RESET}")

    @staticmethod
    def clear_screen():
        """Limpa a tela do console."""
        print("\033[H\033[J", end="")