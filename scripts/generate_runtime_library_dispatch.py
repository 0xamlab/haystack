from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from apps.runtime.mojo_inventory import RuntimeFunctionSpec, RuntimeLibraryModule, RuntimeStructSpec

TARGET = ROOT / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo"
INDENT = " " * 4
_STRUCT_ENVELOPE_TYPE_KEY = "__algenta_struct"
_STRUCT_ENVELOPE_VALUES_KEY = "v"


def _is_list_type(type_name: str) -> bool:
    return type_name.startswith("List[") and type_name.endswith("]")


def _list_inner_type(type_name: str) -> str:
    return type_name[5:-1]


def _type_depth(type_name: str) -> int:
    depth = 0
    current = type_name
    while _is_list_type(current):
        depth += 1
        current = _list_inner_type(current)
    return depth


def _sanitize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _type_fn_suffix(type_name: str) -> str:
    return _sanitize_identifier(type_name.replace("[", "_").replace("]", ""))


def _function_alias(module_path: str, function_name: str) -> str:
    return f"_{_sanitize_identifier(module_path)}__{_sanitize_identifier(function_name)}"


def _register_type(type_name: str, collected: set[str]) -> None:
    collected.add(type_name)
    if _is_list_type(type_name):
        _register_type(_list_inner_type(type_name), collected)


def _ordered_types(type_names: set[str]) -> list[str]:
    return sorted(type_names, key=lambda item: (_type_depth(item), item))


def _parse_fn_name(type_name: str) -> str:
    return f"_parse_{_type_fn_suffix(type_name)}_token"


def _to_json_fn_name(type_name: str) -> str:
    return f"_to_json_{_type_fn_suffix(type_name)}"


def _emit_scalar_parse_function(type_name: str) -> list[str]:
    fn_name = _parse_fn_name(type_name)
    if type_name == "Bool":
        return [
            f"fn {fn_name}(token: String) raises -> Bool:",
            f'{INDENT}if token == "true":',
            f"{INDENT * 2}return True",
            f'{INDENT}if token == "false":',
            f"{INDENT * 2}return False",
            f'{INDENT}raise Error("Expected Bool token, received " + token)',
            "",
        ]
    if type_name == "String":
        return [
            f"fn {fn_name}(token: String) raises -> String:",
            f"{INDENT}return _unquote_json_string(token)",
            "",
        ]
    if type_name == "Int":
        return [
            f"fn {fn_name}(token: String) raises -> Int:",
            f"{INDENT}return parse_int(token)",
            "",
        ]
    if type_name == "Float64":
        return [
            f"fn {fn_name}(token: String) raises -> Float64:",
            f"{INDENT}return parse_float64(token)",
            "",
        ]
    if type_name == "Float32":
        return [
            f"fn {fn_name}(token: String) raises -> Float32:",
            f"{INDENT}return Float32(parse_float64(token))",
            "",
        ]
    if type_name in {"UInt8", "UInt16", "UInt32", "UInt64"}:
        return [
            f"fn {fn_name}(token: String) raises -> {type_name}:",
            f"{INDENT}var parsed = parse_int(token)",
            f"{INDENT}if parsed < 0:",
            (
                f"{INDENT * 2}raise Error("
                f'"Expected non-negative {type_name} token, received " + token)'
            ),
            f"{INDENT}return {type_name}(parsed)",
            "",
        ]
    raise ValueError(f"Unsupported scalar type for parse generation: {type_name}")


def _emit_list_parse_function(type_name: str) -> list[str]:
    inner_type = _list_inner_type(type_name)
    inner_parse = _parse_fn_name(inner_type)
    fn_name = _parse_fn_name(type_name)
    suffix = "^" if _is_list_type(inner_type) else ""
    return [
        f"fn {fn_name}(token: String) raises -> {type_name}:",
        f'{INDENT}var wrapped = "{{\\"v\\":" + token + "}}"',
        f'{INDENT}var array_json = json_get_array(wrapped, "v")',
        f"{INDENT}var count = json_array_len(array_json)",
        f"{INDENT}var result = {type_name}()",
        f"{INDENT}for i in range(count):",
        f"{INDENT * 2}result.append({inner_parse}(json_array_get(array_json, i)){suffix})",
        f"{INDENT}return result^",
        "",
    ]


