.PHONY: dev dev-api dev-portal dev-local dev-up dev-build down logs seed \
        migrate migrate-down migrate-new mcp-setup mcp-stdio mcp-http \
        test test-unit test-integration test-contract test-load \
        lint format typecheck openapi clean help stop-api logs-api-local \
        bench bench-gate bench-boundary bench-concurrency bench-vs-python \
        bench-dist-accuracy bench-real-data test-mojo-engines test-mojo-malformed

# ─── Shell / PATH ──────────────────────────────────────────────────────────────
SHELL := /bin/bash
export PATH := /usr/local/bin:/opt/homebrew/bin:$(PATH)

# ─── Environment ───────────────────────────────────────────────────────────────
ENV_FILE ?= .env
COMPOSE  := docker compose -f infra/docker/docker-compose.yml --env-file $(ENV_FILE)
API_CONTAINER := decision-engine-api-1
WORKER_CONTAINER := decision-engine-worker-1

# ─── Development ───────────────────────────────────────────────────────────────

## Start API server locally (no Docker, hot-reload). Reads .env for DB credentials.
dev-api:
	@kill $$(lsof -ti :8000) 2>/dev/null || true
	@if [ -f .env ]; then \
		set -a && . ./.env && set +a; \
	fi; \
	PYTHONPATH=. python3 -m uvicorn apps.api_server.main:app --port 8000 --reload

## Set up MCP server virtualenv (isolated from API server — avoids starlette version conflict)
mcp-setup:
	@echo "Creating isolated MCP virtual environment..."
	python3 -m venv mcp_venv
	mcp_venv/bin/pip install --upgrade pip -q
	mcp_venv/bin/pip install -r requirements-mcp.txt
	@echo "✓ MCP venv ready. Set ALGENTA_API_KEY and run: make mcp-stdio"

## Start MCP server (stdio transport — for Claude Desktop, Cursor)
mcp-stdio:
	@if [ -z "$(ALGENTA_API_KEY)" ]; then \
		echo "ERROR: ALGENTA_API_KEY is not set. Export it first:"; \
		echo "  export ALGENTA_API_KEY=de_live_..."; \
		exit 1; \
	fi
	ALGENTA_API_KEY=$(ALGENTA_API_KEY) ALGENTA_BASE_URL=$${ALGENTA_BASE_URL:-https://api.algenta.ai} \
		PYTHONPATH=. mcp_venv/bin/python -m apps.mcp_server.server --transport stdio

## Start MCP server (HTTP/SSE transport — for n8n, LangChain, remote agents) on port 8001
mcp-http:
	@if [ -z "$(ALGENTA_API_KEY)" ]; then \
		echo "ERROR: ALGENTA_API_KEY is not set."; exit 1; \
	fi
	ALGENTA_API_KEY=$(ALGENTA_API_KEY) ALGENTA_BASE_URL=$${ALGENTA_BASE_URL:-https://api.algenta.ai} \
		PYTHONPATH=. mcp_venv/bin/python -m apps.mcp_server.server --transport http --port $${ALGENTA_MCP_PORT:-8001}

## Start Algenta portal locally (Next.js dev server, port 3000)
dev-portal:
	@kill $$(lsof -ti :3000) 2>/dev/null || true; sleep 1
	cd apps/portal && npm run dev

## Start the full local development stack (build images if needed)
dev:
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE) up --build

## Start in background — uses Docker if available, falls back to native (no Docker)
dev-up:
	@cp -n .env.example .env 2>/dev/null || true
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		echo "Docker found — starting with Docker Compose..."; \
		$(COMPOSE) up --build -d; \
	else \
		echo "Docker not available — starting natively (make dev-local)..."; \
		$(MAKE) dev-local; \
	fi

## Start without Docker — API (port 8000) in background + Portal (port 3000) in foreground
## API log: /tmp/algenta-api.log  |  Stop API: make stop-api
dev-local:
	@cp -n .env.example .env 2>/dev/null || true
	@echo "Stopping any existing processes on :8000 and :3000..."
	@kill $$(lsof -ti :8000) 2>/dev/null || true
	@kill $$(lsof -ti :3000) 2>/dev/null || true
	@sleep 1
	@echo "Starting API server on :8000 (log: /tmp/algenta-api.log)..."
	@(set -a && . ./.env && set +a && \
		PYTHONPATH=. nohup python3 -m uvicorn apps.api_server.main:app \
		--port 8000 --reload > /tmp/algenta-api.log 2>&1 &\
		echo $$! > /tmp/algenta-api.pid && \
		echo "API PID: $$!")
	@sleep 2
	@echo "API running — starting Portal on :3000 (Ctrl+C stops portal, API keeps running)..."
	@cd apps/portal && npm run dev

## Stop API server (started with dev-local)
stop-api:
	@if [ -f /tmp/algenta-api.pid ]; then \
		kill $$(cat /tmp/algenta-api.pid) 2>/dev/null && \
		echo "API server stopped (PID $$(cat /tmp/algenta-api.pid))" && \
		rm -f /tmp/algenta-api.pid; \
	else \
		kill $$(lsof -ti :8000) 2>/dev/null && echo "API server stopped" || echo "API not running"; \
	fi

## Tail API server logs (when running via dev-local)
logs-api-local:
	@tail -f /tmp/algenta-api.log

## Stop all services
down:
	$(COMPOSE) down

## Stop and remove volumes (destructive!)
down-clean:
	$(COMPOSE) down -v --remove-orphans

## Follow logs from all services
logs:
	$(COMPOSE) logs -f

## Follow logs from API only
logs-api:
	$(COMPOSE) logs -f api

## Follow logs from worker only
logs-worker:
	$(COMPOSE) logs -f worker

# ─── Database ──────────────────────────────────────────────────────────────────

## Apply all pending Alembic migrations
migrate:
	$(COMPOSE) exec api alembic upgrade head

## Roll back one migration
migrate-down:
	$(COMPOSE) exec api alembic downgrade -1

## Create a new Alembic migration (usage: make migrate-new MSG="add_jobs_table")
migrate-new:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(MSG)"

## Seed the database with a dev org, user, and API key
seed:
	$(COMPOSE) exec api python scripts/seed_dev.py

# ─── Testing ───────────────────────────────────────────────────────────────────

## Run all tests (requires running stack)
test: test-unit test-integration test-contract

## Run unit tests only (no running stack required)
test-unit:
	pytest tests/unit/ -v --tb=short

## Run integration tests (requires running stack)
test-integration:
	pytest tests/integration/ -v --tb=short

## Run contract tests
test-contract:
	pytest tests/contract/ -v --tb=short

## Run load tests (requires k6)
test-load:
	k6 run tests/load/simulate_load.js

## Run tests with coverage report
test-coverage:
	pytest tests/unit/ tests/integration/ --cov=apps --cov-report=term-missing --cov-report=html

# ─── Code Quality ──────────────────────────────────────────────────────────────

## Run all linters
lint:
	ruff check .
	black --check .
	mypy apps/

## Auto-format code
format:
	ruff check --fix .
	black .

## Run type checker only
typecheck:
	mypy apps/

# ─── OpenAPI ───────────────────────────────────────────────────────────────────

## Generate and validate OpenAPI spec from running API
openapi:
	@echo "Generating OpenAPI spec..."
	curl -s http://localhost:8000/openapi.json | python scripts/convert_openapi.py > schemas/openapi/openapi.yaml
	openapi-spec-validator schemas/openapi/openapi.yaml
	@echo "✅ OpenAPI spec generated and validated: schemas/openapi/openapi.yaml"

# ─── Build ─────────────────────────────────────────────────────────────────────

## Build all Docker images
build:
	$(COMPOSE) build

## Install pixi + Mojo nightly (first-time setup)
setup-mojo:
	bash scripts/install_mojo.sh

## Build Mojo engine binary using pixi environment in mojo_env/
build-mojo:
	mkdir -p mojo_build
	@if [ -d mojo_env ] && command -v pixi >/dev/null 2>&1; then \
		cd mojo_env && pixi run mojo build ../mojo/engine/main.mojo -o ../mojo_build/simulate && \
		echo "✅ Mojo engine built: mojo_build/simulate (engine_version: 0.2.0-mojo-native)"; \
	else \
		echo "❌ pixi/mojo_env not found. Run: make setup-mojo"; exit 1; \
	fi

## Smoke-test the compiled Mojo binary
test-mojo:
	@echo '{"runs":500,"variables":[{"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"rev"}' \
		| ./mojo_build/simulate | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'✅ engine={d[\"engine_version\"]} mean={d[\"summary\"][\"mean\"]:.0f}')"

