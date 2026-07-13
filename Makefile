# Atlas — convenience targets. Run `make help` for the list.
# Backend commands run from apps/api; infra from the repo root.

API_DIR := apps/api

.PHONY: help install dev test lint fix ingest eval-retrieval eval-ragas \
        up down logs build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install the API (editable) with dev + eval extras
	cd $(API_DIR) && pip install -e ".[dev,eval]"

dev: ## Run the API with hot reload
	cd $(API_DIR) && uvicorn atlas.main:app --reload

test: ## Run the test suite offline (no network/keys)
	cd $(API_DIR) && ATLAS_OFFLINE_EMBED=1 python -m pytest -q --cov=atlas --cov-report=term-missing

lint: ## Lint with ruff
	cd $(API_DIR) && python -m ruff check atlas

fix: ## Auto-fix lint issues
	cd $(API_DIR) && python -m ruff check atlas --fix

ingest: ## Ingest the local corpus (add TICKER=AAPL to also pull a 10-K)
	cd $(API_DIR) && python -m atlas.core.rag.ingest $(if $(TICKER),--ticker $(TICKER),)

eval-retrieval: ## Run the dependency-free retrieval eval (offline)
	cd $(API_DIR) && ATLAS_OFFLINE_EMBED=1 python -m atlas.eval.retrieval_eval

eval-ragas: ## Run the Ragas eval -> Langfuse (needs GROQ_API_KEY)
	cd $(API_DIR) && python -m atlas.eval.ragas_eval

up: ## Start infra (Qdrant + Langfuse) and the API
	docker compose up -d qdrant langfuse api

down: ## Stop the stack
	docker compose down

logs: ## Tail the stack logs
	docker compose logs -f

build: ## Build the Docker images
	docker compose build

clean: ## Remove caches and build artifacts
	cd $(API_DIR) && rm -rf .pytest_cache .ruff_cache __pycache__ .coverage
