"""
Executor — bridges gRPC ExecuteModule / VerifyAndExecute calls to the Mojo
binary (unix socket) or the Python fallback when the binary is unavailable.

Mojo binary protocol (from mojo/engine/main.mojo):
  Wire: [4-byte big-endian uint32 length][UTF-8 JSON payload]
  On connect: server sends {"status":"ready"}
  Request:    JSON with "engine_type" field (+ payload)
  Response:   JSON result string

The executor maintains a persistent connection to the Mojo server socket
(managed by daemon.py). If the socket is not available it falls back to
the Python adapter.
"""
from __future__ import annotations

import asyncio
import json
import os
import struct
import time
import uuid
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default socket path — must match daemon.py
_DEFAULT_MOJO_SOCK = os.environ.get(
    "ALGENTA_MOJO_SOCK",
    "/tmp/algenta-mojo/worker-0.sock",
)

# Module registry: maps library name → list of known public functions.
# Populated lazily from the test suite file names and MOJO_TIMING output.
# This is the v1 static registry; v2+ will read from the bundle manifest.
_MODULE_REGISTRY: dict[str, list[str]] = {
    "scheduling_algo": ["fcfs", "sjf", "priority_scheduling"],
    "recommender": [
        "cosine_sim_users", "predict_rating", "popularity_ranking",
        "mean_rating_per_item", "mean_rating_per_user", "top_n_items",
    ],
    # Simulation engines always available via engine_type dispatch
    "monte_carlo": ["run"],
    "scenario": ["run"],
    "bootstrap": ["run"],
    "sensitivity": ["run"],
    "decision_tree": ["run"],
    "time_series": ["run"],
}


# ── Low-level Mojo socket helpers ─────────────────────────────────────────────

async def _mojo_send(writer: asyncio.StreamWriter, payload: str) -> None:
    data = payload.encode()
    header = struct.pack(">I", len(data))
    writer.write(header + data)
    await writer.drain()


async def _mojo_recv(reader: asyncio.StreamReader) -> str:
    header = await reader.readexactly(4)
    length = struct.unpack(">I", header)[0]
    data = await reader.readexactly(length)
    return data.decode()


async def _mojo_call(payload: dict, sock_path: str = _DEFAULT_MOJO_SOCK) -> dict:
    """
    Open a connection to the Mojo unix socket, send one request, return parsed JSON.
    Raises ConnectionRefusedError / FileNotFoundError if socket is not available.
    """
    reader, writer = await asyncio.open_unix_connection(sock_path)
    try:
        # Consume the ready handshake
        _ready = await _mojo_recv(reader)   # {"status":"ready"}

        await _mojo_send(writer, json.dumps(payload))
        raw = await _mojo_recv(reader)
        return json.loads(raw)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ── Python fallback ───────────────────────────────────────────────────────────

def _python_fallback(module: str, function: str, args: Any) -> dict:
    """
    Thin Python fallback for simulation engines.
    For A-Z domain libraries, returns a not-implemented stub until the Mojo
    binary is built and the library is wired into main.mojo's dispatch.
    """
    # Simulation engine fallback — delegates to existing python_adapter
    if module in ("monte_carlo", "scenario", "bootstrap", "sensitivity",
                  "decision_tree", "time_series"):
        from mojo.bindings.python_adapter import run_simulation  # type: ignore[import]
        if isinstance(args, list) and len(args) > 0:
            config = args[0]
        elif isinstance(args, dict):
            config = args
        else:
            config = {}
        config.setdefault("engine_type", module)
        result = run_simulation(config)
        return {"result": result, "engine": "python-fallback"}

    # Domain library fallback — not yet implemented
    return {
        "error": (
            f"Module '{module}' not available in Python fallback. "
            "Build the Mojo binary to enable domain library execution: "
            "cd mojo_env && pixi run mojo build ../mojo/engine/main.mojo -o ../mojo_build/simulate"
        ),
        "engine": "python-fallback",
    }


# ── Public executor API ───────────────────────────────────────────────────────