def _emit_struct_parse_function(
    type_name: str,
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
) -> list[str]:
    spec = struct_specs[type_name]
    fn_name = _parse_fn_name(type_name)
    lines = [
        f"fn {fn_name}(token: String) raises -> {type_name}:",
        f'{INDENT}var values_json = json_get_array(token, "{_STRUCT_ENVELOPE_VALUES_KEY}")',
        f"{INDENT}if json_array_len(values_json) != {len(spec.fields)}:",
        (
            f'{INDENT * 2}raise Error("Expected {len(spec.fields)} fields for {type_name}, '
            'received " + String(json_array_len(values_json)))'
        ),
    ]
    for index, field in enumerate(spec.fields):
        lines.append(
            f"{INDENT}var field_{index} = {_parse_fn_name(field.typ)}(json_array_get(values_json, {index}))"
        )
    field_args = ", ".join(f"field_{index}" for index in range(len(spec.fields)))
    lines.append(f"{INDENT}return {type_name}({field_args})")
    lines.append("")
    return lines


def _emit_parse_functions(
    type_names: set[str],
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
) -> list[str]:
    lines: list[str] = []
    for type_name in _ordered_types(type_names):
        if type_name == "None":
            continue
        if _is_list_type(type_name):
            lines.extend(_emit_list_parse_function(type_name))
        elif type_name in struct_specs:
            lines.extend(_emit_struct_parse_function(type_name, struct_specs=struct_specs))
        else:
            lines.extend(_emit_scalar_parse_function(type_name))
    return lines


def _emit_scalar_to_json_function(type_name: str) -> list[str]:
    fn_name = _to_json_fn_name(type_name)
    if type_name == "Bool":
        return [
            f"fn {fn_name}(value: Bool) -> String:",
            f'{INDENT}return "true" if value else "false"',
            "",
        ]
    if type_name == "String":
        return [
            f"fn {fn_name}(value: String) -> String:",
            f'{INDENT}return "\\"" + _escape_json_string(value) + "\\""',
            "",
        ]
    if type_name == "None":
        return [
            f"fn {fn_name}() -> String:",
            f'{INDENT}return "null"',
            "",
        ]
    if type_name in {"Float32", "Float64"}:
        return [
            f"fn {fn_name}(value: {type_name}) -> String:",
            f"{INDENT}return String(value)",
            "",
        ]
    if type_name in {"Int", "UInt8", "UInt16", "UInt32", "UInt64"}:
        return [
            f"fn {fn_name}(value: {type_name}) -> String:",
            f"{INDENT}return String(value)",
            "",
        ]
    raise ValueError(f"Unsupported scalar type for JSON generation: {type_name}")


def _emit_list_to_json_function(type_name: str) -> list[str]:
    inner_type = _list_inner_type(type_name)
    inner_json = _to_json_fn_name(inner_type)
    fn_name = _to_json_fn_name(type_name)
    return [
        f"fn {fn_name}(value: {type_name}) -> String:",
        f'{INDENT}var result = String("[")',
        f"{INDENT}for i in range(len(value)):",
        f"{INDENT * 2}if i > 0:",
        f'{INDENT * 3}result += ","',
        f"{INDENT * 2}result += {inner_json}(value[i])",
        f'{INDENT}result += "]"',
        f"{INDENT}return result",
        "",
    ]


def _emit_struct_to_json_function(
    type_name: str,
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
) -> list[str]:
    spec = struct_specs[type_name]
    fn_name = _to_json_fn_name(type_name)
    lines = [
        f"fn {fn_name}(value: {type_name}) -> String:",
        f'{INDENT}var result = String("{{\\"{_STRUCT_ENVELOPE_TYPE_KEY}\\":\\"{type_name}\\",\\"{_STRUCT_ENVELOPE_VALUES_KEY}\\":[")',
    ]
    for index, field in enumerate(spec.fields):
        if index > 0:
            lines.append(f'{INDENT}result += ","')
        lines.append(f"{INDENT}result += {_to_json_fn_name(field.typ)}(value.{field.name})")
    lines.extend(
        [
            f'{INDENT}result += "]}}"',
            f"{INDENT}return result",
            "",
        ]
    )
    return lines


