from __future__ import annotations

import builtins
from typing import Any

from fastapi import FastAPI

from apps.mcp_server.server import create_fastapi_router
from tests._asgi_client import SyncASGIClient


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
    assert "/mcp/sse" in openapi["paths"]
    assert "/mcp/messages" in openapi["paths"]
    assert openapi["paths"]["/mcp/tools"]["get"].get("security") is None
    assert openapi["paths"]["/mcp/sse"]["get"].get("security") is None
    assert openapi["paths"]["/mcp/messages"]["post"].get("security") is None
    assert "200" in openapi["paths"]["/mcp/tools"]["get"]["responses"]
    assert "503" in openapi["paths"]["/mcp/sse"]["get"]["responses"]
    assert "503" in openapi["paths"]["/mcp/messages"]["post"]["responses"]
    assert "200" not in openapi["paths"]["/mcp/sse"]["get"]["responses"]
    assert "200" not in openapi["paths"]["/mcp/messages"]["post"]["responses"]
    assert (
        openapi["paths"]["/mcp/sse"]["get"]["responses"]["503"]["description"]
        == "MCP SSE transport unavailable in this environment."
    )
    assert (
        openapi["paths"]["/mcp/messages"]["post"]["responses"]["503"]["description"]
        == "MCP message transport unavailable in this environment."
    )
