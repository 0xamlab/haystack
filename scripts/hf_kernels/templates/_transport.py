"""Argument validation and result decoding against this kernel's published contract.

A dependency-free port of the Algenta SDK's transport layer (`runtime_library_transport` and
`runtime_count_guard`): the same acceptance rules and the same error codes, worded for people who
have never seen the engine. The native boundary enforces the count relations again; this layer
exists so mistakes are reported before the call, in plain language, and so results come back as
plain Python values.
"""

from __future__ import annotations

import math
from array import array
from typing import Any

from ._contract import CONTRACT
from ._native import KernelError

STRUCT_TYPE_KEY = "__algenta_struct"
STRUCT_VALUES_KEY = "v"
PACKED_FLOAT64_PREFIX = "@u8:"
_BASE64 = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
_INT_MIN, _INT_MAX = -(1 << 63), (1 << 63) - 1
#: Plain values `to_plain` passes through untouched; a flat list of these needs no walk.
_PLAIN_TYPES = frozenset({int, float, str, bool, type(None)})
_NUMBER_TYPES = frozenset({int, float})
_UINT_BITS = {"UInt8": 8, "UInt16": 16, "UInt32": 32, "UInt64": 64}
_WORDS = {
    "Int": "an int",
    "Bool": "a bool",
    "String": "a string",
    "Float64": "a number",
    "Float32": "a number",
    "None": "None",
}


