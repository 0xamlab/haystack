"""Protocol + security behavior of the standalone algenta-mcp package (GTM Wave 1, item 4 / PR2).

In-process tests against a respx-mocked upstream API (no network, no running server). They lock
the contract that matters for a Cursor/Claude-Desktop install:
  - the tool catalog exposes API-backed runtime libraries without a local daemon;
  - call-tool dispatches + forwards the caller's API key as `Authorization: Bearer …`;
  - request_overrides swaps the forwarded key per request;
  - errors (401 / 5xx / timeout) never leak the API key into the surfaced message;
  - the SDK-reused egress guard refuses cloud-owned URLs under a private profile.

Sync tests drive the async handlers via asyncio.run + respx as a context manager (no async plugin).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx
from algenta_mcp import registry
from algenta_mcp.client import request_overrides
from algenta_mcp.errors import (
    InvalidArgumentsError,
    MCPToolError,
    UnknownToolError,
    UnsupportedMCPAuthConfigurationError,
    serialize_tool_error,
)

_KEY = "de_live_SECRET_must_not_leak_0123456789abcdef"
_OVERRIDE_KEY = "de_live_OVERRIDE_key_must_not_leak_fedcba9876"
_BASE = "http://test-selfhost.local:8000"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", _KEY)
    monkeypatch.setenv("ALGENTA_BASE_URL", _BASE)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)


def test_list_tools_is_the_decoupled_catalog() -> None:
    specs = registry.get_tool_specs()
    names = {s["name"] for s in specs}
    # core tools present
    assert {"get_contract", "query_data", "simulate"} <= names, names
    # the valuable repository fix/pipeline tools were KEPT (vendored channel_envelope)
    assert "run_repository_fix" in names
    assert {"list_runtime_libraries", "execute_runtime_library"} <= names
    # every spec is well-formed for MCP list-tools
    for spec in specs:
        assert spec.get("name") and isinstance(spec.get("inputSchema"), dict), spec


def test_runtime_library_list_proxies_query_and_auth() -> None:
    with respx.mock as router:
        route = router.get(f"{_BASE}/v1/libraries").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )

        out = asyncio.run(
            registry.call_tool("list_runtime_libraries", {"q": "statistics", "limit": 25})
        )

        assert route.called
        request = route.calls.last.request
        assert request.headers["authorization"] == f"Bearer {_KEY}"
        assert dict(request.url.params) == {"limit": "25", "q": "statistics"}
        assert json.loads(out) == {"items": [], "total": 0}


def test_runtime_library_execute_proxies_exact_payload() -> None:
    with respx.mock as router:
        route = router.post(f"{_BASE}/v1/libraries/execute").mock(
            return_value=httpx.Response(200, json={"success": True, "result": 3.0})
        )
        arguments = {
            "module": "statistics.descriptive",
            "function": "mean",
            "args": {"values": [1.0, 2.0, 6.0]},
            "request_id": "req_runtime_1",
        }

        out = asyncio.run(registry.call_tool("execute_runtime_library", arguments))

        assert route.called
        request = route.calls.last.request
        assert request.headers["authorization"] == f"Bearer {_KEY}"
        assert json.loads(request.read()) == arguments
        assert json.loads(out) == {"success": True, "result": 3.0}


def test_runtime_library_list_paginates_to_requested_limit() -> None:
    def _page_response(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        modules = (
            [
                {"name": "alpha", "engine": "mojo", "functions": ["a"]},
                {"name": "beta", "engine": "mojo", "functions": ["b"]},
            ]
            if page == 1
            else [{"name": "gamma", "engine": "mojo", "functions": ["g"]}]
        )
        return httpx.Response(
            200,
            json={
                "modules": modules,
                "count": len(modules),
                "total": 3,
                "page": page,
                "limit": 3,
                "pages": 2,
            },
        )

    with respx.mock as router:
        route = router.get(f"{_BASE}/v1/libraries").mock(side_effect=_page_response)

        payload = json.loads(
            asyncio.run(registry.call_tool("list_runtime_libraries", {"limit": 3}))
        )

        assert route.call_count == 2
        assert [module["name"] for module in payload["modules"]] == ["alpha", "beta", "gamma"]
        assert payload["count"] == 3


def test_call_tool_forwards_bearer_auth_to_configured_base_url() -> None:
    with respx.mock as router:
        route = router.get(f"{_BASE}/v1/meta/contract").mock(
            return_value=httpx.Response(200, json={"contract_version": "2026.06"})
        )
        out = asyncio.run(registry.call_tool("get_contract", {}))
        assert route.called
        assert route.calls.last.request.headers["authorization"] == f"Bearer {_KEY}"
        assert "contract_version" in out


def test_simulate_maps_n_simulations_to_api_runs() -> None:
    with respx.mock as router:
        route = router.post(f"{_BASE}/v1/simulate").mock(
            return_value=httpx.Response(
                200,
                json={
                    "recommended_action": "proceed",
                    "confidence": 1.0,
                    "rationale": "ok",
                    "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
                    "percentiles": {"p5": 1.0, "p95": 1.0},
                    "scenarios_run": 1234,
                    "run_id": "run_123",
                },
            )
        )

        out = asyncio.run(
            registry.call_tool(
                "simulate",
                {
                    "objective": "maximize_net_value",
                    "n_simulations": 1234,
                    "variables": [{"name": "revenue", "low": 1.0, "high": 2.0}],
                },
            )
        )

        assert route.called
        body = json.loads(route.calls.last.request.read().decode())
        assert body["runs"] == 1234
        assert "n_simulations" not in body
        assert json.loads(out)["scenarios_run"] == 1234


def test_simulate_without_objective_uses_api_auto_default() -> None:
    with respx.mock as router:
        route = router.post(f"{_BASE}/v1/simulate").mock(
            return_value=httpx.Response(
                200,
                json={
                    "recommended_action": "proceed",
                    "confidence": 1.0,
                    "rationale": "ok",
                    "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
                    "percentiles": {"p5": 1.0, "p95": 1.0},
                    "scenarios_run": 10000,
                    "run_id": "run_123",
                },
            )
        )

        asyncio.run(
            registry.call_tool(
                "simulate",
                {"variables": [{"name": "revenue", "low": 1.0, "high": 2.0}]},
            )
        )

        body = json.loads(route.calls.last.request.read().decode())
        assert body["scenario"]["objective"] == "maximize_net_value"


def test_simulate_expert_maps_to_api_simulation_contract() -> None:
    with respx.mock as router:
        route = router.post(f"{_BASE}/v1/simulate").mock(
            return_value=httpx.Response(
                200,
                json={
                    "recommended_action": "proceed",
                    "confidence": 1.0,
                    "rationale": "ok",
                    "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
                    "percentiles": {"p5": 1.0, "p95": 1.0},
                    "scenarios_run": 250,
                    "run_id": "run_123",
                },
            )
        )

        out = asyncio.run(
            registry.call_tool(
                "simulate",
                {
                    "mode": "expert",
                    "objective_function": "revenue - cost",
                    "n_simulations": 250,
                    "variables": [
                        {"name": "revenue", "low": 1.0, "mode": 1.5, "high": 2.0},
                        {"name": "cost", "low": 0.2, "mode": 0.4, "high": 0.7},
                    ],
                },
            )
        )

        body = json.loads(route.calls.last.request.read().decode())
        assert body == {
            "mode": "expert",
            "runs": 250,
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "triangular",
                        "params": {"low": 1.0, "mode": 1.5, "high": 2.0},
                    },
                    {
                        "name": "cost",
                        "distribution": "triangular",
                        "params": {"low": 0.2, "mode": 0.4, "high": 0.7},
                    },
                ],
                "objective_function": "revenue - cost",
            },
        }
        assert json.loads(out)["scenarios_run"] == 250


def test_simulate_expert_requires_objective_function() -> None:
    out = asyncio.run(
        registry.call_tool(
            "simulate",
            {
                "mode": "expert",
                "variables": [{"name": "revenue", "low": 1.0, "mode": 1.5, "high": 2.0}],
            },
        )
    )

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "expert mode requires objective_function",
        }
    }


def test_simulate_rejects_malformed_variables() -> None:
    out = asyncio.run(registry.call_tool("simulate", {"variables": ["not-an-object"]}))

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "variables must be an array of objects",
        }
    }


def test_simulate_rejects_invalid_auto_objective() -> None:
    out = asyncio.run(
        registry.call_tool(
            "simulate",
            {
                "objective": "maximize",
                "variables": [{"name": "revenue", "low": 1.0, "high": 2.0}],
            },
        )
    )

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "objective must be a supported auto-mode objective",
        }
    }


def test_request_overrides_swaps_the_forwarded_key() -> None:
    with respx.mock as router:
        route = router.get(f"{_BASE}/v1/meta/contract").mock(
            return_value=httpx.Response(200, json={})
        )

        async def _run():
            with request_overrides(api_key=_OVERRIDE_KEY):
                await registry.call_tool("get_contract", {})

        asyncio.run(_run())
        assert route.calls.last.request.headers["authorization"] == f"Bearer {_OVERRIDE_KEY}"


@pytest.mark.parametrize(
    "response",
    [
        # plain 401 + a body that REFLECTS the key (a hostile/verbose upstream).
        httpx.Response(401, json={"error": {"code": "unauthorized", "message": f"bad key {_KEY}"}}),
        # plain 4xx with the key reflected in a non-structured body.
        httpx.Response(422, text=f"rejected request with Authorization: Bearer {_KEY}"),
        # STRUCTURED 5xx (the path the original tests missed — not converted to 'unavailable').
        httpx.Response(500, json={"error": {"code": "x", "message": f"boom {_KEY}"}}),
    ],
)
def test_upstream_errors_never_leak_the_api_key(response) -> None:
    with respx.mock as router:
        router.get(f"{_BASE}/v1/meta/contract").mock(return_value=response)
        with pytest.raises(Exception) as exc:  # noqa: PT011 — exact type varies by status
            asyncio.run(registry.call_tool("get_contract", {}))
    # Check BOTH surfaces a client/operator actually sees: the raised message (logged via str(exc))
    # AND the serialized tool error returned over the MCP wire.
    serialized = serialize_tool_error(exc.value, tool_name="get_contract")
    surfaces = f"{exc.value!r} {exc.value} {serialized}"
    assert _KEY not in surfaces, "API key leaked into a surfaced/returned tool error"


def test_timeout_surfaces_a_clean_error_without_the_key() -> None:
    with respx.mock as router:
        router.get(f"{_BASE}/v1/meta/contract").mock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(MCPToolError) as exc:
            asyncio.run(registry.call_tool("get_contract", {}))
    assert _KEY not in f"{exc.value!r} {exc.value}"


def test_unknown_tool_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        asyncio.run(registry.call_tool("not_a_real_tool", {}))


def test_egress_guard_refuses_cloud_url_under_private_profile(monkeypatch) -> None:
    # Reused from the SDK: a private profile must not target an Algenta-owned cloud URL.
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    with pytest.raises(MCPToolError):
        asyncio.run(registry.call_tool("get_contract", {}))


# ── Error-envelope contract: tool failures arrive as isError=True on both transports ──
#
# Regression coverage for the two protocol bugs in the 2026-09-23 external first-run audit:
#   Bug 1 — both transports returned EVERY tool failure (auth pre-flight, unknown tool,
#           upstream 4xx/5xx) as a successful CallToolResult (isError=False); agents read
#           failures as output. The serialized error JSON in content[0].text is unchanged;
#           only the envelope flag moved.
#   Bug 2 — a missing required argument surfaced as unknown_tool (404) via a bare-KeyError
#           mapping; arguments are now validated against the tool's inputSchema BEFORE
#           dispatch (invalid_arguments, 400, naming the field), and only a genuine
#           dispatch miss reports unknown_tool.


class _AbortStdioError(Exception):
    """Stops run_stdio_server() the instant its real Server is built, before stdin/stdout."""


async def _capture_real_stdio_server() -> Any:
    """Build the REAL stdio Server by spying on the SDK's public Server.__init__."""
    import contextlib

    import mcp.server as mcp_server_module
    import mcp.server.stdio as stdio_module

    captured: dict[str, Any] = {}
    original_init = mcp_server_module.Server.__init__

    def _capturing_init(self: Any, *args: Any, **kwargs: Any) -> None:
        captured["server"] = self
        original_init(self, *args, **kwargs)

    @contextlib.asynccontextmanager
    async def _abort_before_real_stdio():
        raise _AbortStdioError()
        yield  # pragma: no cover - unreachable, required to keep this an async generator

    mcp_server_module.Server.__init__ = _capturing_init
    stdio_module.stdio_server = _abort_before_real_stdio
    try:
        from algenta_mcp.transports.stdio import run_stdio_server

        try:
            await run_stdio_server()
        except _AbortStdioError:
            pass
    finally:
        mcp_server_module.Server.__init__ = original_init
    assert "server" in captured, "run_stdio_server() did not construct a Server"
    return captured["server"]


