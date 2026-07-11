"""
Mojo engine adapter.

Production path: delegates to MojoWorkerPool (long-lived processes, Unix socket IPC).
Fallback paths:
  1. asyncio.create_subprocess_exec() for a compiled native binary.
  2. The Python reference engine for supported simulation payloads when the
     native binary is absent and runtime fallbacks are allowed.

Phase 1: MOJO_ALLOW_SUBPROCESS_FALLBACK env var is checked before silently
         falling back. If "false" and pool raises a non-transient error,
         re-raises as MojoEngineError with clear message — does NOT silently fall back.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import structlog

from apps.api_server.compute.mojo_errors import (
    MojoEngineError,
    infer_mojo_error_code,
    validate_mojo_payload,
)
from apps.api_server.config import SettingsProxy
from apps.runtime.native_worker import resolve_native_worker

logger = structlog.get_logger(__name__)
settings = SettingsProxy()

__all__ = ["MojoEngineError", "invoke_engine", "invoke_engine_sync"]

_REPO_ROOT = Path(__file__).parents[3]


def _default_binary_path() -> Path:
    resolved = resolve_native_worker(require_verified=False)
    if resolved is not None and not resolved.public_error:
        return resolved.path
    return _REPO_ROOT / "mojo_build" / "simulate"


_BINARY_PATH = _default_binary_path()
_PYTHON_ADAPTER_PATH = _REPO_ROOT / "mojo" / "bindings" / "python_adapter.py"
_PYTHON_FALLBACK_ENGINES = frozenset(
    {
        "monte_carlo",
        "qmc_sobol",
        "lhs",
        "bootstrap",
        "scenario",
        "sensitivity",
        "mcmc",
        "decision_tree",
        "time_series",
        "compare",
        "importance_sampling",
    }
)


def _env_flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() == "true"


# Phase 1: fallback policy — read once at module load
_ALLOW_SUBPROCESS_FALLBACK = _env_flag("MOJO_ALLOW_SUBPROCESS_FALLBACK")
_FALLBACK_WARNING_COOLDOWN_S = float(
    os.environ.get("MOJO_FALLBACK_WARNING_COOLDOWN_S", "60"),
)
_FALLBACK_WARNING_STATE: dict[tuple[str, str, str], float] = {}

# Pool error messages that indicate the pool is intentionally not running
# (binary missing, server mode not supported). These are non-transient and trigger fallback.
_POOL_FALLBACKABLE_CODES = frozenset(
    {
        "pool_not_running",
        "pool_not_initialized",
        "pool_loop_unavailable",
        "sync_on_pool_thread",
        "timeout",
        "worker_unhealthy",
    }
)


def _log_fallback_warning(
    event: str,
    *,
    engine_type: str,
    binary_path: str | None = None,
    exit_code: int | None = None,
    fallback_allowed: bool,
) -> None:
    detail_key = str(exit_code) if exit_code is not None else str(binary_path or "")
    cache_key = (event, engine_type, detail_key)
    now = time.monotonic()
    last_warning_at = _FALLBACK_WARNING_STATE.get(cache_key)
    if last_warning_at is not None and now - last_warning_at < _FALLBACK_WARNING_COOLDOWN_S:
        logger.debug(
            f"{event}_suppressed",
            binary_path=binary_path,
            cooldown_s=_FALLBACK_WARNING_COOLDOWN_S,
            engine_type=engine_type,
            exit_code=exit_code,
            fallback_allowed=fallback_allowed,
        )
        return

    _FALLBACK_WARNING_STATE[cache_key] = now
    logger.warning(
        event,
        binary_path=binary_path,
        cooldown_s=_FALLBACK_WARNING_COOLDOWN_S,
        engine_type=engine_type,
        exit_code=exit_code,
        fallback_allowed=fallback_allowed,
    )


@lru_cache(maxsize=1)
def _load_python_fallback_runner() -> Callable[[dict[str, Any]], dict[str, Any]]:
    if not _PYTHON_ADAPTER_PATH.is_file():
        raise MojoEngineError(
            "Python simulation fallback is unavailable. "
            f"Expected adapter at `{_PYTHON_ADAPTER_PATH}` or build the native engine.",
            exit_code=1,
            code="python_fallback_unavailable",
            recoverable=False,
        )

    spec = importlib.util.spec_from_file_location(
        "decision_engine_python_adapter",
        _PYTHON_ADAPTER_PATH,
    )
    if spec is None or spec.loader is None:
        raise MojoEngineError(
            "Python simulation fallback is unavailable. "
            f"Could not load adapter spec from `{_PYTHON_ADAPTER_PATH}`.",
            exit_code=1,
            code="python_fallback_unavailable",
            recoverable=False,
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run_simulation = getattr(module, "run_simulation", None)
    if not callable(run_simulation):
        raise MojoEngineError(
            "Python simulation fallback is unavailable. "
            f"`{_PYTHON_ADAPTER_PATH}` does not expose callable `run_simulation`.",
            exit_code=1,
            code="python_fallback_unavailable",
            recoverable=False,
        )

    return cast(Callable[[dict[str, Any]], dict[str, Any]], run_simulation)


def _supports_python_fallback(payload: dict[str, Any]) -> bool:
    engine_type = payload.get("engine_type")
    return isinstance(engine_type, str) and engine_type in _PYTHON_FALLBACK_ENGINES


async def _invoke_python_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    engine_type = str(payload.get("engine_type") or "monte_carlo")
    if not _supports_python_fallback(payload):
        raise MojoEngineError(
            f"Python fallback does not support engine_type '{engine_type}'.",
            exit_code=1,
            code="python_fallback_unsupported",
            recoverable=False,
            engine_type=engine_type,
        )

    try:
        run_simulation = _load_python_fallback_runner()
    except MojoEngineError:
        raise
    except Exception as exc:
        raise MojoEngineError(
            "Python simulation fallback is unavailable. Ensure "
            f"`{_PYTHON_ADAPTER_PATH}` is loadable or build the native engine.",
            exit_code=1,
            code="python_fallback_unavailable",
            recoverable=False,
            engine_type=engine_type,
        ) from exc

    loop = asyncio.get_running_loop()
    raw_result = await loop.run_in_executor(None, run_simulation, payload)
    if not isinstance(raw_result, dict):
        raise MojoEngineError(
            "Python simulation fallback returned a non-object response.",
            exit_code=1,
            code="invalid_response",
            recoverable=False,
            engine_type=engine_type,
        )

    result = dict(raw_result)
    result.setdefault("simulation_model", engine_type)
    result.setdefault("engine_type", engine_type)
    return result


def _invoke_python_fallback_sync(payload: dict[str, Any]) -> dict[str, Any]:
    engine_type = str(payload.get("engine_type") or "monte_carlo")
    if not _supports_python_fallback(payload):
        raise MojoEngineError(
            f"Python fallback does not support engine_type '{engine_type}'.",
            exit_code=1,
            code="python_fallback_unsupported",
            recoverable=False,
            engine_type=engine_type,
        )

    try:
        run_simulation = _load_python_fallback_runner()
    except MojoEngineError:
        raise
    except Exception as exc:
        raise MojoEngineError(
            "Python simulation fallback is unavailable. Ensure "
            f"`{_PYTHON_ADAPTER_PATH}` is loadable or build the native engine.",
            exit_code=1,
            code="python_fallback_unavailable",
            recoverable=False,
            engine_type=engine_type,
        ) from exc

    raw_result = run_simulation(payload)
    if not isinstance(raw_result, dict):
        raise MojoEngineError(
            "Python simulation fallback returned a non-object response.",
            exit_code=1,
            code="invalid_response",
            recoverable=False,
            engine_type=engine_type,
        )

    result = dict(raw_result)
    result.setdefault("simulation_model", engine_type)
    result.setdefault("engine_type", engine_type)
    return result


def _decode_engine_output(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    raw_output = stdout.decode()
    last_line = ""
    for line in raw_output.strip().splitlines():
        stripped = line.strip()
        if stripped:
            last_line = stripped

    try:
        result = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise MojoEngineError(
            f"Mojo engine returned invalid JSON: {exc}",
            stderr=stderr.decode(errors="replace"),
            code="invalid_response",
            recoverable=False,
            stage="decode",
        ) from exc

    if not isinstance(result, dict):
        raise MojoEngineError(
            "Mojo engine returned a non-object JSON response.",
            stderr=stderr.decode(errors="replace"),
            exit_code=1,
            code="invalid_response",
            recoverable=False,
            stage="decode",
        )

    if "error" in result:
        raise MojoEngineError(
            str(result["error"]),
            stderr=stderr.decode(errors="replace"),
            exit_code=1,
            code="engine_reported_error",
            recoverable=False,
            stage="decode",
        )
    return dict(result)


async def invoke_engine(
    payload: dict[str, Any],
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """
    Invoke the Mojo simulation engine.

    Production: routes through MojoWorkerPool (no process spawn per request).
    Fallback: native subprocess when available, otherwise the Python reference
    engine for supported simulation payloads when runtime policy allows it.

    Phase 1: If MOJO_ALLOW_SUBPROCESS_FALLBACK=false, non-transient pool errors
             are re-raised as MojoEngineError — no silent subprocess fallback.

    :param payload: Simulation config dict.
    :returns: Engine result dict.
    :raises MojoEngineError: On binary absence, computation error, or timeout.
    """
    engine_type = validate_mojo_payload(payload)
    try:
        from apps.api_server.compute.mojo_pool import get_pool_sync

        try:
            pool = get_pool_sync()
            return await pool.invoke(payload, timeout=timeout)
        except MojoEngineError as exc:
            error_code = (
                exc.code
                if exc.code != "engine_error"
                else infer_mojo_error_code(str(exc), exit_code=getattr(exc, "exit_code", None))
            )
            if error_code in _POOL_FALLBACKABLE_CODES:
                # Pool cannot safely serve this request on the current path.
                if not _ALLOW_SUBPROCESS_FALLBACK:
                    raise MojoEngineError(
                        f"Mojo pool fallback is disabled and MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                        f"Cannot serve requests. Original error: {exc}",
                        exit_code=1,
                        code=error_code,
                        recoverable=False,
                        engine_type=engine_type,
                        stage="pool_dispatch",
                        details=exc.as_error_details()["details"],
                    ) from exc
                logger.debug(
                    "mojo_pool_fallback_to_subprocess",
                    reason=str(exc),
                    code=error_code,
                    allow_fallback=True,
                )
            else:
                # Transient compute error — always re-raise
                raise MojoEngineError(
                    str(exc),
                    exit_code=getattr(exc, "exit_code", 1),
                    code=error_code,
                    recoverable=exc.recoverable,
                    engine_type=engine_type,
                    stage=exc.stage or "pool_dispatch",
                    details=exc.as_error_details()["details"],
                ) from exc
    except MojoEngineError:
        raise
    except Exception as exc:
        # Pool not initialized yet (e.g. unit tests without lifespan)
        if not _ALLOW_SUBPROCESS_FALLBACK:
            raise MojoEngineError(
                "Mojo pool not initialized and MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                "Cannot serve requests without a running pool in production mode.",
                exit_code=1,
                code="pool_not_initialized",
                recoverable=False,
                engine_type=engine_type,
                stage="pool_dispatch",
            ) from exc

    # Fallback path — native subprocess when available, otherwise Python fallback
    return await _invoke_subprocess(payload, timeout=timeout or 60.0)


def invoke_engine_sync(payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    """
    Synchronous Mojo invocation for sync planner code running off the event loop.

    This prefers the shared MojoWorkerPool when available, then falls back to
    the single-use subprocess path under the same runtime policy as invoke_engine().
    """
    engine_type = validate_mojo_payload(payload)
    try:
        from apps.api_server.compute.mojo_pool import get_pool_sync

        try:
            pool = get_pool_sync()
            return pool.invoke_sync(payload, timeout=timeout)
        except MojoEngineError as exc:
            err_msg = str(exc)
            error_code = (
                exc.code
                if exc.code != "engine_error"
                else infer_mojo_error_code(err_msg, exit_code=getattr(exc, "exit_code", None))
            )
            fallbackable = error_code in _POOL_FALLBACKABLE_CODES
            if not fallbackable:
                raise MojoEngineError(
                    err_msg,
                    exit_code=getattr(exc, "exit_code", 1),
                    code=error_code,
                    recoverable=exc.recoverable,
                    engine_type=engine_type,
                    stage=exc.stage or "pool_dispatch",
                    details=exc.as_error_details()["details"],
                ) from exc
            if not _ALLOW_SUBPROCESS_FALLBACK:
                raise MojoEngineError(
                    f"{err_msg} and MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                    "Cannot serve sync Mojo requests without a running pool.",
                    exit_code=1,
                    code=error_code,
                    recoverable=False,
                    engine_type=engine_type,
                    stage="pool_dispatch",
                    details=exc.as_error_details()["details"],
                ) from exc
            logger.debug(
                "mojo_pool_sync_fallback_to_subprocess",
                reason=err_msg,
                code=error_code,
                allow_fallback=True,
                engine_type=str(payload.get("engine_type") or "unknown"),
            )
    except MojoEngineError:
        raise
    except Exception as exc:
        if not _ALLOW_SUBPROCESS_FALLBACK:
            raise MojoEngineError(
                "Mojo pool not initialized and MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                "Cannot serve sync Mojo requests without a running pool.",
                exit_code=1,
                code="pool_not_initialized",
                recoverable=False,
                engine_type=engine_type,
                stage="pool_dispatch",
            ) from exc

    return _invoke_subprocess_sync(payload, timeout=timeout or 60.0)


async def _invoke_subprocess(
    payload: dict[str, Any],
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Single-use subprocess invocation (fallback only — not used in production)."""
    engine_type = validate_mojo_payload(payload)
    if not _BINARY_PATH.exists() or not os.access(_BINARY_PATH, os.X_OK):
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_binary_missing_using_python_fallback",
                binary_path=str(_BINARY_PATH),
                engine_type=engine_type,
                fallback_allowed=True,
                exit_code=None,
            )
            return await _invoke_python_fallback(payload)
        raise MojoEngineError(
            f"Algenta runtime worker not found at {_BINARY_PATH}. "
            "Install an Algenta build that includes the bundled runtime for this platform.",
            code="binary_missing",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_preflight",
        )

    payload_bytes = json.dumps(payload).encode()

    try:
        proc = await asyncio.create_subprocess_exec(
            str(_BINARY_PATH),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_binary_unexecutable_using_python_fallback",
                binary_path=str(_BINARY_PATH),
                engine_type=engine_type,
                fallback_allowed=True,
                exit_code=getattr(exc, "errno", None),
            )
            return await _invoke_python_fallback(payload)
        raise MojoEngineError(
            f"Algenta runtime worker could not start from {_BINARY_PATH}: {exc}",
            code="binary_unexecutable",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=payload_bytes),
            timeout=timeout,
        )
    except TimeoutError as exc:
        proc.kill()
        raise MojoEngineError(
            f"Algenta runtime worker timed out after {timeout}s",
            exit_code=124,
            code="timeout",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        ) from exc
    except (BrokenPipeError, ConnectionResetError, OSError, RuntimeError) as exc:
        try:
            if proc.returncode is None:
                proc.kill()
        except ProcessLookupError:
            pass
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_subprocess_io_failed_using_python_fallback",
                engine_type=engine_type,
                exit_code=None,
                fallback_allowed=True,
                binary_path=str(_BINARY_PATH),
            )
            return await _invoke_python_fallback(payload)
        raise MojoEngineError(
            f"Algenta runtime worker I/O failed while invoking {_BINARY_PATH}: {exc}",
            code="subprocess_io_failed",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        ) from exc

    if proc.returncode != 0:
        return_code = proc.returncode if proc.returncode is not None else -1
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_engine_crashed_using_python_fallback",
                engine_type=engine_type,
                exit_code=proc.returncode,
                fallback_allowed=True,
                binary_path=None,
            )
            return await _invoke_python_fallback(payload)
        raise MojoEngineError(
            f"Algenta runtime worker exited with code {return_code}",
            stderr=stderr.decode(errors="replace"),
            exit_code=return_code,
            code="engine_crash" if return_code < 0 else "engine_failed",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        )

    return _decode_engine_output(stdout, stderr)


