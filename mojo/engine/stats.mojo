"""
Statistics utilities and introsort (iterative, median-of-3, stack-safe).

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_stats.mojo
benchmark: benchmarks/mojo_benchmarks/bench_stats.mojo
docs: none
version_introduced: pre_manifest
deprecation_state: active
@endcapability
"""
from std.math import sqrt


def compute_mean(v: List[Float64], n: Int) -> Float64:
    """Arithmetic mean of the first `n` values.

    Re-derived from the body, not from the previous block: the only reads are `v[i]` for `i` in
    `[0, n)`, a negative or zero `n` makes `range(n)` empty and reads nothing, so
    `n <= len(v)` is the COMPLETE requirement and nothing here checks it. `[enforced]` is
    therefore true and sufficient.

    Sufficient for the READS. It does not make the function safe: `n = 0` satisfies the
    relation and returns `0.0/0.0`, and a NON-FINITE Float64 return ends the worker process
    (MEASURED: `compute_mean(five, 0)` and `compute_mean([1e308, 1e308], 2)` each took the
    serving pid to gone, `os.kill(pid, 0)` confirming the process itself was dead, not just the
    session). That is a serialization defect on the result path, outside what any count
    relation can express, and it is reported separately rather than papered over here -- a
    count relation must not be widened to imply a guarantee it does not give.

    @capability compute_mean
    complexity: O(n)
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    var t: Float64 = 0.0
    for i in range(n): t += v[i]
    return t / Float64(n)

def compute_variance(v: List[Float64], n: Int, mean: Float64) -> Float64:
    """Sample variance of the first `n` values about a caller-supplied `mean`.

    Reads `v[i]` for `i` in `[0, n)` behind an `n <= 1` early return, so `n <= len(v)` is the
    complete read requirement and nothing here checks it. The non-finite-return hazard noted on
    `compute_mean` applies to this result too.

    @capability compute_variance
    complexity: O(n)
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    if n <= 1: return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        var d = v[i] - mean; s += d * d
    return s / Float64(n - 1)