def _emit_to_json_functions(
    type_names: set[str],
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
) -> list[str]:
    lines: list[str] = []
    ordered = _ordered_types(type_names)
    if "None" in type_names:
        lines.extend(_emit_scalar_to_json_function("None"))
    for type_name in ordered:
        if type_name == "None":
            continue
        if _is_list_type(type_name):
            lines.extend(_emit_list_to_json_function(type_name))
        elif type_name in struct_specs:
            lines.extend(_emit_struct_to_json_function(type_name, struct_specs=struct_specs))
        else:
            lines.extend(_emit_scalar_to_json_function(type_name))
    return lines


def _emit_imports(modules: tuple[RuntimeLibraryModule, ...]) -> list[str]:
    lines: list[str] = []
    for module in modules:
        lines.append(f"from {module.import_path} import (")
        for function in module.functions:
            alias = _function_alias(module.import_path, function.name)
            lines.append(f"{INDENT}{function.name} as {alias},")
        lines.append(")")
        lines.append("")
    return lines


def _emit_module_dispatch(module: RuntimeLibraryModule) -> list[str]:
    helper_name = f"_dispatch_{_sanitize_identifier(module.import_path)}"
    lines = [
        f"fn {helper_name}(function_name: String, args_array: String) raises -> String:",
        f"{INDENT}var arg_count = json_array_len(args_array)",
    ]
    for function in module.functions:
        lines.extend(_emit_function_dispatch(module.import_path, function))
    lines.extend(
        [
            f"{INDENT}return _error_json(",
            f'{INDENT * 2}"function_not_registered",',
            (
                f'{INDENT * 2}"Function \'" + function_name + "\' is not registered for module '
                f'{module.import_path}."'
            ),
            f"{INDENT})",
            "",
        ]
    )
    return lines


def _accepted_arities(function: RuntimeFunctionSpec) -> tuple[int, ...]:
    required = sum(1 for param in function.params if not param.has_default)
    return tuple(range(required, len(function.params) + 1))


def _emit_function_dispatch(module_name: str, function: RuntimeFunctionSpec) -> list[str]:
    lines = [f'{INDENT}if function_name == "{function.name}":']
    accepted = _accepted_arities(function)
    function_alias = _function_alias(module_name, function.name)
    mutable_param_indices = [index for index, param in enumerate(function.params) if param.is_mut]
    for arity in accepted:
        lines.append(f"{INDENT * 2}if arg_count == {arity}:")
        lines.append(f"{INDENT * 3}try:")
        for index, param in enumerate(function.params[:arity]):
            parse_fn = _parse_fn_name(param.typ)
            lines.append(
                f"{INDENT * 4}var arg_{index} = {parse_fn}(json_array_get(args_array, {index}))"
            )
        call_args = ", ".join(f"arg_{index}" for index in range(arity))
        if function.return_type == "None":
            lines.append(f"{INDENT * 4}_ = {function_alias}({call_args})")
            lines.append(f'{INDENT * 4}var result_json = "null"')
        else:
            to_json_fn = _to_json_fn_name(function.return_type)
            lines.append(f"{INDENT * 4}var result = {function_alias}({call_args})")
            lines.append(f"{INDENT * 4}var result_json = {to_json_fn}(result)")

        if mutable_param_indices:
            lines.append(f'{INDENT * 4}var mutated_args_json = String("{{")')
            active_mut_indices = [index for index in mutable_param_indices if index < arity]
            for mut_position, index in enumerate(active_mut_indices):
                if mut_position > 0:
                    lines.append(f'{INDENT * 4}mutated_args_json += ","')
                param = function.params[index]
                to_json_fn = _to_json_fn_name(param.typ)
                lines.append(
                    f'{INDENT * 4}mutated_args_json += "\\"{index}\\":" + {to_json_fn}(arg_{index})'
                )
            lines.append(f'{INDENT * 4}mutated_args_json += "}}"')
            lines.append(
                f"{INDENT * 4}return _success_with_mutated_args_json(result_json, mutated_args_json)"
            )
        else:
            lines.append(f"{INDENT * 4}return _success_json(result_json)")
        lines.append(f"{INDENT * 3}except:")
        lines.append(f"{INDENT * 4}return _error_json(")
        lines.append(f'{INDENT * 5}"mojo_library_execution_failed",')
        lines.append(
            f'{INDENT * 5}"Mojo library execution failed for {module_name}.{function.name}."'
        )
        lines.append(f"{INDENT * 4})")
    expected_text = " or ".join(str(arity) for arity in accepted)
    lines.extend(
        [
            f"{INDENT * 2}return _error_json(",
            f'{INDENT * 3}"invalid_arguments",',
            (
                f'{INDENT * 3}"Function {module_name}.{function.name} expected {expected_text} '
                'arguments, received " + String(arg_count) + "."'
            ),
            f"{INDENT * 2})",
        ]
    )
    return lines


