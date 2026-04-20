"""
gRPC server — implements AlgentaRuntime service over unix socket / TCP loopback.

Socket path:  /tmp/algenta-runtime/daemon.sock   (unix, macOS/Linux)
TCP fallback: 127.0.0.1:50099                    (Windows / explicit override)

Usage (internal — called by daemon.py):
    server = RuntimeServer(executor, entitlement_fn)
    await server.start()
    await server.wait_for_termination()
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import grpc
import grpc.aio
import structlog

from apps.runtime.entitlement import check_entitlement, is_module_permitted
from apps.runtime.executor import Executor
from apps.runtime.metering import UsageEvent, metering
from apps.runtime.proto import runtime_pb2, runtime_pb2_grpc

logger = structlog.get_logger(__name__)

_DEFAULT_DAEMON_SOCK = str(Path(tempfile.gettempdir()) / "algenta-runtime" / "daemon.sock")
_DAEMON_SOCK = os.environ.get(
    "ALGENTA_DAEMON_SOCK",
    _DEFAULT_DAEMON_SOCK,
)
_DAEMON_TCP = os.environ.get("ALGENTA_DAEMON_TCP", "127.0.0.1:50099")
_RUNTIME_VERSION = "0.1.0"


class _AlgentaRuntimeServicer(runtime_pb2_grpc.AlgentaRuntimeServicer):
    """Concrete implementation of the AlgentaRuntime gRPC service."""

    def __init__(self, executor: Executor, start_time: float) -> None:
        self._executor = executor
        self._start_time = start_time

    # ── Health ────────────────────────────────────────────────────────────────

    async def Health(  # noqa: N802
        self,
        request: runtime_pb2.HealthRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.HealthResponse:
        uptime = time.monotonic() - self._start_time
        engine = "mojo" if self._executor._mojo_available() else "python-fallback"
        metering.record(UsageEvent(event_type="health", engine_used=engine))
        return runtime_pb2.HealthResponse(
            ok=True,
            version=_RUNTIME_VERSION,
            uptime_seconds=uptime,
            engine=engine,
        )

    # ── RuntimeInfo ───────────────────────────────────────────────────────────

    async def GetRuntimeInfo(  # noqa: N802
        self,
        request: runtime_pb2.RuntimeInfoRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.RuntimeInfoResponse:
        uptime = time.monotonic() - self._start_time
        modules = self._executor.list_modules()
        mojo_ok = self._executor._mojo_available()
        mojo_bin = os.environ.get(
            "ALGENTA_MOJO_BINARY",
            str((os.path.dirname(__file__) + "/../../mojo_build/simulate").replace("//", "/")),
        )
        return runtime_pb2.RuntimeInfoResponse(
            version=_RUNTIME_VERSION,
            engine="mojo" if mojo_ok else "python-fallback",
            module_count=len(modules),
            uptime_seconds=uptime,
            socket_path=_DAEMON_SOCK,
            mojo_binary_path=mojo_bin,
            mojo_available=mojo_ok,
        )

    # ── ListModules ───────────────────────────────────────────────────────────

    async def ListModules(  # noqa: N802
        self,
        request: runtime_pb2.ListModulesRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.ListModulesResponse:
        modules = self._executor.list_modules()
        return runtime_pb2.ListModulesResponse(
            modules=[
                runtime_pb2.ModuleInfo(
                    name=m["name"],
                    engine=m["engine"],
                    functions=m["functions"],
                )
                for m in modules
            ]
        )

    # ── ExecuteModule ─────────────────────────────────────────────────────────

    async def ExecuteModule(  # noqa: N802
        self,
        request: runtime_pb2.ExecuteRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.ExecuteResponse:
        entitlement = check_entitlement()
        if not is_module_permitted(request.module, entitlement):
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                (
                    f"Module '{request.module}' not permitted under current "
                    f"entitlement tier '{entitlement.tier}'."
                ),
            )

        try:
            args = json.loads(request.args_json) if request.args_json else []
        except json.JSONDecodeError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "args_json is not valid JSON.")

        result = await self._executor.execute_module(
            module=request.module,
            function=request.function,
            args=args,
            request_id=request.request_id,
        )
        metering.record(UsageEvent(
            event_type="execute_module",
            module=request.module,
            function=request.function,
            engine_used=result["engine_used"],
            latency_ms=result["latency_ms"],
            success=result["success"],
            request_id=request.request_id,
        ))
        return runtime_pb2.ExecuteResponse(
            result_json=result["result_json"],
            latency_ms=result["latency_ms"],
            engine_used=result["engine_used"],
            success=result["success"],
            error=result["error"],
            request_id=request.request_id,
        )

    # ── VerifyAndExecute ──────────────────────────────────────────────────────

    async def VerifyAndExecute(  # noqa: N802
        self,
        request: runtime_pb2.VerifyAndExecuteRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.VerifyAndExecuteResponse:
        """
        Hot-path RPC: verify plan → execute — all local, no cloud round-trip.

        v1: delegates to the existing FastAPI query engine via in-process call.
        v2+: inlined execution without HTTP overhead.
        """
        t0 = time.monotonic()

        # Import here to avoid circular dependency at module load time
        from apps.api_server.routers.query import QueryRequest

        try:
            if request.join_source_name:
                raise RuntimeError(
                    "Legacy runtime join_source_name is no longer supported; "
                    "/v1/query now requires join_path."
                )
            query_payload = QueryRequest(
                source_name=request.source_name,
                metric_column=request.metric_column,
                aggregation=request.aggregation,
                group_column=request.group_column or None,
                limit=request.limit or None,
                order=request.order or "desc",
            )

            # Import and call query_sources inline (no HTTP round-trip)

            from apps.api_server.routers.query import router as query_router  # noqa: F401

            # Find the query endpoint function
            for route in query_router.routes:  # type: ignore[attr-defined]
                if hasattr(route, "path") and route.path == "/v1/query":
                    endpoint_fn = route.endpoint
                    break
            else:
                raise RuntimeError("Could not find /v1/query endpoint")

            # Call with stub org context
            resp = await endpoint_fn(payload=query_payload, org_id="local-dev")
            latency_ms = round((time.monotonic() - t0) * 1000, 2)

            result_json = json.dumps(resp.result) if resp.result is not None else "null"
            metering.record(UsageEvent(
                event_type="verify_and_execute",
                engine_used="query-engine",
                latency_ms=latency_ms,
                success=True,
                request_id=request.request_id,
            ))
            return runtime_pb2.VerifyAndExecuteResponse(
                valid=True,
                errors=[],
                result_json=result_json,
                result_type=resp.result_type or "scalar",
                confidence=resp.confidence or 0.0,
                exact_spec=resp.exact_spec or False,
                latency_ms=latency_ms,
                engine_used="query-engine",
                request_id=request.request_id,
            )

        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            logger.error("verify_and_execute_error", error=str(exc))
            return runtime_pb2.VerifyAndExecuteResponse(
                valid=False,
                errors=[str(exc)],
                result_json="null",
                result_type="none",
                confidence=0.0,
                exact_spec=False,
                latency_ms=latency_ms,
                engine_used="error",
                request_id=request.request_id,
            )

    # ── Entitlement ───────────────────────────────────────────────────────────

    async def GetEntitlementStatus(  # noqa: N802
        self,
        request: runtime_pb2.EntitlementRequest,
        context: grpc.aio.ServicerContext,
    ) -> runtime_pb2.EntitlementResponse:
        ent = check_entitlement()
        return runtime_pb2.EntitlementResponse(
            valid=ent.valid,
            tier=ent.tier,
            permitted_modules=ent.permitted_modules,
            expires_at=ent.expires_at,
            message=ent.message,
            device_id=ent.device_id[:8] if ent.device_id else "",
            device_limit=ent.device_limit,
            source="",   # v1: populated in v3 when cloud license is real
        )


# ── Server lifecycle ──────────────────────────────────────────────────────────

class RuntimeServer:
    """Wraps the gRPC aio server with start/stop lifecycle."""

    def __init__(self, executor: Executor, start_time: float) -> None:
        self._executor = executor
        self._start_time = start_time
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        self._server = grpc.aio.server()
        runtime_pb2_grpc.add_AlgentaRuntimeServicer_to_server(
            _AlgentaRuntimeServicer(self._executor, self._start_time),
            self._server,
        )

        # Primary: unix socket
        sock_dir = Path(_DAEMON_SOCK).parent
        sock_dir.mkdir(parents=True, exist_ok=True)

        # Remove stale socket file
        sock_path = Path(_DAEMON_SOCK)
        if sock_path.exists():
            sock_path.unlink()

        self._server.add_insecure_port(f"unix://{_DAEMON_SOCK}")

        # Secondary: TCP loopback (always bind — used by Windows and explicit overrides)
        self._server.add_insecure_port(_DAEMON_TCP)

        await self._server.start()
        logger.info(
            "daemon_started",
            unix_sock=_DAEMON_SOCK,
            tcp=_DAEMON_TCP,
            version=_RUNTIME_VERSION,
        )

    async def stop(self, grace: float = 5.0) -> None:
        if self._server:
            await self._server.stop(grace)
            logger.info("daemon_stopped")

    async def wait_for_termination(self) -> None:
        if self._server:
            await self._server.wait_for_termination()
