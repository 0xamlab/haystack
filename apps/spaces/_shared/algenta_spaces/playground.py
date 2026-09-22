"""Playground — the contract-driven "run any function" layer behind the flagship's Playground tab.

A loaded Hub kernel (`kernels.get_kernel("thyn-ai/algenta-<family>", version=1, backend="cpu",
trust_remote_code=TRUST)`) exposes `CONTRACT`: every module, function, parameter (`name`, `type`,
`has_default`), struct, count relation and engine status vocabulary — plus an `excluded_functions`
list. This module turns that contract into the three things the tab needs and nothing else:

* `form_spec(kernel, module, function)` — a `Form` of `FieldSpec`s the tab renders as typed
  controls: `Int`/`UInt*` -> `int` (a number with precision 0), `Float*` -> `float`, `Bool` ->
  `bool`, `String` -> `str`, lists and structs -> `json` (a code box). Excluded functions are
  refused here, before any control exists.
* `parse_inputs(form, raw)` — validation with the SAME acceptance rules as the kernel's own
  `_transport.normalize_arguments` (bools are not ints, 64-bit int ranges, `UInt*` ranges, finite
  floats, UTF-8 strings, list element types, struct keys, defaults filled only from the right,
  count relations such as `len(x) == n_rows * n_cols`) plus a list-size budget. Every failure is a
  `ValidationError(field, reason)` in plain language; bad input never reaches the C ABI.
* `snippet(family, module, function, args, mode=...)` — the exact reproducible call with the
  visitor's actual arguments in three dialects: `kernels` (pip + `get_kernel` + the module wrapper
  call), `sdk` (`algenta.libraries()`), `mcp` (the JSON-RPC `tools/call` frame for
  `execute_runtime_library`). Every rendered Python snippet is valid Python; the JSON is valid JSON.

`hero_functions()` is the plan's fifteen hero entries as data (family, module, function, incumbent,
race or run, default arguments). Three lines of the plan name functions that live elsewhere in the
published contracts, and the table records what actually ships: the ML metric is
`calibration.calibration_curve` (the ROC/NDCG helpers are per-term scalars), the n-gram tokenizer
`text.tokenizer` is published in `algenta-llm`, the dHash `perceptual_hash` in `algenta-crypto`,
and the sampling entry is `llmk.generate.greedy_argmax_flat`, the list-based sampler. The table is
structurally checked at import and, when kernels are loaded, validated against their contracts.

Every entry point takes the kernel module `get_kernel` returns, a `hubkernel.LoadedKernel` (the
module sits in its `.kernel`), or a contract mapping (`native_module` unwraps them).
`run(kernel, module, function, raw)` chains the three steps and times the native call; the timing
is one wall-clock number around `kernel.execute`, so it includes the JSON marshalling across the
C ABI — cards say so. ABI §9 applies: one native execution per container at a time, so the tab
calls `run` from its single native lane.

Stdlib only. `kernels`, `torch` and `gradio` are never imported here.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

ORG = "thyn-ai"
KERNEL_VERSION = 1
BACKEND = "cpu"
MCP_TOOL = "execute_runtime_library"
PIP_KERNELS = "pip install kernels torch"
PIP_SDK = "pip install algenta"

#: Every repo in the umbrella's dependency tree — the loader's allowlist must name them all
#: (HF-TRUST-002). Mirrors `docs/hf-kernels/release/capabilities.json`
#: `publication_state.capped_v1_shas`; `tests/spaces/test_playground.py` asserts the two agree.
TRUST: tuple[str, ...] = (
    "thyn-ai/algenta",
    "thyn-ai/algenta-bits-time",
    "thyn-ai/algenta-crypto",
    "thyn-ai/algenta-finance",
    "thyn-ai/algenta-general-a",
    "thyn-ai/algenta-general-b",
    "thyn-ai/algenta-general-c",
    "thyn-ai/algenta-general-d",
    "thyn-ai/algenta-general-e",
    "thyn-ai/algenta-geometry",
    "thyn-ai/algenta-graph",
    "thyn-ai/algenta-llm",
    "thyn-ai/algenta-ml",
    "thyn-ai/algenta-networking",
    "thyn-ai/algenta-serialization",
    "thyn-ai/algenta-signal",
    "thyn-ai/algenta-stats",
    "thyn-ai/algenta-tensors",
    "thyn-ai/algenta-text",
    "thyn-ai/algenta-vision",
)
UMBRELLA = f"{ORG}/algenta"
#: Short family names (`stats`, `text`, ...): every capped repo except the umbrella.
FAMILIES: tuple[str, ...] = tuple(
    repo.removeprefix(f"{ORG}/algenta-") for repo in TRUST if repo != UMBRELLA
)

#: Functions the published kernels refuse before dispatch (`capabilities.json`
#: `excluded_functions`); `module.*` covers a whole module. A loaded kernel's own
#: `excluded_functions` list is honoured as well.
EXCLUDED_FUNCTIONS: tuple[str, ...] = (
    "column_rank.run_column_rank",
    "combinatorial.tsp_greedy",
    "compression.huffman.generate_codes",
    "constraint.magic_square_check",
    "contest_strategy.option_board",
    "datetime.now_epoch",
    "dependency.dependency_depth",
    "dimensionality.power_iteration",
    "env.*",
    "gbdt.gbdt_predict",
    "matrix_decomp.lu_decompose",
    "matrix_decomp.trace",
    "svm_kernel.is_positive_semidefinite",
    "svm_kernel.kernel_center",
    "topology.filtration_values",
    "topology.persistence_diagram_0",
    "topology.vietoris_rips_edges",
    "trie.*",
)

KIND_INT = "int"
KIND_FLOAT = "float"
KIND_BOOL = "bool"
KIND_STR = "str"
KIND_JSON = "json"
KINDS: tuple[str, ...] = (KIND_INT, KIND_FLOAT, KIND_BOOL, KIND_STR, KIND_JSON)

MODE_KERNELS = "kernels"
MODE_SDK = "sdk"
MODE_MCP = "mcp"
MODES: tuple[str, ...] = (MODE_KERNELS, MODE_SDK, MODE_MCP)

HERO_RACE = "race"
HERO_RUN = "run"
HERO_MODES: tuple[str, ...] = (HERO_RACE, HERO_RUN)
HERO_COUNT = 15

#: The plan's budget for list arguments in a single playground call.
MAX_LIST_ELEMENTS = 200_000
#: A rendered call longer than this is broken one argument per line.
CALL_WIDTH = 88

_INT_MIN, _INT_MAX = -(1 << 63), (1 << 63) - 1
_UINT_BITS: dict[str, int] = {"UInt8": 8, "UInt16": 16, "UInt32": 32, "UInt64": 64}
_FLOAT_TYPES = frozenset({"Float32", "Float64"})
_PLURAL = {
    "Int": "ints",
    "Bool": "bools",
    "String": "strings",
    "Float64": "numbers",
    "Float32": "numbers",
}
_WORDS = {
    "Int": "an int",
    "Bool": "a bool",
    "String": "a string",
    "Float64": "a number",
    "Float32": "a number",
    "None": "None",
}
_TRUE_WORDS = frozenset({"true", "1", "yes", "on"})
_FALSE_WORDS = frozenset({"false", "0", "no", "off"})
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlaygroundError(ValueError):
    """Base class: every refusal this module makes before a call."""


class UnknownFunctionError(PlaygroundError, LookupError):
    """The module or function is not part of the loaded kernel's contract."""

    def __init__(self, module: str, function: str | None = None) -> None:
        self.module = module
        self.function = function
        what = module if function is None else f"{module}.{function}"
        super().__init__(f"{what} is not part of this kernel")