def render_dispatch_source(modules: tuple[RuntimeLibraryModule, ...]) -> str:
    param_types: set[str] = set()
    result_types: set[str] = set()
    struct_specs: dict[str, RuntimeStructSpec] = {}
    from apps.runtime.mojo_inventory import parse_runtime_struct_specs

    for module in modules:
        for struct_name, struct_spec in parse_runtime_struct_specs(module.path).items():
            struct_specs.setdefault(struct_name, struct_spec)

    def register_value_type(type_name: str, collected: set[str]) -> None:
        _register_type(type_name, collected)
        if type_name in struct_specs:
            for field in struct_specs[type_name].fields:
                register_value_type(field.typ, collected)

    for module in modules:
        for function in module.functions:
            for param in function.params:
                register_value_type(param.typ, param_types)
            register_value_type(function.return_type, result_types)

    lines = [
        '"""',
        (
            "runtime_library_dispatch_generated.mojo — AUTO-GENERATED by "
            "scripts/generate_runtime_library_dispatch.py."
        ),
        "Do not edit by hand.",
        '"""',
        "from conv import parse_float64, parse_int",
        "from json.parser import json_get_array, json_get_string, json_array_len, json_array_get",
        "",
    ]
    lines.extend(_emit_imports(modules))
    lines.extend(
        [
            "fn _unquote_json_string(token: String) -> String:",
            f"{INDENT}var n = len(token)",
            f"{INDENT}if n < 2:",
            f"{INDENT * 2}return token",
            f"{INDENT}var bytes = token.as_bytes()",
            f"{INDENT}if bytes[0] != UInt8(34) or bytes[n - 1] != UInt8(34):",
            f"{INDENT * 2}return token",
            f'{INDENT}var result = String("")',
            f"{INDENT}var i = 1",
            f"{INDENT}while i < n - 1:",
            f"{INDENT * 2}if bytes[i] == UInt8(92) and i + 1 < n - 1:",
            f"{INDENT * 3}var nxt = bytes[i + 1]",
            f"{INDENT * 3}if nxt == UInt8(34):",
            f"{INDENT * 4}result += '\"'",
            f"{INDENT * 3}elif nxt == UInt8(92):",
            f'{INDENT * 4}result += "\\\\"',
            f"{INDENT * 3}elif nxt == UInt8(110):",
            f'{INDENT * 4}result += "\\n"',
            f"{INDENT * 3}elif nxt == UInt8(116):",
            f'{INDENT * 4}result += "\\t"',
            f"{INDENT * 3}elif nxt == UInt8(114):",
            f'{INDENT * 4}result += "\\r"',
            f"{INDENT * 3}elif nxt == UInt8(47):",
            f'{INDENT * 4}result += "/"',
            f"{INDENT * 3}else:",
            f"{INDENT * 4}result += chr(Int(nxt))",
            f"{INDENT * 3}i += 2",
            f"{INDENT * 3}continue",
            f"{INDENT * 2}result += chr(Int(bytes[i]))",
            f"{INDENT * 2}i += 1",
            f"{INDENT}return result",
            "",
            "fn _escape_json_string(value: String) -> String:",
            f'{INDENT}var result = String("")',
            f"{INDENT}var bytes = value.as_bytes()",
            f"{INDENT}for i in range(len(value)):",
            f"{INDENT * 2}var b = bytes[i]",
            f"{INDENT * 2}if b == UInt8(34):",
            f'{INDENT * 3}result += "\\\\\\""',
            f"{INDENT * 2}elif b == UInt8(92):",
            f'{INDENT * 3}result += "\\\\\\\\"',
            f"{INDENT * 2}elif b == UInt8(10):",
            f'{INDENT * 3}result += "\\\\n"',
            f"{INDENT * 2}elif b == UInt8(13):",
            f'{INDENT * 3}result += "\\\\r"',
            f"{INDENT * 2}elif b == UInt8(9):",
            f'{INDENT * 3}result += "\\\\t"',
            f"{INDENT * 2}else:",
            f"{INDENT * 3}result += chr(Int(b))",
            f"{INDENT}return result",
            "",
            "fn _success_json(result_json: String) -> String:",
            f'{INDENT}return "{{\\"result\\":" + result_json + "}}"',
            "",
            "fn _success_with_mutated_args_json(result_json: String, mutated_args_json: String) -> String:",
            f'{INDENT}return "{{\\"result\\":" + result_json + ",\\"mutated_args\\":" + mutated_args_json + "}}"',
            "",
            "fn _error_json(code: String, message: String) -> String:",
            (
                f'{INDENT}return "{{\\"error\\":\\"" + code + ": " + _escape_json_string(message) '
                '+ "\\",\\"error_code\\":\\"" + code + "\\",\\"error_message\\":\\"" '
                '+ _escape_json_string(message) + "\\"}"'
            ),
            "",
        ]
    )
    lines.extend(_emit_parse_functions(param_types, struct_specs=struct_specs))
    lines.extend(_emit_to_json_functions(result_types, struct_specs=struct_specs))
    for module in modules:
        lines.extend(_emit_module_dispatch(module))
    lines.extend(
        [
            "fn dispatch_runtime_library(raw: String) raises -> String:",
            f'{INDENT}var module_name = json_get_string(raw, "module")',
            f"{INDENT}if len(module_name) == 0:",
            (
                f"{INDENT * 2}return _error_json("
                '"invalid_arguments", '
                '"library_execute request requires a non-empty module.")'
            ),
            f'{INDENT}var function_name = json_get_string(raw, "function")',
            f"{INDENT}if len(function_name) == 0:",
            (
                f"{INDENT * 2}return _error_json("
                '"invalid_arguments", '
                '"library_execute request requires a non-empty function.")'
            ),
            f'{INDENT}var args_array = json_get_array(raw, "args")',
            f"{INDENT}if len(args_array) == 0:",
            f'{INDENT * 2}args_array = "[]"',
        ]
    )
    for module in modules:
        helper_name = f"_dispatch_{_sanitize_identifier(module.import_path)}"
        lines.append(f'{INDENT}if module_name == "{module.import_path}":')
        lines.append(f"{INDENT * 2}return {helper_name}(function_name, args_array)")
    lines.extend(
        [
            f"{INDENT}return _error_json(",
            f'{INDENT * 2}"module_not_registered",',
            (
                f'{INDENT * 2}"Module \'" + module_name + "\' is not registered '
                'in the executable Mojo runtime inventory."'
            ),
            f"{INDENT})",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    from apps.runtime.mojo_inventory import discover_runtime_library_modules

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args()
    modules = discover_runtime_library_modules(executable_only=True)
    rendered = render_dispatch_source(modules)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
