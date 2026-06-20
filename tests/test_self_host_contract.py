from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF_HOST_DOC = ROOT / "apps" / "docs" / "docs" / "self-hosting.md"
DOCS_INDEX = ROOT / "apps" / "docs" / "docs" / "index.md"
QUICKSTART_DOC = ROOT / "apps" / "docs" / "docs" / "quickstart.md"
OPERATIONS_INDEX = ROOT / "apps" / "docs" / "docs" / "operations" / "index.md"
TLS_DOC = ROOT / "apps" / "docs" / "docs" / "operations" / "tls-and-reverse-proxy.md"
LOGS_DOC = ROOT / "apps" / "docs" / "docs" / "operations" / "logs-and-metrics.md"
UPGRADE_DOC = ROOT / "apps" / "docs" / "docs" / "operations" / "upgrade-and-rollback.md"
ADVANCED_INDEX = ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "index.md"
BACKUP_DOC = ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "backup-and-recovery.md"
TROUBLESHOOTING_DOC = ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "troubleshooting.md"
SUPPORT_BOUNDARIES_DOC = (
    ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "support-boundaries.md"
)
AUTH_DOC = ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md"
PYTHON_SDK_DOC = ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md"
TS_SDK_DOC = ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md"
HOW_IT_WORKS_DOC = ROOT / "apps" / "docs" / "docs" / "how-algenta-works-today.md"
TRUST_MODEL_DOC = ROOT / "apps" / "docs" / "docs" / "trust-model.md"
LOCAL_RUNTIME_DOC = ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md"
GITBOOK_NAV = ROOT / "apps" / "docs" / "gitbook_v1_navigation.json"
INSTALL_SCRIPT = ROOT / "install.sh"
SELF_HOST_COMPOSE = ROOT / "infra" / "docker" / "docker-compose.selfhosted.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
API_DOCKERFILE = ROOT / "infra" / "docker" / "Dockerfile.api.prod"
WORKER_DOCKERFILE = ROOT / "infra" / "docker" / "Dockerfile.worker.prod"
MAKEFILE = ROOT / "Makefile"
README = ROOT / "README.md"
DOCKERIGNORE = ROOT / ".dockerignore"


def test_gitbook_navigation_manifest_matches_self_host_v1_plan() -> None:
    manifest = json.loads(GITBOOK_NAV.read_text(encoding="utf-8"))

    assert manifest["scope"] == "self_hosted_v1"
    assert [section["label"] for section in manifest["sections"]] == [
        "🧭 Overview",
        "⚡ Quickstart",
        "⚙️ Operations",
        "🛠️ Operations (Advanced)",
        "🔐 API Authentication",
        "📦 SDKs",
    ]
    assert "apps/docs/docs/integrations/local-runtime.md" in manifest["exclude_from_primary_nav"]
    assert "apps/docs/docs/mcp.md" in manifest["exclude_from_primary_nav"]
    assert "apps/docs/docs/direct-api-client.md" in manifest["exclude_from_primary_nav"]
    assert "apps/docs/docs/supported-secondary-modes.md" in manifest["exclude_from_primary_nav"]


def test_overview_is_short_and_points_to_quickstart() -> None:
    text = DOCS_INDEX.read_text(encoding="utf-8")

    assert "# Overview" in text
    assert "curl -sSL https://algenta.ai/install.sh | bash" in text
    assert "Open [Quickstart](/quickstart)." in text
    assert "from algenta import Runtime" not in text
    assert "Backup & Recovery" not in text
    assert "Kubernetes" not in text


def test_quickstart_is_self_host_first_and_minimal() -> None:
    text = QUICKSTART_DOC.read_text(encoding="utf-8")

    assert "# Quickstart" in text
    assert "In this guide you will:" in text
    assert "curl -sSL https://algenta.ai/install.sh | bash" in text
    assert "curl http://localhost:8000/v1/health" in text
    assert "API Key: <SELF_HOST_BOOTSTRAP_KEY>" in text
    assert "export ALGENTA_API_KEY='<SELF_HOST_BOOTSTRAP_KEY>'" in text
    assert "Rotate the bootstrap key" in text
    assert "POST http://localhost:8000/v1/api-keys" in text
    assert '"expires_at":"2028-05-19T00:00:00Z"' in text
    assert "Temporarily export the bootstrap key printed by the installer" in text
    assert "returned `raw_key` value is shown only once" in text
    assert "`key_prefix`" in text
    assert "`expires_at`" in text
    assert "curl -X POST http://localhost:8000/v1/simulate \\" in text
    assert '"objective": "maximize_net_value"' in text
    assert "No SDK or Python install is required to use Algenta." in text
    assert "Next: Configure production setup -> [Operations](/operations)" in text
    assert "Backup & Recovery" not in text
    assert "pip install algenta-sdk" not in text
    assert "pip install algenta-core" not in text
    assert "TLS & Reverse Proxy" not in text
    assert "local runtime" not in text.lower()


