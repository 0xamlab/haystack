.PHONY: dev dev-api dev-local dev-up dev-build down logs seed self-host-smoke self-host-persistence-proof self-host-install-proof self-host-endpoint-matrix self-host-status self-host-verify docs-gitbook-status docs-gitbook-pack docs-gitbook-verify docs-gen docs-check capability-plane-verify repository-intelligence-channel-parity \
        migrate migrate-down migrate-new mcp-setup mcp-stdio mcp-http \
        test test-unit test-integration test-contract test-load \
        lint format typecheck openapi clean help stop-api logs-api-local \
        js-install js-lint js-test js-build js-check \
        bench bench-gate bench-boundary bench-vs-python bench-algenta-mojo-catalog bench-algenta-import bench-decision-engine-import bench-decision-engine-client-init bench-algenta-connector-preview bench-algenta-runtime-read-cache bench-algenta-local-runtime-exact bench-algenta-local-connect bench-algenta-api-exact-resolve bench-algenta-api-payload \
        go-live-status go-live-status-json go-live-status-strict go-live-status-tier2 go-live-status-tier3 \
        go-live-status-fivetran go-live-status-fivetran-json go-live-report go-live-report-fivetran \
        go-live-inspect-fivetran-account \
        go-live-probe-redis go-live-probe-snowflake go-live-probe-clickhouse go-live-probe-elasticsearch go-live-probe-neo4j \
        go-live-bench-clickhouse-consistency go-live-bench-elasticsearch-consistency go-live-bench-neo4j-consistency \
        go-live-verify go-live-verify-all go-live-verify-tier2 go-live-verify-tier3 go-live-verify-fivetran \
        go-live-refresh-fivetran-inventory go-live-refresh-fivetran-baseline go-live-hydrate-fivetran-manifest \
        go-live-show-fivetran-manifest \
        go-live-verify-fivetran-prebaseline \
        test-go-live-connectivity test-go-live-connectivity-tier2 test-go-live-connectivity-tier3 test-go-live-full \
        test-csv-generic test-csv-regression test-csv-all bench-csv-corpus bench-csv-corpus-full \
        bench-dist-accuracy bench-real-data test-mojo-engines test-mojo-malformed

# ─── Shell / PATH ──────────────────────────────────────────────────────────────
SHELL := /bin/bash
export PATH := /usr/local/bin:/opt/homebrew/bin:$(PATH)

# ─── Environment ───────────────────────────────────────────────────────────────
ENV_FILE ?= .env
COMPOSE  := docker compose -f infra/docker/docker-compose.yml --env-file $(ENV_FILE)
API_CONTAINER := decision-engine-api-1
WORKER_CONTAINER := decision-engine-worker-1
CONTRACT_PYTEST_FILES := $(sort $(shell find tests -maxdepth 2 -name '*contract*.py' | sort))
CONTRACT_SCRIPT_FILES := tests/integration/test_openapi.py
REPO_PYTHON := ./scripts/run_repo_python.sh
RI_CHANNEL_PARITY_FILTER ?= repository
RI_CHANNEL_PARITY_OUTPUT ?= build/repository_intelligence_channel_parity_summary.json
RI_CHANNEL_PARITY_LOGS_DIR ?= build/repository_intelligence_channel_parity_logs
RI_CHANNEL_PARITY_JOBS ?= 1

# ─── Development ───────────────────────────────────────────────────────────────

## Start API server locally (no Docker, hot-reload). Reads .env for DB credentials.
dev-api:
	@kill $$(lsof -ti :8000) 2>/dev/null || true
	@if [ -f .env ]; then \
		set -a && . ./.env && set +a; \
	fi; \
	PYTHONPATH=. python3 -m uvicorn apps.api_server.main:app --port 8000 --reload --timeout-graceful-shutdown 10

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
	ALGENTA_API_KEY=$(ALGENTA_API_KEY) \
		PYTHONPATH=. mcp_venv/bin/python -m apps.mcp_server.server --transport stdio

