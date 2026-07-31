"""Declared capabilities of the local kernel library — and what a kernel has NOT said.

A signature says what types a kernel takes. It cannot say whether the kernel is
deterministic, whether it needs a seed, whether it keeps state between calls, what it
costs, or which of its integer parameters is an ELEMENT COUNT bounding which list. Those
are declared by the kernel author and read here:

    from algenta import MojoRuntime

    rt = MojoRuntime(mode="local")
    caps = rt.capabilities()

    found = caps.search(module_prefix="optimization.", deterministic=True)
    for record in found:
        record.function, record.complexity

    caps.describe("optimization.linear", "lp_solve_default").as_dict()

Undeclared is not False
-----------------------
Every field is either a declared value or `UNDECLARED`. "We have not said" and "we have
said no" are different answers, so they have different representations, and `UNDECLARED`
raises on truth-testing rather than quietly reading as `False`:

    record.deterministic is UNDECLARED     # the only correct test
    if record.deterministic: ...           # TypeError, deliberately

A search never silently omits what it could not evaluate, either. `search()` returns
matches AND the functions that were in scope but had not declared the field being
filtered on, because a caller who sees only the matches would conclude a capability does
not exist when it merely was not described.

Scope and errors
----------------
The catalog covers the runtime library contract that ships with this package. An unknown
module or function RAISES `CapabilityError` — it does not come back as an empty result,
for the same reason: a typo must not read as "that capability is not there".

Where the declarations come from
--------------------------------
Two sources, deliberately:

* **Count relations** travel on the library contract itself, beside the signature they
  constrain, because the runtime enforces them from the same place. An EMPTY list on the
  contract means the relations were not published for that function — silence, not "this
  function has no count arguments" — so it reports as `UNDECLARED`.
* **Everything else** comes from `runtime_capability_manifest.json`, bundled beside the
  contract. Its shape is `{"schema_version": 1, "modules": [{"name": <module>,
  "functions": [{"name": <function>, "capability": {<field>: <value>, ...}}]}]}`; a flat
  `{"functions": [{"module": ..., "function": ..., "capability": {...}}]}` is accepted
  too, and the block may be spelled inline on the function entry. A field that is absent
  or `null` is undeclared, and so is a block that states nothing at all — an empty block
  carries no more information than no block, and reporting `has_block=True` for one would
  invite a reader to conclude that someone considered and declined every field.

That resource is generated from the kernels' own declared blocks by
`scripts/generate_algenta_capability_manifest.py` (run by `make inventory-refresh`, drift-
gated by `make inventory-check`) and shipped as package data. It is a TRANSCRIPTION: a
field the kernel author did not declare is omitted, never written out as `false`. A
function with no declared block of its own gets no entry — including when its module
declares module-scope defaults, because spreading a module-scope claim over functions
nobody annotated would manufacture a per-function declaration.

A build that ships no such resource reports every field as `UNDECLARED`, which is the
honest answer rather than a tree of `false`; check `manifest_present` before reading a
search as evidence about the kernels. A malformed manifest RAISES rather than degrading to
"nothing declared", because that degradation is indistinguishable from a tree nobody has
annotated yet.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources
from typing import Any

__all__ = [
    "UNDECLARED",
    "CapabilityCatalog",
    "CapabilityError",
    "CapabilityRecord",
    "CapabilitySearchResult",
    "CountRelation",
    "Undeclared",
    "UndeclaredCapability",
    "capabilities",
]


# The bundled artifact holding the declared blocks. Absent (a build that has not
# generated it yet) means every function reports UNDECLARED — never `False`.
_MANIFEST_RESOURCE = "runtime_capability_manifest.json"
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS = (1,)


class CapabilityError(RuntimeError):
    """A capability lookup was rejected, or the bundled manifest is unusable.

    `code` is one of `module_not_registered`, `function_not_registered`,
    `invalid_arguments` or `invalid_capability_manifest`; `details` carries the names
    involved. A rejected lookup returns NO record — an empty record would be
    indistinguishable from a function that declared nothing.
    """

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class Undeclared:
    """The value of a capability field nobody has declared.

    Not `False`, not `None`, not `""`. Truth-testing raises, so `if rec.stateful:`
    cannot silently treat "not stated" as "stateless" — that conflation is the whole
    reason this object exists rather than a default.
    """

    __slots__ = ()
    _instance: Undeclared | None = None

    def __new__(cls) -> Undeclared:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNDECLARED"

    def __str__(self) -> str:
        return "undeclared"

    def __bool__(self) -> bool:
        raise TypeError(
            "This capability is UNDECLARED, which is not True and not False. "
            "Compare with `is UNDECLARED` and decide what to do about the absence."
        )

    def __reduce__(self) -> tuple[Any, ...]:
        return (Undeclared, ())


UNDECLARED = Undeclared()


@dataclass(frozen=True)
class CountRelation:
    """`product(factors) + plus` elements are required in each list named by `bounds`.

    The declared statement that some integer parameter is an element COUNT over some
    list, which no signature can express. One factor is a plain element count; two are
    the dimensions of a flat row-major matrix. One count bounding several parallel lists
    is ONE relation with several `bounds`, which is how a sparse triple is written.
    `plus` is a constant added to the product, and `plus=1` is also how an INDEX
    parameter is expressed — reading `adj[node]` needs `node + 1` elements. `scope` is
    `length` for the list itself or `element_length` for every element list of a nested
    list; `role` is `count` or `index` and only shapes a message.

    Field names and meanings mirror the runtime's own relation type, so the reported
    relation and the enforced relation cannot drift into two different statements. This
    surface REPORTS; the runtime enforces.
    """

    factors: tuple[str, ...]
    bounds: tuple[str, ...]
    plus: int = 0
    scope: str = "length"
    role: str = "count"

    @property
    def expression(self) -> str:
        """The bound as a reader would say it, e.g. `rows * cols + 1 <= len(a)`."""
        left = " * ".join(self.factors)
        if self.plus:
            left = f"{left} + {self.plus}"
        lists = ", ".join(self.bounds)
        return f"{left} <= len({lists})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "factors": list(self.factors),
            "bounds": list(self.bounds),
            "plus": self.plus,
            "scope": self.scope,
            "role": self.role,
        }


# Canonical field order, matching the declared block. `count_relations` is the field
# with a caller-facing consequence: it is the only machine-readable statement of which
# integer parameter counts elements of which list.
CAPABILITY_FIELDS: tuple[str, ...] = (
    "deterministic",
    "seed_requirements",
    "stateful",
    "batch_capable",
    "stream_capable",
    "supported_dtypes",
    "complexity",
    "backend",
    "surfaces",
    "count_relations",
    "golden_vectors",
    "benchmark",
    "docs",
    "version_introduced",
    "deprecation_state",
)

_BOOL_FIELDS = ("deterministic", "stateful", "batch_capable", "stream_capable")
_STRING_FIELDS = (
    "seed_requirements",
    "complexity",
    "backend",
    "golden_vectors",
    "benchmark",
    "docs",
    "version_introduced",
    "deprecation_state",
)
_STRING_TUPLE_FIELDS = ("supported_dtypes", "surfaces")

# The closed vocabularies a declaration draws on, mirrored here so a filter typo carries
# the caller's traceback instead of coming back as zero matches. Mirrored, not owned: a
# filter value is also accepted when some loaded declaration uses it, so a vocabulary
# that grows on the engine side can never make this surface refuse a real value.
SEED_REQUIREMENTS = ("none", "optional", "required")
BACKENDS = ("mojo", "mojo_simd", "python_fallback")
SURFACES = (
    "library_execute",
    "batch_execute",
    "pipeline_execute",
    "query_execute",
    "session",
    "internal",
)
DEPRECATION_STATES = ("active", "soft_deprecated", "deprecated", "scheduled_removal")

# `requires_seed=False` asks "can I call this without a seed", so an OPTIONAL seed
# qualifies. Only `required` means a caller must supply one. The three-valued
# `seed_requirements` stays available, because collapsing it here would lose "optional".
_SEED_NOT_REQUIRED = frozenset({"none", "optional"})


@dataclass(frozen=True)
class CapabilityRecord:
    """What one kernel function has declared, field by field.

    Every field is a declared value or `UNDECLARED`. `has_block` is False when the
    function carries no declared block at all, which is different from a block that
    happens to omit one field.
    """

    module: str
    function: str
    has_block: bool = False
    deterministic: bool | Undeclared = UNDECLARED
    seed_requirements: str | Undeclared = UNDECLARED
    stateful: bool | Undeclared = UNDECLARED
    batch_capable: bool | Undeclared = UNDECLARED
    stream_capable: bool | Undeclared = UNDECLARED
    supported_dtypes: tuple[str, ...] | Undeclared = UNDECLARED
    complexity: str | Undeclared = UNDECLARED
    backend: str | Undeclared = UNDECLARED
    surfaces: tuple[str, ...] | Undeclared = UNDECLARED
    count_relations: tuple[CountRelation, ...] | Undeclared = UNDECLARED
    golden_vectors: str | Undeclared = UNDECLARED
    benchmark: str | Undeclared = UNDECLARED
    docs: str | Undeclared = UNDECLARED
    version_introduced: str | Undeclared = UNDECLARED
    deprecation_state: str | Undeclared = UNDECLARED

    # ── which fields are answers, and which are silence ───────────────────────
    def declared_fields(self) -> tuple[str, ...]:
        return tuple(name for name in CAPABILITY_FIELDS if getattr(self, name) is not UNDECLARED)

    def undeclared_fields(self) -> tuple[str, ...]:
        return tuple(name for name in CAPABILITY_FIELDS if getattr(self, name) is UNDECLARED)

    def is_declared(self, field_name: str) -> bool:
        """True when `field_name` carries a declared value. Raises on an unknown name."""
        if field_name not in CAPABILITY_FIELDS:
            raise CapabilityError(
                "invalid_arguments",
                f"Unknown capability field {field_name!r}.",
                {"field": field_name, "known_fields": list(CAPABILITY_FIELDS)},
            )
        return getattr(self, field_name) is not UNDECLARED

    @property
    def requires_seed(self) -> bool | Undeclared:
        """Whether a caller MUST supply a seed, read from `seed_requirements`.

        `UNDECLARED` when nothing was said. `optional` reads as False here — the call
        works without one — so read `seed_requirements` itself when the difference
        between "no seed exists" and "a seed is accepted" matters.
        """
        declared = self.seed_requirements
        if declared is UNDECLARED:
            return UNDECLARED
        assert isinstance(declared, str)
        return declared.strip().lower() not in _SEED_NOT_REQUIRED

    def as_dict(self) -> dict[str, Any]:
        """Declared fields only, plus the names of the ones nobody declared.

        Undeclared fields are OMITTED rather than serialized as `null` or `false`: a
        JSON consumer must not be handed a value the kernel never claimed.
        """
        payload: dict[str, Any] = {
            "module": self.module,
            "function": self.function,
            "has_block": self.has_block,
        }
        for name in CAPABILITY_FIELDS:
            value = getattr(self, name)
            if value is UNDECLARED:
                continue
            if name == "count_relations":
                assert isinstance(value, tuple)
                payload[name] = [relation.as_dict() for relation in value]
            elif isinstance(value, tuple):
                payload[name] = list(value)
            else:
                payload[name] = value
        requires_seed = self.requires_seed
        if requires_seed is not UNDECLARED:
            payload["requires_seed"] = requires_seed
        payload["undeclared_fields"] = list(self.undeclared_fields())
        return payload


@dataclass(frozen=True)
class UndeclaredCapability:
    """A function that was in scope but could not be judged against the filters.

    `missing` names the filtered fields it never declared. `has_block` is False when it
    carries no declared block at all. It is reported rather than dropped, so a caller
    cannot mistake silence for absence.
    """

    module: str
    function: str
    has_block: bool
    missing: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "function": self.function,
            "has_block": self.has_block,
            "missing": list(self.missing),
        }


@dataclass(frozen=True, repr=False)
class CapabilitySearchResult:
    """Matches, and the in-scope functions whose declarations could not answer.

    Iterating and `len()` give the MATCHES, because that is what a caller loops over.
    `undeclared` is never empty-by-omission: read it before concluding a capability does
    not exist anywhere.
    """

    filters: Mapping[str, Any]
    matches: tuple[CapabilityRecord, ...] = ()
    undeclared: tuple[UndeclaredCapability, ...] = ()
    total_matches: int = 0
    truncated: bool = False
    scanned: int = 0

    def __iter__(self) -> Iterator[CapabilityRecord]:
        return iter(self.matches)

    def __len__(self) -> int:
        return len(self.matches)

    def __repr__(self) -> str:
        return (
            f"CapabilitySearchResult(matches={len(self.matches)}, "
            f"total_matches={self.total_matches}, truncated={self.truncated}, "
            f"undeclared={len(self.undeclared)}, scanned={self.scanned})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "filters": dict(self.filters),
            "matches": [record.as_dict() for record in self.matches],
            "undeclared": [item.as_dict() for item in self.undeclared],
            "total_matches": self.total_matches,
            "truncated": self.truncated,
            "scanned": self.scanned,
        }


# ── manifest parsing ──────────────────────────────────────────────────────────
# Strict about types, permissive about nothing. A malformed manifest raises rather than
# degrading into "everything is undeclared", because that degradation would look exactly
# like a tree nobody has annotated yet.


def _manifest_error(message: str, details: dict[str, Any] | None = None) -> CapabilityError:
    return CapabilityError("invalid_capability_manifest", message, details)


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _manifest_error(f"{context} must be an object", {"context": context})
    return value


def _require_sequence(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise _manifest_error(f"{context} must be a list", {"context": context})
    return value


def _require_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _manifest_error(f"{context} must be a non-empty string", {"context": context})
    return value.strip()


def _parse_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise _manifest_error(f"{context} must be a boolean", {"context": context})
    return value


def _parse_string(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise _manifest_error(f"{context} must be a string", {"context": context})
    return value.strip()


def _parse_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, list | tuple):
        items: list[str] = []
        for index, item in enumerate(value):
            if not isinstance(item, str):
                raise _manifest_error(f"{context}[{index}] must be a string", {"context": context})
            if item.strip():
                items.append(item.strip())
        return tuple(items)
    raise _manifest_error(f"{context} must be a string or a list of strings", {"context": context})


_RELATION_SCOPES = frozenset({"length", "element_length"})
_RELATION_ROLES = frozenset({"count", "index"})


def _first_present(payload: Mapping[str, Any], keys: Sequence[str]) -> tuple[str, Any] | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            return key, payload[key]
    return None


def _parse_count_relation(value: Any, context: str) -> CountRelation:
    payload = _require_mapping(value, context)
    factors = _parse_string_tuple(payload.get("factors"), f"{context}.factors")
    bounds = _parse_string_tuple(payload.get("bounds"), f"{context}.bounds")
    # A relation missing either side could never be evaluated, so it would silently
    # disable itself — the exact failure this mechanism exists to remove.
    if not factors or not bounds:
        raise _manifest_error(
            f"{context} must name at least one factor and one bound", {"context": context}
        )
    plus = payload.get("plus", 0)
    if isinstance(plus, bool) or not isinstance(plus, int) or plus < 0:
        raise _manifest_error(
            f"{context}.plus must be a non-negative integer", {"context": context}
        )
    scope = _parse_string(payload.get("scope", "length"), f"{context}.scope")
    if scope not in _RELATION_SCOPES:
        raise _manifest_error(
            f"{context}.scope must be one of {sorted(_RELATION_SCOPES)}", {"context": context}
        )
    role = _parse_string(payload.get("role", "count"), f"{context}.role")
    if role not in _RELATION_ROLES:
        raise _manifest_error(
            f"{context}.role must be one of {sorted(_RELATION_ROLES)}", {"context": context}
        )
    return CountRelation(factors=factors, bounds=bounds, plus=plus, scope=scope, role=role)


def _parse_count_relations(value: Any, context: str) -> tuple[CountRelation, ...]:
    entries = _require_sequence(value, context)
    relations = tuple(
        _parse_count_relation(item, f"{context}[{index}]") for index, item in enumerate(entries)
    )
    if len(set(relations)) != len(relations):
        raise _manifest_error(f"{context} declares the same relation twice", {"context": context})
    return relations


def _relation_from_contract(value: Any, context: str) -> CountRelation:
    """One relation as the shipped library contract carries it.

    Accepts the contract's own relation object or the equivalent mapping. Malformed input
    raises: a relation nobody can read must not become a relation nobody applies.
    """
    if isinstance(value, Mapping):
        return _parse_count_relation(value, context)
    payload = {
        "factors": getattr(value, "factors", None),
        "bounds": getattr(value, "bounds", None),
        "plus": getattr(value, "plus", 0),
        "scope": getattr(value, "scope", "length"),
        "role": getattr(value, "role", "count"),
    }
    return _parse_count_relation(payload, context)


_BLOCK_KEYS = ("capability", "capabilities", "declared", "block")


def _capability_block(payload: Mapping[str, Any], context: str) -> dict[str, Any] | None:
    """The declared block for one function, or None when there is no block.

    Accepts the block nested under a `capability` key or spelled inline on the function
    entry; a function entry carrying neither has NO block, which is a real answer.

    An EMPTY block is the same answer. `{"capability": {}}`, and a block whose every field
    is `null`, state nothing — reporting `has_block=True` for them would tell a reader that
    someone looked at this function and declined every field, which is a stronger claim than
    the artifact makes. So they read as "no block", and every field stays `UNDECLARED`.
    """
    nested = _first_present(payload, _BLOCK_KEYS)
    if nested is not None:
        block = _require_mapping(nested[1], f"{context}.{nested[0]}")
    else:
        block = {key: value for key, value in payload.items() if key in CAPABILITY_FIELDS}
    stated = {key: value for key, value in block.items() if value is not None}
    return block if stated else None


def _parse_block(
    module: str,
    function: str,
    block: Mapping[str, Any],
    context: str,
) -> CapabilityRecord:
    values: dict[str, Any] = {}
    for name in CAPABILITY_FIELDS:
        raw = block.get(name)
        if raw is None:
            # Absent and explicit null are the same statement: nothing was said.
            continue
        where = f"{context}.{name}"
        if name in _BOOL_FIELDS:
            values[name] = _parse_bool(raw, where)
        elif name in _STRING_FIELDS:
            values[name] = _parse_string(raw, where)
        elif name in _STRING_TUPLE_FIELDS:
            values[name] = _parse_string_tuple(raw, where)
        elif name == "count_relations":
            values[name] = _parse_count_relations(raw, where)
        else:  # pragma: no cover - defended by the field tables above
            raise _manifest_error(f"{where} has no parse rule", {"field": name})
    return CapabilityRecord(module=module, function=function, has_block=True, **values)


def _parse_manifest(payload: Any) -> dict[tuple[str, str], CapabilityRecord]:
    root = _require_mapping(payload, "capability manifest")
    version = root.get("schema_version")
    if version not in _SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        raise _manifest_error(
            "Unsupported capability manifest schema version",
            {"schema_version": version, "supported": list(_SUPPORTED_MANIFEST_SCHEMA_VERSIONS)},
        )

    records: dict[tuple[str, str], CapabilityRecord] = {}

    def _add(record: CapabilityRecord, context: str) -> None:
        key = (record.module, record.function)
        if key in records:
            raise _manifest_error(
                f"{context} declares {record.module}.{record.function} twice",
                {"module": record.module, "function": record.function},
            )
        records[key] = record

    if "modules" in root:
        for module_index, raw_module in enumerate(
            _require_sequence(root.get("modules"), "modules")
        ):
            module_context = f"modules[{module_index}]"
            module_payload = _require_mapping(raw_module, module_context)
            module_name = _require_name(
                module_payload.get("name") or module_payload.get("module"),
                f"{module_context}.name",
            )
            for function_index, raw_function in enumerate(
                _require_sequence(module_payload.get("functions"), f"{module_context}.functions")
            ):
                function_context = f"{module_context}.functions[{function_index}]"
                function_payload = _require_mapping(raw_function, function_context)
                function_name = _require_name(
                    function_payload.get("name") or function_payload.get("function"),
                    f"{function_context}.name",
                )
                block = _capability_block(function_payload, function_context)
                if block is None:
                    continue
                _add(
                    _parse_block(module_name, function_name, block, function_context),
                    function_context,
                )
        return records

    flat = _first_present(root, ("functions", "capabilities"))
    if flat is None:
        raise _manifest_error(
            "Capability manifest has neither `modules` nor a flat function list",
            {"keys": sorted(root)},
        )
    for index, raw_entry in enumerate(_require_sequence(flat[1], flat[0])):
        context = f"{flat[0]}[{index}]"
        entry = _require_mapping(raw_entry, context)
        module_name = _require_name(entry.get("module"), f"{context}.module")
        function_name = _require_name(
            entry.get("function") or entry.get("name"), f"{context}.function"
        )
        block = _capability_block(entry, context)
        if block is None:
            continue
        _add(_parse_block(module_name, function_name, block, context), context)
    return records


def _read_bundled_json(resource_name: str) -> Any | None:
    """Parsed bundled JSON, or None when this build does not ship that resource."""
    try:
        resource = resources.files("algenta").joinpath(resource_name)
    except ModuleNotFoundError, TypeError:  # pragma: no cover - packaging edge
        return None
    try:
        if not resource.is_file():
            return None
        text = resource.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _manifest_error(
            f"The bundled {resource_name} is not valid JSON", {"resource": resource_name}
        ) from exc


@lru_cache(maxsize=1)
def _bundled_declarations() -> tuple[dict[tuple[str, str], CapabilityRecord], str]:
    """(declarations, source resource name). No source means everything is UNDECLARED.

    Count relations do NOT come from here — they travel on the library contract, beside
    the signature they constrain, so the relation this surface reports and the relation
    the runtime enforces are one statement rather than two that can disagree.
    """
    payload = _read_bundled_json(_MANIFEST_RESOURCE)
    if payload is not None:
        return _parse_manifest(payload), _MANIFEST_RESOURCE
    return {}, ""


# ── the catalog ───────────────────────────────────────────────────────────────


def _validate_optional_bool(name: str, value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise CapabilityError(
        "invalid_arguments",
        f"`{name}` must be True, False or None (None means 'do not filter on it').",
        {"filter": name, "value": repr(value)},
    )


def _validate_optional_text(name: str, value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CapabilityError(
            "invalid_arguments",
            f"`{name}` must be a string.",
            {"filter": name, "value": repr(value)},
        )
    stripped = value.strip()
    if value and not stripped:
        raise CapabilityError(
            "invalid_arguments",
            f"`{name}` is whitespace, which matches nothing; omit it instead.",
            {"filter": name},
        )
    return stripped


@dataclass(frozen=True)
class _FunctionRef:
    module: str
    function: str


class CapabilityCatalog:
    """Search and describe the declared capabilities of the local kernel library.

    Constructed for you by `MojoRuntime.capabilities()`. The two keyword arguments are
    a testing seam: `contract_modules` overrides the function inventory and
    `manifest_payload` overrides the declared blocks.
    """

    def __init__(
        self,
        *,
        contract_modules: Any = None,
        manifest_payload: Any = None,
    ) -> None:
        self._functions: tuple[_FunctionRef, ...] = ()
        self._module_functions: dict[str, tuple[str, ...]] = {}
        self._contract_relations: dict[tuple[str, str], tuple[CountRelation, ...]] = {}
        self._load_functions(contract_modules)
        if manifest_payload is None:
            declarations, source = _bundled_declarations()
            self._declarations = dict(declarations)
            self._declaration_source = source
        else:
            self._declarations = _parse_manifest(manifest_payload)
            self._declaration_source = "supplied"
        self._declared_value_cache: dict[str, frozenset[str]] = {}
        known = {(ref.module, ref.function) for ref in self._functions}
        self._orphans = tuple(sorted(key for key in self._declarations if key not in known))

    # ── inventory ─────────────────────────────────────────────────────────────
    def _load_functions(self, contract_modules: Any) -> None:
        if contract_modules is None:
            from algenta.runtime_library_contract import (
                RuntimeLibraryContractError,
                runtime_modules,
            )

            try:
                contract_modules = runtime_modules()
            except RuntimeLibraryContractError as exc:
                raise CapabilityError(
                    exc.code,
                    f"The runtime library contract is unusable: {exc}",
                    dict(exc.details),
                ) from exc
        refs: list[_FunctionRef] = []
        module_functions: dict[str, tuple[str, ...]] = {}
        for module in contract_modules:
            module_name = str(getattr(module, "import_path", "") or "").strip()
            if not module_name:
                raise CapabilityError(
                    "invalid_arguments",
                    "A contract module was supplied without an import path.",
                    {"module": repr(module)},
                )
            names: list[str] = []
            for function in getattr(module, "functions", ()) or ():
                function_name = str(getattr(function, "name", function) or "").strip()
                if not function_name:
                    raise CapabilityError(
                        "invalid_arguments",
                        f"Module {module_name!r} listed a function without a name.",
                        {"module": module_name},
                    )
                names.append(function_name)
                refs.append(_FunctionRef(module_name, function_name))
                # An EMPTY tuple on the contract means the relations have not been
                # published for this function, which is silence — not "this function has
                # no count parameters". Only a non-empty tuple is a declaration.
                raw_relations = getattr(function, "count_relations", ()) or ()
                if raw_relations:
                    context = f"{module_name}.{function_name}.count_relations"
                    self._contract_relations[(module_name, function_name)] = tuple(
                        _relation_from_contract(item, f"{context}[{index}]")
                        for index, item in enumerate(raw_relations)
                    )
            module_functions[module_name] = tuple(names)
        self._functions = tuple(refs)
        self._module_functions = module_functions

    def modules(self) -> tuple[str, ...]:
        """Every module the catalog covers, whether or not it has declared anything."""
        return tuple(sorted(self._module_functions))

    def functions(self, module: str) -> tuple[str, ...]:
        """Function names in `module`. Raises when the module is unknown."""
        return self._module_functions[self._require_module(module)]

    @property
    def manifest_present(self) -> bool:
        """False when this build ships no declarations, so every field is UNDECLARED.

        Worth checking before reporting a search as evidence: with no declarations at
        all, "no matches" says nothing about the kernels and everything about the build.
        """
        return bool(self._declaration_source)

    @property
    def declaration_source(self) -> str:
        """Where the declarations were read from; empty when none were found."""
        return self._declaration_source

    @property
    def orphan_declarations(self) -> tuple[tuple[str, str], ...]:
        """Declarations naming a function the contract does not list.

        Reported rather than dropped: a declaration nobody can reach is a stale
        artifact, and staleness that produces no symptom is how a manifest rots.
        """
        return self._orphans

    # ── describe ──────────────────────────────────────────────────────────────
    def _require_module(self, module: Any) -> str:
        name = _validate_optional_text("module", module)
        if not name:
            raise CapabilityError(
                "invalid_arguments", "A module name is required.", {"module": repr(module)}
            )
        if name not in self._module_functions:
            raise CapabilityError(
                "module_not_registered",
                f"Unknown runtime library {name!r}.",
                {"module": name},
            )
        return name

    _VOCABULARY_FIELD = {
        "backend": "backend",
        "surface": "surfaces",
        "deprecation_state": "deprecation_state",
        "seed_requirements": "seed_requirements",
    }

    def _declared_values(self, filter_name: str) -> frozenset[str]:
        """Every value the loaded declarations actually use for this field."""
        cached = self._declared_value_cache.get(filter_name)
        if cached is not None:
            return cached
        field_name = self._VOCABULARY_FIELD[filter_name]
        seen: set[str] = set()
        for record in self._declarations.values():
            value = getattr(record, field_name)
            if value is UNDECLARED:
                continue
            if isinstance(value, tuple):
                seen.update(item.lower() for item in value)
            else:
                seen.add(str(value).lower())
        found = frozenset(seen)
        self._declared_value_cache[filter_name] = found
        return found

    def _require_vocabulary(self, name: str, value: str, vocabulary: Sequence[str]) -> None:
        """Reject a filter value no declaration could ever carry.

        Checked against the mirrored vocabulary OR anything the loaded declarations use,
        so this can refuse a typo without being able to refuse a real value.
        """
        if not value:
            return
        if value in {item.lower() for item in vocabulary} or value in self._declared_values(name):
            return
        raise CapabilityError(
            "invalid_arguments",
            f"`{name}={value!r}` is not a value a declaration uses; "
            f"expected one of {sorted(vocabulary)}.",
            {"filter": name, "value": value, "expected": sorted(vocabulary)},
        )

    def describe(self, module: str, function: str) -> CapabilityRecord:
        """What `module.function` has declared, field by field.

        A function with no declared block returns a record whose `has_block` is False
        and whose every field is `UNDECLARED` — never `deterministic=False`. An unknown
        module or function RAISES rather than returning an empty record.
        """
        module_name = self._require_module(module)
        function_name = _validate_optional_text("function", function)
        if not function_name:
            raise CapabilityError(
                "invalid_arguments",
                "A function name is required.",
                {"module": module_name, "function": repr(function)},
            )
        if function_name not in self._module_functions[module_name]:
            raise CapabilityError(
                "function_not_registered",
                f"Runtime library {module_name!r} does not expose {function_name!r}.",
                {"module": module_name, "function": function_name},
            )
        record = self._effective(module_name, function_name)
        if record is not None:
            return record
        return CapabilityRecord(module=module_name, function=function_name, has_block=False)

    def _effective(self, module: str, function: str) -> CapabilityRecord | None:
        """The merged record, or None when nothing at all has been declared.

        The declared block owns every field it states, including a declared-EMPTY
        `count_relations` (the author saying "no count parameters"). Relations published
        on the library contract fill that field only when the block is silent about it, so
        one statement never overwrites another.
        """
        record = self._declarations.get((module, function))
        relations = self._contract_relations.get((module, function))
        if record is None:
            if relations is None:
                return None
            return CapabilityRecord(
                module=module, function=function, has_block=False, count_relations=relations
            )
        if relations is not None and record.count_relations is UNDECLARED:
            return replace(record, count_relations=relations)
        return record

    # ── search ────────────────────────────────────────────────────────────────
    def search(
        self,
        *,
        module: str | None = None,
        module_prefix: str | None = None,
        function: str | None = None,
        deterministic: bool | None = None,
        requires_seed: bool | None = None,
        seed_requirements: str | None = None,
        stateful: bool | None = None,
        batch_capable: bool | None = None,
        stream_capable: bool | None = None,
        declares_count_relations: bool | None = None,
        dtype: str | None = None,
        backend: str | None = None,
        surface: str | None = None,
        complexity: str | None = None,
        deprecation_state: str | None = None,
        limit: int | None = None,
    ) -> CapabilitySearchResult:
        """Find functions by what they DECLARED, and report what could not be judged.

        `module` / `module_prefix` / `function` narrow the scope by name; `function` is a
        case-insensitive substring. A `module` or `module_prefix` matching nothing RAISES
        — zero matches for a typo is the failure mode this whole surface exists to avoid.

        The remaining arguments filter on declared capabilities. A function in scope that
        never declared a filtered field cannot match and cannot be ruled out either, so
        it is returned in `undeclared` with the field named. `requires_seed=True` means
        `seed_requirements` is `required`; `False` accepts `none` and `optional`, since
        both can be called without one — filter `seed_requirements` directly to separate
        those two. `declares_count_relations` selects functions that have stated which of
        their integer parameters count the elements of which list.

        `complexity`, `backend`, `surface`, `dtype` and `deprecation_state` compare
        case-insensitively, and `dtype`/`surface` test membership of the declared list. A
        value outside the vocabulary a declaration can use RAISES, for the same reason a
        mistyped module does.
        """
        module_name = _validate_optional_text("module", module)
        prefix = _validate_optional_text("module_prefix", module_prefix)
        needle = _validate_optional_text("function", function).lower()
        dtype_filter = _validate_optional_text("dtype", dtype).lower()
        backend_filter = _validate_optional_text("backend", backend).lower()
        surface_filter = _validate_optional_text("surface", surface).lower()
        complexity_filter = _validate_optional_text("complexity", complexity).lower()
        deprecation_filter = _validate_optional_text("deprecation_state", deprecation_state).lower()
        seed_filter = _validate_optional_text("seed_requirements", seed_requirements).lower()
        self._require_vocabulary("backend", backend_filter, BACKENDS)
        self._require_vocabulary("surface", surface_filter, SURFACES)
        self._require_vocabulary("deprecation_state", deprecation_filter, DEPRECATION_STATES)
        self._require_vocabulary("seed_requirements", seed_filter, SEED_REQUIREMENTS)

        bool_filters = {
            "deterministic": _validate_optional_bool("deterministic", deterministic),
            "stateful": _validate_optional_bool("stateful", stateful),
            "batch_capable": _validate_optional_bool("batch_capable", batch_capable),
            "stream_capable": _validate_optional_bool("stream_capable", stream_capable),
        }
        requires_seed_filter = _validate_optional_bool("requires_seed", requires_seed)
        count_relations_filter = _validate_optional_bool(
            "declares_count_relations", declares_count_relations
        )

        if limit is not None:
            if not isinstance(limit, int) or isinstance(limit, bool):
                raise CapabilityError(
                    "invalid_arguments", "`limit` must be an integer.", {"limit": repr(limit)}
                )
            if limit <= 0:
                raise CapabilityError(
                    "invalid_arguments",
                    "`limit` must be greater than zero; omit it to return everything.",
                    {"limit": limit},
                )

        if module_name:
            self._require_module(module_name)
        if prefix and not any(name.startswith(prefix) for name in self._module_functions):
            raise CapabilityError(
                "module_not_registered",
                f"No runtime library starts with {prefix!r}.",
                {"module_prefix": prefix},
            )

        filters: dict[str, Any] = {}
        for name, value in (
            ("module", module_name),
            ("module_prefix", prefix),
            ("function", needle),
            ("dtype", dtype_filter),
            ("backend", backend_filter),
            ("surface", surface_filter),
            ("complexity", complexity_filter),
            ("deprecation_state", deprecation_filter),
            ("seed_requirements", seed_filter),
        ):
            if value:
                filters[name] = value
        for name, value in bool_filters.items():
            if value is not None:
                filters[name] = value
        if requires_seed_filter is not None:
            filters["requires_seed"] = requires_seed_filter
        if count_relations_filter is not None:
            filters["declares_count_relations"] = count_relations_filter
        if limit is not None:
            filters["limit"] = limit

        matches: list[CapabilityRecord] = []
        undeclared: list[UndeclaredCapability] = []
        scanned = 0

        for ref in self._functions:
            if module_name and ref.module != module_name:
                continue
            if prefix and not ref.module.startswith(prefix):
                continue
            if needle and needle not in ref.function.lower():
                continue
            scanned += 1

            record = self._effective(ref.module, ref.function)
            if record is None:
                undeclared.append(
                    UndeclaredCapability(
                        module=ref.module,
                        function=ref.function,
                        has_block=False,
                        missing=tuple(
                            name
                            for name in self._filtered_field_names(
                                bool_filters,
                                requires_seed_filter,
                                count_relations_filter,
                                dtype_filter,
                                backend_filter,
                                surface_filter,
                                complexity_filter,
                                deprecation_filter,
                                seed_filter,
                            )
                        ),
                    )
                )
                continue

            missing: list[str] = []
            keep = True

            for name, wanted in bool_filters.items():
                if wanted is None:
                    continue
                declared = getattr(record, name)
                if declared is UNDECLARED:
                    missing.append(name)
                elif declared != wanted:
                    keep = False

            if requires_seed_filter is not None:
                declared_seed = record.requires_seed
                if declared_seed is UNDECLARED:
                    missing.append("seed_requirements")
                elif declared_seed != requires_seed_filter:
                    keep = False

            if count_relations_filter is not None:
                declared_relations = record.count_relations
                if declared_relations is UNDECLARED:
                    missing.append("count_relations")
                elif bool(declared_relations) != count_relations_filter:
                    keep = False

            for name, wanted_text, membership in (
                ("complexity", complexity_filter, False),
                ("backend", backend_filter, False),
                ("deprecation_state", deprecation_filter, False),
                ("seed_requirements", seed_filter, False),
                ("supported_dtypes", dtype_filter, True),
                ("surfaces", surface_filter, True),
            ):
                if not wanted_text:
                    continue
                declared_value = getattr(record, name)
                if declared_value is UNDECLARED:
                    missing.append(name)
                    continue
                if membership:
                    assert isinstance(declared_value, tuple)
                    if wanted_text not in {item.lower() for item in declared_value}:
                        keep = False
                elif str(declared_value).lower() != wanted_text:
                    keep = False

            if missing:
                # It declared something, but not the thing being asked about. Neither a
                # match nor a rejection.
                undeclared.append(
                    UndeclaredCapability(
                        module=ref.module,
                        function=ref.function,
                        has_block=True,
                        missing=tuple(dict.fromkeys(missing)),
                    )
                )
                continue
            if keep:
                matches.append(record)

        total = len(matches)
        truncated = limit is not None and total > limit
        if truncated:
            matches = matches[:limit]
        return CapabilitySearchResult(
            filters=filters,
            matches=tuple(matches),
            undeclared=tuple(undeclared),
            total_matches=total,
            truncated=truncated,
            scanned=scanned,
        )

    @staticmethod
    def _filtered_field_names(
        bool_filters: Mapping[str, bool | None],
        requires_seed_filter: bool | None,
        count_relations_filter: bool | None,
        dtype_filter: str,
        backend_filter: str,
        surface_filter: str,
        complexity_filter: str,
        deprecation_filter: str,
        seed_filter: str,
    ) -> tuple[str, ...]:
        names: list[str] = [name for name, value in bool_filters.items() if value is not None]
        if requires_seed_filter is not None or seed_filter:
            names.append("seed_requirements")
        if count_relations_filter is not None:
            names.append("count_relations")
        if complexity_filter:
            names.append("complexity")
        if backend_filter:
            names.append("backend")
        if deprecation_filter:
            names.append("deprecation_state")
        if dtype_filter:
            names.append("supported_dtypes")
        if surface_filter:
            names.append("surfaces")
        return tuple(dict.fromkeys(names))


def capabilities(**kwargs: Any) -> CapabilityCatalog:
    """The declared-capability catalog for the runtime library shipped here."""
    return CapabilityCatalog(**kwargs)