class ExcludedFunctionError(PlaygroundError):
    """The function is published but refused before dispatch (`excluded_functions`)."""

    def __init__(self, module: str, function: str) -> None:
        self.module = module
        self.function = function
        super().__init__(f"{module}.{function} is not callable in-process on the Hub")


class ValidationError(PlaygroundError):
    """One field's value cannot be sent: `field` names it, `reason` says why in plain words."""

    def __init__(self, field_name: str, reason: str) -> None:
        self.field = field_name
        self.reason = reason
        super().__init__(f"{field_name}: {reason}")


class HeroMismatchError(PlaygroundError):
    """A hero entry disagrees with the loaded contract it names."""


# ---------------------------------------------------------------------------
# Contract access
# ---------------------------------------------------------------------------


def native_module(kernel: Any) -> Any:
    """The object that carries `CONTRACT` and `execute`: the kernel module itself, or the module
    inside a `hubkernel.LoadedKernel`-shaped record (`.kernel`). Mappings pass through."""
    if isinstance(kernel, Mapping) or hasattr(kernel, "CONTRACT"):
        return kernel
    inner = getattr(kernel, "kernel", None)
    if inner is not None and hasattr(inner, "CONTRACT"):
        return inner
    return kernel


def contract_of(kernel: Any) -> Mapping[str, Any]:
    """The contract mapping of a loaded kernel, or of a contract dict passed directly."""
    kernel = native_module(kernel)
    contract = kernel if isinstance(kernel, Mapping) else getattr(kernel, "CONTRACT", None)
    if not isinstance(contract, Mapping) or not isinstance(contract.get("modules"), Mapping):
        raise TypeError("expected a loaded kernel with CONTRACT or a contract mapping with modules")
    return contract


def excluded_of(kernel: Any) -> tuple[str, ...]:
    """The published exclusions plus whatever the kernel itself lists, sorted and deduplicated."""
    kernel = native_module(kernel)
    if isinstance(kernel, Mapping):
        own = kernel.get("excluded_functions", ())
    else:
        own = getattr(kernel, "excluded_functions", ())
    if isinstance(own, str) or not isinstance(own, Sequence):
        raise TypeError("excluded_functions must be a sequence of 'module.function' strings")
    return tuple(sorted(set(EXCLUDED_FUNCTIONS) | {str(item) for item in own}))


