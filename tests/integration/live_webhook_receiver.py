from __future__ import annotations

import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextlib.contextmanager
def webhook_receiver(host: str = "127.0.0.1", path: str = "/webhook"):
    deliveries: list[dict[str, object]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(content_length)
            try:
                body = json.loads(payload)
            except Exception:
                body = {"raw": payload.decode("utf-8", errors="replace")}
            deliveries.append({"path": self.path, "body": body})
            encoded = json.dumps({"received": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        bound_host, port = server.server_address
        yield f"http://{bound_host}:{port}{path}", deliveries
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