## Start MCP server (HTTP/SSE transport — for n8n, LangChain, remote agents) on port 8001
mcp-http:
	@if [ -z "$(ALGENTA_API_KEY)" ]; then \
		echo "ERROR: ALGENTA_API_KEY is not set."; exit 1; \
	fi
	ALGENTA_API_KEY=$(ALGENTA_API_KEY) \
		PYTHONPATH=. mcp_venv/bin/python -m apps.mcp_server.server --transport http --port $${ALGENTA_MCP_PORT:-8001}

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

## Start without Docker — API (port 8000) in background.
## API log: /tmp/algenta-api.log  |  Stop API: make stop-api
dev-local:
	@cp -n .env.example .env 2>/dev/null || true
	@echo "Stopping any existing process on :8000..."
	@kill $$(lsof -ti :8000) 2>/dev/null || true
	@sleep 1
	@echo "Starting API server on :8000 (log: /tmp/algenta-api.log)..."
	@(set -a && . ./.env && set +a && \
		PYTHONPATH=. nohup python3 -m uvicorn apps.api_server.main:app \
		--port 8000 --reload --timeout-graceful-shutdown 10 > /tmp/algenta-api.log 2>&1 &\
		echo $$! > /tmp/algenta-api.pid && \
		echo "API PID: $$!")
	@sleep 2
	@echo "API running on :8000. The web interface is maintained outside this repository."

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
	$(REPO_PYTHON) -m pytest tests/unit/ -v --tb=short

## Run integration tests (requires running stack)
test-integration:
	$(REPO_PYTHON) -m pytest tests/integration/ -v --tb=short

## Run contract tests
# REPO_PYTHON routes through pixi when available; pure-stdlib host fallback
# is equivalent to: "$$PY_BIN" $(CONTRACT_SCRIPT_FILES)
test-contract:
	$(REPO_PYTHON) -m pytest $(CONTRACT_PYTEST_FILES) -v --tb=short && \
	$(REPO_PYTHON) $(CONTRACT_SCRIPT_FILES)

## Run load tests (requires k6)
test-load:
	k6 run tests/load/simulate_load.js

## Run tests with coverage report
test-coverage:
	$(REPO_PYTHON) -m pytest tests/unit/ tests/integration/ --cov=apps --cov-report=term-missing --cov-report=html

## Build local self-hosted release images and run the service-first smoke path
self-host-smoke:
	bash scripts/self_host_smoke.sh

## Prove restart persistence and backup/restore against the local self-hosted stack
self-host-persistence-proof:
	bash scripts/self_host_persistence_proof.sh

## Run a fresh temp-directory install proof against local self-hosted release artifacts
self-host-install-proof:
	bash scripts/self_host_install_proof.sh

## Run the broader self-hosted endpoint matrix against an already-running stack
self-host-endpoint-matrix:
	if [ -z "$${ALGENTA_BASE_URL:-}" ] || [ -z "$${ALGENTA_API_KEY:-}" ] || [ -z "$${ALGENTA_BOOTSTRAP_EMAIL:-}" ] || [ -z "$${ALGENTA_BOOTSTRAP_PASSWORD:-}" ]; then \
		echo "ALGENTA_BASE_URL, ALGENTA_API_KEY, ALGENTA_BOOTSTRAP_EMAIL, and ALGENTA_BOOTSTRAP_PASSWORD are required."; \
		exit 1; \
	fi; \
	$(REPO_PYTHON) scripts/self_host_endpoint_matrix.py \
		--base-url "$${ALGENTA_BASE_URL}" \
		--api-key "$${ALGENTA_API_KEY}" \
		--bootstrap-email "$${ALGENTA_BOOTSTRAP_EMAIL}" \
		--bootstrap-password "$${ALGENTA_BOOTSTRAP_PASSWORD}"

## Validate the GitBook v1 navigation contract and page split
docs-gitbook-status:
	$(REPO_PYTHON) scripts/check_gitbook_v1_docs.py