def is_excluded(module: str, function: str, excluded: Sequence[str] = EXCLUDED_FUNCTIONS) -> bool:
    """True when `module.function` (or the whole module via `module.*`) is refused."""
    return f"{module}.{function}" in excluded or f"{module}.*" in excluded


def function_entry(
    kernel: Any, module: str, function: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """The `(module entry, function entry)` pair, refusing unknown and excluded functions."""
    contract = contract_of(kernel)
    mod = contract["modules"].get(module)
    if not isinstance(mod, Mapping):
        raise UnknownFunctionError(module)
    fn = mod.get("functions", {}).get(function)
    if not isinstance(fn, Mapping):
        raise UnknownFunctionError(module, function)
    if is_excluded(module, function, excluded_of(kernel)):
        raise ExcludedFunctionError(module, function)
    return mod, fn


def list_functions(kernel: Any) -> list[tuple[str, str]]:
    """Every callable `(module, function)` of the kernel, sorted, exclusions dropped."""
    contract = contract_of(kernel)
    excluded = excluded_of(kernel)
    out = [
        (module, function)
        for module, mod in contract["modules"].items()
        for function in mod.get("functions", {})
        if not is_excluded(module, function, excluded)
    ]
    return sorted(out)


def status_name(kernel: Any, module: str, code: int) -> str | None:
    """The engine's name for an integer `status` reported by a function of `module`.

    Engine modules publish a status vocabulary through `status_decoder`; `None` when the module
    has none or the code is not in it. `ok` codes differ per engine (`norm_ok` is 380), so a card
    must ask by name, never compare with zero.
    """
    contract = contract_of(kernel)
    mod = contract["modules"].get(module)
    if not isinstance(mod, Mapping):
        raise UnknownFunctionError(module)
    decoder = mod.get("status_decoder")
    if not decoder:
        return None
    names = contract.get("status_names", {}).get(decoder, {})
    return names.get(code, names.get(str(code)))


def is_ok_status(name: str | None) -> bool:
    """True for a status the kernel wrapper would not raise on: `ok`, `*_ok`, or no vocabulary."""
    return name is None or name == "ok" or name.endswith("_ok")


# ---------------------------------------------------------------------------
# Form specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """One argument control: `kind` picks the component, `type_name` is the runtime type."""

    name: str
    kind: str
    type_name: str
    default: Any = None
    help: str = ""
    list_of: str | None = None
    required: bool = True
    is_mut: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if not _IDENT_RE.match(self.name):
            raise ValueError(f"field name {self.name!r} is not an identifier")


@dataclass(frozen=True)
class Form(Sequence[FieldSpec]):
    """The fields of one function plus what validation needs: structs and count relations."""

    module: str
    function: str
    fields: tuple[FieldSpec, ...]
    return_type: str = ""
    doc: str = ""
    structs: Mapping[str, Any] = field(default_factory=dict)
    count_relations: tuple[Mapping[str, Any], ...] = ()

    def __len__(self) -> int:
        return len(self.fields)

    def __getitem__(self, index):  # type: ignore[override]
        return self.fields[index]

    def __iter__(self) -> Iterator[FieldSpec]:
        return iter(self.fields)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.fields)


def list_inner(type_name: str) -> str | None:
    """`Float64` for `List[Float64]`, `None` for anything that is not a list type."""
    if type_name.startswith("List[") and type_name.endswith("]"):
        return type_name[5:-1]
    return None


def field_kind(type_name: str) -> str:
    """Runtime type -> control kind (the mapping in the module docstring)."""
    if type_name == "Bool":
        return KIND_BOOL
    if type_name == "Int" or type_name in _UINT_BITS:
        return KIND_INT
    if type_name in _FLOAT_TYPES:
        return KIND_FLOAT
    if type_name == "String":
        return KIND_STR
    return KIND_JSON


def type_words(type_name: str, structs: Mapping[str, Any] | None = None) -> str:
    """`an int from 0 to 255`, `a list of numbers`, `a WeightedEdge object with keys src, dst`."""
    inner = list_inner(type_name)
    if inner is not None:
        if inner in _PLURAL:
            return f"a list of {_PLURAL[inner]}"
        if inner in _UINT_BITS:
            return f"a list of ints from 0 to {(1 << _UINT_BITS[inner]) - 1}"
        if list_inner(inner) is not None:
            return "a list of lists of " + type_words(inner, structs).split(" of ", 1)[1]
        return f"a list of {inner} objects"
    if type_name in _UINT_BITS:
        return f"an int from 0 to {(1 << _UINT_BITS[type_name]) - 1}"
    if type_name in _WORDS:
        return _WORDS[type_name]
    struct = (structs or {}).get(type_name)
    if isinstance(struct, Mapping):
        keys = ", ".join(f["name"] for f in struct.get("fields", ()))
        return f"a {type_name} object with keys {keys}"
    return f"a {type_name} object"


