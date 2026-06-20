"""
Algenta Python SDK — Runtime class.

Public surface for executing domain libraries and simulation engines.

Modes:
  "auto"   — local daemon if running, else cloud (default)
  "local"  — always use local daemon (auto-start if needed)
  "cloud"  — always use cloud REST API
  "direct" — in-process executor (no daemon; for testing / scripting)

Usage:
    from apps.runtime.sdk import Runtime

    rt = Runtime(api_key="<YOUR_ALGENTA_API_KEY>")  # Cloud Managed example

    # `self_hosted` and `air_gapped` accept ALGENTA_API_KEY / DE_API_KEY too,
    # but they must use an explicit self-hosted base_url or
    # ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL and fail closed if that
    # is missing.

    # Execute a domain library function
    result = rt.execute("scheduling_algo", "fcfs", {"jobs": [...]})

    # Run a simulation engine
    result = rt.simulate("monte_carlo", {"trials": 50000, "mean": 0.08})

    # Async API
    result = await rt.aexecute("recommender", "cosine_sim_users", args)

Sync methods (execute, simulate, health, list_modules) are safe to call
from any context — they manage their own event loop.

Async methods (aexecute, asimulate, ahealth, alist_modules) must be awaited
inside an existing event loop (e.g., FastAPI handlers, async scripts).
"""

from __future__ import annotations

import asyncio
import builtins
import os
import time
from collections.abc import Awaitable
from contextlib import suppress
from typing import Any, cast
from urllib.parse import urlparse

import structlog

from apps.privacy_policy import is_algenta_owned_destination, policy_from_environment
from apps.platform_contract_constants import API_BASE_URL
from apps.runtime.privacy_guard import (
    RuntimeEgressPolicyDeniedError,
    runtime_http_request,
    validated_runtime_egress_url,
)

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT = 30.0

# Simulation engines — these can go to cloud /v1/simulate
_SIM_ENGINES = frozenset(
    {
        "monte_carlo",
        "scenario",
        "bootstrap",
        "sensitivity",
        "decision_tree",
        "time_series",
        "mcmc",
        "lhs",
        "qmc_sobol",
        "importance_sampling",
    }
)


class SDKRuntimeError(Exception):
    """Raised when execution fails and no result is available."""


# Backwards-compatible export for callers that imported RuntimeError
RuntimeError = SDKRuntimeError