def test_operations_docs_cover_setup_tls_logs_and_upgrade() -> None:
    setup = SELF_HOST_DOC.read_text(encoding="utf-8")
    operations = OPERATIONS_INDEX.read_text(encoding="utf-8")
    tls = TLS_DOC.read_text(encoding="utf-8")
    logs = LOGS_DOC.read_text(encoding="utf-8")
    upgrade = UPGRADE_DOC.read_text(encoding="utf-8")

    assert "# Setup & Configuration" in setup
    assert "service product" in setup
    assert "standalone `docker-compose`" in setup
    assert "python scripts/bootstrap_self_host.py" in setup
    assert "POST http://localhost:8000/v1/api-keys" in setup
    assert "DELETE http://localhost:8000/v1/api-keys/${BOOTSTRAP_API_KEY_ID}" in setup
    assert '"expires_at":"2028-05-19T00:00:00Z"' in setup
    assert "one-time" in setup
    assert "BOOTSTRAP_API_KEY_ID" in setup
    assert "BOOTSTRAP_API_KEY_PREFIX" in setup
    assert "replacement key" in setup
    assert "`raw_key` as `ALGENTA_API_KEY`" in setup
    assert "`key_prefix`" in setup
    assert "does not return" in setup
    assert "`raw_key` again" in setup
    assert "ongoing operator and service access" in setup
    assert "ordinary hosted API traffic" in setup
    assert "`X-Algenta-Device-Id`" in setup
    assert "`X-Algenta-Platform`" in setup
    assert "`X-Algenta-Hostname-Hash`" in setup
    assert "`X-Algenta-Device-Binding-Token`" in setup
    assert "ALGENTA_IMAGE_TAG=git-YOUR_RELEASE_TAG" in setup
    assert "ALGENTA_DEPLOYMENT_MODE=self_hosted" in setup
    assert "ALGENTA_DISABLE_CLOUD=1" in setup
    assert "ALGENTA_DISABLE_TELEMETRY=1" in setup
    assert "ALGENTA_TELEMETRY_MODE=local_audit" in setup
    assert "ALGENTA_METERING_MODE=local_audit" in setup
    assert "ALGENTA_ALLOW_OUTBOUND_NETWORK=0" in setup
    assert "ALGENTA_API_PUBLIC_BASE_URL=http://localhost:8000" in setup
    assert "`ALGENTA_DISABLE_TELEMETRY=1` means no outbound or vendor telemetry" in setup
    assert "Algenta keeps user-facing links on the API origin" in setup
    assert "GET /v1/admin/privacy-report" in setup
    assert "`METRICS_SECRET`" in setup
    assert "`RESULT_STORAGE_ENABLED`" in setup
    assert "`POSTGRES_HOST_PORT`" in setup
    assert "`REDIS_HOST_PORT`" in setup
    assert "`MINIO_API_HOST_PORT`" in setup
    assert "`MINIO_CONSOLE_HOST_PORT`" in setup

    assert "# Operations" in operations
    assert "[Setup & Configuration](/self-hosting)" in operations
    assert "[TLS & Reverse Proxy](/operations/tls-and-reverse-proxy)" in operations
    assert "[Logs & Metrics](/operations/logs-and-metrics)" in operations
    assert "[Upgrade & Rollback](/operations/upgrade-and-rollback)" in operations
    assert "[Operations (Advanced)](/operations-advanced)" in operations

    assert "# TLS & Reverse Proxy" in tls
    assert "Configure TLS before exposing the API publicly." in tls
    assert "reverse_proxy 127.0.0.1:8000" in tls
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in tls

    assert "# Logs & Metrics" in logs
    assert "docker compose -f infra/docker/docker-compose.selfhosted.yml ps" in logs
    assert "docker compose -f infra/docker/docker-compose.selfhosted.yml logs -f api" in logs
    assert "docker compose -f infra/docker/docker-compose.selfhosted.yml logs -f worker" in logs
    assert "curl http://localhost:8000/metrics" in logs
    assert "X-Metrics-Secret" in logs
    assert "make self-host-status" in logs
    assert "make self-host-verify" in logs

    assert "# Upgrade & Rollback" in upgrade
    assert "ALGENTA_IMAGE_TAG" in upgrade
    assert "python -m alembic -c apps/api_server/alembic.ini upgrade head" in upgrade
    assert "make self-host-status" in upgrade
    assert "make self-host-verify" in upgrade


