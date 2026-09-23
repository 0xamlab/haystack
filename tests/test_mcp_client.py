from __future__ import annotations

import importlib
import json

import httpx
import pytest

from apps.mcp_server import client as mcp_client
from apps.mcp_server.errors import (
    MCPAPIError,
    MCPPrivacyConfigurationError,
    MCPUpstreamUnavailableError,
    UnknownToolError,
    UnsupportedMCPAuthConfigurationError,
    serialize_tool_error,
)
from apps.platform_contract_constants import API_BASE_URL


def test_request_overrides_supply_api_key_and_base_url(monkeypatch):
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with pytest.raises(UnsupportedMCPAuthConfigurationError) as excinfo:
        mcp_client._headers()
    message = str(excinfo.value)
    assert "ALGENTA_API_KEY is not set" in message
    assert "free community login" in message
    assert "algenta login" in message

    with mcp_client.request_overrides(
        api_key="de_test_override",
        base_url="http://127.0.0.1:8000",
    ):
        headers = mcp_client._headers()
        assert headers["Authorization"] == "Bearer de_test_override"
        assert mcp_client._resolve_base_url() == "http://127.0.0.1:8000"


def test_request_overrides_do_not_leak_state(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_env")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://env.local")

    with mcp_client.request_overrides(
        api_key="de_test_override",
        base_url="http://override.local",
    ):
        assert mcp_client._headers()["Authorization"] == "Bearer de_test_override"
        assert mcp_client._resolve_base_url() == "http://override.local"

    assert mcp_client._headers()["Authorization"] == "Bearer de_test_env"
    assert mcp_client._resolve_base_url() == "http://env.local"


def test_private_profile_requires_self_hosted_mcp_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setattr(mcp_client.config, "BASE_URL", API_BASE_URL)

    with pytest.raises(MCPPrivacyConfigurationError, match="cannot target Algenta-owned"):
        mcp_client._resolve_base_url()


def test_private_profile_allows_explicit_self_hosted_mcp_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    assert mcp_client._resolve_base_url() == "http://localhost:8000"


def test_private_profile_allows_legacy_self_hosted_mcp_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.setenv("DE_BASE_URL", "http://localhost:8001")

    assert mcp_client._resolve_base_url() == "http://localhost:8001"


def test_private_profile_allows_algenta_api_url_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8002")

    assert mcp_client._resolve_base_url() == "http://localhost:8002"


def test_headers_accept_legacy_api_key_env(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setenv("DE_API_KEY", "de_test_legacy")

    assert mcp_client._headers()["Authorization"] == "Bearer de_test_legacy"


def test_private_profile_rejects_request_override_to_algenta_cloud(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")

    with mcp_client.request_overrides(base_url="https://api.algenta.ai"):
        with pytest.raises(MCPPrivacyConfigurationError, match="cannot target Algenta-owned"):
            mcp_client._resolve_base_url()


def test_private_profile_base_url_error_mentions_legacy_env(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.setattr(mcp_client.config, "BASE_URL", API_BASE_URL)

    with pytest.raises(MCPPrivacyConfigurationError) as excinfo:
        mcp_client._resolve_base_url()
    assert "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL" in str(excinfo.value)


def test_mcp_config_private_profile_defaults_blank_base_url() -> None:
    import apps.mcp_server.config as mcp_config

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)

        reloaded = importlib.reload(mcp_config)
        assert reloaded.BASE_URL == ""

    importlib.reload(mcp_config)


def test_mcp_config_tracks_current_environment_without_reload(monkeypatch) -> None:
    import apps.mcp_server.config as mcp_config

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.delenv("ALGENTA_MCP_HOST", raising=False)
    assert mcp_config.BASE_URL == API_BASE_URL
    assert mcp_config.HOST == "127.0.0.1"

    monkeypatch.setenv("ALGENTA_MCP_HOST", "0.0.0.0")
    assert mcp_config.HOST == "0.0.0.0"

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")
    assert mcp_config.BASE_URL == ""

    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    assert mcp_config.BASE_URL == "http://localhost:8000"

    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.setenv("DE_BASE_URL", "http://localhost:8001")
    assert mcp_config.BASE_URL == "http://localhost:8001"

    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8002")
    assert mcp_config.BASE_URL == "http://localhost:8002"


@pytest.mark.anyio
async def test_api_maps_transport_error_to_upstream_unavailable() -> None:
    class _BrokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("boom", request=request)

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _BrokenClient  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            with pytest.raises(MCPUpstreamUnavailableError, match="unavailable"):
                await mcp_client.api("GET", "/v1/health")
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]


@pytest.mark.anyio
async def test_api_uses_explicit_timeout_override() -> None:
    seen: dict[str, object] = {}

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            seen["timeout"] = kwargs["timeout"]
            seen["headers"] = kwargs["headers"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _Client  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            response = await mcp_client.api("GET", "/v1/health", timeout=123.0)
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]

    assert response == {"ok": True}
    assert seen["timeout"] == 123.0


@pytest.mark.anyio
async def test_api_with_status_preserves_structured_upstream_503_payload() -> None:
    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            return httpx.Response(
                503,
                json={
                    "error": {
                        "code": "repository_model_unavailable",
                        "message": "Repository planner model is not configured.",
                        "details": [],
                    }
                },
                request=httpx.Request("POST", url),
            )

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _Client  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            status_code, payload = await mcp_client.api_with_status(
                "POST",
                "/v1/repositories/repo_123/decision-plans",
            )
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]

    assert status_code == 503
    assert payload["error"]["code"] == "repository_model_unavailable"


