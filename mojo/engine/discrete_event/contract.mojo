"""
discrete_event.contract — the package's one vocabulary. Zero Python imports.

Everything that more than one module in `discrete_event` needs to agree about lives here and
nowhere else: the status codes, the ceilings, the work budget, the two named RNG streams and
the event-ordering contract. Rule 3 applies inside a package: `optimization/` shipped
`_finite` six times, byte-identical and private in every file, and the copies then enforced
one declared invariant at three different strengths under three different codes. One
definition, one place.

Finiteness and the tolerance builder are IMPORTED from `inference.core` rather than re-spelled.
That module is already a dependency (its Student-t quantile is what turns replications into a
confidence interval), and a second definition of "finite" is how two modules in one answer path
end up disagreeing about whether a number exists.

The ordering contract
---------------------
`de_event_order()` returns the identifier of the rule the calendar implements. It is a
FUNCTION, not a comment, because the rule is the simulation's determinism: two events at the
same timestamp must resolve in a defined order or the same seed gives different answers, and a
caller storing a result needs to record which rule produced it. `discrete_event.calendar`
asserts its own `de_key_less` against this identifier's meaning in its suite.

Bounds, and why there are two kinds
-----------------------------------
`DE_MAX_*` bound ALLOCATION. `DE_MAX_WORK` bounds OPERATIONS, and they are not the same
check: a request can sit inside every allocation ceiling and still drive minutes of loop
iterations, which from the caller's side is indistinguishable from the uncatchable abort that
`DE_ERR_COUNT` exists to prevent. So every driver here charges the work its loops actually do
— `n` events times the heap depth `n` implies, replications times customers times that depth —
and refuses `DE_ERR_WORK_BUDGET` before starting rather than partway through.

The products are formed by DIVISION (`de_product_fits`), never by multiplying and comparing:
`3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic, so a multiply is not a bound at
all. `sparse_numerics.csr.dims_fit` is the frozen precedent and this is the same shape.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from determinism.counter_rng import rng_version
from determinism.streams import stream_id
from inference.core import (
    inference_finite,
    inference_scaled_tol,
    inference_scaled_tol_ulps,
)

# ── status codes: discrete_event owns 400-419 ─────────────────────────────────
# One code per defect, because a caller that gets a refusal needs to know WHICH of its
# arguments is wrong. A single "invalid" would send it looking at all seven. Rule 4e: the
# range is recorded here and no other file in this package defines a status constant.

comptime DE_OK: Int = 400
comptime DE_ERR_NON_FINITE: Int = 401
comptime DE_ERR_EMPTY: Int = 402
comptime DE_ERR_COUNT: Int = 403
comptime DE_ERR_DIMENSION_TOO_LARGE: Int = 404
comptime DE_ERR_WORK_BUDGET: Int = 405
comptime DE_ERR_TIME_BACKWARD: Int = 406
comptime DE_ERR_CAPACITY: Int = 407
comptime DE_ERR_RATE_RANGE: Int = 408
comptime DE_ERR_UNSTABLE: Int = 409
comptime DE_ERR_TOO_FEW: Int = 410
comptime DE_ERR_NO_STEADY_STATE: Int = 411
comptime DE_ERR_TOO_FEW_REPS: Int = 412
comptime DE_ERR_LEVEL_RANGE: Int = 413
comptime DE_ERR_PRIORITY_RANGE: Int = 414
comptime DE_ERR_SEED_RANGE: Int = 415
comptime DE_ERR_WARMUP_RANGE: Int = 416
comptime DE_ERR_NEGATIVE_DURATION: Int = 417
comptime DE_ERR_BATCH_RANGE: Int = 418
comptime DE_ERR_NO_ESTIMATE: Int = 419

# ── allocation ceilings ───────────────────────────────────────────────────────
# A calendar entry is five parallel 8-byte slots (time, priority, sequence, kind, entity) =
# 40 bytes, and `calendar_replay_flat` also materialises a five-array trace of what it popped
# = another 40 bytes per event. So the ceiling costs 80 bytes per event, and 2^20 events is
# ~84 MB — one object inside the 512 MiB resident-dataset budget that
# `algenta_runtime.session` already treats as the outer limit, with room for the caller's
# input arrays beside it. Rule 1c: this is `k` arrays per unit, counted, not assumed.
comptime DE_MAX_EVENTS: Int = 1 << 20

# A resource run allocates three per-JOB result arrays (wait, start, depart) and schedules
# exactly two events per job, so jobs are capped an order of magnitude below events: 2^18 jobs
# = 2^19 events (inside DE_MAX_EVENTS) and 3 x 2^18 x 8 = 6.3 MB of returned arrays.
comptime DE_MAX_JOBS: Int = 1 << 18

# Capacity allocates NOTHING — free servers are a counter, not an array — so this ceiling is
# not a memory bound. It exists because utilisation divides by capacity, and a capacity of
# 10^18 makes the ratio meaningless rather than wrong.
comptime DE_MAX_SERVERS: Int = 1 << 16

comptime DE_MAX_REPLICATIONS: Int = 1 << 12
comptime DE_MAX_OBS: Int = 1 << 20
comptime DE_MAX_BATCH: Int = 1 << 16

# A priority is a RANK, not a subscript: nothing is indexed by it. It is bounded anyway so
# that the ordering key stays in a range where `Int` comparison is the whole story, and
# negative ranks are refused rather than silently accepted as "extremely urgent".
comptime DE_MAX_PRIORITY: Int = 1 << 20

# ── the work budget ───────────────────────────────────────────────────────────
# Charged operations, not bytes. 2^27 is about a tenth of a second of heap sifting at this
# tree's measured rate, which keeps the worst accepted request inside a request timeout
# instead of inside a hang.
comptime DE_MAX_WORK: Int = 1 << 27

comptime DE_DBL_EPSILON: Float64 = 2.220446049250313e-16

# `inference_scaled_tol` returns this for a non-finite or negative magnitude, and every
# `error > tol` test in this package reads it as "refuse".
comptime DE_TOL_UNDEFINED: Float64 = -1.0


def de_status_name(code: Int) -> String:
    """Name for a status code, so a refusal surfaces the defect and not a bare number.


    @capability de_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == DE_OK:
        return "ok"
    if code == DE_ERR_NON_FINITE:
        return "non_finite_input"
    if code == DE_ERR_EMPTY:
        return "empty_input"
    if code == DE_ERR_COUNT:
        return "count_exceeds_list_length"
    if code == DE_ERR_DIMENSION_TOO_LARGE:
        return "dimension_above_ceiling"
    if code == DE_ERR_WORK_BUDGET:
        return "work_budget_exceeded"
    if code == DE_ERR_TIME_BACKWARD:
        return "event_time_before_clock"
    if code == DE_ERR_CAPACITY:
        return "capacity_out_of_range"
    if code == DE_ERR_RATE_RANGE:
        return "rate_out_of_range"
    if code == DE_ERR_UNSTABLE:
        return "no_steady_state_utilisation_at_or_above_one"
    if code == DE_ERR_TOO_FEW:
        return "too_few_observations"
    if code == DE_ERR_NO_STEADY_STATE:
        return "transient_never_settled_within_the_run"
    if code == DE_ERR_TOO_FEW_REPS:
        return "too_few_replications_for_an_interval"
    if code == DE_ERR_LEVEL_RANGE:
        return "confidence_level_out_of_range"
    if code == DE_ERR_PRIORITY_RANGE:
        return "priority_out_of_range"
    if code == DE_ERR_SEED_RANGE:
        return "seed_or_replication_negative"
    if code == DE_ERR_WARMUP_RANGE:
        return "warmup_count_out_of_range"
    if code == DE_ERR_NEGATIVE_DURATION:
        return "negative_service_duration"
    if code == DE_ERR_BATCH_RANGE:
        return "batch_size_out_of_range"
    if code == DE_ERR_NO_ESTIMATE:
        return "estimate_does_not_exist"
    return "unknown_status"


