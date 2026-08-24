"""A tiny real HTTP server standing in for the customer's downstream webhook endpoint.

This is the genuinely-external boundary that ``execute_decision`` posts to (a customer-owned
URL) — the same boundary tests/test_decisions_api.py already stubs (there, by monkeypatching
``async_http_request``; here, by actually listening on loopback so the real
``async_http_request`` call in apps/api_server/routers/decisions.py really goes over the wire).
Not a test module itself — imported by the new A3 test files.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {"_raw": raw.decode("utf-8", "replace")}
        received: list[dict[str, Any]] = self.server.received  # type: ignore[attr-defined]
        received.append({"path": self.path, "payload": payload})
        body = json.dumps({"received": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return  # keep test output quiet


@contextlib.contextmanager
def webhook_receiver() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Start a real loopback HTTP server. Yields (webhook_url, received_list)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    received: list[dict[str, Any]] = []
    server.received = received  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}/hook", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