class Runtime:
    """
    Algenta execution runtime.

    Single entry point for all local and cloud execution.
    Thread-safe. Sync methods create a new event loop per call.

    Parameters
    ----------
    api_key:
        Algenta API key. Defaults to ALGENTA_API_KEY or DE_API_KEY env var.
    mode:
        Execution mode: "auto" | "local" | "cloud" | "direct"
    timeout:
        Per-request timeout in seconds.
    auto_start_daemon:
        If True (default) and mode is "local" or "auto", start the daemon
        automatically if it isn't running.
    base_url:
        Cloud API base URL. Reads explicit base_url, ALGENTA_BASE_URL,
        DE_BASE_URL, or ALGENTA_API_URL. Cloud Managed falls back to the
        canonical Algenta API URL only when private-profile policy allows it;
        self-hosted private profiles must use an explicit self-hosted base URL.
    """

    def __init__(
        self,
        api_key: str = "",
        mode: str = "auto",
        timeout: float = _DEFAULT_TIMEOUT,
        auto_start_daemon: bool = True,
        base_url: str = "",
    ) -> None:
        self._api_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        explicit_base_url = (base_url or _configured_cloud_api_url()).rstrip("/")
        self._base_url_explicit = bool(explicit_base_url)
        privacy_policy = policy_from_environment()
        self._mode = mode
        self._timeout = timeout
        self._auto_start = auto_start_daemon
        self._base_url = (
            explicit_base_url or ("" if privacy_policy.disable_cloud else _cloud_api_url())
        )

        if mode not in ("auto", "local", "cloud", "direct"):
            raise ValueError(f"Invalid mode '{mode}'. Use: auto | local | cloud | direct")
        if self._base_url and (self._base_url_explicit or mode == "cloud"):
            self._validated_cloud_base_url(surface="sdk_cloud_config", record=False)

    # ── Sync public API ───────────────────────────────────────────────────────

    def execute(
        self,
        module: str,
        function: str,
        args: Any = None,
    ) -> dict[str, Any]:
        """
        Execute module::function(args) and return the result.

        Returns a dict with keys: result, latency_ms, engine_used, success, error.
        Raises RuntimeError on hard failures (auth error, module not found, etc.)
        """
        return cast(dict[str, Any], _run(self.aexecute(module, function, args)))

    def simulate(self, engine: str, config: dict[str, Any]) -> dict[str, Any]:
        """Shorthand for simulation engines: simulate("monte_carlo", config)."""
        return self.execute(engine, "run", config)

    def health(self) -> dict[str, Any]:
        """Check daemon / cloud API health."""
        return cast(dict[str, Any], _run(self.ahealth()))

    def list_modules(self) -> list[dict[str, Any]]:
        """List all available modules and their functions."""
        return cast(list[dict[str, Any]], _run(self.alist_modules()))

    # ── Async public API ──────────────────────────────────────────────────────

    async def aexecute(
        self,
        module: str,
        function: str,
        args: Any = None,
    ) -> dict[str, Any]:
        mode = self._resolve_mode(module)

        if mode == "local":
            return await self._local_execute(module, function, args)
        elif mode == "cloud":
            return await self._cloud_execute(module, function, args)
        else:  # "direct"
            return await self._direct_execute(module, function, args)

    async def asimulate(self, engine: str, config: dict[str, Any]) -> dict[str, Any]:
        return await self.aexecute(engine, "run", config)

    async def ahealth(self) -> dict[str, Any]:
        mode = self._resolve_mode("")
        if mode in ("local", "auto"):
            from apps.runtime.client import DaemonClient

            client = DaemonClient(timeout=self._timeout)
            return await client.health()
        return await self._cloud_health()

    async def alist_modules(self) -> list[dict[str, Any]]:
        mode = self._resolve_mode("")
        if mode == "cloud":
            return _CLOUD_MODULE_LIST
        from apps.runtime.client import DaemonClient

        client = DaemonClient(timeout=self._timeout)
        modules = await client.list_modules()
        return [dict(module) for module in modules] if modules else _CLOUD_MODULE_LIST

    # ── Mode resolution ───────────────────────────────────────────────────────

    def _resolve_mode(self, module: str) -> str:
        """Decide which execution path to use for this request."""
        if self._mode == "direct":
            return "direct"
        if self._mode == "cloud":
            return "cloud"
        if self._mode == "local":
            return "local"

        # "auto" — prefer local if daemon is running
        from apps.runtime.client import DaemonClient

        if DaemonClient.is_daemon_running():
            return "local"
        # Domain libraries require local runtime
        if module and module not in _SIM_ENGINES:
            logger.warning(
                "sdk_domain_library_no_daemon",
                module=module,
                hint=(
                    "Domain libraries require the local daemon. "
                    "Run: python -m apps.runtime.daemon start"
                ),
            )
        if not self._base_url:
            raise SDKRuntimeError(
                "Algenta cloud fallback is disabled in this deployment profile. "
                "Start the local daemon or set an explicit self-hosted base URL."
            )
        self._validated_cloud_base_url(surface="sdk_cloud_resolve", record=False)
        return "cloud"

    # ── Local execution ───────────────────────────────────────────────────────

    async def _local_execute(
        self,
        module: str,
        function: str,
        args: Any,
    ) -> dict[str, Any]:
        from apps.runtime.client import DaemonClient

        # Auto-start daemon if not running
        if not DaemonClient.is_daemon_running():
            if self._auto_start:
                await self._start_daemon()
            else:
                return {
                    "result": None,
                    "latency_ms": 0.0,
                    "engine_used": "none",
                    "success": False,
                    "error": (
                        "Local daemon is not running. "
                        "Start it with: python -m apps.runtime.daemon start"
                    ),
                }

        client = DaemonClient(timeout=self._timeout)
        return await client.execute(module, function, args)

    async def _start_daemon(self) -> None:
        """Start the daemon in the background and wait until it is reachable."""
        try:
            from apps.runtime.daemon import cmd_start

            env_updates = _daemon_bootstrap_env(api_key=self._api_key, base_url=self._base_url)

            previous = {key: os.environ.get(key) for key in env_updates}
            try:
                os.environ.update(env_updates)
                cmd_start(foreground=False)
            finally:
                for key, old_value in previous.items():
                    if old_value is None:
                        with suppress(KeyError):
                            del os.environ[key]
                    else:
                        os.environ[key] = old_value
            from apps.runtime.client import DaemonClient

            wait_timeout_s = max(15.0, min(self._timeout, 30.0))
            deadline = time.monotonic() + wait_timeout_s
            while time.monotonic() < deadline:
                if DaemonClient.is_daemon_running():
                    health = await DaemonClient(
                        timeout=min(self._timeout, 5.0),
                    ).health()
                    if health.get("status") != "unreachable":
                        logger.info("sdk_daemon_auto_started", status=health.get("status"))
                        return
                await asyncio.sleep(0.25)
            logger.warning("sdk_daemon_start_timeout", timeout_s=wait_timeout_s)
        except Exception as exc:
            logger.warning("sdk_daemon_auto_start_failed", error=str(exc))

    # ── Cloud execution ───────────────────────────────────────────────────────

    async def _cloud_execute(
        self,
        module: str,
        function: str,
        args: Any,
    ) -> dict[str, Any]:
        if not self._base_url:
            return {
                "result": None,
                "latency_ms": 0.0,
                "engine_used": "cloud-disabled",
                "success": False,
                "error": (
                    "Cloud execution is disabled in this deployment profile. "
                    "Set an explicit self-hosted base URL or run the local daemon."
                ),
            }
        # shape-validate only; runtime_http_request below is the single enforce + audit point
        base_url = self._validated_cloud_base_url(surface="sdk_cloud_execute", record=False)
        if module not in _SIM_ENGINES:
            return {
                "result": None,
                "latency_ms": 0.0,
                "engine_used": "cloud-unavailable",
                "success": False,
                "error": (
                    f"Domain library '{module}' requires the local runtime. "
                    "Install and start the daemon: python -m apps.runtime.daemon start"
                ),
            }

        # Map to cloud /v1/simulate payload
        config = args if isinstance(args, dict) else {}
        config.setdefault("simulation_model", module)

        t0 = time.monotonic()
        try:
            # B10: route the cloud simulate POST through the approved runtime egress wrapper
            # (enforce-before-dispatch, fail-closed); base_url was validated above.
            resp = await runtime_http_request(
                method="POST",
                url=f"{base_url}/v1/simulate",
                surface="sdk_cloud_execute",
                headers=self._auth_headers(),
                json=config,
                client_kwargs={"timeout": self._timeout},
            )
            latency = round((time.monotonic() - t0) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "result": data,
                    "latency_ms": data.get("execution_ms", latency),
                    "engine_used": "cloud",
                    "success": True,
                    "error": "",
                }
            else:
                detail = resp.json().get("error", {})
                return {
                    "result": None,
                    "latency_ms": latency,
                    "engine_used": "cloud",
                    "success": False,
                    "error": detail.get("message", f"HTTP {resp.status_code}"),
                }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 2)
            return {
                "result": None,
                "latency_ms": latency,
                "engine_used": "cloud-error",
                "success": False,
                "error": str(exc),
            }

    async def _cloud_health(self) -> dict[str, Any]:
        if not self._base_url:
            return {
                "status": "unreachable",
                "error": (
                    "Cloud health is disabled in this deployment profile. "
                    "Set an explicit self-hosted base URL or run the local daemon."
                ),
            }
        # shape-validate only; runtime_http_request below is the single enforce + audit point
        base_url = self._validated_cloud_base_url(surface="sdk_cloud_health", record=False)
        try:
            # B10: route the cloud health GET through the approved runtime egress wrapper.
            resp = await runtime_http_request(
                method="GET",
                url=f"{base_url}/health",
                surface="sdk_cloud_health",
                headers=self._auth_headers(),
                client_kwargs={"timeout": 5.0},
            )
            if resp.status_code == 200:
                payload = resp.json()
                return payload if isinstance(payload, dict) else {"status": "error", "code": 500}
            return {"status": "error", "code": resp.status_code}
        except Exception as exc:
            return {"status": "unreachable", "error": str(exc)}

    # ── Direct (in-process) execution ─────────────────────────────────────────

    async def _direct_execute(
        self,
        module: str,
        function: str,
        args: Any,
    ) -> dict[str, Any]:
        """Execute directly in-process via Executor (no daemon needed)."""
        from apps.runtime.executor import Executor

        executor = Executor()
        return await executor.execute_module(module, function, args)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _validated_cloud_base_url(
        self,
        *,
        surface: str,
        record: bool = True,
    ) -> str:
        normalized = self._base_url.rstrip("/")
        if not normalized:
            raise SDKRuntimeError(
                "Algenta cloud fallback is disabled in this deployment profile. "
                "Start the local daemon or set an explicit self-hosted base URL."
            )
        parsed = urlparse(normalized)
        egress_class = (
            "algenta_cloud"
            if parsed.hostname and is_algenta_owned_destination(parsed.hostname)
            else "operator_service"
        )
        try:
            return validated_runtime_egress_url(
                normalized,
                surface=surface,
                field_name="Runtime base_url",
                explicit_configured=self._base_url_explicit,
                egress_class=egress_class,
                record=record,
            )
        except RuntimeEgressPolicyDeniedError as exc:
            raise SDKRuntimeError(
                "Runtime base_url is blocked by the active privacy policy. "
                f"Reason: {exc.decision.reason}."
            ) from exc
        except ValueError as exc:
            raise SDKRuntimeError(str(exc)) from exc

    def __repr__(self) -> str:
        return (
            f"Runtime(mode={self._mode!r}, "
            f"api_key={'set' if self._api_key else 'not set'}, "
            f"timeout={self._timeout})"
        )


