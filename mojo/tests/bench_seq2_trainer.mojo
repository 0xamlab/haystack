"""Timing harness for the seq2 2-layer LSTM trainer — reports ms/epoch on a
realistic slice (2000 sequences, seq_len 22, input_dim 11, hidden 32,
dense 32, batch 64, 5 epochs) so the keras/CPU-TF comparison has
like-for-like numbers. Compares scalar single-thread BPTT vs SIMD
single-thread vs SIMD parallel. Not a test; prints [BENCH] lines."""

from std.time import perf_counter_ns
from std.sys import info
from seq2_trainer import seq2_init, seq2_train_workers, seq2_train_scalar


def _lcg_next(state: UInt64) -> UInt64:
    return state * UInt64(6364136223846793005) + UInt64(1442695040888963407)


def _lcg_f64(state: UInt64) -> Float64:
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)


def main():
    var n_seq = 2000
    var T = 22
    var D = 11
    var H = 32
    var Dh = 32
    var epochs = 5
    var batch = 64
    var lr = 0.001

    # synthetic but learnable: y = f(last-step features) + noise
    var s = UInt64(20260725)
    var x = List[Float64](capacity=n_seq * T * D)
    var y = List[Float64](capacity=n_seq)
    for _ in range(n_seq):
        var acc: Float64 = 0.0
        for t in range(T):
            for d in range(D):
                s = _lcg_next(s)
                var v = _lcg_f64(s) * 2.0 - 1.0
                x.append(v)
                if t == T - 1 and d < 4:
                    acc += v
        s = _lcg_next(s)
        y.append(0.25 * acc + 0.05 * (_lcg_f64(s) * 2.0 - 1.0))
    var empty = List[Float64]()
    var params = seq2_init(D, H, Dh, 42)
    var cores = info.num_physical_cores()

    # -- scalar single-thread baseline (non-SIMD build of the same loop) ------
    var t0 = perf_counter_ns()
    var r_sc = seq2_train_scalar(
        params, x, y, n_seq, T, D, empty, empty, 0, epochs, batch, lr, 0.0, 0, 7
    )
    var t1 = perf_counter_ns()
    var sc_ms = Float64(t1 - t0) / 1e6 / Float64(epochs)
    print(
        "[BENCH] seq2_train SCALAR 1-thread n=2000 T=22 D=11 H=32 batch=64:",
        sc_ms,
        "ms/epoch | final loss:",
        r_sc.train_loss[len(r_sc.train_loss) - 1],
    )

    # -- SIMD single-thread ----------------------------------------------------
    t0 = perf_counter_ns()
    var r_st = seq2_train_workers(
        params, x, y, n_seq, T, D, empty, empty, 0, epochs, batch, lr, 0.0, 0, 7, 1
    )
    t1 = perf_counter_ns()
    var st_ms = Float64(t1 - t0) / 1e6 / Float64(epochs)
    print(
        "[BENCH] seq2_train SIMD   1-thread n=2000 T=22 D=11 H=32 batch=64:",
        st_ms,
        "ms/epoch | final loss:",
        r_st.train_loss[len(r_st.train_loss) - 1],
    )

    # -- SIMD parallel (all physical cores) ------------------------------------
    t0 = perf_counter_ns()
    var r_par = seq2_train_workers(
        params, x, y, n_seq, T, D, empty, empty, 0, epochs, batch, lr, 0.0, 0, 7,
        cores,
    )
    t1 = perf_counter_ns()
    var par_ms = Float64(t1 - t0) / 1e6 / Float64(epochs)
    print(
        "[BENCH] seq2_train SIMD",
        cores,
        "workers n=2000 T=22 D=11 H=32 batch=64:",
        par_ms,
        "ms/epoch | final loss:",
        r_par.train_loss[len(r_par.train_loss) - 1],
    )

    # -- SIMD parallel, 8 workers (the 8-core target box) -----------------------
    t0 = perf_counter_ns()
    var r_p8 = seq2_train_workers(
        params, x, y, n_seq, T, D, empty, empty, 0, epochs, batch, lr, 0.0, 0, 7, 8
    )
    t1 = perf_counter_ns()
    var p8_ms = Float64(t1 - t0) / 1e6 / Float64(epochs)
    print(
        "[BENCH] seq2_train SIMD   8 workers n=2000 T=22 D=11 H=32 batch=64:",
        p8_ms,
        "ms/epoch | final loss:",
        r_p8.train_loss[len(r_p8.train_loss) - 1],
    )

    print(
        "[BENCH] speedups vs scalar 1-thread: SIMD 1-thread",
        sc_ms / st_ms,
        "x | SIMD 8-worker",
        sc_ms / p8_ms,
        "x | SIMD",
        cores,
        "-worker",
        sc_ms / par_ms,
        "x",
    )
