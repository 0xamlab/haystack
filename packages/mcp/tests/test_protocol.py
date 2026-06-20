"""Protocol + security behavior of the standalone algenta-mcp package (GTM Wave 1, item 4 / PR2).

In-process tests against a respx-mocked upstream API (no network, no running server). They lock
the contract that matters for a Cursor/Claude-Desktop install:
  - the tool catalog (list-tools) is the decoupled set (daemon tools dropped; repo fix/pipeline kept);
  - call-tool dispatches + forwards the caller's API key as `Authorization: Bearer …`;
  - request_overrides swaps the forwarded key per request;
  - errors (401 / 5xx / timeout) never leak the API key into the surfaced message;
  - the SDK-reused egress guard refuses cloud-owned URLs under a private profile.

Sync tests drive the async handlers via asyncio.run + respx as a context manager (no async plugin).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from algenta_mcp import registry
from algenta_mcp.client import request_overrides
from algenta_mcp.errors import MCPToolError

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
    # the local-daemon runtime-libraries tools were DROPPED for the standalone proxy
    assert "list_runtime_libraries" not in names
    assert "execute_runtime_library" not in names
    # every spec is well-formed for MCP list-tools
    for spec in specs:
        assert spec.get("name") and isinstance(spec.get("inputSchema"), dict), spec


def test_call_tool_forwards_bearer_auth_to_configured_base_url() -> None:
    with respx.mock as router:
        route = router.get(f"{_BASE}/v1/meta/contract").mock(
            return_value=httpx.Response(200, json={"contract_version": "2026.06"})
        )
        out = asyncio.run(registry.call_tool("get_contract", {}))
        assert route.called
        assert route.calls.last.request.headers["authorization"] == f"Bearer {_KEY}"
        assert "contract_version" in out


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


from algenta_mcp.errors import serialize_tool_error


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
    surfaces = f"{exc.value!r} {exc.value} {serialize_tool_error(exc.value, tool_name='get_contract')}"
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
