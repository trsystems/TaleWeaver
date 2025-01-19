# TaleWeaver - Contador de Histórias Interativo

## Descrição do Projeto
TaleWeaver é um sistema de criação de histórias interativas utilizando IA (LLM local ou online) para gerar narrativas envolventes e personagens complexos. O projeto permite que usuários interajam com personagens controlados por IA, influenciando o rumo da história.

## Estrutura do Projeto

```
TaleWeaver/
├── additional_files/       # Arquivos de exemplo e referência
├── project_documents/      # Documentação do projeto
├── voices/                 # Arquivos de voz para personagens e narradores
├── character_manager.py    # Gerenciamento de personagens
├── config.py               # Configurações do sistema
├── database.py             # Gerenciamento do banco de dados
├── logger.py               # Sistema de logs
├── main.py                 # Ponto de entrada do sistema
├── story_manager.py        # Gerenciamento de histórias
├── narrator_system.py      # Sistema de narradores
├── tests/                  # Testes unitários
│   └── utilities/          # Utilitários para testes e manutenção
│       ├── check_schema.py # Verifica a estrutura do banco de dados
│       ├── reset_db.py     # Reseta o banco de dados para estado inicial
│       ├── reset_characters_table.py # Reseta tabela de personagens
│       └── reset_and_restart.bat # Script para resetar e reiniciar o sistema
├── Makefile                # Automação de tarefas
├── requirements.txt        # Dependências do projeto
└── .gitignore              # Arquivos ignorados pelo Git
```

### Utilitários de Teste

- **check_schema.py**: Verifica se a estrutura do banco de dados está correta
- **reset_db.py**: Reseta completamente o banco de dados para o estado inicial
- **reset_characters_table.py**: Reseta especificamente a tabela de personagens
- **reset_and_restart.bat**: Script que para o sistema, reseta o banco de dados e reinicia a aplicação

## Funcionalidades Implementadas

- [x] Estrutura básica do projeto
- [x] Configuração inicial do Git
- [x] Integração com repositório remoto no GitHub
- [x] Módulos principais organizados
- [x] Implementação das classes principais no story_manager.py
  - LLMClient para integração com LMStudio
  - StoryManager para gerenciamento de histórias
- [x] Sistema de narradores implementado
  - Narrador Descritivo (padrão)
  - Narrador Sassy
- [x] Gerenciamento de personagens
  - Criação de personagens principais
  - Criação do personagem do jogador
  - Interação com personagens via diálogo
- [x] Sistema de vozes integrado
  - Vozes específicas para personagens
  - Vozes para narradores (descriptive.wav e sassy.wav)

## Sistema de Narradores

O TaleWeaver oferece dois tipos de narradores:

1. **Narrador Descritivo (padrão)**
   - Narra a cena de forma neutra e descritiva
   - Voz: narrator_descriptive.wav
   - Ideal para histórias sérias e narrativas detalhadas

2. **Narrador Sassy**
   - Adiciona comentários irônicos e humorísticos
   - Voz: narrator_sassy.wav
   - Ideal para histórias mais leves e descontraídas

## Interação com Personagens

O sistema permite:
- Criação de personagens principais
- Criação do personagem do jogador
- Diálogos interativos com personagens
- Evolução de relacionamentos entre personagens
- Sistema de memórias e contexto

## Próximos Passos

1. Correção de bugs no sistema de banco de dados
2. Implementação de sistema de lembranças
3. Melhoria na interface de linha de comando
4. Adição de mais perfis de narradores
5. Expansão do sistema de vozes

## Como Contribuir

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas alterações (`git commit -m 'Adiciona nova feature'`)
4. Faça push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Requisitos

- Python 3.8+
- LMStudio rodando localmente
- XTTS2 para geração de vozes
- Banco de dados SQLite3

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.
