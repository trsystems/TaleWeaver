.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: test
test:
	pytest tests/ -v --cov=./ --cov-report=html

.PHONY: run
run:
	python main.py

.PHONY: format
format:
	black .
	isort .

.PHONY: lint
lint:
	flake8 .
	mypy .
