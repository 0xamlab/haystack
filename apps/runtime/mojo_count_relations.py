"""Declared relations between a caller-supplied element COUNT and the List it bounds.

WHY THIS EXISTS. A signature cannot say that an `Int` parameter is the number of elements
the kernel will read out of a `List` parameter. That relation lives only in the author's
head, and getting it wrong is not a wrong answer — it is an UNCATCHABLE bounds assertion
that aborts the whole worker process, taking every resident dataset and open cursor with
it. `try`/`except` at any layer above does not help; see
`docs/mojo/new-kernel-package-rules.md` rule 1 and
`tests/integration/test_kernel_count_arg_robustness.py`.

MEASURED on `origin/main`: `library_execute stats.sort_values [[5 floats], 25]` ended the
serving pid. Four public contract exports funnelled through that one hole. Nothing found
them, because the generated A-Z suite calls every contract function with a five-element
list and `5` for every `Int` (`_SCALAR_VALUES` / the `_lf5` preamble in
`tests/generate_mojo_tests.py`), so `n <= len(v)` always held. The hazard is structurally
invisible to a harness whose sample count always equals its sample length.

Once the relation is written down, a caller-supplied count that exceeds its list can be
refused BEFORE the frame reaches the kernel — a typed error instead of a dead process, and
in a batch, one refused item instead of every item's resident data.

WHAT MAY BE DECLARED HERE, AND WHAT MAY NOT

A relation is a statement about a specific frozen kernel, verified by reading that kernel.
Never inferred from a parameter name: `n` is a length in `stats.compute_mean(v, n)` and a
DIMENSION in `clustering_metrics.cluster_sizes(labels, k)`, where `k` sizes a list the
kernel allocates itself and bounds nothing the caller supplied. A wrong relation rejects
valid calls, which is worse than the absence of one, so:

* Declare only what the kernel actually requires. `correlation.cholesky_lower(corr, n)`
  reads `corr[i][j]` for `j <= i`, so `n <= len(corr)` is required but
  `n <= len(corr[i])` for every `i` is NOT — a lower-triangular ragged `corr` is legal, and
  declaring the inner bound would refuse it. The outer bound alone is declared.
* Do not declare a relation for a kernel that CLAMPS. `stats.median` deliberately clamps a
  large `n` to the available values and answers the question asked; refusing it would
  convert a working call into an error. The four functions from the incident above are
  therefore absent from this table on purpose.
* A kernel that already REJECTS an over-large count with a status of its own
  (`optimization.*` validates every dense shape through `sparse_numerics.csr.dims_fit`)
  gains nothing from a declaration and would lose its typed status field, so those are
  absent too.

`dimensions` records the opposite finding: an `Int` that was examined and found to bound no
caller-supplied list. It exists so "nobody has looked at this function" and "somebody looked
and there is no relation" are different states.

WHAT A DECLARED RELATION IS ALLOWED TO SKIP: NOTHING IT CAN MEASURE

Two holes in the first version of this guard both came from the same instinct — "this case
cannot be compared, so pass it" — and both were measured killing the worker on a function the
manifest presents as guarded:

* A NON-POSITIVE factor was a pass for every relation, on the premise that
  `for i in range(n)` runs zero times. True of a count; false of an INDEX, which is a direct
  subscript. `network_analysis.degree(adj, -1)` passed the guard and aborted the process.
  `role` now decides — see `CountRelation.role` and `product_fits`.
* A bounded argument that was not a Python `list` was a pass, which turned every declared
  relation off for `"@u8:<base64>"`, a SUPPORTED spelling of `List[Float64]` on both paths.
  Length is now measured for every supported encoding, and an argument that is present but
  unmeasurable is REFUSED rather than skipped — see `count_relation_violation`.

The rule that follows from both: a relation declared `[enforced]` must be checked on every
call that carries the arguments it names, or the call must be refused. Passing an
unverifiable call is indistinguishable, from the caller's side, from not having a guard —
except that the manifest now says there is one.

`packages/algenta/algenta/runtime_count_guard.py` is the SDK-side twin of this file and must
reach the same verdict on the same call;
`tests/test_runtime_count_relations.py::test_both_implementations_reach_the_same_verdict`
pins them together over a shared table, including the negative-index, packed-buffer and
deferred-reference cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache, lru_cache

__all__ = [
    "COUNT_RELATION_ERROR_CODE",
    "PACKED_FLOAT64_PREFIX",
    "UNMEASURABLE_ARGUMENT_ERROR_CODE",
    "CountRelation",
    "CountSpec",
    "count_relation_violation",
    "declared_count_spec",
    "declared_count_specs",
    "measured_element_count",
    "packed_float64_element_count",
    "product_fits",
]

COUNT_RELATION_ERROR_CODE = "count_exceeds_list_length"

# A bounded argument whose length cannot be established is REFUSED, not waved through: see
# `count_relation_violation`. It is not `count_exceeds_list_length` — nothing was found to
# exceed anything — so it reuses the existing `invalid_arguments` code, which both paths
# already raise for an argument this guard cannot work with and which the API maps to 422.
UNMEASURABLE_ARGUMENT_ERROR_CODE = "invalid_arguments"

_LENGTH = "length"
_ELEMENT_LENGTH = "element_length"

_ROLE_COUNT = "count"
_ROLE_INDEX = "index"

# `"@u8:<base64>"` is a supported spelling of `List[Float64]` on both the SDK
# (`runtime_library_transport._normalize_value`) and the server
# (`mojo_library_runner._normalize_runtime_value`): the worker decodes it with
# `json_parse_float64_list`, one Float64 per decoded byte. It is a LIST, so every declared
# relation applies to it, and its element count is exact — see
# `packed_float64_element_count`.
PACKED_FLOAT64_PREFIX = "@u8:"

# The base64 alphabet `mojo/engine/json/parser._b64_sextet` accepts. Everything else —
# including `=` padding and whitespace — is SKIPPED there, so it must be skipped here too or
# the two sides would disagree about the length by up to two elements.
_BASE64_SEXTETS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)


@dataclass(frozen=True)
class CountRelation:
    """`product(factors) + plus` elements are required in each list named by `bounds`.

    `factors` holds Int parameter names. One name is a plain element count
    (`compute_mean(v, n)`); two are the dimensions of a flat row-major matrix
    (`unvec(v, rows, cols)` reads `v[j * rows + i]`, so `rows * cols` elements). A count
    that bounds several lists at once is ONE relation with several `bounds`, which is how a
    CSR triple is written: `(("nnz",), ("values", "col_index"))` beside
    `(("rows",), ("row_ptr",), plus=1)`.

    `plus` is a constant added to the product. `plus=1` also expresses an INDEX parameter:
    reading `adj[node]` requires `node + 1` elements.

    `scope` is `length` for `len(list)` and `element_length` for `len(list[k])` at every
    `k` — the inner dimension of a `List[List[...]]`, which is a different requirement from
    the outer one and is only declared where the kernel reads every element list at the
    full width.

    `role` DECIDES what a non-positive value means, so it is not documentation:

    * `count` — the value bounds a loop (`for i in range(n)`). `n = 0` and `n < 0` both make
      that loop empty, so the kernel reads nothing and there is nothing to refuse.
    * `index` — the value is a direct subscript (`adj[node]`). Mojo does NOT normalise a
      negative index: `a[-1]` on a 3-element List is
      `Assert Error: index -1 is out of bounds, valid range is 0 to 2`, i.e. the same
      uncatchable process abort this whole file exists to prevent. A negative index is
      therefore a VIOLATION, not an empty loop.

    A relation with `plus > 0` is index-shaped by construction — `x + k <= len(L)` asserts
    that the element at offset `x + k - 1` is read — so it is treated as an index whatever
    the `role` field says, and `_translate_capability_relations` labels such a relation
    `index` so the published contract and the violation message agree with the check.
    """

    factors: tuple[str, ...]
    bounds: tuple[str, ...]
    plus: int = 0
    scope: str = _LENGTH
    role: str = "count"
    why: str = ""

    def __post_init__(self) -> None:
        if not self.factors:
            raise ValueError("a count relation needs at least one Int factor")
        if not self.bounds:
            raise ValueError("a count relation must bound at least one List parameter")
        if self.scope not in {_LENGTH, _ELEMENT_LENGTH}:
            raise ValueError(f"unknown count-relation scope {self.scope!r}")
        if self.role not in {_ROLE_COUNT, _ROLE_INDEX}:
            raise ValueError(f"unknown count-relation role {self.role!r}")

    @property
    def subscripts_directly(self) -> bool:
        """Whether a negative value would be a read at a negative offset, not an empty loop.

        True for `role="index"` and for any relation with a positive `plus`: `x + 1 <= len(a)`
        is the declaration of an unconditional read at offset `x`, so `x < 0` reads `a[-1]`.
        """
        return self.role == _ROLE_INDEX or self.plus > 0


@dataclass(frozen=True)
class CountSpec:
    """Every declared count relation for one contract function, plus the bare dimensions."""

    relations: tuple[CountRelation, ...] = ()
    dimensions: tuple[str, ...] = ()

    def to_payload(self) -> list[dict[str, object]]:
        """The wire form carried in the generated SDK contract.

        Only `relations` crosses: `dimensions` is a review record, not something a guard
        acts on, and putting it on the wire would invite a consumer to treat "declared a
        dimension" as "declared safe".

        `role` is published as the role the guard will ACT on, not as the field was written:
        both guards derive `index` from a positive `plus`, and publishing anything else would
        put a different statement on the wire from the one being enforced.
        """
        return [
            {
                "factors": list(relation.factors),
                "bounds": list(relation.bounds),
                "plus": relation.plus,
                "scope": relation.scope,
                "role": _ROLE_INDEX if relation.subscripts_directly else relation.role,
            }
            for relation in self.relations
        ]


def product_fits(factors: list[int], available: int, *, role: str = _ROLE_COUNT) -> bool:
    """Whether `product(factors) <= available`, WITHOUT forming the product.

    The naive `rows * cols <= len(a)` is wrong on the worker side, where `Int` is 64 bits
    wide and the multiply WRAPS: `3 * 6148914691236517206 == 2`, so a hostile pair passes
    the check and the kernel then reads far past the end of a two-element list. The frozen
    `sparse_numerics.csr.dims_fit` avoids it by dividing instead of multiplying, and this
    mirrors that reasoning so the two sides agree about which shapes are admissible.

    Python's ints do not wrap, so forming the product here would not overflow — but it
    would answer a DIFFERENT question from the one the worker will ask, and it would do
    arbitrary-precision arithmetic on caller-controlled magnitudes. Dividing is exact:
    for integers, `f * p <= L` iff `p <= L // f`, so the floor loses nothing.

    THE ROLE DECIDES WHAT A NON-POSITIVE FACTOR MEANS. This used to be one branch,
    `if factor <= 0: return True`, justified by "the kernel's loop `for i in range(n)` runs
    zero times and reads nothing". That is true of a COUNT and false of an INDEX, where the
    value is a direct subscript: measured, `network_analysis.degree([[0.0, 1.0], [1.0]], -1)`
    passed that check and ended the worker process, because `adj[-1]` is not an empty loop —
    Mojo does not normalise a negative index, it aborts. So:

    * `count`: a factor of 0 makes the product 0 and a negative factor makes the per-dimension
      loop empty (`range(-3)` is empty even when a second negative factor would make the
      arithmetic product positive). Nothing is read; admissible.
    * `index`: a negative value is inadmissible, full stop. `available` already carries the
      `plus` subtraction, so `0 <= value <= available` is the remaining question.
    """
    if available < 0:
        return False
    if role == _ROLE_INDEX and any(factor < 0 for factor in factors):
        return False
    if any(factor == 0 for factor in factors):
        # The product is 0 regardless of the other factors, so nothing is read. Checked up
        # front rather than inside the loop: `[1, 0]` against an empty list needs 0 elements,
        # and the incremental division would have refused it on the leading 1.
        return True
    remaining = available
    for factor in factors:
        if factor < 0:
            # A count: `for i in range(-3)` is empty, so this dimension reads nothing.
            return True
        if factor > remaining:
            return False
        remaining //= factor
    return True


def packed_float64_element_count(value: str) -> int:
    """Elements the worker will decode from a `"@u8:<base64>"` buffer.

    Counted exactly the way `mojo/engine/json/parser.json_decode_base64_bytes` counts: every
    character in the base64 alphabet contributes 6 bits, a byte is emitted for every 8 bits
    accumulated, and any other character (padding, whitespace, a stray `"`) is skipped. So
    the count is `floor(6 * sextets / 8)` and one decoded byte is one `Float64`.

    `"@u8:AQID"` is 4 sextets → 3 bytes → 3 elements, which is what makes
    `compute_mean("@u8:AQID", 25)` an over-read the guard can now refuse instead of a call it
    waved through because the argument was "not a list".
    """
    sextets = sum(
        1 for character in value[len(PACKED_FLOAT64_PREFIX) :] if character in _BASE64_SEXTETS
    )
    return (sextets * 6) // 8


def measured_element_count(value: object) -> int | None:
    """How many elements the worker will see in `value`, or `None` if that is unknowable.

    Every SUPPORTED spelling of a List argument is measured here, because a bounded argument
    the guard cannot measure is refused rather than passed (see `count_relation_violation`),
    and refusing a legitimate encoding would be a false refusal. The supported spellings are
    a JSON array and, for `List[Float64]`, a `"@u8:<base64>"` packed buffer.

    `None` means the length genuinely does not exist on this side of the wire — a deferred
    `"@handle"` (a dataset resident in the worker; `dataset_list` reports its BYTES, not its
    element count) or a `"$k"` pipeline reference (node `k` has not run yet).
    """
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value.startswith(PACKED_FLOAT64_PREFIX):
        return packed_float64_element_count(value)
    return None


def count_relation_violation(
    *,
    module: str,
    function: str,
    param_names: tuple[str, ...],
    args: tuple[object, ...] | list[object],
    spec: CountSpec | None,
) -> dict[str, object] | None:
    """The first declared relation the supplied arguments break, or `None`.

    Returns a details mapping — never raises and never inspects an undeclared function, so
    a function with no entry in this table behaves exactly as it did before this guard
    existed. Each caller wraps the mapping in its own typed error, using the `code` the
    mapping carries.

    AN ARGUMENT THAT IS ABSENT IS A PASS; AN ARGUMENT THAT IS PRESENT AND UNMEASURABLE IS A
    REFUSAL. The two used to be the same branch, which is what made the guard skippable: a
    caller who spelled the list as a supported `"@u8:"` buffer or as a deferred `"@handle"`
    reached `if not isinstance(listed, list): continue` and every declared relation stopped
    applying. Measured, `compute_mean("@u8:AQID", 25)` and `compute_mean("@ds_1", 5)` each
    ended the worker process while the guard reported the call as fine. So:

    * The parameter is not in `supplied` at all — the caller omitted a defaulted argument.
      Nothing was passed, so nothing can be over-read through it. PASS.
    * The parameter is present and its element count is measurable (a list, or a `"@u8:"`
      packed buffer). CHECK it.
    * The parameter is present and its element count is not knowable here (a `"@handle"`
      dataset reference, a `"$k"` pipeline reference). REFUSE. Deferring this to the worker is
      what the old docstring did, on the premise that "the worker fails loudly" — and the
      failure this guard exists to prevent is not loud, it is a process abort that takes every
      resident dataset with it. An unverifiable bound on a function declared `[enforced]` is
      the one case where refusing is the conservative answer.

    A non-integer COUNT is still a pass: an omitted defaulted count and a `"$k"` count are
    both unmeasurable, and the second is only reachable through `pipeline_execute`, which does
    not run this guard at all. That gap is stated rather than closed here.
    """
    if spec is None or not spec.relations:
        return None

    supplied: dict[str, object] = {}
    for name, value in zip(param_names, args, strict=False):
        supplied[name] = value

    for relation in spec.relations:
        factors: list[int] = []
        for name in relation.factors:
            value = supplied.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                factors = []
                break
            factors.append(value)
        if not factors:
            continue
        # Derived, not read off the field, and derived identically in the SDK twin: a relation
        # with a positive `plus` is index-shaped whatever its `role` says, and the two paths
        # must not disagree about that or the same call is accepted by one SDK and refused by
        # the other.
        role = _ROLE_INDEX if relation.subscripts_directly else _ROLE_COUNT

        for list_name in relation.bounds:
            if list_name not in supplied:
                continue
            listed = supplied[list_name]
            for length, element_index in _measured_lengths(relation, listed):
                if length is None:
                    return _unmeasurable_details(
                        module=module,
                        function=function,
                        relation=relation,
                        role=role,
                        list_name=list_name,
                        value=listed,
                        element_index=element_index,
                    )
                available = length - relation.plus
                if product_fits(factors, available, role=role):
                    continue
                details: dict[str, object] = {
                    "code": COUNT_RELATION_ERROR_CODE,
                    "module": module,
                    "function": function,
                    "parameter": (
                        relation.factors[0]
                        if len(relation.factors) == 1
                        else list(relation.factors)
                    ),
                    "count": factors[0] if len(factors) == 1 else factors,
                    "required_elements": _describe_requirement(relation, factors),
                    "list_parameter": list_name,
                    "actual_length": length,
                    "role": role,
                }
                if element_index is not None:
                    details["list_element_index"] = element_index
                details["message"] = _describe_violation(
                    module=module,
                    function=function,
                    relation=relation,
                    role=role,
                    factors=factors,
                    list_name=list_name,
                    length=length,
                    element_index=element_index,
                )
                return details
    return None


def _measured_lengths(
    relation: CountRelation, listed: object
) -> list[tuple[int | None, int | None]]:
    """`(element count, element index)` pairs to check; a `None` count is UNMEASURABLE.

    For an `element_length` relation every element of the outer list is a bound of its own, so
    an unmeasurable ROW is reported with its index — the row is what the caller has to fix.
    """
    if relation.scope == _LENGTH:
        return [(measured_element_count(listed), None)]
    if not isinstance(listed, list):
        return [(None, None)]
    return [
        (measured_element_count(element), index) for index, element in enumerate(listed)
    ]


def _unmeasurable_details(
    *,
    module: str,
    function: str,
    relation: CountRelation,
    role: str,
    list_name: str,
    value: object,
    element_index: int | None,
) -> dict[str, object]:
    """The refusal for a bounded argument whose length this side cannot establish."""
    target = f"{list_name}[{element_index}]" if element_index is not None else list_name
    if element_index is not None and isinstance(value, list):
        shown = value[element_index]
    else:
        shown = value
    encoding = shown if isinstance(shown, str) else type(shown).__name__
    details: dict[str, object] = {
        "code": UNMEASURABLE_ARGUMENT_ERROR_CODE,
        "module": module,
        "function": function,
        "parameter": (
            relation.factors[0] if len(relation.factors) == 1 else list(relation.factors)
        ),
        "list_parameter": list_name,
        "unmeasurable_argument": encoding,
        "reason": "unmeasurable_bounded_argument",
        "role": role,
    }
    if element_index is not None:
        details["list_element_index"] = element_index
    # Word for word the message `runtime_count_guard._refuse_unmeasurable` raises: the two
    # guards are pinned to each other by
    # `tests/test_runtime_count_relations.py::test_both_implementations_reach_the_same_verdict`,
    # which compares the text and not only the verdict.
    details["message"] = (
        f"{module}.{function}: '{target}' is bounded by a declared element count "
        f"({_describe_relation(relation, list_name)}), and the length of {encoding!r} cannot "
        "be determined before the call. Reading past the end of that list inside the runtime "
        "worker is an uncatchable abort of the whole process, so the call is declined rather "
        f"than sent unchecked. Pass '{list_name}' as a list, or as a "
        f'"{PACKED_FLOAT64_PREFIX}<base64>" buffer, both of which can be measured here.'
    )
    return details


def _describe_relation(relation: CountRelation, list_name: str) -> str:
    product = " * ".join(relation.factors)
    if relation.plus:
        product = f"{product} + {relation.plus}"
    if relation.scope == _ELEMENT_LENGTH:
        return f"{product} <= len({list_name}[k])"
    return f"{product} <= len({list_name})"


def _describe_requirement(relation: CountRelation, factors: list[int]) -> str:
    product = " * ".join(relation.factors)
    if relation.plus:
        product = f"{product} + {relation.plus}"
    values = " * ".join(str(value) for value in factors)
    if relation.plus:
        values = f"{values} + {relation.plus}"
    return f"{product} = {values}"


def _describe_violation(
    *,
    module: str,
    function: str,
    relation: CountRelation,
    role: str,
    factors: list[int],
    list_name: str,
    length: int,
    element_index: int | None,
) -> str:
    target = f"{list_name}[{element_index}]" if element_index is not None else list_name
    if len(relation.factors) == 1:
        counted = f"{relation.factors[0]}={factors[0]}"
    else:
        counted = ", ".join(
            f"{name}={value}" for name, value in zip(relation.factors, factors, strict=True)
        )
    requirement = _describe_requirement(relation, factors)
    if role == _ROLE_INDEX and any(factor < 0 for factor in factors):
        # A negative index is not "past the end" and not an empty loop. Mojo does not
        # normalise it: `a[-1]` on a 3-element List aborts with "index -1 is out of bounds,
        # valid range is 0 to 2", which ends the worker process.
        return (
            f"{module}.{function}: {counted} is a negative index into '{target}'. The runtime "
            "does not read a negative index from the end of the list; it aborts the whole "
            "worker process. An index must be 0 or greater."
        )
    if role == _ROLE_INDEX:
        return (
            f"{module}.{function}: {counted} indexes past the end of '{target}', which has "
            f"{length} element(s); reading it would abort the runtime worker. "
            f"'{list_name}' must hold at least {requirement} element(s)."
        )
    return (
        f"{module}.{function}: {counted} counts more elements than '{target}' holds "
        f"({length}); reading them would abort the runtime worker. '{list_name}' must hold "
        f"at least {requirement} element(s)."
    )


def _count(list_param: str, count_param: str, why: str) -> CountRelation:
    return CountRelation(factors=(count_param,), bounds=(list_param,), why=why)


def _counts(list_params: tuple[str, ...], count_param: str, why: str) -> CountRelation:
    return CountRelation(factors=(count_param,), bounds=list_params, why=why)


def _index(list_param: str, index_param: str, why: str) -> CountRelation:
    return CountRelation(
        factors=(index_param,), bounds=(list_param,), plus=1, role="index", why=why
    )


# ── The declarations ──────────────────────────────────────────────────────────────────
#
# One entry per verified frozen kernel, keyed (module import path, function name). Every
# `why` is the source expression that requires the bound, so a future reader can re-check
# the claim against the kernel rather than trust this file.
#
# NOT here, deliberately, with the reason:
#   stats.sort_values / quantile / percentile / median   — clamp, and answer the question
#   optimization.*, retrieval.fuse.*, seq_nn.*, pls.*    — validate and return a status
#   reservoir.*, timeseries_stats.rolling_mean           — treat an over-large count as
#                                                          "take everything"
#   clustering_metrics.*, dependency.resolve_order,
#   graph.weighted.floyd_warshall, sparse_vector.sv_to_dense
#                                                       — the Int is a DIMENSION; see
#                                                         `dimensions` on those entries
_DECLARED: dict[tuple[str, str], CountSpec] = {
    # ── auction: every driver loops `for i in range(n)` over `bids`, no `len` anywhere ──
    ("auction", "all_pay_revenue"): CountSpec(
        relations=(_count("bids", "n", "for i in range(n): total += bids[i]"),)
    ),
    ("auction", "dutch_auction_revenue"): CountSpec(
        relations=(_count("bids", "n", "bids[0] then for i in range(1, n): bids[i]"),)
    ),
    ("auction", "english_auction_revenue"): CountSpec(
        relations=(_count("bids", "n", "bids[0] then for i in range(1, n): bids[i]"),)
    ),
    ("auction", "first_price_sealed"): CountSpec(
        relations=(_count("bids", "n", "bids[0] then for i in range(1, n): bids[i]"),)
    ),
    ("auction", "second_price_sealed"): CountSpec(
        relations=(_count("bids", "n", "bids[0] then for i in range(1, n): bids[i]"),)
    ),
    ("auction", "revenue_equivalence_check"): CountSpec(
        relations=(
            _count(
                "bids",
                "n",
                "delegates to dutch_auction_revenue(bids, n) and english_auction_revenue(bids, n)",
            ),
        )
    ),
    ("auction", "reserve_price_filter"): CountSpec(
        relations=(_count("bids", "n", "for i in range(n): if bids[i] >= reserve"),)
    ),
    ("auction", "vcg_payment"): CountSpec(
        relations=(_count("values", "n", "for i in range(n): values[i] > max_other"),)
    ),
    # ── cellular: a nested grid read at the full width, so BOTH dimensions are bounds ──
    ("cellular", "game_of_life_step"): CountSpec(
        relations=(
            _count("grid", "rows", "for r in range(rows): grid[r][c]"),
            CountRelation(
                factors=("cols",),
                bounds=("grid",),
                scope=_ELEMENT_LENGTH,
                why="for c in range(cols): grid[r][c], at every r",
            ),
        )
    ),
    ("cellular", "is_still_life"): CountSpec(
        relations=(
            _count("grid", "rows", "for r in range(rows): grid[r][c]"),
            CountRelation(
                factors=("cols",),
                bounds=("grid",),
                scope=_ELEMENT_LENGTH,
                why="for c in range(cols): grid[r][c], at every r",
            ),
        )
    ),
    # ── flat row-major matrices: the PRODUCT is the count ──────────────────────────────
    ("cellular_automata", "game_of_life_step"): CountSpec(
        relations=(
            CountRelation(
                factors=("rows", "cols"),
                bounds=("grid",),
                why=(
                    "grid[ni * cols + nj] with ni < rows and nj < cols; the docstring "
                    "declares grid as a row-major rows x cols matrix"
                ),
            ),
        )
    ),
    ("matrix_ops", "unvec"): CountSpec(
        relations=(
            CountRelation(
                factors=("rows", "cols"),
                bounds=("v",),
                why="v[j * rows + i] for i < rows, j < cols; max index rows * cols - 1",
            ),
        )
    ),
    ("cellular_automata", "rule_step_1d"): CountSpec(
        relations=(_count("cells", "n", "cells[n - 1], cells[i - 1], cells[i], cells[i + 1]"),)
    ),
    ("compiler_theory", "instruction_latency_sum"): CountSpec(
        relations=(_count("latencies", "n", "for i in range(n): total += latencies[i]"),)
    ),
    # ── correlation: OUTER bound only. `corr[i][j]` has `j <= i`, so a ragged
    #    lower-triangular argument is legal and an element_length bound would refuse it.
    ("correlation", "cholesky_lower"): CountSpec(
        relations=(_count("corr", "n", "for i in range(n): corr[i][i], corr[i][j] with j <= i"),)
    ),
    ("correlation", "sample_correlated_normal"): CountSpec(
        relations=(
            _count("L", "n_vars", "for i in range(n_vars): L[i][j] for j in range(i + 1)"),
        )
    ),
    # ── petri_net: one count over three parallel arrays — ONE relation, three bounds ───
    ("petri_net", "is_transition_enabled_list"): CountSpec(
        relations=(
            _counts(
                ("marking", "input_arcs"),
                "n_places",
                "for i in range(n_places): marking[i] < input_arcs[i]",
            ),
        )
    ),
    ("petri_net", "fire_transition_list"): CountSpec(
        relations=(
            _counts(
                ("marking", "input_arcs", "output_arcs"),
                "n_places",
                "for i in range(n_places): marking[i] - input_arcs[i] + output_arcs[i]",
            ),
        )
    ),
    # ── reinforcement: outer count over the state axis, inner over the action axis ─────
    ("reinforcement", "value_iteration"): CountSpec(
        relations=(
            _counts(
                ("rewards", "transitions"),
                "n_states",
                "for s in range(n_states): rewards[s][0], transitions[s][0]",
            ),
            CountRelation(
                factors=("n_actions",),
                bounds=("rewards", "transitions"),
                scope=_ELEMENT_LENGTH,
                why="for a in range(1, n_actions): rewards[s][a], transitions[s][a]",
            ),
        )
    ),
    ("reinforcement", "policy_evaluation"): CountSpec(
        relations=(
            _counts(
                ("policy", "rewards", "transitions"),
                "n_states",
                "for s in range(n_states): policy[s], rewards[s][a], transitions[s][a]",
            ),
        )
    ),
    # ── stats: the family named in docs/mojo/new-kernel-package-rules.md rule 1 ────────
    ("stats", "compute_mean"): CountSpec(
        relations=(_count("v", "n", "for i in range(n): t += v[i]"),)
    ),
    ("stats", "compute_variance"): CountSpec(
        relations=(_count("v", "n", "for i in range(n): d = v[i] - mean"),)
    ),
    ("stats", "count_below_zero"): CountSpec(
        relations=(_count("v", "n", "for i in range(n): if v[i] < 0.0"),)
    ),
    ("stats", "pctile"): CountSpec(
        relations=(_count("v", "n", "v[max(0, min((n - 1) * p // 100, n - 1))]"),)
    ),
    ("voting", "approval_score"): CountSpec(
        relations=(_count("approvals", "n_voters", "for i in range(n_voters): approvals[i]"),)
    ),
    # ── INDEX parameters. Same hazard, same machinery: `plus=1`. ───────────────────────
    ("sorting", "nth_smallest"): CountSpec(
        relations=(
            _index("data", "n", "sorted_data[n], where sorted_data has len(data) elements"),
        )
    ),
    ("network_analysis", "degree"): CountSpec(
        relations=(_index("adj", "node", "len(adj[node])"),)
    ),
    ("network_analysis", "clustering_coefficient"): CountSpec(
        relations=(_index("adj", "node", "len(adj[node]) then adj[node][i]"),)
    ),
    ("social_network", "out_degree"): CountSpec(
        relations=(_index("adj", "node", "len(adj[node])"),)
    ),
    ("graph.weighted", "union_find_find"): CountSpec(
        relations=(_index("parent", "x", "parent[x] != x"),)
    ),
    ("recommender", "cosine_sim_users"): CountSpec(
        relations=(
            CountRelation(
                factors=("u1",),
                bounds=("ratings",),
                plus=1,
                role="index",
                why="len(ratings[u1]) then ratings[u1][j]",
            ),
            CountRelation(
                factors=("u2",),
                bounds=("ratings",),
                plus=1,
                role="index",
                why="ratings[u2][j]",
            ),
        )
    ),
    ("recommender", "item_overlap"): CountSpec(
        relations=(
            CountRelation(
                factors=("u1",),
                bounds=("ratings",),
                plus=1,
                role="index",
                why="len(ratings[u1]) then ratings[u1][j]",
            ),
            CountRelation(
                factors=("u2",),
                bounds=("ratings",),
                plus=1,
                role="index",
                why="ratings[u2][j]",
            ),
        )
    ),
    ("crypto.chacha20", "quarter_round"): CountSpec(
        relations=(
            _index("state", "a", "state[a] = (state[a] + state[b]) & MASK32"),
            _index("state", "b", "state[b] = rotl32(state[b] ^ state[c], 12)"),
            _index("state", "c", "state[c] = (state[c] + state[d]) & MASK32"),
            _index("state", "d", "state[d] = rotl32(state[d] ^ state[a], 16)"),
        )
    ),
    ("stats", "part3"): CountSpec(
        relations=(
            _index("a", "lo", "a[lo] read unconditionally"),
            _index("a", "hi", "a[hi] and a[hi - 1] read unconditionally"),
        )
    ),
    # `lo` is NOT declared for ins_sort: `range(lo + 1, hi + 1)` is empty when lo >= hi, so
    # a large `lo` reads nothing and `ins_sort(a, 100, 0)` is a legal no-op today.
    ("stats", "ins_sort"): CountSpec(
        relations=(_index("a", "hi", "for i in range(lo + 1, hi + 1): a[i]"),)
    ),
    # ── Examined, no relation: the Int bounds a list the KERNEL allocates ──────────────
    ("clustering_metrics", "cluster_sizes"): CountSpec(dimensions=("k",)),
    ("clustering_metrics", "davies_bouldin"): CountSpec(dimensions=("k",)),
    ("clustering_metrics", "contingency_matrix"): CountSpec(dimensions=("n_true", "n_pred")),
    ("dependency", "resolve_order"): CountSpec(dimensions=("n_packages",)),
    ("graph.weighted", "floyd_warshall"): CountSpec(dimensions=("n",)),
    ("sparse_vector", "sv_to_dense"): CountSpec(dimensions=("size",)),
    ("reservoir", "reservoir_sample"): CountSpec(dimensions=("k",)),
    ("reservoir", "weighted_reservoir_sample"): CountSpec(dimensions=("k",)),
    ("reservoir", "systematic_sample"): CountSpec(dimensions=("k",)),
    ("timeseries_stats", "rolling_mean"): CountSpec(dimensions=("window",)),
}


def declared_count_spec(
    module: str,
    function: str,
    *,
    module_path: object | None = None,
) -> CountSpec | None:
    """The declared spec for one contract function, or `None` if none has been written.

    An IN-SOURCE `@capability` block wins over this file's table. That block sits beside the
    kernel it describes, so it cannot drift from it, and it is what a new module is required
    to carry. This table exists for the frozen kernels that have no block yet: it is a
    migration path, not a second opinion, and a function declared in both places is read
    from the block.

    `None` is the fail-open case and it is per FUNCTION: an undeclared neighbour never
    disables the guard for a declared one.

    `module_path` lets a caller that already holds the module's `.mojo` path hand it over,
    which is every caller on the request path. Without it the path is looked up by reloading
    the runtime inventory — correct, but a wasted ~70 ms once per process.
    """
    from_block = _capability_block_spec(module, function, module_path)
    if from_block is not None:
        return from_block
    return _DECLARED.get((module, function))


def declared_count_specs() -> dict[tuple[str, str], CountSpec]:
    """Every function with a spec, from both sources, blocks winning on a collision."""
    merged = dict(_DECLARED)
    merged.update(_capability_block_specs())
    return merged


# ── Bridge to the in-source `@capability` blocks ──────────────────────────────────────
#
# `apps/runtime/mojo_capability_manifest.py` owns the block grammar and its own richer
# relation type. Only the part this guard can act on is translated: an ENFORCED relation
# over a caller-supplied list. Deliberately dropped, with the reason:
#
#   enforcement `clamped`          — the kernel answers the question; refusing would be a
#                                    behaviour change (this is `stats.median`'s case)
#   enforcement `kernel_validated` — the kernel already returns a typed status, which is
#                                    more informative than a client-side refusal
#   kind `dimension`               — bounds no caller-supplied list, so there is nothing
#                                    here to compare it against
#   comparison `==`                — only the `<=` half is enforced. Refusing a SHORT list
#                                    prevents an over-read; refusing an over-LONG one is a
#                                    shape opinion the kernel itself should state.


def _translate_capability_relations(spec: object) -> CountSpec | None:
    relations: list[CountRelation] = []
    dimensions: list[str] = []
    declared = getattr(spec, "count_relations", None)
    if declared is None:
        return None
    for relation in declared:
        kind = getattr(relation, "kind", "")
        counts = tuple(getattr(relation, "counts", ()) or ())
        if kind == "dimension":
            dimensions.extend(counts)
            continue
        if getattr(relation, "enforcement", "") != "enforced":
            continue
        bounds = tuple(getattr(relation, "bounded_lists", ()) or ())
        if not counts or not bounds:
            continue
        addend = getattr(relation, "addend", 0)
        plus = addend if isinstance(addend, int) and addend > 0 else 0
        relations.append(
            CountRelation(
                factors=counts,
                bounds=bounds,
                plus=plus,
                # The block grammar has no `role` field, and a translated relation used to
                # arrive here as a `count` — which is why `stats.part3` published
                # `role: "count"` for two parameters the table declares as INDEXES, and why a
                # negative `lo`/`hi` was waved through by the non-positive branch of
                # `product_fits` (measured: `part3(FIVE, 0, -1)` ended the worker). `x + k <=
                # len(L)` IS the index shape: it asserts a read at offset `x + k - 1`, so a
                # negative `x` is a read at a negative offset. Labelling it here keeps the
                # check, the message and the published contract saying the same thing.
                role=_ROLE_INDEX if plus > 0 else _ROLE_COUNT,
                why=str(getattr(relation, "raw", "")),
            )
        )
    if not relations and not dimensions:
        # `count_relations == ()` is the author saying "no count parameters here". That is a
        # decision, and recording it as an empty spec keeps it distinct from "never looked".
        return CountSpec()
    return CountSpec(relations=tuple(relations), dimensions=tuple(dict.fromkeys(dimensions)))


@lru_cache(maxsize=1)
def _capability_block_specs() -> dict[tuple[str, str], CountSpec]:
    """Translated blocks for the whole tree, or `{}` if the manifest cannot be built.

    Whole-tree, so this is for the contract generator and the tests — NOT for the request
    path, which uses `_capability_block_spec` and pays for one file. Building the manifest
    over 500+ modules takes about a second, and a second on the first `library_execute` of a
    process would show up in the latency gate.

    Built non-strictly and defensively. A manifest that will not build is a defect the
    capability GATE reports loudly with every issue listed; making this guard raise as well
    would take the pre-validation offline for every function at once, which is strictly
    worse than falling back to the table in this file.
    """
    try:
        from apps.runtime.mojo_inventory import build_capability_manifest

        manifest = build_capability_manifest(strict=False)
    except Exception:  # noqa: BLE001 - see the docstring: never take the guard offline
        return {}
    specs: dict[tuple[str, str], CountSpec] = {}
    for module in getattr(manifest, "modules", ()):
        for function_spec in getattr(module, "functions", ()):
            translated = _translate_capability_relations(function_spec)
            if translated is None:
                continue
            specs[(module.import_path, function_spec.target)] = translated
    return specs


@cache
def _module_paths() -> dict[str, object]:
    try:
        from apps.runtime.mojo_inventory import discover_runtime_library_modules

        return {module.import_path: module.path for module in discover_runtime_library_modules()}
    except Exception:  # noqa: BLE001
        return {}


@cache
def _module_block_specs(module: str, module_path: object | None = None) -> dict[str, CountSpec]:
    """Translated blocks for ONE module: a single-file parse, memoised per module.

    Only the modules a process actually calls are ever read, and a file with no
    `@capability` fence is rejected by one substring test inside the parser.
    """
    path = module_path if module_path is not None else _module_paths().get(module)
    if path is None:
        return {}
    try:
        from apps.runtime.mojo_inventory import parse_runtime_capability_specs

        parse = parse_runtime_capability_specs(path)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 - never take the guard offline; see above
        return {}
    specs: dict[str, CountSpec] = {}
    for function_spec in getattr(parse, "functions", ()):
        translated = _translate_capability_relations(function_spec)
        if translated is not None:
            specs[function_spec.target] = translated
    return specs


def _capability_block_spec(
    module: str,
    function: str,
    module_path: object | None = None,
) -> CountSpec | None:
    return _module_block_specs(module, module_path).get(function)
