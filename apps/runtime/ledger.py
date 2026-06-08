"""Append-only local runtime ledger for offline auditability."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def ledger_path() -> Path:
    runtime_dir = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
    return runtime_dir / "history.jsonl"


def append_event(
    *,
    task_id: str,
    surface: str,
    action: str,
    status: str,
    target: str,
    request_id: str = "",
    engine_used: str = "",
    latency_ms: float | None = None,
    success: bool | None = None,
    error: str = "",
    sync_state: str = "local_only",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "task_id": task_id,
        "surface": surface,
        "action": action,
        "status": status,
        "target": target,
        "request_id": request_id or None,
        "engine_used": engine_used or None,
        "latency_ms": latency_ms,
        "success": success,
        "error": error or None,
        "sync_state": sync_state,
        "details": details or {},
        "timestamp": time.time(),
    }
    path = ledger_path()
    line = json.dumps(event, sort_keys=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError:
        # Ledger failures must never break execution paths.
        event["sync_state"] = "write_failed"
    return event
