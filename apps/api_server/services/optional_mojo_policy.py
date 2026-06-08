from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from apps.api_server.compute.mojo_errors import (
    MojoEngineError,
    build_mojo_engine_status,
    coerce_mojo_engine_error,
    is_global_optional_mojo_circuit_error,
    is_optional_mojo_circuit_error,
    mojo_failure_reason,
    validate_mojo_payload,
)

GLOBAL_OPTIONAL_MOJO_ENGINE_KEY = "__global__"
OptionalMojoFailureState = MutableMapping[str, tuple[float, str]]
OptionalMojoInvokeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
OptionalMojoMonotonicFn = Callable[[], float]


def optional_mojo_payload_bytes(payload: dict[str, Any]) -> int:
    try:
        return len(
            json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise MojoEngineError(
            "Invalid Mojo payload: could not serialize engine payload to JSON.",
            code="invalid_payload",
            recoverable=False,
            engine_type=str(payload.get("engine_type") or "unknown"),
            stage="preflight",
        ) from exc


def get_optional_mojo_engine_reason(
    *,
    failure_state: OptionalMojoFailureState,
    cache_key: str,
    cooldown_s: float,
    monotonic_fn: OptionalMojoMonotonicFn,
) -> str | None:
    cached = failure_state.get(cache_key)
    if cached is None:
        return None
    failed_at, reason = cached
    if monotonic_fn() - failed_at < cooldown_s:
        return reason
    failure_state.pop(cache_key, None)
    return None


def get_optional_mojo_engine_skip_reason(
    *,
    failure_state: OptionalMojoFailureState,
    engine_type: str,
    cooldown_s: float,
    monotonic_fn: OptionalMojoMonotonicFn,
    global_key: str = GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
) -> tuple[str | None, str | None]:
    global_reason = get_optional_mojo_engine_reason(
        failure_state=failure_state,
        cache_key=global_key,
        cooldown_s=cooldown_s,
        monotonic_fn=monotonic_fn,
    )
    if global_reason is not None:
        return global_reason, "global"
    engine_reason = get_optional_mojo_engine_reason(
        failure_state=failure_state,
        cache_key=engine_type,
        cooldown_s=cooldown_s,
        monotonic_fn=monotonic_fn,
    )
    if engine_reason is not None:
        return engine_reason, "engine"
    return None, None


def record_optional_mojo_engine_failure(
    *,
    failure_state: OptionalMojoFailureState,
    engine_type: str,
    reason: BaseException | str,
    monotonic_fn: OptionalMojoMonotonicFn,
    global_key: str = GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
) -> str:
    normalized_reason = mojo_failure_reason(reason)
    if not is_optional_mojo_circuit_error(reason):
        return normalized_reason
    failure = (monotonic_fn(), normalized_reason)
    failure_state[engine_type] = failure
    if is_global_optional_mojo_circuit_error(reason):
        failure_state[global_key] = failure
    return normalized_reason


def clear_optional_mojo_engine_failure(
    *,
    failure_state: OptionalMojoFailureState,
    engine_type: str,
    global_key: str = GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
    clear_global: bool = False,
) -> None:
    failure_state.pop(engine_type, None)
    if clear_global:
        failure_state.pop(global_key, None)


def build_optional_mojo_preflight_status(
    *,
    engine_type: str,
    payload: dict[str, Any],
    max_payload_bytes: int,
    reason: str | None = None,
) -> dict[str, Any] | None:
    validate_mojo_payload(payload)
    if reason is not None:
        return build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason=reason,
            message=f"Optional Mojo engine skipped during preflight: {reason}.",
            details={},
        )

    payload_bytes = optional_mojo_payload_bytes(payload)
    if payload_bytes <= max_payload_bytes:
        return None
    return build_mojo_engine_status(
        engine_type=engine_type,
        status="disabled",
        reason="preflight_payload_too_large",
        message=(
            "Optional Mojo payload exceeds configured limit and will use the "
            "deterministic fallback path instead."
        ),
        details={
            "payload_bytes": payload_bytes,
            "payload_limit_bytes": max_payload_bytes,
        },
    )


def _status_with_circuit_details(
    status: dict[str, Any],
    *,
    circuit_scope: str,
    cooldown_s: float,
) -> dict[str, Any]:
    details = dict(status.get("details") or {})
    details.setdefault("circuit_scope", circuit_scope)
    details.setdefault("cooldown_s", cooldown_s)
    status["details"] = details
    return status


async def invoke_optional_mojo_engine(
    *,
    engine_type: str,
    payload: dict[str, Any],
    preflight_reason: str | None,
    timeout_s: float,
    max_payload_bytes: int,
    cooldown_s: float,
    failure_state: OptionalMojoFailureState,
    monotonic_fn: OptionalMojoMonotonicFn,
    invoke_engine: Callable[..., Awaitable[dict[str, Any]]],
    global_key: str = GLOBAL_OPTIONAL_MOJO_ENGINE_KEY,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    preflight_status = build_optional_mojo_preflight_status(
        engine_type=engine_type,
        payload=payload,
        max_payload_bytes=max_payload_bytes,
        reason=preflight_reason,
    )
    if preflight_status is not None:
        return None, preflight_status

    skip_reason, circuit_scope = get_optional_mojo_engine_skip_reason(
        failure_state=failure_state,
        engine_type=engine_type,
        cooldown_s=cooldown_s,
        monotonic_fn=monotonic_fn,
        global_key=global_key,
    )
    if skip_reason is not None:
        return None, _status_with_circuit_details(
            build_mojo_engine_status(
                engine_type=engine_type,
                status="disabled",
                reason="engine_circuit_open",
                message=skip_reason,
                details={},
            ),
            circuit_scope=circuit_scope or "engine",
            cooldown_s=cooldown_s,
        )

    try:
        result = await invoke_engine(payload, timeout=timeout_s)
    except Exception as exc:
        error = coerce_mojo_engine_error(
            exc,
            engine_type=engine_type,
            stage="optional_exec",
        )
        record_optional_mojo_engine_failure(
            failure_state=failure_state,
            engine_type=engine_type,
            reason=error,
            monotonic_fn=monotonic_fn,
            global_key=global_key,
        )
        engine_status = error.as_error_details()
        if is_optional_mojo_circuit_error(error):
            return None, _status_with_circuit_details(
                engine_status,
                circuit_scope=(
                    "global" if is_global_optional_mojo_circuit_error(error) else "engine"
                ),
                cooldown_s=cooldown_s,
            )
        return None, engine_status

    clear_optional_mojo_engine_failure(
        failure_state=failure_state,
        engine_type=engine_type,
        global_key=global_key,
    )
    return result, build_mojo_engine_status(
        engine_type=engine_type,
        status="enabled",
        reason=None,
        details={"timeout_s": timeout_s},
    )
