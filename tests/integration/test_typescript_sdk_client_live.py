"""
Live TypeScript SDK client integration tests against a real API server.

This validates the direct TypeScript client path:
  - health and version helpers
  - governed contract and runtime-proof routes
  - decision runtime helpers
  - plan-aligned LLM utility routes
  - quota-aware decision planning, agent-runs, and simulate path

Run:
  DE_API_KEY="..." python3 tests/integration/test_typescript_sdk_client_live.py
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_typescript_sdk_client_live.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)


import atexit
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

socket.setdefaulttimeout(15)

ROOT = Path(__file__).resolve().parents[2]
TS_SDK_DIR = ROOT / "packages" / "ts-sdk"
TS_DIST_ENTRY_CANDIDATES = (
    TS_SDK_DIR / "dist" / "index.mjs",
    TS_SDK_DIR / "dist" / "index.js",
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from apps.platform_contract import PlatformContractResponse  # noqa: E402
from apps.runtime_manifest import (  # noqa: E402
    RuntimeAdminBenchmarksResponse,
    normalize_runtime_validation_payload,
)
from tests._manifest_backed_integrations import (
    contract_integrations_match_manifest,
)
from tests.integration.live_capacity_blockers import (
    classify_simulation_capacity_blocker,  # noqa: E402
)
from tests.integration.live_check_filter import (  # noqa: E402
    filtered_live_check_reason,
    live_check_filter_tokens,
    selected_live_check_filter,
    should_run_live_check,
)
from tests.integration.live_data_source_server import (  # noqa: E402
    default_refreshable_dataset_payload,
    static_json_server,
)
from tests.integration.live_integration_artifacts import (
    write_live_integration_summary,  # noqa: E402
)
from tests.integration.live_local_surface_env import (  # noqa: E402
    configure_local_live_server_env,
)
from tests.integration.live_repository_fixture import (  # noqa: E402
    assert_repository_intelligence_capabilities_payload,
    live_repository_fixture,
    local_repository_live_support_reason,
)
from tests.integration.live_webhook_receiver import webhook_receiver  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
try:
    from tests.integration.live_local_auth_bootstrap import (
        ensure_bootstrapped_local_live_api_key,
    )
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )
except ModuleNotFoundError:
    from live_local_auth_bootstrap import ensure_bootstrapped_local_live_api_key
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )

CONFIGURED_BASE_URL = configured_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
SUITE_NAME = "typescript_sdk_client_live"
STARTED = time.perf_counter()
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple[str, str, str]] = []
MISSING_JOB_ID = "00000000-0000-0000-0000-000000000001"


class EnvironmentBlocked(RuntimeError):  # noqa: N818
    """Raised when live capacity or quota blocks this integration path."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _assert_empty_provider_trace_payload(
    payload: dict[str, Any], *, output_items: bool = False
) -> None:
    assert payload["provider_backend"] is None, payload
    assert payload["provider_model_id"] is None, payload
    assert payload["provider_attempts"] == [], payload
    if output_items:
        for item in payload["output"]:
            assert item["provider_backend"] is None, item
            assert item["provider_model_id"] is None, item
            assert item["provider_attempts"] == [], item


