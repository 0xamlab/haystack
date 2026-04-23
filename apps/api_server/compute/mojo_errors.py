from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_RECOVERABLE_CODES = frozenset(
    {
        "binary_missing",
        "engine_crash",
        "engine_failed",
        "pool_not_initialized",
        "pool_not_running",
        "pool_loop_unavailable",
        "server_mode_unavailable",
        "timeout",
        "worker_unhealthy",
    }
)

_GLOBAL_CIRCUIT_CODES = frozenset(
    {
        "binary_missing",
        "engine_crash",
        "pool_not_initialized",
        "pool_not_running",
        "pool_loop_unavailable",
        "server_mode_unavailable",
        "worker_unhealthy",
    }
)


class MojoEngineError(Exception):
    """Raised when the Mojo engine fails or is unavailable."""

    def __init__(
        self,
        message: str,
        stderr: str = "",
        exit_code: int = 0,
        *,
        code: str = "engine_error",
        recoverable: bool | None = None,
        engine_type: str | None = None,
        stage: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code
        self.code = code
        self.recoverable = (
            code in _RECOVERABLE_CODES if recoverable is None else recoverable
        )
        self.engine_type = engine_type
        self.stage = stage
        self.details = dict(details or {})

    def as_error_details(self) -> dict[str, Any]:
        details = dict(self.details)
        if self.engine_type:
            details.setdefault("engine_type", self.engine_type)
        if self.stage:
            details.setdefault("stage", self.stage)
        if self.stderr:
            details.setdefault("stderr", self.stderr)
        if self.exit_code:
            details.setdefault("exit_code", self.exit_code)
        return {
            "engine": "mojo",
            "status": "failed",
            "reason": self.code,
            "message": str(self),
            "recoverable": self.recoverable,
            "details": details,
        }


def build_mojo_engine_status(
    *,
    engine_type: str,
    status: str,
    reason: str | None,
    message: str | None = None,
    recoverable: bool = True,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status_details = dict(details or {})
    status_details.setdefault("engine_type", engine_type)
    return {
        "engine": "mojo",
        "status": status,
        "reason": reason,
        "message": message,
        "recoverable": recoverable,
        "details": status_details,
    }


def validate_mojo_payload(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise MojoEngineError(
            "Invalid Mojo payload: expected an object.",
            code="invalid_payload",
            recoverable=False,
            stage="preflight",
        )
    engine_type = payload.get("engine_type")
    if not isinstance(engine_type, str) or not engine_type.strip():
        raise MojoEngineError(
            "Invalid Mojo payload: requires a non-empty string engine_type.",
            code="invalid_payload",
            recoverable=False,
            stage="preflight",
        )
    return engine_type.strip()


def infer_mojo_error_code(message: str, *, exit_code: int | None = None) -> str:
    lowered = message.lower()
    if "requires a non-empty string engine_type" in lowered or "invalid mojo payload" in lowered:
        return "invalid_payload"
    if "binary not found" in lowered:
        return "binary_missing"
    if "does not support --server mode" in lowered or (
        "server mode" in lowered and "rebuild" in lowered
    ):
        return "server_mode_unavailable"
    if "pool not initialized" in lowered:
        return "pool_not_initialized"
    if "pool is not running" in lowered:
        return "pool_not_running"
    if "pool loop is not available" in lowered:
        return "pool_loop_unavailable"
    if "worker" in lowered and "unhealthy" in lowered:
        return "worker_unhealthy"
    if "timed out" in lowered:
        return "timeout"
    if "all " in lowered and "workers busy" in lowered:
        return "workers_busy"
    if "returned invalid json" in lowered:
        return "invalid_response"
    if "returned a non-object response" in lowered:
        return "invalid_response"
    if "python fallback is unavailable" in lowered:
        return "python_fallback_unavailable"
    if "payload exceeds optional mojo limit" in lowered:
        return "preflight_payload_too_large"
    if "exited with code" in lowered:
        if "exited with code -" in lowered:
            return "engine_crash"
        if exit_code is not None and exit_code < 0:
            return "engine_crash"
        return "engine_failed"
    return "engine_error"


def mojo_failure_reason(error: BaseException | str) -> str:
    if isinstance(error, MojoEngineError):
        return f"{error.code}: {error}"
    if isinstance(error, str):
        return f"{infer_mojo_error_code(error)}: {error}"
    message = str(error)
    return f"{infer_mojo_error_code(message)}: {message}"


def coerce_mojo_engine_error(
    error: BaseException | str,
    *,
    engine_type: str | None = None,
    stage: str | None = None,
) -> MojoEngineError:
    if isinstance(error, MojoEngineError):
        return error
    message = error if isinstance(error, str) else str(error)
    return MojoEngineError(
        message,
        code=infer_mojo_error_code(message),
        engine_type=engine_type,
        stage=stage,
    )


def is_optional_mojo_circuit_error(error: BaseException | str) -> bool:
    if isinstance(error, MojoEngineError):
        return error.code in _RECOVERABLE_CODES
    return infer_mojo_error_code(str(error)) in _RECOVERABLE_CODES


def is_global_optional_mojo_circuit_error(error: BaseException | str) -> bool:
    if isinstance(error, MojoEngineError):
        return error.code in _GLOBAL_CIRCUIT_CODES
    return infer_mojo_error_code(str(error)) in _GLOBAL_CIRCUIT_CODES
