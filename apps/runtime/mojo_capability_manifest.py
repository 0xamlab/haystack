"""Declared capability blocks for Mojo kernels: the grammar, the parser and the checker.

WHY THIS EXISTS
===============

A Mojo signature cannot express the one relationship that kills the worker. Reading past
the end of a `List` in Mojo is an UNCATCHABLE bounds assertion: it aborts the whole
process, taking every resident dataset and open cursor with it, and a `try`/`except` at
any layer above does not help. So a kernel that takes an explicit element count and
trusts it -- `compute_mean(v: List[Float64], n: Int)` looping `for i in range(n)` -- is a
remote process-abort primitive the moment `n > len(v)`.

Measured on this tree: `library_execute stats.sort_values [[5 floats], 25]` killed the
serving worker (a `pgrep` before and after showed the pid gone). `quantile`, `percentile`
and `median` all funnelled through `sort_values`, so four public contract exports shared
one hole. That one function now clamps. The CLASS did not go away: 628 contract functions
take at least one `List` and at least one `Int`, and NOTHING in the tree says which of
those `Int`s is an element count or which list it bounds. That fact lives only in the
author's head.

It is also structurally invisible to the generated A-Z suite, which calls every contract
function with a FIVE-element list and `5` for every `Int` (`_SCALAR_VALUES` and the `_lf5`
preamble in `tests/generate_mojo_tests.py`), so `n <= len(v)` always holds there. A harness
whose sample count always equals its sample length cannot find this bug, ever.

The declared block below makes the count/list relationship machine-readable. That is the
point; the searchable metadata (determinism, complexity, dtypes, docs) is a by-product.

WHERE THE BLOCK LIVES, AND WHY
==============================

Inside the docstring of the thing it declares:

* a FUNCTION block sits in that function's own docstring, fenced by
  `@capability <function_name>` ... `@endcapability`;
* a MODULE block sits in the module docstring, fenced by `@capability-module` ...
  `@endcapability`, and must appear before the first `fn`/`def`/`struct` in the file. It
  supplies DEFAULTS that function blocks may override.

Three deliberate choices:

1. *In the docstring, not in a `#` comment.* A docstring is part of the declared surface
   of the function -- it survives formatting, it is what a reader of the kernel sees
   first, and it cannot drift into a different file the way a sidecar manifest can. A
   fence found OUTSIDE a docstring is reported as an issue (`block_outside_docstring`)
   rather than ignored, because "I wrote the block and nothing read it" is precisely the
   failure mode this module exists to end.

2. *The fence names its target.* Positional association alone ("the block belongs to the
   nearest preceding signature") silently reattaches when a function is renamed, moved or
   reordered -- and a count relation attached to the wrong function is worse than no
   relation, because a caller stops looking. So the fence carries the function name AND
   the parser cross-checks it against the enclosing signature; a mismatch is
   `block_scope_mismatch`, a hard issue. `apps.runtime.mojo_inventory` then cross-checks
   every parameter named in the block against the parsed signature, so a typo, a renamed
   parameter or a wrong type is an issue too.

3. *A parse failure is a structured issue with a file, a 1-indexed line and a stable
   code -- never a skip.* `mojo_inventory`'s nine-line signature window is the cautionary
   tale: a signature that closes on the tenth line is dropped from the contract with no
   error anywhere, and two registered functions in `optimization/model.mojo` closed on
   EXACTLY the ninth. This parser therefore reports and lets callers decide, and both
   callers fail loudly: the gate (`scripts/capability_manifest_gate.py`) fails on any
   issue in any module, grandfathered or not, and
   `mojo_inventory.build_capability_manifest()` raises rather than hand a guard a manifest
   it would read as "nothing declared here".

COST OVER 522 MODULES
=====================

One substring test (`"@capability" in text`) rejects a file before any regex runs, so a
full-tree scan is ~120 ms warm -- about a fifth of the uncached function/struct parse
(~680 ms) that needed the on-disk cache in `mojo_inventory`. There is deliberately NO new
cache file: the existing runtime-library cache must keep its schema version and payload
byte-for-byte (a bumped key would invalidate every developer's cache and is out of scope
for this change), and a second on-disk cache would be a second source of truth for a
SAFETY field. In-process reuse is `functools.lru_cache` at the call sites.

THE COUNT-RELATION FIELD
========================

One relation per line under `counts:`, count expression on the LEFT, `len(...)` on the
RIGHT, always in that order so that a reviewer reads every relation the same way:

    relation   := "-" ( length_rel | dim_rel ) enforcement
    length_rel := expr op "len(" NAME { "," NAME } ")"
    expr       := ( term | "ceil(" term "/" INT ")" ) [ "+" INT ]
    term       := NAME { "*" NAME }
    op         := "<=" | "=="
    dim_rel    := "dim" NAME [ "<=" ( INT | COMPTIME_NAME ) ]
    enforcement:= "[enforced]" | "[kernel_validated]" | "[clamped]"

That covers the five real shapes in this tree:

    - n <= len(v) [enforced]                     # stats.compute_mean: n bounds len(v)
    - rows * cols == len(dense) [kernel_validated]   # flat row-major matrix; the PRODUCT
                                                 # is the relation
    - rows + 1 == len(indptr) [kernel_validated] # CSR: indptr has rows+1 entries
    - n_acts == len(duration, start) [kernel_validated]  # ONE count, SEVERAL lists
    - dim n_vehicles <= ROUTE_MAX_NODES [kernel_validated]  # an `n` that is a DIMENSION,
                                                 # not the length of any parameter

plus a sixth that a sibling package hit within the hour this landed -- a PACKED buffer, where
the count and the length are not in a 1:1 ratio:

    - ceil(n_values / 2) <= len(packed) [kernel_validated]   # two int4 codes per byte

That one is the reason the grammar has a divisor at all. Without it the author wrote
`n_values <= len(packed) + n_values`, which parses as a relation and is TAUTOLOGICALLY TRUE
-- a declaration that looks like a bound and is not one. Missing expressiveness does not
produce a missing declaration; it produces a false one.

The additive term doubles as the idiom for an INDEX parameter, which is a bound too:
`ins_sort(a, lo, hi)` reads `a[hi]`, so `- hi + 1 <= len(a) [enforced]`.

`dim` exists so that an author who is asked "which list does this `n` bound?" can answer
"none -- it is a dimension the kernel derives or bounds itself" IN THE DECLARATION, rather
than inventing a relation that is not true. Use it ONLY for a count that bounds no list: an
`n` with both a product relation and a ceiling (`optimization.quadratic`'s `n`) declares the
product, because that is the relation tied to the payload. Rule 1c of
`docs/mojo/new-kernel-package-rules.md` applies to the rest: a dimension bounded only by a
ceiling is still not bounded by the payload. The ceiling is checkable here; the payload tie
is not, and the kernel owns it.

A ceiling may NAME a `comptime <NAME>: Int = ...` constant (`1 << 12` is understood) instead
of copying its value, so the declaration cannot drift from the constant the kernel actually
tests. The constant may live in the same file, or in a module this file imports it FROM --
the newer packages keep one ceiling per package in a shared `contract.mojo` (`ATTN_MAX_SEQ`
in `attnk/contract.mojo`, imported by `attnk/mask.mojo` and `attnk/rope.mojo`) rather than
redeclaring it per module the way `sparse_numerics/csr.mojo` does. Resolving same-file names
only would force those modules to copy the literal, which is exactly the drift this check
exists to prevent. Same-file wins on a clash. A name that does not resolve either way is an
issue, not a silently dropped bound.

Two deliberate limits, stated so nobody reads more into a block than it says:

* A `counts:` list is what the author VERIFIED, not a proof that no other shape constraint
  exists. `[enforced]` is the claim with teeth ("nothing in the kernel checks this");
  omitting a relation the kernel validates costs nothing.
* Conditional shapes are not expressible. `optimization.routing.vrp_check` accepts
  `len(ready) == n` OR `len(ready) == 0`, so its window lists are simply not declared --
  under-declaring is honest, and a false relation would be worse than none.

Out of scope for the same reason: list-to-list length agreement
(`len(indices) == len(values)`). It is not a count relation, and the CSR kernels already
report it as a status (`CSR_ERR_LENGTH_MISMATCH`) rather than crashing.

`version_introduced: pre_manifest` is the honest value for a kernel that predates this
mechanism; a new module states a real version.

THE PRODUCT MUST BE CHECKED WITHOUT A WRAPPING MULTIPLY
-------------------------------------------------------

`rows * cols` is a wrapping 64-bit multiply in the kernel: `3 * 6148914691236517206 == 2`,
which is how `csr_from_dense_driver([1.0, 2.0], 3, 6148914691236517206, 1e-15)` walked
straight past a `rows * cols != len(dense)` guard and crashed the process.
`sparse_numerics.csr.dims_fit` fixed it with a DIVISION, and this checker uses the same
shape generalised to n factors: it never forms a product larger than the bound, it grows
it factor by factor and treats "would exceed the bound" as the violation. A count outside
the signed 64-bit range is itself a violation (`count_out_of_int64_range`), because a JSON
integer wider than `Int` wraps on the way in and the checker's verdict would then describe
a different number than the kernel receives.

WHY THE ENFORCEMENT TAG IS MANDATORY
------------------------------------

Some of these relations are already handled inside the kernel, and handled DIFFERENTLY:
`dims_fit` returns an empty/invalid-shape result, and `stats.sort_values` deliberately
CLAMPS (returning empty there would turn a crash into a silent median of 0.0). Rejecting
such a call before it reaches the kernel would replace a documented answer with an error
-- a behaviour change nobody asked for. So each relation states who enforces it:

* `[enforced]`          -- nothing in the kernel checks it; the pre-call guard MUST reject.
* `[kernel_validated]`  -- the kernel checks it and returns a status/sentinel; the guard
                           must NOT pre-empt that.
* `[clamped]`           -- the kernel clamps the count into range on purpose.

The tag has no default. An omitted tag is a parse issue that names the three choices,
because the whole phase exists to make "someone must decide" the failure mode instead of
"it silently ships undeclared". Choosing the tag requires reading the kernel, which is the
work that cannot be automated -- and it is a one-line, verifiable claim once made.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

MODULE_FENCE = "@capability-module"
FUNCTION_FENCE_PREFIX = "@capability"
END_FENCE = "@endcapability"

#: One substring test that rejects a file before any regex runs.
FENCE_SENTINEL = "@capability"

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

ENFORCEMENT_ENFORCED = "enforced"
ENFORCEMENT_KERNEL_VALIDATED = "kernel_validated"
ENFORCEMENT_CLAMPED = "clamped"
ENFORCEMENTS = (ENFORCEMENT_ENFORCED, ENFORCEMENT_KERNEL_VALIDATED, ENFORCEMENT_CLAMPED)

SEED_REQUIREMENTS = ("none", "optional", "required")
DEPRECATION_STATES = ("active", "soft_deprecated", "deprecated", "scheduled_removal")
#: What actually executes. ``metal`` is not a synonym for ``mojo``: a Metal module's code is a
#: compiled SHADER produced at build time by an external shader compiler, so it has a different build
#: prerequisite, a different failure mode (``Metal Compiler failed to compile metallib`` at COMPILE
#: time, on a host that has no compiler) and a different runtime owner. Declaring `accel/launch.mojo`
#: as ``mojo`` would have made this field say the one thing about that module that is not true.
#: ``cuda`` joined when kernels existed for it — ``residentk/kernels_prefill_f32.mojo`` and
#: ``residentk/session_cuda.mojo``, run-verified on a real Tesla T4 (the Phase-0/Phase-2 CUDA-native
#: session evidence) — per this enum's own rule that a value with no implementation behind it is a
#: claim. ``rocm`` stays out until kernels exist for it.
BACKENDS = ("mojo", "mojo_simd", "python_fallback", "metal", "cuda")
SURFACES = (
    "library_execute",
    "batch_execute",
    "pipeline_execute",
    "query_execute",
    "session",
    "internal",
)

_BOOL_FIELDS = ("deterministic", "stateful", "batch_capable", "stream_capable")
_ENUM_FIELDS = {
    "seed_requirements": SEED_REQUIREMENTS,
    "deprecation_state": DEPRECATION_STATES,
    "backend": BACKENDS,
}
_TOKEN_LIST_FIELDS = ("supported_dtypes", "surfaces")
_TEXT_FIELDS = ("complexity", "golden_vectors", "benchmark", "docs", "version_introduced")
_KNOWN_FIELDS = frozenset(
    (*_BOOL_FIELDS, *_ENUM_FIELDS, *_TOKEN_LIST_FIELDS, *_TEXT_FIELDS, "counts")
)
#: Fields a MODULE block may not carry. `counts` is per-function on purpose: a defaulted
#: count relation is a guessed count relation, which is the failure this module prevents.
_MODULE_FORBIDDEN_FIELDS = frozenset({"counts"})

_FUNCTION_FENCE_RE = re.compile(r"^@capability\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
_DEFINITION_RE = re.compile(r"^\s*(?:fn|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[(\[]")
_STRUCT_RE = re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)")
_FIELD_RE = re.compile(r"^([a-z_][a-z0-9_]*)\s*:(.*)$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+/\-]*$")
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LENGTH_REL_RE = re.compile(r"^(?P<expr>[^<=]+?)\s*(?P<op><=|==)\s*len\(\s*(?P<lists>[^)]*)\)$")
_DIM_REL_RE = re.compile(
    r"^dim\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*<=\s*(?P<ceiling>-?\d+|[A-Za-z_][A-Za-z0-9_]*))?$"
)
#: `comptime NAME: Int = 4096` / `= 1 << 12`, so a declared ceiling can name the constant
#: the kernel actually tests against instead of copying its value and rotting.
_COMPTIME_INT_RE = re.compile(
    r"^\s*comptime\s+([A-Z_][A-Z0-9_]*)\s*:\s*Int\s*=\s*(\d+)(?:\s*<<\s*(\d+))?\s*$",
    re.MULTILINE,
)
#: `from <module> import (A, B)` — both the single-line and parenthesized spellings. Used only to
#: follow a ceiling constant back to the package `contract.mojo` that declares it.
_FROM_IMPORT_RE = re.compile(
    r"^[ \t]*from[ \t]+([A-Za-z_][A-Za-z0-9_.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n]*)",
    re.MULTILINE,
)
_ENFORCEMENT_RE = re.compile(r"^(?P<body>.*?)\s*\[(?P<tag>[a-z_]+)\]$")


@dataclass(frozen=True)
class CapabilityIssue:
    """A parse or cross-validation failure, addressed so a human can fix it."""

    path: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.message}"


@dataclass(frozen=True)
class RuntimeCountRelation:
    """One declared relation between caller-supplied counts and caller-supplied lists."""

    raw: str
    line: int
    kind: str  # "length" | "dimension"
    enforcement: str
    counts: tuple[str, ...] = ()
    #: The left side is a SUM of products: `Σ summands + addend`. `counts` stays the FLAT,
    #: ordered list of every name involved so name resolution and the violation detail keep
    #: working unchanged; `summands` groups them back into the products being summed. A single
    #: product -- every declaration in the tree before `inference.resample` -- is one group,
    #: and `_relation_holds` keeps its original path for that case.
    summands: tuple[tuple[str, ...], ...] = ()
    addend: int = 0
    #: `ceil(product / divisor)` elements are required, for a PACKED buffer (two int4 codes
    #: per byte is `divisor = 2`). 1 means unpacked.
    divisor: int = 1
    comparison: str = "=="
    bounded_lists: tuple[str, ...] = ()
    ceiling: int | None = None

    @property
    def is_enforced(self) -> bool:
        return self.enforcement == ENFORCEMENT_ENFORCED


@dataclass(frozen=True)
class RuntimeCapabilitySpec:
    """A declared capability block. `None` means "not declared", never "false"/"empty"."""

    target: str
    is_module: bool
    line: int
    deterministic: bool | None = None
    stateful: bool | None = None
    batch_capable: bool | None = None
    stream_capable: bool | None = None
    seed_requirements: str | None = None
    backend: str | None = None
    deprecation_state: str | None = None
    supported_dtypes: tuple[str, ...] | None = None
    surfaces: tuple[str, ...] | None = None
    complexity: str | None = None
    golden_vectors: str | None = None
    benchmark: str | None = None
    docs: str | None = None
    version_introduced: str | None = None
    #: `None` = the author never said; `()` = the author said "no count parameters".
    count_relations: tuple[RuntimeCountRelation, ...] | None = None

    @property
    def declares_counts(self) -> bool:
        return self.count_relations is not None

    @property
    def enforced_relations(self) -> tuple[RuntimeCountRelation, ...]:
        return tuple(rel for rel in self.count_relations or () if rel.is_enforced)

    def inherit(self, module_spec: RuntimeCapabilitySpec | None) -> RuntimeCapabilitySpec:
        """This block's own values, falling back to the module block's for unset fields."""
        if module_spec is None:
            return self
        updates: dict[str, Any] = {}
        for field_name in (
            *_BOOL_FIELDS,
            *_ENUM_FIELDS,
            *_TOKEN_LIST_FIELDS,
            *_TEXT_FIELDS,
        ):
            if getattr(self, field_name) is None:
                inherited = getattr(module_spec, field_name)
                if inherited is not None:
                    updates[field_name] = inherited
        return replace(self, **updates) if updates else self


#: What an ABSENT declaration means to a consumer (the SDK's `capabilities()` surface, a
#: docs generator, a scheduler deciding whether it may cache a result). A claim not made is
#: not granted, so an unseeded kernel reads as `deterministic: false` -- which DECLARES
#: today's uncertainty rather than changing what the kernel does. `None` where the honest
#: answer is "not stated" and there is no conservative reading.
UNDECLARED_CLAIMS: dict[str, Any] = {
    "deterministic": False,
    "stateful": False,
    "batch_capable": False,
    "stream_capable": False,
    "seed_requirements": None,
    "backend": None,
    "deprecation_state": None,
    "supported_dtypes": None,
    "surfaces": None,
    "complexity": None,
    "golden_vectors": None,
    "benchmark": None,
    "docs": None,
    "version_introduced": None,
}


def resolved_claims(spec: RuntimeCapabilitySpec | None) -> dict[str, Any]:
    """Declared values over `UNDECLARED_CLAIMS`, so a consumer never reads `None` as `True`."""
    resolved = dict(UNDECLARED_CLAIMS)
    if spec is None:
        return resolved
    for field_name in resolved:
        value = getattr(spec, field_name, None)
        if value is not None:
            resolved[field_name] = value
    return resolved


@dataclass(frozen=True)
class CapabilityParse:
    """Everything one `.mojo` file declared, plus everything wrong with it."""

    path: str
    module: RuntimeCapabilitySpec | None
    functions: tuple[RuntimeCapabilitySpec, ...]
    issues: tuple[CapabilityIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def by_name(self) -> dict[str, RuntimeCapabilitySpec]:
        return {spec.target: spec for spec in self.functions}


def _issue(path: str, line: int, code: str, message: str) -> CapabilityIssue:
    return CapabilityIssue(path=path, line=line, code=code, message=message)


def _parse_bool(raw: str) -> bool | None:
    if raw == "true":
        return True
    if raw == "false":
        return False
    return None


def _parse_token_list(raw: str) -> tuple[str, ...] | None:
    if raw == "none":
        return ()
    tokens = [token.strip() for token in raw.split(",")]
    if any(not token or not _TOKEN_RE.match(token) for token in tokens):
        return None
    return tuple(tokens)


def _comptime_int_constants(text: str) -> dict[str, int]:
    constants: dict[str, int] = {}
    for name, base, shift in _COMPTIME_INT_RE.findall(text):
        constants[name] = int(base) << int(shift) if shift else int(base)
    return constants


@lru_cache(maxsize=None)
def _module_comptime_int_constants(resolved: Path) -> tuple[tuple[str, int], ...]:
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple(_comptime_int_constants(text).items())


def _imported_comptime_int_constants(text: str, path: str) -> dict[str, int]:
    """Ceiling constants reachable through this file's own imports.

    A ceiling should name the constant the kernel tests against — but the newer packages keep that
    constant in one `contract.mojo` per package (`ATTN_MAX_SEQ` in `attnk/contract.mojo`, used by
    `attnk/mask.mojo` and `attnk/rope.mojo`), rather than redeclaring it in every module the way
    `sparse_numerics/csr.mojo` does. Resolving only same-file constants would force those files to
    copy the literal, which is precisely the drift this check exists to prevent: two spellings of a
    ceiling, one of them silently stale.

    So an imported name resolves to the value in the module it is imported FROM. Same-file constants
    still win, an unresolvable import is simply absent (the caller reports it unresolved as before),
    and nothing outside the kernel tree is read.
    """
    source = Path(path)
    if not source.is_file():
        return {}

    constants: dict[str, int] = {}
    for module_path, names_blob in _FROM_IMPORT_RE.findall(text):
        imported = {
            name for name in re.findall(r"[A-Z_][A-Z0-9_]*", names_blob)
        }
        if not imported:
            continue
        parts = module_path.split(".")
        for root in list(source.parents)[:4]:
            candidate = root.joinpath(*parts).with_suffix(".mojo")
            if not candidate.is_file():
                continue
            for name, value in _module_comptime_int_constants(candidate.resolve()):
                if name in imported:
                    constants[name] = value
            break
    return constants


def _parse_count_relation(
    raw: str,
    *,
    path: str,
    line: int,
    issues: list[CapabilityIssue],
    constants: dict[str, int] | None = None,
) -> RuntimeCountRelation | None:
    body_match = _ENFORCEMENT_RE.match(raw)
    if body_match is None:
        issues.append(
            _issue(
                path,
                line,
                "count_relation_missing_enforcement",
                (
                    f"relation {raw!r} must end with an enforcement tag: "
                    "[enforced] when nothing in the kernel checks it, [kernel_validated] "
                    "when the kernel checks it and returns a status, or [clamped] when the "
                    "kernel clamps the count on purpose. There is no default -- pick one by "
                    "reading the kernel."
                ),
            )
        )
        return None
    tag = body_match.group("tag")
    if tag not in ENFORCEMENTS:
        issues.append(
            _issue(
                path,
                line,
                "count_relation_unknown_enforcement",
                f"unknown enforcement tag [{tag}]; expected one of {', '.join(ENFORCEMENTS)}",
            )
        )
        return None
    body = body_match.group("body").strip()

    dim_match = _DIM_REL_RE.match(body)
    if dim_match is not None:
        ceiling_raw = dim_match.group("ceiling")
        ceiling: int | None = None
        if ceiling_raw is not None:
            if re.match(r"^-?\d+$", ceiling_raw):
                ceiling = int(ceiling_raw)
            else:
                resolved = (constants or {}).get(ceiling_raw)
                if resolved is None:
                    issues.append(
                        _issue(
                            path,
                            line,
                            "dimension_ceiling_unresolved",
                            (
                                f"{raw!r}: {ceiling_raw!r} is not a `comptime <NAME>: Int = ...` "
                                "constant in this file. Name a same-file constant so the ceiling "
                                "cannot drift from the one the kernel tests, or write the literal."
                            ),
                        )
                    )
                    return None
                ceiling = resolved
        if ceiling is not None and ceiling < 0:
            issues.append(
                _issue(
                    path, line, "count_relation_negative_ceiling", f"{raw!r} has a negative ceiling"
                )
            )
            return None
        return RuntimeCountRelation(
            raw=raw,
            line=line,
            kind="dimension",
            enforcement=tag,
            counts=(dim_match.group("name"),),
            comparison="<=",
            ceiling=ceiling,
        )

    length_match = _LENGTH_REL_RE.match(body)
    if length_match is None:
        issues.append(
            _issue(
                path,
                line,
                "count_relation_unparsable",
                (
                    f"relation {raw!r} does not match the grammar: "
                    "`<count>[ * <count>...][ + <int>] (<=|==) len(<list>[, <list>...])` "
                    "or `dim <count>[ <= <int>]`, then an enforcement tag"
                ),
            )
        )
        return None

    expr = length_match.group("expr").strip()
    addend = 0
    divisor = 1
    # The left side is a sum of terms, each either a non-negative integer literal or a product
    # of parameter names. Two NAMED terms are what `inference.resample.permutation_test_flat`
    # needs: `n1 + n2 == len(values)`, the two group sizes together accounting for the whole
    # list. Declaring `n1 <= len(values)` and `n2 <= len(values)` instead would be a strictly
    # WEAKER pair of bounds than the kernel enforces -- both hold for `n1 = n2 = len(values)`,
    # which the kernel rejects -- and shipping a weaker relation as `[enforced]` is the
    # false-assurance failure this gate exists to prevent.
    named_terms: list[str] = []
    for term in (piece.strip() for piece in expr.split("+")):
        if re.match(r"^\d+$", term):
            addend += int(term)
            continue
        if not term:
            issues.append(
                _issue(
                    path,
                    line,
                    "count_relation_bad_addend",
                    f"{raw!r}: an additive term is empty",
                )
            )
            return None
        named_terms.append(term)
    if not named_terms:
        issues.append(
            _issue(
                path,
                line,
                "count_relation_bad_addend",
                f"{raw!r}: the left side must name at least one count parameter",
            )
        )
        return None
    if len(named_terms) > 1 and any("ceil(" in term for term in named_terms):
        issues.append(
            _issue(
                path,
                line,
                "count_relation_unparsable",
                (
                    f"{raw!r}: a packed `ceil(<count> / <int>)` term cannot be summed with "
                    "another count; the packing divisor would be ambiguous"
                ),
            )
        )
        return None
    expr = named_terms[0]
    ceil_match = re.match(r"^ceil\(\s*(?P<inner>[^/)]+?)\s*/\s*(?P<divisor>\d+)\s*\)$", expr)
    if ceil_match is not None:
        divisor = int(ceil_match.group("divisor"))
        if divisor < 1:
            issues.append(
                _issue(
                    path,
                    line,
                    "count_relation_bad_divisor",
                    f"{raw!r}: a packing divisor must be a positive integer literal",
                )
            )
            return None
        expr = ceil_match.group("inner").strip()
    elif "ceil(" in expr or "/" in expr:
        issues.append(
            _issue(
                path,
                line,
                "count_relation_unparsable",
                (
                    f"{raw!r}: a packed buffer is written `ceil(<count> / <int>) <= len(buf)`; "
                    "no other division is understood"
                ),
            )
        )
        return None
    # `expr` is the first term with any `ceil(...)` wrapper removed; the rest are plain products.
    summands: list[tuple[str, ...]] = []
    for term in [expr, *named_terms[1:]]:
        factors = [factor.strip() for factor in term.split("*")]
        if not factors or any(not _NAME_RE.match(factor) for factor in factors):
            issues.append(
                _issue(
                    path,
                    line,
                    "count_relation_bad_factor",
                    f"{raw!r}: every factor left of the comparison must be a parameter name",
                )
            )
            return None
        summands.append(tuple(factors))
    factors = [name for group in summands for name in group]
    bounded = [name.strip() for name in length_match.group("lists").split(",")]
    if not bounded or any(not _NAME_RE.match(name) for name in bounded):
        issues.append(
            _issue(
                path,
                line,
                "count_relation_bad_bounded_list",
                f"{raw!r}: len(...) must name one or more list parameters",
            )
        )
        return None
    return RuntimeCountRelation(
        raw=raw,
        line=line,
        kind="length",
        enforcement=tag,
        counts=tuple(factors),
        summands=tuple(summands),
        addend=addend,
        divisor=divisor,
        comparison=length_match.group("op"),
        bounded_lists=tuple(bounded),
    )


class _BlockBuilder:
    """Accumulates one block's fields, reporting duplicates and unknown keys."""

    def __init__(
        self,
        *,
        target: str,
        is_module: bool,
        line: int,
        path: str,
        constants: dict[str, int] | None = None,
    ) -> None:
        self.constants = constants or {}
        self.target = target
        self.is_module = is_module
        self.line = line
        self.path = path
        self.values: dict[str, Any] = {}
        self.seen: set[str] = set()
        self.counts: list[RuntimeCountRelation] | None = None
        self.counts_declared_none = False
        self.counts_line = 0
        self.counts_relation_lines = 0
        self.in_counts = False

    def _duplicate(self, key: str, line: int, issues: list[CapabilityIssue]) -> bool:
        if key in self.seen:
            issues.append(
                _issue(
                    self.path, line, "duplicate_field", f"field {key!r} declared twice in one block"
                )
            )
            return True
        self.seen.add(key)
        return False

    def field(self, key: str, raw: str, line: int, issues: list[CapabilityIssue]) -> None:
        # Any field line ends a `counts:` section, so a stray `- ...` line after one is
        # reported (`relation_outside_counts`) instead of silently joining the wrong field.
        self.in_counts = False
        if key not in _KNOWN_FIELDS:
            issues.append(
                _issue(
                    self.path,
                    line,
                    "unknown_field",
                    f"unknown capability field {key!r}; known fields: "
                    + ", ".join(sorted(_KNOWN_FIELDS)),
                )
            )
            return
        if self.is_module and key in _MODULE_FORBIDDEN_FIELDS:
            issues.append(
                _issue(
                    self.path,
                    line,
                    "field_not_allowed_at_module_scope",
                    (
                        f"field {key!r} may not be declared in a module block: a defaulted count "
                        "relation is a guessed count relation. Declare it on each function."
                    ),
                )
            )
            return
        if self._duplicate(key, line, issues):
            return
        value = raw.strip()
        if key == "counts":
            self.counts_line = line
            if value == "none":
                self.counts = []
                self.counts_declared_none = True
                return
            if value:
                issues.append(
                    _issue(
                        self.path,
                        line,
                        "counts_inline_value",
                        (
                            "`counts:` takes one `- <relation>` line per relation, or the literal "
                            "`counts: none` to state that no parameter is an element count"
                        ),
                    )
                )
                return
            self.counts = []
            self.in_counts = True
            return
        if key in _BOOL_FIELDS:
            parsed = _parse_bool(value)
            if parsed is None:
                issues.append(
                    _issue(
                        self.path,
                        line,
                        "bad_bool",
                        f"field {key!r} must be `true` or `false`, got {value!r}",
                    )
                )
                return
            self.values[key] = parsed
            return
        if key in _ENUM_FIELDS:
            allowed = _ENUM_FIELDS[key]
            if value not in allowed:
                issues.append(
                    _issue(
                        self.path,
                        line,
                        "bad_enum",
                        f"field {key!r} must be one of {', '.join(allowed)}, got {value!r}",
                    )
                )
                return
            self.values[key] = value
            return
        if key in _TOKEN_LIST_FIELDS:
            tokens = _parse_token_list(value)
            if tokens is None:
                issues.append(
                    _issue(
                        self.path,
                        line,
                        "bad_token_list",
                        f"field {key!r} must be a comma-separated token list "
                        f"or `none`, got {value!r}",
                    )
                )
                return
            if key == "surfaces":
                unknown = [token for token in tokens if token not in SURFACES]
                if unknown:
                    issues.append(
                        _issue(
                            self.path,
                            line,
                            "bad_surface",
                            f"unknown surface(s) {', '.join(unknown)}; expected from "
                            + ", ".join(SURFACES),
                        )
                    )
                    return
            self.values[key] = tokens
            return
        if not value:
            issues.append(_issue(self.path, line, "empty_field", f"field {key!r} has no value"))
            return
        self.values[key] = value

    def relation(self, raw: str, line: int, issues: list[CapabilityIssue]) -> None:
        if not self.in_counts or self.counts is None:
            issues.append(
                _issue(
                    self.path,
                    line,
                    "relation_outside_counts",
                    f"relation line {raw!r} must follow a `counts:` field",
                )
            )
            return
        self.counts_relation_lines += 1
        parsed = _parse_count_relation(
            raw, path=self.path, line=line, issues=issues, constants=self.constants
        )
        if parsed is not None:
            self.counts.append(parsed)

    def build(self, *, end_line: int, issues: list[CapabilityIssue]) -> RuntimeCapabilitySpec:
        if (
            self.counts is not None
            and not self.counts_relation_lines
            and not self.counts_declared_none
        ):
            issues.append(
                _issue(
                    self.path,
                    self.counts_line or end_line,
                    "counts_block_empty",
                    (
                        "`counts:` was opened with no relation lines. Write `counts: none` "
                        "to state "
                        "that no parameter is an element count."
                    ),
                )
            )
        return RuntimeCapabilitySpec(
            target=self.target,
            is_module=self.is_module,
            line=self.line,
            count_relations=tuple(self.counts) if self.counts is not None else None,
            **self.values,
        )


