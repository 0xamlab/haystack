"""
Executor — bridges gRPC ExecuteModule / VerifyAndExecute calls to the local
Mojo runtime surfaces.

Mojo binary protocol (from mojo/engine/main.mojo):
  Wire: [4-byte big-endian uint32 length][UTF-8 JSON payload]
  On connect: server sends {"status":"ready"}
  Request:    JSON with "engine_type" field (+ payload)
  Response:   JSON result string

The executor uses the compiled Mojo worker socket for both simulation engines
and runtime-owned libraries. Python fallback is intentionally disabled.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import structlog

from apps.runtime.mojo_inventory import RuntimeLibraryModule
from apps.runtime.mojo_library_runner import (
    MojoLibraryError,
    build_runtime_library_worker_request,
    library_runtime_available,
    parse_runtime_library_worker_response,
    runtime_library_modules,
)
from apps.runtime.runtime_shards import ShardWorkerPool, ShardWorkerUnavailable

logger = structlog.get_logger(__name__)

# Default socket path — must match daemon.py


def _default_mojo_socket() -> str:
    base_dir = Path(tempfile.gettempdir()) / "algenta-mojo"
    return str(base_dir / "worker-0.sock")


_DEFAULT_MOJO_SOCK = os.environ.get("ALGENTA_MOJO_SOCK", _default_mojo_socket())
_SIMULATION_ENGINES = (
    "bootstrap",
    "decision_tree",
    "importance_sampling",
    "lhs",
    "mcmc",
    "monte_carlo",
    "qmc_sobol",
    "scenario",
    "sensitivity",
    "time_series",
)


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


async def _mojo_call(
    payload: dict[str, Any],
    sock_path: str = _DEFAULT_MOJO_SOCK,
) -> dict[str, Any]:
    """
    Open a connection to the runtime worker socket, send one request, return parsed JSON.
    Raises ConnectionRefusedError / FileNotFoundError if socket is not available.
    """
    reader, writer = await asyncio.open_unix_connection(sock_path)
    try:
        # Consume the ready handshake
        _ready = await _mojo_recv(reader)  # {"status":"ready"}

        await _mojo_send(writer, json.dumps(payload))
        raw = await _mojo_recv(reader)
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("Runtime worker returned a non-object response payload.")
        return decoded
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception as exc:
            logger.debug("mojo_socket_close_failed", error=str(exc), socket=sock_path)


# ── Python fallback ───────────────────────────────────────────────────────────


def _python_fallback(module: str, function: str, args: Any) -> dict[str, str]:
    """
    Thin Python fallback for simulation engines.
    For A-Z domain libraries, returns a not-implemented stub until the Mojo
    binary is built and the library is wired into main.mojo's dispatch.
    """
    return {
        "error": (
            f"python_fallback_disabled: Python fallback is disabled for {module}.{function}. "
            "Start the local Mojo runtime or use governed Algenta API endpoints."
        ),
        "engine": "unavailable",
    }


# ── Public executor API ───────────────────────────────────────────────────────


class Executor:
    """
    Stateless executor — each call opens and closes a Mojo socket connection.
    v2+ will use a persistent connection pool.

    Shard-aware mode: when constructed with a ``shard_pool`` (the daemon found
    a ``runtime-shards.json`` next to the worker), each ``library_execute``
    request is routed to the shard owning that module — the pool spawns/caches
    the shard's worker lazily. Simulation engines and the query plane always
    run on the default shard. Without a pool the single-worker socket path is
    preserved exactly.
    """

    def __init__(
        self,
        mojo_sock: str = _DEFAULT_MOJO_SOCK,
        shard_pool: ShardWorkerPool | None = None,
    ) -> None:
        self._mojo_sock = mojo_sock
        self._shard_pool = shard_pool

    def _mojo_available(self) -> bool:
        return Path(self._mojo_sock).exists()

    async def _worker_call(
        self,
        payload: dict[str, Any],
        routing_module: str | None,
    ) -> dict[str, Any]:
        """Send one framed request to the worker that owns ``routing_module``.

        ``None`` routes to the default worker (simulation engines, the query
        plane). With no shard pool this is the historical single socket,
        unchanged. Acquire/release bracket the call so the pool never evicts a
        shard while a request is in flight on it.
        """
        if self._shard_pool is None:
            return await _mojo_call(payload, self._mojo_sock)
        sock_path = await self._shard_pool.acquire(routing_module)
        try:
            return await _mojo_call(payload, sock_path)
        finally:
            self._shard_pool.release(routing_module)

    def _library_runtime_available(self) -> bool:
        return library_runtime_available()

    def _list_runtime_library_modules(self) -> tuple[RuntimeLibraryModule, ...]:
        return runtime_library_modules()

    async def execute_module(
        self,
        module: str,
        function: str,
        args: Any,
        request_id: str = "",
    ) -> dict[str, Any]:
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
                "latency_ms": 0.0,
                "engine_used": "blocked",
                "success": False,
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

        is_sim_engine = module in _SIMULATION_ENGINES

        try:
            # With a shard pool the socket-existence gate is skipped: shard
            # sockets legitimately don't exist until their first routed request,
            # and the pool spawns/revives workers itself (raising
            # ShardWorkerUnavailable, handled below, when it cannot).
            if self._shard_pool is None and not self._mojo_available():
                return {
                    "result_json": "null",
                    "latency_ms": round((time.monotonic() - t0) * 1000, 2),
                    "engine_used": "unavailable",
                    "success": False,
                    "error": (
                        "compute_runtime_unavailable: local Mojo runtime is "
                        "not available. Start the daemon with a compiled Mojo binary."
                    ),
                }
            if is_sim_engine:
                mojo_payload: dict[str, Any]
                if isinstance(args, dict):
                    mojo_payload = {**args, "engine_type": module}
                else:
                    mojo_payload = {"engine_type": module}
                # Simulation engines live in the default shard.
                raw = await self._worker_call(mojo_payload, None)
                result_payload = raw.get("result", raw)
                has_error = bool(raw.get("error"))
                engine_used = "mojo"
                error_message = str(raw.get("error", "") or "")
            else:
                function_spec, mojo_payload = build_runtime_library_worker_request(
                    module,
                    function,
                    args,
                )
                # Route to the shard owning this module (default shard when no
                # shard pool, or the module is unrouted — same fallback the SDK
                # native path uses).
                raw = await self._worker_call(mojo_payload, module)
                result_payload = parse_runtime_library_worker_response(
                    module,
                    function,
                    raw,
                    function_spec=function_spec,
                )
                has_error = False
                engine_used = "mojo"
                error_message = ""
        except ShardWorkerUnavailable as exc:
            logger.warning("runtime_shard_worker_unavailable", module=module, error=str(exc))
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_module",
                status="failed",
                target=target,
                request_id=request_id,
                engine_used="unavailable",
                latency_ms=latency_ms,
                success=False,
                error=f"compute_runtime_unavailable: {exc}",
            )
            return {
                "result_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unavailable",
                "success": False,
                "error": f"compute_runtime_unavailable: {exc}",
            }
        except MojoLibraryError as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_module",
                status="failed",
                target=target,
                request_id=request_id,
                engine_used="unavailable",
                latency_ms=latency_ms,
                success=False,
                error=f"{exc.code}: {exc.message}",
            )
            return {
                "result_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unavailable",
                "success": False,
                "error": f"{exc.code}: {exc.message}",
            }
        except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
            logger.warning("mojo_socket_unavailable", sock=self._mojo_sock, error=str(exc))
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            return {
                "result_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unavailable",
                "success": False,
                "error": (
                    "compute_runtime_unavailable: local Mojo runtime connection failed. "
                    "Start the daemon before executing runtime-owned modules."
                ),
            }
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
            error=error_message if has_error else "",
        )
        return {
            "result_json": json.dumps(result_payload),
            "latency_ms": latency_ms,
            "engine_used": engine_used,
            "success": not has_error,
            "error": error_message if has_error else "",
        }

    async def execute_query(
        self,
        request_json: str,
        request_id: str = "",
    ) -> dict[str, Any]:
        """
        Execute a query plan against the bundled worker's "query_execute" message
        type (`mojo/engine/query/plan.mojo`). Returns
        {"response_json", "latency_ms", "engine_used", "success", "error"}.

        `response_json` carries the engine's own answer, OR its own refusal
        (`{"error_code":..., "error_message":...}` -- an unknown table, a bad join
        key, an over-budget plan, etc.), verbatim -- both are a SUCCESSFUL round
        trip, so `success`/`error` here describe only whether the request reached
        and was answered by the engine, never whether the PLAN itself was accepted.
        A caller distinguishes a refused plan by `error_code` inside the decoded
        `response_json`, exactly as `packages/algenta/algenta/query.py`'s
        `run_query` already does talking to the bundled worker directly.
        """
        from apps.runtime.ledger import append_event

        task_id = request_id or f"task_{uuid.uuid4().hex}"

        try:
            payload = json.loads(request_json)
        except json.JSONDecodeError as exc:
            return {
                "response_json": "null",
                "latency_ms": 0.0,
                "engine_used": "unavailable",
                "success": False,
                "error": f"invalid_arguments: request_json is not valid JSON ({exc}).",
            }
        if not isinstance(payload, dict):
            return {
                "response_json": "null",
                "latency_ms": 0.0,
                "engine_used": "unavailable",
                "success": False,
                "error": "invalid_arguments: request_json must decode to a JSON object.",
            }
        # Forced, never trusted from the caller. This path bypasses
        # `mojo_library_runner`'s function-spec validation entirely, so nothing
        # else stands between an arbitrary "type" value and `main.mojo`'s own
        # dispatch -- including "shutdown", which would take down the shared
        # worker for every OTHER caller on this socket, not just this request.
        payload["type"] = "query_execute"

        # ── Credit check (local quota enforcement), same gate execute_module uses ──
        from apps.runtime.credits import consume_credit

        if not await consume_credit():
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_query",
                status="blocked",
                target="query_execute",
                request_id=request_id,
                engine_used="blocked",
                latency_ms=0.0,
                success=False,
                error="execution_quota_exhausted",
            )
            return {
                "response_json": "null",
                "latency_ms": 0.0,
                "engine_used": "blocked",
                "success": False,
                "error": (
                    "execution_quota_exhausted: no execution credits remaining. "
                    "The daemon will refresh automatically when the server is reachable, "
                    "or run `algenta login` to re-register."
                ),
            }

        append_event(
            task_id=task_id,
            surface="runtime",
            action="execute_query",
            status="started",
            target="query_execute",
            request_id=request_id,
        )
        t0 = time.monotonic()

        try:
            # Same gate semantics as execute_module: with a shard pool the
            # default worker is spawned/revived on demand by the pool.
            if self._shard_pool is None and not self._mojo_available():
                return {
                    "response_json": "null",
                    "latency_ms": round((time.monotonic() - t0) * 1000, 2),
                    "engine_used": "unavailable",
                    "success": False,
                    "error": (
                        "compute_runtime_unavailable: local Mojo runtime is "
                        "not available. Start the daemon with a compiled Mojo binary."
                    ),
                }
            # The query plane runs in the default shard.
            raw = await self._worker_call(payload, None)
        except ShardWorkerUnavailable as exc:
            logger.warning(
                "runtime_shard_worker_unavailable", target="query_execute", error=str(exc)
            )
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_query",
                status="failed",
                target="query_execute",
                request_id=request_id,
                engine_used="unavailable",
                latency_ms=latency_ms,
                success=False,
                error="compute_runtime_unavailable",
            )
            return {
                "response_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unavailable",
                "success": False,
                "error": f"compute_runtime_unavailable: {exc}",
            }
        except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
            logger.warning("mojo_socket_unavailable", sock=self._mojo_sock, error=str(exc))
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_query",
                status="failed",
                target="query_execute",
                request_id=request_id,
                engine_used="unavailable",
                latency_ms=latency_ms,
                success=False,
                error="compute_runtime_unavailable",
            )
            return {
                "response_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unavailable",
                "success": False,
                "error": (
                    "compute_runtime_unavailable: local Mojo runtime connection failed. "
                    "Start the daemon before executing a query."
                ),
            }
        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            append_event(
                task_id=task_id,
                surface="runtime",
                action="execute_query",
                status="failed",
                target="query_execute",
                request_id=request_id,
                engine_used="unknown",
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )
            return {
                "response_json": "null",
                "latency_ms": latency_ms,
                "engine_used": "unknown",
                "success": False,
                "error": str(exc),
            }

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        engine_error = raw.get("error_code") if isinstance(raw, dict) else None
        append_event(
            task_id=task_id,
            surface="runtime",
            action="execute_query",
            status="completed" if not engine_error else "refused",
            target="query_execute",
            request_id=request_id,
            engine_used="mojo",
            latency_ms=latency_ms,
            success=True,
            error=str(engine_error or ""),
        )
        return {
            "response_json": json.dumps(raw),
            "latency_ms": latency_ms,
            "engine_used": "mojo",
            "success": True,
            "error": "",
        }

    def list_modules(self) -> list[dict[str, object]]:
        """Return runtime-executable modules with their functions and engine availability."""
        result: list[dict[str, Any]] = []
        sim_engine_state = "mojo" if self._mojo_available() else "unavailable"
        library_engine_state = (
            "mojo"
            if self._mojo_available() and self._library_runtime_available()
            else "unavailable"
        )

        for name in _SIMULATION_ENGINES:
            result.append({"name": name, "engine": sim_engine_state, "functions": ["run"]})

        for module in self._list_runtime_library_modules():
            result.append(
                {
                    "name": module.import_path,
                    "engine": library_engine_state,
                    "functions": [function.name for function in module.functions],
                }
            )

        result.sort(key=lambda entry: entry["name"])
        return result
