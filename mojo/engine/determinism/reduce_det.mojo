"""
determinism.reduce_det — reductions whose ORDER is a pure function of the input length.

Why this file exists, measured rather than asserted
---------------------------------------------------
Floating-point addition is not associative, so a left-to-right sum is a different
function for every way the work is split. Measured on `[1e16] + 1024 x 1.0`, whose exact
sum is 10000000000001024, a plain sequential sum chunked seven ways gives six distinct
answers:

    chunk    1   ->  1e+16                     (every 1.0 lost: 1e16 + 1.0 rounds to 1e16)
    chunk    2   ->  1.0000000000001024e+16    (exact)
    chunk    3   ->  1.0000000000001362e+16
    chunk    7   ->  1.0000000000001164e+16
    chunk   64   ->  1.000000000000096e+16
    chunk  257   ->  1.0000000000000766e+16
    chunk 1024   ->  1e+16

Six spellings of "the sum of this array", differing by up to 1024 absolute (the bench
sweeps eleven chunkings and finds eight). Nothing in any of those results says which
chunking produced it, so a stored answer cannot be
re-derived and a replay cannot be checked. That is the defect; `numeric.reduce.reduce_sum`
is the left-to-right path and is left exactly as it is (it is frozen, and it is the right
choice when reproducibility is not the requirement).

The fixed tree shape
--------------------
Every reduction here uses ONE tree whose shape depends on the element count `n` and on
nothing else — not on chunk size, thread count, or traversal order.

The shape is the aligned power-of-two decomposition of `[0, n)`. Elements are pushed into
a binary counter: a completed run of `2^k` consecutive elements starting at a multiple of
`2^k` collapses to one node, so every node is the perfect-tree sum of an aligned block.
What survives at the end is the canonical decomposition of `n` into descending powers of
two — for `n = 7` the blocks `[0,4) [4,6) [6,7)` — folded right-nested:
`P1 + (P2 + (P3 + ...))`.

Two properties follow, and both are asserted with `==` in
`mojo/tests/libs/test_determinism_reduce_det.mojo`:

* **Chunk invariance.** Because a node only ever forms from two true siblings, a chunk
  reduced on its own produces a prefix of the same node set. Merging adjacent chunk
  states reproduces the whole-array tree bit-for-bit, for ANY chunk size. Measured: chunk
  sizes 1, 2, 3, 7, 64, 1000, n/2, n and n+5 at n = 2^10 + 1; every size from 1 to 39 plus
  40, 77, 114, ... on a 1048-element ragged array of mixed magnitudes and alternating
  signs; 1 and 4096 at n = 2^20 + 1; and 1, 3, 64, 1024, 65536, 10^6 and n at n = 10^7 + 1
  in a compiled binary. Zero disagreements. The suite asserts `==`, never a tolerance: a
  tolerance would hide exactly the drift this file removes.
* **Accuracy as a side effect.** On the `[1e16] + N x 1.0` family the tree result is the
  exactly-rounded answer for N = 2^10, 2^16, 2^20 and 10^7, where the sequential sum is
  off by N. Accuracy is not the deliverable — reproducibility is — but it is not a
  regression either.

`O(log n)` working memory, `n - 1` additions
--------------------------------------------
The counter holds at most two nodes per level, so the state is `<= COUNTER_CAPACITY`
(130) entries whatever `n` is — see that constant for the derivation. No array proportional
to `n` is allocated by `det_sum`, `det_sum_chunked`,
`det_mean`, `det_dot` or `det_sum_squares`, so rule 1c's `k x ceiling` arithmetic is
`k = 0` for those five and no local dimension ceiling is needed beyond `n <= len(a)`.
`det_kahan_sum` is the one exception and says so in its own docstring.

What the tree COSTS, measured
----------------------------
Reproducibility is not free and this file does not claim it is. Compiled binary (not the
JIT), 10,000,001 `Float64`, best of 5 after a warm-up pass, macOS arm64:

    sequential (`det_naive_sum`)        21.9 ms      <- the fastest, and the one that
                                                       gives seven different answers
    fixed tree (`det_sum`)              51.8 ms      2.4x the sequential sum
    Neumaier (`det_neumaier_sum`)       22.6 ms
    frozen `kahan_sum`                  61.4 ms
    `det_sum_chunked`, chunks >= 64     60-63 ms     flat across 64 .. n
    `det_sum_chunked`, chunk = 1       430 ms        every element becomes its own block

So the tree costs about 2.4x a sequential sum (2.31x-2.45x across repeated runs of the
same binary) and is cheaper than the frozen compensated sum it sits beside. It is NOT free, and a caller that does not need a reproducible answer
should keep using `numeric.reduce.reduce_sum`. Two earlier revisions of this file were 9.7x
and 8.5x the sequential sum; both numbers were measured, and the 2.4x came from reserving
the counter to its proven bound and folding 8-aligned runs inline — not from changing the
tree. The tree is bit-identical across all three revisions: every expected value in the
suite is unchanged, and `det_sum == det_sum_chunked(a, n, 1)` cross-checks the folded route
against the one-leaf-at-a-time route on every input the suite carries.

Compensated summation, and what it does NOT buy
-----------------------------------------------
`det_kahan_sum` calls the frozen `numerical_stability.kahan_sum`; `det_neumaier_sum` adds
the Neumaier variant, which is a different algorithm rather than a rewrite — Kahan's
compensation is dropped whenever the running sum is smaller in magnitude than the incoming
term. Measured on `[1.0, 1e100, 1.0, -1e100]`, exact answer 2.0:

    sequential 0.0      kahan 0.0      pairwise 0.0      neumaier 2.0

Both compensated forms reduce error. **Neither makes addition associative**, and neither
is chunk-invariant: they carry a scalar running compensation, so splitting the input
splits the compensation. Measured, same array, exact answer 2.0:

    neumaier whole -> 2.0    the same array split into two halves -> 0.0

(gated in `benchmarks/mojo_benchmarks/bench_determinism_reduce_det.mojo`, which fails if
Neumaier ever comes out chunk-invariant)

So they are offered for accuracy on a fixed traversal and are explicitly NOT the
reproducible path. `det_sum` is.

Status codes
------------
Package `determinism` allocates 200-209 to this module and 210-229 to
`determinism.manifest`; pick from what is left (rule 4e).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: none
golden_vectors: mojo/tests/libs/test_determinism_reduce_det.mojo
benchmark: benchmarks/mojo_benchmarks/bench_determinism_reduce_det.mojo
docs: none
version_introduced: unreleased
deprecation_state: active
@endcapability
"""
from numerical_stability import kahan_sum

