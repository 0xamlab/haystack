from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _json_dumps(payload: Any) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _stable_identifier(prefix: str, payload: Any) -> str:
    return f"{prefix}_{_hash_payload(payload)[:24]}"


def _coerce_scope_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    text = str(value).strip()
    try:
        return uuid.UUID(text)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, text)
