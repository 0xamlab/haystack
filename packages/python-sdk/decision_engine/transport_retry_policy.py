# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

DEFAULT_RETRY_AFTER_SECONDS = 60
INLINE_PREVIEW_RATE_LIMIT_ERROR = "inline_preview_rate_limited"
RATE_LIMIT_BACKOFF_BASE_SECONDS = 5
SERVER_ERROR_BACKOFF_BASE_SECONDS = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_retry_after_header(
    value: str | None,
    *,
    default_seconds: int = DEFAULT_RETRY_AFTER_SECONDS,
) -> int:
    if value is None:
        return default_seconds
    stripped = value.strip()
    if not stripped:
        return default_seconds
    try:
        return max(int(stripped), 0)
    except ValueError:
        pass
    try:
        retry_after_at = parsedate_to_datetime(stripped)
    except (TypeError, ValueError, IndexError, OverflowError):
        return default_seconds
    if retry_after_at.tzinfo is None:
        retry_after_at = retry_after_at.replace(tzinfo=UTC)
    return max(math.ceil((retry_after_at - utc_now()).total_seconds()), 0)


def should_retry_rate_limit(error_code: str | None) -> bool:
    return error_code != INLINE_PREVIEW_RATE_LIMIT_ERROR


def rate_limit_backoff_seconds(retry_after: int | None, *, attempt: int) -> float:
    if retry_after is not None and retry_after > 0:
        return float(retry_after)
    return float((2**attempt) * RATE_LIMIT_BACKOFF_BASE_SECONDS)


def server_error_backoff_seconds(*, attempt: int) -> float:
    return float((2**attempt) * SERVER_ERROR_BACKOFF_BASE_SECONDS)


__all__ = [
    "DEFAULT_RETRY_AFTER_SECONDS",
    "INLINE_PREVIEW_RATE_LIMIT_ERROR",
    "parse_retry_after_header",
    "rate_limit_backoff_seconds",
    "server_error_backoff_seconds",
    "should_retry_rate_limit",
    "utc_now",
]
