# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

DEVICE_BINDING_TOKEN_HEADER = "X-Algenta-Device-Binding-Token"  # noqa: S105
_BINDING_STORE_FILENAME = "hosted_device_binding_tokens.json"
_STORE_LOCK = threading.Lock()
_MEMORY_STORE: dict[str, str] = {}


def _runtime_dir() -> Path:
    configured = os.environ.get("ALGENTA_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path.home() / ".algenta" / "runtime"


def _binding_store_path() -> Path:
    return _runtime_dir() / _BINDING_STORE_FILENAME


def _binding_store_key(base_url: str, api_key: str, device_id: str) -> str:
    normalized = f"{base_url.rstrip('/')}|{api_key}|{device_id}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _read_store() -> dict[str, str]:
    path = _binding_store_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if isinstance(value, str)}


def _write_store(payload: dict[str, str]) -> None:
    path = _binding_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temp_path.chmod(0o600)
    temp_path.replace(path)
    path.chmod(0o600)


def load_device_binding_token(*, base_url: str, api_key: str, device_id: str) -> str | None:
    key = _binding_store_key(base_url, api_key, device_id)
    with _STORE_LOCK:
        cached = _MEMORY_STORE.get(key)
        if cached:
            return cached
        stored = _read_store().get(key)
        if stored:
            _MEMORY_STORE[key] = stored
        return stored


def store_device_binding_token(
    *,
    base_url: str,
    api_key: str,
    device_id: str,
    binding_token: str,
) -> None:
    token = binding_token.strip()
    if not token:
        return
    key = _binding_store_key(base_url, api_key, device_id)
    with _STORE_LOCK:
        _MEMORY_STORE[key] = token
        payload = _read_store()
        payload[key] = token
        try:
            _write_store(payload)
        except OSError:
            return


__all__ = [
    "DEVICE_BINDING_TOKEN_HEADER",
    "load_device_binding_token",
    "store_device_binding_token",
]
