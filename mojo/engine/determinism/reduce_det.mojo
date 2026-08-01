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

The shape is the aligned power-of-two decomposition of `[0, n)`, DEFINED by a binary
counter: a completed run of `2^k` consecutive elements starting at a multiple of `2^k`
collapses to one node, so every node is the perfect-tree sum of an aligned block. What
survives at the end is the canonical decomposition of `n` into descending powers of two —
for `n = 7` the blocks `[0,4) [4,6) [6,7)` — folded right-nested:
`P1 + (P2 + (P3 + ...))`.

The counter is the DEFINITION, not the method. That block set is a closed form of `n`, so
`_ingest` emits it directly instead of discovering it one element at a time, and
`_block_sum` computes each block's balanced sum with vector adds instead of a scalar
dependency chain. Same blocks, same pairing, same bits — see those two functions for the
exhaustive interval-by-interval equality check against the leaf-at-a-time counter, and see
the cost table below for what dropping the bookkeeping was worth.

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
Less than a sequential sum. That sentence used to read "about 2.4x a sequential sum", and
the change is worth stating plainly because the earlier number was not a property of
pairwise summation — it was the cost of DISCOVERING a block set that `n` already encodes.

Compiled binary (not the JIT), macOS arm64 (Mac16,6, 16 cores), n = 10,000,001 `Float64`,
min of 5 in ONE process with the previous implementation kept alongside as a verbatim
replica and the two interleaved rep by rep, so both rows saw the same machine:

                                       before      after
    sequential (`det_naive_sum`)       27.4 ms     15.8 ms
    fixed tree (`det_sum`)             67.8 ms      4.3 ms    15.6x faster
    tree / sequential                   2.48x       0.27x     the tree is now the CHEAPER
                                                              of the two
    `det_sum_chunked`, chunk 4096      72.8 ms      4.6 ms    15.7x faster
    `det_sum_chunked`, chunk = 1      545 ms      436 ms      about the same — see below

One column of one process, and three whole runs of that process put the before-ratio at
2.44x-2.58x, the after-ratio at 0.275x-0.299x and the tree's own speedup at 14.5x-15.6x, so
read the speedup as "about 15x" rather than as 15.6.

`det_sum_chunked(a, n, 1)` is the one configuration this did not speed up much, and the
figure above is a single shot: repeated, it gave 1.01x, 1.25x and 2.69x at 10,000,001
elements, and 1.30x-1.32x at n = 2^20 + 1 (min of 3). Read it as "unchanged, possibly
better"; a single shot of it is not a measurement. Either way it is the right place for the
cost to sit, and that it did not move is expected — a one-element chunk makes
every element its own block, so it takes none of the vector path and pays `_push_leaf` per
element into the cross-chunk merge, which is exactly what makes it the invariance
demonstration rather than a working configuration.

At n = 2^20 + 1 the bench itself reports, ns per element, min of 5: sequential 1.32, fixed
tree 0.38, frozen `kahan_sum` 6.02, Neumaier 1.46. So the tree is now cheaper than every
other summation in this file including the plain one.

Read the ratio, not the milliseconds — and do not read the ratio as more precise than it
is. This machine carried a load average near 90 from concurrent builds while these were
taken. TEN runs of the bench, five each from two compiled binaries of the same source:

    0.289x 0.291x 0.278x 0.460x 0.285x      0.289x 0.287x 0.287x 0.305x 0.282x

Nine inside 0.278x-0.305x and one outlier at 0.460x; the absolute nanoseconds moved by about
80% across the same ten. Two JIT runs gave 0.269x and 0.304x. So the honest claim is "the
tree costs roughly 0.3x a sequential sum, worst observed 0.46x", not 0.28x.
`benchmarks/mojo_benchmarks/bench_determinism_reduce_det.mojo` gates the ratio at 1.5x — 3.3x
clear of the worst of those ten — and gates no absolute time at all.

Note that the sequential row moved too, 27.4 ms to 15.8 ms, so the ratio is NOT flattered
by a slowed baseline — the baseline got 1.7x faster and the tree still overtook it. Every
public function here USED TO run `_first_non_finite` first, and once the tree was vectorised
that refusal pass — which computes none of the answer — was 88% of `det_sum`'s remaining cost
(1.68 of 1.90 ns/elem), so it was vectorised as well; `det_naive_sum` gets the same benefit
for free, which is where its own 1.7x comes from. The tree's own ~15x came from `_ingest` and
`_block_sum`.

The scan is no longer run first by ANYTHING. `_finish_screened` moved it behind the
"result is not finite" branch for every reduction in the file — see that function for why a
finite result proves every input was finite, and `det_sum` for the per-function before/after.

