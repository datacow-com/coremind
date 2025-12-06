clean-uploads:
	@python3 scripts/cleanup_uploads.py

check-index:
	@python3 scripts/check_index_consistency.py
.PHONY: setup install precommit lint format type test dev help fix check push-check e2e e2e-docker db-init milvus-bench type-strict models data eval fast-test models-class eval-layoutlm recommend

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
	pre-commit install --hook-type pre-push

lint:
	ruff check
	bandit -c .bandit -r core server --exit-zero
	npm --prefix $(FRONTEND_DIR) run lint
	npm --prefix $(EMBEDDED_DIR) run lint

format:
	ruff format
	npx --prefix $(FRONTEND_DIR) prettier --write .
	npx --prefix $(EMBEDDED_DIR) prettier --write .

fix:
	ruff check --fix
	npm --prefix $(FRONTEND_DIR) run lint -- --fix
	npm --prefix $(EMBEDDED_DIR) run lint -- --fix

check:
	pre-commit run --all-files

push-check:
	pre-commit run --hook-stage pre-push --all-files

ci:
	$(MAKE) check
	$(MAKE) push-check
	pytest -q tests/test_route_intent.py::test_route_intent_classification \
					tests/test_chat_stream.py::test_chat_stream_basic \
					tests/test_html_ingest.py::test_html_ingest_to_markdown \
					tests/test_vector_store_api.py::test_vector_collections_endpoint \
					tests/test_web_search_provider.py::test_web_search_runs \
					tests/test_usage_alerts.py::test_threshold_webhook_trigger || true

coverage:
	pytest --cov=core --cov=server --cov-report=xml --cov-report=term-missing -q

type:
	mypy --config-file mypy.ini core server
	npm --prefix $(FRONTEND_DIR) run type-check
	npm --prefix $(EMBEDDED_DIR) run type-check

type-strict:
	mypy --config-file mypy.ini core server

test:
	pytest -q || true

E2E_BASE_URL ?= http://127.0.0.1:8000
e2e:
	E2E_BASE_URL=$(E2E_BASE_URL) pytest -q -k 'e2e'

e2e-docker:
	docker compose up -d --wait
	E2E_BASE_URL=http://localhost:3500 pytest -q -k 'e2e' || true
	docker compose down -v

dev:
	bash scripts/dev.sh

db-init:
	python3 scripts/db_init.py

milvus-bench:
	python3 scripts/milvus_bench.py

models:
	python3 scripts/download_models.py --out models --yolo-file yolov8n.pt --layoutlm-model microsoft/layoutlmv3-base

data:
	python3 scripts/prepare_data.py

eval:
	python3 scripts/eval_hybrid.py data/samples/queries.jsonl --doc feat-doc || true

fast-test:
	pytest -q -n auto -k 'not e2e'

models-class:
	python3 scripts/cache_layoutlm_models.py --model nielsr/layoutlmv3-finetuned-funsd --out models/hf

eval-layoutlm:
	python3 scripts/eval_layoutlm.py data/samples/pdf/arxiv_sample.pdf --class_model $$LAYOUTLM_CLASS_MODEL --out reports/layoutlm_eval.json

recommend:
	PYTHONPATH=. python3 scripts/recommend_config.py data/samples/queries.jsonl --base_url $$E2E_BASE_URL --doc feat-doc || true