from numeric.contract import AGG_AVG, AGG_SUM, empty_yields_null
from numeric.reduce import is_finite_value

# ── status codes (determinism package range 200-209) ──────────────────────────
# Distinct per defect: a caller whose call was refused needs to know which argument to
# look at, and one "invalid" code would send it looking at all of them.

comptime DET_OK: Int = 200
comptime DET_ERR_COUNT: Int = 201
comptime DET_ERR_PAIR_LENGTH: Int = 202
comptime DET_ERR_CHUNK: Int = 203
comptime DET_EMPTY: Int = 204
comptime DET_ERR_NON_FINITE: Int = 205
comptime DET_ERR_OVERFLOW: Int = 206

# The identity of the tree shape. It travels in a replay manifest, so changing the
# decomposition or the fold direction MUST bump this string: every stored answer produced
# by the old shape is a different function of the same data.
comptime REDUCTION_SHAPE_ID: String = "det-pairwise-aligned-blocks/v1"

# One entry per level of the binary counter. 64 covers every Int-addressable length.
comptime MAX_TREE_LEVELS: Int = 64

# Capacity the counter columns are reserved to. NOT `MAX_TREE_LEVELS`: a counter fed an
# interval that does not start at a multiple of its block sizes holds up to TWO blocks per
# level — one for each ragged edge — as `[3, 10)` does with `{3} [4,8) [8,10)`. Plus one
# transient entry between the push and the collapse it triggers. `2 * 64 + 2` is therefore
# the bound at which no push can reallocate, and it is 130 entries, so stating it generously
# costs nothing. This is what makes the O(log n) memory claim above a bound and not a
# typical case.
comptime COUNTER_CAPACITY: Int = 2 * MAX_TREE_LEVELS + 2