Where these land against reputable external references, measured on this machine
--------------------------------------------------------------------------------
Not against each other. Every figure below is a separate process launch per arm, arms
INTERLEAVED within a round and the launch order rotated per round, load average 24-34,
Apple M4 Max, ns per element hot (min over K launches / median over K). NumPy 2.5.1 on
scipy-openblas 0.3.33 and PyArrow 23.0.1, both pinned to one thread because every kernel
here is single-threaded — unpinned, OpenBLAS's threaded `ddot` collapses to 4.0 ms against
0.217 ms pinned on this contended box, and banking that would have flattered us ~18x.
Both sides build the array from the same counter-based recipe and print an XOR fingerprint
of all `n` raw bit patterns; the fingerprint set per configuration has size 1.

    n = 1,048,577, random mixed-sign          ours      reference          ratio
      det_sum          vs np.sum             0.1364    0.1723             1.26x / 1.16x
      det_sum          vs np.add.reduce      0.1364    0.1718             1.26x / 1.16x
      det_sum          vs pyarrow pc.sum     0.1364    0.1418             1.04x / 1.02x
      det_mean         vs np.mean            0.1497    0.1740             1.16x / 1.23x
      det_sum_squares  vs np.dot(a, a)       0.1020    0.1538             1.51x / 1.56x
      det_dot          vs np.dot(a, b)       0.2184    0.2249             1.03x / 1.04x
      det_neumaier_sum vs math.fsum          1.1349    5.6270             4.96x / 4.60x
      det_kahan_sum    vs math.fsum          3.3197    5.6270             1.70x / 1.73x

    n = 16,777,217 (134 MB, out of every cache)
      det_sum          vs np.sum             0.1373    0.1725             1.26x / 1.14x
      det_sum          vs pyarrow pc.sum     0.1373    0.1382             1.01x / 1.02x
      det_sum_squares  vs np.dot(a, a)       0.1087    0.1533             1.41x / 1.42x
      det_dot          vs np.dot(a, b)       0.1892    0.2066             1.09x / 1.07x

ACCURACY, ulps from `math.fsum` (correctly rounded) on the same inputs: `det_sum` -1 where
`np.sum` is -2 and `pyarrow` +7; `det_sum_squares` 0 where `np.dot(a,a)` is -3;
`det_dot` +2 where `np.dot(a,b)` is -25; `det_mean` -1 where `np.mean` is -2. On
`[1e16] + (n-1) x 1.0` the tree is EXACT and all three references are -8. That is
input-dependent and must not be read as a general claim of higher accuracy — it is a
statement about these inputs.

WHAT DOES NOT WIN, kept here because a page that hides it is worse than no page:
`det_naive_sum` is 0.15x of `np.sum` — 6.6x SLOWER. It is the deliberately order-dependent
baseline and exists to be beaten, so its speed is not a claim; but the internal
tree/sequential ratio this file prints is a ratio against something an order of magnitude
off the state of the art, and it should never be the headline. The external ratios above
are the ones that mean anything.

Where the ~15x came from, measured at n = 1048577, compiled, min of 5:

    per-8-element counter bookkeeping removed   4.36 of 6.23 ns/elem   70%
      (three `append`s, an amortised collapse of three indexed loads, three compares, two
       indexed stores and three `pop`s, plus a runtime integer division for the alignment
       test — none of it an addition of the answer)
    of that, the runtime `%` alone                     0.38 ns/elem     6%
    the rest: 31 scalar adds on a dependency chain per 32 elements became five vector adds

Three earlier revisions of this file were 9.7x, 8.5x and 2.4x the sequential sum. Every one
of those numbers was measured, and the tree is bit-identical across all four: every expected
value in the suite is unchanged, `REDUCTION_SHAPE_ID` is unchanged because a bit-identical
reduction is the same function, and `det_sum == det_sum_chunked(a, n, 1)` cross-checks the
block-at-a-time route against the one-leaf-at-a-time route on every input the suite carries.

A caller that does not need a reproducible answer can still use `numeric.reduce.reduce_sum`;
it is simply no longer true that reproducibility is what it would be paying for.

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
from std.algorithm import parallelize

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

    Since `_ingest` was rewritten to push whole aligned blocks (see there), this runs
    O(log n) times per interval rather than once per element, and only the cross-chunk
    merge in `det_sum_chunked` can make it collapse at all. It is still the ONE place a
    collapse is defined, so a chunk boundary and a whole-array traversal cannot drift.
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
        # `starts[j-1] % (2 * sizes[j-1]) != 0` with a bitmask instead of a divide. Every
        # `sizes` entry is a power of two by construction — entries enter as one and only
        # ever double — so `x % 2^k` is `x & (2^k - 1)` exactly, not approximately. The
        # divisor is runtime-variable, so the `%` spelling lowered to a hardware sdiv that
        # no strength reduction could remove: measured 0.38 ns/elem of the tree's cost.
        if (starts[j - 1] & (2 * sizes[j - 1] - 1)) != 0:
            break
        vals[j - 1] = vals[j - 1] + vals[j]
        sizes[j - 1] = sizes[j - 1] * 2
        _ = starts.pop()
        _ = sizes.pop()
        _ = vals.pop()


