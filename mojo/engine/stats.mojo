"""
Statistics utilities and introsort (iterative, median-of-3, stack-safe).
"""
from std.math import sqrt


def compute_mean(v: List[Float64], n: Int) -> Float64:
    var t: Float64 = 0.0
    for i in range(n): t += v[i]
    return t / Float64(n)

def compute_variance(v: List[Float64], n: Int, mean: Float64) -> Float64:
    if n <= 1: return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        var d = v[i] - mean; s += d * d
    return s / Float64(n - 1)

def pctile(v: List[Float64], n: Int, p: Int) -> Float64:
    return v[max(0, min((n-1)*p//100, n-1))]

def count_below_zero(v: List[Float64], n: Int) -> Int:
    var c: Int = 0
    for i in range(n):
        if v[i] < 0.0: c += 1
    return c


# ── Introsort ─────────────────────────────────────────────────────────────────

def ins_sort(mut a: List[Float64], lo: Int, hi: Int):
    for i in range(lo+1, hi+1):
        var k = a[i]; var j = i-1
        while j >= lo and a[j] > k: a[j+1] = a[j]; j -= 1
        a[j+1] = k

def ilog2(n: Int) -> Int:
    var r = 0; var x = n
    while x > 1: x >>= 1; r += 1
    return r

def part3(mut a: List[Float64], lo: Int, hi: Int) -> Int:
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
    Finite test: NaN fails x==x; +/-inf fails (x-x)==0 since inf-inf=NaN."""
    var cap = n if n > 0 else 1
    var a = List[Float64](capacity=cap)
    for i in range(n):
        var x = v[i]
        if x == x and (x - x) == 0.0: a.append(x)
    fast_sort(a, len(a))
    return a^

def quantile(v: List[Float64], n: Int, q: Float64) -> Float64:
    """Linear-interpolated quantile of UNSORTED input, q in [0,1] (numpy 'linear'). Non-finite
    values are ignored; the rank is computed over the finite count."""
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
    """Linear-interpolated percentile of UNSORTED input, p in [0,100]."""
    return quantile(v, n, Float64(p) / 100.0)

def median(v: List[Float64], n: Int) -> Float64:
    """Median of UNSORTED input (mean of the two middle values for even n)."""
    return quantile(v, n, 0.5)