def _stdio_call_tool(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    from mcp import ClientSession
    from mcp.client._memory import InMemoryTransport

    async def _run() -> Any:
        async with InMemoryTransport(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)

    return asyncio.run(_run())


def test_stdio_auth_failure_is_marked_is_error(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    server = asyncio.run(_capture_real_stdio_server())

    result = _stdio_call_tool(server, "list_models", {})

    assert result.is_error is True
    assert "unsupported_mcp_auth_configuration" in result.content[0].text


def test_stdio_unknown_tool_is_marked_is_error() -> None:
    server = asyncio.run(_capture_real_stdio_server())

    result = _stdio_call_tool(server, "not_a_real_tool", {})

    assert result.is_error is True
    assert "unknown_tool" in result.content[0].text


def test_stdio_upstream_401_is_marked_is_error() -> None:
    with respx.mock as router:
        router.post(f"{_BASE}/v1/tokenize").mock(
            return_value=httpx.Response(
                401, json={"error": {"code": "invalid_api_key", "message": "bad key"}}
            )
        )
        server = asyncio.run(_capture_real_stdio_server())
        result = _stdio_call_tool(server, "tokenize", {"input": "hello"})

    assert result.is_error is True
    assert "invalid_api_key" in result.content[0].text


def test_stdio_success_stays_is_error_false() -> None:
    with respx.mock as router:
        router.post(f"{_BASE}/v1/tokenize").mock(
            return_value=httpx.Response(
                200, json={"tokens": ["hello"], "token_count": 1, "model": "text.tokenizer"}
            )
        )
        server = asyncio.run(_capture_real_stdio_server())
        result = _stdio_call_tool(server, "tokenize", {"input": "hello"})

    assert result.is_error is False
    assert "hello" in result.content[0].text


_HTTP_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-11-25",
}
_INIT_PARAMS: dict[str, Any] = {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {"name": "algenta-package-test", "version": "1.0.0"},
}


def _http_rpc(
    client: Any,
    method: str,
    params: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return client.post(
        "/mcp",
        headers={**_HTTP_HEADERS, **(headers or {})},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )


def _build_test_http_client() -> Any:
    from algenta_mcp.transports.http_sse import _build_http_app
    from starlette.testclient import TestClient

    return TestClient(_build_http_app(), base_url="http://127.0.0.1:8001")


def test_http_unknown_tool_is_marked_is_error() -> None:
    with _build_test_http_client() as client:
        _http_rpc(client, "initialize", _INIT_PARAMS)
        response = _http_rpc(
            client,
            "tools/call",
            {"name": "not_a_real_tool", "arguments": {}},
            headers={"Authorization": f"Bearer {_KEY}"},
        )

    payload = response.json()["result"]
    assert payload["isError"] is True
    assert "unknown_tool" in payload["content"][0]["text"]


def test_http_upstream_401_is_marked_is_error() -> None:
    with respx.mock as router:
        router.post(f"{_BASE}/v1/tokenize").mock(
            return_value=httpx.Response(
                401, json={"error": {"code": "invalid_api_key", "message": "bad key"}}
            )
        )
        with _build_test_http_client() as client:
            _http_rpc(client, "initialize", _INIT_PARAMS)
            response = _http_rpc(
                client,
                "tools/call",
                {"name": "tokenize", "arguments": {"input": "hello"}},
                headers={"Authorization": f"Bearer {_KEY}"},
            )

    payload = response.json()["result"]
    assert payload["isError"] is True
    assert "invalid_api_key" in payload["content"][0]["text"]


def test_http_success_stays_is_error_false() -> None:
    with respx.mock as router:
        router.post(f"{_BASE}/v1/tokenize").mock(
            return_value=httpx.Response(
                200, json={"tokens": ["hello"], "token_count": 1, "model": "text.tokenizer"}
            )
        )
        with _build_test_http_client() as client:
            _http_rpc(client, "initialize", _INIT_PARAMS)
            response = _http_rpc(
                client,
                "tools/call",
                {"name": "tokenize", "arguments": {"input": "hello"}},
                headers={"Authorization": f"Bearer {_KEY}"},
            )

    assert response.json()["result"]["isError"] is False


def test_http_anonymous_tool_call_is_401_with_free_login_guidance() -> None:
    with _build_test_http_client() as client:
        _http_rpc(client, "initialize", _INIT_PARAMS)
        response = _http_rpc(
            client, "tools/call", {"name": "tokenize", "arguments": {"input": "hello"}}
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == -32001
    assert body["error"]["message"] == (
        "Authentication required: executing tools needs a free community login — "
        "device registration at algenta.ai (free). "
        "Introspection (initialize/tools/list) needs no credentials."
    )


# ── Argument validation (invalid_arguments, 400) precedes dispatch and auth ──


def test_missing_required_argument_is_invalid_arguments_naming_the_field() -> None:
    with pytest.raises(InvalidArgumentsError) as exc:
        asyncio.run(registry.call_tool("tokenize", {}))

    assert exc.value.error_code == "invalid_arguments"
    assert exc.value.status_code == 400
    payload = json.loads(serialize_tool_error(exc.value, tool_name="tokenize"))
    assert payload == {
        "error": {
            "code": "invalid_arguments",
            "message": "Invalid arguments for tool 'tokenize': missing required argument 'input'.",
            "status_code": 400,
            "details": [{"argument": "input", "problem": "missing required argument 'input'"}],
        }
    }


def test_embeddings_missing_input_is_invalid_arguments() -> None:
    with pytest.raises(InvalidArgumentsError, match="'input'"):
        asyncio.run(registry.call_tool("embeddings", {"dimensions": 64}))


def test_wrong_typed_argument_is_invalid_arguments_naming_the_field() -> None:
    with pytest.raises(InvalidArgumentsError) as exc:
        asyncio.run(registry.call_tool("embeddings", {"input": "hello", "dimensions": "abc"}))

    assert "dimensions" in str(exc.value)
    assert "integer" in str(exc.value)


def test_arguments_must_be_a_json_object() -> None:
    with pytest.raises(InvalidArgumentsError, match="JSON object"):
        asyncio.run(registry.call_tool("tokenize", ["not", "an", "object"]))  # type: ignore[arg-type]


def test_unknown_tool_is_a_genuine_dispatch_miss() -> None:
    with pytest.raises(UnknownToolError) as exc:
        asyncio.run(registry.call_tool("not_a_real_tool", {}))

    # Backward compatible: still a KeyError for existing except-KeyError callers.
    assert isinstance(exc.value, KeyError)
    assert str(exc.value) == "Unknown tool: not_a_real_tool"
    payload = json.loads(serialize_tool_error(exc.value, tool_name="not_a_real_tool"))
    assert payload == {
        "error": {
            "code": "unknown_tool",
            "message": "Unknown tool: not_a_real_tool",
            "status_code": 404,
        }
    }


def test_out_of_edition_tool_is_the_same_dispatch_miss() -> None:
    # A product edition is a hard boundary: outside the visible set reads as nonexistent.
    with pytest.raises(UnknownToolError):
        asyncio.run(registry.call_tool("tokenize", {"input": "x"}, frozenset({"embeddings"})))


def test_bare_keyerror_no_longer_maps_to_unknown_tool() -> None:
    # The narrowed branch: only UnknownToolError means unknown_tool; any other KeyError
    # escaping a handler is an internal failure (tool_error/500), never a wrong 404.
    payload = json.loads(serialize_tool_error(KeyError("input"), tool_name="tokenize"))
    assert payload["error"]["code"] == "tool_error"
    assert payload["error"]["status_code"] == 500


def test_argument_validation_precedes_the_auth_preflight(monkeypatch) -> None:
    """Error precedence must not depend on argument shape: a malformed call reports
    invalid_arguments with or without a credential; the auth pre-flight fires only
    once the arguments are valid (unknown_tool 404 → invalid_arguments 400 → auth 400)."""
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(InvalidArgumentsError):
        asyncio.run(registry.call_tool("tokenize", {}))

    with pytest.raises(UnsupportedMCPAuthConfigurationError):
        asyncio.run(registry.call_tool("tokenize", {"input": "hello"}))