fn _new_counter_f64() -> List[Float64]:
    """A counter column, pre-reserved to its hard bound so no push ever reallocates.

    `COUNTER_CAPACITY` is derived from the two-blocks-per-level bound beside its
    definition, so this is a proof that no push reallocates rather than a hint.

    Reserving it was worth 252.6 ms -> 186.2 ms at 10,000,001 elements back when `_ingest`
    pushed one leaf at a time and the reduction really was dominated by push/pop
    bookkeeping. `_ingest` now pushes O(log n) whole blocks, so the reservation is worth
    almost nothing in time — it is kept because it is what makes the O(log n) working-memory
    claim in this module's docstring a proof (no reallocation on any input) rather than a
    typical case, and `det_sum_chunked` still runs `_push_leaf` once per surviving block per
    chunk.
    """
    return List[Float64](capacity=COUNTER_CAPACITY)


fn _new_counter_int() -> List[Int]:
    return List[Int](capacity=COUNTER_CAPACITY)


# Leaf modes, so ONE ingestion path serves sum, dot product and sum of squares. Three
# copies of the tree walk is how the copies drift (rule 3 applies inside a package too).
comptime _LEAF_VALUE: Int = 0
comptime _LEAF_PRODUCT: Int = 1
comptime _LEAF_SQUARE: Int = 2

# Lanes per vector load in `_block_sum`. The `if size == ...` ladder there is written for
# exactly this width: it must hand-dispatch every power of two BELOW it, because a vector
# width is a compile-time parameter and a block size is not. Raising this constant means
# extending that ladder. It does not change the tree — the tree is the balanced pairing,
# and `_vec_balanced` computes that pairing at any width.
comptime VEC_WIDTH: Int = 32


fn _leaf[mode: Int](a: List[Float64], b: List[Float64], i: Int) -> Float64:
    """The value the tree's leaf `i` carries. Caller has already bounded `i`.

    `mode` is a compile-time parameter, not a runtime `Int`: it is a literal at all five
    call sites, and as a runtime argument it cost two compares per leaf — 16 per 8-element
    group — to re-decide something already known when the binary was built.
    """
    comptime if mode == _LEAF_PRODUCT:
        return a[i] * b[i]
    elif mode == _LEAF_SQUARE:
        return a[i] * a[i]
    else:
        return a[i]


fn _leaf_vec[
    mode: Int, W: Int
](
    ap: UnsafePointer[Float64, ...], bp: UnsafePointer[Float64, ...], i: Int
) -> SIMD[DType.float64, W]:
    """`W` consecutive leaf values as one vector. Lane `k` is exactly `_leaf(..., i + k)`.

    `alignment=8` is deliberate and required: a block is aligned to its own SIZE in
    ELEMENTS, which says nothing about the byte alignment of `List`'s heap buffer, so
    asking for natural vector alignment would be asking for an address the allocator never
    promised. An unaligned vector load is the correct instruction here, not a fallback.
    """
    var av = ap.load[width=W, alignment=8](i)
    comptime if mode == _LEAF_PRODUCT:
        return av * bp.load[width=W, alignment=8](i)
    elif mode == _LEAF_SQUARE:
        return av * av
    else:
        return av


