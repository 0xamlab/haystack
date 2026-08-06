from __future__ import annotations

from pathlib import Path

import pytest

from apps.runtime import mojo_library_runner
from apps.runtime.mojo_inventory import RuntimeFunctionSpec, RuntimeLibraryModule, RuntimeParamSpec


def _fake_module(*functions: RuntimeFunctionSpec) -> RuntimeLibraryModule:
    return RuntimeLibraryModule(
        import_path="orders",
        lib_id="orders",
        path=Path("mojo/engine/orders.mojo"),
        functions=functions,
    )


def test_build_runtime_library_worker_request_normalizes_named_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function_spec = RuntimeFunctionSpec(
        name="count_orders",
        params=(
            RuntimeParamSpec(name="status", typ="String", has_default=False),
            RuntimeParamSpec(name="min_amount", typ="Float64", has_default=False),
            RuntimeParamSpec(name="limit", typ="Int", has_default=True),
        ),
        return_type="Int",
    )
    module = _fake_module(function_spec)
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"orders": module},
    )

    resolved_spec, payload = mojo_library_runner.build_runtime_library_worker_request(
        "orders",
        "count_orders",
        {"status": "completed", "min_amount": 1000},
    )

    assert resolved_spec == function_spec
    assert payload == {
        "type": "library_execute",
        "engine_type": "library_execute",
        "module": "orders",
        "function": "count_orders",
        "args": ["completed", 1000.0],
    }


def test_build_runtime_library_worker_request_validates_nested_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function_spec = RuntimeFunctionSpec(
        name="sum_grid",
        params=(RuntimeParamSpec(name="grid", typ="List[List[Float64]]", has_default=False),),
        return_type="Float64",
    )
    module = _fake_module(function_spec)
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"orders": module},
    )

    _, payload = mojo_library_runner.build_runtime_library_worker_request(
        "orders",
        "sum_grid",
        [[[1, 2], [3.5, 4.5]]],
    )

    assert payload["args"] == [[[1.0, 2.0], [3.5, 4.5]]]


def test_build_runtime_library_worker_request_rejects_invalid_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function_spec = RuntimeFunctionSpec(
        name="set_enabled",
        params=(RuntimeParamSpec(name="enabled", typ="Bool", has_default=False),),
        return_type="None",
    )
    module = _fake_module(function_spec)
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"orders": module},
    )

    with pytest.raises(mojo_library_runner.MojoLibraryError) as excinfo:
        mojo_library_runner.build_runtime_library_worker_request(
            "orders",
            "set_enabled",
            {"enabled": "yes"},
        )

    assert excinfo.value.code == "invalid_arguments"


def test_parse_runtime_library_worker_response_surfaces_structured_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function_spec = RuntimeFunctionSpec(
        name="count_orders",
        params=(RuntimeParamSpec(name="status", typ="String", has_default=False),),
        return_type="Int",
    )
    module = _fake_module(function_spec)
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"orders": module},
    )

    with pytest.raises(mojo_library_runner.MojoLibraryError) as excinfo:
        mojo_library_runner.parse_runtime_library_worker_response(
            "orders",
            "count_orders",
            {
                "error": "invalid_arguments: bad payload",
                "error_code": "invalid_arguments",
                "error_message": "bad payload",
            },
            function_spec=function_spec,
        )

    assert excinfo.value.code == "invalid_arguments"
    assert excinfo.value.message == "bad payload"


def test_parse_result_preserves_unquoted_string_values() -> None:
    assert (
        mojo_library_runner._parse_result(
            "diagnostic line\nplain mojo string output\n",
            "String",
        )
        == "plain mojo string output"
    )


def test_build_runtime_library_worker_request_validates_struct_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "orders.mojo"
    module_path.write_text(
        "\n".join(
            [
                "struct OrderConfig(Copyable, Movable):",
                "    var id: Int",
                "    var threshold: Float64",
                "",
                "def upsert(config: OrderConfig) -> Int:",
                "    return config.id",
            ]
        ),
        encoding="utf-8",
    )
    function_spec = RuntimeFunctionSpec(
        name="upsert",
        params=(RuntimeParamSpec(name="config", typ="OrderConfig", has_default=False),),
        return_type="Int",
    )
    module = RuntimeLibraryModule(
        import_path="orders",
        lib_id="orders",
        path=module_path,
        functions=(function_spec,),
    )
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"orders": module},
    )

    _, payload = mojo_library_runner.build_runtime_library_worker_request(
        "orders",
        "upsert",
        {"config": {"id": 41, "threshold": 0.75}},
    )

    assert payload["args"] == [
        {"__algenta_struct": "OrderConfig", "v": [41, 0.75]},
    ]

    with pytest.raises(mojo_library_runner.MojoLibraryError) as excinfo:
        mojo_library_runner.build_runtime_library_worker_request(
            "orders",
            "upsert",
            {"config": {"id": 41}},
        )
    assert excinfo.value.code == "invalid_arguments"


def test_parse_runtime_library_worker_response_decodes_struct_and_mutable_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "cache.mojo"
    module_path.write_text(
        "\n".join(
            [
                "struct Cache(Copyable, Movable):",
                "    var values: List[Int]",
                "    var hits: Int",
                "",
                "def cache_push(mut cache: Cache, value: Int) -> Bool:",
                "    return True",
            ]
        ),
        encoding="utf-8",
    )
    function_spec = RuntimeFunctionSpec(
        name="cache_push",
        params=(
            RuntimeParamSpec(name="cache", typ="Cache", has_default=False, is_mut=True),
            RuntimeParamSpec(name="value", typ="Int", has_default=False),
        ),
        return_type="Bool",
    )
    module = RuntimeLibraryModule(
        import_path="cache",
        lib_id="cache",
        path=module_path,
        functions=(function_spec,),
    )
    monkeypatch.setattr(
        mojo_library_runner,
        "runtime_library_module_map",
        lambda: {"cache": module},
    )

    parsed = mojo_library_runner.parse_runtime_library_worker_response(
        "cache",
        "cache_push",
        {
            "result": True,
            "mutated_args": {
                "0": {
                    "__algenta_struct": "Cache",
                    "v": [[1, 2, 3], 9],
                }
            },
        },
        function_spec=function_spec,
    )

    assert parsed == {
        "result": True,
        "mutated_args": {
            "cache": {
                "values": [1, 2, 3],
                "hits": 9,
            }
        },
    }