def de_finite(v: Float64) -> Bool:
    """True for a real number — neither NaN nor an infinity.

    A one-line delegation to `inference.core.inference_finite` ON PURPOSE. This package needs
    one name for the predicate its callers see, and it must not be a second implementation:
    the moment two spellings exist they can disagree, and "does this answer exist" is exactly
    the question that must not have two answers. Named here so a reader of a `discrete_event`
    guard does not have to know which sibling package owns the definition.

    @capability de_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return inference_finite(v)


def de_absent() -> Float64:
    """The value written into a quantity slot whose `has_*` flag is False: exactly 0.0.

    NOT a NaN, which is what a scalar-only helper would return. The dispatch REFUSES to
    serialise a non-finite Float64, so a struct field holding one turns the entire response
    into a typed error — one absent quantity would erase eleven present ones. So the value
    slot is always representable and THE FLAG IS THE ANSWER. `0.0` alone would be the
    silent-wrong-answer this rule exists to prevent, which is why no driver here returns a
    bare value without its flag.

    @capability de_absent
    complexity: O(1)
    counts: none
    @endcapability
    """
    return 0.0


def de_scaled_tol(quantity_magnitude: Float64, abs_tol: Float64) -> Float64:
    """`abs_tol + 256 * DBL_EPSILON * |quantity_magnitude|`, from `inference.core`.

    `quantity_magnitude` must be the magnitude of THE ONE QUANTITY BEING JUDGED. Never a sum
    or a maximum over other items (a `Σ|b_i|` scale let 200 ordinary rows swallow a flat
    contradiction and an infeasible LP returned OPTIMAL), never a `1 + |x|` floor (which is an
    absolute allowance of one whole unit dressed as a relative one), and never the caller's
    tolerance multiplied by a magnitude.

    @capability de_scaled_tol
    complexity: O(1)
    counts: none
    @endcapability
    """
    return inference_scaled_tol(quantity_magnitude, abs_tol)


def de_scaled_tol_additions(
    quantity_magnitude: Float64, abs_tol: Float64, additions: Int
) -> Float64:
    """The same tolerance, widened by one ulp per floating-point addition that built the value.

    Used for exactly one comparison in this package: the time-average number in system is
    accumulated over `2n` event intervals while the sum of sojourn times is accumulated over
    `n` jobs. The two are mathematically identical over a completed window, and differ only by
    the rounding of two different summation ORDERS — a discrepancy that genuinely grows with
    the number of additions. `optimization.explain` set the precedent and
    `inference.core.inference_scaled_tol_ulps` is the frozen implementation.

    A negative `additions` widens nothing (clamped to zero), so a nonsense count cannot loosen
    a comparison.

    @capability de_scaled_tol_additions
    complexity: O(1)
    counts: none
    @endcapability
    """
    var extra = additions
    if extra < 0:
        extra = 0
    return inference_scaled_tol_ulps(quantity_magnitude, abs_tol, Float64(extra))


def de_event_order() -> String:
    """The identifier of the calendar's tie-breaking rule. Deterministic, zero-argument.

    `time,priority,sequence/v1`: events pop in increasing time; at equal time, in increasing
    priority rank (0 is most urgent); at equal time AND priority, in increasing insertion
    sequence, which is a monotone counter that is never reused. The third key makes the order
    TOTAL — no two calendar entries can ever compare equal — so the pop order is a function of
    the input alone and a fixed seed reproduces bit-for-bit.

    Returned as a value rather than left in a comment because a stored result has to be able
    to name the rule that produced it. Changing any of the three keys, or their order, changes
    every simulation this package has ever run, which is why the identifier is versioned.

    @capability de_event_order
    complexity: O(1)
    counts: none
    @endcapability
    """
    return String("time,priority,sequence/v1")


def de_rng_version() -> String:
    """The frozen generator contract behind every draw, from `determinism.counter_rng`.

    Reported back by the run drivers so a stored estimate names the generator that produced
    it. A result that cannot be reproduced is not a result.

    @capability de_rng_version
    complexity: O(1)
    counts: none
    @endcapability
    """
    return rng_version()


def de_stream_arrival() -> Int:
    """The independent RNG stream id for inter-arrival draws.

    Derived by NAME through `determinism.streams.stream_id`, not hardcoded: an integer picked
    by hand collides with whoever picked it first and the two streams silently stop being
    independent, with nothing failing. Returned as `Int` because that is what crosses the
    wire; the generator takes `UInt64` and the conversion is upward from a value the frozen
    kernel guarantees is in [8, 65534].

    @capability de_stream_arrival
    complexity: O(1)
    counts: none
    @endcapability
    """
    return Int(stream_id("discrete_event.interarrival"))


def de_stream_service() -> Int:
    """The independent RNG stream id for service-time draws.

    Separate from the arrival stream so that changing an arrival distribution does not shift a
    single service time. That is what makes two configurations comparable on common random
    numbers, and `queue_sim` returns `total_service_time` so the property is measurable rather
    than promised.

    @capability de_stream_service
    complexity: O(1)
    counts: none
    @endcapability
    """
    return Int(stream_id("discrete_event.service"))


def de_heap_levels(n: Int) -> Int:
    """`floor(log2(n)) + 1` — the depth of a binary heap holding `n` entries, or 0 for none.

    Computed by doubling rather than by a floating-point logarithm: this number multiplies
    into a work budget, and a budget derived from a rounding of `log2` is a budget that can be
    off by a whole level at the exact power of two where it matters. Verified against the
    definition at the boundaries — 1, 2, 3, 4, 7, 8 give 1, 2, 2, 3, 3, 4 — which is where an
    off-by-one in either direction would hide.

    @capability de_heap_levels
    complexity: O(log n)
    counts: none
    @endcapability
    """
    if n <= 0:
        return 0
    var levels = 1
    var span = 2
    while span <= n:
        span += span
        levels += 1
    return levels


def de_product_fits(a: Int, b: Int, limit: Int) -> Bool:
    """True when `a * b <= limit`, decided WITHOUT forming the product.

    `a * b` is a wrapping 64-bit multiply, so comparing it against a limit is not a bound:
    `3 * 6148914691236517206 == 2` passes any ceiling. Division cannot wrap.

    @capability de_product_fits
    complexity: O(1)
    counts: none
    @endcapability
    """
    if a < 0 or b < 0 or limit < 0:
        return False
    if a == 0 or b == 0:
        return True
    return a <= limit // b


def de_product3_fits(a: Int, b: Int, c: Int, limit: Int) -> Bool:
    """True when `a * b * c <= limit`, grown factor by factor so no intermediate wraps.


    @capability de_product3_fits
    complexity: O(1)
    counts: none
    @endcapability
    """
    if a < 0 or b < 0 or c < 0 or limit < 0:
        return False
    if a == 0 or b == 0 or c == 0:
        return True
    if not de_product_fits(a, b, limit):
        return False
    return a * b <= limit // c


def de_heap_work_fits(n_events: Int) -> Bool:
    """True when pushing and popping `n_events` entries fits the work budget.

    Each entry is pushed once and popped once, and each operation sifts at most one heap depth,
    so the charge is `2 * n_events * de_heap_levels(n_events)`. Charging only `n_events` would
    be the defect that measured 0.49s against 23.89s at identical declared cost: the depth is a
    factor of the real product and a budget that counts one factor of a product is not a
    budget.

    @capability de_heap_work_fits
    complexity: O(log n_events)
    counts: none
    @endcapability
    """
    if n_events < 0:
        return False
    return de_product_fits(2 * n_events, de_heap_levels(n_events), DE_MAX_WORK)


def de_heap_work(n_events: Int) -> Int:
    """The charge `de_heap_work_fits` tests, so a report can carry what it was charged.

    Returns -1 when the charge does not fit, rather than a wrapped product: a work figure that
    wrapped would read as a small cost for an enormous request.

    @capability de_heap_work
    complexity: O(log n_events)
    counts: none
    @endcapability
    """
    if not de_heap_work_fits(n_events):
        return -1
    return 2 * n_events * de_heap_levels(n_events)


def de_ceilings() -> List[Int]:
    """Every declared ceiling, in one call, so a caller can size a request before sending it.

    Order is fixed and documented: events, jobs, servers, replications, observations, batch
    size, priority, work. Appending a new ceiling is additive; reordering is not.

    @capability de_ceilings
    complexity: O(1)
    counts: none
    @endcapability
    """
    var out = List[Int]()
    out.append(DE_MAX_EVENTS)
    out.append(DE_MAX_JOBS)
    out.append(DE_MAX_SERVERS)
    out.append(DE_MAX_REPLICATIONS)
    out.append(DE_MAX_OBS)
    out.append(DE_MAX_BATCH)
    out.append(DE_MAX_PRIORITY)
    out.append(DE_MAX_WORK)
    return out^


def de_all_finite(values: List[Float64], n: Int) -> Bool:
    """True when the FIRST `n` entries are all finite, and `n` is a length the list has.

    The count is checked before any read, because `n > len(values)` is not a wrong answer — it
    is an uncatchable bounds abort that takes the whole worker process and every resident
    dataset with it, and `try`/`except` at any layer above does not help. A negative `n` reads
    nothing and is answered True for the empty prefix it names.


    @capability de_all_finite
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n > len(values):
        return False
    for i in range(n):
        if not de_finite(values[i]):
            return False
    return True


