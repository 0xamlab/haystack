from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from apps import platform_contract
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
AGENT_RUN_TEST_ID = "00000000-0000-0000-0000-000000000001"
PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]
INVALID_TEST_API_KEY = "de_live_INVALID_KEY_000000000000000"
REQUIRED_RUNTIME_MCP_TOOLS = [
    "get_contract",
    "get_runtime_manifest",
    "get_runtime_modules",
    "get_runtime_benchmarks",
    "get_runtime_release_validation",
]
MCP_TRANSPORT_UNAVAILABLE_HINT = (
    "Install the API or algenta-mcp package with its dependencies."
)
REPRESENTATIVE_PROTECTED_OPENAPI_OPERATIONS = [
    ("/v1/models", "get"),
    ("/v1/chat/completions", "post"),
    ("/v1/responses", "post"),
    ("/v1/embeddings", "post"),
    ("/v1/embeddings/similarity", "post"),
    ("/v1/rerank", "post"),
    ("/v1/agent/runs", "get"),
    ("/v1/agent/runs", "post"),
    ("/v1/agent/runs/{run_id}", "get"),
    ("/v1/agent/runs/{run_id}/events", "get"),
    ("/v1/agent/runs/{run_id}/resume", "post"),
    ("/v1/agent/runs/{run_id}/cancel", "post"),
    ("/v1/agent/runs/{run_id}/approve", "post"),
    ("/v1/simulate", "post"),
    ("/v1/decisions/plan", "post"),
    ("/v1/runs", "get"),
    ("/v1/templates", "get"),
    ("/v1/connectors", "get"),
    ("/v1/analytics", "get"),
    ("/v1/jobs", "post"),
    ("/v1/query", "post"),
    ("/v1/verify", "post"),
    ("/v1/sources/register", "post"),
]
REPRESENTATIVE_PROTECTED_RUNTIME_GET_PATHS = [
    "/v1/models",
    "/v1/runs",
    "/v1/templates",
    "/v1/connectors",
    "/v1/analytics",
    f"/v1/agent/runs/{AGENT_RUN_TEST_ID}",
    f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/events",
]
RUNTIME_ADMIN_GET_PATHS = [
    "/v1/admin/runtime/modules",
    "/v1/admin/runtime/benchmarks",
    "/v1/admin/runtime/validation",
]
REPRESENTATIVE_PROTECTED_RUNTIME_POST_PATHS = [
    "/v1/chat/completions",
    "/v1/tokenize",
    "/v1/count_tokens",
    "/v1/responses",
    "/v1/embeddings",
    "/v1/embeddings/similarity",
    "/v1/rerank",
    "/v1/agent/runs",
    f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/resume",
    f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/cancel",
    f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/approve",
    "/v1/simulate",
    "/v1/decisions/plan",
    "/v1/jobs",
    "/v1/query",
    "/v1/verify",
    "/v1/sources/register",
]


def _expected_requested_urls(base_url: str) -> list[str]:
    urls = [
        f"{base_url}/v1/health",
        f"{base_url}/v1/runtime/manifest",
        f"{base_url}/v1/meta/contract",
        f"{base_url}/openapi.json",
        f"{base_url}/mcp/tools",
        f"{base_url}/mcp",
    ]
    urls.extend(f"{base_url}{path}" for path in RUNTIME_ADMIN_GET_PATHS)
    urls.extend(f"{base_url}{path}" for path in REPRESENTATIVE_PROTECTED_RUNTIME_GET_PATHS)
    urls.extend(f"{base_url}{path}" for path in REPRESENTATIVE_PROTECTED_RUNTIME_POST_PATHS)
    for headers in (
        {"X-API-Key": INVALID_TEST_API_KEY},
        {"Authorization": f"Bearer {INVALID_TEST_API_KEY}"},
    ):
        del headers
        urls.extend(f"{base_url}{path}" for path in [*RUNTIME_ADMIN_GET_PATHS, *REPRESENTATIVE_PROTECTED_RUNTIME_GET_PATHS])
        urls.extend(f"{base_url}{path}" for path in REPRESENTATIVE_PROTECTED_RUNTIME_POST_PATHS)
    return urls


