from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTTP_SSE_TRANSPORT = ROOT / "apps" / "mcp_server" / "transports" / "http_sse.py"


def test_standalone_mcp_http_transport_uses_canonical_routes_with_legacy_aliases() -> None:
    text = HTTP_SSE_TRANSPORT.read_text(encoding="utf-8")

    assert "StreamableHTTPSessionManager" in text
    assert "_StreamableHTTPASGIApp" in text
    assert "_CallableASGIApp" in text
    assert "json_response=True" in text
    assert "stateless=True" in text
    assert 'messages_path="/mcp/messages"' in text
    assert 'messages_path="/messages"' in text
    assert 'Route("/mcp/tools", endpoint=handle_tools)' in text
    assert 'Route("/tools", endpoint=handle_tools)' in text
    assert 'router.add_route(\n        "/mcp/sse"' in text
    assert 'router.add_route(\n        "/mcp/messages"' in text

    # Auth posture, wired per mount — the whole point of the earlier asymmetry was that ONE mount had
    # the challenge and the others did not, so the wiring is asserted mount by mount.
    # Streamable /mcp: discovery open, tools/call challenged (standalone app + embedded router alike).
    assert 'Route("/mcp", endpoint=_MCPToolCallAuthChallengeASGIApp(streamable_http))' in text
    # Deprecated HTTP+SSE pair: a key on every request, both at the canonical paths and the aliases.
    assert 'Mount("/mcp/sse", app=_MCPLegacyTransportAuthASGIApp(canonical_sse))' in text
    assert 'Mount("/mcp/messages", app=_MCPLegacyTransportAuthASGIApp(canonical_messages))' in text
    assert 'Mount("/sse", app=_MCPLegacyTransportAuthASGIApp(legacy_sse))' in text
    assert 'Mount("/messages", app=_MCPLegacyTransportAuthASGIApp(legacy_messages))' in text
    assert "_MCPLegacyTransportAuthASGIApp(_CallableASGIApp(sse_endpoint_app))" in text
    assert "_MCPLegacyTransportAuthASGIApp(_CallableASGIApp(post_message_endpoint_app))" in text