# ─── Benchmarks ────────────────────────────────────────────────────────────────

## Run all 11-engine latency benchmark (requires running API server)
bench:
	PYTHONPATH=. python3 -m tests.benchmark.bench_engines

## CI latency gate: all 11 engines, per-class thresholds, no subprocess fallback (exit 1 on regression)
bench-gate:
	MOJO_ALLOW_SUBPROCESS_FALLBACK=false PYTHONPATH=. python3 -m tests.benchmark.bench_ci_gate

## Phase 4 boundary micro-benchmark: measure json.loads() cost vs compute (requires running API server)
bench-boundary:
	PYTHONPATH=. python3 -m tests.benchmark.bench_boundary

## Concurrency benchmark: pool behavior at 1/10/100/500 simultaneous requests (Phase 0 + Phase 8)
bench-concurrency:
	MOJO_ALLOW_SUBPROCESS_FALLBACK=false PYTHONPATH=. python3 -m tests.benchmark.bench_concurrency

## Phase 8 baseline: Mojo vs NumPy/SciPy on Monte Carlo, LHS, Bootstrap (requires numpy + scipy)
bench-vs-python:
	PYTHONPATH=. python3 -m tests.benchmark.bench_vs_python

## Distribution statistical correctness tests (PhD-grade, 22 distributions, 10k runs each)
bench-dist-accuracy:
	PYTHONPATH=. python3 -m tests.benchmark.bench_distribution_accuracy

## Real-data integration test (CSV files → FileConnector → auto-map → Mojo engine)
bench-real-data:
	PYTHONPATH=. python3 -m tests.benchmark.bench_real_data

## Run all Mojo engine unit tests (all 11 engines, score range, histogram/CDF presence)
test-mojo-engines:
	@if [ -d mojo_env ] && command -v pixi >/dev/null 2>&1; then \
		cd mojo_env && pixi run mojo run ../tests/mojo/test_engines.mojo; \
	else \
		echo "❌ pixi/mojo_env not found. Run: make setup-mojo"; exit 1; \
	fi

## Run Mojo malformed payload tests (Phase 4 exit criteria)
test-mojo-malformed:
	@if [ -d mojo_env ] && command -v pixi >/dev/null 2>&1; then \
		cd mojo_env && pixi run mojo run ../tests/mojo/test_malformed_payload.mojo; \
	else \
		echo "❌ pixi/mojo_env not found. Run: make setup-mojo"; exit 1; \
	fi

# ─── Cleanup ───────────────────────────────────────────────────────────────────

## Remove build artifacts and caches
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf mojo_build/ htmlcov/ .coverage

# ─── Help ──────────────────────────────────────────────────────────────────────

## Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/## //' | column -t -s ':' | sort