def _base_url(port: int) -> str:
    return f"http://{DEFAULT_HOST}:{port}"


def _port_open(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _read_log(log_path: Path) -> str:
    try:
        contents = log_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not contents:
        return ""
    return f"\nServer log:\n{contents}"


def _choose_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((DEFAULT_HOST, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_health(
    base_url: str,
    log_path: Path,
    proc: subprocess.Popen[str] | None = None,
    timeout_seconds: float = 30,
) -> None:
    start = time.monotonic()
    last_error = "no response"
    while time.monotonic() - start < timeout_seconds:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(
                f"Runtime API exited before readiness probe with code {proc.returncode}."
                f"{_read_log(log_path)}"
            )
        try:
            response = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if response.status_code == 200:
                return
            last_error = f"status {response.status_code}"
        except Exception as exc:  # pragma: no cover - best effort startup probe
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


def _endpoint_serves_canonical_startup_contract(base_url: str) -> bool:
    try:
        _assert_runtime_health_manifest_contract_and_openapi(base_url)
    except Exception:
        return False
    return True


def _probe_or_launch_runtime_endpoint(
    log_dir: Path,
    log_path: Path,
) -> tuple[str, subprocess.Popen[str] | None, bool]:
    started_here = False
    proc: subprocess.Popen[str] | None = None
    port = DEFAULT_PORT
    base_url = _base_url(port)

    if _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5)
            if not _endpoint_serves_canonical_startup_contract(base_url):
                port = _choose_free_port()
                base_url = _base_url(port)
        except RuntimeError:
            port = _choose_free_port()
            base_url = _base_url(port)
    if port != DEFAULT_PORT or not _port_open(DEFAULT_HOST, DEFAULT_PORT):
        env = os.environ.copy()
        env.setdefault("ALGENTA_SOURCE_REGISTRY_ROOT", str(log_dir / "sources"))
        env.setdefault("ALGENTA_RUNTIME_DIR", str(log_dir / "runtime"))
        with log_path.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.Popen(
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
        started_here = True
        _wait_for_health(base_url, log_path, proc=proc)
    return base_url, proc, started_here


def _assert_runtime_health_manifest_contract_and_openapi(base_url: str) -> None:
    health = httpx.get(f"{base_url}/v1/health", timeout=5.0)
    assert health.status_code == 200, health.text
    health_payload = health.json()
    assert health_payload["status"] == "ok"
    assert isinstance(health_payload["timestamp"], str)

    manifest = httpx.get(f"{base_url}/v1/runtime/manifest", timeout=10.0)
    assert manifest.status_code == 200, manifest.text
    manifest_payload = manifest.json()
    assert manifest_payload["runtime_version"] == "2026.05.0"
    assert len(manifest_payload["modules"]) == 22
    assert manifest_payload["module_manifest_version"]
    assert manifest_payload["signature"]["algorithm"] == "hmac-sha256"
    assert manifest_payload["signature"]["scope"] == "control_plane_hmac_v1"
    assert manifest_payload["signature"]["signature_hex"]

    contract = httpx.get(f"{base_url}/v1/meta/contract", timeout=10.0)
    assert contract.status_code == 200, contract.text
    contract_payload = contract.json()
    expected_contract = platform_contract.load_platform_contract_manifest_model()
    assert contract_payload["brand"] == expected_contract.brand
    assert contract_payload["contract_version"] == expected_contract.contract_version
    assert contract_payload["api_base_url"] == expected_contract.api_base_url
    assert contract_payload["mcp_endpoint"] == expected_contract.mcp_endpoint
    assert contract_payload["mcp_tools_endpoint"] == expected_contract.mcp_tools_endpoint
    assert contract_payload["api_key_prefixes"] == expected_contract.api_key_prefixes.model_dump(
        mode="json"
    )
    assert_manifest_backed_integrations(contract_payload["integrations"])
    assert (
        contract_payload["primary_data_query_contract"]["api"]["contract_endpoint"]
        == expected_contract.primary_data_query_contract.api.contract_endpoint
    )
    assert (
        contract_payload["primary_data_query_contract"]["mcp"]["contract_tool"]
        == expected_contract.primary_data_query_contract.mcp.contract_tool
    )

    openapi = httpx.get(f"{base_url}/openapi.json", timeout=10.0)
    assert openapi.status_code == 200, openapi.text
    openapi_payload = openapi.json()
    assert openapi_payload["servers"] == [{"url": expected_contract.api_base_url}]
    assert openapi_payload["openapi"].startswith("3.")
    assert openapi_payload["x-canonical-mcp-endpoint"] == expected_contract.mcp_endpoint
    assert (
        openapi_payload["x-primary-data-query-contract"]
        == expected_contract.primary_data_query_contract.model_dump(mode="json")
    )
    assert "/v1/health" in openapi_payload["paths"]
    assert "/v1/runtime/manifest" in openapi_payload["paths"]
    assert "/v1/meta/contract" in openapi_payload["paths"]
    assert "/v1/admin/runtime/modules" in openapi_payload["paths"]
    assert "/v1/admin/runtime/benchmarks" in openapi_payload["paths"]
    assert "/v1/admin/runtime/validation" in openapi_payload["paths"]
    assert "/mcp/tools" in openapi_payload["paths"]
    assert "/mcp" in openapi_payload["paths"]
    assert "/mcp/sse" in openapi_payload["paths"]
    assert "/mcp/messages" in openapi_payload["paths"]
    for path, method in REPRESENTATIVE_PROTECTED_OPENAPI_OPERATIONS:
        assert path in openapi_payload["paths"]
        assert openapi_payload["paths"][path][method]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        "text/event-stream"
        in openapi_payload["paths"]["/v1/chat/completions"]["post"]["responses"]["200"]["content"]
    )
    assert (
        "text/event-stream"
        in openapi_payload["paths"]["/v1/responses"]["post"]["responses"]["200"]["content"]
    )
    assert (
        "text/event-stream"
        in openapi_payload["paths"]["/v1/agent/runs/{run_id}/events"]["get"]["responses"]["200"]["content"]
    )
    assert openapi_payload["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "APIKey",
        "description": "Canonical v1 authentication. Use Authorization: Bearer <api_key>.",
    }
    assert openapi_payload["components"]["securitySchemes"]["LegacyApiKey"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Legacy compatibility header for existing v1 clients.",
    }
    assert openapi_payload["paths"]["/v1/runtime/manifest"]["get"].get("security") is None
    assert openapi_payload["paths"]["/v1/meta/contract"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp/tools"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp"]["post"].get("security") is None
    assert openapi_payload["paths"]["/mcp/sse"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp/messages"]["post"].get("security") is None
    assert "200" in openapi_payload["paths"]["/mcp/tools"]["get"]["responses"]
    assert "200" in openapi_payload["paths"]["/mcp"]["post"]["responses"]
    assert openapi_payload["paths"]["/mcp/sse"]["get"]["deprecated"] is True
    assert openapi_payload["paths"]["/mcp/messages"]["post"]["deprecated"] is True
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/modules"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/benchmarks"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/validation"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )

    mcp_tools = httpx.get(f"{base_url}/mcp/tools", timeout=10.0)
    assert mcp_tools.status_code == 200, mcp_tools.text
    mcp_tools_payload = mcp_tools.json()
    tool_names = {tool["name"] for tool in mcp_tools_payload["tools"]}
    assert tool_names.issuperset(REQUIRED_RUNTIME_MCP_TOOLS)

    mcp_initialize = httpx.post(
        f"{base_url}/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "startup-smoke", "version": "1.0.0"},
            },
        },
        timeout=10.0,
    )
    assert mcp_initialize.status_code == 200, mcp_initialize.text
    assert mcp_initialize.json()["result"]["protocolVersion"] == "2025-11-25"

    for path in RUNTIME_ADMIN_GET_PATHS:
        unauthorized = httpx.get(f"{base_url}{path}", timeout=10.0)
        assert unauthorized.status_code == 401, unauthorized.text
        unauthorized_payload = unauthorized.json()
        assert unauthorized_payload["error"]["code"] == "authentication_required"

    for path in REPRESENTATIVE_PROTECTED_RUNTIME_GET_PATHS:
        unauthorized = httpx.get(f"{base_url}{path}", timeout=10.0)
        assert unauthorized.status_code == 401, unauthorized.text
        unauthorized_payload = unauthorized.json()
        assert unauthorized_payload["error"]["code"] == "authentication_required"

    for path in REPRESENTATIVE_PROTECTED_RUNTIME_POST_PATHS:
        unauthorized = httpx.post(f"{base_url}{path}", json={}, timeout=10.0)
        assert unauthorized.status_code == 401, unauthorized.text
        unauthorized_payload = unauthorized.json()
        assert unauthorized_payload["error"]["code"] == "authentication_required"

    for headers in (
        {"X-API-Key": INVALID_TEST_API_KEY},
        {"Authorization": f"Bearer {INVALID_TEST_API_KEY}"},
    ):
        for path in [*RUNTIME_ADMIN_GET_PATHS, *REPRESENTATIVE_PROTECTED_RUNTIME_GET_PATHS]:
            invalid = httpx.get(f"{base_url}{path}", headers=headers, timeout=10.0)
            assert invalid.status_code == 401, invalid.text
            invalid_payload = invalid.json()
            assert invalid_payload["error"]["code"] == "invalid_api_key"
        for path in REPRESENTATIVE_PROTECTED_RUNTIME_POST_PATHS:
            invalid = httpx.post(f"{base_url}{path}", headers=headers, json={}, timeout=10.0)
            assert invalid.status_code == 401, invalid.text
            invalid_payload = invalid.json()
            assert invalid_payload["error"]["code"] == "invalid_api_key"


def test_runtime_api_boots_on_port_8000_and_serves_health_manifest_contract_and_openapi() -> None:
    proc: subprocess.Popen[str] | None = None
    started_here = False
    log_dir = Path(tempfile.mkdtemp(prefix="runtime-startup-smoke-"))
    log_path = log_dir / "api_server_8000.log"

    try:
        base_url, proc, started_here = _probe_or_launch_runtime_endpoint(log_dir, log_path)
        _assert_runtime_health_manifest_contract_and_openapi(base_url)
    finally:
        if started_here and proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeProc:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


def _fake_platform_contract_payload() -> dict[str, Any]:
    expected_contract = platform_contract.load_platform_contract_manifest_model()
    return expected_contract.model_dump(mode="json")


def _fake_openapi_payload() -> dict[str, Any]:
    expected_contract = platform_contract.load_platform_contract_manifest_model()
    return {
        "openapi": "3.1.0",
        "servers": [{"url": expected_contract.api_base_url}],
        "x-canonical-mcp-endpoint": expected_contract.mcp_endpoint,
        "x-primary-data-query-contract": expected_contract.primary_data_query_contract.model_dump(
            mode="json"
        ),
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "APIKey",
                    "description": (
                        "Canonical v1 authentication. Use Authorization: Bearer <api_key>."
                    ),
                },
                "LegacyApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "Legacy compatibility header for existing v1 clients.",
                },
            }
        },
        "paths": {
            "/v1/health": {"get": {}},
            "/v1/runtime/manifest": {"get": {}},
            "/v1/meta/contract": {"get": {}},
            "/v1/models": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/chat/completions": {
                "post": {
                    "security": PROTECTED_OPENAPI_SECURITY,
                    "responses": {"200": {"content": {"text/event-stream": {}}}},
                }
            },
            "/v1/tokenize": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/count_tokens": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/responses": {
                "post": {
                    "security": PROTECTED_OPENAPI_SECURITY,
                    "responses": {"200": {"content": {"text/event-stream": {}}}},
                }
            },
            "/v1/embeddings": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/embeddings/similarity": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/rerank": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/agent/runs": {
                "get": {"security": PROTECTED_OPENAPI_SECURITY},
                "post": {"security": PROTECTED_OPENAPI_SECURITY},
            },
            "/v1/agent/runs/{run_id}": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/agent/runs/{run_id}/events": {
                "get": {
                    "security": PROTECTED_OPENAPI_SECURITY,
                    "responses": {"200": {"content": {"text/event-stream": {}}}},
                }
            },
            "/v1/agent/runs/{run_id}/resume": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/agent/runs/{run_id}/cancel": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/agent/runs/{run_id}/approve": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/simulate": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/decisions/plan": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/runs": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/templates": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/connectors": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/analytics": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/jobs": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/query": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/verify": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/sources/register": {"post": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/admin/runtime/modules": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/admin/runtime/benchmarks": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/v1/admin/runtime/validation": {"get": {"security": PROTECTED_OPENAPI_SECURITY}},
            "/mcp/tools": {"get": {"responses": {"200": {"description": "Successful Response"}}}},
            "/mcp": {
                "get": {"responses": {"200": {"description": "MCP event stream"}}},
                "post": {"responses": {"200": {"description": "MCP response"}}},
                "delete": {"responses": {"404": {"description": "Session not found"}}},
            },
            "/mcp/sse": {
                "get": {
                    "deprecated": True,
                    "responses": {"200": {"description": "Legacy MCP SSE stream"}},
                }
            },
            "/mcp/messages": {
                "post": {
                    "deprecated": True,
                    "responses": {"202": {"description": "Legacy MCP message accepted"}},
                }
            },
        },
    }