def test_advanced_operator_docs_cover_backup_warning_troubleshooting_and_support_boundaries() -> (
    None
):
    advanced = ADVANCED_INDEX.read_text(encoding="utf-8")
    backup = BACKUP_DOC.read_text(encoding="utf-8")
    troubleshooting = TROUBLESHOOTING_DOC.read_text(encoding="utf-8")
    support = SUPPORT_BOUNDARIES_DOC.read_text(encoding="utf-8")

    assert "# Operations (Advanced)" in advanced
    assert "[Backup & Recovery](/operations-advanced/backup-and-recovery)" in advanced
    assert "[Troubleshooting](/operations-advanced/troubleshooting)" in advanced
    assert "[Support Boundaries](/operations-advanced/support-boundaries)" in advanced

    assert "# Backup & Recovery" in backup
    assert (
        "This section is for operators managing backup, restore, and disaster recovery." in backup
    )
    assert "It is not required for first-time setup." in backup
    assert "Configure backups after initial deployment and validation." in backup
    assert "pg_dump -U algenta algenta" in backup
    assert "psql -U algenta -d algenta" in backup
    assert "algenta_minio_data" in backup
    assert "algenta_sources_data" in backup

    assert "# Troubleshooting" in troubleshooting
    assert "docker info" in troubleshooting
    assert "docker compose -f infra/docker/docker-compose.selfhosted.yml ps" in troubleshooting
    assert "curl http://localhost:8000/v1/health" in troubleshooting
    assert "logs --tail=200 api" in troubleshooting
    assert "logs --tail=200 worker" in troubleshooting
    assert "python scripts/bootstrap_self_host.py" in troubleshooting
    assert "BOOTSTRAP_API_KEY_ID=..." in troubleshooting
    assert "BOOTSTRAP_API_KEY_PREFIX=..." in troubleshooting
    assert "curl http://localhost:8000/metrics \\" in troubleshooting
    assert "make self-host-status" in troubleshooting
    assert "make self-host-verify" in troubleshooting

    expected_table = """| Area | Status |
| --- | --- |
| Single VM + Compose | ✅ Supported |
| API + Worker | ✅ Supported |
| Backup/Restore | ✅ Supported |
| SDK usage | ⚠️ Best effort / secondary |
| Kubernetes | ❌ Not supported |
| UI/Portal | ❌ Not included |"""
    assert expected_table in support


def test_auth_and_sdk_docs_are_secondary_to_running_service() -> None:
    auth = AUTH_DOC.read_text(encoding="utf-8")
    python_sdk = PYTHON_SDK_DOC.read_text(encoding="utf-8")
    ts_sdk = TS_SDK_DOC.read_text(encoding="utf-8")

    assert "# API Authentication" in auth
    assert "de_test_" in auth
    assert "<SELF_HOST_BOOTSTRAP_KEY>" in auth
    assert "Authorization: Bearer" in auth
    assert "X-API-Key" in auth
    assert "replacement-key" in auth
    assert "It never returns `raw_key` again." in auth
    assert "[Quickstart](/quickstart)" in auth

    assert "# Python SDK" in python_sdk
    assert "Use the Python SDK after the service is already running." in python_sdk
    assert "pip install algenta-sdk" in python_sdk
    assert "from decision_engine import AlgentaClient" in python_sdk
    assert "submit_job" in python_sdk
    assert "[Quickstart](/quickstart)" in python_sdk
    assert "[API Authentication](/api-reference/authentication)" in python_sdk
    assert "pip install algenta-core" in python_sdk
    assert "from algenta import Runtime" not in python_sdk

    assert "# TypeScript SDK" in ts_sdk
    assert "Use the TypeScript SDK after the service is already running." in ts_sdk
    assert "npm install algenta-sdk" in ts_sdk
    assert 'import { AlgentaClient } from "algenta-sdk";' in ts_sdk
    assert "submitJob" in ts_sdk
    assert "[Quickstart](/quickstart)" in ts_sdk
    assert "[API Authentication](/api-reference/authentication)" in ts_sdk
    assert 'import { Runtime } from "algenta-sdk";' not in ts_sdk


