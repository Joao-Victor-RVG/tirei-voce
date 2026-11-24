COMPOSE := docker compose -f infra/docker-compose.yml
API := cd apps/api &&
WEB := cd apps/web &&

.PHONY: dev down logs migrate migration test test-api test-web lint lint-api lint-web format help

dev: ## Sobe tudo (postgres, redis, api, worker, web) com hot reload
	$(COMPOSE) up --build

down: ## Derruba os containers
	$(COMPOSE) down

logs: ## Acompanha os logs
	$(COMPOSE) logs -f

migrate: ## Aplica as migrations (com o compose rodando)
	$(COMPOSE) exec api alembic upgrade head

migration: ## Gera uma migration: make migration m="descricao"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

test: test-api test-web ## Roda todos os testes

test-api: ## Testes do backend (precisa do postgres e redis do compose)
	$(API) uv run pytest --cov

test-web:
	$(WEB) pnpm test

lint: lint-api lint-web ## Lint + type-check

lint-api:
	$(API) uv run ruff check . && uv run ruff format --check . && uv run mypy .

lint-web:
	$(WEB) pnpm lint && pnpm typecheck

format: ## Formata o código
	$(API) uv run ruff format . && uv run ruff check --fix .
	$(WEB) pnpm format

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'
