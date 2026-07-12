from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY

import pytest

from apps.api_server.services.runtime_library_service import (
    RuntimeLibraryServiceError,
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime.mojo_library_runner import MojoLibraryError


def _fake_module(name: str, functions: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        import_path=name,
        functions=[SimpleNamespace(name=function_name) for function_name in functions],
    )


def test_list_public_runtime_library_descriptors_is_sorted_and_filterable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.runtime_library_modules",
        lambda: (
            _fake_module("zeta", ["project"]),
            _fake_module("ab_testing", ["sample_size", "power"]),
            _fake_module("inventory", ["reorder_point"]),
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service._runtime_worker_available",
        lambda: True,
    )

    descriptors = list_public_runtime_library_descriptors()
    assert [descriptor.name for descriptor in descriptors] == [
        "ab_testing",
        "inventory",
        "zeta",
    ]
    assert descriptors[0].functions == ("power", "sample_size")
    assert descriptors[0].engine == "mojo"

    filtered = list_public_runtime_library_descriptors(query="reorder")
    assert [descriptor.name for descriptor in filtered] == ["inventory"]


def test_get_public_runtime_library_health_reflects_runtime_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.runtime_library_modules",
        lambda: (
            _fake_module("ab_testing", ["sample_size"]),
            _fake_module("pricing", ["elasticity"]),
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service._runtime_worker_available",
        lambda: False,
    )

    health = get_public_runtime_library_health()

    assert health.status == "unavailable"
    assert health.engine == "unavailable"
    assert health.module_count == 2
    assert health.runtime_available is False


@pytest.mark.anyio
async def test_execute_public_runtime_library_returns_result_with_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_build_request(module: str, function: str, args: object):
        captured["module"] = module
        captured["function"] = function
        captured["args"] = args
        return object(), {
            "type": "library_execute",
            "module": module,
            "function": function,
            "args": [args],
        }

    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.build_runtime_library_worker_request",
        _fake_build_request,
    )

    async def _fake_invoke(payload: object) -> object:
        captured["payload"] = payload
        return {"result": {"sample_size": 812}}

    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.invoke_via_pool",
        _fake_invoke,
    )

    def _fake_parse(
        module: str, function: str, response: object, *, function_spec: object
    ) -> object:
        captured["parse"] = (module, function, response, function_spec)
        return {"sample_size": 812}

    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.parse_runtime_library_worker_response",
        _fake_parse,
    )

    result = await execute_public_runtime_library(
        module="ab_testing",
        function="sample_size",
        args={"alpha": 0.05, "power": 0.8},
        request_id="req_123",
    )

    assert captured == {
        "module": "ab_testing",
        "function": "sample_size",
        "args": {"alpha": 0.05, "power": 0.8},
        "payload": {
            "type": "library_execute",
            "module": "ab_testing",
            "function": "sample_size",
            "args": [{"alpha": 0.05, "power": 0.8}],
        },
        "parse": (
            "ab_testing",
            "sample_size",
            {"result": {"sample_size": 812}},
            ANY,
        ),
    }
    assert result.module == "ab_testing"
    assert result.function == "sample_size"
    assert result.result == {"sample_size": 812}
    assert result.engine_used == "mojo"
    assert result.request_id == "req_123"
    assert result.latency_ms >= 0


@pytest.mark.anyio
async def test_execute_public_runtime_library_translates_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _reject_request(module: str, function: str, args: object) -> None:
        del module, function, args
        raise MojoLibraryError(
            "invalid_arguments",
            "Runtime arguments do not match the function contract.",
            {"field": "values"},
        )

    monkeypatch.setattr(
        "apps.api_server.services.runtime_library_service.build_runtime_library_worker_request",
        _reject_request,
    )

    with pytest.raises(RuntimeLibraryServiceError) as excinfo:
        await execute_public_runtime_library(
            module="vector_kernels.dot",
            function="dot64_f32",
            args={"values": "invalid"},
        )

    assert excinfo.value.code == "invalid_arguments"
    assert excinfo.value.details == {"field": "values"}
    assert "function contract" in excinfo.value.message
