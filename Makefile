SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help env build model model-verify up down restart logs ps health test lint benchmark clean
help:
	@printf 'Targets: env | build | model | model-verify | up | down | restart | logs | ps | health | test | lint | benchmark\n'
env:
	@test -e .env || cp .env.example .env
build:
	$(COMPOSE) build
# Ephemeral command on api image; no third long-running container. Persists in model_cache volume.
model:
	$(COMPOSE) run --rm --no-deps --entrypoint python api -m scripts.download_model
model-verify:
	$(COMPOSE) run --rm --no-deps --entrypoint python api -m scripts.download_model --verify-only
up:
	$(COMPOSE) up -d --build api ui
down:
	$(COMPOSE) down
restart:
	$(COMPOSE) restart
logs:
	$(COMPOSE) logs -f --tail=100
ps:
	$(COMPOSE) ps
health:
	curl -fsS http://127.0.0.1:$${API_PORT:-8000}/health/ready && echo
	curl -fsS http://127.0.0.1:$${UI_PORT:-8080}/healthz && echo
test:
	python -m pytest backend/tests -q
lint:
	ruff check backend/app backend/scripts backend/tests
benchmark:
	@echo 'Run: python -m scripts.benchmark --file sample.png --requests 20 --concurrency 2 (from backend dir)'
clean:
	@echo 'Use docker compose down (data retained). To wipe models: docker compose down -v'
