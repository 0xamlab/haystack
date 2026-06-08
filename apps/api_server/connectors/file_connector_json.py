"""JSON parsing and flattening helpers for the file connector."""

from __future__ import annotations

import json
from typing import Any


def parse_json_records(content: str, *, path: str = "") -> list[dict[str, Any]]:
    try:
        data: Any = json.loads(content.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if path:
        for key in path.split("."):
            if isinstance(data, dict):
                data = data.get(key, [])
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]

    if isinstance(data, dict):
        for key in ("data", "records", "rows", "results", "items", "value"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        return []
    return [flatten_dict(record) for record in data if isinstance(record, dict)]


def flatten_dict(
    obj: dict[str, Any],
    prefix: str = "",
    sep: str = ".",
    max_depth: int = 5,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    _flatten_into(obj, prefix, sep, max_depth, 0, result)
    return result


def _flatten_into(
    obj: Any,
    prefix: str,
    sep: str,
    max_depth: int,
    depth: int,
    out: dict[str, Any],
) -> None:
    if depth >= max_depth or not isinstance(obj, dict):
        out[prefix] = obj
        return

    for key, value in obj.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict) and depth < max_depth - 1:
            _flatten_into(value, full_key, sep, max_depth, depth + 1, out)
            continue
        if isinstance(value, list):
            out[full_key] = json.dumps(value) if len(value) <= 20 else f"[{len(value)} items]"
            continue
        out[full_key] = value
