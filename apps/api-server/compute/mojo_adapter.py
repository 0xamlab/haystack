"""
Mojo engine adapter — Pattern A (subprocess invocation).

Serializes the simulation payload to JSON, calls the compiled Mojo binary,
parses stdout JSON result. Raises typed exceptions on failure.

Falls back to the Python reference implementation (mojo/bindings/python_adapter.py)
when the Mojo binary is not yet compiled. The Python fallback has the same
input/output contract and is safe for development.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any

import structlog

from apps.api_server.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Add the project root to sys.path so the mojo package is importable
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class MojoEngineError(Exception):
    """Raised when the Mojo engine exits with a non-zero code or produces invalid output."""

    def __init__(self, message: str, stderr: str = "", exit_code: int = 0) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


class MojoEngineNotFoundError(MojoEngineError):
    """Raised when the Mojo binary is not found at the configured path."""

    pass


async def _invoke_python_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Invoke the Python reference implementation as a fallback.
    Used in development when the Mojo binary is not compiled.
    """
    try:
        from mojo.bindings.python_adapter import run_simulation  # type: ignore[import]

        logger.warning(
            "mojo_binary_not_found_using_python_fallback",
            binary_path=settings.mojo_binary_path,
        )
        # Run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_simulation, payload)
        return result
    except ImportError as exc:
        raise MojoEngineNotFoundError(
            f"Algenta runtime worker not found at '{settings.mojo_binary_path}' "
            f"and the development fallback could not be imported. "
            f"Install an Algenta build that includes the bundled runtime for this platform."
        ) from exc


async def invoke_engine(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Invoke the Mojo simulation engine asynchronously.

    In development (binary not found): falls back to Python reference implementation.
    In production: calls the compiled Mojo binary via subprocess.

    Args:
        payload: Dict matching the engine's stdin JSON contract.

    Returns:
        Dict of simulation results from the engine's stdout.

    Raises:
        MojoEngineNotFoundError: Binary not found and Python fallback unavailable.
        MojoEngineError: Engine exited with non-zero code or invalid JSON output.
        asyncio.TimeoutError: Engine exceeded MOJO_TIMEOUT_SECONDS.
    """
    binary_path = settings.mojo_binary_path
    timeout = settings.mojo_timeout_seconds

    if not os.path.isfile(binary_path):
        # In development: fall back to Python implementation
        if settings.is_development:
            return await _invoke_python_fallback(payload)
        raise MojoEngineNotFoundError(
            f"Algenta runtime worker not found at '{binary_path}'. "
            f"Install an Algenta build that includes the bundled runtime for this platform."
        )

    input_json = json.dumps(payload)
    start = time.perf_counter()

    try:
        proc = await asyncio.create_subprocess_exec(
            binary_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_json.encode()),
                timeout=float(timeout),
            )
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)

        if proc.returncode != 0:
            stderr_text = stderr.decode(errors="replace").strip()
            logger.error(
                "mojo_engine_failed",
                exit_code=proc.returncode,
                stderr=stderr_text,
                duration_ms=duration_ms,
            )
            raise MojoEngineError(
                f"Engine exited with code {proc.returncode}",
                stderr=stderr_text,
                exit_code=proc.returncode or 0,
            )

        stdout_text = stdout.decode().strip()
        if not stdout_text:
            raise MojoEngineError("Engine produced no output", exit_code=0)

        try:
            result = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise MojoEngineError(
                f"Engine output is not valid JSON: {exc}",
                exit_code=0,
            ) from exc

        logger.info(
            "mojo_engine_success",
            duration_ms=duration_ms,
            scenarios_run=result.get("scenarios_run", payload.get("runs")),
            engine_version=result.get("engine_version", "unknown"),
        )
        return result

    except (MojoEngineNotFoundError, MojoEngineError):
        raise
    except TimeoutError as exc:
        logger.error("mojo_engine_timeout", timeout_seconds=timeout)
        raise MojoEngineError(
            f"Engine timed out after {timeout} seconds",
            exit_code=-1,
        ) from exc