def _pnpm_command() -> list[str]:
    for candidate in (["pnpm"], ["corepack", "pnpm"], ["npx", "pnpm"]):
        try:
            subprocess.run(
                [candidate[0], "--version"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            return candidate
        except Exception:
            continue
    raise FileNotFoundError("Unable to find pnpm-compatible package manager.")


def _resolve_ts_dist_entry() -> Path | None:
    for candidate in TS_DIST_ENTRY_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _ensure_ts_sdk_dist() -> Path:
    entry = _resolve_ts_dist_entry()
    if entry is not None:
        return entry
    proc = subprocess.run(
        [*_pnpm_command(), "--dir", str(TS_SDK_DIR), "build"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TypeScript SDK build failed.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    entry = _resolve_ts_dist_entry()
    if entry is None:
        checked = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"Built TypeScript SDK entry missing. Checked: {checked}")
    return entry


def _read_log(log_path: Path | None) -> str:
    if log_path is None:
        return ""
    try:
        contents = log_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not contents:
        return ""
    return f"\nServer log:\n{contents}"


def _port_open(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _choose_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((DEFAULT_HOST, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _probe_json(
    base_url: str,
    path: str,
    timeout: float = 3.0,
    *,
    headers: dict[str, str] | None = None,
):
    request = urllib.request.Request(
        f"{base_url}{path}",
        headers=headers or {},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, json.loads(body)
        except Exception:
            return err.code, body.decode("utf-8", errors="replace")


def _wait_for_health(base_url: str, log_path: Path, timeout_seconds: float = 30.0) -> None:
    start = time.monotonic()
    last_error = "no response"
    while time.monotonic() - start < timeout_seconds:
        if _runtime_proc is not None and _runtime_proc.poll() is not None:
            raise RuntimeError(
                f"Runtime API exited before readiness probe with code {_runtime_proc.returncode}."
                f"{_read_log(log_path)}"
            )
        try:
            status, _body = _probe_json(base_url, "/v1/health", timeout=2.0)
            if status == 200:
                return
            last_error = f"status {status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


def _endpoint_serves_canonical_ts_sdk_surface(base_url: str) -> bool:
    try:
        status, health = _probe_json(base_url, "/v1/health", timeout=3.0)
        if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
            return False
        auth_headers = {"Authorization": f"Bearer {API_KEY}"}
        status, contract = _probe_json(
            base_url,
            "/v1/meta/contract",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(contract, dict):
            return False
        PlatformContractResponse.model_validate(contract)
        if not contract_integrations_match_manifest(contract["integrations"]):
            return False
        status, benchmarks = _probe_json(
            base_url,
            "/v1/admin/runtime/benchmarks",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(benchmarks, dict):
            return False
        RuntimeAdminBenchmarksResponse.model_validate(
            normalize_runtime_validation_payload(benchmarks)
        )
        status, spec = _probe_json(base_url, "/openapi.json", timeout=5.0)
        if status != 200 or not isinstance(spec, dict):
            return False
        expected_security = [{"BearerAuth": []}, {"LegacyApiKey": []}]
        for path, method in (
            ("/v1/meta/contract", "get"),
            ("/v1/runtime/manifest", "get"),
            ("/v1/admin/runtime/modules", "get"),
            ("/v1/admin/runtime/benchmarks", "get"),
            ("/v1/admin/runtime/validation", "get"),
            ("/v1/me", "get"),
            ("/v1/me", "patch"),
            ("/v1/usage", "get"),
            ("/v1/limits", "get"),
            ("/v1/connectors", "get"),
            ("/v1/connectors", "post"),
            ("/v1/connectors/test", "post"),
            ("/v1/connectors/browse", "post"),
            ("/v1/connectors/{connector_id}", "get"),
            ("/v1/connectors/{connector_id}", "patch"),
            ("/v1/connectors/{connector_id}/test", "post"),
            ("/v1/connectors/{connector_id}/browse", "get"),
            ("/v1/connectors/{connector_id}", "delete"),
            ("/v1/data/connect", "post"),
            ("/v1/data", "get"),
            ("/v1/data/{dataset_id}", "get"),
            ("/v1/data/{dataset_id}/summary", "get"),
            ("/v1/data/{dataset_id}/refresh", "post"),
            ("/v1/data/{dataset_id}", "delete"),
            ("/v1/repositories/capabilities", "get"),
            ("/v1/repositories/{repository_id}/snapshots", "post"),
            ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
            ("/v1/repositories/{repository_id}/triage", "post"),
            ("/v1/repositories/{repository_id}/decision-plans", "post"),
            ("/v1/repositories/{repository_id}/simulate", "post"),
            ("/v1/repositories/{repository_id}/apply", "post"),
            ("/v1/distributions", "get"),
            ("/v1/templates", "get"),
            ("/v1/billing/info", "get"),
            ("/v1/api-keys", "get"),
            ("/v1/api-keys", "post"),
            ("/v1/api-keys/{key_id}", "delete"),
            ("/v1/webhooks/test", "post"),
            ("/v1/jobs/list", "get"),
            ("/v1/jobs/{job_id}", "get"),
            ("/v1/jobs/{job_id}/result", "get"),
            ("/v1/jobs/{job_id}/cancel", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
            ("/v1/metering", "post"),
            ("/v1/credits/refresh", "post"),
            ("/v1/team", "get"),
            ("/v1/team/invite", "post"),
            ("/v1/team/{user_id}/role", "patch"),
            ("/v1/team/{user_id}", "delete"),
            ("/v1/device/list", "get"),
            ("/v1/device/{registration_id}", "delete"),
            ("/v1/audit-logs", "get"),
            ("/v1/audit-logs/artifacts", "get"),
            ("/v1/execution/policy", "get"),
            ("/v1/execution/policy/snapshots", "get"),
            ("/v1/execution/policy", "patch"),
            ("/v1/recommend", "post"),
            ("/v1/score", "post"),
            ("/v1/batch", "post"),
            ("/v1/compare", "post"),
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
            ("/v1/deployments/regions", "get"),
            ("/v1/deployments", "get"),
            ("/v1/chat/completions", "post"),
            ("/v1/responses", "post"),
            ("/v1/embeddings", "post"),
            ("/v1/embeddings/similarity", "post"),
            ("/v1/rerank", "post"),
            ("/v1/decision", "post"),
            ("/v1/agent/run", "post"),
            ("/v1/optimize", "post"),
            ("/v1/retrieve", "post"),
            ("/v1/forecast", "post"),
            ("/v1/decisions/plan", "post"),
            ("/v1/decisions", "post"),
            ("/v1/decisions", "get"),
            ("/v1/decisions/{decision_id}", "get"),
            ("/v1/decisions/{decision_id}/outcome", "patch"),
            ("/v1/decisions/{decision_id}/execute", "post"),
            ("/v1/decisions/{decision_id}", "delete"),
            ("/v1/agent/runs", "post"),
            ("/v1/agent/runs", "get"),
            ("/v1/agent/runs/{run_id}", "get"),
            ("/v1/agent/runs/{run_id}/events", "get"),
            ("/v1/agent/runs/{run_id}/checkpoints", "get"),
            ("/v1/agent/runs/checkpoints", "get"),
            ("/v1/agent/runs/{run_id}/mission-events", "get"),
            ("/v1/agent/runs/mission-events", "get"),
            ("/v1/agent/runs/{run_id}/telemetry", "get"),
            ("/v1/agent/runs/telemetry", "get"),
            ("/v1/agent/runs/{run_id}/approve", "post"),
        ):
            operation = spec.get("paths", {}).get(path, {}).get(method, {})
            if path in {"/v1/meta/contract", "/v1/runtime/manifest"}:
                if operation.get("security") not in ([], None):
                    return False
            elif operation.get("security") != expected_security:
                return False
        for path, method in (
            ("/v1/chat/completions", "post"),
            ("/v1/responses", "post"),
            ("/v1/agent/runs/{run_id}/events", "get"),
        ):
            content = (
                spec.get("paths", {})
                .get(path, {})
                .get(method, {})
                .get("responses", {})
                .get("200", {})
                .get("content", {})
            )
            if "text/event-stream" not in content:
                return False
        status, models = _probe_json(
            base_url,
            "/v1/models",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(models, dict) or not isinstance(models.get("data"), list):
            return False
        return True
    except Exception:
        return False


def _cleanup_runtime() -> None:
    global _runtime_proc
    if not _runtime_started_here or _runtime_proc is None:
        return
    _runtime_proc.terminate()
    try:
        _runtime_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _runtime_proc.kill()
        _runtime_proc.wait(timeout=5)
    _runtime_proc = None


def _resolve_base_url() -> str:
    global _runtime_proc, _runtime_started_here, _runtime_log_path
    if CONFIGURED_BASE_URL:
        return CONFIGURED_BASE_URL.rstrip("/")

    base_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    log_dir = Path(tempfile.mkdtemp(prefix="integration-typescript-sdk-client-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_ts_sdk_surface(base_url):
                return base_url
        except RuntimeError:
            pass

    port = _choose_free_port()
    base_url = f"http://{DEFAULT_HOST}:{port}"
    env = os.environ.copy()
    env.setdefault("ALGENTA_SOURCE_REGISTRY_ROOT", str(log_dir / "sources"))
    env.setdefault("ALGENTA_RUNTIME_DIR", str(log_dir / "runtime"))
    env.setdefault("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL", "repository.deterministic_local_v1")
    env = configure_local_live_server_env(env, root_dir=log_dir)
    with log_path.open("w", encoding="utf-8") as log_handle:
        _runtime_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api_server.main:app",
                "--host",
                DEFAULT_HOST,
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    _runtime_started_here = True
    _runtime_log_path = log_path
    _wait_for_health(base_url, log_path)
    return base_url


BASE_URL = _resolve_base_url()
API_KEY, API_KEY_CONFIGURED, LOCAL_LIVE_AUTH_BOOTSTRAP_ERROR = (
    ensure_bootstrapped_local_live_api_key(
        api_key=API_KEY,
        api_key_configured=API_KEY_CONFIGURED,
        active_base_url=BASE_URL,
    )
)
atexit.register(_cleanup_runtime)

NODE_RUNNER_SOURCE = """
import { pathToFileURL } from 'node:url';

const sdkModule = await import(pathToFileURL(process.env.TS_SDK_DIST_ENTRY).href);
const { AlgentaClient } = sdkModule;
const client = new AlgentaClient({
  apiKey: process.env.DE_API_KEY,
  baseUrl: process.env.DE_BASE_URL,
  maxRetries: 0,
});

function output(payload) {
  process.stdout.write(JSON.stringify(payload));
}

async function captureJobError(operation) {
  try {
    const value = await operation();
    return { ok: true, value };
  } catch (error) {
    return {
      ok: false,
      name: error?.name ?? 'Error',
      message: error?.message ?? String(error),
      statusCode: error?.statusCode ?? null,
      errorCode: error?.errorCode ?? null,
      responseBody: error?.responseBody ?? null,
    };
  }
}

async function captureApiError(operation) {
  try {
    const value = await operation();
    return { ok: true, value };
  } catch (error) {
    return {
      ok: false,
      name: error?.name ?? 'Error',
      message: error?.message ?? String(error),
      statusCode: error?.statusCode ?? null,
      errorCode: error?.errorCode ?? null,
      responseBody: error?.responseBody ?? null,
    };
  }
}

async function main() {
  const kind = process.argv[2];
  try {
    switch (kind) {
      case 'health': {
        const health = await client.health();
        const version = await client.version();
        output({ ok: true, health, version });
        return;
      }
      case 'proof': {
        const contract = await client.getContract();
        const manifest = await client.getRuntimeManifest();
        const modules = await client.getRuntimeModules();
        const benchmarks = await client.getRuntimeBenchmarks();
        const validation = await client.getRuntimeReleaseValidation();
        output({ ok: true, contract, manifest, modules, benchmarks, validation });
        return;
      }
      case 'account': {
        const me = await client.me();
        const usage = await client.usage();
        const limits = await client.limits();
        const distributions = await client.distributions();
        const templates = await client.templates();
        const label = `ts-sdk-account-${Date.now()}-${process.pid}`;
        let created = null;
        let requestedDeviceLimit = 2;
        try {
          const listedBefore = await client.listApiKeys();
          try {
            created = await client.createApiKey({
              label,
              expires_at: '2028-05-19T00:00:00Z',
              device_limit: requestedDeviceLimit,
            });
          } catch (error) {
            if (error?.errorCode !== 'invalid_device_limit') {
              throw error;
            }
            requestedDeviceLimit = 0;
            created = await client.createApiKey({
              label,
              expires_at: '2028-05-19T00:00:00Z',
            });
          }
          const listedAfter = await client.listApiKeys();
          const revoke = await client.revokeApiKey(created.id);
          const listedFinal = await client.listApiKeys();
          output({
            ok: true,
            me,
            usage,
            limits,
            distributions,
            templates,
            listedBefore,
            created,
            requestedDeviceLimit,
            listedAfter,
            revoke,
            listedFinal,
          });
          return;
        } catch (error) {
          if (created && typeof created.id === 'string') {
            try {
              await client.revokeApiKey(created.id);
            } catch {}
          }
          throw error;
        }
      }
      case 'datasets': {
        if (!process.env.DE_REFRESHABLE_DATASET_URL) {
          throw new Error('DE_REFRESHABLE_DATASET_URL is required for dataset checks.');
        }
        const connectors = await client.listConnectors({ page: 1, limit: 50 });
        const previewTestedConnector = await client.previewTestConnector({
          connector_type: 'rest',
          config: {
            url: process.env.DE_REFRESHABLE_DATASET_URL,
            data_path: 'items',
          },
        });
        const previewBrowsedConnector = await client.previewBrowseConnector({
          connector_type: 'rest',
          config: {
            url: process.env.DE_REFRESHABLE_DATASET_URL,
            data_path: 'items',
          },
        });
        const savedConnector = await client.createConnector({
          name: `ts-sdk-connector-${Date.now()}-${process.pid}`,
          connector_type: 'rest',
          description: 'Live TypeScript SDK saved connector check.',
          config: {
            url: process.env.DE_REFRESHABLE_DATASET_URL,
            data_path: 'items',
          },
        });
        const connectorId = savedConnector.id;
        if (!connectorId) {
          throw new Error(`saved connector response missing id: ${JSON.stringify(savedConnector)}`);
        }
        try {
          const created = await client.connectData({
            connection_type: 'api',
            provider: 'rest',
            dataset_name: `ts-sdk-refreshable-${Date.now()}-${process.pid}`,
            description: 'Live TypeScript SDK refreshable dataset check.',
            connection_config: {
              url: process.env.DE_REFRESHABLE_DATASET_URL,
              data_path: 'items',
            },
          });
          const datasetId = created.dataset_id;
          const datasetName = created.dataset_name;
          if (!datasetId || !datasetName) {
            throw new Error(`dataset connect response missing identifiers: ${JSON.stringify(created)}`);
          }

          const listedConnectors = await client.listConnectors({ page: 1, limit: 25 });
          const connectorDetail = await client.getConnector(connectorId);
          const updatedConnector = await client.updateConnector(connectorId, {
            description: 'Live TypeScript SDK connector updated description.',
          });
          const testedConnector = await client.testConnector(connectorId);
          const browsedConnector = await client.browseConnector(connectorId);
          try {
            const datasets = await client.listDatasets({
              search: datasetName,
              compact: true,
              page: 1,
              limit: 25,
            });
            const refreshed = await client.refreshDataset(datasetId);
            const summary = await client.getDatasetSummary(datasetId);
            const detail = await client.getDataset(datasetId);
            output({
              ok: true,
              connectors,
              previewTestedConnector,
              previewBrowsedConnector,
              savedConnector,
              listedConnectors,
              connectorDetail,
              updatedConnector,
              testedConnector,
              browsedConnector,
              created,
              datasets,
              refreshed,
              summary,
              detail,
            });
            return;
          } finally {
            await client.deleteDataset(datasetId);
          }
        } finally {
          await client.deleteConnector(connectorId);
        }
      }
      case 'repositories': {
        if (!process.env.DE_LOCAL_REPOSITORY_PATH) {
          throw new Error('DE_LOCAL_REPOSITORY_PATH is required for repository checks.');
        }
        const capabilities = await client.getRepositoryIntelligenceCapabilities();
        const savedConnector = await client.createConnector({
          name: `ts-sdk-repository-${Date.now()}-${process.pid}`,
          connector_type: 'local_repo',
          description: 'Live TypeScript SDK repository intelligence check.',
          config: {
            path: process.env.DE_LOCAL_REPOSITORY_PATH,
          },
        });
        const repositoryId = savedConnector.id;
        if (!repositoryId) {
          throw new Error(`saved repository connector response missing id: ${JSON.stringify(savedConnector)}`);
        }
        try {
          const snapshot = await client.createRepositorySnapshot(repositoryId, {
            include_patterns: ['src/**', 'tests/**', 'README.md'],
            exclude_patterns: ['**/__pycache__/**'],
            max_files: 128,
            max_file_size_bytes: 100000,
          });
          const fetchedSnapshot = await client.getRepositorySnapshot(repositoryId, snapshot.snapshot_id);
          const repeatedSnapshot = await client.createRepositorySnapshot(repositoryId, {
            include_patterns: ['src/**', 'tests/**', 'README.md'],
            exclude_patterns: ['**/__pycache__/**'],
            max_files: 128,
            max_file_size_bytes: 100000,
          });
          const triage = await client.triageRepository(repositoryId, {
            snapshot_id: snapshot.snapshot_id,
            signals: {
              issue_text: 'Production regression: normalize_status returns closed for OPEN inputs after the latest deploy.',
              diagnostics: [
                {
                  path: 'src/service.py',
                  line: 4,
                  severity: 'error',
                  message: \"normalize_status('OPEN') returns 'closed' instead of 'open'.\",
                },
              ],
              failing_tests: ['tests/test_service.py::test_normalize_status_open'],
              changed_files: ['src/service.py'],
              workspace_context: ['incident/normalize-status-regression', 'jira/REPO-1842'],
            },
          });
          const graph = await client.queryRepositoryGraph(repositoryId, {
            snapshot_id: snapshot.snapshot_id,
            workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
            file_path: 'src/service.py',
            symbol_name: 'normalize_status',
            direction: 'both',
            max_depth: 2,
            max_nodes: 64,
          });
          const planAttempt = await captureApiError(() =>
            client.createRepositoryDecisionPlan(repositoryId, {
              snapshot_id: snapshot.snapshot_id,
              workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
            }),
          );
          let simulation = null;
          let applyAttempt = null;
          if (planAttempt.ok) {
            simulation = await client.simulateRepository(repositoryId, {
              snapshot_id: snapshot.snapshot_id,
              decision_plan_id: planAttempt.value.decision_plan_id,
              runs: 1000,
              seed: 42,
            });
            const simulationId = simulation?.validated_inputs?.simulation_id;
            if (!simulationId) {
              throw new Error(`repository simulation missing simulation_id: ${JSON.stringify(simulation)}`);
            }
            applyAttempt = await captureApiError(() =>
              client.applyRepository(repositoryId, {
                snapshot_id: snapshot.snapshot_id,
                decision_plan_id: planAttempt.value.decision_plan_id,
                simulation_id: simulationId,
                mode: 'local_branch',
                write_permission: true,
                branch_name: 'algenta/live-repository-fix',
              }),
            );
          }
          output({
            ok: true,
            capabilities,
            savedConnector,
            snapshot,
            fetchedSnapshot,
            repeatedSnapshot,
            triage,
            graph,
            planAttempt,
            simulation,
            applyAttempt,
          });
          return;
        } finally {
          try {
            await client.deleteConnector(repositoryId);
          } catch (error) {
            if (error?.statusCode !== 404 && error?.errorCode !== 'not_found') {
              throw error;
            }
          }
        }
      }
      case 'control_plane': {
        const team = await client.listTeamMembers({ page: 1, limit: 50 });
        const jobs = await client.listJobs({ page: 1, limit: 5, status: 'queued' });
        const missingJob = await captureJobError(() => client.getJob('00000000-0000-0000-0000-000000000001'));
        const missingJobResult = await captureJobError(() => client.getJobResult('00000000-0000-0000-0000-000000000001'));
        const cancelledMissingJob = await captureJobError(() => client.cancelJob('00000000-0000-0000-0000-000000000001'));
        const polledMissingJob = await captureJobError(() => client.pollJob('00000000-0000-0000-0000-000000000001', { timeoutMs: 10, pollIntervalMs: 1 }));
        const billing = await client.getBillingInfo();
        const credits = await client.refreshCredits({
          device_id: `ts-sdk-credit-live-${Date.now()}-${process.pid}`,
          billing_period: new Date().toISOString().slice(0, 7),
          credits_used: 0,
        });
        const metering = await client.ingestMeteringEvents({
          device_id: `ts-sdk-live-${Date.now()}-${process.pid}`,
          events: [
            {
              event_type: 'runtime_call',
              module: 'integration',
              function: 'typescript_sdk_client_live',
              engine_used: 'typescript',
              latency_ms: 14.5,
              success: true,
            },
          ],
        });
        const webhook = process.env.DE_TEST_WEBHOOK_URL
          ? await client.testWebhookDelivery(process.env.DE_TEST_WEBHOOK_URL)
          : null;
        const devices = await client.listDevices({ page: 1, limit: 25 });
        const logs = await client.getAuditLogs({ page: 1, limit: 20 });
        const policy = await client.getExecutionPolicy();
        const snapshots = await client.listExecutionPolicySnapshots();
        const updated = await client.updateExecutionPolicy({
          min_confidence: policy.min_confidence,
          risk_floor: policy.risk_floor,
          require_calibration: policy.require_calibration,
          allow_reexecution: policy.allow_reexecution,
        });
        output({
          ok: true,
          team,
          jobs,
          missingJob,
          missingJobResult,
          cancelledMissingJob,
          polledMissingJob,
          billing,
          credits,
          metering,
          webhook,
          devices,
          logs,
          policy,
          snapshots,
          updated,
        });
        return;
      }
      case 'triggers': {
        let created = null;
        try {
          created = await client.registerTrigger({
            name: `ts-sdk-trigger-${Date.now()}-${process.pid}`,
            condition: {
              source_id: `missing_source_ts_sdk_${Date.now()}_${process.pid}`,
              metric_hint: 'revenue',
              threshold: 1000,
              direction: 'above',
              aggregation: 'sum',
            },
            simulation_template: {
              mode: 'auto',
              scenario: {
                variables: { revenue: { low: 1000, high: 2000 } },
                objective: 'maximize_net_value',
              },
              runs: 50,
            },
            description: 'Live TypeScript SDK trigger lifecycle check.',
            auto_execute: false,
          });
          const listed = await client.listTriggers({ status: 'all', page: 1, limit: 25 });
          const fired = await client.fireTrigger(created.trigger_id, { force: false });
          const paused = await client.pauseTrigger(created.trigger_id, { paused: true });
          const resumed = await client.pauseTrigger(created.trigger_id, { paused: false });
          const deleted = await client.deleteTrigger(created.trigger_id);
          output({ ok: true, created, listed, fired, paused, resumed, deleted });
          return;
        } catch (error) {
          if (created?.trigger_id) {
            try {
              await client.deleteTrigger(created.trigger_id);
            } catch {}
          }
          throw error;
        }
      }
      case 'deployment_lifecycle': {
        const current = await client.getDeployment();
        if (current) {
          output({
            ok: false,
            error: {
              name: 'EnvironmentBlocked',
              message: 'deployment mutation requires an org without an existing deployment',
              statusCode: 409,
              errorCode: 'deployment_exists',
              responseBody: { error: { code: 'deployment_exists' } },
            },
          });
          return;
        }
        const created = await client.createDeployment({
          provider: 'algenta_shared',
          region: 'algenta-shared',
          config: { instance_size: 'small' },
          billing_markup_pct: 20,
        });
        const cost = await client.getDeploymentCost(created.deployment_id);
        const deleted = await client.deleteDeployment(created.deployment_id);
        output({ ok: true, created, cost, deleted });
        return;
      }
      case 'llm': {
        const models = await client.listModels();
        const artifact = await client.resolveArtifactBridge({
          repo_id: 'bert-base-uncased',
          filename: 'model.safetensors',
          revision: 'main',
          local_files_only: true,
        });
        const tokenized = await client.tokenize({ input: 'alpha beta gamma' });
        const counted = await client.countTokens({ input: 'alpha beta gamma' });
        const deploymentRegions = await client.listDeploymentRegions();
        const deployment = await client.getDeployment();
        const deploymentCost =
          deployment && deployment.deployment_id
            ? await client.getDeploymentCost(deployment.deployment_id)
            : null;
        const chat = await client.chatCompletions({
          messages: [{ role: 'user', content: 'summarize alpha beta' }],
        });
        const responses = await client.responses({ input: 'alpha beta' });
        const embeddings = await client.embeddings({
          input: ['alpha beta', 'gamma'],
          dimensions: 8,
        });
        const similarity = await client.embeddingSimilarity({
          left: [1.0, 0.0],
          right: [0.5, 0.5],
        });
        const rerank = await client.rerank({
          query_embedding: [1.0, 0.0],
          documents: [
            { id: 'doc_a', embedding: [1.0, 0.0], text: 'alpha' },
            { id: 'doc_b', embedding: [0.0, 1.0], text: 'beta' },
          ],
          top_n: 2,
        });
        output({
          ok: true,
          models,
          artifact,
          tokenized,
          counted,
          deploymentRegions,
          deployment,
          deploymentCost,
          chat,
          responses,
          embeddings,
          similarity,
          rerank,
        });
        return;
      }
      case 'decision': {
        const recommendation = await client.recommend(
          [
            {
              name: 'expand',
              request: {
                mode: 'expert',
                runs: 250,
                simulation: {
                  variables: [
                    {
                      name: 'outcome',
                      distribution: 'fixed',
                      params: { value: 140000 },
                    },
                  ],
                  objective_function: 'outcome',
                },
              },
            },
            {
              name: 'hold',
              request: {
                mode: 'expert',
                runs: 250,
                simulation: {
                  variables: [
                    {
                      name: 'outcome',
                      distribution: 'fixed',
                      params: { value: 90000 },
                    },
                  ],
                  objective_function: 'outcome',
                },
              },
            },
          ],
          { runs: 250, seed: 42 },
        );
        const score = await client.score(
          {
            mode: 'expert',
            runs: 250,
            simulation: {
              variables: [
                {
                  name: 'outcome',
                  distribution: 'normal',
                  params: { mean: 100, std: 10 },
                },
              ],
              objective_function: 'outcome',
            },
          },
          { expected_value: 0.7, downside_risk: 0.3 },
        );
        const batch = await client.batch([
          {
            mode: 'expert',
            runs: 100,
            simulation: {
              variables: [{ name: 'outcome', distribution: 'fixed', params: { value: 100 } }],
              objective_function: 'outcome',
            },
          },
          {
            mode: 'expert',
            runs: 100,
            simulation: {
              variables: [{ name: 'outcome', distribution: 'fixed', params: { value: 120 } }],
              objective_function: 'outcome',
            },
          },
        ]);
        const compared = await client.compare([
          {
            name: 'base',
            request: {
              mode: 'expert',
              runs: 150,
              simulation: {
                variables: [{ name: 'outcome', distribution: 'fixed', params: { value: 100 } }],
                objective_function: 'outcome',
              },
            },
          },
          {
            name: 'stretch',
            request: {
              mode: 'expert',
              runs: 150,
              simulation: {
                variables: [{ name: 'outcome', distribution: 'fixed', params: { value: 120 } }],
                objective_function: 'outcome',
              },
            },
          },
        ]);
        output({ ok: true, recommendation, score, batch, compared });
        return;
      }
      case 'product': {
        const decision = await client.productDecision({
          inputs: [
            {
              name: 'revenue',
              value: 120000,
              low: 100000,
              high: 150000,
              unit: 'USD',
            },
            {
              name: 'cost',
              value: 70000,
              low: 60000,
              high: 90000,
              unit: 'USD',
            },
          ],
          risk_tolerance: 'medium',
          scenarios: 1000,
        });
        const agentRun = await client.productAgentRun({
          task: `Summarize benchmark blockers ${Date.now()}`,
          tools: ['search'],
          max_steps: 3,
        });
        const optimize = await client.productOptimize({
          objective: 'maximize profit',
          variables: [
            { name: 'price', min: 50, max: 150 },
            { name: 'discount', min: 0.0, max: 0.2 },
          ],
          iterations: 100,
        });
        const retrieve = await client.productRetrieve({
          query: 'launch checklist',
          documents: [
            { id: 'doc_1', content: 'Launch checklist for product release.' },
            { id: 'doc_2', content: 'Pricing review for launch approval.' },
          ],
          top_k: 2,
        });
        const forecast = await client.productForecast({
          metric: 'monthly_revenue',
          history: [100, 120, 130, 140],
          horizon: 3,
        });
        output({ ok: true, decision, agentRun, optimize, retrieve, forecast });
        return;
      }
      case 'stream': {
        const chatChunks = [];
        for await (const chunk of client.streamChatCompletions({
          messages: [{ role: 'user', content: 'summarize alpha beta' }],
        })) {
          chatChunks.push(chunk);
        }
        const responseEvents = [];
        for await (const event of client.streamResponses({ input: 'alpha beta' })) {
          responseEvents.push(event);
        }
        output({ ok: true, chatChunks, responseEvents });
        return;
      }
      case 'agent_stream': {
        const created = await client.createAgentRun({
          task: `Search benchmark notes ${Date.now()}`,
          tools: ['search'],
          approval_mode: 'auto',
        });
        const streamedEvents = [];
        for await (const event of client.streamAgentRunEvents(created.run_id, { limit: 20 })) {
          streamedEvents.push(event);
        }
        output({ ok: true, created, streamedEvents });
        return;
      }
      case 'plan': {
        const plan = await client.planDecision({
          mode: 'expert',
          runs: 250,
          simulation: {
            variables: [
              {
                name: 'outcome',
                distribution: 'normal',
                params: { mean: 100, std: 10 },
              },
            ],
            objective_function: 'outcome',
          },
        });
        const created = await client.createAgentRun({
          task: `Search benchmark notes ${Date.now()}`,
          tools: ['search'],
          approval_mode: 'manual',
        });
        const fetched = await client.getAgentRun(created.run_id);
        const events = await client.getAgentRunEvents(created.run_id, { limit: 20 });
        const approved = await client.approveAgentRun(created.run_id);
        output({ ok: true, plan, created, fetched, events, approved });
        return;
      }
      case 'simulate': {
        const result = await client.simulate({
          mode: 'auto',
          runs: 200,
          scenario: {
            variables: { revenue: { low: 120000, high: 140000 } },
            objective: 'maximize_net_value',
          },
        });
        output({ ok: true, result });
        return;
      }
      default:
        output({ ok: false, error: { message: `unknown check kind: ${kind}` } });
    }
  } catch (error) {
    output({
      ok: false,
      error: {
        name: error?.name ?? 'Error',
        message: error?.message ?? String(error),
        statusCode: error?.statusCode ?? null,
        errorCode: error?.errorCode ?? null,
        responseBody: error?.responseBody ?? null,
      },
    });
  }
}

await main();
"""


def _run_node_check(
    kind: str,
    *,
    webhook_url: str | None = None,
    dataset_source_url: str | None = None,
    repository_path: str | None = None,
) -> dict[str, Any]:
    dist_entry = _ensure_ts_sdk_dist()
    with tempfile.TemporaryDirectory(prefix="ts-sdk-client-live-") as tmp_dir:
        script_path = Path(tmp_dir) / "runner.mjs"
        script_path.write_text(NODE_RUNNER_SOURCE, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(script_path), kind],
            cwd=str(ROOT),
            env={
                **os.environ,
                "DE_API_KEY": API_KEY,
                "DE_BASE_URL": BASE_URL,
                "DE_TEST_WEBHOOK_URL": webhook_url or "",
                "DE_REFRESHABLE_DATASET_URL": dataset_source_url or "",
                "DE_LOCAL_REPOSITORY_PATH": repository_path or "",
                "TS_SDK_DIST_ENTRY": str(dist_entry),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TypeScript SDK live check failed for {kind}.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"TypeScript SDK live check produced invalid JSON for {kind}: {proc.stdout}"
        ) from exc
    if payload.get("ok") is True:
        return payload
    error = payload.get("error", {})
    raise RuntimeError(json.dumps(error, sort_keys=True))


def _capacity_reason_from_failure(exc: Exception) -> str | None:
    message = str(exc)
    payload: dict[str, Any] | None = None
    status: int | None = None
    try:
        parsed = json.loads(message)
        if isinstance(parsed, dict):
            payload = parsed.get("responseBody")
            raw_status = parsed.get("statusCode")
            if isinstance(raw_status, int):
                status = raw_status
            message = str(parsed.get("message") or message)
    except json.JSONDecodeError:
        payload = None
    return classify_simulation_capacity_blocker(
        status=status,
        payload=payload,
        text=message,
    )


def raise_if_capacity_blocked(exc: Exception) -> None:
    reason = _capacity_reason_from_failure(exc)
    if reason:
        raise EnvironmentBlocked(reason) from exc


def raise_if_credit_refresh_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    status = parsed.get("statusCode")
    payload = parsed.get("responseBody")
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            code = raw_code
    text = str(parsed.get("message") or exc).lower()
    if status == 429 and code in {"quota_exhausted", "quota_exceeded"}:
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment") from exc
    if status == 429 and ("quota_exhausted" in text or "quota_exceeded" in text):
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment") from exc


def raise_if_artifact_bridge_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    payload = parsed.get("responseBody")
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise EnvironmentBlocked(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        ) from exc


def raise_if_deployment_mutation_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    status = parsed.get("statusCode")
    code = parsed.get("errorCode")
    if status == 403:
        raise EnvironmentBlocked("deployment mutation requires owner role") from exc
    if status == 409 or code == "deployment_exists":
        raise EnvironmentBlocked(
            "deployment mutation requires an org without an existing deployment"
        ) from exc


def _assert_repository_error_payload(
    payload: dict[str, Any],
    *,
    status_code: int,
    error_code: str,
) -> None:
    assert payload["statusCode"] == status_code, payload
    assert payload["errorCode"] == error_code, payload
    response_body = payload.get("responseBody")
    detail = (
        response_body.get("detail", response_body.get("error"))
        if isinstance(response_body, dict)
        else None
    )
    error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(error, dict), response_body
    assert error.get("code") == error_code, response_body


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    text = str(exc)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        status = parsed.get("statusCode")
        if status == 401 or parsed.get("errorCode") == "invalid_api_key":
            return (
                "DE_API_KEY is not set; skipping authenticated TypeScript SDK checks that "
                "require a real live key."
            )
    if "invalid_api_key" in text or "invalid, expired, or has been revoked" in text:
        return (
            "DE_API_KEY is not set; skipping authenticated TypeScript SDK checks that require "
            "a real live key."
        )
    return None


def check(name: str, fn) -> None:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    if not should_run_live_check(name, ACTIVE_LIVE_CHECK_FILTER_TOKENS):
        reason = filtered_live_check_reason(ACTIVE_LIVE_CHECK_FILTER)
        results.append((SKIP, name, reason))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {reason}")
        return
    try:
        fn()
        results.append((PASS, name, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as exc:
        results.append((SKIP, name, str(exc)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except AssertionError as exc:
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except Exception as exc:  # noqa: BLE001
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        message = f"{type(exc).__name__}: {exc}"
        results.append((FAIL, name, message))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {message}")


def _write_summary() -> Path:
    passed = sum(1 for status, *_ in results if status == PASS)
    failed = sum(1 for status, *_ in results if status == FAIL)
    skipped = sum(1 for status, *_ in results if status == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_typescript_sdk_client_live.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "api_key_configured": API_KEY_CONFIGURED,
            "base_url": BASE_URL,
            "failed_checks": [name for status, name, _ in results if status == FAIL],
            "skipped_checks": [name for status, name, _ in results if status == SKIP],
        },
    )
    _emit(f"\nSummary artifact: {artifact}")
    return artifact


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live TypeScript SDK integration.")
    response = _probe_json(BASE_URL, "/v1/health", timeout=5.0)
    assert response[0] == 200, f"/v1/health returned {response[0]}"


def test_client_health_and_version() -> None:
    payload = _run_node_check("health")
    health = payload["health"]
    version = payload["version"]
    assert health["status"] == "ok", health
    assert version["api_version"], version
    assert version["engine_version"], version


def test_client_contract_and_runtime_proof_routes() -> None:
    payload = _run_node_check("proof")
    contract = payload["contract"]
    manifest = payload["manifest"]
    modules = payload["modules"]
    benchmarks = payload["benchmarks"]
    validation = payload["validation"]
    assert isinstance(contract["api_base_url"], str) and contract["api_base_url"].startswith("http")
    assert contract["mcp_endpoint"].endswith("/mcp")
    assert manifest["runtime_version"]
    assert len(manifest["modules"]) >= 1
    manifest_provider_routing_overhead = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B8"),
        None,
    )
    assert manifest_provider_routing_overhead is not None, manifest["benchmarking"]["classes"]
    assert manifest_provider_routing_overhead["description"] == "provider routing overhead"
    assert manifest_provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    manifest_checkpoint_replay_overhead = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B6"),
        None,
    )
    assert manifest_checkpoint_replay_overhead is not None, manifest["benchmarking"]["classes"]
    assert manifest_checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"
    assert manifest_checkpoint_replay_overhead["evidence_paths"] == []
    manifest_decision_workflow_completion = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B10"),
        None,
    )
    assert manifest_decision_workflow_completion is not None, manifest["benchmarking"]["classes"]
    assert (
        manifest_decision_workflow_completion["description"]
        == "decision workflow completion latency"
    )
    assert manifest_decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]
    assert len(modules["modules"]) >= 1
    assert modules["summary"]["module_count"] >= 1
    assert len(benchmarks["module_benchmarks"]) >= 1
    provider_routing_overhead = next(
        (entry for entry in benchmarks["benchmarking"]["classes"] if entry["code"] == "B8"),
        None,
    )
    assert provider_routing_overhead is not None, benchmarks["benchmarking"]["classes"]
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_replay_overhead = next(
        (entry for entry in benchmarks["quality_gate_benchmark_classes"] if entry["code"] == "B6"),
        None,
    )
    assert checkpoint_replay_overhead is not None, benchmarks["quality_gate_benchmark_classes"]
    assert checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_replay_overhead["evidence_paths"] == []
    decision_workflow_completion = next(
        (entry for entry in benchmarks["quality_gate_benchmark_classes"] if entry["code"] == "B10"),
        None,
    )
    assert decision_workflow_completion is not None, benchmarks["quality_gate_benchmark_classes"]
    assert decision_workflow_completion["description"] == "decision workflow completion latency"
    assert decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]
    assert {entry["code"] for entry in benchmarks["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in benchmarks["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert benchmarks["evaluation_summary"]["replay_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["decision_quality_gate_enabled"] is True
    assert validation["valid_release"] is True


def test_client_account_surface() -> None:
    payload = _run_node_check("account")
    me = payload["me"]
    usage = payload["usage"]
    limits = payload["limits"]
    distributions = payload["distributions"]
    templates = payload["templates"]
    created = payload["created"]
    requested_device_limit = payload["requestedDeviceLimit"]
    listed_after = payload["listedAfter"]
    listed_final = payload["listedFinal"]

    assert any(key in me for key in ("org_id", "organization", "email", "user", "org")), me
    assert usage["billing_period"]
    assert usage["quota_limit"] >= 0
    assert any(
        key in limits for key in ("plan", "simulations_per_month", "rate_limit_per_minute")
    ), limits
    assert distributions["page"] == 1
    assert distributions["limit"] >= 1
    assert distributions["total"] >= len(distributions["distributions"])
    assert distributions["pages"] >= 1
    assert distributions["distributions"]
    assert distributions["distributions"][0]["name"]
    assert templates["page"] == 1
    assert templates["limit"] >= 1
    assert templates["total"] >= len(templates["templates"])
    assert templates["pages"] >= 1
    assert templates["templates"]
    assert templates["templates"][0]["id"]
    assert created["label"].startswith("ts-sdk-account-")
    assert created["device_limit"] == requested_device_limit
    assert created["raw_key"].startswith(created["key_prefix"])
    listed_match = next((entry for entry in listed_after if entry["id"] == created["id"]), None)
    assert isinstance(listed_match, dict), "Created API key missing from listApiKeys()"
    assert listed_match["device_limit"] == requested_device_limit
    assert listed_match["expires_at"] == "2028-05-19T00:00:00Z"
    assert listed_match["key_prefix"] == created["key_prefix"]
    assert not any(entry["id"] == created["id"] for entry in listed_final)


def test_client_dataset_surface() -> None:
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        payload = _run_node_check("datasets", dataset_source_url=source_url)
    connectors = payload["connectors"]
    preview_tested_connector = payload["previewTestedConnector"]
    preview_browsed_connector = payload["previewBrowsedConnector"]
    saved_connector = payload["savedConnector"]
    listed_connectors = payload["listedConnectors"]
    connector_detail = payload["connectorDetail"]
    updated_connector = payload["updatedConnector"]
    tested_connector = payload["testedConnector"]
    browsed_connector = payload["browsedConnector"]
    created = payload["created"]
    datasets = payload["datasets"]
    refreshed = payload["refreshed"]
    summary = payload["summary"]
    detail = payload["detail"]

    assert connectors["page"] == 1
    assert connectors["limit"] == 50
    assert connectors["total"] >= len(connectors["connectors"])
    assert connectors["pages"] >= 1
    assert preview_tested_connector["success"] is True
    assert preview_tested_connector["status"] == "live"
    assert preview_browsed_connector["connector_type"] == "rest"
    assert preview_browsed_connector["total"] >= 1
    assert saved_connector["id"]
    assert saved_connector["name"]
    assert listed_connectors["page"] == 1
    assert listed_connectors["limit"] == 25
    assert listed_connectors["total"] >= len(listed_connectors["connectors"])
    assert any(item["id"] == saved_connector["id"] for item in listed_connectors["connectors"])
    assert connector_detail["id"] == saved_connector["id"]
    assert connector_detail["name"] == saved_connector["name"]
    assert updated_connector["id"] == saved_connector["id"]
    assert updated_connector["description"] == "Live TypeScript SDK connector updated description."
    assert tested_connector["success"] is True
    assert tested_connector["status"] == "live"
    assert browsed_connector["connector_type"] == "rest"
    assert browsed_connector["total"] >= 1
    assert created["status"] == "ready"
    assert created["dataset_id"]
    assert created["dataset_name"]
    assert datasets["total"] >= len(datasets["datasets"])
    assert any(item["dataset_id"] == created["dataset_id"] for item in datasets["datasets"])
    assert refreshed["status"] == "ready"
    assert refreshed["dataset_id"] == created["dataset_id"]
    assert summary["dataset_id"] == created["dataset_id"]
    assert summary["name"] == created["dataset_name"]
    assert summary["column_count"] >= 2
    assert detail["dataset"]["dataset_id"] == created["dataset_id"]
    assert detail["dataset"]["dataset_name"] == created["dataset_name"]
    assert isinstance(detail["schema"], dict)
    assert len(detail["schema"].get("columns", [])) >= 2


def test_client_repository_surface() -> None:
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    with live_repository_fixture("ts-sdk") as repository_fixture:
        payload = _run_node_check("repositories", repository_path=str(repository_fixture.root_path))
        assert_repository_intelligence_capabilities_payload(payload["capabilities"])
        saved_connector = payload["savedConnector"]
        snapshot = payload["snapshot"]
        fetched_snapshot = payload["fetchedSnapshot"]
        repeated_snapshot = payload["repeatedSnapshot"]
        triage = payload["triage"]
        graph = payload["graph"]
        plan_attempt = payload["planAttempt"]
        simulation = payload["simulation"]
        apply_attempt = payload["applyAttempt"]

        assert saved_connector["id"]
        assert saved_connector["connector_type"] == "local_repo"
        assert snapshot["connector_type"] == "local_repo"
        assert snapshot["file_count"] >= 2
        assert fetched_snapshot["snapshot_id"] == snapshot["snapshot_id"]
        assert fetched_snapshot["content_hash"] == snapshot["content_hash"]
        assert repeated_snapshot["snapshot_id"] == snapshot["snapshot_id"]
        assert repeated_snapshot["status"] == "existing"
        assert triage["workspace_evidence_bundle_ref"]
        assert triage["reduction_ratio"] >= 1.0
        assert triage["evidence_items"]
        assert triage["suspect_files"][0] == repository_fixture.primary_file
        assert triage["workspace_evidence_bundle_artifact"]["artifact_kind"] == "WorkspaceEvidenceBundle"
        assert graph["snapshot_id"] == snapshot["snapshot_id"]
        assert repository_fixture.primary_file in graph["seed_file_paths"]
        assert repository_fixture.primary_file in graph["impacted_files"]
        assert graph["graph_nodes"]
        assert graph["top_change_risk_files"]

        if not plan_attempt["ok"]:
            _assert_repository_error_payload(
                plan_attempt,
                status_code=503,
                error_code="repository_model_unavailable",
            )
            return

        decision_plan = plan_attempt["value"]
        repository_analysis = decision_plan["decision_plan"]["repository_analysis"]
        assert decision_plan["decision_plan_id"]
        assert repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"
        assert repository_analysis["planner_execution_mode"] == "deterministic_local"
        assert repository_analysis["planner_provider_backend"] is None
        assert repository_analysis["generated_patch_ref"]
        assert repository_analysis["patch_impact_report_ref"]
        assert repository_analysis["token_reduction_metrics"]["reduction_ratio"] >= 1.0

        assert simulation is not None
        simulation_id = simulation["validated_inputs"]["simulation_id"]
        apply_gate = simulation["score_breakdown"]["apply_gate"]
        assert simulation_id
        assert apply_gate["policy_snapshot_id"]

        assert apply_attempt is not None
        if apply_gate["passed"]:
            assert apply_attempt["ok"] is True, apply_attempt
            applied = apply_attempt["value"]
            assert applied["mode"] == "local_branch"
            assert applied["applied"] is True
            assert applied["patch"]
            assert applied["branch_name"] == "algenta/live-repository-fix"
            assert applied["commit_sha"]
            assert applied["local_checkout_path"]
            repository_fixture.assert_local_branch_applied(
                branch_name="algenta/live-repository-fix",
                checkout_path=applied["local_checkout_path"],
            )
            assert repository_fixture.primary_file in applied["validation_summary"]["patch_files"]
        else:
            assert apply_attempt["ok"] is False, apply_attempt
            _assert_repository_error_payload(
                apply_attempt,
                status_code=409,
                error_code="repository_apply_gate_failed",
            )


def test_client_control_plane_surface() -> None:
    with webhook_receiver() as (callback_url, deliveries):
        try:
            payload = _run_node_check("control_plane", webhook_url=callback_url)
        except Exception as exc:  # noqa: BLE001
            raise_if_credit_refresh_blocked(exc)
            raise
        team = payload["team"]
        jobs = payload["jobs"]
        missing_job = payload["missingJob"]
        missing_job_result = payload["missingJobResult"]
        cancelled_missing_job = payload["cancelledMissingJob"]
        polled_missing_job = payload["polledMissingJob"]
        billing = payload["billing"]
        credits = payload["credits"]
        metering = payload["metering"]
        webhook = payload["webhook"]
        devices = payload["devices"]
        logs = payload["logs"]
        policy = payload["policy"]
        snapshots = payload["snapshots"]
        updated = payload["updated"]

        assert team["page"] == 1
        assert team["limit"] == 50
        assert team["total"] >= len(team["members"])
        assert team["pages"] >= 1
        assert team["members"]
        assert team["members"][0]["email"]
        assert team["members"][0]["role"]
        assert jobs["page"] == 1
        assert jobs["limit"] == 5
        assert jobs["total"] >= len(jobs["jobs"])
        assert jobs["pages"] >= 1
        for job in jobs["jobs"]:
            assert job["status"] == "queued"
            assert job["queue_name"]
        for missing in (missing_job, missing_job_result, cancelled_missing_job, polled_missing_job):
            assert missing["ok"] is False
            assert missing["statusCode"] == 404, missing
            assert missing["errorCode"] in {"job_not_found", "not_found"}, missing
            response_body = missing["responseBody"]
            assert isinstance(response_body, dict), missing
            assert response_body.get("error", {}).get("code") in {"job_not_found", "not_found"}, missing
        assert billing["plan"]
        assert credits["billing_period"] == time.strftime("%Y-%m", time.gmtime())
        assert credits["credits_granted"] >= 0
        if credits["monthly_limit"] == 0:
            assert credits["credits_issued_this_month"] == 0
        else:
            assert credits["credits_issued_this_month"] >= credits["credits_granted"]
        assert credits["monthly_limit"] >= 0
        assert credits["monthly_remaining"] >= 0
        assert credits["refresh_after"] >= credits["server_time"]
        assert credits["expires_at"] >= credits["refresh_after"]
        assert metering["accepted"] == 1
        assert metering["billing_period"]
        assert webhook["success"] is True
        assert webhook["status_code"] == 200
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]
        assert devices["page"] == 1
        assert devices["limit"] == 25
        assert devices["total"] >= len(devices["devices"])
        assert devices["pages"] >= 1
        assert devices["device_count"] == len(devices["devices"])
        assert devices["plan"]

        assert logs["page"] == 1
        assert logs["limit"] == 20
        assert logs["total"] >= len(logs["entries"])
        assert logs["pages"] >= 1
        assert logs["entries"]
        assert logs["entries"][0]["action"]
        assert logs["entries"][0]["resource_type"]
        assert logs["entries"][0]["result"] in {"success", "failure"}

        assert 0 <= policy["min_confidence"] <= 1
        assert isinstance(policy["require_calibration"], bool)
        assert isinstance(policy["allow_reexecution"], bool)
        assert policy["updated_at"]
        assert snapshots["total_snapshots"] >= len(snapshots["data"])
        if snapshots["data"]:
            assert snapshots["data"][0]["snapshot_id"]
            assert snapshots["data"][0]["revision"] >= 1
        assert updated["min_confidence"] == policy["min_confidence"]
        assert updated["risk_floor"] == policy["risk_floor"]
        assert updated["require_calibration"] == policy["require_calibration"]
        assert updated["allow_reexecution"] == policy["allow_reexecution"]


def test_client_trigger_surface() -> None:
    payload = _run_node_check("triggers")
    created = payload["created"]
    listed = payload["listed"]
    fired = payload["fired"]
    paused = payload["paused"]
    resumed = payload["resumed"]
    deleted = payload["deleted"]

    assert created["trigger_id"]
    assert created["status"] == "active"
    assert listed["page"] == 1
    assert listed["limit"] == 25
    assert listed["total"] >= len(listed["triggers"])
    assert any(item["trigger_id"] == created["trigger_id"] for item in listed["triggers"])
    assert fired["trigger_id"] == created["trigger_id"]
    assert fired["condition_met"] is False
    assert fired["fired"] is False
    assert paused["status"] == "paused"
    assert resumed["status"] == "active"
    assert deleted == {"trigger_id": created["trigger_id"], "deleted": True}


def test_client_deployment_lifecycle_surface() -> None:
    try:
        payload = _run_node_check("deployment_lifecycle")
    except Exception as exc:  # noqa: BLE001
        raise_if_deployment_mutation_blocked(exc)
        raise_if_capacity_blocked(exc)
        raise
    created = payload["created"]
    cost = payload["cost"]
    deleted = payload["deleted"]
    assert created["deployment_id"]
    assert created["provider"] == "algenta_shared"
    assert created["region"] == "algenta-shared"
    assert created["status"] in {"requested", "provisioning", "active"}
    assert cost["deployment_id"] == created["deployment_id"]
    assert cost["provider"] == created["provider"]
    assert cost["billable_cost_usd_month"] >= cost["cost_usd_month"]
    assert deleted["deployment_id"] == created["deployment_id"]
    assert deleted["status"] in {"deprovisioning", "deleted"}


def test_client_llm_utility_surface() -> None:
    try:
        payload = _run_node_check("llm")
    except Exception as exc:  # noqa: BLE001
        raise_if_artifact_bridge_blocked(exc)
        raise
    tokenizer = next((item for item in payload["models"]["data"] if item["id"] == "text.tokenizer"), None)
    assert tokenizer is not None, payload["models"]["data"]
    for item in payload["models"]["data"]:
        assert item.get("provider_backend") is None or isinstance(item.get("provider_backend"), str), item
        for field_name in (
            "routing_targets",
            "resolved_routing_targets",
            "chat_routing_targets",
            "resolved_chat_routing_targets",
            "embedding_routing_targets",
            "resolved_embedding_routing_targets",
            "routing_fallback_on",
            "chat_routing_fallback_on",
            "embedding_routing_fallback_on",
            "required_provider_headers",
            "chat_required_provider_headers",
            "embedding_required_provider_headers",
            "provider_auth_env_vars",
            "chat_provider_auth_env_vars",
            "embedding_provider_auth_env_vars",
        ):
            value = item.get(field_name)
            assert isinstance(value, list), (item["id"], field_name, value)
            assert all(isinstance(entry, str) and entry for entry in value), (
                item["id"],
                field_name,
                value,
            )
        for field_name in (
            "routing_fallback_policy",
            "chat_routing_fallback_policy",
            "embedding_routing_fallback_policy",
        ):
            value = item.get(field_name)
            assert value is None or isinstance(value, str), (item["id"], field_name, value)
        for field_name in (
            "routing_max_attempts",
            "chat_routing_max_attempts",
            "embedding_routing_max_attempts",
        ):
            value = item.get(field_name)
            assert value is None or (isinstance(value, int) and value > 0), (item["id"], field_name, value)
        for field_name in ("timeout_seconds", "chat_timeout_seconds", "embedding_timeout_seconds"):
            value = item.get(field_name)
            assert value is None or (isinstance(value, int | float) and value > 0), (
                item["id"],
                field_name,
                value,
            )
        assert isinstance(item.get("provider_auth_configured"), bool), item
        assert isinstance(item.get("chat_provider_auth_configured"), bool), item
        assert isinstance(item.get("embedding_provider_auth_configured"), bool), item
        if item.get("provider_backend") != "router":
            assert item["resolved_routing_targets"] == [], item
            assert item["resolved_chat_routing_targets"] == [], item
            assert item["resolved_embedding_routing_targets"] == [], item
            assert item["routing_fallback_policy"] is None, item
            assert item["chat_routing_fallback_policy"] is None, item
            assert item["embedding_routing_fallback_policy"] is None, item
            assert item["routing_fallback_on"] == [], item
            assert item["chat_routing_fallback_on"] == [], item
            assert item["embedding_routing_fallback_on"] == [], item
            assert item["routing_max_attempts"] is None, item
            assert item["chat_routing_max_attempts"] is None, item
            assert item["embedding_routing_max_attempts"] is None, item
    assert tokenizer["provider_backend"] is None, tokenizer
    assert tokenizer["routing_targets"] == [], tokenizer
    assert tokenizer["resolved_routing_targets"] == [], tokenizer
    assert tokenizer["chat_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_chat_routing_targets"] == [], tokenizer
    assert tokenizer["embedding_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_embedding_routing_targets"] == [], tokenizer
    assert tokenizer["routing_fallback_policy"] is None, tokenizer
    assert tokenizer["chat_routing_fallback_policy"] is None, tokenizer
    assert tokenizer["embedding_routing_fallback_policy"] is None, tokenizer
    assert tokenizer["routing_fallback_on"] == [], tokenizer
    assert tokenizer["chat_routing_fallback_on"] == [], tokenizer
    assert tokenizer["embedding_routing_fallback_on"] == [], tokenizer
    assert tokenizer["routing_max_attempts"] is None, tokenizer
    assert tokenizer["chat_routing_max_attempts"] is None, tokenizer
    assert tokenizer["embedding_routing_max_attempts"] is None, tokenizer
    assert tokenizer["timeout_seconds"] is None, tokenizer
    assert tokenizer["chat_timeout_seconds"] is None, tokenizer
    assert tokenizer["embedding_timeout_seconds"] is None, tokenizer
    assert tokenizer["required_provider_headers"] == [], tokenizer
    assert tokenizer["chat_required_provider_headers"] == [], tokenizer
    assert tokenizer["embedding_required_provider_headers"] == [], tokenizer
    assert tokenizer["provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["chat_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["embedding_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["provider_auth_configured"] is False, tokenizer
    assert tokenizer["chat_provider_auth_configured"] is False, tokenizer
    assert tokenizer["embedding_provider_auth_configured"] is False, tokenizer
    model_ids = {item["id"] for item in payload["models"]["data"]}
    assert "text.tokenizer" in model_ids
    assert "text.hash_embedding_v1" in model_ids
    assert "embeddings.cosine_similarity" in model_ids
    assert payload["artifact"]["status"] in {"resolved", "not_cached"}
    assert payload["artifact"]["filename"] == "model.safetensors"
    if payload["artifact"]["resolved_path"] is not None:
        assert payload["artifact"]["resolved_path"]
    assert payload["tokenized"]["object"] == "tokenization"
    assert payload["tokenized"]["token_count"] == 3
    assert payload["counted"]["object"] == "token_count"
    assert payload["counted"]["token_count"] == 3
    assert payload["deploymentRegions"]["providers"]
    managed_provider = next(
        (
            provider
            for provider in payload["deploymentRegions"]["providers"]
            if provider["id"] == "algenta_shared"
        ),
        None,
    )
    assert managed_provider is not None
    assert managed_provider["regions"]
    if payload["deployment"] is not None:
        assert payload["deployment"]["deployment_id"]
        assert payload["deploymentCost"] is not None
        assert (
            payload["deploymentCost"]["deployment_id"] == payload["deployment"]["deployment_id"]
        )
    assert payload["chat"]["object"] == "chat.completion"
    assert payload["chat"]["choices"][0]["message"]["role"] == "assistant"
    _assert_empty_provider_trace_payload(payload["chat"])
    assert payload["responses"]["object"] == "response"
    assert payload["responses"]["status"] == "completed"
    assert len(payload["responses"]["output"]) >= 1
    _assert_empty_provider_trace_payload(payload["responses"], output_items=True)
    assert payload["embeddings"]["object"] == "list"
    assert payload["embeddings"]["dimensions"] == 8
    assert len(payload["embeddings"]["data"]) == 2
    _assert_empty_provider_trace_payload(payload["embeddings"])
    assert payload["similarity"]["object"] == "embedding_similarity"
    assert payload["similarity"]["dimension"] == 2
    assert payload["rerank"]["object"] == "list"
    assert payload["rerank"]["returned_documents"] == 2
    assert payload["rerank"]["data"][0]["rank"] == 1
    assert payload["rerank"]["data"][0]["id"] == "doc_a"


def test_client_decision_runtime_surface() -> None:
    try:
        payload = _run_node_check("decision")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    recommendation = payload["recommendation"]
    score = payload["score"]
    batch = payload["batch"]
    compared = payload["compared"]
    assert recommendation["recommended_action"]
    assert len(recommendation["action_results"]) == 2
    assert isinstance(score["score"], int | float)
    assert isinstance(score["score_breakdown"], dict)
    assert score["score_breakdown"]
    assert all(isinstance(value, int | float) for value in score["score_breakdown"].values())
    assert batch["total"] == 2
    assert len(batch["results"]) == 2
    assert compared["winner"] in {"base", "stretch"}
    assert len(compared["scenarios"]) == 2


def test_client_product_surface() -> None:
    try:
        payload = _run_node_check("product")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    assert payload["decision"]["action"]
    assert 0 <= payload["decision"]["confidence"] <= 1
    assert payload["agentRun"]["run_id"]
    assert payload["agentRun"]["status"] in {"completed", "requires_approval", "running"}
    assert payload["optimize"]["status"] == "completed"
    assert payload["optimize"]["optimal_values"]
    assert payload["retrieve"]["results"]
    assert payload["retrieve"]["results"][0]["content"]
    assert payload["forecast"]["forecast_mean"] >= 0
    assert payload["forecast"]["periods"]


def test_client_streaming_llm_surface() -> None:
    payload = _run_node_check("stream")
    chat_chunks = payload["chatChunks"]
    response_events = payload["responseEvents"]
    assert len(chat_chunks) >= 2
    assert chat_chunks[0]["object"] == "chat.completion.chunk"
    assert chat_chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert all(chunk["provider_backend"] is None for chunk in chat_chunks), chat_chunks
    assert all(chunk["provider_model_id"] is None for chunk in chat_chunks), chat_chunks
    assert all(chunk["provider_attempts"] == [] for chunk in chat_chunks), chat_chunks
    assert any(
        item["choices"][0]["delta"].get("content")
        for item in chat_chunks
        if item["choices"]
    )
    assert chat_chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert len(response_events) == 3
    assert response_events[0]["type"] == "response.created"
    assert response_events[1]["type"] == "response.output_item.done"
    assert response_events[2]["type"] == "response.completed"
    assert response_events[2]["response"]["status"] == "completed"
    assert response_events[0]["response"]["provider_backend"] is None, response_events
    assert response_events[0]["response"]["provider_model_id"] is None, response_events
    assert response_events[0]["response"]["provider_attempts"] == [], response_events
    assert response_events[1]["item"]["provider_backend"] is None, response_events
    assert response_events[1]["item"]["provider_model_id"] is None, response_events
    assert response_events[1]["item"]["provider_attempts"] == [], response_events
    assert response_events[2]["response"]["provider_backend"] is None, response_events
    assert response_events[2]["response"]["provider_model_id"] is None, response_events
    assert response_events[2]["response"]["provider_attempts"] == [], response_events


def test_client_plan_decision_and_agent_runs() -> None:
    try:
        payload = _run_node_check("plan")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    assert isinstance(payload["plan"]["recommended_action"], str) and payload["plan"]["recommended_action"]
    assert 0 <= payload["plan"]["confidence"] <= 1
    assert payload["created"]["status"] == "requires_approval"
    assert payload["created"]["pending_action"] == "approve"
    assert payload["fetched"]["run_id"] == payload["created"]["run_id"]
    assert payload["events"]["run_id"] == payload["created"]["run_id"]
    assert payload["events"]["total_events"] >= 3
    assert payload["approved"]["status"] == "completed"


def test_client_agent_run_event_stream() -> None:
    try:
        payload = _run_node_check("agent_stream")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    assert payload["created"]["run_id"]
    assert len(payload["streamedEvents"]) >= 2
    assert payload["streamedEvents"][0]["type"] == "agent.run.event"
    assert payload["streamedEvents"][0]["event"]["event_type"] == "run_created"
    assert payload["streamedEvents"][-1]["type"] == "agent.run.completed"
    assert payload["streamedEvents"][-1]["status"] == "completed"


def test_client_simulate_path() -> None:
    try:
        payload = _run_node_check("simulate")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    result = payload["result"]
    assert result["status"] == "completed"
    assert result["scenarios_run"] >= 200
    assert isinstance(result["metrics"]["expected_value"], int | float)


def main() -> int:
    _emit("\n" + "=" * 70)
    _emit("  LIVE TYPESCRIPT SDK CLIENT INTEGRATION")
    _emit("=" * 70)

    _preflight()

    check("TypeScript SDK client health() + version()", test_client_health_and_version)
    check("TypeScript SDK client contract + runtime proof routes", test_client_contract_and_runtime_proof_routes)
    check("TypeScript SDK client account/API-key surface", test_client_account_surface)
    check("TypeScript SDK client connectors + dataset lifecycle surface", test_client_dataset_surface)
    check("TypeScript SDK client repository intelligence surface", test_client_repository_surface)
    check(
        "TypeScript SDK client team/credits/metering/audit/execution-policy surface",
        test_client_control_plane_surface,
    )
    check("TypeScript SDK client trigger lifecycle surface", test_client_trigger_surface)
    check(
        "TypeScript SDK client deployment create/delete lifecycle",
        test_client_deployment_lifecycle_surface,
    )
    check("TypeScript SDK client decision runtime surface", test_client_decision_runtime_surface)
    check("TypeScript SDK client simplified product surface", test_client_product_surface)
    check("TypeScript SDK client LLM utility surface", test_client_llm_utility_surface)
    check("TypeScript SDK client streaming LLM surface", test_client_streaming_llm_surface)
    check("TypeScript SDK client plan_decision + agent-runs lifecycle", test_client_plan_decision_and_agent_runs)
    check("TypeScript SDK client agent-run event stream", test_client_agent_run_event_stream)
    check("TypeScript SDK client simulate path", test_client_simulate_path)

    passed = sum(1 for status, *_ in results if status == PASS)
    skipped = sum(1 for status, *_ in results if status == SKIP)
    failed = sum(1 for status, *_ in results if status == FAIL)

    _emit("\n" + "=" * 70)
    _emit(f"Passed: {passed}")
    _emit(f"Skipped: {skipped}")
    _emit(f"Failed: {failed}")
    if skipped:
        _emit("Skipped:")
        for status, name, detail in results:
            if status == SKIP:
                _emit(f"  - {name}: {detail}")
    if failed:
        _emit("Failures:")
        for status, name, detail in results:
            if status == FAIL:
                _emit(f"  - {name}: {detail}")
    _emit("=" * 70)

    _write_summary()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
