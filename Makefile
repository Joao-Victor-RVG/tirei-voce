COMPOSE := docker compose -f infra/docker-compose.yml
API := cd apps/api &&
WEB := cd apps/web &&

.PHONY: dev down logs migrate migration seed keys api-types prod-up prod-down test test-api test-web lint lint-api lint-web format help

dev: ## Sobe tudo (postgres, redis, api, worker, web) com hot reload
	$(COMPOSE) up --build

down: ## Derruba os containers
	$(COMPOSE) down

logs: ## Acompanha os logs
	$(COMPOSE) logs -f

migrate: ## Aplica as migrations (com o compose rodando)
	$(COMPOSE) exec api alembic upgrade head

seed: ## Carrega os dados iniciais (temas); idempotente
	$(COMPOSE) exec api python -m app.seed

keys: ## Gera segredos novos para JWT_SECRET, DRAW_ENCRYPTION_KEY e DRAW_HMAC_KEY
	@cd apps/api && uv run python -c "import secrets; from cryptography.fernet import Fernet; \
	print('JWT_SECRET=' + secrets.token_urlsafe(48)); \
	print('DRAW_ENCRYPTION_KEY=' + Fernet.generate_key().decode()); \
	print('DRAW_HMAC_KEY=' + secrets.token_urlsafe(48))"

migration: ## Gera uma migration: make migration m="descricao"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

api-types: ## Regenera openapi.json e os tipos TypeScript do frontend
	$(API) uv run python -m app.export_openapi ../web/openapi.json
	$(WEB) pnpm gen:api && pnpm exec prettier --write openapi.json >/dev/null

prod-up: ## Sobe as imagens de produção localmente em http://localhost:8080
	docker compose --env-file .env -f infra/docker-compose.prod.yml up --build

prod-down:
	docker compose --env-file .env -f infra/docker-compose.prod.yml down

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