fn _vec_balanced[W: Int](v: SIMD[DType.float64, W]) -> Float64:
    """The balanced tree over `W` lanes, one vector add per level. `W` a power of two.

    `deinterleave()` splits even lanes from odd, so `even + odd` is exactly the
    adjacent-pair level of the balanced tree with lane order preserved, and recursing on
    the result walks the tree level by level. Each lane is an independent IEEE-754 double
    add, so this is not a vectorised APPROXIMATION of the tree — it is the same additions,
    in the same pairing, issued sideways instead of one at a time. `W = 32` becomes five
    vector adds and four shuffles for what was 31 scalar adds on a dependency chain.
    """
    comptime if W == 1:
        return v[0]
    else:
        var half = v.deinterleave()
        return _vec_balanced[W // 2](
            rebind[SIMD[DType.float64, W // 2]](half[0] + half[1])
        )


fn _block_sum[mode: Int](
    a: List[Float64], b: List[Float64], offset: Int, size: Int
) -> Float64:
    """Balanced-tree sum of the `size` leaves at `offset`. `size` is a power of two.

    A perfect power-of-two block has exactly ONE balanced tree, so this is bit-identical to
    feeding those leaves into `_push_leaf` one at a time and letting the counter collapse
    them — which is what this module used to do. Verified exhaustively rather than argued:
    see `_ingest`.

    Above `VEC_WIDTH` the block is walked in vector-sized chunks whose subtotals go into a
    binary carry counter held in registers. `lvl[j]` holds the subtotal of
    `VEC_WIDTH * 2^j` elements, and chunk `m` collapses exactly `trailing_ones(m)` times —
    the counter's own rule, read off the loop index instead of stored, because inside a
    perfect block every chunk is aligned and no alignment test can fail.
    """
    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    if size == 1:
        return _leaf[mode](a, b, offset)
    if size == 2:
        return _vec_balanced[2](_leaf_vec[mode, 2](ap, bp, offset))
    if size == 4:
        return _vec_balanced[4](_leaf_vec[mode, 4](ap, bp, offset))
    if size == 8:
        return _vec_balanced[8](_leaf_vec[mode, 8](ap, bp, offset))
    if size == 16:
        return _vec_balanced[16](_leaf_vec[mode, 16](ap, bp, offset))
    var lvl = InlineArray[Float64, MAX_TREE_LEVELS](fill=0.0)
    var chunks = size // VEC_WIDTH
    var top = 0
    for m in range(chunks):
        var carry = _vec_balanced[VEC_WIDTH](
            _leaf_vec[mode, VEC_WIDTH](ap, bp, offset + m * VEC_WIDTH)
        )
        var mm = m
        var j = 0
        while (mm & 1) == 1:
            carry = lvl[j] + carry
            mm >>= 1
            j += 1
        lvl[j] = carry
        if j > top:
            top = j
    # `chunks` is a power of two, so the counter ends with exactly one occupied level and
    # it is the highest one ever written.
    return lvl[top]


fn _pow2_floor(v: Int) -> Int:
    """Largest power of two `<= v`. Caller guarantees `v >= 1`."""
    var p = 1
    while (p << 1) <= v:
        p <<= 1
    return p


fn _block_span(start: Int, remaining: Int) -> Int:
    """Size of the aligned block the tree puts at `start` when `remaining` leaves are left.

    The largest `2^k` that both divides `start` and fits in `remaining`. `start & -start`
    isolates the lowest set bit of `start`, which IS the largest power of two dividing it;
    `start == 0` divides by every power of two, so only the fit binds there.
    """
    var fits = _pow2_floor(remaining)
    if start == 0:
        return fits
    var align = start & -start
    return align if align < fits else fits


fn _ingest[mode: Int](
    a: List[Float64], b: List[Float64], lo: Int, hi: Int,
    mut starts: List[Int], mut sizes: List[Int], mut vals: List[Float64]
):
    """Feed `[lo, hi)` into the counter as whole aligned blocks. The ONE place leaves enter.

    The block set the counter ends up holding for `[lo, hi)` is not something that has to
    be DISCOVERED by pushing leaves and watching them collapse — it is a closed form. At
    each position the tree takes the largest aligned power-of-two block that fits, which is
    `_block_span`, and those blocks are pairwise non-mergeable by construction, so the
    counter's collapse loop has nothing left to do. Sizes rise to a peak and then fall:
    `[3, 10)` is `{3} [4,8) [8,10)`, exactly as `_push_leaf`'s docstring records.

    This is the whole optimisation. The previous revision pushed one leaf (or one 8-wide
    run) at a time and paid, per 8 elements, three `List.append`s, an amortised collapse of
    three indexed loads, three comparisons, two indexed stores and three `pop`s, and a
    runtime integer division for the alignment test. None of it computed a single addition
    of the answer; all of it re-derived structure that `n` already encodes. Measured at
    n = 1048577, compiled, min of 5: that bookkeeping was 4.36 of the tree's 6.23 ns/elem —
    70% of the cost of a reduction whose useful work is `n - 1` additions.

    Blocks still go through `_push_leaf` rather than straight into the columns. That is not
    ceremony: `det_sum_chunked` calls this with an arbitrary `lo` and then merges chunk
    states, and pushing a whole aligned block is bit-identical to pushing its leaves —
    a partly-formed sub-block of an aligned block can never be a true sibling of whatever
    the counter already holds, so it cannot merge leftwards before it is complete. One
    collapse rule, used by both routes.

    Bit-identity against the leaf-at-a-time counter is not asserted, it is measured: the
    resulting `(starts, sizes, vals)` triples were compared entry for entry and bit for bit
    over every `(lo, hi)` with `0 <= lo <= hi <= 192` in `_LEAF_VALUE` mode, every
    `(lo, hi) <= 96` in `_LEAF_PRODUCT` and `_LEAF_SQUARE` mode, sixteen wide/offset ranges,
    and every chunk boundary produced by chunk sizes 1..60 over a 1037-element array —
    33,247 intervals, zero differences. `det_sum == det_sum_chunked(a, n, 1)` in the suite
    then keeps the two routes cross-checked on every input the suite carries.
    """
    var start = lo
    while start < hi:
        var size = _block_span(start, hi - start)
        _push_leaf(
            starts, sizes, vals, start, size, _block_sum[mode](a, b, start, size)
        )
        start += size


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
    exactly where it is most likely to be wrong.

    This is a SECOND full pass over the data, and once the tree itself was vectorised it
    became the dominant cost of every public reduction here — measured 1.68 of `det_sum`'s
    total 1.90 ns/elem, i.e. 88%, for a pass that computes none of the answer. So it is
    screened a vector at a time.

    `numeric.reduce.is_finite_value` remains the ONLY definition of finiteness (rule 3):
    the vector step is a SKIP filter, never an answer. `v - v` is exactly `+0.0` for every
    finite `v` including subnormals, and `nan` for both `inf` and `nan`, so
    `(v - v).eq(0).reduce_and()` is the same predicate as
    `not isnan and not isinf` applied lanewise — and any vector it does not clear is handed
    straight to the scalar `is_finite_value` loop, which is what actually decides and what
    reports the index. A screen that were ever wrong in the accepting direction could only
    make this pass slower, not more permissive.
    """
    var ap = a.unsafe_ptr()
    var i = 0
    var vec_end = n - VEC_WIDTH
    while i <= vec_end:
        var v = ap.load[width=VEC_WIDTH, alignment=8](i)
        var d = v - v
        # `.eq` is the LANEWISE comparison. Spelling it `==` binds to the scalar
        # `EqualityComparable` overload, which collapses 32 lanes to one Bool and would
        # have made this screen answer a question nobody asked.
        if d.eq(SIMD[DType.float64, VEC_WIDTH](0.0)).reduce_and():
            i += VEC_WIDTH
            continue
        # Something in this vector is not finite. The frozen predicate says which.
        for k in range(i, i + VEC_WIDTH):
            if not is_finite_value(a[k]):
                return k
        i += VEC_WIDTH
    for k in range(i, n):
        if not is_finite_value(a[k]):
            return k
    return -1


fn _finish(total: Float64, n: Int) -> DetReduction:
    """Wrap a completed tree sum, refusing a result that is not representable.

    A sum of finite values can overflow to `inf`. The mathematical answer exists but this
    is not it, so it is reported absent rather than returned as `inf` (rule 4).
    """
    if not is_finite_value(total):
        return det_absent(n, DET_ERR_OVERFLOW)
    return DetReduction(total, True, n, DET_OK)


fn _finish_screened(
    total: Float64, a: List[Float64], b: List[Float64], n: Int, pair: Bool
) -> DetReduction:
    """`_finish`, plus the non-finite screen — run ONLY when the result is not finite.

    THE ONE PLACE the reordering argument lives, so that every reduction in this file
    reaches it by calling this rather than by repeating it. `pair` selects whether `b`
    participates; `det_dot` is the only caller that passes True.

    WHY A FINITE RESULT IS A PROOF THAT EVERY INPUT WAS FINITE. Every reduction in this
    module combines its leaves with IEEE-754 addition and nothing else, and addition cannot
    turn a non-finite value back into a finite one: `nan + x` is `nan` for every `x`,
    `+inf + finite` is `+inf`, and `+inf + -inf` is `nan`. So one non-finite leaf makes the
    result non-finite, and by contraposition a FINITE result proves all `n` leaves were
    finite. For the leaf itself: `a[i]` is the value, `a[i] * a[i]` and `a[i] * b[i]` are
    products, and a product with a non-finite operand is never finite — `inf * x` is `±inf`
    for `x != 0` and `nan` for `x == 0`, and `nan * x` is always `nan` — so a finite leaf
    proves its operands finite too.

    The screen is therefore not removed, it is MOVED behind a branch that a well-formed
    input never takes. It is still what decides between the two refusals: an input
    containing a non-finite value is `DET_ERR_NON_FINITE`, and an all-finite input whose
    total left the range is `DET_ERR_OVERFLOW`. Both statuses survive with the same
    meaning, and on the success path the returned Float64 is bit-identical because it is
    the same `_fold` of the same tree.

    WHAT IT COSTS, and it is a real cost on a real path: refusal is now O(n) for the
    computation plus O(n) for the screen instead of exiting at the first bad element, so an
    array whose first element is `nan` does all the work. It is bounded by roughly twice
    what the caller already spent materialising the array, it is an error path, and the
    trade is taken deliberately in this direction. `det_sum`'s docstring carries the
    measurement that justifies it.
    """
    if is_finite_value(total):
        return DetReduction(total, True, n, DET_OK)
    if _first_non_finite(a, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    if pair and _first_non_finite(b, n) >= 0:
        return det_absent(n, DET_ERR_NON_FINITE)
    return det_absent(n, DET_ERR_OVERFLOW)


# ── public reductions ─────────────────────────────────────────────────────────


fn det_sum(a: List[Float64], n: Int) -> DetReduction:
    """Sum of `a[0..n)` under the fixed tree shape.

    Sum of nothing is 0.0 and present, matching `numeric.contract`: `count` and `sum` of
    nothing are real answers where a mean is not.

    The refusal screen runs AFTER the tree, not before, and that is a correctness argument
    rather than a shortcut. A non-finite summand cannot produce a finite total: `nan`
    propagates through every add, `+inf` with `-inf` gives `nan`, and `+inf` with finite
    values gives `+inf`. So a finite total is a PROOF that every one of the `n` inputs was
    finite, and the screen is only needed on the non-finite total to say WHICH of
    `DET_ERR_NON_FINITE` and `DET_ERR_OVERFLOW` applies — a distinction this module makes
    and keeps. Every status this function can return is unchanged, and the returned Float64
    is bit-identical, because on the success path it is the same `_fold(_ingest(...))`.

    What it buys: `_first_non_finite` is a SECOND full pass that computes none of the
    answer, and it was 56% of this function's cost — measured at n = 1,048,577 with the two
    variants interleaved rep by rep in one process, 0.381 ns/element shipped against 0.167
    ns/element fused, min of 5, load average 350. That is the difference between losing to
    `np.sum` by 1.96x and beating it; see `gitbook/benchmarks/deterministic-reduction.md`.

    What it costs: the REFUSAL path is now O(n) twice instead of exiting at the first bad
    element, so an input whose first element is `nan` does the full tree and then the full
    screen. That is bounded by twice the work the caller already spent materialising the
    array, and it is an error path, so the trade is taken deliberately in this direction.

    The argument now lives in `_finish_screened` and EVERY reduction in this file routes
    through it, so none of them pays a second full pass on the success path. `det_dot`
    saved two passes rather than one. Measured the same way — a verbatim replica of each
    OLD body kept alongside the new one and the two interleaved rep by rep in ONE process,
    min of 9, n = 1,048,577, three runs at load average 48-84, and every pair asserted to
    return identical BITS before any timing was read — ns per element, before -> after:

        det_sum_squares          0.290 - 0.314  ->  0.112 - 0.121     2.58 - 2.61x
        det_dot                  0.557 - 0.605  ->  0.202 - 0.218     2.75 - 2.77x
        det_sum_chunked(4096)    0.320 - 0.351  ->  0.146 - 0.158     2.20 - 2.22x
        det_kahan_sum            5.147 - 5.194  ->  3.352 - 3.353     1.54x
        det_naive_sum                    1.188  ->  0.997             1.19x
        det_neumaier_sum         1.188 - 1.297  ->  1.010 - 1.101     1.18x

    The three that move by more than 2x are the ones whose own work was comparable to a
    scan; the compensated and sequential arms move by ~1.2x because their loops cost several
    times what a scan costs, so removing one scan is proportionally less. `det_kahan_sum`
    is in between because it also stopped copying — see there.

    @capability det_sum
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest[_LEAF_VALUE](a, a, 0, n, starts, sizes, vals)
    return _finish_screened(_fold(vals), a, a, n, False)


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
        _ingest[_LEAF_VALUE](a, a, lo, hi, starts, sizes, vals)
        for b in range(len(sizes)):
            _push_leaf(acc_starts, acc_sizes, acc_vals, starts[b], sizes[b], vals[b])
        lo = hi
    return _finish_screened(_fold(acc_vals), a, a, n, False)


fn det_sum_parallel(a: List[Float64], n: Int, n_workers: Int) -> DetReduction:
    """`det_sum(a, n)` computed on `n_workers` threads. BIT-IDENTICAL for every worker count.

    Why this is possible at all, and why it is the module's strongest property
    -------------------------------------------------------------------------
    A parallel floating-point reduction normally cannot be reproducible: the answer depends on
    which partial sums happened to combine first, so it varies with thread count, with
    scheduling, and between runs. That is why `numpy.sum` makes no cross-platform bit-identity
    promise and why an OpenMP `reduction(+:x)` gives a different answer on a different machine.

    Here the tree's SHAPE is a pure function of `n` alone. A worker owning `[lo, hi)` builds
    exactly the blocks that interval contributes to the whole-array tree — `_ingest` takes the
    largest aligned power-of-two block at each position, and that choice depends only on the
    position, never on what any other worker is doing. Merging the workers' block lists left to
    right through `_push_leaf` then rebuilds precisely the tree `det_sum` walks.

    So the additions are the same additions, associated the same way, in the same order. Not
    "close enough" — the same. `det_sum_parallel(a, n, k) == det_sum(a, n)` bit-for-bit for
    every `k`, which the suite asserts with `==` rather than a tolerance.

    This is what the fixed shape was FOR. `det_sum_chunked`'s docstring calls itself "the shape
    a parallel implementation takes"; this is that implementation, with the chunks computed
    concurrently instead of in sequence.

    The measurement that motivated it
    ---------------------------------
    A STREAM measurement on this host (`benchmarks/mojo_benchmarks/measure_stream_bandwidth.mojo`,
    16 physical cores, 8 lanes) puts the memory ceiling at ~271 GB/s. Single-threaded `det_sum`
    moves 8 bytes per element at ~0.34 ns/element, which is ~23.5 GB/s — under 9% of that
    ceiling. The gap was never arithmetic; it was one thread.

    Merging is SEQUENTIAL and that is deliberate
    --------------------------------------------
    Only the per-worker ingests run concurrently. The merge walks the workers in index order,
    because the order the blocks enter `_push_leaf` is what determines which siblings collapse —
    merging them in completion order would produce a different, run-dependent tree and destroy
    the entire property. The merge is O(workers * log n), which is nothing beside the O(n)
    ingest.

    `n_workers <= 0` is treated as 1 rather than refused: a caller passing a computed core count
    that came back zero wants a working reduction, not an error, and one worker is exactly
    `det_sum`. Workers beyond `n` are idle, not an error.

    @capability det_sum_parallel
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n:
        workers = n
    if workers <= 1 or n == 0:
        return det_sum(a, n)

    # Each worker's block list is collected into its own slot, so no two workers touch the
    # same memory and no lock is needed. Sized `workers` exactly.
    var w_starts = List[List[Int]](capacity=workers)
    var w_sizes = List[List[Int]](capacity=workers)
    var w_vals = List[List[Float64]](capacity=workers)
    for _ in range(workers):
        w_starts.append(_new_counter_int())
        w_sizes.append(_new_counter_int())
        w_vals.append(_new_counter_f64())

    # Contiguous bands. The band boundary is arbitrary — any partition gives the same answer,
    # which is the point — so it is chosen to balance work rather than to align to the tree.
    var band = (n + workers - 1) // workers
    var sp = w_starts.unsafe_ptr()
    var zp = w_sizes.unsafe_ptr()
    var vp = w_vals.unsafe_ptr()

    @parameter
    fn ingest_band(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n:
            hi = n
        if lo < hi:
            _ingest[_LEAF_VALUE](a, a, lo, hi, sp[w], zp[w], vp[w])

    parallelize[ingest_band](workers)

    # Sequential merge in WORKER INDEX order — see the docstring on why not completion order.
    var acc_starts = _new_counter_int()
    var acc_sizes = _new_counter_int()
    var acc_vals = _new_counter_f64()
    for w in range(workers):
        for b in range(len(w_sizes[w])):
            _push_leaf(
                acc_starts, acc_sizes, acc_vals,
                w_starts[w][b], w_sizes[w][b], w_vals[w][b],
            )
    # `_finish_screened`, not `_finish`, and that FIXES a status inconsistency this function
    # had: it never screened at all, so a `nan` in the input came back `DET_ERR_OVERFLOW`
    # here while the same array through `workers <= 1` — which delegates to `det_sum` —
    # came back `DET_ERR_NON_FINITE`. The status therefore depended on the worker count, in
    # the one function whose entire point is that nothing depends on the worker count. It
    # cost nothing to fix because the screen now runs only on a non-finite total, which is
    # exactly the case that was reporting the wrong reason. Gated in the suite across
    # worker counts 1..5 on a poisoned array.
    return _finish_screened(_fold(acc_vals), a, a, n, False)


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
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest[_LEAF_PRODUCT](a, b, 0, n, starts, sizes, vals)
    # `pair=True`: on a non-finite total BOTH inputs are screened, because either could be
    # the one carrying it. This function saved TWO full passes rather than one — it screened
    # `a` and then `b` before computing anything — which is why it moved further than any
    # other reduction here: 0.550 -> 0.194 ns/element.
    return _finish_screened(_fold(vals), a, b, n, True)


fn det_sum_squares(a: List[Float64], n: Int) -> DetReduction:
    """Sum of squares of `a[0..n)` under the fixed tree shape.

    Not `det_dot(a, a, n)` — the tree and the fold are the shared ones, and the results
    agree bit-for-bit (asserted in the suite). The reason used to be that `det_dot` would
    scan the same array twice for finiteness; since neither scans on the success path that
    is no longer it, and what remains is that `_LEAF_SQUARE` reads one array where
    `_LEAF_PRODUCT` reads two, which is half the loads for the same answer.

    An element can be finite while its SQUARE overflows — `1e200 * 1e200` is `+inf`. That
    lands on `DET_ERR_OVERFLOW`, not `DET_ERR_NON_FINITE`, because the screen finds every
    input finite; the sum of squares really did leave the range. Gated in the suite.

    @capability det_sum_squares
    complexity: O(n)
    counts:
    - n <= len(a) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(a):
        return det_absent(0, DET_ERR_COUNT)
    var starts = _new_counter_int()
    var sizes = _new_counter_int()
    var vals = _new_counter_f64()
    _ingest[_LEAF_SQUARE](a, a, 0, n, starts, sizes, vals)
    return _finish_screened(_fold(vals), a, a, n, False)


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
    var total: Float64 = 0.0
    for i in range(n):
        total = total + a[i]
    return _finish_screened(total, a, a, n, False)


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
    return _finish_screened(total, a, a, n, False)


# ── compensated summation: less error, still not associative ──────────────────


fn det_kahan_sum(a: List[Float64], n: Int) -> DetReduction:
    """Kahan compensated sum of `a[0..n)`, via the frozen `numerical_stability.kahan_sum`.

    Calls the frozen kernel rather than compensating inline (rule 3). That kernel takes a
    whole `List` and sums all of it, so a request for a PREFIX needs a copy — but only then.

    THE COPY IS SKIPPED WHEN `n == len(a)`, which is the whole-array call and the one every
    benchmark and almost every caller makes. `kahan_sum` takes its argument by reference and
    reads `len(values)`, so when the requested count already IS the list's length the list
    can be handed over as it stands and the answer is the same additions in the same order —
    not equivalent, identical, because it is literally the same call on the same memory.

    ATTRIBUTED BY STAGE TIMING, not by reading, because the obvious suspect was wrong. The
    cost here looked like compensated arithmetic; it was mostly bookkeeping. At
    n = 1,048,577, min of 7, load average 30, ns per element: the whole function 4.030, of
    which `kahan_sum` itself 3.087, the copy 1.583, the refusal screen 0.175. So the copy
    was 39% of the cost and the copy was `append` into an UNRESERVED `List` — it
    reallocated and recopied the whole array on the way up. `capacity=n` alone brings it to
    1.373 and a `memcpy` to 0.237, but not copying at all is free, so that is what the
    whole-array path does. Prefix requests still copy, and now with `capacity=n` reserved.

    Whole function, before against after, in the same interleaved in-process A/B the module
    docstring tabulates: 5.147-5.194 -> 3.352-3.353 ns/element, 1.54x, bits identical.

    WHAT IS LEFT IS THE FROZEN KERNEL, and it is 3.087 of the remaining ~3.35 ns/element —
    92%. It is latency-bound, not throughput-bound: `y = v - c; t = s + y; c = (t - s) - y`
    is a three-add dependency chain through `c` that must complete before the next element
    starts, so it cannot vectorise and no amount of work here can speed it up. Making it
    faster means changing `numerical_stability.kahan_sum`, which is frozen. Reported as a
    finding instead; `det_neumaier_sum` is the compensated arm that does win.

    Rule 1c arithmetic for the path that still allocates: ONE array of `n` `Float64` = `8n`
    bytes, and `n <= len(a)` is enforced first, so it is bounded by an array the caller
    already holds.

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
    if n == len(a):
        return _finish_screened(kahan_sum(a), a, a, n, False)
    var head = List[Float64](capacity=n)
    for i in range(n):
        head.append(a[i])
    return _finish_screened(kahan_sum(head), a, a, n, False)


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
    # `s + c` non-finite is enough to reach the screen, and the compensation cannot hide a
    # poisoned input from it: the step that first meets a non-finite `v` sets `t` non-finite
    # and takes the `else` branch — `|s| >= |v|` is false for `v` infinite and false for
    # `v` NaN, comparisons with NaN being false — so `c` picks up `(v - t) + s`, which is
    # `inf - inf` or `nan`, i.e. NaN. From then on both `s` and `c` stay non-finite. Gated
    # in the suite by a poison sweep at every position.
    return _finish_screened(s + c, a, a, n, False)


fn det_sum_opcode() -> Int:
    """The `numeric.contract` opcode this module's `det_sum` implements.

    Present so the aggregation vocabulary has one owner: a caller mapping a token to a
    reduction resolves it through `numeric.contract.parse_aggregation` and lands here,
    rather than this module inventing a second set of names.
    """
    return AGG_SUM
