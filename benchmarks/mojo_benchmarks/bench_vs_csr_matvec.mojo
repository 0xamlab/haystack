"""bench_vs_csr_matvec — the SHIPPED SpMV entry point, BEFORE against AFTER.

Why this file exists
--------------------
`spmv.spmv_matvec` -> `csr.csr_matvec` is the API a caller actually reaches, and it was
measured at 3.35-7.15 ns per nonzero against scipy's 0.39-1.34 — a 4x to 8x loss on every
size and every sparsity pattern. A previous round added a fast UNCHECKED kernel beside it
and left the checked entry alone, so the loss stayed exactly where callers meet it.

There is no `unchecked` SpMV entry point in `sparse_numerics.spmv` -- only `spmv_matvec`
and the arithmetic it wraps, `csr.csr_matvec`. This file times those two, BEFORE against
AFTER, plus a verbatim copy of the pre-change implementation.

Before changing anything, the call was split by stage on a 4.7M-nonzero band matrix, with
the stages INTERLEAVED (a first attempt ran each stage to completion and reported
`csr_matvec` as faster than the `csr_validate` it contains — an impossible ordering that
was purely a load spike). That split:

    csr_matvec total                    5.17 ns/nnz
      of which csr_validate             1.52   (29.5%)
      of which the multiply itself      0.62   (12.0%)
      of which List overhead            3.02   (58.5%)  <- the largest share
    spmv_matvec wrapper on top          0.03   ( 0.6%)

The 58.5% was neither the arithmetic nor the gate: it was one bounds-checked
`List.__getitem__` per `values[k]`, per `indices[k]` and per `x[...]`, plus `out.append`
growing an unreserved list. Worth recording that the wrapper's `values.copy()` had been
named as a cause and is 0.6% — attribution by measurement, not by reading.

What is compared
----------------
`old_*` below are verbatim copies of the two functions as they shipped. They run in the
SAME process as the new ones, alternating one repetition at a time with the order rotated
each round, because on a host at load 100 with seventy other Mojo processes a ratio taken
across two processes measures the machine.

Every timed arm folds its result into a checksum that is printed. Without that the
pointer-store multiply is dead code and can be optimised away entirely — which is what
produced the impossible ordering above before a sink was added. Bit-exactness against the
old arm is asserted before any clock starts.

`BENCH_GATE csr_matvec PASS|FAIL <n>` where n counts arms that failed their own dispersion
check; an INVALID arm prints no ns/nnz and contributes no ratio.
"""
from std.time import perf_counter_ns
from sparse_numerics.csr import (
    CSRMatrix,
    csr_matvec,
    csr_validate,
    CSR_OK,
    CSR_ERR_SHAPE,
    CSR_ERR_LENGTH_MISMATCH,
    CSR_ERR_INDPTR_LENGTH,
    CSR_ERR_INDPTR_START,
    CSR_ERR_INDPTR_NOT_MONOTONIC,
    CSR_ERR_INDPTR_TAIL,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_DIMENSION_TOO_LARGE,
    MAX_CSR_DIM,
)
from sparse_numerics.spmv import spmv_matvec

comptime MAX_SPREAD: Float64 = 2.0
comptime MAX_MAXMIN_SPREAD: Float64 = 8.0
comptime ROUNDS: Int = 9


def splitmix64(seed: UInt64) -> UInt64:
    var z = seed + 0x9E3779B97F4A7C15
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)


# ── the BEFORE arms, verbatim ─────────────────────────────────────────────────