class Executor:
    """
    Stateless executor — each call opens and closes a Mojo socket connection.
    v2+ will use a persistent connection pool.
    """

    def __init__(self, mojo_sock: str = _DEFAULT_MOJO_SOCK) -> None:
        self._mojo_sock = mojo_sock

    def _mojo_available(self) -> bool:
        return Path(self._mojo_sock).exists()

    async def execute_module(
        self,
        module: str,
        function: str,
        args: Any,
        request_id: str = "",
    ) -> dict:
        """
        Execute module::function(args).
        Returns {"result_json", "latency_ms", "engine_used", "success", "error"}.
        """
        from apps.runtime.ledger import append_event

        task_id = request_id or f"task_{uuid.uuid4().hex}"
        target = f"{module}.{function}"

        # ── Credit check (local quota enforcement) ────────────────────────
        from apps.runtime.credits import consume_credit
        if not await consume_credit():
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_module",
                status="blocked",
                target=target,
                request_id=request_id,
                engine_used="blocked",
                latency_ms=0.0,
                success=False,
                error="execution_quota_exhausted",
            )
            return {
                "result_json": "null",
                "latency_ms":  0.0,
                "engine_used": "blocked",
                "success":     False,
                "error": (
                    "execution_quota_exhausted: no execution credits remaining. "
                    "The daemon will refresh automatically when the server is reachable, "
                    "or run `algenta login` to re-register."
                ),
            }

        append_event(
            task_id=task_id,
            surface="runtime",
            action="execute_module",
            status="started",
            target=target,
            request_id=request_id,
            details={"module": module, "function": function},
        )
        t0 = time.monotonic()

        # Build Mojo dispatch payload.
        # Simulation engines use engine_type dispatch.
        # Domain libraries use module::function dispatch (added in future main.mojo).
        mojo_payload: dict = {}
        is_sim_engine = module in ("monte_carlo", "scenario", "bootstrap",
                                   "sensitivity", "decision_tree", "time_series",
                                   "mcmc", "lhs", "qmc_sobol")
        if is_sim_engine:
            if isinstance(args, dict):
                mojo_payload = {**args, "engine_type": module}
            else:
                mojo_payload = {"engine_type": module}
        else:
            # Generic library dispatch — routes via "library" engine_type
            mojo_payload = {
                "engine_type": "library",
                "module": module,
                "function": function,
                "args": args,
            }

        try:
            if self._mojo_available():
                raw = await _mojo_call(mojo_payload, self._mojo_sock)
                engine_used = "mojo"
            else:
                raw = _python_fallback(module, function, args)
                engine_used = "python-fallback"
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            logger.warning("mojo_socket_unavailable", sock=self._mojo_sock)
            raw = _python_fallback(module, function, args)
            engine_used = "python-fallback"
        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_module",
                status="failed",
                target=target,
                request_id=request_id,
                engine_used=engine_used if "engine_used" in dir() else "unknown",
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )
            return {
                "result_json": "null",
                "latency_ms": latency_ms,
                "engine_used": engine_used if "engine_used" in dir() else "unknown",
                "success": False,
                "error": str(exc),
            }

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        has_error = "error" in raw and raw.get("error")
        append_event(
            task_id=task_id,
            surface="runtime",
            action="execute_module",
            status="completed" if not has_error else "failed",
            target=target,
            request_id=request_id,
            engine_used=engine_used,
            latency_ms=latency_ms,
            success=not has_error,
            error=raw.get("error", "") if has_error else "",
        )
        return {
            "result_json": json.dumps(raw.get("result", raw)),
            "latency_ms": latency_ms,
            "engine_used": engine_used,
            "success": not has_error,
            "error": raw.get("error", "") if has_error else "",
        }

    def list_modules(self) -> list[dict]:
        """Return all known modules with their functions and engine availability."""
        mojo_ok = self._mojo_available()
        sim_engines = {"monte_carlo", "scenario", "bootstrap", "sensitivity",
                       "decision_tree", "time_series", "mcmc", "lhs", "qmc_sobol"}
        result = []
        for name, fns in _MODULE_REGISTRY.items():
            if name in sim_engines:
                engine = "mojo" if mojo_ok else "python-fallback"
            else:
                engine = "mojo" if mojo_ok else "unavailable"
            result.append({"name": name, "engine": engine, "functions": fns})
        return result
