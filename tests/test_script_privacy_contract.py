from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_LOCAL_SCRIPT = ROOT / "scripts" / "start-local.sh"
VERIFY_PHASE5A_SCRIPT = ROOT / "scripts" / "verify_phase5a.py"
VERIFY_LIVE_API_SCRIPT = ROOT / "scripts" / "verify_live_api.py"
GITBOOK_AUDIT_SCRIPT = ROOT / "scripts" / "gitbook" / "audit.py"
LEGACY_LIVE_API_KEY_LITERAL = "de_live_" + "LrL6UWSAfgXsTjgfyaboI9aolrsznjLU"
LOCAL_PLACEHOLDER_KEY_LITERAL = "de_live_" + "testonlyplaceholderdonotuse1234567890abcd"


def _script_env(*, skip_env_file: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("DE_API_KEY", None)
    env.pop("ALGENTA_API_KEY", None)
    env.pop("ALGENTA_BASE_URL", None)
    env.pop("DE_BASE_URL", None)
    env.pop("ALGENTA_API_URL", None)
    env.pop("ALGENTA_DEPLOYMENT_MODE", None)
    env.pop("ALGENTA_DISABLE_CLOUD", None)
    env.pop("ALGENTA_ALLOW_OUTBOUND_NETWORK", None)
    env.pop("ALGENTA_EGRESS_ALLOWLIST", None)
    if skip_env_file:
        env["ALGENTA_SKIP_ENV_FILE"] = "1"
    else:
        env.pop("ALGENTA_SKIP_ENV_FILE", None)
    return env


def test_verify_phase5a_requires_explicit_api_key() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_PHASE5A_SCRIPT)],
        cwd=ROOT,
        env=_script_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "ALGENTA_API_KEY or DE_API_KEY must be set" in result.stderr
    assert "No default live key is bundled with this script." in result.stderr


def test_gitbook_audit_uses_public_algenta_placeholder_convention() -> None:
    text = GITBOOK_AUDIT_SCRIPT.read_text(encoding="utf-8")

    assert "$ALGENTA_API_KEY convention" in text
    assert "CODNA_TOKEN" not in text


