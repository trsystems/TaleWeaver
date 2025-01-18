# Makefile para automação de tarefas do TaleWeaver

# Variáveis
PYTHON = python3
PIP = pip3
PYTEST = pytest
BLACK = black
FLAKE8 = flake8
ISORT = isort
MYPY = mypy

# Comandos padrão
.PHONY: install test format lint typecheck clean

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTEST) tests/ -v

format:
	$(BLACK) .
	$(ISORT) .

lint:
	$(FLAKE8) .

typecheck:
	$(MYPY) .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/

run:
	$(PYTHON) main.py

all: install format lint typecheck test
