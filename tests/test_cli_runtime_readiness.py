from __future__ import annotations

import asyncio
import json

from apps.cli import main as cli_main


def test_wait_for_runtime_ready_retries_until_health_is_ok(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def health(self) -> dict[str, object]:
            self.calls += 1
            if self.calls < 3:
                return {"status": "unreachable"}
            return {"status": "ok", "engine": "mojo"}

    client = FakeClient()
    monkeypatch.setattr(cli_main, "_RUNTIME_READY_POLL_SECONDS", 0.0)

    health = asyncio.run(cli_main._wait_for_runtime_ready(client=client, timeout_seconds=1.0))

    assert health == {"status": "ok", "engine": "mojo"}
    assert client.calls == 3


def test_runtime_list_modules_sync_retries_transient_unreachable(monkeypatch) -> None:
    import apps.runtime.client as runtime_client

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            del timeout
            self.calls = 0

        async def health(self) -> dict[str, object]:
            self.calls += 1
            if self.calls == 1:
                return {"status": "unreachable"}
            return {"status": "ok", "engine": "mojo"}

        async def list_modules(self) -> list[dict[str, object]]:
            return [{"name": "kv_cache", "engine": "mojo", "functions": ["kv_cache_total_memory"]}]

    monkeypatch.setattr(runtime_client, "DaemonClient", FakeClient)
    monkeypatch.setattr(cli_main, "_RUNTIME_READY_POLL_SECONDS", 0.0)

    modules = cli_main._runtime_list_modules_sync()

    assert modules == [
        {"name": "kv_cache", "engine": "mojo", "functions": ["kv_cache_total_memory"]}
    ]


def test_cmd_runtime_execute_retries_transient_unreachable(monkeypatch, capsys) -> None:
    import apps.runtime.client as runtime_client

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            del timeout
            self.calls = 0

        async def health(self) -> dict[str, object]:
            self.calls += 1
            if self.calls == 1:
                return {"status": "unreachable"}
            return {"status": "ok", "engine": "mojo"}

        async def execute(
            self,
            module: str,
            function: str,
            args: object = None,
            request_id: str = "",
        ) -> dict[str, object]:
            del request_id
            return {
                "result": {"module": module, "function": function, "args": args},
                "latency_ms": 0.42,
                "engine_used": "mojo",
                "success": True,
            }

    monkeypatch.setattr(runtime_client, "DaemonClient", FakeClient)
    monkeypatch.setattr(cli_main, "_RUNTIME_READY_POLL_SECONDS", 0.0)

    cli_main.cmd_runtime_execute(
        "kv_cache",
        "kv_cache_total_memory",
        args_json=json.dumps([4096.0, 32.0]),
        format="json",
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "module": "kv_cache",
        "function": "kv_cache_total_memory",
        "args": [4096.0, 32.0],
        "result": {
            "module": "kv_cache",
            "function": "kv_cache_total_memory",
            "args": [4096.0, 32.0],
        },
        "latency_ms": 0.42,
        "engine_used": "mojo",
        "success": True,
    }