def test_start_local_requires_explicit_api_key_when_env_file_is_skipped() -> None:
    result = subprocess.run(
        ["bash", str(START_LOCAL_SCRIPT)],
        cwd=ROOT,
        env=_script_env(skip_env_file=True),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "ALGENTA_API_KEY or DE_API_KEY must be set" in result.stderr
    assert "No default API key is bundled with this script." in result.stderr


def test_start_local_propagates_all_supported_base_url_aliases_to_mcp_server() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'API_PORT="${ALGENTA_API_PORT:-8000}"' in text
    assert 'API_BASE_URL="http://localhost:$API_PORT"' in text
    assert 'ALGENTA_API_KEY="$API_KEY"' in text
    assert 'DE_API_KEY="$API_KEY"' in text
    assert 'ALGENTA_BASE_URL="$API_BASE_URL"' in text
    assert 'DE_BASE_URL="$API_BASE_URL"' in text
    assert 'ALGENTA_API_URL="$API_BASE_URL"' in text


def test_start_local_supports_explicit_env_file_path() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert '_capture_env_override() {' in text
    assert '_restore_env_override() {' in text
    assert 'ENV_FILE_PATH="${ALGENTA_ENV_FILE:-${DE_ENV_FILE:-$ROOT/.env}}"' in text
    assert '[ "${ALGENTA_SKIP_ENV_FILE:-0}" != "1" ] && [ -f "$ENV_FILE_PATH" ]' in text
    assert 'ENV_EXPORTS="$(python3 "$ROOT/scripts/emit_start_local_env_exports.py" "$ENV_FILE_PATH")"' in text
    assert 'eval "$ENV_EXPORTS"' in text
    assert '_capture_env_override "$START_LOCAL_OVERRIDE_KEY"' in text
    assert '_restore_env_override "$START_LOCAL_OVERRIDE_KEY"' in text
    assert 'ALGENTA_API_PORT \\' in text
    assert 'ALGENTA_MCP_PORT \\' in text
    assert 'ALGENTA_LLM_PROVIDER_MODELS_JSON \\' in text


def test_start_local_auto_derives_provider_router_registry_when_unset() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'EFFECTIVE_PROVIDER_MODELS_JSON="${ALGENTA_LLM_PROVIDER_MODELS_JSON:-$DEFAULT_LOCAL_PROVIDER_MODELS_JSON}"' in text
    assert 'ALGENTA_LLM_PROVIDER_MODELS_JSON="$EFFECTIVE_PROVIDER_MODELS_JSON"' in text
    assert 'DEFAULT_LOCAL_PROVIDER_MODELS_JSON="$(python3 "$ROOT/scripts/emit_local_provider_registry.py")"' in text
    assert 'python3 "$ROOT/scripts/emit_local_provider_registry.py" --has-router "$EFFECTIVE_PROVIDER_MODELS_JSON"' in text
    assert 'ALGENTA_LLM_PROVIDER_MODELS_JSON must be a valid provider registry JSON array.' in text


def test_start_local_only_claims_provider_router_when_registry_contains_router() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'if [ "$PROVIDER_ROUTER_ENABLED" = "1" ]; then' in text
    assert 'echo "   LLM:  provider.router enabled on /v1/models"' in text


def test_start_local_bootstraps_mcp_http_dependencies_and_uses_canonical_routes() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert 'API_HEALTH_URL="$API_BASE_URL/v1/health"' in text
    assert 'MCP_TOOLS_URL="http://localhost:$MCP_PORT/mcp/tools"' in text
    assert 'MCP_URL="http://localhost:$MCP_PORT/mcp"' in text
    assert 'UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/uv-cache}"' in text
    assert 'START_LOCAL_STATE_DIR="$ROOT/build/start-local"' in text
    assert 'API_PID_FILE="$START_LOCAL_STATE_DIR/api-$API_PORT.pid"' in text
    assert 'MCP_PID_FILE="$START_LOCAL_STATE_DIR/mcp-$MCP_PORT.pid"' in text
    assert 'API_LEASE_FILE="$START_LOCAL_STATE_DIR/api-$API_PORT.lease"' in text
    assert 'MCP_LEASE_FILE="$START_LOCAL_STATE_DIR/mcp-$MCP_PORT.lease"' in text
    assert 'UV_CACHE_DIR="$UV_CACHE_DIR" uv run --isolated --with-requirements "$ROOT/requirements-mcp.txt" python - <<\'PY\'' in text
    assert "from apps.mcp_server.registry import TOOLS" in text
    assert 'python3 "$ROOT/scripts/detach_process.py"' in text
    assert 'python3 "$ROOT/scripts/lease_supervisor.py" \\' in text
    assert '--stdout-log /tmp/algenta-api.log' in text
    assert '--stdout-log /tmp/algenta-mcp.log' in text
    assert '--lease-file "$API_LEASE_FILE" \\' in text
    assert '--lease-file "$MCP_LEASE_FILE" \\' in text
    assert '--lease-token "$API_LEASE_TOKEN" \\' in text
    assert '--lease-token "$MCP_LEASE_TOKEN" \\' in text
    assert '-- \\' in text
    assert 'API server exited before becoming ready. Check /tmp/algenta-api.log.' in text
    assert 'API health endpoint did not become ready at $API_HEALTH_URL.' in text
    assert 'API listener PID could not be resolved on port $API_PORT.' in text
    assert 'Port $API_PORT is already in use by a non-start-local process.' in text
    assert 'Port $MCP_PORT is already in use by a non-start-local process.' in text
    assert 'ALGENTA_LLM_PROVIDER_MODELS_JSON="$EFFECTIVE_PROVIDER_MODELS_JSON" \\' in text
    assert 'uv run uvicorn apps.api_server.main:app --port "$API_PORT"' in text
    assert 'PYTHONPATH=. \\' in text
    assert 'uv run --isolated --with-requirements "$ROOT/requirements-mcp.txt"' in text
    assert 'python -m apps.mcp_server.server --mode http --port "$MCP_PORT"' in text
    assert 'MCP server exited before becoming ready. Check /tmp/algenta-mcp.log.' in text
    assert 'MCP tools endpoint did not become ready at $MCP_TOOLS_URL.' in text
    assert 'MCP listener PID could not be resolved on port $MCP_PORT.' in text
    assert 'echo "   MCP:  $MCP_URL — $TOOL_COUNT tools"' in text
    assert 'echo "Mission Platform will auto-connect via ALGENTA_MCP_URL=$MCP_URL"' in text
    assert 'nohup ' not in text
    assert 'kill $(lsof -ti :8000)' not in text
    assert 'kill $(lsof -ti :$MCP_PORT)' not in text


def test_start_local_only_stops_recorded_processes_and_cleans_partial_start() -> None:
    text = START_LOCAL_SCRIPT.read_text(encoding="utf-8")

    assert '_prune_stale_state_files() {' in text
    assert 'for state_file in "$START_LOCAL_STATE_DIR"/api-*.pid "$START_LOCAL_STATE_DIR"/mcp-*.pid; do' in text
    assert 'local base_path="${state_file%.pid}"' in text
    assert 'local lease_file="${base_path}.lease"' in text
    assert 'echo "  Cleared orphaned state $(basename "$state_file")"' in text
    assert '_prune_stale_state_files' in text
    assert '_generate_lease_token() {' in text
    assert '_retire_recorded_process "$API_PID_FILE" "$API_LEASE_FILE" "$API_PORT" "API"' in text
    assert '_retire_recorded_process "$MCP_PID_FILE" "$MCP_LEASE_FILE" "$MCP_PORT" "MCP"' in text
    assert 'rm -f "$lease_file"' in text
    assert 'if ! _port_in_use "$port"; then' in text
    assert 'echo "  Cleared stale $label lease"' in text
    assert 'echo "  Stopped previous $label"' in text
    assert 'echo "Failed to stop previous $label on port $port."' in text
    assert 'API_PID="$(_listening_pid "$API_PORT")"' in text
    assert 'MCP_PID="$(_listening_pid "$MCP_PORT")"' in text
    assert 'printf \'%s\\n\' "$API_LEASE_TOKEN" > "$API_LEASE_FILE"' in text
    assert 'printf \'%s\\n\' "$MCP_LEASE_TOKEN" > "$MCP_LEASE_FILE"' in text
    assert 'printf \'%s\\n\' "$API_PID" > "$API_PID_FILE"' in text
    assert 'printf \'%s\\n\' "$MCP_PID" > "$MCP_PID_FILE"' in text
    assert 'trap _cleanup_partial_start EXIT' in text
    assert 'trap - EXIT' in text
    assert 'rm -f "$API_PID_FILE" "$MCP_PID_FILE" "$API_LEASE_FILE" "$MCP_LEASE_FILE"' in text
    assert 'START_LOCAL_READY=1' in text


def test_requirements_mcp_includes_fastapi_for_http_transport() -> None:
    text = (ROOT / "requirements-mcp.txt").read_text(encoding="utf-8")

    assert "fastapi==0.133.1" in text
    assert "mcp==2.0.0" in text
    assert "starlette==1.3.1" in text


def test_verify_live_api_honors_explicit_base_url_argument() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_LIVE_API_SCRIPT), "--base-url", "http://127.0.0.1:9"],
        cwd=ROOT,
        env=_script_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Cannot connect to http://127.0.0.1:9" in result.stdout