## Export the GitBook v1 publishing pack into build/gitbook-v1
docs-gitbook-pack:
	$(REPO_PYTHON) scripts/export_gitbook_v1_pack.py

## Validate and export the GitBook v1 publishing pack
docs-gitbook-verify: docs-gitbook-status docs-gitbook-pack

## Regenerate the source-driven docs reference pages (config, errors, rate limits)
docs-gen:
	$(REPO_PYTHON) scripts/docs/gen_config_reference.py
	$(REPO_PYTHON) scripts/docs/gen_error_reference.py
	$(REPO_PYTHON) scripts/docs/gen_limits_reference.py
	$(REPO_PYTHON) scripts/docs/gen_openapi_pages.py
	$(REPO_PYTHON) scripts/docs/gen_runtime_library_reference.py

## Docs coverage gate: fail if any source-derived name (MCP tool, SDK method, CLI command,
## connector, backend, OpenAPI path, error meaning) is absent from gitbook/. Proves 100% coverage.
docs-coverage:
	$(REPO_PYTHON) scripts/docs/check_docs_coverage.py

## CI no-drift gate: fail if any generated reference page is stale vs the code
docs-check:
	$(REPO_PYTHON) scripts/docs/gen_config_reference.py --check
	$(REPO_PYTHON) scripts/docs/gen_error_reference.py --check
	$(REPO_PYTHON) scripts/docs/gen_limits_reference.py --check
	$(REPO_PYTHON) scripts/docs/gen_openapi_pages.py --check
	$(REPO_PYTHON) scripts/docs/gen_runtime_library_reference.py --check
	$(REPO_PYTHON) scripts/docs/check_docs_coverage.py

## capability-plane-verify: run the focused capability-plane proof bundle across contract, API, MCP, runtime, CLI, and docs
capability-plane-verify:
	$(REPO_PYTHON) -m pytest -q \
		tests/test_capability_plane_contract_parity.py \
		tests/test_capability_plane_typed_failure_parity.py \
		tests/test_capability_plane_public_agnosticity.py \
		tests/test_capability_plane_agnostic_contract.py \
		tests/test_capability_plane_api.py \
		tests/test_capability_plane_examples.py \
		tests/test_capability_plane_importer.py \
		tests/test_algenta_runtime_capability_plane.py \
		tests/test_decision_engine_capability_plane_client_surface.py \
		tests/test_cli_data.py \
		tests/test_cli_capability_plane_docs.py \
		tests/test_sdk_capability_plane_docs.py \
		tests/test_service_docs_privacy.py \
		tests/test_example_docs_privacy.py \
		tests/test_package_distribution_surface.py \
		tests/test_runtime_surface_compatibility.py \
		tests/test_mcp_meta_tools.py \
		tests/test_mcp_capability_plane_tools.py \
		tests/test_gitbook_v1_docs.py && \
		pnpm --filter algenta-sdk test -- src/capability_plane.test.ts

## repository-intelligence-channel-parity: run the live Repository Intelligence parity proof across CLI, SDK, runtime, and MCP surfaces
repository-intelligence-channel-parity:
	$(REPO_PYTHON) scripts/run_repository_intelligence_channel_parity.py \
		--filter "$(RI_CHANNEL_PARITY_FILTER)" \
		--output "$(RI_CHANNEL_PARITY_OUTPUT)" \
		--jobs "$(RI_CHANNEL_PARITY_JOBS)" \
		--logs-dir "$(RI_CHANNEL_PARITY_LOGS_DIR)"