def test_top_level_docs_position_service_first_and_runtime_as_development_surface() -> None:
    readme = README.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    how_it_works = HOW_IT_WORKS_DOC.read_text(encoding="utf-8")
    trust_model = TRUST_MODEL_DOC.read_text(encoding="utf-8")
    local_runtime = LOCAL_RUNTIME_DOC.read_text(encoding="utf-8")
    quickstart = QUICKSTART_DOC.read_text(encoding="utf-8")

    assert "self-hosted decision engine you deploy on your infrastructure" in readme
    assert "Integrate via API or SDK. Run locally for development if needed." in readme
    assert "self-hosted by default" in readme
    assert "GET /v1/admin/privacy-report" in readme
    assert "Development quickstart" in readme
    assert "This section is the **development** surface." in readme
    assert "service-first deterministic execution system" in readme
    assert "local-first deterministic runtime" not in readme

    assert "# Overview" in docs_index
    assert "Open [Quickstart](/quickstart)." in docs_index
    assert "from algenta import Runtime" not in docs_index

    assert "deploy the self-hosted service" in how_it_works
    assert "optional local runtime for development and embedded use" in how_it_works
    assert "local-first runtime" not in how_it_works

    assert "service-first deployment" in trust_model
    assert "`self_hosted` is the private-by-default enterprise profile" in trust_model
    assert "GET /v1/admin/privacy-report" in trust_model
    assert "optional local runtime for development or embedded execution" in trust_model
    assert "local-first execution" not in trust_model

    assert "local development, testing, or embedded execution" in local_runtime
    assert "default `self_hosted` enterprise profile" in local_runtime
    assert "ALGENTA_DEPLOYMENT_MODE=air_gapped" in local_runtime
    assert "default local-first path and the one we recommend first" not in local_runtime
    assert "primary local-runtime docs and SDK path" in local_runtime

    assert "Run your first decision" in quickstart
    assert "No SDK or Python install is required to use Algenta." in quickstart
    assert "local runtime" not in quickstart.lower()


