from __future__ import annotations

import ast
import asyncio
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.runtime.mojo_inventory import (
    RuntimeFunctionSpec,
    RuntimeLibraryModule,
    RuntimeStructSpec,
    discover_runtime_library_modules,
    parse_runtime_struct_specs,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MOJO_ENV = _PROJECT_ROOT / "mojo_env"
_MOJO_BIN = _MOJO_ENV / ".pixi" / "envs" / "default" / "bin" / "mojo"
_ENGINE_DIR = _PROJECT_ROOT / "mojo" / "engine"
_MODULAR_HOME = _MOJO_ENV / ".pixi" / "envs" / "default" / "share" / "max"
_MODULAR_CACHE_DIR = _PROJECT_ROOT / ".cache" / "modular"
_MODULAR_DATA_DIR = _PROJECT_ROOT / ".local" / "share"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_STRUCT_ENVELOPE_TYPE_KEY = "__algenta_struct"
_STRUCT_ENVELOPE_VALUES_KEY = "v"


@dataclass
class MojoLibraryError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


@lru_cache(maxsize=1)
def runtime_library_modules() -> tuple[RuntimeLibraryModule, ...]:
    return discover_runtime_library_modules(executable_only=True)


@lru_cache(maxsize=1)
def runtime_library_module_map() -> dict[str, RuntimeLibraryModule]:
    return {module.import_path: module for module in runtime_library_modules()}


@lru_cache(maxsize=1)
def _runtime_struct_specs_index() -> dict[str, RuntimeStructSpec]:
    specs: dict[str, RuntimeStructSpec] = {}
    for module in runtime_library_modules():
        try:
            module_specs = parse_runtime_struct_specs(module.path)
        except OSError:
            continue
        for struct_name, struct_spec in module_specs.items():
            specs.setdefault(struct_name, struct_spec)
    return specs


def _module_struct_specs(module_name: str) -> dict[str, RuntimeStructSpec]:
    module = runtime_library_module_map().get(module_name)
    resolved = dict(_runtime_struct_specs_index())
    if module is None:
        return resolved
    try:
        resolved.update(parse_runtime_struct_specs(module.path))
        return resolved
    except OSError:
        return resolved


def library_runtime_available() -> bool:
    return _MOJO_BIN.exists() and _MODULAR_HOME.exists()


def find_runtime_function(
    module_name: str,
    function_name: str,
) -> tuple[RuntimeLibraryModule, RuntimeFunctionSpec]:
    module = runtime_library_module_map().get(module_name)
    if module is None:
        raise MojoLibraryError(
            "module_not_registered",
            f"Module '{module_name}' is not registered in the executable Mojo runtime inventory.",
            {"module": module_name},
        )
    for function in module.functions:
        if function.name == function_name:
            return module, function
    raise MojoLibraryError(
        "function_not_registered",
        (
            f"Function '{function_name}' is not registered for module "
            f"'{module_name}' in the executable Mojo runtime inventory."
        ),
        {"module": module_name, "function": function_name},
    )


def _json_string_literal(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _mojo_scalar_literal(value: Any, type_name: str) -> str:
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Bool argument, received {type(value).__name__}.",
            )
        return "True" if value else "False"
    if type_name == "String":
        if not isinstance(value, str):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected String argument, received {type(value).__name__}.",
            )
        return _json_string_literal(value)
    if type_name == "Int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Int argument, received {type(value).__name__}.",
            )
        return str(value)
    if type_name in {"UInt8", "UInt16", "UInt32", "UInt64"}:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected non-negative {type_name} argument, received {value!r}.",
            )
        return f"{type_name}({value})"
    if type_name == "Float32":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Float32 argument, received {type(value).__name__}.",
            )
        return f"Float32({float(value)!r})"
    if type_name == "Float64":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Float64 argument, received {type(value).__name__}.",
            )
        return repr(float(value))
    raise MojoLibraryError(
        "unsupported_signature",
        f"Unsupported scalar Mojo type '{type_name}'.",
        {"type": type_name},
    )


def _is_struct_type(type_name: str, struct_specs: dict[str, RuntimeStructSpec]) -> bool:
    return type_name in struct_specs