## Run focused self-hosted service contract checks without external connector scope
self-host-status:
	$(REPO_PYTHON) scripts/check_gitbook_v1_docs.py; \
	bash -n install.sh; \
	bash -n scripts/self_host_smoke.sh; \
	bash -n scripts/self_host_persistence_proof.sh; \
	bash -n scripts/self_host_install_proof.sh; \
	$(REPO_PYTHON) -m ruff check \
		apps/api_server/compute/mojo_adapter.py \
		apps/worker/tasks/simulation_task.py \
		scripts/self_host_endpoint_matrix.py \
		tests/test_install_script.py \
		tests/test_self_host_endpoint_matrix.py \
		tests/test_self_host_install_proof_script.py \
		tests/test_self_host_persistence_proof_script.py \
		tests/test_self_host_smoke_script.py \
		tests/test_self_host_contract.py \
		tests/test_gitbook_v1_docs.py \
		tests/test_bootstrap_self_host.py \
		tests/test_mojo_adapter.py \
		tests/test_worker_task_session_factory.py; \
	$(REPO_PYTHON) -m pytest \
		tests/test_install_script.py \
		tests/test_self_host_endpoint_matrix.py \
		tests/test_self_host_install_proof_script.py \
		tests/test_self_host_persistence_proof_script.py \
		tests/test_self_host_smoke_script.py \
		tests/test_self_host_contract.py \
		tests/test_gitbook_v1_docs.py \
		tests/test_bootstrap_self_host.py \
		tests/test_mojo_adapter.py \
		tests/test_worker_task_session_factory.py \
		-q

## Run the full self-hosted go-live proof: focused contract checks plus live smoke
self-host-verify: self-host-status
	$(MAKE) self-host-smoke
	$(MAKE) self-host-persistence-proof ALGENTA_SELF_HOST_PERSISTENCE_SKIP_BUILD=1
	$(MAKE) self-host-install-proof ALGENTA_SELF_HOST_INSTALL_PROOF_SKIP_BUILD=1

## Print current go-live connector matrix status and skip reasons
go-live-status:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_matrix_status

## Print current go-live connector matrix status as JSON
go-live-status-json:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_matrix_status --json

## Print only the Tier 2 credentialed-example go-live matrix status
go-live-status-tier2:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_matrix_status --tiers credentialed_example

## Print only the Tier 3 customer-credential go-live matrix status
go-live-status-tier3:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_matrix_status --tiers customer_credentials_required $$CONNECTOR_ARGS

## Fail unless every matrix case is configured and behavior-ready
go-live-status-strict:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_matrix_status --strict

## Print the Fivetran wave-1 validation status
go-live-status-fivetran:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran status $$CONNECTOR_ARGS

## Print the Fivetran wave-1 validation status as JSON
go-live-status-fivetran-json:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran status --json $$CONNECTOR_ARGS

## Render the frozen Fivetran wave-1 validation report as Markdown
go-live-report-fivetran:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran report $$CONNECTOR_ARGS

## Run the full go-live proof serially: status, connectivity, full real suite, full tests
go-live-verify:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_verify --parallel-tasks $${PARALLEL_TASKS:-4} --mojo-workers $${MOJO_WORKERS:-4} --mojo-timeout $${MOJO_TIMEOUT:-30} $$CONNECTOR_ARGS

## Render the latest go-live verifier summary as a Markdown report without rerunning the suite
go-live-report:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_verify_report

## Fail unless every matrix case is configured and behavior-ready, then run the full serial proof
go-live-verify-all:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_verify --strict --parallel-tasks $${PARALLEL_TASKS:-4} --mojo-workers $${MOJO_WORKERS:-4} --mojo-timeout $${MOJO_TIMEOUT:-30} $$CONNECTOR_ARGS

## Fail unless Tier 2 is configured and behavior-ready, then run the Tier 2 connectivity proof only
go-live-verify-tier2:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_verify --tiers credentialed_example --require-all-configured --require-all-behavior-ready --skip-full-real --skip-pytest --parallel-tasks $${PARALLEL_TASKS:-4} $$CONNECTOR_ARGS

## Fail unless Tier 3 is configured and behavior-ready, then run the Tier 3 connectivity proof only
go-live-verify-tier3:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_verify --tiers customer_credentials_required --require-all-configured --require-all-behavior-ready --skip-full-real --skip-pytest --parallel-tasks $${PARALLEL_TASKS:-4} $$CONNECTOR_ARGS