def _invoke_subprocess_sync(payload: dict[str, Any], *, timeout: float = 60.0) -> dict[str, Any]:
    """Single-use synchronous subprocess invocation for sync planner paths."""
    engine_type = validate_mojo_payload(payload)
    if not _BINARY_PATH.exists() or not os.access(_BINARY_PATH, os.X_OK):
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_binary_missing_using_python_fallback",
                binary_path=str(_BINARY_PATH),
                engine_type=engine_type,
                fallback_allowed=True,
                exit_code=None,
            )
            return _invoke_python_fallback_sync(payload)
        raise MojoEngineError(
            f"Algenta runtime worker not found at {_BINARY_PATH}. "
            "Install an Algenta build that includes the bundled runtime for this platform.",
            code="binary_missing",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_preflight",
        )

    payload_bytes = json.dumps(payload).encode()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed local binary path discovered by module constant
            [str(_BINARY_PATH)],
            input=payload_bytes,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise MojoEngineError(
            f"Algenta runtime worker timed out after {timeout}s",
            exit_code=124,
            code="timeout",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        ) from exc
    except OSError as exc:
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_binary_unexecutable_using_python_fallback",
                binary_path=str(_BINARY_PATH),
                engine_type=engine_type,
                fallback_allowed=True,
                exit_code=getattr(exc, "errno", None),
            )
            return _invoke_python_fallback_sync(payload)
        raise MojoEngineError(
            f"Algenta runtime worker could not start from {_BINARY_PATH}: {exc}",
            code="binary_unexecutable",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        ) from exc

    if proc.returncode != 0:
        if settings.allow_runtime_fallbacks and _supports_python_fallback(payload):
            _log_fallback_warning(
                "mojo_engine_crashed_using_python_fallback",
                engine_type=engine_type,
                exit_code=proc.returncode,
                fallback_allowed=True,
                binary_path=None,
            )
            return _invoke_python_fallback_sync(payload)
        raise MojoEngineError(
            f"Algenta runtime worker exited with code {proc.returncode}",
            stderr=proc.stderr.decode(errors="replace"),
            exit_code=proc.returncode or -1,
            code="engine_crash" if proc.returncode < 0 else "engine_failed",
            recoverable=True,
            engine_type=engine_type,
            stage="subprocess_exec",
        )

    return _decode_engine_output(proc.stdout, proc.stderr)
