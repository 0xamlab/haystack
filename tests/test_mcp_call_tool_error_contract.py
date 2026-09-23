"""Apps-side contract tests for the 1.0.28 MCP error model (ported from the package's
packages/mcp/tests/test_protocol.py — the embedded copy in apps/mcp_server now shares that
contract, and these tests keep the two from diverging again):

  - registry.call_tool validates arguments against the tool's published inputSchema BEFORE
    dispatch (and therefore before the auth pre-flight), so a missing or ill-typed argument
    surfaces as invalid_arguments/400 naming the field — never as unknown_tool/404.
  - Only a genuine dispatch miss raises UnknownToolError (still a KeyError subclass for
    backward-compatible except-KeyError callers); a bare KeyError escaping a handler is an
    internal failure (tool_error/500), no longer misreported as unknown_tool.
  - Deterministic precedence: dispatch miss 404 → invalid arguments 400 → auth pre-flight 400.
  - Both transports mark the CallToolResult envelope isError=True when the payload is a
    serialized error (the stdio flavor is pinned end-to-end by
    tests/test_mcp_official_sdk_e2e.py; the Streamable-HTTP flavor is pinned here over the
    real ASGI app, with no network — dispatch-miss and invalid-argument failures both fire
    before any upstream call).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from apps.mcp_server import registry
from apps.mcp_server.errors import (
    InvalidArgumentsError,
    UnknownToolError,
    UnsupportedMCPAuthConfigurationError,
    serialize_tool_error,
)


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


def test_argument_validation_precedes_the_auth_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Error precedence must not depend on argument shape: a malformed call reports
    invalid_arguments with or without a credential; the auth pre-flight fires only
    once the arguments are valid (unknown_tool 404 → invalid_arguments 400 → auth 400)."""
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    with pytest.raises(InvalidArgumentsError):
        asyncio.run(registry.call_tool("tokenize", {}))

    with pytest.raises(UnsupportedMCPAuthConfigurationError):
        asyncio.run(registry.call_tool("tokenize", {"input": "hello"}))


# ── Streamable HTTP transport: serialized errors carry isError=True on the real ASGI app ──


def _post_tool_call(client: TestClient, name: str, arguments: dict) -> dict:
    response = client.post(
        "/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            # Any bearer satisfies the presence-check challenge; both failures below fire
            # inside the registry BEFORE the keyed client would ever touch the network.
            "Authorization": "Bearer sk-error-envelope-contract-test",
        },
        json={
            "jsonrpc": "2.0",
            "id": f"error-envelope-{name}",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response.status_code == 200, response.text[:500]
    return response.json()["result"]


def _trusted_test_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # The transport's DNS-rebinding guard rejects TestClient's default `testserver` Host;
    # serving the app under the configured public base URL is the established pattern
    # (tests/test_mcp_router.py's modern-era round trip).
    pytest.importorskip("mcp")
    from apps.mcp_server.transports.http_sse import _build_http_app

    monkeypatch.setenv("ALGENTA_BASE_URL", "https://api.algenta.ai")
    return TestClient(_build_http_app(), base_url="https://api.algenta.ai")


def test_http_unknown_tool_is_marked_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with _trusted_test_client(monkeypatch) as client:
        result = _post_tool_call(client, "not_a_real_tool", {})

    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["error"]["code"] == "unknown_tool"
    assert payload["error"]["status_code"] == 404


def test_http_invalid_arguments_is_marked_is_error_and_precedes_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # tokenize with no `input`: invalid_arguments/400 even though the bearer is bogus —
    # validation precedes the auth pre-flight, so this needs no real upstream.
    with _trusted_test_client(monkeypatch) as client:
        result = _post_tool_call(client, "tokenize", {})

    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["error"]["code"] == "invalid_arguments"
    assert payload["error"]["status_code"] == 400
    assert payload["error"]["details"] == [
        {"argument": "input", "problem": "missing required argument 'input'"}
    ]