def _help_text(param: Mapping[str, Any], structs: Mapping[str, Any]) -> str:
    doc = str(param.get("doc") or "").strip()
    words = type_words(str(param["type"]), structs)
    return f"{doc} — {words}" if doc else words


def form_spec(kernel: Any, module: str, function: str) -> Form:
    """The typed form for `module.function`, built from the contract; exclusions are refused."""
    mod, fn = function_entry(kernel, module, function)
    structs = mod.get("structs") or {}
    fields: list[FieldSpec] = []
    for param in fn.get("params", ()):
        type_name = str(param["type"])
        has_default = bool(param.get("has_default"))
        fields.append(
            FieldSpec(
                name=str(param["name"]),
                kind=field_kind(type_name),
                type_name=type_name,
                default=None,
                help=_help_text(param, structs),
                list_of=list_inner(type_name),
                required=not has_default,
                is_mut=bool(param.get("is_mut", False)),
            )
        )
    return Form(
        module=module,
        function=function,
        fields=tuple(fields),
        return_type=str(fn.get("return_type") or ""),
        doc=str(fn.get("doc") or "").strip(),
        structs=structs,
        count_relations=tuple(fn.get("count_relations") or ()),
    )


# ---------------------------------------------------------------------------
# Input parsing and validation (port of `_transport.normalize_arguments` + count guard)
# ---------------------------------------------------------------------------


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def to_plain(value: Any) -> Any:
    """Tensors, arrays, tuples and buffers become plain Python values (no framework import)."""
    if hasattr(value, "tolist") and not isinstance(value, list | dict | str | bytes):
        return value.tolist()
    if isinstance(value, bytes | bytearray | memoryview):
        return list(memoryview(value).tolist())
    if isinstance(value, list | tuple):
        return [to_plain(v) for v in value]
    if isinstance(value, Mapping):
        return {k: to_plain(v) for k, v in value.items()}
    return value


def coerce(spec: FieldSpec, value: Any) -> Any:
    """Turn what a control hands back (often text) into the Python value the type expects.

    Numbers may arrive as text or as an integral float (a number box); bools as text; JSON kinds as
    JSON text or an already-parsed list/dict. Anything else is a `ValidationError`.
    """
    name = spec.name
    if spec.kind == KIND_INT:
        if isinstance(value, bool):
            raise ValidationError(name, "must be an int, not a bool")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value) or value != int(value):
                raise ValidationError(name, "must be a whole number")
            return int(value)
        if isinstance(value, str):
            text = value.strip().replace("_", "")
            try:
                return int(text, 10)
            except ValueError as exc:
                raise ValidationError(name, "must be an int") from exc
        raise ValidationError(name, "must be an int")
    if spec.kind == KIND_FLOAT:
        if isinstance(value, bool):
            raise ValidationError(name, "must be a number, not a bool")
        if isinstance(value, int | float):
            return value
        if isinstance(value, str):
            try:
                return float(value.strip().replace("_", ""))
            except ValueError as exc:
                raise ValidationError(name, "must be a number") from exc
        raise ValidationError(name, "must be a number")
    if spec.kind == KIND_BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            word = value.strip().lower()
            if word in _TRUE_WORDS:
                return True
            if word in _FALSE_WORDS:
                return False
        raise ValidationError(name, "must be true or false")
    if spec.kind == KIND_STR:
        if isinstance(value, str):
            return value
        raise ValidationError(name, "must be a string")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                name, f"is not valid JSON ({exc.msg} at position {exc.pos})"
            ) from exc
    if isinstance(value, list | tuple | Mapping) or hasattr(value, "tolist"):
        return to_plain(value)
    raise ValidationError(name, "must be JSON: a list or an object")


def _count_elements(value: Any) -> int:
    if isinstance(value, list):
        return sum(_count_elements(item) for item in value) if value else 0
    if isinstance(value, Mapping):
        return sum(_count_elements(item) for item in value.values())
    return 1