def _normalize_struct_runtime_value(
    value: Any,
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec],
    context: str,
) -> dict[str, Any]:
    spec = struct_specs.get(type_name)
    if spec is None:
        raise MojoLibraryError(
            "unsupported_signature",
            f"Unsupported struct type '{type_name}' in runtime transport.",
            {"type": type_name, "context": context},
        )

    if isinstance(value, dict) and value.get(_STRUCT_ENVELOPE_TYPE_KEY) == type_name:
        values = value.get(_STRUCT_ENVELOPE_VALUES_KEY)
        if not isinstance(values, list):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Structured value for {type_name} must include a list '{_STRUCT_ENVELOPE_VALUES_KEY}'.",
                {"type": type_name, "context": context},
            )
        provided = dict(zip((field.name for field in spec.fields), values, strict=False))
    elif isinstance(value, dict):
        provided = value
    else:
        raise MojoLibraryError(
            "invalid_arguments",
            f"Expected object argument for {type_name}, received {type(value).__name__}.",
            {"type": type_name, "context": context},
        )

    normalized_values: list[Any] = []
    for field in spec.fields:
        if field.name not in provided:
            raise MojoLibraryError(
                "invalid_arguments",
                f"Missing required field '{field.name}' for {type_name}.",
                {"type": type_name, "field": field.name, "context": context},
            )
        normalized_values.append(
            _normalize_runtime_value(
                provided[field.name],
                field.typ,
                struct_specs=struct_specs,
                context=f"{context}.{field.name}",
            )
        )

    extra_fields = sorted(set(provided) - {field.name for field in spec.fields})
    if extra_fields:
        raise MojoLibraryError(
            "invalid_arguments",
            f"Unexpected fields for {type_name}: {', '.join(extra_fields)}.",
            {"type": type_name, "extra_fields": extra_fields, "context": context},
        )

    return {
        _STRUCT_ENVELOPE_TYPE_KEY: type_name,
        _STRUCT_ENVELOPE_VALUES_KEY: normalized_values,
    }