## Refresh the frozen Fivetran inventory + selection locks from the official docs catalog
go-live-refresh-fivetran-inventory:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran refresh-inventory

## Refresh the frozen Fivetran warehouse baselines under the strict capture safeguards
go-live-refresh-fivetran-baseline:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran refresh-baseline $$CONNECTOR_ARGS

## Hydrate placeholder Fivetran manifest connection IDs from the live account when matches are unambiguous
go-live-hydrate-fivetran-manifest:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran hydrate-manifest $$CONNECTOR_ARGS

## Print the exact manifest entry and remaining placeholder fields for one Fivetran connector
go-live-show-fivetran-manifest:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	if [ -z "$${CONNECTOR:-}" ]; then \
		echo "❌ CONNECTOR is required. Example: make go-live-show-fivetran-manifest CONNECTOR=github"; \
		exit 1; \
	fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran manifest-connector --connector "$$CONNECTOR"

## Inspect live Fivetran destinations, connections, and connector match candidates
go-live-inspect-fivetran-account:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran account --json $$CONNECTOR_ARGS

## Run a focused live Redis connector probe with keys.txt/env-backed credentials
go-live-probe-redis:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_connector_probe --connector redis

## Run a focused live Snowflake connector probe with keys.txt/env-backed credentials
go-live-probe-snowflake:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_connector_probe --connector snowflake

## Run a focused live ClickHouse connector probe with keys.txt/env-backed credentials
go-live-probe-clickhouse:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_connector_probe --connector clickhouse

## Run a focused live Elasticsearch connector probe with keys.txt/env-backed credentials
go-live-probe-elasticsearch:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_connector_probe --connector elasticsearch

## Run a focused live Neo4j connector probe with keys.txt/env-backed credentials
go-live-probe-neo4j:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_connector_probe --connector neo4j

## Measure live ClickHouse probe/validate/fetch consistency with the current keys.txt/env-backed credentials
go-live-bench-clickhouse-consistency:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m benchmarks.clickhouse_live_consistency_benchmark $${ARGS:-}

## Measure live Elasticsearch probe/validate/fetch/browse consistency with the current keys.txt/env-backed credentials
go-live-bench-elasticsearch-consistency:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m benchmarks.elasticsearch_live_consistency_benchmark $${ARGS:-}

## Measure live Neo4j probe/validate/fetch/browse consistency with the current keys.txt/env-backed credentials
go-live-bench-neo4j-consistency:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m benchmarks.neo4j_live_consistency_benchmark $${ARGS:-}

## Run the strict Fivetran wave-1 validation only
go-live-verify-fivetran:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	CONNECTOR_ARGS=""; \
	if [ -n "$${CONNECTOR:-}" ]; then CONNECTOR_ARGS="--connector $$CONNECTOR"; fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran verify $$CONNECTOR_ARGS

## Run the strict pre-baseline Fivetran validation for one connector and allow only missing-baseline blockers
go-live-verify-fivetran-prebaseline:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	if [ -z "$${CONNECTOR:-}" ]; then \
		echo "❌ CONNECTOR is required. Example: make go-live-verify-fivetran-prebaseline CONNECTOR=github"; \
		exit 1; \
	fi; \
	PYTHONPATH=. "$$PY_BIN" -m tests.go_live_fivetran verify --pre-baseline --connector "$$CONNECTOR"

## Run the real connectivity + behavioral SLA gate
test-go-live-connectivity:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -u tests/integration/test_go_live_connectivity_real.py --parallel-tasks $${PARALLEL_TASKS:-4}

## Run only the Tier 2 credentialed-example connectivity + behavioral SLA cases
test-go-live-connectivity-tier2:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -u tests/integration/test_go_live_connectivity_real.py --parallel-tasks $${PARALLEL_TASKS:-4} --tiers credentialed_example

