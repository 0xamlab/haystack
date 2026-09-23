from __future__ import annotations

import builtins
import importlib.util
import json
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI

from apps.mcp_server.server import create_fastapi_router
from tests._asgi_client import SyncASGIClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module_name", ["apps.mcp_server.server", "algenta_mcp.server"])
def test_mcp_server_main_handles_keyboard_interrupt_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
) -> None:
    if module_name == "algenta_mcp.server":
        module_path = ROOT / "packages/mcp/algenta_mcp/server.py"
        spec = importlib.util.spec_from_file_location("package_algenta_mcp_server", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = __import__(module_name, fromlist=["main"])

    def _interrupt(coroutine: Any) -> None:
        coroutine.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: SimpleNamespace(mode="http", port=8765),
    )
    monkeypatch.setattr(module.asyncio, "run", _interrupt)

    module.main()


def test_create_fastapi_router_keeps_tools_endpoint_without_mcp_package(
    monkeypatch,
) -> None:
    real_import = builtins.__import__

    def _fake_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name.startswith("mcp"):
            raise ImportError("mcp package not installed")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    router = create_fastapi_router()

    assert router is not None
    app = FastAPI()
    app.include_router(router)

    with SyncASGIClient(app) as client:
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        payload = response.json()
        assert "tools" in payload
        assert payload["tools"]

        streamable_response = client.post("/mcp", json={})
        assert streamable_response.status_code == 503
        assert streamable_response.json()["error"]["code"] == "mcp_transport_unavailable"

        sse_response = client.get("/mcp/sse")
        assert sse_response.status_code == 503
        assert sse_response.json()["error"]["code"] == "mcp_transport_unavailable"

        messages_response = client.post("/mcp/messages", json={})
        assert messages_response.status_code == 503
        assert messages_response.json()["error"]["code"] == "mcp_transport_unavailable"

        openapi_response = client.get("/openapi.json")
        assert openapi_response.status_code == 200
        openapi = openapi_response.json()

    assert "/mcp/tools" in openapi["paths"]
    assert "/mcp" in openapi["paths"]
    assert "/mcp/sse" in openapi["paths"]
    assert "/mcp/messages" in openapi["paths"]
    assert openapi["paths"]["/mcp/tools"]["get"].get("security") is None
    assert openapi["paths"]["/mcp"]["post"].get("security") is None
    assert openapi["paths"]["/mcp/sse"]["get"].get("security") is None
    assert openapi["paths"]["/mcp/messages"]["post"].get("security") is None
    transport_operation_ids = {
        openapi["paths"]["/mcp"]["get"]["operationId"],
        openapi["paths"]["/mcp"]["post"]["operationId"],
        openapi["paths"]["/mcp"]["delete"]["operationId"],
        openapi["paths"]["/mcp/sse"]["get"]["operationId"],
        openapi["paths"]["/mcp/messages"]["post"]["operationId"],
    }
    assert len(transport_operation_ids) == 5
    assert all(transport_operation_ids)
    assert "200" in openapi["paths"]["/mcp/tools"]["get"]["responses"]
    assert "503" in openapi["paths"]["/mcp"]["post"]["responses"]
    assert "503" in openapi["paths"]["/mcp/sse"]["get"]["responses"]
    assert "503" in openapi["paths"]["/mcp/messages"]["post"]["responses"]
    assert "200" not in openapi["paths"]["/mcp/sse"]["get"]["responses"]
    assert "200" not in openapi["paths"]["/mcp/messages"]["post"]["responses"]
    assert (
        openapi["paths"]["/mcp/sse"]["get"]["responses"]["503"]["description"]
        == "Legacy MCP SSE transport unavailable in this environment."
    )
    assert (
        openapi["paths"]["/mcp/messages"]["post"]["responses"]["503"]["description"]
        == "Legacy MCP message transport unavailable in this environment."
    )


