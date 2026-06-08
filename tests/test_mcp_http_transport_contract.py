from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTTP_SSE_TRANSPORT = ROOT / "apps" / "mcp_server" / "transports" / "http_sse.py"


def test_standalone_mcp_http_transport_uses_canonical_routes_with_legacy_aliases() -> None:
    text = HTTP_SSE_TRANSPORT.read_text(encoding="utf-8")

    assert 'canonical_sse, canonical_messages = _build_transport_endpoints(messages_path="/mcp/messages")' in text
    assert 'legacy_sse, legacy_messages = _build_transport_endpoints(messages_path="/messages")' in text
    assert 'Route("/mcp/tools", endpoint=handle_tools)' in text
    assert 'Mount("/mcp/sse", app=canonical_sse)' in text
    assert 'Mount("/mcp/messages", app=canonical_messages)' in text
    assert 'Route("/tools", endpoint=handle_tools)' in text
    assert 'Mount("/sse", app=legacy_sse)' in text
    assert 'Mount("/messages", app=legacy_messages)' in text
