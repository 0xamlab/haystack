from __future__ import annotations

import json

import pytest

from apps.api_server.services.runtime_library_service import (
    RuntimeLibraryDescriptor,
    RuntimeLibraryExecutionResult,
    RuntimeLibraryHealth,
    RuntimeLibraryServiceError,
)
from apps.mcp_server.tools import runtime_libraries


def test_list_runtime_libraries_spec_names_are_stable() -> None:
    assert runtime_libraries.LIST_RUNTIME_LIBRARIES_SPEC["name"] == "list_runtime_libraries"
    assert runtime_libraries.EXECUTE_RUNTIME_LIBRARY_SPEC["name"] == "execute_runtime_library"


@pytest.mark.anyio
async def test_list_runtime_libraries_handler_filters_and_limits(monkeypatch) -> None:
    modules = (
        RuntimeLibraryDescriptor("bpe_tokenizer", "mojo", ("bpe_merge_score",)),
        RuntimeLibraryDescriptor("rerank_eval", "mojo", ("precision_at_k", "ndcg_at_k")),
        RuntimeLibraryDescriptor("vector_kernels.ranker", "mojo", ("run_column_rank_v2",)),
    )
    monkeypatch.setattr(
        runtime_libraries,
        "get_public_runtime_library_health",
        lambda: RuntimeLibraryHealth("ok", "mojo", len(modules), True),
    )
    monkeypatch.setattr(
        runtime_libraries,
        "list_public_runtime_library_descriptors",
        lambda: modules,
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
async def test_list_runtime_libraries_handler_fails_closed_when_runtime_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_libraries,
        "get_public_runtime_library_health",
        lambda: RuntimeLibraryHealth("unavailable", "unavailable", 0, False),
    )

    with pytest.raises(RuntimeError, match="encapsulated Algenta runtime is unavailable"):
        await runtime_libraries.list_runtime_libraries_handler({})


@pytest.mark.anyio
async def test_execute_runtime_library_handler_returns_result(monkeypatch) -> None:
    async def _execute(**kwargs):
        return RuntimeLibraryExecutionResult(
            module=kwargs["module"],
            function=kwargs["function"],
            result=0.8333333333333334,
            latency_ms=0.23,
            engine_used="mojo",
            request_id=kwargs["request_id"],
        )

    monkeypatch.setattr(runtime_libraries, "execute_public_runtime_library", _execute)

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
    async def _execute(**kwargs):
        del kwargs
        raise RuntimeLibraryServiceError(
            "module_not_registered", "Unknown Mojo module.", {}
        )

    monkeypatch.setattr(runtime_libraries, "execute_public_runtime_library", _execute)

    with pytest.raises(RuntimeError, match="Unknown Mojo module"):
        await runtime_libraries.execute_runtime_library_handler(
            {
                "module": "missing",
                "function": "run",
            }
        )
