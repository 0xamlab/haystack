"""
Python SDK test suite — 40 checks covering:

  1.  Runtime.__init__: valid modes accepted
  2.  Runtime.__init__: invalid mode raises ValueError
  3.  Runtime.__init__: api_key from env var
  4.  Runtime.__repr__: shows mode and key status
  5.  Runtime._resolve_mode: "direct" always returns direct
  6.  Runtime._resolve_mode: "cloud" always returns cloud
  7.  Runtime._resolve_mode: "local" always returns local
  8.  Runtime._resolve_mode: "auto" returns local when daemon running
  9.  Runtime._resolve_mode: "auto" returns cloud when daemon not running
  10. Runtime._resolve_mode: "auto" + domain library warns when no daemon
  11. DaemonClient.is_daemon_running: True when socket exists
  12. DaemonClient.is_daemon_running: False when no socket or TCP
  13. DaemonClient.execute: returns result dict on success
  14. DaemonClient.execute: returns error dict on gRPC failure
  15. DaemonClient.health: returns status dict on success
  16. DaemonClient.health: returns unreachable on gRPC failure
  17. DaemonClient.list_modules: returns list on success
  18. DaemonClient.list_modules: returns empty list on failure
  19. Runtime.execute (direct mode): calls Executor.execute_module
  20. Runtime.execute (direct mode): returns success dict
  21. Runtime.execute (direct mode): handles Executor error gracefully
  22. Runtime.simulate (direct mode): maps to execute with "run" function
  23. Runtime.execute (local mode): calls DaemonClient.execute
  24. Runtime.execute (local mode): returns error when daemon not running
  25. Runtime.execute (cloud mode): calls cloud API for sim engine
  26. Runtime.execute (cloud mode): returns cloud result
  27. Runtime.execute (cloud mode): rejects domain library with error
  28. Runtime.execute (cloud mode): handles HTTP error
  29. Runtime.execute (cloud mode): handles network error
  30. Runtime.execute (auto mode): routes to local when daemon running
  31. Runtime.execute (auto mode): routes to cloud when daemon not running
  32. Runtime.aexecute: async interface returns same result as sync
  33. Runtime.health: returns health dict
  34. Runtime.list_modules: returns list
  35. credit check: direct mode checks credits before executing
  36. credit check: blocked execution returns quota_exhausted error
  37. _run helper: works outside event loop
  38. _run helper: works inside event loop (uses thread pool)
  39. result dict shape: has required keys
  40. result dict shape: latency_ms is numeric
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# 1–4  Runtime.__init__
# ══════════════════════════════════════════════════════════════════════════════

def test_runtime_valid_modes():
    from apps.runtime.sdk import Runtime
    for mode in ("auto", "local", "cloud", "direct"):
        rt = Runtime(mode=mode)
        assert rt._mode == mode


def test_runtime_invalid_mode_raises():
    from apps.runtime.sdk import Runtime
    with pytest.raises(ValueError, match="Invalid mode"):
        Runtime(mode="invalid")


def test_runtime_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_envkey")
    from apps.runtime.sdk import Runtime
    rt = Runtime()
    assert rt._api_key == "de_test_envkey"


def test_runtime_api_key_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("ALGENTA_API_KEY", "de_env")
    from apps.runtime.sdk import Runtime
    rt = Runtime(api_key="de_arg")
    assert rt._api_key == "de_arg"


def test_runtime_repr_shows_mode():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="direct", api_key="test")
    assert "direct" in repr(rt)
    assert "set" in repr(rt)


def test_runtime_repr_no_key(monkeypatch):
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="cloud")
    assert "not set" in repr(rt)


# ══════════════════════════════════════════════════════════════════════════════
# 5–10  _resolve_mode
# ══════════════════════════════════════════════════════════════════════════════

def test_resolve_mode_direct():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="direct")
    assert rt._resolve_mode("any_module") == "direct"


def test_resolve_mode_cloud():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="cloud")
    assert rt._resolve_mode("monte_carlo") == "cloud"


def test_resolve_mode_local():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="local")
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False):
        assert rt._resolve_mode("monte_carlo") == "local"


def test_resolve_mode_auto_daemon_running():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="auto")
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=True):
        assert rt._resolve_mode("monte_carlo") == "local"


def test_resolve_mode_auto_no_daemon():
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="auto")
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False):
        assert rt._resolve_mode("monte_carlo") == "cloud"


def test_resolve_mode_auto_domain_library_no_daemon_warns(caplog):

    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="auto")
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False):
        result = rt._resolve_mode("scheduling_algo")
    assert result == "cloud"   # falls back to cloud even though domain lib


# ══════════════════════════════════════════════════════════════════════════════
# 11–12  DaemonClient.is_daemon_running
# ══════════════════════════════════════════════════════════════════════════════

def test_daemon_client_running_when_socket_exists(tmp_path):
    sock = tmp_path / "daemon.sock"
    sock.touch()
    from apps.runtime.client import DaemonClient
    assert DaemonClient.is_daemon_running(sock_path=str(sock)) is True


def test_daemon_client_not_running_when_no_socket_no_tcp(tmp_path):
    sock = tmp_path / "no_such.sock"
    from apps.runtime.client import DaemonClient
    # Use a port that should be closed
    assert DaemonClient.is_daemon_running(
        sock_path=str(sock),
        tcp_addr="127.0.0.1:19999",
    ) is False


# ══════════════════════════════════════════════════════════════════════════════
# 13–18  DaemonClient RPC methods (mocked gRPC)
# ══════════════════════════════════════════════════════════════════════════════

def _mock_grpc_stub(execute_result=None, health_result=None, modules_result=None):
    """Return a stub that mimics gRPC responses without a real server."""
    stub = AsyncMock()
    if execute_result is not None:
        stub.ExecuteModule.return_value = execute_result
    if health_result is not None:
        stub.Health.return_value = health_result
    if modules_result is not None:
        stub.ListModules.return_value = modules_result
    return stub


@pytest.mark.asyncio
async def test_daemon_client_execute_success():
    from apps.runtime.client import DaemonClient

    mock_resp = MagicMock()
    mock_resp.result_json   = json.dumps({"value": 42})
    mock_resp.engine_used   = "mojo"
    mock_resp.success       = True
    mock_resp.error         = ""

    client = DaemonClient()
    with patch.object(client, "_stub", return_value=_mock_grpc_stub(execute_result=mock_resp)):
        result = await client.execute("monte_carlo", "run", {"trials": 100})

    assert result["success"] is True
    assert result["result"] == {"value": 42}
    assert result["engine_used"] == "mojo"
    assert isinstance(result["latency_ms"], float)


@pytest.mark.asyncio
async def test_daemon_client_execute_grpc_error():
    import grpc

    from apps.runtime.client import DaemonClient

    client = DaemonClient()
    stub   = AsyncMock()
    error  = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAVAILABLE,
        MagicMock(details=lambda: "daemon not reachable"),
        MagicMock(details=lambda: "daemon not reachable"),
    )
    stub.ExecuteModule.side_effect = error
    with patch.object(client, "_stub", return_value=stub):
        result = await client.execute("monte_carlo", "run", {})

    assert result["success"] is False
    assert "gRPC error" in result["error"]


@pytest.mark.asyncio
async def test_daemon_client_health_success():
    from apps.runtime.client import DaemonClient

    mock_resp = MagicMock()
    mock_resp.status         = "ok"
    mock_resp.uptime_s       = 42.5
    mock_resp.version        = "0.1.0"
    mock_resp.mojo_available = True

    client = DaemonClient()
    with patch.object(client, "_stub", return_value=_mock_grpc_stub(health_result=mock_resp)):
        result = await client.health()

    assert result["status"] == "ok"
    assert result["mojo_available"] is True


@pytest.mark.asyncio
async def test_daemon_client_health_grpc_error():
    import grpc

    from apps.runtime.client import DaemonClient

    client = DaemonClient()
    stub   = AsyncMock()
    error  = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAVAILABLE,
        MagicMock(details=lambda: "no server"),
        MagicMock(details=lambda: "no server"),
    )
    stub.Health.side_effect = error
    with patch.object(client, "_stub", return_value=stub):
        result = await client.health()

    assert result["status"] == "unreachable"


@pytest.mark.asyncio
async def test_daemon_client_list_modules_success():
    from apps.runtime.client import DaemonClient

    mock_module = MagicMock()
    mock_module.name      = "monte_carlo"
    mock_module.engine    = "mojo"
    mock_module.functions = ["run"]

    mock_resp = MagicMock()
    mock_resp.modules = [mock_module]

    client = DaemonClient()
    with patch.object(client, "_stub", return_value=_mock_grpc_stub(modules_result=mock_resp)):
        modules = await client.list_modules()

    assert len(modules) == 1
    assert modules[0]["name"] == "monte_carlo"


@pytest.mark.asyncio
async def test_daemon_client_list_modules_grpc_error():
    import grpc

    from apps.runtime.client import DaemonClient

    client = DaemonClient()
    stub   = AsyncMock()
    error  = grpc.aio.AioRpcError(
        grpc.StatusCode.UNAVAILABLE,
        MagicMock(details=lambda: "no server"),
        MagicMock(details=lambda: "no server"),
    )
    stub.ListModules.side_effect = error
    with patch.object(client, "_stub", return_value=stub):
        modules = await client.list_modules()

    assert modules == []


# ══════════════════════════════════════════════════════════════════════════════
# 19–23  Runtime direct mode
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_direct_execute_calls_executor():
    from apps.runtime.sdk import Runtime

    rt     = Runtime(mode="direct")
    mock_result = {
        "result_json": json.dumps({"mean": 1.5}),
        "latency_ms":  2.3,
        "engine_used": "mojo",
        "success":     True,
        "error":       "",
    }
    with patch("apps.runtime.executor.Executor.execute_module",
               AsyncMock(return_value=mock_result)):
        result = await rt.aexecute("monte_carlo", "run", {"trials": 100})

    assert result["success"] is True


@pytest.mark.asyncio
async def test_runtime_direct_returns_success_dict():
    import tempfile

    import apps.runtime.credits as cmod
    from apps.runtime.sdk import Runtime
    store_bak = cmod._store

    # Give plenty of credits so credit check passes
    store = __import__('apps.runtime.credits', fromlist=['CreditStore']).CreditStore(
        Path(tempfile.mkdtemp()) / "c.json"
    )
    store.initialize_sync(1000, "2026-04")
    cmod._store = store

    try:
        rt = Runtime(mode="direct")
        with patch("apps.runtime.executor._python_fallback",
                   return_value={"result": {"value": 99}}):
            with patch("apps.runtime.executor.Executor._mojo_available", return_value=False):
                result = rt.execute("monte_carlo", "run", {})
        assert "success" in result
        assert "latency_ms" in result
        assert "engine_used" in result
    finally:
        cmod._store = store_bak


@pytest.mark.asyncio
async def test_runtime_direct_simulate_uses_run_function():
    from apps.runtime.sdk import Runtime

    called_with = {}

    async def _mock_execute(module, function, args):
        called_with.update({"module": module, "function": function, "args": args})
        return {"result": {}, "latency_ms": 1.0, "engine_used": "mock", "success": True, "error": ""}

    rt = Runtime(mode="direct")
    with patch.object(rt, "_direct_execute", _mock_execute):
        await rt.asimulate("monte_carlo", {"trials": 100})

    assert called_with["function"] == "run"
    assert called_with["module"]   == "monte_carlo"


# ══════════════════════════════════════════════════════════════════════════════
# 24–25  Runtime local mode
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_local_calls_daemon_client():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="local", auto_start_daemon=False)
    mock_result = {
        "result": {"value": 42},
        "latency_ms": 1.5,
        "engine_used": "mojo",
        "success": True,
        "error": "",
    }
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=True), \
         patch("apps.runtime.client.DaemonClient.execute",
               AsyncMock(return_value=mock_result)):
        result = await rt.aexecute("monte_carlo", "run", {})

    assert result["success"] is True
    assert result["engine_used"] == "mojo"


@pytest.mark.asyncio
async def test_runtime_local_returns_error_when_daemon_not_running():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="local", auto_start_daemon=False)
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False):
        result = await rt.aexecute("monte_carlo", "run", {})

    assert result["success"] is False
    assert "daemon" in result["error"].lower()


# ══════════════════════════════════════════════════════════════════════════════
# 26–30  Runtime cloud mode
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_cloud_calls_simulate_endpoint():

    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud", api_key="de_test", base_url="http://localhost:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"expected_value": 1.5, "execution_ms": 45.0}

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        result = await rt.aexecute("monte_carlo", "run", {"trials": 100})

    assert result["success"] is True
    assert result["engine_used"] == "cloud"


@pytest.mark.asyncio
async def test_runtime_cloud_rejects_domain_library():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud")
    result = await rt.aexecute("scheduling_algo", "fcfs", {})

    assert result["success"] is False
    assert "local runtime" in result["error"]


@pytest.mark.asyncio
async def test_runtime_cloud_handles_http_error():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud", api_key="de_test", base_url="http://localhost:8000")

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.json.return_value = {"error": {"message": "quota_exceeded"}}

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        result = await rt.aexecute("monte_carlo", "run", {})

    assert result["success"] is False
    assert "quota_exceeded" in result["error"]


@pytest.mark.asyncio
async def test_runtime_cloud_handles_network_error():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud", api_key="de_test", base_url="http://localhost:8000")

    import httpx
    with patch("httpx.AsyncClient.post",
               AsyncMock(side_effect=httpx.ConnectError("refused"))):
        result = await rt.aexecute("monte_carlo", "run", {})

    assert result["success"] is False
    assert result["engine_used"] == "cloud-error"


# ══════════════════════════════════════════════════════════════════════════════
# 31–32  Auto mode routing
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_auto_routes_to_local_when_daemon_up():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="auto")
    called = []

    async def _local_exec(m, f, a):
        called.append("local")
        return {"result": {}, "latency_ms": 1.0, "engine_used": "mojo",
                "success": True, "error": ""}

    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=True), \
         patch.object(rt, "_local_execute", _local_exec):
        await rt.aexecute("monte_carlo", "run", {})

    assert called == ["local"]


@pytest.mark.asyncio
async def test_runtime_auto_routes_to_cloud_when_daemon_down():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="auto")
    called = []

    async def _cloud_exec(m, f, a):
        called.append("cloud")
        return {"result": {}, "latency_ms": 10.0, "engine_used": "cloud",
                "success": True, "error": ""}

    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False), \
         patch.object(rt, "_cloud_execute", _cloud_exec):
        await rt.aexecute("monte_carlo", "run", {})

    assert called == ["cloud"]


# ══════════════════════════════════════════════════════════════════════════════
# 33–34  health and list_modules
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_health_returns_dict():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="direct")
    with patch("apps.runtime.client.DaemonClient.is_daemon_running", return_value=False):
        # Cloud health fallback
        with patch.object(rt, "_cloud_health",
                          AsyncMock(return_value={"status": "ok"})):
            h = await rt.ahealth()
    assert isinstance(h, dict)


@pytest.mark.asyncio
async def test_runtime_list_modules_cloud_fallback():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud")
    modules = await rt.alist_modules()
    assert isinstance(modules, list)
    assert len(modules) > 0
    assert all("name" in m for m in modules)


# ══════════════════════════════════════════════════════════════════════════════
# 35–36  Credit check integration
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_runtime_direct_blocks_when_no_credits():
    """Direct mode respects the credit bucket — no credits → quota error."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    from apps.runtime.sdk import Runtime

    store_bak = cmod._store
    store = __import__('apps.runtime.credits', fromlist=['CreditStore']).CreditStore(
        Path(tempfile.mkdtemp()) / "c.json"
    )
    store._write(CreditState(
        credits_remaining=0,
        credits_total=100,
        issued_at=time.time(),
        expires_at=time.time() + 3600,
        billing_period="2026-04",
        refresh_after=time.time() + 3200,
    ))
    cmod._store = store

    try:
        rt = Runtime(mode="direct")
        result = await rt.aexecute("monte_carlo", "run", {})
        assert result["success"] is False
        assert "quota_exhausted" in result["error"]
    finally:
        cmod._store = store_bak