def test_install_script_and_compose_lock_service_only_boundary() -> None:
    install = INSTALL_SCRIPT.read_text(encoding="utf-8")
    compose = SELF_HOST_COMPOSE.read_text(encoding="utf-8")
    dockerfile = API_DOCKERFILE.read_text(encoding="utf-8")
    worker_dockerfile = WORKER_DOCKERFILE.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "https://algenta.ai/install.sh" in install
    assert "/v1/health" in install
    assert "/v1/api-keys" in install
    assert "mission-runtime" in install
    assert "expires_at" in install
    assert "2028-05-19T00:00:00Z" in install
    assert (
        "The returned raw_key is shown once; store it with id, key_prefix, and expires_at before revoking the bootstrap key."
        in install
    )
    assert "Bootstrap key id:" in install
    assert "Bootstrap key prefix:" in install
    assert "Set temporarily:" in install
    assert "paste the bootstrap key above" in install
    assert "Replace it:" in install
    assert "paste the replacement key returned above" in install
    assert "No SDK or Python install is required to use Algenta." in install
    assert "Portal UI" not in install
    assert "bootstrap_self_host.py" in install
    assert "seed_dev.py" not in install
    assert "${COMPOSE_DISPLAY} logs -f api" in install
    assert "${COMPOSE_DISPLAY} logs -f worker" in install
    assert "ALGENTA_SOURCES_DIR=/home/app/.algenta/sources" in install
    assert "RESULT_STORAGE_ENABLED=true" in install
    assert "ALGENTA_DEPLOYMENT_MODE=self_hosted" in install
    assert "ALGENTA_DISABLE_CLOUD=1" in install
    assert "ALGENTA_TELEMETRY_MODE=local_audit" in install

    assert "portal:" not in compose
    # api/worker images are fail-closed on a pinned ALGENTA_IMAGE_TAG (never a silent :latest);
    # enforced by tests/test_image_pin_guard.py.
    assert "/api:${ALGENTA_IMAGE_TAG:?" in compose
    assert "/worker:${ALGENTA_IMAGE_TAG:?" in compose
    assert "command: python -m apps.worker.main" not in compose
    assert "DATABASE_URL_SYNC" in compose
    assert "ALGENTA_SOURCES_DIR" in compose
    assert "RUNTIME_FALLBACK_MODE: ${RUNTIME_FALLBACK_MODE:-deny}" in compose
    assert "RESULT_STORAGE_ENABLED: ${RESULT_STORAGE_ENABLED:-true}" in compose
    assert "${POSTGRES_HOST_PORT:-5432}" in compose
    assert "${REDIS_HOST_PORT:-6379}" in compose
    assert "${MINIO_API_HOST_PORT:-9000}" in compose
    assert "${MINIO_CONSOLE_HOST_PORT:-9001}" in compose
    assert "sources_data:/home/app/.algenta" in compose
    assert "algenta_network" not in compose
    assert "/v1/health" in compose
    assert "useradd --system --gid app --home-dir /home/app --create-home app" in dockerfile
    assert "ENV HOME=/home/app" in dockerfile
    assert "useradd --system --gid app --home-dir /home/app --create-home app" in worker_dockerfile
    assert "ENV HOME=/home/app" in worker_dockerfile
    assert "COPY --from=builder /build/context/engines/ /app/engines/" in dockerfile
    assert "COPY --from=builder /build/context/training/ /app/training/" in dockerfile
    assert "COPY --from=builder /build/context/scripts/ /app/scripts/" in dockerfile
    assert 'CMD ["python", "-m", "celery"' in worker_dockerfile
    assert "apps.worker.tasks.simulation_task:celery_app" in worker_dockerfile
    assert "self-host-status:" in makefile
    assert "self-host-persistence-proof:" in makefile
    assert "self-host-install-proof:" in makefile
    assert "self-host-endpoint-matrix:" in makefile
    assert "self-host-verify:" in makefile
    assert "self-host-smoke:" in makefile
    assert "ALGENTA_SELF_HOST_PERSISTENCE_SKIP_BUILD=1" in makefile
    assert "ALGENTA_SELF_HOST_INSTALL_PROOF_SKIP_BUILD=1" in makefile
    assert "restart: on-failure" not in compose


def test_dockerignore_excludes_heavy_non_runtime_paths_from_self_host_images() -> None:
    text = DOCKERIGNORE.read_text(encoding="utf-8")

    assert ".venv" in text
    assert ".cache" in text
    assert "test_files" in text
    assert "tests" in text
    assert "benchmarks" in text
    assert "apps/docs" in text
    assert "mojo/tests" in text


def test_ci_publishes_pinned_git_sha_tags_for_self_hosted_installs() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "type=sha,prefix=git-,format=short" in workflow


def test_env_example_keeps_result_storage_disabled_by_default_for_dev_bootstrap() -> None:
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "RESULT_STORAGE_ENABLED=false" in env_text
    assert "ALGENTA_DEPLOYMENT_MODE=saas" in env_text
    assert "ALGENTA_EGRESS_ALLOWLIST=" in env_text
    assert "ALGENTA_API_PUBLIC_BASE_URL=" in env_text
    assert "ALGENTA_APP_BASE_URL=" in env_text


def test_self_host_docs_default_private_allowlist_includes_internal_minio() -> None:
    env_text = (ROOT / "apps/docs/docs/self-hosting.md").read_text(encoding="utf-8")

    assert "ALGENTA_EGRESS_ALLOWLIST=minio:9000" in env_text


def test_makefile_mcp_targets_do_not_force_cloud_base_url() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "mcp-stdio:" in text
    assert "mcp-http:" in text
    assert "ALGENTA_BASE_URL=$${ALGENTA_BASE_URL:-https://api.algenta.ai}" not in text
    assert "\tALGENTA_API_KEY=$(ALGENTA_API_KEY) \\" in text
    assert "apps.mcp_server.server --transport stdio" in text
    assert "apps.mcp_server.server --transport http" in text
