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
├── tests/                  # Testes unitários
├── Makefile                # Automação de tarefas
├── requirements.txt        # Dependências do projeto
└── .gitignore              # Arquivos ignorados pelo Git
```

## Funcionalidades Implementadas

- [x] Estrutura básica do projeto
- [x] Configuração inicial do Git
- [x] Integração com repositório remoto no GitHub
- [x] Módulos principais organizados

## Próximos Passos

1. Implementar sistema de menus interativos
2. Desenvolver integração com LMStudio
3. Criar sistema de gerenciamento de histórias
4. Implementar banco de dados para personagens e histórias
5. Desenvolver sistema de narração
6. Criar interface de linha de comando
7. Implementar sistema de geração de vozes

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

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.
