"""
Mojo engine adapter.

Production path: delegates to MojoWorkerPool (long-lived processes, Unix socket IPC).
Fallback path:   asyncio.create_subprocess_exec() — used only when the pool is
                 not yet initialized (e.g. during unit tests without a running server).

Phase 1: MOJO_ALLOW_SUBPROCESS_FALLBACK env var is checked before silently
         falling back. If "false" and pool raises a non-transient error,
         re-raises as MojoEngineError with clear message — does NOT silently fall back.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_REPO_ROOT   = Path(__file__).parents[3]
_BINARY_PATH = _REPO_ROOT / "mojo_build" / "simulate"


def _env_flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() == "true"


# Phase 1: fallback policy — read once at module load
_ALLOW_SUBPROCESS_FALLBACK = _env_flag("MOJO_ALLOW_SUBPROCESS_FALLBACK")

# Pool error messages that indicate the pool is intentionally not running
# (binary missing, server mode not supported). These are non-transient and trigger fallback.
_POOL_NOT_RUNNING_MSGS = (
    "Mojo pool is not running",
    "Mojo pool not initialized",
)


class MojoEngineError(Exception):
    """Raised when the Mojo engine fails or is unavailable."""
    def __init__(self, message: str, stderr: str = "", exit_code: int = 0) -> None:
        super().__init__(message)
        self.stderr    = stderr
        self.exit_code = exit_code


async def invoke_engine(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Invoke the Mojo simulation engine.

    Production: routes through MojoWorkerPool (no process spawn per request).
    Fallback: single subprocess (for tests / first request before pool warms).

    Phase 1: If MOJO_ALLOW_SUBPROCESS_FALLBACK=false, non-transient pool errors
             are re-raised as MojoEngineError — no silent subprocess fallback.

    :param payload: Simulation config dict.
    :returns: Engine result dict.
    :raises MojoEngineError: On binary absence, computation error, or timeout.
    """
    try:
        from apps.api_server.compute.mojo_pool import MojoEngineError as PoolError
        from apps.api_server.compute.mojo_pool import get_pool_sync
        pool = get_pool_sync()
        try:
            return await pool.invoke(payload)
        except PoolError as exc:
            err_msg = str(exc)
            if any(m in err_msg for m in _POOL_NOT_RUNNING_MSGS):
                # Pool is intentionally inactive (binary missing / no server mode)
                if not _ALLOW_SUBPROCESS_FALLBACK:
                    raise MojoEngineError(
                        f"Mojo pool is not running and MOJO_ALLOW_SUBPROCESS_FALLBACK=false. "
                        f"Cannot serve requests. Original error: {err_msg}",
                        exit_code=1,
                    ) from exc
                logger.debug(
                    "mojo_pool_not_running_fallback_to_subprocess",
                    reason=err_msg,
                    allow_fallback=True,
                )
            else:
                # Transient compute error — always re-raise
                raise MojoEngineError(
                    err_msg, exit_code=getattr(exc, "exit_code", 1)
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
            ) from exc

    # Fallback path — subprocess per call (dev / tests only)
    return await _invoke_subprocess(payload)


async def _invoke_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    """Single-use subprocess invocation (fallback only — not used in production)."""
    if not _BINARY_PATH.exists() or not os.access(_BINARY_PATH, os.X_OK):
        raise MojoEngineError(
            f"Mojo binary not found at {_BINARY_PATH}. "
            "Run `make setup-mojo && make build-mojo` to build the native engine."
        )

    payload_bytes = json.dumps(payload).encode()

    proc = await asyncio.create_subprocess_exec(
        str(_BINARY_PATH),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=payload_bytes),
            timeout=60.0,
        )
    except TimeoutError as exc:
        proc.kill()
        raise MojoEngineError("Mojo engine timed out after 60s", exit_code=124) from exc

    if proc.returncode != 0:
        raise MojoEngineError(
            f"Mojo engine exited with code {proc.returncode}",
            stderr=stderr.decode(errors="replace"),
            exit_code=proc.returncode or -1,
        )

    # Handle multi-line output (streaming mode emits NDJSON progress + final)
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
        ) from exc

    if isinstance(result, dict) and "error" in result:
        raise MojoEngineError(
            str(result["error"]),
            stderr=stderr.decode(errors="replace"),
            exit_code=1,
        )

    return result
