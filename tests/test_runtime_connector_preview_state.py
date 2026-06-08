from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _preview_state_module():
    return importlib.import_module("algenta.runtime_connector_preview_state")


def _runtime_errors_module():
    return importlib.import_module("algenta.runtime_errors")


def test_consume_inline_preview_slot_prunes_stale_events_and_appends_now() -> None:
    consume_inline_preview_slot = _preview_state_module().consume_inline_preview_slot
    events = [10.0, 50.0]

    updated = consume_inline_preview_slot(events, now_monotonic=lambda: 100.0)

    assert updated == [50.0, 100.0]


def test_consume_inline_preview_slot_raises_structured_rate_limit_error() -> None:
    consume_inline_preview_slot = _preview_state_module().consume_inline_preview_slot
    runtime_validation_error = _runtime_errors_module().RuntimeValidationError
    events = [100.0] * 20

    with pytest.raises(runtime_validation_error) as exc_info:
        consume_inline_preview_slot(events, now_monotonic=lambda: 100.0)

    assert exc_info.value.code == "inline_preview_rate_limited"
    assert exc_info.value.details == {"limit": 20, "window_seconds": 60}


def test_inline_preview_cache_helpers_expire_entries_and_store_values() -> None:
    preview_state = _preview_state_module()
    get_inline_preview_cache = preview_state.get_inline_preview_cache
    put_inline_preview_cache = preview_state.put_inline_preview_cache
    cache = {"stale": (10.0, "expired")}

    assert get_inline_preview_cache(cache, "stale", now_monotonic=lambda: 11.0) is None
    assert cache == {}

    stored = put_inline_preview_cache(
        cache,
        "fresh",
        {"status": "ok"},
        now_monotonic=lambda: 100.0,
    )

    assert stored == {"status": "ok"}
    assert cache["fresh"][0] == 105.0
    assert get_inline_preview_cache(cache, "fresh", now_monotonic=lambda: 101.0) == {"status": "ok"}


def test_inline_preview_capability_helpers_expire_entries_and_store_flags() -> None:
    preview_state = _preview_state_module()
    get_inline_preview_capability = preview_state.get_inline_preview_capability
    put_inline_preview_capability = preview_state.put_inline_preview_capability
    capabilities = {"browse": (10.0, False)}

    assert (
        get_inline_preview_capability(
            capabilities,
            operation="browse",
            now_monotonic=lambda: 11.0,
        )
        is None
    )
    assert capabilities == {}

    put_inline_preview_capability(
        capabilities,
        operation="browse",
        supported=False,
        now_monotonic=lambda: 20.0,
    )

    assert capabilities["browse"][0] == 80.0
    assert (
        get_inline_preview_capability(
            capabilities,
            operation="browse",
            now_monotonic=lambda: 21.0,
        )
        is False
    )