def test_streamable_http_negotiates_latest_protocol_and_lists_tools(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from apps.mcp_server.transports.http_sse import _build_http_app

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "algenta-test", "version": "1.0.0"},
        },
    }

    with TestClient(_build_http_app(), base_url="https://api.algenta.ai") as client:
        response = client.post("/mcp", headers=request_headers, json=initialize)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        payload = response.json()
        assert payload["result"]["protocolVersion"] == "2025-11-25"
        from apps.mcp_server import config as _engine_mcp_config
        assert payload["result"]["serverInfo"]["version"] == _engine_mcp_config.VERSION

        tools_response = client.post(
            "/mcp",
            headers=request_headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert tools_response.status_code == 200
        tool_names = {item["name"] for item in tools_response.json()["result"]["tools"]}
        assert {"get_contract", "list_data", "query_data"} <= tool_names

        invalid_version = client.post(
            "/mcp",
            headers={**request_headers, "MCP-Protocol-Version": "2099-01-01"},
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
        )
        assert invalid_version.status_code == 400


def test_modern_protocol_era_round_trips_through_real_registry_and_auth_challenge(
    monkeypatch,
) -> None:
    """The 2026-07-28 per-request era (no `initialize` handshake — a `_meta`-enveloped request
    plus `MCP-Protocol-Version`/`Mcp-Method` headers) against a REAL running server instance: real
    `Server` dual-era dispatch (on_list_tools=/on_call_tool=, mcp>=2.0.0), real
    `_MCPToolCallAuthChallengeASGIApp` auth gate, and real `apps.mcp_server.registry.call_tool`
    name-based dispatch. Only the tool's own outbound HTTP call to the downstream Algenta API is
    stubbed (api_with_status) — same boundary test_mcp_meta_tools.py stubs at, and the same
    minimal-mock level test_published_mcp_package_uses_same_streamable_http_contract already uses
    for the legacy handshake path below. Nothing about the SDK, the router, or the auth challenge
    is mocked.
    """
    pytest.importorskip("mcp")
    from copy import deepcopy

    from starlette.testclient import TestClient

    from apps.mcp_server import config as mcp_config
    from apps.mcp_server.tools import meta as meta_tools
    from apps.mcp_server.transports.http_sse import _build_http_app
    from apps.platform_contract import load_platform_contract_manifest

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")

    # A real, fully valid contract payload (same source _platform_contract_payload() in
    # tests/test_mcp_meta_tools.py uses) — the handler validates this against the real
    # PlatformContractResponse schema, so a hand-trimmed dict would fail that real validation.
    contract_payload = deepcopy(load_platform_contract_manifest())

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/meta/contract")
        return 200, contract_payload

    monkeypatch.setattr(meta_tools, "api_with_status", _fake_api_with_status)

    modern_meta = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "algenta-modern-era-test", "version": "1.0.0"},
    }
    modern_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2026-07-28",
    }

    with TestClient(_build_http_app(), base_url="https://api.algenta.ai") as client:
        # 1. Discovery (tools/list) is public on the modern path too — no handshake, no session.
        tools_response = client.post(
            "/mcp",
            headers={**modern_headers, "Mcp-Method": "tools/list"},
            json={
                "jsonrpc": "2.0",
                "id": "modern-tools-list",
                "method": "tools/list",
                "params": {"_meta": modern_meta},
            },
        )
        assert tools_response.status_code == 200
        list_result = tools_response.json()["result"]
        # resultType/serverInfo are stamped unconditionally by the SDK for 2026-07-28 responses —
        # their presence proves this really took the modern path, not a legacy one silently
        # ignoring the extra headers.
        assert list_result["resultType"] == "complete"
        assert list_result["_meta"]["io.modelcontextprotocol/serverInfo"]["version"] == mcp_config.VERSION
        tool_names = {item["name"] for item in list_result["tools"]}
        assert {"get_contract", "list_data", "query_data"} <= tool_names

        # 2. Execution IS gated — same auth-challenge posture the legacy handshake path gets
        # (test_embedded_tool_call_without_auth_returns_oauth_challenge pins the legacy version of
        # this exact assertion; the challenge sniffs the JSON-RPC body's "method", not the era).
        anonymous_call = client.post(
            "/mcp",
            headers={**modern_headers, "Mcp-Method": "tools/call"},
            json={
                "jsonrpc": "2.0",
                "id": "modern-call-anonymous",
                "method": "tools/call",
                "params": {"name": "get_contract", "arguments": {}, "_meta": modern_meta},
            },
        )
        assert anonymous_call.status_code == 401
        assert anonymous_call.json()["error"]["code"] == -32001

        # 3. An authenticated caller's modern tools/call reaches Algenta's REAL registry/router:
        # get_contract really executes end to end and really answers with this server's own
        # contract tool output, round-tripped through the real running app.
        authenticated_call = client.post(
            "/mcp",
            headers={
                **modern_headers,
                "Mcp-Method": "tools/call",
                "Mcp-Name": "get_contract",
                "Authorization": "Bearer sk-modern-era-round-trip-test",
            },
            json={
                "jsonrpc": "2.0",
                "id": "modern-call-authenticated",
                "method": "tools/call",
                "params": {"name": "get_contract", "arguments": {}, "_meta": modern_meta},
            },
        )

    assert authenticated_call.status_code == 200
    call_result = authenticated_call.json()["result"]
    assert call_result["resultType"] == "complete"
    assert call_result["isError"] is False
    tool_output = json.loads(call_result["content"][0]["text"])
    assert tool_output["contract_version"] == "v1.5"
    # The truthful field get_contract adds on top of whatever the (here-stubbed) API returned —
    # this deployment really serves both eras, and this real round trip proves it end to end.
    assert tool_output["mcp_protocol_versions_supported"] == list(
        mcp_config.MCP_PROTOCOL_VERSIONS_SUPPORTED
    )


