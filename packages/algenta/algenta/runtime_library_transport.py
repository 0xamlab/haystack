"""Validated JSON transport for bundled runtime-library execution."""

from __future__ import annotations

from typing import Any

from algenta.runtime_count_guard import (
    PACKED_FLOAT64_PREFIX as _PACKED_FLOAT64_PREFIX,
)
from algenta.runtime_count_guard import enforce_count_relations
from algenta.runtime_library_contract import (
    RuntimeFunctionSpec,
    RuntimeLibraryContractError,
    RuntimeLibraryModule,
    RuntimeStructSpec,
    find_runtime_function,
)

_STRUCT_TYPE_KEY = "__algenta_struct"
_STRUCT_VALUES_KEY = "v"


def _list_inner_type(type_name: str) -> str | None:
    if type_name.startswith("List[") and type_name.endswith("]"):
        return type_name[5:-1]
    return None


def _invalid(message: str, **details: Any) -> RuntimeLibraryContractError:
    return RuntimeLibraryContractError("invalid_arguments", message, details)


def _normalize_value(
    value: Any,
    type_name: str,
    structs: dict[str, RuntimeStructSpec],
    context: str,
) -> Any:
    if type_name == "None":
        if value is not None:
            raise _invalid(f"{context} must be null", expected=type_name)
        return None
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise _invalid(f"{context} must be Bool", expected=type_name)
        return value
    if type_name == "String":
        if not isinstance(value, str):
            raise _invalid(f"{context} must be String", expected=type_name)
        return value
    if type_name == "Int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise _invalid(f"{context} must be Int", expected=type_name)
        return value
    if type_name in {"UInt8", "UInt16", "UInt32", "UInt64"}:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise _invalid(f"{context} must be a non-negative {type_name}", expected=type_name)
        return value
    if type_name in {"Float32", "Float64"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise _invalid(f"{context} must be numeric", expected=type_name)
        return float(value)
    inner_type = _list_inner_type(type_name)
    if inner_type is not None:
        if (
            type_name == "List[Float64]"
            and isinstance(value, str)
            and value.startswith(_PACKED_FLOAT64_PREFIX)
        ):
            # A packed uint8 buffer the runtime decodes to one Float64 per byte. It is a LIST,
            # not a deferred reference: `runtime_count_guard.measured_element_count` reads its
            # exact length, so every declared count relation still applies to it.
            return value
        if not isinstance(value, list):
            raise _invalid(f"{context} must be {type_name}", expected=type_name)
        return [
            _normalize_value(item, inner_type, structs, f"{context}[{index}]")
            for index, item in enumerate(value)
        ]
    struct = structs.get(type_name)
    if struct is None:
        raise RuntimeLibraryContractError(
            "unsupported_signature",
            f"Unsupported runtime type {type_name!r}",
            {"type": type_name, "context": context},
        )
    if not isinstance(value, dict):
        raise _invalid(f"{context} must be an object for {type_name}", expected=type_name)
    raw_values = value.get(_STRUCT_VALUES_KEY)
    if value.get(_STRUCT_TYPE_KEY) == type_name and isinstance(raw_values, list):
        provided = dict(zip((field.name for field in struct.fields), raw_values, strict=False))
    else:
        provided = value
    expected_fields = {field.name for field in struct.fields}
    missing = sorted(expected_fields - set(provided))
    extra = sorted(set(provided) - expected_fields - {_STRUCT_TYPE_KEY, _STRUCT_VALUES_KEY})
    if missing or extra:
        raise _invalid(
            f"{context} has invalid fields for {type_name}", missing=missing, extra=extra
        )
    normalized = [
        _normalize_value(provided[field.name], field.typ, structs, f"{context}.{field.name}")
        for field in struct.fields
    ]
    return {_STRUCT_TYPE_KEY: type_name, _STRUCT_VALUES_KEY: normalized}


def is_deferred_reference(value: Any) -> bool:
    """True for an argument the worker resolves, so the client cannot type-check it.

    Two forms, both resolved inside Mojo before the kernel sees them:

    * ``"@handle"`` — a resident dataset (``dataset_open``)
    * ``"$k"``      — the output of pipeline node k

    A reference stands in for a value of any declared type, so validating it here
    would reject every legitimate use: `"@ds_1"` is a string where the signature
    says `List[Float64]`. Arity is still enforced, and the worker fails loudly on an
    unknown handle or an out-of-range node, so deferring the TYPE check does not
    lose the error — it moves it to where the value actually exists.

    Deferring a LENGTH check does not have that property, and this docstring used to
    claim it did. An unknown handle is a loud error; an element count larger than the
    resolved list is an uncatchable process abort, which is not an error the worker
    can report at all. So a deferred reference in a position that a declared count
    relation BOUNDS is refused by ``runtime_count_guard.enforce_count_relations``
    rather than passed on — measured, ``compute_mean("@ds_1", 5)`` ended the worker
    process, and ``"@ds_1"`` reaches a unary ``library_execute`` unbound (only
    ``batch_execute`` and ``pipeline_execute`` bind references), so the kernel saw an
    empty list and every count above zero was an over-read.

    ``"@u8:<base64>"`` is deliberately NOT a deferred reference: it is a packed
    ``List[Float64]`` the runtime decodes in place, its element count is exact, and
    treating it as deferred is what let it skip both the type check and the guard.
    """
    if not isinstance(value, str) or len(value) < 2:
        return False
    if value.startswith(_PACKED_FLOAT64_PREFIX):
        return False
    if value[0] == "@":
        return len(value) > 1
    if value[0] == "$":
        return value[1:].isdigit()
    return False


def _normalize_arguments(
    args: Any,
    function: RuntimeFunctionSpec,
    structs: dict[str, RuntimeStructSpec],
) -> list[Any]:
    if args is None:
        provided: list[Any] = []
    elif isinstance(args, list):
        provided = args
    elif isinstance(args, dict):
        provided = []
        skipped_default = False
        parameter_names = {param.name for param in function.params}
        extra = sorted(set(args) - parameter_names)
        if extra:
            raise _invalid("Unexpected named arguments", extra=extra)
        for param in function.params:
            if param.name in args:
                if skipped_default:
                    raise _invalid(
                        "Named arguments cannot skip an earlier defaulted parameter",
                        parameter=param.name,
                    )
                provided.append(args[param.name])
            elif param.has_default:
                skipped_default = True
            else:
                raise _invalid("Missing required argument", parameter=param.name)
    else:
        provided = [args]
    required = sum(not param.has_default for param in function.params)
    if not required <= len(provided) <= len(function.params):
        raise _invalid(
            "Runtime argument count is outside the function signature",
            required=required,
            accepted=len(function.params),
            received=len(provided),
        )
    return [
        value
        if is_deferred_reference(value)
        else _normalize_value(value, param.typ, structs, f"args.{param.name}")
        for param, value in zip(function.params, provided, strict=False)
    ]


def build_worker_request(
    module_name: str,
    function_name: str,
    args: Any,
) -> tuple[RuntimeLibraryModule, RuntimeFunctionSpec, dict[str, Any]]:
    module, function = find_runtime_function(module_name, function_name)
    structs = {struct.name: struct for struct in module.structs}
    normalized = _normalize_arguments(args, function, structs)
    # An element count larger than the list it measures has to be declined here: inside the
    # runtime the over-read is an uncatchable abort of the whole process, so there is no
    # later point at which it could be reported. Batched execution builds each item through
    # this same function, so one bad item is refused on its own and its neighbours — and the
    # datasets they are holding — are untouched.
    enforce_count_relations(module_name, function, normalized)
    return module, function, {
        "type": "library_execute",
        "engine_type": "library_execute",
        "module": module_name,
        "function": function_name,
        "args": normalized,
    }


def _decode_value(
    value: Any,
    type_name: str,
    structs: dict[str, RuntimeStructSpec],
    context: str,
) -> Any:
    inner_type = _list_inner_type(type_name)
    if inner_type is not None:
        if not isinstance(value, list):
            raise RuntimeLibraryContractError(
                "runtime_execution_failed",
                f"The bundled runtime returned an invalid {context}",
            )
        return [
            _decode_value(item, inner_type, structs, f"{context}[{index}]")
            for index, item in enumerate(value)
        ]

    struct = structs.get(type_name)
    if struct is None:
        try:
            return _normalize_value(value, type_name, structs, context)
        except RuntimeLibraryContractError as exc:
            raise RuntimeLibraryContractError(
                "runtime_execution_failed",
                f"The bundled runtime returned an invalid {context}",
            ) from exc

    if not isinstance(value, dict) or value.get(_STRUCT_TYPE_KEY) != type_name:
        raise RuntimeLibraryContractError(
            "runtime_execution_failed",
            f"The bundled runtime returned an invalid {type_name} for {context}",
        )
    raw_values = value.get(_STRUCT_VALUES_KEY)
    if not isinstance(raw_values, list) or len(raw_values) != len(struct.fields):
        raise RuntimeLibraryContractError(
            "runtime_execution_failed",
            f"The bundled runtime returned invalid fields for {type_name}",
        )
    return {
        field.name: _decode_value(
            raw_value,
            field.typ,
            structs,
            f"{context}.{field.name}",
        )
        for field, raw_value in zip(struct.fields, raw_values, strict=True)
    }


def parse_worker_response(
    module: RuntimeLibraryModule,
    function: RuntimeFunctionSpec,
    response: Any,
) -> Any:
    if not isinstance(response, dict):
        raise RuntimeLibraryContractError(
            "runtime_execution_failed", "The bundled runtime returned a malformed response"
        )
    error = response.get("error")
    if isinstance(error, str) and error.strip():
        raise RuntimeLibraryContractError(
            str(response.get("error_code") or "runtime_execution_failed"),
            str(response.get("error_message") or error),
            {"module": module.import_path, "function": function.name},
        )
    if "result" not in response:
        raise RuntimeLibraryContractError(
            "runtime_execution_failed", "The bundled runtime response has no result"
        )
    structs = {struct.name: struct for struct in module.structs}
    result = _decode_value(response["result"], function.return_type, structs, "result")
    mutations = response.get("mutated_args")
    if not isinstance(mutations, dict) or not mutations:
        return result
    decoded: dict[str, Any] = {}
    for raw_index, raw_value in mutations.items():
        try:
            index = int(raw_index)
            param = function.params[index]
        except (ValueError, IndexError) as exc:
            raise RuntimeLibraryContractError(
                "runtime_execution_failed", "The bundled runtime returned invalid mutation data"
            ) from exc
        decoded[param.name] = _decode_value(
            raw_value, param.typ, structs, f"mutated_args.{param.name}"
        )
    return {"result": result, "mutated_args": decoded}