def _fake_mcp_tools_payload() -> dict[str, Any]:
    return {
        "tools": [
            {"name": name, "description": f"{name} tool", "inputSchema": {"type": "object"}}
            for name in REQUIRED_RUNTIME_MCP_TOOLS
        ]
    }


def _fake_mcp_transport_unavailable_payload() -> dict[str, Any]:
    return {
        "error": {
            "code": "mcp_transport_unavailable",
            "message": "The MCP SSE transport is unavailable in this environment.",
            "details": {"hint": MCP_TRANSPORT_UNAVAILABLE_HINT},
        }
    }


def _fake_mcp_initialize_payload() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "algenta-mcp", "version": "1.0.4"},
        },
    }


def _fake_unauthorized_payload() -> dict[str, Any]:
    return {
        "error": {
            "code": "authentication_required",
            "message": "API key required.",
            "details": {},
        }
    }


def _fake_invalid_api_key_payload() -> dict[str, Any]:
    return {
        "error": {
            "code": "invalid_api_key",
            "message": "The API key provided is invalid, expired, or has been revoked.",
            "details": {},
        }
    }


def test_startup_smoke_reuses_healthy_port_8000_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api_server_8000.log"
    wait_calls: list[tuple[str, bool, float]] = []
    popen_called = False
    requested_urls: list[str] = []

    def _fake_wait(
        base_url: str,
        _: Path,
        proc: subprocess.Popen[str] | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        wait_calls.append((base_url, proc is not None, timeout_seconds))

    def _fake_get(url: str, timeout: float, headers: dict[str, str] | None = None) -> _FakeResponse:
        del timeout
        requested_urls.append(url)
        if url.endswith("/v1/health"):
            return _FakeResponse(200, {"status": "ok", "timestamp": "2026-05-23T00:00:00Z"})
        if url.endswith("/v1/runtime/manifest"):
            return _FakeResponse(
                200,
                {
                    "runtime_version": "2026.05.0",
                    "modules": [{}] * 22,
                    "module_manifest_version": "runtime-manifest-v1",
                    "signature": {
                        "algorithm": "hmac-sha256",
                        "scope": "control_plane_hmac_v1",
                        "signature_hex": "abc123",
                    },
                },
            )
        if url.endswith("/v1/meta/contract"):
            return _FakeResponse(200, _fake_platform_contract_payload())
        if url.endswith("/openapi.json"):
            return _FakeResponse(200, _fake_openapi_payload())
        if url.endswith("/mcp/tools"):
            return _FakeResponse(200, _fake_mcp_tools_payload())
        if url.endswith("/mcp/sse"):
            return _FakeResponse(503, _fake_mcp_transport_unavailable_payload())
        if (
            url.endswith("/v1/models")
            or url.endswith("/v1/runs")
            or url.endswith("/v1/templates")
            or url.endswith("/v1/connectors")
            or url.endswith("/v1/analytics")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/events")
            or url.endswith("/v1/admin/runtime/modules")
            or url.endswith("/v1/admin/runtime/benchmarks")
            or url.endswith("/v1/admin/runtime/validation")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        raise AssertionError(url)

    def _fake_post(
        url: str,
        timeout: float,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        del timeout, json
        requested_urls.append(url)
        if (
            url.endswith("/v1/tokenize")
            or url.endswith("/v1/chat/completions")
            or url.endswith("/v1/count_tokens")
            or url.endswith("/v1/responses")
            or url.endswith("/v1/embeddings")
            or url.endswith("/v1/embeddings/similarity")
            or url.endswith("/v1/rerank")
            or url.endswith("/v1/agent/runs")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/resume")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/cancel")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/approve")
            or url.endswith("/v1/simulate")
            or url.endswith("/v1/decisions/plan")
            or url.endswith("/v1/jobs")
            or url.endswith("/v1/query")
            or url.endswith("/v1/verify")
            or url.endswith("/v1/sources/register")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        if url.endswith("/mcp"):
            return _FakeResponse(200, _fake_mcp_initialize_payload())
        raise AssertionError(url)

    def _fake_popen(*args: Any, **kwargs: Any) -> _FakeProc:
        del args, kwargs
        nonlocal popen_called
        popen_called = True
        return _FakeProc()

    monkeypatch.setattr("tests.test_runtime_startup_smoke._port_open", lambda host, port: True)
    monkeypatch.setattr("tests.test_runtime_startup_smoke._wait_for_health", _fake_wait)
    monkeypatch.setattr(
        "tests.test_runtime_startup_smoke._endpoint_serves_canonical_startup_contract",
        lambda base_url: True,
    )
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.get", _fake_get)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.post", _fake_post)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.subprocess.Popen", _fake_popen)

    base_url, proc, started_here = _probe_or_launch_runtime_endpoint(tmp_path, log_path)

    assert base_url == _base_url(DEFAULT_PORT)
    assert proc is None
    assert started_here is False
    assert wait_calls == [(_base_url(DEFAULT_PORT), False, 5)]

    _assert_runtime_health_manifest_contract_and_openapi(base_url)

    assert requested_urls == _expected_requested_urls(_base_url(DEFAULT_PORT))
    assert popen_called is False


def test_startup_smoke_falls_back_to_free_port_when_8000_listener_is_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api_server_8000.log"
    wait_calls: list[tuple[str, bool, float]] = []
    requested_urls: list[str] = []
    fake_proc = _FakeProc()

    def _fake_wait(
        base_url: str,
        _: Path,
        proc: subprocess.Popen[str] | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        wait_calls.append((base_url, proc is not None, timeout_seconds))
        if base_url == _base_url(DEFAULT_PORT) and proc is None:
            raise RuntimeError("stale unhealthy listener")

    def _fake_get(url: str, timeout: float, headers: dict[str, str] | None = None) -> _FakeResponse:
        del timeout
        requested_urls.append(url)
        if url.endswith("/v1/health"):
            return _FakeResponse(200, {"status": "ok", "timestamp": "2026-05-23T00:00:00Z"})
        if url.endswith("/v1/runtime/manifest"):
            return _FakeResponse(
                200,
                {
                    "runtime_version": "2026.05.0",
                    "modules": [{}] * 22,
                    "module_manifest_version": "runtime-manifest-v1",
                    "signature": {
                        "algorithm": "hmac-sha256",
                        "scope": "control_plane_hmac_v1",
                        "signature_hex": "abc123",
                    },
                },
            )
        if url.endswith("/v1/meta/contract"):
            return _FakeResponse(200, _fake_platform_contract_payload())
        if url.endswith("/openapi.json"):
            return _FakeResponse(200, _fake_openapi_payload())
        if url.endswith("/mcp/tools"):
            return _FakeResponse(200, _fake_mcp_tools_payload())
        if url.endswith("/mcp/sse"):
            return _FakeResponse(503, _fake_mcp_transport_unavailable_payload())
        if (
            url.endswith("/v1/models")
            or url.endswith("/v1/runs")
            or url.endswith("/v1/templates")
            or url.endswith("/v1/connectors")
            or url.endswith("/v1/analytics")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/events")
            or url.endswith("/v1/admin/runtime/modules")
            or url.endswith("/v1/admin/runtime/benchmarks")
            or url.endswith("/v1/admin/runtime/validation")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        raise AssertionError(url)

    def _fake_post(
        url: str,
        timeout: float,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        del timeout, json
        requested_urls.append(url)
        if (
            url.endswith("/v1/tokenize")
            or url.endswith("/v1/chat/completions")
            or url.endswith("/v1/count_tokens")
            or url.endswith("/v1/responses")
            or url.endswith("/v1/embeddings")
            or url.endswith("/v1/embeddings/similarity")
            or url.endswith("/v1/rerank")
            or url.endswith("/v1/agent/runs")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/resume")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/cancel")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/approve")
            or url.endswith("/v1/simulate")
            or url.endswith("/v1/decisions/plan")
            or url.endswith("/v1/jobs")
            or url.endswith("/v1/query")
            or url.endswith("/v1/verify")
            or url.endswith("/v1/sources/register")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        if url.endswith("/mcp"):
            return _FakeResponse(200, _fake_mcp_initialize_payload())
        raise AssertionError(url)

    def _fake_popen(*args: Any, **kwargs: Any) -> _FakeProc:
        del args
        assert kwargs["cwd"] == str(ROOT)
        assert kwargs["env"]["ALGENTA_SOURCE_REGISTRY_ROOT"] == str(tmp_path / "sources")
        assert kwargs["env"]["ALGENTA_RUNTIME_DIR"] == str(tmp_path / "runtime")
        assert kwargs["text"] is True
        return fake_proc

    monkeypatch.setattr("tests.test_runtime_startup_smoke._port_open", lambda host, port: port == DEFAULT_PORT)
    monkeypatch.setattr("tests.test_runtime_startup_smoke._wait_for_health", _fake_wait)
    monkeypatch.setattr(
        "tests.test_runtime_startup_smoke._endpoint_serves_canonical_startup_contract",
        lambda base_url: True,
    )
    monkeypatch.setattr("tests.test_runtime_startup_smoke._choose_free_port", lambda: 58123)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.get", _fake_get)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.post", _fake_post)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.subprocess.Popen", _fake_popen)

    base_url, proc, started_here = _probe_or_launch_runtime_endpoint(tmp_path, log_path)

    assert base_url == _base_url(58123)
    assert proc is fake_proc
    assert started_here is True
    assert wait_calls == [
        (_base_url(DEFAULT_PORT), False, 5),
        (_base_url(58123), True, 30),
    ]

    _assert_runtime_health_manifest_contract_and_openapi(base_url)

    assert requested_urls == _expected_requested_urls(_base_url(58123))


def test_startup_smoke_falls_back_to_free_port_when_8000_listener_is_stale(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api_server_8000.log"
    wait_calls: list[tuple[str, bool, float]] = []
    requested_urls: list[str] = []
    fake_proc = _FakeProc()

    def _fake_wait(
        base_url: str,
        _: Path,
        proc: subprocess.Popen[str] | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        wait_calls.append((base_url, proc is not None, timeout_seconds))

    def _fake_get(url: str, timeout: float, headers: dict[str, str] | None = None) -> _FakeResponse:
        del timeout
        requested_urls.append(url)
        if url.endswith("/v1/health"):
            return _FakeResponse(200, {"status": "ok", "timestamp": "2026-05-23T00:00:00Z"})
        if url.endswith("/v1/runtime/manifest"):
            return _FakeResponse(
                200,
                {
                    "runtime_version": "2026.05.0",
                    "modules": [{}] * 22,
                    "module_manifest_version": "runtime-manifest-v1",
                    "signature": {
                        "algorithm": "hmac-sha256",
                        "scope": "control_plane_hmac_v1",
                        "signature_hex": "abc123",
                    },
                },
            )
        if url.endswith("/v1/meta/contract"):
            return _FakeResponse(200, _fake_platform_contract_payload())
        if url.endswith("/openapi.json"):
            return _FakeResponse(200, _fake_openapi_payload())
        if url.endswith("/mcp/tools"):
            return _FakeResponse(200, _fake_mcp_tools_payload())
        if url.endswith("/mcp/sse"):
            return _FakeResponse(503, _fake_mcp_transport_unavailable_payload())
        if (
            url.endswith("/v1/models")
            or url.endswith("/v1/runs")
            or url.endswith("/v1/templates")
            or url.endswith("/v1/connectors")
            or url.endswith("/v1/analytics")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/events")
            or url.endswith("/v1/admin/runtime/modules")
            or url.endswith("/v1/admin/runtime/benchmarks")
            or url.endswith("/v1/admin/runtime/validation")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        raise AssertionError(url)

    def _fake_post(
        url: str,
        timeout: float,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        del timeout, json
        requested_urls.append(url)
        if (
            url.endswith("/v1/tokenize")
            or url.endswith("/v1/chat/completions")
            or url.endswith("/v1/count_tokens")
            or url.endswith("/v1/responses")
            or url.endswith("/v1/embeddings")
            or url.endswith("/v1/embeddings/similarity")
            or url.endswith("/v1/rerank")
            or url.endswith("/v1/agent/runs")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/resume")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/cancel")
            or url.endswith(f"/v1/agent/runs/{AGENT_RUN_TEST_ID}/approve")
            or url.endswith("/v1/simulate")
            or url.endswith("/v1/decisions/plan")
            or url.endswith("/v1/jobs")
            or url.endswith("/v1/query")
            or url.endswith("/v1/verify")
            or url.endswith("/v1/sources/register")
        ):
            if headers and (
                headers.get("X-API-Key") == INVALID_TEST_API_KEY
                or headers.get("Authorization") == f"Bearer {INVALID_TEST_API_KEY}"
            ):
                return _FakeResponse(401, _fake_invalid_api_key_payload())
            return _FakeResponse(401, _fake_unauthorized_payload())
        if url.endswith("/mcp"):
            return _FakeResponse(200, _fake_mcp_initialize_payload())
        raise AssertionError(url)

    def _fake_popen(*args: Any, **kwargs: Any) -> _FakeProc:
        del args
        assert kwargs["cwd"] == str(ROOT)
        assert kwargs["env"]["ALGENTA_SOURCE_REGISTRY_ROOT"] == str(tmp_path / "sources")
        assert kwargs["env"]["ALGENTA_RUNTIME_DIR"] == str(tmp_path / "runtime")
        assert kwargs["text"] is True
        return fake_proc

    monkeypatch.setattr(
        "tests.test_runtime_startup_smoke._port_open",
        lambda host, port: port == DEFAULT_PORT,
    )
    monkeypatch.setattr("tests.test_runtime_startup_smoke._wait_for_health", _fake_wait)
    monkeypatch.setattr(
        "tests.test_runtime_startup_smoke._endpoint_serves_canonical_startup_contract",
        lambda base_url: base_url != _base_url(DEFAULT_PORT),
    )
    monkeypatch.setattr("tests.test_runtime_startup_smoke._choose_free_port", lambda: 58124)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.get", _fake_get)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.httpx.post", _fake_post)
    monkeypatch.setattr("tests.test_runtime_startup_smoke.subprocess.Popen", _fake_popen)

    base_url, proc, started_here = _probe_or_launch_runtime_endpoint(tmp_path, log_path)

    assert base_url == _base_url(58124)
    assert proc is fake_proc
    assert started_here is True
    assert wait_calls == [
        (_base_url(DEFAULT_PORT), False, 5),
        (_base_url(58124), True, 30),
    ]

    _assert_runtime_health_manifest_contract_and_openapi(base_url)

    assert requested_urls == _expected_requested_urls(_base_url(58124))
