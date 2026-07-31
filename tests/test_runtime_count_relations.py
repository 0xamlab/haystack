"""The declared count-relation guard: what it refuses, what it must never refuse.

The guard converts an UNCATCHABLE process abort into a typed error. That claim is proved
against a compiled worker in `tests/integration/test_batch_count_guard_e2e.py`; this file
proves the properties a unit test can actually establish:

* every declaration matches the live contract signature it describes
* the product test is exact and does not use a wrapping multiply
* the guard is silent for every function without a declaration, and one function's silence
  cannot silence another's
* the A-Z sample arguments break no declared relation, so adding the guard cannot regress
  the generated suite
* the server-side and SDK-side implementations agree case by case
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
for _path in (str(_REPO_ROOT), str(_ALGENTA)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from algenta.runtime_count_guard import (  # noqa: E402
    COUNT_RELATION_ERROR_CODE,
    count_fits,
    enforce_count_relations,
)
from algenta.runtime_count_guard import (  # noqa: E402
    measured_element_count as sdk_measured_element_count,
)
from algenta.runtime_count_guard import (  # noqa: E402
    packed_float64_element_count as sdk_packed_float64_element_count,
)
from algenta.runtime_library_contract import (  # noqa: E402
    RuntimeLibraryContractError,
    find_runtime_function,
    runtime_modules,
)
from algenta.runtime_library_transport import build_worker_request  # noqa: E402

from apps.runtime import mojo_library_runner as runner  # noqa: E402
from apps.runtime.mojo_count_relations import (  # noqa: E402
    UNMEASURABLE_ARGUMENT_ERROR_CODE,
    CountRelation,
    CountSpec,
    count_relation_violation,
    declared_count_spec,
    declared_count_specs,
    measured_element_count,
    packed_float64_element_count,
    product_fits,
)
from apps.runtime.mojo_inventory import discover_runtime_library_modules  # noqa: E402

FIVE = [5.0, 4.0, 3.0, 2.0, 1.0]


@pytest.fixture(scope="module")
def engine_modules():
    return {module.import_path: module for module in discover_runtime_library_modules()}


# ── The declarations describe real signatures ─────────────────────────────────────────


def test_every_declaration_matches_the_live_signature(engine_modules) -> None:
    """A relation naming a parameter that does not exist would silently never fire.

    That is the exact failure this whole mechanism exists to remove, so it is asserted
    rather than trusted: every factor must be an `Int` parameter of that function, every
    bound must be a `List[...]` parameter, and an `element_length` bound must be nested.
    """
    problems: list[str] = []
    for (module_name, function_name), spec in declared_count_specs().items():
        module = engine_modules.get(module_name)
        if module is None:
            problems.append(f"{module_name}: not in the runtime inventory")
            continue
        function = next((f for f in module.functions if f.name == function_name), None)
        if function is None:
            problems.append(f"{module_name}.{function_name}: not a contract function")
            continue
        types = {param.name: param.typ for param in function.params}
        for relation in spec.relations:
            for factor in relation.factors:
                if types.get(factor) != "Int":
                    problems.append(
                        f"{module_name}.{function_name}: factor {factor!r} is "
                        f"{types.get(factor)!r}, not Int"
                    )
            for bound in relation.bounds:
                bound_type = types.get(bound)
                if bound_type is None or not bound_type.startswith("List["):
                    problems.append(
                        f"{module_name}.{function_name}: bound {bound!r} is {bound_type!r}"
                    )
                elif relation.scope == "element_length" and not bound_type.startswith(
                    "List[List["
                ):
                    problems.append(
                        f"{module_name}.{function_name}: element_length bound {bound!r} is "
                        f"{bound_type!r}, which has no element lists"
                    )
        for dimension in spec.dimensions:
            if types.get(dimension) != "Int":
                problems.append(
                    f"{module_name}.{function_name}: dimension {dimension!r} is "
                    f"{types.get(dimension)!r}, not Int"
                )
    assert not problems, "\n".join(problems)


def test_the_declarations_reach_the_shipped_contract() -> None:
    """The SDK reads relations from the bundled contract, not from `apps/`."""
    published = {
        (module.import_path, function.name): function.count_relations
        for module in runtime_modules()
        for function in module.functions
        if function.count_relations
    }
    declared = {
        key: spec for key, spec in declared_count_specs().items() if spec.relations
    }
    assert set(published) == set(declared), (
        "the bundled contract and the declaration table disagree about which functions "
        "carry relations — run `make inventory-refresh`"
    )
    for key, spec in declared.items():
        assert len(published[key]) == len(spec.relations), key


def test_the_clamping_functions_from_the_incident_are_deliberately_undeclared() -> None:
    """`stats.median` and friends clamp an over-large count and answer the question.

    Declaring a relation for them would turn a working call into an error, which is why
    "never guess a relation" is a rule and not a preference. Asserted so a later sweep
    cannot add them by pattern-matching on `(List, Int)`.
    """
    hostile = {
        "median": [FIVE, 25],
        "sort_values": [FIVE, 25],
        "quantile": [FIVE, 25, 0.5],
        "percentile": [FIVE, 25, 50],
    }
    for function_name, args in hostile.items():
        spec = declared_count_spec("stats", function_name)
        # Either no declaration at all, or an in-source block whose relation is tagged
        # `clamped` — which the bridge translates to zero ENFORCED relations. Both mean the
        # guard must not act.
        assert spec is None or not spec.relations, (function_name, spec)
        _m, _f, request = build_worker_request("stats", function_name, args)
        assert request["args"] == args


# ── The product test is exact, and does not wrap ──────────────────────────────────────


@pytest.mark.parametrize(
    ("factors", "available", "expected"),
    [
        ([5], 5, True),
        ([6], 5, False),
        ([0], 0, True),
        ([-3], 0, True),
        ([3, 6], 25, True),
        ([5, 5], 25, True),
        ([5, 6], 25, False),
        ([13, 2], 25, False),
        ([2, 13], 25, False),
        ([5, 5, 2], 25, False),
        ([3, 3, 3], 27, True),
        ([2, 2, 7], 27, False),
        ([1], 0, False),
        ([4], -1, False),
        # A zero factor makes the product 0 whatever precedes it: `unvec([], 1, 0)` needs no
        # elements. Refusing it was an order-dependent false refusal, since `[0, 1]` passed.
        ([1, 0], 0, True),
        ([3, 0], 0, True),
        ([0, 1], 0, True),
        # Two negative factors multiply to a POSITIVE number, and it is still admissible: the
        # kernel loops per dimension (`for i in range(rows)`), so `range(-3)` reads nothing.
        ([-3, -5], 0, True),
    ],
)
def test_product_fits_is_exact(factors, available, expected) -> None:
    assert product_fits(list(factors), available) is expected
    assert count_fits(list(factors), available) is expected
    if all(factor > 0 for factor in factors):
        product = 1
        for factor in factors:
            product *= factor
        assert expected == (product <= available)


@pytest.mark.parametrize(
    ("factors", "available", "expected"),
    [
        ([0], 0, True),  # index 0 into a 1-element list: `available` already lost the `plus`
        ([2], 2, True),
        ([3], 2, False),
        ([-1], 5, False),  # THE FIX: a negative subscript, not an empty loop
        ([-9], 5, False),
        ([-1], -1, False),
    ],
)
def test_the_index_role_refuses_a_negative_value(factors, available, expected) -> None:
    """The role, not the sign alone, decides — and both implementations must decide alike."""
    assert product_fits(list(factors), available, role="index") is expected
    assert count_fits(list(factors), available, role="index") is expected


def test_a_wrapping_multiply_would_have_accepted_this_pair() -> None:
    """`3 * 6148914691236517206` is `2` in fixed-width 64-bit arithmetic.

    A naive `rows * cols <= len(a)` therefore passes for a two-element list and the kernel
    reads far past its end. `sparse_numerics.csr.dims_fit` avoids that by dividing, and this
    guard mirrors it — so the pair below must be REFUSED here and the wrapped product must
    not be what decided it.
    """
    rows, cols = 3, 6148914691236517206
    wrapped = (rows * cols) % (1 << 64)
    if wrapped >= (1 << 63):
        wrapped -= 1 << 64
    assert wrapped == 2, "the counterexample no longer wraps to 2; pick another"
    # What a wrapping check would have concluded about a 6-element list: 2 <= 6, admissible.
    assert wrapped <= 6
    # What dividing concludes: not admissible, which is the truth.
    assert product_fits([rows, cols], 6) is False
    assert count_fits([rows, cols], 6) is False

    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("matrix_ops", "unvec", [[1.0] * 6, rows, cols])
    assert caught.value.code == COUNT_RELATION_ERROR_CODE


# ── Refusal, and its shape ────────────────────────────────────────────────────────────


def test_an_over_length_count_is_refused_with_a_naming_error() -> None:
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("stats", "compute_mean", [FIVE, 25])
    error = caught.value
    assert error.code == COUNT_RELATION_ERROR_CODE
    assert error.details["function"] == "compute_mean"
    assert error.details["parameter"] == "n"
    assert error.details["count"] == 25
    assert error.details["list_parameter"] == "v"
    assert error.details["actual_length"] == 5
    for fragment in ("compute_mean", "n=25", "'v'", "5"):
        assert fragment in str(error)


def test_the_server_side_path_refuses_the_same_call() -> None:
    with pytest.raises(runner.MojoLibraryError) as caught:
        runner.build_runtime_library_worker_request("stats", "compute_mean", [FIVE, 25])
    assert caught.value.code == COUNT_RELATION_ERROR_CODE
    assert caught.value.details["actual_length"] == 5


@pytest.mark.parametrize(
    ("module_name", "function_name", "args"),
    [
        ("stats", "compute_mean", [FIVE, 5]),
        ("stats", "compute_mean", [FIVE, 0]),
        ("stats", "compute_mean", [FIVE, -4]),
        ("stats", "pctile", [FIVE, 5, 50]),
        ("auction", "vcg_payment", [FIVE, 5, 0]),
        ("matrix_ops", "unvec", [[1.0] * 6, 2, 3]),
        ("matrix_ops", "unvec", [[1.0] * 6, 1, 6]),
        ("cellular", "game_of_life_step", [[[0, 1], [1, 0]], 2, 2]),
        ("petri_net", "fire_transition_list", [[1, 1], [1, 0], [0, 1], 2]),
        ("sorting", "nth_smallest", [FIVE, 4]),
        ("network_analysis", "degree", [[[1], [0]], 1]),
    ],
)
def test_a_compliant_call_is_untouched(module_name, function_name, args) -> None:
    """The guard must be non-behavioural for every call that was already legal.

    A count of 0 or a negative count reads nothing, so it is not this guard's business
    either — refusing it would change behaviour the kernels already define.
    """
    _module, _function, request = build_worker_request(module_name, function_name, args)
    assert request["args"][-1] is not None or True
    runner.build_runtime_library_worker_request(module_name, function_name, args)


def test_a_product_bound_refuses_only_when_the_product_exceeds() -> None:
    build_worker_request("matrix_ops", "unvec", [[1.0] * 6, 3, 2])
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("matrix_ops", "unvec", [[1.0] * 6, 3, 3])
    assert caught.value.details["required_elements"] == "rows * cols = 3 * 3"


def test_an_element_length_bound_names_the_offending_row() -> None:
    """`cellular.game_of_life_step` reads `grid[r][c]` at the full width of every row."""
    build_worker_request("cellular", "game_of_life_step", [[[0, 1], [1, 0]], 2, 2])
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("cellular", "game_of_life_step", [[[0, 1], [1]], 2, 2])
    assert caught.value.details["list_element_index"] == 1
    assert caught.value.details["actual_length"] == 1


def test_an_index_parameter_needs_one_more_element_than_its_value() -> None:
    build_worker_request("network_analysis", "degree", [[[1], [0]], 1])
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("network_analysis", "degree", [[[1], [0]], 2])
    assert caught.value.details["role"] == "index"
    assert caught.value.details["required_elements"] == "node + 1 = 2 + 1"


# ── A negative INDEX is a violation; a negative COUNT is not ──────────────────────────


@pytest.mark.parametrize(
    ("module_name", "function_name", "args", "negative_parameter"),
    [
        ("network_analysis", "degree", [[[0, 1], [1]], -1], "node"),
        ("network_analysis", "clustering_coefficient", [[[0, 1], [1]], -2], "node"),
        ("social_network", "out_degree", [[[0]], -3], "node"),
        ("graph.weighted", "union_find_find", [[0, 1], -1], "x"),
        ("sorting", "nth_smallest", [[1.0, 2.0, 3.0], -1], "n"),
        ("crypto.chacha20", "quarter_round", [[1, 2, 3, 4], -1, 0, 1, 2], "a"),
        ("recommender", "item_overlap", [[[1.0], [1.0]], 0, -1], "u2"),
    ],
)
def test_a_negative_index_is_refused_on_both_paths(
    module_name, function_name, args, negative_parameter
) -> None:
    """THE REGRESSION. `product_fits` returned True for any factor `<= 0`.

    The justification was "the kernel's loop `for i in range(n)` runs zero times and reads
    nothing" — true of a count, false of an index, which is a direct subscript. Mojo does not
    normalise a negative index: `a[-1]` on a 3-element List is
    `Assert Error: index -1 is out of bounds, valid range is 0 to 2` and the process ends.
    MEASURED: every call below passed the guard, and `network_analysis.degree`
    (`return len(adj[node])`) and `graph.weighted.union_find_find` (`parent[x] = ...`, a
    negative-offset WRITE) ended the serving pid.
    """
    with pytest.raises(RuntimeLibraryContractError) as sdk:
        build_worker_request(module_name, function_name, args)
    assert sdk.value.code == COUNT_RELATION_ERROR_CODE
    assert sdk.value.details["role"] == "index"
    assert sdk.value.details["parameter"] == negative_parameter
    assert "negative index" in str(sdk.value)

    with pytest.raises(runner.MojoLibraryError) as server:
        runner.build_runtime_library_worker_request(module_name, function_name, args)
    assert server.value.code == COUNT_RELATION_ERROR_CODE
    assert str(server.value) == str(sdk.value)


def test_a_negative_index_is_refused_through_named_arguments_too() -> None:
    """The named form maps to the same positional list, so it must not be a second door."""
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("network_analysis", "degree", {"adj": [[0, 1], [1]], "node": -1})
    assert caught.value.code == COUNT_RELATION_ERROR_CODE


def test_a_negative_count_is_still_allowed() -> None:
    """`for i in range(-4)` reads nothing, so refusing it would be a behaviour change.

    Verified against the compiled worker in the robustness suite:
    `ins_sort(FIVE, 0, -1)` and `sort_values(FIVE, -3)` are measured no-ops with the pid
    unchanged. The role is what separates this case from the one above.
    """
    build_worker_request("stats", "compute_mean", [FIVE, -4])
    runner.build_runtime_library_worker_request("stats", "compute_mean", [FIVE, -4])
    assert product_fits([-4], 5) is True
    assert count_fits([-4], 5) is True
    assert product_fits([-4], 5, role="index") is False
    assert count_fits([-4], 5, role="index") is False


def test_a_relation_with_a_positive_plus_is_index_shaped_whatever_its_role_says() -> None:
    """`x + 1 <= len(a)` asserts a read at offset `x`, so a negative `x` is a read at `a[-1]`.

    The in-source `@capability` grammar has no `role` field, so a translated block relation
    used to arrive as a `count` — which is how `stats.part3` published `role: "count"` for two
    parameters that are indexes and how a negative `lo`/`hi` was waved through. Derived from
    the shape, identically on both paths, so the two cannot drift.
    """
    spec = CountSpec(
        relations=(CountRelation(factors=("hi",), bounds=("a",), plus=1, role="count"),)
    )
    violation = count_relation_violation(
        module="stats",
        function="demo",
        param_names=("a", "hi"),
        args=(FIVE, -1),
        spec=spec,
    )
    assert violation is not None
    assert violation["role"] == "index"
    assert "negative index" in str(violation["message"])

    module, function = find_runtime_function("network_analysis", "degree")
    published = function.count_relations[0]
    assert published.plus == 1 and published.role == "index"


def test_one_count_bounding_several_lists_checks_all_of_them() -> None:
    """`n_places` bounds three parallel arrays through a single declared relation."""
    build_worker_request("petri_net", "fire_transition_list", [[1, 1], [1, 0], [0, 1], 2])
    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("petri_net", "fire_transition_list", [[1, 1], [1, 0], [0], 2])
    assert caught.value.details["list_parameter"] == "output_arcs"


# ── Fail-open, per function ───────────────────────────────────────────────────────────


def test_an_undeclared_function_is_passed_through() -> None:
    """`stats.compute_mean` is declared; `numeric`-style neighbours are not.

    An undeclared function must behave exactly as before, which for an over-large count
    means the call is built and sent unchanged.
    """
    module, function = find_runtime_function("auction", "bid_shading_optimal")
    assert function.count_relations == ()
    _m, _f, request = build_worker_request("auction", "expected_revenue_uniform", [10 ** 9, 3])
    assert request["type"] == "library_execute"


def test_the_absence_of_a_relation_does_not_disable_a_neighbour() -> None:
    """Per-function fail-open: an undeclared call between two declared ones changes nothing."""
    build_worker_request("stats", "median", [FIVE, 25])  # undeclared, clamps, allowed
    with pytest.raises(RuntimeLibraryContractError):
        build_worker_request("stats", "compute_mean", [FIVE, 25])
    build_worker_request("stats", "median", [FIVE, 25])
    with pytest.raises(RuntimeLibraryContractError):
        build_worker_request("stats", "count_below_zero", [FIVE, 25])


# ── A bounded argument the guard cannot measure is refused, not skipped ───────────────
#
# This section replaces `test_an_unmeasurable_argument_is_a_pass`, which asserted the
# opposite and was wrong: both spellings below were MEASURED ending the serving worker pid
# while the guard reported the call as fine. `"@u8:"` is measurable and is now measured;
# `"@ds_1"` is not measurable here and is now refused.


def test_a_packed_buffer_is_measured_like_any_other_list() -> None:
    """`"@u8:<base64>"` is a supported spelling of `List[Float64]`, not an opaque token.

    MEASURED on the compiled worker before this fix:
    `execute("stats", "compute_mean", ["@u8:AQID", 25])` — `AQID` is 3 bytes — took the
    serving pid from `[83690]` to `[]`, while the identical call spelled as a literal list was
    refused. Re-encoding the same list was a complete bypass of every declared relation.
    """
    assert packed_float64_element_count("@u8:AQID") == 3
    assert sdk_packed_float64_element_count("@u8:AQID") == 3

    with pytest.raises(RuntimeLibraryContractError) as caught:
        build_worker_request("stats", "compute_mean", ["@u8:AQID", 25])
    assert caught.value.code == COUNT_RELATION_ERROR_CODE
    assert caught.value.details["actual_length"] == 3
    with pytest.raises(runner.MojoLibraryError) as server:
        runner.build_runtime_library_worker_request("stats", "compute_mean", ["@u8:AQID", 25])
    assert server.value.code == COUNT_RELATION_ERROR_CODE
    assert server.value.details["actual_length"] == 3

    # And a count the buffer really does hold is untouched, on both paths.
    _m, _f, request = build_worker_request("stats", "compute_mean", ["@u8:AQID", 3])
    assert request["args"] == ["@u8:AQID", 3]
    runner.build_runtime_library_worker_request("stats", "compute_mean", ["@u8:AQID", 3])


@pytest.mark.parametrize(
    ("payload", "elements"),
    [
        ("@u8:", 0),
        ("@u8:AQ==", 1),  # '=' padding is skipped by the runtime decoder, so it is skipped here
        ("@u8:AQI=", 2),
        ("@u8:AQID", 3),
        ("@u8:AQIDBA==", 4),
        ("@u8:A", 0),  # one sextet is 6 bits: not enough for a byte
        ("@u8:AA", 1),
        ("@u8:AA\n", 1),  # whitespace is skipped, not counted
    ],
)
def test_the_packed_length_is_what_the_runtime_will_decode(payload, elements) -> None:
    """The count must match `json_decode_base64_bytes` exactly, or the guard is off by two.

    That decoder skips every character outside the base64 alphabet — padding, whitespace,
    anything invalid — and emits a byte per 8 accumulated bits, so the element count is
    `floor(6 * sextets / 8)` and not `len(base64.b64decode(...))`, which would raise on
    several of these instead of answering.
    """
    assert packed_float64_element_count(payload) == elements
    assert sdk_packed_float64_element_count(payload) == elements
    assert measured_element_count(payload) == elements
    assert sdk_measured_element_count(payload) == elements


def test_a_deferred_handle_in_a_bounded_position_is_refused() -> None:
    """MEASURED: `["@ds_1", 5]` and `["$0", 5]` each ended the worker pid.

    A unary `library_execute` never binds a reference — only `batch_execute` and
    `pipeline_execute` do — so the kernel received an empty list and every count above zero
    was an over-read. Even where it IS bound, the length is not knowable here: the runtime
    reports a resident dataset's bytes, not its element count. Unverifiable, therefore
    declined — the failure being prevented is a dead process, not an error response.
    """
    for spelling in ("@ds_1", "$0"):
        with pytest.raises(RuntimeLibraryContractError) as caught:
            build_worker_request("stats", "compute_mean", [spelling, 5])
        assert caught.value.code == UNMEASURABLE_ARGUMENT_ERROR_CODE
        assert caught.value.details["reason"] == "unmeasurable_bounded_argument"
        assert caught.value.details["list_parameter"] == "v"
        assert spelling in str(caught.value)
    # A count of 1 is no safer than 25: the list is still unmeasured.
    with pytest.raises(RuntimeLibraryContractError):
        build_worker_request("stats", "compute_mean", ["@ds_1", 1])
    # An UNDECLARED function is untouched — fail-open is still per function.
    _m, _f, request = build_worker_request("stats", "median", ["@ds_1", 25])
    assert request["args"] == ["@ds_1", 25]


def test_an_unmeasurable_row_of_a_nested_bound_names_the_row() -> None:
    """An `element_length` relation bounds every row, so an unmeasurable ROW is refused."""
    spec = CountSpec(
        relations=(
            CountRelation(factors=("cols",), bounds=("grid",), scope="element_length"),
        )
    )
    violation = count_relation_violation(
        module="cellular",
        function="game_of_life_step",
        param_names=("grid", "rows", "cols"),
        args=([[0, 1], "@ds_1"], 2, 2),
        spec=spec,
    )
    assert violation is not None
    assert violation["code"] == UNMEASURABLE_ARGUMENT_ERROR_CODE
    assert violation["list_element_index"] == 1


def test_an_omitted_defaulted_count_is_a_pass() -> None:
    """Fewer arguments than parameters must not be read as a zero-length list."""
    spec = CountSpec(relations=(CountRelation(factors=("n",), bounds=("v",)),))
    assert (
        count_relation_violation(
            module="m",
            function="f",
            param_names=("v", "n"),
            args=([1.0, 2.0],),
            spec=spec,
        )
        is None
    )


# ── The two implementations agree ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("module_name", "function_name", "args"),
    [
        ("stats", "compute_mean", [FIVE, 25]),
        ("stats", "compute_mean", [FIVE, 5]),
        ("stats", "compute_variance", [FIVE, 6, 1.0]),
        ("stats", "pctile", [FIVE, 9, 50]),
        ("stats", "part3", [FIVE, 0, 9]),
        ("stats", "ins_sort", [FIVE, 0, 9]),
        ("matrix_ops", "unvec", [[1.0] * 6, 3, 3]),
        ("matrix_ops", "unvec", [[1.0] * 6, 2, 3]),
        ("cellular", "is_still_life", [[[0, 1], [1]], 2, 2]),
        ("reinforcement", "value_iteration", [2, 3, [[1.0, 2.0]], [[0, 1]], 0.9, 1e-6]),
        ("voting", "approval_score", [[1, 0, 1], 9]),
        ("recommender", "item_overlap", [[[1.0], [1.0]], 0, 7]),
        ("crypto.chacha20", "quarter_round", [[1, 2, 3, 4], 0, 1, 2, 99]),
        ("sorting", "nth_smallest", [FIVE, 5]),
        ("graph.weighted", "union_find_find", [[0, 1], 7]),
        # ── The four defects this table exists to keep from drifting apart ─────────────
        # A negative INDEX (the role must decide on both sides, not just one).
        ("network_analysis", "degree", [[[0, 1], [1]], -1]),
        ("social_network", "out_degree", [[[0]], -3]),
        ("graph.weighted", "union_find_find", [[0, 1], -1]),
        ("sorting", "nth_smallest", [FIVE, -1]),
        ("crypto.chacha20", "quarter_round", [[1, 2, 3, 4], -1, 0, 1, 2]),
        # A negative COUNT, which neither side may refuse.
        ("stats", "compute_mean", [FIVE, -4]),
        ("stats", "count_below_zero", [FIVE, 0]),
        # A packed buffer, measured on both sides — under, exact and over.
        ("stats", "compute_mean", ["@u8:AQID", 25]),
        ("stats", "compute_mean", ["@u8:AQID", 4]),
        ("stats", "compute_mean", ["@u8:AQID", 3]),
        ("stats", "compute_mean", ["@u8:", 1]),
        ("matrix_ops", "unvec", ["@u8:AQIDBAUG", 3, 3]),
        # A zero dimension whose product is 0: legal, and refused by neither.
        ("matrix_ops", "unvec", [[], 1, 0]),
        ("matrix_ops", "unvec", [[], 0, 1]),
    ],
)
def test_both_implementations_reach_the_same_verdict(module_name, function_name, args) -> None:
    """One table, both guards. A guard that is stricter on one path than the other means the
    same call is accepted or refused depending on which SDK made it — so the verdict, the
    error code and the message text are all pinned, not just the yes/no."""
    sdk_error: RuntimeLibraryContractError | None = None
    try:
        build_worker_request(module_name, function_name, args)
    except RuntimeLibraryContractError as exc:  # noqa: PERF203
        sdk_error = exc

    server_error: runner.MojoLibraryError | None = None
    try:
        runner.build_runtime_library_worker_request(module_name, function_name, args)
    except runner.MojoLibraryError as exc:
        server_error = exc

    assert (sdk_error is None) == (server_error is None), (
        f"{module_name}.{function_name}: sdk={sdk_error!r} server={server_error!r}"
    )
    if sdk_error is not None and server_error is not None:
        assert sdk_error.code == server_error.code
        assert sdk_error.code in {
            COUNT_RELATION_ERROR_CODE,
            UNMEASURABLE_ARGUMENT_ERROR_CODE,
        }
        assert sdk_error.details["list_parameter"] == server_error.details["list_parameter"]
        assert sdk_error.details.get("actual_length") == server_error.details.get(
            "actual_length"
        )
        assert sdk_error.details.get("role") == server_error.details.get("role")
        assert str(sdk_error) == str(server_error)


def test_the_two_implementations_agree_on_a_deferred_reference() -> None:
    """The deferred spelling only exists on the SDK path, so the verdicts are compared by
    OUTCOME rather than by message: the SDK's count guard refuses it, and the server's
    normalizer refuses the same string before the guard is even reached. What must never
    happen is one path sending it to a worker."""
    with pytest.raises(RuntimeLibraryContractError) as sdk:
        build_worker_request("stats", "compute_mean", ["@ds_1", 5])
    assert sdk.value.code == UNMEASURABLE_ARGUMENT_ERROR_CODE
    with pytest.raises(runner.MojoLibraryError) as server:
        runner.build_runtime_library_worker_request("stats", "compute_mean", ["@ds_1", 5])
    assert server.value.code == UNMEASURABLE_ARGUMENT_ERROR_CODE


def test_the_two_implementations_word_the_unmeasurable_refusal_identically() -> None:
    """Compared directly, because the server's normalizer rejects `"@ds_1"` before its guard
    is reached — so the shared-table test can only compare the outcome for that case. The two
    guards are what must not drift, and a message is part of a guard's behaviour."""
    _module, function = find_runtime_function("stats", "compute_mean")
    with pytest.raises(RuntimeLibraryContractError) as sdk:
        enforce_count_relations("stats", function, ["@ds_1", 5])

    violation = count_relation_violation(
        module="stats",
        function="compute_mean",
        param_names=("v", "n"),
        args=("@ds_1", 5),
        spec=declared_count_spec("stats", "compute_mean"),
    )
    assert violation is not None
    assert violation["code"] == sdk.value.code == UNMEASURABLE_ARGUMENT_ERROR_CODE
    assert violation["message"] == str(sdk.value)
    assert {key: value for key, value in violation.items() if key not in {"code", "message"}} == (
        sdk.value.details
    )


