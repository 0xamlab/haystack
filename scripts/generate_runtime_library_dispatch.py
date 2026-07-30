from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from apps.runtime.mojo_inventory import (
        RuntimeFunctionSpec,
        RuntimeLibraryModule,
        RuntimeStructSpec,
    )

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


def _module_dispatch_name(import_path: str) -> str:
    # Sanitize each dotted segment independently and join with "__" so a
    # top-level module (e.g. "graph_algorithms") cannot collapse onto a
    # sub-package module (e.g. "graph.algorithms"). Both previously sanitized
    # to "graph_algorithms", producing duplicate `_dispatch_graph_algorithms`.
    return "__".join(_sanitize_identifier(part) for part in import_path.split("."))


_SCALAR_RUNTIME_TYPES = {
    "Bool",
    "Float32",
    "Float64",
    "Int",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
}


def _clean_field_type(raw: str) -> str:
    return raw.split("=", 1)[0].split("#", 1)[0].strip()


def _clean_param_type(raw: str) -> str:
    cleaned = raw.split("=", 1)[0].split("#", 1)[0].strip()
    for prefix in ("owned ", "mut ", "inout ", "read ", "borrowed ", "var "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def _init_param_types(signature: str) -> list[str]:
    """Non-`self` positional param TYPES of an __init__ signature, in order."""
    open_paren = signature.find("(")
    if open_paren < 0:
        return []
    depth = 0
    params_str = ""
    for ch in signature[open_paren:]:
        if ch in "([":
            depth += 1
            if depth == 1 and ch == "(":
                continue
        elif ch in ")]":
            depth -= 1
            if depth == 0:
                break
        params_str += ch
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in params_str:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    types: list[str] = []
    for part in parts:
        if not part or ":" not in part:
            continue  # skips `self` / `out self` / `*args` (no annotation)
        name_part, type_part = part.split(":", 1)
        if name_part.strip().split()[-1] == "self":
            continue
        types.append(_clean_param_type(type_part))
    return types


def _parse_struct_defs(path) -> dict[str, tuple[list[tuple[str, str]], str]]:
    """Generator-local struct parser: {name: (fields, construction)}.

    `fields` are the `var name: type` declarations at the struct's own body
    indent (NOT method-local vars, which mojo_inventory's parser misreads as
    fields — e.g. DataFrame.sum_val).

    `construction` is how a decoder can build the struct, resolved from the
    source rather than assumed:

    * ``"positional"`` — `Name(field_0, ..., field_{n-1})`. Available when a
      @value / @fieldwise_init decorator synthesises a field-ordered
      constructor, or an explicit __init__ takes exactly the fields, in order,
      BY TYPE (matching arity alone is not enough — e.g. Tensor1D(data, size)
      vs its __init__(size, fill)).
    * ``"assign"`` — `var v = Name(); v.field = ...`. Available when the struct
      has a zero-argument __init__ and at least one field. Structs such as
      SVMModel / PLSResult / GRUState only offer this shape; emitting positional
      construction for them produces code that does not compile.
    * ``"none"`` — cannot be built from a payload at all. The struct and every
      function touching it must be excluded rather than emitted.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    result: dict[str, tuple[list[tuple[str, str]], bool]] = {}
    n = len(lines)
    i = 0
    while i < n:
        match = re.match(r"^(\s*)struct\s+([A-Za-z_][A-Za-z0-9_]*)", lines[i])
        if match is None:
            i += 1
            continue
        struct_indent = len(match.group(1))
        name = match.group(2)
        deco_memberwise = False
        j = i - 1
        while j >= 0:
            decorator = lines[j].strip()
            if not decorator:
                j -= 1
                continue
            if decorator.startswith("@"):
                if "value" in decorator or "fieldwise_init" in decorator:
                    deco_memberwise = True
                j -= 1
                continue
            break
        i += 1
        fields: list[tuple[str, str]] = []
        init_signatures: list[list[str]] = []
        has_init = False
        body_indent: int | None = None
        while i < n:
            raw = lines[i]
            stripped = raw.strip()
            cur_indent = len(raw) - len(raw.lstrip(" "))
            if stripped and cur_indent <= struct_indent:
                break
            if stripped and body_indent is None:
                body_indent = cur_indent
            if cur_indent == body_indent:
                field_match = re.match(
                    r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", raw
                )
                if field_match is not None:
                    fields.append(
                        (field_match.group(1), _clean_field_type(field_match.group(2)))
                    )
                if re.match(r"^\s*fn\s+__init__\s*\(", raw):
                    has_init = True
                    sig = stripped
                    k = i
                    while ")" not in sig and k + 1 < n:
                        k += 1
                        sig += " " + lines[k].strip()
                    init_signatures.append(_init_param_types(sig))
            i += 1
        field_types = [field_typ for _, field_typ in fields]
        if deco_memberwise or (has_init and any(field_types == sig for sig in init_signatures)):
            construction = "positional"
        elif has_init and any(len(sig) == 0 for sig in init_signatures) and fields:
            construction = "assign"
        else:
            construction = "none"
        result[name] = (fields, construction)
    return result


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
    # List[Float64] is the hot path (flat pixel buffers for the image kernels). Route it to the
    # single-pass parser that ALSO accepts a "@u8:<base64>" binary buffer — O(n), no per-element
    # text parse. The generic list path below is likewise single-pass (json_array_tokens), so no
    # list type pays the old O(n^2) `json_array_get(arr, i)`-per-index re-scan.
    if type_name == "List[Float64]":
        return [
            f"fn {fn_name}(token: String) raises -> {type_name}:",
            f"{INDENT}return json_parse_float64_list(token)",
            "",
        ]
    return [
        f"fn {fn_name}(token: String) raises -> {type_name}:",
        f'{INDENT}var wrapped = "{{\\"v\\":" + token + "}}"',
        f'{INDENT}var array_json = json_get_array(wrapped, "v")',
        f"{INDENT}var _elem_tokens = json_array_tokens(array_json)",
        f"{INDENT}var result = {type_name}()",
        f"{INDENT}for _i in range(len(_elem_tokens)):",
        f"{INDENT * 2}result.append({inner_parse}(_elem_tokens[_i]){suffix})",
        f"{INDENT}return result^",
        "",
    ]


def _emit_struct_parse_function(
    type_name: str,
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
    struct_construction: dict[str, str],
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

    construction = struct_construction.get(type_name, "positional")
    if construction == "assign":
        # The struct has no field-ordered constructor, only `__init__(out self)`.
        # Default-construct, then assign each decoded field.
        lines.append(f"{INDENT}var decoded = {type_name}()")
        for index, field in enumerate(spec.fields):
            lines.append(f"{INDENT}decoded.{field.name} = field_{index}^")
        lines.append(f"{INDENT}return decoded^")
    else:
        field_args = ", ".join(f"field_{index}^" for index in range(len(spec.fields)))
        lines.append(f"{INDENT}return {type_name}({field_args})")
    lines.append("")
    return lines


def _emit_parse_functions(
    type_names: set[str],
    *,
    struct_specs: dict[str, "RuntimeStructSpec"],
    struct_construction: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    for type_name in _ordered_types(type_names):
        if type_name == "None":
            continue
        if _is_list_type(type_name):
            lines.extend(_emit_list_parse_function(type_name))
        elif type_name in struct_specs:
            lines.extend(
                _emit_struct_parse_function(
                    type_name,
                    struct_specs=struct_specs,
                    struct_construction=struct_construction,
                )
            )
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
    display_names: dict[str, str] | None = None,
) -> list[str]:
    spec = struct_specs[type_name]
    fn_name = _to_json_fn_name(type_name)
    display = (display_names or {}).get(type_name, type_name)
    lines = [
        f"fn {fn_name}(value: {type_name}) -> String:",
        f'{INDENT}var result = String("{{\\"{_STRUCT_ENVELOPE_TYPE_KEY}\\":\\"{display}\\",\\"{_STRUCT_ENVELOPE_VALUES_KEY}\\":[")',
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
    display_names: dict[str, str] | None = None,
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
            lines.extend(
                _emit_struct_to_json_function(
                    type_name, struct_specs=struct_specs, display_names=display_names
                )
            )
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
    helper_name = f"_dispatch_{_module_dispatch_name(module.import_path)}"
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
    from apps.runtime.mojo_inventory import (
        RuntimeFunctionSpec,
        RuntimeLibraryModule,
        RuntimeParamSpec,
        RuntimeStructFieldSpec,
        RuntimeStructSpec,
    )

    # Parse every struct definition with correct (body-indent) field detection,
    # keeping the field layout PER (module, struct). Structs with the same name
    # defined in different modules (e.g. the vector_kernels RankResult/RankRequest
    # variants, which genuinely differ in fields) are distinct nominal types and
    # are namespaced per defining module via `qualify()` below — so the generated
    # ser/de never conflate them, and no function is filtered out.
    module_struct_fields: dict[tuple[str, str], list[tuple[str, str]]] = {}
    module_defines: dict[str, set[str]] = {}
    struct_def_count: dict[str, int] = {}
    module_struct_construction: dict[tuple[str, str], str] = {}
    for module in modules:
        defined = module_defines.setdefault(module.import_path, set())
        for struct_name, (fields, construction) in _parse_struct_defs(module.path).items():
            if struct_name not in defined:
                module_struct_fields[(module.import_path, struct_name)] = fields
                module_struct_construction[(module.import_path, struct_name)] = construction
                defined.add(struct_name)
                struct_def_count[struct_name] = struct_def_count.get(struct_name, 0) + 1
    ambiguous = {name for name, count in struct_def_count.items() if count > 1}

    struct_specs: dict[str, RuntimeStructSpec] = {}
    struct_origin: dict[str, str] = {}            # non-aliased struct name -> module
    alias_imports: dict[str, tuple[str, str]] = {}  # alias -> (module, base name)
    # Emitted-name -> "positional" | "assign" | "none". Aliases inherit the
    # strategy of the base struct in their defining module.
    struct_construction: dict[str, str] = {}

    def qualify(type_name: str, module: str) -> str:
        """Map an ambiguous struct (defined in `module`) to a per-module alias
        (a real type imported `as` the alias); recurse into List[...]. Registers
        struct_specs / origins lazily as types are first encountered."""
        if _is_list_type(type_name):
            return f"List[{qualify(_list_inner_type(type_name), module)}]"
        if type_name in ambiguous and type_name in module_defines.get(module, set()):
            alias = f"{type_name}__{_sanitize_identifier(module)}"
            if alias not in struct_specs:
                alias_imports[alias] = (module, type_name)
                struct_specs[alias] = RuntimeStructSpec(
                    name=alias,
                    fields=tuple(
                        RuntimeStructFieldSpec(name=fname, typ=qualify(ftyp, module))
                        for fname, ftyp in module_struct_fields.get((module, type_name), [])
                    ),
                )
                struct_construction[alias] = module_struct_construction.get(
                    (module, type_name), "positional"
                )
            return alias
        if type_name in struct_specs or type_name in alias_imports:
            return type_name
        for (mod, nm), fields in module_struct_fields.items():
            if nm == type_name:
                struct_specs[type_name] = RuntimeStructSpec(
                    name=type_name,
                    fields=tuple(
                        RuntimeStructFieldSpec(name=fname, typ=qualify(ftyp, mod))
                        for fname, ftyp in fields
                    ),
                )
                struct_origin[type_name] = mod
                struct_construction[type_name] = module_struct_construction.get(
                    (mod, nm), "positional"
                )
                break
        return type_name

    # No function is filtered out. Build per-module qualified function specs for
    # type handling; the real imported function alias is unchanged.
    filtered_modules = modules
    qualified_list: list[RuntimeLibraryModule] = []
    for module in filtered_modules:
        qfns = tuple(
            RuntimeFunctionSpec(
                name=fn.name,
                params=tuple(
                    RuntimeParamSpec(
                        name=p.name,
                        typ=qualify(p.typ, module.import_path),
                        has_default=p.has_default,
                        is_mut=p.is_mut,
                    )
                    for p in fn.params
                ),
                return_type=qualify(fn.return_type, module.import_path),
            )
            for fn in module.functions
        )
        qualified_list.append(
            RuntimeLibraryModule(
                import_path=module.import_path,
                lib_id=module.lib_id,
                path=module.path,
                functions=qfns,
            )
        )
    qualified_modules = tuple(qualified_list)
    struct_display = {alias: base for alias, (_mod, base) in alias_imports.items()}

    def register_value_type(type_name: str, collected: set[str]) -> None:
        _register_type(type_name, collected)
        if _is_list_type(type_name):
            register_value_type(_list_inner_type(type_name), collected)
            return
        if type_name in struct_specs:
            for field in struct_specs[type_name].fields:
                register_value_type(field.typ, collected)

    for module in qualified_modules:
        for function in module.functions:
            for param in function.params:
                register_value_type(param.typ, param_types)
                if param.is_mut:
                    register_value_type(param.typ, result_types)
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
        "from json.parser import json_get_array, json_get_string, json_array_len, json_array_get, json_array_tokens, json_parse_float64_list",
        "",
    ]
    lines.extend(_emit_imports(filtered_modules))
    all_types = param_types | result_types
    struct_imports_by_module: dict[str, list[str]] = {}
    # Non-ambiguous structs: imported by bare name from their defining module.
    for struct_name in sorted(t for t in all_types if t in struct_origin):
        struct_imports_by_module.setdefault(struct_origin[struct_name], []).append(struct_name)
    # Ambiguous structs: imported `as <alias>` from each defining module, so the
    # same name from different modules stays a distinct nominal type.
    for alias in sorted(a for a in alias_imports if a in all_types):
        module_ip, base = alias_imports[alias]
        struct_imports_by_module.setdefault(module_ip, []).append(f"{base} as {alias}")
    for module_import_path in sorted(struct_imports_by_module):
        lines.append(f"from {module_import_path} import (")
        for entry in sorted(struct_imports_by_module[module_import_path]):
            lines.append(f"{INDENT}{entry},")
        lines.append(")")
        lines.append("")
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
    lines.extend(
        _emit_parse_functions(
            param_types,
            struct_specs=struct_specs,
            struct_construction=struct_construction,
        )
    )
    lines.extend(
        _emit_to_json_functions(
            result_types, struct_specs=struct_specs, display_names=struct_display
        )
    )
    for module in qualified_modules:
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
    for module in qualified_modules:
        helper_name = f"_dispatch_{_module_dispatch_name(module.import_path)}"
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
    from apps.runtime.mojo_inventory import (
        DEFAULT_ENGINE_DIR,
        discover_runtime_library_modules,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=DEFAULT_ENGINE_DIR,
        help="Engine source root to inventory. Dedicated builds should pass an isolated stage.",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help="Optional isolated inventory-cache path.",
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        default=(),
        help="Optional runtime-library import paths to include in the generated dispatch.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help=(
            "Write a JSON census of per-struct construction strategies "
            "(positional / assign / none). Structs resolving to 'none' cannot be "
            "decoded from a payload; this makes that visible instead of silent."
        ),
    )
    args = parser.parse_args()
    modules = discover_runtime_library_modules(
        engine_root=args.engine_root,
        executable_only=True,
        cache_path=args.cache_path,
    )
    if args.modules:
        available_modules = {module.import_path: module for module in modules}
        missing_modules = [
            module_name
            for module_name in args.modules
            if module_name not in available_modules
        ]
        if missing_modules:
            raise SystemExit(
                "Unknown runtime-library modules requested for dispatch generation: "
                + ", ".join(sorted(missing_modules))
            )
        modules = tuple(available_modules[module_name] for module_name in args.modules)
    rendered = render_dispatch_source(modules)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)

    if args.report is not None:
        entries: list[dict[str, object]] = []
        counts: dict[str, int] = {"positional": 0, "assign": 0, "none": 0}
        seen: set[tuple[str, str]] = set()
        for module in modules:
            for struct_name, (fields, construction) in _parse_struct_defs(module.path).items():
                key = (module.import_path, struct_name)
                if key in seen:
                    continue
                seen.add(key)
                counts[construction] = counts.get(construction, 0) + 1
                entries.append(
                    {
                        "module": module.import_path,
                        "struct": struct_name,
                        "fields": len(fields),
                        "construction": construction,
                    }
                )
        entries.sort(key=lambda item: (str(item["module"]), str(item["struct"])))
        report = {
            "schema_version": 1,
            "counts": counts,
            "undecodable": [e for e in entries if e["construction"] == "none"],
            "structs": entries,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{args.report} ({counts})")


if __name__ == "__main__":
    main()