@fieldwise_init
struct DetReduction(Copyable, Movable):
    """A reduction outcome under the fixed tree shape.

    `present == False` means no answer exists and `value` is not one — a mean of nothing,
    a refused call, or a sum that overflowed. `status` says which; `DET_OK` is the only
    status under which `value` is an answer. Declared in this file rather than reusing
    `numeric.reduce.Reduction` because a struct from another module is silently dropped
    from the runtime contract (rule 2), and because this one carries a status that one
    does not.
    """

    var value: Float64
    var present: Bool
    var n: Int
    var status: Int


fn det_absent(n: Int, status: Int) -> DetReduction:
    """No answer, with the reason. `value` is 0.0 and means nothing."""
    return DetReduction(0.0, False, n, status)


fn det_status_name(code: Int) -> String:
    """Name for a status code, so a rejection surfaces the defect and not a bare number."""
    if code == DET_OK:
        return "ok"
    if code == DET_ERR_COUNT:
        return "count_exceeds_input_length"
    if code == DET_ERR_PAIR_LENGTH:
        return "count_exceeds_one_of_the_two_inputs"
    if code == DET_ERR_CHUNK:
        return "chunk_size_below_one"
    if code == DET_EMPTY:
        return "no_elements_so_no_answer_exists"
    if code == DET_ERR_NON_FINITE:
        return "non_finite_input"
    if code == DET_ERR_OVERFLOW:
        return "result_not_representable"
    return "unknown_status"


fn reduction_shape_id() -> String:
    """Identity of the reduction order. Deterministic, zero-argument.

    A replay manifest records this string; two runs whose manifests agree on it summed
    their data in the same order.
    """
    return REDUCTION_SHAPE_ID


fn det_tree_depth(n: Int) -> Int:
    """Height of the fixed tree for `n` elements — `ceil(log2(n))`, and 0 for `n <= 1`.

    Exposed so a caller can assert the shape rather than infer it, and so a test can
    prove the counter bound in `MAX_TREE_LEVELS` is not being approached.
    """
    if n <= 1:
        return 0
    var depth = 0
    var span = 1
    while span < n:
        span = span * 2
        depth += 1
    return depth


# ── the fixed tree, in one place ──────────────────────────────────────────────


fn _push_leaf(
    mut starts: List[Int], mut sizes: List[Int], mut vals: List[Float64],
    start: Int, size: Int, value: Float64
):
    """Add one aligned block to the counter, collapsing siblings as they complete.

    A collapse happens only when the top two entries are TRUE siblings: same size,
    adjacent, and the left one aligned to twice that size. That is the whole reason a
    chunk can be reduced independently — a node that straddles a chunk boundary simply
    does not form until the neighbouring chunk's blocks arrive.
    """
    starts.append(start)
    sizes.append(size)
    vals.append(value)
    while len(sizes) >= 2:
        var j = len(sizes) - 1
        if sizes[j] != sizes[j - 1]:
            break
        if starts[j] != starts[j - 1] + sizes[j - 1]:
            break
        if starts[j - 1] % (2 * sizes[j - 1]) != 0:
            break
        vals[j - 1] = vals[j - 1] + vals[j]
        sizes[j - 1] = sizes[j - 1] * 2
        _ = starts.pop()
        _ = sizes.pop()
        _ = vals.pop()


fn _new_counter_f64() -> List[Float64]:
    """A counter column, pre-reserved to its hard bound so no push ever reallocates.

    `COUNTER_CAPACITY` is derived from the two-blocks-per-level bound beside its
    definition, so this is a proof that no push reallocates rather than a hint. Measured on
    10,000,001 elements: reserving it took `det_sum` from 252.6 ms to 186.2 ms. The
    reduction is dominated by push/pop bookkeeping, not by the additions.
    """
    return List[Float64](capacity=COUNTER_CAPACITY)


fn _new_counter_int() -> List[Int]:
    return List[Int](capacity=COUNTER_CAPACITY)


# Leaf modes, so ONE ingestion path serves sum, dot product and sum of squares. Three
# copies of the tree walk is how the copies drift (rule 3 applies inside a package too).
comptime _LEAF_VALUE: Int = 0
comptime _LEAF_PRODUCT: Int = 1
comptime _LEAF_SQUARE: Int = 2

# Width of the aligned run that `_ingest` folds inline before touching the counter. The
# unrolled expression below is written for exactly this width — changing the constant
# without rewriting that expression changes the tree, which is why it is not a parameter.
comptime RUN_WIDTH: Int = 8