@pytest.mark.anyio
async def test_api_raises_typed_mcp_api_error_for_structured_http_errors() -> None:
    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            return httpx.Response(
                503,
                json={
                    "error": {
                        "code": "repository_model_unavailable",
                        "message": "Repository planner model is not configured.",
                        "details": [],
                    }
                },
                request=httpx.Request("POST", url),
            )

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _Client  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            with pytest.raises(MCPAPIError) as excinfo:
                await mcp_client.api("POST", "/v1/repositories/repo_123/decision-plans")
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]

    assert excinfo.value.error_code == "repository_model_unavailable"
    assert excinfo.value.status_code == 503
    assert '"repository_model_unavailable"' in str(excinfo.value)
    serialized = serialize_tool_error(excinfo.value, tool_name="create_repository_decision_plan")
    assert '"repository_model_unavailable"' in serialized
    assert '"status_code": 503' in serialized


@pytest.mark.anyio
async def test_api_with_status_maps_unstructured_500_to_upstream_unavailable() -> None:
    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            return httpx.Response(
                500,
                text="Internal Server Error",
                request=httpx.Request("GET", url),
            )

    original = mcp_client.httpx.AsyncClient
    mcp_client.httpx.AsyncClient = _Client  # type: ignore[assignment]
    try:
        with mcp_client.request_overrides(
            api_key="de_test_override",
            base_url="http://127.0.0.1:8000",
        ):
            with pytest.raises(MCPUpstreamUnavailableError, match="temporary upstream failure"):
                await mcp_client.api_with_status("GET", "/v1/health")
    finally:
        mcp_client.httpx.AsyncClient = original  # type: ignore[assignment]


def test_serialize_tool_error_returns_contract_payloads() -> None:
    auth_error = UnsupportedMCPAuthConfigurationError("missing auth")
    upstream_error = MCPUpstreamUnavailableError("temporary outage")
    api_error = MCPAPIError(
        error_code="repository_model_unavailable",
        message=(
            'API error 503: {"error":{"code":"repository_model_unavailable",'
            '"message":"Repository planner model is not configured.","details":[]}}'
        ),
        status_code=503,
        details=[],
    )

    assert "unsupported_mcp_auth_configuration" in serialize_tool_error(
        auth_error, tool_name="simulate"
    )
    assert "mcp_upstream_unavailable" in serialize_tool_error(upstream_error, tool_name="simulate")
    assert "repository_model_unavailable" in serialize_tool_error(
        api_error, tool_name="create_repository_decision_plan"
    )
    # Only a genuine dispatch miss (UnknownToolError, raised by registry.call_tool) serializes
    # as unknown_tool/404. A bare KeyError escaping a handler is an internal failure and now
    # falls through to tool_error/500 — the 1.0.28 contract killed the old bare-KeyError →
    # unknown_tool mapping, which had misreported missing-argument handler crashes as 404s.
    unknown_payload = json.loads(serialize_tool_error(UnknownToolError("nope"), tool_name="nope"))
    assert unknown_payload["error"]["code"] == "unknown_tool"
    assert unknown_payload["error"]["status_code"] == 404
    assert unknown_payload["error"]["message"] == "Unknown tool: nope"
    bare_payload = json.loads(serialize_tool_error(KeyError("nope"), tool_name="nope"))
    assert bare_payload["error"]["code"] == "tool_error"
    assert bare_payload["error"]["status_code"] == 500


def test_api_error_message_redacts_key_material() -> None:
    # An upstream that reflects the request (or mints a key into a 4xx body) must never turn
    # our error message — logged and returned to the MCP client — into a credential leak.
    payload = {
        "error": {
            "code": "invalid_api_key",
            "message": "key de_live_abc123XYZ789 is not valid for Bearer de_test_DEF456ghi012",
        }
    }
    exc = mcp_client._api_error_from_status_payload(401, payload)
    message = str(exc)
    assert "de_live_abc123XYZ789" not in message
    assert "de_test_DEF456ghi012" not in message
    assert message.count("[redacted]") == 2
    # The structured payload is preserved verbatim for programmatic handling; only the
    # human/log-facing message string is scrubbed.
    assert exc.payload is payload
    assert exc.error_code == "invalid_api_key"