def test_verify_live_api_uses_contract_prefix_helper_for_invalid_keys() -> None:
    text = VERIFY_LIVE_API_SCRIPT.read_text(encoding="utf-8")

    assert "from apps.platform_contract_constants import API_KEY_PREFIX_LIVE" in text
    assert 'headers={"X-API-Key": _invalid_api_key(' in text
    assert "de_live_totally_invalid_key_that_does_not_exist" not in text
    assert 'de_live_something' not in text
    assert 'de_live_fakekeyfortestingonly1234567' not in text


def test_run_diagnostics_uses_contract_prefix_constant_for_key_generation() -> None:
    text = (ROOT / "scripts" / "run_diagnostics.py").read_text(encoding="utf-8")

    assert "from apps.platform_contract_constants import API_KEY_PREFIX_LIVE" in text
    assert "raw.startswith(API_KEY_PREFIX_LIVE)" in text
    assert 'Key should start with de_live_' not in text


def test_self_host_proof_scripts_load_api_key_contract_helper() -> None:
    helper_text = (ROOT / "scripts" / "api_key_contract.sh").read_text(encoding="utf-8")
    assert "API_KEY_PREFIX" in helper_text
    assert "API_KEY_TEST_PREFIX" in helper_text

    for relative_path in (
        "scripts/self_host_smoke.sh",
        "scripts/self_host_persistence_proof.sh",
        "scripts/self_host_install_proof.sh",
    ):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'source "$ROOT_DIR/scripts/api_key_contract.sh"' in text

    smoke_text = (ROOT / "scripts" / "self_host_smoke.sh").read_text(encoding="utf-8")
    assert "API_KEY_PREFIX=${API_KEY_PREFIX}" in smoke_text
    assert "API_KEY_TEST_PREFIX=${API_KEY_TEST_PREFIX}" in smoke_text
    assert "API_KEY_PREFIX=de_live_" not in smoke_text
    assert "API_KEY_TEST_PREFIX=de_test_" not in smoke_text

    persistence_text = (ROOT / "scripts" / "self_host_persistence_proof.sh").read_text(
        encoding="utf-8"
    )
    assert "API_KEY_PREFIX=${API_KEY_PREFIX}" in persistence_text
    assert "API_KEY_TEST_PREFIX=${API_KEY_TEST_PREFIX}" in persistence_text
    assert "API_KEY_PREFIX=de_live_" not in persistence_text
    assert "API_KEY_TEST_PREFIX=de_test_" not in persistence_text

    install_text = (ROOT / "scripts" / "self_host_install_proof.sh").read_text(
        encoding="utf-8"
    )
    assert 'API_KEY_TEST_PREFIX="$API_KEY_TEST_PREFIX" python3 - "$OUTPUT_FILE"' in install_text
    assert 'de_test_[A-Za-z0-9._\\-]+' not in install_text