class _KernelDefault:
    """Marker for a parameter whose default value lives in the kernel itself."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<kernel default>"


KERNEL_DEFAULT = _KernelDefault()


def _invalid(message: str, **details: Any) -> KernelError:
    return KernelError("invalid_arguments", message, details)


def _list_inner(type_name: str) -> str | None:
    return type_name[5:-1] if type_name.startswith("List[") and type_name.endswith("]") else None


_PLURAL = {
    "Int": "ints",
    "Bool": "bools",
    "String": "strings",
    "Float64": "numbers",
    "Float32": "numbers",
}


def _words(type_name: str) -> str:
    inner = _list_inner(type_name)
    if inner is not None:
        if inner in _PLURAL:
            return f"a list of {_PLURAL[inner]}"
        if inner in _UINT_BITS:
            return f"a list of ints from 0 to {(1 << _UINT_BITS[inner]) - 1}"
        if _list_inner(inner) is not None:
            return "a list of lists of " + _words(inner).split(" of ", 1)[1]
        return f"a list of {inner} dicts"
    if type_name in _UINT_BITS:
        return f"an int from 0 to {(1 << _UINT_BITS[type_name]) - 1}"
    return _WORDS.get(type_name, f"a {type_name} dict")


def to_plain(value: Any) -> Any:
    """Accept tensors, arrays and buffers alongside plain Python values (no framework import)."""
    if hasattr(value, "tolist") and not isinstance(value, (list, dict, str, bytes)):
        return value.tolist()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return list(memoryview(value).tolist())
    if isinstance(value, list) and set(map(type, value)) <= _PLAIN_TYPES:
        return value  # a flat list of plain values: nothing to convert (one C-level pass)
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    return value


def normalize_value(value: Any, type_name: str, structs: dict, context: str) -> Any:
    if type_name == "None":
        if value is not None:
            raise _invalid(f"{context} must be None", expected=type_name)
        return None
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise _invalid(f"{context} must be a bool", expected=type_name)
        return value
    if type_name == "String":
        if not isinstance(value, str):
            raise _invalid(f"{context} must be a string", expected=type_name)
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _invalid(
                f"{context} contains unpaired surrogate characters", expected=type_name
            ) from exc
        return value
    if type_name == "Int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise _invalid(f"{context} must be an int", expected=type_name)
        if not _INT_MIN <= value <= _INT_MAX:
            raise _invalid(f"{context} is outside the 64-bit int range", expected=type_name)
        return value
    if type_name in _UINT_BITS:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value >= 1 << _UINT_BITS[type_name]
        ):
            raise _invalid(f"{context} must be {_words(type_name)}", expected=type_name)
        return value
    if type_name in {"Float32", "Float64"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _invalid(f"{context} must be a number", expected=type_name)
        try:
            number = float(value)
        except OverflowError as exc:
            raise _invalid(
                f"{context} is too large for a 64-bit float", expected=type_name
            ) from exc
        if not math.isfinite(number):
            raise _invalid(f"{context} must be a finite number", expected=type_name)
        return number
    inner = _list_inner(type_name)
    if inner is not None:
        if (
            type_name == "List[Float64]"
            and isinstance(value, str)
            and value.startswith(PACKED_FLOAT64_PREFIX)
        ):
            return value
        if not isinstance(value, list):
            raise _invalid(f"{context} must be {_words(type_name)}", expected=type_name)
        fast = _normalize_flat_list(value, inner)
        if fast is not None:
            return fast
        return [
            normalize_value(item, inner, structs, f"{context}[{i}]") for i, item in enumerate(value)
        ]
    struct = structs.get(type_name)
    if struct is None:
        raise KernelError(
            "unsupported_signature",
            f"Unsupported runtime type {type_name!r}",
            {"type": type_name, "context": context},
        )
    if not isinstance(value, dict):
        raise _invalid(
            f"{context} must be a dict with keys {', '.join(f['name'] for f in struct['fields'])}",
            expected=type_name,
        )
    fields = struct["fields"]
    raw_values = value.get(STRUCT_VALUES_KEY)
    if value.get(STRUCT_TYPE_KEY) == type_name and isinstance(raw_values, list):
        provided = dict(zip((f["name"] for f in fields), raw_values))  # noqa: B905
    else:
        provided = value
    expected = {f["name"] for f in fields}
    missing = sorted(expected - set(provided))
    extra = sorted(set(provided) - expected - {STRUCT_TYPE_KEY, STRUCT_VALUES_KEY})
    if missing or extra:
        raise _invalid(
            f"{context} must have exactly the keys {', '.join(f['name'] for f in fields)}",
            missing=missing,
            extra=extra,
        )
    return {
        STRUCT_TYPE_KEY: type_name,
        STRUCT_VALUES_KEY: [
            normalize_value(provided[f["name"]], f["type"], structs, f"{context}.{f['name']}")
            for f in fields
        ],
    }


def _normalize_flat_list(value: list, inner: str) -> list | None:
    """A flat list of primitives checked in C-level passes, or None when any element needs the
    per-element path (which then produces the exact refusal). The result equals what the
    per-element path returns for the same accepted input: floats as floats (ints widened),
    ints, strings and bools as they came."""
    if not value:
        return []
    kinds = set(map(type, value))
    if inner in ("Float64", "Float32"):
        if not kinds <= _NUMBER_TYPES:
            return None
        try:
            doubles = array("d", value)
        except (OverflowError, TypeError, ValueError):
            return None
        if not all(map(math.isfinite, doubles)):
            return None
        return doubles.tolist()
    if inner == "Int":
        if kinds != {int}:
            return None
        try:
            array("q", value)  # the 64-bit range, checked in C
        except (OverflowError, TypeError, ValueError):
            return None
        return value
    if inner in _UINT_BITS:
        if kinds != {int} or min(value) < 0 or max(value) >= 1 << _UINT_BITS[inner]:
            return None
        return value
    if inner == "String":
        if kinds != {str}:
            return None
        try:
            "".join(value).encode("utf-8")
        except UnicodeEncodeError:
            return None
        return value
    if inner == "Bool":
        return value if kinds == {bool} else None
    return None


def normalize_arguments(args: Any, function: dict, structs: dict) -> list:
    params = function["params"]
    if args is None:
        provided: list = []
    elif isinstance(args, list):
        provided = args
    elif isinstance(args, dict):
        provided = []
        skipped: str | None = None
        names = {p["name"] for p in params}
        extra = sorted(set(args) - names)
        if extra:
            raise _invalid(f"unknown argument names: {', '.join(extra)}", extra=extra)
        for p in params:
            if p["name"] in args:
                if skipped is not None:
                    raise _invalid(
                        f"{skipped} must be given when {p['name']} is; "
                        "this kernel fills defaults only from the right",
                        parameter=skipped,
                    )
                provided.append(args[p["name"]])
            elif p["has_default"]:
                skipped = p["name"]
            else:
                raise _invalid(f"missing required argument {p['name']}", parameter=p["name"])
    else:
        provided = [args]
    required = sum(not p["has_default"] for p in params)
    if not required <= len(provided) <= len(params):
        raise _invalid(
            f"{function['name']} takes {required} to {len(params)} arguments, "
            f"{len(provided)} given",
            required=required,
            accepted=len(params),
            received=len(provided),
        )
    for i, v in enumerate(provided):
        if isinstance(v, _KernelDefault):
            raise _invalid(
                f"{params[i]['name']} must be given when a later argument is; "
                "this kernel fills defaults only from the right",
                parameter=params[i]["name"],
            )
    return [
        normalize_value(v, p["type"], structs, p["name"])
        for p, v in zip(params, provided)  # noqa: B905
    ]


# --- count relations (port of runtime_count_guard) --------------------------------------------


def _packed_count(value: str) -> int:
    sextets = sum(1 for c in value[len(PACKED_FLOAT64_PREFIX) :] if c in _BASE64)
    return (sextets * 6) // 8


def measured_element_count(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value.startswith(PACKED_FLOAT64_PREFIX):
        return _packed_count(value)
    return None


def count_fits(factors: list, available: int, *, role: str = "count") -> bool:
    if available < 0:
        return False
    if role == "index" and any(f < 0 for f in factors):
        return False
    if any(f == 0 for f in factors):
        return True
    remaining = available
    for f in factors:
        if f < 0:
            return True
        if f > remaining:
            return False
        remaining //= f
    return True


def enforce_count_relations(module: str, function: dict, normalized: list) -> None:
    relations = function.get("count_relations") or []
    if not relations:
        return
    supplied = dict(zip((p["name"] for p in function["params"]), normalized))  # noqa: B905
    for rel in relations:
        factors: list = []
        for name in rel["factors"]:
            v = supplied.get(name)
            if isinstance(v, bool) or not isinstance(v, int):
                factors = []
                break
            factors.append(v)
        if not factors:
            continue
        role = "index" if (rel["role"] == "index" or rel["plus"] > 0) else "count"
        for list_name in rel["bounds"]:
            if list_name not in supplied:
                continue
            listed = supplied[list_name]
            items = (
                [(measured_element_count(listed), None)]
                if rel["scope"] == "length"
                else (
                    [(measured_element_count(e), i) for i, e in enumerate(listed)]
                    if isinstance(listed, list)
                    else [(None, None)]
                )
            )
            for length, index in items:
                target = f"{list_name}[{index}]" if index is not None else list_name
                if length is None:
                    raise KernelError(
                        "invalid_arguments",
                        f"{module}.{function['name']}: the length of {target} bounds a "
                        "declared element count and cannot be determined before the call; "
                        f"pass it as a list or an '{PACKED_FLOAT64_PREFIX}<base64>' buffer.",
                        {
                            "module": module,
                            "function": function["name"],
                            "list_parameter": list_name,
                        },
                    )
                if count_fits(factors, length - rel["plus"], role=role):
                    continue
                counted = ", ".join(
                    f"{n}={v}"
                    for n, v in zip(rel["factors"], factors)  # noqa: B905
                )
                raise KernelError(
                    "count_exceeds_list_length",
                    f"{module}.{function['name']}: {counted} counts more elements "
                    f"than {target} holds ({length}).",
                    {
                        "module": module,
                        "function": function["name"],
                        "list_parameter": list_name,
                        "actual_length": length,
                    },
                )


# --- results -------------------------------------------------------------------------------------


def decode_value(value: Any, type_name: str, structs: dict, context: str) -> Any:
    inner = _list_inner(type_name)
    if inner is not None:
        if not isinstance(value, list):
            raise KernelError(
                "runtime_execution_failed", f"The kernel returned an invalid {context}"
            )
        if inner not in structs:
            fast = _normalize_flat_list(value, inner)
            if fast is not None:
                return fast  # the kernel's own list of primitives, checked in one pass
        return [
            decode_value(item, inner, structs, f"{context}[{i}]") for i, item in enumerate(value)
        ]
    struct = structs.get(type_name)
    if struct is None:
        try:
            return normalize_value(value, type_name, structs, context)
        except KernelError as exc:
            raise KernelError(
                "runtime_execution_failed", f"The kernel returned an invalid {context}"
            ) from exc
    if not isinstance(value, dict) or value.get(STRUCT_TYPE_KEY) != type_name:
        raise KernelError(
            "runtime_execution_failed", f"The kernel returned an invalid {type_name} for {context}"
        )
    raw_values = value.get(STRUCT_VALUES_KEY)
    fields = struct["fields"]
    if not isinstance(raw_values, list) or len(raw_values) != len(fields):
        raise KernelError(
            "runtime_execution_failed", f"The kernel returned invalid fields for {type_name}"
        )
    return {
        f["name"]: decode_value(v, f["type"], structs, f"{context}.{f['name']}")
        for f, v in zip(fields, raw_values)  # noqa: B905
    }


def status_name(module: str, code: int) -> str | None:
    """The engine's name for a status code reported by a function of `module`, if the module's
    engine publishes a status vocabulary (`None` otherwise)."""
    decoder = CONTRACT["modules"].get(module, {}).get("status_decoder")
    if not decoder:
        return None
    return CONTRACT.get("status_names", {}).get(decoder, {}).get(code)


def _raise_on_status(module: str, function_name: str, result: Any) -> None:
    """Engine kernels report shape and finiteness problems as an integer `status` in their result
    struct. When the engine's vocabulary names the code and it is not an `ok`, raise it."""
    if not isinstance(result, dict):
        return
    code = result.get("status")
    if isinstance(code, bool) or not isinstance(code, int):
        return
    name = status_name(module, code)
    if name is None or name == "ok" or name.endswith("_ok"):
        return
    raise KernelError(
        name,
        f"{module}.{function_name} reported {name} (status {code})",
        {"module": module, "function": function_name, "status": code, "result": result},
    )