## Run only the Tier 3 customer-credential connectivity + behavioral SLA cases
test-go-live-connectivity-tier3:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -u tests/integration/test_go_live_connectivity_real.py --parallel-tasks $${PARALLEL_TASKS:-4} --tiers customer_credentials_required

## Run the full curated real-path go-live suite
test-go-live-full:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -u tests/integration/test_go_live_full_real.py --parallel-tasks $${PARALLEL_TASKS:-4} --mojo-workers $${MOJO_WORKERS:-4} --mojo-timeout $${MOJO_TIMEOUT:-30}

## Run the deterministic generated CSV correctness gate
test-csv-generic:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m pytest tests/test_csv_generic_ingestion.py -q

## Run the real root-corpus CSV regression gate
test-csv-regression:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" -m pytest tests/test_csv_regression_corpus.py tests/test_columnar_loading.py -q

## Run all blocking CSV correctness surfaces plus curated semantic benchmarks
test-csv-all:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	$(MAKE) test-csv-generic && \
	$(MAKE) test-csv-regression && \
	PYTHONPATH=. "$$PY_BIN" benchmarks/uploaded_csv_exact_benchmark.py && \
	PYTHONPATH=. "$$PY_BIN" benchmarks/uploaded_csv_spec_reconstruction_benchmark.py && \
	PYTHONPATH=. "$$PY_BIN" benchmarks/uploaded_csv_api_warm_benchmark.py

## Run the CSV breadth/perf benchmark against the root corpus only
bench-csv-corpus:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" benchmarks/source_matrix_runtime_benchmark.py --skip-public --skip-db --csv-only

## Run the CSV breadth/perf benchmark against root plus Processed variants
bench-csv-corpus-full:
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	PYTHONPATH=. "$$PY_BIN" benchmarks/source_matrix_runtime_benchmark.py --skip-public --skip-db --csv-only --include-processed-variants

# ─── Code Quality ──────────────────────────────────────────────────────────────

## Run all linters
lint:
	ruff check .
	ruff format --check .
	mypy apps/api_server apps/mcp_server apps/runtime apps/worker

## Install JavaScript package dependencies from the repo root
js-install:
	pnpm install

## Run JavaScript/TypeScript lint checks from the repo root
js-lint:
	pnpm lint

## Run the shipped JavaScript/TypeScript test surface from the repo root
js-test:
	pnpm test

## Build the shipped JavaScript packages from the repo root
js-build:
	pnpm build

## Run the full JavaScript/TypeScript install + lint + test + build path
js-check:
	pnpm check

## Auto-format code
format:
	ruff check --fix .
	ruff format .

## Run type checker only
typecheck:
	mypy apps/api_server apps/mcp_server apps/runtime apps/worker

# ─── OpenAPI ───────────────────────────────────────────────────────────────────

## Generate and validate OpenAPI spec from running API
openapi:
	@echo "Generating OpenAPI spec..."
	@PY_BIN="$$(if [ -x ./.venv/bin/python ]; then echo ./.venv/bin/python; else echo python3; fi)"; \
	mkdir -p schemas/openapi; \
	curl -fsS http://localhost:8000/openapi.json | "$$PY_BIN" -c 'import json, sys, yaml; yaml.safe_dump(json.load(sys.stdin), sys.stdout, sort_keys=False)' > schemas/openapi/openapi.yaml; \
	"$$PY_BIN" -c 'from pathlib import Path; import yaml; from openapi_spec_validator import validate_spec; spec = yaml.safe_load(Path("schemas/openapi/openapi.yaml").read_text()); validate_spec(spec)'; \
	echo "✅ OpenAPI spec generated and validated: schemas/openapi/openapi.yaml"

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
	@PIXI_BIN="$$(command -v pixi 2>/dev/null || true)"; \
	if [ -z "$$PIXI_BIN" ] && [ -x "$(PWD)/.pixi/bin/pixi" ]; then \
		PIXI_BIN="$(PWD)/.pixi/bin/pixi"; \
	fi; \
	if [ ! -f mojo/engine/main.mojo ]; then \
		echo "❌ mojo/engine/main.mojo not found. Restore the native simulation entrypoint before building mojo_build/simulate."; \
		exit 1; \
	fi; \
	if [ -d mojo_env ] && [ -n "$$PIXI_BIN" ]; then \
		PIXI_BIN="$$PIXI_BIN" bash scripts/build_mojo_binary.sh >/dev/null && \
		echo "✅ Mojo engine built: mojo_build/simulate"; \
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