def test_verify_live_api_private_profile_requires_explicit_base_url() -> None:
    env = _script_env()
    env["ALGENTA_DEPLOYMENT_MODE"] = "self_hosted"

    result = subprocess.run(
        [sys.executable, str(VERIFY_LIVE_API_SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "verify_live_api.py private profiles require an explicit self-hosted API origin" in result.stderr


def test_verify_phase5a_private_profile_requires_explicit_base_url() -> None:
    env = _script_env()
    env["ALGENTA_DEPLOYMENT_MODE"] = "self_hosted"
    env["ALGENTA_API_KEY"] = LOCAL_PLACEHOLDER_KEY_LITERAL

    result = subprocess.run(
        [sys.executable, str(VERIFY_PHASE5A_SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "verify_phase5a.py private profiles require an explicit self-hosted API origin" in result.stderr


def test_repo_no_longer_contains_legacy_live_api_key_literal() -> None:
    matches: list[str] = []
    for base in (ROOT / "scripts", ROOT / "tests"):
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".sh"}:
                continue
            if path == Path(__file__):
                continue
            if LEGACY_LIVE_API_KEY_LITERAL in path.read_text(encoding="utf-8"):
                matches.append(str(path.relative_to(ROOT)))

    assert matches == []


def test_integration_harness_uses_shared_local_placeholder_module() -> None:
    matches: list[str] = []
    allowed = {
        ROOT / "tests" / "integration" / "live_local_defaults.py",
        Path(__file__),
    }
    for path in [ROOT / "tests" / "run_all.py", *sorted((ROOT / "tests" / "integration").rglob("*.py"))]:
        if path in allowed:
            continue
        if LOCAL_PLACEHOLDER_KEY_LITERAL in path.read_text(encoding="utf-8"):
            matches.append(str(path.relative_to(ROOT)))

    assert matches == []


def test_integration_harness_uses_shared_local_base_url_module() -> None:
    forbidden_fragments = (
        'os.environ.get("DE_BASE_URL", "http://localhost:8000")',
        'os.environ.get("DE_BASE_URL", "http://localhost:8000").rstrip("/")',
        'CONFIGURED_BASE_URL = os.environ.get("DE_BASE_URL")',
    )
    matches: list[str] = []
    allowed = {
        ROOT / "tests" / "integration" / "live_local_defaults.py",
        Path(__file__),
    }
    for path in [
        ROOT / "tests" / "run_all.py",
        ROOT / "tests" / "conftest.py",
        *sorted((ROOT / "tests" / "integration").rglob("*.py")),
    ]:
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if any(fragment in text for fragment in forbidden_fragments):
            matches.append(str(path.relative_to(ROOT)))

    assert matches == []