def de_nondecreasing(values: List[Float64], n: Int) -> Bool:
    """True when the first `n` entries never decrease. Count checked before any read.

    Used by `resource.resource_serve_flat` on its arrival list: an arrival stream out of time
    order has no well-defined truncation point, and inventing one would put the warm-up cut at
    an arbitrary place in the run.


    @capability de_nondecreasing
    complexity: O(n)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n > len(values):
        return False
    for i in range(1, n):
        if values[i] < values[i - 1]:
            return False
    return True


def de_agrees(quantity: Float64, reference: Float64, abs_tol: Float64, additions: Int) -> Bool:
    """True when `quantity` equals `reference` to within a tolerance built from `quantity`.

    `quantity` is the number being judged and is therefore the only magnitude the tolerance is
    allowed to come from — not the reference, not a sum over other quantities, not a `1 + |x|`
    floor. `additions` widens it by one ulp per floating-point addition that built `quantity`,
    for the one case in this package where two mathematically identical sums are accumulated in
    different orders.

    Returns FALSE — refuse — when either side is non-finite or the tolerance is undefined.
    That direction is deliberate: a NaN defeats an unvalidated threshold silently, because
    `gap > nan` is False and an audit then passes having counted zero violations. There is no
    `Float64` this can return instead: an "undefined gap" of `0.0` reads as perfect agreement
    and a negative one reads as inside any tolerance, so the verdict is a `Bool` and the caller
    keeps its own `has_*` flag for whether the comparison was possible at all.

    @capability de_agrees
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not de_finite(quantity) or not de_finite(reference):
        return False
    var tol = de_scaled_tol_additions(quantity, abs_tol, additions)
    if tol < 0.0 or not de_finite(tol):
        return False
    var d = quantity - reference
    if not de_finite(d):
        return False
    return fabs(d) <= tol
