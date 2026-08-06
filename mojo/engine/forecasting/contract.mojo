"""
forecasting.contract — the package's single vocabulary. Zero Python imports.

Everything in `forecasting/` reaches its status codes, its ceilings, its definition of
"finite", its tolerance builder and its empirical quantile through THIS file. Rule 3 applies
inside a package: `optimization/` shipped `_finite` six times byte-identical, `_round_f`
three times with only one copy avoiding the hazard it documented, and one input invariant
enforced at three strengths under three status codes. A duplicated guard reads as
defence-in-depth while providing one arbitrary behaviour per call site.

STATUS CODE RANGE: 300-319, all twenty allocated below, and this package uses no other
range. Rule 4e: `optimization.integer` and `optimization.explain` independently claimed
80-84, so `milp_status_name(81)` was "node_limit" while `explain_status_name(81)` was
"feasible_so_there_is_no_infeasibility_core" — one integer, two meanings, one package, and
a logged code that nothing could disambiguate. There is exactly one `fc_status_name` here
and no per-file table anywhere in `forecasting/`.

The tolerance rule, spelled out because it has recurred five times in this tree
--------------------------------------------------------------------------------
`fc_tolerance(quantity, abs_tol)` is `abs_tol + FC_TOL_SLACK * DBL_EPSILON * |quantity|`,
where `quantity` is THE ONE NUMBER BEING JUDGED and nothing else.

  * It is NOT `1 + |quantity|`. A "relative" tolerance floored at 1.0 is an ABSOLUTE
    allowance of one whole unit whenever the real scale is small — measured elsewhere in
    this tree as a resource limit that permitted one unit of overload.
  * The relative multiplier is `DBL_EPSILON`, never the caller's tolerance. Sizing the
    relative term by `abs_tol` turned a measured gap of 400,000,000 into `at_optimum = True`.
  * `quantity` is never a sum or a max over OTHER items. `feas_tol * (1 + sum_i |b_i|)` let
    200 ordinary capacity rows swallow a flat contradiction and returned LP_OPTIMAL with
    duals and a basis for an infeasible program; a pivot tolerance scaled by the largest
    diagonal of the whole matrix accepted an eigenvalue of -0.68 as convex. `max` looks
    per-item and is not.

There is exactly one place in this package where the judged quantity is ITSELF an aggregate:
`hierarchy`'s coherence residual `parent - sum(children)`. The rounding bound for that
difference legitimately involves the magnitudes of the terms that FORM it, and only those —
`|parent| + sum_j |child_j|` over that parent's own children, never another parent's. That
distinction is the whole content of the rule, so it is stated at the call site too.

`FC_TOL_SLACK = 64` is a rounding-accumulation allowance, not a fudge factor: the longest
chain judged here is a per-cell difference of two values each formed by a handful of
multiply-adds, and 64 ulps covers it with room. Raising it would be a behaviour change and
is not the way to make a failing comparison pass.

The horizon is bounded by the PAYLOAD, not only by a ceiling
------------------------------------------------------------
Rule 1c: a dimension inside the allocation ceiling can still be tied to nothing in the
request. `linear.lp_from_arenas` took `n_vars` as a bare `Int` and materialised ~200 bytes
per variable regardless of how many variables the arena actually referenced — 3.50 GB from
a ~60-byte request. So `fc_horizon_defect` bounds `horizon` against `MAX_FC_HORIZON` AND
against `n_obs`: a request to forecast 500 steps from 5 observations is refused, because
there is no evidence in the payload for step 6 and there is certainly no way to backtest it.
That is also the Rule-4 half of the same check — "a forecast horizon longer than the data
can support has no answer; do not extrapolate silently".

Reads past a List end are UNCATCHABLE
-------------------------------------
Every driver in this package derives its element counts from `len(...)` rather than taking a
redundant count parameter, which removes the entire `n > len(v)` class by construction. The
`Int` parameters that remain are DIMENSIONS — `horizon`, `period`, `min_train`, `step`,
`ar_order`, `n_origins`, `n_nodes`, `n_draws` — and each is validated here or at its call
site before anything is indexed. The generated A-Z suite calls every contract function with
a five-element list and `5` for every `Int`, so `n <= len(v)` always holds there and that
harness structurally cannot find a bounds bug; the guards are written for the caller, not
for the harness.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, ceil, isinf, isnan

from risk import value_at_risk
from series import exponential_forecast
from sparse_numerics.csr import MAX_CSR_DIM, dims_fit

# ── status codes: 300-319, this package's entire allocation ────────────────────

comptime FC_OK: Int = 300
comptime FC_ERR_EMPTY_SERIES: Int = 301
comptime FC_ERR_NON_FINITE: Int = 302
comptime FC_ERR_DIMENSION_TOO_LARGE: Int = 303
comptime FC_ERR_LENGTH_MISMATCH: Int = 304
comptime FC_ERR_HORIZON: Int = 305
comptime FC_ERR_INSUFFICIENT_HISTORY: Int = 306
comptime FC_ERR_PARAM_RANGE: Int = 307
comptime FC_ERR_PERIOD: Int = 308
comptime FC_ERR_NO_ORIGINS: Int = 309
comptime FC_ERR_WORK_BUDGET: Int = 310
comptime FC_ERR_METHOD: Int = 311
comptime FC_ERR_NEGATIVE_VALUES: Int = 312
comptime FC_ERR_NO_DEMAND: Int = 313
comptime FC_ERR_HIERARCHY_SHAPE: Int = 314
comptime FC_ERR_INCOHERENT: Int = 315
comptime FC_ERR_NO_RESIDUALS: Int = 316
comptime FC_ERR_LEVEL_RANGE: Int = 317
comptime FC_ERR_SEED_RANGE: Int = 318
comptime FC_ERR_ALL_UNDEFINED: Int = 319

# ── method ids: ONE table, THREE non-overlapping ranges ───────────────────────
#
# `point`, `intermittent` and `backtest` all name methods from this block. Two files
# numbering their own methods would repeat rule 4e one level down: a `method_id` logged
# beside a `BacktestReport` has to mean the same thing as one passed to a single-forecast
# driver, and only a shared table makes that true. Ids are append-only — a stored report
# names its method by number, so renumbering would silently relabel history.
#
# THE RANGES, and the collision that made them necessary
# ------------------------------------------------------
# `method_id` is a bare `Int` field in three different structs — `PointForecast.method_id`,
# `IntervalBand.method_id`, `Reconciliation.method_id` — and `interval` and `hierarchy` each
# used to allocate 0 and 1 for their own two methods, in their own files. `0` therefore meant
# `naive point forecast`, `empirical interval` AND `bottom-up reconciliation` at once, and `1`
# meant `drift`, `bootstrap interval` and `top-down`. Inside this package the Mojo type
# disambiguates them; a caller holding a bare id, a stored report, or a flat
# `"method_id": 0` on a wire has nothing to disambiguate with, and neither does a log line
# with two of them side by side. That is the same defect as `optimization`'s `81` meaning two
# things in one package, one level down.
#
# So the three vocabularies get three DISJOINT ranges, allocated here and nowhere else,
# exactly as the status ranges are (`forecasting` owns 300-319, `inference` 320-339,
# `retrieval` 200-219):
#
#     0-10     point / intermittent / backtest forecasting methods   FC_METHOD_*
#     100-101  prediction-interval constructions                     FC_INTERVAL_*
#     200-201  hierarchical reconciliations                          HIER_*
#
# EVERY code inside every one of those spans is assigned and named by `fc_method_name`, which
# the suite verifies by walking each span rather than by trusting this comment; the gaps
# BETWEEN the spans are unassigned on purpose and are the room to append. `fc_method_family`
# maps an id back to which of the three vocabularies it belongs to, so a bare number can be
# interpreted without knowing which struct it came out of — which is the property that was
# missing. The forecasting ids keep their existing numbers because they are already in stored
# reports; only the two files that had collided with them move.

comptime FC_METHOD_NAIVE: Int = 0
comptime FC_METHOD_DRIFT: Int = 1
comptime FC_METHOD_MEAN: Int = 2
comptime FC_METHOD_SEASONAL_NAIVE: Int = 3
comptime FC_METHOD_ETS_ANN: Int = 4
comptime FC_METHOD_ETS_AAN: Int = 5
comptime FC_METHOD_ETS_AAA: Int = 6
comptime FC_METHOD_THETA: Int = 7
comptime FC_METHOD_THETA_DRIFT: Int = 8
comptime FC_METHOD_AR: Int = 9
comptime FC_METHOD_CROSTON: Int = 10
comptime FC_METHOD_MIN: Int = 0
comptime FC_METHOD_MAX: Int = 10

# The interval range. `interval.interval_empirical_flat` / `interval_bootstrap_flat` set
# these into `IntervalBand.method_id`; they are NOT point-forecast methods and cannot be
# passed to `point.forecast_flat` or `backtest.backtest_flat`, which refuse anything above
# `FC_METHOD_MAX` with FC_ERR_METHOD.
comptime FC_INTERVAL_EMPIRICAL: Int = 100
comptime FC_INTERVAL_BOOTSTRAP: Int = 101
comptime FC_INTERVAL_METHOD_MIN: Int = 100
comptime FC_INTERVAL_METHOD_MAX: Int = 101

# The reconciliation range. `hierarchy.reconcile_flat` DISPATCHES on these, so the range also
# fixes what that driver accepts: a forecasting id or an interval id reaching it is
# FC_ERR_METHOD rather than a silent bottom-up run, which is what `method_id = 0` used to be.
comptime HIER_BOTTOM_UP: Int = 200
comptime HIER_TOP_DOWN: Int = 201
comptime HIER_METHOD_MIN: Int = 200
comptime HIER_METHOD_MAX: Int = 201

# The three family labels `fc_method_family` returns, so a caller compares against a name
# from here rather than a string literal it typed itself.
comptime FC_FAMILY_FORECAST: String = "forecast"
comptime FC_FAMILY_INTERVAL: String = "interval"
comptime FC_FAMILY_RECONCILIATION: String = "reconciliation"
comptime FC_FAMILY_UNKNOWN: String = "unknown"

# ── tolerance constants ───────────────────────────────────────────────────────

comptime FC_DBL_EPSILON: Float64 = 2.220446049250313e-16
comptime FC_TOL_SLACK: Float64 = 64.0

# ── ceilings, with the allocation arithmetic stated ───────────────────────────
#
# `MAX_CSR_DIM` (1 << 26) is the tree's ONE shared dimension ceiling and is never redefined
# or moved here: it is justified in `sparse_numerics/csr.mojo` as the point at which a
# single row-pointer array reaches the ~512 MB resident-dataset budget FOR ONE OBJECT. Rule
# 1c: a driver that allocates k arrays of that length is bounded at k x 512 MB, so every
# ceiling below is scaled down by the number of arrays the entry points here actually
# allocate per unit. Each is asserted to be at or below MAX_CSR_DIM by `fc_ceilings`.

# One observation array is 8 bytes; 1 << 22 obs = 33.6 MB. `point.deseasonalise_flat` is the
# widest series-length allocator here: trend, detrended, interior, raw indices, adjusted and
# the returned copy = 6 arrays = 201 MB. Under the 512 MB budget with room.
comptime MAX_FC_SERIES: Int = 1 << 22

# A forecast array is `horizon` doubles; 1 << 16 = 512 KB. The real bound on `horizon` is
# `n_obs` (see `fc_horizon_defect`), which is what ties it to the payload.
comptime MAX_FC_HORIZON: Int = 1 << 16

# `n_origins * horizon` cells. 1 << 21 cells = 16.8 MB per array; `BacktestReport` holds
# forecast, actual and error at that length (50 MB) plus three arrays at `n_origins`
# (<= 50 MB more). ~100 MB worst case.
comptime MAX_FC_CELLS: Int = 1 << 21

# `hierarchy` allocates reconciled (bounded by MAX_FC_CELLS) plus is_leaf, child_total and
# a residual array at `n_nodes`: 3 x 8.4 MB at this ceiling.
comptime MAX_FC_NODES: Int = 1 << 20

# `arima.durbin_levinson` is O(p^2) in time and O(p) in space. 1024^2 = ~1M operations.
comptime MAX_FC_AR_ORDER: Int = 1 << 10

# `risk.value_at_risk` — this package's empirical quantile — sorts with `risk._sort_copy`,
# an INSERTION sort, so it is O(k^2). 4096^2 = 16.8M comparisons for one quantile. Memory
# would permit far more; this is a WORK bound, and bounding memory is not bounding work.
comptime FC_MAX_QUANTILE_SAMPLES: Int = 1 << 12

# Every factor that multiplies into a cost must be charged. `interval` computes two
# quantiles per horizon step over k samples each, so the charged product is
# `horizon * k * k` and it is formed by DIVISION, never by a wrapping multiply.
comptime FC_MAX_QUANTILE_WORK: Int = 1 << 28

# `backtest` refits per origin, so its cost is `n_origins * (train_len + horizon)` with
# `train_len <= n_obs`. Same division-based charge.
comptime FC_MAX_BACKTEST_WORK: Int = 1 << 28

# The seasonal decomposition is O(n_obs * period): `time_series_decompose.moving_average_trend`
# sums a `period`-wide window at every one of `n_obs` positions. BOUNDING MEMORY IS NOT BOUNDING
# WORK, and this is the one place in this package where a shape that passes every allocation
# ceiling still drives an unbounded number of operations: `fc_period_defect` only requires
# `n_obs >= 2 * period`, so `n_obs = 2^22` with `period = 2^21` is a STRUCTURALLY VALID request
# for 2^43 window additions — a hang, which from the caller's side is the same outcome as the
# uncatchable abort. 2^30 is about a second of window sums and admits every realistic pairing
# (100,000 daily points at period 365 is 3.65e7). Charged inside `fc_period_defect` so that the
# ONE definition of an admissible period owns it and no caller can forget.
comptime FC_MAX_SEASONAL_WORK: Int = 1 << 30

# Above this the `Int(...)` in `fc_min_samples_for_level` would be a conversion whose
# result nobody can use anyway; `Float64(Int(v))` past the integer grid is poison rather
# than truncation (rule 4c), so the guard runs BEFORE the conversion.
comptime FC_MAX_LEVEL_SAMPLES_F: Float64 = 1.0e9


def fc_status_name(code: Int) -> String:
    """Name for a status code, so an error surfaces the defect and not a bare number.

    THE one vocabulary for `forecasting/`. Every module's `status_name` field is filled from
    here; there is no second table.
    """
    if code == FC_OK:
        return "ok"
    if code == FC_ERR_EMPTY_SERIES:
        return "empty_series"
    if code == FC_ERR_NON_FINITE:
        return "non_finite_input"
    if code == FC_ERR_DIMENSION_TOO_LARGE:
        return "dimension_too_large"
    if code == FC_ERR_LENGTH_MISMATCH:
        return "length_mismatch"
    if code == FC_ERR_HORIZON:
        return "horizon_unsupported_by_data"
    if code == FC_ERR_INSUFFICIENT_HISTORY:
        return "insufficient_history"
    if code == FC_ERR_PARAM_RANGE:
        return "parameter_out_of_range"
    if code == FC_ERR_PERIOD:
        return "seasonal_period_invalid"
    if code == FC_ERR_NO_ORIGINS:
        return "no_complete_backtest_origin"
    if code == FC_ERR_WORK_BUDGET:
        return "work_budget_exceeded"
    if code == FC_ERR_METHOD:
        return "unknown_method"
    if code == FC_ERR_NEGATIVE_VALUES:
        return "negative_value_where_nonnegative_required"
    if code == FC_ERR_NO_DEMAND:
        return "no_positive_demand_observed"
    if code == FC_ERR_HIERARCHY_SHAPE:
        return "hierarchy_shape_invalid"
    if code == FC_ERR_INCOHERENT:
        return "cannot_reconcile_children_to_parent"
    if code == FC_ERR_NO_RESIDUALS:
        return "no_estimable_residual_set"
    if code == FC_ERR_LEVEL_RANGE:
        return "interval_level_out_of_range"
    if code == FC_ERR_SEED_RANGE:
        return "seed_or_stream_out_of_range"
    if code == FC_ERR_ALL_UNDEFINED:
        return "every_candidate_undefined"
    return "unknown"


def fc_method_name(method_id: Int) -> String:
    """Name for a method id — THE one table for all THREE method ranges in this package.

    Shared by `point`, `intermittent` and `backtest` (0-10), by `interval` (100-101) and by
    `hierarchy` (200-201). One table across the three ranges is the point: a name is what
    makes a bare id readable, and a second table per file is how the ranges drifted into
    collision in the first place.

    An unknown id is "unknown" rather than a default method. Falling back to naive would
    make a typo'd id return a plausible forecast under a success status, which is the
    `func_id` defect `optimization.model` exists to undo: every frozen objective table
    returns 0.0 for an unrecognised id, so a gradient method sees a zero gradient and
    reports converged on iteration 0.

    Every id inside each declared range has a name here; the numbers BETWEEN the ranges
    (11-99, 102-199, 202 and up) are unassigned and return "unknown", which the suite
    asserts in both directions.
    """
    if method_id == FC_METHOD_NAIVE:
        return "naive"
    if method_id == FC_METHOD_DRIFT:
        return "drift"
    if method_id == FC_METHOD_MEAN:
        return "window_mean"
    if method_id == FC_METHOD_SEASONAL_NAIVE:
        return "seasonal_naive"
    if method_id == FC_METHOD_ETS_ANN:
        return "ets_ann"
    if method_id == FC_METHOD_ETS_AAN:
        return "ets_aan_damped"
    if method_id == FC_METHOD_ETS_AAA:
        return "ets_aaa"
    if method_id == FC_METHOD_THETA:
        return "theta"
    if method_id == FC_METHOD_THETA_DRIFT:
        return "theta_drift"
    if method_id == FC_METHOD_AR:
        return "ar_yule_walker"
    if method_id == FC_METHOD_CROSTON:
        return "croston"
    if method_id == FC_INTERVAL_EMPIRICAL:
        return "interval_empirical"
    if method_id == FC_INTERVAL_BOOTSTRAP:
        return "interval_bootstrap"
    if method_id == HIER_BOTTOM_UP:
        return "reconcile_bottom_up"
    if method_id == HIER_TOP_DOWN:
        return "reconcile_top_down"
    return "unknown"


def fc_method_family(method_id: Int) -> String:
    """Which of the three method vocabularies `method_id` belongs to, or FC_FAMILY_UNKNOWN.

    THE reason the ranges are disjoint: a `method_id` read out of a stored report, a log line
    or a flat JSON field can be interpreted without knowing which struct produced it. Before
    the split this function could not have existed — 0 was a point method, an interval method
    and a reconciliation method simultaneously, so there was no function from id to family.

    Deterministic, allocation-free, and total: every `Int` maps to exactly one of the four
    labels, and the three real families are disjoint by construction because their spans are.
    """
    if method_id >= FC_METHOD_MIN and method_id <= FC_METHOD_MAX:
        return FC_FAMILY_FORECAST
    if method_id >= FC_INTERVAL_METHOD_MIN and method_id <= FC_INTERVAL_METHOD_MAX:
        return FC_FAMILY_INTERVAL
    if method_id >= HIER_METHOD_MIN and method_id <= HIER_METHOD_MAX:
        return FC_FAMILY_RECONCILIATION
    return FC_FAMILY_UNKNOWN


def fc_finite(v: Float64) -> Bool:
    """True for a real number: neither NaN nor +/-inf.

    THE single definition of "finite" for this package, public for exactly the reason
    `optimization.model_finite` is public — six private copies were six chances to drift.

    It also has to run BEFORE any tolerance is built from an input. With a NaN in hand,
    `tol = SLOP * (1 + nan)` is `nan`, every `fabs(d) > nan` is `False`, and an audit passes
    having counted zero violations — a certificate defeated silently by an unvalidated
    threshold.
    """
    return not isnan(v) and not isinf(v)


def fc_all_finite(values: List[Float64]) -> Bool:
    """True when every element is a real number. O(n)."""
    for i in range(len(values)):
        if not fc_finite(values[i]):
            return False
    return True


def fc_tolerance(quantity: Float64, abs_tol: Float64) -> Float64:
    """`abs_tol + FC_TOL_SLACK * DBL_EPSILON * |quantity|` — the module docstring's rule.

    `quantity` must be the magnitude of THE ONE NUMBER BEING JUDGED. Not `1 + |quantity|`
    (a 1.0 floor makes a "relative" test absolute at any small scale), not `abs_tol *
    |quantity|` (sizing the relative term by the caller's tolerance), and not an aggregate
    over other items.

    A non-finite `quantity` or `abs_tol` yields -1.0, which no comparison of the form
    `error > tol` can pass — the opposite of the NaN failure mode, where every comparison
    passes. Callers must still reject non-finite inputs; this is the second line only.
    """
    if not fc_finite(quantity) or not fc_finite(abs_tol) or abs_tol < 0.0:
        return -1.0
    return abs_tol + FC_TOL_SLACK * FC_DBL_EPSILON * fabs(quantity)


def fc_sum_tolerance(
    term_magnitude_sum: Float64, n_terms: Int, abs_tol: Float64
) -> Float64:
    """`abs_tol + DBL_EPSILON * (n_terms + 1) * term_magnitude_sum` — for a SUM's own residual.

    THE one place in this package where the judged quantity is itself an aggregate, and the
    only reason a second tolerance builder exists. `hierarchy` asks whether
    `parent - sum_j child_j` is zero. Floating-point addition is not associative, so that
    difference has a genuine rounding budget, and the budget of a `k`-term summation really
    does depend on the magnitudes of the `k` terms and on `k`.

    THIS IS NOT rule 4b's first spelling, and the difference is exactly what that rule is
    about. `term_magnitude_sum` must be `|parent| + sum_j |child_j|` over the terms that FORM
    THIS residual and nothing else — never over another parent's children, never over the whole
    hierarchy. The defect the rule names was `feas_tol * (1 + sum_i |b_i|)`, where the sum ran
    over every row in the model, so an unrelated row's magnitude paid for this row's
    contradiction. Here every term in the sum appears in the subtraction being judged.

    `fc_tolerance` is still the builder for every PER-ITEM comparison and this must not be used
    for one: `n_terms` would then be a fiction and the tolerance would widen for no reason.

    Non-finite or negative inputs give -1.0, which no `error > tol` test can pass.
    """
    if not fc_finite(term_magnitude_sum) or not fc_finite(abs_tol):
        return -1.0
    if abs_tol < 0.0 or term_magnitude_sum < 0.0 or n_terms < 0:
        return -1.0
    return abs_tol + FC_DBL_EPSILON * Float64(n_terms + 1) * term_magnitude_sum


def fc_ceilings() -> List[Int]:
    """The declared ceilings, in order, so a caller can size a request before making it.

    [MAX_FC_SERIES, MAX_FC_HORIZON, MAX_FC_CELLS, MAX_FC_NODES, MAX_FC_AR_ORDER,
     FC_MAX_QUANTILE_SAMPLES, FC_MAX_QUANTILE_WORK, FC_MAX_BACKTEST_WORK,
     FC_MAX_SEASONAL_WORK, MAX_CSR_DIM].

    The first SIX are dimension ceilings and the next THREE are WORK budgets, which is why the
    two groups are checked differently: `MAX_CSR_DIM` is last and is the tree's shared
    DIMENSION ceiling, reported rather than redefined, and the suite asserts every dimension
    ceiling here is at or below it — the machine-checkable form of the rule-1c arithmetic in the
    comments beside each constant. A work budget is a count of operations, not of allocated
    slots, so it is deliberately larger and comparing it against a dimension ceiling would be a
    category error.
    """
    var out = List[Int]()
    out.append(MAX_FC_SERIES)
    out.append(MAX_FC_HORIZON)
    out.append(MAX_FC_CELLS)
    out.append(MAX_FC_NODES)
    out.append(MAX_FC_AR_ORDER)
    out.append(FC_MAX_QUANTILE_SAMPLES)
    out.append(FC_MAX_QUANTILE_WORK)
    out.append(FC_MAX_BACKTEST_WORK)
    out.append(FC_MAX_SEASONAL_WORK)
    out.append(MAX_CSR_DIM)
    return out^


def fc_series_defect(y: List[Float64]) -> Int:
    """Validate an observation series: non-empty, all finite, within the series ceiling.

    The count comes from `len(y)`, so there is no count/list relation to declare and no way
    for a caller-supplied integer to walk off the end.

    @capability fc_series_defect
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(y)
    if n == 0:
        return FC_ERR_EMPTY_SERIES
    if n > MAX_FC_SERIES:
        return FC_ERR_DIMENSION_TOO_LARGE
    if not fc_all_finite(y):
        return FC_ERR_NON_FINITE
    return FC_OK


def fc_horizon_defect(n_obs: Int, horizon: Int) -> Int:
    """Validate a forecast horizon against the ceiling AND against the data behind it.

    Three refusals, in the order a caller most needs to distinguish:

      * `horizon <= 0` — there is nothing to forecast (FC_ERR_HORIZON).
      * `horizon > MAX_FC_HORIZON` — the allocation ceiling (FC_ERR_DIMENSION_TOO_LARGE).
      * `horizon > n_obs` — the PAYLOAD bound, and the Rule-4 one: a horizon longer than
        the record itself cannot be supported by the record and cannot be backtested at all
        (there is no origin with `horizon` actuals after it). Silently extrapolating it
        returns numbers where none exist, which is the failure this whole package is built
        against. FC_ERR_HORIZON.

    `n_obs <= 0` is FC_ERR_EMPTY_SERIES rather than a horizon defect, so a caller is not
    told the horizon is wrong when the series is the problem.
    """
    if horizon <= 0:
        return FC_ERR_HORIZON
    if horizon > MAX_FC_HORIZON:
        return FC_ERR_DIMENSION_TOO_LARGE
    if n_obs <= 0:
        return FC_ERR_EMPTY_SERIES
    if horizon > n_obs:
        return FC_ERR_HORIZON
    return FC_OK


def fc_period_defect(n_obs: Int, period: Int) -> Int:
    """Validate a seasonal period against the data length.

    `period < 1` is not a season. `period == 1` is "no seasonality" and is accepted by the
    callers that treat it as a no-op, so it is NOT refused here.

    A period needs at least one COMPLETE cycle of evidence inside the region where a
    centered moving average is defined. `time_series_decompose.moving_average_trend` leaves
    the first and last `period // 2` positions zero-padded, so the usable interior is
    `n_obs - 2 * (period // 2)` long and one full cycle requires
    `n_obs >= period + 2 * (period // 2)` — `2 * period` for an even period. Refusing
    anything shorter is what stops a seasonal index being estimated from the padding.

    THE WORK CHARGE LIVES HERE, and that is the point of putting it in the shared validator:
    the decomposition is O(n_obs * period) and the shape rule above admits `period` up to
    `n_obs / 2`, so a structurally valid request can ask for 2^43 operations. Charging it
    against `FC_MAX_SEASONAL_WORK` (by DIVISION, never by forming the product) in the ONE
    function that decides whether a period is admissible means `point.ets_aaa_forecast`,
    `point.deseasonalise_flat` and every backtest origin inherit it and none of them can
    forget it — one invariant, one place, one status.

    `backtest.backtest_flat` charges the SAME quantity again against the tighter
    `FC_MAX_BACKTEST_WORK`, and that is not the same invariant enforced at two strengths: a
    backtest performs the decomposition once per ORIGIN, so it is bounding a strictly larger
    amount of work and must be stricter. The check here is the per-decomposition bound.
    """
    if period < 1:
        return FC_ERR_PERIOD
    if period > MAX_FC_SERIES:
        return FC_ERR_DIMENSION_TOO_LARGE
    if n_obs <= 0:
        return FC_ERR_EMPTY_SERIES
    if period == 1:
        return FC_OK
    var half = period // 2
    if n_obs < period + 2 * half:
        return FC_ERR_PERIOD
    if not fc_work_fits(n_obs, period, FC_MAX_SEASONAL_WORK):
        return FC_ERR_WORK_BUDGET
    return FC_OK


def fc_smoothing_defect(alpha: Float64) -> Int:
    """Validate a smoothing weight: finite and in (0, 1].

    `alpha = 0` is refused rather than clamped: it means "never update", so the level stays
    at the first observation forever and the forecast is `y[0]` no matter how long the
    series is. That is a defensible recursion and an indefensible forecast, and no status
    would have said which one the caller got.
    """
    if not fc_finite(alpha):
        return FC_ERR_NON_FINITE
    if alpha <= 0.0 or alpha > 1.0:
        return FC_ERR_PARAM_RANGE
    return FC_OK


def fc_damping_defect(phi: Float64) -> Int:
    """Validate a trend damping factor: finite and in (0, 1].

    `phi = 1` is undamped Holt. `phi > 1` compounds the trend geometrically and is refused;
    `phi <= 0` inverts or annihilates it.
    """
    if not fc_finite(phi):
        return FC_ERR_NON_FINITE
    if phi <= 0.0 or phi > 1.0:
        return FC_ERR_PARAM_RANGE
    return FC_OK


def fc_level_defect(level: Float64) -> Int:
    """Validate a two-sided interval level: finite and strictly inside (0, 1).

    `level = 1` asks for a band containing every future value with certainty, which no
    finite residual sample can deliver; `level = 0` asks for a band of width zero.
    """
    if not fc_finite(level):
        return FC_ERR_NON_FINITE
    if level <= 0.0 or level >= 1.0:
        return FC_ERR_LEVEL_RANGE
    return FC_OK


def fc_cells_fit(rows: Int, cols: Int, length: Int) -> Bool:
    """True when `rows x cols` is exactly `length` cells AND inside this package's ceiling.

    Delegates the shape test to `sparse_numerics.csr.dims_fit`, which does it with a
    DIVISION. `rows * cols == length` is a wrapping 64-bit multiply and therefore not a
    bound at all — verified in that file as `3 * 6148914691236517206 == 2`, which walked
    straight past a product guard and crashed the process. Never re-derive this test.

    The extra condition here is rule 1c: `dims_fit` bounds each dimension by `MAX_CSR_DIM`,
    which is the budget for ONE object. `BacktestReport` and `Reconciliation` each hold
    three arrays of `rows * cols`, so the local ceiling is the smaller `MAX_FC_CELLS`.
    """
    if not dims_fit(rows, cols, length):
        return False
    return length <= MAX_FC_CELLS


def fc_work_fits(units: Int, cost_per_unit: Int, budget: Int) -> Bool:
    """True when `units * cost_per_unit <= budget`, computed WITHOUT forming the product.

    Same division shape as `dims_fit`, for the same reason: a work charge that overflows is
    a charge of a small number, so the budget silently stops being one. `cost_per_unit == 0`
    is free, and a negative argument is never a valid charge.
    """
    if units < 0 or cost_per_unit < 0 or budget < 0:
        return False
    if units == 0 or cost_per_unit == 0:
        return True
    return units <= budget // cost_per_unit


def fc_min_samples_for_level(level: Float64) -> Int:
    """Smallest residual sample size at which a two-sided `level` band is ESTIMABLE.

    A two-sided band at level `L` needs the `(1-L)/2` and `(1+L)/2` empirical quantiles. The
    smallest nonzero tail an order statistic of `k` samples can express is `1/k`, so a tail
    of `(1-L)/2` needs `k >= 2 / (1 - L)`: 40 samples for 95%, 20 for 90%, 200 for 99%.

    Below that the "95% band" is the min and max of a handful of numbers wearing a
    confidence label, which is the precise shape of a confident wrong answer. The interval
    drivers therefore report the band ABSENT for a step with too few residuals and return
    the per-step count, rather than returning the sample range under a success status.

    THE `ceil` IS TAKEN WITH A TOLERANCE, and it has to be. `1 - 0.9` is
    0.09999999999999998 in binary, so `1 / tail` is 20.000000000000004 and a bare `ceil`
    returns 21 — a discrete threshold moved by one because of a representation error in the
    caller's literal, which then refused a perfectly estimable 20-sample band. The judged
    quantity is `1 / tail` and the tolerance is built from THAT quantity's own magnitude
    (`FC_TOL_SLACK * DBL_EPSILON * (1 / tail)`) and from nothing else, per the module
    docstring. 64 ulps is many orders of magnitude below any gap that could matter here: a
    level whose true requirement is 20.5 samples still rounds to 21.

    Returns -1 when there is no answer — a level outside (0, 1), or a requirement past
    `FC_MAX_LEVEL_SAMPLES_F`. -1 is impossible for a real sample count, so an ignored
    return reads as a loud defect rather than as "no samples needed". The magnitude guard
    runs BEFORE `Int(...)`: `fptosi` past the integer grid is undefined and yields an
    arbitrary value, not a clamp (rule 4c), and `1e300` passes every finiteness test.
    """
    if fc_level_defect(level) != FC_OK:
        return -1
    var tail = 0.5 * (1.0 - level)
    if tail <= 0.0:
        return -1
    var exact = 1.0 / tail
    if not fc_finite(exact) or exact <= 0.0:
        return -1
    var need = ceil(exact - FC_TOL_SLACK * FC_DBL_EPSILON * exact)
    if need < 1.0:
        need = 1.0
    if not fc_finite(need) or need > FC_MAX_LEVEL_SAMPLES_F:
        return -1
    return Int(need)


def _fc_ses_level(y: List[Float64], alpha: Float64) -> List[Float64]:
    """`[terminal SES level]` from the frozen `series.exponential_forecast`, or empty.

    THE package's one route to a simple-exponential-smoothing level. `point` needs it for
    ETS(A,N,N) and for Theta's theta-line, and `intermittent` needs it twice per Croston call
    (demand sizes and inter-demand intervals). Four call sites, one definition — rule 3
    applies inside a package, and `optimization/` is the cautionary case: `_finite` existed
    six times byte-identical, so no file could import it and any one of them could drift.

    A one-element list rather than a bare `Float64` because that makes "no level" expressible
    without a sentinel. `exponential_forecast` returns a 0.0-filled path for an empty series —
    a level of zero indistinguishable from a real one — so emptiness is checked here rather
    than inherited, and a non-finite level is reported absent for the same reason.

    Private (the leading underscore only keeps a helper out of the runtime contract; Mojo has
    no access control, so siblings import it exactly as `optimization.integer` imports
    `optimization.model._round_f`).
    """
    var out = List[Float64]()
    if len(y) == 0:
        return out^
    var path = exponential_forecast(y, alpha, 1)
    if len(path) != 1 or not fc_finite(path[0]):
        return out^
    out.append(path[0])
    return out^


@fieldwise_init
struct FcQuantile(Copyable, Movable):
    """One empirical quantile, with its absence marker and its sample size.

    `has_value` is the authority. `value` is 0.0 when absent and that is not a claim: 0.0 is
    a perfectly ordinary quantile of a residual distribution, so it cannot double as a
    sentinel. NaN was rejected for the same reason it was rejected in `optimization.model` —
    it is the loudest marker in arithmetic and it does not survive the JSON frame these
    drivers cross, so it would arrive as a parse error rather than as an absent value.
    """

    var status: Int
    var has_value: Bool
    var value: Float64
    var n_samples: Int
    var p: Float64
    var status_name: String


def fc_quantile_of(values: List[Float64], p: Float64) -> FcQuantile:
    """The type-7 (linear-interpolated) empirical quantile at probability `p`.

    Computed as `-risk.value_at_risk(values, 1 - p)`, which is an identity and not a trick:
    `value_at_risk(x, c)` returns the NEGATED value at index `(1-c)(n-1)` of the sorted
    sample with linear interpolation between neighbours, so substituting `c = 1 - p` gives
    index `p(n-1)` and negating restores the sign. That frozen kernel is the tree's one
    definition of an interpolated empirical quantile and this package does not add a second.

    Two frozen behaviours are made honest here rather than inherited:

      * `value_at_risk([], c)` returns 0.0 — "the quantile of nothing is zero", which is
        indistinguishable from a real answer. Here an empty sample is FC_ERR_EMPTY_SERIES
        with `has_value = False`.
      * its sort is `risk._sort_copy`, an insertion sort, so the call is O(k^2). Bounding
        memory is not bounding work, so the sample size is charged against
        `FC_MAX_QUANTILE_SAMPLES` before the call rather than after it.

    `p` outside [0, 1] has no quantile. `p = 0` and `p = 1` are the sample min and max and
    are accepted; whether they are ESTIMATES of anything is a separate question that
    `fc_min_samples_for_level` answers.

    @capability fc_quantile_of
    complexity: O(n^2) -- the frozen sort inside `risk.value_at_risk` is an insertion sort
    counts: none
    @endcapability
    """
    var n = len(values)
    if n == 0:
        return FcQuantile(
            FC_ERR_EMPTY_SERIES, False, 0.0, 0, p,
            fc_status_name(FC_ERR_EMPTY_SERIES),
        )
    if n > FC_MAX_QUANTILE_SAMPLES:
        return FcQuantile(
            FC_ERR_WORK_BUDGET, False, 0.0, n, p,
            fc_status_name(FC_ERR_WORK_BUDGET),
        )
    if not fc_finite(p) or p < 0.0 or p > 1.0:
        return FcQuantile(
            FC_ERR_PARAM_RANGE, False, 0.0, n, p,
            fc_status_name(FC_ERR_PARAM_RANGE),
        )
    if not fc_all_finite(values):
        return FcQuantile(
            FC_ERR_NON_FINITE, False, 0.0, n, p,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    var q = -value_at_risk(values, 1.0 - p)
    if not fc_finite(q):
        return FcQuantile(
            FC_ERR_NON_FINITE, False, 0.0, n, p,
            fc_status_name(FC_ERR_NON_FINITE),
        )
    return FcQuantile(FC_OK, True, q, n, p, fc_status_name(FC_OK))
