from __future__ import annotations

from functools import lru_cache
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


def _stable_identifier_cache_key(payload: Any) -> Any:
    if payload is None or isinstance(payload, bool | int | float | str):
        return payload
    if isinstance(payload, tuple):
        return ("tuple", tuple(_stable_identifier_cache_key(item) for item in payload))
    if isinstance(payload, list):
        return ("list", tuple(_stable_identifier_cache_key(item) for item in payload))
    if isinstance(payload, dict):
        return (
            "dict",
            tuple(
                (
                    str(key),
                    _stable_identifier_cache_key(value),
                )
                for key, value in sorted(payload.items(), key=lambda item: str(item[0]))
            ),
        )
    if isinstance(payload, set | frozenset):
        normalized_items = tuple(_stable_identifier_cache_key(item) for item in payload)
        return ("set", tuple(sorted(normalized_items, key=repr)))
    return ("str", str(payload))


@lru_cache(maxsize=32768)
def _payload_ascii_for_cache_key(cache_key: Any) -> str:
    # The cache key normalization above reduces inputs to tuples, strings, and
    # scalar primitives. `ascii(...)` keeps the encoding deterministic while
    # avoiding the JSON encoder overhead visible in steady-state repo profiles.
    return ascii(cache_key)


@lru_cache(maxsize=32768)
def _payload_digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


@lru_cache(maxsize=32768)
def _stable_identifier_from_json(prefix: str, payload_json: str) -> str:
    return f"{prefix}_{_payload_digest(payload_json)[:24]}"


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _stable_identifier(prefix: str, payload: Any) -> str:
    return _stable_identifier_from_json(
        prefix,
        _payload_ascii_for_cache_key(_stable_identifier_cache_key(payload)),
    )


def _coerce_scope_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    text = str(value).strip()
    try:
        return uuid.UUID(text)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, text)