def call(module: str, function_name: str, args: Any, in_place: dict | None = None) -> Any:
    """Validate, execute and decode one runtime-library call.

    Returns the decoded result. When the function updates list or dict arguments and `in_place`
    maps their names to the caller's objects, the updates are written back into those objects;
    otherwise a call that produced updates returns `{"result": ..., "mutated_args": {...}}`."""
    from ._native import execute

    mod = CONTRACT["modules"].get(module)
    if mod is None:
        raise KernelError(
            "module_not_registered", f"{module} is not part of this kernel", {"module": module}
        )
    function = mod["functions"].get(function_name)
    if function is None:
        raise KernelError(
            "function_not_registered",
            f"{module}.{function_name} is not part of this kernel",
            {"module": module, "function": function_name},
        )
    structs = mod["structs"]
    for name, target in (in_place or {}).items():
        kind = (
            "dict"
            if any(p["name"] == name and p["type"] in structs for p in function["params"])
            else "list"
        )
        if not isinstance(target, dict if kind == "dict" else list):
            raise _invalid(f"{name} is updated in place; pass a {kind}", parameter=name)
    normalized = normalize_arguments(to_plain(args), function, structs)
    enforce_count_relations(module, function, normalized)
    response = execute(
        {"type": "library_execute", "module": module, "function": function_name, "args": normalized}
    )
    if not isinstance(response, dict):
        raise KernelError("runtime_execution_failed", "The kernel returned a malformed response")
    error = response.get("error")
    if error not in (None, "", False):
        raise KernelError(
            str(response.get("error_code") or "runtime_execution_failed"),
            str(response.get("error_message") or error),
            {"module": module, "function": function_name},
        )
    if "result" not in response:
        raise KernelError("runtime_execution_failed", "The kernel response has no result")
    result = decode_value(response["result"], function["return_type"], structs, "result")
    _raise_on_status(module, function_name, result)
    mutations = response.get("mutated_args")
    decoded: dict = {}
    if isinstance(mutations, dict):
        for raw_index, raw_value in mutations.items():
            if not (isinstance(raw_index, str) and raw_index.isdigit()) or int(raw_index) >= len(
                function["params"]
            ):
                raise KernelError(
                    "runtime_execution_failed", "The kernel returned invalid mutation data"
                )
            param = function["params"][int(raw_index)]
            decoded[param["name"]] = decode_value(
                raw_value, param["type"], structs, f"mutated_args.{param['name']}"
            )
    if in_place is not None:
        for name, value in decoded.items():
            target = in_place.get(name)
            if isinstance(target, list):
                target[:] = value
            elif isinstance(target, dict):
                target.clear()
                target.update(value)
        return result
    if not decoded:
        return result
    return {"result": result, "mutated_args": decoded}