fn _leaf(a: List[Float64], b: List[Float64], mode: Int, i: Int) -> Float64:
    """The value the tree's leaf `i` carries. Caller has already bounded `i`."""
    if mode == _LEAF_PRODUCT:
        return a[i] * b[i]
    if mode == _LEAF_SQUARE:
        return a[i] * a[i]
    return a[i]


fn _ingest(
    a: List[Float64], b: List[Float64], mode: Int, lo: Int, hi: Int,
    mut starts: List[Int], mut sizes: List[Int], mut vals: List[Float64]
):
    """Feed leaves `[lo, hi)` into the counter. The ONE place leaves enter the tree.

    An 8-aligned run that fits entirely inside `[lo, hi)` is folded inline as
    `((x0+x1)+(x2+x3)) + ((x4+x5)+(x6+x7))` and pushed as a single size-8 block. That is
    BIT-IDENTICAL to pushing the eight leaves one at a time, because the counter would
    build exactly that perfect subtree from them — a perfect power-of-two block has one
    balanced tree and both routes produce it. It is not an approximation, and it is not a
    second tree: `det_sum_chunked(a, n, 1)` never takes the fast route (a one-element chunk
    can never fit an eight-wide run), so the suite's `det_sum == det_sum_chunked(a, n, 1)`
    assertion is a live cross-check between the two routes rather than a tautology.

    Measured on 10,000,001 elements, compiled (not JIT), best of 5: 186.2 ms pushing every
    leaf individually, 51.8 ms with the run fold. The cost lands on `det_sum_chunked(a, n,
    1)`, which cannot use the fast route and pays one extra alignment test per element:
    378 ms before, 430 ms after. That is the right place for it — a one-element chunk is the
    invariance demonstration, not a working configuration.
    """
    var i = lo
    while i < hi:
        if i % RUN_WIDTH == 0 and i + RUN_WIDTH <= hi:
            var v0 = _leaf(a, b, mode, i) + _leaf(a, b, mode, i + 1)
            var v1 = _leaf(a, b, mode, i + 2) + _leaf(a, b, mode, i + 3)
            var v2 = _leaf(a, b, mode, i + 4) + _leaf(a, b, mode, i + 5)
            var v3 = _leaf(a, b, mode, i + 6) + _leaf(a, b, mode, i + 7)
            _push_leaf(starts, sizes, vals, i, RUN_WIDTH, (v0 + v1) + (v2 + v3))
            i += RUN_WIDTH
        else:
            _push_leaf(starts, sizes, vals, i, 1, _leaf(a, b, mode, i))
            i += 1


fn _fold(vals: List[Float64]) -> Float64:
    """Combine the surviving blocks right-nested: `P1 + (P2 + (P3 + ...))`.

    Right-nested rather than left, because the surviving blocks have strictly DECREASING
    sizes and this order pairs each block with the sum of everything to its right — the
    same association the recursive "split off the largest aligned prefix" definition
    gives. Either direction would be reproducible; only one can be the definition, so it
    is written down here and versioned by `REDUCTION_SHAPE_ID`.
    """
    if len(vals) == 0:
        # Sum of nothing is 0 — a real answer, per numeric.contract.
        return 0.0
    var acc = vals[len(vals) - 1]
    for i in range(len(vals) - 2, -1, -1):
        acc = vals[i] + acc
    return acc


fn _first_non_finite(a: List[Float64], n: Int) -> Int:
    """Index of the first non-finite value in `a[0..n)`, or -1. Caller has bounded `n`.

    Non-finite input is refused rather than aggregated, for a reason specific to this
    file: the invariance property is asserted with `==`, and `nan != nan`. An `inf` and a
    `-inf` in the same array produce a `nan` whose bit pattern IS identical across
    chunkings, yet `==` reports them unequal — so the guarantee would become unverifiable
    exactly where it is most likely to be wrong. Uses `numeric.reduce.is_finite_value`
    rather than a second predicate (rule 3).
    """
    for i in range(n):
        if not is_finite_value(a[i]):
            return i
    return -1


fn _finish(total: Float64, n: Int) -> DetReduction:
    """Wrap a completed tree sum, refusing a result that is not representable.

    A sum of finite values can overflow to `inf`. The mathematical answer exists but this
    is not it, so it is reported absent rather than returned as `inf` (rule 4).
    """
    if not is_finite_value(total):
        return det_absent(n, DET_ERR_OVERFLOW)
    return DetReduction(total, True, n, DET_OK)


