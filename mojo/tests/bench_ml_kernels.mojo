"""Timing harness for the new ML kernels — reports ns per call so the
sklearn/scipy comparison (run from Python) has like-for-like numbers.
Not a test; prints [BENCH] lines."""

from time import perf_counter_ns
from calibration import isotonic_fit
from model_selection import walk_forward_splits
from model_compare import mcnemar_exact_p
from gbdt import gbdt_fit, gbdt_predict


fn _lcg_next(state: UInt64) -> UInt64:
    return state * UInt64(6364136223846793005) + UInt64(1442695040888963407)


fn _lcg_f64(state: UInt64) -> Float64:
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)


def main():
    # -- isotonic (PAV) fit on 50k monotone-noisy points ----------------------
    var n_iso = 50000
    var xs = List[Float64](capacity=n_iso)
    var ys = List[Float64](capacity=n_iso)
    var s = UInt64(12345)
    for i in range(n_iso):
        s = _lcg_next(s)
        xs.append(Float64(i))
        ys.append(Float64(i) * 0.001 + _lcg_f64(s) * 2.0 - 1.0)
    var t0 = perf_counter_ns()
    var fit = isotonic_fit(xs, ys)
    var t1 = perf_counter_ns()
    print("[BENCH] isotonic_fit n=50000:", Float64(t1 - t0) / 1e6, "ms | thresholds:", len(fit.thresholds))

    # -- walk-forward splits over 500k rows, 10 splits -------------------------
    t0 = perf_counter_ns()
    var splits = walk_forward_splits(500000, 10, 50000, True)
    t1 = perf_counter_ns()
    print("[BENCH] walk_forward_splits n=500000 k=10:", Float64(t1 - t0) / 1e6, "ms | splits:", len(splits))

    # -- McNemar exact on 1000 discordants -------------------------------------
    t0 = perf_counter_ns()
    var p: Float64 = 0.0
    for _ in range(100):
        p = mcnemar_exact_p(430, 570)
    t1 = perf_counter_ns()
    print("[BENCH] mcnemar_exact_p n_disc=1000 x100:", Float64(t1 - t0) / 1e6, "ms | p:", p)

    # -- GBDT: 5000 rows x 8 features, 50 trees depth 3 ------------------------
    var rows = 5000
    var feats = 8
    var X = List[Float64](capacity=rows * feats)
    var y = List[Float64](capacity=rows)
    s = UInt64(999)
    for i in range(rows):
        var acc: Float64 = 0.0
        for j in range(feats):
            s = _lcg_next(s)
            var v = _lcg_f64(s)
            X.append(v)
            if j < 3:
                acc += v
        s = _lcg_next(s)
        y.append(acc + _lcg_f64(s) * 0.1)
    t0 = perf_counter_ns()
    var model = gbdt_fit(X, y, feats, 50, 3, 0.1)
    t1 = perf_counter_ns()
    var fit_ms = Float64(t1 - t0) / 1e6
    t0 = perf_counter_ns()
    var acc: Float64 = 0.0
    for i in range(rows):
        var row = List[Float64](capacity=feats)
        for j in range(feats):
            row.append(X[i * feats + j])
        acc += gbdt_predict(model, row)
    t1 = perf_counter_ns()
    print("[BENCH] gbdt_fit 5000x8 trees=50 depth=3:", fit_ms, "ms | predict 5000 rows:", Float64(t1 - t0) / 1e6, "ms | mean:", acc / Float64(rows))
