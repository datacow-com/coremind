.PHONY: setup install precommit lint format type test dev help

FRONTEND_DIR := frontend
EMBEDDED_DIR := apps/embedded-ui

help:
	@echo "Targets: setup install precommit lint format type test dev"

setup: install precommit

install:
	python3 -m pip install --user pre-commit
	npm --prefix $(FRONTEND_DIR) install
	npm --prefix $(EMBEDDED_DIR) install

precommit:
	pre-commit install

lint:
	ruff check
	bandit -c .bandit -r core server --exit-zero
	npm --prefix $(FRONTEND_DIR) run lint
	npm --prefix $(EMBEDDED_DIR) run lint

format:
	ruff format
	npx --prefix $(FRONTEND_DIR) prettier --write .
	npx --prefix $(EMBEDDED_DIR) prettier --write .

type:
	mypy --config-file mypy.ini core server
	npm --prefix $(FRONTEND_DIR) run type-check
	npm --prefix $(EMBEDDED_DIR) run type-check

test:
	pytest -q || true

dev:
	bash scripts/dev.sh