# ── public reductions ─────────────────────────────────────────────────────────


fn det_sum(a: List[Float64], n: Int) -> DetReduction:
    """Sum of `a[0..n)` under the fixed tree shape.

    Sum of nothing is 0.0 and present, matching `numeric.contract`: `count` and `sum` of
    nothing are real answers where a mean is not.

    @capability det_sum
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    var bad = _first_non_finite(a, n)
    if bad >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest(a, a, _LEAF_VALUE, 0, n, starts, sizes, vals)
    return _finish(_fold(vals), n)


fn det_sum_chunked(a: List[Float64], n: Int, chunk: Int) -> DetReduction:
    """Identical to `det_sum(a, n)`, computed as independent chunks of `chunk` elements.

    This exists to be compared, and to be the shape a parallel implementation takes: each
    chunk builds its own counter with no knowledge of its neighbours, and the chunk states
    are merged afterwards. The merged tree is the whole-array tree, so the result is
    bit-identical to `det_sum` for every `chunk >= 1`. `chunk >= n` is a single chunk;
    `chunk == 1` is one block per element.

    @capability det_sum_chunked
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if chunk < 1:
        return det_absent(n, DET_ERR_CHUNK)
    var bad = _first_non_finite(a, n)
    if bad >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)

    var acc_starts = _new_counter_int()
    var acc_sizes = _new_counter_int()
    var acc_vals = _new_counter_f64()
    # Declared outside the loop and CLEARED per chunk, not reallocated. Three allocations
    # per chunk is the difference between 3760 ms and 322 ms at `chunk = 1` over ten
    # million elements, and `chunk = 1` is the case a caller reaches for when proving the
    # invariance. Clearing keeps the "fresh counter per chunk" semantics exactly: nothing
    # is carried across a boundary, which is what makes the chunks independent.
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    var lo = 0
    while lo < n:
        var hi = lo + chunk
        if hi > n:
            hi = n
        starts.clear()
        sizes.clear()
        vals.clear()
        _ingest(a, a, _LEAF_VALUE, lo, hi, starts, sizes, vals)
        for b in range(len(sizes)):
            _push_leaf(acc_starts, acc_sizes, acc_vals, starts[b], sizes[b], vals[b])
        lo = hi
    return _finish(_fold(acc_vals), n)


fn det_mean(a: List[Float64], n: Int) -> DetReduction:
    """Arithmetic mean of `a[0..n)` — the fixed-tree sum divided by `n`.

    Division is a single rounding of a reproducible sum, so the mean inherits the
    invariance. Deliberately NOT Welford (`numeric.reduce.reduce_mean`): Welford's update
    is sequential by construction, so its result depends on traversal order and it cannot
    be the reproducible mean. Both definitions stay reachable.

    A mean of nothing does not exist: `n == 0` returns absent under `DET_EMPTY`, never
    0.0 and never under `DET_OK`. The emptiness policy is read from
    `numeric.contract.empty_yields_null` so there is one definition of it.

    @capability det_mean
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if n == 0 and empty_yields_null(AGG_AVG):
        return det_absent(0, DET_EMPTY)
    var total = det_sum(a, n)
    if not total.present:
        return det_absent(total.n, total.status)
    return _finish(total.value / Float64(n), n)


fn det_dot(a: List[Float64], b: List[Float64], n: Int) -> DetReduction:
    """Dot product of `a[0..n)` and `b[0..n)` under the fixed tree shape.

    Each product is a single rounding, so the only order-sensitive step is the summation,
    which is the tree. Refused unless `n` fits BOTH inputs — the frozen `sparse.sparse_matvec`
    crashes the process on a mismatch and that is the behaviour being avoided, not copied.

    @capability det_dot
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    - n <= len(b) [kernel_validated]
    @endcapability
    """
    if n < 0:
        return det_absent(0, DET_ERR_COUNT)
    if n > len(a) or n > len(b):
        return det_absent(0, DET_ERR_PAIR_LENGTH)
    if _first_non_finite(a, n) >= 0 or _first_non_finite(b, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest(a, b, _LEAF_PRODUCT, 0, n, starts, sizes, vals)
    return _finish(_fold(vals), n)


fn det_sum_squares(a: List[Float64], n: Int) -> DetReduction:
    """Sum of squares of `a[0..n)` under the fixed tree shape.

    Not `det_dot(a, a, n)` only because that would scan the same array twice for
    finiteness; the tree and the fold are the shared ones, and the results agree
    bit-for-bit (asserted in the suite).

    @capability det_sum_squares
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest(a, a, _LEAF_SQUARE, 0, n, starts, sizes, vals)
    return _finish(_fold(vals), n)


