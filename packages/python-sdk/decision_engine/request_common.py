from __future__ import annotations

from typing import Any


def _strip_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


__all__ = ["_strip_none"]
