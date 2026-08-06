"""
inference.multiplicity — Bonferroni, Holm and Benjamini-Hochberg. Zero Python imports.

Why this module exists
----------------------
Nothing in the tree corrects for multiple testing. `stat_tests` returns a `reject_h0` flag
per test at a hardcoded `alpha = 0.05`, `hypothesis` returns bare p-values, and a caller
running twenty of them and reporting the significant ones has an expected one false
discovery and no way to say so. There is no adjustment function anywhere.

What a correction changes, and why the method has to travel with the numbers
---------------------------------------------------------------------------
Correction changes what a REJECTION MEANS, not merely the threshold:

* Bonferroni and Holm control the family-wise error rate — the probability of ANY false
  rejection in the family.
* Benjamini-Hochberg controls the false discovery rate — the expected PROPORTION of false
  rejections among those rejected.

Those are different guarantees, and an adjusted value of 0.04 means something different
under each. So `Correction.method` is part of every result and `Correction.n_tests` states
how large the family was, because an adjusted p-value is meaningless without both. Reporting
adjusted values alone — which is what a bare `List[Float64]` return would do — is the
failure this module is shaped to avoid.

What is reused rather than rebuilt
----------------------------------
* `retrieval.score.retrieval_rank_order` — the tree's index sort with a stated tie-break
  (score DESCENDING, ordinal ASCENDING). p-values must be ordered ASCENDING, so the scores
  handed to it are the NEGATED p-values: `-p_a > -p_b` exactly when `p_a < p_b`, and the
  tie-break on the original position makes the ordering total, so a family with repeated
  p-values adjusts reproducibly rather than depending on which one the sort met first.
  Negation is exact in floating point, so nothing is lost. The alternative was a fourth
  merge sort in the tree; `sorting.mergesort` cannot be used because it sorts a bare
  `List[Float64]` and discards the position each adjusted value has to return to.
* `inference.core` — the status vocabulary, `inference_finite`, `MAX_TESTS`.

Both procedures are computed in a form that makes tied p-values agree by construction:
Holm's adjusted value is the running MAXIMUM of `(n - j) p_(j)` from the smallest upward and
BH's is the running MINIMUM of `n p_(j) / (j+1)` from the largest downward, so two equal raw
p-values cannot receive two different adjusted values.

Rule 4 in this module
---------------------
* A value offered as a p-value that is not in `[0, 1]` is not a p-value:
  `INF_ERR_PVALUE_RANGE`, and nothing is adjusted. Silently clamping it would hide exactly
  the kind of defect `inference.core` documents (fixed as of this session, but keeps the
  history): a broken tail once produced a NEGATIVE p-value that a clamp turned into `0.0`
  under `reject_h0 = True`.
* `max_rejected_p` is `-1.0` when nothing was rejected. A p-value cannot be negative, so
  the sentinel is outside the range and cannot be read as "the critical value was zero" —
  which is what returning `0.0` there would say.
* `n_tests` is the caller's declared family size and is required to be at most
  `len(p_values)`; it is never silently reduced to the shorter of the two. A family of
  twenty tests of which five were supplied is not a family of five, and correcting as if it
  were would understate every adjusted value.

Status codes 320-339 belong to the `inference` package; this module allocates none of its
own and imports them from `inference.core` (rule 4e).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_inference_multiplicity.mojo
benchmark: benchmarks/mojo_benchmarks/bench_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from inference.core import (
    INF_ERR_ALPHA_RANGE,
    INF_ERR_DIMENSION_TOO_LARGE,
    INF_ERR_EMPTY,
    INF_ERR_PVALUE_RANGE,
    INF_ERR_SHAPE,
    INF_OK,
    MAX_TESTS,
    inference_finite,
)
from retrieval.score import retrieval_rank_order

# A p-value cannot be negative, so this is outside the range and cannot be mistaken for a
# critical value of zero. Same convention as `optimization.assignment.ASSIGN_DEFECT_ABSENT`.
comptime MULT_P_ABSENT: Float64 = -1.0

comptime METHOD_BONFERRONI: String = "bonferroni"
comptime METHOD_HOLM: String = "holm_bonferroni_step_down"
comptime METHOD_BH: String = "benjamini_hochberg_step_up"


@fieldwise_init
struct Correction(Copyable, Movable):
    """One multiple-testing correction applied to one family of p-values.

    `adjusted` and `rejected` are in the CALLER'S original order, not sorted order, so a
    caller does not have to reconstruct the permutation. Both are EMPTY unless
    `status == INF_OK`.

    `method` and `n_tests` are not decoration: an adjusted p-value without the method that
    produced it and the size of the family it was corrected against cannot be interpreted,
    because the three methods control different quantities (see the module docstring).

    `max_rejected_p` is the largest RAW p-value that was rejected — the critical value the
    procedure actually applied — and `MULT_P_ABSENT` (-1.0) when nothing was rejected.
    """

    var status: Int
    var method: String
    var alpha: Float64
    var n_tests: Int
    var n_rejected: Int
    var adjusted: List[Float64]
    var rejected: List[Bool]
    var min_p: Float64
    var max_rejected_p: Float64


fn _correction_failure(code: Int, method: String, alpha: Float64, n: Int) -> Correction:
    return Correction(
        code, method, alpha, n, 0, List[Float64](), List[Bool](),
        MULT_P_ABSENT, MULT_P_ABSENT,
    )


fn multiplicity_input_defect(
    p_values: List[Float64], n: Int, alpha: Float64
) -> Int:
    """`INF_OK`, or the one status that describes what is wrong with this family.

    PUBLIC and the SINGLE validator for all three procedures in this module, so the three
    cannot disagree about what a valid family is — rule 3's "one declared input invariant
    enforced at three different strengths under three different status codes" is the defect
    this shape avoids. Checks, in order: a positive family size, the ceiling, that the
    payload really contains `n` values, finiteness, membership in `[0, 1]`, and `alpha`
    strictly inside `(0, 1)`.

    `alpha` at exactly 0 or 1 is refused rather than admitted: at `alpha = 0` no rejection
    is possible and at `alpha = 1` every hypothesis is rejected, so neither is a decision
    rule anyone means to state.

    @capability multiplicity_input_defect
    complexity: O(n)
    counts:
    - n <= len(p_values) [kernel_validated]
    @endcapability
    """
    if n <= 0:
        return INF_ERR_EMPTY
    if n > MAX_TESTS:
        return INF_ERR_DIMENSION_TOO_LARGE
    if n > len(p_values):
        return INF_ERR_SHAPE
    if not inference_finite(alpha) or alpha <= 0.0 or alpha >= 1.0:
        return INF_ERR_ALPHA_RANGE
    for i in range(n):
        if not inference_finite(p_values[i]):
            return INF_ERR_PVALUE_RANGE
        if p_values[i] < 0.0 or p_values[i] > 1.0:
            return INF_ERR_PVALUE_RANGE
    return INF_OK


fn _ascending_order(p_values: List[Float64], n: Int) -> List[Int]:
    """Positions of the first `n` p-values in ASCENDING order, ties by original position.

    The frozen `retrieval.score.retrieval_rank_order` orders by score DESCENDING with an
    ascending ordinal tie-break, so negating the p-values turns it into the ascending order
    this module needs. Negation of a finite double is exact, so no ordering information is
    invented or lost. Returns an empty list only if the frozen kernel refuses, which it does
    for a length mismatch or a non-finite score — both already excluded by
    `multiplicity_input_defect`.
    """
    var scores = List[Float64](capacity=n)
    var ordinals = List[Int](capacity=n)
    for i in range(n):
        scores.append(-p_values[i])
        ordinals.append(i)
    return retrieval_rank_order(scores, ordinals)


fn _finish(
    method: String, alpha: Float64, n: Int,
    adjusted: List[Float64], p_values: List[Float64],
) -> Correction:
    """Decide rejections from adjusted values and assemble the result.

    One place decides `rejected`, for all three procedures: `adjusted_i <= alpha`. That is
    equivalent to Holm's step-down and BH's step-up rules precisely because both adjusted
    sequences are enforced monotone in sorted order, so a single threshold reproduces the
    stepwise decision. Having one implementation is the point — three copies of a
    comparison is three chances for one of them to use `<` where the others use `<=`.
    """
    var rejected = List[Bool](capacity=n)
    var n_rejected = 0
    var min_p = p_values[0]
    var max_rejected = MULT_P_ABSENT
    for i in range(n):
        if p_values[i] < min_p:
            min_p = p_values[i]
        var reject = adjusted[i] <= alpha
        rejected.append(reject)
        if reject:
            n_rejected += 1
            if p_values[i] > max_rejected:
                max_rejected = p_values[i]
    return Correction(
        INF_OK, method, alpha, n, n_rejected, adjusted.copy(), rejected^,
        min_p, max_rejected,
    )


fn bonferroni_flat(
    p_values: List[Float64], n: Int, alpha: Float64
) -> Correction:
    """Bonferroni: `adjusted_i = min(1, n * p_i)`; controls the family-wise error rate.

    The simplest correction and the most conservative of the three. No ordering is needed,
    so this procedure alone does not sort. The product `n * p_i` is a Float64 multiply of a
    count by a probability, not the wrapping integer multiply rule 1c warns about, and `n`
    is bounded by `MAX_TESTS` well below the Float64 integer grid.

    @capability bonferroni_flat
    complexity: O(n)
    counts:
    - n <= len(p_values) [kernel_validated]
    @endcapability
    """
    var defect = multiplicity_input_defect(p_values, n, alpha)
    if defect != INF_OK:
        return _correction_failure(defect, METHOD_BONFERRONI, alpha, n)
    var nf = Float64(n)
    var adjusted = List[Float64](capacity=n)
    for i in range(n):
        var a = nf * p_values[i]
        adjusted.append(1.0 if a > 1.0 else a)
    return _finish(METHOD_BONFERRONI, alpha, n, adjusted, p_values)


fn holm_flat(
    p_values: List[Float64], n: Int, alpha: Float64
) -> Correction:
    """Holm-Bonferroni step-down: `adjusted_(i) = max_{j<=i} min(1, (n-j) p_(j))`.

    Controls the family-wise error rate like Bonferroni and is uniformly at least as
    powerful: for the SMALLEST p-value the two adjusted values are identical, `n * p_min`,
    and for every larger one Holm's multiplier shrinks. The suite asserts that equality
    exactly rather than approximately, because it is an identity and not a numerical
    coincidence.

    The running maximum is what makes the sequence monotone, which is also what makes tied
    p-values receive equal adjusted values.

    @capability holm_flat
    complexity: O(n log n)
    counts:
    - n <= len(p_values) [kernel_validated]
    @endcapability
    """
    var defect = multiplicity_input_defect(p_values, n, alpha)
    if defect != INF_OK:
        return _correction_failure(defect, METHOD_HOLM, alpha, n)
    var order = _ascending_order(p_values, n)
    if len(order) != n:
        return _correction_failure(INF_ERR_SHAPE, METHOD_HOLM, alpha, n)

    var adjusted = List[Float64](capacity=n)
    for _ in range(n):
        adjusted.append(0.0)
    var running: Float64 = 0.0
    for rank in range(n):
        var idx = order[rank]
        var a = Float64(n - rank) * p_values[idx]
        if a > 1.0:
            a = 1.0
        if a > running:
            running = a
        adjusted[idx] = running
    return _finish(METHOD_HOLM, alpha, n, adjusted, p_values)


fn benjamini_hochberg_flat(
    p_values: List[Float64], n: Int, alpha: Float64
) -> Correction:
    """Benjamini-Hochberg step-up: `adjusted_(i) = min_{j>=i} min(1, n p_(j) / (j+1))`.

    Controls the FALSE DISCOVERY RATE — the expected proportion of false rejections among
    the rejected — under independence or positive dependence of the test statistics. That is
    a weaker guarantee than family-wise control and buys more power, which is why
    `Correction.method` travels with the numbers: 0.04 under BH and 0.04 under Holm license
    different claims.

    The running minimum taken from the LARGEST p-value downward is what makes the sequence
    monotone. It also makes `adjusted_(i) <= holm_adjusted_(i)` provable for every `i`, since
    `n p_(i) / (i+1) <= (n - i) p_(i)` whenever `1 <= i+1 <= n`; the suite asserts that
    ordering across all three procedures.

    @capability benjamini_hochberg_flat
    complexity: O(n log n)
    counts:
    - n <= len(p_values) [kernel_validated]
    @endcapability
    """
    var defect = multiplicity_input_defect(p_values, n, alpha)
    if defect != INF_OK:
        return _correction_failure(defect, METHOD_BH, alpha, n)
    var order = _ascending_order(p_values, n)
    if len(order) != n:
        return _correction_failure(INF_ERR_SHAPE, METHOD_BH, alpha, n)

    var adjusted = List[Float64](capacity=n)
    for _ in range(n):
        adjusted.append(0.0)
    var nf = Float64(n)
    var running: Float64 = 1.0
    for step in range(n):
        var rank = n - 1 - step
        var idx = order[rank]
        var a = nf * p_values[idx] / Float64(rank + 1)
        if a > 1.0:
            a = 1.0
        if a < running:
            running = a
        adjusted[idx] = running
    return _finish(METHOD_BH, alpha, n, adjusted, p_values)


@fieldwise_init
struct CorrectionAgreement(Copyable, Movable):
    """Whether this module's three procedures agree with each other on one family.

    Self-consistency is a testable property, so it is tested — and exported, so a caller can
    test it too. Two of the criticals in rule 4b were endorsed by a module's own
    cross-checks; a report that contradicts itself means a caller can use neither half.

    `smallest_p_identical` is exact equality of the Bonferroni and Holm adjusted values at
    the smallest p-value: both are `n * p_min`, an identity, so anything other than bitwise
    equality is a defect and not a rounding difference.

    `monotone_bh_le_holm_le_bonferroni` checks the provable ordering at EVERY position, not
    only at the ones this family happens to reject.
    """

    var status: Int
    var n_tests: Int
    var n_rejected_bonferroni: Int
    var n_rejected_holm: Int
    var n_rejected_bh: Int
    var smallest_p_identical: Bool
    var monotone_bh_le_holm_le_bonferroni: Bool
    var power_ordering_holds: Bool


fn correction_agreement_flat(
    p_values: List[Float64], n: Int, alpha: Float64
) -> CorrectionAgreement:
    """Run all three corrections on one family and report whether they cohere.

    `power_ordering_holds` is `n_bonferroni <= n_holm <= n_bh`: a less conservative
    procedure cannot reject fewer hypotheses than a more conservative one on the same
    family. It is implied by the adjusted-value ordering, and asserting both catches a
    threshold comparison that disagrees with the adjusted values it was derived from.

    @capability correction_agreement_flat
    complexity: O(n log n)
    counts:
    - n <= len(p_values) [kernel_validated]
    @endcapability
    """
    var defect = multiplicity_input_defect(p_values, n, alpha)
    if defect != INF_OK:
        return CorrectionAgreement(defect, n, 0, 0, 0, False, False, False)
    var bonf = bonferroni_flat(p_values, n, alpha)
    var holm = holm_flat(p_values, n, alpha)
    var bh = benjamini_hochberg_flat(p_values, n, alpha)
    if bonf.status != INF_OK or holm.status != INF_OK or bh.status != INF_OK:
        return CorrectionAgreement(INF_ERR_SHAPE, n, 0, 0, 0, False, False, False)

    var smallest = 0
    for i in range(1, n):
        if p_values[i] < p_values[smallest]:
            smallest = i
    var identical = bonf.adjusted[smallest] == holm.adjusted[smallest]

    var monotone = True
    for i in range(n):
        if bh.adjusted[i] > holm.adjusted[i]:
            monotone = False
        if holm.adjusted[i] > bonf.adjusted[i]:
            monotone = False
    var power_ok = (
        bonf.n_rejected <= holm.n_rejected and holm.n_rejected <= bh.n_rejected
    )
    return CorrectionAgreement(
        INF_OK, n, bonf.n_rejected, holm.n_rejected, bh.n_rejected,
        identical, monotone, power_ok,
    )