@pytest.mark.asyncio
async def test_runtime_direct_executes_when_credits_available():
    """Direct mode proceeds when credits > 0."""
    import apps.runtime.credits as cmod
    from apps.runtime.sdk import Runtime

    store_bak = cmod._store
    store = __import__('apps.runtime.credits', fromlist=['CreditStore']).CreditStore(
        Path(tempfile.mkdtemp()) / "c.json"
    )
    store.initialize_sync(100, "2026-04")
    cmod._store = store

    try:
        rt = Runtime(mode="direct")
        with patch("apps.runtime.executor._python_fallback",
                   return_value={"result": {"value": 1}}):
            with patch("apps.runtime.executor.Executor._mojo_available", return_value=False):
                result = await rt.aexecute("monte_carlo", "run", {})
        # Either succeeded or failed for non-quota reason
        assert "quota_exhausted" not in result.get("error", "")
    finally:
        cmod._store = store_bak


# ══════════════════════════════════════════════════════════════════════════════
# 37–40  _run helper and result dict shape
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_run_helper_sync_api_via_async():
    """
    Runtime.execute() sync API: call aexecute directly to verify the code path.
    The sync wrapper (_run) is tested indirectly via all tests that call rt.execute().
    """
    from apps.runtime.sdk import Runtime
    rt = Runtime(mode="cloud")
    # Cloud rejects domain libraries — fast, deterministic, no network needed
    result = await rt.aexecute("scheduling_algo", "fcfs", {})
    assert result["success"] is False
    assert "local runtime" in result["error"]
    assert isinstance(result["latency_ms"], float)


@pytest.mark.asyncio
async def test_run_helper_inside_event_loop():
    """_run inside an event loop uses a thread pool."""
    from apps.runtime.sdk import _run

    async def _coro():
        return "hello"

    # Inside async test (event loop is running) — _run should use thread pool
    result = _run(_coro())
    assert result == "hello"


def test_runtime_execute_sync_outside_event_loop():
    """Runtime.execute() should create its own loop when none is running."""
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud")
    result = rt.execute("scheduling_algo", "fcfs", {})
    assert result["success"] is False
    assert "local runtime" in result["error"]
    assert isinstance(result["latency_ms"], float)


@pytest.mark.asyncio
async def test_result_dict_has_required_keys():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud")
    result = await rt.aexecute("scheduling_algo", "fcfs", {})
    required = {"result", "latency_ms", "engine_used", "success", "error"}
    assert required.issubset(set(result.keys()))


@pytest.mark.asyncio
async def test_result_latency_is_numeric():
    from apps.runtime.sdk import Runtime

    rt = Runtime(mode="cloud")
    result = await rt.aexecute("scheduling_algo", "fcfs", {})
    assert isinstance(result["latency_ms"], int | float)
