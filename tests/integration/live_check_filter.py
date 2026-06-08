from __future__ import annotations

import os
from collections.abc import Sequence

LIVE_CHECK_FILTER_ENV = "ALGENTA_LIVE_CHECK_FILTER"


def selected_live_check_filter() -> str | None:
    raw_value = os.environ.get(LIVE_CHECK_FILTER_ENV, "")
    normalized = raw_value.strip()
    return normalized or None


def live_check_filter_tokens(active_filter: str | None = None) -> tuple[str, ...]:
    normalized_filter = (active_filter or selected_live_check_filter() or "").strip().lower()
    if not normalized_filter:
        return ()
    return tuple(token.strip() for token in normalized_filter.split(",") if token.strip())


def should_run_live_check(
    name: str,
    active_filter: str | Sequence[str] | None = None,
) -> bool:
    if isinstance(active_filter, str) or active_filter is None:
        tokens = live_check_filter_tokens(active_filter)
    else:
        tokens = tuple(token.strip().lower() for token in active_filter if token.strip())
    if not tokens:
        return True
    normalized_name = name.strip().lower()
    return any(token in normalized_name for token in tokens)


def filtered_live_check_reason(active_filter: str | None = None) -> str:
    normalized_filter = active_filter or selected_live_check_filter() or ""
    return f"filtered out by {LIVE_CHECK_FILTER_ENV}={normalized_filter}"


def filtered_minimum_passed(
    default_minimum_passed: int,
    active_filter: str | Sequence[str] | None = None,
) -> int:
    if not isinstance(default_minimum_passed, int) or isinstance(default_minimum_passed, bool):
        raise ValueError("default_minimum_passed must be an integer")
    if default_minimum_passed < 0:
        raise ValueError("default_minimum_passed must be >= 0")
    if isinstance(active_filter, str) or active_filter is None:
        tokens = live_check_filter_tokens(active_filter)
    else:
        tokens = tuple(token.strip().lower() for token in active_filter if token.strip())
    return 1 if tokens else default_minimum_passed
