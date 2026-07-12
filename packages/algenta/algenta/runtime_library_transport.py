"""Validated JSON transport for bundled runtime-library execution."""

from __future__ import annotations

from typing import Any

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
        if type_name == "List[Float64]" and isinstance(value, str) and value.startswith("@u8:"):
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
        _normalize_value(value, param.typ, structs, f"args.{param.name}")
        for param, value in zip(function.params, provided, strict=False)
    ]


def build_worker_request(
    module_name: str,
    function_name: str,
    args: Any,
) -> tuple[RuntimeLibraryModule, RuntimeFunctionSpec, dict[str, Any]]:
    module, function = find_runtime_function(module_name, function_name)
    structs = {struct.name: struct for struct in module.structs}
    return module, function, {
        "type": "library_execute",
        "engine_type": "library_execute",
        "module": module_name,
        "function": function_name,
        "args": _normalize_arguments(args, function, structs),
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
