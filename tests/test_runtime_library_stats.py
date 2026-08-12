"""Public runtime library-stats route (apps/api_server/routers/meta.py).

Counts only, no auth: algenta.ai renders its catalog counters from this route,
fail-soft to pinned values. The counts must match the repo's contract exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.main import app
from tests._asgi_client import SyncASGIClient

_CONTRACT = Path(__file__).resolve().parents[1] / "packages/algenta/algenta/runtime_library_contract.json"


def test_library_stats_public_and_exact() -> None:
    expected = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    with SyncASGIClient(app) as client:
        response = client.get("/v1/runtime/library-stats")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["module_count"] == expected["module_count"] == len(expected["modules"])
    assert body["function_count"] == expected["function_count"]
    # The catalog only grows — a shrink means a broken contract shipped.
    assert body["function_count"] >= 6065
    assert body["module_count"] >= 643