def _normalize_runtime_value(
    value: Any,
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
    context: str = "args",
) -> Any:
    resolved_struct_specs = struct_specs or {}
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Bool argument, received {type(value).__name__}.",
            )
        return value
    if type_name == "String":
        if not isinstance(value, str):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected String argument, received {type(value).__name__}.",
            )
        return value
    if type_name == "Int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Int argument, received {type(value).__name__}.",
            )
        return value
    if type_name in {"UInt8", "UInt16", "UInt32", "UInt64"}:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected non-negative {type_name} argument, received {value!r}.",
            )
        return value
    if type_name == "Float32":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Float32 argument, received {type(value).__name__}.",
            )
        return float(value)
    if type_name == "Float64":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected Float64 argument, received {type(value).__name__}.",
            )
        return float(value)
    if _is_list_type(type_name):
        # Binary-buffer fast path: a "@u8:<base64>" string is a packed uint8 buffer (pixel data
        # 0-255) that the Mojo dispatch decodes for List[Float64] in one O(n) pass
        # (json_parse_float64_list). Pass it through verbatim — validating/normalizing it
        # element-by-element here would itself be an O(n) Python loop, defeating the purpose.
        # Only List[Float64] has the Mojo-side binary decoder.
        if (
            type_name == "List[Float64]"
            and isinstance(value, str)
            and value.startswith("@u8:")
        ):
            return value
        if not isinstance(value, list):
            raise MojoLibraryError(
                "invalid_arguments",
                f"Expected {type_name} argument, received {type(value).__name__}.",
                {"type": type_name, "context": context},
            )
        inner_type = _list_inner_type(type_name)
        return [
            _normalize_runtime_value(
                item,
                inner_type,
                struct_specs=resolved_struct_specs,
                context=f"{context}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    if _is_struct_type(type_name, resolved_struct_specs):
        return _normalize_struct_runtime_value(
            value,
            type_name,
            struct_specs=resolved_struct_specs,
            context=context,
        )
    raise MojoLibraryError(
        "unsupported_signature",
        f"Unsupported Mojo runtime type '{type_name}'.",
        {"type": type_name, "context": context},
    )


def _is_list_type(type_name: str) -> bool:
    return type_name.startswith("List[") and type_name.endswith("]")


def _list_inner_type(type_name: str) -> str:
    return type_name[5:-1]


def _emit_mojo_value(
    *,
    value: Any,
    type_name: str,
    variable_name: str,
    lines: list[str],
) -> str:
    normalized_value = _normalize_runtime_value(value, type_name)
    if _is_list_type(type_name):
        inner_type = _list_inner_type(type_name)
        lines.append(f"    var {variable_name} = {type_name}()")
        for index, item in enumerate(normalized_value):
            item_expr = _emit_mojo_value(
                value=item,
                type_name=inner_type,
                variable_name=f"{variable_name}_{index}",
                lines=lines,
            )
            suffix = "^" if _is_list_type(inner_type) else ""
            lines.append(f"    {variable_name}.append({item_expr}{suffix})")
        return variable_name
    return _mojo_scalar_literal(normalized_value, type_name)


def _normalize_provided_args(
    args: Any,
    function_spec: RuntimeFunctionSpec,
    *,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
) -> tuple[Any, ...]:
    params = list(function_spec.params)
    if args is None:
        provided_args: list[Any] = []
    elif isinstance(args, list):
        provided_args = args
    elif isinstance(args, dict):
        provided_args = []
        saw_missing_default = False
        for param in params:
            if param.name in args:
                if saw_missing_default:
                    raise MojoLibraryError(
                        "invalid_arguments",
                        (
                            "Named arguments must not skip an earlier defaulted "
                            f"parameter before providing '{param.name}'."
                        ),
                        {"module": function_spec.name, "parameter": param.name},
                    )
                provided_args.append(args[param.name])
                continue
            if param.has_default:
                saw_missing_default = True
                continue
            raise MojoLibraryError(
                "invalid_arguments",
                f"Missing required argument '{param.name}'.",
                {"parameter": param.name},
            )
        extra_keys = sorted(set(args) - {param.name for param in params})
        if extra_keys:
            raise MojoLibraryError(
                "invalid_arguments",
                f"Unexpected argument keys: {', '.join(extra_keys)}.",
                {"extra_keys": extra_keys},
            )
    else:
        provided_args = [args]

    required_count = sum(1 for param in params if not param.has_default)
    if len(provided_args) < required_count:
        raise MojoLibraryError(
            "invalid_arguments",
            (
                f"Function '{function_spec.name}' requires at least {required_count} "
                f"arguments, received {len(provided_args)}."
            ),
            {"required": required_count, "received": len(provided_args)},
        )
    if len(provided_args) > len(params):
        raise MojoLibraryError(
            "invalid_arguments",
            (
                f"Function '{function_spec.name}' accepts at most {len(params)} "
                f"arguments, received {len(provided_args)}."
            ),
            {"accepted": len(params), "received": len(provided_args)},
        )

    normalized_args: list[Any] = []
    for param, value in zip(params, provided_args, strict=False):
        normalized_args.append(
            _normalize_runtime_value(
                value,
                param.typ,
                struct_specs=struct_specs,
                context=f"args.{param.name}",
            )
        )
    return tuple(normalized_args)


def _normalize_call_arguments(
    args: Any,
    function_spec: RuntimeFunctionSpec,
    *,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
) -> tuple[list[str], list[str]]:
    provided_args = _normalize_provided_args(args, function_spec, struct_specs=struct_specs)
    prep_lines: list[str] = []
    call_arguments: list[str] = []
    for index, (param, value) in enumerate(zip(function_spec.params, provided_args, strict=False)):
        call_arguments.append(
            _emit_mojo_value(
                value=value,
                type_name=param.typ,
                variable_name=f"__algenta_arg_{index}",
                lines=prep_lines,
            )
        )
    return prep_lines, call_arguments


def build_runtime_library_worker_request(
    module_name: str,
    function_name: str,
    args: Any,
) -> tuple[RuntimeFunctionSpec, dict[str, Any]]:
    _, function_spec = find_runtime_function(module_name, function_name)
    normalized_args = _normalize_provided_args(
        args,
        function_spec,
        struct_specs=_module_struct_specs(module_name),
    )
    return function_spec, {
        "type": "library_execute",
        "engine_type": "library_execute",
        "module": module_name,
        "function": function_name,
        "args": list(normalized_args),
    }


def parse_runtime_library_worker_response(
    module_name: str,
    function_name: str,
    response: Any,
    *,
    function_spec: RuntimeFunctionSpec | None = None,
) -> Any:
    if function_spec is None:
        _, function_spec = find_runtime_function(module_name, function_name)

    if not isinstance(response, dict):
        raise MojoLibraryError(
            "mojo_library_execution_failed",
            (
                "Mojo library worker returned a malformed response for "
                f"{module_name}.{function_name}."
            ),
            {"module": module_name, "function": function_name, "response": response},
        )

    error_message = response.get("error")
    if isinstance(error_message, str) and error_message.strip():
        error_code = str(response.get("error_code") or "mojo_library_execution_failed")
        details = {
            "module": module_name,
            "function": function_name,
            "response": response,
        }
        if function_spec is not None:
            details["return_type"] = function_spec.return_type
        raise MojoLibraryError(
            error_code,
            str(response.get("error_message") or error_message),
            details,
        )

    if "result" not in response:
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            (f"Mojo library worker completed without a result for {module_name}.{function_name}."),
            {"module": module_name, "function": function_name, "response": response},
        )
    struct_specs = _module_struct_specs(module_name)
    decoded_result = _decode_transport_value(
        response["result"],
        function_spec.return_type,
        struct_specs=struct_specs,
        context="result",
    )

    raw_mutated_args = response.get("mutated_args")
    if not isinstance(raw_mutated_args, dict) or len(raw_mutated_args) == 0:
        return decoded_result

    decoded_mutations: dict[str, Any] = {}
    for raw_index, raw_value in raw_mutated_args.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                "Mutable argument payload contains a non-numeric argument index.",
                {"index": raw_index, "module": module_name, "function": function_name},
            ) from exc
        if index < 0 or index >= len(function_spec.params):
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                "Mutable argument payload contains an out-of-range argument index.",
                {
                    "index": index,
                    "module": module_name,
                    "function": function_name,
                    "param_count": len(function_spec.params),
                },
            )
        param = function_spec.params[index]
        decoded_mutations[param.name] = _decode_transport_value(
            raw_value,
            param.typ,
            struct_specs=struct_specs,
            context=f"mutated_args.{param.name}",
        )

    return {
        "result": decoded_result,
        "mutated_args": decoded_mutations,
    }


