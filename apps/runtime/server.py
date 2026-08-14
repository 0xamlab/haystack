"""
gRPC server — implements CodnaRuntime service over unix socket / TCP loopback.

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
import uuid
from pathlib import Path
from typing import Any

import grpc
import grpc.aio
import structlog

from apps.api_server.services.auth_service import AuthContext
from apps.runtime.entitlement import check_entitlement, is_module_permitted
from apps.runtime.executor import Executor
from apps.runtime.metering import UsageEvent, metering
from apps.runtime.proto import runtime_pb2, runtime_pb2_grpc
from apps.runtime.worker_broker import worker_slot

logger = structlog.get_logger(__name__)
runtime_pb2_module: Any = runtime_pb2
runtime_pb2_grpc_module: Any = runtime_pb2_grpc

_DEFAULT_DAEMON_SOCK = str(Path(tempfile.gettempdir()) / "algenta-runtime" / "daemon.sock")
_DAEMON_SOCK = os.environ.get(
    "ALGENTA_DAEMON_SOCK",
    _DEFAULT_DAEMON_SOCK,
)
_DAEMON_TCP = os.environ.get("ALGENTA_DAEMON_TCP", "127.0.0.1:50099")
_RUNTIME_VERSION = "0.1.0"


class _CodnaRuntimeServicer(runtime_pb2_grpc_module.CodnaRuntimeServicer):  # type: ignore[misc]
    """Concrete implementation of the CodnaRuntime gRPC service."""

    def __init__(self, executor: Executor, start_time: float) -> None:
        self._executor = executor
        self._start_time = start_time

    # ── Health ────────────────────────────────────────────────────────────────

    async def Health(  # noqa: N802
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        uptime = time.monotonic() - self._start_time
        engine = (
            "mojo"
            if self._executor._library_runtime_available() and self._executor._mojo_available()
            else "unavailable"
        )
        metering.record(UsageEvent(event_type="health", engine_used=engine))
        return runtime_pb2_module.HealthResponse(
            ok=True,
            version=_RUNTIME_VERSION,
            uptime_seconds=uptime,
            engine=engine,
        )

    # ── RuntimeInfo ───────────────────────────────────────────────────────────

    async def GetRuntimeInfo(  # noqa: N802
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        uptime = time.monotonic() - self._start_time
        modules = self._executor.list_modules()
        mojo_ok = self._executor._library_runtime_available() and self._executor._mojo_available()
        mojo_bin = os.environ.get(
            "ALGENTA_MOJO_BINARY",
            str((os.path.dirname(__file__) + "/../../mojo_build/simulate").replace("//", "/")),
        )
        return runtime_pb2_module.RuntimeInfoResponse(
            version=_RUNTIME_VERSION,
            engine="mojo" if mojo_ok else "unavailable",
            module_count=len(modules),
            uptime_seconds=uptime,
            socket_path=_DAEMON_SOCK,
            mojo_binary_path=mojo_bin,
            mojo_available=mojo_ok,
        )

    # ── ListModules ───────────────────────────────────────────────────────────

    async def ListModules(  # noqa: N802
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        modules = self._executor.list_modules()
        return runtime_pb2_module.ListModulesResponse(
            modules=[
                runtime_pb2_module.ModuleInfo(
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
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
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

        # Hold one licensed worker slot for the execution. Dark by default: a license
        # with concurrent_worker_limit==0 (the current default) makes this a no-op;
        # a license with a real cap bounds this node's concurrent executions (excess
        # callers queue here until a slot frees).
        async with worker_slot():
            result = await self._executor.execute_module(
                module=request.module,
                function=request.function,
                args=args,
                request_id=request.request_id,
            )
        metering.record(
            UsageEvent(
                event_type="execute_module",
                module=request.module,
                function=request.function,
                engine_used=result["engine_used"],
                latency_ms=result["latency_ms"],
                success=result["success"],
                request_id=request.request_id,
            )
        )
        return runtime_pb2_module.ExecuteResponse(
            result_json=result["result_json"],
            latency_ms=result["latency_ms"],
            engine_used=result["engine_used"],
            success=result["success"],
            error=result["error"],
            request_id=request.request_id,
        )

    # ── ExecuteQuery ──────────────────────────────────────────────────────────

    async def ExecuteQuery(  # noqa: N802
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """Execute a query plan (`query/plan.mojo`'s `query_execute` op).

        Gated the same way `ExecuteModule` is — `is_module_permitted` was already a
        flat capability-name check, not specifically a Mojo-module-name one, so
        `"query_execute"` (the same name `apps/runtime/mojo_capability_manifest.py`'s
        `SURFACES` already lists) slots in as the capability being permitted, with no
        change to the entitlement system itself.
        """
        entitlement = check_entitlement()
        if not is_module_permitted("query_execute", entitlement):
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                (
                    "Query execution not permitted under current entitlement tier "
                    f"'{entitlement.tier}'."
                ),
            )

        if not request.request_json:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "request_json is required.")

        async with worker_slot():
            result = await self._executor.execute_query(
                request_json=request.request_json,
                request_id=request.request_id,
            )
        metering.record(
            UsageEvent(
                event_type="execute_query",
                module="query",
                engine_used=result["engine_used"],
                latency_ms=result["latency_ms"],
                success=result["success"],
                request_id=request.request_id,
            )
        )
        return runtime_pb2_module.QueryExecuteResponse(
            response_json=result["response_json"],
            latency_ms=result["latency_ms"],
            engine_used=result["engine_used"],
            success=result["success"],
            error=result["error"],
            request_id=request.request_id,
        )

    # ── VerifyAndExecute ──────────────────────────────────────────────────────

    async def VerifyAndExecute(  # noqa: N802
        self,
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        """
        Hot-path RPC: verify plan → execute — all local, no cloud round-trip.

        v1: delegates to the existing FastAPI query engine via in-process call.
        v2+: inlined execution without HTTP overhead.
        """
        t0 = time.monotonic()

        local_auth_context: AuthContext = {
            "org_id": uuid.UUID(int=0),
            "key_id": uuid.UUID(int=0),
            "key_prefix": "local-runtime",
            "user_id": None,
            "plan": "developer",
            "device_limit": 0,
            "device_limit_configured": False,
            "role": "owner",
            "email": "local-runtime@algenta.local",
        }

        # Import here to avoid circular dependency at module load time
        from apps.api_server.routers.query import query_sources
        from apps.api_server.routers.query_contract import QueryRequest

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

            # Hold a licensed worker slot for this execution too — VerifyAndExecute reaches the same
            # in-proc query engine as ExecuteQuery, so it must be under the same concurrency cap
            # (else it's a way around the worker limit). Dark when concurrent_worker_limit==0.
            async with worker_slot():
                resp = await query_sources(
                    payload=query_payload,
                    auth=local_auth_context,
                )
            latency_ms = round((time.monotonic() - t0) * 1000, 2)

            result_json = json.dumps(resp.result) if resp.result is not None else "null"
            metering.record(
                UsageEvent(
                    event_type="verify_and_execute",
                    engine_used="query-engine",
                    latency_ms=latency_ms,
                    success=True,
                    request_id=request.request_id,
                )
            )
            return runtime_pb2_module.VerifyAndExecuteResponse(
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
            return runtime_pb2_module.VerifyAndExecuteResponse(
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
        request: Any,
        context: grpc.aio.ServicerContext,
    ) -> Any:
        ent = check_entitlement()
        return runtime_pb2_module.EntitlementResponse(
            valid=ent.valid,
            tier=ent.tier,
            permitted_modules=ent.permitted_modules,
            expires_at=ent.expires_at,
            message=ent.message,
            device_id=ent.device_id[:8] if ent.device_id else "",
            device_limit=ent.device_limit,
            source="",  # v1: populated in v3 when cloud license is real
        )


# ── Server lifecycle ──────────────────────────────────────────────────────────


class RuntimeServer:
    """Wraps the gRPC aio server with start/stop lifecycle."""

    def __init__(self, executor: Executor, start_time: float) -> None:
        self._executor = executor
        self._start_time = start_time
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        # Offline node-cap L2: for shared-token clusters, count peers via the customer's own coordination
        # Redis and refuse the node past active_node_limit (fail closed BEFORE we bind/serve). No-op unless
        # enforcing + ALGENTA_ENFORCE_PEER_NODE_CAP + a reachable backend; bound tokens are already L1-gated.
        from apps.runtime import node_broker

        await node_broker.admit_node_and_start_heartbeat()

        self._server = grpc.aio.server()
        runtime_pb2_grpc_module.add_CodnaRuntimeServicer_to_server(
            _CodnaRuntimeServicer(self._executor, self._start_time),
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
        from apps.runtime import node_broker

        await node_broker.stop_node_census_heartbeat()  # release this node's census slot immediately
        if self._server:
            await self._server.stop(grace)
            logger.info("daemon_stopped")

    async def wait_for_termination(self) -> None:
        if self._server:
            await self._server.wait_for_termination()
