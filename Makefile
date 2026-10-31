SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help doctor env config build model model-verify up down restart logs ps health test lint benchmark
help:
	@printf 'Targets: doctor | env | config | build | model | model-verify | up | down | restart | logs | ps | health | test | lint | benchmark\n'
doctor:
	@docker version >/dev/null && $(COMPOSE) version && $(COMPOSE) config --quiet && echo 'Docker / Compose / configuration: OK'
env:
	@test -e .env || cp .env.example .env
config:
	$(COMPOSE) config --quiet
build:
	$(COMPOSE) build
# One-shot download reuses the model_cache volume; it is not a third service.
model:
	$(COMPOSE) run --rm --no-deps --entrypoint python api -m scripts.download_model
model-verify:
	$(COMPOSE) run --rm --no-deps --entrypoint python api -m scripts.download_model --verify-only
up:
	$(COMPOSE) up -d --no-build api ui
down:
	$(COMPOSE) down
restart:
	$(COMPOSE) restart
logs:
	$(COMPOSE) logs -f --tail=100
ps:
	$(COMPOSE) ps
health:
	$(COMPOSE) exec -T api python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=10).read().decode())'
	$(COMPOSE) exec -T ui wget -q -O - http://127.0.0.1:80/healthz
test:
	PYTHONPATH=backend python -m pytest backend/tests -q
lint:
	ruff check backend/app backend/scripts backend/tests
benchmark:
	@echo 'Run: cd backend && python -m scripts.benchmark --file /path/to/image.png --requests 30 --concurrency 2'
