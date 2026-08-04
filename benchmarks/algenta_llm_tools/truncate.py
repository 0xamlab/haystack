"""Model-context shaping for tool results.

Mirrors the truncation discipline sqai's AI-SDK tools already ship
(``/Users/angel/Developer/sqai/packages/ai-sdk/src/truncate.ts``), reimplemented here
in plain Python with no dependency on that package: what the model sees is a small,
labeled projection of a real result; the full, untruncated result is kept in-process
and is retrievable by ``result_id`` via ``get_stored_result`` -- nothing is discarded,
it is just not dumped wholesale into the model's context. Truncation is always
declared on the returned dict (``truncated: bool``), never silent.

Element-preview budget (``MAX_ELEMENTS_TO_MODEL``/``MAX_ELEMENT_BYTES_TO_MODEL``) is
deliberately tiny -- a handful of values, not hundreds. Every tool that returns a raw
array (``get_column``, ``get_columns``, a vector-shaped ``execute`` result) already
hands back a ``result_id``/``result_ids`` the model is instructed to pipe straight
into ``execute()`` for any real computation (see ``tools.py``'s ``_resolve_result_refs``
and the ``GET_COLUMN_SCHEMA``/``EXECUTE_SCHEMA`` descriptions) -- the model never
computes a statistic by eyeballing the preview, so a large preview is pure token cost
with no compute benefit. A prior version previewed up to 500 elements / 32KB per call;
across a growing multi-turn tool-calling conversation (the full message history is
resent on every turn) that repeated, mostly-unread blob was the dominant contributor
to the uplift benchmark's measured ~6.5K prompt tokens/call. Row-shaped (tabular)
results keep a larger budget (25 rows / 250 cells) since a model plausibly does read a
handful of real rows to sanity-check shape/values before aggregating.

The in-process store below is intentionally a plain dict with no eviction: this is a
minimal wrapper for local tool-calling in one process, not a multi-tenant service. A
production deployment would swap this for a bounded/expiring store without touching
``tools.py``.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

MAX_ROWS_TO_MODEL = 25
MAX_CELLS_TO_MODEL = 250
MAX_ELEMENTS_TO_MODEL = 20
MAX_ELEMENT_BYTES_TO_MODEL = 3_000
MAX_BYTES_TO_MODEL = 32_000

_RESULTS: dict[str, Any] = {}


def store_result(value: Any) -> str:
    """Keep the full, untruncated value; return a short id that retrieves it later."""
    result_id = uuid.uuid4().hex[:12]
    _RESULTS[result_id] = value
    return result_id


def get_stored_result(result_id: str) -> Any:
    """The full value a prior tool call stored, by the id it returned."""
    if result_id not in _RESULTS:
        raise KeyError(f"No stored result for id {result_id!r} (unknown or expired).")
    return _RESULTS[result_id]


def _byte_len(value: Any) -> int:
    return len(json.dumps(value, default=str).encode("utf-8"))


def shape_for_model(value: Any) -> dict[str, Any]:
    """Shape one kernel result for the model's context window.

    Scalars (including ``None``) pass through unchanged. A list of dicts (row-shaped
    results) is shaped rows-first, then cells, exactly like the sqai TypeScript
    reference: whole rows are dropped until the cell budget fits, never a partial row.
    A list of scalars (vector/array results) is shaped as a leading preview, halved
    until it fits the byte budget. A plain dict passes through if it fits the byte
    budget, and is dropped (declared truncated) otherwise. Everything else is
    stringified rather than guessed at.
    """
    if value is None or isinstance(value, bool | int | float | str):
        return {"value": value, "truncated": False}

    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            return _shape_rows(value)
        return _shape_elements(value)

    if isinstance(value, dict):
        if _byte_len(value) <= MAX_BYTES_TO_MODEL:
            return {"value": value, "truncated": False}
        return {"value": None, "truncated": True}

    text = str(value)
    if len(text.encode("utf-8")) <= MAX_BYTES_TO_MODEL:
        return {"value": text, "truncated": False}
    return {"value": None, "truncated": True}


def _shape_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    columns = list(rows[0].keys())
    keep = min(total, MAX_ROWS_TO_MODEL)
    cells_per_row = max(1, len(columns))
    if keep * cells_per_row > MAX_CELLS_TO_MODEL:
        keep = max(0, MAX_CELLS_TO_MODEL // cells_per_row)
    return {
        "value": {"columns": columns, "rows": rows[:keep]},
        "element_count": total,
        "truncated": keep < total,
    }


def _shape_elements(values: list[Any]) -> dict[str, Any]:
    total = len(values)
    preview = values[: min(total, MAX_ELEMENTS_TO_MODEL)]
    while preview and _byte_len(preview) > MAX_ELEMENT_BYTES_TO_MODEL:
        preview = preview[: len(preview) // 2]
    return {
        "value": preview,
        "element_count": total,
        "truncated": len(preview) < total,
    }
