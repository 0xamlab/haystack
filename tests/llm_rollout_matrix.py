from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from benchmarks.llm_compiled_runtime_benchmark import _build_args, collect_target_modules

_NUMERIC_RETURN_TYPES = {
    "Float16",
    "Float32",
    "Float64",
    "Int",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "UInt",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
}


@dataclass(frozen=True)
class LLMRolloutFunctionCase:
    module: str
    function: str
    args: Any
    return_type: str

    def to_json(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "function": self.function,
            "args": self.args,
            "return_type": self.return_type,
        }


def _collect_cases() -> tuple[LLMRolloutFunctionCase, ...]:
    modules = collect_target_modules()
    cases: list[LLMRolloutFunctionCase] = []
    for module_name, functions in modules.items():
        for function_spec in functions:
            cases.append(
                LLMRolloutFunctionCase(
                    module=module_name,
                    function=function_spec.name,
                    args=_build_args(module_name, function_spec),
                    return_type=function_spec.return_type,
                )
            )
    return tuple(cases)


LLM_ROLLOUT_FUNCTION_CASES = _collect_cases()
LLM_ROLLOUT_CASES_JSON = tuple(case.to_json() for case in LLM_ROLLOUT_FUNCTION_CASES)
LLM_ROLLOUT_MODULE_NAMES = tuple(
    module_name for module_name in collect_target_modules()
)
LLM_ROLLOUT_FUNCTIONS_BY_MODULE = {
    module_name: tuple(function.name for function in functions)
    for module_name, functions in collect_target_modules().items()
}


def _assert_json_safe(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        assert math.isfinite(value), f"Expected finite float, received {value!r}"
        return
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for item in value:
            _assert_json_safe(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str), f"Expected string key, received {type(key)!r}"
            _assert_json_safe(item)
        return
    raise AssertionError(f"Unsupported runtime payload type: {type(value)!r}")


def assert_rollout_channel_result(case: LLMRolloutFunctionCase, result: Any) -> None:
    if case.module == "vector_kernels.ranker":
        assert isinstance(result, str), f"{case.module}.{case.function} returned {type(result)!r}"
        payload = json.loads(result)
        assert isinstance(payload, dict)
        assert "ambiguous" in payload
        assert "matches" in payload
        _assert_json_safe(payload)
        return

    if case.module == "vector_kernels.table" and case.function == "build_query":
        assert isinstance(result, dict), f"{case.module}.{case.function} returned {type(result)!r}"
        assert {"source_id", "role_id", "top_k", "query_norm_inv", "query_vec"} <= set(result)
        _assert_json_safe(result)
        return

    if case.module == "vector_kernels.table" and case.function == "build_table_json":
        assert isinstance(result, dict), f"{case.module}.{case.function} returned {type(result)!r}"
        assert "entries" in result
        _assert_json_safe(result)
        return

    if case.return_type == "None":
        assert result is None
        return

    if case.return_type == "Bool":
        assert isinstance(result, bool), f"{case.module}.{case.function} returned {type(result)!r}"
        return

    if case.return_type in _NUMERIC_RETURN_TYPES:
        assert isinstance(result, (int, float)), (
            f"{case.module}.{case.function} returned {type(result)!r}"
        )
        assert math.isfinite(float(result))
        return

    if case.return_type == "String":
        assert isinstance(result, str), f"{case.module}.{case.function} returned {type(result)!r}"
        return

    if case.return_type.startswith("List["):
        assert isinstance(result, list), f"{case.module}.{case.function} returned {type(result)!r}"
        _assert_json_safe(result)
        return

    assert result is not None, f"{case.module}.{case.function} returned None unexpectedly"
    _assert_json_safe(result)
