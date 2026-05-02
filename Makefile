.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE := docker compose -f infra/docker-compose.yml
PNPM    := pnpm
UV      := uv

.PHONY: help dev db logs seed test stop down clean lint typecheck install web

help:
	@echo "AgentTape — make targets"
	@echo "  make dev        Bring up all services (db + redis + 5 python svcs + web)"
	@echo "  make db         Start Postgres + Redis only"
	@echo "  make logs       Tail logs from every service"
	@echo "  make seed       No-op: AgentTape uses autonomous discovery, no seed list"
	@echo "  make test       Run all TS + Python tests"
	@echo "  make lint       Lint TS + Python"
	@echo "  make typecheck  Typecheck TS + Python"
	@echo "  make install    Install JS + Python deps"
	@echo "  make web        Run only the Next.js web app (host)"
	@echo "  make stop       Stop containers (keep volumes)"
	@echo "  make down       Stop and remove containers + network"
	@echo "  make clean      Down + remove volumes"

install:
	$(PNPM) install
	$(UV) sync

dev:
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Services:"
	@echo "  api       http://localhost:8001/health"
	@echo "  realtime  http://localhost:8002/health"
	@echo "  discovery http://localhost:8003/health"
	@echo "  ingestion http://localhost:8004/health"
	@echo "  scoring   http://localhost:8005/health"
	@echo "  postgres  localhost:5432"
	@echo "  redis     localhost:6379"
	@echo ""
	@echo "Web (run separately on host):  cd apps/web && pnpm dev"

db:
	$(COMPOSE) up -d postgres redis

logs:
	$(COMPOSE) logs -f --tail=100

seed:
	@echo "AgentTape does not use a seed list."
	@echo "The discovery service scans GitHub / Hugging Face / MCP / arXiv / HN"
	@echo "and admits agents autonomously. It begins on first start."

test:
	$(PNPM) -r test
	$(UV) run pytest

lint:
	$(PNPM) -r lint
	$(UV) run ruff check .

typecheck:
	$(PNPM) -r typecheck
	$(UV) run mypy apps

web:
	cd apps/web && $(PNPM) dev

stop:
	$(COMPOSE) stop

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v