def _decode_transport_value(
    value: Any,
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec],
    context: str,
) -> Any:
    if _is_list_type(type_name):
        if not isinstance(value, list):
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                f"Expected list result for {context} ({type_name}), received {type(value).__name__}.",
                {"type": type_name, "context": context, "value": value},
            )
        inner = _list_inner_type(type_name)
        return [
            _decode_transport_value(
                item,
                inner,
                struct_specs=struct_specs,
                context=f"{context}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    if type_name in struct_specs:
        return _decode_struct_transport_value(
            value,
            type_name,
            struct_specs=struct_specs,
            context=context,
        )
    return _normalize_runtime_value(value, type_name, context=context)


def _decode_struct_transport_value(
    value: Any,
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec],
    context: str,
) -> dict[str, Any]:
    spec = struct_specs.get(type_name)
    if spec is None:
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            f"Unsupported struct result type '{type_name}'.",
            {"type": type_name, "context": context},
        )
    if not isinstance(value, dict):
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            f"Expected object payload for struct {type_name}.",
            {"type": type_name, "context": context, "value": value},
        )

    if value.get(_STRUCT_ENVELOPE_TYPE_KEY) not in {None, type_name}:
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            f"Struct result envelope type mismatch for {type_name}.",
            {
                "expected": type_name,
                "actual": value.get(_STRUCT_ENVELOPE_TYPE_KEY),
                "context": context,
            },
        )

    field_values = value.get(_STRUCT_ENVELOPE_VALUES_KEY)
    if isinstance(field_values, list):
        if len(field_values) != len(spec.fields):
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                f"Struct result for {type_name} has {len(field_values)} fields; expected {len(spec.fields)}.",
                {"type": type_name, "context": context},
            )
        payload_map = {
            field.name: field_values[index]
            for index, field in enumerate(spec.fields)
        }
    else:
        payload_map = value

    decoded: dict[str, Any] = {}
    for field in spec.fields:
        if field.name not in payload_map:
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                f"Missing struct field '{field.name}' in {type_name} result.",
                {"type": type_name, "field": field.name, "context": context},
            )
        decoded[field.name] = _decode_transport_value(
            payload_map[field.name],
            field.typ,
            struct_specs=struct_specs,
            context=f"{context}.{field.name}",
        )
    return decoded