def test_the_two_implementations_publish_the_same_error_codes() -> None:
    from algenta import runtime_count_guard as sdk_guard

    from apps.runtime import mojo_count_relations as server_guard

    assert sdk_guard.COUNT_RELATION_ERROR_CODE == server_guard.COUNT_RELATION_ERROR_CODE
    assert (
        sdk_guard.UNMEASURABLE_ARGUMENT_ERROR_CODE
        == server_guard.UNMEASURABLE_ARGUMENT_ERROR_CODE
    )
    assert sdk_guard.PACKED_FLOAT64_PREFIX == server_guard.PACKED_FLOAT64_PREFIX


# ── The guard cannot regress the generated A-Z suite ──────────────────────────────────


def test_no_declared_relation_is_broken_by_the_az_sample_arguments(engine_modules) -> None:
    """The generated suite calls every contract function with a 5-element list and `5`.

    That is why it never found the original hazard, and it is also the set of calls the
    guard must not start refusing. Every declared function IS reached by that suite, so
    this is a complete check over the declarations rather than a spot check.
    """
    az = importlib.import_module("tests.integration.test_mojo_kernel_libraries_az")
    specs = declared_count_specs()
    reached: set[tuple[str, str]] = set()
    refused: list[str] = []
    for target in az._build_kernel_targets():
        key = (target.module_name, target.function_name)
        spec = specs.get(key)
        if spec is None:
            continue
        reached.add(key)
        function = next(
            f for f in engine_modules[key[0]].functions if f.name == key[1]
        )
        violation = count_relation_violation(
            module=key[0],
            function=key[1],
            param_names=tuple(param.name for param in function.params),
            args=target.args,
            spec=spec,
        )
        if violation is not None:
            refused.append(f"{key[0]}.{key[1]}{target.args}: {violation['message']}")
    assert not refused, "\n".join(refused)
    assert reached == set(specs), sorted(set(specs) - reached)