def old_csr_validate_flat(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> Int:
    """`csr.csr_validate_flat` as it shipped: a scalar, bounds-checked index scan."""
    if nrows < 0 or ncols < 0:
        return CSR_ERR_SHAPE
    if nrows > MAX_CSR_DIM or ncols > MAX_CSR_DIM:
        return CSR_ERR_DIMENSION_TOO_LARGE
    if len(indices) != len(values):
        return CSR_ERR_LENGTH_MISMATCH
    if len(indptr) != nrows + 1:
        return CSR_ERR_INDPTR_LENGTH
    if indptr[0] != 0:
        return CSR_ERR_INDPTR_START
    for i in range(1, nrows + 1):
        if indptr[i] < indptr[i - 1]:
            return CSR_ERR_INDPTR_NOT_MONOTONIC
    if indptr[nrows] != len(values):
        return CSR_ERR_INDPTR_TAIL
    for k in range(len(indices)):
        if indices[k] < 0 or indices[k] >= ncols:
            return CSR_ERR_INDEX_OUT_OF_RANGE
    return CSR_OK


def old_csr_validate(m: CSRMatrix) -> Int:
    return old_csr_validate_flat(m.indptr, m.indices, m.values, m.nrows, m.ncols)


def old_csr_matvec(m: CSRMatrix, x: List[Float64]) -> List[Float64]:
    """`csr.csr_matvec` as it shipped: validate, then a bounds-checked appending loop."""
    var status = old_csr_validate(m)
    if status != CSR_OK:
        return List[Float64]()
    if len(x) != m.ncols:
        return List[Float64]()
    var out = List[Float64]()
    for i in range(m.nrows):
        var acc = 0.0
        for k in range(m.indptr[i], m.indptr[i + 1]):
            acc += m.values[k] * x[m.indices[k]]
        out.append(acc)
    return out^


# ── matrices ──────────────────────────────────────────────────────────────────


def build_band9(nrows: Int) -> CSRMatrix:
    """Nine-point band. The gather is local, so this is the pattern where a fraction of
    streaming bandwidth is even meaningful."""
    var indptr = List[Int](unsafe_uninit_length=nrows + 1)
    var indices = List[Int]()
    var values = List[Float64]()
    indptr[0] = 0
    for i in range(nrows):
        for d in range(-4, 5):
            var j = i + d
            if j >= 0 and j < nrows:
                indices.append(j)
                values.append(0.5 + Float64(d) * 0.125)
        indptr[i + 1] = len(indices)
    return CSRMatrix(indptr^, indices^, values^, nrows, nrows, True, True)


def build_scatter(nrows: Int, per_row: Int) -> CSRMatrix:
    """Columns drawn across the whole space, so `x` does NOT stay cache-resident and the
    dependent gather actually pays. Indices ascending per row, as the layout requires."""
    var indptr = List[Int](unsafe_uninit_length=nrows + 1)
    var indices = List[Int]()
    var values = List[Float64]()
    indptr[0] = 0
    for i in range(nrows):
        var placed = List[Int]()
        for d in range(per_row):
            var j = Int(splitmix64(UInt64(i) * 1_000_003 + UInt64(d)) % UInt64(nrows))
            var dup = False
            for q in range(len(placed)):
                if placed[q] == j:
                    dup = True
            if not dup:
                placed.append(j)
        for a in range(len(placed)):
            for b in range(a + 1, len(placed)):
                if placed[b] < placed[a]:
                    var t = placed[a]
                    placed[a] = placed[b]
                    placed[b] = t
        for a in range(len(placed)):
            indices.append(placed[a])
            values.append(
                Float64(splitmix64(UInt64(i) * 7919 + UInt64(a)) >> 11)
                * (1.0 / 9007199254740992.0)
            )
        indptr[i + 1] = len(indices)
    return CSRMatrix(indptr^, indices^, values^, nrows, nrows, True, True)


def median_of(var xs: List[Int]) -> Int:
    for i in range(1, len(xs)):
        var v = xs[i]
        var j = i - 1
        while j >= 0 and xs[j] > v:
            xs[j + 1] = xs[j]
            j -= 1
        xs[j + 1] = v
    return xs[len(xs) // 2]


@fieldwise_init
struct Cell(Copyable, Movable):
    var cold: Int
    var warm: Int
    var hot: Int
    var med: Int
    var mx: Int


def summarise(samples: List[Int]) -> Cell:
    var cold = samples[0]
    var warm = samples[1] if len(samples) > 1 else samples[0]
    var hot = 0
    var mx = 0
    var rest = List[Int]()
    for i in range(1, len(samples)):
        rest.append(samples[i])
        if hot == 0 or samples[i] < hot:
            hot = samples[i]
        if samples[i] > mx:
            mx = samples[i]
    if len(rest) == 0:
        hot = cold
        mx = cold
        rest.append(cold)
    return Cell(cold, warm, hot, median_of(rest^), mx)


def gate_reason(c: Cell) -> String:
    """Names every condition that FAILED, and only those."""
    var reason = String("")
    if c.hot > c.warm:
        reason += "hot>warm "
    var med_spread = Float64(c.med) / Float64(c.hot)
    if med_spread > MAX_SPREAD:
        reason += "median/min " + String(med_spread) + ">" + String(MAX_SPREAD) + " "
    var mm = Float64(c.mx) / Float64(c.hot)
    if mm > MAX_MAXMIN_SPREAD:
        reason += "max/min " + String(mm) + ">" + String(MAX_MAXMIN_SPREAD) + " "
    return reason


def main():
    print("bench_vs_csr_matvec: shipped SpMV entry, BEFORE vs AFTER")
    print("rounds", ROUNDS, "gate median/min <=", MAX_SPREAD, " max/min <=", MAX_MAXMIN_SPREAD)
    print("")
    print("case            nnz        old_validate old_matvec  new_validate new_matvec  wrapper | validate_x  matvec_x")

    var invalid = 0
    for case_index in range(6):
        var m: CSRMatrix
        var label = String("")
        if case_index == 0:
            m = build_band9(8_192)
            label = String("band9_8k")
        elif case_index == 1:
            m = build_band9(65_536)
            label = String("band9_64k")
        elif case_index == 2:
            m = build_band9(524_288)
            label = String("band9_512k")
        elif case_index == 3:
            m = build_band9(2_097_152)
            label = String("band9_2m")
        elif case_index == 4:
            m = build_scatter(65_536, 40)
            label = String("scatter_64k")
        else:
            m = build_scatter(524_288, 32)
            label = String("scatter_512k")

        var nnz = m.nnz()
        var ncols = m.ncols
        var x = List[Float64](unsafe_uninit_length=ncols)
        for i in range(ncols):
            x[i] = 1.0 + Float64(i % 17) * 0.03125

        # ── correctness before any clock ──────────────────────────────────────
        var ref_vals = old_csr_matvec(m, x)
        var new_res = csr_matvec(m, x)
        var wrap_res = spmv_matvec(m, x)
        var mismatch = 0
        if new_res.status != CSR_OK or len(ref_vals) != new_res.length:
            mismatch += 1
        else:
            for i in range(len(ref_vals)):
                # Bit-exact: the accumulation order is unchanged, so anything other than
                # equality is a defect, not a rounding difference.
                if ref_vals[i] != new_res.values[i]:
                    mismatch += 1
                    break
            for i in range(len(ref_vals)):
                if ref_vals[i] != wrap_res.values[i]:
                    mismatch += 1
                    break
        if old_csr_validate(m) != csr_validate(m):
            mismatch += 1
        if mismatch != 0:
            print(label, "*** RESULT DISAGREES -- no timing reported ***")
            invalid += 1
            continue

        var ov = List[Int]()
        var om = List[Int]()
        var nv = List[Int]()
        var nm = List[Int]()
        var wr = List[Int]()
        var sink = 0.0
        var status_sink = 0

        for rd in range(ROUNDS):
            for slot in range(5):
                var arm = (slot + rd) % 5
                if arm == 0:
                    var t0 = perf_counter_ns()
                    var s = old_csr_validate(m)
                    var t1 = perf_counter_ns()
                    ov.append(Int(t1 - t0))
                    status_sink += s
                elif arm == 1:
                    var t0 = perf_counter_ns()
                    var r = old_csr_matvec(m, x)
                    var t1 = perf_counter_ns()
                    om.append(Int(t1 - t0))
                    sink += r[0] + r[len(r) - 1]
                elif arm == 2:
                    var t0 = perf_counter_ns()
                    var s = csr_validate(m)
                    var t1 = perf_counter_ns()
                    nv.append(Int(t1 - t0))
                    status_sink += s
                elif arm == 3:
                    var t0 = perf_counter_ns()
                    var r = csr_matvec(m, x)
                    var t1 = perf_counter_ns()
                    nm.append(Int(t1 - t0))
                    sink += r.values[0] + r.values[r.length - 1]
                else:
                    var t0 = perf_counter_ns()
                    var r = spmv_matvec(m, x)
                    var t1 = perf_counter_ns()
                    wr.append(Int(t1 - t0))
                    sink += r.values[0] + r.values[r.length - 1]

        var covr = summarise(ov)
        var comr = summarise(om)
        var cnvr = summarise(nv)
        var cnmr = summarise(nm)
        var cwr = summarise(wr)

        var r_ov = gate_reason(covr)
        var r_om = gate_reason(comr)
        var r_nv = gate_reason(cnvr)
        var r_nm = gate_reason(cnmr)
        var r_wr = gate_reason(cwr)
        for t in range(5):
            var rr = r_ov
            if t == 1:
                rr = r_om
            elif t == 2:
                rr = r_nv
            elif t == 3:
                rr = r_nm
            elif t == 4:
                rr = r_wr
            if len(rr) != 0:
                invalid += 1

        def cellstr(c: Cell, reason: String, denom: Int) -> String:
            if len(reason) != 0:
                return String("INVALID")
            return String(Float64(c.hot) / Float64(denom))

        var vx = String("no ratio")
        if len(r_ov) == 0 and len(r_nv) == 0:
            vx = String(Float64(covr.hot) / Float64(cnvr.hot)) + "x"
        var mx_ = String("no ratio")
        if len(r_om) == 0 and len(r_nm) == 0:
            mx_ = String(Float64(comr.hot) / Float64(cnmr.hot)) + "x"

        print(
            label,
            nnz,
            cellstr(covr, r_ov, nnz),
            cellstr(comr, r_om, nnz),
            cellstr(cnvr, r_nv, nnz),
            cellstr(cnmr, r_nm, nnz),
            cellstr(cwr, r_wr, nnz),
            "|",
            vx,
            mx_,
            "sink=" + String(sink != 0.0),
            "st=" + String(status_sink),
        )
        print(
            "COLD_WARM_HOT",
            "csrmatvec_new_" + label,
            Float64(cnmr.cold) / Float64(nnz),
            Float64(cnmr.warm) / Float64(nnz),
            Float64(cnmr.hot) / Float64(nnz),
            "ns/nnz",
        )
        for t in range(5):
            var nm_ = String("old_validate")
            var rr = r_ov
            if t == 1:
                nm_ = String("old_matvec")
                rr = r_om
            elif t == 2:
                nm_ = String("new_validate")
                rr = r_nv
            elif t == 3:
                nm_ = String("new_matvec")
                rr = r_nm
            elif t == 4:
                nm_ = String("wrapper")
                rr = r_wr
            if len(rr) != 0:
                print("   ", label, nm_, "INVALID --", rr, "; no ns/nnz, no ratio")

    print("")
    if invalid == 0:
        print("BENCH_GATE csr_matvec PASS")
    else:
        print("BENCH_GATE csr_matvec FAIL", invalid)
