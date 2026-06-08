from __future__ import annotations

import contextlib
import json
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


def default_refreshable_dataset_payload() -> dict[str, object]:
    return {
        "items": [
            {"customer_id": "A", "amount": 10.0, "status": "completed"},
            {"customer_id": "B", "amount": 20.0, "status": "completed"},
        ]
    }


@contextlib.contextmanager
def static_json_server(payload: dict[str, Any]) -> Iterator[str]:
    """Serve a deterministic JSON payload from a temporary local HTTP server."""
    temp_dir = Path(tempfile.mkdtemp(prefix="algenta-live-rest-"))
    payload_path = temp_dir / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    handler = partial(SimpleHTTPRequestHandler, directory=str(temp_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        yield f"http://127.0.0.1:{port}/payload.json"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