def parse_capability_blocks(text: str, *, path: str = "<text>") -> CapabilityParse:
    """Extract every declared block from one `.mojo` source, plus every issue found.

    Never raises and never silently drops a block: anything it cannot understand comes
    back as a `CapabilityIssue` with a 1-indexed line, and both callers (the gate and
    `mojo_inventory.build_capability_manifest`) fail on a non-empty issue list.
    """
    issues: list[CapabilityIssue] = []
    if FENCE_SENTINEL not in text:
        return CapabilityParse(path=path, module=None, functions=(), issues=())

    # Imported first, same-file second: a module that declares its own ceiling always wins.
    constants = _imported_comptime_int_constants(text, path)
    constants.update(_comptime_int_constants(text))
    module_spec: RuntimeCapabilitySpec | None = None
    function_specs: list[RuntimeCapabilitySpec] = []
    builder: _BlockBuilder | None = None
    docstring_delimiter: str | None = None
    enclosing_function: str | None = None
    seen_definition = False

    for index, raw_line in enumerate(text.splitlines()):
        line_number = index + 1
        stripped = raw_line.strip()
        inside_docstring = docstring_delimiter is not None

        if not inside_docstring:
            if _DEFINITION_RE.match(raw_line):
                enclosing_function = _DEFINITION_RE.match(raw_line).group(1)  # type: ignore[union-attr]
                seen_definition = True
            elif _STRUCT_RE.match(raw_line):
                enclosing_function = None
                seen_definition = True
            if stripped.startswith('"""') or stripped.startswith("'''"):
                delimiter = '"""' if stripped.startswith('"""') else "'''"
                if stripped.count(delimiter) % 2 == 1:
                    docstring_delimiter = delimiter
                # A one-line docstring cannot hold a fenced block; nothing else to do.
                if FENCE_SENTINEL in stripped and stripped.count(delimiter) % 2 == 0:
                    issues.append(
                        _issue(
                            path,
                            line_number,
                            "block_in_single_line_docstring",
                            "a capability block needs a multi-line docstring",
                        )
                    )
                continue
            if FENCE_SENTINEL in stripped or stripped == END_FENCE:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "block_outside_docstring",
                        (
                            f"{stripped!r} is not inside a docstring, so nothing would read it. "
                            "Capability blocks live in the docstring of the module or function "
                            "they declare."
                        ),
                    )
                )
            continue

        # Inside a docstring from here down.
        closes_docstring = (
            docstring_delimiter in stripped and stripped.count(docstring_delimiter) % 2 == 1
        )

        if builder is not None and not closes_docstring:
            if stripped == END_FENCE:
                spec = builder.build(end_line=line_number, issues=issues)
                if spec.is_module:
                    module_spec = spec
                else:
                    function_specs.append(spec)
                builder = None
                continue
            if not stripped:
                continue
            if stripped.startswith("-"):
                builder.relation(stripped[1:].strip(), line_number, issues)
                continue
            field_match = _FIELD_RE.match(stripped)
            if field_match is None:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "unparsable_line",
                        f"{stripped!r} is neither `key: value` nor `- <relation>` nor {END_FENCE}",
                    )
                )
                continue
            builder.field(field_match.group(1), field_match.group(2), line_number, issues)
            continue

        if closes_docstring:
            if builder is not None:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "unterminated_block",
                        (
                            f"capability block for {builder.target or 'the module'!r} opened "
                            f"on line "
                            f"{builder.line} is not closed by {END_FENCE} before the docstring ends"
                        ),
                    )
                )
                builder = None
            docstring_delimiter = None
            continue

        if stripped == MODULE_FENCE:
            if seen_definition:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "module_block_not_at_module_scope",
                        f"{MODULE_FENCE} must appear in the module docstring, before the "
                        "first definition",
                    )
                )
                continue
            if module_spec is not None:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "duplicate_module_block",
                        "a second module block was declared",
                    )
                )
                continue
            builder = _BlockBuilder(
                target="", is_module=True, line=line_number, path=path, constants=constants
            )
            continue

        if stripped.startswith(FUNCTION_FENCE_PREFIX):
            fence_match = _FUNCTION_FENCE_RE.match(stripped)
            if fence_match is None:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "malformed_fence",
                        (
                            f"{stripped!r} is not a valid fence; use `{FUNCTION_FENCE_PREFIX} "
                            f"<function_name>` or `{MODULE_FENCE}`"
                        ),
                    )
                )
                continue
            target = fence_match.group(1)
            if enclosing_function != target:
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "block_scope_mismatch",
                        (
                            f"block declares {target!r} but sits in the docstring of "
                            f"{enclosing_function or 'the module'!r}; a relation attached to "
                            "the wrong "
                            "function is worse than no relation"
                        ),
                    )
                )
                continue
            if any(spec.target == target for spec in function_specs):
                issues.append(
                    _issue(
                        path,
                        line_number,
                        "duplicate_function_block",
                        f"a second capability block was declared for {target!r}",
                    )
                )
                continue
            builder = _BlockBuilder(
                target=target, is_module=False, line=line_number, path=path, constants=constants
            )
            continue

        if stripped == END_FENCE:
            issues.append(
                _issue(
                    path,
                    line_number,
                    "end_without_start",
                    f"{END_FENCE} with no open capability block",
                )
            )

    if builder is not None:
        issues.append(
            _issue(
                path,
                len(text.splitlines()),
                "unterminated_block",
                f"capability block opened on line {builder.line} is never closed by {END_FENCE}",
            )
        )

    return CapabilityParse(
        path=path,
        module=module_spec,
        functions=tuple(function_specs),
        issues=tuple(issues),
    )


