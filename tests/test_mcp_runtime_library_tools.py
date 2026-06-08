from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import runtime_libraries


class _FakeDaemonClient:
    def __init__(self, *, health, modules=None, execute_result=None):
        self._health = health
        self._modules = modules or []
        self._execute_result = execute_result or {
            "success": True,
            "result": 1.0,
            "latency_ms": 0.5,
            "engine_used": "mojo",
        }

    async def health(self) -> dict[str, object]:
        return dict(self._health)

    async def list_modules(self) -> list[dict[str, object]]:
        return [dict(module) for module in self._modules]

    async def execute(
        self,
        module: str,
        function: str,
        args: object = None,
        request_id: str = "",
    ) -> dict[str, object]:
        result = dict(self._execute_result)
        result.setdefault("module", module)
        result.setdefault("function", function)
        result.setdefault("args", args)
        result.setdefault("request_id", request_id)
        return result


def test_list_runtime_libraries_spec_names_are_stable() -> None:
    assert runtime_libraries.LIST_RUNTIME_LIBRARIES_SPEC["name"] == "list_runtime_libraries"
    assert runtime_libraries.EXECUTE_RUNTIME_LIBRARY_SPEC["name"] == "execute_runtime_library"


@pytest.mark.anyio
async def test_list_runtime_libraries_handler_filters_and_limits(monkeypatch) -> None:
    modules = [
        {"name": "bpe_tokenizer", "engine": "mojo", "functions": ["bpe_merge_score"]},
        {"name": "rerank_eval", "engine": "mojo", "functions": ["precision_at_k", "ndcg_at_k"]},
        {
            "name": "vector_kernels.ranker",
            "engine": "mojo",
            "functions": ["run_column_rank_v2"],
        },
    ]
    monkeypatch.setattr(
        runtime_libraries,
        "DaemonClient",
        lambda timeout=20.0: _FakeDaemonClient(
            health={"status": "ok", "engine": "mojo"},
            modules=modules,
        ),
    )

    payload = json.loads(
        await runtime_libraries.list_runtime_libraries_handler({"search": "rank", "limit": 2})
    )

    assert payload["runtime_health"]["status"] == "ok"
    assert payload["module_count"] == 2
    assert [module["name"] for module in payload["libraries"]] == [
        "rerank_eval",
        "vector_kernels.ranker",
    ]


@pytest.mark.anyio
async def test_list_runtime_libraries_handler_fails_closed_when_daemon_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_libraries,
        "DaemonClient",
        lambda timeout=20.0: _FakeDaemonClient(health={"status": "unreachable"}),
    )

    with pytest.raises(RuntimeError, match="runtime daemon is unavailable"):
        await runtime_libraries.list_runtime_libraries_handler({})


@pytest.mark.anyio
async def test_execute_runtime_library_handler_returns_result(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_libraries,
        "DaemonClient",
        lambda timeout=30.0: _FakeDaemonClient(
            health={"status": "ok", "engine": "mojo"},
            execute_result={
                "success": True,
                "result": 0.8333333333333334,
                "latency_ms": 0.23,
                "engine_used": "mojo",
            },
        ),
    )

    payload = json.loads(
        await runtime_libraries.execute_runtime_library_handler(
            {
                "module": "bpe_tokenizer",
                "function": "bpe_merge_rank_score",
                "args": [5.0, 5.0],
                "request_id": "req_rollout_1",
            }
        )
    )

    assert payload["module"] == "bpe_tokenizer"
    assert payload["function"] == "bpe_merge_rank_score"
    assert payload["result"] == pytest.approx(0.8333333333333334)
    assert payload["engine_used"] == "mojo"
    assert payload["success"] is True


@pytest.mark.anyio
async def test_execute_runtime_library_handler_surfaces_runtime_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_libraries,
        "DaemonClient",
        lambda timeout=30.0: _FakeDaemonClient(
            health={"status": "ok", "engine": "mojo"},
            execute_result={
                "success": False,
                "error": "module_not_registered: Unknown Mojo module.",
                "engine_used": "mojo",
            },
        ),
    )

    with pytest.raises(RuntimeError, match="Unknown Mojo module"):
        await runtime_libraries.execute_runtime_library_handler(
            {
                "module": "missing",
                "function": "run",
            }
        )
