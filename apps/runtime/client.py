"""
gRPC client for the Algenta local runtime daemon.

Provides async methods that map directly to the AlgentaRuntime gRPC RPCs.
Used exclusively by sdk.py — not part of the public API.

Connection:
  1. Unix socket  /tmp/algenta-runtime/daemon.sock  (macOS/Linux)
  2. TCP loopback 127.0.0.1:50099                   (Windows / fallback)

The client is stateless — each method creates a short-lived channel.
A persistent channel with keep-alive is planned for v2 (connection pool).
"""
from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_DAEMON_SOCK = os.environ.get("ALGENTA_DAEMON_SOCK", "/tmp/algenta-runtime/daemon.sock")
_DAEMON_TCP  = os.environ.get("ALGENTA_DAEMON_TCP",  "127.0.0.1:50099")
_DEFAULT_TIMEOUT = 30.0


class DaemonClient:
    """
    Thin async gRPC client for the local runtime daemon.

    Usage:
        client = DaemonClient()
        result = await client.execute("monte_carlo", "run", {"trials": 50000})
        await client.close()

    Or as a context manager:
        async with DaemonClient() as c:
            result = await c.execute("monte_carlo", "run", config)
    """

    def __init__(
        self,
        sock_path: str = _DAEMON_SOCK,
        tcp_addr:  str = _DAEMON_TCP,
        timeout:   float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._sock_path = sock_path
        self._tcp_addr  = tcp_addr
        self._timeout   = timeout
        self._channel   = None

    # ── Connection management ─────────────────────────────────────────────────

    def _make_channel(self):
        from pathlib import Path

        import grpc
        if Path(self._sock_path).exists():
            target = f"unix://{self._sock_path}"
        else:
            target = self._tcp_addr
        return grpc.aio.insecure_channel(target)

    async def connect(self) -> None:
        """Open a persistent channel (optional — RPCs auto-connect if not called)."""
        self._channel = self._make_channel()
        await self._channel.channel_ready()

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()
            self._channel = None

    async def __aenter__(self) -> DaemonClient:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    def _stub(self):
        from apps.runtime.proto import runtime_pb2_grpc
        ch = self._channel or self._make_channel()
        return runtime_pb2_grpc.AlgentaRuntimeStub(ch)

    # ── RPCs ──────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        """Returns {"status", "uptime_s", "version", "mojo_available"}."""
        import grpc

        from apps.runtime.proto import runtime_pb2
        try:
            stub = self._stub()
            resp = await stub.Health(
                runtime_pb2.HealthRequest(),
                timeout=self._timeout,
            )
            return {
                "status":         resp.status,
                "uptime_s":       resp.uptime_s,
                "version":        resp.version,
                "mojo_available": resp.mojo_available,
            }
        except grpc.aio.AioRpcError as exc:
            return {"status": "unreachable", "error": str(exc.details())}

    async def execute(
        self,
        module:     str,
        function:   str,
        args:       Any = None,
        request_id: str = "",
    ) -> dict:
        """
        Execute module::function(args) on the local daemon.
        Returns {"result", "latency_ms", "engine_used", "success", "error"}.
        """
        import time

        import grpc

        from apps.runtime.proto import runtime_pb2

        args_json = json.dumps(args) if args is not None else "null"
        t0 = time.monotonic()
        try:
            stub = self._stub()
            resp = await stub.ExecuteModule(
                runtime_pb2.ExecuteRequest(
                    module=module,
                    function=function,
                    args_json=args_json,
                    request_id=request_id,
                ),
                timeout=self._timeout,
            )
            latency = round((time.monotonic() - t0) * 1000, 2)
            return {
                "result":      json.loads(resp.result_json) if resp.result_json else None,
                "latency_ms":  latency,
                "engine_used": resp.engine_used,
                "success":     resp.success,
                "error":       resp.error or "",
            }
        except grpc.aio.AioRpcError as exc:
            latency = round((time.monotonic() - t0) * 1000, 2)
            return {
                "result":      None,
                "latency_ms":  latency,
                "engine_used": "grpc-error",
                "success":     False,
                "error":       f"gRPC error {exc.code()}: {exc.details()}",
            }

    async def list_modules(self) -> list[dict]:
        """Return all available modules with their functions."""
        import grpc

        from apps.runtime.proto import runtime_pb2
        try:
            stub = self._stub()
            resp = await stub.ListModules(
                runtime_pb2.ListModulesRequest(),
                timeout=self._timeout,
            )
            return [
                {
                    "name":      m.name,
                    "engine":    m.engine,
                    "functions": list(m.functions),
                }
                for m in resp.modules
            ]
        except grpc.aio.AioRpcError as exc:
            logger.warning("list_modules_grpc_error", error=str(exc.details()))
            return []

    async def entitlement(self) -> dict:
        """Return current entitlement status from the daemon."""
        import grpc

        from apps.runtime.proto import runtime_pb2
        try:
            stub = self._stub()
            resp = await stub.GetEntitlementStatus(
                runtime_pb2.EntitlementRequest(),
                timeout=self._timeout,
            )
            return {
                "valid":              resp.valid,
                "tier":               resp.tier,
                "permitted_modules":  list(resp.permitted_modules),
                "expires_at":         resp.expires_at,
                "device_id":          resp.device_id,
                "device_limit":       resp.device_limit,
                "source":             resp.source,
                "message":            resp.message,
            }
        except grpc.aio.AioRpcError as exc:
            return {"valid": False, "error": str(exc.details())}

    # ── Availability check ────────────────────────────────────────────────────

    @classmethod
    def is_daemon_running(
        cls,
        sock_path: str = _DAEMON_SOCK,
        tcp_addr:  str = _DAEMON_TCP,
    ) -> bool:
        """
        Quick sync check — does the daemon socket / TCP port exist?
        Does NOT verify the process is healthy — use health() for that.
        """
        import socket
        from pathlib import Path
        if Path(sock_path).exists():
            return True
        # Try TCP fallback
        host, port = tcp_addr.rsplit(":", 1)
        try:
            s = socket.create_connection((host, int(port)), timeout=0.5)
            s.close()
            return True
        except OSError:
            return False