# ── Fallback module list for cloud mode ──────────────────────────────────────

_CLOUD_MODULE_LIST = [
    {"name": "monte_carlo", "engine": "cloud", "functions": ["run"]},
    {"name": "scenario", "engine": "cloud", "functions": ["run"]},
    {"name": "bootstrap", "engine": "cloud", "functions": ["run"]},
    {"name": "sensitivity", "engine": "cloud", "functions": ["run"]},
    {"name": "decision_tree", "engine": "cloud", "functions": ["run"]},
    {"name": "time_series", "engine": "cloud", "functions": ["run"]},
]


def _daemon_bootstrap_env(*, api_key: str, base_url: str) -> dict[str, str]:
    env_updates: dict[str, str] = {}
    if api_key:
        env_updates["ALGENTA_API_KEY"] = api_key
        env_updates["DE_API_KEY"] = api_key
    if base_url:
        env_updates["ALGENTA_BASE_URL"] = base_url
        env_updates["DE_BASE_URL"] = base_url
        env_updates["ALGENTA_API_URL"] = base_url
        env_updates["ALGENTA_CONTROL_PLANE_URL"] = base_url
    return env_updates


def _configured_cloud_api_url() -> str:
    for env_name in ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL"):
        configured = os.environ.get(env_name, "").strip()
        if configured:
            return configured.rstrip("/")
    return ""


def _cloud_api_url() -> str:
    return _configured_cloud_api_url() or API_BASE_URL.rstrip("/")


# ── Event loop helper ─────────────────────────────────────────────────────────


def _run(coro: Awaitable[Any]) -> Any:
    """
    Run a coroutine from sync code.

    - If called from inside a running event loop (e.g. FastAPI, Jupyter):
      offloads to a background thread so it doesn't block the loop.
    - Otherwise: creates a new event loop, runs the coro, tears it down.

    For high-throughput code inside an async framework, use the async API
    (aexecute / asimulate) directly to avoid the thread overhead.
    """
    try:
        asyncio.get_running_loop()
        # Already inside a running loop — offload to a thread to avoid deadlock.
        import concurrent.futures

        def _run_in_thread() -> Any:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run_in_thread).result()
    except builtins.RuntimeError:
        # No running loop — create a fresh one without touching global state.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