def compute_std(v: List[Float64], n: Int, mean: Float64) -> Float64:
    """Sample standard deviation (ddof=1) of the first `n` values about a caller-supplied
    `mean` -- `sqrt(compute_variance(v, n, mean))`, computed in ONE kernel call instead of
    two plus a caller-side square root.

    This exists because a caller without it has to call `compute_mean` then
    `compute_variance` and then take the square root ITSELF, outside the kernel -- and a
    manual client-side sqrt of a float already computed by this engine is exactly the kind
    of second, independent recomputation this module's sibling kernels are built to avoid.
    Measured concretely on `test_files/Processed_Quotes.csv`'s UNIT_PRICE column (see
    `benchmarks/algenta_llm_tools/eval/probe_compute_std_kernel.py`): the uplift benchmark's
    q05 previously had a tool-calling model do `execute(compute_mean)` +
    `execute(compute_variance)` and then take a manual square root itself, landing on
    2332.003 against a true `numpy(ddof=1)` value of 2331.963152 -- a real, measured error
    from that extra, model-side arithmetic step. `sqrt(compute_variance(...))` computed
    here, in double precision, in the same kernel call as the variance itself, removes that
    step (and its error) entirely: there is no intermediate value for a caller to round,
    retype, or misplace a digit of.

    Delegates its read entirely to `compute_variance`, so the identical requirement applies
    here unchanged: reads `v[i]` for `i` in `[0, n)` behind `compute_variance`'s own `n <= 1`
    early return, and `n <= len(v)` is the complete read requirement. The non-finite-return
    hazard noted on `compute_mean` and `compute_variance` applies to this result too --
    `compute_variance` never returns a negative number for finite input, so `sqrt` here
    never sees a negative argument and introduces no new failure mode of its own.

    @capability compute_std
    complexity: O(n)
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    return sqrt(compute_variance(v, n, mean))

def pctile(v: List[Float64], n: Int, p: Int) -> Float64:
    """O(1) percentile index into a PRE-SORTED buffer of `n` values (`p` in [0,100]).

    `p` is not a count: it selects a rank inside the first `n` values, and the index it
    produces is clamped to `[0, n-1]`. `n` is the count, and the clamp is to `n`, not to
    the list -- so `n > len(v)` reads past the end for large `p`.

    TWO conditions are required, not one. The `max(0, ...)` floor means index 0 is read
    UNCONDITIONALLY -- for every `n` and every `p`, including `n = 0` and a negative `n`. So
    `n <= len(v)` alone is not sufficient: `pctile([], 0, 50)` satisfies it and still reads
    `v[0]`. MEASURED against the compiled worker before this line existed: it ended the
    serving pid. The reachable internal callers are why that matters --
    `engines/monte_carlo.mojo:494` calls `pctile(mo, len(mo), 5)`, which is this exact shape
    whenever `mo` is empty.

    NOT EXPRESSIBLE IN THE COUNT-RELATION GRAMMAR, therefore checked here:

        1 <= len(v)          -- a minimum length tied to no count parameter

    The grammar's left side must be a parameter name (`expr := term [+ INT]`,
    `term := NAME {* NAME}`), so a bare constant lower bound cannot be written at all, and the
    nearest expressible spelling, `n + 1 <= len(v)`, would refuse the primary use
    (`pctile(five_values, 5, p)`). Writing that would be the `tensorx/pack.mojo` tautology
    mistake in the other direction: a relation that parses and says the wrong thing. See rule
    1d of docs/mojo/new-kernel-package-rules.md, "the three relations the grammar cannot say".

    `n <= len(v)` IS expressible and nothing here checks it, so it stays `[enforced]` and the
    pre-call guard keeps refusing an over-count with a typed error naming both numbers, which
    is more use to a caller than a clamped answer.

    An empty buffer has no percentile. `nan` would be the honest absence, but a NON-FINITE
    Float64 return currently ENDS THE WORKER PROCESS (measured: `compute_mean(five, 0)`
    returns `0.0/0.0` and the serving pid vanishes -- reported separately, it is a
    serialization defect, not a bounds one), so returning `nan` here would trade one process
    kill for another. `quantile` already answers 0.0 for "no finite values", so this follows
    the convention this module already publishes rather than inventing a second one.

    NAME-SIMILARITY HAZARD, DECLARED HERE RATHER THAN FIXED IN THE BODY: this is an O(1)
    lookup into a buffer the CALLER must have already sorted -- it does not call
    `sort_values` the way `quantile`/`percentile`/`median` do below. A caller who has not
    read this docstring and reaches for the name closest to "percentile" gets `pctile` and a
    confidently wrong, non-error number on unsorted input; nothing about the signature
    distinguishes it from the safe functions. That is precisely the failure mode an
    agentic/tool-calling caller is exposed to when a capability catalog offers `pctile`
    alongside `quantile`/`percentile` by name alone, with no way to know "pre-sorted" is a
    precondition. Per this module's frozen-kernel discipline the KERNEL does not change --
    same signature, same O(1) contract, same internal callers (`engines/monte_carlo.mojo`)
    keep working unmodified. The fix is `surfaces: internal` below, overriding this module's
    default `library_execute, batch_execute`: it removes `pctile` from the discoverable/
    agent-callable catalog (`algenta.capabilities()`, the capability-plane catalog) while
    leaving it fully reachable via a direct `runtime.execute("stats", "pctile", args)` call
    from a caller who already knows the pre-sorted precondition -- the same pattern
    `quantfin.heston` already uses at module scope for an unaudited surface.

    @capability pctile
    complexity: O(1)
    surfaces: internal
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    # The index is clamped to `>= 0`, so an EMPTY list is read at `v[0]` whatever `n` is --
    # an uncatchable bounds abort that ends the whole worker process. `n <= len(v)` cannot catch
    # it: `pctile([], 0, 50)` SATISFIES that relation (0 <= 0) and still ended the serving pid,
    # measured on a compiled shard. 0.0 is what `quantile` already answers for an empty input, so
    # the empty case gains no second spelling.
    if len(v) == 0: return 0.0
    return v[max(0, min((n-1)*p//100, n-1))]

def count_below_zero(v: List[Float64], n: Int) -> Int:
    """How many of the first `n` values are negative.

    Reads `v[i]` for `i` in `[0, n)` and nothing else; a non-positive `n` reads nothing. So
    `n <= len(v)` is complete, and an `Int` return has no non-finite spelling to trip over.

    @capability count_below_zero
    complexity: O(n)
    counts:
    - n <= len(v) [enforced]
    @endcapability
    """
    var c: Int = 0
    for i in range(n):
        if v[i] < 0.0: c += 1
    return c


# ── Introsort ─────────────────────────────────────────────────────────────────

def ins_sort(mut a: List[Float64], lo: Int, hi: Int):
    """Insertion-sort `a[lo..hi]` in place.

    `hi` is an INDEX, and an index is a bound too: the loop reads `a[i]` up to `i == hi`, so
    `hi + 1 <= len(a)` is one required condition. It is not the only one, and the previous
    version of this block got that wrong in the direction that kills the process. It recorded
    "`lo` is deliberately NOT declared: no element is read unconditionally at `lo`, and
    `lo > hi` merely makes the loop empty". Half of that is right -- `ins_sort(a, 0, -1)` is a
    measured no-op with the pid unchanged -- but it covers only `lo > hi`. A NEGATIVE `lo`
    makes `while j >= lo and a[j] > k` walk below zero, and `lo = -1` and `lo = -9` on a
    five-element list both ENDED the serving pid when measured. A written-down "there is no
    relation here" is worse than silence, because it stops the next reader from re-deriving it.

    Every index this reads or writes lies in `[lo, hi]`: `a[i]` for `i` in `(lo, hi]`, `a[j]`
    for `j >= lo`, and `a[j+1]` for `j+1 <= i <= hi`. So the true requirement is
    `0 <= lo` AND `hi <= len(a) - 1`, whenever `lo <= hi`.

    NOT EXPRESSIBLE IN THE COUNT-RELATION GRAMMAR, therefore checked here:

        0 <= lo              -- a lower bound; the grammar has `<=` and `==` against a
                                `len(...)` on the RIGHT and no way to bound a parameter below

    Because that half must be checked in the kernel, both conditions are checked here and the
    tags say `[kernel_validated]` rather than `[enforced]`. Splitting them -- guard-enforcing
    `hi` and kernel-checking `lo` -- would make the tag on the `hi` relation false, and it is
    also strictly worse for the caller: enforcing `lo + 1 <= len(a)` in the guard would refuse
    `ins_sort(a, 1000, 3)`, a no-op that is safe today, whereas validating here preserves it.
    Out-of-range indices are a no-op, which is what `lo > hi` already was.

    @capability ins_sort
    complexity: O((hi - lo)^2)
    counts:
    - lo + 1 <= len(a) [kernel_validated]
    - hi + 1 <= len(a) [kernel_validated]
    @endcapability
    """
    # `lo`/`hi` are direct SUBSCRIPTS, not counts, and Mojo does not normalise a negative
    # index: `a[-1]` is `index -1 is out of bounds` and the process ends. Measured: both
    # `ins_sort(five, -1, 4)` and `ins_sort(five, 0, 99)` ended the serving pid. A merely EMPTY
    # range (`hi < lo`) is left alone -- the loop runs zero times, which is already correct and
    # is what `fast_sort` relies on when it pushes `p-1` / `p+1`.
    if lo < 0 or lo >= len(a) or hi >= len(a): return
    # `lo >= len(a)` is checked as well as `lo < 0`, because `range(lo+1, ...)` WRAPS at
    # `lo == INT64_MAX` and would then iterate from `-2^63`. Rejecting it costs nothing: with
    # `lo >= len(a) > hi` the loop was already empty.
    for i in range(lo+1, hi+1):
        var k = a[i]; var j = i-1
        while j >= lo and a[j] > k: a[j+1] = a[j]; j -= 1
        a[j+1] = k

def ilog2(n: Int) -> Int:
    var r = 0; var x = n
    while x > 1: x >>= 1; r += 1
    return r

def part3(mut a: List[Float64], lo: Int, hi: Int) -> Int:
    """Median-of-3 partition of `a[lo..hi]`, returning the pivot's final index.

    Returns -1, an impossible index, for a range this cannot partition. Callers must test it;
    `fast_sort` below never sees it (see the arithmetic there).

    THREE conditions are required, and the two this block used to declare were the two that
    did not matter. It declared `lo + 1 <= len(a) [enforced]` and `hi + 1 <= len(a) [enforced]`
    and the guard enforced both -- and almost every pair that SATISFIES both still ended the
    worker. Measured on the compiled worker: `(0,0)`, `(0,1)`, `(1,1)`, `(2,2)`, `(3,4)` and
    `(4,4)` on a five-element list each passed the guard and the serving pid was gone; only
    `(0,4)` and `(0,2)` survived. Through `batch_execute` one such item took the whole frame,
    returning `compute_runtime_unavailable` for its three innocent neighbours too. A relation
    that is green for a call which aborts is worse than no relation, because a reader stops
    looking -- the same logic as rule 4d.

    What the reads actually require:

        0 <= lo              -- `a[lo]` is read unconditionally
        hi + 1 <= len(a)     -- `a[hi]` is read unconditionally
        lo + 2 <= hi         -- `a[hi-1]` is read unconditionally, AND the inner scans are
                                bounded ONLY by sentinels: the median-of-3 leaves `a[lo] <= piv`
                                and puts `piv` at `a[hi-1]`, so `while a[i] < piv` stops at
                                `i <= hi-1` and `while a[j] > piv` stops at `j >= lo`. Neither
                                sentinel exists unless the window holds at least three
                                elements. At `hi == lo + 1` the `j` scan walks to `a[lo-1]`;
                                at `hi == lo` the `a[hi-1]` swap itself reads `a[lo-1]`.

    Neither sentinel is ever swapped away: `i > lo` always, and `j <= hi-2` at every
    comparison, so the invariant holds for the whole loop rather than just its first pass.

    NOT EXPRESSIBLE IN THE COUNT-RELATION GRAMMAR, therefore checked here:

        0 <= lo              -- a lower bound
        lo + 2 <= hi         -- a relation between two PARAMETERS; the grammar's right side is
                                always a `len(...)`

    So the honest options were to extend the grammar or to stop claiming enforcement, and both
    missing conditions are of a shape the grammar cannot hold (see rule 1d of
    docs/mojo/new-kernel-package-rules.md, "the three relations the grammar cannot say"). The
    kernel now validates ALL THREE and the tags say `[kernel_validated]`. `[enforced]` on the
    two length relations would be false once the kernel checks them, and a guard that enforced
    only those two could never make this function safe no matter how correct it is.

    @capability part3
    complexity: O(hi - lo)
    counts:
    - lo + 1 <= len(a) [kernel_validated]
    - hi + 1 <= len(a) [kernel_validated]
    @endcapability
    """
    # The same subscript hazard as `ins_sort`, plus one more: this reads `a[hi-1]` and relies
    # on the pivot sitting there as a SENTINEL so the inner `while a[i] < piv` walk terminates.
    # With `hi < lo + 2` there is no room for the sentinel and the walk runs off the end.
    # Measured: `part3(five, -1, 4)`, `part3(five, 0, 99)`, `part3([], 0, 0)` and
    # `part3(five, 0, 1)` each ended the serving pid. -1 is returned because it is not a valid
    # partition point, so `fast_sort` cannot mistake it for one (and it only ever calls this with
    # `hi - lo > 16`, so the guard never fires on its path).
    if lo < 0 or hi < 0 or lo >= len(a) or hi >= len(a): return -1
    if hi < lo + 2: return -1
    # Both indices are bracketed BEFORE `lo + 2` is formed, because that addition wraps at
    # `lo == INT64_MAX` and a wrapped comparison would wave the call through. Once both are in
    # `[0, len(a)-1]` no term here can overflow.
    var mid = lo + (hi - lo) // 2
    if a[lo] > a[mid]:   var t = a[lo];  a[lo]  = a[mid]; a[mid] = t
    if a[lo] > a[hi]:    var t = a[lo];  a[lo]  = a[hi];  a[hi]  = t
    if a[mid] > a[hi]:   var t = a[mid]; a[mid] = a[hi];  a[hi]  = t
    var piv = a[mid]
    var t2 = a[mid]; a[mid] = a[hi-1]; a[hi-1] = t2
    var i = lo; var j = hi-1
    while True:
        i += 1
        while a[i] < piv: i += 1
        j -= 1
        while a[j] > piv: j -= 1
        if i >= j: break
        var t3 = a[i]; a[i] = a[j]; a[j] = t3
    var t4 = a[i]; a[i] = a[hi-1]; a[hi-1] = t4
    return i

def fast_sort(mut a: List[Float64], n: Int):
    """Introsort the first `n` elements of `a` in place.

    `n <= len(a)` is the complete requirement, and it is the one in this module that takes an
    argument to establish rather than a glance at a loop. `n <= 1` returns; `n <= 16` calls
    `ins_sort(a, 0, n-1)`, within range; otherwise every `(lo, hi)` pushed on the stack stays
    inside `[0, n-1]` because `part3` returns `p` in `(lo, hi)` and the pushes are
    `(lo, p-1)` and `(p+1, hi)`. Nothing here checks `n`, so `[enforced]` is true.

    `part3` is only called when `hi - lo > 16`, hence `hi >= lo + 17 >= lo + 2` with
    `0 <= lo` and `hi <= n-1 <= len(a)-1`: all three of its preconditions hold on every call
    from here, so its -1 sentinel is unreachable on this path and the checks it now performs
    are inert for the sort.

    @capability fast_sort
    complexity: O(n log n)
    counts:
    - n <= len(a) [enforced]
    @endcapability
    """
    if n <= 1:  return
    if n <= 16: ins_sort(a, 0, n-1); return
    var stk = List[Int](capacity=128)
    stk.append(0); stk.append(n-1); stk.append(2*ilog2(n))
    while len(stk) > 0:
        var d  = stk[len(stk)-1]
        var hi = stk[len(stk)-2]
        var lo = stk[len(stk)-3]
        stk.resize(len(stk)-3, 0)
        if hi <= lo: continue
        if hi - lo <= 16: ins_sort(a, lo, hi); continue
        if d == 0:  ins_sort(a, lo, hi); continue
        var p = part3(a, lo, hi)
        stk.append(lo);   stk.append(p-1); stk.append(d-1)
        stk.append(p+1);  stk.append(hi);  stk.append(d-1)


# ── Sorting order-statistics (sort a COPY — safe for UNSORTED input) ─────────────
# `pctile` above is the O(1) index-into-a-pre-sorted-buffer hot path (callers
# fast_sort first). The kernels below take raw UNSORTED input, sort a private
# copy, and never mutate the caller's list. `quantile`/`percentile`/`median` use
# linear interpolation to match numpy's default method and pandas .median()/.quantile().

def sort_values(v: List[Float64], n: Int) -> List[Float64]:
    """Ascending-sorted COPY of the FINITE values among the first n (drops NaN/+/-inf so a
    non-finite input degrades gracefully instead of crashing the worker; input untouched).
    Finite test: NaN fails x==x; +/-inf fails (x-x)==0 since inf-inf=NaN.

    `n` is CLAMPED to the list's real length. It is in the public runtime contract, so `n` is
    caller-supplied over the wire, and reading past a List end is an uncatchable abort that takes
    the whole worker process and every resident dataset with it — `library_execute stats.sort_values
    [[5 floats], 25]` killed the serving worker. The A-Z suite cannot catch this class: it calls
    every contract function with a 5-element list and 5 for every Int, so `n <= len(v)` always held.
    `quantile`, `percentile` and `median` all funnel through here, so one guard covers four exports.

    Clamped rather than refused-as-empty on purpose: `quantile` maps an empty result to 0.0, so
    returning empty would convert this crash into a SILENT WRONG ANSWER (a median of 0.0 for real
    data) for a caller who merely passed too large an `n`. Clamping answers the question actually
    asked -- the finite values among the first `n`, of which only `len(v)` exist.

    @capability sort_values
    complexity: O(n log n)
    counts:
    - n <= len(v) [clamped]
    @endcapability
    """
    var upto = n if n < len(v) else len(v)
    if upto < 0: upto = 0
    var cap = upto if upto > 0 else 1
    var a = List[Float64](capacity=cap)
    for i in range(upto):
        var x = v[i]
        if x == x and (x - x) == 0.0: a.append(x)
    fast_sort(a, len(a))
    return a^

def quantile(v: List[Float64], n: Int, q: Float64) -> Float64:
    """Linear-interpolated quantile of UNSORTED input, q in [0,1] (numpy 'linear'). Non-finite
    values are ignored; the rank is computed over the finite count.

    @capability quantile
    complexity: O(n log n)
    counts:
    - n <= len(v) [clamped]
    @endcapability
    """
    var a = sort_values(v, n)
    var m = len(a)
    if m == 0: return 0.0
    if m == 1: return a[0]
    var qq = q
    if qq < 0.0: qq = 0.0
    if qq > 1.0: qq = 1.0
    var rank = Float64(m - 1) * qq
    var lo = Int(rank)
    if lo >= m - 1: return a[m - 1]
    var frac = rank - Float64(lo)
    return a[lo] + frac * (a[lo + 1] - a[lo])

def percentile(v: List[Float64], n: Int, p: Int) -> Float64:
    """Linear-interpolated percentile of UNSORTED input, p in [0,100].

    @capability percentile
    complexity: O(n log n)
    counts:
    - n <= len(v) [clamped]
    @endcapability
    """
    return quantile(v, n, Float64(p) / 100.0)

def median(v: List[Float64], n: Int) -> Float64:
    """Median of UNSORTED input (mean of the two middle values for even n).

    @capability median
    complexity: O(n log n)
    counts:
    - n <= len(v) [clamped]
    @endcapability
    """
    return quantile(v, n, 0.5)