def normalize_value(
    value: Any,
    type_name: str,
    structs: Mapping[str, Any],
    field_name: str,
    context: str | None = None,
) -> Any:
    """Check one value against one runtime type with the kernel wrapper's exact acceptance rules.

    Returns the value as the kernel will see it (structs as dicts in field order). Raises
    `ValidationError(field_name, ...)`; `context` is the path inside the top-level field.
    """
    where = field_name if context is None else context
    if type_name == "None":
        if value is not None:
            raise ValidationError(field_name, f"{where} must be None")
        return None
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise ValidationError(field_name, f"{where} must be a bool")
        return value
    if type_name == "String":
        if not isinstance(value, str):
            raise ValidationError(field_name, f"{where} must be a string")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValidationError(
                field_name, f"{where} contains unpaired surrogate characters"
            ) from exc
        return value
    if type_name == "Int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(field_name, f"{where} must be an int")
        if not _INT_MIN <= value <= _INT_MAX:
            raise ValidationError(field_name, f"{where} is outside the 64-bit int range")
        return value
    if type_name in _UINT_BITS:
        bits = _UINT_BITS[type_name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= 1 << bits:
            raise ValidationError(field_name, f"{where} must be {type_words(type_name)}")
        return value
    if type_name in _FLOAT_TYPES:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError(field_name, f"{where} must be a number")
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValidationError(field_name, f"{where} is too large for a 64-bit float") from exc
        if not math.isfinite(number):
            raise ValidationError(field_name, f"{where} must be a finite number")
        return number
    inner = list_inner(type_name)
    if inner is not None:
        if not isinstance(value, list):
            raise ValidationError(field_name, f"{where} must be {type_words(type_name, structs)}")
        return [
            normalize_value(item, inner, structs, field_name, f"{where}[{i}]")
            for i, item in enumerate(value)
        ]
    struct = structs.get(type_name)
    if not isinstance(struct, Mapping):
        raise ValidationError(field_name, f"{where} has the unsupported runtime type {type_name}")
    fields = struct.get("fields", ())
    keys = ", ".join(f["name"] for f in fields)
    if not isinstance(value, Mapping):
        raise ValidationError(field_name, f"{where} must be an object with keys {keys}")
    expected = [f["name"] for f in fields]
    missing = sorted(set(expected) - set(value))
    extra = sorted(set(value) - set(expected))
    if missing or extra:
        raise ValidationError(field_name, f"{where} must have exactly the keys {keys}")
    return {
        f["name"]: normalize_value(
            value[f["name"]], f["type"], structs, field_name, f"{where}.{f['name']}"
        )
        for f in fields
    }


def count_fits(factors: Sequence[int], available: int, *, role: str = "count") -> bool:
    """Port of the count guard: do `factors` (a product of counts) fit in `available` elements?"""
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


def enforce_count_relations(form: Form, supplied: Mapping[str, Any]) -> None:
    """Refuse a call whose integer counts claim more elements than its lists hold."""
    for rel in form.count_relations:
        factors: list[int] = []
        for name in rel["factors"]:
            v = supplied.get(name)
            if isinstance(v, bool) or not isinstance(v, int):
                factors = []
                break
            factors.append(v)
        if not factors:
            continue
        role = "index" if (rel["role"] == "index" or rel["plus"] > 0) else "count"
        counted = ", ".join(f"{n}={v}" for n, v in zip(rel["factors"], factors, strict=True))
        for list_name in rel["bounds"]:
            if list_name not in supplied:
                continue
            listed = supplied[list_name]
            if rel["scope"] == "length":
                items: list[tuple[Any, int | None]] = [(listed, None)]
            elif isinstance(listed, list):
                items = [(e, i) for i, e in enumerate(listed)]
            else:
                items = [(None, None)]
            for element, index in items:
                target = f"{list_name}[{index}]" if index is not None else list_name
                if not isinstance(element, list):
                    raise ValidationError(
                        list_name, f"{target} must be a list so its length can be checked"
                    )
                if count_fits(factors, len(element) - rel["plus"], role=role):
                    continue
                raise ValidationError(
                    list_name,
                    f"{counted} counts more elements than {target} holds ({len(element)})",
                )


def parse_inputs(
    spec: Sequence[FieldSpec],
    raw: Mapping[str, Any],
    *,
    max_list_elements: int = MAX_LIST_ELEMENTS,
) -> list:
    """Validate `raw` (field name -> control value) and return the positional argument list.

    Missing optional fields at the end are left to the kernel's defaults; an optional field may
    not be skipped when a later one is given (the kernel fills defaults only from the right).
    Unknown names, missing required fields, type mismatches, out-of-range numbers, non-finite
    floats, bad JSON, wrong struct keys, oversized lists and broken count relations all raise
    `ValidationError`.
    """
    fields = list(spec)
    names = [f.name for f in fields]
    extra = sorted(set(raw) - set(names))
    if extra:
        raise ValidationError(extra[0], "is not an argument of this function")
    provided: list[tuple[FieldSpec, Any]] = []
    skipped: str | None = None
    for f in fields:
        # None, or blank text in a number/bool/JSON box, means "not given"; a blank string is a
        # legitimate value for a String parameter.
        given = f.name in raw and raw[f.name] is not None
        if given and f.kind != KIND_STR and _is_blank(raw[f.name]):
            given = False
        if given:
            if skipped is not None:
                raise ValidationError(
                    skipped, f"must be given when {f.name} is; defaults fill only from the right"
                )
            provided.append((f, coerce(f, raw[f.name])))
        elif f.required:
            raise ValidationError(f.name, "is required")
        else:
            skipped = f.name
    structs = spec.structs if isinstance(spec, Form) else {}
    values: list[Any] = []
    for f, value in provided:
        normalized = normalize_value(value, f.type_name, structs, f.name)
        if f.kind == KIND_JSON:
            size = _count_elements(normalized)
            if size > max_list_elements:
                raise ValidationError(
                    f.name,
                    f"holds {size:,} elements; the playground accepts up to {max_list_elements:,}",
                )
        values.append(normalized)
    if isinstance(spec, Form):
        enforce_count_relations(spec, dict(zip([f.name for f, _ in provided], values, strict=True)))
    return values


def named_args(spec: Sequence[FieldSpec], values: Sequence[Any]) -> dict[str, Any]:
    """`{name: value}` for a positional argument list, in signature order."""
    fields = list(spec)
    if len(values) > len(fields):
        raise ValueError(f"{len(values)} values for {len(fields)} fields")
    return {f.name: v for f, v in zip(fields, values, strict=False)}


# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------


def repo_id(family: str) -> str:
    """`stats`, `algenta-stats` or `thyn-ai/algenta-stats` -> the capped repo id."""
    name = family.strip()
    if "/" not in name:
        if not name.startswith("algenta"):
            name = f"algenta-{name}"
        name = f"{ORG}/{name}"
    if name not in TRUST:
        raise PlaygroundError(f"{family!r} is not a published Algenta kernel family")
    return name


def family_of(repo: str) -> str:
    """`thyn-ai/algenta-stats` -> `stats`; the umbrella -> `algenta`."""
    full = repo_id(repo)
    return "algenta" if full == UMBRELLA else full.removeprefix(f"{ORG}/algenta-")


def py_literal(value: Any) -> str:
    """Python source for a plain value: bools, None, ints, finite floats, strings, lists, dicts."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("a snippet cannot carry a non-finite float")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list | tuple):
        return "[" + ", ".join(py_literal(v) for v in value) + "]"
    if isinstance(value, Mapping):
        return (
            "{"
            + ", ".join(f"{py_literal(str(k))}: {py_literal(v)}" for k, v in value.items())
            + "}"
        )
    raise TypeError(f"cannot render {type(value).__name__} in a snippet")


def _arg_items(args: Any) -> list[str]:
    if isinstance(args, Mapping):
        for key in args:
            if not _IDENT_RE.match(str(key)):
                raise PlaygroundError(f"{key!r} is not a valid keyword")
        return [f"{key}={py_literal(v)}" for key, v in args.items()]
    if isinstance(args, list | tuple):
        return [py_literal(v) for v in args]
    if args is None:
        return []
    raise TypeError("args must be a mapping (keywords), a sequence (positional) or None")


def render_call(callee: str, args: Any, *, width: int = CALL_WIDTH) -> str:
    """`callee(a=1, b=2)` on one line, or one argument per line when it would run past `width`."""
    items = _arg_items(args)
    flat = f"{callee}({', '.join(items)})"
    if len(flat) <= width or not items:
        return flat
    body = "".join(f"    {item},\n" for item in items)
    return f"{callee}(\n{body})"


def _check_names(module: str, function: str) -> None:
    if not _DOTTED_RE.match(module):
        raise PlaygroundError(f"{module!r} is not a module name")
    if not _IDENT_RE.match(function):
        raise PlaygroundError(f"{function!r} is not a function name")


def snippet(family: str, module: str, function: str, args: Any, *, mode: str) -> str:
    """The reproducible call for `family/module.function(args)` in one of `MODES`.

    `args` is a mapping (rendered as keywords, the tab's case) or a sequence (positional). The
    `kernels` and `sdk` texts are valid Python; `mcp` is a JSON-RPC 2.0 `tools/call` frame.
    """
    _check_names(module, function)
    repo = repo_id(family)
    if mode == MODE_KERNELS:
        trust = "".join(f'    "{r}",\n' for r in TRUST)
        load = (
            f'k = get_kernel("{repo}", version={KERNEL_VERSION}, backend="{BACKEND}", '
            "trust_remote_code=TRUST)"
        )
        call = render_call(f"result = k.{module}.{function}", args)
        return (
            f"# {PIP_KERNELS}\n"
            "from kernels import get_kernel\n\n"
            f"TRUST = [\n{trust}]\n"
            f"{load}\n"
            f"{call}\n"
            "print(result)\n"
        )
    if mode == MODE_SDK:
        call = render_call(f'result = libs.module("{module}").{function}', args)
        return (
            f"# {PIP_SDK}\n"
            "from algenta import libraries\n\n"
            "libs = libraries()\n"
            f"{call}\n"
            "print(result)\n"
        )
    if mode == MODE_MCP:
        if isinstance(args, tuple):
            args = list(args)
        if not (args is None or isinstance(args, list | Mapping)):
            raise TypeError("args must be a mapping, a sequence or None")
        frame = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": MCP_TOOL,
                "arguments": {"module": module, "function": function, "args": args},
            },
        }
        return json.dumps(frame, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    raise PlaygroundError(f"mode must be one of {MODES}, got {mode!r}")


# ---------------------------------------------------------------------------
# Hero functions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hero:
    """One hero entry: what to run, against which incumbent, race or run, with which inputs."""

    family: str
    module: str
    function: str
    incumbent: str
    mode: str
    args: Mapping[str, Any]
    note: str

    def __post_init__(self) -> None:
        if self.mode not in HERO_MODES:
            raise ValueError(f"mode must be one of {HERO_MODES}, got {self.mode!r}")
        if self.family not in FAMILIES:
            raise ValueError(f"{self.family!r} is not a kernel family")
        _check_names(self.module, self.function)
        if is_excluded(self.module, self.function):
            raise ValueError(f"{self.module}.{self.function} is excluded")

    @property
    def repo(self) -> str:
        return repo_id(self.family)

    @property
    def qualname(self) -> str:
        return f"{self.module}.{self.function}"


def _grey_sample(width: int, height: int) -> list[float]:
    """A width x height grey image, row-major: a ramp whose direction alternates per row, so a
    difference hash of it has both set and clear bits."""
    rows: list[list[float]] = []
    for r in range(height):
        row = [10.0 * (c + 1) + 5.0 * r for c in range(width)]
        rows.append(row[::-1] if r % 2 else row)
    return [v for row in rows for v in row]


HEROES: tuple[Hero, ...] = (
    Hero(
        "stats",
        "ab_testing",
        "z_test_proportions",
        "statsmodels",
        HERO_RUN,
        {"successes_a": 200, "n_a": 1000, "successes_b": 260, "n_b": 1000},
        "two-proportion z-test: [z, p]",
    ),
    Hero(
        "stats",
        "stat_tests",
        "t_test_2sample",
        "scipy",
        HERO_RUN,
        {
            "sample1": [5.1, 4.9, 6.2, 5.8, 6.0, 5.5, 5.3, 6.1],
            "sample2": [4.8, 5.2, 4.9, 5.0, 4.7, 5.1, 4.6, 5.3],
        },
        "Welch two-sample t-test",
    ),
    Hero(
        "ml",
        "calibration",
        "calibration_curve",
        "scikit-learn",
        HERO_RUN,
        {
            "probs": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95],
            "labels": [0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "n_bins": 5,
        },
        "reliability curve, equal-width bins",
    ),
    Hero(
        "graph",
        "graph_analytics.centrality",
        "graph_betweenness_from_triplets",
        "networkx",
        HERO_RACE,
        {
            "src": [0, 0, 1, 1, 2, 3, 3, 4],
            "dst": [1, 2, 2, 3, 3, 4, 5, 5],
            "weight": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "n_nodes": 6,
            "weighted": False,
            "normalized": True,
        },
        "betweenness centrality",
    ),
    Hero(
        "graph",
        "graph.weighted",
        "shortest_path_dijkstra",
        "networkx",
        HERO_RACE,
        {
            "n": 5,
            "edges": [
                {"src": 0, "dst": 1, "weight": 4.0},
                {"src": 0, "dst": 2, "weight": 1.0},
                {"src": 2, "dst": 1, "weight": 2.0},
                {"src": 1, "dst": 3, "weight": 1.0},
                {"src": 2, "dst": 3, "weight": 5.0},
                {"src": 3, "dst": 4, "weight": 3.0},
            ],
            "source": 0,
        },
        "single-source shortest paths",
    ),
    Hero(
        "text",
        "text.fuzzy",
        "levenshtein_distance",
        "nltk",
        HERO_RACE,
        {"a": "kitten", "b": "sitting"},
        "edit distance",
    ),
    Hero(
        "llm",
        "text.tokenizer",
        "word_ngrams",
        "nltk",
        HERO_RACE,
        {"tokens": ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"], "n": 2},
        "word bigrams",
    ),
    Hero(
        "bits-time",
        "number_theory",
        "is_prime",
        "sympy",
        HERO_RACE,
        {"n": 1_000_003},
        "deterministic Miller-Rabin primality",
    ),
    Hero(
        "finance",
        "option_greeks_batch",
        "chain_greeks",
        "py_vollib",
        HERO_RACE,
        {
            "spots": [100.0, 100.0, 100.0, 100.0],
            "strikes": [90.0, 100.0, 110.0, 120.0],
            "times": [0.5, 0.5, 0.5, 0.5],
            "rates": [0.05, 0.05, 0.05, 0.05],
            "sigmas": [0.2, 0.2, 0.2, 0.2],
            "is_calls": [1.0, 1.0, 0.0, 0.0],
        },
        "Black-Scholes price and Greeks for an option chain",
    ),
    Hero(
        "geometry",
        "geodesy",
        "haversine_distance",
        "geopy",
        HERO_RACE,
        {"lat1": 51.5074, "lon1": -0.1278, "lat2": 48.8566, "lon2": 2.3522},
        "great-circle distance London to Paris, km",
    ),
    Hero(
        "llm",
        "normk.rmsnorm",
        "rmsnorm_fwd_flat",
        "torch",
        HERO_RUN,
        {
            "x": [1.0, 2.0, 3.0, 4.0, 0.5, -1.5, 2.5, -3.5],
            "gamma": [1.0, 1.0, 1.0, 1.0],
            "n_rows": 2,
            "n_cols": 4,
            "eps": 1e-6,
        },
        "RMSNorm forward, 2 rows x 4 columns",
    ),
    Hero(
        "llm",
        "attnk.rope",
        "rope_table",
        "transformers",
        HERO_RUN,
        {"head_dim": 8, "max_pos": 16, "theta": 10000.0},
        "rotary cos/sin table",
    ),
    Hero(
        "llm",
        "llmk.generate",
        "greedy_argmax_flat",
        "transformers",
        HERO_RUN,
        {"logits": [0.1, 2.5, -1.0, 2.4, 0.0, 1.9, -0.5, 0.3], "n": 8},
        "greedy next token over one row of logits",
    ),
    Hero(
        "crypto",
        "perceptual_hash",
        "dhash_flat",
        "imagehash",
        HERO_RUN,
        {
            "flat": _grey_sample(9, 8),
            "width": 9,
            "height": 8,
        },
        "difference hash of a 9x8 grey image, rows alternating direction",
    ),
    Hero(
        "crypto",
        "crypto.hmac",
        "hmac_sha256",
        "hmac (stdlib)",
        HERO_RUN,
        {"key": "algenta", "message": "hello, kernels"},
        "HMAC-SHA256 as hex",
    ),
)


def _check_hero_table(heroes: Sequence[Hero]) -> None:
    if len(heroes) != HERO_COUNT:
        raise HeroMismatchError(f"{len(heroes)} hero entries, the plan has {HERO_COUNT}")
    seen: set[tuple[str, str, str]] = set()
    for hero in heroes:
        key = (hero.family, hero.module, hero.function)
        if key in seen:
            raise HeroMismatchError(f"duplicate hero {hero.repo} {hero.qualname}")
        seen.add(key)
        if not hero.args:
            raise HeroMismatchError(f"{hero.qualname} has no default arguments")
        if not hero.incumbent.strip() or not hero.note.strip():
            raise HeroMismatchError(f"{hero.qualname} needs an incumbent and a note")


_check_hero_table(HEROES)


def check_hero(hero: Hero, kernel: Any) -> list:
    """Validate a hero against the kernel it names; returns the parsed positional arguments."""
    try:
        form = form_spec(kernel, hero.module, hero.function)
        values = parse_inputs(form, hero.args)
    except PlaygroundError as exc:
        raise HeroMismatchError(f"{hero.repo} {hero.qualname}: {exc}") from exc
    if len(values) != len(hero.args):
        raise HeroMismatchError(
            f"{hero.repo} {hero.qualname}: {len(values)} of {len(hero.args)} args used"
        )
    return values


def hero_functions(kernels: Mapping[str, Any] | None = None) -> tuple[Hero, ...]:
    """The fifteen hero entries; with `kernels` (family or repo id -> loaded kernel) each hero whose
    family is loaded is validated against that kernel's contract and `HeroMismatchError` is raised
    for the first disagreement."""
    if kernels:
        loaded = {family_of(key): kernel for key, kernel in kernels.items()}
        for hero in HEROES:
            kernel = loaded.get(hero.family)
            if kernel is not None:
                check_hero(hero, kernel)
    return HEROES


def heroes_for(family: str, heroes: Sequence[Hero] = HEROES) -> tuple[Hero, ...]:
    """The hero entries of one family, in table order."""
    short = family_of(family)
    return tuple(hero for hero in heroes if hero.family == short)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """One validated, timed native call; `latency_ms` includes JSON marshalling across the ABI."""

    module: str
    function: str
    args: list
    result: Any
    latency_ms: float

    @property
    def qualname(self) -> str:
        return f"{self.module}.{self.function}"


def run(
    kernel: Any,
    module: str,
    function: str,
    raw: Mapping[str, Any],
    *,
    max_list_elements: int = MAX_LIST_ELEMENTS,
    clock: Callable[[], float] = time.perf_counter,
) -> RunResult:
    """form_spec -> parse_inputs -> `kernel.execute(module, function, args)`, timed.

    Validation errors are raised before anything native runs; a kernel error (the kernel's own
    `KernelError`) propagates unchanged so the card can show its code. `clock` returns seconds.
    """
    form = form_spec(kernel, module, function)
    args = parse_inputs(form, raw, max_list_elements=max_list_elements)
    execute = native_module(kernel).execute
    t0 = clock()
    result = execute(module, function, args)
    latency_ms = (clock() - t0) * 1e3
    log.info("%s.%s ran in %.3f ms", module, function, latency_ms)
    return RunResult(
        module=module, function=function, args=args, result=result, latency_ms=latency_ms
    )