def _render_wrapper(
    module_name: str,
    function_spec: RuntimeFunctionSpec,
    args: Any,
) -> str:
    prep_lines, call_arguments = _normalize_call_arguments(args, function_spec)
    call_expression = f"{function_spec.name}({', '.join(call_arguments)})"
    lines = [
        f"from {module_name} import {function_spec.name}",
        "",
        "def main() raises:",
        *prep_lines,
    ]
    if function_spec.return_type == "None":
        lines.extend(
            [
                f"    _ = {call_expression}",
                '    print("__ALGENTA_NONE__")',
            ]
        )
    else:
        lines.extend(
            [
                f"    var __algenta_result = {call_expression}",
                "    print(__algenta_result)",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _runtime_env() -> dict[str, str]:
    _MODULAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _MODULAR_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "MODULAR_HOME": str(_MODULAR_HOME),
        "MODULAR_CACHE_DIR": str(_MODULAR_CACHE_DIR),
        "XDG_DATA_HOME": str(_MODULAR_DATA_DIR),
        "MODULAR_TELEMETRY_ENABLED": "0",
    }


def _mojo_command(wrapper_path: Path) -> list[str]:
    if not library_runtime_available():
        raise MojoLibraryError(
            "compute_runtime_unavailable",
            (
                "Mojo library runtime is unavailable. Install the local Mojo toolchain "
                "and ensure mojo_env is present before executing runtime-owned libraries."
            ),
        )
    return [str(_MOJO_BIN), "run", f"-I{_ENGINE_DIR}", str(wrapper_path)]


def _parse_result(stdout: str, return_type: str) -> Any:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            "Mojo library execution completed without producing a result.",
            {"return_type": return_type},
        )
    raw = lines[-1]
    if raw == "__ALGENTA_NONE__":
        return None
    if return_type == "Bool":
        if raw == "True":
            return True
        if raw == "False":
            return False
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            f"Unable to parse Bool result: {raw!r}.",
            {"return_type": return_type, "raw": raw},
        )
    if return_type in {"Float32", "Float64"}:
        try:
            return float(raw)
        except ValueError as exc:
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                f"Unable to parse numeric result: {raw!r}.",
                {"return_type": return_type, "raw": raw},
            ) from exc
    if return_type in {"Int", "UInt8", "UInt16", "UInt32", "UInt64"}:
        try:
            return int(raw)
        except ValueError as exc:
            raise MojoLibraryError(
                "mojo_result_parse_failed",
                f"Unable to parse integer result: {raw!r}.",
                {"return_type": return_type, "raw": raw},
            ) from exc
    if return_type == "String":
        # Mojo prints String values without JSON quoting; preserve the raw line.
        return raw
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError) as exc:
        raise MojoLibraryError(
            "mojo_result_parse_failed",
            f"Unable to parse runtime result for type '{return_type}'.",
            {"return_type": return_type, "raw": raw},
        ) from exc


async def execute_runtime_library(
    module_name: str,
    function_name: str,
    args: Any,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    _, function_spec = find_runtime_function(module_name, function_name)
    wrapper_source = _render_wrapper(module_name, function_spec, args)
    wrapper_path = Path(tempfile.mkstemp(prefix="algenta_runtime_", suffix=".mojo")[1])
    try:
        wrapper_path.write_text(wrapper_source, encoding="utf-8")
        process = await asyncio.create_subprocess_exec(
            *_mojo_command(wrapper_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_MOJO_ENV),
            env=_runtime_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise MojoLibraryError(
                "mojo_library_timeout",
                (
                    f"Mojo library execution timed out after {timeout_seconds:.1f}s "
                    f"for {module_name}.{function_name}."
                ),
                {"module": module_name, "function": function_name},
            ) from exc

        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            raise MojoLibraryError(
                "mojo_library_execution_failed",
                (
                    f"Mojo library execution failed for {module_name}.{function_name}: "
                    f"{stderr_text or f'exit code {process.returncode}'}"
                ),
                {
                    "module": module_name,
                    "function": function_name,
                    "stderr": stderr_text,
                    "returncode": process.returncode,
                },
            )

        return _parse_result(stdout.decode("utf-8", errors="replace"), function_spec.return_type)
    finally:
        try:
            wrapper_path.unlink(missing_ok=True)
        except OSError:
            pass