# ── the checker: declared relations vs a concrete argument list ────────────────


@dataclass(frozen=True)
class CountViolation:
    """A declared, enforced relation that the supplied arguments break."""

    code: str
    relation: str
    message: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class SkippedRelation:
    """A relation that was NOT evaluated, and why. Never silent."""

    relation: str
    reason: str


@dataclass(frozen=True)
class CountCheckResult:
    violations: tuple[CountViolation, ...] = ()
    skipped: tuple[SkippedRelation, ...] = ()
    evaluated: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations


def _int_value(value: Any) -> int | None:
    # `bool` is an `int` in Python but not an `Int` over the wire; leave it to the
    # existing type normalisation, which reports it more precisely than this checker can.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _product_fits(factors: Sequence[int], limit: int) -> tuple[bool, bool]:
    """(fits, exact) for `Π factors` against `limit`, formed WITHOUT a wrapping multiply.

    Grows the product factor by factor and stops the moment it would pass `limit`, the way
    `sparse_numerics.csr.dims_fit` does with a division. Returns `fits=False` for an
    overflow past the limit, which is the only fact a bound needs.
    """
    product = 1
    for factor in factors:
        if factor == 0:
            product = 0
            break
        if product > limit // factor:
            return False, False
        product *= factor
    return product <= limit, product == limit