## Public algenta.libraries() catalog latency benchmark (cold manifest + warm catalog)
bench-algenta-mojo-catalog:
	PYTHONPATH=. python3 benchmarks/algenta_mojo_catalog_benchmark.py $${ARGS:-}

## Cold import benchmark for the public algenta package root.
bench-algenta-import:
	PYTHONPATH=. python3 benchmarks/algenta_import_benchmark.py $${ARGS:-}

## Cold import benchmark for the public decision_engine SDK package root.
bench-decision-engine-import:
	PYTHONPATH=. python3 benchmarks/decision_engine_import_benchmark.py $${ARGS:-}

## Cold constructor benchmark for the public decision_engine SDK clients.
bench-decision-engine-client-init:
	PYTHONPATH=. python3 benchmarks/decision_engine_client_init_benchmark.py $${ARGS:-}

## Inline connector preview benchmark: direct preview endpoints versus ephemeral connector fallback.
bench-algenta-connector-preview:
	PYTHONPATH=. python3 benchmarks/algenta_connector_preview_benchmark.py $${ARGS:-}

## Saved connector/dataset read benchmark: short-lived SDK cache for repeated reads.
bench-algenta-runtime-read-cache:
	PYTHONPATH=. python3 benchmarks/algenta_runtime_read_cache_benchmark.py $${ARGS:-}

## Local exact Runtime benchmark: connect, resolve, query, and verify over a registered source.
bench-algenta-local-runtime-exact:
	PYTHONPATH=. python3 benchmarks/algenta_local_runtime_exact_benchmark.py $${ARGS:-}

## Local Runtime connect benchmark: single-source and connect_many registration path.
bench-algenta-local-connect:
	PYTHONPATH=. python3 benchmarks/algenta_local_connect_benchmark.py $${ARGS:-}

## API exact Runtime benchmark: cached exact resolve versus fuzzy API resolve fallback.
bench-algenta-api-exact-resolve:
	PYTHONPATH=. python3 benchmarks/algenta_api_exact_resolve_benchmark.py $${ARGS:-}

## API payload benchmark: resolve/query payload coercion helpers on the public Runtime path.
bench-algenta-api-payload:
	PYTHONPATH=. python3 benchmarks/algenta_api_payload_benchmark.py $${ARGS:-}

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

# ─── Deploy (Fly.io + Cloudflare) ────────────────────────────────────────────────

## Provision Fly apps + Managed Postgres + Upstash + Tigris + volume + cert (idempotent)
bootstrap:
	./scripts/bootstrap.sh

## Deploy everything: Fly apps then the Cloudflare edge (TAG=git-<sha> optional)
deploy:
	./scripts/deploy.sh $(TAG)

## Deploy the Fly apps (engine then api; api runs alembic upgrade head)
deploy-fly:
	./scripts/deploy-fly.sh $(TAG)

## Apply the Cloudflare edge (DNS, TLS Full-Strict, cache, WAF) via OpenTofu
deploy-cloudflare:
	./scripts/deploy-cloudflare.sh

## Deployment health: fly status + /v1/health + required-secrets check
status:
	./scripts/status.sh

## Tail logs (APP=api|engine)
logs:
	./scripts/logs.sh $(APP)

## Roll an app back to a tag (APP=api|engine TAG=git-<sha>)
rollback:
	./scripts/rollback.sh $(APP) $(TAG)

# ─── Help ──────────────────────────────────────────────────────────────────────

## Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/## //' | column -t -s ':' | sort
