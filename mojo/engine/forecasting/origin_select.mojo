"""
forecasting.origin_select — CRN-paired rolling-origin selection and tournament-gated
combination over the fitted pool {SES, Damped, Theta}. Zero Python imports.

What this module adds
---------------------
`forecasting.select` chooses between the three fitted candidates by IN-SAMPLE one-step
MAE — a single number per candidate, measured on points every candidate has already
seen. This module replaces that single-holdout estimate with a K-SAMPLE PAIRED estimate:
K rolling origins inside the training series, every candidate refitted at every origin
on exactly the same window and scored on exactly the same held-out h-step slice. The
origins are the "common random numbers" here — the same variance-reduction argument as
`strategy.crn`, applied to method selection: because every candidate faces the SAME K
windows, the between-origin noise cancels in every pairwise comparison, and the
selection statistic (the mean of the K per-origin h-step MAEs) orders candidates with a
variance the unpaired estimate cannot reach.

Everything here is a pure function of the TRAINING series `y` alone. The h-step
"test" slices used per origin are themselves inside `y`; no quantity from any true test
window enters any decision. The suite's refuter constructs a continuation that rewards
the method the training data disfavours and asserts the selection cannot see it.

Selection versus combination — the tournament gate
--------------------------------------------------
M4's central lesson is that combinations beat selected single methods BECAUSE apparent
per-series winners are often noise. The honest per-series answer is a statistical one:
`tournament_gated_select` hands the K per-origin paired MAEs to
`strategy.tournament.tourney_paired_diff_flat` (the paired-t core that already knows how
to say "no significant difference"). If the apparent best candidate is statistically
TIED with others at level `alpha`, the tied set is COMBINED with inverse-error weights;
only a candidate that clearly wins its pairings is selected alone. With K = 1 origin (a
short Yearly series) no test exists and every fitted candidate is tied by construction —
the weakest evidence yields the most cautious answer, which is the combination.

A comparison the machinery cannot make (a refused test, an absent p) counts as a TIE,
never as a win: failing to decide is evidence of nothing, and the cautious reading of
nothing is the combination.

The origin schedule, and why it is adaptive
-------------------------------------------
Origins are the most recent `K` training prefixes `y[.. t)` with `t + horizon <= n`,
spaced `max(1, horizon // 2)` apart so consecutive held-out slices overlap by at most
half a horizon, thinned from the recent end because the recent origins are the ones that
resemble the true forecast origin. Every window keeps at least `max(ORG_MIN_TRAIN,
horizon)` observations so each candidate's fit sees enough record to mean something.
When that spacing admits fewer than two origins the spacing collapses to 1 — a short
Yearly series supports only 2-3 origins and gets exactly the K its length affords,
`origin_schedule` being the one arithmetic authority (exposed, so a caller can size a
run and the suite can pin the numbers).

Candidates and refusals
-----------------------
The candidate pool, fits and forecast paths are `forecasting.select`'s
(`_fit_candidates`: SES via golden-section alpha, the fitted damped trend, classical
Theta) — this module weights and gates those fits, it does not add recursions. A
candidate that refuses ANY origin, or the full-series refit, is dropped with its status
carried (`component_status`); the survivors keep exact pairing on all K origins. If no
candidate survives, the status is FC_ERR_ALL_UNDEFINED and there is no forecast — a
selection among nothing is not a naive fallback. `mean_origin_maes` reports -1.0 for a
dropped candidate (impossible for a real MAE), and `p_values` reports -1.0 where no test
was made (impossible for a real p), so an ignored status reads loud, never as "fitted
perfectly".

Method ids are the package's ONE vocabulary (`FC_METHOD_ETS_ANN`, `FC_METHOD_ETS_AAN`,
`FC_METHOD_THETA`); a combination is reported as its components and weights with
`chosen_method_id = -1`, exactly as `forecasting.select` reports it.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_origin_select.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_LEVEL_RANGE,
    FC_ERR_NO_ORIGINS,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_ERR_WORK_BUDGET,
    FC_MAX_BACKTEST_WORK,
    FC_OK,
    fc_finite,
    fc_horizon_defect,
    fc_series_defect,
    fc_status_name,
    fc_work_fits,
)
from forecasting.select import (
    SEL_EXACT_MAE,
    _Candidates,
    _fit_candidates,
    _sel_method_ids,
)
from strategy.contract import (
    STRAT_OK,
    STRAT_VERDICT_A_BETTER,
    STRAT_VERDICT_B_BETTER,
)
from strategy.tournament import tourney_paired_diff_flat

# The smallest training window an origin may hand a candidate. Three observations is
# `select`'s floor for a meaningful in-sample MAE; five gives the damped fit's jointly
# estimated (l0, b0) at least three degrees of freedom beyond its state.
comptime ORG_MIN_TRAIN: Int = 5

# A ceiling on K whatever the caller asks: past a few dozen origins the added pairs
# measure the same recent record again while the refit cost keeps growing linearly.
comptime ORG_MAX_ORIGINS: Int = 64

# The confidence level handed to the paired-diff core for its interval. The DECISION is
# taken on the p-value against the caller's `alpha`; the interval is reporting, and one
# fixed level keeps two runs' records comparable.
comptime ORG_TOURNEY_LEVEL: Float64 = 0.95

# The number of candidates, one place. Parallel lists in the result are exactly this long.
comptime ORG_N_CANDIDATES: Int = 3

# The practical-equivalence floor, scaled by the two mean MAEs being compared. A mean
# per-origin difference below twelve orders under the error scale is floating-point
# residue, not evidence: on a series where every candidate fits to within a few ulps,
# the per-origin differences are rounding noise with a CONSISTENT sign, which a paired t
# happily reads as overwhelming significance — selecting on noise is exactly what the
# tie verdict exists to refuse. So a candidate inside this floor is tied BEFORE any test
# is consulted (its p reads -1.0: no test was made), and the same floor is handed to the
# paired core's deterministic branch as `abs_tol`. A genuine constant-margin dominance —
# a margin comparable to the errors themselves — sits astronomically above the floor and
# stays fully decidable.
comptime ORG_TIE_EPS: Float64 = 1.0e-12


def origin_schedule(n: Int, horizon: Int, max_origins: Int) -> List[Int]:
    """The rolling origins a series of length `n` affords, ascending. Pure arithmetic.

    Each origin `t` trains on `y[.. t)` and scores on `y[t .. t + horizon)`, so
    `t + horizon <= n` and `t >= max(ORG_MIN_TRAIN, horizon)` (a window shorter than its
    own forecast is the defect `fc_horizon_defect` refuses at the series level). Origins
    are taken from the recent end, spaced `max(1, horizon // 2)` apart; if that spacing
    admits fewer than two origins the spacing collapses to 1, so a short series yields
    the 2-3 origins it actually affords rather than none. At most
    `min(max_origins, ORG_MAX_ORIGINS)` origins are returned.

    Empty for a configuration that admits no origin (including non-positive arguments)
    — the callers turn that into FC_ERR_NO_ORIGINS rather than inventing a schedule.

    @capability origin_schedule
    complexity: O(max_origins)
    counts:
    - dim max_origins [kernel_validated]
    @endcapability
    """
    var out = List[Int]()
    if n <= 0 or horizon <= 0 or max_origins <= 0:
        return out^
    var floor_t = horizon if horizon > ORG_MIN_TRAIN else ORG_MIN_TRAIN
    var t_max = n - horizon
    if t_max < floor_t:
        return out^
    var cap = max_origins if max_origins < ORG_MAX_ORIGINS else ORG_MAX_ORIGINS
    var step = horizon // 2
    if step < 1:
        step = 1
    var avail = (t_max - floor_t) // step + 1
    if avail < 2 and step > 1:
        step = 1
        avail = t_max - floor_t + 1
    var k = cap if cap < avail else avail
    var t = t_max - (k - 1) * step
    for _ in range(k):
        out.append(t)
        t += step
    return out^


@fieldwise_init
struct OriginSelected(Copyable, Movable):
    """A per-series selection or combination decided by K paired rolling origins.

    `values` holds steps 1..horizon from the FULL-series refit(s), EMPTY on refusal
    (`has_forecast` is the authority). `method_ids` is always the three candidates in
    `forecasting.select`'s tie-break order; `component_status`, `mean_origin_maes`,
    `weights` and `p_values` are parallel to it. `origin_index` is the schedule that was
    run (ascending training-window ends); `origin_maes` is the row-major
    `ORG_N_CANDIDATES x n_origins` per-origin MAE matrix with -1.0 filling a dropped
    candidate's row — the paired samples themselves, so any other statistic can be
    computed without re-running the fits.

    `p_values[i]` is the paired-t p of candidate i against the apparent best; -1.0 where
    no test was made (the best itself, a dropped candidate, K < 2) — impossible for a
    real p, so it cannot be misread as significance. `n_tied` counts the members of the
    tied set that produced the forecast: 1 for a selection, >= 2 for a combination
    (`is_combination` says which; `chosen_method_id` is -1 for a combination).
    """

    var status: Int
    var horizon: Int
    var n_train: Int
    var n_origins: Int
    var values: List[Float64]
    var has_forecast: Bool
    var chosen_method_id: Int
    var is_combination: Bool
    var n_tied: Int
    var method_ids: List[Int]
    var component_status: List[Int]
    var mean_origin_maes: List[Float64]
    var weights: List[Float64]
    var p_values: List[Float64]
    var origin_index: List[Int]
    var origin_maes: List[Float64]
    var status_name: String


def _no_origin_selection(status: Int, horizon: Int, n_train: Int) -> OriginSelected:
    """A refusal: no path, no winner, every candidate marked absent, no matrix."""
    var maes = List[Float64]()
    var weights = List[Float64]()
    var pvals = List[Float64]()
    var stats = List[Int]()
    for _ in range(ORG_N_CANDIDATES):
        maes.append(-1.0)
        weights.append(0.0)
        pvals.append(-1.0)
        stats.append(status)
    return OriginSelected(
        status, horizon, n_train, 0, List[Float64](), False, -1, False, 0,
        _sel_method_ids(), stats^, maes^, weights^, pvals^,
        List[Int](), List[Float64](), fc_status_name(status),
    )


@fieldwise_init
struct _OriginMatrix(Copyable, Movable):
    """The paired per-origin MAEs: statuses, survival flags, and the K-column matrix."""

    var status: List[Int]
    var ok: List[Bool]
    var maes: List[Float64]
    var mean_maes: List[Float64]


def _paired_origin_maes(
    y: List[Float64], horizon: Int, origins: List[Int]
) -> _OriginMatrix:
    """Refit every candidate at every origin and score the SAME h-step slice.

    Row-major `ORG_N_CANDIDATES x len(origins)`; a candidate survives only if it fits at
    EVERY origin, so the surviving rows are exactly paired. A dropped candidate's row is
    filled with -1.0 and its first failing status is carried. The fits are
    `forecasting.select._fit_candidates` on the window — the same fits the full-series
    refit runs, so the selection statistic and the forecast cannot come from different
    models.
    """
    var k = len(origins)
    var status = List[Int]()
    var ok = List[Bool]()
    var maes = List[Float64]()
    var mean_maes = List[Float64]()
    for _ in range(ORG_N_CANDIDATES):
        status.append(FC_OK)
        ok.append(True)
        mean_maes.append(0.0)
    for _ in range(ORG_N_CANDIDATES * k):
        maes.append(-1.0)

    for j in range(k):
        var t = origins[j]
        var window = List[Float64](capacity=t)
        for i in range(t):
            window.append(y[i])
        var cand = _fit_candidates(window, horizon)
        for c in range(ORG_N_CANDIDATES):
            if not ok[c]:
                continue
            if cand.status[c] != FC_OK or len(cand.paths[c]) != horizon:
                ok[c] = False
                status[c] = cand.status[c]
                continue
            var abs_sum: Float64 = 0.0
            for h in range(horizon):
                abs_sum += fabs(y[t + h] - cand.paths[c][h])
            var mae = abs_sum / Float64(horizon)
            if not fc_finite(mae):
                ok[c] = False
                status[c] = FC_ERR_NON_FINITE
                continue
            maes[c * k + j] = mae

    for c in range(ORG_N_CANDIDATES):
        if not ok[c]:
            mean_maes[c] = -1.0
            for j in range(k):
                maes[c * k + j] = -1.0
            continue
        var total: Float64 = 0.0
        for j in range(k):
            total += maes[c * k + j]
        mean_maes[c] = total / Float64(k)

    return _OriginMatrix(status^, ok^, maes^, mean_maes^)


def _tie_weights(mean_maes: List[Float64], in_tie: List[Bool]) -> List[Float64]:
    """Inverse-MAE weights over the tied set, normalised to sum 1.

    The same exact-fit guard as `forecasting.select._selection_weights`: a member with
    `mae <= SEL_EXACT_MAE` takes the whole weight (split equally among exact members),
    because `1/mae` past that point overflows and poisons the normalisation. Members
    outside the tie weigh 0. Empty when the normalisation cannot be formed.
    """
    var out = List[Float64]()
    var n_exact = 0
    var any_in = False
    for i in range(len(mean_maes)):
        if in_tie[i]:
            any_in = True
            if mean_maes[i] <= SEL_EXACT_MAE:
                n_exact += 1
    if not any_in:
        return out^
    if n_exact > 0:
        for i in range(len(mean_maes)):
            if in_tie[i] and mean_maes[i] <= SEL_EXACT_MAE:
                out.append(1.0 / Float64(n_exact))
            else:
                out.append(0.0)
        return out^
    var total: Float64 = 0.0
    for i in range(len(mean_maes)):
        if in_tie[i]:
            total += 1.0 / mean_maes[i]
    if not fc_finite(total) or total <= 0.0:
        return List[Float64]()
    for i in range(len(mean_maes)):
        if in_tie[i]:
            out.append((1.0 / mean_maes[i]) / total)
        else:
            out.append(0.0)
    return out^


@fieldwise_init
struct _GateInputs(Copyable, Movable):
    """Everything both drivers need past validation: schedule, matrix, full-series fits."""

    var status: Int
    var origins: List[Int]
    var matrix: _OriginMatrix
    var full: _Candidates
    var eligible: List[Bool]
    var component_status: List[Int]
    var best: Int


def _gate_inputs(y: List[Float64], horizon: Int, max_origins: Int) -> _GateInputs:
    """Validate, schedule, run the paired matrix and the full-series refits, find the best.

    A candidate is ELIGIBLE only if it fitted at every origin AND on the full series —
    the selection statistic and the deliverable forecast must come from the same
    surviving model. `best` is the eligible candidate with the smallest mean per-origin
    MAE, ties to the first (the simpler model), -1 when none survived.
    """
    var empty_matrix = _OriginMatrix(
        List[Int](), List[Bool](), List[Float64](), List[Float64]()
    )
    var empty_cand = _Candidates(List[Int](), List[Float64](), List[List[Float64]]())
    var n = len(y)
    var defect = fc_series_defect(y)
    if defect == FC_OK:
        defect = fc_horizon_defect(n, horizon)
    if defect == FC_OK and max_origins <= 0:
        defect = FC_ERR_PARAM_RANGE
    if defect != FC_OK:
        return _GateInputs(
            defect, List[Int](), empty_matrix^, empty_cand^,
            List[Bool](), List[Int](), -1,
        )
    var origins = origin_schedule(n, horizon, max_origins)
    if len(origins) == 0:
        return _GateInputs(
            FC_ERR_NO_ORIGINS, List[Int](), empty_matrix^, empty_cand^,
            List[Bool](), List[Int](), -1,
        )
    # Each origin costs one three-candidate refit over a window of at most n points; the
    # damped fit's own eval budget multiplies in, so charge it by division up front.
    if not fc_work_fits(len(origins), n, FC_MAX_BACKTEST_WORK):
        return _GateInputs(
            FC_ERR_WORK_BUDGET, List[Int](), empty_matrix^, empty_cand^,
            List[Bool](), List[Int](), -1,
        )
    var matrix = _paired_origin_maes(y, horizon, origins)
    var full = _fit_candidates(y, horizon)
    var eligible = List[Bool]()
    var comp = List[Int]()
    for c in range(ORG_N_CANDIDATES):
        var live = matrix.ok[c] and full.status[c] == FC_OK
        eligible.append(live)
        if live:
            comp.append(FC_OK)
        elif not matrix.ok[c]:
            comp.append(matrix.status[c])
        else:
            comp.append(full.status[c])
    var best = -1
    for c in range(ORG_N_CANDIDATES):
        if not eligible[c]:
            continue
        if best < 0 or matrix.mean_maes[c] < matrix.mean_maes[best]:
            best = c
    return _GateInputs(FC_OK, origins^, matrix^, full^, eligible^, comp^, best)


def crn_origin_select(
    y: List[Float64], horizon: Int, max_origins: Int
) -> OriginSelected:
    """Select the single candidate with the smallest mean paired per-origin MAE.

    Mechanism 1 alone: K rolling origins inside the training series, every candidate
    refitted on the same windows and scored on the same held-out h-step slices, the
    winner refitted on the full series for the deliverable forecast. Ties break to the
    first of (SES, Damped, Theta) — a tie in the statistic is not evidence for the more
    flexible model. No statistical gate here; `tournament_gated_select` adds it.

    @capability crn_origin_select
    complexity: O(k * n) -- k bounded three-candidate refits, each O(n) passes
    counts:
    - dim horizon [kernel_validated]
    - dim max_origins [kernel_validated]
    @endcapability
    """
    var gate = _gate_inputs(y, horizon, max_origins)
    if gate.status != FC_OK:
        return _no_origin_selection(gate.status, horizon, len(y))
    if gate.best < 0:
        return _no_origin_selection(FC_ERR_ALL_UNDEFINED, horizon, len(y))
    var k = len(gate.origins)
    var weights = List[Float64]()
    var pvals = List[Float64]()
    for c in range(ORG_N_CANDIDATES):
        weights.append(1.0 if c == gate.best else 0.0)
        pvals.append(-1.0)
    var ids = _sel_method_ids()
    var chosen = ids[gate.best]
    return OriginSelected(
        FC_OK, horizon, len(y), k, gate.full.paths[gate.best].copy(), True,
        chosen, False, 1, ids^, gate.component_status.copy(),
        gate.matrix.mean_maes.copy(), weights^, pvals^,
        gate.origins.copy(), gate.matrix.maes.copy(), fc_status_name(FC_OK),
    )


def tournament_gated_select(
    y: List[Float64], horizon: Int, max_origins: Int, alpha: Float64
) -> OriginSelected:
    """Select the paired-origins winner only if it clearly wins; combine the tied set.

    Mechanism 2: the K per-origin MAEs go to `strategy.tournament`'s paired-t core, best
    against every other survivor at significance `alpha`. Candidates the best does NOT
    significantly beat form the tied set with it and are combined by inverse
    mean-origin-MAE weight over their full-series refits; a clear winner is selected
    alone. K < 2 admits no test, so every survivor is tied — the shortest series get the
    most cautious answer, the combination, which is M4's own lesson applied per series.
    A comparison the machinery refuses counts as a tie, never as a win.

    `alpha` outside (0, 1) is FC_ERR_LEVEL_RANGE: a gate at alpha = 0 can never select
    and at alpha = 1 can never combine, and both extremes silently reduce this function
    to one of its arms — a caller who wants an arm should call it by name.

    @capability tournament_gated_select
    complexity: O(k * n) -- k bounded three-candidate refits plus O(k) paired tests
    counts:
    - dim horizon [kernel_validated]
    - dim max_origins [kernel_validated]
    @endcapability
    """
    var n = len(y)
    if not fc_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return _no_origin_selection(FC_ERR_LEVEL_RANGE, horizon, n)
    var gate = _gate_inputs(y, horizon, max_origins)
    if gate.status != FC_OK:
        return _no_origin_selection(gate.status, horizon, n)
    if gate.best < 0:
        return _no_origin_selection(FC_ERR_ALL_UNDEFINED, horizon, n)
    var k = len(gate.origins)

    # The tied set always contains the best. With K >= 2 the best must BEAT a candidate
    # (a decided, directional verdict in its favour) to exclude it; anything else — no
    # difference, an undecided test, a refused comparison — keeps the candidate in.
    var in_tie = List[Bool]()
    var pvals = List[Float64]()
    for _ in range(ORG_N_CANDIDATES):
        in_tie.append(False)
        pvals.append(-1.0)
    in_tie[gate.best] = True

    var n_eligible = 0
    for c in range(ORG_N_CANDIDATES):
        if gate.eligible[c]:
            n_eligible += 1

    if n_eligible >= 2:
        if k >= 2:
            # Rows of the outcome matrix are eligible candidates in tie-break order;
            # the map back to candidate indices is `rows`.
            var rows = List[Int]()
            var outcomes = List[Float64]()
            for c in range(ORG_N_CANDIDATES):
                if not gate.eligible[c]:
                    continue
                rows.append(c)
                for j in range(k):
                    outcomes.append(gate.matrix.maes[c * k + j])
            var best_row = -1
            for r in range(len(rows)):
                if rows[r] == gate.best:
                    best_row = r
            for r in range(len(rows)):
                var c = rows[r]
                if c == gate.best:
                    continue
                var tie_tol = ORG_TIE_EPS * (
                    1.0 + gate.matrix.mean_maes[gate.best] + gate.matrix.mean_maes[c]
                )
                # Practical equivalence first: a mean difference inside the scaled
                # floor is numerical residue and TIES without consulting the test —
                # a paired t on consistently-signed rounding noise would reject.
                if (
                    gate.matrix.mean_maes[c] - gate.matrix.mean_maes[gate.best]
                    <= tie_tol
                ):
                    in_tie[c] = True
                    continue
                var diff = tourney_paired_diff_flat(
                    outcomes, len(rows), k, best_row, r,
                    ORG_TOURNEY_LEVEL, alpha, False, tie_tol,
                )
                if diff.has_p:
                    pvals[c] = diff.p_value
                var beaten = (
                    diff.status == STRAT_OK
                    and diff.decided
                    and diff.verdict == STRAT_VERDICT_A_BETTER
                )
                # B_BETTER cannot occur (the best has the smaller mean by construction)
                # but if it ever did, the candidate that BEAT the best must stay tied
                # rather than be excluded by the test that favoured it.
                if not beaten:
                    in_tie[c] = True
        else:
            for c in range(ORG_N_CANDIDATES):
                if gate.eligible[c]:
                    in_tie[c] = True

    var n_tied = 0
    for c in range(ORG_N_CANDIDATES):
        if in_tie[c]:
            n_tied += 1

    var ids = _sel_method_ids()
    if n_tied == 1:
        var weights = List[Float64]()
        for c in range(ORG_N_CANDIDATES):
            weights.append(1.0 if c == gate.best else 0.0)
        var chosen = ids[gate.best]
        return OriginSelected(
            FC_OK, horizon, n, k, gate.full.paths[gate.best].copy(), True,
            chosen, False, 1, ids^, gate.component_status.copy(),
            gate.matrix.mean_maes.copy(), weights^, pvals^,
            gate.origins.copy(), gate.matrix.maes.copy(), fc_status_name(FC_OK),
        )

    var weights = _tie_weights(gate.matrix.mean_maes, in_tie)
    if len(weights) != ORG_N_CANDIDATES:
        return _no_origin_selection(FC_ERR_ALL_UNDEFINED, horizon, n)
    var values = List[Float64]()
    for h in range(horizon):
        var v: Float64 = 0.0
        for c in range(ORG_N_CANDIDATES):
            if weights[c] > 0.0:
                v += weights[c] * gate.full.paths[c][h]
        if not fc_finite(v):
            return _no_origin_selection(FC_ERR_NON_FINITE, horizon, n)
        values.append(v)
    return OriginSelected(
        FC_OK, horizon, n, k, values^, True, -1, True, n_tied,
        ids^, gate.component_status.copy(), gate.matrix.mean_maes.copy(),
        weights^, pvals^, gate.origins.copy(), gate.matrix.maes.copy(),
        fc_status_name(FC_OK),
    )
