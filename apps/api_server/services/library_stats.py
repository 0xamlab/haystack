"""Counts from the sanitized runtime-library contract — the docs' source of truth.

The contract JSON ships in the repo at ``packages/algenta/algenta/`` and is copied
to the same relative path inside the API image, so one root-relative rule covers
dev, CI, and production. Counts only ever leave this module — never the surface.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_RELATIVE = Path("packages/algenta/algenta/runtime_library_contract.json")


class LibraryStatsUnavailableError(RuntimeError):
    """The bundled contract file is missing or unreadable."""


def _candidate_paths() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    roots = [parent for parent in here.parents]
    return tuple(root / _RELATIVE for root in roots)


@lru_cache(maxsize=1)
def library_stats() -> dict[str, int]:
    for path in _candidate_paths():
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LibraryStatsUnavailableError(f"unreadable contract at {path}") from exc
        modules = payload.get("modules")
        function_count = payload.get("function_count")
        module_count = payload.get("module_count")
        if (
            not isinstance(modules, list)
            or not isinstance(function_count, int)
            or not isinstance(module_count, int)
            or module_count != len(modules)
        ):
            raise LibraryStatsUnavailableError(f"inconsistent contract at {path}")
        return {
            "schema_version": int(payload.get("schema_version", 1)),
            "function_count": function_count,
            "module_count": module_count,
        }
    raise LibraryStatsUnavailableError("runtime_library_contract.json not found")