# ── the order-dependent baselines, kept in-tree so the claim stays measurable ──


fn det_naive_sum(a: List[Float64], n: Int) -> DetReduction:
    """Left-to-right sum of `a[0..n)`. NOT reproducible under chunking — that is the point.

    Present so the comparison in this module's docstring is a runnable assertion rather
    than a story, and so a caller can see for itself what the tree is buying. Validated
    on exactly the same path as `det_sum` so the two differ only in association order.

    @capability det_naive_sum
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var total: Float64 = 0.0
    for i in range(n):
        total = total + a[i]
    return _finish(total, n)


fn det_naive_sum_chunked(a: List[Float64], n: Int, chunk: Int) -> DetReduction:
    """Left-to-right sum of independently-summed chunks. Gives a DIFFERENT answer per `chunk`.

    The suite asserts that at least two chunk sizes disagree here, which is the failing
    baseline that makes `det_sum_chunked`'s `==` invariance a result instead of a tautology.

    @capability det_naive_sum_chunked
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if chunk < 1:
        return det_absent(n, DET_ERR_CHUNK)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var total: Float64 = 0.0
    var lo = 0
    while lo < n:
        var hi = lo + chunk
        if hi > n:
            hi = n
        var part: Float64 = 0.0
        for i in range(lo, hi):
            part = part + a[i]
        total = total + part
        lo = hi
    return _finish(total, n)


# ── compensated summation: less error, still not associative ──────────────────


fn det_kahan_sum(a: List[Float64], n: Int) -> DetReduction:
    """Kahan compensated sum of `a[0..n)`, via the frozen `numerical_stability.kahan_sum`.

    Calls the frozen kernel rather than compensating inline (rule 3), which costs one copy
    of the first `n` values because that kernel takes a whole `List`. Rule 1c arithmetic:
    ONE array of `n` `Float64` = `8n` bytes, and `n <= len(a)` is enforced first, so the
    allocation is bounded by an array the caller already holds — no separate ceiling is
    needed, and this is the only function in the module that allocates proportional to `n`.

    NOT chunk-invariant: the compensation is a single running scalar, so splitting the
    input splits it. Use `det_sum` when the answer has to be reproducible.

    @capability det_kahan_sum
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var head = List[Float64]()
    for i in range(n):
        head.append(a[i])
    return _finish(kahan_sum(head), n)


fn det_neumaier_sum(a: List[Float64], n: Int) -> DetReduction:
    """Neumaier compensated sum of `a[0..n)`. A different algorithm, not a rewrite.

    Kahan's `c = (t - s) - y` recovers the low bits of `s`, which is the wrong half
    whenever `|y| > |s|`; Neumaier branches on the comparison and recovers the low bits of
    whichever operand was smaller. Measured on `[1.0, 1e100, 1.0, -1e100]`, exact 2.0:
    `kahan_sum` returns 0.0 and this returns 2.0. That limit is why the frozen kernel is
    called for Kahan and not extended.

    What this does NOT do: make addition associative. It reduces the error of ONE
    traversal. It is sequential, so it is not reproducible under chunking — measured, same
    array: whole 2.0, split into two halves 0.0. `det_sum` is the reproducible path; this is
    the accurate one for a fixed traversal.

    @capability det_neumaier_sum
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    var s: Float64 = 0.0
    var c: Float64 = 0.0
    for i in range(n):
        var v = a[i]
        var t = s + v
        if (s if s >= 0.0 else -s) >= (v if v >= 0.0 else -v):
            c = c + ((s - t) + v)
        else:
            c = c + ((v - t) + s)
        s = t
    return _finish(s + c, n)


fn det_sum_opcode() -> Int:
    """The `numeric.contract` opcode this module's `det_sum` implements.

    Present so the aggregation vocabulary has one owner: a caller mapping a token to a
    reduction resolves it through `numeric.contract.parse_aggregation` and lands here,
    rather than this module inventing a second set of names.
    """
    return AGG_SUM
