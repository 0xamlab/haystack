from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import httpx

FailureType = Literal[
    "auth",
    "permission",
    "not_found",
    "rate_limit",
    "timeout",
    "invalid_config",
    "invalid_identifier",
    "unknown",
]


@dataclass(frozen=True)
class ConnectorTestOutcome:
    success: bool
    message: str
    latency_ms: int | None
    status: Literal["live", "error"]
    error_type: FailureType | None
    recoverable: bool | None


def elapsed_ms(started_at: float) -> int:
    return max(int((time.perf_counter() - started_at) * 1000), 0)


def classify_connector_failure(
    *,
    message: str,
    exception: BaseException | None = None,
    status_code: int | None = None,
) -> tuple[FailureType, bool]:
    exception_message = str(exception) if exception is not None else ""
    lower = f"{message}\n{exception_message}".lower()
    exc_name = type(exception).__name__.lower() if exception is not None else ""

    if status_code == 401:
        return "auth", True
    if status_code == 403:
        return "permission", True
    if status_code == 400:
        return "invalid_identifier", True
    if status_code == 404:
        return "not_found", True
    if status_code == 408:
        return "timeout", True
    if status_code == 409:
        return "invalid_identifier", True
    if status_code == 422:
        return "invalid_config", True
    if status_code == 429:
        return "rate_limit", True
    if status_code is not None and 400 <= status_code < 500:
        return "invalid_config", True

    if isinstance(exception, TimeoutError | httpx.TimeoutException):
        return "timeout", True
    if isinstance(exception, FileNotFoundError):
        return "not_found", True
    if isinstance(exception, PermissionError):
        return "permission", True
    if "egress_policy_denied" in lower or ("egress blocked" in lower and "privacy policy" in lower):
        return "permission", True

    if 'role "' in lower and "does not exist" in lower:
        return "auth", True

    auth_markers = (
        "unauthorized",
        "authentication failed",
        "authentication required",
        "incorrect username or password",
        "invalid username-password pair",
        "invalid username/password",
        "logon denied",
        "ora-01017",
        "invalid api key",
        "invalid access token",
        "invalid token",
        "password authentication failed",
        "login failed",
        "wrongpass",
        "noauth",
        "access token",
        "api key",
        "credentials",
        "permission denied for relation",
    )
    if any(marker in lower for marker in auth_markers):
        return "auth", True

    permission_markers = (
        "forbidden",
        "permission denied",
        "insufficient privilege",
        "access denied",
        "not authorized",
        "network policy",
        "warehouse usage",
        "warehouse access",
        "not accessible for current role",
    )
    if any(marker in lower for marker in permission_markers):
        return "permission", True

    rate_limit_markers = ("rate limit", "too many requests", "429")
    if any(marker in lower for marker in rate_limit_markers):
        return "rate_limit", True

    timeout_markers = (
        "timed out",
        "timeout",
        "connection refused",
        "connection reset",
        "unreachable",
        "connect error",
        "could not connect",
    )
    if any(marker in lower for marker in timeout_markers):
        return "timeout", True

    invalid_identifier_markers = (
        "relation does not exist",
        "table does not exist",
        "schema does not exist",
        "dataset does not exist",
        "unknown database",
        "unknown table",
        "unknown schema",
        "unknown dataset",
        "unknown relation",
        "no such table",
        "invalid identifier",
        "unsupported version",
    )
    if any(marker in lower for marker in invalid_identifier_markers):
        return "invalid_identifier", True

    not_found_markers = (
        "not found",
        "no such key",
        "nosuchkey",
        "resource not found",
        "blob not found",
        "blobnotfound",
        "bucket does not exist",
        "404",
    )
    if any(marker in lower for marker in not_found_markers) or "notfound" in exc_name:
        return "not_found", True

    invalid_config_markers = (
        "requires",
        "missing",
        "invalid config",
        "invalid connection string",
        "invalid json",
        "malformed",
        "must be",
        "base_url",
        "config.",
    )
    if any(marker in lower for marker in invalid_config_markers):
        return "invalid_config", True

    return "unknown", False


def success_outcome(message: str, latency_ms: int) -> ConnectorTestOutcome:
    return ConnectorTestOutcome(
        success=True,
        message=message,
        latency_ms=latency_ms,
        status="live",
        error_type=None,
        recoverable=None,
    )


def failure_outcome(
    *,
    message: str,
    latency_ms: int,
    exception: BaseException | None = None,
    status_code: int | None = None,
    error_type: FailureType | None = None,
    recoverable: bool | None = None,
) -> ConnectorTestOutcome:
    classified_error_type, classified_recoverable = classify_connector_failure(
        message=message,
        exception=exception,
        status_code=status_code,
    )
    return ConnectorTestOutcome(
        success=False,
        message=message,
        latency_ms=latency_ms,
        status="error",
        error_type=error_type or classified_error_type,
        recoverable=classified_recoverable if recoverable is None else recoverable,
    )