def test_streamable_http_rejects_untrusted_host_and_origin(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from apps.mcp_server.transports.http_sse import _build_http_app

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "algenta-test", "version": "1.0.0"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    with TestClient(_build_http_app(), base_url="https://api.algenta.ai") as client:
        bad_origin = client.post(
            "/mcp",
            headers={**headers, "Origin": "https://attacker.example"},
            json=initialize,
        )
        assert bad_origin.status_code == 403

        bad_host = client.post(
            "/mcp",
            headers={**headers, "Host": "attacker.example"},
            json=initialize,
        )
        assert bad_host.status_code == 421


def test_embedded_base_url_ignores_untrusted_forwarded_headers() -> None:
    from apps.mcp_server.transports.http_sse import _scope_base_url

    scope: dict[str, Any] = {
        "scheme": "https",
        "headers": [
            (b"host", b"api.algenta.ai"),
            (b"x-forwarded-host", b"attacker.example"),
            (b"x-forwarded-proto", b"http"),
        ],
    }

    assert _scope_base_url(scope) == "https://api.algenta.ai"


def test_embedded_mcp_uses_validated_loopback_target(monkeypatch) -> None:
    from apps.mcp_server.transports.http_sse import _embedded_downstream_base_url

    monkeypatch.setenv("PORT", "9123")
    assert _embedded_downstream_base_url({}) == "http://127.0.0.1:9123"

    monkeypatch.setenv("ALGENTA_MCP_LOOPBACK_URL", "https://localhost:9443")
    assert _embedded_downstream_base_url({}) == "https://localhost:9443"

    monkeypatch.setenv("ALGENTA_MCP_LOOPBACK_URL", "https://attacker.example")
    with pytest.raises(ValueError, match="absolute loopback"):
        _embedded_downstream_base_url({})


def test_embedded_tool_call_without_auth_returns_oauth_challenge(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from apps.mcp_server.transports.http_sse import _build_fastapi_router

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    router = _build_fastapi_router()
    assert router is not None
    app = FastAPI()
    app.include_router(router)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }

    with TestClient(app, base_url="https://api.algenta.ai") as client:
        discovery = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        challenge = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_contract", "arguments": {}},
            },
        )

    assert discovery.status_code == 200
    assert challenge.status_code == 401
    assert challenge.headers["www-authenticate"].startswith('Bearer realm="algenta"')
    assert challenge.json() == {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {
            "code": -32001,
            "message": (
                "Authentication required: executing tools needs a free community login — "
                "device registration at algenta.ai (free). "
                "Introspection (initialize/tools/list) needs no credentials."
            ),
        },
    }


def test_embedded_legacy_message_route_reaches_mcp_transport(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from apps.mcp_server.transports.http_sse import _build_fastapi_router

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    router = _build_fastapi_router()
    assert router is not None
    app = FastAPI()
    app.include_router(router)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.post("/mcp/messages", json={})

    assert response.status_code not in {404, 500}


def test_streamable_manager_lifespan_supports_sync_asgi_harness(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from apps.mcp_server.transports.http_sse import _build_fastapi_router

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    router = _build_fastapi_router()
    assert router is not None
    app = FastAPI()
    app.include_router(router)

    for _ in range(2):
        with SyncASGIClient(app, manage_lifespan=True) as client:
            response = client.get("/mcp/tools")
        assert response.status_code == 200


def test_published_mcp_package_uses_same_streamable_http_contract(monkeypatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    monkeypatch.syspath_prepend(str(ROOT / "packages" / "python-sdk"))
    monkeypatch.syspath_prepend(str(ROOT / "packages" / "mcp"))
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://engine.example")

    from algenta_mcp import client as package_client
    from algenta_mcp import registry as package_registry
    from algenta_mcp.transports.http_sse import _build_http_app

    async def _capture_downstream_base_url(
        _name: str,
        _arguments: dict[str, Any],
        _allowed: frozenset[str] | None = None,
    ) -> str:
        return package_client.resolve_base_url()

    monkeypatch.setattr(package_registry, "call_tool", _capture_downstream_base_url)

    assert version("mcp") == "2.0.0"
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "algenta-package-test", "version": "1.0.0"},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    tool_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "get_contract", "arguments": {}},
    }

    with TestClient(_build_http_app(), base_url="http://127.0.0.1:8001") as client:
        response = client.post("/mcp", headers=headers, json=initialize)
        anonymous_tool_response = client.post("/mcp", headers=headers, json=tool_call)
        tool_response = client.post(
            "/mcp",
            headers={**headers, "Authorization": "Bearer sk-package-contract-test"},
            json=tool_call,
        )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["protocolVersion"] == "2025-11-25"
    # This test exercises the standalone published package, whose serverInfo reports the
    # package version (importlib.metadata, guarded by the D2 lockstep test) — not the
    # engine router's embedded literal.
    from algenta_mcp import config as _pkg_mcp_config
    assert payload["serverInfo"]["version"] == _pkg_mcp_config.VERSION
    # Discovery (initialize) is open; execution is not. The standalone app used to mount the session
    # manager bare, so a keyless tools/call ran the tool with the server's own ambient credential.
    assert anonymous_tool_response.status_code == 401
    assert anonymous_tool_response.json()["error"]["code"] == -32001
    assert tool_response.status_code == 200
    assert tool_response.json()["result"]["content"][0]["text"] == "https://engine.example"