def _relation_holds(
    relation: RuntimeCountRelation,
    count_values: Sequence[int],
    length: int,
) -> bool:
    """Whether `ceil(Π counts / divisor) + addend  <=|==  length`, without a wrapping multiply.

    Every comparison is turned into one against a bound derived from `length`, which is a
    real list length and therefore small: `ceil(P / d) <= limit` is exactly `P <= limit * d`,
    and `_product_fits` then grows `P` by division and stops the moment it passes that bound.
    """
    limit = length - relation.addend
    if any(value < 0 for value in count_values):
        # A negative count makes `for i in range(n)` empty, so it cannot over-read; `<=` is
        # satisfied. Under `==` the shape is still wrong, because no length is negative.
        # Checked over EVERY value before any arithmetic, so the verdict cannot depend on the
        # order the factors happen to be declared in.
        return relation.comparison == "<="
    if limit < 0:
        return False
    if len(relation.summands) > 1:
        # `Σ products + addend  <=|==  length`. Every value is non-negative here and each
        # product is proven to fit in the REMAINING budget before it is formed, so the running
        # total is bounded by a real list length and cannot wrap.
        total = 0
        offset = 0
        for group in relation.summands:
            group_values = list(count_values[offset : offset + len(group)])
            offset += len(group)
            fits, _ = _product_fits(group_values, limit - total)
            if not fits:
                return False
            product = 1
            for value in group_values:
                product *= value
            total += product
        return total <= limit if relation.comparison == "<=" else total == limit
    scaled = limit * relation.divisor
    fits, exact = _product_fits(count_values, scaled)
    if relation.comparison == "<=":
        return fits
    if relation.divisor == 1:
        return exact
    if limit == 0:
        return exact
    # `ceil(P / d) == limit`  <=>  `(limit - 1) * d < P <= limit * d`.
    below, _ = _product_fits(count_values, (limit - 1) * relation.divisor)
    return fits and not below


