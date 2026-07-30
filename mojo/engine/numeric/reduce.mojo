"""
numeric.reduce — the reductions, with nulls and empties handled once. Zero Python.

Every reduction returns `(value, present)`. `present == False` means "no answer
exists", which is different from `value == 0.0` and is the distinction the existing
paths lose when they return 0.0 for an empty group.

Nulls are carried in a parallel validity mask rather than by a sentinel value, so a
legitimate 0.0 and a missing value stay distinguishable — a sentinel cannot do that
without stealing a real value from the domain.

NaN and infinity are rejected on ingest rather than aggregated. Once a NaN enters a
sum, every downstream number is NaN and the report shows NaN where a figure belongs;
refusing it names the offending row while that information still exists.
"""
from std.math import isinf, isnan, sqrt

from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MEDIAN,
    AGG_MIN,
    AGG_STD,
    AGG_SUM,
    AGG_VAR,
)


struct Reduction(Copyable, Movable):
    """A reduction outcome. `present == False` means no answer exists."""

    var value: Float64
    var present: Bool
    var n: Int

    fn __init__(out self, value: Float64, present: Bool, n: Int):
        self.value = value
        self.present = present
        self.n = n


fn absent(n: Int) -> Reduction:
    return Reduction(0.0, False, n)


fn is_finite_value(value: Float64) -> Bool:
    return not isnan(value) and not isinf(value)


fn first_non_finite(values: List[Float64], valid: List[Bool]) -> Int:
    """Index of the first non-finite live value, or -1.

    Called before reducing so the failure names a row rather than surfacing as a NaN
    in the result.
    """
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        if not is_finite_value(values[i]):
            return i
    return -1


fn count_valid(valid: List[Bool]) -> Int:
    var n = 0
    for i in range(len(valid)):
        if valid[i]:
            n += 1
    return n


fn _is_live(valid: List[Bool], index: Int) -> Bool:
    """Whether position `index` is present, for a mask that may be shorter than the values.

    A position with NO mask entry is absent, not present. That is the conservative
    reading and — more importantly — it is the same reading
    `columnar.array.float64_with_nulls` uses. These two functions sit one package apart
    and used to disagree: `reduce` counted an unmasked tail as live while
    `float64_with_nulls` marked it absent, so handing a short mask to both produced two
    different answers over the same data with nothing to indicate it.

    Callers with genuinely no nulls should pass `all_valid(len(values))` rather than
    an empty list.
    """
    if index < 0 or index >= len(valid):
        return False
    return valid[index]


fn reduce_sum(values: List[Float64], valid: List[Bool]) -> Reduction:
    var total: Float64 = 0.0
    var n = 0
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        total += values[i]
        n += 1
    # Sum of nothing is 0 — that is an answer, not a missing one.
    return Reduction(total, True, n)


fn reduce_count(valid: List[Bool]) -> Reduction:
    var n = count_valid(valid)
    return Reduction(Float64(n), True, n)


fn reduce_mean(values: List[Float64], valid: List[Bool]) -> Reduction:
    """Welford's online mean — one definition of "average", everywhere.

    Chosen over `sum/n` because it is numerically stable for long or wide-magnitude
    inputs, and because having exactly one implementation is the point: three
    different means is how the current divergence arose.
    """
    var mean: Float64 = 0.0
    var n = 0
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        n += 1
        mean += (values[i] - mean) / Float64(n)
    if n == 0:
        return absent(0)
    return Reduction(mean, True, n)


fn reduce_min(values: List[Float64], valid: List[Bool]) -> Reduction:
    var best: Float64 = 0.0
    var n = 0
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        if n == 0 or values[i] < best:
            best = values[i]
        n += 1
    if n == 0:
        return absent(0)
    return Reduction(best, True, n)


fn reduce_max(values: List[Float64], valid: List[Bool]) -> Reduction:
    var best: Float64 = 0.0
    var n = 0
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        if n == 0 or values[i] > best:
            best = values[i]
        n += 1
    if n == 0:
        return absent(0)
    return Reduction(best, True, n)


fn reduce_variance(values: List[Float64], valid: List[Bool]) -> Reduction:
    """Sample variance (n-1) via Welford. Undefined below two observations."""
    var mean: Float64 = 0.0
    var m2: Float64 = 0.0
    var n = 0
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        n += 1
        var delta = values[i] - mean
        mean += delta / Float64(n)
        m2 += delta * (values[i] - mean)
    if n < 2:
        # One observation has no spread; reporting 0.0 would assert certainty that
        # the data does not support.
        return absent(n)
    return Reduction(m2 / Float64(n - 1), True, n)


fn reduce_stddev(values: List[Float64], valid: List[Bool]) -> Reduction:
    var variance = reduce_variance(values, valid)
    if not variance.present:
        return absent(variance.n)
    return Reduction(sqrt(variance.value), True, variance.n)


fn reduce_median(values: List[Float64], valid: List[Bool]) -> Reduction:
    """Median of the live values; the mean of the middle pair when even.

    Sorts a copy — the caller's list is never reordered, since an aggregation that
    mutates its input is a trap for anything that reads the column afterwards.
    """
    var live = List[Float64]()
    for i in range(len(values)):
        if not _is_live(valid, i):
            continue
        live.append(values[i])
    var n = len(live)
    if n == 0:
        return absent(0)

    for i in range(1, n):
        var j = i
        while j > 0 and live[j] < live[j - 1]:
            var swap = live[j]
            live[j] = live[j - 1]
            live[j - 1] = swap
            j -= 1

    if n % 2 == 1:
        return Reduction(live[n // 2], True, n)
    return Reduction((live[n // 2 - 1] + live[n // 2]) / 2.0, True, n)


fn reduce(opcode: Int, values: List[Float64], valid: List[Bool]) -> Reduction:
    """Dispatch to a reduction by opcode. Unknown opcodes yield absent."""
    if opcode == AGG_SUM:
        return reduce_sum(values, valid)
    if opcode == AGG_AVG:
        return reduce_mean(values, valid)
    if opcode == AGG_MIN:
        return reduce_min(values, valid)
    if opcode == AGG_MAX:
        return reduce_max(values, valid)
    if opcode == AGG_COUNT:
        return reduce_count(valid)
    if opcode == AGG_VAR:
        return reduce_variance(values, valid)
    if opcode == AGG_STD:
        return reduce_stddev(values, valid)
    if opcode == AGG_MEDIAN:
        return reduce_median(values, valid)
    return absent(0)


fn all_valid(n: Int) -> List[Bool]:
    """A mask marking every position live — for callers with no nulls."""
    var mask = List[Bool]()
    for _ in range(n):
        mask.append(True)
    return mask^