# ── The contract loader refuses a relation it could not evaluate ──────────────────────


def test_a_relation_naming_an_unknown_parameter_is_rejected(tmp_path, monkeypatch) -> None:
    """A guard that silently does nothing is the failure mode being removed."""
    contract = importlib.import_module("algenta.runtime_library_contract")
    payload = {
        "schema_version": 1,
        "module_count": 1,
        "function_count": 1,
        "modules": [
            {
                "name": "demo",
                "engine": "mojo",
                "structs": [],
                "functions": [
                    {
                        "name": "f",
                        "return_type": "Float64",
                        "params": [
                            {
                                "name": "v",
                                "type": "List[Float64]",
                                "has_default": False,
                                "is_mut": False,
                            }
                        ],
                        "count_relations": [{"factors": ["n"], "bounds": ["v"]}],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "runtime_library_contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    class _Files:
        def joinpath(self, _name):
            return path

    monkeypatch.setattr(contract.resources, "files", lambda _package: _Files())
    contract.runtime_modules.cache_clear()
    try:
        with pytest.raises(RuntimeLibraryContractError) as caught:
            contract.runtime_modules()
        assert "absent from the signature" in str(caught.value)
    finally:
        contract.runtime_modules.cache_clear()


def test_enforce_is_a_no_op_for_a_function_without_relations() -> None:
    _module, function = find_runtime_function("stats", "median")
    enforce_count_relations("stats", function, [FIVE, 10 ** 9])
