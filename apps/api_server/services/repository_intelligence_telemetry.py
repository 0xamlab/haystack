"""Lightweight, always-on telemetry for the repository-intelligence pipeline.

AR-OPT-0 baseline: measured spans + token/counter capture so every later
optimization (parsing parallelism, prompt caching, slim manifests, semantic
retrieval, incremental graph) can *prove* its impact against `scripts/
g0_token_benchmark.py` and a CI telemetry-presence gate.

Design: contextvar-scoped (async-safe). A top-level pipeline entrypoint opens a
`collect()` scope; instrumented call sites anywhere beneath it record into it via
`span()` / `record()` / `record_tokens()`. Outside a scope every call is a cheap
no-op, so instrumentation is safe to sprinkle freely. Spans accumulate (additive)
so repeated work — e.g. per-adapter parse time — sums into one field.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_collector: ContextVar[dict[str, Any] | None] = ContextVar(
    "repository_intelligence_telemetry", default=None
)

# Span fields the AR-OPT-0 CI gate expects the snapshot pipeline to populate.
SNAPSHOT_SPANS = (
    "snapshot_parse_ms",
    "graph_build_ms",
    "parquet_write_ms",
    "tar_write_ms",
    "manifest_write_ms",
)
TRIAGE_SPANS = ("triage_rank_ms",)
TOKEN_FIELDS = (
    "llm_input_tokens_uncached",
    "llm_input_tokens_cached_read",
    "llm_input_tokens_cached_write",
    "llm_output_tokens",
)


@contextmanager
def collect() -> Iterator[dict[str, Any]]:
    """Open a fresh telemetry scope; yields the dict that accumulates spans/counters/events."""
    data: dict[str, Any] = {"spans_ms": {}, "counters": {}, "events": []}
    token = _collector.set(data)
    try:
        yield data
    finally:
        _collector.reset(token)


def current() -> dict[str, Any] | None:
    """The active telemetry dict, or None outside a `collect()` scope."""
    return _collector.get()


def record_span_ms(name: str, elapsed_ms: float) -> None:
    """Add a pre-measured duration to ``spans_ms[name]`` (additive). No-op outside a scope.

    Use when wrapping a large block in :func:`span` would force an unwieldy re-indent:
    bookend the block with ``time.perf_counter()`` and record the delta here instead.
    """
    data = _collector.get()
    if data is not None:
        spans = data["spans_ms"]
        spans[name] = round(spans.get(name, 0.0) + elapsed_ms, 3)


@contextmanager
def span(name: str) -> Iterator[None]:
    """Time a block into ``spans_ms[name]`` (additive). No-op outside a scope."""
    start = time.perf_counter()
    try:
        yield
    finally:
        record_span_ms(name, (time.perf_counter() - start) * 1000.0)


def record(field: str, value: float | int) -> None:
    """Add ``value`` to ``counters[field]`` (additive). No-op outside a scope."""
    data = _collector.get()
    if data is not None:
        counters = data["counters"]
        counters[field] = counters.get(field, 0) + value


def emit(name: str, payload: dict[str, Any]) -> None:
    """Append a structured event (e.g. a shadow routing decision) to ``events``.

    No-op outside a scope. Used for observe-only signals that feed offline
    calibration rather than per-call counters/spans.
    """
    data = _collector.get()
    if data is not None:
        data.setdefault("events", []).append({"name": name, "payload": payload})


def record_tokens(
    *,
    input_uncached: int = 0,
    input_cached_read: int = 0,
    input_cached_write: int = 0,
    output: int = 0,
) -> None:
    """Record one LLM call's token usage (cached/uncached split) into counters."""
    record("llm_input_tokens_uncached", input_uncached)
    record("llm_input_tokens_cached_read", input_cached_read)
    record("llm_input_tokens_cached_write", input_cached_write)
    record("llm_output_tokens", output)


def missing_fields(data: dict[str, Any], required: tuple[str, ...], *, kind: str) -> list[str]:
    """Return required span/counter fields absent from a collected telemetry dict.

    ``kind`` is ``"spans_ms"`` or ``"counters"``. Used by the CI presence gate so a
    future change can't silently drop instrumentation.
    """
    present = data.get(kind, {})
    return [f for f in required if f not in present]