def check_count_relations(
    *,
    params: Sequence[Any],
    capability: RuntimeCapabilitySpec | None,
    args: Sequence[Any],
) -> CountCheckResult:
    """Check every ENFORCED declared relation against a concrete positional argument list.

    `params` is the function's parsed parameter sequence (anything with `.name`, `.typ`
    and `.has_default` -- i.e. `RuntimeFunctionSpec.params`); `args` is the caller's
    positional arguments, already aligned to it.

    Contract, in the two directions that matter:

    * A function with NO declared relation yields an empty result, so behaviour is exactly
      as it is today. This never guesses a relation.
    * The absence of a relation for ONE parameter never disables the others: relations are
      evaluated independently, and anything not evaluated is reported in `skipped` with a
      reason rather than dropped.
    """
    if capability is None or not capability.count_relations:
        return CountCheckResult()

    by_name = {param.name: param for param in params}
    values: dict[str, Any] = {}
    for param, value in zip(params, args, strict=False):
        values[param.name] = value

    violations: list[CountViolation] = []
    skipped: list[SkippedRelation] = []
    evaluated = 0

    for relation in capability.count_relations:
        if not relation.is_enforced:
            skipped.append(SkippedRelation(relation.raw, f"enforcement_{relation.enforcement}"))
            continue

        missing = [
            name for name in (*relation.counts, *relation.bounded_lists) if name not in values
        ]
        if missing:
            unexpected = [name for name in missing if name not in by_name]
            if unexpected:
                # The declaration names a parameter the function does not have. That is a
                # manifest defect, surfaced by the inventory cross-check; refuse to guess.
                skipped.append(SkippedRelation(relation.raw, "relation_names_unknown_parameter"))
            else:
                skipped.append(SkippedRelation(relation.raw, "argument_not_provided"))
            continue

        count_values: list[int] = []
        out_of_range = False
        non_integer = False
        for name in relation.counts:
            parsed = _int_value(values[name])
            if parsed is None:
                non_integer = True
                break
            if parsed < INT64_MIN or parsed > INT64_MAX:
                violations.append(
                    CountViolation(
                        code="count_out_of_int64_range",
                        relation=relation.raw,
                        message=(
                            f"count '{name}' is {values[name]}, outside the signed 64-bit "
                            "range the "
                            "kernel receives, so it would wrap on the way in"
                        ),
                        detail={"parameter": name, "value": values[name]},
                    )
                )
                out_of_range = True
                break
            count_values.append(parsed)
        if non_integer:
            skipped.append(SkippedRelation(relation.raw, "count_not_an_integer"))
            continue
        if out_of_range:
            evaluated += 1
            continue

        if relation.kind == "dimension":
            evaluated += 1
            if relation.ceiling is not None and count_values[0] > relation.ceiling:
                violations.append(
                    CountViolation(
                        code="dimension_exceeds_ceiling",
                        relation=relation.raw,
                        message=(
                            f"dimension '{relation.counts[0]}' is {count_values[0]}, above "
                            f"the declared "
                            f"ceiling {relation.ceiling}"
                        ),
                        detail={
                            "parameter": relation.counts[0],
                            "value": count_values[0],
                            "ceiling": relation.ceiling,
                        },
                    )
                )
            continue

        skipped_this = False
        for list_name in relation.bounded_lists:
            bounded_value = values[list_name]
            if not isinstance(bounded_value, (list, tuple)):
                skipped.append(SkippedRelation(relation.raw, "bounded_argument_not_a_list"))
                skipped_this = True
                break
            length = len(bounded_value)
            if _relation_holds(relation, count_values, length):
                continue
            violations.append(
                CountViolation(
                    code="count_exceeds_list_length"
                    if relation.comparison == "<="
                    else "count_shape_mismatch",
                    relation=relation.raw,
                    message=(
                        f"{relation.raw.split('[')[0].strip()} is false: "
                        f"len({list_name}) is {length}"
                    ),
                    detail={
                        "counts": dict(zip(relation.counts, count_values, strict=True)),
                        "list": list_name,
                        "length": length,
                    },
                )
            )
        if not skipped_this:
            evaluated += 1

    return CountCheckResult(
        violations=tuple(violations),
        skipped=tuple(skipped),
        evaluated=evaluated,
    )
